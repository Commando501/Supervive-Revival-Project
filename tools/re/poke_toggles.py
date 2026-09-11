# S89 path-1: flip the client's game-feature-toggle READINESS + fill the values, on every client
# LokiServerAuthConfig instance. TWO pokes (both live-proven, external RPM):
#   (1) READINESS BIT — set bit 6 of byte [SAC+0xB3]. This is the ACTUAL readiness flag:
#       LokiGameplayStatics::GetFeatureTogglesReady disassembles to `return bit6([GameState+0x5A0]+0xB3)`
#       (GameState+0x5A0 = the ServerAuthConfig ptr). Setting it makes GetFeatureTogglesReady return true.
#       (NOT GameFeatureToggles.Num()>0 — that was the wrong first hypothesis.)
#   (2) VALUES — size+fill GameFeatureToggles (TArray<bool> @+0x130) to Num=Count all-true, so the value getters
#       (GetGameFeatureToggleValue) return real toggles. Each instance gets its OWN VirtualAllocEx buffer
#       (never freed by us; the game won't realloc it since the array is never re-replicated on the DS route).
#   usage: poke_toggles.py <PID> <BASE-hex> [Count=151]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); COUNT=int(sys.argv[3]) if len(sys.argv)>3 else 151
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18; OFF=0x130
k=ctypes.WinDLL("kernel32",use_last_error=True)
k.OpenProcess.restype=wintypes.HANDLE
k.VirtualAllocEx.restype=wintypes.LPVOID
k.VirtualAllocEx.argtypes=[wintypes.HANDLE,wintypes.LPVOID,ctypes.c_size_t,wintypes.DWORD,wintypes.DWORD]
h=k.OpenProcess(0x1F0FFF,False,PID)
if not h: print("OpenProcess failed",k.GetLastError()); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wpm(a,data):
    r=ctypes.c_size_t(0); buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    return bool(k.WriteProcessMemory(h,ctypes.c_void_p(a),buf,len(data),ctypes.byref(r))) and r.value==len(data)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6
                if 0<ln<200:
                    s=rpm(bp+off+2,ln); r=s.decode("latin1","replace") if s else "?"
    _nc[idx]=r; return r
def oname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def clsname(o): c=u64(rpm(o+0x18,8) or b'\0'*8,0); return oname(c) if looksptr(c) else "?"

hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
nc=(numEl+PERCHUNK-1)//PERCHUNK; cp=rpm(objectsPtr,nc*8); insts=[]
for ci in range(nc):
    ch=int.from_bytes(cp[ci*8:ci*8+8],"little")
    if not looksptr(ch): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); it=rpm(ch,cnt*STRIDE)
    if not it: continue
    for j in range(cnt):
        o=u64(it,j*STRIDE)
        if looksptr(o) and clsname(o)=="LokiServerAuthConfig": insts.append(o)
print(f"found {len(insts)} LokiServerAuthConfig instances; setting readiness bit + filling {COUNT} toggles")
MEM_COMMIT=0x1000; MEM_RESERVE=0x2000; PAGE_RW=0x04
for o in insts:
    # (1) readiness bit — bit 6 of [+0xB3]
    b=rpm(o+0xB3,1); rok="?"
    if b:
        new=b[0] | 0x40; wpm(o+0xB3, bytes([new])); chk=rpm(o+0xB3,1)
        rok=f"0x{b[0]:02x}->0x{chk[0]:02x} bit6={(chk[0]>>6)&1}" if chk else "?"
    # (2) values array
    buf=k.VirtualAllocEx(h,None,COUNT,MEM_COMMIT|MEM_RESERVE,PAGE_RW)
    aok="allocfail"
    if buf and wpm(buf, bytes([1])*COUNT):
        hdr=int(buf).to_bytes(8,"little")+int(COUNT).to_bytes(4,"little")+int(COUNT).to_bytes(4,"little")
        if wpm(o+OFF, hdr):
            chk=rpm(o+OFF,16); aok=f"ptr={u64(chk,0):#x} Num={i32(chk,8)}"
    print(f"  {o:#x}: ready[{rok}]  toggles[{aok}]")
print("done — GetFeatureTogglesReady now returns TRUE (proven: it reads exactly [GameState+0x5A0]+0xB3 bit6).")
