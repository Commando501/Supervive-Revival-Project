# S118 -- bounded extraction of Lobby::HandleNotif case bodies.
# For each case: the type-name FString it names, and every [rdi+disp] reference
# into the delegate band, classified by how the CLIENT uses it.
import ctypes,sys,json
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); LOBBY=int(sys.argv[3],16)
JT=BASE+0x4B04978; DEF=0x4B048F9
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
def fstring(p):
    hd=rpm(p,16)
    if not hd: return None
    q,num=u64(hd,0),u32(hd,8)
    if not q or not (0<num<200): return None
    d=rpm(q,num*2)
    return "".join(chr(d[i*2]|(d[i*2+1]<<8)) for i in range(num)).rstrip("\x00") if d else None
def slot(off):
    b=rpm(LOBBY+off,16)
    return (u64(b,0),i32(b,8)) if b else (None,None)

fails=[]
if fstring(BASE+0x9FFE6F0)!="dsNotif": fails.append("CTRL .data 0x9FFE6F0 != 'dsNotif'")
tbl=rpm(JT,33*4); rvas=[u32(tbl,i*4) for i in range(33)]
if any(r==DEF for r in rvas): fails.append("a case == default")
# CTRL: the two slots proved bound/unbound by an independent instrument must reproduce here
if slot(0x12c0)[1]!=3: fails.append("CTRL +0x12c0 not size=3")
if slot(0x1550)!=(0,0): fails.append("CTRL +0x1550 not (0,0)")
if fails: print("[ABORT] VOID:"); [print("  ",f) for f in fails]; sys.exit(1)
print("[CTRL] type-string, jump-table, bound(+0x12c0)/unbound(+0x1550) all reproduce  PASS\n")

bounds=sorted(set(rvas))
def endof(r):
    for b in bounds:
        if b>r: return min(b, r+0x300)
    return r+0x300
out=[]
for i,rva in enumerate(rvas):
    n=endof(rva)-rva; body=rpm(BASE+rva,n) or b""
    typ=None; refs={}
    j=0
    while j<len(body)-7:
        b0,b1,b2=body[j],body[j+1],body[j+2]
        d=i32(body,j+3)
        if b0==0x48 and b1==0x8D and b2==0x0D:                    # lea rcx,[rip+d32]
            s=fstring(BASE+rva+j+7+d)
            if s and typ is None: typ=s
            j+=7; continue
        if (b0,b1) in ((0x48,0x8D),(0x4C,0x8D),(0x48,0x8B),(0x4C,0x8B)) and b2 in (0x97,0x8F,0x87,0xB7,0xBF):
            if 0x1000<=d<0x1800: refs.setdefault(d,set()).add("lea/mov [rdi+d]")
            j+=7; continue
        if b0==0x44 and b1==0x39 and b2==0xAF:                     # cmp [rdi+d32], r13d
            if 0x1000<=d<0x1800: refs.setdefault(d,set()).add("cmp-size(IsBound)")
            j+=7; continue
        if b0==0x83 and b1==0xBF:                                  # cmp dword[rdi+d32], imm8
            dd=i32(body,j+2)
            if 0x1000<=dd<0x1800: refs.setdefault(dd,set()).add("cmp-size(IsBound)")
            j+=7; continue
        j+=1
    # a delegate BASE is either a directly-lea'd offset, or (size-test offset - 8)
    bases=set()
    for d,kinds in refs.items():
        bases.add(d-8 if "cmp-size(IsBound)" in kinds else d)
    rec={"caseIndex":i+1,"bodyRVA":hex(rva),"bodyLen":n,"typeName":typ,
         "delegateBases":[{"off":hex(b),"ptr":hex(slot(b)[0] or 0),"size":slot(b)[1],
                           "bound":bool(slot(b)[1])} for b in sorted(bases)]}
    out.append(rec)
    bs=" ".join(f"+0x{b:x}{'[BOUND]' if slot(b)[1] else '[unbound]'}" for b in sorted(bases))
    print(f"case {i+1:2d} body=+0x{rva:X} len={n:3d} type={str(typ):26s} {bs}")
json.dump(out,open("scratchpad/s118/casemap.json","w"),indent=1)
print("\n[SAVED] scratchpad/s118/casemap.json")
