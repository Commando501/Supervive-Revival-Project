import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from grade import grade, extent
from img2 import vslots
L=vslots(0x088F8570,413); C=vslots(0x07FBED58,413)
d=[i for i in range(413) if L[i]!=C[i]]
print("slot disp     CMC_addr    grade_CMC                 LOKI_addr   grade_LOKI            LOKIsize")
for i in d:
    gc,_,_=grade(C[i]); gl,exl,hl=grade(L[i])
    sz = (exl[1]-exl[0]) if exl else -1
    print("%3d 0x%04X  0x%07X %-24s 0x%07X %-22s %5d  %s"%(i,i*8,C[i],gc,L[i],gl,sz,hl[:12].hex()))
