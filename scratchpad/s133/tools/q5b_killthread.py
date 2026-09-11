#!/usr/bin/env python
"""q5b_killthread.py -- follow-up to q5: the FK-31 crash stack is only ~0x200-0x600 bytes
deep and its bottom two frames are KERNEL32+0x17374 / ntdll+0x4CC91.  That is the signature
of a BRAND-NEW THREAD faulting on its FIRST instruction, not of a jump taken inside running
code.

TESTS RUN HERE
  T1  stack depth: RSP vs the top of the crashed thread's stack region.
  T2  POSITIVE CONTROL: do OTHER, healthy threads in the SAME dump also bottom out at
      KERNEL32+0x17374 / ntdll+0x4CC91?  If yes, those two ARE the thread-init frames and
      the crashed thread has nothing above them.
  T3  CONTRAST CONTROL: the 14 reports of the *other* family (our own catalog_store_fix
      heap-scan fault, addr&0xFFFF==0x205d) must show a DEEP stack with game frames -- if
      those look identical to the FK-31 ones, "shallow stack" is a dump-writer artifact.
  T4  registers at fault: a fresh thread entered via BaseThreadInitThunk has a very
      characteristic register state.
  T5  is the crashed TID the highest/newest TID in ThreadList?  Thread names (stream 24).

usage: python q5b_killthread.py
"""
import collections
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402
from q5_killstack import memranges, read                       # noqa: E402


def tnames(d):
    out = {}
    if 24 not in d.streams:
        return out
    ds, rva = d.streams[24][0]
    n = struct.unpack('<I', d._at(rva, 4))[0]
    if not n:
        return out
    elem = (ds - 4) // n
    blob = d._at(rva + 4, n * elem)
    for i in range(n):
        tid = struct.unpack_from('<I', blob, i * elem)[0]
        nr = struct.unpack_from('<Q', blob, i * elem + (8 if elem >= 16 else 4))[0]
        try:
            out[tid] = d._wstr(nr)
        except Exception:                                       # noqa: BLE001
            pass
    return out


def analyse(path, label):
    d = Dump(path)
    rs = memranges(d)
    nm = tnames(d)
    tid = d.exc['tid']
    th = {t['tid']: t for t in d.threads}
    t = th.get(tid)
    rsp = d.regs.get('rsp', 0)
    top = t['stack'] + t['stacksize'] if t else 0
    print("\n%s  %s" % (label, os.path.basename(path)))
    print("  exc addr 0x%X  tid %d  name=%r" % (d.exc['addr'], tid, nm.get(tid, '')))
    print("  T1 stack: region 0x%X..0x%X  RSP 0x%X  bytes above RSP = 0x%X  (%d qwords)"
          % (t['stack'], top, rsp, top - rsp, (top - rsp) // 8))
    # T4
    r = d.regs
    print("  T4 regs: rax=0x%X rcx=0x%X rdx=0x%X r8=0x%X r9=0x%X rbp=0x%X rdi=0x%X rsi=0x%X"
          % (r['rax'], r['rcx'], r['rdx'], r['r8'], r['r9'], r['rbp'], r['rdi'], r['rsi']))
    for k in ('rax', 'rcx', 'rdx', 'r8', 'r9', 'rbx', 'rdi', 'rsi'):
        m = d.modof(r[k])
        if m:
            print("         %s -> %s+0x%X" % (k, m[0], m[1]))
    # T2: bottom-of-stack frames of every OTHER thread with captured stack
    bots = collections.Counter()
    got = 0
    for tt in d.threads:
        if tt['tid'] == tid:
            continue
        tp = tt['stack'] + tt['stacksize']
        b = read(d, rs, max(tt['stack'], tp - 0x40), min(0x40, tt['stacksize']))
        if b is None:
            continue
        got += 1
        found = []
        for i in range(0, len(b) - 7, 8):
            q = struct.unpack_from('<Q', b, i)[0]
            m = d.modof(q)
            if m:
                found.append("%s+0x%X" % (m[0], m[1]))
        if found:
            bots[tuple(found)] += 1
    print("  T2 other threads with a captured stack tail: %d" % got)
    for k, n in bots.most_common(4):
        print("     %-3d threads bottom out at %s" % (n, ' , '.join(k)))
    # T5
    tids = sorted(x['tid'] for x in d.threads)
    print("  T5 crashed tid rank: %d of %d (1 = lowest tid).  tid=%d  max tid=%d"
          % (tids.index(tid) + 1, len(tids), tid, tids[-1]))


rows = list(csv.DictReader(open('scratchpad/s133/evidence/md_sweep.tsv', encoding='utf-8'),
                           delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))
fam = [r for r in rows if r['kill_shape'] == 'AV+EXEC+PLUS1']
other = [r for r in rows if r['exc_addr'] and int(r['exc_addr'], 16) & 0xFFFF == 0x205D]
print("=" * 100)
print("Q5b  IS THE FK-31 KILL A FRESHLY-CREATED THREAD?")
print("=" * 100)
print("FK-31-family reports: %d ; contrast family (our own 0x205d scan fault): %d"
      % (len(fam), len(other)))
seen = set()
for r in fam:
    if r['ntdll'] in seen:
        continue
    seen.add(r['ntdll'])
    analyse(r['first_path'], "[FK-31 boot %s]" % r['ntdll'])
print("\n" + "-" * 100)
print("T3  CONTRAST CONTROL -- our own catalog_store_fix heap-scan faults")
print("-" * 100)
for r in other[:3]:
    analyse(r['first_path'], "[0x205d]")
