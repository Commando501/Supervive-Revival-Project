import sys, struct
from capstone import *
IMG=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
DATA=open(IMG,'rb').read()
# parse PE
pe_off=struct.unpack_from('<I',DATA,0x3c)[0]
assert DATA[pe_off:pe_off+4]==b'PE\0\0'
nsec=struct.unpack_from('<H',DATA,pe_off+6)[0]
optsz=struct.unpack_from('<H',DATA,pe_off+20)[0]
magic=struct.unpack_from('<H',DATA,pe_off+24)[0]
IMAGEBASE=struct.unpack_from('<Q',DATA,pe_off+24+24)[0]
secoff=pe_off+24+optsz
SECS=[]
for i in range(nsec):
    o=secoff+40*i
    name=DATA[o:o+8].rstrip(b'\0').decode()
    vs,va,rs,ra=struct.unpack_from('<IIII',DATA,o+8)
    SECS.append((name,va,vs,ra,rs))
def sec_of(rva):
    for s in SECS:
        if s[1]<=rva<s[1]+max(s[2],s[4]): return s
    return None
def rd(rva,n):
    return DATA[rva:rva+n]   # RVA==file offset per tasking; verify below
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def dis(rva,n=200,end=None):
    out=[]
    code=DATA[rva:rva+(n if end is None else (end-rva))]
    for i in md.disasm(code,rva):
        out.append(i)
        if end and i.address+i.size>=end: break
    return out
if __name__=='__main__':
    print("ImageBase 0x%X"%IMAGEBASE)
    for s in SECS: print("%-8s va=0x%08X vs=0x%08X ra=0x%08X rs=0x%08X"%(s[0],s[1],s[2],s[3],s[4]))
