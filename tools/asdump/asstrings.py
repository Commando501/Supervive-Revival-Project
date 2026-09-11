#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
asstrings.py -- validated length-prefixed string extractor for
SUPERVIVE's PrecompiledScript.Cache (UE-Angelscript).

STRING ENCODING (validated on 10,834 strings; see spec):
    u32 len (LE)  followed by  len bytes
    The string is ALWAYS NUL-terminated on disk.  Two writers are in play:
      form A (len INCLUDES the NUL): body[len-1] == 0            -> 350 hits
      form B (len EXCLUDES the NUL): body[len]   == 0 (extra)    -> 10,484 hits
    A candidate with NEITHER trailing NUL is a FALSE POSITIVE (all 315 such
    hits are 1-2 char runs inside pointer/int fields).  Requiring the NUL is
    therefore the validation rule.

stdlib only, read-only.
"""
import struct, sys, os, re, csv, collections

CACHE = r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache'
PRINTABLE = frozenset(range(0x20, 0x7f))


def read_string(data, off):
    """Read a length-prefixed string at `off`.  Returns (text, next_off) or None.
    Implements the exact NUL rule above."""
    if off + 4 > len(data):
        return None
    ln = struct.unpack_from('<I', data, off)[0]
    if ln == 0:
        return ('', off + 4)                     # empty string: no NUL written
    if ln > 0x100000 or off + 4 + ln > len(data):
        return None
    body = data[off + 4:off + 4 + ln]
    if body[-1] == 0:                            # form A
        core, end = body[:-1], off + 4 + ln
    elif off + 4 + ln < len(data) and data[off + 4 + ln] == 0:   # form B
        core, end = body, off + 4 + ln + 1
    else:
        return None
    if core and not all(b in PRINTABLE for b in core):
        return None
    return (core.decode('latin1'), end)


def scan_all(data, minlen=1):
    """Greedy left-to-right validated scan.  Yields (off, text, form, total_bytes)."""
    out = []
    i, n = 0, len(data)
    while i + 4 <= n:
        ln = struct.unpack_from('<I', data, i)[0]
        if minlen <= ln <= 8192 and i + 4 + ln <= n:
            body = data[i + 4:i + 4 + ln]
            form = None
            if body[-1] == 0 and all(b in PRINTABLE for b in body[:-1]) and len(body) > 1:
                core, form, end = body[:-1], 'A', i + 4 + ln
            elif (i + 4 + ln < n and data[i + 4 + ln] == 0
                  and all(b in PRINTABLE for b in body)):
                core, form, end = body, 'B', i + 4 + ln + 1
            if form:
                out.append((i, core.decode('latin1'), form, end - i))
                i = end
                continue
        i += 1
    return out


# ---------------------------------------------------------------- classification
TAGRE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$')
DECLRE = re.compile(r'[(),]')

def classify(s):
    if not s:
        return 'empty'
    if s.endswith('.as'):
        return 'source_path'
    if s.startswith('/Game/') or s.startswith('/Script/') or s.startswith('/Engine/'):
        return 'asset_path'
    if s.startswith('::'):
        return 'namespaced_ident'
    if '(' in s and ')' in s:
        return 'declaration'
    if ' ' in s or '\t' in s:
        return 'literal_or_text'
    if TAGRE.match(s):
        return 'dotted_name'
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', s):
        return 'identifier'
    return 'other'


def main():
    data = open(CACHE, 'rb').read()
    rows = scan_all(data)
    print('file: %d bytes' % len(data))
    print('validated strings: %d' % len(rows))
    byform = collections.Counter(r[2] for r in rows)
    print('forms:', dict(byform))
    cov = sum(r[3] for r in rows)
    print('bytes in string records: %d (%.1f%%)' % (cov, 100.0 * cov / len(data)))
    cls = collections.Counter(classify(r[1]) for r in rows)
    for k, v in cls.most_common():
        print('  %-18s %6d' % (k, v))
    uniq = collections.Counter(r[1] for r in rows)
    print('unique strings: %d' % len(uniq))
    return rows, data


if __name__ == '__main__':
    main()
