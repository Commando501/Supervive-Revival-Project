import sys, capstone
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv")
from img import *
# scan a window of .text around APawn code for instructions touching +0x418
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=False
lo,hi = 0x03BA0000, 0x03BC0000
hits=[]
off=lo
# linear sweep with resync every 16 bytes to catch misaligned starts
for base in range(lo,hi,16):
    for ins in md.disasm(DATA[base:base+64], base):
        if '0x418]' in ins.op_str and ('add' in ins.mnemonic or 'mov' in ins.mnemonic):
            hits.append((ins.address, ins.mnemonic, ins.op_str))
        break
seen=set(); out=[]
for base in range(lo,hi,1):
    pass
# simpler: full linear from lo
for ins in md.disasm(DATA[lo:hi], lo):
    if '+ 0x418]' in ins.op_str:
        out.append((ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
for a,b,m,o in out:
    print(f"0x{a:08X}  {b:<20} {m} {o}")
