import struct
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
d=open(P,'rb').read(); IB=0x7FF608F40000
def q(rva): return struct.unpack_from('<Q',d,rva)[0]
VT=0x088F8570
print("=== LokiCMC vtable %#x ==="%VT)
for disp,exp,label in [(0xAA8,0x055B8370,"PerformMovement"),(0x3D0,0x055C2B90,"TickComponent"),
                       (0x890,0x055A7680,"ControlledCharacterMove"),(0xA38,0x055A75B0,"ConstrainInputAcceleration"),
                       (0x830,0x055B89F0,"PhysFalling"),(0x720,0x055C2430,"StartNewPhysics"),
                       (0xA50,None,"?A50?"),(0x6B8,0x035E64C0,"HasValidData"),(0x0,None,"slot0")]:
    raw=q(VT+disp); rva=raw-IB
    ok = "" if exp is None else ("PASS" if rva==exp else "*** FAIL exp %#x ***"%exp)
    print(f"  +{disp:#06x} raw={raw:#018x} rva={rva:#010x}  {label:28} {ok}")
