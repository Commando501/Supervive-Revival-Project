#!/usr/bin/env python
"""
uht_funcflags.py -- OFFLINE recovery of EFunctionFlags for every NATIVE UFunction,
straight out of UHT's `UECodeGen_Private::FFunctionParams` static structs in .data.

Why this exists (FK-13, S114 lane 3): FK-6 measured `Exec == 0` across all 500
*script* UFUNCTIONs.  Nobody had measured the flag on the native ones, so
"the dev console / exec surface is stripped" was never tested against the half of
the surface that matters.  This tool tests it with no game running.

LAYOUT -- calibrated empirically against four ground-truth functions, NOT assumed:

    +0x00  UObject*  (*OuterFunc)()        -> .text, == Z_Construct_UClass_<Owner>
    +0x08  UFunction*(*SuperFunc)()        -> usually NULL
    +0x10  const char* NameUTF8            -> .rdata ASCII function name
    +0x18  const char* OwningClassName     -> NULL for class member funcs
    +0x20  const char* DelegateName        -> NULL for class member funcs
    +0x28  const FPropertyParamsBase* const* PropertyArray
    +0x30  uint16 NumProperties
    +0x32  uint16 StructureSize
    +0x34  EObjectFlags   ObjectFlags      == 0x45 (RF_Public|RF_MarkAsNative|RF_Transient)
    +0x38  EFunctionFlags FunctionFlags    <-- THE MEASUREMENT
    +0x3C  uint16 RPCId ; +0x3E uint16 RPCResponseId
    +0x40  const FMetaDataPairParam* MetaDataArray ; +0x48 int32 NumMetaData

CALIBRATION EVIDENCE (dumps/tutorial-hero, base 0x7FF6505C0000):
    ServerVerifyViewTarget  params 0x09AD9EC0  flags 0x80220CC2
        = NetValidate|NetServer|Public|Event|Native|NetReliable|Net|RequiredAPI
          -- matches this project's own RE of that RPC (memory: supervive-rpc-signature-solved)
    ClientSetHUD            params 0x09AD8800  flags 0x05020CC2
        = BlueprintCallable|NetClient|Public|Event|Native|NetReliable|Net|RequiredAPI
          -- matches stock UE APlayerController::ClientSetHUD
    ToggleDebugCamera       params 0x09A70750  flags 0x00020602  (has FUNC_Exec)
    God                     params 0x09A70290  flags 0x04020602  (has FUNC_Exec)
ObjectFlags@+0x34 == 0x45 on 100% of accepted rows is the built-in layout control;
the reject count is printed so a silent mis-parse cannot masquerade as a clean scan.

Owner class names are resolved from `FClassRegisterCompiledInInfo`
{ OuterRegister; InnerRegister; const TCHAR* Name; ... } -- i.e. find the .data
record whose +0x00 equals this function's OuterFunc and whose +0x10 is a WIDE string.

Usage
-----
  python uht_funcflags.py <dump.exe> --base 0xHEX [--csv out.csv]
                          [--flag Exec] [--grep SUBSTR] [--class SUBSTR]
"""
import sys, struct, argparse, re, csv

FUNC = [
    (0x00000001, 'Final'), (0x00000002, 'RequiredAPI'),
    (0x00000004, 'BlueprintAuthorityOnly'), (0x00000008, 'BlueprintCosmetic'),
    (0x00000040, 'Net'), (0x00000080, 'NetReliable'),
    (0x00000100, 'NetRequest'), (0x00000200, 'Exec'),
    (0x00000400, 'Native'), (0x00000800, 'Event'),
    (0x00001000, 'NetResponse'), (0x00002000, 'Static'),
    (0x00004000, 'NetMulticast'), (0x00008000, 'UbergraphFunction'),
    (0x00010000, 'MulticastDelegate'), (0x00020000, 'Public'),
    (0x00040000, 'Private'), (0x00080000, 'Protected'),
    (0x00100000, 'Delegate'), (0x00200000, 'NetServer'),
    (0x00400000, 'HasOutParms'), (0x00800000, 'HasDefaults'),
    (0x01000000, 'NetClient'), (0x02000000, 'DLLImport'),
    (0x04000000, 'BlueprintCallable'), (0x08000000, 'BlueprintEvent'),
    (0x10000000, 'BlueprintPure'), (0x20000000, 'EditorOnly'),
    (0x40000000, 'Const'), (0x80000000, 'NetValidate'),
]
BITS = dict((n, b) for b, n in FUNC)
RF_EXPECT = 0x45
NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def flagstr(v):
    return '|'.join(n for b, n in FUNC if v & b) or 'None'


class Img:
    def __init__(self, path, base_override=None):
        with open(path, 'rb') as f:
            self.d = f.read()
        pe = struct.unpack_from('<I', self.d, 0x3C)[0]
        nsec = struct.unpack_from('<H', self.d, pe + 6)[0]
        optsz = struct.unpack_from('<H', self.d, pe + 20)[0]
        opt = pe + 24
        self.base = base_override or struct.unpack_from('<Q', self.d, opt + 24)[0]
        sh = opt + optsz
        self.sec = []
        for i in range(nsec):
            o = sh + i * 40
            self.sec.append((self.d[o:o + 8].rstrip(b'\0').decode('latin1'),
                             struct.unpack_from('<I', self.d, o + 12)[0],
                             struct.unpack_from('<I', self.d, o + 8)[0],
                             struct.unpack_from('<I', self.d, o + 20)[0],
                             struct.unpack_from('<I', self.d, o + 16)[0]))
        self.flat = all(ra == va for _, va, _, ra, _ in self.sec if ra)

    def rng(self, name):
        for n, va, vs, ra, rs in self.sec:
            if n == name:
                return va, vs
        return None, None

    def off(self, rva):
        if self.flat:
            return rva if 0 <= rva < len(self.d) else None
        for n, va, vs, ra, rs in self.sec:
            if rs and va <= rva < va + rs:
                return ra + (rva - va)
        return None

    def rva(self, va):
        r = va - self.base
        return r if 0 <= r < 0x10000000 else None

    def cstr(self, rva, cap=200):
        o = self.off(rva)
        if o is None:
            return None
        e = self.d.find(b'\0', o, o + cap)
        if e <= o:
            return None
        s = self.d[o:e]
        if any(c < 0x20 or c > 0x7e for c in s):
            return None
        return s.decode('ascii')

    def wstr(self, rva, cap=200):
        o = self.off(rva)
        if o is None:
            return None
        out = []
        while len(out) < cap:
            c = struct.unpack_from('<H', self.d, o)[0]
            if c == 0:
                break
            if c < 0x20 or c > 0x7e:
                return None
            out.append(chr(c))
            o += 2
        return ''.join(out) if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('--base', type=lambda x: int(x, 0))
    ap.add_argument('--csv')
    ap.add_argument('--flag')
    ap.add_argument('--grep')
    ap.add_argument('--klass')
    a = ap.parse_args()

    im = Img(a.image, a.base)
    tva, tvs = im.rng('.text')
    tlo, thi = im.base + tva, im.base + tva + tvs
    print('base=%#x flat=%s' % (im.base, im.flat))

    # ---- pass 1: FClassRegisterCompiledInInfo -> {Z_Construct_UClass VA: name}
    owner = {}
    for sect in ('.data', '.rdata'):
        va, vs = im.rng(sect)
        o0 = im.off(va)
        blob = im.d[o0:o0 + vs]
        for s in range(0, len(blob) - 0x20, 8):
            f0 = struct.unpack_from('<Q', blob, s)[0]
            if not (tlo <= f0 < thi):
                continue
            f1 = struct.unpack_from('<Q', blob, s + 8)[0]
            if not (tlo <= f1 < thi):
                continue
            nr = im.rva(struct.unpack_from('<Q', blob, s + 0x10)[0])
            if nr is None:
                continue
            nm = im.wstr(nr, 120)
            if nm and NAME_RE.match(nm) and f0 not in owner:
                owner[f0] = nm
    print('class-registration records giving Z_Construct_UClass -> name : %d' % len(owner))

    # ---- pass 2: FFunctionParams
    rows, rejected, cand = [], 0, 0
    for sect in ('.data', '.rdata'):
        va, vs = im.rng(sect)
        o0 = im.off(va)
        blob = im.d[o0:o0 + vs]
        for s in range(0, len(blob) - 0x50, 8):
            outer = struct.unpack_from('<Q', blob, s)[0]
            if not (tlo <= outer < thi):
                continue
            if struct.unpack_from('<Q', blob, s + 0x18)[0]:
                continue
            nr = im.rva(struct.unpack_from('<Q', blob, s + 0x10)[0])
            if nr is None:
                continue
            nm = im.cstr(nr)
            if not nm or not NAME_RE.match(nm):
                continue
            cand += 1
            if struct.unpack_from('<I', blob, s + 0x34)[0] != RF_EXPECT:
                rejected += 1
                continue
            ff = struct.unpack_from('<I', blob, s + 0x38)[0]
            rows.append((owner.get(outer, '?0x%x' % (outer - im.base)), nm, ff,
                         va + s, outer - im.base))

    # de-dup: the same params struct can be referenced twice
    seen, uniq = set(), []
    for r in rows:
        k = (r[0], r[1], r[3])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    rows = uniq

    print('candidates matching the pointer signature : %d' % cand)
    print('  accepted (ObjectFlags@+0x34 == 0x45)    : %d  (%.2f%%)  <-- layout control'
          % (len(rows), 100.0 * len(rows) / max(cand, 1)))
    print('  rejected                                : %d' % rejected)
    named = sum(1 for r in rows if not r[0].startswith('?'))
    print('  owner class resolved                    : %d (%.1f%%)'
          % (named, 100.0 * named / max(len(rows), 1)))
    ex = [r for r in rows if r[2] & 0x200]
    print('\nnative UFunction registrations recovered  : %d' % len(rows))
    print('  with FUNC_Native (0x400)  [sanity]      : %d' % sum(1 for r in rows if r[2] & 0x400))
    print('  with FUNC_Exec   (0x200)                : %d' % len(ex))
    print('  with FUNC_Net    (0x40)   [sanity]      : %d' % sum(1 for r in rows if r[2] & 0x40))

    if a.csv:
        with open(a.csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['owner', 'func', 'flags_hex', 'flags', 'params_rva', 'outer_rva'])
            for o, n, ff, prva, orva in sorted(rows):
                w.writerow([o, n, '0x%08x' % ff, flagstr(ff), '0x%08x' % prva, '0x%08x' % orva])
        print('wrote', a.csv)

    sel = rows
    if a.flag:
        sel = [r for r in sel if r[2] & BITS[a.flag]]
    if a.grep:
        sel = [r for r in sel if a.grep.lower() in r[1].lower()]
    if a.klass:
        sel = [r for r in sel if a.klass.lower() in r[0].lower()]
    if a.flag or a.grep or a.klass:
        print()
        for o, n, ff, prva, orva in sorted(sel):
            print('%-34s %-40s 0x%08x  %s' % (o[:34], n[:40], ff, flagstr(ff)))
        print('(%d rows)' % len(sel))


if __name__ == '__main__':
    main()
