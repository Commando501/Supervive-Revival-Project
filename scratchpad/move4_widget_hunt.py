"""Enumerate live UUserWidget-shaped objects looking for anything Health-related.

Approach: walk GUObjectArray, print any object whose class name contains 'Widget'
AND whose own name (or class name) hints at Health/HP/Vital/HUD. Doesn't try to
verify UMG bindings — just surfaces candidates for follow-up.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
psapi = ctypes.WinDLL("psapi")
psapi.EnumProcessModules.restype = wintypes.BOOL
psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
psapi.GetModuleBaseNameW.restype = wintypes.DWORD
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]

h = k32.OpenProcess(0x0410, False, PID)
mods = (wintypes.HMODULE * 512)()
needed = wintypes.DWORD(0)
psapi.EnumProcessModules(h, mods, ctypes.sizeof(mods), ctypes.byref(needed))
count = needed.value // ctypes.sizeof(wintypes.HMODULE)
base = None
buf = ctypes.create_unicode_buffer(260)
for i in range(count):
    psapi.GetModuleBaseNameW(h, mods[i], buf, 260)
    if buf.value.lower().startswith("supervive"):
        base = int(mods[i])
        break
print(f"base=0x{base:X}")

RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20

def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(got))
    if not ok or got.value < n:
        return None
    return bytes(b[:got.value])

def fname(idx):
    blk = idx >> 16
    off = (idx & 0xFFFF) << 1
    bp = rpm(base + RVA_NAMEPOOL + blk*8, 8)
    if not bp: return "?"
    bp = struct.unpack("<Q", bp)[0]
    if not (0x10000 <= bp < 0x0001000000000000): return "?"
    hd = rpm(bp + off, 2)
    if not hd: return "?"
    hd = struct.unpack("<H", hd)[0]
    ln = hd >> 6
    wide = hd & 1
    if ln <= 0 or ln > 200: return "?"
    s = rpm(bp + off + 2, ln * (2 if wide else 1))
    if not s: return "?"
    return ("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln))) if wide else s.decode("latin1", "replace")

gu = rpm(base + RVA_OBJOBJECTS, 32)
objects_ptr = struct.unpack("<Q", gu[0:8])[0]
num = struct.unpack("<i", gu[0x14:0x18])[0]
print(f"num objects = {num}")

# We'll batch-read chunks. Names of interest:
KEYWORDS = ["Health", "HealthBar", "HealthText", "HP_", "HP.", "HPbar", "Vital", "Hp_", "Damage"]
hits = []
chunk_ct = (num + PERCHUNK - 1) // PERCHUNK
scanned = 0
for c in range(chunk_ct):
    cp = rpm(objects_ptr + c*8, 8)
    if not cp: continue
    chunk_ptr = struct.unpack("<Q", cp)[0]
    if not (0x10000 <= chunk_ptr < 0x0001000000000000): continue
    n_this = min(PERCHUNK, num - c*PERCHUNK)
    for start in range(0, n_this, 4096):
        cnt = min(4096, n_this - start)
        raw = rpm(chunk_ptr + start*STRIDE, cnt*STRIDE)
        if not raw: continue
        for k in range(cnt):
            off = k * STRIDE
            obj_ptr = struct.unpack("<Q", raw[off:off+8])[0]
            if not (0x10000 <= obj_ptr < 0x0001000000000000): continue
            hdr = rpm(obj_ptr, 0x30)
            if not hdr: continue
            cls = struct.unpack("<Q", hdr[CLASS_OFF:CLASS_OFF+8])[0]
            name_idx = struct.unpack("<I", hdr[NAME_OFF:NAME_OFF+4])[0]
            if not (0x10000 <= cls < 0x0001000000000000): continue
            cls_hdr = rpm(cls, 0x30)
            if not cls_hdr: continue
            cls_name_idx = struct.unpack("<I", cls_hdr[NAME_OFF:NAME_OFF+4])[0]
            cls_name = fname(cls_name_idx)
            # Only look at widget-family classes
            if "Widget" not in cls_name and "HUD" not in cls_name and "Bar" not in cls_name:
                continue
            obj_name = fname(name_idx)
            # Skip archetype/CDO/GEN_VARIABLE noise
            if obj_name.startswith("Default__") or "_GEN_VARIABLE" in obj_name or "TRASHCLASS_" in obj_name or obj_name == "?":
                continue
            # Skip Class objects
            if cls_name == "?":
                continue
            joined = obj_name + " " + cls_name
            if any(k.lower() in joined.lower() for k in KEYWORDS):
                hits.append((obj_ptr, obj_name, cls_name))
            scanned += 1

print(f"\nscanned {scanned} widget-family objects")
print(f"health/HP/vital hits: {len(hits)}")
for obj, on, cn in hits[:80]:
    print(f"  0x{obj:X}  name={on!r}  class={cn}")
if len(hits) > 80:
    print(f"  ... {len(hits)-80} more")
