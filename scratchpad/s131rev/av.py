# Independent adversarial verifier: own PE loader + capstone, no dependence on s131 tools.
import struct, sys, os
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
ROOT = r"G:\git\Supervive Revival Project"
IMGS = {
 'merged4': os.path.join(ROOT,'dumps','merged4.dump.exe'),
 'merged3': os.path.join(ROOT,'dumps','merged3.dump.exe'),
 'merged2': os.path.join(ROOT,'dumps','merged2.dump.exe'),
 'ride':    os.path.join(ROOT,'dumps','s131-rideable-live','SUPERVIVE-Win64-Shipping.dump.exe'),
 'pod':     os.path.join(ROOT,'dumps','s131-droppod-live','SUPERVIVE-Win64-Shipping.dump.exe'),
 'tuthero': os.path.join(ROOT,'dumps','tutorial-hero','SUPERVIVE-Win64-Shipping.dump.exe'),
 's129':    os.path.join(ROOT,'dumps','s129-poolgate','SUPERVIVE-Win64-Shipping.dump.exe'),
}
_c={}
class Img:
    def __init__(self,key):
        p=IMGS[key]; d=open(p,'rb').read()
        pe=struct.unpack_from('<I',d,0x3C)[0]
        self.base=struct.unpack_from('<Q',d,pe+0x30)[0]
        nsec=struct.unpack_from('<H',d,pe+6)[0]; opt=struct.unpack_from('<H',d,pe+0x14)[0]
        self.secs=[]
        for i in range(nsec):
            o=pe+0x18+opt+i*40
            nm=d[o:o+8].rstrip(b'\x00').decode()
            vs=struct.unpack_from('<I',d,o+8)[0]; va=struct.unpack_from('<I',d,o+12)[0]
            rs=struct.unpack_from('<I',d,o+16)[0]; ro=struct.unpack_from('<I',d,o+20)[0]
            self.secs.append((nm,va,vs,ro,rs))
        self.d=d; self.key=key
    def sec(self,rva):
        for nm,va,vs,ro,rs in self.secs:
            if va<=rva<va+vs: return nm
        return None
    def read(self,rva,n): return self.d[rva:rva+n]   # flat: file offset == RVA
    def zpages(self,rva,n):
        out=[]
        p=rva & ~0xFFF
        while p < rva+n:
            out.append((p, self.d[p:p+0x1000]==b'\x00'*0x1000)); p+=0x1000
        return out
def img(k):
    if k not in _c: _c[k]=Img(k)
    return _c[k]
def dis(key,rva,n=0x80,show=True):
    I=img(key); md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
    for p,z in I.zpages(rva,n):
        if z: print(";; WARN page 0x%08X ALL-ZERO in %s"%(p,key))
    outs=[]
    for ins in md.disasm(I.read(rva,n), I.base+rva):
        r=ins.address-I.base; ann=""
        for op in ins.operands:
            if op.type==2 and (ins.mnemonic=="call" or ins.mnemonic[0]=="j"):
                t=op.imm-I.base; ann="   ; -> RVA 0x%08X [%s]"%(t,I.sec(t))
            if op.type==3 and op.mem.base==41:
                t=(ins.address+ins.size+op.mem.disp)-I.base; ann="   ; -> RVA 0x%08X [%s]"%(t,I.sec(t))
        line="0x%08X  %-24s %s %s%s"%(r,ins.bytes.hex(),ins.mnemonic,ins.op_str,ann)
        outs.append((r,ins,line))
        if show: print(line)
    return outs
if __name__=="__main__":
    a=sys.argv[1:]
    key=a[0]; rva=int(a[1],0); n=int(a[2],0) if len(a)>2 else 0x80
    dis(key,rva,n)
