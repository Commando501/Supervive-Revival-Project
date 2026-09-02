"""Death probe: write Health.CurrentValue = 0 briefly, observe reactions.

Reads before/after, waits, checks for any game-side response (values changing
themselves, other attribute values shifting). Restores Health = 1000 at the
end to leave the state in a clean poked position.
"""
import ctypes, struct, sys, time
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
SET_PTR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x15F109D5500
HEALTH_CUR_ADDR = SET_PTR + 0x70 + 0xC   # Health.CurrentValue
HEALTH_BASE_ADDR = SET_PTR + 0x70 + 0x8  # Health.BaseValue
MAX_CUR_ADDR = SET_PTR + 0x80 + 0xC      # MaxHealth.CurrentValue
MAX_BASE_ADDR = SET_PTR + 0x80 + 0x8     # MaxHealth.BaseValue

# Also probe a few sibling offsets on the same set: Damage@+0x0, DamageMitigated@+0x10,
# Healing@+0x20, Shield@+0x30, MaxShield@+0x40 -- based on UHT prop indices
DAMAGE_ADDR = SET_PTR + 0x00 + 0xC
HEALING_ADDR = SET_PTR + 0x20 + 0xC if False else None  # skip; offsets vary

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = wintypes.BOOL
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

h = k32.OpenProcess(0x0038, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

def rpm4(addr):
    b = (ctypes.c_ubyte * 4)()
    got = ctypes.c_size_t(0)
    return struct.unpack("<I", bytes(b))[0] if k32.ReadProcessMemory(h, ctypes.c_void_p(addr), b, 4, ctypes.byref(got)) and got.value == 4 else None

def wpm4(addr, val):
    buf = struct.pack("<I", val)
    put = ctypes.c_size_t(0)
    return k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, 4, ctypes.byref(put)) and put.value == 4

def bits_to_f(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]

def snapshot(label):
    hcur = rpm4(HEALTH_CUR_ADDR)
    hbase = rpm4(HEALTH_BASE_ADDR)
    mcur = rpm4(MAX_CUR_ADDR)
    mbase = rpm4(MAX_BASE_ADDR)
    dmg = rpm4(DAMAGE_ADDR)
    print(f"  [{label}] Health.Cur={bits_to_f(hcur)} Health.Base={bits_to_f(hbase)} "
          f"MaxHealth.Cur={bits_to_f(mcur)} MaxHealth.Base={bits_to_f(mbase)} "
          f"Damage.Cur={bits_to_f(dmg)}")

print(f"PID={PID} SET_PTR=0x{SET_PTR:X}")

print("\n=== T=0: baseline (should show Health=750, MaxHealth=1000 from prior pokes) ===")
snapshot("T=0")

print("\n=== T=0.1: write Health.CurrentValue = 0.0 ===")
if not wpm4(HEALTH_CUR_ADDR, 0x00000000):
    print("write failed")
    sys.exit(4)

print("\n=== Sampling every 1s for 8s (looking for game-side reactions) ===")
for t in range(1, 9):
    time.sleep(1)
    print(f"[T=+{t}s]")
    snapshot(f"T=+{t}s")

print("\n=== T=+8s: restore Health.CurrentValue = 1000.0 ===")
if not wpm4(HEALTH_CUR_ADDR, 0x447A0000):
    print("restore failed")
    sys.exit(4)

print("\n=== T=+8.1s: post-restore verify ===")
snapshot("post-restore")

# Now check if MaxHealth or Damage moved during the death window
final_hcur = rpm4(HEALTH_CUR_ADDR)
if final_hcur == 0x447A0000:
    print("\nOK: Health.CurrentValue restored to 1000.0. Full sequence completed.")
    sys.exit(0)
else:
    print(f"\nWARN: post-restore Health.CurrentValue = 0x{final_hcur:08X}, expected 0x447A0000")
    sys.exit(5)
