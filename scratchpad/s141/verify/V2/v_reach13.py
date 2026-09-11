import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,und,ind=cfg(I,0x035EC850)
R13={'r13','r13d','r13w','r13b'}
def defs_r13(a):
    i=ins[a]
    return any(i.reg_name(r) in R13 for r in i.regs_access()[1])
DEF=[a for a in ins if defs_r13(a)]
# forward dataflow: at each node, set of reaching r13-def sites
IN={a:frozenset() for a in ins}
entry=0x035EC850
work=[entry]; IN[entry]=frozenset(['ENTRY'])
changed=True
import collections
while changed:
    changed=False
    for a in sorted(ins):
        out = frozenset([a]) if a in DEF else IN[a]
        for s in succ.get(a,()):
            if s in IN and not out <= IN[s]:
                IN[s]=IN[s]|out; changed=True
print("r13 def sites:", [hex(a) for a in DEF])
ZERO={0x035EC92A,0x035ED0AF}
for site in (0x35ecbd1,0x35ecbde,0x35ecfe2,0x35ed5ce):
    if ins[site].op_str.endswith('r13'):
        rd=IN[site]
        nz = [d for d in rd if d!='ENTRY' and d not in ZERO]
        z  = [d for d in rd if d in ZERO]
        print("\n%08x  %s %s" % (site, ins[site].mnemonic, ins[site].op_str))
        print("   reaching r13 defs: zeroing=%s  non-zeroing=%s  ENTRY=%s" %
              ([hex(x) for x in z], [hex(x) for x in nz], 'ENTRY' in rd))
        print("   => r13 == 0 at this point:", (len(nz)==0 and 'ENTRY' not in rd))
print()
print("=== rsi+0x10 and rdi+0xf8 are the SAME address? ===")
print("   rsi = rdi+0xe8 (lea 0x035EC9AC). rsi+0x10 = rdi+0xf8 :", 0xe8+0x10==0xf8)
