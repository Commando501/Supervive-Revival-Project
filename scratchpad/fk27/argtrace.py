#!/usr/bin/env python3
"""For every direct call to TARGET, print the last instruction that writes ECX/RCX
(arg1) before the call, by disassembling the containing function from its pdata start."""
import sys
import fkdis, fn
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_ECX, X86_REG_RCX, X86_REG_CL, X86_REG_CX

REGS = {X86_REG_ECX, X86_REG_RCX, X86_REG_CL, X86_REG_CX}

def main():
    args = sys.argv[1:]
    dump = "merged2"
    if "--dump" in args:
        k = args.index("--dump"); dump = args[k+1]; del args[k:k+2]
    target = int(args[0], 0)
    img = fkdis.load(dump)
    base = img.imagebase
    sites = [rva for _n, rva, _k in fkdis.find_call(img, target, limit=500)]
    print(f"target 0x{target:08X}: {len(sites)} direct E8/E9 sites")
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    tally = {}
    for s in sites:
        f = fn.find(s)
        if not f:
            print(f"  0x{s:08X}  <no pdata fn>")
            continue
        b, e, _sz, _seen = f
        data = img.read(b, e - b)
        last = None
        for ins in md.disasm(data, base + b):
            r = ins.address - base
            if r == s:
                break
            _rd, wr = ins.regs_access()
            if any(w in REGS for w in wr):
                last = (r, ins.mnemonic, ins.op_str)
        if last:
            key = f"{last[1]} {last[2]}"
            tally[key] = tally.get(key, 0) + 1
            print(f"  call@0x{s:08X}  fn 0x{b:08X}  arg1 <- 0x{last[0]:08X}  {key}")
        else:
            print(f"  call@0x{s:08X}  fn 0x{b:08X}  arg1 <- (not written in this chunk; inherited)")
            tally["<inherited>"] = tally.get("<inherited>", 0) + 1
    print("\nsummary:")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d}  {k}")

if __name__ == "__main__":
    main()
