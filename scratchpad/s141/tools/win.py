import sys
sys.path.insert(0,'.')
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
lo=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 60
b=im.read(lo, n*8)
for i in CS.disasm(b, lo):
    print(f"{i.address:#010x}  {i.bytes.hex():<18s} {i.mnemonic} {i.op_str}")
