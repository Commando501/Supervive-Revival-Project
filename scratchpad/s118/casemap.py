# S118 -- extract HandleNotif's case bodies: case index -> type-name FString -> Lobby delegate offset.
# Pure RPM, read-only. usage: casemap.py PID BASE
import ctypes,sys,json
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16)
JT   = BASE+0x4B04978     # 33 dword RVAs  (docs/fk15-handlenotif-jumptable-20260813.md)
DEF  = 0x4B048F9          # default case RVA
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
    hdr=rpm(p,16)
    if not hdr: return None
    q,num=u64(hdr,0),u32(hdr,8)
    if not q or not (0<num<200): return None
    d=rpm(q,num*2)
    if not d: return None
    return "".join(chr(d[i*2]|(d[i*2+1]<<8)) for i in range(num)).rstrip("\x00")

# ---- SELF-TEST (method-rules 10/13): the harness must reproduce a fact proved
# independently before it is allowed to report anything.
fails=[]
ctrl=fstring(BASE+0x9FFE6F0)
if ctrl!="dsNotif": fails.append(f"CTRL: .data 0x9FFE6F0 read {ctrl!r}, expected 'dsNotif'")
bogus=fstring(BASE+0x9FFE6F8)       # deliberately misaligned -> must NOT read as a type name
if bogus in ("dsNotif",): fails.append("CTRL-neg: misaligned read still produced 'dsNotif'")
tbl=rpm(JT,33*4)
if not tbl: fails.append("cannot read jump table")
else:
    rvas=[u32(tbl,i*4) for i in range(33)]
    if any(r==DEF for r in rvas): fails.append("a jump-table entry equals the default -- contradicts the static finding")
    if not all(0x4000000<r<0x6000000 for r in rvas): fails.append(f"jump-table entries out of .text range: {[hex(r) for r in rvas]}")
if fails:
    print("[ABORT] harness self-test FAILED -- VOID, not a result:"); [print("  ",f) for f in fails]; sys.exit(1)
print(f"[CTRL] .data 0x9FFE6F0 -> {ctrl!r}  PASS")
print(f"[CTRL] 33/33 jump-table entries in .text, none == default 0x{DEF:X}  PASS\n")

out=[]
for i,rva in enumerate(rvas):
    body=rpm(BASE+rva,0x140)
    idx=i+1
    typ=None; delegs=[]; leas=[]
    if body:
        j=0
        while j < len(body)-7:
            # lea rcx,[rip+d32] = 48 8D 0D d32 ; also rdx/r8 variants 48 8D 15 / 4C 8D 05
            if body[j]==0x48 and body[j+1]==0x8D and body[j+2] in (0x0D,0x15,0x05):
                tgt=BASE+rva+j+7+i32(body,j+3); s=fstring(tgt)
                leas.append((hex(rva+j),hex(tgt-BASE),s))
                if s and typ is None: typ=s
                j+=7; continue
            # lea rdx,[rdi+d32]=48 8D 97 d32 ; lea rcx,[rdi+d32]=48 8D 8F ; lea r8,[rdi+d32]=4C 8D 87
            if body[j]==0x48 and body[j+1]==0x8D and body[j+2] in (0x97,0x8F,0x87):
                delegs.append(i32(body,j+3)); j+=7; continue
            # short form lea rdx,[rdi+d8] = 48 8D 57 d8
            if body[j]==0x48 and body[j+1]==0x8D and body[j+2] in (0x57,0x4F,0x47):
                delegs.append(body[j+3]); j+=4; continue
            j+=1
    out.append(dict(caseIndex=idx, bodyRVA=hex(rva), typeName=typ,
                    delegateOffsets=[hex(d) for d in delegs], leas=[(a,t,s) for a,t,s in leas if s]))
    print(f"case {idx:2d}  body=+0x{rva:X}  type={typ!r}  lobbyOffsets={[hex(d) for d in delegs[:4]]}")
json.dump(out,open("scratchpad/s118/casemap.json","w"),indent=1)
print("\n[SAVED] scratchpad/s118/casemap.json")
