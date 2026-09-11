import struct
from capstone import *
from capstone.x86 import *
IMG=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
DATA=open(IMG,'rb').read()
IMAGEBASE=struct.unpack_from('<Q',DATA,struct.unpack_from('<I',DATA,0x3c)[0]+24+24)[0]
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
