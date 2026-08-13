#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stub_recheck5.py -- CLASS ATTRIBUTION of the exec thunks.

Each of the four contested names maps to TWO registered thunks, so "name -> thunk"
alone cannot decide which one belongs to the class CLAIM A names.  Resolve it the
way UHT actually lays it out:

  StaticRegisterNatives<UClass>(...) is handed a CONTIGUOUS array of
  FNameNativePtrPair {const ANSICHAR* Name; FNativeFuncPtr Ptr;} (stride 16).
  So: find maximal contiguous runs, then assign each run to the class whose
  native-function name set (from uht_funcflags_tuthero.csv, an independent
  instrument) best matches the run's name set.

BUILT-IN CONTROL: APlayerController::LocalTravel must land on 0x3C64600 and
UKismetSystemLibrary::ExecuteConsoleCommand on 0x395D790 -- both derived
independently by a Z_Construct walk in docs/fk13-console-exec-settled.md.
"""
import struct, os, collections, csv, bisect
from array import array
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

REPO = r'G:\git\Supervive Revival Project'
CSVP = os.path.join(REPO, 'tools', 're', 'out', 'uht_funcflags_tuthero.csv')
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
IMG = os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')
IMG2 = os.path.join(REPO, 'dumps', 'merged.dump.exe')
md = Cs(CS_ARCH_X86, CS_MODE_64)

PB, PE_ = array('l'), array('l')
with open(PDATA_CSV) as f:
    next(f)
    for line in f:
        p = line.split(',')
        PB.append(int(p[0], 16)); PE_.append(int(p[1], 16))
_o = sorted(range(len(PB)), key=lambda i: PB[i])
PB = [PB[i] for i in _o]; PE_ = [PE_[i] for i in _o]


def pdata_for(rva):
    i = bisect.bisect_right(PB, rva) - 1
    return (PB[i], PE_[i]) if i >= 0 and PB[i] <= rva < PE_[i] else None


class Img:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.d = f.read()
        pe = struct.unpack_from('<I', self.d, 0x3C)[0]
        nsec = struct.unpack_from('<H', self.d, pe + 6)[0]
        szopt = struct.unpack_from('<H', self.d, pe + 20)[0]
        opt = pe + 24
        self.base = struct.unpack_from('<Q', self.d, opt + 24)[0]
        self.sec = {}
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i * 40
            nm = self.d[o:o + 8].rstrip(b'\0').decode('latin1')
            vs, va, rs, rp = struct.unpack_from('<IIII', self.d, o + 8)
            self.sec[nm] = (va, vs)

    def cstr(self, rva, cap=96):
        e = self.d.find(b'\0', rva, rva + cap)
        if e <= rva:
            return None
        s = self.d[rva:e]
        if any(c < 0x20 or c > 0x7e for c in s):
            return None
        return s.decode('ascii')

    def page_nz(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.d[p:p + 0x1000] if b)

    def grade(self, rva):
        if self.page_nz(rva) == 0:
            return 'COVERAGE-BLOCKED'
        b = self.d[rva:rva + 4]
        for pat, txt in ((b'\xc2\x00\x00', 'EMPTY ret 0'), (b'\xc3', 'EMPTY ret'),
                         (b'\x33\xc0\xc3', 'EMPTY xor eax,eax;ret'), (b'\x32\xc0\xc3', 'EMPTY xor al,al;ret')):
            if b[:len(pat)] == pat:
                return txt
        pd = pdata_for(rva)
        n = sum(1 for _ in md.disasm(self.d[rva:(pd[1] if pd else rva + 48)], rva))
        return 'REAL (%s, %d insn)' % ('%dB' % (pd[1] - pd[0]) if pd else 'no pdata', n)


im = Img(IMG)
im2 = Img(IMG2)
tva, tvs = im.sec['.text']; TLO, THI = im.base + tva, im.base + tva + tvs
rva_, rvs = im.sec['.rdata']; RLO, RHI = im.base + rva_, im.base + rva_ + rvs


def is_pair(blob, o, secva):
    if o + 16 > len(blob):
        return None
    p0 = struct.unpack_from('<Q', blob, o)[0]
    if not (RLO <= p0 < RHI):
        return None
    p1 = struct.unpack_from('<Q', blob, o + 8)[0]
    if not (TLO <= p1 < THI):
        return None
    nm = im.cstr(p0 - im.base)
    if not nm or len(nm) < 2 or not (nm[0].isalpha() or nm[0] == '_'):
        return None
    if not all(c.isalnum() or c == '_' for c in nm):
        return None
    return nm, p1 - im.base


# ---- contiguous runs (stride 16)
runs = []
for sect in ('.rdata', '.data'):
    va, vs = im.sec[sect]
    blob = im.d[va:va + vs]
    o = 0
    while o + 16 <= len(blob):
        r = is_pair(blob, o, va)
        if r is None:
            o += 8
            continue
        cur = []
        while o + 16 <= len(blob):
            r = is_pair(blob, o, va)
            if r is None:
                break
            cur.append(r)
            o += 16
        runs.append((va + (o - 16 * len(cur)), cur))
print('contiguous FNameNativePtrPair runs found: %d  (total pairs %d)'
      % (len(runs), sum(len(c) for _, c in runs)))

# ---- per-class native function name sets from the independent CSV
cls_funcs = collections.defaultdict(set)
with open(CSVP, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if 'Native' in row['flags']:
            cls_funcs[row['owner']].add(row['func'])

# ---- assign each run to its best-matching class
run_class = []
for rva, pairs in runs:
    ns = set(n for n, _ in pairs)
    best, bestsc = None, 0.0
    for c, fs in cls_funcs.items():
        if not fs:
            continue
        inter = len(ns & fs)
        if not inter:
            continue
        sc = inter / len(ns | fs)
        if sc > bestsc:
            best, bestsc = c, sc
    run_class.append((rva, pairs, best, bestsc))

byclass = collections.defaultdict(list)
for rva, pairs, c, sc in run_class:
    if c:
        byclass[c].append((rva, pairs, sc))
print('runs attributed to a class: %d / %d' % (sum(len(v) for v in byclass.values()), len(runs)))
print()

CONTROLS = [('APlayerController', 'LocalTravel', 0x3C64600),
            ('UKismetSystemLibrary', 'ExecuteConsoleCommand', 0x395D790)]
QUERIES = [('ALokiGameMode', 'SpawnPlayer', 0x534C070),
           ('ALokiPlayerState', 'AuthSetSpawnTeamLeader', 0x5254180),
           ('ALokiTeamState_TeamOnly', 'SetDropLeader', 0x2C2CE30),
           ('ALokiDropPlane', 'OverridePlaneLocations', 0x53372A0)]


def lookup(cls, fn):
    hits = []
    for rva, pairs, sc in byclass.get(cls, ()):
        for n, t in pairs:
            if n == fn:
                hits.append((t, rva, sc, len(pairs)))
    return hits


def impl_of(img, thunk, helpers):
    pd = pdata_for(thunk)
    end = pd[1] if pd else thunk + 48
    out = []
    for i in md.disasm(img.d[thunk:end], thunk):
        if i.mnemonic in ('call', 'jmp') and i.op_str.startswith('0x'):
            t = int(i.op_str, 16)
            if not (thunk <= t < end) and t not in helpers:
                out.append(t)
    return out


HELPERS = {0x135f5e0, 0x1345fb0, 0x1345fe0, 0x0ff9310, 0x12f3fc0, 0x133f8f0,
           0x133e870, 0x133ebe0, 0x133eea0, 0x133f840, 0x133f370, 0x1258bf0,
           0x751deb0}

for tag, group in (('CONTROL', CONTROLS), ('CONTESTED', QUERIES)):
    for cls, fn, claimed in group:
        print('=' * 96)
        print('%-9s %s::%s      CLAIM A / FK-13 address = %#x' % (tag, cls, fn, claimed))
        hits = lookup(cls, fn)
        if not hits:
            print('   !! no attributed run for this class carries this name')
        for t, runrva, sc, npairs in hits:
            print('   attributed thunk %#09x   (run @%#x, %d pairs, jaccard %.2f)%s'
                  % (t, runrva, npairs, sc, '   <== MATCHES the claimed address' if t == claimed else ''))
            for img, nm in ((im2, 'merged'), (im, 'tuthero')):
                impls = impl_of(img, t, HELPERS)
                print('      [%-7s] thunk=%-26s impl(s)=%s'
                      % (nm, img.grade(t),
                         ', '.join('%#x [%s]' % (x, img.grade(x)) for x in impls) or '(none)'))
        # also show the other thunk(s) the bare name maps to
        print()
