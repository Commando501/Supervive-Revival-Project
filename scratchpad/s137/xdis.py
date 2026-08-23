import sys, struct, capstone
P='dumps/merged12.dump.exe'
IB=0x7ff6af000000
d=open(P,'rb').read()
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail=False
def dis(rva, n=0x100, stop_at_ret=False):
    code=d[rva:rva+n]
    out=[]
    for ins in md.disasm(code, rva):
        s=f"0x{ins.address:08X}  {ins.bytes.hex():<20s} {ins.mnemonic} {ins.op_str}"
        # annotate rip-relative target
        if 'rip +' in ins.op_str or 'rip -' in ins.op_str:
            pass
        out.append(s)
        if stop_at_ret and ins.mnemonic in ('ret','jmp') and ins.address>rva:
            break
    return out
if __name__=='__main__':
    rva=int(sys.argv[1],0); n=int(sys.argv[2],0) if len(sys.argv)>2 else 0x100
    print('\n'.join(dis(rva,n)))
