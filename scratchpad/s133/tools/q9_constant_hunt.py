#!/usr/bin/env python
"""q9_constant_hunt.py -- the register census of q8a gives a FIXED FINGERPRINT of the code
that transfers control to <runtime.dll base>+1:

    rbp = 0x537AC9E1      108/108 reports, 3 boot sessions, 16 days
    r11 = 0x95654773B3BC  108/108
    rdi == rsp            108/108
    rbx == r10            108/108 (high entropy, different every report)
    rax = rcx = rsi = r12 = r13 = r14 = r15 = 0

runtime.dll is plaintext on disk (FK-10 [M]).  So search it for the immediates.

WHY THIS IS NOT THE S132 CONFOUND: S132's refuted search was for `ImageBase + 1`, and
ImageBase == 0x200000000 == 2^33, so every hit aliased with ordinary MBA arithmetic on bit
33.  0x537AC9E1 and 0x95654773B3BC are NOT powers of two and not the image base; a
byte-exact search for them has no such aliasing.

CONTROLS
  C1 the same search is run for three CONTROL constants of the same width drawn at random.
     Their hit counts are the ambient rate for a 4/6-byte literal in a 64 MB obfuscated
     binary.  A finding must clear that floor.
  C2 the search is also run over SUPERVIVE-Win64-Shipping.exe (on disk) and preloader.dll,
     so a hit that is really ambient across all binaries is visible as such.

usage: python q9_constant_hunt.py
"""
import random
import struct
import sys

RT = "G:/git/GAME BACKUPS FOR REVERSE ENGINEERING/SUPERVIVE/Loki/Binaries/Win64/runtime.dll"
PL = "G:/git/GAME BACKUPS FOR REVERSE ENGINEERING/SUPERVIVE/Loki/Binaries/Win64/preloader.dll"
EXE = "G:/git/GAME BACKUPS FOR REVERSE ENGINEERING/SUPERVIVE/Loki/Binaries/Win64/SUPERVIVE-Win64-Shipping.exe"


def sections(data):
    e = struct.unpack_from('<I', data, 0x3C)[0]
    nsec = struct.unpack_from('<H', data, e + 6)[0]
    optsz = struct.unpack_from('<H', data, e + 20)[0]
    st = e + 24 + optsz
    out = []
    for i in range(nsec):
        s = st + i * 40
        nm = data[s:s + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, rp = struct.unpack_from('<IIII', data, s + 8)
        out.append((nm, va, vsz, rp, rsz, struct.unpack_from('<I', data, s + 36)[0]))
    return out


def off2rva(secs, off):
    for nm, va, vsz, rp, rsz, ch in secs:
        if rp <= off < rp + rsz:
            return va + (off - rp), nm
    return None, '(headers)'


def findall(data, pat):
    out = []
    i = data.find(pat)
    while i >= 0:
        out.append(i)
        i = data.find(pat, i + 1)
    return out


def sweep(path, label, pats):
    with open(path, 'rb') as f:
        data = f.read()
    secs = sections(data)
    print("\n--- %s  (%d bytes, %d sections) ---" % (label, len(data), len(secs)))
    for name, pat in pats:
        hits = findall(data, pat)
        print("  %-34s %-22s hits=%d" % (name, pat.hex(), len(hits)))
        for h in hits[:12]:
            rva, sec = off2rva(secs, h)
            ctx = data[max(0, h - 8):h + 16].hex()
            print("      file 0x%08X  rva 0x%08X  %-9s  ctx %s" % (h, rva or 0, sec, ctx))
    return data, secs


RBP = 0x537AC9E1
R11 = 0x95654773B3BC

pats = [
    ("mov ebp, 0x537AC9E1        (BD ..)", b'\xBD' + struct.pack('<I', RBP)),
    ("raw dword 0x537AC9E1", struct.pack('<I', RBP)),
    ("mov r11, 0x95654773B3BC (49 BB)", b'\x49\xBB' + struct.pack('<Q', R11)),
    ("raw qword 0x95654773B3BC", struct.pack('<Q', R11)),
    ("raw 6 bytes of 0x95654773B3BC", struct.pack('<Q', R11)[:6]),
]
random.seed(7)
ctl = []
for i in range(3):
    v = random.getrandbits(32) | 0x40000000
    ctl.append(("CONTROL raw dword 0x%08X" % v, struct.pack('<I', v)))
for i in range(3):
    v = random.getrandbits(48)
    ctl.append(("CONTROL raw 6B 0x%012X" % v, struct.pack('<Q', v)[:6]))

print("=" * 100)
print("Q9  HUNT THE FK-31 TRANSFER-SITE CONSTANTS IN THE PLAINTEXT PROTECTOR")
print("=" * 100)
sweep(RT, "runtime.dll", pats + ctl)
sweep(PL, "preloader.dll  (C2)", pats)
sweep(EXE, "SUPERVIVE-Win64-Shipping.exe  (C2)", pats)
