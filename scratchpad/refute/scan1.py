import struct
d=open(r"dumps/merged12.dump.exe",'rb').read()
TEXT_VA=0x1000; TEXT_SZ=0x7649000
lit=open("scratchpad/refute/litpages.bin",'rb').read()
pat=b'\x88\x04\x00\x00'
occ=[]
i=TEXT_VA
end=TEXT_VA+TEXT_SZ
while True:
    j=d.find(pat,i,end)
    if j<0: break
    pg=(j-TEXT_VA)//0x1000
    if lit[pg]: occ.append(j)
    i=j+1
print("disp32 0x488 byte-pattern occurrences on LIT pages:",len(occ))
import json; json.dump(occ,open("scratchpad/refute/occ488.json","w"))
# control: pattern that must exist
print("control KERNEL32 in image:", d.find(b'KERNEL32'))
