import sys, json, capstone
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True

h=json.load(open('scratchpad/lanev5/hits2.json'))
stores=[x for x in h if x['dst'] and x['mnem'] not in ('call','jmp','cmp','test') and x['base']!='rsp']

# For each store, disassemble the containing function linearly and look at the
# 12 instructions preceding the store for AND/OR/XOR immediates on the source reg.
def analyse(x):
    b,e = x['fn_b'], x['fn_e']
    if b is None:
        b,e = x['rva']-0x60, x['rva']+0x10
    ins=list(md.disasm(data[b:e], b))
    k=None
    for i,z in enumerate(ins):
        if z.address==x['rva']: k=i; break
    if k is None: return None
    win=ins[max(0,k-14):k+1]
    # source register of the store
    src=None
    if len(ins[k].operands)>1 and ins[k].operands[1].type==X86_OP_REG:
        src=ins[k].reg_name(ins[k].operands[1].reg)
    masks=[]
    for z in win[:-1]:
        if z.mnemonic in ('and','or','xor','bts','btr','shl','movzx','mov','test') :
            if len(z.operands)>1 and z.operands[1].type==X86_OP_IMM and z.operands[0].type==X86_OP_REG:
                masks.append((z.address, z.mnemonic, z.reg_name(z.operands[0].reg), z.operands[1].imm))
    return src, masks, win

print("=== RMW / dataflow classification of all %d non-stack writes to [reg+0x488] ===" % len(stores))
print("Question: can the stored value CLEAR bit 0x20 of the byte at +0x488?\n")
clearers=[]; preservers=[]; unknown=[]
for x in sorted(stores,key=lambda z:z['rva']):
    m=x['mnem']; imm=x['imm']
    if m=='and' and imm is not None and (imm & 0x20)==0:
        clearers.append((x,'AND imm 0x%X clears bit0x20'%(imm & 0xffffffff))); continue
    if m=='and' and imm is not None:
        preservers.append((x,'AND imm keeps bit')); continue
    if m in ('or','xor') and imm is not None:
        (preservers if not (imm&0x20) else clearers).append((x,'%s imm 0x%X'%(m,imm))); continue
    if m=='mov' and imm is not None:
        (preservers if (imm & 0x20) else clearers).append((x,'MOV imm 0x%X -> bit0x20=%d'%(imm&0xffffffff,1 if imm&0x20 else 0))); continue
    r=analyse(x)
    if r is None: unknown.append((x,'no decode')); continue
    src,masks,win=r
    # look for an "isolate one bit" idiom: xor/and imm/xor
    idio=[mm for mm in masks if mm[1]=='and']
    unknown.append((x,(src,idio)))
print("-- writes that provably CLEAR bit 0x20 (immediate form): %d" % len(clearers))
for x,w in clearers: print("   0x%08X fn=%s %-28s %s %s  [%s]"%(x['rva'],('0x%X'%x['fn_b']) if x['fn_b'] else '-',x['bytes'],x['mnem'],x['ops'],w))
print("\n-- writes that provably do NOT clear it (immediate form): %d" % len(preservers))
for x,w in preservers[:40]: print("   0x%08X fn=%s %s %s  [%s]"%(x['rva'],('0x%X'%x['fn_b']) if x['fn_b'] else '-',x['mnem'],x['ops'],w))
print("\n-- register-sourced writes needing dataflow: %d" % len(unknown))
json.dump([x['rva'] for x,_ in unknown], open('scratchpad/lanev5/unknown_writes.json','w'))
