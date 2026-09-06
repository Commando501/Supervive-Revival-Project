import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img()
print("RAW BYTE EVIDENCE (merged13, RVA==file offset, flat=%s)"%im.flat())
for r,n,lbl in [(0x035E9EEE,7,'mov r13,[rcx+0xc0]  (World)'),
                (0x035E9F00,5,'test r13,r13 / jne'),
                (0x035E9F17,6,'call [rdx+0x6b8] HasValidData'),
                (0x035E9F1D,8,'test al,al / je 0x35eb1a7   EXIT1'),
                (0x035E9F25,9,'test r13,r13 / je 0x35eb1a7 EXIT2'),
                (0x035E9F2E,7,'mov rcx,[rbx+0xd0] UpdatedComponent'),
                (0x035E9F7F,3,'xor r15d,r15d'),
                (0x035E9F90,13,'cmp byte[rbx+0x231],r15b / je 0x35eb7cf EXIT3'),
                (0x035E9F9D,13,'cmp byte[rcx+0x1bb],2 / jne 0x35eb7cf EXIT4'),
                (0x035E9FAA,11,'mov rax,[rcx]; mov edx,r15d; ...'),
                (0x035E9FB5,6,'call [rax+0x4c0] IsSimulatingPhysics'),
                (0x035E9FBB,8,'test al,al / jne 0x35eb7cf EXIT5'),
                (0x035EA249,6,'call [rax+0xb68] TickCharacterPose'),
                (0x035EA255,6,'call [rax+0x6b8] HasValidData #2'),
                (0x035EA25B,8,'test al,al / je 0x35eb150 EXIT6'),
                (0x035EB129,3,'xor r8d,r8d  (Iterations=0)'),
                (0x035EB13A,6,'call [rax+0x720] StartNewPhysics'),
                (0x035E64C0,0x25,'HasValidData body'),
                (0x03C9B0A0,0x20,'IsSimulatingPhysics head'),
                (0x03C91C60,0x19,'GetBodyInstance full'),
                (0x01E2F940,0x0C,'IsInstanceSimulatingPhysics head (test [BI+0x10],1)'),
                (0x0350C270,8,'SetBitFunc ACharacter +0x580 mask 0x08'),
                (0x0350C350,11,'SetBitFunc ACharacter +0x580 mask 0x200')]:
    print(f"  {r:#010x} {im.read(r,n).hex():<52s} {lbl}")
print()
print("page_nonzero of exit targets / key fns:")
for r,l in [(0x035E9EC0,'engine PerformMovement'),(0x035EB1A7,'epilogue'),(0x035EB7CF,'bail A'),
            (0x035EB150,'bail B'),(0x03600990,'engine StartNewPhysics'),(0x055C2430,'ULokiCMC::StartNewPhysics'),
            (0x055B8370,'ULokiCMC::PerformMovement'),(0x5A6AC40,'KNOWN-DARK CONTROL')]:
    print(f"   {r:#010x} nz={im.page_nonzero(r):4d}  {l}")
