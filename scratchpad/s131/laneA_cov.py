import sys, os, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
paths={
 'merged4':r"dumps\merged4.dump.exe",
 'merged3':r"dumps\merged3.dump.exe",
 'merged2':r"dumps\merged2.dump.exe",
 'tuthero':r"dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
 'rideable-live':r"dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe",
 'droppod-live':r"dumps\s131-droppod-live\SUPERVIVE-Win64-Shipping.dump.exe",
}
KEY=[('bail block 0x55CD7B2',0x55CD7B2),('fold call 0x55CD572',0x55CD572),('fn start 0x55CD510',0x55CD510),
     ('fold body 0x0F7EB50',0x0F7EB50),('IsA<RoundGM> 0x55C7DD0',0x55C7DD0),('RoundGM StaticClass 0x5453580',0x5453580),
     ('GetGameMode impl 0x37D7BF0',0x37D7BF0),('GetLokiGameMode impl 0x5630970',0x5630970)]
for k,p in paths.items():
    img=fkdis.Img(p)
    nm,va,vs,rp,rs=[s for s in img.sections if s[0]=='.text'][0]
    tot=vs//0x1000; live=0
    b=img.buf
    for pg in range(va, va+vs, 0x1000):
        if any(b[pg:pg+0x1000]): live+=1
    line=f"{k:<14} .text pages {live}/{tot} = {100.0*live/tot:5.2f}%   "
    marks=[]
    for lbl,r in KEY:
        pg=r & ~0xFFF
        marks.append(('Y' if any(b[pg:pg+0x1000]) else '.'))
    print(line + " ".join(f"{lbl.split()[0][:6]}:{m}" for (lbl,_),m in zip(KEY,marks)))
print()
print("KEY legend:", [k for k,_ in KEY])
# bytes of the fold in merged4
img=fkdis.Img(paths['merged4'])
print("0x0F7EB50 bytes (merged4):", img.read(0x0F7EB50,8).hex())
print("0x0F7EC20 bytes (merged4):", img.read(0x0F7EC20,8).hex())
