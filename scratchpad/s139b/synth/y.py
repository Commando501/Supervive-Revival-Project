import capstone
P=r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
d=open(P,'rb').read()
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
for i in md.disasm(d[0x035E9F8A:0x035E9F8A+140],0x035E9F8A,count=25):
    print("%08X %-10s %s"%(i.address,i.mnemonic,i.op_str))
print("--- 0x3600a57 ---")
for i in md.disasm(d[0x03600A57:0x03600A57+90],0x03600A57,count=14):
    print("%08X %-10s %s"%(i.address,i.mnemonic,i.op_str))
