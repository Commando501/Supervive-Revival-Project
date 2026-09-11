import struct,json
from capstone import *
from capstone.x86 import *
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
D=open(P,'rb').read(); IB=0x7FF608F40000
LO,HI=0x1000,0x1000+0x07649000
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
pat=b'\xc8\x16\x00\x00'
cands=[]
s=LO
while True:
    i=D.find(pat,s)
    if i<0 or i>=HI: break
    cands.append(i); s=i+1
print("byte candidates in .text:",len(cands))
# adjudicate: try starts D-1..D-15
res={}
for cpos in cands:
    found=[]
    for back in range(1,16):
        st=cpos-back
        if st<LO: continue
        g=list(md.disasm(D[st:st+16],st))
        if not g: continue
        ins=g[0]
        if ins.address+ins.size <= cpos+3: continue   # must cover disp bytes
        ok=False; kind=None
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.disp==0x16C8: ok=True; kind='mem'
            if op.type==X86_OP_IMM and op.imm==0x16C8: ok=True; kind=kind or 'imm'
        if ok:
            found.append((st,ins,kind))
    res[cpos]=found
nz=sum(1 for k,v in res.items() if v)
print("candidates with >=1 covering interpretation:",nz)
print("candidates with ZERO interpretation (data / misaligned):",len(cands)-nz)
# Which sites are MEM with disp 0x16C8 (any base) - dedupe by (start,mnemonic)
rows=[]
for cpos,v in res.items():
    for st,ins,kind in v:
        rows.append((st,ins.mnemonic,ins.op_str,kind,ins.bytes.hex(' ')))
rows.sort()
print("total (start,insn) interpretations:",len(rows))
# mandated positive control
mand={0x055C2438,0x055C2441,0x055C2469}
got={r[0] for r in rows}
print("POSITIVE CONTROL 3/3:", all(m in got for m in mand), [hex(m) for m in mand if m not in got])
json.dump([[hex(a),b,c,d,e] for a,b,c,d,e in rows],open(r"G:\git\Supervive Revival Project\scratchpad\s140\verify-L6\rows.json","w"),indent=0)
