import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
IB=im.imagebase
ENTRY=0x035E9EC0; CALL=0x035EB13A; RET=0x035EB1CA; CLR=0x035EB569
c=CFG2(im,ENTRY)
# paths from call-fallthrough to RET that AVOID CLR
def reach_avoid(start, avoid):
    S={start}; wl=[start]
    while wl:
        n=wl.pop()
        for s in c.succ.get(n,()):
            if s==avoid: continue
            if s not in S: S.add(s); wl.append(s)
    return S
A=reach_avoid(0x035EB140, CLR)
print("can reach RET from the call's fallthrough WITHOUT passing 0x035EB569:", RET in A)
# how many other calls to disp 0xA50 in the fn
n=[a for a,(sz,mn,ops,i) in c.ins.items() if i.id==X86_INS_CALL and i.operands[0].type==X86_OP_MEM and i.operands[0].mem.disp==0xA50]
print("disp 0xA50 call sites in engine PerformMovement:", [hex(x) for x in n])
# is CLR reachable from EVERY successor path of the call? show the branch that avoids it
print("\n--- 0x035EB146..0x035EB160 (post-call HasValidData) ---")
for i in md.disasm(im.read(0x035EB140,0x2a),0x035EB140):
    print(f"  {i.address:#010x} {im.read(i.address,i.size).hex():<20} {i.mnemonic} {i.op_str}")

# the two [rcx+0x878] sites: resolve via pawn-family vtable pinned on APawn::SpawnDefaultController disp 0x8C0 = 0x3BBF3C0
tgt=struct.pack('<Q', IB+0x03BBF3C0); s=0; cands=[]
while True:
    p=im.buf.find(tgt,s)
    if p<0: break
    if p%8==0: cands.append(p-0x8C0)
    s=p+1
print(f"\npawn-family vtable candidates (disp 0x8C0 == SpawnDefaultController): {len(cands)}")
res={}
for vb in cands:
    q=struct.unpack_from('<Q', im.buf, vb+0x878)[0]-IB
    res.setdefault(q,0); res[q]+=1
FOLDS={0x00F7EC20,0x00F7EB50,0x00F7EB60,0x00B9E1F0,0x00FC6CF0}
print("distinct disp 0x878 targets:")
for q,n2 in sorted(res.items()):
    g='FOLD' if q in FOLDS else ('DARK' if im.page_nonzero(q)==0 else 'REAL')
    rets='-'
    if g=='REAL':
        cc=CFG2(im,q); rets=f"{len(cc.ins)}i/{len(cc.rets)}r"
    print(f"   {q:#010x} x{n2:<3} nz={im.page_nonzero(q):4d} {g:5} {rets}")

# Loki wrapper
print("\n=== ULokiCMC::PerformMovement 0x055B8370 ===")
w=CFG2(im,0x055B8370); SUP=0x055B85C1
Rw=w.reach_backward(SUP)
print(f"insns={len(w.ins)} rets={len(w.rets)} calls={len(w.calls)} ijmp={len(w.indirect_jumps)} fail={len(w.decode_failures)} |R|={len(Rw)}")
bw=[]
for u in sorted(Rw):
    if u==SUP: continue
    for v in w.succ.get(u,()):
        if v not in Rw: bw.append((u,v,w.ins[u][1],w.ins[u][2]))
print("BAIL EDGES skipping the Super call:", len(bw), [(hex(a),hex(b)) for a,b,_,_ in bw])
print("nodes in Rw with no successors:", [hex(a) for a in Rw if not w.succ.get(a)])
# S139's two flagged branches
for a in (0x055B845E,0x055B846B):
    if a in w.ins:
        print(f"  {a:#x}: {w.ins[a][1]} {w.ins[a][2]}  succ={[hex(x) for x in w.succ[a]]}")
