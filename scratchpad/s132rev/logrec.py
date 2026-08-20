import sys, os, struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from rev import load
img=load(sys.argv[2] if len(sys.argv)>2 else "merged4")
def wstr(rva,maxn=400):
    d=img.read(rva,maxn*2)
    out=[]
    for i in range(0,len(d),2):
        c=d[i]|(d[i+1]<<8)
        if c==0: break
        out.append(chr(c))
    return "".join(out)
def astr(rva,maxn=400):
    d=img.read(rva,maxn); 
    return d.split(b'\0')[0].decode('latin1',errors='replace')
rec=int(sys.argv[1],0)
b=img.read(rec,0x20)
fmt,fil=struct.unpack_from("<QQ",b,0)
line,verb=struct.unpack_from("<iI",b,0x10)
p5=struct.unpack_from("<Q",b,0x18)[0]
print("rec 0x%08X  fmt_rva=0x%08X file_rva=0x%08X line=%d verb=%d p5_rva=0x%08X"%(
  rec,fmt-img.imagebase,fil-img.imagebase,line,verb,p5-img.imagebase))
print("  FMT : %r"%wstr(fmt-img.imagebase))
print("  FILE: %r"%astr(fil-img.imagebase))
