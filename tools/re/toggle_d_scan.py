# Resolve the feature-toggle readiness object D from a hero CMC (identity-vfn188 chain), print D's class, then
# enumerate ALL live instances of D's class with their readiness byte[+0xB3] bit6 (0x40). Optionally POKE bit6 set.
#   usage: toggle_d_scan.py <PID> <BASE-hex> <CMC-hex> [--poke]
# Chain (this build): applier=[CMC+0xC0]; vfn188=[[applier]+0x188] (identity for the applier); C=[applier+0x258];
#   D=[C+0x5A0]; readiness=byte[D+0xB3] bit6. D is (hoped) a UObject: class@+0x18, name@+0x20.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CMC=int(sys.argv[3],16); POKE="--poke" in sys.argv
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wpm(a,data):
    r=ctypes.c_size_t(0); buf=(ctypes.c_ubyte*len(data))(*data)
    return bool(k32.WriteProcessMemory(h,ctypes.c_void_p(a),buf,len(data),ctypes.byref(r)) and r.value==len(data))
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a): b=rpm(a,8); return u64(b,0) if b else 0
def u8(a): b=rpm(a,1); return b[0] if b else -1
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if wide else 1))
                    if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r
def oname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o): c=p(o+0x18); return oname(c) if looksptr(c) else "?"
# resolve D
applier=p(CMC+0xC0)
C=p(applier+0x258)
D=p(C+0x5A0)
print(f"applier=0x{applier:X} C=0x{C:X} D=0x{D:X}")
if not looksptr(D): print("D not a ptr — abort"); sys.exit(1)
dname=oname(D); dcls=ocls(D)
print(f"D name='{dname}' class='{dcls}' readiness byte[+0xB3]=0x{u8(D+0xB3):02X} bit6={ (u8(D+0xB3)>>6)&1 }")
if dcls=="?" or dcls=="": print("D is NOT a UObject (no class) — cannot enumerate by class."); sys.exit(0)
# enumerate all instances of D's class, read readiness
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14); numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8); found=[];
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o=u64(items,j*STRIDE)
        if not looksptr(o): continue
        if ocls(o)==dcls: found.append(o)
print(f"\n{len(found)} live instance(s) of class '{dcls}':")
nready=nnot=0
for o in found:
    b=u8(o+0xB3); bit6=(b>>6)&1
    if bit6: nready+=1
    else: nnot+=1
    print(f"  0x{o:012X} byte[+0xB3]=0x{b:02X} bit6={bit6}{' <-- NOT READY' if not bit6 else ''}")
    if POKE and not bit6:
        wpm(o+0xB3, bytes([b|0x40]))
        print(f"      -> POKED to 0x{(b|0x40):02X}")
print(f"\nready={nready} notReady={nnot}  (poke={'ON' if POKE else 'OFF'})")
