import json,re,capstone
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
EXEC=[(nm,va,vs,ra,rs) for nm,va,vs,ra,rs,ch in SEC if ch&0x20000000]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
print("--- context of every raw '4d 5a' in exec sections (60) ---")
n=0
for nm,va,vs,ra,rs in EXEC:
    b=D[ra:ra+rs]
    for m in re.finditer(re.escape(b'\x4d\x5a'),b):
        i=m.start(); n+=1
        pre=b[max(0,i-6):i].hex()
        print("  %-9s rva %08x  pre=%s  at=%s"%(nm,va+i,pre,b[i:i+4].hex()))
print("total",n)
# explicit 16-bit compare forms
for lbl,pat in [("cmp ax,5A4D  66 3d 4d 5a",b'\x66\x3d\x4d\x5a'),
                ("cmp/and word imm16 66 81 /x ... 4d5a  (regex)",None)]:
    if pat:
        t=sum(len(re.findall(re.escape(pat),D[ra:ra+rs])) for nm,va,vs,ra,rs in EXEC)
        print(lbl,"->",t)
# 66 81 <modrm> [disp] 4d 5a : allow modrm 0x38-0x3f (cmp) / 0x20-0x27 (and) with 0/1/4 byte disp
import struct
cnt=0
for nm,va,vs,ra,rs in EXEC:
    b=D[ra:ra+rs]
    for m in re.finditer(rb'\x66\x81', b):
        i=m.start()
        if i+3>=len(b): continue
        mrm=b[i+2]; mod=mrm>>6; rm=mrm&7; reg=(mrm>>3)&7
        if reg not in (7,4): continue   # cmp=/7 and=/4
        dl = 0 if mod==0 else (1 if mod==1 else (4 if mod==2 else 0))
        if mod==0 and rm==5: dl=4
        sib = 1 if (mod!=3 and rm==4) else 0
        j=i+3+sib+dl
        if b[j:j+2]==b'\x4d\x5a': cnt+=1
print("66 81 /7 or /4 with imm16 = 0x5A4D :",cnt)
