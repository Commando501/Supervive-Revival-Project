# anim_trace.py — trace floats at fixed offsets on a live object over time.
#
# S99. Companion to obj_diff_time.py. A 2-sample diff proves "something changed"; this proves the change is a
# SMOOTH, CONTINUOUS trajectory (an animation evaluating) rather than one-off noise or a re-alloc.
#
#   usage: anim_trace.py <PID> <objHex> <off1,off2,...> [samples=12] [intervalSec=0.35]
import ctypes, sys, time, struct
from ctypes import wintypes

PID = int(sys.argv[1], 0)
OBJ = int(sys.argv[2], 16)
OFFS = [int(x, 0) for x in sys.argv[3].split(",")]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 12
IV = float(sys.argv[5]) if len(sys.argv) > 5 else 0.35

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

rows = []
for i in range(N):
    vals = []
    for o in OFFS:
        b = rd(OBJ + o, 4)
        vals.append(struct.unpack_from("<f", b, 0)[0] if b else float("nan"))
    rows.append(vals)
    if i != N - 1:
        time.sleep(IV)

print("obj 0x%X   %d samples @ %.2fs" % (OBJ, N, IV))
print("    t   " + "".join("  +0x%04X " % o for o in OFFS))
for i, vals in enumerate(rows):
    print("  %5.2f " % (i * IV) + "".join("  %8.5f" % v for v in vals))

print("\n  delta " + "".join("  %+8.5f" % (rows[-1][j] - rows[0][j]) for j in range(len(OFFS))))
moved = sum(1 for j in range(len(OFFS)) if any(rows[i][j] != rows[0][j] for i in range(1, N)))
print("\n%d/%d traced floats moved -> %s" % (
    moved, len(OFFS),
    "CONTINUOUS MOTION (the skeleton is being posed every frame)" if moved else "STATIC"))
