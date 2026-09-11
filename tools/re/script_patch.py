# Locate a UFunction's Script (TArray<uint8> bytecode) and optionally patch its first
# instruction to EX_Jump <offset>. Reliable (the VM executes Script directly; heap data,
# no .text integrity wall). Read-only unless 'patch <jmpOffset-dec>' is given.
#   read:   script_patch.py <PID> <UFunc-hex>
#   patch:  script_patch.py <PID> <UFunc-hex> patch <jmpTargetOffset-dec>
#   restore:script_patch.py <PID> <UFunc-hex> restore <hex-bytes-of-original-first-6>
import ctypes, sys
from ctypes import wintypes

PID    = int(sys.argv[1], 0)
UFUNC  = int(sys.argv[2], 16)
MODE   = sys.argv[3] if len(sys.argv) > 3 else "read"

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wpm(a,d):
    b=(ctypes.c_ubyte*len(d)).from_buffer_copy(d); r=ctypes.c_size_t(0)
    return k32.WriteProcessMemory(h,ctypes.c_void_p(a),b,len(d),ctypes.byref(r)) and r.value==len(d)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")

# find Script TArray in UFunction: scan +0x40..+0xC0 for {Data*, Num, Max} where Data[0]==0x14 (EX_LetBool)
ub = rpm(UFUNC, 0x100)
scriptDataAddr = scriptNum = scriptOff = None
for off in range(0x40, 0xC0, 8):
    dp = u64(ub, off); num = u32(ub, off+8); mx = u32(ub, off+12)
    if 0x10000 <= dp < 0x1000000000000 and 32 <= num <= 4096 and mx >= num:
        head = rpm(dp, 4)
        if head and head[0] in (0x14,0x0F,0x06,0x5F):  # plausible first opcode
            scriptDataAddr, scriptNum, scriptOff = dp, num, off
            break
if scriptDataAddr is None:
    print("Script TArray NOT found in UFunction"); sys.exit(1)
print(f"Script @UFunc+0x{scriptOff:X}  Data=0x{scriptDataAddr:X}  Num={scriptNum}")
code = rpm(scriptDataAddr, scriptNum)
print("first 16 bytes:", code[:16].hex(" "))
# key offsets from the ShouldHideHero offline dump
for lbl,o in (("off104",104),("off109",109),("off120",120)):
    if o < scriptNum: print(f"  {lbl} = {code[o:o+6].hex(' ')}")
if MODE == "dump":
    for o in range(0, scriptNum, 16):
        print(f"  {o:4d}: {code[o:o+16].hex(' ')}")
    sys.exit(0)

if MODE == "patch":
    tgt = int(sys.argv[4])
    orig6 = code[:6]
    newb = bytes([0x06]) + tgt.to_bytes(4,"little") + bytes([code[5]])  # EX_Jump tgt (5 bytes) + keep 6th byte
    # only need 5 bytes for EX_Jump; write 5
    patch = bytes([0x06]) + tgt.to_bytes(4,"little")
    print(f"orig first 6 = {orig6.hex(' ')}")
    ok = wpm(scriptDataAddr, patch)
    print(f"patched Script[0..5] = {patch.hex(' ')}  ok={ok}")
elif MODE == "restore":
    raw = bytes.fromhex(sys.argv[4].replace(" ",""))
    ok = wpm(scriptDataAddr, raw)
    print(f"restored Script[0..{len(raw)}] = {raw.hex(' ')}  ok={ok}")
elif MODE == "jump0":  # overwrite Script[0..5] with EX_Jump <target>
    tgt = int(sys.argv[4])
    print(f"orig Script[0..6] = {code[:6].hex(' ')}")
    patch = bytes([0x06]) + tgt.to_bytes(4,"little")
    print(f"jump0 -> {tgt}: wrote {patch.hex(' ')}  ok={wpm(scriptDataAddr, patch)}")
elif MODE == "pokebyte":  # flip a single byte at an offset
    off = int(sys.argv[4]); val = int(sys.argv[5],16)
    print(f"orig byte[{off}] = {code[off]:02x} -> {val:02x}  ok={wpm(scriptDataAddr+off, bytes([val]))}")
