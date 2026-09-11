from advh import *
from cfg import build
# does slot342 clobber xmm6 without restoring?
seen,succ=build(0x055B8250,0x2000)
for a in sorted(x for x in succ if seen[x]):
    i=seen[a]
    r,w=i.regs_access()
    names_w=[md.reg_name(x) for x in w]; names_r=[md.reg_name(x) for x in r]
    if any(n and n.startswith('xmm') for n in names_w+names_r):
        print("  0x%08X %-40s W=%s R=%s"%(a,i.mnemonic+" "+i.op_str,[n for n in names_w if n.startswith('xmm')],[n for n in names_r if n.startswith('xmm')]))
print()
seen2,succ2=build(0x035E9EC0)
for a in (0x035E9F8F,0x035E9F90,0x035E9F91):
    if a in seen2: print("boundary 0x%08X -> %s"%(a,seen2[a].mnemonic+" "+seen2[a].op_str))
# print the instruction whose fallthrough is 0x035E9F97
for a,i in sorted(seen2.items()):
    if i and i.address+i.size==0x035E9F97: print("pred of gate3: 0x%08X %-16s %s"%(a,i.bytes.hex(),i.mnemonic+" "+i.op_str))
# readers of +0x16D0 in loki cmc: identify containing fn start via backward scan for known fn starts
for probe in (0x055AC1C0,0x055ACB32,0x055B88CD):
    for off in range(0,4):
        g=list(md.disasm(DATA[probe-off:probe-off+16],probe-off))
        if g and g[0].address==probe-off and 'xmm' in g[0].op_str:
            print("  probe 0x%08X -> 0x%08X %s"%(probe,g[0].address,g[0].mnemonic+" "+g[0].op_str)); break
