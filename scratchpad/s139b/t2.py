from h import *
start=0x055B8370; end=0x055B88DE
insns=list(md.disasm(DATA[start:end],start))
print("n=",len(insns))
X=md.reg_name
def acc(i):
    r,w=i.regs_access()
    return set(X(x) for x in r), set(X(x) for x in w)
for reg in ('xmm6','xmm0','xmm7','rsi','xmm1','xmm11'):
    ws=[];rs=[]
    for i in insns:
        a,b=acc(i)
        if reg in b: ws.append(i)
        if reg in a: rs.append(i)
    print("== %s: writes=%d reads=%d"%(reg,len(ws),len(rs)))
    if reg in ('xmm6','rsi','xmm7'):
        for i in ws: print("   W 0x%08X %s %s"%(i.address,i.mnemonic,i.op_str))
        for i in rs: print("   r 0x%08X %s %s"%(i.address,i.mnemonic,i.op_str))
