"""Disassemble ULokiCharacter::AuthCheatSetHealth (Func @0x52FD620) to check if it
actually writes Health, or if it's a stripped-body variant.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
FUNC_RVA = 0x52FD620
MAX_INSNS = 60

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

# Known folds
FOLDS = {
    0x00F7EC20: "void_ret (c2 00 00)",
    0x00F7EB50: "xor_eax_eax_ret",
    0x00F7EB60: "LokiIsServer (xor al,al) — HARDCODED FALSE",
    0x00B9E1F0: "LokiIsClient (mov al,1) — HARDCODED TRUE",
    0x00FC6CF0: "zero_float_ret",
}

body_b = (ctypes.c_ubyte * 512)()
got = ctypes.c_size_t(0)
k32.ReadProcessMemory(h, ctypes.c_void_p(base + FUNC_RVA), body_b, 512, ctypes.byref(got))
body = bytes(body_b[:got.value])
print(f"module base = 0x{base:X}, AuthCheatSetHealth @ RVA 0x{FUNC_RVA:X}")
print(f"read {len(body)} bytes")
print(f"first 32 bytes: {' '.join(f'{b:02X}' for b in body[:32])}")

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM
except ImportError:
    print("capstone unavailable")
    sys.exit(9)

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

print("\nDisassembly:")
count = 0
call_targets = []
for insn in md.disasm(body, base + FUNC_RVA):
    if count >= MAX_INSNS:
        break
    count += 1
    off = insn.address - base
    line = f"  {off:08X}: {insn.mnemonic:6s} {insn.op_str}"
    # Annotate calls
    for op in insn.operands:
        if op.type == X86_OP_IMM and insn.mnemonic in ("call", "jmp"):
            target_rva = op.imm - base
            call_targets.append((off, insn.mnemonic, target_rva))
            fold = FOLDS.get(target_rva, "")
            line += f"    ; target RVA 0x{target_rva:X}"
            if fold:
                line += f"  *** {fold} ***"
    print(line)
    if insn.mnemonic == "ret":
        print(f"  {off:08X}: [function exit]")
        break

print(f"\ndisassembled {count} insns")
print(f"call targets: {len(call_targets)}")
for off, mnem, rva in call_targets:
    print(f"  {off:08X} {mnem} -> 0x{rva:X}  {FOLDS.get(rva, '')}")
