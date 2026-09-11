import sys, struct
sys.path.insert(0,'.')
import capstone
from capstone import x86
from peimg import Img
from cfg import CFG
im=Img(); IB=im.imagebase
VT=0x088F8570; NSLOT=413
slots=[]
for k in range(NSLOT):
    q=struct.unpack('<Q', im.read(VT+8*k,8))[0]
    if IB<=q<IB+im.sizeofimage:
        rv=q-IB
        s=im.sec_of(rv)
        if s and s['name']=='.text': slots.append((k,rv))
print(f'vtable {VT:#x}: {len(slots)}/{NSLOT} slots resolve into .text')
# sanity controls: known displacements
known={0x3D0:'TickComponent 0x055C2B90',0xAA8:'PerformMovement 0x055B8370',0x720:'StartNewPhysics 0x055C2430',
       0x890:'ControlledCharacterMove 0x055A7680',0xA38:'ConstrainInputAcceleration 0x055A75B0',
       0x830:'PhysFalling 0x055B89F0',0x6B8:'HasValidData',0x4E0:'ShouldSkipUpdate'}
for d,lbl in known.items():
    q=struct.unpack('<Q', im.read(VT+d,8))[0]
    print(f'  CONTROL disp {d:#x} ({lbl}) -> {q-IB:#x}')

RMW={'inc','dec','add','sub','and','or','xor','adc','sbb','neg','not','shl','shr','sar','rol','ror','btr','bts','btc','xadd','cmpxchg'}
def is_store(i):
    if i.mnemonic=='call' or not i.operands: return False
    op0=i.operands[0]
    if op0.type!=x86.X86_OP_MEM: return False
    if op0.access & capstone.CS_AC_WRITE: return True
    if i.mnemonic.startswith('mov') and len(i.operands)==2: return True
    if i.mnemonic in RMW: return True
    return False

TARG={0x16D0,0x16C8,0x16B0,0x16C0,0x12B0,0x1308}
hits={t:[] for t in TARG}
dark=0; done=set(); fails=0
for k,rv in slots:
    if rv in done: continue
    done.add(rv)
    if im.page_nonzero(rv)==0: dark+=1; continue
    try: c=CFG(im,rv,maxinsn=40000)
    except Exception as e: fails+=1; continue
    for a,i in c.insns.items():
        for op in i.operands:
            if op.type!=x86.X86_OP_MEM: continue
            d=op.mem.disp
            if d in TARG and op.mem.base:
                bn=i.reg_name(op.mem.base)
                if bn=='rip' or bn=='rsp': continue
                hits[d].append((rv,a,bn,is_store(i),i.mnemonic,i.op_str))
print(f'\nswept {len(done)} unique vtable impls, {dark} on DARK pages, {fails} CFG failures')
for d in sorted(TARG):
    hs=hits[d]
    print(f'\n--- disp {d:#x}: {len(hs)} operand references across the ULokiCMC vtable ---')
    fns=sorted(set(h[0] for h in hs))
    for f in fns:
        sub=[h for h in hs if h[0]==f]
        w=[h for h in sub if h[3]]
        print(f'   fn {f:#010x}: {len(sub)} refs, {len(w)} STORES')
        for h in sub:
            print(f'        {"W" if h[3] else "r"} {h[1]:#010x} base={h[2]:4s} {h[4]} {h[5]}')
