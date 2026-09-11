import sys,struct; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
print("=== L2's claimed ctor init block 0x035CF860..0x035CF8C5 (linear read, then verified in CFG) ===")
md_ins,succ,und,ind = cfg(I,0x035CF840)
print("cfg(0x035CF840): insns=%d und=%d ind=%d ret(s)=%s" % (len(md_ins),len(und),len(ind),[hex(a) for a in md_ins if md_ins[a].id in RETS][:4]))
for a in sorted(md_ins):
    if 0x035CF860<=a<=0x035CF8C5:
        i=md_ins[a]
        t=''
        for o in i.operands:
            if o.type==X86_OP_MEM and i.reg_name(o.mem.base)=='rip':
                t=' -> rip target 0x%08X' % (i.address+i.size+o.mem.disp)
        print("   %08x %-22s %-8s %-40s%s" % (a,i.bytes.hex(),i.mnemonic,i.op_str,t))
print()
for rva in (0x099C88A0,0x099C88B0,0x09A75290,0x09A752A0):
    s=I.sec_of(rva); b=I.read(rva,16)
    d=struct.unpack('<2d',b)
    print("  %08X  sec=%-8s bytes=%s  as 2 doubles = (%g, %g)" % (rva,s['name'],b.hex(),d[0],d[1]))
