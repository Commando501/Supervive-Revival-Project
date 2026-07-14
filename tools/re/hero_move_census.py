# Movement-state census across all live instances of a class. Read-only RPM.
# For each instance: Role, bCharacterMovementEnabled, CMC ptr, MovementMode, GravityScale, |Velocity|.
#   usage: hero_move_census.py <PID> <BASE-hex> <ClassNameSubstr>
# Offsets (this build): Actor Role@+0x160; Character CharacterMovement@+0x458; LokiCharacter bCharacterMovementEnabled@+0xB59;
#   CMC GravityScale@+0x1A0, MovementMode@+0x231, CustomMovementMode@+0x232, Velocity(FVector dbl)@+0xE8, UpdatedComponent@+0xD0.
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); WANT=sys.argv[3]
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a): b=rpm(a,8); return u64(b,0) if b else 0
def u8(a): b=rpm(a,1); return b[0] if b else -1
def f32(a): b=rpm(a,4); return struct.unpack("<f",b)[0] if b else None
def dbl(a): b=rpm(a,8); return struct.unpack("<d",b)[0] if b else None
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
MODES={0:"None",1:"Walking",2:"NavWalk",3:"Falling",4:"Swim",5:"Fly",6:"Custom"}
ROLES={0:"None",1:"SimProxy",2:"AutoProxy",3:"Authority"}
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14); numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8); found=0
print(f"{'obj':>14} {'role':>9} {'mvEn':>4} {'CMC':>14} {'mode':>8} {'grav':>6} {'|Vel|':>9}")
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o=u64(items,j*STRIDE)
        if not looksptr(o): continue
        cn=ocls(o)
        if WANT not in cn: continue
        if oname(o).startswith("Default__"): continue
        role=u8(o+0x160); mven=u8(o+0xB59); cmc=p(o+0x458)
        mode=grav=vel="-"
        if looksptr(cmc):
            mm=u8(cmc+0x231); mode=MODES.get(mm,str(mm))
            g=f32(cmc+0x1A0); grav=f"{g:.2f}" if g is not None else "-"
            vx=dbl(cmc+0xE8); vy=dbl(cmc+0xF0); vz=dbl(cmc+0xF8)
            if None not in (vx,vy,vz): vel=f"{(vx*vx+vy*vy+vz*vz)**0.5:.1f}"
        print(f"0x{o:012X} {ROLES.get(role,str(role)):>9} {mven:>4} 0x{cmc:012X} {mode:>8} {grav:>6} {vel:>9}")
        found+=1
print(f"\n{found} live instance(s) of class containing '{WANT}'")
