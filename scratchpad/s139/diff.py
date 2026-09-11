import sys
sys.path.insert(0,'scratchpad/s139')
from vt import slots
L=slots(0x088F8570,413); C=slots(0x07FBED58,413)
P=slots(0x07FE2A10,204); N=slots(0x07FDB188,197); M=slots(0x07FD7568,184)
print("POSCTRL slot188 disp0x5E0: CMC=%s Loki=%s  (expect 0x35F41D0 both)"%(hex(C[188]),hex(L[188])))
d=[i for i in range(413) if L[i]!=C[i]]
print("Loki overrides vs UCharacterMovementComponent: %d slots"%len(d))
for i in d:
    print("  slot %3d disp 0x%04X  CMC=0x%07X  LOKI=0x%07X"%(i,i*8,C[i],L[i]))
print()
# where does CMC itself override its bases
def cmp2(name, base, n):
    dd=[i for i in range(n) if C[i]!=base[i]]
    print("%s: CMC overrides %d of first %d"%(name,len(dd),n))
cmp2("vs UPawnMovementComponent",P,204)
cmp2("vs UNavMovementComponent",N,197)
cmp2("vs UMovementComponent",M,184)
