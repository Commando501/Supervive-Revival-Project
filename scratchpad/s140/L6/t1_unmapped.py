"""Fallback adjudication for candidates with no pdata_union row.
For each candidate disp-byte position D, try every instruction start D-1..D-15; accept a
start S iff the decoded insn covers [D,D+4) AND has an operand with disp/imm 0x16C8.
Report ALL viable interpretations (raw), do not pick one silently."""
import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
X86=capstone.x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
UNMAPPED=[0x530abfb,0x530ac12,0x530c801,0x55c243b,0x55c2444,0x55c246b]
for D in UNMAPPED:
    print(f"\n--- candidate disp-bytes @ {D:#x}   context: {im.read(D-16,32).hex(' ')}")
    for back in range(1,16):
        S=D-back
        try: b=im.read(S,16)
        except ValueError: continue
        g=CS.disasm(b,S)
        try: i=next(g)
        except StopIteration: continue
        if not (S <= D and D+4 <= S+i.size): continue
        hit=None
        for op in i.operands:
            if op.type==X86.X86_OP_MEM and op.mem.disp==0x16C8: hit='MEM'
            elif op.type==X86.X86_OP_IMM and op.imm==0x16C8: hit='IMM'
        if hit:
            print(f"    start {S:#x} (D-{back}) len={i.size}  {i.bytes.hex(' '):<26} {i.mnemonic} {i.op_str}   [{hit}]")
