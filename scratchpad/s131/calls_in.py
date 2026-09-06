import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s131\tools")
import fkdis, rectab
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
rectab.P['merged4']=r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
recs=rectab.scan('merged4')
byimpl={}
for r in recs: byimpl.setdefault(r['impl'],[]).append(r['name'])
img=fkdis.Img(rectab.P['merged4']); IB=img.imagebase
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
lo,hi=int(sys.argv[1],0),int(sys.argv[2],0)
for ins in md.disasm(img.read(lo,hi-lo), IB+lo):
    if ins.mnemonic!="call": continue
    for op in ins.operands:
        if op.type==2:
            t=op.imm-IB
            nm = byimpl.get(t)
            f = rectab.FOLD.get(t)
            print("  0x%08X  call 0x%08X  %s%s"%(ins.address-IB,t, (",".join(nm[:3]) if nm else ""), (" ["+f+"]" if f else "")))
        elif op.type==3 and op.mem.base!=41:
            print("  0x%08X  call %s  (indirect/vtable)"%(ins.address-IB, ins.op_str))
