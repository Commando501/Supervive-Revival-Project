import ctypes, sys
from ctypes import wintypes

PID  = int(sys.argv[1]) if len(sys.argv) > 1 else 71268
MGR  = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x24C7E28AEA0
BASE = 0x7FF682A80000
ATM_OFF   = 0x478      # LokiAssetManager -> AssetTypeMap (TMap<FPrimaryAssetType, FPrimaryAssetTypeData>)
HERO_TYPE = 0x1A568    # FName index of "Hero"
ASSETMAP_IN_TD = 0x178 # FPrimaryAssetTypeData -> AssetMap (TMap) offset (S47)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed", ctypes.get_last_error()); sys.exit(1)

def rpm(addr, size):
    buf = (ctypes.c_ubyte * size)()
    n = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)) or n.value != size:
        return None
    return bytes(buf)

def u32(b, o): return int.from_bytes(b[o:o+4], "little")
def u64(b, o): return int.from_bytes(b[o:o+8], "little")

# AssetTypeMap header
atm = rpm(MGR + ATM_OFF, 0x10)
data, num = u64(atm, 0), u32(atm, 8)
print(f"AssetTypeMap @0x{MGR+ATM_OFF:X}: Data=0x{data:X} Num={num}")

# Read a chunk of the sparse array and locate the Hero key (FName 0x1A568).
blob = rpm(data, 0x8000)
if not blob:
    print("read map data failed"); sys.exit(1)
pat = HERO_TYPE.to_bytes(4, "little")
hits = []
o = 0
while True:
    i = blob.find(pat, o)
    if i < 0: break
    hits.append(i); o = i + 4
print(f"Hero FName (0x1A568) occurrences in map data at offsets: {[hex(x) for x in hits]}")

# The element base = the KEY occurrence (value.Type is 8 bytes later). Take the first of each 8-apart pair.
elem_bases = []
seen = set()
for x in hits:
    if x - 8 in hits and x not in seen:  # x is value.Type, x-8 is key
        continue
    elem_bases.append(x); seen.add(x); seen.add(x+8)
print(f"candidate Hero element bases: {[hex(x) for x in elem_bases]}")

for eb in elem_bases:
    td = eb + 8                       # value (FPrimaryAssetTypeData) starts after 8-byte key
    am = td + ASSETMAP_IN_TD          # AssetMap TMap within the type-data
    am_hdr = rpm(data + am, 0x10) if False else rpm(data + eb + 8 + ASSETMAP_IN_TD, 0x10)
    # NOTE: eb is an offset into the buffer/region; absolute addr = data + eb
    hdr = rpm(data + eb + 8 + ASSETMAP_IN_TD, 0x10)
    if not hdr:
        print(f"  elem@+0x{eb:X}: AssetMap read failed"); continue
    am_data, am_num = u64(hdr, 0), u32(hdr, 8)
    print(f"  Hero elem@0x{data+eb:X}: AssetMap Data=0x{am_data:X} **Num={am_num}**")
