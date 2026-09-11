import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img()
def wstr(rva,maxn=400):
    b=im.read(rva,maxn); out=[]
    for i in range(0,len(b)-1,2):
        w=b[i]|(b[i+1]<<8)
        if w==0: break
        out.append(chr(w))
    return ''.join(out)
def astr(rva,maxn=300):
    b=im.read(rva,maxn); out=[]
    for x in b:
        if x==0: break
        if 32<=x<127: out.append(chr(x))
        else: return None
    return ''.join(out)
for r in [0x07fc0548,0x07fc0670,0x0768774c]:
    print(f"{r:#010x} hex {im.read(r,48).hex()}")
    print(f"   W: {wstr(r)!r}")
    print(f"   A: {astr(r)!r}")
    print()
print("=== .data log category candidate 0x09f80598 ===")
b=im.read(0x09f80598,32); print("bytes",b.hex())
print("Verbosity",b[0],"DebugBreak",b[1],"Default",b[2],"CompileTime",b[3],"FName idx",int.from_bytes(b[4:8],'little'),"num",int.from_bytes(b[8:12],'little'))
