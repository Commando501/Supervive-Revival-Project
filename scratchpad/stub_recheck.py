#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stub_recheck.py -- INDEPENDENT re-measurement of the four "empty stub" RVAs from
docs/fk1-angelscript-settled.md:168-171, contested by docs/fk13-console-exec-settled.md 6.1.

Deliberately shares NO code and NO constant table with exec_chain_grade.py
(whose KNOWN_FOLDS already hardcodes 0x05254180 -> 'ret', i.e. it has ingested the
claim under test).  Everything here is derived from the image bytes.

Measures, per RVA, per image:
  * first 32 raw bytes
  * capstone disassembly bounded by that image's OWN .pdata RUNTIME_FUNCTION
  * .pdata extent from the image's own exception directory (data dir #3)
  * COVERAGE GUARD: zero-byte census of the containing 4 KiB page and neighbours
"""
import struct, sys, os, bisect
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

REPO = r'G:\git\Supervive Revival Project'
IMAGES = [
    ('merged',   os.path.join(REPO, 'dumps', 'merged.dump.exe'),                                    0x7FF6AF000000),
    ('tuthero',  os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe'), 0x7FF6505C0000),
]

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = False


class Img:
    def __init__(self, tag, path, expect_base):
        self.tag, self.path = tag, path
        with open(path, 'rb') as f:
            self.d = f.read()
        pe = struct.unpack_from('<I', self.d, 0x3C)[0]
        assert self.d[pe:pe + 4] == b'PE\0\0', 'not a PE'
        nsec = struct.unpack_from('<H', self.d, pe + 6)[0]
        szopt = struct.unpack_from('<H', self.d, pe + 20)[0]
        opt = pe + 24
        magic = struct.unpack_from('<H', self.d, opt)[0]
        assert magic == 0x20b, 'not PE32+'
        self.base = struct.unpack_from('<Q', self.d, opt + 24)[0]
        self.expect_base = expect_base
        ndd = struct.unpack_from('<I', self.d, opt + 108)[0]
        dd = opt + 112
        self.exc_rva, self.exc_size = struct.unpack_from('<II', self.d, dd + 3 * 8)
        self.sec = []
        sh = opt + szopt
        self.flat = True
        for i in range(nsec):
            o = sh + i * 40
            nm = self.d[o:o + 8].rstrip(b'\0').decode('latin1')
            vs, va, rs, rp = struct.unpack_from('<IIII', self.d, o + 8)
            self.sec.append((nm, va, vs, rp, rs))
            if rs and rp != va:
                self.flat = False
        # own .pdata
        self.pb, self.pe_, self.pu = [], [], []
        n = self.exc_size // 12
        for i in range(n):
            o = self.exc_rva + i * 12
            b, e, u = struct.unpack_from('<III', self.d, o)
            if b == 0 and e == 0:
                continue
            self.pb.append(b); self.pe_.append(e); self.pu.append(u)
        order = sorted(range(len(self.pb)), key=lambda i: self.pb[i])
        self.pb = [self.pb[i] for i in order]
        self.pe_ = [self.pe_[i] for i in order]
        self.pu = [self.pu[i] for i in order]

    def sect(self, rva):
        for nm, va, vs, rp, rs in self.sec:
            if va <= rva < va + vs:
                return nm
        return '?'

    def pdata_for(self, rva):
        i = bisect.bisect_right(self.pb, rva) - 1
        if i < 0:
            return None
        if self.pb[i] <= rva < self.pe_[i]:
            return (self.pb[i], self.pe_[i], self.pu[i])
        return None

    def page_stats(self, rva):
        out = []
        for delta in (-0x1000, 0, 0x1000):
            p = (rva & ~0xFFF) + delta
            if p < 0 or p + 0x1000 > len(self.d):
                out.append((p, None))
                continue
            blk = self.d[p:p + 0x1000]
            out.append((p, sum(1 for b in blk if b)))
        return out


def show(img, rva, label, maxins=14):
    print('  [%s] base=%#x (expected %#x)%s  section=%s'
          % (img.tag, img.base, img.expect_base,
             '' if img.base == img.expect_base else '   <<< BASE MISMATCH',
             img.sect(rva)))
    if rva + 32 > len(img.d):
        print('    RVA beyond file'); return
    raw = img.d[rva:rva + 32]
    print('    first32: ' + ' '.join('%02x' % b for b in raw))
    pd = img.pdata_for(rva)
    if pd:
        b, e, u = pd
        print('    .pdata : begin=%#08x end=%#08x  extent=%d B  unwind=%#x%s'
              % (b, e, e - b, u, '' if b == rva else '   (rva is +%d INTO the function)' % (rva - b)))
        end = e
    else:
        print('    .pdata : NO RUNTIME_FUNCTION covers this RVA (leaf/absent)')
        end = rva + 32
    n = 0
    for ins in md.disasm(img.d[rva:min(end, rva + 160)], rva):
        print('      %08x  %-22s %s %s' % (ins.address, ins.bytes.hex(' '), ins.mnemonic, ins.op_str))
        n += 1
        if n >= maxins:
            print('      ... (truncated at %d instructions)' % maxins)
            break
    if n == 0:
        print('      <no instruction decoded>')
    ps = img.page_stats(rva)
    print('    coverage: ' + '  '.join(
        '%s@%#x=%s' % (('prev', 'THIS', 'next')[i], p, ('unmapped' if c is None else '%d/4096 nonzero' % c))
        for i, (p, c) in enumerate(ps)))


TARGETS = [
    (0x534C070, 'CLAIM A: ALokiGameMode::SpawnPlayer'),
    (0x5254180, 'CLAIM A: ALokiPlayerState::AuthSetSpawnTeamLeader'),
    (0x2C2CE30, 'CLAIM A: ALokiTeamState_TeamOnly::SetDropLeader'),
    (0x53372A0, 'CLAIM A: ALokiDropPlane::OverridePlaneLocations'),
    (0x00F7EC20, 'NEG CONTROL: universal `ret 0` fold (c2 00 00)'),
    (0x00F7EB60, 'NEG CONTROL: `xor al,al; ret` fold'),
    (0x3C64600,  'POS CONTROL: APlayerController::LocalTravel exec thunk'),
    (0x395D790,  'POS CONTROL: UKismetSystemLibrary::ExecuteConsoleCommand thunk'),
    (0x5795300,  'POS CONTROL: impl behind CheatTravelToMainMenu (fk6 csv: 113 ins)'),
]

imgs = [Img(t, p, b) for t, p, b in IMAGES]
for im in imgs:
    print('%-8s %s' % (im.tag, im.path))
    print('   ImageBase=%#x  flat(RVA==fileoff)=%s  .pdata dir rva=%#x size=%d  entries=%d'
          % (im.base, im.flat, im.exc_rva, im.exc_size, len(im.pb)))
    print('   sections: ' + ', '.join('%s@%#x+%#x' % (n, v, s) for n, v, s, _, _ in im.sec))
print()

for rva, label in TARGETS:
    print('=' * 100)
    print('RVA %#09x   %s' % (rva, label))
    print('=' * 100)
    for im in imgs:
        show(im, rva, label)
        print()
