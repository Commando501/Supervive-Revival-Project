import sys, struct
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv")
from img import *
targ = int(sys.argv[1],16)
va = targ + IMAGEBASE
pat = struct.pack('<Q', va)
hits=[]
start=0
while True:
    i = DATA.find(pat, start)
    if i<0: break
    if i%8==0: hits.append(i)
    start=i+1
print(f"{len(hits)} aligned qword occurrences of VA of 0x{targ:08X}")
for h in hits[:40]:
    s=sec_of(h)
    print(f"  0x{h:08X} in {s[0] if s else '?'}")
    if s and s[0]=='.rdata':
        for d in range(-6,7):
            v=u64(h+d*8)-IMAGEBASE
            mark='  <<<' if d==0 else ''
            print(f"      [{d:+d}] 0x{h+d*8:08X} -> 0x{v:08X}{mark}")
