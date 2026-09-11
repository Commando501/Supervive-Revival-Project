import sys, struct, collections, os
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64)

DUMP = sys.argv[1] if len(sys.argv)>1 else r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
TGT  = int(sys.argv[2],0) if len(sys.argv)>2 else 0x0F7EB50
img = fkdis.Img(DUMP)
IB = img.imagebase
b = img.buf
sec = [s for s in img.sections if s[0]=='.text'][0]
name,vaddr,vsize,rawptr,rawsize = sec
blob = b[rawptr:rawptr+rawsize]

# page decrypted map
def page_live(rva):
    p = rva & ~0xFFF
    return any(b[p:p+0x1000])

sites=[]
n=len(blob)
i=0
while i < n-5:
    if blob[i]==0xE8:
        disp = struct.unpack_from("<i", blob, i+1)[0]
        if vaddr + i + 5 + disp == TGT:
            sites.append(vaddr+i)
    i+=1
print(f"dump={os.path.basename(DUMP)}  target=0x{TGT:07X}")
print(f"UNCAPPED direct E8 call sites in .text (unit: call sites) = {len(sites)}")
live=[s for s in sites if page_live(s)]
print(f"  of which on a DECRYPTED page = {len(live)}   (all E8 bytes come from decrypted pages by construction)")

# classify shape: bytes after the call
shapes=collections.Counter()
detail=[]
for s in sites:
    after = b[s+5:s+5+16]
    before = b[max(0,s-24):s]
    # decode the 3 instructions after
    ins=[]
    for k,x in enumerate(md.disasm(after, IB+s+5)):
        ins.append(f"{x.mnemonic} {x.op_str}")
        if k>=2: break
    key = " ; ".join(ins[:2])
    shapes[key]+=1
    detail.append((s, key, ins))
print()
print("=== shape histogram of the 2 instructions FOLLOWING each call (unit: call sites) ===")
for k,v in shapes.most_common(40):
    print(f"  {v:5d}  {k}")
