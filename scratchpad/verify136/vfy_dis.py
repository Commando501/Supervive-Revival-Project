import capstone
d=open("dumps/s136-botai/SUPERVIVE-Win64-Shipping.dump.exe","rb").read()
RVA=0x3BBF3C0
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
print("=== disassembly of 0x3BBF3C0 (claimed APawn::SpawnDefaultController) ===")
n=0
for i in md.disasm(d[RVA:RVA+0x220],RVA):
    print(f"  0x{i.address:08X}  {i.mnemonic:8s} {i.op_str}")
    n+=1
    if i.mnemonic=="ret" and n>20: break
    if n>90: break
