import struct
IMG=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
d=open(IMG,'rb').read(); pe=struct.unpack_from('<I',d,0x3c)[0]; IB=struct.unpack_from('<Q',d,pe+24+24)[0]
def s(vt,disp):
    q=struct.unpack_from('<Q',d,vt+disp)[0]; return q-IB if q else 0
V={'AActor':None,'ACharacter':0x07F99368,'APawn':0x08179718,'ALokiCharacter':0x088E5CA8,
   'ALokiHeroCharacter':0x089A6DA0,'UCapsuleComponent':0x07FBD070}
for disp in (0x540,0x878,0x4C0):
    row=[]
    for k,v in V.items():
        if v is None: continue
        row.append("%s=0x%08X"%(k,s(v,disp)))
    print("disp 0x%03X slot %3d : %s"%(disp,disp//8," ".join(row)))
print()
CTRL={'AController':0x08010428,'AAIController':0x08431398,'ALokiAIController':0x08878580,'ALokiBotController':0x088CDE18}
for disp in (0x848,):
    for k,v in CTRL.items(): print("disp 0x%03X slot %d %s = 0x%08X"%(disp,disp//8,k,s(v,disp)))
