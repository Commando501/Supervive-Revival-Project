#!/usr/bin/env python3
"""Annotated disassembler: resolves rip-relative targets and call targets by machine.
Usage: dz.py <rva> [nbytes] [--dump merged2|tuthero|merged]
"""
import sys, struct
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_IMM
from capstone.x86 import X86_REG_RIP

def sec_name(img, rva):
    s = img.sec_of(rva)
    return s[0] if s else "?"

def try_str(img, rva, maxn=140):
    d = img.read(rva, maxn)
    if not d:
        return None
    # utf-16le
    try:
        u = d.decode("utf-16-le", errors="strict")
        u = u.split("\x00")[0]
        if len(u) >= 3 and all(32 <= ord(c) < 0x3000 for c in u):
            return ("U", u)
    except Exception:
        pass
    a = d.split(b"\x00")[0]
    if len(a) >= 4 and all(32 <= c < 127 for c in a):
        return ("A", a.decode("latin1"))
    return None

def run(img, rva, n, out=sys.stdout):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    data = img.read(rva, n)
    if data is None:
        print("<not mapped>", file=out); return
    for p, z in fkdis.zero_pages(img, rva, n):
        if z:
            print(f"  ;; WARNING page 0x{p:08X} ALL-ZERO (not decrypted)", file=out)
    base = img.imagebase
    for ins in md.disasm(data, base + rva):
        r = ins.address - base
        note = ""
        # rip-relative memory operand
        for op in ins.operands:
            if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                tgt = (ins.address + ins.size + op.mem.disp) - base
                s = try_str(img, tgt)
                extra = ""
                if s:
                    extra = f"  {s[0]}'{s[1][:60]}'"
                else:
                    q = img.read(tgt, 8)
                    if q and len(q) == 8:
                        v = struct.unpack("<Q", q)[0]
                        d4 = struct.unpack("<i", q[:4])[0]
                        extra = f"  q=0x{v:016X} d=0x{d4 & 0xFFFFFFFF:08X}({d4})"
                        if base <= v < base + 0x0B000000:
                            pr = v - base
                            ps = try_str(img, pr)
                            extra += f" ->rva 0x{pr:08X}"
                            if ps:
                                extra += f" {ps[0]}'{ps[1][:50]}'"
                note += f"   ; [rip]-> 0x{tgt:08X} ({sec_name(img,tgt)}){extra}"
            elif op.type == CS_OP_IMM and ins.mnemonic in ("call", "jmp", "je", "jne", "jg", "jge", "jl", "jle", "ja", "jae", "jb", "jbe", "js", "jns"):
                t = op.imm - base
                note += f"   ; -> 0x{t:08X}"
        by = ins.bytes.hex()
        print(f"  0x{r:08X}  {by:<22} {ins.mnemonic} {ins.op_str}{note}", file=out)

if __name__ == "__main__":
    args = sys.argv[1:]
    dump = "merged2"
    if "--dump" in args:
        k = args.index("--dump"); dump = args[k+1]; del args[k:k+2]
    img = fkdis.load(dump)
    run(img, int(args[0], 0), int(args[1], 0) if len(args) > 1 else 0x100)
