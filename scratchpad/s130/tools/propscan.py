#!/usr/bin/env python
"""Offline scanner for UHT UECodeGen_Private::F*PropertyParams records in .data/.rdata.

Hypothesised layout (UE5.4, WITH_METADATA=0):
  +0x00 const char* NameUTF8
  +0x08 const char* RepNotifyFuncUTF8
  +0x10 uint64 PropertyFlags (EPropertyFlags)
  +0x18 uint32 Flags         (EPropertyGenFlags)
  +0x1C uint32 ObjectFlags   (expect 0x45)
  +0x20 void*  SetterFunc
  +0x28 void*  GetterFunc
  +0x30 uint16 ArrayDim
  +0x32 uint16 Offset        <-- the measurement
CALIBRATED against known-offset ground truth, not assumed.
"""
import sys, struct, re, argparse

DUMPS = {
 's129':   r'G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe',
 'merged2':r'G:\git\Supervive Revival Project\dumps\merged2.dump.exe',
 'tuthero':r'G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe',
}
IDENT = re.compile(rb'^[A-Za-z_][A-Za-z0-9_]{0,127}$')


class Img:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        pe = struct.unpack_from('<I', self.d, 0x3C)[0]
        nsec = struct.unpack_from('<H', self.d, pe + 6)[0]
        optsz = struct.unpack_from('<H', self.d, pe + 20)[0]
        opt = pe + 24
        self.base = struct.unpack_from('<Q', self.d, opt + 24)[0]
        sh = opt + optsz
        self.sec = []
        for i in range(nsec):
            o = sh + i * 40
            self.sec.append((self.d[o:o + 8].rstrip(b'\0').decode('latin1'),
                             struct.unpack_from('<I', self.d, o + 12)[0],
                             struct.unpack_from('<I', self.d, o + 8)[0],
                             struct.unpack_from('<I', self.d, o + 20)[0],
                             struct.unpack_from('<I', self.d, o + 16)[0]))

    def rng(self, n):
        for nm, va, vs, ra, rs in self.sec:
            if nm == n:
                return va, vs
        return None, None

    def secof(self, rva):
        for nm, va, vs, ra, rs in self.sec:
            if va <= rva < va + vs:
                return nm
        return None

    def rva(self, va):
        r = va - self.base
        return r if 0 <= r < len(self.d) else None

    def cstr(self, rva, cap=160):
        if rva is None or rva < 0 or rva >= len(self.d):
            return None
        e = self.d.find(b'\0', rva, rva + cap)
        if e <= rva:
            return None
        s = self.d[rva:e]
        return s if IDENT.match(s) else None


GEN = {0x00: 'Byte', 0x01: 'Int8', 0x02: 'Int16', 0x03: 'Int', 0x04: 'Int64', 0x05: 'UInt16',
       0x06: 'UInt32', 0x07: 'UInt64', 0x08: 'UnusedFloat', 0x09: 'Double', 0x0A: 'Bool',
       0x0B: 'SoftClass', 0x0C: 'WeakObject', 0x0D: 'LazyObject', 0x0E: 'SoftObject',
       0x0F: 'Class', 0x10: 'Object', 0x11: 'Interface', 0x12: 'Name', 0x13: 'Str',
       0x14: 'Array', 0x15: 'Map', 0x16: 'Set', 0x17: 'Struct', 0x18: 'Delegate',
       0x19: 'InlineMulticastDelegate', 0x1A: 'SparseMulticastDelegate', 0x1B: 'Text',
       0x1C: 'Enum', 0x1D: 'FieldPath', 0x1E: 'LargeWorldCoordinatesReal', 0x1F: 'Optional'}
GENMASK = 0x1F   # S130 recovery: re-added; boolscan.py imports it
GENMOD = [(0x20, 'NativeBool'), (0x40, 'Config'), (0x80, 'ObjectPtr')]

PF = [(0x1, 'Edit'), (0x2, 'ConstParm'), (0x4, 'BlueprintVisible'), (0x8, 'ExportObject'),
      (0x10, 'BlueprintReadOnly'), (0x20, 'Net'), (0x40, 'EditFixedSize'), (0x80, 'Parm'),
      (0x100, 'OutParm'), (0x200, 'ZeroConstructor'), (0x400, 'ReturnParm'),
      (0x800, 'DisableEditOnTemplate'), (0x1000, 'NonNullable'), (0x2000, 'Transient'),
      (0x4000, 'Config'), (0x8000, 'RequiredParm'), (0x10000, 'DisableEditOnInstance'),
      (0x20000, 'EditConst'), (0x40000, 'GlobalConfig'), (0x80000, 'InstancedReference'),
      (0x200000, 'DuplicateTransient'), (0x1000000, 'SaveGame'), (0x2000000, 'NoClear'),
      (0x8000000, 'ReferenceParm'), (0x10000000, 'BlueprintAssignable'),
      (0x20000000, 'Deprecated'), (0x40000000, 'IsPlainOldData'), (0x80000000, 'RepSkip'),
      (0x100000000, 'RepNotify'), (0x200000000, 'Interp'), (0x400000000, 'NonTransactional'),
      (0x800000000, 'EditorOnly'), (0x1000000000, 'NoDestructor'), (0x4000000000, 'AutoWeak'),
      (0x8000000000, 'ContainsInstancedReference'), (0x10000000000, 'AssetRegistrySearchable'),
      (0x20000000000, 'SimpleDisplay'), (0x40000000000, 'AdvancedDisplay'),
      (0x80000000000, 'Protected'), (0x100000000000, 'BlueprintCallable'),
      (0x200000000000, 'BlueprintAuthorityOnly'), (0x400000000000, 'TextExportTransient'),
      (0x800000000000, 'NonPIEDuplicateTransient'), (0x1000000000000, 'ExposeOnSpawn'),
      (0x2000000000000, 'PersistentInstance'), (0x4000000000000, 'UObjectWrapper'),
      (0x8000000000000, 'HasGetValueTypeHash'), (0x10000000000000, 'NativeAccessSpecifierPublic'),
      (0x20000000000000, 'NativeAccessSpecifierProtected'),
      (0x40000000000000, 'NativeAccessSpecifierPrivate'), (0x80000000000000, 'SkipSerialization')]

_KNOWN = 0
for _b, _n in PF:
    _KNOWN |= _b


def pfstr(v):
    out = [n for b, n in PF if v & b]
    rest = v & ~_KNOWN
    if rest:
        out.append('unk:0x%X' % rest)
    return '|'.join(out) or 'None'


def genstr(v):
    t = v & 0x1F
    s = GEN.get(t, '?%d' % t)
    for b, n in GENMOD:
        if v & b:
            s += '|' + n
    rest = v & ~0xFF
    if rest:
        s += '|unk:0x%X' % rest
    return s


def scan(img, want_off=None, want_name=None, sections=('.data', '.rdata')):
    hits = []
    for sname in sections:
        va, vs = img.rng(sname)
        if va is None:
            continue
        end = min(va + vs, len(img.d))
        for r in range(va, end - 0x38, 8):
            if struct.unpack_from('<I', img.d, r + 0x1C)[0] != 0x45:
                continue
            ad = struct.unpack_from('<H', img.d, r + 0x30)[0]
            if ad < 1 or ad > 256:
                continue
            off = struct.unpack_from('<H', img.d, r + 0x32)[0]
            if want_off is not None and off != want_off:
                continue
            nptr = struct.unpack_from('<Q', img.d, r)[0]
            nm = img.cstr(img.rva(nptr))
            if nm is None:
                continue
            if want_name is not None and nm.decode() != want_name:
                continue
            rn = struct.unpack_from('<Q', img.d, r + 8)[0]
            rnm = img.cstr(img.rva(rn)) if rn else b''
            hits.append(dict(rva=r, sec=sname, name=nm.decode(),
                             repnotify=(rnm or b'').decode(),
                             pflags=struct.unpack_from('<Q', img.d, r + 0x10)[0],
                             gflags=struct.unpack_from('<I', img.d, r + 0x18)[0],
                             arraydim=ad, off=off))
    return hits


def show(h):
    print('0x%08X %-7s %-46s off=0x%-5X dim=%d gen=%s' %
          (h['rva'], h['sec'], h['name'], h['off'], h['arraydim'], genstr(h['gflags'])))
    print('     pflags=0x%016X %s%s' % (h['pflags'], pfstr(h['pflags']),
          ('  repnotify=' + h['repnotify']) if h['repnotify'] else ''))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default='s129')
    ap.add_argument('--off', type=lambda x: int(x, 0), default=None)
    ap.add_argument('--name', default=None)
    ap.add_argument('--gen', type=lambda x: int(x, 0), default=None,
                    help='filter on EPropertyGenFlags low 5 bits')
    a = ap.parse_args()
    img = Img(DUMPS[a.dump])
    hits = scan(img, a.off, a.name)
    if a.gen is not None:
        hits = [h for h in hits if (h['gflags'] & 0x1F) == a.gen]
    print('image %s base 0x%X   hits: %d' % (a.dump, img.base, len(hits)))
    for h in hits:
        show(h)
