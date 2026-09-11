import sys, capstone
from vimg import VImg
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=VImg()
start=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 40
buf=im.read(start, 16*n+32)
c=0
for i in CS.disasm(bytes(buf), start):
    print("0x%08x  %-28s %s %s" % (i.address, " ".join("%02x"%b for b in i.bytes), i.mnemonic, i.op_str))
    c+=1
    if c>=n: break
