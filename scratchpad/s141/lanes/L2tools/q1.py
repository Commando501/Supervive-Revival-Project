import sys, struct, math
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
img = L2Img('dumps/merged14.dump.exe')

print("=== Q1: the gate constant at .rdata 0x077F5180 ===")
raw = img.read(0x077F5180, 32)
print("raw bytes @0x077F5180 (32):", ' '.join('%02x'%c for c in raw))
gate = struct.unpack('<d', raw[0:8])[0]
print()
print("gate (double) = %.20g" % gate)
print("gate repr     = %r" % gate)
print("gate hex bits = 0x%016X" % struct.unpack('<Q', raw[0:8])[0])
print("gate.hex()    = %s" % gate.hex())
print()
# candidates
a = struct.unpack('<d', struct.pack('<d', struct.unpack('<f', struct.pack('<f', 1e-3))[0]))[0]
a2 = float(struct.unpack('<f', struct.pack('<f', 1e-3))[0])          # (double)(float)1e-3
b_small = float(struct.unpack('<f', struct.pack('<f', 1e-4))[0])     # (double)(float)1e-4  = KINDA_SMALL_NUMBER
b = b_small * 10.0                                                   # times ten
c_dbl = 1e-3                                                         # exact double literal 1e-3
print("(a) (double)(float)1e-3           = %.20g   bits 0x%016X" % (a2, struct.unpack('<Q',struct.pack('<d',a2))[0]))
print("(b) (double)(float)1e-4 * 10.0    = %.20g   bits 0x%016X" % (b,  struct.unpack('<Q',struct.pack('<d',b))[0]))
print("(c) double literal 1e-3           = %.20g   bits 0x%016X" % (c_dbl, struct.unpack('<Q',struct.pack('<d',c_dbl))[0]))
print("    (double)(float)1e-4 alone     = %.20g   bits 0x%016X" % (b_small, struct.unpack('<Q',struct.pack('<d',b_small))[0]))
print()
print("MATCH (a)?", gate == a2)
print("MATCH (b)?", gate == b)
print("MATCH (c)?", gate == c_dbl)
# also: (float)1e-3 * ... alt formulations
alt = {}
alt['(double)(float)(1e-4f*10.0f)'] = float(struct.unpack('<f', struct.pack('<f', struct.unpack('<f',struct.pack('<f',1e-4))[0]*10.0))[0])
alt['(double)(float)1e-4 * (double)10']= b
alt['KINDA_SMALL_NUMBER(double)=1e-8*?']= None
for k,v in alt.items():
    if v is None: continue
    print("  alt %-34s = %.20g  match=%s" % (k, v, gate==v))
print()
thr = math.sqrt(gate)
print("escape threshold sqrt(gate) = %.20g" % thr)
print("                            = %r" % thr)
print()
# neighbours
print("--- neighbouring qwords ---")
for i in range(0, 32, 8):
    q = struct.unpack_from('<Q', raw, i)[0]
    d = struct.unpack_from('<d', raw, i)[0]
    f0,f1 = struct.unpack_from('<ff', raw, i)
    print("  0x%08X  qword=0x%016X  double=%-24.17g  floats=(%g, %g)" % (0x077F5180+i, q, d, f0, f1))
