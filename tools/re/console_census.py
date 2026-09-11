#!/usr/bin/env python
"""
console_census.py -- OFFLINE, CONTROLLED, multi-image, multi-encoding string census.

Written for FK-13 (lane 3, S114).  It exists to replace the S3 FOUND/ABSENT table in
`docs/dedicated-server-stub.md:541-556`, which was produced by an ASCII-only scan of a
binary whose .text/.rdata were still encrypted -- instance #N of this project's
"instrument-artifact" error mode.

Design rules baked in, because the project keeps paying for their absence:

  1. EVERY token is searched in BOTH UTF-16LE and ASCII, separately reported.
     (All behavioural strings in these binaries are UTF-16LE.)
  2. Every run carries POSITIVE CONTROLS in the same tool, same scope, same encoding.
     A zero for a probe token is only interpretable next to a non-zero control.
  3. Hits are reported as the FULL containing string, not the matched substring, so
     `Console` matching inside `EnableConsole120Fps` cannot be mistaken for a hit on
     the standalone name.  `exact` = the containing string equals the token.
  4. RVAs, not file offsets, are printed for on-disk PEs (file offset != RVA there).
     For usmapdump `dumpimage` output, file offset == RVA and the tool verifies it.

Usage
-----
  python console_census.py --images <img.json|auto> --tokens <tokens.txt> [--json out.json]
  python console_census.py --list-images
"""
import sys, os, json, struct, argparse, re

# ---------------------------------------------------------------- PE handling

class Image:
    def __init__(self, path, label):
        self.path = path
        self.label = label
        with open(path, 'rb') as f:
            self.data = f.read()
        self.sections = []
        self.imagebase = 0
        self.flat = False          # True when file offset == RVA (dumpimage output)
        self._parse()

    def _parse(self):
        d = self.data
        if d[:2] != b'MZ':
            raise ValueError('not a PE: %s' % self.path)
        pe = struct.unpack_from('<I', d, 0x3C)[0]
        if d[pe:pe+4] != b'PE\0\0':
            raise ValueError('bad PE sig: %s' % self.path)
        nsec = struct.unpack_from('<H', d, pe+6)[0]
        optsz = struct.unpack_from('<H', d, pe+20)[0]
        opt = pe + 24
        magic = struct.unpack_from('<H', d, opt)[0]
        if magic == 0x20b:
            self.imagebase = struct.unpack_from('<Q', d, opt+24)[0]
        else:
            self.imagebase = struct.unpack_from('<I', d, opt+28)[0]
        sh = opt + optsz
        flat = True
        for i in range(nsec):
            o = sh + i*40
            name = d[o:o+8].rstrip(b'\0').decode('latin1')
            vsize = struct.unpack_from('<I', d, o+8)[0]
            vaddr = struct.unpack_from('<I', d, o+12)[0]
            rsize = struct.unpack_from('<I', d, o+16)[0]
            raddr = struct.unpack_from('<I', d, o+20)[0]
            self.sections.append((name, vaddr, vsize, raddr, rsize))
            if raddr != vaddr:
                flat = False
        self.flat = flat

    def off_to_rva(self, off):
        if self.flat:
            return off
        for name, vaddr, vsize, raddr, rsize in self.sections:
            if rsize and raddr <= off < raddr + rsize:
                return vaddr + (off - raddr)
        return None

    def sect_of_off(self, off):
        if self.flat:
            for name, vaddr, vsize, raddr, rsize in self.sections:
                if vaddr <= off < vaddr + max(vsize, rsize):
                    return name
            return '?'
        for name, vaddr, vsize, raddr, rsize in self.sections:
            if rsize and raddr <= off < raddr + rsize:
                return name
        return '?'


# ---------------------------------------------------------------- string expansion

PRINT_ASCII = set(range(0x20, 0x7f))

def expand_ascii(d, i, n, limit=200):
    s = i
    while s > 0 and d[s-1] in PRINT_ASCII and i - s < limit:
        s -= 1
    e = i + n
    while e < len(d) and d[e] in PRINT_ASCII and e - (i+n) < limit:
        e += 1
    return d[s:e].decode('ascii', 'replace'), s

def expand_wide(d, i, n, limit=400):
    # walk back in 2-byte steps while [c,0x00] with c printable
    s = i
    while s >= 2 and d[s-1] == 0 and d[s-2] in PRINT_ASCII and i - s < limit:
        s -= 2
    e = i + n
    while e + 1 < len(d) and d[e+1] == 0 and d[e] in PRINT_ASCII and e - (i+n) < limit:
        e += 2
    return d[s:e].decode('utf-16-le', 'replace'), s


def find_all(d, needle, cap=4000):
    out, start = [], 0
    while len(out) < cap:
        i = d.find(needle, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out


def census_token(img, tok, cap=400):
    d = img.data
    res = {'wide': [], 'ascii': [], 'wide_n': 0, 'ascii_n': 0,
           'wide_exact': 0, 'ascii_exact': 0}

    wb = tok.encode('utf-16-le')
    hits = find_all(d, wb, cap)
    res['wide_n'] = len(hits)
    seen = set()
    for i in hits:
        full, s = expand_wide(d, i, len(wb))
        rva = img.off_to_rva(s)
        exact = (full == tok)
        if exact:
            res['wide_exact'] += 1
        key = (full, rva)
        if key in seen:
            continue
        seen.add(key)
        if len(res['wide']) < 40:
            res['wide'].append({'rva': rva, 'off': s, 'sect': img.sect_of_off(s),
                                'full': full, 'exact': exact})

    ab = tok.encode('ascii')
    hits = find_all(d, ab, cap)
    # an ASCII hit that is really the first half of a wide hit would show
    # d[i+1]==0; count those separately so we never double-report.
    real_ascii = []
    for i in hits:
        if i + len(ab) < len(d) and d[i+1] == 0 and (len(ab) < 2 or d[i+3] == 0):
            continue  # looks like UTF-16LE, not ASCII
        real_ascii.append(i)
    res['ascii_n'] = len(real_ascii)
    seen = set()
    for i in real_ascii:
        full, s = expand_ascii(d, i, len(ab))
        rva = img.off_to_rva(s)
        exact = (full == tok)
        if exact:
            res['ascii_exact'] += 1
        key = (full, rva)
        if key in seen:
            continue
        seen.add(key)
        if len(res['ascii']) < 40:
            res['ascii'].append({'rva': rva, 'off': s, 'sect': img.sect_of_off(s),
                                 'full': full, 'exact': exact})
    return res


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', action='append', default=[],
                    help='label=path ; repeatable')
    ap.add_argument('--tokens', required=True)
    ap.add_argument('--json')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    imgs = []
    for spec in a.image:
        label, _, path = spec.partition('=')
        imgs.append(Image(path, label))

    toks = []
    for line in open(a.tokens, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        kind = 'probe'
        if line.startswith('!'):
            kind, line = 'CONTROL', line[1:]
        toks.append((line, kind))

    out = {'images': [], 'rows': []}
    for im in imgs:
        out['images'].append({'label': im.label, 'path': im.path,
                              'imagebase': hex(im.imagebase), 'flat': im.flat,
                              'size': len(im.data)})
        print('IMAGE %-14s base=%#x flat=%s size=%d  %s'
              % (im.label, im.imagebase, im.flat, len(im.data), im.path))
    print()

    hdr = 'TOKEN'.ljust(30) + 'KIND'.ljust(9)
    for im in imgs:
        hdr += (im.label + ':W/A').ljust(18)
    print(hdr)
    print('-' * len(hdr))

    for tok, kind in toks:
        row = {'token': tok, 'kind': kind, 'per_image': {}}
        line = tok.ljust(30) + kind.ljust(9)
        for im in imgs:
            r = census_token(im, tok)
            row['per_image'][im.label] = r
            cell = '%d/%d' % (r['wide_n'], r['ascii_n'])
            if r['wide_exact'] or r['ascii_exact']:
                cell += ' *%d/%d' % (r['wide_exact'], r['ascii_exact'])
            line += cell.ljust(18)
        print(line)
        out['rows'].append(row)

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=1)
        print('\nwrote', a.json)

    print('\nLEGEND: W/A = UTF-16LE hits / ASCII hits (ASCII hits that are actually the')
    print('first byte-pair of a UTF-16LE string are excluded).  *X/Y = of those, how many')
    print('are EXACT standalone strings (containing string == token) rather than substrings.')


if __name__ == '__main__':
    main()
