# Dump a BP UFunction's Script bytecode; decode UE5 EExprToken + resolve embedded UObject* to names. Read-only RPM.
import ctypes,sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CLS=int(sys.argv[3],16); WANT=sys.argv[4]
NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
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
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=u64(NAMEPOOL+blk*8)
    if not looksptr(bp): return "?"
    hd=u16(bp+off); ln=hd>>6; wide=hd&1
    if not(0<ln<200): return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
def oname(o):
    if not looksptr(o): return None
    n=fname(u32(o+0x20))
    return n if n and n!="?" else None
OPS={0x00:"LocalVariable",0x01:"InstanceVariable",0x04:"Return",0x06:"Jump",0x07:"JumpIfNot",0x0B:"Nothing",
 0x0F:"Let",0x14:"LetBool",0x16:"EndFunctionParms",0x17:"Self",0x19:"Context",0x1A:"Context_FailSilent",
 0x1B:"VirtualFunction",0x1C:"FinalFunction",0x1D:"IntConst",0x20:"ObjectConst",0x21:"NameConst",
 0x24:"ByteConst",0x25:"IntZero",0x26:"IntOne",0x27:"True",0x28:"False",0x2A:"NoObject",0x2E:"DynamicCast",
 0x45:"LocalVirtualFunction",0x46:"LocalFinalFunction",0x48:"LocalOutVariable",0x4C:"PushExecutionFlow",
 0x4D:"PopExecutionFlow",0x4E:"ComputedJump",0x4F:"PopExecutionFlowIfNot",0x51:"InterfaceContext",
 0x53:"EndOfScript",0x5A:"WireTracepoint",0x5E:"Tracepoint",0x5F:"LetObj",0x63:"CallMulticastDelegate",
 0x64:"LetValueOnPersistentFrame",0x68:"CallMath",0x69:"SwitchValue"}
cls=CLS; d=0
while looksptr(cls) and d<16:
    f=u64(cls+0x50); i=0
    while looksptr(f) and i<900:
        if fname(u32(f+0x20))==WANT:
            data=u64(f+0x68); num=u32(f+0x70)
            print("%s @0x%X on %s | Script.Data=0x%X Num=%d PropSz=%d"%(WANT,f,fname(u32(cls+0x20)),data,num,u32(f+0x60)))
            b=rpm(data,num)
            print("raw:", " ".join("%02x"%x for x in b))
            print("--- decode (ptr-aware) ---")
            j=0
            while j<num:
                op=b[j]; nm=OPS.get(op,"op_0x%02X"%op); ann=""
                # 8-byte operand following these ops is a UObject*/FProperty*
                if op in (0x00,0x01,0x20,0x1C,0x46,0x45,0x1B,0x48,0x2E,0x68,0x5F,0x0F,0x64):
                    q=int.from_bytes(b[j+1:j+9],"little") if j+9<=num else 0
                    n=oname(q)
                    if n: ann="  -> %s (0x%X)"%(n,q)
                    elif q: ann="  -> 0x%X"%q
                print("  +%-3d %-24s %s"%(j,nm,ann))
                j+=1
            sys.exit(0)
        f=u64(f+0x30); i+=1
    cls=u64(cls+0x48); d+=1
print("not found")
