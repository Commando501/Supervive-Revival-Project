# move4_bind_verify.py -- S148 Move 4 between-step verifier.
#
# Goal: before injecting the S148 self-damage arm, prove that the AvatarActor bind written by the
# preceding S149-bind-only injection is STILL LIVE on some ASC AND that the ASC has at least one
# SpawnedAttribute -- both conditions S148 flight 4 refused on.
#
# Read-only RPM. No injection, no writes, no thread suspension. Same instrument shape as
# tools/re/asc_census.py (borrowed constants + walker), stripped to the two questions Move 4 asks.
#
#   usage:
#     python tools/re/move4_bind_verify.py <PID> --hero 0x<hex>
#
#     PID   : the live SUPERVIVE-Win64-Shipping.exe process
#     --hero 0x<hex> : the possessed hero pointer parsed from the S149 marker's
#                      PLAYER-POST-BIND line (Avatar@0x410=0x<hex>)
#
# Exit codes:
#   0  PASS -- some live ASC has AvatarActor==<hero> AND SpawnedAttributes.Num >= 1
#              (S148's preflight for AVATAR_BINDING and HEALTH_COUNT bits should clear)
#   3  FAIL_BIND_LOST -- no ASC has AvatarActor==<hero> (bind cleared/GC'd between S149 and now)
#   4  FAIL_NO_ATTRSET -- AvatarActor is bound but no ASC has SpawnedAttributes.Num >= 1
#                         (S148 would refuse on HEALTH_COUNT; save the FK-32 draw and skip)
#   5  FAIL_NO_ASC -- no live ASC objects exist at all
#   6  FAIL_HERO_MALFORMED -- --hero argument couldn't be parsed
#   9  FAIL_INSTRUMENT -- OpenProcess / module resolve / property lookup failed
#
# The exit code is what configs/s148-move4.ps1 branches on. Human-readable diagnostics go to stdout.
import ctypes, sys
from ctypes import wintypes

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"
RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
# NON-STANDARD in this build (stock 0x10/0x18)
CLASS_OFF, NAME_OFF = 0x18, 0x20
SUPER_OFF, CHILDPROPS_OFF = 0x48, 0x58
FIELD_NEXT, FPROP_NAME, FPROP_OFFSET = 0x18, 0x20, 0x44

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype  = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype  = wintypes.BOOL
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype  = wintypes.HANDLE

class ME32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]

def modbase(pid):
    """Return the (base, size) of PROCNAME in `pid`, or (None, None) if not found."""
    s = k32.CreateToolhelp32Snapshot(0x8|0x10, pid)   # TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32
    if int(s) == -1: return (None, None)
    me = ME32W(); me.dwSize = ctypes.sizeof(ME32W)
    Module32FirstW = k32.Module32FirstW
    Module32NextW  = k32.Module32NextW
    Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ME32W)]
    Module32NextW.argtypes  = [wintypes.HANDLE, ctypes.POINTER(ME32W)]
    ok = Module32FirstW(s, ctypes.byref(me))
    while ok:
        if me.szModule.lower() == PROCNAME.lower():
            return (ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value, me.modBaseSize)
        ok = Module32NextW(s, ctypes.byref(me))
    return (None, None)

def rpm(h, addr, size):
    """Return `size` bytes at `addr` in process `h`, or None on any failure."""
    if not addr: return None
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)): return None
    return bytes(buf[:got.value])

def q(h, addr): b = rpm(h, addr, 8); return int.from_bytes(b, "little") if b else 0
def u32(h, addr): b = rpm(h, addr, 4); return int.from_bytes(b, "little") if b else 0
def looks(a): return isinstance(a, int) and 0x10000 < a < 0x00007FFFFFFFFFFF

def fname_str(h, base, idx):
    """Resolve an FName ComparisonIndex to its string via the pool at base+RVA_NAMEPOOL."""
    if idx <= 0: return ""
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = q(h, base + RVA_NAMEPOOL + blk*8)
    if not bp: return ""
    hdr = u32(h, bp + off) & 0xFFFF
    if not hdr: return ""
    ln = hdr >> 6; wide = hdr & 1
    b = rpm(h, bp + off + 2, ln * (2 if wide else 1))
    if not b: return ""
    try: return b.decode("utf-16-le" if wide else "utf-8", "replace")
    except: return ""

def cname(h, base, cls):
    """Class name from a UClass pointer."""
    if not looks(cls): return ""
    return fname_str(h, base, u32(h, cls + NAME_OFF))

def objects(h, base):
    """Iterate live UObjects. Yields (addr, class_ptr, class_name, obj_name_index)."""
    oo = base + RVA_OBJOBJECTS
    objects_ptr = q(h, oo)
    num_el      = u32(h, oo + 0x14)
    if not looks(objects_ptr) or num_el <= 0 or num_el > 8_000_000: return
    chunks = (num_el + PERCHUNK - 1) // PERCHUNK
    for ci in range(chunks):
        chunk = q(h, objects_ptr + ci*8)
        if not looks(chunk): continue
        cnt = num_el - ci*PERCHUNK if ci == chunks-1 else PERCHUNK
        for j in range(cnt):
            item = chunk + j*STRIDE
            obj  = q(h, item)
            if not looks(obj): continue
            cls  = q(h, obj + CLASS_OFF)
            if not looks(cls): continue
            yield (obj, cls, cname(h, base, cls), u32(h, obj + NAME_OFF))

def propoff(h, base, cls, want):
    """Resolve a UPROPERTY offset on a class chain by name. None if not found."""
    walk = cls
    depth = 0
    while looks(walk) and depth < 32:
        f = q(h, walk + CHILDPROPS_OFF)
        d = 0
        while looks(f) and d < 512:
            nm = fname_str(h, base, u32(h, f + FPROP_NAME))
            if nm == want:
                return u32(h, f + FPROP_OFFSET)
            f = q(h, f + FIELD_NEXT)
            d += 1
        walk = q(h, walk + SUPER_OFF)
        depth += 1
    return None

def is_asc_class(cn):
    """Coarse class-name predicate: any AbilitySystemComponent-shaped class."""
    return "AbilitySystemComponent" in cn or cn.endswith("ASC")

def main():
    argv = sys.argv[1:]
    if len(argv) < 3 or argv[1] != "--hero":
        print("usage: move4_bind_verify.py <PID> --hero 0x<hex>"); return 6
    try:
        pid = int(argv[0])
        hero = int(argv[2], 16) if argv[2].lower().startswith("0x") else int(argv[2], 16)
    except (ValueError, IndexError):
        print("could not parse PID or --hero"); return 6
    if not looks(hero):
        print("hero pointer 0x%X does not look like a heap address" % hero); return 6

    h = k32.OpenProcess(0x0410, False, pid)   # PROCESS_VM_READ|PROCESS_QUERY_INFORMATION
    if not h:
        print("OpenProcess failed for PID %d (err=%d)" % (pid, ctypes.get_last_error())); return 9
    base, _ = modbase(pid)
    if not base:
        print("could not find module '%s' in PID %d" % (PROCNAME, pid)); return 9
    print("PID=%d base=0x%X hero=0x%X" % (pid, base, hero))

    # ---- 1. enumerate every live ASC, look for one whose AvatarActor==hero ----------------------
    ascs = []
    for (o, c, cn, _nm) in objects(h, base):
        if is_asc_class(cn):
            ascs.append((o, c, cn))
    print("live ASC-shaped objects (excluding CDOs): %d" % len(ascs))
    if not ascs:
        print("=> no live ASC objects. VERDICT: FAIL_NO_ASC (S149 bind never took, or the game GC'd everything)")
        return 5

    # Property offsets resolved BY NAME, per-class -- never hardcoded.
    matches = []
    for (o, c, cn) in ascs:
        avaOff = propoff(h, base, c, "AvatarActor")
        if avaOff is None: continue
        av = q(h, o + avaOff)
        if av == hero:
            matches.append((o, c, cn, avaOff))
    if not matches:
        print("=> no ASC has AvatarActor==0x%X. Sampled offsets and values:" % hero)
        for (o, c, cn) in ascs[:8]:
            avaOff = propoff(h, base, c, "AvatarActor")
            av = q(h, o + avaOff) if avaOff is not None else -1
            print("     ASC 0x%X %-40s AvatarActor@0x%X = 0x%X" %
                  (o, cn, avaOff or 0, av))
        print("VERDICT: FAIL_BIND_LOST (S149-bind-only either never wrote the target ASC or it was overwritten)")
        return 3

    print("=> AvatarActor bind LIVE on %d ASC(s):" % len(matches))
    for (o, c, cn, avaOff) in matches:
        print("     ASC 0x%X %-40s AvatarActor@0x%X = 0x%X (=hero)" % (o, cn, avaOff, hero))

    # ---- 2. does any matching ASC have SpawnedAttributes.Num >= 1? -----------------------------
    # SpawnedAttributes is a TArray<UAttributeSet*> on UAbilitySystemComponent. TArray header:
    # {Data(8), Num(4), Max(4)} at the property offset.
    with_attrs = 0
    for (o, c, cn, _avaOff) in matches:
        saOff = propoff(h, base, c, "SpawnedAttributes")
        if saOff is None:
            print("     ASC 0x%X: no SpawnedAttributes property on this class -- skipped" % o)
            continue
        num = u32(h, o + saOff + 8)   # Num is at TArray+8
        data = q(h, o + saOff)
        print("     ASC 0x%X SpawnedAttributes@0x%X: Data=0x%X Num=%d" % (o, saOff, data, num))
        if num >= 1: with_attrs += 1

    if with_attrs == 0:
        print("VERDICT: FAIL_NO_ATTRSET (bind is live but S148 would refuse on HEALTH_COUNT -- skip)")
        return 4

    print("VERDICT: PASS -- %d bound ASC(s) also have SpawnedAttributes populated. S148 preflight should clear." % with_attrs)
    return 0

if __name__ == "__main__":
    sys.exit(main())
