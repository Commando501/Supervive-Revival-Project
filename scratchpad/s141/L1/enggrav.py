import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
FOLD={0x0F7EC20:'FOLD void',0x0F7EB50:'FOLD null/false',0x0F7EB60:'FOLD false',0x0B9E1F0:'FOLD true',0x0FC6CF0:'FOLD 0.0f'}
for ent,label in [(0x035E3650,'ENGINE UMovementComponent::GetGravityZ (base of the Loki override)')]:
    c=CFGMOD.CFG(im,ent); ins=c.insns
    print(f"=========== {label}  {ent:#x}  page={im.page_nonzero(ent)}/4096 ===========")
    print(f"  insns={len(ins)} calls={len(c.calls)} indirect_jmp={len(c.indirect_jumps)}")
    for r in sorted(ins):
        i=ins[r]; ex=''
        for op in i.operands:
            if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
                t=r+i.size+op.mem.disp
                try:
                    b=im.read(t,8); ex=f"  ; ->{t:#x} f={struct.unpack('<f',b[:4])[0]!r}"
                except Exception: ex=f"  ; ->{t:#x}"
        if i.mnemonic=='call' and i.operands[0].type==X.X86_OP_IMM:
            t=i.operands[0].imm
            g='FOLD' if t in FOLD else ('DARK' if im.page_nonzero(t)==0 else 'REAL')
            ex+=f"   ; callee {t:#x} [{g}] {FOLD.get(t,'')}"
        if i.mnemonic=='call' and i.operands[0].type==X.X86_OP_MEM:
            ex+=f"   ; INDIRECT disp={i.operands[0].mem.disp:#x}"
        print(f"  {r:#010x}  {bytes(i.bytes).hex():24s} {i.mnemonic:10s} {i.op_str}{ex}")
