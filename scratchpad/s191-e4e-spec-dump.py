"""Read spec[0] on the live process to enumerate FGameplayAbilitySpec state.
Read-only RPM. E4E K_GRANT'd spec was at 0x1C27ADB4ED0 in process 55960.
"""
import ctypes, sys
from ctypes import wintypes

k = ctypes.windll.kernel32
k.OpenProcess.restype = wintypes.HANDLE
k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k.ReadProcessMemory.restype = wintypes.BOOL
k.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PID = 55960
ASC = 0x1C2AAB80100
ITEMS_DATA_EXPECTED = 0x1C27ADB4ED0  # E4E measurement

h = k.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {k.GetLastError()}")
    sys.exit(1)

def rpm(addr, size):
    buf = (ctypes.c_ubyte * size)()
    read = ctypes.c_size_t(0)
    ok = k.ReadProcessMemory(h, addr, buf, size, ctypes.byref(read))
    if not ok or read.value != size:
        return None
    return bytes(buf)

# Read Items header
hdr = rpm(ASC + 0x538, 16)
if hdr is None:
    print(f"[FAIL] cannot read ASC+0x538 ({ASC+0x538:#x}) - process gone or ASC moved")
    sys.exit(1)
items_data = int.from_bytes(hdr[0:8], 'little')
items_num  = int.from_bytes(hdr[8:12], 'little', signed=True)
items_max  = int.from_bytes(hdr[12:16], 'little', signed=True)
print(f"[LIVE] ASC=0x{ASC:X}  Items.Data=0x{items_data:X}  Num={items_num}  Max={items_max}  (expected Data=0x{ITEMS_DATA_EXPECTED:X})")

if items_num < 1:
    print("[FAIL] Items is empty (spec cleaned up by ability system since E4E?)")
    sys.exit(1)

# Read full 0xF8 stride of spec[0]
spec = rpm(items_data, 0xF8)
if spec is None:
    print(f"[FAIL] cannot read spec[0] at 0x{items_data:X}")
    sys.exit(1)

# Enumerate every 8-byte and 4-byte and byte field of interest
print(f"\n[SPEC[0]] full dump at 0x{items_data:X} (0xF8 bytes):")
for off in range(0, 0xF8, 16):
    row = spec[off:off+16]
    hexs = ' '.join(f'{b:02x}' for b in row)
    print(f"  +0x{off:03X}: {hexs}")

# Named fields per workflow model / CLAUDE.md
def u8(o):  return spec[o]
def u16(o): return int.from_bytes(spec[o:o+2], 'little')
def u32(o): return int.from_bytes(spec[o:o+4], 'little')
def i32(o): return int.from_bytes(spec[o:o+4], 'little', signed=True)
def u64(o): return int.from_bytes(spec[o:o+8], 'little')

print(f"\n[SPEC[0] NAMED FIELDS]:")
print(f"  +0x00  ??:                    0x{u64(0x00):X}")
print(f"  +0x08  ??:                    0x{u64(0x08):X}")
print(f"  +0x0C  Handle:                {i32(0x0C)}")
print(f"  +0x10  Ability:               0x{u64(0x10):X}")
print(f"  +0x18  ??:                    0x{u64(0x18):X}")
print(f"  +0x20  Level:                 {i32(0x20)}")
print(f"  +0x24  InputID:               {i32(0x24)}")
print(f"  +0x28  bIsBeingDestroyed?:    {u8(0x28)}")
print(f"  +0x30  Source (weakobj+ser):  0x{u64(0x30):X} 0x{u32(0x38):X}")
print(f"  +0x38  ??:                    0x{u64(0x38):X}")
print(f"  +0x39  flag byte (S159):      0x{u8(0x39):02X}  (bits 01=InputPressed 02=RemoveAfterActivation 04=PendingRemove 08=bActivateOnce 10=? 40=?)")
print(f"  +0x3A  ??:                    0x{u8(0x3A):02X}")
print(f"  +0x40  ??:                    0x{u64(0x40):X}")
print(f"  +0x48  ??:                    0x{u64(0x48):X}")
print(f"  +0x50  ??:                    0x{u64(0x50):X}")
print(f"  +0x58  ??:                    0x{u64(0x58):X}")
print(f"  +0x60  ??:                    0x{u64(0x60):X}")
print(f"  +0x68  ??:                    0x{u64(0x68):X}")
print(f"  +0x70  ??:                    0x{u64(0x70):X}")
print(f"  +0x78  ??:                    0x{u64(0x78):X}")
print(f"  +0x80  NonRep.Data:           0x{u64(0x80):X}")
print(f"  +0x88  NonRep.Num:            {i32(0x88)}")
print(f"  +0x8C  NonRep.Max:            {i32(0x8C)}")
print(f"  +0x90  Rep.Data:              0x{u64(0x90):X}")
print(f"  +0x98  Rep.Num:               {i32(0x98)}")
print(f"  +0x9C  Rep.Max:               {i32(0x9C)}")
print(f"  +0xA0  ??:                    0x{u64(0xA0):X}")
print(f"  +0xA8  ??:                    0x{u64(0xA8):X}")
print(f"  +0xB0  ??:                    0x{u64(0xB0):X}")
print(f"  +0xB8  ??:                    0x{u64(0xB8):X}")
print(f"  +0xC0  ??:                    0x{u64(0xC0):X}")
print(f"  +0xC8  ??:                    0x{u64(0xC8):X}")
print(f"  +0xD0  ??:                    0x{u64(0xD0):X}")
print(f"  +0xD8  ??:                    0x{u64(0xD8):X}")
print(f"  +0xE0  ??:                    0x{u64(0xE0):X}")
print(f"  +0xE8  ??:                    0x{u64(0xE8):X}")
print(f"  +0xF0  ??:                    0x{u64(0xF0):X}")

# Also read [Ability+0xEE] byte AND the value at [Ability+0xC0]/[Ability+0xC8] which is where
# workflow docs typically place InstancingPolicy (0=NonInstanced, 1=InstancedPerActor, 2=InstancedPerExecution)
ability_ptr = u64(0x10)
if ability_ptr:
    ability = rpm(ability_ptr, 0x200)
    if ability:
        print(f"\n[Ability CDO @ 0x{ability_ptr:X}]:")
        print(f"  +0xEE:  0x{ability[0xEE]:02X}")
        # dump 0xE0..0x110 (where InstancingPolicy typically sits in stock UE UGameplayAbility)
        for off in [0xE0, 0xE8, 0xF0, 0xF8, 0x100, 0x108, 0x110]:
            row = ability[off:off+8]
            print(f"  +0x{off:03X}: {row.hex(' ')}  (u64=0x{int.from_bytes(row,'little'):X})")

k.CloseHandle(h)
