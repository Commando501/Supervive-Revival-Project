# obj_diff_time.py — sample a raw object window TWICE and report which qwords/floats changed.
#
# S99. Reflection is blind to the fields that prove an animation is ticking (UAnimInstance's delta-time /
# the FAnimSingleNodeInstanceProxy's CurrentTime are plain C++ members, no UPROPERTY). This is the
# reflection-free witness: read N bytes at an object twice, diff, and print every changed 4-byte slot with a
# plausible float interpretation. Any changing float inside an AnimInstance == it is being TICKED and the
# skeleton is being posed.
#
#   usage: obj_diff_time.py <PID> <objHex> [bytes=0x600] [delaySec=2.0]
import ctypes, sys, time, struct
from ctypes import wintypes

PID = int(sys.argv[1], 0)
OBJ = int(sys.argv[2], 16)
N = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x600
DELAY = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed"); sys.exit(1)

def rd(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)

a = rd(OBJ, N)
if a is None:
    print("unreadable at 0x%X (+0x%X)" % (OBJ, N)); sys.exit(1)
time.sleep(DELAY)
b = rd(OBJ, N)
if b is None:
    print("second read failed"); sys.exit(1)

def f32(buf, o):
    v = struct.unpack_from("<f", buf, o)[0]
    return v if (v == v and abs(v) < 1e12) else None

changed = []
for o in range(0, N, 4):
    if a[o:o+4] != b[o:o+4]:
        changed.append(o)

print("object 0x%X  window 0x%X  delay %.1fs  -> %d changed dwords" % (OBJ, N, DELAY, len(changed)))
for o in changed:
    fa, fb = f32(a, o), f32(b, o)
    ia = int.from_bytes(a[o:o+4], "little"); ib = int.from_bytes(b[o:o+4], "little")
    note = ""
    if fa is not None and fb is not None and (0.0 <= fa < 1000.0) and (0.0 <= fb < 1000.0):
        note = "   float %.5f -> %.5f  (d=%+.5f)" % (fa, fb, fb - fa)
    print("  +0x%04X  %08X -> %08X%s" % (o, ia, ib, note))

print("\nVERDICT: %s" % ("TICKING — %d fields advanced, the object is being updated every frame" % len(changed)
                        if changed else "STATIC — nothing in this window changed over %.1fs" % DELAY))
