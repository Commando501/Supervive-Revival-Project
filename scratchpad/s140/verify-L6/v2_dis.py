import struct
from capstone import *
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
d=open(P,'rb').read(); IB=0x7FF608F40000
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def dis(rva,n=0x40,label=""):
    print(f"--- {label} {rva:#x} ---")
    print("  raw:", d[rva:rva+n].hex(' '))
    for i in md.disasm(d[rva:rva+n], rva):
        print(f"  {i.address:#010x}  {i.bytes.hex(' '):<28} {i.mnemonic} {i.op_str}")
dis(0x0530ABE0,0x30,"around 0x530ABF0 (start at ABE0)")
print()
dis(0x0530ABF0,0x20,"slot A50 impl")
print()
dis(0x055C2430,0x70,"ULokiCMC::StartNewPhysics")
print()
dis(0x035EB120,0x30,"engine PM SNP call site")
print()
dis(0x035EB550,0x30,"engine PM A50 call site")
print()
dis(0x035D6790,0x30,"engine A50 impl")
