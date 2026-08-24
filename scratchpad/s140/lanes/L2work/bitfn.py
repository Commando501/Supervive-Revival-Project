import sys,io,struct,re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); BASE=im.imagebase; d=im.data
text=[s for s in im.sections if s['name']=='.text'][0]
st=text['praw']; en=st+text['rawsz']
pats={}
off=0x580
# or dword [rcx+off], imm8   : 83 89 <disp32> imm8 c3
pats['or dword imm8']=bytes([0x83,0x89])+struct.pack('<i',off)
# or dword [rcx+off], imm32  : 81 89 <disp32> imm32 c3
pats['or dword imm32']=bytes([0x81,0x89])+struct.pack('<i',off)
# or byte [rcx+off], imm8    : 80 89 <disp32> imm8 c3
pats['or byte imm8']=bytes([0x80,0x89])+struct.pack('<i',off)
found=[]
for name,p in pats.items():
    i=st
    while True:
        j=d.find(p,i,en)
        if j<0: break
        rva=j-text['praw']+text['va']
        blob=d[j:j+16]
        found.append((name,rva,blob.hex()))
        i=j+1
for n,r,b in found: print(f"  {n:16s} rva {r:#010x}  {b}")
print(f"total {len(found)}")
