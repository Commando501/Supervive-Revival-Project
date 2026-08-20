import sys, struct, os
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
IB=img.imagebase; b=img.buf
nm,vaddr,vsize,rawptr,rawsize=[s for s in img.sections if s[0]=='.text'][0]
blob=b[rawptr:rawptr+rawsize]
TGT=0x0F7EB50
sites=[]
for i in range(len(blob)-5):
    if blob[i]==0xE8:
        d=struct.unpack_from("<i",blob,i+1)[0]
        if vaddr+i+5+d==TGT: sites.append(vaddr+i)

# pdata union for containing function
import csv
pd=[]
pf=r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv"
if os.path.exists(pf):
    with open(pf,newline='') as f:
        rd=csv.reader(f)
        hdr=next(rd)
        for row in rd:
            try: pd.append((int(row[0],0), int(row[1],0)))
            except: pass
    pd.sort()
import bisect
starts=[x[0] for x in pd]
def fnof(r):
    i=bisect.bisect_right(starts,r)-1
    if i>=0 and pd[i][0]<=r<pd[i][1]: return pd[i]
    return None

def back_ins(rva, count=5):
    # decode forward from rva-40 and keep the last `count` that end at rva
    for start in range(rva-48, rva):
        out=[]
        ok=False
        for x in md.disasm(b[start:rva], IB+start):
            out.append(x)
            if x.address - IB + x.size == rva: ok=True
        if ok and len(out)>=count:
            return out[-count:]
    return []

print(f"{len(sites)} call sites to 0x{TGT:07X}\n")
for s in sites:
    fn=fnof(s)
    pre=back_ins(s,4)
    post=[]
    for k,x in enumerate(md.disasm(b[s+5:s+5+24], IB+s+5)):
        post.append(x)
        if k>=2: break
    prestr=" | ".join(f"{x.mnemonic} {x.op_str}" for x in pre)
    poststr=" | ".join(f"{x.mnemonic} {x.op_str}" for x in post)
    fs=f"pdata[0x{fn[0]:07X}-0x{fn[1]:07X}]" if fn else "pdata:?"
    print(f"0x{s:07X} {fs}\n    PRE : {prestr}\n    POST: {poststr}")
