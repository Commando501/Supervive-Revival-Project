import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg
I = VImg('dumps/merged14.dump.exe')
print("ImageBase", hex(I.ImageBase), "flat", I.flat(), "nsec", I.nsec, "SizeOfImage", hex(I.SizeOfImage))
for s in I.sections:
    print("  %-10s va=%08x vsz=%08x praw=%08x rawsz=%08x ch=%08x" % (s['name'],s['vaddr'],s['vsize'],s['praw'],s['rawsz'],s['ch']))
print()
print("[C1] DARK ctrl 0x5A6AC40 page_nonzero =", I.page_nonzero(0x5A6AC40), "/4096")
folds = {0x0F7EC20:'c20000',0x0F7EB50:'33c0c3',0x0F7EB60:'32c0c3',0x0B9E1F0:'b001c3',0x0FC6CF0:'0f57c0c3'}
for rva,exp in folds.items():
    got = I.read(rva, len(exp)//2).hex()
    print("[C2] fold %08X expect %-8s got %-8s %s" % (rva,exp,got,"PASS" if got==exp else "*** FAIL ***"))
for name,rva in [("ENGINE PhysFalling",0x035EC850),("zero block",0x035ED973),("quatA",0x035F4620),
                 ("quatB",0x035F4770),("LokiPhysFalling",0x055B89F0),("CalcVelocity",0x035D5D20),
                 ("ENGINE StartNewPhysics",0x03600990),("ENGINE PerformMovement",0x035E9EC0)]:
    print("[C3] LIT %-24s %08X %4d/4096" % (name,rva,I.page_nonzero(rva)))
s=I.sec_of(0x077F5180); print("[C4] .rdata 0x077F5180 in section", s['name'], "page", I.page_nonzero(0x077F5180))
# .pdata state
pd = [x for x in I.sections if x['name']=='.pdata']
if pd: print("[C5] .pdata first page nonzero:", I.page_nonzero(pd[0]['vaddr']), " datadir[3]=", [hex(x) for x in I.datadirs[3]])
