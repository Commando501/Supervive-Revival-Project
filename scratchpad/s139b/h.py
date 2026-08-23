import struct, sys
import capstone
PATH=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
DATA=open(PATH,'rb').read()
pe=struct.unpack_from('<I',DATA,0x3c)[0]
nsec=struct.unpack_from('<H',DATA,pe+6)[0]
optoff=pe+24
optsize=struct.unpack_from('<H',DATA,pe+20)[0]
IMAGEBASE=struct.unpack_from('<Q',DATA,optoff+24)[0]
secs=[]
for i in range(nsec):
    o=optoff+optsize+i*40
    name=DATA[o:o+8].rstrip(b'\0').decode()
    vs,va,rs,ra=struct.unpack_from('<IIII',DATA,o+8)
    secs.append((name,va,vs,ra,rs))
def sec_of(rva):
    for n,va,vs,ra,rs in secs:
        if va<=rva<va+max(vs,rs): return n
    return None
def rd(rva,n):
    return DATA[rva:rva+n]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
md.detail=True
def dis(rva,n=200,count=0):
    code=rd(rva,n)
    out=[]
    for ins in md.disasm(code,rva):
        out.append(ins)
        if count and len(out)>=count: break
    return out
def p(rva,n=200,count=0):
    for ins in dis(rva,n,count):
        print("0x%08X  %-24s %s %s"%(ins.address,ins.bytes.hex(),ins.mnemonic,ins.op_str))
def q(rva):
    return struct.unpack_from('<Q',DATA,rva)[0]
def d(rva):
    return struct.unpack_from('<I',DATA,rva)[0]
def va2rva(va):
    return va-IMAGEBASE
def rva2va(r):
    return r+IMAGEBASE
if __name__=='__main__':
    print("IMAGEBASE 0x%X"%IMAGEBASE)
    for s in secs: print(s[0],"va=0x%X vs=0x%X ra=0x%X rs=0x%X"%(s[1],s[2],s[3],s[4]))
