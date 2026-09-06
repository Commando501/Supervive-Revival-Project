import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"); IB=img.imagebase
def wstr(rva,n=400):
    b=img.read(rva,n)
    if b is None: return None
    out=[]
    for i in range(0,len(b)-1,2):
        c=struct.unpack_from("<H",b,i)[0]
        if c==0: break
        if c<32 or c>0x2000: return None
        out.append(chr(c))
    return "".join(out)
def astr(rva,n=300):
    b=img.read(rva,n)
    if b is None: return None
    out=[]
    for c in b:
        if c==0: break
        if c<32 or c>126: return None
        out.append(chr(c))
    return "".join(out)
VERB={0:'NoLogging',1:'Fatal',2:'Error',3:'Warning',4:'Display',5:'Log',6:'Verbose',7:'VeryVerbose'}
for r in [int(x,0) for x in sys.argv[1:]]:
    b=img.read(r,0x28)
    print("REC 0x%08X raw=%s"%(r,b.hex(' ')))
    q=struct.unpack_from("<QQ",b,0)
    for i,v in enumerate(q):
        rv=v-IB if v>IB else v
        print("   +0x%02X = 0x%016X (rva 0x%08X) W=%r A=%r"%(i*8,v,rv,wstr(rv),astr(rv)))
    ln,vb = struct.unpack_from("<II", b, 0x10)
    print("   +0x10 line=%d  +0x14 verbosity=%d (%s)"%(ln,vb,VERB.get(vb&0xF,'?')))
