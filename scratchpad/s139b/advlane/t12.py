import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
FOLDS={0x00F7EC20:'FOLD-void',0x00F7EB50:'FOLD-null',0x00F7EB60:'FOLD-false',0x00B9E1F0:'FOLD-true',0x00FC6CF0:'FOLD-0.0f'}
def scanfn(lo,hi,label):
    print("### %s  %08X..%08X (%d B)"%(label,lo,hi,hi-lo))
    writes=[]; calls=set(); ind=0; disp1090=0; netmode=0
    for i in MD.disasm(D[lo:hi], lo):
        if i.group(CS_GRP_CALL):
            op=i.operands[0]
            if op.type==X86_OP_IMM: calls.add(op.imm)
            else: ind+=1
        # memory writes: first operand is mem
        if i.operands and i.operands[0].type==X86_OP_MEM and i.mnemonic not in ('cmp','test','comiss','comisd','ucomiss','ucomisd','push'):
            m=i.operands[0].mem
            if m.base!=X86_REG_RSP and m.base!=X86_REG_RBP and m.base!=0:
                writes.append((i.address,i.mnemonic,i.op_str,MD.reg_name(m.base),m.disp))
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.disp==0x1090: disp1090+=1
    print("  direct callees (%d):"%len(calls))
    for c in sorted(calls):
        g=FOLDS.get(c,'')
        p=pnz(c)
        pre=D[c:c+8].hex()
        if not g:
            if p==0: g='DARK'
            elif pre.startswith('ff25'): g='FORWARDER'
            else: g='REAL'
        print("     %08X  page_nz=%4d  %-10s  %s"%(c,p,g,pre))
    print("  indirect calls: %d   [+0x1090] operands: %d"%(ind,disp1090))
    print("  non-stack memory WRITES (%d):"%len(writes))
    for a,m,o,b,dsp in writes: print("     %08X  %s %s   (base=%s disp=0x%X)"%(a,m,o,b,dsp))
    print()
scanfn(0x055B89F0,0x055B90F1,"ULokiCMC::PhysFalling")
