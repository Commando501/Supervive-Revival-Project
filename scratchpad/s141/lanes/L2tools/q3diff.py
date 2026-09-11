import sys, struct
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import cfg
img=L2Img('dumps/merged14.dump.exe')
A=img.read(0x035F4620, 0x14F); B=img.read(0x035F4770, 0x14F)
print("=== Q3: are the two helpers the SAME operation on different quats? byte diff ===")
print("len A=%d len B=%d  identical=%s" % (len(A),len(B),A==B))
diffs=[(k,A[k],B[k]) for k in range(len(A)) if A[k]!=B[k]]
print("differing byte positions: %d" % len(diffs))
for k,a,b in diffs: print("   +0x%03X  A=%02x  B=%02x   (delta %+d)" % (k,a,b,b-a))
print()
print("interpretation: every differing byte is the LOW byte of a quat displacement")
print("  A reads 0x1F0/0x1F8/0x200/0x208 ; B reads 0x210/0x218/0x220/0x228")
print("  -> the ARITHMETIC is byte-identical => SAME rotation operation, different quat.")
print("  -> neither is FQuat::UnrotateVector (that would negate the vector part and differ in arithmetic).")
print()
print("=== comisd branch semantics at the gate ===")
import math
gate = struct.unpack('<d', img.read(0x077F5180,8))[0]
for name,v in [("SizeSq2D = 0 (the fixed point)",0.0),
               ("SizeSq2D just below gate", gate*0.999),
               ("SizeSq2D == gate exactly", gate),
               ("SizeSq2D just above gate", gate*1.001),
               ("|V_xy| = 2^-10 (S140 ARM H poison)", (2.0**-10)**2),
               ("|V_xy| = 600 (S140 flight 3)", 600.0**2)]:
    taken = v > gate   # ja == CF=0 and ZF=0 == unordered-false and strictly greater
    print("  %-38s SizeSq=%-14.6g  ja taken=%-5s -> %s" %
          (name, v, taken, "SKIP (velocity kept)" if taken else "FALL THROUGH -> ZEROING WRITE EXECUTES"))
print("  NaN: comisd sets ZF=PF=CF=1 -> ja (CF=0 && ZF=0) is FALSE -> the zeroing write EXECUTES.")
print()
print("  escape threshold |V_xy| > sqrt(gate) = %.17g" % math.sqrt(gate))
print("  2^-10 = %.17g   -> ratio to threshold = %.6g  (BELOW  -> zeroed)" % (2.0**-10, (2.0**-10)/math.sqrt(gate)))
print("  600   -> ratio to threshold = %.6g  (ABOVE -> kept)" % (600.0/math.sqrt(gate)))
