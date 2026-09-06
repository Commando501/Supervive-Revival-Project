import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
from capstone import x86
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im = Img()
sec = [s for s in im.sections if s['name']=='.text'][0]
base, size = sec['va'], max(sec['vsz'], sec['rawsz'])
print(f".text va={base:#x} size={size:#x}")
data = im.data[sec['praw']:sec['praw']+size]

PAT = bytes([0xb0,0x12,0x00,0x00])
hits=[]
i = data.find(PAT)
while i != -1:
    hits.append(base+i)
    i = data.find(PAT, i+1)
print("raw dword-pattern hits in .text:", len(hits))

# INDEPENDENT ADJUDICATOR: for each hit, try every start s in [h-15,h] and accept a decode
# whose byte range covers [h,h+4).  Collect ALL accepted decodes (do not stop at first).
res = collections.defaultdict(list)
for h in hits:
    for s in range(h-15, h+1):
        try:
            b = im.read(s,16)
        except ValueError:
            continue
        try:
            ins = next(CS.disasm(b, s))
        except StopIteration:
            continue
        if not (s <= h and s+ins.size >= h+4):
            continue
        memdisp = [op.mem.disp for op in ins.operands if op.type==x86.X86_OP_MEM]
        imms    = [op.imm for op in ins.operands if op.type==x86.X86_OP_IMM]
        kind=None
        if 0x12b0 in memdisp: kind='MEM'
        elif 0x12b0 in imms: kind='IMM'
        else: kind='OTHER'
        res[h].append((s, ins.mnemonic, ins.op_str, ins.size, kind,
                       [ (op.mem.base, op.mem.index, op.mem.disp, op.size, op.access) for op in ins.operands if op.type==x86.X86_OP_MEM ]))
print("hits with >=1 covering decode:", sum(1 for h in res if res[h]))
print("hits with NO covering decode:", sum(1 for h in hits if h not in res or not res[h]))

import json
out=[]
for h in hits:
    cands = res.get(h,[])
    # prefer the decode that classifies MEM with disp 0x12b0
    mem = [c for c in cands if c[4]=='MEM']
    imm = [c for c in cands if c[4]=='IMM']
    out.append((h, mem, imm, cands))
with open('verify-L5/scan_raw.txt','w') as f:
    for h,mem,imm,cands in out:
        f.write(f"HIT {h:#010x}  nmem={len(mem)} nimm={len(imm)} ncand={len(cands)}\n")
        for c in cands:
            f.write(f"    start={c[0]:#010x} {c[1]} {c[2]} size={c[3]} kind={c[4]} mem={c[5]}\n")
print("wrote verify-L5/scan_raw.txt")
