from advh import *
from cfg import build
# slot 342 body
E=0x055B8250
seen,succ=build(E,0x2000)
addrs=sorted(a for a in succ if seen[a])
print("slot342 0x%08X: nodes=%d range 0x%08X..0x%08X  rets=%s"%(E,len(addrs),addrs[0],addrs[-1],["0x%08X"%a for a in addrs if seen[a].mnemonic=='ret']))
print("  first bytes:",DATA[E:E+16].hex(' '))
FOLDS={0x00F7EC20:'ret0-void',0x00F7EB50:'null',0x00F7EB60:'false',0x00B9E1F0:'true',0x00FC6CF0:'0.0f'}
print("  is fold?", E in FOLDS)
# does it touch xmm6/xmm1?
xs=[(a,seen[a].mnemonic,seen[a].op_str) for a in addrs if 'xmm' in seen[a].op_str]
print("  xmm-touching insns:",len(xs))
print("  calls:",["0x%08X->%s"%(a,seen[a].op_str) for a in addrs if seen[a].mnemonic=='call'])
print()
print("=== engine PerformMovement gates 0x035E9F8A..0x035E9FD0")
for i in md.disasm(DATA[0x035E9F8A:0x035E9FD0],0x035E9F8A):
    print("  0x%08X %-16s %s"%(i.address,i.bytes.hex(),i.mnemonic+" "+i.op_str))
print()
print("=== .pdata sanity: first 64 bytes")
print(DATA[0x0A0B7000:0x0A0B7040].hex(' '))
print("nonzero bytes in .pdata:",sum(1 for b in DATA[0x0A0B7000:0x0A0B7000+0x1000] if b))
