import capstone
d=open("dumps/s136-botai/SUPERVIVE-Win64-Shipping.dump.exe","rb").read()
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
RVA=0x4631C50
print("=== UAIBlueprintHelperLibrary::SpawnAIFromClass 0x4631C50 ===")
print("  looking for: (a) indirect call through vtable disp 0x8C0 == slot 280 == SpawnDefaultController")
print("               (b) a read of Pawn->Controller (+0x400) guarding it  [stock: if (NewPawn->Controller == NULL)]")
found=[]
for i in md.disasm(d[RVA:RVA+0x400],RVA):
    s=f"{i.mnemonic} {i.op_str}"
    if "0x8c0" in s or "0x400" in s or i.mnemonic=="call" or i.mnemonic=="ret":
        print(f"  0x{i.address:08X}  {s}")
    if "0x8c0" in s: found.append(("VTABLE SLOT 280",i.address,s))
    if "0x400" in s: found.append(("Pawn->Controller",i.address,s))
    if i.mnemonic=="ret": break
print("\n=== HITS ===")
for t,a,s in found: print(f"  {t:20s} @0x{a:08X}  {s}")
