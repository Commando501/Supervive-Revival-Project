# claim_page_probe.py -- page-protection readout for the hero-mastery claim path.  (S120)
#
# PAGE_NOACCESS == the function has NEVER EXECUTED in this process, which makes 0x57EC800 (the
# shared claim POST sender) an exact, zero-cost detector for 'did a claim actually go out'.
# MEASURED working: 'never ran' at baseline -> 'EXECUTED' after a real claim, with both negative
# controls still 'never ran' IN THE SAME RUN.
#
# claimprobe.py -- page-protection readout for the hero-mastery claim path.
#   usage: claimprobe.py <PID> <BASE-hex>
#
# A PAGE_NOACCESS function has NEVER EXECUTED in this process (the build demand-decrypts .text on
# execution, and decryption is MONOTONE within one process lifetime). So this is an exact, zero-cost
# detector for "did a claim POST go out".
#
# NEGATIVE CONTROL is mandatory and built in: CreateMissionsModel 0x56E0600 and OnPSMissionsUpdated
# 0x56F51B0 are known-never-executed, so they MUST read FAILED. If they read OK the instrument is
# not discriminating and every other line here is uninterpretable.
# POSITIVE CONTROL: the progression ingester 0x585A570 runs every session, so it MUST read OK.
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed (process gone?)")
    raise SystemExit(1)


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("a", ctypes.c_uint32),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD), ("b", ctypes.c_uint32)]


TARGETS = [
    ("*** claim POST sender", 0x57EC800),
    ("hero-claim builder", 0x5827DA0),
    ("accountpass-claim builder", 0x5827440),
    ("GetAllClaimableHeroMasteryRewards impl", 0x583F1F0),
    ("VM level walker", 0x57ABCC0),
    ("FindVM", 0x57AB180),
    ("CheckMasteryChanges impl", 0x5795510),
    ("BulkClaimAllProgTrackRewards impl", 0x58267D0),
    ("POSCTRL progression ingester", 0x585A570),
    ("NEGCTRL CreateMissionsModel", 0x56E0600),
    ("NEGCTRL OnPSMissionsUpdated", 0x56F51B0),
]

print("PID %d base 0x%X" % (PID, BASE))
for name, rva in TARGETS:
    m = MBI()
    k.VirtualQueryEx(h, ctypes.c_void_p(BASE + rva), ctypes.byref(m), ctypes.sizeof(m))
    b = (ctypes.c_ubyte * 16)()
    r = ctypes.c_size_t()
    ok = bool(k.ReadProcessMemory(h, ctypes.c_void_p(BASE + rva), b, 16, ctypes.byref(r)) and r.value == 16)
    print("  %-40s 0x%07X  Protect=0x%03X  %s" % (name, rva, m.Protect, "EXECUTED" if ok else "never ran"))
