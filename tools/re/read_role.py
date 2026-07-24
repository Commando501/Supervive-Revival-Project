# read_role.py — read AActor Role/RemoteRole (+ owner) on live instances, and find a GameState/PlayerController's Role.
# ROLE_None=0 SimulatedProxy=1 AutonomousProxy=2 Authority=3. usage: read_role.py <PID> <BASE-hex> <instHex...>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); INSTS=[int(x,16) for x in sys.argv[3:]]
NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    b2=rpm(bp+off,2)
    if not b2: return "?"
    hd=int.from_bytes(b2,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
def nameid(o):
    b=rpm(o+0x20,4); return u32(b,0) if b else 0
def clsof(o):
    b=rpm(o+0x18,8); return u64(b,0) if b else 0
def cname(o):
    c=clsof(o); return fname(nameid(c)) if looksptr(c) else "?"
# Find Role/RemoteRole offsets by walking the class's ChildProperties chain up the super chain (they are UPROPERTYs on AActor).
def find_prop_off(cls,want):
    depth=0
    while looksptr(cls) and depth<14:
        f=rpm(cls+0x58,8); f=u64(f,0) if f else 0
        n=0
        while looksptr(f) and n<500:
            if fname(nameid(f))==want:
                ob=rpm(f+0x44,4)
                return u32(ob,0) if ob else None
            nx=rpm(f+0x18,8); f=u64(nx,0) if nx else 0; n+=1
        sc=rpm(cls+0x48,8); cls=u64(sc,0) if sc else 0; depth+=1
    return None
RN={0:"None",1:"SimulatedProxy",2:"AutonomousProxy",3:"Authority"}
for inst in INSTS:
    cls=clsof(inst)
    ro=find_prop_off(cls,"Role"); rr=find_prop_off(cls,"RemoteRole")
    role=rpm(inst+ro,1)[0] if ro is not None and rpm(inst+ro,1) else -1
    rrole=rpm(inst+rr,1)[0] if rr is not None and rpm(inst+rr,1) else -1
    # Owner @ AActor (find via prop)
    oo=find_prop_off(cls,"Owner")
    owner=u64(rpm(inst+oo,8),0) if oo is not None and rpm(inst+oo,8) else 0
    print("0x%X %-40s Role@%s=%s(%s) RemoteRole@%s=%s(%s) Owner=0x%X(%s)"%(
        inst,cname(inst),
        hex(ro) if ro is not None else "?",role,RN.get(role,"?"),
        hex(rr) if rr is not None else "?",rrole,RN.get(rrole,"?"),
        owner, cname(owner) if looksptr(owner) else "-"))
