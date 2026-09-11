#!/usr/bin/env python
"""q10_syscall_decode.py -- 0x537AC9E1 is the protector's SYSCALL-NUMBER XOR KEY.

The 27 sites found in q9b all share one idiom, visible in the raw bytes:

    8B 05 <disp32>          mov eax, [rip+disp32]        ; obfuscated SSN cell
    B9/BB/BD/41BF.. <K>     mov <r32>, 0x537AC9E1
    31 C8 / 44 31 F8 ...    xor eax, <r32>
    C1 C0 07                rol eax, 7
    05 <imm32>              add eax, imm32
    0F 05                   syscall

So SSN = ROL32(cell ^ 0x537AC9E1, 7) + imm32.

This matters because CLAUDE.md carries an explicit open grade correction:
  '"0x80F7F0 IS NtTerminateProcess(h,0xDEAD)" is [I], NOT [M] -- the syscall number is
   computed at runtime and on disk evaluates to 0xFFFFFFFF, which is not a valid service
   number.'
Recovering the formula makes the number computable offline IF the cell is initialised on
disk.

CONTROL: Windows 10 19045 x64 SSNs are a dense range roughly [0x00,0x01FF].  If the formula
is right, decoded values must fall in that range far more often than chance (a random 32-bit
value lands there with p = 512/2^32 = 1.2e-7).  Any value >= 0x1000 is reported as such --
the failure is then in the CELL (runtime-initialised), not in the formula.

usage: python q10_syscall_decode.py
"""
import struct
import sys

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
            return (off if off < len(data) else None), nm
    return None, None


def rol32(v, n):
    v &= 0xFFFFFFFF
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF


# known Win10 19045 x64 SSNs, for the control
KNOWN = {0x0F: 'NtClose', 0x18: 'NtAllocateVirtualMemory', 0x1E: 'NtQueryInformationProcess',
         0x23: 'NtQueryVirtualMemory', 0x2C: 'NtTerminateProcess', 0x34: 'NtDelayExecution',
         0x36: 'NtQuerySystemInformation', 0x3A: 'NtWriteVirtualMemory',
         0x3F: 'NtReadVirtualMemory', 0x50: 'NtProtectVirtualMemory',
         0xC7: 'NtCreateThreadEx', 0x4E: 'NtCreateFile', 0x55: 'NtCreateSection',
         0x28: 'NtMapViewOfSection', 0x2A: 'NtUnmapViewOfSection', 0x19: 'NtQueryInfoToken',
         0x06: 'NtWaitForSingleObject', 0x08: 'NtWriteFile', 0x03: 'NtDeviceIoControlFile',
         0x1A: 'NtQueryVolumeInformationFile', 0x0A: 'NtQueryInformationFile',
         0x12: 'NtQueryEvent', 0x05: 'NtQueryInformationThread'}

pat = struct.pack('<I', KEY)
print("=" * 100)
print("Q10  DECODE THE PROTECTOR'S SYSCALL NUMBERS  (key 0x%08X)" % KEY)
print("=" * 100)
rows = []
i = data.find(pat)
while i >= 0:
    # the mov <r32>, K opcode byte is at i-1 (0xB8..0xBF), possibly with a REX at i-2
    start = i - 1
    if start - 1 >= 0 and data[start - 1] in (0x41, 0x44, 0x45, 0x49):
        start -= 1
    tail = data[i + 4:i + 4 + 24]
    # find "rol eax,7" == C1 C0 07 then "05 imm32" then 0F 05
    j = tail.find(b'\xC1\xC0\x07')
    ssn = None
    imm = None
    cell_rva = None
    if j >= 0 and len(tail) >= j + 3 + 5:
        if tail[j + 3] == 0x05:
            imm = struct.unpack_from('<I', tail, j + 4)[0]
    # the cell load: search backwards up to 24 bytes for 8B 05 disp32
    pre = data[max(0, start - 24):start]
    k = pre.rfind(b'\x8B\x05')
    if k >= 0 and len(pre) - k >= 6:
        disp = struct.unpack_from('<i', pre, k + 2)[0]
        insn_off = max(0, start - 24) + k
        insn_rva, _ = o2r(insn_off)
        if insn_rva is not None:
            cell_rva = (insn_rva + 6 + disp) & 0xFFFFFFFF
    if imm is not None and cell_rva is not None:
        off, sec = r2o(cell_rva)
        if off is not None:
            cell = struct.unpack_from('<I', data, off)[0]
            ssn = (rol32(cell ^ KEY, 7) + imm) & 0xFFFFFFFF
            rva, s2 = o2r(i)
            rows.append((rva, cell_rva, sec, cell, imm, ssn))
    i = data.find(pat, i + 1)

print("sites with a fully-decodable idiom: %d of 27\n" % len(rows))
print("%-12s %-12s %-9s %-10s %-12s %-12s %s"
      % ("site RVA", "cell RVA", "cell sec", "cell(disk)", "add imm32", "SSN", "known?"))
inrange = 0
for rva, cell_rva, sec, cell, imm, ssn in rows:
    ok = KNOWN.get(ssn, '')
    if ssn < 0x200:
        inrange += 1
    print("0x%08X   0x%08X   %-9s 0x%08X   0x%08X    0x%08X   %s"
          % (rva, cell_rva, sec, cell, imm, ssn, ok if ok else
             ('<in SSN range>' if ssn < 0x200 else '')))
print("\nCONTROL: decoded values landing in the plausible SSN range [0,0x200): %d of %d"
      % (inrange, len(rows)))
print("         chance rate for a uniform 32-bit value: 512/2^32 = 1.2e-7 per site")
print("\nNOTE the cell sections: a cell in a WRITABLE packer section is initialised at")
print("runtime, so its on-disk value is not the live one and the SSN cannot be recovered")
print("statically from THAT site.  A cell in a READ-ONLY section can be.")
