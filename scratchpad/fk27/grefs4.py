#!/usr/bin/env python3
"""Verified refs to several globals in ONE .text pass. Prints WRITE/RMW first."""
import sys, struct
import fkdis, fn
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM
from capstone.x86 import X86_REG_RIP

def main():
    args = sys.argv[1:]
    dump = "merged2"
    if "--dump" in args:
        k = args.index("--dump"); dump = args[k+1]; del args[k:k+2]
    only_writes = "--writes" in args
    if only_writes:
        args.remove("--writes")
    targets = set(int(a, 0) for a in args)
    img = fkdis.load(dump)
    base = img.imagebase
    # one pass over .text collecting candidate disp32 windows for any target
    cand = {t: [] for t in targets}
    for name, vaddr, vsize, rawptr, rawsize in img.sections:
        if name != ".text":
            continue
        blob = img.buf[rawptr:rawptr+rawsize]
        n = len(blob)
        up = struct.unpack_from
        for i in range(0, n - 4):
            disp = up("<i", blob, i)[0]
            if not disp:
                continue
            t = vaddr + i + 4 + disp
            if t in cand:
                cand[t].append(vaddr + i)
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    allfns = {}
    for t, sites in cand.items():
        for s in sites:
            f = fn.find(s)
            if f:
                allfns[f[0]] = f
    # disassemble each function once
    results = {t: [] for t in targets}
    for b, (bb, e, sz, seen) in allfns.items():
        data = img.read(b, e - b)
        if not data:
            continue
        for ins in md.disasm(data, base + b):
            for op in ins.operands:
                if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                    t = (ins.address + ins.size + op.mem.disp) - base
                    if t in results:
                        dst = ins.op_str.split(",")[0].strip()
                        kind = "WRITE" if dst.endswith("[rip + 0x%x]" % op.mem.disp) or dst.startswith(("dword ptr [rip", "qword ptr [rip", "byte ptr [rip")) else "read"
                        if ins.mnemonic in ("or", "and", "add", "sub", "xor", "inc", "dec", "lock") and dst.startswith(("dword ptr [rip",)):
                            kind = "RMW"
                        results[t].append((ins.address - base, b, e, kind, ins.mnemonic, ins.op_str, ins.bytes.hex()))
    for t in sorted(results):
        rs = sorted(results[t])
        print(f"\n######## global 0x{t:08X}: {len(cand[t])} disp32 cands, {len(rs)} verified insns")
        for r, b, e, kind, m, o, by in rs:
            if only_writes and kind == "read":
                continue
            print(f"  0x{r:08X}  fn 0x{b:08X}..0x{e:08X} [{kind:5}] {m} {o}")

if __name__ == "__main__":
    main()
