# S89: dump a UFunction's PARAMETER SIGNATURE via live RPM reflection (beats the anti-tamper wall — the
# reflection data is built in live heap at startup, readable without touching the protected .text).
# A UFunction is a UStruct; its params are FProperties in ChildProperties (CPF_Parm set), laid out in the
# param frame by Offset_Internal (declaration order).
#   usage: ufunc_params.py <PID> <BASE-hex> <UFunctionObj-hex>
#   find the UFunction addr with: find_uclass.py <PID> <BASE> MulticastSetGameFeatureToggle Function
# Offsets (this build, from netfields_dump.py + rep_expand_class.py):
#   UObject Class@+0x18 Name@+0x20 | UStruct SuperStruct@+0x48 Children(UField*)@+0x50 ChildProperties(FField*)@+0x58
#   UField Next@+0x30 | FField Class(FFieldClass*)@+0x08 Next@+0x18 Name@+0x20 | FProperty ArrayDim@+0x30
#   ElementSize@+0x34 PropertyFlags@+0x38 | StructProperty.Struct@+0x70 ArrayProperty.Inner@+0x78
#   UFunction FunctionFlags@+0xB8 (NumParms/ParmsSize/ReturnValueOffset follow)
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); FN=int(sys.argv[3],16); NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
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
def oname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"        # UObject name
def ocls(o): c=p(o+0x18); return oname(c) if looksptr(c) else "?"          # UObject class name
def fldname(f): b=rpm(f+0x20,4); return fname(u32(b,0)) if b else "?"       # FField name
def fldtype(f):                                                            # FField class (property type) name
    fc=p(f+0x08); return (fname(u32(rpm(fc,4),0)) if looksptr(fc) else "?")

# --- resolve an enum/struct pointer inside a property by scanning 0x68..0x98 for a UObject of the right class
def scan_for_class(f, want):
    for off in range(0x68,0x98,0x8):
        q=p(f+off)
        if looksptr(q) and ocls(q)==want:
            return off,q,oname(q)
    return None,0,"?"

CPF={0x2:"Const",0x80:"Parm",0x100:"OutParm",0x400:"ReturnParm",0x800:"DisableEditOnInstance",
     0x8000000:"ReferenceParm",0x400000:"RepSkip"}
def cpf_str(fl):
    return "|".join(v for k,v in CPF.items() if fl&k) or "-"

FUNC={0x40:"Net",0x80:"NetReliable",0x400:"Native",0x1000:"NetResponse",0x4000:"NetMulticast",
      0x200000:"NetServer",0x1000000:"NetClient",0x2000000:"NetValidate"}
def func_str(fl):
    return "|".join(v for k,v in FUNC.items() if fl&k) or "-"

print(f"=== UFunction {oname(FN)} @0x{FN:X}  (class={ocls(FN)}) ===")
ff=u32(rpm(FN+0xB8,4) or b'\0\0\0\0',0)
print(f"FunctionFlags=0x{ff:08X} [{func_str(ff)}]")
# NumParms(uint8)/ParmsSize(uint16)/ReturnValueOffset(uint16) follow FunctionFlags; dump a window to read them
tail=rpm(FN+0xB8,0x18)
if tail:
    print(f"  raw @+0xB8: "+" ".join(f"{b:02X}" for b in tail))
    print(f"  guess NumParms@+0xBC={tail[0x04]}  ParmsSize@+0xBE={u16(tail,0x06)}  RVOffset@+0xC0={u16(tail,0x08)}")

# Walk ChildProperties (FField* @ +0x58, Next @ +0x18) — these are the params (+ return value)
print("--- ChildProperties (params, in list order) ---")
params=[]
c=p(FN+0x58); i=0
while looksptr(c) and i<40:
    nm=fldname(c); tp=fldtype(c)
    fl=u64(rpm(c+0x38,8) or b'\0'*8,0)
    arrdim=i32(rpm(c+0x30,4) or b'\0'*4,0); elsz=i32(rpm(c+0x34,4) or b'\0'*4,0)
    # offset_internal candidates (declaration-order key)
    win=rpm(c+0x40,0x18) or b'\0'*0x18
    off_cands={o:i32(win,o-0x40) for o in (0x44,0x48,0x4C)}
    extra=""
    if tp in("EnumProperty","ByteProperty"):
        eo,ep,en=scan_for_class(c,"Enum"); extra=f"  enum={en}@+0x{eo:X}" if ep else "  enum=?"
    elif tp=="StructProperty":
        st=p(c+0x70); extra=f"  struct={oname(st)}" if looksptr(st) else ""
    elif tp=="ArrayProperty":
        inner=p(c+0x78); extra=f"  inner={fldtype(inner)}({fldname(inner)})" if looksptr(inner) else ""
    elif tp=="ObjectProperty":
        pc=p(c+0x70); extra=f"  objclass={oname(pc)}" if looksptr(pc) else ""
    params.append((nm,tp,fl,arrdim,elsz,off_cands,extra,c))
    c=p(c+0x18); i+=1

for nm,tp,fl,ad,es,oc,ex,addr in params:
    print(f"  {nm:28} {tp:16} flags=0x{fl:012X}[{cpf_str(fl)}] arrDim={ad} elemSize={es} off{{44:{oc[0x44]},48:{oc[0x48]},4C:{oc[0x4C]}}}{ex}")

# Reconstruct the signature: params = CPF_Parm & !CPF_ReturnParm, ordered by the offset that is monotonic.
parms=[x for x in params if x[2]&0x80]
ret=[x for x in params if x[2]&0x400]
def order_key_field(cands_list):
    for key in (0x44,0x48,0x4C):
        vals=[oc[key] for *_,oc,_,_ in cands_list]
        if all(0<=v<0x1000 for v in vals) and len(set(vals))==len(vals):
            return key
    return 0x4C
print("\n--- RECONSTRUCTED SIGNATURE ---")
if parms:
    key=order_key_field(parms)
    parms_sorted=sorted(parms,key=lambda x:x[5][key])
    sig=", ".join(f"{('[out] ' if x[2]&0x100 else '')}{x[1].replace('Property','')} {x[0]}"+(x[6].strip() and f" /*{x[6].strip()}*/" or "") for x in parms_sorted)
    rv=("void" if not ret else ret[0][1].replace("Property",""))
    print(f"  {rv} {oname(FN)}({sig})   [order by off@+0x{key:X}]")
else:
    print(f"  {oname(FN)}()  — NO CPF_Parm properties (parameterless RPC)")
