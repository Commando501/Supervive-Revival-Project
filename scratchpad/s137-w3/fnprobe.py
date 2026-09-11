import sys,csv,struct,bisect
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img
import capstone
im=Img('dumps/merged13.dump.exe'); b=im.b
rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    r=csv.reader(f); next(r)
    for x in r: rows.append((int(x[0],16),int(x[1],16)))
rows.sort(); begins=[x[0] for x in rows]
def extent(start):
    i=bisect.bisect_left(begins,start)
    if i>=len(rows) or rows[i][0]!=start:
        i=bisect.bisect_right(begins,start)-1
    if i<0: return None
    bgn,end=rows[i]
    # chain forward
    j=i
    while j+1<len(rows) and rows[j+1][0]==rows[j][1]:
        j+=1; end=rows[j][1]
    return rows[i][0],end
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
NAMED={0x3F61A60:'UWorld::GetNetMode',0xF7EB60:'LokiIsServer(false)',0xB9E1F0:'LokiIsClient(true)',
       0x1311870:'ServerOnly/ClientOnly/ClientServerSplit gate',0x13852F0:'CheatsEnabledOnly gate',
       0xF7EC20:'FOLD ret-void',0xF7EB50:'FOLD ret-null',0xFC6CF0:'FOLD ret-0.0f',
       0x338CF70:'AActor::HasAuthority',0x338ABB0:'AActor::GetLocalRole',0x2DD7020:'AActor::GetRemoteRole'}
def probe(start,label):
    ex=extent(start)
    print('=== %s %s extent %s'%(label,hex(start),(hex(ex[0]),hex(ex[1])) if ex else None))
    if not ex: return
    bgn,end=ex
    pg=[sum(1 for x in b[p:p+4096] if x) for p in range(bgn&~0xFFF,end,4096)]
    print('   size',hex(end-bgn),'page-nonzero',pg)
    pos=bgn
    while pos<end:
        try: ins=next(md.disasm(b[pos:pos+16], im.rva2va(pos)))
        except StopIteration: pos+=1; continue
        for op in ins.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.disp in (0x160,0x72) and op.mem.index==0:
                print('   ROLE?  %s  %s %s'%(hex(pos),ins.mnemonic,ins.op_str))
        if ins.mnemonic in ('call','jmp') and ins.operands and ins.operands[0].type==capstone.x86.X86_OP_IMM:
            t=ins.operands[0].imm-im.imagebase
            if t in NAMED: print('   CALL   %s -> %s (%s)'%(hex(pos),NAMED[t],hex(t)))
        pos+=ins.size
if __name__=='__main__':
    import ast
    for spec in sys.argv[1:]:
        a,_,n=spec.partition(':')
        probe(int(a,16), n or a)
