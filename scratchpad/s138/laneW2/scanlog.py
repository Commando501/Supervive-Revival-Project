import sys,os,struct
os.chdir('G:/git/Supervive Revival Project'); sys.path.insert(0,'scratchpad/s138/laneW2')
from xdis import *
from logrec import rec
from capstone.x86 import X86_OP_IMM, X86_OP_MEM
pe=PE('dumps/merged13.dump.exe')
LOG=0x106B650
CALLEES=[('ALokiBotController::Tick (self)',0x556E9F0),
 ('0x5640FC0 Super::Tick',0x5640FC0),('GetServerTime 0x37D9D40',0x37D9D40),
 ('IsA-helper 0x54F8DC0',0x54F8DC0),('IsAbilityBlocked 0x55B1330',0x55B1330),
 ('IsIgnoringMovementInput 0x55B18E0',0x55B18E0),('GlideCheck 0x55713B0',0x55713B0),
 ('GetLokiAbilitySystem_BP 0x55AC880',0x55AC880),('GetWorld? 0x338C990',0x338C990),
 ('0x55A95A0',0x55A95A0),('0x1258BF0',0x1258BF0),('AuthHasActiveGameplayEffect 0x44685E0',0x44685E0),
 ('HazardJump 0x55708B0',0x55708B0),('BrokenPath 0x5563D50',0x5563D50),
 ('IsActorSafeFromDeathCircle 0x5664F70',0x5664F70),('DARK 0x5566870',0x5566870),
 ('BB GetValueAsBool 0x45F13A0',0x45F13A0),('IsA-helper 0x554A1A0',0x554A1A0),
 ('0x10A4470',0x10A4470)]
sep=chr(92)
for name,a in CALLEES:
    pg=a&~0xFFF
    if sum(1 for c in pe.read(pg,0x1000) if c)==0:
        print('%-42s DARK PAGE - cannot scan'%name); continue
    s=walk(pe,a,0x3000)
    ks=sorted(s)
    hits=[]
    for idx,k in enumerate(ks):
        ins=s[k]
        if ins.mnemonic=='call' and ins.operands and ins.operands[0].type==X86_OP_IMM and ins.operands[0].imm==LOG:
            recaddr=None
            for p in ks[max(0,idx-10):idx]:
                i2=s[p]
                if i2.mnemonic=='lea' and i2.op_str.startswith('rdx') and i2.operands[1].type==X86_OP_MEM and i2.operands[1].mem.base==0x29:
                    recaddr=i2.address+i2.size+i2.operands[1].mem.disp
            hits.append((k,recaddr))
    print('%-42s ext=0x%X-0x%X BasicLog sites: %d'%(name,ks[0],ks[-1]+s[ks[-1]].size,len(hits)))
    for site,ra in hits:
        if ra is None:
            print('      site 0x%08X  (record not resolved)'%site); continue
        try:
            r=rec(ra)
            print('      site 0x%08X rec .rdata 0x%08X [%s] fmt@0x%08X %r  (%s:%d)'%(
                site,ra,r['verb'],r['fmt_rva'],r['fmt'],r['file'].split(sep)[-1],r['line']))
        except Exception as e:
            print('      site 0x%08X rec 0x%08X decode-fail %r'%(site,ra,e))
