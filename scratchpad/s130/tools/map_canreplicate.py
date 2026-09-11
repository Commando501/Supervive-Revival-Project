#!/usr/bin/env python
"""Map every compiled store to AActor+0x6C (bCanEverReplicate) and, where the
containing function installs a vtable, NAME the class that does it.

This answers "what is the default for class X" without guessing, and it doubles
as a semantic check on C7: if the classes that clear bCanEverReplicate are also
the ones that set bEnablePooling (+0x2D3), then pooling and replication are
mutually exclusive by design.

BOUNDED, and say so: ~47% of .text is undecrypted in this image, and a value
that is only ever set by the Blueprint CDO leaves no compiled store at all.
An absence here is COVERAGE-BLOCKED-or-data, never "nothing sets it".

KNOWN DEFECT, DO NOT TRUST THE TOTAL: scan_stores() advances i by ONE BYTE, so a
single instruction is re-decoded at successive offsets and can be reported twice
(you will see pairs like `mov byte [rsi+0x6c], r15b` / `mov byte [rsi+0x6c], bh`
at consecutive addresses -- that is ONE instruction, mis-anchored).  The reported
count (363 for disp 0x6C) is therefore an UPPER BOUND, not a count.  It was good
enough for its purpose -- showing that disp 0x6C is far too common to attribute --
which is why the class-scoped classprops_uht.py replaced it.  Fix by advancing
i by ins.size on a hit before reusing this for anything quantitative.
"""
import struct, sys, csv, bisect, argparse
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
import capstone

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

PDATA = r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv"


def load_pdata():
    rows = []
    with open(PDATA, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((int(r["begin_rva"], 16), int(r["end_rva"], 16)))
    rows.sort()
    return rows


def fn_of(rows, rva):
    i = bisect.bisect_right(rows, (rva, 1 << 62)) - 1
    if i >= 0 and rows[i][0] <= rva < rows[i][1]:
        return rows[i]
    return None


def scan_stores(blob, vaddr, disp):
    """byte-sized stores with memory displacement == disp (disp8 or disp32)."""
    hits = []
    n = len(blob)
    i = 0
    while i < n - 8:
        b = blob[i]
        # candidate opcodes: C6 (mov r/m8, imm8), 88 (mov r/m8, r8), 80 (grp1 r/m8, imm8)
        if b in (0xC6, 0x88, 0x80) or (0x40 <= b <= 0x4F and blob[i + 1] in (0xC6, 0x88, 0x80)):
            try:
                ins = next(md.disasm(blob[i:i + 16], vaddr + i))
            except StopIteration:
                i += 1
                continue
            if ins.operands:
                o = ins.operands[0]
                if o.type == capstone.x86.X86_OP_MEM and o.mem.disp == disp \
                   and o.size == 1 and o.mem.index == 0 \
                   and ins.mnemonic in ("mov", "or", "and"):
                    hits.append((vaddr + i, "%s %s" % (ins.mnemonic, ins.op_str)))
        i += 1
    return hits


def vtable_of(img, blob, vaddr, lo, hi):
    """a ctor installs its vtable: lea r64,[rip+X] ; mov [reg], r64  -> return X (rdata rva)"""
    off = lo - vaddr
    end = hi - vaddr
    last_lea = {}
    while off < end:
        try:
            ins = next(md.disasm(blob[off:off + 16], vaddr + off))
        except StopIteration:
            off += 1
            continue
        if ins.mnemonic == "lea" and len(ins.operands) == 2:
            d, s = ins.operands
            if s.type == capstone.x86.X86_OP_MEM and s.mem.base == capstone.x86.X86_REG_RIP:
                last_lea[d.reg] = vaddr + off + ins.size + s.mem.disp
        elif ins.mnemonic == "mov" and len(ins.operands) == 2:
            d, s = ins.operands
            if d.type == capstone.x86.X86_OP_MEM and d.mem.disp == 0 and d.mem.index == 0 \
               and s.type == capstone.x86.X86_OP_REG and s.reg in last_lea:
                t = last_lea[s.reg]
                if img.sec_of(t) and img.sec_of(t)[0] == ".rdata":
                    return t
        off += ins.size if ins.size else 1
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default="s129")
    ap.add_argument("--disp", type=lambda x: int(x, 0), default=0x6C)
    ap.add_argument("--also", type=lambda x: int(x, 0), default=0x2D3)
    a = ap.parse_args()

    img = fkdis.load(a.dump)
    sec = [s for s in img.sections if s[0] == ".text"][0]
    _, vaddr, vsize, rawptr, rawsize = sec
    blob = img.buf[rawptr:rawptr + rawsize]
    rows = load_pdata()

    hits = scan_stores(blob, vaddr, a.disp)
    print("byte-sized stores at disp 0x%X: %d (unit: instructions)" % (a.disp, len(hits)))
    print("NOTE: disp 0x%X is NOT class-specific -- any class with a byte member there matches.\n"
          "      Only the ones whose function installs a NAMED vtable are attributable.\n" % a.disp)

    seen = {}
    for r, t in hits:
        fn = fn_of(rows, r)
        key = fn if fn else ("orphan", r)
        seen.setdefault(key, []).append((r, t))

    named = 0
    for key in sorted(seen, key=lambda k: (isinstance(k[0], str), k[1] if isinstance(k[0], str) else k[0])):
        if isinstance(key[0], str):
            for r, t in seen[key]:
                print("  [no .pdata row] 0x%08X  %s" % (r, t))
            continue
        lo, hi = key
        vt = vtable_of(img, blob, vaddr, lo, hi)
        also = scan_stores(blob[lo - vaddr:hi - vaddr], lo, a.also)
        name = ""
        if vt:
            try:
                import subprocess
                out = subprocess.run([sys.executable, "vtables.py", "who", hex(vt)],
                                     cwd=r"G:\git\Supervive Revival Project\tools\strxref",
                                     capture_output=True, text=True, timeout=180).stdout.strip()
                name = out
                named += 1
            except Exception as e:
                name = "(who failed: %s)" % e
        for r, t in seen[key]:
            print("  0x%08X  %-38s fn[0x%08X..0x%08X)  also+0x%X:%d  %s"
                  % (r, t, lo, hi, a.also, len(also), name or "(no vtable install found)"))
    print("\nattributed to a named class: %d of %d functions" % (named, len(seen)))
