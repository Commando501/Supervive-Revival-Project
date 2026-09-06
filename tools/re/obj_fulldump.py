# obj_fulldump.py — dump a live UObject instance's FULL property tree (name@off = value, typed) across its
# super chain, resolving object-ref fields to their class name. Read-only RPM. Finds the ACTIVE registered
# objective by showing every field of the training component / quests / objectives components.
#   usage: obj_fulldump.py <PID> <BASE-hex> <instPtrHex> [instPtrHex...]
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); INSTS=[int(x,16) for x in sys.argv[3:]]
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def f32(b,o): return struct.unpack("<f",b[o:o+4])[0]
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
def objname(o):
    if not looksptr(o): return "-"
    c=clsof(o)
    if looksptr(c): return fname(nameid(c))
    return "?"+fname(nameid(o))
# FField: Class(FFieldClass*)@0x08, Next@0x18, Name@0x20; FProperty: ElementSize@0x34, Flags@0x38, Offset@0x44
def ffclass_name(fc):
    # FFieldClass has a Name FName at +0x00 in this build? try +0x00 then +0x08
    for off in (0x00,0x08):
        b=rpm(fc+off,4)
        if b:
            nm=fname(u32(b,0))
            if nm and nm!="?" and "Property" in nm: return nm
    return "?"
def dump(inst):
    print("\n==== 0x%X  class=%s ===="%(inst,objname(inst)))
    cls=clsof(inst); depth=0
    while looksptr(cls) and depth<8:
        cn=fname(nameid(cls))
        f=rpm(cls+0x58,8); f=u64(f,0) if f else 0   # ChildProperties (FField*)
        n=0
        while looksptr(f) and n<400:
            nm=fname(nameid(f))
            fc=rpm(f+0x08,8); fc=u64(fc,0) if fc else 0
            tn=ffclass_name(fc) if looksptr(fc) else "?"
            offb=rpm(f+0x44,4); off=u32(offb,0) if offb else 0xFFFFFFFF
            flb=rpm(f+0x38,8); fl=u64(flb,0) if flb else 0
            val=""
            if off!=0xFFFFFFFF:
                vb=rpm(inst+off,8)
                if vb:
                    q=u64(vb,0)
                    if tn in ("ObjectProperty","ClassProperty","WeakObjectProperty","InterfaceProperty","SoftObjectProperty"):
                        val="0x%X (%s)"%(q&0xFFFFFFFFFFFFFFFF, objname(q&0xFFFFFFFFFFFFFFFF) if looksptr(q&0xFFFFFFFFFFFFFFFF) else "-")
                    elif tn=="BoolProperty":
                        val="%d"%(vb[0]&1)
                    elif tn in ("IntProperty","Int32Property"):
                        val="%d"%i32(vb,0)
                    elif tn in ("FloatProperty","DoubleProperty"):
                        val="%.3f"%f32(vb,0)
                    elif tn in ("ByteProperty","EnumProperty"):
                        val="%d"%vb[0]
                    elif tn in ("ArrayProperty","MapProperty","SetProperty"):
                        # TArray: Data ptr@+0, Num@+8
                        num=u32(vb,0) # actually need +8 for num; read 16
                        vb2=rpm(inst+off,16)
                        num=u32(vb2,8) if vb2 else 0
                        val="Num=%d data=0x%X"%(num,q)
                    elif tn=="NameProperty":
                        val="FName:%s"%fname(u32(vb,0))
                    else:
                        val="0x%X"%q
            fmark=""
            if fl & 0x80: fmark+="P"          # CPF_Parm
            if fl & 0x20: fmark+="R"          # CPF_Net (rep)
            print("  [%-10s] %-38s @0x%-4X %s %s"%(tn,nm,off,val,("<"+fmark+">") if fmark else ""))
            nx=rpm(f+0x18,8); f=u64(nx,0) if nx else 0; n+=1
        sc=rpm(cls+0x48,8); cls=u64(sc,0) if sc else 0; depth+=1
        if not (cn.startswith("BP_") or "Comp_" in cn or "Quest" in cn or "Augment" in cn or "Training" in cn):
            break  # stop at the first engine-native ancestor to keep output focused
for a in INSTS: dump(a)
