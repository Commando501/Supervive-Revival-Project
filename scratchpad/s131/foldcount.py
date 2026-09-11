"""Count calls to the four known ICF folds inside a set of function extents."""
import sys, csv
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"); IB=img.imagebase
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
FOLD={0xF7EC20:'ret0',0xF7EB50:'xor eax;ret',0xF7EB60:'xor al;ret',0xB9E1F0:'mov al,1;ret'}
rows=list(csv.reader(open(r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv")))[1:]
starts=sorted({int(r[0],0) for r in rows})
ends={int(r[0],0):int(r[1],0) for r in rows}
def extent(fn):
    """union of chained pdata rows starting at fn"""
    e=ends.get(fn)
    if e is None: return None
    while e in ends: e=ends[e]
    return fn,e
def scan(fn,label):
    ex=extent(fn)
    if not ex: print("%-46s no pdata"%label); return
    lo,hi=ex
    data=img.read(lo,hi-lo)
    pgs=fkdis.zero_pages(img,lo,hi-lo)
    zero=sum(1 for p,z in pgs if z)
    cnt={}
    total=0
    for ins in md.disasm(data, IB+lo):
        if ins.mnemonic=="call":
            for op in ins.operands:
                if op.type==2:
                    t=op.imm-IB; total+=1
                    if t in FOLD: cnt.setdefault(t,[]).append(ins.address-IB)
    d=" ".join("%s x%d @%s"%(FOLD[k],len(v),",".join("0x%X"%x for x in v)) for k,v in sorted(cnt.items()))
    print("%-46s 0x%08X..0x%08X (%d B) directcalls=%d zeropages=%d/%d  FOLDS: %s"%(label,lo,hi,hi-lo,total,zero,len(pgs),d or "none"))
for fn,label in [(0x55CD510,'ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable'),
                 (0x55CCE70,'ULokiRideableComponent::AuthPlayerEnterWorld'),
                 (0x55CD800,'ULokiRideableComponent::AuthPlayerPreSpawnOnAddToPlane'),
                 (0x55DCAA0,'HasEverContainedPlayer'),
                 (0x56680F0,'LokiTeleportActor'),
                 (0x55C1B20,'ALokiCharacter::SpawnAndMoveLokiCharacter_MoveStep'),
                 (0x56BE0D0,'GetLokiCharacter'),
                 (0x339A550,'SetActorEnableCollision'),
                 (0x37D9D40,'GetServerTime'),
                 (0x55CBB60,'ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane'),
                 (0x597E730,'ALokiDropShip::SpawnDropPodForTeam(AS)')]:
    scan(fn,label)
print()
for fn,label in [(0x55CCCB0,'ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable'),
                 (0x55D89F0,'ULokiRideableComponent::GetLandingTeleportLocation'),
                 (0x55DAB50,'ULokiRideableComponent::GetRidePosition'),
                 (0x54537C0,'MulticastOnPlayerEnteredWorld'),
                 (0x5453780,'MulticastOnPlayerEntered')]:
    scan(fn,label)
