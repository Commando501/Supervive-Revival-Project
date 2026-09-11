"""L6 step 2: adjudicate every candidate. Two independent instruments per candidate:
   (A) recursive-descent CFG from the containing pdata function's begin_rva
   (B) linear sweep over [begin,end) of that function
   A hit counts only if it is a real capstone operand with disp==0x16C8 or imm==0x16C8.
"""
import sys, bisect, csv, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86 = capstone.x86
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im = Img()

TARGET = 0x16C8

# ---- load pdata union ----
begins=[]; rows=[]
with open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv") as f:
    r = csv.reader(f); next(r)
    for a,b,sz,u,seen in r:
        begins.append(int(a,16)); rows.append((int(a,16), int(b,16), int(sz), int(seen)))
begins.sort(); rows.sort()
print(f"pdata_union: {len(rows)} ranges")
def fn_of(rva):
    i = bisect.bisect_right(begins, rva)-1
    if i < 0: return None
    b,e,sz,seen = rows[i]
    return (b,e,sz,seen) if b <= rva < e else None

# PC on the function map: 0x055C2469 must live in a function whose begin <= 0x055C2430
f = fn_of(0x055C2469)
print(f"  FN-MAP CTRL fn_of(0x055C2469) = {f if f is None else (hex(f[0]),hex(f[1]),f[2],f[3])}")
f2 = fn_of(0x035EB13A)
print(f"  FN-MAP CTRL fn_of(0x035EB13A) = {f2 if f2 is None else (hex(f2[0]),hex(f2[1]),f2[2],f2[3])}  (engine PerformMovement 0x035E9EC0)")

cands = [int(l,16) for l in open('L6/cands.txt')]

def hits_in_insns(insns):
    out=[]
    for i in insns:
        for op in i.operands:
            if op.type == X86.X86_OP_MEM and op.mem.disp == TARGET:
                out.append((i.address, 'MEM', i)); break
            if op.type == X86.X86_OP_IMM and op.imm == TARGET:
                out.append((i.address, 'IMM', i)); break
    return out

def cfg_hits(entry):
    try:
        c = CFG(im, entry, maxinsn=200000)
    except Exception as ex:
        return None, str(ex)
    return hits_in_insns([c.insns[k] for k in sorted(c.insns)]), None

def linear_hits(b, e):
    try: data = im.read(b, e-b)
    except ValueError: return []
    return hits_in_insns(list(CS.disasm(data, b)))

seen_fn = {}
report = []
nofn = []
for c in cands:
    # the instruction START is at most 15 bytes before the disp bytes
    f = fn_of(c)
    if f is None:
        # try the instruction-start window
        f = None
        for back in range(1,16):
            f = fn_of(c-back)
            if f: break
    if f is None:
        nofn.append(c); continue
    key=(f[0],f[1])
    if key not in seen_fn:
        ch, err = cfg_hits(f[0])
        lh = linear_hits(f[0], f[1])
        seen_fn[key] = (ch, err, lh, f)
    report.append((c, key))

print(f"\ncandidates: {len(cands)};  mapped to {len(seen_fn)} distinct pdata functions;  unmapped: {len(nofn)}")
if nofn: print("  UNMAPPED candidate byte positions:", [hex(x) for x in nofn])

print("\n=== PER-FUNCTION ADJUDICATION ===")
allhits = {}
for (b,e),(ch,err,lh,f) in sorted(seen_fn.items()):
    cset = set(a for a,_,_ in (ch or []))
    lset = set(a for a,_,_ in lh)
    tag = ""
    if err: tag = f"  CFG-ERR:{err}"
    if cset != lset: tag += f"  *** CFG/LINEAR DISAGREE: only-cfg={[hex(x) for x in sorted(cset-lset)]} only-lin={[hex(x) for x in sorted(lset-cset)]}"
    print(f"\nFN {b:#010x}-{e:#010x} size={f[2]} seen_in_dumps={f[3]}  cfg_hits={len(cset)} lin_hits={len(lset)}{tag}")
    for a,kind,i in sorted((ch or [])+lh, key=lambda t:(t[0],t[1])):
        if a in allhits: continue
        allhits[a]=(kind,i,b)
        rw = []
        # crude read/write classification from capstone regs_access
        try:
            _, wr = i.regs_access()
        except Exception: wr=()
        print(f"    {a:#010x}  {i.bytes.hex(' '):<24} {i.mnemonic} {i.op_str}   [{kind}]")

print("\n=== POSITIVE CONTROL: the three known sites ===")
for c in (0x055C2438, 0x055C2441, 0x055C2469):
    print(f"  {c:#x}: {'FOUND' if c in allhits else '*** MISSING -> INSTRUMENT BROKEN ***'}")
print(f"\nTOTAL distinct instructions touching disp/imm 0x16C8: {len(allhits)}")
import json
json.dump({hex(k):(v[0], v[1].mnemonic+' '+v[1].op_str, hex(v[2])) for k,v in allhits.items()}, open('L6/hits.json','w'), indent=1)
