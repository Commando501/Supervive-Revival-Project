import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); BASE=im.imagebase
def wstr(rva,maxn=800):
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
def rec(r,label):
    b=im.read(r,0x28)
    print(f"=== {label} record {r:#010x} : {b.hex()}")
    for off in (0,8,0x18,0x20):
        v=struct.unpack_from('<Q',b,off)[0]
        if BASE<=v<BASE+im.sizeofimage:
            rv=v-BASE; s=im.sec_of(rv)
            print(f"   +{off:#04x} VA {v:#x} -> RVA {rv:#010x} [{s['name'] if s else '?'}]  W={wstr(rv)[:180]!r}  A={astr(rv)!r}")
        else:
            print(f"   +{off:#04x} raw {v:#x}")
    print(f"   +0x10 line={struct.unpack_from('<I',b,0x10)[0]}  +0x14 verbosity={struct.unpack_from('<I',b,0x14)[0]}")
rec(0x07fc0548,"PerformMovement-log")
# the StartNewPhysics one: find its record. literal at 0x07fc0670; record usually just before
for cand in (0x07fc0630,0x07fc0638,0x07fc0640,0x07fc0648,0x07fc0650,0x07fc0658,0x07fc0660,0x07fc0668):
    b=im.read(cand,0x28)
    v=struct.unpack_from('<Q',b,0)[0]
    if BASE<=v<BASE+im.sizeofimage and (v-BASE)==0x07fc0670:
        rec(cand,"StartNewPhysics-log"); break
else:
    print("no record found pointing at 0x07fc0670 in scanned window")
