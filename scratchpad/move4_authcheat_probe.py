"""Find ULokiCharacter::AuthCheatSetHealth UFunction and grade its Func pointer.

Enumerates live UObjects looking for a UFunction whose name matches, then reads
UFunction+0xE0 (Func) and classifies against known stripped folds.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
TARGET_NAME = "AuthCheatSetHealth"

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.EnumProcessModules = ctypes.WinDLL("psapi").EnumProcessModules
k32.EnumProcessModules.restype = wintypes.BOOL
k32.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
k32.GetModuleBaseNameW = ctypes.WinDLL("psapi").GetModuleBaseNameW
k32.GetModuleBaseNameW.restype = wintypes.DWORD
k32.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]

h = k32.OpenProcess(0x0410, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

def rpm(addr, n):
    buf = (ctypes.c_ubyte * n)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
    if not ok or got.value < n:
        return None
    return bytes(buf[:got.value])

# Locate module base
mods = (wintypes.HMODULE * 512)()
needed = wintypes.DWORD(0)
k32.EnumProcessModules(h, mods, ctypes.sizeof(mods), ctypes.byref(needed))
count = needed.value // ctypes.sizeof(wintypes.HMODULE)
base = None
namebuf = ctypes.create_unicode_buffer(260)
for i in range(count):
    k32.GetModuleBaseNameW(h, mods[i], namebuf, 260)
    if namebuf.value.lower().startswith("supervive"):
        base = int(mods[i])
        break
if not base:
    print("could not find SUPERVIVE module base")
    sys.exit(9)
print(f"PID={PID} base=0x{base:X}")

# Constants per this build (non-standard UObjectBase layout: CLASS_OFF=0x18, NAME_OFF=0x20)
RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20

# Known folds (from CLAUDE.md FK-1 / S131 census)
FOLDS = {
    0x0F7EC20: "void_ret_c2_00_00 (ret 0)",
    0x0F7EB50: "xor_al_al_ret (returns false)",
    0x0F7EB60: "xor_al_al_ret (returns false, sibling)",
    0x0B9E1F0: "mov_al_1_ret (returns true)",
    0x0FC6CF0: "xorps_xmm0_xmm0_ret (returns 0.0f)",
    0x0F7EB50: "xor_eax_eax_ret",
}

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

# Walk GUObjectArray
gu = rpm(base + RVA_OBJOBJECTS, 32)
if not gu:
    print("could not read GUObjectArray")
    sys.exit(9)
# Per tools/re/move4_bind_verify.py: Objects=+0x00, NumElements=+0x14 (this build)
objects_ptr = struct.unpack("<Q", gu[0:8])[0]
num = struct.unpack("<i", gu[0x14:0x18])[0]
print(f"GUObjectArray: Data=0x{objects_ptr:X} Num={num}")

# Chunks
chunk_ct = (num + PERCHUNK - 1) // PERCHUNK
found = []
for c in range(chunk_ct):
    chunk_ptr_bytes = rpm(objects_ptr + c*8, 8)
    if not chunk_ptr_bytes: continue
    chunk_ptr = struct.unpack("<Q", chunk_ptr_bytes)[0]
    if not (0x10000 <= chunk_ptr < 0x0001000000000000): continue
    n_this = min(PERCHUNK, num - c*PERCHUNK)
    # Read a batch of the chunk
    batch_sz = 4096
    for start in range(0, n_this, batch_sz):
        cnt = min(batch_sz, n_this - start)
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
            nm = fname(name_idx)
            if nm != TARGET_NAME: continue
            # Confirm class is a UFunction
            if not (0x10000 <= cls < 0x0001000000000000): continue
            cls_hdr = rpm(cls, 0x30)
            if not cls_hdr: continue
            cls_name_idx = struct.unpack("<I", cls_hdr[NAME_OFF:NAME_OFF+4])[0]
            cls_name = fname(cls_name_idx)
            # Read Func at UFunction+0xE0
            func_bytes = rpm(obj_ptr + 0xE0, 8)
            if not func_bytes: continue
            func = struct.unpack("<Q", func_bytes)[0]
            func_rva = func - base if func >= base else func
            fold_label = FOLDS.get(func_rva, None)
            # Also read outer (owner class)
            outer_ptr_bytes = rpm(obj_ptr + 0x28, 8)
            outer_name = "?"
            if outer_ptr_bytes:
                outer_ptr = struct.unpack("<Q", outer_ptr_bytes)[0]
                if 0x10000 <= outer_ptr < 0x0001000000000000:
                    outer_hdr = rpm(outer_ptr, 0x30)
                    if outer_hdr:
                        outer_name = fname(struct.unpack("<I", outer_hdr[NAME_OFF:NAME_OFF+4])[0])
            found.append((obj_ptr, cls_name, outer_name, func, func_rva, fold_label))

print(f"\nUFunction '{TARGET_NAME}' matches: {len(found)}")
for obj, cls_name, outer, func, rva, fold in found:
    print(f"  obj=0x{obj:X}  class={cls_name}  outer={outer}")
    print(f"    Func=0x{func:X}  RVA=0x{rva:X}  {'*** FOLD: ' + fold + ' ***' if fold else '(not a known fold)'}")
    # Read the first 4 bytes of the function code for a signature check
    code = rpm(func, 8)
    if code:
        print(f"    first 8 bytes: {' '.join(f'{b:02X}' for b in code)}")
