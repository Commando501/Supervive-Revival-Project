# INDEPENDENT UHT FPropertyParams offset oracle. Written from scratch.
# Record layout (non-bool): +0x00 NameUTF8* +0x08 RepNotify* +0x10 Flags(u64) +0x18 GenFlags(u32)
#                           +0x1C ObjFlags(u32) +0x20 Setter* +0x28 Getter* +0x30 ArrayDim(u16) +0x32 Offset(u16)
import struct, sys
from vimg import VImg, IMAGEBASE
im=VImg()
buf=im.buf
RD_LO, RD_HI = 0x0764A000, 0x0764A000+0x0237D000

def find_str(name):
    pat = name.encode()+b'\0'
    out=[]
    i=RD_LO
    while True:
        j=buf.find(pat, i, RD_HI)
        if j<0: break
        # require the preceding byte to be 0 so we get a whole string, not a suffix
        if buf[j-1]==0: out.append(j)
        i=j+1
    return out

def ptrs_to(rva):
    va = IMAGEBASE + rva
    pat = struct.pack('<Q', va)
    out=[]
    i=RD_LO
    while True:
        j=buf.find(pat, i, RD_HI)
        if j<0: break
        if j % 8 == 0: out.append(j)
        i=j+1
    return out

GEN = {0x00:'Byte',0x01:'Int8',0x02:'Int16',0x03:'Int',0x04:'Int64',0x05:'UInt16',0x06:'UInt32',
       0x07:'UInt64',0x08:'UnsizedInt',0x09:'UnsizedUInt',0x0A:'Float',0x0B:'Double',0x0C:'Bool',
       0x0D:'SoftClass',0x0E:'WeakObject',0x0F:'LazyObject',0x10:'SoftObject',0x11:'Class',
       0x12:'Object',0x13:'Interface',0x14:'Name',0x15:'Str',0x16:'Array',0x17:'Map',0x18:'Set',
       0x19:'Struct',0x1A:'Delegate',0x1B:'InlineMulticastDelegate',0x1C:'SparseMulticastDelegate',
       0x1D:'Text',0x1E:'Enum',0x1F:'FieldPath',0x20:'LargeWorldCoordinatesReal',0x21:'Optional'}

def probe(name, verbose=True):
    ss=find_str(name)
    recs=[]
    for s in ss:
        for p in ptrs_to(s):
            rec=p
            try:
                flags, = struct.unpack_from('<Q', buf, rec+0x10)
                gen,   = struct.unpack_from('<I', buf, rec+0x18)
                arrdim,off = struct.unpack_from('<HH', buf, rec+0x30)
                sizeouter, = struct.unpack_from('<I', buf, rec+0x34)
                setbit,    = struct.unpack_from('<Q', buf, rec+0x38)
            except Exception:
                continue
            k = gen & 0x3F
            recs.append(dict(rec=rec,strrva=s,flags=flags,gen=gen,kind=GEN.get(k,hex(k)),
                             arrdim=arrdim,off=off,sizeouter=sizeouter,setbit=setbit))
    if verbose:
        if not recs:
            print("  %-40s -> NO RECORDS (string occurrences: %d)" % (name, len(ss)))
        for r in recs:
            if r['kind']=='Bool':
                sb = r['setbit'] - IMAGEBASE if r['setbit']>IMAGEBASE else 0
                bts = im.read(sb, 10) if 0<sb<len(buf) else b''
                print("  %-40s BOOL rec=0x%08X SizeOfOuter=0x%X SetBitFunc=0x%08X bytes=%s" %
                      (name, r['rec'], r['sizeouter'], sb, " ".join("%02x"%b for b in bts)))
            else:
                print("  %-40s %-8s rec=0x%08X ArrayDim=%d Offset=0x%X flags=0x%016X" %
                      (name, r['kind'], r['rec'], r['arrdim'], r['off'], r['flags']))
    return recs

print("=== POSITIVE CONTROLS: offsets already measured live by S139 ===")
for n in ['MovementMode','UpdatedComponent','CharacterOwner','Acceleration','MaxAcceleration','AnalogInputModifier']:
    probe(n)
print()
print("=== L3's PREDICTED-THEN-QUERIED offsets ===")
for n in ['LastUpdateLocation','LastUpdateRotation','LastUpdateVelocity','ServerLastTransformUpdateTimeStamp',
          'RootMotionParams','AnimRootMotionVelocity','CurrentRootMotion','LastUpdateRequestedVelocity']:
    probe(n)
print()
print("=== L3's claimed NEGATIVES (must return 0 records) + their positive control ===")
for n in ['bTeleportedSinceLastUpdate','NumJumpApexAttempts','bHasRequestedVelocity','RequestedVelocity','bForceNextFloorCheck']:
    probe(n)
