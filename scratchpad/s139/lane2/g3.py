import sys, struct; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA, IMAGEBASE
target=int(sys.argv[1],16)
val=struct.pack('<Q', target+IMAGEBASE)
RD_LO,RD_HI=0x764a000,0x764a000+0x237d000
i=RD_LO; hits=[]
while True:
    j=DATA.find(val,i,RD_HI)
    if j<0: break
    if j%8==0: hits.append(j)
    i=j+1
print("rdata qword hits for 0x%X:"%target,[hex(h) for h in hits])
