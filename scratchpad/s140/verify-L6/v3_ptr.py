import struct
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
D=open(P,'rb').read(); IB=0x7FF608F40000
SEC={'.text':(0x1000,0x764a000),'.rdata':(0x764a000,0x99c7000),'.data':(0x99c7000,0xa0b7000),
     '_RDATA':(0xa6b8000,0xa716000),'.pdata':(0xa0b7000,0xa6b5000)}
def secof(o):
    for n,(a,b) in SEC.items():
        if a<=o<b: return n
    return '?'
def find_aligned(rva):
    pat=struct.pack('<Q',IB+rva); out=[]
    s=0
    while True:
        i=D.find(pat,s)
        if i<0: break
        out.append((i,i%8==0)); s=i+1
    return out
for name,rva in [("ULokiCMC::StartNewPhysics",0x055C2430),("slotA50 impl",0x0530ABF0),
                 ("ULokiCMC::PerformMovement",0x055B8370),("engine SNP",0x03600990),
                 ("engine PerformMovement",0x035E9EC0),("engine A50",0x035D6790),
                 ("LokiCMC dtor slot0",0x0530AAA0)]:
    hits=find_aligned(rva)
    al=[h for h,a in hits if a]
    print(f"{name:28} {rva:#010x}  total={len(hits):3} aligned={len(al):3}  " +
          " ".join(f"{h:#x}[{secof(h)}]" for h in al[:8]))
