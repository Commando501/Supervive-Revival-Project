import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
from capstone import x86
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im = Img()
sec = [s for s in im.sections if s['name']=='.text'][0]
base = sec['va']; size=max(sec['vsz'],sec['rawsz'])
data = im.data[sec['praw']:sec['praw']+size]
PAT=bytes([0xb0,0x12,0x00,0x00])
hits=[]; i=data.find(PAT)
while i!=-1: hits.append(base+i); i=data.find(PAT,i+1)

REGN = {x86.X86_REG_RSP:'rsp', x86.X86_REG_RBP:'rbp', x86.X86_REG_RIP:'rip'}
rows=[]
for h in hits:
    best=None
    for s in range(h-15,h+1):
        try: b=im.read(s,16)
        except ValueError: continue
        try: ins=next(CS.disasm(b,s))
        except StopIteration: continue
        if not(s<=h and s+ins.size>=h+4): continue
        mems=[op for op in ins.operands if op.type==x86.X86_OP_MEM and op.mem.disp==0x12b0]
        imms=[op for op in ins.operands if op.type==x86.X86_OP_IMM and op.imm==0x12b0]
        score = 2 if mems else (1 if imms else 0)
        cand=(score, -(h-s), s, ins, mems, imms)
        if best is None or cand[:2] > best[:2]: best=cand
    score,_,s,ins,mems,imms = best
    if mems:
        m=mems[0].mem
        bn = CS.reg_name(m.base) if m.base else None
        idx = CS.reg_name(m.index) if m.index else None
        w = mems[0].size
        acc = mems[0].access  # 1=read 2=write 3=rw
        cls = 'STACK' if bn in ('rsp','rbp') else ('RIP' if bn=='rip' else 'OBJ')
        rows.append((h,s,ins.mnemonic,ins.op_str,cls,bn,idx,w,acc))
    elif imms:
        rows.append((h,s,ins.mnemonic,ins.op_str,'IMM',None,None,0,0))
    else:
        rows.append((h,s,ins.mnemonic,ins.op_str,'NONE',None,None,0,0))

cnt=collections.Counter(r[4] for r in rows)
print("partition:", dict(cnt), "total", len(rows))
print()
print("=== NON-STACK, NON-IMM, NON-NONE (object-relative) ===")
for r in sorted(rows):
    if r[4]=='OBJ':
        h,s,mn,ops,cls,bn,idx,w,acc = r
        accs = {1:'READ',2:'WRITE',3:'RW'}.get(acc, str(acc))
        print(f"  {s:#010x}  {mn:8s} {ops:45s} base={bn} idx={idx} width={w} access={accs}")
print()
print("=== IMM ===")
for r in sorted(rows):
    if r[4]=='IMM': print(f"  {r[1]:#010x}  {r[2]} {r[3]}")
print()
print("=== NONE (no 0x12b0 operand at any covering decode) ===")
for r in sorted(rows):
    if r[4]=='NONE': print(f"  hit={r[0]:#010x} bestdecode {r[1]:#010x} {r[2]} {r[3]}")
print()
print("=== RIP ===")
for r in sorted(rows):
    if r[4]=='RIP': print(f"  {r[1]:#010x} {r[2]} {r[3]}")
