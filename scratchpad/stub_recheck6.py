#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stub_recheck6.py -- how RARE is an empty impl?

If most native UFunctions in this image fold to the empty stub, then "these four
are empty" carries no information about server-code stripping.  Measure the base rate.

Discriminates real execFoo thunks from Z_Construct_UFunction_* singletons
(which call UECodeGen_Private::ConstructUFunction @0x135F5E0) -- the pass-5 artifact.
"""
import struct, os, bisect, collections
from array import array
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

REPO = r'G:\git\Supervive Revival Project'
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
IMGP = os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')
md = Cs(CS_ARCH_X86, CS_MODE_64)

PB, PE_ = array('l'), array('l')
with open(PDATA_CSV) as f:
    next(f)
    for line in f:
        p = line.split(',')
        PB.append(int(p[0], 16)); PE_.append(int(p[1], 16))
_o = sorted(range(len(PB)), key=lambda i: PB[i])
PB = [PB[i] for i in _o]; PE_ = [PE_[i] for i in _o]


def pdata_for(r):
    i = bisect.bisect_right(PB, r) - 1
    return (PB[i], PE_[i]) if i >= 0 and PB[i] <= r < PE_[i] else None


d = open(IMGP, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3C)[0]
nsec = struct.unpack_from('<H', d, pe + 6)[0]
szopt = struct.unpack_from('<H', d, pe + 20)[0]
opt = pe + 24
BASE = struct.unpack_from('<Q', d, opt + 24)[0]
sec = {}
sh = opt + szopt
for i in range(nsec):
    o = sh + i * 40
    nm = d[o:o + 8].rstrip(b'\0').decode('latin1')
    vs, va, rs, rp = struct.unpack_from('<IIII', d, o + 8)
    sec[nm] = (va, vs)
tva, tvs = sec['.text']; TLO, THI = BASE + tva, BASE + tva + tvs
rva_, rvs = sec['.rdata']; RLO, RHI = BASE + rva_, BASE + rva_ + rvs

CONSTRUCT_UFUNCTION = 0x135F5E0
HELPERS = {0x135f5e0, 0x1345fb0, 0x1345fe0, 0x0ff9310, 0x12f3fc0, 0x133f8f0,
           0x133e870, 0x133ebe0, 0x133eea0, 0x133f840, 0x133f370, 0x1258bf0, 0x751deb0}
EMPTY = {b'\xc2\x00\x00': 'ret 0', b'\xc3': 'ret',
         b'\x33\xc0\xc3': 'xor eax,eax; ret', b'\x32\xc0\xc3': 'xor al,al; ret'}


def page_nz(r):
    p = r & ~0xFFF
    return sum(1 for b in d[p:p + 0x1000] if b)


def emptykind(r):
    if page_nz(r) == 0:
        return 'COVERAGE-BLOCKED'
    b = d[r:r + 4]
    for pat, t in EMPTY.items():
        if b[:len(pat)] == pat:
            return t
    return None


def cstr(r, cap=96):
    e = d.find(b'\0', r, r + cap)
    if e <= r:
        return None
    s = d[r:e]
    if any(c < 0x20 or c > 0x7e for c in s):
        return None
    return s.decode('ascii')


# name -> thunk candidates
t2n = collections.defaultdict(set)
for s in ('.rdata', '.data'):
    va, vs = sec[s]
    blob = d[va:va + vs]
    for o in range(0, len(blob) - 16 + 1, 8):
        p0 = struct.unpack_from('<Q', blob, o)[0]
        if not (RLO <= p0 < RHI):
            continue
        p1 = struct.unpack_from('<Q', blob, o + 8)[0]
        if not (TLO <= p1 < THI):
            continue
        nm = cstr(p0 - BASE)
        if not nm or len(nm) < 2 or not (nm[0].isalpha() or nm[0] == '_'):
            continue
        if not all(c.isalnum() or c == '_' for c in nm):
            continue
        t2n[p1 - BASE].add(nm)

stat = collections.Counter()
impl_hist = collections.Counter()
blocked = 0
for th in t2n:
    if page_nz(th) == 0:
        blocked += 1
        stat['thunk COVERAGE-BLOCKED'] += 1
        continue
    pd = pdata_for(th)
    end = pd[1] if pd else th + 64
    tg, is_construct = [], False
    for i in md.disasm(d[th:end], th):
        if i.mnemonic in ('call', 'jmp') and i.op_str.startswith('0x'):
            t = int(i.op_str, 16)
            if t == CONSTRUCT_UFUNCTION:
                is_construct = True
            if not (th <= t < end) and t not in HELPERS:
                tg.append(t)
    if is_construct:
        stat['Z_Construct_UFunction singleton (not an exec thunk)'] += 1
        continue
    stat['exec thunk analysed'] += 1
    if not tg:
        stat['  no non-helper target (impl inlined/none)'] += 1
        continue
    impl = tg[-1] if len(tg) == 1 else tg[0]
    for t in tg:
        k = emptykind(t)
        if k:
            impl = t
            break
    k = emptykind(impl)
    if k == 'COVERAGE-BLOCKED':
        stat['  impl COVERAGE-BLOCKED'] += 1
    elif k:
        stat['  impl EMPTY'] += 1
        impl_hist[(impl, k)] += 1
    else:
        stat['  impl REAL'] += 1

print('registered .text pointers scanned : %d' % len(t2n))
for k, v in stat.most_common():
    print('  %-52s %6d' % (k, v))
tot = stat['  impl EMPTY'] + stat['  impl REAL']
if tot:
    print('\nBASE RATE among exec thunks with a resolvable impl:  EMPTY %d / %d = %.1f%%'
          % (stat['  impl EMPTY'], tot, 100.0 * stat['  impl EMPTY'] / tot))
print('\nempty-fold targets by popularity:')
for (a, k), c in impl_hist.most_common(10):
    print('   %#09x  %-20s %6d thunks' % (a, k, c))
print()
for a in (0x0F7EC20, 0x0F7EB50, 0x0F7EB60):
    print('%#09x : %-22s names registered directly at it = %d'
          % (a, emptykind(a) or 'REAL', len(t2n.get(a, ()))))
