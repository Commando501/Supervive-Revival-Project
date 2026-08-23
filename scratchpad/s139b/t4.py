from h import *
print(DATA[0x055B88D0:0x055B88F0].hex(' '))
VT=0x088F8570
def slot(n):
    va=struct.unpack_from('<Q',DATA,VT+8*n)[0]
    return va-IMAGEBASE
for n,name in [(122,'TickComponent'),(156,'ShouldSkipUpdate'),(194,'?IsMovingOnGround'),(200,'ConsumeInputVector'),(215,'HasValidData'),(228,'StartNewPhysics'),(260,'?'),(262,'PhysFalling'),(327,'ConstrainInputAccel'),(339,'?'),(341,'PerformMovement'),(342,'?slot342'),(365,'TickCharacterPose')]:
    print("slot %-4d (+0x%03X) -> 0x%08X   %s"%(n,8*n,slot(n),name))
# count slots until a non-.text pointer
n=0
while True:
    va=struct.unpack_from('<Q',DATA,VT+8*n)[0]
    r=va-IMAGEBASE
    if not (0x1000<=r<0x0764A000): break
    n+=1
print("contiguous .text slots from VT:",n)
