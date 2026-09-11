# Enumerate the game's CHEAT/DEBUG UFunction vocabulary from a LIVE process.
# Finds every UCLASS whose name matches a filter (default "Cheat"), walks its SUPER
# chain, and dumps each UFunction: decoded FunctionFlags (Exec/Net*/Native/BPCallable...),
# native-thunk addr, and an inline PARAM signature. Also lists LIVE (non-CDO) instances
# of each matched class as ready native-call targets.
#
# Motivation: the shipping build KEEPS its whole cheat RPC surface (ClientCheatFly/Ghost/Walk,
# ServerCheat*, AuthCheatChangeCharacter, ServerConsoleCommand, ServerTriggerControllerCheatCommand,
# the replicated LokiPlayerCheats object). Only the console ENABLE path was stripped (S3), NOT the
# functions. They stay reachable via the game-thread native-call primitive. This probe surfaces the
# full vocabulary + signatures BEFORE we build a native-call shim. Memory: supervive-cheat-surface-inventory.
#
#   usage: cheat_enum.py [PID|auto] [BASE-hex|auto] [classFilter=Cheat] [funcSubstr]
#   e.g.:  cheat_enum.py auto auto
#          cheat_enum.py 57360 0x7FF6B54F0000 LokiPlayerCheats
#          cheat_enum.py auto auto Cheat teleport
#
# Read-only RPM (no injection). Any thread works — this touches only static tables + object memory.
# Offsets (this build): UObject Class@+0x18 Name@+0x20; UStruct SuperStruct@+0x48 Children(UField*)@+0x50
#   ChildProperties(FField*)@+0x58; UField.Next@+0x30; UFunction.FunctionFlags@+0xB8 Func(thunk)@+0xE0;
#   FField.Next@+0x18 Name@+0x20 FFieldClass@+0x08 Flags(EPropertyFlags)@+0x38 ElementSize@+0x34;
#   CPF_Parm=0x80 CPF_OutParm=0x100 CPF_ReturnParm=0x400. GUObjectArray/NamePool are BASE-relative.
import ctypes, sys
from ctypes import wintypes

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

def _autodetect_pid():
    class PE32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snap == wintypes.HANDLE(-1).value: return None
    e = PE32W(); e.dwSize = ctypes.sizeof(PE32W)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    found = None
    while ok:
        if e.szExeFile == PROCNAME: found = e.th32ProcessID; break
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap); return found

def _autodetect_base(pid):
    class ME32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                    ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                    ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                    ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]
    # TH32CS_SNAPMODULE(0x8) | TH32CS_SNAPMODULE32(0x10)
    snap = k32.CreateToolhelp32Snapshot(0x18, pid)
    if snap == wintypes.HANDLE(-1).value: return None
    e = ME32W(); e.dwSize = ctypes.sizeof(ME32W)
    ok = k32.Module32FirstW(snap, ctypes.byref(e))  # first module == the main exe
    base = None
    while ok:
        if e.szModule == PROCNAME:
            base = ctypes.cast(e.modBaseAddr, ctypes.c_void_p).value; break
        ok = k32.Module32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap); return base

# --- args (with auto-detect) ---
a1 = sys.argv[1] if len(sys.argv) > 1 else "auto"
a2 = sys.argv[2] if len(sys.argv) > 2 else "auto"
CLSFILT = (sys.argv[3] if len(sys.argv) > 3 else "Cheat").lower()
FUNCFILT = sys.argv[4].lower() if len(sys.argv) > 4 else None

PID = _autodetect_pid() if a1 == "auto" else int(a1, 0)
if not PID: print(f"could not find process '{PROCNAME}' (is the game running?)"); sys.exit(1)
BASE = _autodetect_base(PID) if a2 == "auto" else int(a2, 16)
if not BASE: print(f"could not resolve module base for PID {PID}"); sys.exit(1)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK = 65536
STRIDE = 0x18
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h: print(f"OpenProcess failed for PID {PID} (elevation? game running?)"); sys.exit(1)

def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n: return None
    return bytes(b)
def u32(b, o): return int.from_bytes(b[o:o+4], "little")
def u64(b, o): return int.from_bytes(b[o:o+8], "little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0
def p(a): b = rpm(a, 8); return u64(b, 0) if b else 0
_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + off + 2, ln * (2 if wide else 1))
                    if s: r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln)) if wide else s.decode("latin1", "replace"))
    _nc[idx] = r; return r
def oname(o): b = rpm(o + 0x20, 4); return fname(u32(b, 0)) if b else "?"
def ocls(o): c = p(o + 0x18); return oname(c) if looksptr(c) else "?"

# --- FunctionFlags decode (UE5.4 EFunctionFlags) ---
FF = [(0x00000200, "Exec"), (0x00000040, "Net"), (0x00200000, "NetServer"),
      (0x01000000, "NetClient"), (0x00004000, "NetMulticast"), (0x00000080, "NetReliable"),
      (0x00000400, "Native"), (0x00002000, "Static"), (0x04000000, "BPCallable"),
      (0x08000000, "BPEvent"), (0x00400000, "HasOutParms"), (0x80000000, "NetValidate")]
def flagstr(fl): return ",".join(n for m, n in FF if fl & m) or "-"

# --- param signature (walk ChildProperties FField chain) ---
def fftype(f):
    fc = p(f + 0x08)
    if not looksptr(fc): return "?"
    b = rpm(fc, 4); return fname(u32(b, 0)) if b else "?"
def ffname(f): b = rpm(f + 0x20, 4); return fname(u32(b, 0)) if b else "?"
def ffdetail(f, ty):
    if ty == "StructProperty":
        st = p(f + 0x70); return fname(u32(rpm(st + 0x20, 4) or b'\0\0\0\0', 0)) if looksptr(st) else "?"
    if ty in ("ObjectProperty", "ClassProperty"):
        pc = p(f + 0x70); return fname(u32(rpm(pc + 0x20, 4) or b'\0\0\0\0', 0)) if looksptr(pc) else "?"
    if ty == "ArrayProperty":
        inner = p(f + 0x78); return "<" + fftype(inner) + ">" if looksptr(inner) else "?"
    if ty == "EnumProperty":
        en = p(f + 0x78); return fname(u32(rpm(en + 0x20, 4) or b'\0\0\0\0', 0)) if looksptr(en) else "?"
    return ""
def tyshort(ty):
    return {"IntProperty": "int32", "BoolProperty": "bool", "FloatProperty": "float",
            "DoubleProperty": "double", "StrProperty": "FString", "NameProperty": "FName",
            "ByteProperty": "byte", "Int64Property": "int64"}.get(ty, ty.replace("Property", ""))
def signature(f):
    ins, outs, ret = [], [], None
    c = p(f + 0x58); k = 0
    while looksptr(c) and k < 40:
        fl = u64(rpm(c + 0x38, 8) or b'\0'*8, 0)
        if fl & 0x80:  # CPF_Parm
            ty = fftype(c); det = ffdetail(c, ty)
            disp = tyshort(ty) + (f"({det})" if det else "")
            nm = ffname(c)
            if fl & 0x400: ret = disp
            elif fl & 0x100: outs.append(f"{disp} {nm}")
            else: ins.append(f"{disp} {nm}")
        c = p(c + 0x18); k += 1
    s = "(" + ", ".join(ins) + ")"
    if outs: s += " out[" + ", ".join(outs) + "]"
    s += " -> " + (ret if ret else "void")
    return s

# --- single GUObjectArray pass: collect cheat UClasses + live cheat instances ---
hdr = rpm(OBJOBJECTS, 0x18)
if not hdr: print("failed to read GUObjectArray (wrong base? game at a loading transition?)"); sys.exit(1)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
print(f"PID={PID} BASE=0x{BASE:X} GUObjectArray=0x{objectsPtr:X} NumElements={numEl} filter='{CLSFILT}'")
numChunks = (numEl + PERCHUNK - 1) // PERCHUNK
chunkPtrs = rpm(objectsPtr, numChunks * 8)
cheat_classes = []   # (clsobj, name)
instances = []       # (obj, clsname, name)
for ci in range(numChunks):
    chunk = int.from_bytes(chunkPtrs[ci*8:ci*8+8], "little")
    if not looksptr(chunk): continue
    cnt = min(PERCHUNK, numEl - ci*PERCHUNK)
    items = rpm(chunk, cnt * STRIDE)
    if not items: continue
    for j in range(cnt):
        obj = u64(items, j * STRIDE)
        if not looksptr(obj): continue
        nm = oname(obj); cn = ocls(obj)
        if cn == "Class":
            if CLSFILT in nm.lower(): cheat_classes.append((obj, nm))
        elif CLSFILT in cn.lower():
            if nm.startswith("Default__"): continue  # skip CDOs — LIVE instances only
            instances.append((obj, cn, nm))

if not cheat_classes:
    print(f"\nNo UClass whose name contains '{CLSFILT}' found. If the game is at the menu the class")
    print("should still be loaded; if this is empty the base/offsets may be off for this build.")
    sys.exit(0)

for clsobj, clsnm in sorted(cheat_classes, key=lambda x: x[1].lower()):
    print(f"\n########## UClass {clsnm} @0x{clsobj:X} ##########")
    cls = clsobj; level = 0
    while looksptr(cls) and level < 12:
        cn = oname(cls); funcs = []
        f = p(cls + 0x50); i = 0
        while looksptr(f) and i < 800:
            if ocls(f) == "Function":
                fn = oname(f)
                if FUNCFILT is None or FUNCFILT in fn.lower():
                    fl = u32(rpm(f + 0xB8, 4) or b'\0\0\0\0', 0)
                    funcs.append((fn, fl, f, p(f + 0xE0)))
            nb = rpm(f + 0x30, 8); f = u64(nb, 0) if nb else 0; i += 1
        if funcs or level == 0:
            tag = f' matching "{FUNCFILT}"' if FUNCFILT else ""
            print(f"\n  === [{level}] {cn}  ({len(funcs)} UFunction{tag}) ===")
        for fn, fl, addr, thunk in sorted(funcs, key=lambda x: x[0].lower()):
            print(f"    {fn:34} [{flagstr(fl):28}] thunk=0x{thunk:X}")
            print(f"        {signature(addr)}")
        cls = p(cls + 0x48); level += 1

print(f"\n########## LIVE (non-CDO) instances of '{CLSFILT}'-named classes — native-call targets ##########")
if not instances:
    print("  (none live yet — cheat objects are spawned per-PlayerController; try again in a match/tutorial)")
for obj, cn, nm in instances[:60]:
    print(f"  obj=0x{obj:X}  Class={cn}  Name={nm}")
