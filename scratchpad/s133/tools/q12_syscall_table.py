#!/usr/bin/env python
"""q12_syscall_table.py -- the protector's COMPLETE direct-syscall inventory, offline.

q11 hand-decoded FK-10's kill primitive at runtime.dll RVA 0x80F7F0:

    4C 8B 51 10        mov  r10, [rcx+0x10]      ; r10 = NT arg1  (ProcessHandle)
    4D 85 D2           test r10, r10
    74 1B              je   0x80F814             ; -> xor eax,eax ; ret
    B8 BF778E61        mov  eax, 0x618E77BF      ; per-site XOR key
    33 05 FCAF1300     xor  eax, [rip+0x13AFFC]  ; -> cell RVA 0x0094A800
    C1 C0 07           rol  eax, 7
    05 47C71067        add  eax, 0x6710C747      ; per-site addend
    BA ADDE0000        mov  edx, 0x0000DEAD      ; NT arg2 = ExitStatus
    0F 05              syscall
    C3                 ret

So the SSN obfuscation is  SSN = ROL32(cell ^ KEY, 7) + ADD  with PER-SITE KEY/ADD and a
per-service CELL in packer2.  0x537AC9E1 (the constant found in the FK-31 fault registers)
is ONE such key, not the only one.

This sweeps the whole plaintext image for the idiom and emits the cell table.

CONTROLS
  C1 every accepted site must have a `0F 05` (syscall) within 32 bytes after the `add`.
  C2 the same scan is run with the rotate amount changed to a wrong value (rol 6 / rol 8);
     accepted-site counts there are the false-positive floor for the structural match.
  C3 the number of DISTINCT cells must be far smaller than the number of sites if the cells
     are a per-service table (as expected), and the cells must be contiguous-ish in packer2.

usage: python q12_syscall_table.py
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
            return (off if off + 4 <= len(data) else None), nm
    return None, None


def rol32(v, n):
    v &= 0xFFFFFFFF
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF


def sweep(rotbyte, label):
    ROL = bytes([0xC1, 0xC0, rotbyte])
    sites = []
    i = data.find(ROL)
    while i >= 0:
        # add eax, imm32 must follow
        if i + 3 + 5 <= len(data) and data[i + 3] == 0x05:
            add = struct.unpack_from('<I', data, i + 4)[0]
            # C1: syscall within 32 bytes after
            win = data[i + 8:i + 8 + 32]
            if b'\x0F\x05' in win:
                # backward: xor eax,[rip+d32] == 33 05 d32, within 24 bytes
                pre_off = max(0, i - 24)
                pre = data[pre_off:i]
                k = pre.rfind(b'\x33\x05')
                cell = key = None
                if k >= 0 and len(pre) - k >= 6:
                    insn = pre_off + k
                    r, _ = o2r(insn)
                    if r is not None:
                        cell = (r + 6 + struct.unpack_from('<i', data, insn + 2)[0]) & 0xFFFFFFFF
                    # key: mov eax, imm32 == B8 imm32 just before
                    if k >= 5 and pre[k - 5] == 0xB8:
                        key = struct.unpack_from('<I', pre, k - 4)[0]
                if cell is None:
                    # variant: 8B 05 d32 (mov eax,[rip]) then xor with a register holding K
                    k = pre.rfind(b'\x8B\x05')
                    if k >= 0 and len(pre) - k >= 6:
                        insn = pre_off + k
                        r, _ = o2r(insn)
                        if r is not None:
                            cell = (r + 6 + struct.unpack_from('<i', data, insn + 2)[0]) & 0xFFFFFFFF
                        # key is in a register loaded earlier: B8..BF imm32 within 24 bytes
                        seg = data[max(0, insn - 24):insn]
                        for p in range(len(seg) - 5, -1, -1):
                            if 0xB8 <= seg[p] <= 0xBF:
                                key = struct.unpack_from('<I', seg, p + 1)[0]
                                break
                rva, sec = o2r(i)
                sites.append((rva, sec, cell, key, add))
        i = data.find(ROL, i + 1)
    return sites


print("=" * 108)
print("Q12  PROTECTOR DIRECT-SYSCALL INVENTORY  (runtime.dll, plaintext on disk)")
print("=" * 108)
good = sweep(0x07, "rol 7")
print("sites matching  rol eax,7 ; add eax,imm32 ; ... ; syscall  : %d" % len(good))
for rot in (0x06, 0x08, 0x05, 0x09):
    bad = sweep(rot, "rol %d" % rot)
    print("   C2 FALSE-POSITIVE FLOOR with rol %d instead of 7 : %d sites" % (rot, len(bad)))

cells = collections.Counter()
decoded = []
for rva, sec, cell, key, add in good:
    if cell is None or key is None:
        continue
    off, csec = r2o(cell)
    if off is None:
        continue
    cv = struct.unpack_from('<I', data, off)[0]
    ssn = (rol32(cv ^ key, 7) + add) & 0xFFFFFFFF
    cells[(cell, csec)] += 1
    decoded.append((rva, sec, cell, csec, key, add, cv, ssn))

print("\nfully decoded sites: %d ; DISTINCT CELLS: %d" % (len(decoded), len(cells)))
print("\n--- the cell table (C3: a per-service table should be small and contiguous) ---")
for (cell, csec), n in sorted(cells.items()):
    off, _ = r2o(cell)
    cv = struct.unpack_from('<I', data, off)[0]
    ex = [d for d in decoded if d[2] == cell][0]
    ssn = (rol32(cv ^ ex[4], 7) + ex[5]) & 0xFFFFFFFF
    print("   cell 0x%08X %-9s disk=0x%08X  used by %3d sites  one decode -> SSN 0x%08X"
          % (cell, csec, cv, n, ssn))

print("\n--- every decoded site (RVA, key, add, SSN-from-disk) ---")
ssnhist = collections.Counter()
for rva, sec, cell, csec, key, add, cv, ssn in sorted(decoded):
    ssnhist['0x%08X' % ssn] += 1
print("SSN(disk) histogram: %s" % ssnhist.most_common(8))
seen = set()
for rva, sec, cell, csec, key, add, cv, ssn in sorted(decoded):
    if (cell, key, add) in seen:
        continue
    seen.add((cell, key, add))
    print("   site 0x%08X %-9s cell 0x%08X key 0x%08X add 0x%08X -> 0x%08X"
          % (rva, sec, cell, key, add, ssn))
print("   (distinct (cell,key,add) triples: %d of %d sites)" % (len(seen), len(decoded)))

out = 'scratchpad/s133/evidence/runtime_syscall_sites.tsv'
with open(out, 'w') as fh:
    fh.write("site_rva\tsection\tcell_rva\tcell_section\tkey\tadd\tcell_disk\tssn_disk\n")
    for rva, sec, cell, csec, key, add, cv, ssn in sorted(decoded):
        fh.write("0x%08X\t%s\t0x%08X\t%s\t0x%08X\t0x%08X\t0x%08X\t0x%08X\n"
                 % (rva, sec, cell, csec, key, add, cv, ssn))
print("\n-> %s" % out)
print("\nLIVE RECOVERY RECIPE (read-only, no injection):")
print("  runtime_base = <the boot session's FK-31 kill address> & ~0xFFF")
for (cell, csec), n in sorted(cells.items()):
    print("  ReadProcessMemory(runtime_base + 0x%08X, 4) -> cell; SSN = ROL32(cell^KEY,7)+ADD"
          % cell)
