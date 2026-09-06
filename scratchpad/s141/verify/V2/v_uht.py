import sys,struct; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg
I=VImg('dumps/merged14.dump.exe')
d=I.d
def cstr(rva,mx=64):
    try: o=I.off(rva)
    except: return None
    if o is None: return None
    e=d.find(b'\0',o,o+mx)
    if e<0: return None
    s=d[o:e]
    try: return s.decode('ascii')
    except: return None
# L2 claims records at 0x07FAF660 + k*0x40 with NameRVA-ptr at +0, ArrayDim u16 @+0x30, Offset u16 @+0x32
print("=== independent walk of the record table around 0x07FAF660, stride 0x40 ===")
base=0x07FAF660
for k in range(-3,10):
    r=base+k*0x40
    try: rec=I.read(r,0x40)
    except KeyError: continue
    nameptr=struct.unpack_from('<Q',rec,0)[0]
    arrdim,off = struct.unpack_from('<HH',rec,0x30)
    nm=None
    if nameptr>I.ImageBase and nameptr-I.ImageBase < I.SizeOfImage:
        nm=cstr(nameptr-I.ImageBase)
    print("  k=%+d rec@%08X  nameptr=%016X  name=%-28s ArrayDim=%d Offset=0x%X" %
          (k,r,nameptr,repr(nm),arrdim,off))
print()
print("=== L2's five decoder controls, re-derived by me ===")
want={'MinAnalogWalkSpeed':0x290,'Acceleration':0x328,'MaxSimulationTimeStep':0x3E0,
      'MaxSimulationIterations':0x3E4,'MovementMode':0x231}
# scan a window of the same table for those names
found={}
for k in range(-400,400):
    r=base+k*0x40
    try: rec=I.read(r,0x40)
    except KeyError: continue
    nameptr=struct.unpack_from('<Q',rec,0)[0]
    if not (I.ImageBase < nameptr < I.ImageBase+I.SizeOfImage): continue
    nm=cstr(nameptr-I.ImageBase)
    if nm in want:
        arrdim,off=struct.unpack_from('<HH',rec,0x30)
        found.setdefault(nm,[]).append((r,off))
for n,exp in want.items():
    got=found.get(n,[])
    ok=any(o==exp for _,o in got)
    print("   %-26s expect 0x%-5X found %s  %s" % (n,exp,[(hex(r),hex(o)) for r,o in got],"PASS" if ok else "*** FAIL ***"))
print()
print("=== layout closure check ===")
print("   GravityDirection 0x1D8 + 24 = 0x%X ; +32 = 0x%X ; +32 = 0x%X" % (0x1D8+24,0x1D8+24+32,0x1D8+24+32+32))
