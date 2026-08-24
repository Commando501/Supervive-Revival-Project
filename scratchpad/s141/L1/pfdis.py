import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone, struct
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns
lo=int(sys.argv[1],0); hi=int(sys.argv[2],0)
for r in sorted(ins):
    if lo<=r<hi:
        i=ins[r]
        extra=''
        # rip-relative -> resolve
        for op in i.operands:
            if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
                tgt=r+i.size+op.mem.disp
                try:
                    b=im.read(tgt,8)
                    dv=struct.unpack('<d',b)[0]; fv=struct.unpack('<f',b[:4])[0]
                    extra=f"   ; ->{tgt:#x} bytes={b.hex()} d={dv!r} f={fv!r}"
                except Exception: extra=f"   ; ->{tgt:#x}"
        p=sorted(c.pred.get(r,()))
        pm=f"  <-preds {[hex(x) for x in p]}" if len(p)>1 or (p and p[0]+ins[p[0]].size!=r) else ''
        print(f"{r:#010x}  {bytes(i.bytes).hex():24s} {i.mnemonic:10s} {i.op_str}{extra}{pm}")
