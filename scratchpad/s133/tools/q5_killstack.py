#!/usr/bin/env python
"""q5_killstack.py -- THE LEAD CLAUDE.md ASKED FOR, ALREADY ON DISK.

CLAUDE.md (FK-31 / FK-10 Wall #7): "If the jump returns instead of faulting, the process may
survive AND THE STACK NAMES THE CALLER -- the protector code that decided to kill, which is
what FK-10's Wall #7 has been hunting."  That was written as a plan needing an injected
VirtualAlloc arm and a live launch.

But the crashpad minidump already carries the FAULTING THREAD'S STACK.  At the moment of an
EXECUTE fault on the first instruction at runtime.dll+1, RSP still points at whatever the
transfer pushed.  If it was a CALL, [RSP] IS the return address in the caller.

This walks the crashed thread's stack out of MemoryList/Memory64List and classifies every
qword by which mapping it falls in -- with special attention to the two hidden runtime.dll
views found in Q1/Q1b.

POSITIVE CONTROL: the same scan must find plenty of pointers into KNOWN modules (ntdll,
kernel32, the game image) on the same stack.  A stack that yields zero recognisable
addresses means the stack was not captured and the runtime.dll null is uninterpretable,
not negative.

usage: python q5_killstack.py [dump.dmp ...]      (default: one per boot session)
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402


def memranges(d):
    rs = []
    if 5 in d.streams:
        for _ds, rva in d.streams[5]:
            n = struct.unpack('<I', d._at(rva, 4))[0]
            blob = d._at(rva + 4, n * 16)
            for i in range(n):
                sa = struct.unpack_from('<Q', blob, i * 16)[0]
                sz, sr = struct.unpack_from('<II', blob, i * 16 + 8)
                rs.append((sa, sz, sr))
    if 9 in d.streams:
        for _ds, rva in d.streams[9]:
            nr, basrva = struct.unpack('<QQ', d._at(rva, 16))
            cur = basrva
            hdr = d._at(rva + 16, nr * 16)
            for i in range(nr):
                sa, sz = struct.unpack_from('<QQ', hdr, i * 16)
                rs.append((sa, sz, cur))
                cur += sz
    rs.sort()
    return rs


def read(d, rs, addr, n):
    for sa, sz, sr in rs:
        if sa <= addr and addr + n <= sa + sz:
            return d._at(sr + (addr - sa), n)
    return None


def classify(d, mi_groups, a):
    m = d.modof(a)
    if m:
        return "%s+0x%X" % (m[0], m[1])
    for ab, span, hid in mi_groups:
        if ab <= a < ab + span:
            return "HIDDEN@0x%X+0x%X" % (ab, a - ab)
    return None


def show(path):
    d = Dump(path)
    if not d.ok or not d.exc:
        print("  parse fail", path, d.err)
        return
    rs = memranges(d)
    mi = fast_meminfo(path, d.streams)
    groups = {}
    for (b, a, ap, sz, st, pr, ty) in mi:
        if ty == 0x1000000:
            groups[a] = groups.get(a, 0) + sz
    hid = [(a, s, True) for a, s in groups.items() if not d.modof(a)]
    rsp = d.regs.get('rsp', 0)
    print("dump : %s" % path)
    print("  exc 0x%08X addr 0x%X  rip 0x%X  rsp 0x%X  tid %d"
          % (d.exc['code'], d.exc['addr'], d.rip or 0, rsp, d.exc['tid']))
    print("  hidden MEM_IMAGE allocs: %s" % [(hex(a), hex(s)) for a, s, _ in sorted(hid)])
    # is the crashed thread's stack present?
    th = [t for t in d.threads if t['tid'] == d.exc['tid']]
    if th:
        t = th[0]
        print("  crashed-thread MINIDUMP_THREAD: Stack.StartOfMemoryRange=0x%X size=0x%X"
              % (t['stack'], t['stacksize']))
    cov = [(sa, sz) for sa, sz, _ in rs if sa <= rsp < sa + sz]
    print("  MemoryList ranges: %d ; range covering RSP: %s"
          % (len(rs), [(hex(a), hex(s)) for a, s in cov]))
    if not cov:
        print("  !! RSP NOT COVERED -- the stack was not captured for this thread.")
        print("     (this null is uninterpretable, not negative)")
        return
    sa, sz = cov[0]
    depth = min(0x800, sa + sz - rsp)
    b = read(d, rs, rsp, depth)
    if b is None:
        print("  !! read failed")
        return
    print("  --- first 0x%X bytes at RSP, qwords that resolve to a mapping ---" % depth)
    known = hidden = 0
    for i in range(0, len(b) - 7, 8):
        q = struct.unpack_from('<Q', b, i)[0]
        if q < 0x10000:
            continue
        c = classify(d, sorted(hid), q)
        if c:
            if c.startswith('HIDDEN'):
                hidden += 1
                print("     [rsp+0x%03X] 0x%016X  ** %s" % (i, q, c))
            else:
                known += 1
                if known <= 12:
                    print("     [rsp+0x%03X] 0x%016X     %s" % (i, q, c))
    print("  CONTROL: qwords resolving to a LOADED module: %d   (if 0, the scan is broken)"
          % known)
    print("  qwords resolving into a HIDDEN image        : %d" % hidden)


if __name__ == '__main__':
    paths = sys.argv[1:]
    if not paths:
        rows = list(csv.DictReader(
            open('scratchpad/s133/evidence/md_sweep.tsv', encoding='utf-8'), delimiter='\t'))
        seen = {}
        for r in rows:
            if r['killalloc_base'] and r['ntdll'] not in seen:
                seen[r['ntdll']] = r['first_path']
        paths = list(seen.values())
    for p in paths:
        show(p)
        print()
