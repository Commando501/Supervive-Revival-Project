# ufunc_survey.py — for an object's class chain, dump every UFunction's INVOCABILITY metadata:
#   Func(+0xE0) native-vs-ProcessInternal, Script(+0x68 ptr/+0x70 num), PropertiesSize(+0x60),
#   ParmsSize(+0xBE), ReturnValueOffset(+0xC0), EventGraphFunction(+0xD0)/CallOffset(+0xD8), Flags(+0xB8)
# Read-only RPM. usage: ufunc_survey.py <PID> <BASE-hex> <OBJ-hex> [name-substr ...]
import ctypes, sys
from ctypes import wintypes

PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); OBJ=int(sys.argv[3],16)
SUBS=[s.lower() for s in sys.argv[4:]]
NAMEPOOL=BASE+0x9D81450
PI=BASE+0x13454A0
CLASS_OFF=0x18; NAME_OFF=0x20
UST_SUPER=0x48; UST_CHILDREN=0x50; FIELD_NEXT_UF=0x30

k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
if not h: print("OpenProcess failed"); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(a):
    b=rpm(a,2); return int.from_bytes(b,"little") if b else 0
def u32(a):
    b=rpm(a,4); return int.from_bytes(b,"little") if b else 0
def u64(a):
    b=rpm(a,8); return int.from_bytes(b,"little") if b else 0
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=u64(NAMEPOOL+blk*8); r="?"
    if looksptr(bp):
        hd=u16(bp+off)
        if hd:
            ln=hd>>6; wide=hd&1
            if 0<ln<200:
                s=rpm(bp+off+2,ln*(2 if wide else 1))
                if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r
def objname(o): return fname(u32(o+NAME_OFF))

FLAGS=[(0x00000400,"Native"),(0x00000800,"Event"),(0x00002000,"Static"),(0x00008000,"Ubergraph"),
       (0x04000000,"BPCallable"),(0x08000000,"BPEvent"),(0x10000000,"BPPure"),(0x00000040,"Net"),
       (0x00200000,"NetServer"),(0x01000000,"NetClient"),(0x00004000,"NetMulticast"),(0x00400000,"HasOutParms")]

cls=u64(OBJ+CLASS_OFF)
print("obj 0x%X  class=%s (0x%X)"%(OBJ,objname(cls),cls))
print("ProcessInternal = 0x%X\n"%PI)
print("%-44s %-16s %6s %6s %6s %6s  %-8s %s"%("FUNCTION","DISPATCH","Script","PropSz","Parms","RetOff","EvtGraph","FLAGS"))
print("-"*150)
depth=0
while looksptr(cls) and depth<16:
    cn=objname(cls)
    rows=[]
    f=u64(cls+UST_CHILDREN); i=0
    while looksptr(f) and i<900:
        nm=objname(f)
        if not SUBS or any(s in nm.lower() for s in SUBS):
            func=u64(f+0xE0); scriptptr=u64(f+0x68); scriptnum=u32(f+0x70)
            propsz=u32(f+0x60); parmsz=u16(f+0xBE); retoff=u16(f+0xC0)
            egf=u64(f+0xD0); egco=u32(f+0xD8); fl=u32(f+0xB8)
            if func==PI: disp="ProcessInternal"
            elif func==0: disp="<none>"
            else: disp="native+0x%X"%(func-BASE) if BASE<func<BASE+0xA9E1000 else "0x%X"%func
            fs=",".join(n for m,n in FLAGS if fl&m)
            eg="0x%X+%d"%(egf,egco) if egf else "-"
            rows.append("%-44s %-16s %6d %6d %6d %6s  %-8s %s"%(
                nm[:44],disp,scriptnum,propsz,parmsz,("-" if retoff==0xFFFF else retoff),eg,fs))
        f=u64(f+FIELD_NEXT_UF); i+=1
    if rows:
        print("\n=== class %s (0x%X) ==="%(cn,cls))
        for r in rows: print(r)
    cls=u64(cls+UST_SUPER); depth+=1
