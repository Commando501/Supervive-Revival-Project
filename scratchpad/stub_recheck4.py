#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stub_recheck4.py -- thunk -> IMPL resolution, with the UHT/CRT helper set derived
EMPIRICALLY (not assumed) from a histogram over every registered exec thunk.

A UE `execFoo` thunk is:   P_GET_* (calls FFrame::Step helpers) ; P_FINISH ;
                           P_THIS->Foo(params) ; [P_NATIVE_END]
so the IMPL is a direct call/jmp target that is NOT one of the high-fanin helpers
and NOT inside the thunk itself.
"""
import struct, os, bisect, collections
from array import array
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

REPO = r'G:\git\Supervive Revival Project'
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
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
    if i >= 0 and PB[i] <= rva < PE_[i]:
        return PB[i], PE_[i]
    return None


class Img:
    def __init__(self, tag, path):
        self.tag = tag
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

    def page_nz(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.d[p:p + 0x1000] if b)

    def cstr(self, rva, cap=96):
        e = self.d.find(b'\0', rva, rva + cap)
        if e <= rva:
            return None
        s = self.d[rva:e]
        if any(c < 0x20 or c > 0x7e for c in s):
            return None
        return s.decode('ascii')

    def native_pairs(self):
        if hasattr(self, '_np'):
            return self._np
        tva, tvs = self.sec['.text']; tlo, thi = self.base + tva, self.base + tva + tvs
        rva_, rvs = self.sec['.rdata']; rlo, rhi = self.base + rva_, self.base + rva_ + rvs
        n2t, t2n = collections.defaultdict(set), collections.defaultdict(set)
        for s in ('.rdata', '.data'):
            va, vs = self.sec[s]
            blob = self.d[va:va + vs]
            for o in range(0, len(blob) - 16 + 1, 8):
                p0 = struct.unpack_from('<Q', blob, o)[0]
                if not (rlo <= p0 < rhi):
                    continue
                p1 = struct.unpack_from('<Q', blob, o + 8)[0]
                if not (tlo <= p1 < thi):
                    continue
                nm = self.cstr(p0 - self.base)
                if not nm or len(nm) < 2 or not (nm[0].isalpha() or nm[0] == '_'):
                    continue
                if not all(c.isalnum() or c == '_' for c in nm):
                    continue
                n2t[nm].add(p1 - self.base); t2n[p1 - self.base].add(nm)
        self._np = (n2t, t2n)
        return self._np

    def targets(self, rva):
        pd = pdata_for(rva)
        end = pd[1] if pd else rva + 48
        out = []
        for i in md.disasm(self.d[rva:end], rva):
            if i.mnemonic in ('call', 'jmp') and i.op_str.startswith('0x'):
                t = int(i.op_str, 16)
                if not (rva <= t < end):          # skip intra-function branches
                    out.append((i.address, i.mnemonic, t))
        return out, end

    def grade(self, rva):
        if not (0 <= rva < len(self.d)):
            return 'OUT-OF-IMAGE'
        if self.page_nz(rva) == 0:
            return 'COVERAGE-BLOCKED'
        b = self.d[rva:rva + 4]
        if b[:3] == b'\xc2\x00\x00':
            return 'EMPTY (ret 0)'
        if b[:1] == b'\xc3':
            return 'EMPTY (ret)'
        if b[:3] == b'\x33\xc0\xc3':
            return 'EMPTY (xor eax,eax; ret)'
        if b[:3] == b'\x32\xc0\xc3':
            return 'EMPTY (xor al,al; ret)'
        pd = pdata_for(rva)
        n = sum(1 for _ in md.disasm(self.d[rva:(pd[1] if pd else rva + 48)], rva))
        return 'REAL (%s, %d insn)' % ('%dB pdata' % (pd[1] - pd[0]) if pd else 'no pdata', n)


im = Img('tuthero', os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe'))
im2 = Img('merged', os.path.join(REPO, 'dumps', 'merged.dump.exe'))
n2t, t2n = im.native_pairs()

# ---- empirical helper histogram over every registered thunk
print('deriving the UHT/CRT helper set empirically over %d distinct registered thunks...' % len(t2n))
fanin = collections.Counter()
for th in t2n:
    if im.page_nz(th) == 0:
        continue
    try:
        tg, _ = im.targets(th)
    except Exception:
        continue
    for _, _, t in tg:
        fanin[t] += 1
HELPER_MIN = 200
HELPERS = {t for t, c in fanin.items() if c >= HELPER_MIN}
print('targets called by >=%d distinct thunks => treated as helpers: %d' % (HELPER_MIN, len(HELPERS)))
for t, c in fanin.most_common(12):
    print('   %#09x  fanin=%-6d %s' % (t, c, im.grade(t)))
print()

CASES = [
    (0x534C070, 'SpawnPlayer',            'CLAIM A #1'),
    (0x5254180, 'AuthSetSpawnTeamLeader', 'CLAIM A #2'),
    (0x2C2CE30, 'SetDropLeader',          'CLAIM A #3'),
    (0x53372A0, 'OverridePlaneLocations', 'CLAIM A #4'),
    (0x3C64600, 'LocalTravel',            'POS CTRL (real body expected)'),
    (0x395D790, 'ExecuteConsoleCommand',  'POS CTRL (real body expected)'),
]

for rva, name, tag in CASES:
    print('=' * 100)
    print('%s   %s   thunk %#09x' % (tag, name, rva))
    print('=' * 100)
    names = sorted(t2n.get(rva, ()))
    print('  ICF fold multiplicity: this thunk is the registered native for %d name(s)' % len(names))
    if len(names) > 1:
        print('    -> the RVA does NOT identify one function. names: %s%s'
              % (', '.join(names[:12]), ' ...' if len(names) > 12 else ''))
    for img in (im2, im):
        tg, end = img.targets(rva)
        impl = [(a, m, t) for a, m, t in tg if t not in HELPERS]
        print('  [%s] thunk grade = %s' % (img.tag, img.grade(rva)))
        print('    all out-of-function targets:')
        for a, m, t in tg:
            print('      %08x %-4s -> %#09x  %-28s %s'
                  % (a, m, t, 'HELPER(fanin=%d)' % fanin[t] if t in HELPERS else 'candidate IMPL',
                     img.grade(t)))
        if impl:
            print('    ==> IMPL = %s' % ', '.join(
                '%#x [%s]' % (t, img.grade(t)) for _, _, t in impl))
        else:
            print('    ==> no non-helper target inside the thunk extent')
    print()
