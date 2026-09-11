#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stub_recheck3.py -- final pass.

Instrument bugs found and fixed in my OWN passes (recorded, per project rule):
  pass 1: read .pdata from the PE exception data directory -> dir#3 is 0/0 in these
          dumps, so EVERY function looked like "no RUNTIME_FUNCTION". Artifact.
  pass 2: read .pdata from the SECTION -> the .pdata section is 100% ZERO in both
          dumps (6,283,264 B, 0 nonzero): it was never paged in. Artifact again.
  pass 3: extents come from tools/strxref/index/pdata_union.csv (union of 68 dumps).

Outputs, per target RVA, per image:
   raw bytes / full disasm over the union extent / branch targets + their grades
   / coverage guard / independent symbol resolution both directions.
"""
import struct, os, bisect, collections, csv
from array import array
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

REPO = r'G:\git\Supervive Revival Project'
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
IMAGES = [
    ('merged',  os.path.join(REPO, 'dumps', 'merged.dump.exe'),                                    0x7FF6AF000000),
    ('tuthero', os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe'), 0x7FF6505C0000),
]
md = Cs(CS_ARCH_X86, CS_MODE_64)

PB, PE_, PSEEN = array('l'), array('l'), array('l')
with open(PDATA_CSV) as f:
    next(f)
    for line in f:
        p = line.split(',')
        PB.append(int(p[0], 16)); PE_.append(int(p[1], 16)); PSEEN.append(int(p[4]))
_o = sorted(range(len(PB)), key=lambda i: PB[i])
PB = [PB[i] for i in _o]; PE_ = [PE_[i] for i in _o]; PSEEN = [PSEEN[i] for i in _o]


def pdata_for(rva):
    i = bisect.bisect_right(PB, rva) - 1
    if i >= 0 and PB[i] <= rva < PE_[i]:
        return PB[i], PE_[i], PSEEN[i]
    return None


class Img:
    def __init__(self, tag, path, base):
        self.tag = tag
        with open(path, 'rb') as f:
            self.d = f.read()
        pe = struct.unpack_from('<I', self.d, 0x3C)[0]
        nsec = struct.unpack_from('<H', self.d, pe + 6)[0]
        szopt = struct.unpack_from('<H', self.d, pe + 20)[0]
        opt = pe + 24
        self.base = struct.unpack_from('<Q', self.d, opt + 24)[0]
        assert self.base == base
        self.sec = {}
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i * 40
            nm = self.d[o:o + 8].rstrip(b'\0').decode('latin1')
            vs, va, rs, rp = struct.unpack_from('<IIII', self.d, o + 8)
            assert not rs or rp == va, 'image not flat'
            self.sec[nm] = (va, vs)

    def sect(self, rva):
        for nm, (va, vs) in self.sec.items():
            if va <= rva < va + vs:
                return nm
        return '?'

    def page_nz(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.d[p:p + 0x1000] if b)

    def cstr(self, rva, cap=96):
        if not (0 <= rva < len(self.d)):
            return None
        e = self.d.find(b'\0', rva, rva + cap)
        if e <= rva:
            return None
        s = self.d[rva:e]
        if any(c < 0x20 or c > 0x7e for c in s):
            return None
        return s.decode('ascii')

    def native_pairs(self):
        """UHT FNameNativePtrPair { const ANSICHAR* Name; FNativeFuncPtr Ptr; }"""
        if hasattr(self, '_np'):
            return self._np
        tva, tvs = self.sec['.text']; tlo, thi = self.base + tva, self.base + tva + tvs
        rva_, rvs = self.sec['.rdata']; rlo, rhi = self.base + rva_, self.base + rva_ + rvs
        n2t = collections.defaultdict(set)
        t2n = collections.defaultdict(set)
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
                if not nm or len(nm) < 2:
                    continue
                if not (nm[0].isalpha() or nm[0] == '_'):
                    continue
                if not all(c.isalnum() or c == '_' for c in nm):
                    continue
                n2t[nm].add(p1 - self.base)
                t2n[p1 - self.base].add(nm)
        self._np = (n2t, t2n)
        return self._np


def grade(im, rva):
    if not (0 <= rva < len(im.d)):
        return 'OUT-OF-IMAGE'
    if im.page_nz(rva) == 0:
        return 'COVERAGE-BLOCKED'
    b = im.d[rva:rva + 4]
    if b[:3] == b'\xc2\x00\x00':
        return 'EMPTY ret 0'
    if b[:1] == b'\xc3':
        return 'EMPTY ret'
    if b[:3] == b'\x33\xc0\xc3':
        return 'EMPTY xor eax,eax;ret'
    if b[:3] == b'\x32\xc0\xc3':
        return 'EMPTY xor al,al;ret'
    pd = pdata_for(rva)
    return 'REAL %dB' % (pd[1] - pd[0]) if pd else 'REAL(no pdata)'


TARGETS = [
    (0x534C070, 'CLAIM A #1  ALokiGameMode::SpawnPlayer', 'SpawnPlayer'),
    (0x5254180, 'CLAIM A #2  ALokiPlayerState::AuthSetSpawnTeamLeader', 'AuthSetSpawnTeamLeader'),
    (0x2C2CE30, 'CLAIM A #3  ALokiTeamState_TeamOnly::SetDropLeader', 'SetDropLeader'),
    (0x53372A0, 'CLAIM A #4  ALokiDropPlane::OverridePlaneLocations', 'OverridePlaneLocations'),
    (0x00F7EC20, 'NEG CTRL   universal ret-0 fold', None),
    (0x00F7EB60, 'NEG CTRL   xor al,al;ret fold', None),
    (0x3C64600, 'POS CTRL   APlayerController::LocalTravel exec thunk', 'LocalTravel'),
    (0x395D790, 'POS CTRL   UKismetSystemLibrary::ExecuteConsoleCommand thunk', 'ExecuteConsoleCommand'),
]

imgs = [Img(t, p, b) for t, p, b in IMAGES]
print('pdata_union.csv entries: %d   (both dumps have a 100%%-ZERO .pdata section)' % len(PB))
for im in imgs:
    n2t, t2n = im.native_pairs()
    print('%-8s base=%#x  FNameNativePtrPair: %d distinct names -> %d distinct thunks'
          % (im.tag, im.base, len(n2t), len(t2n)))
print()

for rva, label, sym in TARGETS:
    print('=' * 104)
    print('RVA %#09x   %s' % (rva, label))
    print('=' * 104)
    pd = pdata_for(rva)
    if pd:
        print('  .pdata(union of 68 dumps): begin=%#08x end=%#08x extent=%d B  seen_in=%d dumps%s'
              % (pd[0], pd[1], pd[1] - pd[0], pd[2],
                 '' if pd[0] == rva else '   <<< RVA IS +%d INTO THE FUNCTION' % (rva - pd[0])))
    else:
        print('  .pdata(union): NO entry covers this RVA')
    for im in imgs:
        end = pd[1] if pd else rva + 48
        print('  [%s] section=%s  page=%d/4096 nonzero  grade=%s'
              % (im.tag, im.sect(rva), im.page_nz(rva), grade(im, rva)))
        print('    first32: ' + ' '.join('%02x' % b for b in im.d[rva:rva + 32]))
        ins_list = list(md.disasm(im.d[rva:end], rva))
        tg = [(i.mnemonic, int(i.op_str, 16)) for i in ins_list
              if i.mnemonic in ('call', 'jmp') and i.op_str.startswith('0x')]
        for i in ins_list[:12]:
            print('      %08x  %-24s %s %s' % (i.address, i.bytes.hex(' '), i.mnemonic, i.op_str))
        if len(ins_list) > 12:
            print('      ... %d instructions total over the %d-byte extent' % (len(ins_list), end - rva))
        if tg:
            print('    branch targets: ' + ' | '.join('%s %#x [%s]' % (m, t, grade(im, t)) for m, t in tg[:6]))
        n2t, t2n = im.native_pairs()
        names = sorted(t2n.get(rva, ()))
        print('    FNameNativePtrPair -> this RVA is the registered native for %d name(s): %s'
              % (len(names), ', '.join(names[:8]) + (' ...' if len(names) > 8 else '') if names else '(none)'))
        if sym:
            got = sorted(n2t.get(sym, ()))
            print('    reverse: name %-24s -> thunk(s) %s   %s'
                  % (sym, ', '.join('%#x' % g for g in got) or '(not registered)',
                     'MATCH' if rva in got else 'NO MATCH'))
        print()
