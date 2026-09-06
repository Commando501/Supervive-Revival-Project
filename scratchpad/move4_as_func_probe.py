"""Probe: read Func @+0xE0 on the live AS UFunctions we just found, and check
if they're callable (non-null, in-image, not a fold).

Answers CLAUDE.md's open question: 'S55 primitive does not apply to AS'
(because Func @+0xE0 = 0). Is that still true in the tutorial world?
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
TARGETS = ["SpawnDropPodForTeam", "Respawn"]

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
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("__pad1", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD), ("__pad2", wintypes.DWORD)]

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

RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20

def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(got))
    if not ok or got.value < n: return None
    return bytes(b[:got.value])

def fname(idx):
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(base + RVA_NAMEPOOL + blk*8, 8)
    if not bp: return "?"
    bp = struct.unpack("<Q", bp)[0]
    if not (0x10000 <= bp < 0x0001000000000000): return "?"
    hd = rpm(bp + off, 2)
    if not hd: return "?"
    hd = struct.unpack("<H", hd)[0]; ln = hd >> 6; wide = hd & 1
    if ln <= 0 or ln > 200: return "?"
    s = rpm(bp + off + 2, ln * (2 if wide else 1))
    if not s: return "?"
    return ("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln))) if wide else s.decode("latin1", "replace")

gu = rpm(base + RVA_OBJOBJECTS, 32)
objects_ptr = struct.unpack("<Q", gu[0:8])[0]
num = struct.unpack("<i", gu[0x14:0x18])[0]

FOLDS = {0xF7EC20, 0xF7EB50, 0xF7EB60, 0xB9E1F0, 0xFC6CF0}

# Find each target's UFunction object
chunk_ct = (num + PERCHUNK - 1) // PERCHUNK
found = []
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
            obj_name = fname(name_idx)
            if obj_name not in TARGETS:
                continue
            cls_hdr = rpm(cls, 0x30)
            if not cls_hdr: continue
            cls_name = fname(struct.unpack("<I", cls_hdr[NAME_OFF:NAME_OFF+4])[0])
            if "Function" not in cls_name:
                continue
            outer_ptr_bytes = rpm(obj_ptr + 0x28, 8)
            outer_name = "?"
            if outer_ptr_bytes:
                outer_ptr = struct.unpack("<Q", outer_ptr_bytes)[0]
                if 0x10000 <= outer_ptr < 0x0001000000000000:
                    outer_hdr = rpm(outer_ptr, 0x30)
                    if outer_hdr:
                        outer_name = fname(struct.unpack("<I", outer_hdr[NAME_OFF:NAME_OFF+4])[0])
            # Read Func @+0xE0
            func_bytes = rpm(obj_ptr + 0xE0, 8)
            if not func_bytes: continue
            func = struct.unpack("<Q", func_bytes)[0]
            func_rva = None
            page_state = "?"
            if func == 0:
                page_state = "NULL"
            else:
                if func >= base:
                    func_rva = func - base
                # Check page state
                mbi = MEMORY_BASIC_INFORMATION()
                got = k32.VirtualQueryEx(h, ctypes.c_void_p(func), ctypes.byref(mbi), ctypes.sizeof(mbi))
                if got:
                    prot = mbi.Protect
                    if prot & 0x01: page_state = "NOACCESS"
                    elif prot & 0x20: page_state = "RX (decrypted)"
                    elif prot & 0x40: page_state = "RWX"
                    else: page_state = f"0x{prot:X}"
            found.append((obj_name, outer_name, cls_name, obj_ptr, func, func_rva, page_state))

print(f"base = 0x{base:X}")
print(f"\n=== AS UFunction Func @+0xE0 probe ===\n")
for on, outer, cn, obj, func, rva, ps in found:
    tag = ""
    if rva is not None and rva in FOLDS:
        tag = " *** IS A KNOWN FOLD ***"
    elif func == 0:
        tag = " *** NULL — matches CLAUDE.md 'S55 primitive does not apply to AS' ***"
    print(f"  {on:30s} on outer={outer}  class={cn}")
    print(f"    obj=0x{obj:X}  Func=0x{func:X}" + (f" (RVA=0x{rva:X})" if rva is not None else "") + f"  page={ps}{tag}")
    if func != 0 and rva is not None:
        code = rpm(func, 12)
        if code:
            print(f"    first 12 bytes: {' '.join(f'{b:02X}' for b in code)}")
    print()
