import sys, capstone
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
data = load(); IB, secs = pehdr(data)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=False
start=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 20
cnt=0
for ins in md.disasm(data[start:start+600], start):
    print("0x%08X  %-30s %s %s" % (ins.address, ' '.join('%02x'%x for x in ins.bytes), ins.mnemonic, ins.op_str))
    cnt+=1
    if cnt>=n: break
