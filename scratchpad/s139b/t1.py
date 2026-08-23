from h import *
start=0x055B8370
insns=[]
addr=start
buf=DATA[start:start+0x1000]
cnt=0
for i in md.disasm(buf,start):
    insns.append(i)
    if i.mnemonic=='ret' or (i.mnemonic in ('jmp',) and i.op_str and not i.op_str.startswith('0x')):
        pass
    cnt+=1
    if cnt>500: break
# find contiguity + rets
prev=start
gaps=[]
for i in insns:
    if i.address!=prev: gaps.append((prev,i.address))
    prev=i.address+i.size
rets=[i.address for i in insns if i.mnemonic=='ret']
print("first ret at 0x%08X"%rets[0] if rets else "no ret")
# count instructions up to and incl first ret
idx=[n for n,i in enumerate(insns) if i.address==rets[0]][0]
sub=insns[:idx+1]
print("instructions to first ret inclusive:",len(sub))
print("end addr 0x%08X"%(sub[-1].address+sub[-1].size))
print("gaps:",gaps)
# all rets in that range
print("rets in range:",["0x%08X"%a for a in rets if a<=sub[-1].address])
# all branches with addr < 0x055B85C1
print("--- branches before 0x055B85C1 ---")
tg=[]
for i in sub:
    if i.address>=0x055B85C1: break
    if i.group(CS_GRP_JUMP) or i.mnemonic.startswith('j'):
        t=i.op_str
        print("0x%08X %-8s %s"%(i.address,i.mnemonic,i.op_str))
        if t.startswith('0x'): tg.append(int(t,16))
print("n branches:",len(tg),"max target 0x%08X"%max(tg),"min 0x%08X"%min(tg))
print("--- any jmp before super? ---")
print([("0x%08X"%i.address,i.mnemonic,i.op_str) for i in sub if i.address<0x055B85C1 and i.mnemonic=='jmp'])
