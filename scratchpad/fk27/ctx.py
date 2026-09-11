# fk27: hexdump + best-effort ASCII/UTF16 rendering around an RVA in a dump image.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load

def render(b):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)

if __name__ == "__main__":
    key = os.environ.get("FK27_IMG", "merged2")
    im = load(key)
    rva = int(sys.argv[1], 16)
    n = int(sys.argv[2],0) if len(sys.argv) > 2 else 0x80
    back = int(sys.argv[3],0) if len(sys.argv) > 3 else 0x20
    start = rva - back
    b = im.rd(start, n + back)
    for i in range(0, len(b), 16):
        chunk = b[i:i+16]
        print(f"  +0x{start+i:07X}  {chunk.hex(' '):<48s}  {render(chunk)}")
