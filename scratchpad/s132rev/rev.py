#!/usr/bin/env python3
"""S132 adversarial re-derivation tool. Independent of scratchpad/s132/*.
   Own PE parser + capstone. Prints RVAs for branch/rip targets (machine-computed)."""
import sys, os, struct
import capstone

BASE = r"G:\git\Supervive Revival Project\dumps"
DUMPS = {
 "merged4": os.path.join(BASE,"merged4.dump.exe"),
 "merged3": os.path.join(BASE,"merged3.dump.exe"),
 "merged2": os.path.join(BASE,"merged2.dump.exe"),
 "merged":  os.path.join(BASE,"merged.dump.exe"),
 "tuthero": os.path.join(BASE,"tutorial-hero","SUPERVIVE-Win64-Shipping.dump.exe"),
 "s129":    os.path.join(BASE,"s129-poolgate","SUPERVIVE-Win64-Shipping.dump.exe"),
 "rideable":os.path.join(BASE,"s131-rideable-live","SUPERVIVE-Win64-Shipping.dump.exe"),
 "droppod": os.path.join(BASE,"s131-droppod-live","SUPERVIVE-Win64-Shipping.dump.exe"),
}

class Img:
    def __init__(self, path):
        self.path=path
        self.buf=open(path,'rb').read()
        b=self.buf
        e=struct.unpack_from("<I",b,0x3C)[0]
        assert b[e:e+4]==b"PE\0\0"
        coff=e+4
        nsec=struct.unpack_from("<H",b,coff+2)[0]
        szopt=struct.unpack_from("<H",b,coff+16)[0]
        opt=coff+20
        self.imagebase=struct.unpack_from("<Q",b,opt+24)[0]
        self.sections=[]
        sh=opt+szopt
        for i in range(nsec):
            o=sh+i*40
            name=b[o:o+8].rstrip(b"\0").decode("latin1")
            vsize,vaddr,rawsize,rawptr=struct.unpack_from("<IIII",b,o+8)
            self.sections.append((name,vaddr,vsize,rawptr,rawsize))
    def sec(self,rva):
        for s in self.sections:
            if s[1]<=rva<s[1]+max(s[2],s[4]): return s
        return None
    def off(self,rva):
        s=self.sec(rva)
        return None if s is None else s[3]+(rva-s[1])
    def read(self,rva,n):
        o=self.off(rva)
        if o is None: return None
        return self.buf[o:o+n]
    def secrange(self,name):
        for s in self.sections:
            if s[0]==name: return s
        return None

def load(d="merged4"): return Img(DUMPS[d])

md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail=True

def dis(img, rva, n=64, show_bytes=True):
    data=img.read(rva,n)
    va=img.imagebase+rva
    out=[]
    for ins in md.disasm(data, va):
        r=ins.address-img.imagebase
        op=ins.op_str
        # annotate rip-rel and branch targets with RVA
        note=""
        for g in ins.groups:
            pass
        if capstone.x86.X86_GRP_JUMP in ins.groups or capstone.x86.X86_GRP_CALL in ins.groups:
            for o in ins.operands:
                if o.type==capstone.x86.X86_OP_IMM:
                    note=" ; ->rva 0x%08X"%(o.imm-img.imagebase)
        for o in ins.operands:
            if o.type==capstone.x86.X86_OP_MEM and o.mem.base==capstone.x86.X86_REG_RIP:
                tgt=ins.address+ins.size+o.mem.disp
                note+=" ; [rip]->rva 0x%08X"%(tgt-img.imagebase)
        bs=ins.bytes.hex() if show_bytes else ""
        out.append("%08X  %-24s %-8s %s%s"%(r,bs,ins.mnemonic,op,note))
    return "\n".join(out)

if __name__=="__main__":
    cmd=sys.argv[1]
    dumpname="merged4"
    args=[]
    i=2
    while i<len(sys.argv):
        if sys.argv[i]=="--dump": dumpname=sys.argv[i+1]; i+=2
        else: args.append(sys.argv[i]); i+=1
    img=load(dumpname)
    if cmd=="d":
        rva=int(args[0],0); n=int(args[1],0) if len(args)>1 else 96
        print("# %s base=0x%X"%(dumpname,img.imagebase))
        print(dis(img,rva,n))
    elif cmd=="x":
        rva=int(args[0],0); n=int(args[1],0) if len(args)>1 else 64
        d=img.read(rva,n)
        for k in range(0,len(d),16):
            print("%08X  %s  %s"%(rva+k," ".join("%02x"%c for c in d[k:k+16]),
                  "".join(chr(c) if 32<=c<127 else "." for c in d[k:k+16])))
    elif cmd=="secs":
        for s in img.sections: print("%-10s vaddr=0x%08X vsize=0x%X rawptr=0x%X rawsize=0x%X"%s)
