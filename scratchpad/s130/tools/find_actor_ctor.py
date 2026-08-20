#!/usr/bin/env python
"""Find AActor's constructor by its member-initialiser run, then read the
compile-time default of the byte at AActor+0x6C (bCanEverReplicate).

METHOD (the same one that found ALokiGameState's ctor default at 0x5676F10):
  a constructor writes its members with literal displacements in a dense,
  mostly-ascending run.  Anchor on a RARE offset that is provably AActor's --
  bEnablePooling at +0x2D3, which needs a disp32 and so has a distinctive
  encoding -- then look in the same function for the write to +0x6C.

Positive controls, all of which must appear in the SAME function:
  +0x2D3  bEnablePooling      [M] AActor property, SetBitFunc mov byte [rcx+0x2d3],1
  +0x68   bAlwaysRelevant / bHidden bitfield byte  [M]
  +0x6C   bCanEverReplicate   [M] the target

Prints every byte-sized store at disp 0x6C found in the winning function, and
its immediate, so the default is READ rather than assumed.
"""
import struct, sys, argparse
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
import capstone

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True


def text_blob(img):
    for name, vaddr, vsize, rawptr, rawsize in img.sections:
        if name == ".text":
            return img.buf[rawptr:rawptr + rawsize], vaddr
    raise SystemExit("no .text")


def scan_disp32_bytestore(blob, vaddr, disp):
    """find `mov byte ptr [reg+disp32], imm8` -> C6 8x <disp32le> ii"""
    pat = b"\xc6" + bytes([0]) # placeholder
    hits = []
    d32 = struct.pack("<i", disp)
    i = 0
    while True:
        i = blob.find(d32, i)
        if i < 0:
            break
        for back in (2, 3):           # C6 8x | REX C6 8x
            s = i - back
            if s < 0:
                continue
            try:
                ins = next(md.disasm(blob[s:s + 16], vaddr + s))
            except StopIteration:
                continue
            if ins.mnemonic != "mov" or not ins.operands:
                continue
            o = ins.operands[0]
            if o.type == capstone.x86.X86_OP_MEM and o.mem.disp == disp and o.size == 1:
                hits.append((vaddr + s, "%s %s" % (ins.mnemonic, ins.op_str)))
                break
        i += 1
    return hits


def stores_at(blob, vaddr, lo, hi, disp):
    """every byte-sized store whose memory displacement == disp, within [lo,hi)"""
    out = []
    off = lo - vaddr
    end = hi - vaddr
    while off < end:
        try:
            ins = next(md.disasm(blob[off:off + 16], vaddr + off))
        except StopIteration:
            off += 1
            continue
        if ins.operands:
            o = ins.operands[0]
            if o.type == capstone.x86.X86_OP_MEM and o.mem.disp == disp and o.size == 1 \
               and ins.mnemonic in ("mov", "or", "and"):
                out.append((vaddr + off, "%s %s" % (ins.mnemonic, ins.op_str)))
        off += ins.size if ins.size else 1
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default="s129")
    a = ap.parse_args()
    img = fkdis.load(a.dump)
    blob, vaddr = text_blob(img)

    print("== anchor: byte stores at disp 0x2D3 (bEnablePooling, AActor-specific) ==")
    anchors = scan_disp32_bytestore(blob, vaddr, 0x2D3)
    for r, t in anchors:
        print("  0x%08X  %s" % (r, t))
    if not anchors:
        raise SystemExit("no anchor found -- method failed, do NOT guess")

    # resolve each anchor to its containing function via the .pdata union
    import csv
    rows = []
    with open(r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv",
              newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((int(r["begin_rva"], 16), int(r["end_rva"], 16)))
    rows.sort()

    def fn_of(rva):
        import bisect
        i = bisect.bisect_right(rows, (rva, 1 << 62)) - 1
        if i >= 0 and rows[i][0] <= rva < rows[i][1]:
            return rows[i]
        return None

    print("\n== for each anchor's function: does it also write +0x68 and +0x6C? ==")
    for r, t in anchors:
        fn = fn_of(r)
        if not fn:
            print("  0x%08X : no .pdata row" % r)
            continue
        lo, hi = fn
        s68 = stores_at(blob, vaddr, lo, hi, 0x68)
        s6c = stores_at(blob, vaddr, lo, hi, 0x6C)
        print("  anchor 0x%08X  fn [0x%08X..0x%08X) %d B   +0x68:%d  +0x6C:%d"
              % (r, lo, hi, hi - lo, len(s68), len(s6c)))
        for x, y in s68:
            print("        +0x68  0x%08X  %s" % (x, y))
        for x, y in s6c:
            print("     >> +0x6C  0x%08X  %s   <== bCanEverReplicate DEFAULT" % (x, y))
