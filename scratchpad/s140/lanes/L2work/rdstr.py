import sys
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img()
def show(rva,n=0x60):
    b=im.read(rva,n)
    # ascii
    a=''.join(chr(x) if 32<=x<127 else '.' for x in b)
    # utf16
    try:
        w=b.decode('utf-16-le','replace')
        w=''.join(ch if ch.isprintable() else '.' for ch in w)
    except Exception: w=''
    print(f"{rva:#010x} raw {b[:32].hex()}")
    print(f"   ascii : {a}")
    print(f"   utf16 : {w}")
for r in [0x076b8d58,0x076b8d64,0x076b8d70,0x076b8d80,0x076b8d90,0x076a51a8,0x07697d68,
          0x076b8e28,0x076b8e34,0x076b8e40,0x076b8e50,0x07fc0548,0x0768774c]:
    show(r); print()
