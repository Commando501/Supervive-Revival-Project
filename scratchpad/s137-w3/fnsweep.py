import sys,struct
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img
import capstone
im=Img('dumps/merged13.dump.exe'); b=im.b
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
NAMED={0x3F61A60:'UWorld::GetNetMode',0xF7EB60:'LokiIsServer(hardcoded false)',0xB9E1F0:'LokiIsClient(hardcoded true)',
       0x1311870:'ServerOnly/ClientOnly/ClientServerSplit exec-pin gate',0x13852F0:'CheatsEnabledOnly gate',
       0xF7EC20:'FOLD ret-void',0xF7EB50:'FOLD ret-null',0xFC6CF0:'FOLD ret-0.0f',
       0x338CF70:'AActor::HasAuthority',0x338ABB0:'AActor::GetLocalRole',0x2DD7020:'AActor::GetRemoteRole',
       0x3BBF3C0:'APawn::SpawnDefaultController',0x36DEE20:'AController::InitPlayerState',0x36E2B60:'AController::Possess'}
def sweep(start,label,maxlen=0x3000):
    pos=start; maxt=start; out=[]; end=None
    while pos-start<maxlen:
        try: ins=next(md.disasm(b[pos:pos+16], im.rva2va(pos)))
        except StopIteration: break
        for op in ins.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.index==0 and op.mem.disp in (0x160,0x72):
                out.append(('ROLE',pos,ins.mnemonic+' '+ins.op_str))
        if ins.operands and ins.operands[0].type==capstone.x86.X86_OP_IMM and ins.mnemonic[0]=='j':
            t=ins.operands[0].imm-im.imagebase
            if t>maxt and t-start<maxlen: maxt=t
        if ins.mnemonic in ('call','jmp') and ins.operands and ins.operands[0].type==capstone.x86.X86_OP_IMM:
            t=ins.operands[0].imm-im.imagebase
            if t in NAMED: out.append(('CALL',pos,NAMED[t]+' '+hex(t)))
        pos+=ins.size
        if ins.mnemonic in ('ret','jmp') and pos>maxt:
            end=pos; break
    pgs={}
    e=end or pos
    for p in range(start&~0xFFF,e,4096): pgs[hex(p)]=sum(1 for x in b[p:p+4096] if x)
    print('=== %-42s %s  size~%s  pages %s'%(label,hex(start),hex((end or pos)-start),pgs))
    for k,p,d in out: print('    %-5s %s  %s'%(k,hex(p),d))
    if not out: print('     (no role read, no netmode call, no fold/stub call)')
if __name__=='__main__':
    for spec in sys.argv[1:]:
        a,_,n=spec.partition(':'); sweep(int(a,16), n or a)
