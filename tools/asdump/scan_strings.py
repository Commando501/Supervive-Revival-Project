#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scan_strings.py -- brute-force scan for length-prefixed strings in
PrecompiledScript.Cache (SUPERVIVE / UE-Angelscript).

String encoding (established): (u32 len LE, char[len]).  NUL handling is
inconsistent between fields -- some lengths INCLUDE the trailing NUL, some
EXCLUDE it with a NUL following.  We record both forms and normalise.

stdlib only.
"""
import sys, os, struct, collections, json

CACHE = r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache'

PRINTABLE = set(range(0x20, 0x7f)) | {0x09, 0x0a, 0x0d}

def scan(data, minlen=1, maxlen=8192):
    """Yield (offset_of_len_field, declared_len, raw_bytes, had_trailing_nul_in_len,
    consumed_extra_nul)."""
    n = len(data)
    out = []
    i = 0
    while i + 4 <= n:
        ln = struct.unpack_from('<I', data, i)[0]
        if minlen <= ln <= maxlen and i + 4 + ln <= n:
            body = data[i+4:i+4+ln]
            # decide printability
            if ln >= 1 and body[-1] == 0:
                core = body[:-1]
                inner_nul = False
                trail = True
            else:
                core = body
                trail = False
            if core and all(b in PRINTABLE for b in core):
                # extra nul following?
                extra = (not trail) and (i+4+ln < n) and data[i+4+ln] == 0
                out.append((i, ln, core, trail, extra))
                i += 4 + ln + (1 if extra else 0)
                continue
        i += 1
    return out

def main():
    data = open(CACHE, 'rb').read()
    res = scan(data)
    print('file bytes: %d' % len(data))
    print('candidate strings: %d' % len(res))
    tot = sum(4 + r[1] + (1 if r[4] else 0) for r in res)
    print('bytes covered by strings: %d (%.1f%%)' % (tot, 100.0*tot/len(data)))
    # length-histogram of NUL convention
    c = collections.Counter()
    for off, ln, core, trail, extra in res:
        c[(trail, extra)] += 1
    print('NUL convention counts (len_includes_nul, extra_nul_after):', dict(c))
    return res, data

if __name__ == '__main__':
    main()
