# Offline disassembler over dumps/merged.dump.exe (file-offset==RVA, ImageBase=0x7FF6AF000000).
# Resolves rip-relative operands, call targets, and FName indices.
import capstone, sys, struct
DUMP=r"dumps/merged.dump.exe"
IMAGEBASE=0x7FF6AF000000
NAMEPOOL_RVA=0x9D81450
f=open(DUMP,"rb"); DATA=f.read()
def rd(rva,n):
    if rva<0 or rva+n>len(DATA): return b""
    return DATA[rva:rva+n]
def u32(b,o=0): return int.from_bytes(b[o:o+4],"little")
def u64(b,o=0): return int.from_bytes(b[o:o+8],"little")
def looksrva(v): return 0<=v<len(DATA)
_nc={}
def fname(idx):
    idx&=0xFFFFFFFF
    if idx==0: return "None"
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rd(NAMEPOOL_RVA+blk*8,8)
    r=None
    if bp:
        blockptr=u64(bp)  # this is a VIRTUAL addr; convert to rva
        if blockptr>IMAGEBASE and blockptr-IMAGEBASE<len(DATA):
            brva=blockptr-IMAGEBASE
            hd=rd(brva+off,2)
            if hd:
                h=u32(hd)&0xFFFF; ln=h>>6; wide=h&1
                if 0<ln<200:
                    s=rd(brva+off+2,ln*(2 if wide else 1))
                    if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r
def peekstr(rva,maxb=64):
    b=rd(rva,maxb)
    if not b: return None
    # try wide
    w="".join(chr(b[i]|(b[i+1]<<8)) for i in range(0,min(len(b)-1,maxb),2) if b[i] or b[i+1])
    # try ansi
    a=""
    for x in b:
        if x==0: break
        if 32<=x<127: a+=chr(x)
        else: a=""; break
    if len(a)>=3: return f'ansi="{a}"'
    ww=""
    for i in range(0,len(b)-1,2):
        c=b[i]|(b[i+1]<<8)
        if c==0: break
        if 32<=c<127: ww+=chr(c)
        else: ww=""; break
    if len(ww)>=3: return f'wide="{ww}"'
    return None
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
md.detail=True
def disasm(rva,length):
    code=rd(rva,length)
    for ins in md.disasm(code,IMAGEBASE+rva):
        addr=ins.address; rvo=addr-IMAGEBASE
        line=f"  {addr:012X} +{rvo:07X}  {ins.mnemonic:6s} {ins.op_str}"
        ann=""
        # rip-relative
        for op in ins.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                tgt=ins.address+ins.size+op.mem.disp
                trva=tgt-IMAGEBASE
                s=peekstr(trva)
                fn=None
                # if target holds an FName index (u32) or a dword, try resolve
                dv=rd(trva,4)
                ann+=f"  ; ->0x{trva:X}"
                if s: ann+=f" {s}"
                # try FName at target
                if dv:
                    idx=u32(dv); nm=fname(idx)
                    if nm and nm!="None" and len(nm)>2: ann+=f" fname[{idx}]={nm}"
            if op.type==capstone.x86.X86_OP_IMM:
                iv=op.imm&0xFFFFFFFF
                if 0x1000<iv<0x2000000:  # plausible FName index range
                    nm=fname(iv)
                    if nm and nm not in("None",) and len(nm)>2 and all(32<=ord(c)<127 for c in nm):
                        ann+=f"  ; imm fname[{iv}]={nm}"
        if ins.group(capstone.CS_GRP_CALL) or ins.group(capstone.CS_GRP_JUMP):
            for op in ins.operands:
                if op.type==capstone.x86.X86_OP_IMM:
                    t=op.imm-IMAGEBASE
                    ann+=f"  ; ={ins.mnemonic}->+0x{t:X}"
        print(line+ann)
if __name__=="__main__":
    rva=int(sys.argv[1],16); ln=int(sys.argv[2]) if len(sys.argv)>2 else 256
    disasm(rva,ln)
