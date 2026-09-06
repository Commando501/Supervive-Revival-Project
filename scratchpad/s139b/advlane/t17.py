import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
def scan_disp(lo,hi,disps):
    hits={d:[] for d in disps}
    for i in MD.disasm(D[lo:hi], lo):
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.disp in disps and op.mem.base!=X86_REG_RSP and op.mem.base!=X86_REG_RBP:
                hits[op.mem.disp].append((i.address,i.mnemonic,i.op_str))
    return hits
targets={'ULokiCMC::PhysFalling':(0x055B89F0,0x055B90F1),
         'tail 0x055B9100':(0x055B9100,0x055B9234),
         'engine PhysFalling':(0x035EC850,0x035EE593),
         'Loki GetGravityZ':(0x055AB8C0,0x055AB96A),
         'Loki NewFallVelocity':(0x055B6AD0,0x055B6B3C)}
# controls the lane named
ctrl={'CTRL 0x055AC7A0 fn':(0x055AC7A0,0x055AC8A0),'CTRL 0x055B7E00 fn':(0x055B7E00,0x055B7F80)}
for name,(a,b) in list(targets.items())+list(ctrl.items()):
    h=scan_disp(a,b,{0x1090,0x160})
    print("%-24s  [+0x1090]=%d  [+0x160]=%d" % (name,len(h[0x1090]),len(h[0x160])))
    for d in (0x1090,0x160):
        for x in h[d]: print("      +0x%X  %08X %s %s"%(d,)+ () if False else ("      +0x%X  %08X %s %s"%(d,x[0],x[1],x[2])))
