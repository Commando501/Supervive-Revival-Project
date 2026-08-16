#!/usr/bin/env python3
"""Find *real* instructions referencing a global, by disassembling the containing
function (bounds from the recovered .pdata union) instead of guessing alignment.

Usage: grefs.py <global_rva> [--dump D]
"""
import sys, struct
import fkdis, fn
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM
from capstone.x86 import X86_REG_RIP


def candidate_sites(img, target_rva):
    """disp32 windows in .text that could encode target_rva."""
    res = []
    for name, vaddr, vsize, rawptr, rawsize in img.sections:
        if name != ".text":
            continue
        blob = img.buf[rawptr:rawptr+rawsize]
        n = len(blob)
        for i in range(0, n - 4):
            disp = struct.unpack_from("<i", blob, i)[0]
            if disp and vaddr + i + 4 + disp == target_rva:
                res.append(vaddr + i)
    return res


def main():
    args = sys.argv[1:]
    dump = "merged2"
    if "--dump" in args:
        k = args.index("--dump"); dump = args[k+1]; del args[k:k+2]
    img = fkdis.load(dump)
    target = int(args[0], 0)
    sites = candidate_sites(img, target)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    base = img.imagebase
    seen_fns = {}
    hits = []
    for s in sites:
        f = fn.find(s)
        if not f:
            continue
        b, e, sz, _ = f
        if b in seen_fns:
            continue
        seen_fns[b] = True
        data = img.read(b, e - b)
        if not data:
            continue
        for ins in md.disasm(data, base + b):
            for op in ins.operands:
                if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                    t = (ins.address + ins.size + op.mem.disp) - base
                    if t == target:
                        hits.append((ins.address - base, b, e, ins.mnemonic, ins.op_str, ins.bytes.hex()))
    print(f"global 0x{target:08X}: {len(sites)} disp32 candidates, {len(seen_fns)} distinct fns, {len(hits)} verified insns")
    for r, b, e, m, o, by in sorted(hits):
        w = "WRITE" if (m.startswith("mov") and o.startswith("qword ptr [rip") is False and o.split(",")[0].strip().startswith(("dword ptr [rip", "qword ptr [rip", "byte ptr [rip", "word ptr [rip"))) else ("RMW " if m in ("inc","dec","add","sub","or","and","xor","lock") else "read ")
        print(f"  0x{r:08X}  fn 0x{b:08X}..0x{e:08X}  [{w}] {m} {o}   ({by})")
    # also report sites with no pdata entry
    orphan = [s for s in sites if not fn.find(s)]
    if orphan:
        print(f"  ({len(orphan)} disp32 candidates had no pdata function entry: " +
              ", ".join(f"0x{o:08X}" for o in orphan[:20]) + ")")


if __name__ == "__main__":
    main()
