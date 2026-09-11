import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
def dis(rva,n,label,stopret=True):
    print(f"== {label} {rva:#010x} page_nz={im.page_nonzero(rva)}")
    for i in CS.disasm(im.read(rva,n),rva):
        print(f"  {i.address:#010x} {i.bytes.hex():<20s} {i.mnemonic} {i.op_str}")
        if stopret and i.mnemonic in ('ret','jmp'): break
    print()
dis(0x01e2f9b7,0x18,'callee1 false-tail')
dis(0x035E64C0,0x60,'HasValidData 0x035E64C0')
dis(0x035afc40,0x40,'callee at 0x35afc40 (GetWorld?)')
dis(0x03536040,0x50,'0x3536040 (IsPlayingRootMotion?)')
dis(0x03536020,0x50,'0x3536020')
dis(0x035e6470,0x50,'0x35e6470 (HasRootMotionSources?)')
