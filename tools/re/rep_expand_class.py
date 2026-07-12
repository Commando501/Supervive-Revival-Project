# Expand a UCLASS's CPF_Net properties the way FRepLayout does, via the REAL property
# path (class -> Missions ArrayProperty -> Inner -> Struct -> recurse). Confirms the
# actual replicated element structure. usage: rep_expand_class.py <PID> <BASE-hex> <ClassObj-hex>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); ROOT=int(sys.argv[3],16); NAMEPOOL=BASE+0x9D81450
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
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8); r="?"
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
def fldname(f): b=rpm(f+0x20,4); return fname(u32(b,0)) if b else "?"
def fldtype(f):
    fc=p(f+0x08)
    if not looksptr(fc): return "?"
    b=rpm(fc+0x00,4); return fname(u32(b,0)) if b else "?"
def fldflags(f): b=rpm(f+0x38,8); return u64(b,0) if b else 0
def structflags(s): b=rpm(s+0xB8,4); return u32(b,0) if b else 0
CPF_Net=0x20; CPF_RepSkip=0x80000000; STRUCT_NetSer=0x400
cmd=[0]
def expand(f, depth):
    ind="  "*depth; tp=fldtype(f); nm=fldname(f)
    if tp=="ArrayProperty":
        print(f"{ind}[{cmd[0]}] DYNARRAY {nm}"); cmd[0]+=1
        inner=p(f+0x78)
        if looksptr(inner): expand(inner, depth+1)
        return
    if tp=="StructProperty":
        st=p(f+0x70); sf=structflags(st) if looksptr(st) else 0
        stn="?"
        if looksptr(st):
            b=rpm(st+0x20,4); stn=fname(u32(b,0)) if b else "?"
        if sf & STRUCT_NetSer:
            print(f"{ind}[{cmd[0]}] NETSER-STRUCT {nm} ({stn}@0x{st:X} flags=0x{sf:X})"); cmd[0]+=1; return
        print(f"{ind}(recurse {stn}@0x{st:X} flags=0x{sf:X})")
        c=p(st+0x58); i=0
        while looksptr(c) and i<256:
            if not (fldflags(c)&CPF_RepSkip): expand(c,depth+1)
            c=p(c+0x18); i+=1
        return
    print(f"{ind}[{cmd[0]}] LEAF {nm} ({tp})"); cmd[0]+=1

print(f"=== CLIENT class @0x{ROOT:X} CPF_Net props, expanded via REAL path ===")
c=p(ROOT+0x58); i=0
while looksptr(c) and i<40:
    fl=fldflags(c)
    if fl & CPF_Net:
        print(f"--- net prop {fldname(c)} (flags=0x{fl:X}) ---")
        expand(c,0)
    c=p(c+0x18); i+=1
print(f"=== total leaf cmds across net props = {cmd[0]} ===")
