#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk13natreg.py -- recover `name -> exec-thunk RVA` for every NATIVE UFunction of a
class, entirely OFFLINE, out of the runtime-initialised native-registration array.

HOW (all measured, see selftest):
  `<Class>::GetPrivateStaticClass` passes `StaticRegisterNatives<Class>` as arg4
  (r9).  That function's fast path is
        mov  r8d, <Count>
        lea  rdx, [rip + <Array>]
        jmp  FNativeFunctionRegistrar::RegisterFunctions
  so Count and Array fall straight out of the last such pair before the tail jmp.

⚠ THE ARRAY STRIDE IN THIS BUILD IS 0x48 (72 B), NOT the stock
  `FNameNativePtrPair`'s 16 B.  That was MEASURED, not assumed: at stride 0x48 all
  55 UCheatManager entries decode to real UCheatManager UFunction names and the
  only two UFunctions missing are exactly the two that carry no FUNC_Native
  (`ReceiveInitCheatManager`, `ReceiveEndPlay`) -- a self-validating check that a
  wrong stride cannot pass.  Fields used: +0x00 const char* Name, +0x08 thunk.
  The array lives in `.data` and is filled at runtime, so it is only readable
  because dumpimage snapshots a LIVE process; a cold on-disk exe would have zeros.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fk13img as FI
import fk13uht as U
import fk13grade as G

STRIDE = 0x48


def registrar_of(class_name, uht=None):
    """-> (register_fn_rva, array_rva, count) or (None, None, None)."""
    u = uht or U.UHT()
    recs = u.scan_class_registrations()
    r = recs.get(class_name)
    if not r:
        return None, None, None
    im = FI.img()
    b, e, src = G.extent(r['inner'])
    reg = None
    for a, mn, ops, sz in G.disasm(b, e):
        m = re.match(r'^r9, \[rip ([+-]) (0x[0-9a-f]+)\]$', ops)
        if mn == 'lea' and m:
            reg = a + sz + (int(m.group(2), 16) if m.group(1) == '+' else -int(m.group(2), 16))
    if reg is None:
        return None, None, None
    b, e, src = G.extent(reg)
    cnt = arr = None
    for a, mn, ops, sz in G.disasm(b, e):
        m = re.match(r'^r8d, (0x[0-9a-f]+|\d+)$', ops)
        if mn == 'mov' and m:
            cnt = int(m.group(1), 0)
        m = re.match(r'^rdx, \[rip ([+-]) (0x[0-9a-f]+)\]$', ops)
        if mn == 'lea' and m:
            t = a + sz + (int(m.group(2), 16) if m.group(1) == '+' else -int(m.group(2), 16))
            if im.section_of(t) in ('.data', '.rdata'):
                arr = t
        if mn == 'jmp' and ops.startswith('0x') and cnt and arr:
            break
    return reg, arr, cnt


def natives(class_name, uht=None):
    """-> dict name -> thunk RVA."""
    im = FI.img()
    reg, arr, cnt = registrar_of(class_name, uht)
    if arr is None:
        return {}, (reg, arr, cnt)
    out = {}
    for i in range(cnt or 0):
        o = arr + i * STRIDE
        n = im.ptr(o)
        nm = im.cstr(n, 80) if n is not None else None
        th = im.ptr(o + 8)
        if nm:
            out[nm] = th
    return out, (reg, arr, cnt)


def selftest():
    u = U.UHT()
    fns = u.scan_functions()
    ok = fail = 0
    for cls in ('UCheatManager', 'APlayerController', 'UGameplayStatics',
                'UKismetSystemLibrary'):
        want = {f['name'] for f in fns if f['owner'] == cls and (f['flags'] & 0x400)}
        got, meta = natives(cls, u)
        stray = set(got) - {f['name'] for f in fns if f['owner'] == cls}
        miss = want - set(got)
        good = not stray and not miss
        ok += good
        fail += (not good)
        print('  %-22s reg=%s arr=%s count=%s  decoded=%d  FUNC_Native=%d  '
              'stray=%d missing=%d  %s'
              % (cls, ('%#x' % meta[0]) if meta[0] else '-',
                 ('%#x' % meta[1]) if meta[1] else '-', meta[2], len(got),
                 len(want), len(stray), len(miss), 'OK' if good else 'FAIL'))
        if stray:
            print('      stray  :', sorted(stray)[:8])
        if miss:
            print('      missing:', sorted(miss)[:8])
    print('natreg selftest %d ok / %d fail' % (ok, fail))
    return fail == 0


if __name__ == '__main__':
    FI.img()
    if len(sys.argv) > 1:
        u = U.UHT()
        got, meta = natives(sys.argv[1], u)
        print('%s : reg=%s array=%s count=%s' %
              (sys.argv[1], ('%#x' % meta[0]) if meta[0] else '-',
               ('%#x' % meta[1]) if meta[1] else '-', meta[2]))
        for nm in sorted(got):
            g = G.grade(got[nm])
            print('  %-46s %#010x %-16s %5d B' % (nm, got[nm], g['verdict'], g['size']))
    else:
        sys.exit(0 if selftest() else 1)
