"""L3: UHT FPropertyParams offset oracle.

Find ASCII property-name literals in .rdata, find qword pointers to them, and
decode the surrounding FPropertyParamsBaseWithOffset record.

Layout hypothesis (UE5 UHT, 64-bit):
    +0x00 const char* NameUTF8
    +0x08 const char* RepNotifyFuncUTF8
    +0x10 uint64 PropertyFlags
    +0x18 uint32 EPropertyGenFlags
    +0x1C uint32 EObjectFlags
    +0x20 SetterFuncPtr
    +0x28 GetterFuncPtr
    +0x30 uint16 ArrayDim
    +0x32 uint16 Offset
The hypothesis is CALIBRATED against names whose offsets are already known
independently; it is only used where the calibration passes.
"""
import sys, struct, re
sys.path.insert(0, '.')
from peimg import Img

def find_cstr(im, s):
    """all rvas of an exact NUL-terminated ASCII literal, in any section"""
    pat = s.encode() + b'\0'
    out = []
    for sec in im.sections:
        blob = im.data[sec['praw']:sec['praw']+sec['rawsz']]
        i = 0
        while True:
            j = blob.find(pat, i)
            if j < 0: break
            # must be start-of-string: preceding byte NUL or section start
            if j == 0 or blob[j-1] == 0:
                out.append(sec['va'] + j)
            i = j + 1
    return out

def find_ptrs(im, rva):
    va = im.imagebase + rva
    pat = struct.pack('<Q', va)
    out = []
    for sec in im.sections:
        blob = im.data[sec['praw']:sec['praw']+sec['rawsz']]
        i = 0
        while True:
            j = blob.find(pat, i)
            if j < 0: break
            if (sec['va'] + j) % 8 == 0:
                out.append(sec['va'] + j)
            i = j + 1
    return out

def decode(im, rec_rva):
    b = im.read(rec_rva, 0x40)
    if len(b) < 0x40: return None
    name_va, repn_va = struct.unpack_from('<QQ', b, 0)
    flags = struct.unpack_from('<Q', b, 0x10)[0]
    genf, objf = struct.unpack_from('<II', b, 0x18)
    setter, getter = struct.unpack_from('<QQ', b, 0x20)
    arraydim, off = struct.unpack_from('<HH', b, 0x30)
    return dict(name_va=name_va, repn=repn_va, flags=flags, genf=genf, objf=objf,
                setter=setter, getter=getter, arraydim=arraydim, off=off, raw=b)

def lookup(im, name, expect=None):
    res = []
    for srva in find_cstr(im, name):
        for prva in find_ptrs(im, srva):
            d = decode(im, prva)
            if d is None: continue
            res.append((srva, prva, d))
    return res

if __name__ == '__main__':
    im = Img()
    tests = sys.argv[1:] or ['LastUpdateVelocity','LastUpdateLocation','LastUpdateRotation',
                             'Velocity','NumJumpApexAttempts','RootMotionParams',
                             'AnimRootMotionVelocity','MovementMode','UpdatedComponent',
                             'Acceleration','bForceNextFloorCheck']
    for t in tests:
        r = lookup(im, t)
        print(f"== {t}: {len(r)} candidate record(s)")
        for srva, prva, d in r[:8]:
            print(f"   str@{srva:#010x} rec@{prva:#010x} ArrayDim={d['arraydim']} "
                  f"Offset={d['off']:#x} genf={d['genf']:#x} flags={d['flags']:#018x}")
