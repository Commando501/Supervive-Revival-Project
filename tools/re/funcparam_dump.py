# S73: resolve a UCLASS by name, find named UFunction(s) under it, dump each one's PARAM signature
# (ChildProperties with CPF_Parm) so the stub mirror can declare matching-signature RPCs.
#   usage: funcparam_dump.py <PID> <BASE-hex> <ClassName> <FuncName>[,<FuncName>...]
# Offsets (this build): UClass.Children(UField*)@+0x50, UField.Next@+0x30, Name@+0x20, Class@+0x18;
#   UStruct.ChildProperties(FField*)@+0x58; FField.Next@+0x18, Name@+0x20, FFieldClass*@+0x08,
#   FlagsPrivate(EPropertyFlags)@+0x38, ElementSize@+0x34. CPF_Parm=0x80 Out=0x100 Return=0x400.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CLSNAME=sys.argv[3]; FUNCS=set(sys.argv[4].split(","))
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
def oname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o): c=p(o+0x18); return oname(c) if looksptr(c) else "?"
def ffname(f): b=rpm(f+0x20,4); return fname(u32(b,0)) if b else "?"
def fftype(f):
    fc=p(f+0x08)
    if not looksptr(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"
def ffflags(f): b=rpm(f+0x38,8); return u64(b,0) if b else 0
def ffsize(f): b=rpm(f+0x34,4); return u32(b,0) if b else 0
# struct/object/enum inner detail for a property FField
def ffdetail(f, ty):
    if ty=="StructProperty":
        st=p(f+0x70); return fname(u32(rpm(st+0x20,4) or b'\0\0\0\0',0)) if looksptr(st) else "?"
    if ty in ("ObjectProperty","ClassProperty"):
        pc=p(f+0x70); return fname(u32(rpm(pc+0x20,4) or b'\0\0\0\0',0)) if looksptr(pc) else "?"
    if ty=="ArrayProperty":
        inner=p(f+0x78); return "<"+fftype(inner)+">" if looksptr(inner) else "?"
    if ty=="EnumProperty":
        en=p(f+0x78); return fname(u32(rpm(en+0x20,4) or b'\0\0\0\0',0)) if looksptr(en) else "?"
    return ""
# resolve class
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
numChunks=(numEl+PERCHUNK-1)//PERCHUNK; chunkPtrs=rpm(objectsPtr,numChunks*8); ROOT=0
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if looksptr(obj):
            nb=rpm(obj+0x20,4)
            if nb and fname(u32(nb,0))==CLSNAME and ocls(obj)=="Class": ROOT=obj; break
    if ROOT: break
assert ROOT, f"class {CLSNAME} not found"
print(f"class {CLSNAME} @0x{ROOT:X}")
ch=p(ROOT+0x50); f=ch; i=0
while looksptr(f) and i<600:
    if ocls(f)=="Function" and oname(f) in FUNCS:
        nm=oname(f)
        print(f"\n=== {nm} @0x{f:X} — params ===")
        c=p(f+0x58); k=0
        while looksptr(c) and k<40:
            fl=ffflags(c); ty=fftype(c); det=ffdetail(c,ty)
            if fl & 0x80:  # CPF_Parm
                role=[]
                if fl&0x400: role.append("RET")
                if fl&0x100: role.append("OUT")
                print(f"    {ty:18}{('('+det+')') if det else '':22} {ffname(c):32} size={ffsize(c):<4} {' '.join(role)}")
            c=p(c+0x18); k+=1
    nb=rpm(f+0x30,8); f=u64(nb,0) if nb else 0; i+=1
