import ctypes
from ctypes import wintypes
PID=43456; BASE=0x7FF608F40000
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def ptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(i):
    if i in _nc: return _nc[i]
    blk=i>>16; off=(i&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if ptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; w=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if w else 1))
                    if s: r=("".join(chr(s[k*2]|(s[k*2+1]<<8)) for k in range(ln)) if w else s.decode("latin1","replace"))
    _nc[i]=r; return r
def chain(c):
    out=[];d=0
    while ptr(c) and d<24:
        b=rpm(c+0x20,4); out.append(fname(u32(b,0)) if b else "?")
        b=rpm(c+0x48,8); c=u64(b,0) if b else 0; d+=1
    return out
_ch={}
def chain_m(c):
    if c not in _ch: _ch[c]=chain(c)
    return _ch[c]
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
nchunks=(numEl+PERCHUNK-1)//PERCHUNK; cp=rpm(objectsPtr,nchunks*8)
actors=[]; ctrls=[]
for ci in range(nchunks):
    ch=int.from_bytes(cp[ci*8:ci*8+8],"little")
    if not ptr(ch): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(ch,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o=u64(items,j*STRIDE)
        if not ptr(o): continue
        b=rpm(o+0x18,0x18)
        if not b: continue
        c=u64(b,0)
        if not ptr(c): continue
        cn=fname(u32(b,8))
        if cn.startswith("Default__"): continue
        ch2=chain_m(c)
        if "Actor" not in ch2: continue
        num=u32(b,12); idx=u32(b,8)
        actors.append((o,ch2[0],cn,num,u32(rpm(o+0x10,4),0)))
        if any(x=="Controller" for x in ch2): ctrls.append((o,ch2[0],cn,num,u32(rpm(o+0x10,4),0),tuple(ch2)))
print(f"live non-CDO ACTORS: {len(actors)}")
dyn=[a for a in actors if a[3]>2_000_000_000]
print(f"  with FName.Number > 2e9 (runtime-spawned counter): {len(dyn)}")
print(f"  with FName.Number == 0 or small (placed/startup)  : {len(actors)-len(dyn)}")
print("\n=== EVERY AController-DERIVED LIVE OBJECT (exact ancestor 'Controller') ===")
for o,leaf,nm,num,ii,ch2 in sorted(ctrls,key=lambda x:-x[3]):
    print(f"  0x{o:X}  idx={ii:<7} Number={num:<12} {leaf:34s} name={nm}")
    print(f"      chain: {' <- '.join(ch2)}")
print("\n=== 25 MOST RECENT runtime-spawned actors by the DECREASING Number counter ===")
for o,leaf,nm,num,ii in sorted(dyn,key=lambda x:x[3])[:25]:
    print(f"  Number={num:<12} idx={ii:<7} {leaf:44s} 0x{o:X}")
