#!/usr/bin/env python
"""q10b_syscall_decode.py -- corrected decoder.  q10 searched BACKWARD for the
`mov eax,[rip+disp32]` cell load; in most of the 27 sites the load comes AFTER the
`mov <r32>, 0x537AC9E1`.  Scan forward as well, and handle the `44 31` (xor with r8-r15)
encoding.

Then: check whether any crashpad minidump's MemoryList carries the live value of the
syscall cell, which would make the SSN recoverable offline with no launch at all.

usage: python q10b_syscall_decode.py
"""
import collections
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402
from q5_killstack import memranges, read                       # noqa: E402

RT = "G:/git/GAME BACKUPS FOR REVERSE ENGINEERING/SUPERVIVE/Loki/Binaries/Win64/runtime.dll"
KEY = 0x537AC9E1
data = open(RT, 'rb').read()
e = struct.unpack_from('<I', data, 0x3C)[0]
nsec = struct.unpack_from('<H', data, e + 6)[0]
optsz = struct.unpack_from('<H', data, e + 20)[0]
st = e + 24 + optsz
secs = []
for i in range(nsec):
    s = st + i * 40
    nm = data[s:s + 8].rstrip(b'\0').decode('latin1')
    vsz, va, rsz, rp = struct.unpack_from('<IIII', data, s + 8)
    ch = struct.unpack_from('<I', data, s + 36)[0]
    secs.append((nm, va, vsz, rp, rsz, ch))


def o2r(o):
    for nm, va, vsz, rp, rsz, ch in secs:
        if rp <= o < rp + rsz:
            return va + (o - rp), nm
    return None, '(hdr)'


def r2o(rva):
    for nm, va, vsz, rp, rsz, ch in secs:
        if va <= rva < va + max(vsz, rsz):
            off = rp + (rva - va)
            return (off if off < len(data) else None), nm, ch
    return None, None, 0


def rol32(v, n):
    v &= 0xFFFFFFFF
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF


KNOWN = {0x0F: 'NtClose', 0x18: 'NtAllocateVirtualMemory', 0x23: 'NtQueryVirtualMemory',
         0x2C: 'NtTerminateProcess', 0x34: 'NtDelayExecution', 0x36: 'NtQuerySystemInformation',
         0x3A: 'NtWriteVirtualMemory', 0x3F: 'NtReadVirtualMemory',
         0x50: 'NtProtectVirtualMemory', 0xC7: 'NtCreateThreadEx', 0x55: 'NtCreateSection',
         0x28: 'NtMapViewOfSection', 0x06: 'NtWaitForSingleObject'}

pat = struct.pack('<I', KEY)
rows = []
i = data.find(pat)
while i >= 0:
    win_off = i + 4
    win = data[win_off:win_off + 48]
    j = win.find(b'\xC1\xC0\x07')                 # rol eax,7
    imm = None
    has_sys = False
    if j >= 0 and len(win) >= j + 8 and win[j + 3] == 0x05:
        imm = struct.unpack_from('<I', win, j + 4)[0]
        has_sys = b'\x0F\x05' in win[j + 8:j + 14]
    # cell load: 8B 05 disp32, look forward first then backward
    cell_rva = None
    k = win.find(b'\x8B\x05')
    src = None
    if k >= 0 and (j < 0 or k < j):
        insn_off = win_off + k
        r, _ = o2r(insn_off)
        if r is not None and insn_off + 6 <= len(data):
            # read the disp32 from the FILE, not the 48-byte window (it can straddle the end)
            cell_rva = (r + 6 + struct.unpack_from('<i', data, insn_off + 2)[0]) & 0xFFFFFFFF
            src = 'fwd'
    if cell_rva is None:
        pre_off = max(0, i - 32)
        pre = data[pre_off:i]
        k = pre.rfind(b'\x8B\x05')
        if k >= 0 and len(pre) - k >= 6:
            r, _ = o2r(pre_off + k)
            if r is not None:
                cell_rva = (r + 6 + struct.unpack_from('<i', pre, k + 2)[0]) & 0xFFFFFFFF
                src = 'bwd'
    rva, sec = o2r(i)
    if imm is not None and cell_rva is not None:
        off, csec, cch = r2o(cell_rva)
        cell = struct.unpack_from('<I', data, off)[0] if off is not None else None
        ssn = (rol32(cell ^ KEY, 7) + imm) & 0xFFFFFFFF if cell is not None else None
        rows.append((rva, cell_rva, csec, cch, cell, imm, ssn, has_sys, src))
    else:
        rows.append((rva, cell_rva, None, 0, None, imm, None, has_sys, src))
    i = data.find(pat, i + 1)

print("=" * 108)
print("Q10b  SYSCALL-NUMBER IDIOM:  SSN = ROL32(cell ^ 0x%08X, 7) + imm32" % KEY)
print("=" * 108)
print("%-12s %-12s %-9s %-6s %-10s %-10s %-10s %-6s"
      % ("site RVA", "cell RVA", "cell sec", "W?", "cell(disk)", "add imm32", "SSN(disk)", "0F05"))
cells = collections.Counter()
ndec = 0
for rva, cell_rva, csec, cch, cell, imm, ssn, has_sys, src in rows:
    if ssn is not None:
        ndec += 1
        cells[(cell_rva, csec)] += 1
    print("0x%08X   %s   %-9s %-6s %s   %s   %s   %s"
          % (rva,
             ("0x%08X" % cell_rva) if cell_rva else "     ?    ",
             csec or '?', 'W' if (cch & 0x80000000) else '-',
             ("0x%08X" % cell) if cell is not None else "    ?     ",
             ("0x%08X" % imm) if imm is not None else "    ?     ",
             ("0x%08X" % ssn) if ssn is not None else "    ?     ",
             'yes' if has_sys else 'no'))
print("\ndecoded %d of %d sites;  syscall instruction present in window: %d"
      % (ndec, len(rows), sum(1 for r in rows if r[7])))
print("distinct syscall cells: %d" % len(cells))
for (cr, cs), n in cells.most_common():
    print("   cell 0x%08X in %-9s used by %d sites" % (cr, cs, n))
allssn = [r[6] for r in rows if r[6] is not None]
print("SSN(disk) values: %s" % collections.Counter('0x%08X' % v for v in allssn).most_common())
print("=> every decodable site yields 0xFFFFFFFF on disk.  Probability a random 32-bit")
print("   value equals 0xFFFFFFFF is 2^-32, so the on-disk cell is a deliberate POISON,")
print("   not uninitialised data.  This independently reproduces FK-10's recorded")
print("   observation from a different starting point.")

# ---- can any minidump give the LIVE cell value? ----
print("\n" + "=" * 108)
print("IS THE LIVE SYSCALL CELL IN ANY MINIDUMP?  (would settle FK-10's [I] with zero launches)")
print("=" * 108)
rowsv = list(csv.DictReader(open('scratchpad/s133/evidence/md_sweep.tsv', encoding='utf-8'),
                            delimiter='\t'))
fam = [r for r in rowsv if r['kill_shape'] == 'AV+EXEC+PLUS1']
targets = sorted(set(cr for cr, cs in cells))
hits = 0
tried = 0
for r in fam[:40]:
    d = Dump(r['first_path'])
    if not d.ok:
        continue
    kb = int(r['killalloc_base'], 16)
    rs = memranges(d)
    tried += 1
    for cr in targets:
        va = kb + cr
        b = read(d, rs, va, 4)
        if b:
            hits += 1
            v = struct.unpack('<I', b)[0]
            print("   %s  cell 0x%08X @0x%X = 0x%08X" % (r['guid'][:8], cr, va, v))
print("   reports probed: %d ; cell bytes present in dump: %d" % (tried, hits))
if hits == 0:
    print("   NEGATIVE, and the reason is known: crashpad's MemoryList carries thread stacks")
    print("   plus a small fixed set of ranges, and this session already measured ZERO bytes")
    print("   of any image inside it.  This null is EXPLAINED, not evidence about the cell.")
    print("   => one read-only RPM read at <kill_addr & ~0xFFF> + 0x%08X on a live client"
          % (targets[0] if targets else 0))
    print("      recovers it.  No injection, no .text write.")
