#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
logrec_scan.py -- OFFLINE enumeration of UE 5.4 `UE::Logging::Private::FStaticBasicLogRecord`
static structs in a dumpimage snapshot.  Stdlib only.  No live process, no injection.

Layout (STOCK UE 5.4, read from the local tree, not guessed):
    H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Core\Public\Logging\LogMacros.h:117
      +0x00  const TCHAR*    Format        -> .rdata UTF-16LE
      +0x08  const ANSICHAR* File          -> .rdata ASCII (__builtin_FILE())
      +0x10  int32           Line
      +0x14  ELogVerbosity::Type Verbosity
      +0x18  FStaticBasicLogDynamicData&   -> writable data
    sizeof == 0x20

The record is emitted `static constexpr` by the UE_LOG macro (LogMacros.h:278), so it
lands in a read-only data section and the whole set is enumerable with a pointer scan.

Usage:
  logrec_scan.py --all                 census (positive control: FK-11 measured 14,030)
  logrec_scan.py --file SUBSTR         records whose File path contains SUBSTR
  logrec_scan.py --fmt SUBSTR          records whose Format contains SUBSTR
"""
import argparse
import struct
import sys
import os

DUMP = r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe"

VERB = {0: 'NoLogging', 1: 'Fatal', 2: 'Error', 3: 'Warning', 4: 'Display',
        5: 'Log', 6: 'Verbose', 7: 'VeryVerbose'}


class Image:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.buf = f.read()
        e_lfanew = struct.unpack_from('<I', self.buf, 0x3C)[0]
        assert self.buf[e_lfanew:e_lfanew + 4] == b'PE\0\0'
        coff = e_lfanew + 4
        nsec = struct.unpack_from('<H', self.buf, coff + 2)[0]
        optsz = struct.unpack_from('<H', self.buf, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from('<H', self.buf, opt)[0]
        assert magic == 0x20B, hex(magic)
        self.base = struct.unpack_from('<Q', self.buf, opt + 24)[0]
        self.sizeofimage = struct.unpack_from('<I', self.buf, opt + 56)[0]
        self.sections = []
        sh = opt + optsz
        for i in range(nsec):
            o = sh + i * 40
            name = self.buf[o:o + 8].rstrip(b'\0').decode('latin1')
            vsize = struct.unpack_from('<I', self.buf, o + 8)[0]
            va = struct.unpack_from('<I', self.buf, o + 12)[0]
            rawsz = struct.unpack_from('<I', self.buf, o + 16)[0]
            rawptr = struct.unpack_from('<I', self.buf, o + 20)[0]
            self.sections.append((name, va, vsize, rawptr, rawsz))

    def sec_of(self, rva):
        for (n, va, vs, rp, rs) in self.sections:
            if va <= rva < va + max(vs, rs):
                return n
        return None

    def off(self, rva):
        """file offset for an RVA, or None"""
        for (n, va, vs, rp, rs) in self.sections:
            if va <= rva < va + max(vs, rs):
                d = rva - va
                if d < rs:
                    return rp + d
                return None
        return None

    def u64(self, rva):
        o = self.off(rva)
        if o is None or o + 8 > len(self.buf):
            return None
        return struct.unpack_from('<Q', self.buf, o)[0]

    def i32(self, rva):
        o = self.off(rva)
        if o is None:
            return None
        return struct.unpack_from('<i', self.buf, o)[0]

    def cstr(self, rva, maxlen=400):
        o = self.off(rva)
        if o is None:
            return None
        end = self.buf.find(b'\0', o, o + maxlen)
        if end < 0:
            return None
        try:
            return self.buf[o:end].decode('utf-8')
        except UnicodeDecodeError:
            return None

    def wstr(self, rva, maxlen=1200):
        o = self.off(rva)
        if o is None:
            return None
        end = o
        lim = min(o + maxlen * 2, len(self.buf) - 1)
        while end < lim:
            if self.buf[end] == 0 and self.buf[end + 1] == 0:
                break
            end += 2
        try:
            return self.buf[o:end].decode('utf-16-le')
        except UnicodeDecodeError:
            return None


def is_printable_ascii(s):
    return s is not None and len(s) > 0 and all(32 <= ord(c) < 127 for c in s)


def scan(img, verbose_reject=False):
    """Return list of dicts for every plausible FStaticBasicLogRecord."""
    base = img.base
    lo, hi = base, base + img.sizeofimage
    out = []
    rejects = {'fmt_range': 0, 'file_range': 0, 'line': 0, 'verb': 0,
               'dyn': 0, 'filestr': 0, 'fmtstr': 0}
    # candidate sections holding constexpr statics
    for (name, va, vs, rp, rs) in img.sections:
        if name not in ('.rdata', '.data', '_RDATA', '.rodata'):
            continue
        n = min(vs, rs)
        buf = img.buf
        # 8-byte aligned walk
        start = rp - (rp % 8) if rp % 8 else rp
        for o in range(rp, rp + n - 0x20, 8):
            fmt = struct.unpack_from('<Q', buf, o)[0]
            if not (lo <= fmt < hi):
                continue
            fil = struct.unpack_from('<Q', buf, o + 8)[0]
            if not (lo <= fil < hi):
                rejects['file_range'] += 1
                continue
            line, verb = struct.unpack_from('<iI', buf, o + 0x10)
            if not (0 < line < 200000):
                rejects['line'] += 1
                continue
            if not (1 <= verb <= 7):
                rejects['verb'] += 1
                continue
            dyn = struct.unpack_from('<Q', buf, o + 0x18)[0]
            if not (lo <= dyn < hi):
                rejects['dyn'] += 1
                continue
            filerva = fil - base
            if img.sec_of(filerva) != '.rdata':
                rejects['file_range'] += 1
                continue
            fs = img.cstr(filerva)
            if not is_printable_ascii(fs) or ('.cpp' not in fs and '.h' not in fs and '.inl' not in fs):
                rejects['filestr'] += 1
                continue
            dynsec = img.sec_of(dyn - base)
            if dynsec not in ('.data', '.bss', None):
                rejects['dyn'] += 1
                continue
            fmtstr = img.wstr(fmt - base)
            if fmtstr is None:
                rejects['fmtstr'] += 1
                continue
            out.append(dict(rec_rva=(rp and (va + (o - rp))), sec=name,
                            fmt_rva=fmt - base, fmt=fmtstr,
                            file=fs, line=line, verb=verb,
                            dyn_rva=dyn - base))
    return out, rejects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default=DUMP)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--file')
    ap.add_argument('--fmt')
    ap.add_argument('--csv')
    a = ap.parse_args()

    img = Image(a.dump)
    sys.stderr.write("image %s base=0x%X sizeofimage=0x%X\n" %
                     (os.path.basename(a.dump), img.base, img.sizeofimage))
    recs, rejects = scan(img)
    sys.stderr.write("found %d FStaticBasicLogRecord candidates\n" % len(recs))
    sys.stderr.write("rejects: %s\n" % rejects)

    if a.all:
        from collections import Counter
        c = Counter(r['verb'] for r in recs)
        print("VERBOSITY HISTOGRAM (whole image)")
        for k in sorted(c):
            print("  %-12s %6d" % (VERB.get(k, k), c[k]))
        print("  TOTAL        %6d" % len(recs))
        loki = [r for r in recs if '\\Loki\\Source\\' in r['file']]
        print("  in \\Loki\\Source\\: %d" % len(loki))

    sel = recs
    if a.file:
        sel = [r for r in sel if a.file.lower() in r['file'].lower()]
    if a.fmt:
        sel = [r for r in sel if a.fmt.lower() in (r['fmt'] or '').lower()]
    if a.file or a.fmt:
        print("\nfound %d matching record(s)" % len(sel))
        for r in sorted(sel, key=lambda x: x['line']):
            print("  rec@0x%08X  %-11s line %-6d %s" %
                  (r['rec_rva'], VERB.get(r['verb'], r['verb']), r['line'],
                   os.path.basename(r['file'])))
            print("      fmt@0x%08X  %r" % (r['fmt_rva'], r['fmt']))

    if a.csv:
        import csv
        with open(a.csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['rec_rva', 'sec', 'verbosity', 'line', 'file', 'fmt_rva', 'fmt', 'dyn_rva'])
            for r in recs:
                w.writerow(['0x%08X' % r['rec_rva'], r['sec'], VERB.get(r['verb'], r['verb']),
                            r['line'], r['file'], '0x%08X' % r['fmt_rva'], r['fmt'],
                            '0x%08X' % r['dyn_rva']])
        sys.stderr.write("wrote %s\n" % a.csv)


if __name__ == '__main__':
    main()
