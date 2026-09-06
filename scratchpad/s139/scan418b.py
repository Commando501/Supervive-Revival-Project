import struct, capstone, sys
d=open("dumps/merged13.dump.exe",'rb').read()
TXT=(0x1000,0x1000+0x07649000)
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
DISP=int(sys.argv[1],16) if len(sys.argv)>1 else 0x418
pat=struct.pack("<i",DISP)
res={}
i=TXT[0]
cnt=0
while True:
    j=d.find(pat,i,TXT[1])
    if j<0: break
    i=j+1
    # skip if page all-zero-ish around? not needed
    for st in range(max(TXT[0],j-15), j):
        try:
            ins=next(md.disasm(d[st:st+16], st))
        except StopIteration:
            continue
        if st+ins.size<=j: continue
        ok=False
        for op in ins.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.disp==DISP:
                ok=True
        if ok:
            res[st]=(ins.mnemonic, ins.op_str, ins.size)
            break
    cnt+=1
print("candidates:",cnt," decoded:",len(res))
# classify write vs read
writes=[]; reads=[]
for a,(m,o,s) in sorted(res.items()):
    first=o.split(',')[0].strip()
    if first.startswith('qword') or first.startswith('xmmword') or first.startswith('dword') or first.startswith('byte') or first.startswith('word') or first.startswith('['):
        writes.append((a,m,o))
    else:
        reads.append((a,m,o))
print("=== WRITES to [*+0x%X] : %d ==="%(DISP,len(writes)))
for a,m,o in writes: print("0x%08X  %s %s"%(a,m,o))
print("=== READS : %d (first 40) ==="%len(reads))
for a,m,o in reads[:40]: print("0x%08X  %s %s"%(a,m,o))
