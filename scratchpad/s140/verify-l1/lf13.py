import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
IB=im.imagebase; VT=0x088F8570
def slot(disp): return struct.unpack_from('<Q', im.buf, VT+disp)[0]-IB

ENTRY=0x035E9EC0; CALL=0x035EB13A
c=CFG2(im,ENTRY); R=c.reach_backward(CALL)
S=0x035EB569
print("0x035EB569 decoded in CFG:", S in c.ins, c.ins.get(S,(0,'','',None))[1:3])
print("0x035EB569 in R (can reach the StartNewPhysics call):", S in R)
F=c.reach_forward(c.succ[CALL])
print("0x035EB569 reachable AFTER the call returns:", S in F)
for t in (0x035EB1A7,0x035EB7CF,0x035EB150):
    Ft=c.reach_forward([t])
    print(f"   reachable from bail target {t:#x}: {S in Ft}")
# rax provenance for 0xA50
ins=sorted(c.ins); k=ins.index(S)
for j in range(k-6,k+1):
    a=ins[j]; sz=c.ins[a][0]
    print(f"   {a:#010x} {im.read(a,sz).hex():<20} {c.ins[a][1]} {c.ins[a][2]}")
t=slot(0xA50)
print(f"\nULokiCMC vtable disp 0xA50 -> {t:#010x}   page nz={im.page_nonzero(t)}")
print("--- body ---")
for i in md.disasm(im.read(t,0x30),t):
    print(f"  {i.address:#010x} {im.read(i.address,i.size).hex():<20} {i.mnemonic} {i.op_str}")
# engine CMC vtable? find a vtable holding engine PerformMovement at 0xAA8 to compare 0xA50
print("\n=== compare against ENGINE UCharacterMovementComponent vtable ===")
hits=[]
for off in range(0, len(im.buf)-8, 8):
    pass
# faster: scan .rdata for qword == IB+0x035E9EC0 (engine PerformMovement) -> candidate vt base = hit-0xAA8
target=struct.pack('<Q', IB+0x035E9EC0)
start=0
cands=[]
while True:
    p=im.buf.find(target,start)
    if p<0: break
    if p%8==0: cands.append(p-0xAA8)
    start=p+1
print("candidate vtables with engine PerformMovement at disp 0xAA8:", [hex(x) for x in cands])
for vb in cands:
    q=struct.unpack_from('<Q', im.buf, vb+0xA50)[0]-IB
    q720=struct.unpack_from('<Q', im.buf, vb+0x720)[0]-IB
    print(f"   vt {vb:#x}: disp0xA50 -> {q:#010x}   disp0x720 -> {q720:#010x}")
# stored pointer occurrences of 0x0530ABF0
tp=struct.pack('<Q', IB+t); n=0; locs=[]
s=0
while True:
    p=im.buf.find(tp,s)
    if p<0: break
    n+=1; locs.append(p); s=p+1
print(f"\nstored-pointer occurrences of {t:#x} image-wide: {n} at {[hex(x) for x in locs]}")
