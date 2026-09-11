#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FK-22 LINE 1 -- grade ULokiBlueprintLibrary::ServerOnly's IMPL, offline.

Method (each step controlled):
  1. Find the .data native-registration record {const char* Name, thunk, impl}
     by scanning .data for a qword that points at the ASCII string "ServerOnly"
     in .rdata.  Layout validated in the SAME PASS on two known-good records:
        0x9C1F298 = {"GoToPhase",  0x5457200, 0x5601020}
        0x9C1F328 = {"OnNewPhase", 0x5457480, 0x330C56C}
  2. Disassemble the thunk, take its LAST DIRECT call, EXCLUDING the security
     cookie 0x751DEB0 (which will mis-grade gold if forgotten).
  3. Read that target's bytes and grade REAL / EMPTY-STUB / CONST-BODY /
     COVERAGE-BLOCKED (all-zero page = never demand-decrypted, NOT empty).
  4. Gold controls in the same pass:
        EMPTY : ALokiGameMode::SpawnPlayer               thunk 0x534C070 -> impl 0x0F7EB50
        REAL  : ALokiServerAnalyticsManager::AddTeamDropEvent  impl 0x557EAE0 (926 B)
  5. Fold multiplicity = count of qword pointers to the impl IMAGE-WIDE
     (a self-built registration table under-counts; image-wide is the honest count).

⚠ .data is mutable -> read registration records from SINGLE-STATE dumps only,
  never dumps/merged2.dump.exe (which splices .data under -wholeimage).
"""
import os, struct, sys, glob
import capstone

ROOT = r"G:\git\Supervive Revival Project"
FOLDS = {
    0x0F7EC20: "ret 0            (c2 00 00)",
    0x0F7EB50: "xor eax,eax; ret (33 c0 c3)",
    0x0F7EB60: "xor al,al;   ret (32 c0 c3)",
}
COOKIE = 0x751DEB0


class Img:
    def __init__(self, path):
        self.path = path
        self.buf = open(path, "rb").read()
        pe = struct.unpack_from("<I", self.buf, 0x3C)[0]
        assert self.buf[pe:pe + 4] == b"PE\0\0"
        opt = pe + 0x18
        self.base = struct.unpack_from("<Q", self.buf, opt + 0x18)[0]
        nsec = struct.unpack_from("<H", self.buf, pe + 6)[0]
        optsz = struct.unpack_from("<H", self.buf, pe + 0x14)[0]
        self.secs = []
        for i in range(nsec):
            o = pe + 0x18 + optsz + i * 40
            name = self.buf[o:o + 8].rstrip(b"\0").decode("latin1")
            va = struct.unpack_from("<I", self.buf, o + 12)[0]
            vsz = struct.unpack_from("<I", self.buf, o + 8)[0]
            raw = struct.unpack_from("<I", self.buf, o + 20)[0]
            rsz = struct.unpack_from("<I", self.buf, o + 16)[0]
            self.secs.append((name, va, vsz, raw, rsz))

    def sec(self, rva):
        for s in self.secs:
            if s[1] <= rva < s[1] + max(s[2], s[4]):
                return s
        return None

    def read(self, rva, n):
        # dumpimage output is FLAT: file offset == RVA.
        return self.buf[rva:rva + n]

    def zero_page(self, rva):
        p = rva & ~0xFFF
        return self.buf[p:p + 0x1000] == b"\0" * 0x1000


def disasm(img, rva, maxb=0x400):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False
    out = []
    for ins in md.disasm(img.read(rva, maxb), rva):
        out.append((ins.address, ins.mnemonic, ins.op_str, ins.size))
        if ins.mnemonic in ("ret", "jmp") and not ins.op_str.startswith("qword"):
            # keep going a little past a jmp only if it is a tail call target we
            # still want; simplest: stop at ret / unconditional direct jmp
            break
        if ins.mnemonic == "ret":
            break
    return out


def last_direct_call(img, thunk_rva, exclude=(COOKIE,)):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    calls = []
    tail = None
    for ins in md.disasm(img.read(thunk_rva, 0x400), thunk_rva):
        if ins.mnemonic == "call" and ins.op_str.startswith("0x"):
            t = int(ins.op_str, 16)
            if t not in exclude:
                calls.append((ins.address, t))
        if ins.mnemonic == "jmp" and ins.op_str.startswith("0x"):
            t = int(ins.op_str, 16)
            if t not in exclude:
                tail = (ins.address, t)
            break
        if ins.mnemonic == "ret":
            break
    return calls, tail


def grade(img, rva):
    if rva is None:
        return "UNRESOLVED", b""
    if img.sec(rva) is None:
        return "OUT-OF-IMAGE", b""
    b = img.read(rva, 16)
    if img.zero_page(rva):
        return "COVERAGE-BLOCKED (all-zero page = never demand-decrypted)", b
    if rva in FOLDS:
        return "EMPTY-STUB / fold %s" % FOLDS[rva], b
    for f, d in FOLDS.items():
        if b[:3] == img.read(f, 3) and b[3:4] in (b"\xc3", b"\x00") and len(set(b[:3])) <= 3:
            pass
    return "REAL-or-CONST (needs body read)", b


def find_string_rva(img, s):
    """all RVAs of the exact NUL-terminated ASCII string s"""
    pat = s.encode() + b"\0"
    hits = []
    start = 0
    while True:
        i = img.buf.find(pat, start)
        if i < 0:
            break
        # must be preceded by a NUL (string start) and live in a real section
        if i > 0 and img.buf[i - 1] == 0 and img.sec(i):
            hits.append(i)
        start = i + 1
    return hits


def find_qword_refs(img, val, secname=None):
    hits = []
    pat = struct.pack("<Q", val)
    start = 0
    while True:
        i = img.buf.find(pat, start)
        if i < 0:
            break
        s = img.sec(i)
        if s and (secname is None or s[0] == secname) and (i % 8 == 0):
            hits.append(i)
        start = i + 1
    return hits


def record_at(img, rva):
    q = struct.unpack_from("<QQQ", img.buf, rva)
    name_rva = q[0] - img.base if q[0] > img.base else None
    nm = ""
    if name_rva and img.sec(name_rva):
        raw = img.read(name_rva, 64)
        nm = raw.split(b"\0")[0].decode("latin1", "replace")
    thunk = q[1] - img.base if q[1] > img.base else None
    impl = q[2] - img.base if q[2] > img.base else None
    return nm, thunk, impl


def main():
    single = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")
    img = Img(single)
    print("IMAGE %s  base=0x%X" % (single, img.base))
    for s in img.secs:
        print("   sec %-8s rva=0x%08X vsz=0x%X" % (s[0], s[1], s[2]))
    print()

    # --- layout validation on two KNOWN records --------------------------------
    print("=== layout validation (known-good records) ===")
    for rva in (0x9C1F298, 0x9C1F328, 0x9BBAFB8):
        print("  .data 0x%07X -> %r" % (rva, record_at(img, rva)))
    print()

    # --- find "ServerOnly" string + every .data qword pointing at it ------------
    print("=== locate ServerOnly registration record ===")
    for s in ("ServerOnly", "ClientOnly"):
        srvs = find_string_rva(img, s)
        print("  string %-12s rvas=%s" % (s, [hex(x) for x in srvs]))
        for sv in srvs:
            refs = find_qword_refs(img, img.base + sv)
            for r in refs:
                sec = img.sec(r)
                print("     ref @ %-7s 0x%07X -> record %r" % (sec[0], r, record_at(img, r)))
    print()


if __name__ == "__main__":
    main()


def hexs(b):
    return " ".join("%02x" % x for x in b)


def show_fn(img, rva, n=64, label=""):
    print("  %-46s rva=0x%07X  sec=%s  zeropage=%s" % (
        label, rva, (img.sec(rva) or ("?",))[0], img.zero_page(rva)))
    print("     bytes: %s" % hexs(img.read(rva, 24)))
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cnt = 0
    for ins in md.disasm(img.read(rva, n), rva):
        print("     %07X  %-9s %s" % (ins.address, ins.mnemonic, ins.op_str))
        cnt += 1
        if ins.mnemonic in ("ret", "jmp"):
            break
        if cnt > 40:
            break


def part2():
    single = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")
    img = Img(single)

    print("\n=== STEP 2: thunk disassembly + last direct call ===")
    targets = {
        "ULokiBlueprintLibrary::ServerOnly": 0x52E12B0,
        "GOLD-EMPTY ALokiGameMode::SpawnPlayer": 0x534C070,
        "GOLD-REAL  GoToPhase (control)": 0x5457200,
    }
    resolved = {}
    for lbl, thunk in targets.items():
        print("\n-- %s : thunk 0x%07X" % (lbl, thunk))
        show_fn(img, thunk, 0x200, "thunk")
        calls, tail = last_direct_call(img, thunk)
        print("     direct calls (cookie 0x%07X excluded): %s" % (
            COOKIE, [(hex(a), hex(t)) for a, t in calls]))
        print("     tail jmp: %s" % (tail and (hex(tail[0]), hex(tail[1]))))
        impl = calls[-1][1] if calls else (tail[1] if tail else None)
        resolved[lbl] = impl
        print("     ==> IMPL = %s" % (impl and hex(impl)))

    print("\n=== STEP 3: impl bodies ===")
    bodies = dict(resolved)
    bodies["GOLD-REAL AddTeamDropEvent (impl direct)"] = 0x557EAE0
    for lbl, impl in bodies.items():
        if impl is None:
            print("\n-- %s : UNRESOLVED" % lbl)
            continue
        print("\n-- %s" % lbl)
        show_fn(img, impl, 0x40, "impl")
        print("     GRADE: %s" % grade(img, impl)[0])
    return resolved


def part3(resolved):
    print("\n=== STEP 4: multi-image presence (18 images) ===")
    paths = sorted(glob.glob(os.path.join(ROOT, "dumps", "*.dump.exe")) +
                   glob.glob(os.path.join(ROOT, "dumps", "*", "*.dump.exe")))
    check = {
        "ServerOnly IMPL 0x1311870": 0x1311870,
        "ServerOnly THUNK 0x52E12B0": 0x52E12B0,
        "GOLD-EMPTY 0x0F7EB50": 0x0F7EB50,
        "GOLD-REAL  0x557EAE0": 0x557EAE0,
    }
    for lbl, rva in check.items():
        seen = {}
        for p in paths:
            try:
                i = Img(p)
            except Exception:
                continue
            b = i.read(rva, 8)
            seen.setdefault(hexs(b), []).append(os.path.basename(os.path.dirname(p)) or os.path.basename(p))
        print("  %-28s across %d images:" % (lbl, len(paths)))
        for k, v in seen.items():
            print("      %-24s x%d  %s" % (k, len(v), ",".join(v[:6]) + ("..." if len(v) > 6 else "")))

    print("\n=== STEP 5: fold multiplicity (image-wide qword pointers) ===")
    single = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")
    img = Img(single)
    for lbl, rva in [("ServerOnly IMPL 0x1311870", 0x1311870),
                     ("ServerOnly THUNK 0x52E12B0", 0x52E12B0),
                     ("fold 0xF7EC20 (ret 0)", 0x0F7EC20),
                     ("fold 0xF7EB50", 0x0F7EB50),
                     ("GOLD-REAL 0x557EAE0", 0x557EAE0),
                     ("execFoo thunk 0x5254180 (known 91-way)", 0x5254180)]:
        refs = find_qword_refs(img, img.base + rva)
        bysec = {}
        for r in refs:
            bysec[img.sec(r)[0]] = bysec.get(img.sec(r)[0], 0) + 1
        print("  %-42s qword ptrs = %-4d  %s" % (lbl, len(refs), bysec))

    print("\n=== STEP 6: rel32 direct CALL/JMP sites to the impl (decrypted .text only) ===")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for lbl, rva in [("ServerOnly IMPL 0x1311870", 0x1311870)]:
        n = 0
        # scan for e8/e9 rel32 whose target == rva, over .text
        s = img.sec(rva)
        tstart, tsz = 0x1000, 0x7649000
        buf = img.buf
        i = tstart
        end = tstart + tsz - 5
        hits = []
        while i < end:
            j = buf.find(b"\xe8", i, end)
            k = buf.find(b"\xe9", i, end)
            cand = min(x for x in (j, k) if x >= 0) if (j >= 0 or k >= 0) else -1
            if cand < 0:
                break
            disp = struct.unpack_from("<i", buf, cand + 1)[0]
            if cand + 5 + disp == rva:
                hits.append(cand)
            i = cand + 1
        print("  %-28s rel32 e8/e9 sites landing on it = %d (byte-level, not instruction-aligned)" % (lbl, len(hits)))
        print("      first 12: %s" % [hex(h) for h in hits[:12]])


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "full":
    r = part2()
    part3(r)
