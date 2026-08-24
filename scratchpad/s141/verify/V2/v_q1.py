import sys,struct; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg
I = VImg('dumps/merged14.dump.exe')
raw = I.read(0x077F5180, 48)
print("bytes @0x077F5180:", ' '.join('%02x'%b for b in raw[:16]))
print("bytes @0x077F5190:", ' '.join('%02x'%b for b in raw[16:32]))
g = struct.unpack('<d', raw[0:8])[0]
gb = struct.unpack('<Q', raw[0:8])[0]
print("gate double = %.20g  bits=0x%016X  hex=%s" % (g, gb, g.hex()))
n = struct.unpack('<d', raw[8:16])[0]
print("next  double = %.20g  bits=0x%016X" % (n, struct.unpack('<Q',raw[8:16])[0]))
def bits(x): return struct.unpack('<Q', struct.pack('<d', x))[0]
import numpy as np
cands = {
 "(double)(float)1e-3"        : float(np.float32(1e-3)),
 "(double)(float)1e-4 * 10.0" : float(np.float32(1e-4))*10.0,
 "double literal 1e-3"        : 1e-3,
 "(double)(float)(1e-4f*10f)" : float(np.float32(np.float32(1e-4)*np.float32(10.0))),
 "(double)(float)1e-4"        : float(np.float32(1e-4)),
 "(double)(float)(1e-3f*1f)"  : float(np.float32(1e-3)),
 "(double)(float)0.001f"      : float(np.float32(0.001)),
}
for k,v in cands.items():
    print("  %-30s %.20g  bits=0x%016X  %s" % (k, v, bits(v), "*** EXACT MATCH ***" if bits(v)==gb else "no"))
# trailing zero bits of mantissa
tz = (gb & -gb).bit_length()-1
print("trailing zero bits of gate:", tz)
print("trailing zero bits of (double)(float)1e-4:", (bits(float(np.float32(1e-4))) & -bits(float(np.float32(1e-4)))).bit_length()-1)
import math
print("sqrt(gate) = %.20g" % math.sqrt(g))
print("seed said   0.03162277644  -> delta %.3g" % (math.sqrt(g)-0.03162277644))
print("L2 said     0.031622776202254524 -> delta %.3g" % (math.sqrt(g)-0.031622776202254524))
print("sqrt(1e-3) = %.20g" % math.sqrt(1e-3))
# retrodiction
for v in (2**-10, 600.0):
    print("  |Vxy|=%g SizeSq=%.6g  vs gate %.6g  -> %s" % (v, v*v, g, "ABOVE(kept)" if v*v>g else "BELOW(zeroed)"))
