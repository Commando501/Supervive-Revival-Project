# Enumerate live UObjects whose class name contains a substring; print byte[+0xB3] bit6 (the Get readiness bit).
# Optionally --poke to set bit6 on the ones that are 0x00 (not-ready) -> 0x40. Read-only unless --poke.
#   usage: config_ready_scan.py <PID> <BASE-hex> <classSubstr> [--poke]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); SUB=sys.argv[3]; POKE="--poke" in sys.argv
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
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14); numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8)
from collections import defaultdict
bycls=defaultdict(list)
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o=u64(items,j*STRIDE)
        if not looksptr(o): continue
        cn=ocls(o)
        if SUB.lower() in cn.lower() and not oname(o).startswith("Default__"):
            bycls[cn].append(o)
poked=0
for cn in sorted(bycls):
    insts=bycls[cn]; nr=sum(1 for o in insts if (u8(o+0xB3)>>6&1)==0)
    print(f"=== {cn}: {len(insts)} inst, {nr} not-ready (byte[+0xB3] bit6=0) ===")
    for o in insts[:20]:
        b=u8(o+0xB3); bit6=(b>>6)&1
        tag=" NOT-READY" if not bit6 else ""
        if POKE and not bit6 and b!=-1:
            if wpm(o+0xB3, bytes([b|0x40])): poked+=1; tag+=" -> POKED 0x40"
        print(f"   0x{o:012X} byte[+0xB3]=0x{b:02X} bit6={bit6}{tag}")
    if len(insts)>20: print(f"   ... (+{len(insts)-20} more)")
print(f"\npoked={poked} (poke={'ON' if POKE else 'OFF'})")
