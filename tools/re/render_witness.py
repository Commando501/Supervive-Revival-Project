# render_witness.py — IS the body component actually being DRAWN this frame?
#
# S99b. Every earlier "is the hero visible" argument in this project was indirect (screenshots, occlusion tests,
# scene-proxy theories, scale reads) and several were wrong. `bRecentlyRendered` is a reflected BoolProperty on
# **SkinnedMeshComponent** (schema.txt), i.e. directly on our body component's own class chain, and the RENDERER
# is what sets it. Reading it is a direct answer instead of an inference:
#     true  -> the component IS being submitted and drawn; anything missing from a picture is framing/capture.
#     false -> it is not being drawn, whatever the transform/visibility flags say.
# Sampled repeatedly because it is a per-frame flag.
#
#   usage: render_witness.py <PID> <compHex> [samples=8] [intervalSec=0.4]
import ctypes, sys, time
from ctypes import wintypes

PID = int(sys.argv[1], 0)
COMP = int(sys.argv[2], 16)
N = int(sys.argv[3]) if len(sys.argv) > 3 else 8
IV = float(sys.argv[4]) if len(sys.argv) > 4 else 0.4

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed"); sys.exit(1)

def rd(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)

def u32(b, o=0): return int.from_bytes(b[o:o+4], "little")
def u64(b, o=0): return int.from_bytes(b[o:o+8], "little")
def looks(v): return 0x10000 <= v < 0x1000000000000

# FNamePool base is read from the module rather than passed, to keep the call site short: the caller already
# knows the component, and the pool offset is fixed for this build.
BASE = None
for arg in sys.argv[1:]:
    pass
import subprocess
# resolve module base via the process's main module
class MODULEENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("GlblcntUsage", wintypes.DWORD), ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE), ("szModule", ctypes.c_char * 256),
                ("szExePath", ctypes.c_char * 260)]
k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
snap = k.CreateToolhelp32Snapshot(0x00000008 | 0x00000010, PID)
me = MODULEENTRY32(); me.dwSize = ctypes.sizeof(MODULEENTRY32)
if k.Module32First(snap, ctypes.byref(me)):
    BASE = ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value
if BASE is None:
    print("could not resolve module base"); sys.exit(1)
NP = BASE + 0x9D81450

def fn(idx):
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rd(NP + blk * 8, 8)
    if not bp: return "?"
    bp = u64(bp)
    if not looks(bp): return "?"
    b2 = rd(bp + off, 2)
    if not b2: return "?"
    hd = int.from_bytes(b2, "little"); ln = hd >> 6; w = hd & 1
    if ln <= 0 or ln > 200: return "?"
    s = rd(bp + off + 2, ln * (2 if w else 1))
    if not s: return "?"
    return "".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln)) if w else s.decode("latin1", "replace")

def clsof(o):
    b = rd(o + 0x18, 8); return u64(b) if b else 0
def nameof(o):
    b = rd(o + 0x20, 4); return fn(u32(b)) if b else "?"

def findprop(cls, want):
    """returns (byteOffset, byteMask) — bools are bitfields, so the MASK matters (reading the whole byte is
    what produced this project's meaningless bHidden=112 / bVisible=99 readings)."""
    d = 0
    while looks(cls) and d < 24:
        f = u64(rd(cls + 0x58, 8) or b"\0" * 8); n = 0
        while looks(f) and n < 2500:
            nb = rd(f + 0x20, 4)
            if nb and fn(u32(nb)) == want:
                ob = rd(f + 0x44, 4)
                mb = rd(f + 0x70, 1)          # FBoolProperty::FieldMask
                return (u32(ob) if ob else None, mb[0] if mb else 0xFF)
            f = u64(rd(f + 0x18, 8) or b"\0" * 8); n += 1
        cls = u64(rd(cls + 0x48, 8) or b"\0" * 8)
        d += 1
    return (None, 0)

cc = clsof(COMP)
print("component 0x%X (%s)  base=0x%X" % (COMP, nameof(cc) if looks(cc) else "?", BASE))

off, mask = findprop(cc, "bRecentlyRendered")
if off is None:
    print("bRecentlyRendered NOT FOUND on this class chain"); sys.exit(2)
print("bRecentlyRendered @0x%X mask=0x%02X" % (off, mask))

seen = []
for i in range(N):
    b = rd(COMP + off, 1)
    if b is None:
        seen.append(None)
    else:
        # try the reported mask, and also report the raw byte so a wrong mask is visible rather than silent
        seen.append((b[0], 1 if (b[0] & mask) else 0))
    if i != N - 1:
        time.sleep(IV)

for i, s in enumerate(seen):
    print("  t=%.1fs  raw=0x%02X  bRecentlyRendered=%s" % (i * IV, s[0], s[1]) if s else "  t=%.1fs  unreadable" % (i * IV))

vals = [s[1] for s in seen if s]
print("\nVERDICT: %s" % (
    "RENDERED — the renderer submitted this skinned mesh (%d/%d samples)" % (sum(vals), len(vals))
    if any(vals) else
    "NOT RENDERED — bRecentlyRendered never set across %d samples" % len(vals)))
