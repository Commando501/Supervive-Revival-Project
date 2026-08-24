# Faithful re-execution of 0x35F4620's instruction sequence, transcribed from the disassembly.
def emu(Qx,Qy,Qz,W, Vx,Vy,Vz):
    xmm3_lo, xmm3_hi = Vx, Vy
    xmm4 = W; xmm6 = Qz; xmm1 = xmm4; xmm0 = xmm6
    xmm7_lo, xmm7_hi = xmm3_lo, xmm3_hi
    xmm8 = xmm6; xmm9 = Qx; xmm5 = xmm9; xmm10 = Qy; xmm11 = xmm10
    xmm8 = xmm8 * xmm3_lo            # 35f4689 mulsd xmm8,xmm3
    xmm12 = Vz                       # 35f4693
    xmm7_lo = xmm3_hi                # 35f4699 unpckhpd xmm7,xmm3 -> lo = hi(xmm7)
    xmm0 = xmm0 * xmm7_lo            # 35f469d
    xmm11 = xmm11 * xmm12            # 35f46a1
    xmm5 = xmm5 * xmm7_lo            # 35f46a6
    xmm11 = xmm11 - xmm0             # 35f46aa
    xmm0 = xmm9                      # 35f46af
    xmm0 = xmm0 * xmm12              # 35f46b3
    xmm11 = xmm11 + xmm11            # 35f46b8
    xmm8 = xmm8 - xmm0               # 35f46bd
    xmm0 = xmm10                     # 35f46c2
    xmm0 = xmm0 * xmm3_lo            # 35f46c6
    xmm1 = xmm1 * xmm11              # 35f46ca
    xmm5 = xmm5 - xmm0               # 35f46cf
    xmm8 = xmm8 + xmm8               # 35f46d3
    xmm1 = xmm1 + xmm3_lo            # 35f46d8
    xmm3s = xmm11                    # 35f46dc movaps xmm3,xmm11
    xmm11 = xmm11 * xmm10            # 35f46e0
    xmm5 = xmm5 + xmm5               # 35f46e5
    xmm3s = xmm3s * xmm6             # 35f46e9
    xmm0 = xmm8                      # 35f46ed
    xmm0 = xmm0 * xmm6               # 35f46f1
    xmm2 = xmm5                      # 35f46fa
    xmm2 = xmm2 * xmm10              # 35f46fd
    xmm2 = xmm2 - xmm0               # 35f4707
    xmm0 = xmm5                      # 35f470b
    xmm0 = xmm0 * xmm9               # 35f470e
    xmm2 = xmm2 + xmm1               # 35f4713   -> OUT.X
    xmm1 = xmm4                      # 35f4717
    xmm1 = xmm1 * xmm8               # 35f471a
    xmm3s = xmm3s - xmm0             # 35f471f
    xmm8 = xmm8 * xmm9               # 35f4723
    xmm1 = xmm1 + xmm7_lo            # 35f472d
    xmm4 = xmm4 * xmm5               # 35f4731
    xmm8 = xmm8 - xmm11              # 35f473a
    OUTX = xmm2                      # 35f4744 [rdx]
    xmm4 = xmm4 + xmm12              # 35f4748
    xmm3s = xmm3s + xmm1             # 35f4752
    xmm8 = xmm8 + xmm4               # 35f4756
    OUTY = xmm3s                     # 35f475b [rdx+8]
    OUTZ = xmm8                      # 35f4760 [rdx+0x10]
    return OUTX,OUTY,OUTZ

def ref_rotatevector(Qx,Qy,Qz,W,Vx,Vy,Vz):
    # FQuat::RotateVector: T = 2*(Q x V); return V + W*T + (Q x T)
    Tx = 2*(Qy*Vz - Qz*Vy); Ty = 2*(Qz*Vx - Qx*Vz); Tz = 2*(Qx*Vy - Qy*Vx)
    return (Vx + W*Tx + (Qy*Tz - Qz*Ty),
            Vy + W*Ty + (Qz*Tx - Qx*Tz),
            Vz + W*Tz + (Qx*Ty - Qy*Tx))

import math, random
print("=== CONTROL 1: emulator == FQuat::RotateVector on random non-identity quats ===")
random.seed(1); worst=0
for _ in range(2000):
    a=[random.uniform(-1,1) for _ in range(4)]
    n=math.sqrt(sum(x*x for x in a)); q=[x/n for x in a]
    v=[random.uniform(-500,500) for _ in range(3)]
    e=emu(*q,*v); r=ref_rotatevector(*q,*v)
    worst=max(worst, max(abs(e[k]-r[k]) for k in range(3)))
print(f"  max |emu - reference| over 2000 random quats/vectors = {worst:g}  -> {'PASS' if worst<1e-9 else 'FAIL'}")

print("\n=== CONTROL 2 (negative): a WRONG reference must NOT match ===")
bad = lambda *a: (a[4],a[5],a[6])   # identity pass-through claimed for all quats
q=[0.0,0.7071067811865476,0.0,0.7071067811865476]; v=[1.0,2.0,3.0]
print(f"  emu(90deg-Y, (1,2,3)) = {emu(*q,*v)}   ref={ref_rotatevector(*q,*v)}   naive-passthrough={bad(*q,*v)}")
print(f"  -> emulator is NOT a trivial pass-through: {emu(*q,*v)!=tuple(v)}")

print("\n=== Q2 THE ANSWER: identity quat, input = (0, 0, GravRelZ) ===")
for gz in (0.0, -4000.0, 123.456, -0.03):
    o=emu(0.0,0.0,0.0,1.0, 0.0,0.0,gz)
    print(f"  in=(0,0,{gz!r:>10})  OUT={o}   OUT.Z==in.Z exactly: {o[2]==gz}")
print("\n=== and with input = (0,0,Z) under a NON-identity gravity quat (30deg about X) ===")
th=math.radians(30); q=[math.sin(th/2),0.0,0.0,math.cos(th/2)]
for gz in (-4000.0,):
    o=emu(*q,0.0,0.0,gz)
    print(f"  in=(0,0,{gz})  OUT={o}  -> OUT.Z is the gravity-axis component in world, NOT zero: {o[2]!=0.0}")
