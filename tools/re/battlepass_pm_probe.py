# battlepass_pm_probe.py — S83. Read the BattlepassProgressManager (PM) account-track gates that
# decide whether CheckAccountPassChanges (0x5794480) will run the Levels populate (0x57DF4B0).
#
# Per S82-part-3 RE, CheckAccountPassChanges is gated by:
#   Gate A: GetAccountTrack (0x5840700)  -> byte[PM+0x208] != 0
#   Gate B: predicate      (0x584B920)  -> dword[track+0xEC] != -1   (track = PM+0x90 copy)
# S82 parts 4/5 measured Gate B FAILING (PM+0x17C == -1) and proved no backend field feeds it.
# If Gate B is the only thing blocking the tier grid, poking PM+0x17C >= 0 should let the populate run.
#
# usage: python battlepass_pm_probe.py [PID] [--set-tier N]   (--set-tier WRITES; probe-only by default)
import ctypes, sys, subprocess, re, io
from ctypes import wintypes
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
BASE=0x7FF6AF000000; NP=BASE+0x9D81450; OBJ=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
def find_pid():
    out=subprocess.run(["tasklist","/FI","IMAGENAME eq SUPERVIVE-Win64-Shipping.exe","/FO","CSV","/NH"],
                       capture_output=True,text=True).stdout
    m=re.search(r'"[^"]+","(\d+)"',out); return int(m.group(1)) if m else None
args=[a for a in sys.argv[1:]]
settier=None
if "--set-tier" in args:
    i=args.index("--set-tier"); settier=int(args[i+1]); del args[i:i+2]
PID=int(args[0]) if args else find_pid()
if not PID: print("NO GAME PROCESS"); sys.exit(1)
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rd(a,n):
    if not a: return None
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wr(a,data):
    r=ctypes.c_size_t(0); buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    ok=k32.WriteProcessMemory(h,ctypes.c_void_p(a),buf,len(data),ctypes.byref(r))
    return bool(ok) and r.value==len(data)
def u8(a): b=rd(a,1); return b[0] if b else -1
def i32(a): b=rd(a,4); return int.from_bytes(b,"little",signed=True) if b else None
def u64(a): b=rd(a,8); return int.from_bytes(b,"little") if b else 0
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    idx&=0xFFFFFFFF
    if idx==0: return "None"
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=u64(NP+blk*8)
    if not looksptr(bp): return "?"
    hd=rd(bp+off,2)
    if not hd: return "?"
    hh=int.from_bytes(hd,"little"); ln=hh>>6; wide=hh&1
    s=rd(bp+off+2,ln*(2 if wide else 1))
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if (s and wide) else (s.decode("latin1","replace") if s else "?")
def objname(o): return fname(ctypes.c_uint32(i32(o+0x20) or 0).value)
def clsname(o): c=u64(o+0x18); return fname(ctypes.c_uint32(i32(c+0x20) or 0).value) if looksptr(c) else "?"
def find_by_class(sub):
    hdr=rd(OBJ,0x18)
    optr=int.from_bytes(hdr[0:8],"little"); num=int.from_bytes(hdr[0x14:0x18],"little")
    for i in range(num):
        ch=u64(optr+(i//PERCHUNK)*8)
        if not looksptr(ch): continue
        o=u64(ch+(i%PERCHUNK)*STRIDE)
        if not looksptr(o): continue
        if looksptr(u64(o+0x18)) and clsname(o)==sub and not objname(o).startswith("Default__"): return o
    return 0
print(f"PID={PID}")
mgr=find_by_class("BattlepassViewManager")
if not mgr: print("no view manager"); sys.exit(1)
pm=u64(mgr+0x1C8)
print(f"BattlepassViewManager @0x{mgr:X}  ProgressionManager(PM)@+0x1C8 = 0x{pm:X} class={clsname(pm) if looksptr(pm) else '?'}")
if not looksptr(pm): sys.exit(1)
print(f"\n--- GATE A: byte[PM+0x208] (account-track present) = {u8(pm+0x208)}   (needs != 0)")
print(f"--- GATE B: dword[PM+0x90+0xEC] = dword[PM+0x17C] (CurrentTierIndex) = {i32(pm+0x17C)}   (needs != -1)")
print(f"    seasonal analogues: byte[PM+0x388]={u8(pm+0x388)}  dword[PM+0x210+0xEC]=dword[PM+0x2FC]={i32(pm+0x2FC)}")
print(f"\n--- account track struct @PM+0x90 (0x120 bytes) ---")
raw=rd(pm+0x90,0x120)
if raw:
    for off in range(0,0x120,16):
        vals=" ".join(f"{b:02X}" for b in raw[off:off+16])
        mark="   <== +0xEC CurrentTierIndex" if off<=0xEC<off+16 else ""
        print(f"  PM+0x{0x90+off:03X} (track+0x{off:03X}): {vals}{mark}")
# a few int views around the tier field
for o in (0xE0,0xE4,0xE8,0xEC,0xF0,0xF4,0xF8):
    print(f"  track+0x{o:03X} (PM+0x{0x90+o:03X}) int32 = {i32(pm+0x90+o)}")
if settier is not None:
    tgt=pm+0x90+0xEC
    before=i32(tgt)
    ok=wr(tgt,int(settier).to_bytes(4,"little",signed=True))
    print(f"\n*** WRITE CurrentTierIndex @0x{tgt:X}: {before} -> {i32(tgt)} (ok={ok}) ***")
    print("    (revert with --set-tier -1)")
