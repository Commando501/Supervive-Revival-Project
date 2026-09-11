import struct,json,sys
p=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
d=open(p,'rb').read()
secs=json.load(open(r'scratchpad/s132/l6/secs.json'))
EXEC=[(nm,va,vs,ra,rs) for nm,va,vs,ra,rs,ch in secs if ch & 0x20000000]
REGS=['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']+['r%d'%i for i in range(8,16)]

def plus1_sites(b):
    """yield (offset, length, regnum, kind) for every '+1 on a 64-bit reg' encoding"""
    n=len(b)
    for i in range(n-4):
        c0=b[i]
        if c0 in (0x48,0x49):
            hi=8 if c0==0x49 else 0
            c1=b[i+1]
            if c1==0xFF and 0xC0<=b[i+2]<=0xC7:            # inc r64
                yield i,3,hi+(b[i+2]-0xC0),'inc'
            elif c1==0x83 and 0xC0<=b[i+2]<=0xC7 and b[i+3]==0x01:   # add r64,1
                yield i,4,hi+(b[i+2]-0xC0),'add1'
            elif c1==0x83 and 0xE8<=b[i+2]<=0xEF and b[i+3]==0xFF:   # sub r64,-1
                yield i,4,hi+(b[i+2]-0xE8),'sub-1'
            elif c1==0x81 and 0xC0<=b[i+2]<=0xC7 and b[i+3:i+7]==b'\x01\x00\x00\x00':
                yield i,7,hi+(b[i+2]-0xC0),'add1_32'
        if c0 in (0x48,0x49,0x4C,0x4D) and b[i+1]==0x8D:   # lea r64,[r64+1]
            mrm=b[i+2]
            if 0x40<=mrm<=0x7F and (mrm&7) not in (4,) and b[i+3]==0x01:
                dst=((mrm>>3)&7)+(8 if c0 in (0x4C,0x4D) else 0)
                yield i,4,dst,'lea+1'

def transfers(b):
    """yield (offset,length,kind,regnum_or_None,desc)"""
    n=len(b)
    for i in range(n-1):
        c0=b[i]
        if c0==0xFF:
            m=b[i+1]
            if 0xE0<=m<=0xE7: yield i,2,'jmp_reg',m-0xE0,'jmp %s'%REGS[m-0xE0]
            elif 0xD0<=m<=0xD7: yield i,2,'call_reg',m-0xD0,'call %s'%REGS[m-0xD0]
            elif m==0x25: yield i,6,'jmp_ripmem',None,'jmp [rip+..]'
            elif m==0x15: yield i,6,'call_ripmem',None,'call [rip+..]'
        elif c0==0x41 and i+2<n:
            m=b[i+2]
            if b[i+1]==0xFF:
                if 0xE0<=m<=0xE7: yield i,3,'jmp_reg',8+(m-0xE0),'jmp %s'%REGS[8+m-0xE0]
                elif 0xD0<=m<=0xD7: yield i,3,'call_reg',8+(m-0xD0),'call %s'%REGS[8+m-0xD0]

W=int(sys.argv[1]) if len(sys.argv)>1 else 40
tot_bytes=0; hits=[]
p1n=0; trn=0
for nm,va,vs,ra,rs in EXEC:
    b=d[ra:ra+rs]; tot_bytes+=len(b)
    tr={}
    for off,ln,kind,reg,desc in transfers(b):
        if reg is not None: tr.setdefault(reg,[]).append((off,kind,desc))
        trn+=1
    for reg in tr: tr[reg].sort()
    import bisect
    for off,ln,reg,kind in plus1_sites(b):
        p1n+=1
        lst=tr.get(reg)
        if not lst: continue
        offs=[x[0] for x in lst]
        j=bisect.bisect_left(offs,off+ln)
        while j<len(offs) and offs[j]<=off+W:
            hits.append((nm,va+off,kind,REGS[reg],lst[j][2],offs[j]-off,ra+off))
            j+=1
print('scanned %d bytes of executable sections; +1 sites=%d ; reg-indirect transfers=%d ; window=%d'%(tot_bytes,p1n,trn,W))
print('PAIRED HITS (+1 on reg, then jmp/call THAT SAME reg within window): %d'%len(hits))
for h in hits:
    print('   %-9s RVA %08x  %-6s %-4s -> %-10s (+%d)  file %08x'%(h[0],h[1],h[2],h[3],h[4],h[5],h[6]))
