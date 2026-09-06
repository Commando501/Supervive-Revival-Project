import sys, capstone, struct
d=open(r"dumps/merged13.dump.exe",'rb').read()
BASE=0x7FF608F40000
FOLDS={0x00F7EC20:'FOLD ret0/void',0x00F7EB50:'FOLD null/0',0x00F7EB60:'FOLD false',
       0x00B9E1F0:'FOLD true',0x00FC6CF0:'FOLD 0.0f'}
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def grade(rva):
    if rva in FOLDS: return FOLDS[rva]
    p=rva&~0xFFF
    nz=sum(1 for b in d[p:p+0x1000] if b)
    if nz==0: return 'DARK(page 0/4096)'
    # sixth shape: sub rsp,0x28; call X; xor eax,eax; ret
    b=d[rva:rva+0x20]
    if b[:4]==b'\x48\x83\xec\x28' and b[4]==0xe8 and b[9:12]==b'\x33\xc0\x48':
        return 'STUB6? '+' '.join('%02x'%x for x in b[:16])
    return 'REAL(page %d/4096) '%nz + ' '.join('%02x'%x for x in b[:8])
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
seen={}
for ins in md.disasm(d[lo:hi], lo):
    if ins.mnemonic=='call':
        op=ins.op_str
        if op.startswith('0x'):
            t=int(op,16); seen.setdefault(t,[]).append(ins.address)
        else:
            print("  INDIRECT %08X call %s" % (ins.address, op))
print()
for t in sorted(seen):
    print("  %08X  <- sites %s   %s" % (t, ','.join('%08X'%a for a in seen[t]), grade(t)))
