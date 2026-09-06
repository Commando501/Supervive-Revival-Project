# exec_regions.py -- enumerate a live process's EXECUTABLE memory and classify each region as
# module-backed (MEM_IMAGE) or private (MEM_PRIVATE == manually mapped / JIT / unpacked code).
# Read-only: VirtualQueryEx only, no reads, no writes.
#
#   usage: exec_regions.py <PID> [addr-hex-to-locate]
#
# WHY (S121, 2026-08-15)
# ---------------------
# Two launches died at the menu with an EXECUTE fault at a fixed address in NO loaded module
# (docs/s121-menu-crash-family.md). "Executing from memory with no module entry" is exactly what
# MANUAL MAPPING produces -- and manual mapping is how this project injects every shim -- so
# "is the crash our own shim?" had to be answered rather than assumed.
#
# This makes that a one-command question for any future crash: pass the faulting address and it
# reports which region contains it, or that none does.
#
# ⚠ A crashpad minidump CANNOT answer this. Its coverage is partial: the fault page is absent from
# the dump, but so is the game's own ImageBase, which is certainly mapped. **Absence from a dump
# says nothing about whether an address was mapped** -- control any such read against an address
# you know is mapped before drawing a conclusion.
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
LOCATE = int(sys.argv[2], 16) if len(sys.argv) > 2 else None

MEM_COMMIT, MEM_IMAGE, MEM_MAPPED, MEM_PRIVATE = 0x1000, 0x1000000, 0x40000, 0x20000
EXEC_PROT = {0x10: "X", 0x20: "RX", 0x40: "RWX", 0x80: "RWXC", 0x02: "R", 0x04: "RW"}
EXEC_MASK = 0x10 | 0x20 | 0x40 | 0x80


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("__align", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD), ("__align2", wintypes.DWORD)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.VirtualQueryEx.restype = ctypes.c_size_t
psapi = ctypes.WinDLL("psapi", use_last_error=True)

h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed -- run elevated, check the PID"); sys.exit(1)


def module_name(base):
    buf = ctypes.create_unicode_buffer(260)
    if psapi.GetModuleFileNameExW(h, ctypes.c_void_p(base), buf, 260):
        return buf.value.rsplit("\\", 1)[-1]
    return ""


addr = 0
mbi = MBI()
regions = []
while addr < 0x00007FFFFFFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == MEM_COMMIT and (mbi.Protect & EXEC_MASK):
        regions.append((base, size, mbi.Protect, mbi.Type,
                        module_name(mbi.AllocationBase or 0) if mbi.Type == MEM_IMAGE else ""))
    addr = base + size
    if size == 0:
        break

priv = [r for r in regions if r[3] == MEM_PRIVATE]
img = [r for r in regions if r[3] == MEM_IMAGE]
print(f"pid {PID}: {len(regions)} executable regions  ({len(img)} image-backed, {len(priv)} PRIVATE)")
print()
print("PRIVATE executable regions (manual maps / JIT / unpacked code):")
for b, s, p, t, _ in sorted(priv):
    print(f"   0x{b:012X}  size 0x{s:<8X}  prot {EXEC_PROT.get(p, hex(p)):4}")

if priv:
    lo, hi = min(b for b, *_ in priv), max(b + s for b, s, *_ in priv)
    print(f"\n   private-exec span: 0x{lo:X} .. 0x{hi:X}")

if LOCATE is not None:
    print(f"\n=== locating 0x{LOCATE:X} ===")
    for b, s, p, t, n in sorted(regions):
        if b <= LOCATE < b + s:
            kind = "IMAGE " + n if t == MEM_IMAGE else ("PRIVATE" if t == MEM_PRIVATE else "MAPPED")
            print(f"   FOUND in {kind}  0x{b:X}..0x{b+s:X}  prot {EXEC_PROT.get(p, hex(p))}")
            break
    else:
        print("   NOT in any committed executable region.")
        below = [r for r in sorted(regions) if r[0] < LOCATE]
        if below:
            b, s, p, t, n = below[-1]
            print(f"   nearest exec below: 0x{b:X}..0x{b+s:X} "
                  f"({'IMAGE '+n if t == MEM_IMAGE else 'PRIVATE'}) gap 0x{LOCATE-(b+s):X}")
