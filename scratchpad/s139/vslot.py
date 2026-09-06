import struct,sys
d=open("dumps/merged13.dump.exe",'rb').read()
IB=0x7ff608f40000
def slot(vt,disp):
    v=struct.unpack_from("<Q",d,vt+disp)[0]
    return v-IB if v>IB else v
VTS={
 "UActorComponent":0x07FA5508,
 "UMovementComponent":0x07FD7568,
 "UNavOrOther_07FDB188":0x07FDB188,
 "UPawnMovementComponent":0x07FE2A10,
 "UCharacterMovementComponent":0x07FBED58,
 "ULokiCharacterMovementComponent":0x088F8570,
}
disps=[int(x,16) for x in sys.argv[1:]]
for dsp in disps:
    print("disp 0x%X (slot %d):"%(dsp,dsp//8))
    for k,v in VTS.items():
        print("   %-34s 0x%08X"%(k,slot(v,dsp)))
