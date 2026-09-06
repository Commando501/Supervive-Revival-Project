# live_bars.py — find live WBP_UI_MissionObjectiveProgress_C widget instances (exist only while the
# Missions modal is open) and read the ACTUAL on-screen bar state: ProgressBarv2.Percent,
# Objective.TotalProgress (max), ObjectiveModel.CurrentProgress (current), MissionModel.ID.
# This is ground truth for "what the bars show right now" without a screenshot. Read-only RPM.
# usage: live_bars.py <PID> <BASE-hex>
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16)
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
LEAF="WBP_UI_MissionObjectiveProgress_C"
OBJ_STRUCT=0x2F0; OBJ_TOTAL=0x2F0+0x10; OBJMODEL=0x320; MISMODEL=0x328; PBAR=0x368; PTEXT=0x370
OM_CURRENT=0x38; MDL_ID=0x30
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def f32(b,o): return struct.unpack_from("<f",b,o)[0]
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a): b=rpm(a,8); return u64(b,0) if b else 0
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
def ftype(f):
    fc=p(f+0x08); return fname(u32(rpm(fc,4),0)) if looksptr(fc) else "?"

# find UProgressBar.Percent offset
def find_class(name):
    op=p(OBJOBJECTS); numEl=u32(rpm(OBJOBJECTS,0x18),0x14); nch=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nch):
        ch=p(op+ci*8)
        if not looksptr(ch): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nch-1 else PERCHUNK
        for j in range(cnt):
            o=p(ch+j*STRIDE)
            if looksptr(o) and oname(o)==name and "Class" in ocls(o): return o
    return 0
def field_off(cls, fieldname):
    c=cls
    for _ in range(8):
        f=p(c+0x58); i=0
        while looksptr(f) and i<80:
            if oname(f)==fieldname:
                return int.from_bytes(rpm(f,0x48)[0x44:0x48],"little",signed=True)
            f=p(f+0x18); i+=1
        c=p(c+0x48)
        if not looksptr(c): return None
    return None
pbcls=find_class("ProgressBar")
percent_off=field_off(pbcls,"Percent") if pbcls else None
print(f"UProgressBar.Percent offset = {hex(percent_off) if percent_off is not None else '?'}")

# iterate all objects, collect leaf widget instances
op=p(OBJOBJECTS); numEl=u32(rpm(OBJOBJECTS,0x18),0x14); nch=(numEl+PERCHUNK-1)//PERCHUNK
insts=[]
for ci in range(nch):
    ch=p(op+ci*8)
    if not looksptr(ch): continue
    cnt=(numEl-ci*PERCHUNK) if ci==nch-1 else PERCHUNK
    for j in range(cnt):
        o=p(ch+j*STRIDE)
        if looksptr(o) and ocls(o)==LEAF and not oname(o).startswith("Default__"):
            insts.append(o)
print(f"live {LEAF} instances: {len(insts)}  (0 => Missions modal is CLOSED)")
for w in insts[:40]:
    raw=rpm(w,0x380) or b""
    total=f32(raw,OBJ_TOTAL) if len(raw)>=OBJ_TOTAL+4 else -1
    om=u64(raw,OBJMODEL); mm=u64(raw,MISMODEL); pbar=u64(raw,PBAR)
    cur=-1
    if looksptr(om):
        omraw=rpm(om,0x40)
        if omraw: cur=f32(omraw,OM_CURRENT)
    pct=-1
    if looksptr(pbar) and percent_off is not None:
        pr=rpm(pbar+percent_off,4)
        if pr: pct=struct.unpack("<f",pr)[0]
    # mission id string
    mid=""
    if looksptr(mm):
        idp=p(mm+MDL_ID); idn=u32(rpm(mm+MDL_ID,0x10),8)
        if looksptr(idp) and 0<idn<128:
            sb=rpm(idp,idn*2); mid=sb.decode("utf-16-le","replace").rstrip("\x00") if sb else ""
    print(f"  w@0x{w:X} mission='{mid}' ObjectiveModel={'null' if not looksptr(om) else hex(om)} "
          f"current={cur:.2f} total(max)={total:.2f} BAR.Percent={pct:.3f}")
