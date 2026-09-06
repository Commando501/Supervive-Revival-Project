import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import vslots, IMAGEBASE
L=vslots(0x088F8570,413); C=vslots(0x07FBED58,413)
P=vslots(0x07FE2A10,204); N=vslots(0x07FDB188,197); M=vslots(0x07FD7568,184)
print("IMAGEBASE 0x%X"%IMAGEBASE)
print("POSCTRL slot188 disp0x5E0: CMC=%s LOKI=%s  (expect 0x35F41D0 both)"%(hex(C[188]),hex(L[188])))
d=[i for i in range(413) if L[i]!=C[i]]
print("LOKI OVERRIDES vs UCharacterMovementComponent: %d of 413"%len(d))
for i in d:
    print("  slot %3d disp 0x%04X  CMC=0x%07X  LOKI=0x%07X"%(i,i*8,C[i],L[i]))
print()
for nm,b,n in (("UPawnMovementComponent",P,204),("UNavMovementComponent",N,197),("UMovementComponent",M,184)):
    dd=[i for i in range(n) if C[i]!=b[i]]
    print("CMC overrides %d of first %d vs %s"%(len(dd),n,nm))
