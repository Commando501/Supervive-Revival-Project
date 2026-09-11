import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img(); BASE=im.imagebase
c=CFG(im,0x035E9EC0)
E=0x035E9EC0; T=0x035EB13A
nodes=sorted(c.insns); N=set(nodes)
D={n:(set([E]) if n==E else set(N)) for n in nodes}
ch=True
while ch:
    ch=False
    for n in nodes:
        if n==E: continue
        ps=[p for p in c.pred.get(n,()) if p in N]
        new={n} if not ps else (set(N).intersection(*[D[p] for p in ps]) | {n})
        if new!=D[n]: D[n]=new; ch=True
dt=D[T]
FOLD={0x00F7EC20:'FOLD ret0(void)',0x00F7EB50:'FOLD null/0',0x00F7EB60:'FOLD false',0x00B9E1F0:'FOLD true',0x00FC6CF0:'FOLD 0.0f'}
LOKIVT=0x088F8570
def grade(rva):
    if rva in FOLD: return FOLD[rva]
    try: nz=im.page_nonzero(rva)
    except Exception: return 'OUT-OF-IMAGE'
    if nz==0: return 'DARK'
    b=im.read(rva,8)
    return f'REAL/lit(nz={nz}) {b.hex()}'
print("=== MANDATORY calls (dominate the StartNewPhysics call) ===")
for r in sorted(c.calls):
    if r not in dt: continue
    i=c.insns[r]; t=c.calls[r]
    if t is not None:
        print(f"  {r:#010x} direct  -> {t:#010x}  {grade(t)}")
    else:
        op=i.op_str
        # resolve through Loki CMC vtable when base is [rbx]-derived vtable (rax = [rbx])
        disp=None
        for o in i.operands:
            if o.type==3 and o.mem.disp: disp=o.mem.disp
        res=''
        if disp is not None:
            try:
                va=struct.unpack('<Q',im.read(LOKIVT+disp,8))[0]; rv=va-BASE
                res=f' | ULokiCMC vt+{disp:#x} -> {rv:#010x} {grade(rv)}'
            except Exception: pass
        print(f"  {r:#010x} INDIRECT {op}{res}")
