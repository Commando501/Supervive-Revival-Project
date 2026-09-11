import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
ENTRY=0x035EC850
SPAN=(0x035EC850,0x035EE593)
c = CFGMOD.CFG(im, ENTRY)
ins=c.insns
print(f"ENGINE PhysFalling entry {ENTRY:#x}  image={IMG}")
print(f"  instructions      : {len(ins)}")
print(f"  calls             : {len(c.calls)}  (direct {sum(1 for v in c.calls.values() if v is not None)}, indirect {sum(1 for v in c.calls.values() if v is None)})")
print(f"  indirect jumps    : {len(c.indirect_jumps)} {[hex(x) for x in c.indirect_jumps]}")
print(f"  decode failures   : {len(c.decode_failures)} {[hex(x) for x in c.decode_failures]}")
print(f"  noreturn cands    : {len(c.noreturn_candidates)}")
rets=[r for r,i in ins.items() if i.mnemonic in ('ret','retf')]
print(f"  ret instructions  : {len(rets)} {[hex(x) for x in sorted(rets)]}")
# byte coverage
covered=set()
out_of_span=[]
for r,i in ins.items():
    for k in range(i.size): covered.add(r+k)
    if not (SPAN[0]<=r<SPAN[1]): out_of_span.append(r)
span_bytes=set(range(SPAN[0],SPAN[1]))
print(f"  span              : {SPAN[0]:#x}..{SPAN[1]:#x} = {len(span_bytes)} bytes")
print(f"  covered in span   : {len(covered & span_bytes)} / {len(span_bytes)} = {100*len(covered&span_bytes)/len(span_bytes):.2f}%")
print(f"  covered outside   : {len(covered - span_bytes)} bytes at {len(set(out_of_span))} insn rvas")
if out_of_span:
    print("   out-of-span insn rvas:", [hex(x) for x in sorted(set(out_of_span))][:40])
gaps=[]
b=None
for x in range(SPAN[0],SPAN[1]):
    if x not in covered:
        if b is None: b=x
    else:
        if b is not None: gaps.append((b,x)); b=None
if b is not None: gaps.append((b,SPAN[1]))
print(f"  uncovered gaps    : {len(gaps)}")
for g in gaps: print(f"      {g[0]:#x}..{g[1]:#x} ({g[1]-g[0]} bytes) first16={im.read(g[0],min(16,g[1]-g[0])).hex()}")
import pickle
pickle.dump({'insns':{r:(i.mnemonic,i.op_str,i.size,bytes(i.bytes)) for r,i in ins.items()},
             'succ':{k:set(v) for k,v in c.succ.items()},'pred':{k:set(v) for k,v in c.pred.items()},
             'calls':dict(c.calls)}, open('L1/cfg.pkl','wb'))
