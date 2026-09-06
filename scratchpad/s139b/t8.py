from h import *
from capstone.x86 import *
BASE=0x0A036130
# walk the whole ctor function 0x055D5EF0 until ret
insns=list(md.disasm(DATA[0x055D5EF0:0x055D5EF0+0x4000],0x055D5EF0))
end=None
writes={}   # target -> (addr, size, imm)
idxbyte={}
for i in insns:
    if i.mnemonic=='ret' and i.address>0x055D5F30:
        end=i.address; break
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            tgt=i.address+i.size+op.mem.disp
            if BASE<=tgt<BASE+151*16 and i.mnemonic=='mov' and len(i.operands)==2 and i.operands[1].type==X86_OP_IMM:
                writes[tgt]=(i.address,op.size,i.operands[1].imm)
print("ctor ret at 0x%08X, span %d bytes"%(end,end-0x055D5EF0))
print("immediate stores into table:",len(writes))
# reconstruct default per entry from word/byte stores at +0xC/+0xD
import collections
defaults={}
idx={}
for tgt,(a,sz,imm) in sorted(writes.items()):
    n=(tgt-BASE)//16; off=(tgt-BASE)%16
    if off==0xC and sz==2: defaults[n]=(imm>>8)&0xFF
    elif off==0xD and sz==1: defaults[n]=imm&0xFF
    elif off==0x0: idx[n]=imm
print("entries with a +0xC/+0xD immediate:",len(defaults))
print("entries with a +0x0 index write:",len(idx),"; mismatched index writes:",[ (n,v) for n,v in idx.items() if v!=n ])
# compare ctor-derived defaults vs the .data bytes in merged13
mis=[]
for n,v in sorted(defaults.items()):
    live=DATA[BASE+16*n+0xD]
    if live!=v: mis.append((n,v,live))
print("ctor-vs-.data mismatches:",len(mis),mis[:20])
print("ctor default for 120 =",defaults.get(120)," live .data byte =",DATA[BASE+120*16+0xD])
print("neighbours ctor:",{k:defaults.get(k) for k in (116,117,118,119,120,121,122,123)})
print("neighbours live:",{k:DATA[BASE+16*k+0xD] for k in (116,117,118,119,120,121,122,123)})
print("count TRUE/FALSE over 0..148 (live):",sum(1 for n in range(149) if DATA[BASE+16*n+0xD]), sum(1 for n in range(149) if not DATA[BASE+16*n+0xD]))
print("live index bytes 0..148 correct:",sum(1 for n in range(149) if DATA[BASE+16*n]==n))
print("entry120 raw:",DATA[BASE+120*16:BASE+121*16].hex(' '))
