import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
def wstr(rva,n=300):
    b=img.read(rva,n); out=[]
    for i in range(0,len(b)-1,2):
        c=struct.unpack_from("<H",b,i)[0]
        if c==0: break
        if c<32 or c>0x2000: return None
        out.append(chr(c))
    return "".join(out)
def astr(rva,n=200):
    b=img.read(rva,n); out=[]
    for c in b:
        if c==0: break
        if c<32 or c>126: return None
        out.append(chr(c))
    return "".join(out)
for r in [int(x,0) for x in sys.argv[1:]]:
    print("0x%08X  W=%r  A=%r" % (r, wstr(r), astr(r)))
