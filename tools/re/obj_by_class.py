# List UObject instances whose CLASS LEAF name contains a substring, via GUObjectArray.
#   usage: obj_by_class.py <PID> <BASE-hex> <ClassNameSubstr> [LIMIT|all]
#
# ⚠ MATCHING IS LEAF-NAME SUBSTRING ONLY. It reads UClass->NamePrivate (cls+0x20) and does NOT
#   walk SuperStruct. So it CANNOT answer "does any AController-DERIVED object exist" — a
#   subclass named e.g. BP_TutorialBot_C matches nothing. Use tools/re/obj_by_chain.py for that.
#   (Class-lookup blind-spot family: obj_by_class substring · cheat_reach_probe endswith ·
#    class_props class-of-class · bpframe_readout first-match.)
#
# The optional 4th arg raises/removes the detail-list cap (default 60, see LIMIT below).
#   "all" or 0 = uncapped.  Env override: OBJ_BY_CLASS_LIMIT.
import ctypes, os, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); WANT=sys.argv[3]
_lim = sys.argv[4] if len(sys.argv)>4 else os.environ.get("OBJ_BY_CLASS_LIMIT","60")
LIMIT = 0 if str(_lim).lower() in ("all","none","0","-1") else int(_lim,0)
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
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
_cn={}
def clsname(cls):
    if cls in _cn: return _cn[cls]
    cb=rpm(cls+0x20,4); r=fname(u32(cb,0)) if cb else "?"; _cn[cls]=r; return r
hdr=rpm(OBJOBJECTS,0x18)
if not hdr: print("failed to read OBJOBJECTS (bad base?)"); sys.exit(1)
objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
print(f"NumElements={numEl}")
numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8)
hits=[]
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK)
    items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if not looksptr(obj): continue
        cb=rpm(obj+0x18,8)
        if not cb: continue
        cls=int.from_bytes(cb,"little")
        if not looksptr(cls): continue
        cn=clsname(cls)
        if WANT.lower() in cn.lower():
            nb=rpm(obj+0x20,4); nm=fname(u32(nb,0)) if nb else "?"
            if nm.startswith("Default__"): continue   # skip CDOs — LIVE instances only
            hits.append((obj,cn,nm))
print(f"found {len(hits)} LIVE (non-CDO) instance(s) whose class contains '{WANT}':")
# ⚠ THE DETAIL LIST IS CAPPED. It always was (hits[:60]), but SILENTLY — and on 2026-08-14
# that produced a wrong result that survived several turns and reached a commit message:
# counting output lines (`obj_by_class.py ... | grep -c "obj="`) saturates at the cap, so a
# class with 126 live instances read as "60". The 60 was then used to conclude that whole
# mission pools were being rejected, which was false.
# The count above was CORRECT the whole time. The fix is to make truncation impossible to
# miss, and to say plainly which number to trust.
# LIMIT is set from argv[4] / OBJ_BY_CLASS_LIMIT at the top of this file; 0 == uncapped.
_shown = hits if LIMIT == 0 else hits[:LIMIT]
for obj,cn,nm in _shown:
    print(f"  obj=0x{obj:X}  Class={cn}  Name={nm}")
if LIMIT and len(hits) > LIMIT:
    print(f"  ... {len(hits)-LIMIT} more not shown (detail list capped at {LIMIT}).")
    print(f"  !! DO NOT COUNT THESE LINES -- the real total is {len(hits)}, printed above.")
    print(f"  !! Pipe to a counter and you will get {LIMIT}, not {len(hits)}. Parse the 'found N' line.")
    print(f"  !! Pass 'all' as the 4th argument to print every row.")
else:
    print(f"  (detail list UNCAPPED: {len(_shown)} of {len(hits)} rows printed)"
          if LIMIT == 0 else f"  (all {len(hits)} rows printed; cap was {LIMIT})")
# Per-class tally -- immune to the row cap, and the actual answer to "what classes are these?"
from collections import Counter
tally = Counter(cn for _,cn,_ in hits)
print(f"\ndistinct classes: {len(tally)}")
for cn,n in tally.most_common():
    print(f"  {n:6}  {cn}")
