import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
from capstone import x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data
sec=[s for s in im.sections if s['name']=='.text'][0]
base=sec['va']; size=max(sec['vsz'],sec['rawsz']); data=d[sec['praw']:sec['praw']+size]
PAT=bytes([0xb0,0x12,0x00,0x00]); hits=[];i=data.find(PAT)
while i!=-1: hits.append(base+i); i=data.find(PAT,i+1)
band=[h for h in hits if 0x35C0000 <= h < 0x3660000]
print("hits in engine CMC band 0x35C0000-0x3660000:", [hex(x) for x in band], "count", len(band))

# dark page census
npages = size//0x1000
dark=0
for p in range(npages):
    off=sec['praw']+p*0x1000
    if not any(data[p*0x1000:(p+1)*0x1000]): dark+=1
print(f".text pages: {npages}, dark(all-zero): {dark}  ({100*dark/npages:.2f}%)")
lo,hi=0x55A0000,0x55C6000
bd=[]
for a in range(lo,hi,0x1000):
    if im.page_nonzero(a)==0: bd.append(a)
print(f"Loki CMC band {lo:#x}-{hi:#x}: {(hi-lo)//0x1000} pages, dark: {[hex(x) for x in bd]}")
print("dark control 0x5A6AC40 page_nonzero:", im.page_nonzero(0x5A6AC40))
for r,l in [(0x055B8370,'A'),(0x055C2430,'B'),(0x055A7440,'C'),(0x055B7BF0,'D'),(0x055BDCB0,'E'),(0x055A56B0,'R1'),(0x055C0970,'R2'),(0x035DB4A0,"C super"),(0x035F1DF0,"E super"),(0x035FA610,"R2 super"),(0x035E9240,"D engine base")]:
    print(f"  page_nonzero({l} {r:#x}) = {im.page_nonzero(r)}")

print()
print("=== engine ControlledCharacterMove Role gate (CFG-anchored) ===")
c=CFG(im,0x035DCD10)
for n in sorted(c.insns):
    if 0x035DCD60 <= n <= 0x035DCDE0:
        print("  ", c.txt(n))
