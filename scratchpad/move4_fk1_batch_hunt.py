"""FK-1 batch hunt: sweep live UFunctions with Auth*/Cheat*/Server* names, disassemble
each Func @+0xE0 body, classify as STRIPPED (tail-calls a known fold) or REAL.

Uses the S152 discovery pattern (a stripped stub has a real MSVC UHT exec-wrapper
prologue that unpacks FFrame params, then tail-calls the fold; the prologue itself
looks byte-identical to a real function).
"""
import ctypes, struct, sys, re
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816

# Known folds (all values in RVA, from S131 census + CLAUDE.md FK-1 block)
FOLDS = {
    0x0F7EC20: "void_ret (c2 00 00 -- ret 0)",
    0x0F7EB50: "xor eax,eax; ret (false/nullptr)",
    0x0F7EB60: "xor al,al; ret (LokiIsServer -- HARDCODED FALSE)",
    0x0B9E1F0: "mov al,1; ret (LokiIsClient -- HARDCODED TRUE)",
    0x0FC6CF0: "xorps xmm0,xmm0; ret (0.0f)",
}

# Candidate name patterns (compiled once)
# Extended S152 rev-2: adds Grant*, Kick*, Ban*, Force*, Debug*, Broadcast*, Init*
# Init* is broad in stock UE — the class-name filter below (LOKI_ONLY_PATTERNS) narrows it.
NAME_PATTERNS = re.compile(r"^(Auth|Server|Grant|Kick|Ban|Force|Debug|Broadcast|Init|.*Cheat.*)")
# For the noisy patterns (Init, Force), require the OUTER class to be Loki-family.
NOISY_NAMES = re.compile(r"^(Init|Force)")
LOKI_ONLY_PATTERNS = re.compile(r"Loki")

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
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

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
print(f"base=0x{base:X}")

RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20

def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(got))
    if not ok or got.value < n:
        return None
    return bytes(b[:got.value])

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

# Walk GUObjectArray, find UFunctions matching NAME_PATTERNS
gu = rpm(base + RVA_OBJOBJECTS, 32)
objects_ptr = struct.unpack("<Q", gu[0:8])[0]
num = struct.unpack("<i", gu[0x14:0x18])[0]
print(f"num objects = {num}")

# Prepare: identify the UClass ptr for "Function" so we can filter fast
# We'll take the class of a known candidate instead. Skip — we'll just check name match then verify.
candidates = []
chunk_ct = (num + PERCHUNK - 1) // PERCHUNK
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
            # Check the object's name first (cheap)
            obj_name = fname(name_idx)
            if not NAME_PATTERNS.match(obj_name):
                continue
            # Confirm class is "Function"
            cls_hdr = rpm(cls, 0x30)
            if not cls_hdr: continue
            cls_name = fname(struct.unpack("<I", cls_hdr[NAME_OFF:NAME_OFF+4])[0])
            if cls_name != "Function":
                continue
            # Read outer name early for the LOKI_ONLY filter on noisy patterns
            outer_ptr_bytes_early = rpm(obj_ptr + 0x28, 8)
            outer_name_early = "?"
            if outer_ptr_bytes_early:
                outer_ptr_early = struct.unpack("<Q", outer_ptr_bytes_early)[0]
                if 0x10000 <= outer_ptr_early < 0x0001000000000000:
                    outer_hdr_early = rpm(outer_ptr_early, 0x30)
                    if outer_hdr_early:
                        outer_name_early = fname(struct.unpack("<I", outer_hdr_early[NAME_OFF:NAME_OFF+4])[0])
            # For NOISY patterns (Init*/Force*), require Loki-family outer
            if NOISY_NAMES.match(obj_name) and not LOKI_ONLY_PATTERNS.search(outer_name_early):
                continue
            # Read Func @+0xE0
            func_bytes = rpm(obj_ptr + 0xE0, 8)
            if not func_bytes: continue
            func = struct.unpack("<Q", func_bytes)[0]
            if not (0x10000 <= func < 0x0001000000000000): continue
            func_rva = func - base if func >= base else func
            # Read outer name for classification
            outer_ptr_bytes = rpm(obj_ptr + 0x28, 8)
            outer_name = "?"
            if outer_ptr_bytes:
                outer_ptr = struct.unpack("<Q", outer_ptr_bytes)[0]
                if 0x10000 <= outer_ptr < 0x0001000000000000:
                    outer_hdr = rpm(outer_ptr, 0x30)
                    if outer_hdr:
                        outer_name = fname(struct.unpack("<I", outer_hdr[NAME_OFF:NAME_OFF+4])[0])
            candidates.append((obj_name, outer_name, func, func_rva))

# Dedupe
seen = set()
uniq = []
for row in candidates:
    key = (row[0], row[1], row[3])
    if key in seen: continue
    seen.add(key)
    uniq.append(row)
print(f"UFunction candidates matching Auth*/Server*/*Cheat*: {len(uniq)}")

# Disassemble each Func body up to first `ret`, looking for `call <fold>` patterns
try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_OP_IMM
except ImportError:
    print("capstone not available; classification cannot proceed")
    sys.exit(9)

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

def classify(func_va, max_bytes=384):
    body = rpm(func_va, max_bytes)
    if not body: return ("UNREADABLE", None, 0)
    fold_calls = []
    insn_count = 0
    for insn in md.disasm(body, func_va):
        insn_count += 1
        if insn_count > 128: break
        if insn.mnemonic in ("call", "jmp"):
            for op in insn.operands:
                if op.type == X86_OP_IMM:
                    target_rva = op.imm - base
                    if target_rva in FOLDS:
                        fold_calls.append((insn.address - base, insn.mnemonic, target_rva))
        if insn.mnemonic == "ret":
            break
    if fold_calls:
        return ("STRIPPED", fold_calls[-1], insn_count)  # tail-fold call (last) is the impl
    # Real function or too short to tell
    return ("REAL", None, insn_count)

print()
print(f"{'name':45s} {'outer':40s} {'func_rva':12s} {'verdict':10s} {'notes'}")
print("-" * 130)
stripped = []
real = []
unreadable = []
for name, outer, func, rva in uniq:
    verdict, fold_call, insn_count = classify(func)
    line = f"{name:45s} {outer:40s} 0x{rva:08X}   {verdict:10s}"
    if verdict == "STRIPPED":
        loc, mnem, target = fold_call
        line += f" -> {mnem} 0x{target:X} = {FOLDS[target]}"
        stripped.append((name, outer, rva, target))
    elif verdict == "REAL":
        line += f" ({insn_count} insns before first ret)"
        real.append((name, outer, rva, insn_count))
    else:
        line += f" ({verdict})"
        unreadable.append((name, outer, rva))
    print(line)

print()
print(f"summary: STRIPPED={len(stripped)} REAL={len(real)} UNREADABLE={len(unreadable)} total={len(uniq)}")

print("\n=== STRIPPED entries (add to FK-1 register) ===")
for name, outer, rva, target in sorted(stripped, key=lambda x: (x[1], x[0])):
    print(f"  {outer}::{name}  Func RVA=0x{rva:X}  impl=0x{target:X}")
