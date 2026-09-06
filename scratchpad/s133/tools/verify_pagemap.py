#!/usr/bin/env python3
"""Independent verification of the crashpad MemoryInfoList .text decryption map.
Written from the MINIDUMP_MEMORY_INFO_LIST spec, not from the other lane's code."""
import struct, glob, os, collections, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
TEXT_OFF, TEXT_SZ, PAGE = 0x1000, 0x7649000, 4096
NPAGES = TEXT_SZ//PAGE + (1 if TEXT_SZ%PAGE else 0)
NOACCESS, EXECUTE_READ = 0x01, 0x20

def streams(f):
    f.seek(0); sig,ver,n,rva = struct.unpack_from('<IIII', f.read(32), 0)
    assert sig==0x504d444d
    f.seek(rva); d=f.read(12*n)
    return {t:(sz,r) for t,sz,r in (struct.unpack_from('<III',d,i*12) for i in range(n))}

def modules(f, sz, rva):
    f.seek(rva); n=struct.unpack('<I',f.read(4))[0]; out=[]
    for _ in range(n):
        b=f.read(108); base,size,cs,ts,nr=struct.unpack('<QIIII',b[:24])
        cur=f.tell(); f.seek(nr); ln=struct.unpack('<I',f.read(4))[0]
        nm=f.read(ln).decode('utf-16-le','replace'); f.seek(cur)
        out.append((base,size,nm))
    return out

def meminfo(f, sz, rva):
    # MINIDUMP_MEMORY_INFO_LIST: u32 SizeOfHeader, u32 SizeOfEntry, u64 NumberOfEntries
    f.seek(rva); hs,es = struct.unpack('<II', f.read(8)); ne = struct.unpack('<Q', f.read(8))[0]
    f.seek(rva+hs); out=[]
    for _ in range(ne):
        b=f.read(es)
        # BaseAddress,AllocationBase u64; AllocationProtect u32; __alignment1 u32;
        # RegionSize u64; State u32; Protect u32; Type u32; __alignment2 u32
        ba,ab,ap,_a1,rs,st,pr,ty,_a2 = struct.unpack_from('<QQIIQIIII', b, 0)
        out.append((ba,rs,pr,st,ty,ab))
    return out

files=sorted(p for p in glob.glob('dumps/crashpad-*/reports/*.dmp') if os.path.getsize(p)>1000)
union=bytearray(NPAGES); prot=collections.Counter(); ok=0; per=[]
seen=set()
for p in files:
    key=os.path.basename(p)
    if key in seen: continue       # same crash archived twice (-DEATH + follow-up)
    seen.add(key)
    try:
        with open(p,'rb') as f:
            st=streams(f)
            if 4 not in st or 16 not in st: continue
            mods=modules(f,*st[4])
            sup=[m for m in mods if 'SUPERVIVE-Win64' in m[2]]
            if not sup: continue
            base=sup[0][0]
            lo,hi = base+TEXT_OFF, base+TEXT_OFF+TEXT_SZ
            bm=bytearray(NPAGES); tiled=0
            for ba,rs,pr,stt,ty,ab in meminfo(f,*st[16]):
                if ba+rs<=lo or ba>=hi: continue
                a=max(ba,lo); b2=min(ba+rs,hi)
                np=(b2-a)//PAGE; tiled+=np
                prot[pr]+=np
                if pr==EXECUTE_READ:
                    s=(a-lo)//PAGE
                    for i in range(s,s+np): bm[i]=1
            if tiled!=NPAGES: per.append((key,sum(bm),tiled,'TILE-MISMATCH')); continue
            ok+=1; per.append((key,sum(bm),tiled,''))
            for i in range(NPAGES):
                if bm[i]: union[i]=1
    except Exception as e:
        per.append((key,0,0,'ERR '+str(e)[:30]))
print(f'distinct crash dumps parsed: {ok}')
print(f'[CTRL] .text tiles to exactly {NPAGES} pages: {sum(1 for r in per if r[3]=="")}/{len(per)}')
print('protection histogram over .text (page-observations):')
names={0x01:'NOACCESS',0x20:'EXECUTE_READ',0x02:'READONLY',0x04:'READWRITE',0x40:'EXECUTE_READWRITE',0x80:'EXECUTE_WRITECOPY',0x08:'WRITECOPY',0x10:'EXECUTE'}
tot=0
for k,v in prot.most_common():
    print(f'   {names.get(k,hex(k)):20s} {v:12d}'); tot+=v
print(f'   TOTAL {tot} ; ok*{NPAGES} = {ok*NPAGES} ; match={tot==ok*NPAGES}')
d=[c for _,c,_,e in per if e=='']
print(f'decrypted pages per crash: min {min(d)} median {sorted(d)[len(d)//2]} max {max(d)}')
print(f'UNION over {ok} distinct crashes: {sum(union)} / {NPAGES} = {sum(union)/NPAGES*100:.2f}%')
# vs merged6
f=open('dumps/merged6.dump.exe','rb'); m=bytearray(NPAGES); f.seek(TEXT_OFF)
for i in range(NPAGES):
    b=f.read(PAGE)
    if not b: break
    if b.count(0)!=len(b): m[i]=1
only_crash=sum(1 for i in range(NPAGES) if union[i] and not m[i])
only_merged=sum(1 for i in range(NPAGES) if m[i] and not union[i])
comb=sum(1 for i in range(NPAGES) if union[i] or m[i])
print(f'merged6: {sum(m)}   crash-only: {only_crash}   merged6-only: {only_merged}')
print(f'CEILING (union of both) = {comb} / {NPAGES} = {comb/NPAGES*100:.2f}%')
