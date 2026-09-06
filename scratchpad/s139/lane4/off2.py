import sys,struct
sys.path.insert(0,'scratchpad/s139/lane4')
import uht
from l4 import DATA,IB
RD_LO,RD_HI=uht.RD_LO,uht.RD_HI
def q(p): return struct.unpack_from('<Q',DATA,p)[0]
def d32(p): return struct.unpack_from('<I',DATA,p)[0]
def u16(p): return struct.unpack_from('<H',DATA,p)[0]
GEN={0x00:'Byte',0x01:'Int8',0x02:'Int16',0x03:'Int',0x04:'Int64',0x05:'UInt16',0x06:'UInt32',0x07:'UInt64',
     0x08:'UnsizedInt',0x09:'UnsizedUInt',0x0a:'Float',0x0b:'Double',0x0c:'Bool',0x0d:'SoftClass',0x0e:'WeakObject',
     0x0f:'LazyObject',0x10:'SoftObject',0x11:'Class',0x12:'Object',0x13:'Interface',0x14:'Name',0x15:'Str',
     0x16:'Array',0x17:'Map',0x18:'Set',0x19:'Struct',0x1a:'Delegate',0x1b:'InlineMulticastDelegate',
     0x1c:'SparseMulticastDelegate',0x1d:'Text',0x1e:'Enum',0x1f:'FieldPath',0x20:'LargeWorldCoordinatesReal',
     0x21:'Optional',0x22:'VerseValue'}
def scan(target):
    out=[]
    for p in range(RD_LO,RD_HI-0x40,8):
        v=q(p)
        if not (IB+RD_LO<=v<IB+RD_HI): continue
        sp=v-IB
        if sp not in uht.STR: continue
        if u16(p+0x32)!=target: continue
        if d32(p+0x1C)!=0x45: continue     # ObjectFlags == RF_Public|RF_Transient|RF_MarkAsNative
        if u16(p+0x30)==0: continue        # ArrayDim
        rn=q(p+8)
        if rn and not (IB+RD_LO<=rn<IB+RD_HI): continue
        gf=d32(p+0x18)
        out.append((p,uht.name_at(sp),GEN.get(gf&0xff,hex(gf)),gf,q(p+0x10)))
    return out
if __name__=='__main__':
    for t in [int(x,16) for x in sys.argv[1:]]:
        r=scan(t)
        print(f'--- offset 0x{t:X}: {len(r)} record(s)')
        for p,n,g,gf,fl in r: print(f'    0x{p:08X}  {n:<44} type={g:<10} genflags=0x{gf:08X} propflags=0x{fl:016X}')
