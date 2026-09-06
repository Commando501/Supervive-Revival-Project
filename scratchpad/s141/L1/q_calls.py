import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns
FOLD={0x0F7EC20:'FOLD void',0x0F7EB50:'FOLD null/false',0x0F7EB60:'FOLD false',0x0B9E1F0:'FOLD true',0x0FC6CF0:'FOLD 0.0f'}
NAMED={0x035F4620:'quatrot A (gravity->world?)',0x035F4770:'quatrot B (world->gravity?)',
       0x035D5D20:'ENGINE CalcVelocity',0x035E64C0:'HasValidData'}
print("=== DIRECT CALLS ===")
seen={}
for r in sorted(c.calls):
    t=c.calls[r]
    if t is None: continue
    seen.setdefault(t,[]).append(r)
for t in sorted(seen):
    try:
        b=im.read(t,8).hex(); nz=im.page_nonzero(t)
    except Exception: b='??'; nz=-1
    tag=FOLD.get(t,'') or NAMED.get(t,'')
    grade='FOLD' if t in FOLD else ('DARK' if nz==0 else 'REAL')
    print(f"  {t:#010x} [{grade}] page={nz:4d} first8={b} x{len(seen[t])} at {[hex(x) for x in seen[t]]}  {tag}")
print("\n=== INDIRECT CALLS (vtable displacement) ===")
disp={}
for r in sorted(c.calls):
    if c.calls[r] is not None: continue
    i=ins[r]; op=i.operands[0]
    if op.type==X.X86_OP_MEM:
        d=op.mem.disp; bn=i.reg_name(op.mem.base) if op.mem.base else '-'
        disp.setdefault((d,bn),[]).append(r)
    else:
        disp.setdefault(('REG',i.op_str),[]).append(r)
VT={0x830:'PhysFalling',0x7A0:'NewFallVelocity',0x7B0:'CalcVelocity',0x4C0:'GetGravityZ',
    0x4C8:'GetMaxSpeed',0x7D0:'GetMaxAcceleration',0x660:'ComputeAnalogInputModifier',
    0xA50:'clears +0x16C8',0x838:'?',0x6B8:'HasValidData?'}
for k in sorted(disp, key=lambda x:(str(type(x[0])),x[0] if isinstance(x[0],int) else 0)):
    d,bn=k
    nm=VT.get(d,'') if isinstance(d,int) else ''
    ds=f"{d:#x}" if isinstance(d,int) else str(d)
    print(f"  disp {ds:>8s} base={bn:4s} x{len(disp[k]):2d}  {nm:28s} at {[hex(x) for x in disp[k]]}")
