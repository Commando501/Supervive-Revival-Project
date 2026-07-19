# battlepass_oracle.py — live-read the PASSES adoption + account-pass VM state (S82).
# usage: python battlepass_oracle.py [PID]   (auto-detects SUPERVIVE PID if omitted)
#
# Reports, on the running game:
#   BattlepassInfoManager  +0x48 tracks.Num, +0x50 adopted, +0x58 target   (adopted>=target => loop stopped)
#   BattlepassViewManager  bInitialized@+0x30, AccountPassViewModel@+0x198, SeasonalPassViewModel@+0x1A8
#   AccountPassViewModel   ID@+0x60, IsAccountPass@+0x88, Levels(count)@+0xC8, ProgressionTrackAsset@+0xE8
# This is THE oracle for the battlepass_adopt_fix shim: after injecting, +0x48 should be 1 and +0x198 non-null.
import ctypes, sys, subprocess, re
from ctypes import wintypes
BASE=0x7FF6AF000000; NP=BASE+0x9D81450; OBJ=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
def find_pid():
    out=subprocess.run(["tasklist","/FI","IMAGENAME eq SUPERVIVE-Win64-Shipping.exe","/FO","CSV","/NH"],
                       capture_output=True,text=True).stdout
    m=re.search(r'"[^"]+","(\d+)"',out); return int(m.group(1)) if m else None
PID=int(sys.argv[1]) if len(sys.argv)>1 else find_pid()
if not PID: print("NO GAME PROCESS"); sys.exit(1)
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rd(a,n):
    if not a: return None
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u8(a): b=rd(a,1); return b[0] if b else -1
def u32(a): b=rd(a,4); return int.from_bytes(b,"little") if b else 0
def i32(a): b=rd(a,4); return int.from_bytes(b,"little",signed=True) if b else -1
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
def objname(o): return fname(u32(o+0x20))
def clsname(o): c=u64(o+0x18); return fname(u32(c+0x20)) if looksptr(c) else "?"
def fstr(a):
    p=u64(a); n=i32(a+8)
    if not looksptr(p) or n<=0 or n>256: return ""
    s=rd(p,n*2); return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(n) if s[i*2] or s[i*2+1]) if s else "?"
def find_by_class(sub):
    hdr=rd(OBJ,0x18); optr=u64(0);
    optr=int.from_bytes(hdr[0:8],"little"); num=int.from_bytes(hdr[0x14:0x18],"little")
    for i in range(num):
        ch=u64(optr+(i//PERCHUNK)*8)
        if not looksptr(ch): continue
        o=u64(ch+(i%PERCHUNK)*STRIDE)
        if not looksptr(o): continue
        c=u64(o+0x18)
        if looksptr(c) and clsname(o)==sub and not objname(o).startswith("Default__"): return o
    return 0
print(f"PID={PID}")
bpim=find_by_class("BattlepassInfoManager"); mgr=find_by_class("BattlepassViewManager")
if bpim:
    print(f"BattlepassInfoManager @0x{bpim:X}: tracks.Num@+0x48={i32(bpim+0x48)} adopted@+0x50={i32(bpim+0x50)} target@+0x58={i32(bpim+0x58)}  loop_stopped={i32(bpim+0x50)>=i32(bpim+0x58)}")
if mgr:
    print(f"BattlepassViewManager @0x{mgr:X}: bInitialized={u8(mgr+0x30)} BattlepassViewModels={i32(mgr+0x58+8)} MasteryViewModels={i32(mgr+0xA8+8)}")
    vm=u64(mgr+0x198)
    print(f"  AccountPassViewModel@+0x198 = 0x{vm:X}   SeasonalPassViewModel@+0x1A8 = 0x{u64(mgr+0x1A8):X}")
    if looksptr(vm):
        pta=u64(vm+0xE8)
        print(f"    ID='{fstr(vm+0x60)}' IsAccountPass={u8(vm+0x88)} Levels(count)@+0xC8={i32(vm+0xC8+8)}")
        print(f"    ProgressionTrackAsset@+0xE8 = 0x{pta:X}" + (f" name='{objname(pta)}' class={clsname(pta)} LevelRewards.Num@+0x70={i32(pta+0x68+8)}" if looksptr(pta) else " (null)"))
