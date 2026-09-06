import struct
d=open(r"dumps/merged12.dump.exe",'rb').read()
IB=0x7ff6af000000
lit=open("scratchpad/refute/litpages.bin",'rb').read()
def islit(a):
    if not (0x1000<=a<0x1000+0x7649000): return None
    return bool(lit[(a-0x1000)//0x1000])
VT={'AController':0x08010428,'AAIController':0x08431398,'ADetourCrowd/AGridPath':0x0845AAC0,
    'ALokiAIController':0x08878580,'ALokiBotController':0x088CDE18,'ALokiMinionAIController':0x089F8078,
    'APawn':0x08179718,'ALokiHeroCharacter':0x089A6DA0}
NSLOT={'AController':289,'AAIController':308,'ADetourCrowd/AGridPath':308,'ALokiAIController':310,
       'ALokiBotController':310,'ALokiMinionAIController':310,'APawn':None,'ALokiHeroCharacter':None}
for name,vt in VT.items():
    n=NSLOT[name]
    if n is None: continue
    dark=[]
    tgts=[]
    for s in range(n):
        q=struct.unpack_from('<Q',d,vt+s*8)[0]
        r=q-IB
        tgts.append(r)
        if islit(r) is False: dark.append((s,r))
    print(f"{name:26s} slots={n} distinct={len(set(tgts))} DARK={len(dark)} {[ (s,hex(r)) for s,r in dark]}")
