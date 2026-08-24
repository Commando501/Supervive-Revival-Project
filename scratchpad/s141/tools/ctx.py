import sys
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
for a in sys.argv[1:]:
    r = int(a,16)
    b = im.read(r-0x40, 0xC0)
    print(f"--- {r:#x} ---")
    print(repr(b))
