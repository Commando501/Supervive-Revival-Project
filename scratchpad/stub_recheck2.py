#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stub_recheck2.py -- pass 2.

Fixes pass 1's own instrument bug: these dumps have a ZEROED exception data
directory (dir#3 rva=0 size=0), so "no RUNTIME_FUNCTION" was an artifact of my
parser, not a property of the image.  The .pdata SECTION is present and full.
Parse the section directly.

Adds:
  * full thunk disassembly to its .pdata end, with call/jmp targets extracted
  * impl grading (follow the tail target)
  * INDEPENDENT symbol resolution via UHT FNameNativePtrPair arrays
        +0x00 const ANSICHAR* NameUTF8  -> .rdata
        +0x08 FNativeFuncPtr            -> .text
    giving name -> thunk AND thunk -> {names}  (the ICF fold multiplicity)
"""
import struct, os, bisect, collections, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

REPO = r'G:\git\Supervive Revival Project'
IMAGES = [
    ('merged',  os.path.join(REPO, 'dumps', 'merged.dump.exe'),                                    0x7FF6AF000000),
    ('tuthero', os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe'), 0x7FF6505C0000),
]
md = Cs(CS_ARCH_X86, CS_MODE_64)


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
        assert self.base == base, 'base %#x != expected %#x' % (self.base, base)
        self.sec = {}
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i * 40
            nm = self.d[o:o + 8].rstrip(b'\0').decode('latin1')
            vs, va, rs, rp = struct.unpack_from('<IIII', self.d, o + 8)
            self.sec[nm] = (va, vs, rp, rs)
        # --- .pdata straight from the SECTION (data dir is zeroed in these dumps)
        pva, pvs, prp, prs = self.sec['.pdata']
        self.pb, self.pe_, self.pu = [], [], []
        blob = self.d[pva:pva + pvs]
        for o in range(0, len(blob) - 12 + 1, 12):
            b, e, u = struct.unpack_from('<III', blob, o)
            if b == 0 and e == 0 and u == 0:
                continue
            if not (b < e):
                continue
            self.pb.append(b); self.pe_.append(e); self.pu.append(u)
        idx = sorted(range(len(self.pb)), key=lambda i: self.pb[i])
        self.pb = [self.pb[i] for i in idx]
        self.pe_ = [self.pe_[i] for i in idx]

    def pdata_for(self, rva):
        i = bisect.bisect_right(self.pb, rva) - 1
        if i >= 0 and self.pb[i] <= rva < self.pe_[i]:
            return self.pb[i], self.pe_[i]
        return None

    def sect(self, rva):
        for nm, (va, vs, rp, rs) in self.sec.items():
            if va <= rva < va + vs:
                return nm
        return '?'

    def page_nonzero(self, rva):
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

    # ---- FNameNativePtrPair scan: name -> thunk
    def native_pairs(self):
        if hasattr(self, '_np'):
            return self._np
        tva, tvs, _, _ = self.sec['.text']
        tlo, thi = self.base + tva, self.base + tva + tvs
        rva_, rvs, _, _ = self.sec['.rdata']
        rlo, rhi = self.base + rva_, self.base + rva_ + rvs
        n2t = collections.defaultdict(set)
        t2n = collections.defaultdict(set)
        for sect in ('.rdata', '.data'):
            va, vs, _, _ = self.sec[sect]
            blob = self.d[va:va + vs]
            for o in range(0, len(blob) - 16 + 1, 8):
                p0 = struct.unpack_from('<Q', blob, o)[0]
                if not (rlo <= p0 < rhi):
                    continue
                p1 = struct.unpack_from('<Q', blob, o + 8)[0]
                if not (tlo <= p1 < thi):
                    continue
                nm = self.cstr(p0 - self.base)
                if not nm or not nm[0].isalpha() and nm[0] != '_':
                    continue
                if not all(c.isalnum() or c == '_' for c in nm) or len(nm) < 2:
                    continue
                n2t[nm].add(p1 - self.base)
                t2n[p1 - self.base].add(nm)
        self._np = (n2t, t2n)
        return self._np


def disasm_fn(im, rva, cap=400):
    pd = im.pdata_for(rva)
    end = pd[1] if pd else rva + 64
    out, targets, ninsn = [], [], 0
    for ins in md.disasm(im.d[rva:min(end, rva + cap)], rva):
        out.append((ins.address, ins.bytes.hex(' '), ins.mnemonic, ins.op_str))
        ninsn += 1
        if ins.mnemonic in ('call', 'jmp') and ins.op_str.startswith('0x'):
            targets.append((ins.mnemonic, int(ins.op_str, 16)))
    return pd, out, targets, ninsn


def grade(im, rva):
    """Three-valued, coverage-guarded."""
    nz = im.page_nonzero(rva)
    if nz == 0:
        return 'COVERAGE-BLOCKED (page all-zero: never decrypted)'
    b = im.d[rva:rva + 8]
    if b[:3] == b'\xc2\x00\x00':
        return 'EMPTY (ret 0)'
    if b[:1] == b'\xc3':
        return 'EMPTY (ret)'
    if b[:3] == b'\x33\xc0\xc3':
        return 'EMPTY (xor eax,eax; ret)'
    if b[:3] == b'\x32\xc0\xc3':
        return 'EMPTY (xor al,al; ret)'
    pd = im.pdata_for(rva)
    if pd:
        return 'REAL (.pdata extent %d B)' % (pd[1] - pd[0])
    return 'REAL? (no .pdata entry; leaf)'


TARGETS = [
    (0x534C070, 'CLAIM A #1  ALokiGameMode::SpawnPlayer'),
    (0x5254180, 'CLAIM A #2  ALokiPlayerState::AuthSetSpawnTeamLeader'),
    (0x2C2CE30, 'CLAIM A #3  ALokiTeamState_TeamOnly::SetDropLeader'),
    (0x53372A0, 'CLAIM A #4  ALokiDropPlane::OverridePlaneLocations'),
    (0x00F7EC20, 'NEG CTRL    universal ret-0 fold'),
    (0x00F7EB60, 'NEG CTRL    xor al,al; ret fold'),
    (0x3C64600, 'POS CTRL    APlayerController::LocalTravel exec thunk'),
    (0x395D790, 'POS CTRL    UKismetSystemLibrary::ExecuteConsoleCommand thunk'),
]

imgs = [Img(t, p, b) for t, p, b in IMAGES]
for im in imgs:
    print('%-8s base=%#x  .pdata entries parsed from SECTION = %d  (data-dir #3 was 0/0 -> pass-1 artifact)'
          % (im.tag, im.base, len(im.pb)))
print()

for rva, label in TARGETS:
    print('=' * 104)
    print('RVA %#09x   %s' % (rva, label))
    print('=' * 104)
    for im in imgs:
        pd, out, tg, n = disasm_fn(im, rva)
        print('  [%s] section=%s  page nonzero=%d/4096  grade=%s'
              % (im.tag, im.sect(rva), im.page_nonzero(rva), grade(im, rva)))
        if pd:
            print('    .pdata: begin=%#08x end=%#08x extent=%d B%s'
                  % (pd[0], pd[1], pd[1] - pd[0],
                     '' if pd[0] == rva else '   <<< rva is +%d INTO fn' % (rva - pd[0])))
        else:
            print('    .pdata: none covering this RVA')
        print('    first32: ' + ' '.join('%02x' % b for b in im.d[rva:rva + 32]))
        for a, h, m, o in out[:10]:
            print('      %08x  %-24s %s %s' % (a, h, m, o))
        if len(out) > 10:
            print('      ... %d instructions total in extent' % n)
        if tg:
            print('    branch targets: ' + ', '.join(
                '%s %#x [%s]' % (m, t, grade(im, t)) for m, t in tg[:8]))
        print()
