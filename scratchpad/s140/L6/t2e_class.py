"""Which class does each candidate function belong to?
(1) vtable membership: search .rdata for aligned qwords == IB+entry; report offset within the
    two KNOWN CMC vtables.  (2) offset fingerprint: which known CMC/Character field offsets the
    function touches."""
import sys, struct, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img(); IB=im.imagebase
rd=[s for s in im.sections if s['name']=='.rdata'][0]
RDATA=im.data[rd['praw']:rd['praw']+rd['rawsz']]
LOKI_VT=0x088F8570; ENG_VT=0x07fbed58

def vt_positions(entry):
    tb=struct.pack('<Q', IB+entry); out=[]; off=RDATA.find(tb)
    while off!=-1:
        if off%8==0: out.append(rd['va']+off)
        off=RDATA.find(tb,off+1)
    return out

# CMC-distinctive offsets (from BRIEF's live table + code)
CMC_OFF={0xD0:'UpdatedComponent',0xE8:'Velocity',0xF8:'Velocity.Z-ish',0x198:'CharacterOwner',
         0x231:'MovementMode',0x328:'Acceleration',0x12B0:'TimeSinceFallingStart',
         0x16B0:'?velSnap',0x16C0:'?snapZ',0x16C8:'?latch'}
CHAR_OFF={0x1090:'ALokiCharacter::LivingState',0xF00:'ASC storage',0xF08:'AttributeSetStorage',
          0x400:'AController::Pawn / APawn Controller',0x160:'Role',0x580:'?charFlags',0x1988:'?'}

FNS=[
 (0x0559c560,'byte cmp [rax+0x16c8]'),
 (0x0559e180,'word write [r14<-rcx]'),
 (0x0559f580,'byte write [rdi<-rcx]'),
 (0x055c0d30,'byte write 1 [rbx<-rcx]'),
 (0x0530aaa0,'byte cmp+write0 [rbx<-rcx]'),
 (0x05292040,'qword read [rbx<-rcx]'),
 (0x05513a00,'qword write [rdi<-rcx]'),
 (0x055be930,'xmm write [rbx<-rcx]'),
 (0x055c00c0,'xmm read via +0x198'),
 (0x055a69f0,'xmm write via +0x198'),
 (0x055c0970,'xmm read [rbx<-rdx]'),
 (0x055bdcb0,'xmm write [rbx<-rdx]'),
 (0x055a7440,'xmm write [rbx<-r8]'),
 (0x055C2430,'*** ULokiCMC::StartNewPhysics (KNOWN CMC) ***'),
 (0x055B8370,'*** ULokiCMC::PerformMovement (KNOWN CMC) ***'),
]
for entry,note in FNS:
    pos=vt_positions(entry)
    tags=[]
    for p in pos:
        if 0<= p-LOKI_VT < 413*8: tags.append(f"LokiCMCvt+{p-LOKI_VT:#x}")
        if 0<= p-ENG_VT  < 500*8: tags.append(f"EngCMCvt+{p-ENG_VT:#x}")
    try:
        c=CFG(im,entry,maxinsn=200000)
        disps=collections.Counter()
        for a in c.insns:
            for op in c.insns[a].operands:
                if op.type==X86.X86_OP_MEM and op.mem.base and c.insns[a].reg_name(op.mem.base) not in ('rsp','rip'):
                    disps[op.mem.disp]+=1
        fp_cmc=[f"{o:#x}={n}" for o,n in CMC_OFF.items() if disps.get(o)]
        fp_ch =[f"{o:#x}={n}" for o,n in CHAR_OFF.items() if disps.get(o)]
        ni=len(c.insns)
    except Exception as ex:
        fp_cmc=fp_ch=[f'CFG-ERR {ex}']; ni=-1
    print(f"\n{entry:#010x}  {note}   insns={ni}")
    print(f"   .rdata aligned qword hits: {len(pos)}  {[hex(x) for x in pos[:6]]}  {tags}")
    print(f"   CMC-offset fingerprint : {fp_cmc}")
    print(f"   CHAR-offset fingerprint: {fp_ch}")
