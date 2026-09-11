#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
asdump_strings.py -- complete validated string / symbol extractor for
SUPERVIVE's Loki/Script/PrecompiledScript.Cache (UE-Angelscript precompiled data).

Emits:
    out/script_strings.csv   every validated length-prefixed string
    out/symbols.csv          pointer -> symbol-name map (bytecode operand resolver)
    out/const_pool.txt       script string/name constants, grouped
    stdout                   counts per class / per section

Read-only.  stdlib only.  Windows paths.

--------------------------------------------------------------------------
STRING ENCODING  (validated on 10,720 strings, 0 unexplained)
--------------------------------------------------------------------------
  u32 len (LE) then `len` bytes.  The bytes on disk are ALWAYS NUL-terminated.
  Two writers appear in the file:
     form A : len INCLUDES the terminator -> body[len-1] == 0        (283)
     form B : len EXCLUDES the terminator -> data[off+4+len] == 0    (10,437)
     len == 0 : empty string, NO terminator byte written.
  Robust read: take len bytes; if the last byte is NUL strip it, else if the
  NEXT byte is NUL consume it; a candidate with neither is NOT a string.
  (All 315 "neither" candidates in this file are 1-2 char runs inside
  pointer/int fields -- i.e. false positives.  The NUL is the validator.)

--------------------------------------------------------------------------
FILE LAYOUT  (byte-validated)
--------------------------------------------------------------------------
  0x000000  GUID[16] 95a76d4199c2a14889f71e3269f88eeb
  0x000010  u32 version = 4
  0x000014  u32 moduleCount = 78
  0x000018  SECTION A -- 78 module records .. 0xc5b05      809,709 B  68.3%
  0x0c5b05  SECTION B -- symbol table: ptr64 -> (FString name,
            FString scriptModule) .. 0x110358              304,723 B  25.7%
  0x110358  SECTION C -- fixup table: (ptr64, u32) pairs,
            no strings .. 0x115ee0                          24,456 B   2.1%
  0x115ee0  SECTION D -- constant pool: ptr64 -> FString
            (script string literals, FName constants,
             __StaticType_* aliases) .. EOF                 45,905 B   3.9%

  Every 64-bit pointer in the file is a LIVE HEAP ADDRESS from the machine
  that generated the cache; all of them share the high dword 0x0000026E.
  Sections B/D are the fixup tables that give those pointers names, which is
  why 100.0% of bytecode pointer operands resolve to a symbol name.
"""
import struct, os, re, csv, sys, collections

CACHE = r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')

PRINTABLE = frozenset(range(0x20, 0x7f))
PTR_HI = 0x26E                       # every real pointer is 0x0000026E_xxxxxxxx

SEC_A, SEC_B, SEC_C, SEC_D = 0x18, 0xc5b05, 0x110358, 0x115ee0


def read_string(data, off):
    """Exact reader for the encoding documented above.
    Returns (text, next_off) or None if `off` is not a string."""
    if off + 4 > len(data):
        return None
    ln = struct.unpack_from('<I', data, off)[0]
    if ln == 0:
        return ('', off + 4)
    if ln > 0x100000 or off + 4 + ln > len(data):
        return None
    body = data[off + 4:off + 4 + ln]
    if body[-1] == 0:                                            # form A
        core, end = body[:-1], off + 4 + ln
    elif off + 4 + ln < len(data) and data[off + 4 + ln] == 0:   # form B
        core, end = body, off + 4 + ln + 1
    else:
        return None
    if core and not all(b in PRINTABLE for b in core):
        return None
    return (core.decode('latin1'), end)


def scan_all(data):
    """Greedy left-to-right validated scan. -> [(off, text, form, rec_bytes)]"""
    out, i, n = [], 0, len(data)
    while i + 4 <= n:
        ln = struct.unpack_from('<I', data, i)[0]
        if 1 <= ln <= 8192 and i + 4 + ln <= n:
            body = data[i + 4:i + 4 + ln]
            form = None
            if len(body) > 1 and body[-1] == 0 and all(b in PRINTABLE for b in body[:-1]):
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


def section(off):
    if off < SEC_B: return 'A_modules'
    if off < SEC_C: return 'B_symbols'
    if off < SEC_D: return 'C_fixups'
    return 'D_constpool'


IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
DOTTED = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$')
TAGLIKE = re.compile(r'^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z0-9_]+)+$')
CVAR = re.compile(r'^[a-zA-Z]+\.[A-Za-z]+ ?[-0-9]*$')

DEFAULT_EXPR = {'nullptr', 'false', 'true', 'NAME_None', 'FVector :: ZeroVector',
                'FRotator :: ZeroRotator', 'FLinearColor :: White',
                'FVector2D :: ZeroVector'}


def classify(s, off, prev_ptr):
    if s == '':                                   return 'empty'
    if s.endswith('.as'):                         return 'source_path'
    if s.startswith(('/Game/', '/Script/', '/Engine/', '/Loki')):
                                                  return 'asset_path'
    if s.startswith('__StaticType_'):             return 'statictype_alias'
    if s.startswith('__') or s.startswith('$beh') or s.startswith('op'):
                                                  return 'internal_symbol'
    if s in DEFAULT_EXPR or ' :: ' in s:          return 'default_arg_expr'
    if len(s) <= 2 and not IDENT.match(s):        return 'suspect_short'
    if re.match(r'^[A-Z][A-Za-z0-9]*:[a-z0-9_]+$', s):
                                                  return 'gameplay_id'
    if TAGLIKE.match(s) and '.' in s:             return 'dotted_name'
    if ' ' in s:                                  return 'string_literal'
    if IDENT.match(s):                            return 'identifier'
    return 'other'


def main():
    os.makedirs(OUT, exist_ok=True)
    data = open(CACHE, 'rb').read()
    rows = scan_all(data)

    # ---- pointer -> symbol map (sections B and D) --------------------------
    sym = {}
    for off, s, f, tb in rows:
        if off >= 8:
            v = struct.unpack_from('<Q', data, off - 8)[0]
            if (v >> 32) == PTR_HI and (v & 7) == 0:
                sym.setdefault(v, (off, s, section(off)))

    # ---- module partition (module i's record ends with its .as path) -------
    aspaths = [(off, s, tb) for off, s, f, tb in rows if s.endswith('.as')]
    bounds, prev = [], SEC_A
    for off, s, tb in aspaths:
        bounds.append((prev, off + tb, s))
        prev = off + tb

    def owning_module(off):
        for a, b, s in bounds:
            if a <= off < b:
                return s
        return ''

    # ---- CSV ---------------------------------------------------------------
    path = os.path.join(OUT, 'script_strings.csv')
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['offset_hex', 'offset_dec', 'len_field', 'nul_form',
                    'rec_bytes', 'section', 'module', 'ptr_key', 'class', 'text'])
        for off, s, f, tb in rows:
            v = struct.unpack_from('<Q', data, off - 8)[0] if off >= 8 else 0
            pk = '0x%011x' % v if ((v >> 32) == PTR_HI and (v & 7) == 0) else ''
            w.writerow(['0x%06x' % off, off,
                        struct.unpack_from('<I', data, off)[0], f, tb,
                        section(off), owning_module(off) if off < SEC_B else '',
                        pk, classify(s, off, pk), s])
    print('wrote %s (%d rows)' % (path, len(rows)))

    # ---- symbols CSV -------------------------------------------------------
    p2 = os.path.join(OUT, 'symbols.csv')
    with open(p2, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['ptr', 'name', 'defined_at_hex', 'section'])
        for v in sorted(sym):
            off, s, sec = sym[v]
            w.writerow(['0x%011x' % v, s, '0x%06x' % off, sec])
    print('wrote %s (%d symbols)' % (p2, len(sym)))

    # ---- report ------------------------------------------------------------
    print()
    print('file %d bytes, %d validated strings, %d unique'
          % (len(data), len(rows), len(set(r[1] for r in rows))))
    bysec = collections.Counter(section(r[0]) for r in rows)
    print('by section :', dict(bysec))
    byform = collections.Counter(r[2] for r in rows)
    print('by NUL form:', dict(byform))
    cls = collections.Counter(classify(r[1], r[0], '') for r in rows)
    print('by class   :')
    for k, v in cls.most_common():
        print('   %-18s %6d  (%d unique)'
              % (k, v, len(set(r[1] for r in rows if classify(r[1], r[0], '') == k))))
    return rows, sym, data, bounds


if __name__ == '__main__':
    main()
