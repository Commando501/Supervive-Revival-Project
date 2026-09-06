"""Walk the live AdjustHealth thunk and enumerate every call target's RVA.

Identifies whether the thunk calls into 0x5516610 (the shim-expected impl) or
into a different address.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
THUNK_RVA = 0x5294270
MAX_INSNS = 200

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
print(f"module base = 0x{base:X}, thunk RVA=0x{THUNK_RVA:X}")

body = bytes(0)
b = (ctypes.c_ubyte * 512)()
got = ctypes.c_size_t(0)
k32.ReadProcessMemory(h, ctypes.c_void_p(base + THUNK_RVA), b, 512, ctypes.byref(got))
body = bytes(b[:got.value])
print(f"read {len(body)} bytes of thunk body")

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_OP_IMM
except ImportError:
    print("capstone not available; falling back to a naive E8/E9 rel32 scan")
    # Scan for E8 (call) and E9 (jmp) opcodes; note this is imprecise
    p = 0
    while p < len(body) - 5:
        op = body[p]
        if op in (0xE8, 0xE9):
            rel = struct.unpack("<i", body[p+1:p+5])[0]
            target_rva = THUNK_RVA + p + 5 + rel
            mnem = "call" if op == 0xE8 else "jmp"
            print(f"  {p:04X}: {mnem} 0x{target_rva:X}   (rel32=0x{rel:08X})")
            p += 5
        else:
            p += 1
    sys.exit(0)

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
count = 0
for insn in md.disasm(body, base + THUNK_RVA):
    if count >= MAX_INSNS:
        break
    count += 1
    if insn.mnemonic in ("call", "jmp"):
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                target_rva = op.imm - base
                marker = ""
                if target_rva == 0x5516610:
                    marker = " *** SHIM-EXPECTED (0x5516610) ***"
                print(f"  {insn.address - base:06X}: {insn.mnemonic:5s} 0x{target_rva:X}{marker}")
    if insn.mnemonic == "ret":
        print(f"  {insn.address - base:06X}: ret (thunk exit)")
        break
print(f"disassembled {count} insns")
