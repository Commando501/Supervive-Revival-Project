import ctypes,struct
from ctypes import wintypes
from collections import Counter
PID=43456; BASE=0x7FF608F40000; NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
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
def nmOf(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
PC=0x1B3234713C0; PH=0x1B399FF5580; A1=0x1B3F58BC5E0; PAWN1=0x1B3E6922AE0; PAWN2=0x1B302F7D560; A2=0x1B3F75EAEA0
print("=== POSITIVE CONTROL: controller-side offsets on the PLAYER'S OWN PlayerController ===")
print("    (if 0x3F8/0x408/0x198 are really Pawn/Character/Instigator, they must resolve HERE too)")
for off,l in ((0x3F8,"Pawn"),(0x408,"Character"),(0x198,"Instigator"),(0x150,"Owner"),(0x3C0,"PlayerState")):
    v=u64(rpm(PC+off,8),0)
    tag=""
    if v==PH: tag="  <== THE PLAYER HERO (control PASSES)"
    print(f"  PC+0x{off:04X} {l:12s} = 0x{v:X}"+(f"  -> {nmOf(v)}" if ptr(v) else "")+tag)
print("\n=== bot pawn locations (re-read now) + capsule half-height ===")
for lbl,o in (("bot1",PAWN1),("bot2",PAWN2),("player",PH)):
    root=u64(rpm(o+0x1B0,8),0)
    if ptr(root):
        b=rpm(root+0x158,24)
        print(f"  {lbl:7s} 0x{o:X} root={nmOf(root):20s} loc=({struct.unpack_from('<d',b,0)[0]:.4f}, {struct.unpack_from('<d',b,8)[0]:.4f}, {struct.unpack_from('<d',b,16)[0]:.4f})")
print("\n=== Is Outer==PersistentLevel INFORMATIVE? distribution over all live non-CDO ACTORS ===")
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
nchunks=(numEl+PERCHUNK-1)//PERCHUNK; cp=rpm(objectsPtr,nchunks*8)
_ch={}
def chain(c):
    if c in _ch: return _ch[c]
    out=[];cur=c;d=0
    while ptr(cur) and d<24:
        b=rpm(cur+0x20,4); out.append(fname(u32(b,0)) if b else "?")
        b=rpm(cur+0x48,8); cur=u64(b,0) if b else 0; d+=1
    _ch[c]=out; return out
outers=Counter()
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
        if fname(u32(b,8)).startswith("Default__"): continue
        if "Actor" not in chain(c): continue
        ov=u64(b,0x10); outers[nmOf(ov) if ptr(ov) else "-"]+=1
tot=sum(outers.values())
print(f"  live non-CDO actors = {tot}")
for k,v in outers.most_common(6):
    print(f"    {v:6} ({100.0*v/tot:5.1f}%)  Outer={k}")
