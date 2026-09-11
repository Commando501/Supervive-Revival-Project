# INDEPENDENT second instrument on L3 section 4: who else writes the ladder offsets,
# over the ULokiCMC vtable surface.  My own CFG + my own this-tracker.
import struct, time, sys
import capstone
from capstone import CS_AC_WRITE
from capstone.x86 import *
from vimg import VImg, IMAGEBASE
from vcfg import VCFG, CS
from vthis import analyse, GPRS, parent

im=VImg(); buf=im.buf
VT=0x088F8570; NSLOT=413
WATCH={0x703,0x390,0x3DC,0x340,0x350,0x360,0x370,0x378,0x388,0x2E9,0x554,0x598,0x5A8,0x16C8}
WRITE_MNEMS_O0 = set("""mov movabs movaps movups movsd movss movdqa movdqu movd movq movnti movntps movntdq
 movlps movhps movlpd movhpd add sub and or xor adc sbb inc dec neg not shl shr sar rol ror
 cmpxchg xchg xadd bts btr btc""".split())
READ_ONLY_O0=set("cmp test ucomiss ucomisd comiss comisd push jmp call bt".split())

targets=[]
for i in range(NSLOT):
    va,=struct.unpack_from('<Q',buf,VT+8*i)
    targets.append((i, va-IMAGEBASE))

found={o:[] for o in WATCH}
dark=0; analysed=0; failed=0
t0=time.time()
for i,rva in targets:
    if not (0x1000 <= rva < 0x0764A000):
        failed+=1; continue
    if im.page_nonzero(rva)==0:
        dark+=1; continue
    try:
        g=VCFG(im,rva,limit=40000)
    except Exception as e:
        failed+=1; continue
    if g.decode_failures and len(g.insns)<5:
        dark+=1; continue
    entry={r:None for r in GPRS}; entry['rcx']=('this',0); entry['rsp']=('frame',0)
    try:
        IN,OUT=analyse(g,entry)
    except Exception:
        failed+=1; continue
    analysed+=1
    for a,ins in g.insns.items():
        ops=ins.operands
        if not ops or ops[0].type!=X86_OP_MEM: continue
        if ins.mnemonic in READ_ONLY_O0 or ins.mnemonic not in WRITE_MNEMS_O0: continue
        mem=ops[0].mem
        if mem.base==0 or mem.index!=0: continue
        bn=parent(CS.reg_name(mem.base)); v=(IN.get(a) or {}).get(bn)
        if v is None or v[0]!='this': continue
        off=v[1]+mem.disp
        if off in WATCH:
            found[off].append((i,rva,a,ins.mnemonic,ins.op_str))
print("slots=%d analysed=%d dark=%d failed=%d  elapsed=%.1fs" % (NSLOT,analysed,dark,failed,time.time()-t0))
for o in sorted(WATCH):
    lst=found[o]
    print("\n+0x%X : %d writer site(s)" % (o,len(lst)))
    seen=set()
    for i,rva,a,mn,ops_ in lst:
        key=(i,a)
        if key in seen: continue
        seen.add(key)
        print("   vslot %-3d (disp 0x%03X) fn 0x%08X  @0x%08X  %s %s" % (i,8*i,rva,a,mn,ops_))
