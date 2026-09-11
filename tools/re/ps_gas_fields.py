# ps_gas_fields.py -- S111. Read the fields TryUpdateAbilitySystem's change-detector actually compares.
# READ-ONLY RPM. No injection, no writes.
#
#   usage: ps_gas_fields.py [PID|auto] [BASE|auto] [--ps 0x...] [--tag BEFORE]
#
# WHY. Disassembly (docs/s111-asc-census.md §10) showed ALokiPlayerState::TryUpdateAbilitySystem is a
# change-detector plus an event broadcast, and nothing else:
#
#     add  rcx, 0x470 ; mov rax,[rcx] ; call [rax+0x10]   ; fetch  <- EMBEDDED vtable at +0x470,
#                                                         ;           i.e. a multiple-inheritance
#                                                         ;           sub-object -- IAbilitySystemInterface
#     mov  eax,[rdi+0x0C] ; shr eax,0x1e ; ...            ; RF_Garbage validity
#     mov  rax,[this+0x650] ; cmp rdi,rax ; je RETURN     ; ★ unchanged => broadcasts NOTHING
#
# If the fetch returns null AND the cache at +0x650 is null, the compare succeeds, the early `je` is
# taken, and no AbilitySystemChanged event is ever broadcast -- so no listener runs and nothing binds
# AvatarActor. That is the standing hypothesis for why the hero's ability system is inert, and this
# prints the two values it turns on.
#
# It also prints the RVA of the fetch itself (the +0x470 vtable's slot 2), so the getter can be
# disassembled offline against dumps/tutorial-hero/ to see WHERE it looks for the ASC -- which is what
# tells us what would have to change for the detector to fire.
import ctypes, sys
from ctypes import wintypes

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"
RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20
MODSZ = 0x0B000000

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

class PE32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
class ME32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]

def autopid():
    s = k32.CreateToolhelp32Snapshot(0x2, 0); e = PE32W(); e.dwSize = ctypes.sizeof(PE32W)
    ok = k32.Process32FirstW(s, ctypes.byref(e)); f = None
    while ok:
        if e.szExeFile == PROCNAME: f = e.th32ProcessID; break
        ok = k32.Process32NextW(s, ctypes.byref(e))
    k32.CloseHandle(s); return f
def autobase(pid):
    s = k32.CreateToolhelp32Snapshot(0x18, pid); e = ME32W(); e.dwSize = ctypes.sizeof(ME32W)
    ok = k32.Module32FirstW(s, ctypes.byref(e)); b = None
    while ok:
        if e.szModule == PROCNAME: b = ctypes.cast(e.modBaseAddr, ctypes.c_void_p).value; break
        ok = k32.Module32NextW(s, ctypes.byref(e))
    k32.CloseHandle(s); return b

argv = [a for a in sys.argv[1:] if not a.startswith("--")]
PSARG, TAG = 0, ""
for i, a in enumerate(sys.argv):
    if a == "--ps" and i + 1 < len(sys.argv): PSARG = int(sys.argv[i + 1], 16)
    if a == "--tag" and i + 1 < len(sys.argv): TAG = sys.argv[i + 1]
PID = autopid() if (not argv or argv[0] == "auto") else int(argv[0], 0)
if not PID: print("game not running"); sys.exit(1)
BASE = autobase(PID) if (len(argv) < 2 or argv[1] == "auto") else int(argv[1], 16)
h = k32.OpenProcess(0x0410, False, PID) or k32.OpenProcess(0x1F0FFF, False, PID)
if not h: print("OpenProcess failed"); sys.exit(2)
g = ctypes.c_size_t(0)
def rd(a, n):
    b = (ctypes.c_ubyte * n)()
    if not a or not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(g)) or g.value != n:
        return None
    return bytes(b)
def u32(b, o=0): return int.from_bytes(b[o:o+4], "little")
def u64(b, o=0): return int.from_bytes(b[o:o+8], "little")
def looks(v): return 0x10000 <= v < 0x0001_0000_0000_0000
def p(a):
    b = rd(a, 8); return u64(b) if b else 0
_nc = {}
def fname(i):
    if i in _nc: return _nc[i]
    blk, off = i >> 16, (i & 0xFFFF) << 1
    r = "?"; bp = rd(BASE + RVA_NAMEPOOL + blk * 8, 8)
    if bp:
        bp = u64(bp)
        if looks(bp):
            hd = rd(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln, w = hd >> 6, hd & 1
                if 0 < ln < 200:
                    s = rd(bp + off + 2, ln * (2 if w else 1))
                    if s: r = ("".join(chr(s[i2*2] | (s[i2*2+1] << 8)) for i2 in range(ln))
                               if w else s.decode("latin1", "replace"))
    _nc[i] = r; return r
def onm(o):
    b = rd(o + NAME_OFF, 4); return fname(u32(b)) if b else "?"
def ocn(o):
    c = p(o + CLASS_OFF); return onm(c) if looks(c) else "?"
def desc(v):
    if v == 0: return "NULL"
    if not looks(v): return "0x%X (not a pointer)" % v
    return "0x%X (%s / %s)" % (v, ocn(v), onm(v))

# ---- locate the PlayerState -------------------------------------------------------------------
PS = PSARG
if not PS:
    hdr = rd(BASE + RVA_OBJOBJECTS, 0x18)
    objectsPtr, numEl = u64(hdr, 0), u32(hdr, 0x14)
    nch = (numEl + PERCHUNK - 1) // PERCHUNK
    cptr = rd(objectsPtr, nch * 8)
    best = []
    for ci in range(nch):
        chunk = u64(cptr, ci * 8)
        if not looks(chunk): continue
        cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
        blob = rd(chunk, cnt * STRIDE)
        if blob is None: continue
        for j in range(cnt):
            o = u64(blob, j * STRIDE)
            if not looks(o): continue
            hb = rd(o + CLASS_OFF, (NAME_OFF - CLASS_OFF) + 4)
            if not hb: continue
            c = u64(hb, 0)
            if not looks(c): continue
            nm = fname(u32(hb, NAME_OFF - CLASS_OFF))
            if nm.startswith("Default__"): continue
            cn = onm(c)
            if cn.endswith("LokiPlayerState_C") or cn == "LokiPlayerState": best.append((o, cn, nm))
    if not best: print("no LokiPlayerState instance found -- is the world up?"); sys.exit(1)
    PS = best[0][0]
    if len(best) > 1: print("(%d PlayerState candidates; using the first)" % len(best))

print("=" * 92)
print("PlayerState %s   %s" % (TAG, desc(PS)))
print("=" * 92)

# ---- the two values the change-detector compares -----------------------------------------------
sub = p(PS + 0x470)                       # the EMBEDDED sub-vtable pointer (not an object pointer)
cache650 = p(PS + 0x650)
cache658 = p(PS + 0x658)
hero_affil = p(PS + 0x4F8)

print("  [+0x470] embedded sub-vtable   0x%X %s" % (sub, "base+0x%X" % (sub - BASE) if BASE <= sub < BASE + MODSZ else "<-- NOT in module"))
if BASE <= sub < BASE + MODSZ:
    slot2 = p(sub + 0x10)
    print("           slot +0x10 (the fetch) 0x%X  %s" % (slot2,
          "base+0x%X   <-- disassemble THIS offline" % (slot2 - BASE) if BASE <= slot2 < BASE + MODSZ else "<-- not in module"))
print("  [+0x650] cached subject        %s" % desc(cache650))
# The sibling at base+0x56CEDB0 opens with `mov rbx,[rcx+0x430]; test rbx,rbx; je bail`, so +0x430 is
# its gate: null there and it does nothing, which is exactly what a null +0x658 cache looks like.
print("  [+0x430] SIBLING GATE          %s" % desc(p(PS + 0x430)))
print("  [+0x658] sibling cache         %s" % desc(cache658))
# After the gate the sibling does `lea rcx,[rbx+0x7f0]; mov rax,[rcx]; call [rax+0x10]` -- the PAWN's
# own IAbilitySystemInterface sub-vtable, i.e. hero->GetAbilitySystemComponent(). If that returns null
# the sibling bails and +0x658 is never set, which is exactly the state observed.
_pawn = p(PS + 0x430)
if looks(_pawn):
    hv = p(_pawn + 0x7F0)
    print("           hero[+0x7F0] sub-vtable 0x%X %s" % (hv, "base+0x%X" % (hv - BASE) if BASE <= hv < BASE + MODSZ else "<-- NOT in module"))
    if BASE <= hv < BASE + MODSZ:
        hs = p(hv + 0x10)
        print("           hero getter slot +0x10  0x%X  %s" % (hs,
              "base+0x%X   <-- the hero-side ASC getter" % (hs - BASE) if BASE <= hs < BASE + MODSZ else "<-- not in module"))
    print("           hero ASCStorage @0xF00  %s" % desc(p(_pawn + 0xF00)))
print("  [+0x4F8] HeroAffiliatedObject  %s" % desc(hero_affil))
if looks(hero_affil):
    asc = p(hero_affil + 0x3E8)
    print("           carrier.ASC @0x3E8    %s" % desc(asc))
    if looks(asc):
        print("           ASC.OwnerActor @0x408 %s" % desc(p(asc + 0x408)))
        print("           ASC.AvatarActor@0x410 %s" % desc(p(asc + 0x410)))
print()
print("  VERDICT: the detector takes its early `je` (and broadcasts NOTHING) when the fetch result")
print("           equals [+0x650]. Both NULL is the commonest way for that to happen.")
