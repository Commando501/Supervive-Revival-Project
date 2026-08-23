import capstone
P=r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
d=open(P,'rb').read()
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def dump(a,n,tag):
    print("=== %s @ %08X ==="%(tag,a))
    for i in md.disasm(d[a:a+n*10],a,count=n):
        print("%08X %-10s %s"%(i.address,i.mnemonic,i.op_str))
dump(0x055C2430,32,"ULokiCMC::StartNewPhysics")
dump(0x055B83F8,10,"Loki PerformMovement HitStop->12B0")
dump(0x036009A0,20,"engine StartNewPhysics guards")
