import sys, re
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
b = im.read(lo, hi-lo)
for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_]{3,63}', b):
    print(f"{lo+m.start():#010x} {m.group().decode()}")
