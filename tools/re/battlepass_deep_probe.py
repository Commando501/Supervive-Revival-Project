# battlepass_deep_probe.py — S83. Deep live comparison of the ACCOUNT-pass VM (shim-built, Levels=0)
# against a WORKING MASTERY VM (natively built, Levels>0), plus the adopted published track.
#
# Why: the account VM renders its tab + tier header but the tier GRID is empty (Levels@+0xC8 = 0).
# Mastery VMs are the only VMs in this build whose Levels array IS populated, so they are the
# ground-truth reference for "what a populated VM looks like" and what our synthetic track lacks.
#
# usage: python battlepass_deep_probe.py [PID]
import ctypes, sys, subprocess, re, io
from ctypes import wintypes
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
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
def i64(a): b=rd(a,8); return int.from_bytes(b,"little",signed=True) if b else -1
def u64(a): b=rd(a,8); return int.from_bytes(b,"little") if b else 0
def f32(a):
    b=rd(a,4); return ctypes.c_float.from_buffer_copy(b).value if b else 0.0
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
def paid(a):   # FPrimaryAssetId = FName Type @+0, FName Name @+8
    return f"{fname(u32(a))}:{fname(u32(a+8))}"
def arr(a):    # TArray -> (ptr, num, max)
    return (u64(a), i32(a+8), i32(a+0xC))
def find_by_class(sub, skip_default=True):
    hdr=rd(OBJ,0x18)
    optr=int.from_bytes(hdr[0:8],"little"); num=int.from_bytes(hdr[0x14:0x18],"little")
    for i in range(num):
        ch=u64(optr+(i//PERCHUNK)*8)
        if not looksptr(ch): continue
        o=u64(ch+(i%PERCHUNK)*STRIDE)
        if not looksptr(o): continue
        c=u64(o+0x18)
        if looksptr(c) and clsname(o)==sub and (not skip_default or not objname(o).startswith("Default__")): return o
    return 0

def dump_vm(vm,label):
    print(f"\n=== {label}  @0x{vm:X}  class={clsname(vm)} ===")
    print(f"  +0x60 ID                 = '{fstr(vm+0x60)}'")
    lp,ln,lm = arr(vm+0x70)
    print(f"  +0x70 LevelsToDisplay?   = TArray(ptr=0x{lp:X} num={ln} max={lm})   [int32 view={i32(vm+0x70)}]")
    print(f"  +0x78 InternalId         = '{fstr(vm+0x78)}'")
    print(f"  +0x88 IsAccountPass={u8(vm+0x88)} +0x89 IsSeasonal={u8(vm+0x89)} +0x8A IsRetired={u8(vm+0x8A)}")
    print(f"  +0x8C Season             = {paid(vm+0x8C)}")
    print(f"  +0xA0 EndDate            = {i64(vm+0xA0)}")
    print(f"  +0xA8 PurchaseableRewardTrack = '{fstr(vm+0xA8)}'")
    cp,cn,cm = arr(vm+0xB8)
    print(f"  +0xB8 Costs              = TArray(ptr=0x{cp:X} num={cn} max={cm})")
    p,n,m = arr(vm+0xC8)
    print(f"  +0xC8 Levels             = TArray(ptr=0x{p:X} num={n} max={m})   <-- THE TIER GRID")
    if looksptr(p) and 0 < n <= 128:
        # RAW dump first — element stride/type is NOT assumed. 16B PrimaryAssetId is only a guess.
        nbytes=min(n*32,0x180)
        raw=rd(p,nbytes)
        if raw:
            print(f"          Levels RAW (first 0x{nbytes:X} bytes @0x{p:X}):")
            for off in range(0,nbytes,16):
                chunk=raw[off:off+16]
                print(f"            +0x{off:03X}: "+" ".join(f"{b:02X}" for b in chunk))
        # LIVE-CORRECTED (S83): Levels is TArray<UObject*> (8-byte ptrs), NOT TArray<FPrimaryAssetId>.
        # The usmap/earlier notes said PrimaryAssetId; raw bytes show num consecutive heap pointers.
        allptr=all(looksptr(u64(p+i*8)) for i in range(n))
        print(f"          -- element test: all {n} qwords look like pointers = {allptr}")
        for i in range(min(n,12)):
            o=u64(p+i*8)
            if looksptr(o):
                cls=clsname(o); nm=objname(o)
                extra=""
                if cls!="?":
                    # LokiBattlepassLevel-ish objects: XP @+0x338 per prior RE of 0x57B1130
                    extra=f"  xp@+0x338={i32(o+0x338)}  tier?@+0x330={i32(o+0x330)}"
                print(f"             Levels[{i:2}] = 0x{o:X} class={cls} name={nm}{extra}")
    pta=u64(vm+0xE8)
    print(f"  +0xE8 ProgressionTrackAsset = 0x{pta:X}" + (f" name='{objname(pta)}' class={clsname(pta)}" if looksptr(pta) else " (NULL)"))
    if looksptr(pta):
        print(f"          asset InternalName@+0x40 = '{fstr(pta+0x40)}'")
        ap,an,am = arr(pta+0x68)
        print(f"          asset LevelRewards(map)@+0x68 num={i32(pta+0x68+8)}  LevelClass@+0xB8=0x{u64(pta+0xB8):X}")
    # raw window for anything we've mis-mapped
    raw=rd(vm+0x60,0xA0)
    if raw:
        print("  raw +0x60..+0x100:")
        for off in range(0,0xA0,16):
            print(f"    +0x{0x60+off:03X}: "+" ".join(f"{b:02X}" for b in raw[off:off+16]))

print(f"PID={PID}")
mgr=find_by_class("BattlepassViewManager"); bpim=find_by_class("BattlepassInfoManager")

# ---- the adopted published track (what the shim fed OnSuccess, deep-copied into BPIM+0x40) ----
if bpim:
    tp,tn,tm = arr(bpim+0x40)
    print(f"\n=== ADOPTED TRACKS @BPIM+0x40  TArray(ptr=0x{tp:X} num={tn} max={tm})  adopted_ver@+0x50={i64(bpim+0x50)} ===")
    if looksptr(tp) and tn>0:
        for i in range(min(tn,3)):
            e=tp+i*0x120
            print(f"  --- LokiPublishedProgressionTrack[{i}] @0x{e:X} ---")
            print(f"    +0x000 ProgressionTrackID = '{fstr(e)}'")
            print(f"    +0x010 Details.InternalId = '{fstr(e+0x10)}'")
            print(f"    +0x020 Details.Season     = {paid(e+0x20)}")
            print(f"    +0x030 Details.Start      = {i64(e+0x30)}   +0x038 End = {i64(e+0x38)}")
            print(f"    +0x040 Details.TierPurchaseDetails.Purchasable={u8(e+0x40)} MaxLevels@+0x78={i32(e+0x78)}")
            rp,rn,rm = arr(e+0x80)
            print(f"    +0x080 Details.RewardTracks    = TArray(ptr=0x{rp:X} num={rn} max={rm})   <-- reward tracks")
            print(f"    +0x090 Details.AutoClaimRewards={u8(e+0x90)}  +0x094 LevelPace={i32(e+0x94)}")
            xp,xn,xm = arr(e+0x98)
            print(f"    +0x098 Details.ExperienceRequiredPerLevel = TArray(ptr=0x{xp:X} num={xn} max={xm})  <-- per-level XP")
            print(f"    +0x0A8 IsRetired={u8(e+0xA8)} IsAccountPass={u8(e+0xA9)} IsReferralPass={u8(e+0xAA)} IsSeasonalPass={u8(e+0xAB)}")

if mgr:
    print(f"\n=== BattlepassViewManager @0x{mgr:X} bInitialized={u8(mgr+0x30)} ===")
    acct=u64(mgr+0x198)
    if looksptr(acct): dump_vm(acct,"ACCOUNT PASS VM (shim-built, grid EMPTY)")
    # walk MasteryViewModels TMap @+0xA8 : stride 0x20, key PrimaryAssetId@+0, value VM ptr@+0x10
    mp=u64(mgr+0xA8); mn=i32(mgr+0xA8+8); mm=i32(mgr+0xA8+0xC)
    print(f"\n=== MasteryViewModels map @+0xA8 ptr=0x{mp:X} num={mn} max={mm} ===")
    shown=0
    if looksptr(mp) and mn>0:
        for i in range(max(mn,mm) if mm>0 else mn):
            if shown>=2: break
            e=mp+i*0x20; v=u64(e+0x10)
            if looksptr(v) and clsname(v).endswith("ViewModel_C"):
                print(f"  entry[{i}] key={paid(e)} vm=0x{v:X}")
                dump_vm(v,f"MASTERY VM (native-built REFERENCE) key={paid(e)}")
                shown+=1
    # also the generic BattlepassViewModels map @+0x58
    bp=u64(mgr+0x58); bn=i32(mgr+0x58+8)
    print(f"\n=== BattlepassViewModels map @+0x58 ptr=0x{bp:X} num={bn} ===")
    if looksptr(bp) and bn>0:
        for i in range(min(bn+4,8)):
            e=bp+i*0x20; v=u64(e+0x10)
            if looksptr(v): print(f"  entry[{i}] key={paid(e)} vm=0x{v:X} class={clsname(v)} ID='{fstr(v+0x60)}' Levels={i32(v+0xC8+8)}")
