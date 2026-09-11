# ubergraph_dump.py — operand-aware UE5 Blueprint bytecode disassembler over a LIVE process (read-only RPM).
#
# Why this exists (S80): BP-folded UFunctions are the deploy surface, and reading what they actually DO before
# calling them is the difference between fact and guesswork. Three separate S79/S80 "walls" turned out to be
# guesses about function behaviour inferred from NAMES (see docs/session-79-moonshot-plan.md). A naive byte-walk
# desyncs instantly on real bytecode; this walks operands recursively so offsets stay exact.
#
# BP events don't carry their own logic: they're an 18-byte `EX_LocalFinalFunction ExecuteUbergraph_X(EntryPoint)`
# thunk. The real graph lives in the ubergraph at that EntryPoint — that's what this dumps.
#
# usage: ubergraph_dump.py <PID> <BASE-hex> <CLASS-hex> <UbergraphFnName> <EntryOffset> [maxbytes]
#   e.g. ubergraph_dump.py 48788 0x7FF6AF000000 0x28694503340 ExecuteUbergraph_BP_LokiHeroCharacter 20077
#
# Bytecode operand facts verified live on this build: FName in bytecode = 12 bytes (first 4 = FNamePool comparison
# index); UObject*/FProperty* = 8 bytes; CodeSkipSizeType = 4 bytes. Confirmed by ClientInitialComponentSetup
# decoding to exactly 88 bytes with every jump offset landing on an opcode boundary.
import ctypes, sys
from ctypes import wintypes

PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CLS=int(sys.argv[3],16)
FN=sys.argv[4]; ENTRY=int(sys.argv[5],0); MAXB=int(sys.argv[6],0) if len(sys.argv)>6 else 3000
NAMEPOOL=BASE+0x9D81450

k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
if not h: print("OpenProcess failed"); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16a(a):
    b=rpm(a,2); return int.from_bytes(b,"little") if b else 0
def u32a(a):
    b=rpm(a,4); return int.from_bytes(b,"little") if b else 0
def u64a(a):
    b=rpm(a,8); return int.from_bytes(b,"little") if b else 0
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=u64a(NAMEPOOL+blk*8); r="?"
    if looksptr(bp):
        hd=u16a(bp+off); ln=hd>>6; wide=hd&1
        if 0<ln<200:
            s=rpm(bp+off+2,ln*(2 if wide else 1))
            if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r
def oname(o):
    if not looksptr(o): return None
    n=fname(u32a(o+0x20)); return n if n and n!="?" else None
def ofull(o):
    """name + owning class, e.g. RefreshCosmetics(LokiHeroCharacter) -- tells native lib calls apart at a glance"""
    n=oname(o)
    if not n: return "0x%X"%o
    out=u64a(o+0x28); on=oname(out) if out else None
    return "%s%s"%(n, "  [%s]"%on if on else "")

# locate the ubergraph UFunction on the class chain
cls=CLS; F=0
while looksptr(cls) and not F:
    f=u64a(cls+0x50); i=0
    while looksptr(f) and i<900:
        if fname(u32a(f+0x20))==FN: F=f; break
        f=u64a(f+0x30); i+=1
    cls=u64a(cls+0x48)
if not F: print("ubergraph fn %s not found"%FN); sys.exit(1)
DATA=u64a(F+0x68); NUM=u32a(F+0x70)
print("%s @0x%X | Script.Data=0x%X Num=%d PropertiesSize=%d"%(FN,F,DATA,NUM,u32a(F+0x60)))
print("entry offset %d (0x%X); decoding until Return/EndOfScript (cap %d bytes)\n"%(ENTRY,ENTRY,MAXB))
B=rpm(DATA,NUM)
if not B: print("RPM of Script failed"); sys.exit(1)

O={0x00:"LocalVariable",0x01:"InstanceVariable",0x02:"DefaultVariable",0x04:"Return",0x06:"Jump",0x07:"JumpIfNot",
0x09:"Assert",0x0B:"Nothing",0x0C:"NothingInt32",0x0F:"Let",0x10:"BitFieldConst",0x12:"ClassContext",0x13:"MetaCast",
0x14:"LetBool",0x15:"EndParmValue",0x16:"EndFunctionParms",0x17:"Self",0x18:"Skip",0x19:"Context",
0x1A:"Context_FailSilent",0x1B:"VirtualFunction",0x1C:"FinalFunction",0x1D:"IntConst",0x1E:"FloatConst",
0x1F:"StringConst",0x20:"ObjectConst",0x21:"NameConst",0x22:"RotationConst",0x23:"VectorConst",0x24:"ByteConst",
0x25:"IntZero",0x26:"IntOne",0x27:"True",0x28:"False",0x29:"TextConst",0x2A:"NoObject",0x2B:"TransformConst",
0x2C:"IntConstByte",0x2D:"NoInterface",0x2E:"DynamicCast",0x2F:"StructConst",0x30:"EndStructConst",0x31:"SetArray",
0x32:"EndArray",0x33:"PropertyConst",0x34:"UnicodeStringConst",0x35:"Int64Const",0x36:"UInt64Const",0x37:"DoubleConst",
0x38:"Cast",0x39:"SetSet",0x3A:"EndSet",0x3B:"SetMap",0x3C:"EndMap",0x3D:"SetConst",0x3E:"EndSetConst",0x3F:"MapConst",
0x40:"EndMapConst",0x41:"Vector3fConst",0x42:"StructMemberContext",0x43:"LetMulticastDelegate",0x44:"LetDelegate",
0x45:"LocalVirtualFunction",0x46:"LocalFinalFunction",0x48:"LocalOutVariable",0x4B:"InstanceDelegate",
0x4C:"PushExecutionFlow",0x4D:"PopExecutionFlow",0x4E:"ComputedJump",0x4F:"PopExecutionFlowIfNot",0x50:"Breakpoint",
0x51:"InterfaceContext",0x52:"ObjToInterfaceCast",0x53:"EndOfScript",0x54:"CrossInterfaceCast",
0x55:"InterfaceToObjCast",0x5A:"WireTracepoint",0x5B:"SkipOffsetConst",0x5C:"AddMulticastDelegate",
0x5D:"ClearMulticastDelegate",0x5E:"Tracepoint",0x5F:"LetObj",0x60:"LetWeakObjPtr",0x61:"BindDelegate",
0x62:"RemoveMulticastDelegate",0x63:"CallMulticastDelegate",0x64:"LetValueOnPersistentFrame",0x65:"ArrayConst",
0x66:"EndArrayConst",0x67:"SoftObjectConst",0x68:"CallMath",0x69:"SwitchValue",0x6B:"ArrayGetByRef",
0x6C:"ClassSparseDataVariable",0x6D:"FieldPathConst"}

out=[]
def emit(off,d,txt): out.append("  %-7d %s%s"%(off,"  "*d,txt))
def rdptr(i): return int.from_bytes(B[i:i+8],"little"), i+8
def rdname(i):  # FName in bytecode = 12 bytes; first 4 = pool comparison index
    return fname(int.from_bytes(B[i:i+4],"little")), i+12
def rdskip(i): return int.from_bytes(B[i:i+4],"little"), i+4
def rdi32(i): return int.from_bytes(B[i:i+4],"little",signed=True), i+4

END=[0]
def step(i,d=0):
    if i>=NUM or i<0 or d>28: return NUM
    op=B[i]; nm=O.get(op,"UNKNOWN_0x%02X"%op); s=i; i+=1
    if op in (0x00,0x01,0x02,0x48,0x33,0x6C):        # variable / property refs
        p,i=rdptr(i); emit(s,d,"%s %s"%(nm,ofull(p)))
    elif op in (0x0B,0x15,0x16,0x17,0x25,0x26,0x27,0x28,0x2A,0x2D,0x30,0x32,0x3A,0x3C,0x3E,0x40,0x50,0x5A,0x5E,0x4D,0x66):
        emit(s,d,nm)
        if op==0x16: return i
    elif op==0x53: emit(s,d,"EndOfScript"); END[0]=1; return NUM
    elif op==0x04: emit(s,d,"Return"); i=step(i,d+1); END[0]=1
    elif op==0x06:
        t,i=rdskip(i); emit(s,d,"Jump -> %d"%t)
    elif op in (0x07,0x18,0x4F):
        if op==0x4F: emit(s,d,nm); i=step(i,d+1)
        else:
            t,i=rdskip(i); emit(s,d,"%s -> %d"%(nm,t)); i=step(i,d+1)
    elif op==0x4C:
        t,i=rdskip(i); emit(s,d,"PushExecutionFlow -> %d"%t)
    elif op in (0x4E,0x51,0x5D,0x67):
        emit(s,d,nm); i=step(i,d+1)
    elif op in (0x14,0x43,0x44,0x5C,0x5F,0x60,0x62,0x6B):
        emit(s,d,nm); i=step(i,d+1); i=step(i,d+1)
    elif op==0x0F:
        p,i=rdptr(i); emit(s,d,"Let %s"%ofull(p)); i=step(i,d+1); i=step(i,d+1)
    elif op==0x64:
        p,i=rdptr(i); emit(s,d,"LetValueOnPersistentFrame %s"%ofull(p)); i=step(i,d+1)
    elif op in (0x19,0x1A,0x12):                      # Context: obj, skip, rvalue prop, member expr
        emit(s,d,"%s:"%nm); i=step(i,d+1); _,i=rdskip(i); p,i=rdptr(i); i=step(i,d+1)
    elif op in (0x1C,0x46,0x68,0x63):                 # calls taking a UFunction*
        p,i=rdptr(i); emit(s,d,"%s %s ("%(nm,ofull(p)))
        if op==0x63: i=step(i,d+1)
        while i<NUM and B[i]!=0x16: i=step(i,d+1)
        if i<NUM: i+=1
        emit(i,d,")")
    elif op in (0x1B,0x45):                           # calls taking an FName
        n,i=rdname(i); emit(s,d,"%s '%s' ("%(nm,n))
        while i<NUM and B[i]!=0x16: i=step(i,d+1)
        if i<NUM: i+=1
        emit(i,d,")")
    elif op in (0x13,0x2E,0x52,0x54,0x55):            # cast: class ptr + expr
        p,i=rdptr(i); emit(s,d,"%s -> %s"%(nm,ofull(p))); i=step(i,d+1)
    elif op==0x42:
        p,i=rdptr(i); emit(s,d,"StructMemberContext %s"%ofull(p)); i=step(i,d+1)
    elif op==0x1D: v,i=rdi32(i); emit(s,d,"IntConst %d"%v)
    elif op==0x1E: v=int.from_bytes(B[i:i+4],"little"); i+=4; emit(s,d,"FloatConst 0x%X"%v)
    elif op==0x20: p,i=rdptr(i); emit(s,d,"ObjectConst %s"%ofull(p))
    elif op==0x21: n,i=rdname(i); emit(s,d,"NameConst '%s'"%n)
    elif op==0x4B: n,i=rdname(i); emit(s,d,"InstanceDelegate '%s'"%n)
    elif op in (0x24,0x2C,0x38): v=B[i]; i+=1; emit(s,d,"%s %d"%(nm,v)); (step(i,d+1) if op==0x38 else None)
    elif op==0x10: p,i=rdptr(i); v=B[i]; i+=1; emit(s,d,"BitFieldConst %s = %d"%(ofull(p),v))
    elif op in (0x35,0x36,0x37): i+=8; emit(s,d,nm)
    elif op==0x0C: v,i=rdi32(i); emit(s,d,"NothingInt32 %d"%v)
    elif op==0x5B: t,i=rdskip(i); emit(s,d,"SkipOffsetConst %d"%t)
    elif op in (0x22,0x23): i+=24; emit(s,d,nm)
    elif op==0x41: i+=12; emit(s,d,nm)
    elif op==0x2B: i+=80; emit(s,d,nm)
    elif op==0x1F:
        e=B.index(b"\x00",i); emit(s,d,'StringConst "%s"'%B[i:e].decode("latin1","replace")); i=e+1
    elif op==0x34:
        e=i
        while e+1<NUM and B[e:e+2]!=b"\x00\x00": e+=2
        emit(s,d,'UnicodeStringConst "%s"'%B[i:e].decode("utf-16-le","replace")); i=e+2
    elif op==0x2F:                                   # StructConst: ptr, int32 size, exprs .. EndStructConst
        p,i=rdptr(i); _,i=rdi32(i); emit(s,d,"StructConst %s {"%ofull(p))
        while i<NUM and B[i]!=0x30: i=step(i,d+1)
        i+=1; emit(i,d,"}")
    elif op in (0x31,0x39,0x3B):                     # SetArray/SetSet/SetMap
        emit(s,d,"%s ["%nm); i=step(i,d+1)
        if op!=0x31: _,i=rdi32(i)
        endtok={0x31:0x32,0x39:0x3A,0x3B:0x3C}[op]
        while i<NUM and B[i]!=endtok: i=step(i,d+1)
        i+=1; emit(i,d,"]")
    elif op in (0x3D,0x65):                          # SetConst/ArrayConst: ptr, int32, exprs .. End
        p,i=rdptr(i); _,i=rdi32(i); emit(s,d,"%s %s ["%(nm,ofull(p)))
        endtok=0x3E if op==0x3D else 0x66
        while i<NUM and B[i]!=endtok: i=step(i,d+1)
        i+=1; emit(i,d,"]")
    elif op==0x3F:
        p,i=rdptr(i); p2,i=rdptr(i); _,i=rdi32(i); emit(s,d,"MapConst {")
        while i<NUM and B[i]!=0x40: i=step(i,d+1)
        i+=1; emit(i,d,"}")
    elif op==0x69:                                   # SwitchValue: u16 cases, skip end, index expr, cases..
        n=int.from_bytes(B[i:i+2],"little"); i+=2; e,i=rdskip(i)
        emit(s,d,"SwitchValue (%d cases, end %d)"%(n,e)); i=step(i,d+1)
        for _ in range(n):
            i=step(i,d+1); _,i=rdskip(i); i=step(i,d+1)
        i=step(i,d+1)
    elif op==0x61:
        n,i=rdname(i); emit(s,d,"BindDelegate '%s'"%n); i=step(i,d+1); i=step(i,d+1)
    elif op==0x09:
        i+=3; emit(s,d,"Assert"); i=step(i,d+1)
    elif op==0x29: emit(s,d,"TextConst <unparsed>"); return NUM
    elif op==0x6D: emit(s,d,"FieldPathConst"); i=step(i,d+1)
    else:
        emit(s,d,"%s  <<< UNKNOWN OPCODE - decode stops (offsets past here are unreliable)"%nm); return NUM
    return i

i=ENTRY
while i<NUM and not END[0] and i-ENTRY<MAXB:
    i=step(i,0)
print("\n".join(out))
print("\n(decoded %d bytes from entry %d)"%(i-ENTRY,ENTRY))
