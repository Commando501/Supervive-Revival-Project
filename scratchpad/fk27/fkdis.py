#!/usr/bin/env python3
"""FK-27 helper: offline disassembly / hex / search over the cold dump images.

Usage:
  dis.py info [--dump D]
  dis.py d <rva> [n_bytes] [--dump D]      disassemble
  dis.py x <rva> [n_bytes] [--dump D]      hexdump
  dis.py cov <rva> [n] [--dump D]          page-coverage (zero page?) report
  dis.py findptr <va_or_rva> [--dump D]    find qwords equal to the VA
  dis.py callxref <rva> [--dump D]         find E8/E9 rel32 calls targeting rva
  dis.py lea <rva> [--dump D]              find rip-rel LEA/MOV referencing rva
"""
import sys, os, struct

DUMPS = {
    "merged2": r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe",
    "tuthero": r"G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
    "merged":  r"G:\git\Supervive Revival Project\dumps\merged.dump.exe",
    "s129":    r"G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe",
    "merged3": r"G:\git\Supervive Revival Project\dumps\merged3.dump.exe",
    "merged4": r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe",
    "rideable": r"G:\git\Supervive Revival Project\dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe",
}

class Img:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.buf = f.read()
        b = self.buf
        e_lfanew = struct.unpack_from("<I", b, 0x3C)[0]
        assert b[e_lfanew:e_lfanew+4] == b"PE\0\0", "not a PE"
        coff = e_lfanew + 4
        nsec = struct.unpack_from("<H", b, coff+2)[0]
        szopt = struct.unpack_from("<H", b, coff+16)[0]
        opt = coff + 20
        self.magic = struct.unpack_from("<H", b, opt)[0]
        self.imagebase = struct.unpack_from("<Q", b, opt+24)[0]
        self.sections = []
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i*40
            name = b[o:o+8].rstrip(b"\0").decode("latin1")
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", b, o+8)
            self.sections.append((name, vaddr, vsize, rawptr, rawsize))

    def sec_of(self, rva):
        for s in self.sections:
            if s[1] <= rva < s[1] + max(s[2], s[4]):
                return s
        return None

    def off(self, rva):
        s = self.sec_of(rva)
        if not s:
            return None
        return s[3] + (rva - s[1])

    def read(self, rva, n):
        o = self.off(rva)
        if o is None:
            return None
        return self.buf[o:o+n]

    def va2rva(self, va):
        return va - self.imagebase if va >= self.imagebase else va


def load(name="merged2"):
    return Img(DUMPS.get(name, name))


def zero_pages(img, rva, n):
    """Return list of (page_rva, is_zero) for pages spanned."""
    out = []
    p0 = rva & ~0xFFF
    p1 = (rva + n - 1) & ~0xFFF
    p = p0
    while p <= p1:
        d = img.read(p, 0x1000)
        out.append((p, d is None or not any(d)))
        p += 0x1000
    return out


def disasm(img, rva, n=0x80, quiet=False):
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = False
    data = img.read(rva, n)
    if data is None:
        print("  <rva not mapped>")
        return
    zp = zero_pages(img, rva, n)
    if not quiet:
        for p, z in zp:
            if z:
                print(f"  ;; WARNING page 0x{p:08X} is ALL-ZERO (not decrypted)")
    lines = []
    for ins in md.disasm(data, img.imagebase + rva):
        r = ins.address - img.imagebase
        by = ins.bytes.hex()
        lines.append(f"  0x{r:08X}  {by:<20} {ins.mnemonic} {ins.op_str}")
    print("\n".join(lines))


def hexdump(img, rva, n=0x80):
    data = img.read(rva, n)
    if data is None:
        print("<not mapped>")
        return
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        h = " ".join(f"{c:02x}" for c in chunk)
        a = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print(f"  0x{rva+i:08X}  {h:<47}  {a}")


def find_qword(img, val, limit=200):
    pat = struct.pack("<Q", val)
    res = []
    b = img.buf
    for name, vaddr, vsize, rawptr, rawsize in img.sections:
        if name in (".reloc", ".rsrc"):
            continue
        blob = b[rawptr:rawptr+rawsize]
        st = 0
        while True:
            i = blob.find(pat, st)
            if i < 0:
                break
            res.append((name, vaddr + i))
            st = i + 1
            if len(res) >= limit:
                return res
    return res


def find_call(img, target_rva, limit=200):
    """E8/E9 rel32 whose target == target_rva."""
    res = []
    b = img.buf
    for name, vaddr, vsize, rawptr, rawsize in img.sections:
        if name != ".text":
            continue
        blob = b[rawptr:rawptr+rawsize]
        for i in range(0, len(blob) - 5):
            op = blob[i]
            if op != 0xE8 and op != 0xE9:
                continue
            disp = struct.unpack_from("<i", blob, i+1)[0]
            tgt = vaddr + i + 5 + disp
            if tgt == target_rva:
                res.append((name, vaddr + i, "call" if op == 0xE8 else "jmp"))
                if len(res) >= limit:
                    return res
    return res


def find_riprel(img, target_rva, limit=400):
    """Any instruction whose rip-relative disp32 resolves to target_rva.
    Brute: for each offset i in .text, for each instruction length guess 6/7,
    compute. Cheaper: scan for disp32 == target - (rva_of_next_insn).
    We do it the direct way: for every 4-byte window treat as disp32 and see if
    rva_window+4+disp == target -> candidate site (start unknown)."""
    res = []
    b = img.buf
    for name, vaddr, vsize, rawptr, rawsize in img.sections:
        if name != ".text":
            continue
        blob = b[rawptr:rawptr+rawsize]
        n = len(blob)
        for i in range(0, n - 4):
            disp = struct.unpack_from("<i", blob, i)[0]
            if disp == 0:
                continue
            if vaddr + i + 4 + disp == target_rva:
                res.append(vaddr + i)
                if len(res) >= limit:
                    return res
    return res


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    dump = "merged2"
    if "--dump" in args:
        k = args.index("--dump")
        dump = args[k+1]
        del args[k:k+2]
    img = load(dump)
    cmd = args[0] if args else "info"
    def num(s):
        return int(s, 0)
    if cmd == "info":
        print(f"path       {img.path}")
        print(f"ImageBase  0x{img.imagebase:X}")
        for s in img.sections:
            print(f"  {s[0]:<10} vaddr=0x{s[1]:08X} vsize=0x{s[2]:08X} rawptr=0x{s[3]:08X} rawsize=0x{s[4]:08X}  off==rva:{s[1]==s[3]}")
    elif cmd == "d":
        disasm(img, num(args[1]), num(args[2]) if len(args) > 2 else 0x80)
    elif cmd == "x":
        hexdump(img, num(args[1]), num(args[2]) if len(args) > 2 else 0x80)
    elif cmd == "cov":
        for p, z in zero_pages(img, num(args[1]), num(args[2]) if len(args) > 2 else 0x1000):
            print(f"  page 0x{p:08X}  {'ZERO' if z else 'present'}")
    elif cmd == "findptr":
        v = num(args[1])
        if v < img.imagebase:
            v += img.imagebase
        for name, rva in find_qword(img, v):
            print(f"  {name} 0x{rva:08X}")
    elif cmd == "callxref":
        for name, rva, kind in find_call(img, num(args[1])):
            print(f"  {kind} site 0x{rva:08X}")
    elif cmd == "lea":
        for rva in find_riprel(img, num(args[1])):
            print(f"  disp32 at 0x{rva:08X} (insn ends 0x{rva+4:08X})")
    else:
        print(__doc__)
