import ctypes, sys
from ctypes import wintypes

PID = 44276
BASE = 0x7FF682A80000
MAP_DATA = 0x15806260600
MAP_NUM  = 0x389           # 905
STRIDE   = 0x20
HERO_TYPE = 0x1A568        # FName index of "Hero"
NAMEPOOL = BASE + 0x9D81450  # &FNamePool.Blocks[0]
HID_OFF  = 0xD3            # CatalogEntry hidden byte (from IsHidden disasm: movzx eax,byte[rcx+0xd3])
NAME_OFF = 0xC8            # CatalogEntry hero-name FName (S45)

POKE = len(sys.argv) > 1 and sys.argv[1] == "poke"

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_ALL = 0x1F0FFF
h = k32.OpenProcess(PROCESS_ALL, False, PID)
if not h:
    print("OpenProcess failed", ctypes.get_last_error()); sys.exit(1)

def rpm(addr, size):
    buf = (ctypes.c_ubyte * size)()
    n = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    if not ok or n.value != size:
        return None
    return bytes(buf)

def wpm(addr, data):
    n = ctypes.c_size_t(0)
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(n))
    return ok and n.value == len(data)

def u32(b, off): return int.from_bytes(b[off:off+4], "little")
def u64(b, off): return int.from_bytes(b[off:off+8], "little")

def fname(idx):
    block = idx >> 16
    off = (idx & 0xFFFF) << 1
    bp_b = rpm(NAMEPOOL + block*8, 8)
    if not bp_b: return "?"
    bp = int.from_bytes(bp_b, "little")
    if bp < 0x10000: return "?"
    hdr_b = rpm(bp + off, 2)
    if not hdr_b: return "?"
    hdr = int.from_bytes(hdr_b, "little")
    ln = hdr >> 6
    wide = hdr & 1
    if ln <= 0 or ln > 200: return "?"
    s = rpm(bp + off + 2, ln*(2 if wide else 1))
    if not s: return "?"
    if wide:
        return "".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln))
    return s.decode("latin1", "replace")

heroes = []
for i in range(MAP_NUM + 128):
    e = rpm(MAP_DATA + i*STRIDE, 0x18)
    if not e: continue
    ktype = u32(e, 0)
    if ktype != HERO_TYPE: continue
    kname = u32(e, 8)
    val = u64(e, 0x10)
    if val < 0x10000: continue
    ce = rpm(val, 0xE0)
    if not ce: continue
    hid = ce[HID_OFF]
    hname_idx = u32(ce, NAME_OFF)
    d0, d1, d2, d3 = ce[0xD0], ce[0xD1], ce[0xD2], ce[0xD3]
    flags = u32(ce, 0xC)
    heroes.append((fname(kname) or fname(hname_idx), val, hid, d0, d1, d2, d3, flags))

print(f"Hero CatalogEntries found: {len(heroes)}")
print(f"{'hero':<20} {'entry':>14}  d3(HID) d0 d1 d2  flags@+0xc")
nhidden = 0
for name, val, hid, d0, d1, d2, d3, flags in heroes:
    if hid: nhidden += 1
    print(f"{name:<20} 0x{val:012X}  {hid:>3}    {d0:02X} {d1:02X} {d2:02X}   0x{flags:08X}")
print(f"\nheroes with IsHidden([+0xd3]!=0) = {nhidden} / {len(heroes)}")

if POKE:
    ok = 0
    for name, val, hid, *_ in heroes:
        if wpm(val + HID_OFF, b"\x00"):
            ok += 1
    print(f"\n[POKE] set [+0xd3]=0 on {ok}/{len(heroes)} hero entries")
