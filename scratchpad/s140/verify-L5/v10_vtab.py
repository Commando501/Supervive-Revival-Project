import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); d=im.data; IB=im.imagebase
def q(r): return struct.unpack_from('<Q',d,r)[0]
def rvaof(v): return v-IB if IB<=v<IB+im.sizeofimage else None
VT=0x088F8570
for disp,label in [(0xAA8,'A PerformMovement'),(0x678,'D OnMovementModeChanged'),(0x720,'B StartNewPhysics'),
                   (0x3D0,'TickComponent'),(0x890,'ControlledCharacterMove'),(0xA38,'ConstrainInputAcceleration'),
                   (0x830,'PhysFalling'),(0xA50,'LF-13 disp 0xA50'),(0xAB0,'A vt+0xab0 call'),
                   (0x728,'R1 gate slot229'),(0x740,'R1 gate slot232')]:
    v=q(VT+disp); r=rvaof(v)
    print(f"disp {disp:#05x} slot {disp//8:3d}: VA {v:#x} -> RVA {r:#x}   {label}")
print()
# engine UCMC vtable? find via engine PerformMovement 0x035E9EC0 presence
# Print the ULokiCMC vtable slot count / find first non-code entry
n=0
while True:
    v=q(VT+n*8); r=rvaof(v)
    if r is None or not (0x1000 <= r < 0x764A000): break
    n+=1
print("ULokiCMC vtable contiguous code-pointer slots:", n)
