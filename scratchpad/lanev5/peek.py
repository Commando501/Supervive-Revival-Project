import sys, capstone
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr

data = load()
IB, secs = pehdr(data)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = False

def pagestat(rva):
    p = rva & ~0xFFF
    chunk = data[p:p+0x1000]
    nz = sum(1 for b in chunk if b)
    return p, nz

def hexdump(rva, n=32):
    b = data[rva:rva+n]
    return ' '.join('%02x'%x for x in b)

def disasm(start, n=24, stop=None):
    out=[]
    for ins in md.disasm(data[start:start+400], start):
        out.append("0x%08X  %-24s %s %s" % (ins.address, ' '.join('%02x'%x for x in ins.bytes), ins.mnemonic, ins.op_str))
        if len(out)>=n: break
    return out

for rva in (0x45D19AD, 0x554B5A9, 0x45D6D1E, 0x45CFA10, 0x45CFA20):
    p,nz = pagestat(rva)
    print("=== RVA 0x%X  page 0x%X nonzero=%d/4096" % (rva, p, nz))
    print("  bytes@rva: ", hexdump(rva, 24))
