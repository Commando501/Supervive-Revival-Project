#!/usr/bin/env python
"""q13_ssn_solve.py -- RECOVER THE PROTECTOR'S SYSCALL NUMBERS OFFLINE.

Every site computes   SSN = ROL32(K_i XOR cell, 7) + A_i
with K_i and A_i BAKED INTO THE CODE and per-site, and `cell` a single dword in packer2
patched at runtime (the disk value is poisoned so every site decodes to 0xFFFFFFFF).

Let x = ROL32(cell,7) and k_i = ROL32(K_i,7).  Because ROL32 is bitwise:
        SSN = (x XOR k_i) + A_i          for every site i sharing that cell.

So for a CANDIDATE service number s:
        x_i = (s - A_i) mod 2^32  XOR  k_i
and all sites on one cell must agree on x_i.  With N sites per cell that is N-1
independent 32-bit constraints, satisfied by chance with p = 2^-32 each.

x86-64 Windows service numbers live in roughly [0, 0x200).  Trying all 512 candidates and
demanding agreement across every site on the cell therefore either pins the SSN uniquely or
proves the method cannot decide -- with no process, no injection and no launch.

CONTROLS
  C1 the disk value MUST come out as the solution for s = 0xFFFFFFFF (that is what the
     poison encodes).  If the solver cannot reproduce that, the algebra is wrong.
  C2 candidate range is widened to [0,0x1000); any solution above 0x200 is reported so a
     spuriously-unique answer outside the plausible range is visible.
  C3 the number of cells that resolve uniquely is reported against the number that resolve
     ambiguously or not at all.

usage: python q13_ssn_solve.py
"""
import collections
import struct

RT = "G:/git/GAME BACKUPS FOR REVERSE ENGINEERING/SUPERVIVE/Loki/Binaries/Win64/runtime.dll"
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
    secs.append((nm, va, vsz, rp, rsz))


def o2r(o):
    for nm, va, vsz, rp, rsz in secs:
        if rp <= o < rp + rsz:
            return va + (o - rp), nm
    return None, '(hdr)'


def r2o(rva):
    for nm, va, vsz, rp, rsz in secs:
        if va <= rva < va + max(vsz, rsz):
            off = rp + (rva - va)
            return (off if off + 4 <= len(data) else None), nm
    return None, None


M = 0xFFFFFFFF


def rol(v, n=7):
    v &= M
    return ((v << n) | (v >> (32 - n))) & M


# ---- extract sites: STRICT form only, no fuzzy backward key search ----
sites = []          # (site_rva, cell_rva, K, A, form)
ROL = b'\xC1\xC0\x07'
i = data.find(ROL)
while i >= 0:
    if i + 8 <= len(data) and data[i + 3] == 0x05:
        A = struct.unpack_from('<I', data, i + 4)[0]
        if b'\x0F\x05' in data[i + 8:i + 40]:
            # form 1: B8 K ; 33 05 d32 ; ROL     (11 bytes before ROL)
            if i >= 11 and data[i - 11] == 0xB8 and data[i - 6] == 0x33 and data[i - 5] == 0x05:
                K = struct.unpack_from('<I', data, i - 10)[0]
                r, _ = o2r(i - 6)
                cell = (r + 6 + struct.unpack_from('<i', data, i - 4)[0]) & M
                rr, _ = o2r(i)
                sites.append((rr, cell, K, A, 'B8/33-05'))
                i = data.find(ROL, i + 1)
                continue
            # form 2: ... 8B 05 d32 ; 31 /r or 44 31 /r ; ROL
            xl = None
            if i >= 2 and data[i - 2] == 0x31:
                xl = i - 2
            elif i >= 3 and data[i - 3] == 0x44 and data[i - 2] == 0x31:
                xl = i - 3
            if xl is not None and xl >= 6 and data[xl - 6] == 0x8B and data[xl - 5] == 0x05:
                r, _ = o2r(xl - 6)
                cell = (r + 6 + struct.unpack_from('<i', data, xl - 4)[0]) & M
                # the key: nearest preceding  (REX?) B8+reg imm32  within 40 bytes
                K = None
                seg_start = max(0, xl - 6 - 40)
                seg = data[seg_start:xl - 6]
                for p in range(len(seg) - 5, -1, -1):
                    if 0xB8 <= seg[p] <= 0xBF:
                        if p >= 1 and seg[p - 1] in (0x41, 0x44, 0x45, 0x49):
                            K = struct.unpack_from('<I', seg, p + 1)[0]
                            break
                        K = struct.unpack_from('<I', seg, p + 1)[0]
                        break
                if K is not None:
                    rr, _ = o2r(i)
                    sites.append((rr, cell, K, A, '8B-05/31'))
    i = data.find(ROL, i + 1)

print("=" * 104)
print("Q13  SOLVE THE PROTECTOR SYSCALL NUMBERS OFFLINE")
print("=" * 104)
print("extracted sites (strict encodings only): %d" % len(sites))
bycell = collections.defaultdict(list)
for rr, cell, K, A, f in sites:
    bycell[cell].append((rr, K, A, f))
print("distinct cells: %d" % len(bycell))

# ---- C1: the disk value must be the s=0xFFFFFFFF solution ----
print("\nC1  does every site on a cell reproduce the DISK dword for s = 0xFFFFFFFF ?")
c1ok = c1bad = 0
for cell, lst in sorted(bycell.items()):
    off, sec = r2o(cell)
    if off is None:
        continue
    disk = struct.unpack_from('<I', data, off)[0]
    xs = set()
    for rr, K, A, f in lst:
        xs.add(((0xFFFFFFFF - A) & M) ^ rol(K))
    ok = (len(xs) == 1 and rol(disk) == next(iter(xs)))
    c1ok += ok
    c1bad += (not ok)
print("   cells reproducing the disk dword: %d ; failing: %d" % (c1ok, c1bad))

# ---- solve ----
print("\n--- solving: for each cell, which s in [0,0x1000) makes ALL its sites agree? ---")
KNOWN = {0x0F: 'NtClose', 0x18: 'NtAllocateVirtualMemory', 0x19: 'NtQueryInformationToken',
         0x23: 'NtQueryVirtualMemory', 0x28: 'NtMapViewOfSection', 0x2C: 'NtTerminateProcess',
         0x34: 'NtDelayExecution', 0x36: 'NtQuerySystemInformation',
         0x3A: 'NtWriteVirtualMemory', 0x3F: 'NtReadVirtualMemory',
         0x50: 'NtProtectVirtualMemory', 0x55: 'NtCreateSection', 0xC7: 'NtCreateThreadEx',
         0x06: 'NtWaitForSingleObject', 0x1E: 'NtQueryInformationProcess',
         0x2A: 'NtUnmapViewOfSection', 0x4E: 'NtCreateFile', 0x08: 'NtWriteFile',
         0x03: 'NtDeviceIoControlFile', 0x0A: 'NtQueryInformationFile',
         0x05: 'NtQueryInformationThread', 0x12: 'NtQueryEvent', 0x11: 'NtSetEvent',
         0x1B: 'NtOpenThreadToken', 0x0D: 'NtSetInformationThread',
         0x24: 'NtQueryObject', 0x37: 'NtQueryTimer', 0x2D: 'NtTerminateThread',
         0x4D: 'NtCreateEvent', 0x1F: 'NtOpenProcessToken'}
uniq = amb = none_ = 0
for cell, lst in sorted(bycell.items()):
    off, sec = r2o(cell)
    disk = struct.unpack_from('<I', data, off)[0] if off is not None else None
    sols = []
    for s in range(0x1000):
        xs = set()
        for rr, K, A, f in lst:
            xs.add(((s - A) & M) ^ rol(K))
            if len(xs) > 1:
                break
        if len(xs) == 1:
            sols.append((s, next(iter(xs))))
    tag = ''
    if len(sols) == 1:
        uniq += 1
        tag = 'UNIQUE'
    elif len(sols) == 0:
        none_ += 1
        tag = 'none'
    else:
        amb += 1
        tag = '%d solutions' % len(sols)
    print("  cell 0x%08X  sites=%-3d disk=0x%08X  %s" % (cell, len(lst), disk or 0, tag))
    for s, x in sols[:8]:
        # invert x = ROL7(cell) -> cell = ROR7(x)
        c = ((x >> 7) | (x << 25)) & M
        print("      s = 0x%03X %-26s live cell would be 0x%08X"
              % (s, KNOWN.get(s, ''), c))
print("\nC3  cells with a UNIQUE solution in [0,0x1000): %d ; ambiguous: %d ; none: %d"
      % (uniq, amb, none_))
print("\nNOTE: sites with only ONE occurrence per cell are unconstrained by construction --")
print("one site admits every s.  Only cells with >=2 DISTINCT (K,A) pairs can decide.")
multi = {c: l for c, l in bycell.items() if len(set((K, A) for _r, K, A, _f in l)) >= 2}
print("cells with >=2 distinct (K,A) pairs: %d of %d" % (len(multi), len(bycell)))
