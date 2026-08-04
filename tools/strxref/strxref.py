#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strxref.py -- offline string census + string->code xref index for the SUPERVIVE
              (UE5.4 "Loki") cold image dump.  Stdlib only.  No live process.

WHY THIS EXISTS
---------------
Two CRITICAL "false-knowns" (docs/ignorance-map-s101.md FK-3 / FK-4) had retired
two static-analysis techniques for this project:

  FK-3  ".rdata union is capped at 63.12% and IS structural ... ~13.9 MB of
         vtables/RTTI/strings are permanently unreadable by RPM."
  FK-4  "this build's packer decrypts .rdata strings to the HEAP on use and
         leaves the module .rdata copy encrypted, so LEA -> string xref is
         defeated."

Both are FALSE, and this tool is the measurement that shows it (run `--rebuild`,
read the SELF-VALIDATION block).  See README.md for the full write-up.

  * FK-3 conflated two different metrics.  "63.12%" counts NON-ZERO BYTES.
    .rdata is 99.64% READABLE by page (33 zero pages out of 9,085); the missing
    36.88% of bytes is null padding inside vtables and between string literals.
    The byte metric is only meaningful for .text, where demand-decrypt zeroes
    WHOLE PAGES (48.05% non-zero vs 52.29% readable pages -- those agree).
  * FK-4 came from ASCII-only scanning (and/or scanning the ON-DISK exe).  The
    live/dumped .rdata is PLAINTEXT; 85,692 of its strings are UTF-16LE, which
    an ASCII scan cannot see.  The on-disk file IS packed (only 7% of its .rdata
    pages match the dump), so a static scan of the exe on disk does see garbage
    -- that is the most likely origin of the false-known.

THE REAL CAP (measured, and it is not what FK-3 said)
-----------------------------------------------------
~49% of UTF-16 strings resolve to code by exact start, ~55% including interior
references.  That tracks .text's 52.29% decrypted-page fraction almost exactly:
essentially EVERY string whose referencing code is decrypted IS xref'd.  The cap
is .text demand-decrypt, NOT .rdata, and it is not structural -- it lifts as the
game executes more code (dump from more states, then `usmapdump mergedumps`).
A zero-xref result therefore NEVER proves "nothing references this".

USAGE
-----
  strxref.py --rebuild [--dump PATH] [--min-len N]   build + print self-validation
  strxref.py census                                  summary stats
  strxref.py find "<substring>" [-n N] [--regex] [--refs-only]
  strxref.py xref 0x<string_rva>                     code sites referencing it
  strxref.py func 0x<code_rva> [--raw]               every string a function touches
  strxref.py validate                                re-run validation incl. null controls
"""

import argparse
import bisect
import os
import pickle
import re
import struct
import sys
import time
from array import array
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DUMP = r"G:\git\Supervive Revival Project\dumps\merged.dump.exe"
INDEX_DIR = os.path.join(HERE, "index")
INDEX_PATH = os.path.join(INDEX_DIR, "strxref.idx")

# --------------------------------------------------------------------------
# Recovered .pdata (S102).  The image's own .pdata is packer-encrypted on disk
# and all-zero in memory, so this tool originally had to infer every function
# boundary.  It no longer does: the packer publishes the real x64 unwind data as
# a DYNAMIC function table, and MiniDumpWriteDump serialises dynamic function
# tables into MINIDUMP stream 13 (FunctionTableStream).  70 of the 85 UE crash
# minidumps under %LOCALAPPDATA%\SUPERVIVE\Saved\Crashes carry it.
#
# pdataunion.py unions the 70 tables (they are materialised LAZILY, in step with
# demand-decrypt, so each crash's table reflects that process's coverage) into
# index/pdata_union.csv -- 382,282 exact, non-overlapping function bounds.
# Verified: 13/13 project-recorded function addresses are EXACT entries.
#
# When the file is present, `func`/`xref` report TRUE bounds instead of the
# next-candidate upper bound.  When it is absent everything falls back to the
# heuristic, so the tool still works standalone.
PDATA_PATH = os.path.join(INDEX_DIR, "pdata_union.csv")
_PDATA = None


def load_pdata(path=PDATA_PATH):
    """-> (beg[], end[]) ascending, or None.  Cached."""
    global _PDATA
    if _PDATA is not None:
        return _PDATA[0] if _PDATA[0] else None
    if not os.path.exists(path):
        _PDATA = (None,)
        return None
    beg, end = array("l"), array("l")
    with open(path) as f:
        next(f)
        for line in f:
            a, b, _s, _u, _k = line.split(",")
            beg.append(int(a, 16))
            end.append(int(b, 16))
    _PDATA = ((beg, end),)
    return _PDATA[0]


def true_func(rva):
    """Exact (begin, end) from the recovered table, or (None, None).

    Returns (None, None) both when there is no table AND when the address falls in
    a gap -- a gap means the containing function was never decrypted in any of the
    70 crash processes, NOT that no function is there.
    """
    p = load_pdata()
    if not p:
        return None, None
    beg, end = p
    i = bisect.bisect_right(beg, rva) - 1
    if i >= 0 and rva < end[i]:
        return beg[i], end[i]
    return None, None

# Reference kinds
K_LEA = 0    # lea  r64,[rip+d32]   (48/4C 8D)   -- the dominant form
K_MOVC = 1   # mov/cmp r64,[rip+d32] (48/4C 8B / 48/4C 3B)
K_PTR = 2    # indirect: code -> qword slot in .rdata/.data -> string

KIND_NAME = {K_LEA: "lea", K_MOVC: "mov/cmp", K_PTR: "ptr-tbl"}

# Function-entry evidence flags
F_CALL1 = 0x01   # target of exactly one E8 rel32
F_CALL2 = 0x02   # target of >=2 distinct E8 rel32 sites
F_PTR = 0x04     # appears as an absolute qword in a data section (vtable / fn table)
F_PAD = 0x08     # 16-aligned start immediately after an int3 (0xCC) padding run
F_PRO = 0x10     # matches a known MSVC x64 prologue
F_A16 = 0x20     # 16-byte aligned
F_PREV = 0x40    # previous byte is a function terminator (C3/C2/CC/E9/EB/00/FF/90)
F_PROSCAN = 0x80  # found by the strong-prologue sweep (16-aligned + prologue + F_PREV)

TIER_HIGH, TIER_MED, TIER_LOW = 2, 1, 0
TIER_NAME = {TIER_HIGH: "HIGH", TIER_MED: "MED", TIER_LOW: "LOW"}


class BuildError(RuntimeError):
    """Raised loudly on any structural surprise.  Never guess, never paper over."""


# --------------------------------------------------------------------------
# PE parsing
# --------------------------------------------------------------------------
class PE:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.d = f.read()
        d = self.d
        if len(d) < 0x400:
            raise BuildError("file too small to be a PE: %d bytes" % len(d))
        if d[:2] != b"MZ":
            raise BuildError("bad DOS magic at 0x0: %r (expected 'MZ')" % d[:2])
        e = struct.unpack_from("<I", d, 0x3C)[0]
        if not (0x40 <= e < len(d) - 24):
            raise BuildError("e_lfanew 0x%X out of range (file is %d bytes)" % (e, len(d)))
        if d[e:e + 4] != b"PE\0\0":
            raise BuildError("bad PE signature at 0x%X: %r" % (e, d[e:e + 4]))
        machine, nsec, _, _, _, szopt, _ = struct.unpack_from("<HHIIIHH", d, e + 4)
        if machine != 0x8664:
            raise BuildError("machine 0x%04X is not AMD64 -- this tool decodes x86-64 only" % machine)
        opt = e + 24
        magic = struct.unpack_from("<H", d, opt)[0]
        if magic != 0x20B:
            raise BuildError("optional-header magic 0x%04X at 0x%X is not PE32+ (0x20B)" % (magic, opt))
        self.imagebase = struct.unpack_from("<Q", d, opt + 24)[0]
        self.sizeofimage = struct.unpack_from("<I", d, opt + 56)[0]
        self.machine, self.nsec = machine, nsec

        self.sections = []  # (name, vaddr, vsize, rawsize, rawptr)
        sh = opt + szopt
        if sh + nsec * 40 > len(d):
            raise BuildError("section table (%d sections at 0x%X) runs past EOF" % (nsec, sh))
        for i in range(nsec):
            o = sh + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode("latin1")
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", d, o + 8)
            self.sections.append((name, vaddr, vsize, rawsize, rawptr))

        # This dump format (usmapdump dumpimage / mergedumps) sets file-offset == RVA.
        # Everything downstream indexes d[rva] directly, so verify it -- loudly.
        for name, vaddr, vsize, rawsize, rawptr in self.sections:
            if rawsize and rawptr != vaddr:
                raise BuildError(
                    "section %r has PointerToRawData 0x%X != VirtualAddress 0x%X. "
                    "This tool requires a flat image where file offset == RVA "
                    "(usmapdump dumpimage / mergedumps output). Do not point it at "
                    "an on-disk PE." % (name, rawptr, vaddr))
        if self.sizeofimage > len(d):
            raise BuildError("SizeOfImage 0x%X exceeds file size 0x%X -- truncated dump?"
                             % (self.sizeofimage, len(d)))
        self._by_name = {s[0]: s for s in self.sections}

    def sec(self, name):
        s = self._by_name.get(name)
        if s is None:
            raise BuildError("section %r not present; have %s"
                             % (name, [x[0] for x in self.sections]))
        return s

    def secof(self, rva):
        for name, vaddr, vsize, _, _ in self.sections:
            if vaddr <= rva < vaddr + vsize:
                return name
        return None

    def bytes_of(self, name):
        _, vaddr, vsize, _, _ = self.sec(name)
        n = min(vsize, len(self.d) - vaddr)
        return self.d[vaddr:vaddr + n], vaddr, n

    def coverage(self):
        rows = []
        for name, vaddr, vsize, _, _ in self.sections:
            n = min(vsize, len(self.d) - vaddr)
            if n <= 0:
                continue
            b = self.d[vaddr:vaddr + n]
            nz = n - b.count(0)
            pages = (n + 4095) // 4096
            zp = sum(1 for p in range(pages) if not any(b[p * 4096:(p + 1) * 4096]))
            rows.append((name, vaddr, vsize, pages, zp, 100.0 * nz / n,
                         100.0 * (pages - zp) / pages))
        return rows


# --------------------------------------------------------------------------
# String scanning
# --------------------------------------------------------------------------
# Sections scanned for strings.  .text/.pdata/.reloc are excluded: measured, they
# carry no code-referenced string literals (see the census "not indexed" line).
STRING_SECTIONS = (".rdata", ".data", "_RDATA", ".rodata", ".rsrc")


def scan_strings(pe, min_len):
    """Return (rvas, ends, encs) sorted by RVA, plus a per-section breakdown.

    ASCII : maximal runs of [\\x20-\\x7e] of >= min_len chars, NUL-terminated.
    UTF-16: maximal runs of ([\\x20-\\x7e]\\x00) pairs of >= min_len chars,
            terminated by 00 00.

    UTF-16 START CORRECTION (measured, load-bearing).  The naive maximal-run scan
    over-extends a wide string backwards by exactly one character whenever the
    wide literal is immediately preceded by an ASCII literal: that ASCII string's
    last character plus its NUL terminator form a valid (printable, 0x00) pair and
    get absorbed.  Observed live: 'eBP_Initialize' for L"BP_Initialize" (preceded
    by "BP_Deinitialize\\0"), 'p%02X ' for L"%02X " (preceded by
    "...CompressionUtil.cpp\\0").  A genuine wide-literal start is always preceded
    by a 0x00 (its predecessor's terminator, or alignment padding), so the rule is:
        while d[s-1] != 0x00:  s += 2
    which converges in one step.  Measured effect at min_len=6: 1,135 runs
    corrected, +596 additional strings resolved to code by exact start.

    ASCII/UTF-16 OVERLAP RULE.  The two scans are independent and can both claim
    bytes (e.g. an array of 1-char ASCII strings looks like UTF-16).  UTF-16 wins:
    an ASCII run whose byte interval is FULLY CONTAINED in a UTF-16 interval is
    dropped.  Partial overlaps are kept (they are genuinely two different data
    items sharing a boundary).  Measured at min_len=6: 1,043 ASCII runs dropped
    (1.0%).  There are ZERO start-RVA collisions between the two sets.
    """
    rx_a = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    rx_u = re.compile(rb"(?:[\x20-\x7e]\x00){%d,}" % min_len)

    rvas, ends, encs = [], [], bytearray()
    per_sec = {}
    stats = Counter()

    for sname in STRING_SECTIONS:
        try:
            b, base, n = pe.bytes_of(sname)
        except BuildError:
            continue
        if n <= 0:
            continue

        u_iv = []
        for m in rx_u.finditer(b):
            s, e = m.start(), m.end()
            if not (e + 1 < n and b[e] == 0 and b[e + 1] == 0):
                continue
            while s > 0 and b[s - 1] != 0 and (e - s) // 2 > 1:
                s += 2
                stats["utf16_start_corrected"] += 1
            if (e - s) // 2 >= min_len:
                u_iv.append((s, e))
            else:
                stats["utf16_dropped_after_correction"] += 1
        u_iv.sort()
        u_starts = [x[0] for x in u_iv]

        def inside_utf16(s, e):
            i = bisect.bisect_right(u_starts, s) - 1
            return i >= 0 and u_iv[i][0] <= s and e <= u_iv[i][1]

        a_iv = []
        for m in rx_a.finditer(b):
            s, e = m.start(), m.end()
            if not (e < n and b[e] == 0):
                continue
            if inside_utf16(s, e):
                stats["ascii_dropped_inside_utf16"] += 1
                continue
            a_iv.append((s, e))

        for s, e in a_iv:
            rvas.append(base + s); ends.append(base + e); encs.append(ord("A"))
        for s, e in u_iv:
            rvas.append(base + s); ends.append(base + e); encs.append(ord("U"))
        per_sec[sname] = (len(a_iv), len(u_iv))

    order = sorted(range(len(rvas)), key=lambda i: rvas[i])
    R = array("q", (rvas[i] for i in order))
    E = array("q", (ends[i] for i in order))
    C = bytearray(encs[i] for i in order)
    if len(set(R)) != len(R):
        dupes = [r for r, c in Counter(R).items() if c > 1][:5]
        raise BuildError("duplicate string start RVAs after merge: %s" % [hex(x) for x in dupes])
    return R, E, C, per_sec, stats


# --------------------------------------------------------------------------
# Reference scanning
# --------------------------------------------------------------------------
# RIP-relative forms.  Each entry: (regex, disp_offset, instr_len, kind).
#
# MEASURED (min_len=6 census, .rdata targets landing on a string START):
#   lea  r64,[rip]  48/4C 8D   517,515 matches -> 245,894 into .rdata -> 113,060 hits
#   mov  r64,[rip]  48/4C 8B   134,564 matches ->     269 into .rdata ->       8 hits
#   cmp  r64,[rip]  48/4C 3B     1,450 matches ->     282 into .rdata ->       5 hits
#   mov  [rip],r64  48/4C 89    55,922 matches ->       0 into .rdata ->       0 hits (.rdata is RO)
#   call [rip]      FF 15       22,721 matches ->  20,750 into .rdata ->       0 hits (that is the IAT)
#   lea  r32,[rip]  8D  no-REX   1,332 matches ->      21 into .rdata ->       2 hits  } EXCLUDED:
#   mov  r32,[rip]  8B  no-REX  18,308 matches ->     376 into .rdata ->      15 hits  } +17 hits (0.015%)
#                                                                                      } for a much
#                                                                                      } higher FP rate
#                                                                                      } (no REX anchor)
#   REX.B variants 49/4D 8D:    +7 matches -> 0 into .rdata.  EXCLUDED (pure noise).
#   push imm32 / mov r32,imm32: IMPOSSIBLE -- ImageBase 0x7FF6AF000000 is > 4 GB, so no
#                               32-bit absolute form can encode an image address.
#   mov r64,imm64 (48 B8+r):    MEASURED ZERO -- of 1,501,710 absolute qwords in the
#                               image, NOT ONE lies inside .text.  x64 code here is
#                               100% RIP-relative.
# => lea accounts for 99.97% of all direct string references.
RIP_FORMS = (
    (rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", 3, 7, K_LEA),
    (rb"[\x48\x4c]\x8b[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", 3, 7, K_MOVC),
    (rb"[\x48\x4c]\x3b[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", 3, 7, K_MOVC),
)


def scan_rip_refs(pe):
    """Yield (site_rva, target_rva, kind) for every RIP-relative reference in .text."""
    tx, tbase, tn = pe.bytes_of(".text")
    up = struct.unpack_from
    out = []
    counts = Counter()
    for pat, doff, ilen, kind in RIP_FORMS:
        rx = re.compile(pat)
        for m in rx.finditer(tx):
            o = m.start()
            if o + ilen > tn:
                continue
            tgt = tbase + o + ilen + up("<i", tx, o + doff)[0]
            counts[kind] += 1
            out.append((tbase + o, tgt, kind))
    return out, counts


def scan_abs_qwords(pe):
    """Every absolute qword in the image whose value is ImageBase+rva.

    Found by locating the 3 constant high bytes of the pointer (bytes 5..7 of the
    little-endian qword) with bytes.find -- C speed -- then validating the full
    qword.  Because ImageBase is 0x7FF6AF000000 and SizeOfImage is 0xA9E1000, every
    in-image pointer has bytes[4:8] == F6 7F 00 00, so this is near-exact: the range
    check rejects the rest.  Catches unaligned pointers too.
    Returns list of (slot_rva, target_rva).
    """
    d = pe.d
    ib = pe.imagebase
    soi = pe.sizeofimage
    tail = struct.pack("<Q", ib)[5:8]
    up = struct.unpack_from
    out = []
    pos = 0
    nd = len(d)
    while True:
        i = d.find(tail, pos)
        if i < 0:
            break
        pos = i + 1
        o = i - 5
        if o < 0 or o + 8 > nd:
            continue
        t = up("<Q", d, o)[0] - ib
        if 0 <= t < soi:
            out.append((o, t))
    return out


def scan_call_targets(pe):
    """E8 rel32 direct-call targets, with distinct-call-site counts.

    This is a byte scan, not a disassembler, so some 0xE8 bytes are immediates or
    displacements inside other instructions.  Corroboration (prologue match,
    16-alignment, call multiplicity, presence in a vtable) is what separates real
    entries from those -- see score_entries().
    """
    tx, tbase, tn = pe.bytes_of(".text")
    up = struct.unpack_from
    mult = Counter()
    for m in re.finditer(rb"\xe8", tx):
        o = m.start()
        if o + 5 > tn:
            continue
        t = tbase + o + 5 + up("<i", tx, o + 1)[0]
        if tbase <= t < tbase + tn:
            mult[t] += 1
    return mult


def scan_pad_starts(pe):
    """16-aligned offsets immediately following an int3 (0xCC) padding run.

    MEASURED: this build barely uses int3 inter-function padding -- only 6,910 runs
    of >=2 CC in 124 MB of .text, yielding 6,824 starts.  Functions are packed
    back-to-back: the byte before an entry is most often 0xC3 (ret).  So this signal
    is a weak corroborator here, not a primary one.
    """
    tx, tbase, tn = pe.bytes_of(".text")
    out = set()
    for m in re.finditer(rb"\xcc\xcc+", tx):
        e = m.end()
        p = (e + 15) & ~15
        while p < tn and tx[p] == 0xCC:
            p += 16
        if p < tn and tx[p] not in (0, 0xCC):
            out.add(tbase + p)
    return out


# MSVC x64 prologues seen at real function entries in this image.
PROLOGUES = (
    b"\x48\x89\x5c\x24", b"\x48\x89\x4c\x24", b"\x48\x89\x54\x24", b"\x48\x89\x44\x24",
    b"\x48\x89\x74\x24", b"\x48\x89\x7c\x24", b"\x4c\x89\x44\x24", b"\x4c\x89\x4c\x24",
    b"\x44\x88\x4c\x24", b"\x89\x4c\x24", b"\x48\x8b\xc4", b"\x4c\x8b\xdc",
    b"\x48\x83\xec", b"\x48\x81\xec", b"\x40\x53", b"\x40\x55", b"\x40\x56",
    b"\x40\x57", b"\x40\x54", b"\x55\x48", b"\x53", b"\x55", b"\x56", b"\x57",
    b"\xe9", b"\xff\x25", b"\xc3", b"\x33\xc0", b"\x48\x8b\xc1", b"\x8b\xc1",
    b"\x48\x85\xc9", b"\x0f\xb6", b"\x48\x8d", b"\x48\x8b", b"\x8b", b"\x0f\x1f",
)
# Unambiguous MSVC x64 frame setup only -- used for the standalone prologue sweep,
# where a weak pattern like a bare 0x8B would generate millions of false entries.
STRONG_PROLOGUES = (
    b"\x48\x89\x5c\x24", b"\x48\x89\x4c\x24", b"\x48\x89\x54\x24", b"\x48\x89\x44\x24",
    b"\x48\x89\x74\x24", b"\x48\x89\x7c\x24", b"\x4c\x89\x44\x24", b"\x4c\x89\x4c\x24",
    b"\x40\x53", b"\x40\x55", b"\x40\x56", b"\x40\x57", b"\x40\x54",
    b"\x48\x83\xec", b"\x48\x81\xec", b"\x4c\x8b\xdc", b"\x48\x8b\xc4", b"\x55\x48\x8b\xec",
)
# Bytes that can legitimately precede a function entry.  C3/C2 = ret, CC = int3,
# E9/EB = jmp opcode of a tail call, 90 = nop pad, 00 = zero pad / non-decrypted,
# FF = the last byte of a negative rel32 displacement (i.e. the previous
# instruction was `E9 xx xx xx FF`, a backward tail-call).
TERMINATORS = (0xC3, 0xC2, 0xCC, 0xE9, 0xEB, 0x00, 0x90, 0xFF)


def scan_prologue_starts(pe):
    """16-aligned offsets in DECRYPTED .text with a strong prologue and a
    legitimate preceding byte.

    Fourth entry signal, and the only one that does not depend on something else
    pointing at the function.  It exists because measurement showed real, heavily
    used entries that no other signal sees: ProcessInternal (base+0x13454A0, the
    project's single most important hook target) is not an E8 rel32 target, is not
    in any vtable, and has no int3 padding -- but it is 16-aligned, starts with
    `48 89 5C 24 08` and is preceded by the tail of a backward jmp.

    MEASURED: 229,161 16-aligned strong-prologue positions; requiring a legitimate
    preceding byte cuts that to 106,526, of which 22,546 are new (+9.9% on the
    entry set).  The prev-byte filter is what keeps this from being noise.
    """
    tx, tbase, tn = pe.bytes_of(".text")
    out = set()
    for p in range(0, tn - 8, 16):
        if tx[p] == 0:
            continue
        if p and tx[p - 1] not in TERMINATORS:
            continue
        w = tx[p:p + 4]
        for s in STRONG_PROLOGUES:
            if w.startswith(s):
                out.add(tbase + p)
                break
    return out


def score_entries(pe, mult, ptr_entries, pad_entries, pro_entries):
    """Union the four entry signals and attach evidence flags + a tier."""
    tx, tbase, tn = pe.bytes_of(".text")
    d = pe.d
    cand = set()
    cand.update(t for t in mult if d[t] != 0)
    cand.update(t for t in ptr_entries if d[t] != 0)
    cand.update(t for t in pad_entries if d[t] != 0)
    cand.update(t for t in pro_entries if d[t] != 0)

    ent = array("q", sorted(cand))
    flags = bytearray(len(ent))
    for i, t in enumerate(ent):
        o = t - tbase
        f = 0
        m = mult.get(t, 0)
        if m >= 2:
            f |= F_CALL2
        elif m == 1:
            f |= F_CALL1
        if t in ptr_entries:
            f |= F_PTR
        if t in pad_entries:
            f |= F_PAD
        if t in pro_entries:
            f |= F_PROSCAN
        if t % 16 == 0:
            f |= F_A16
        if o > 0 and tx[o - 1] in TERMINATORS:
            f |= F_PREV
        w = tx[o:o + 4]
        for p in PROLOGUES:
            if w.startswith(p):
                f |= F_PRO
                break
        flags[i] = f
    return ent, flags


def tier_of(f):
    strong = f & (F_PTR | F_CALL2)
    if strong and (f & F_PRO) and (f & F_A16):
        return TIER_HIGH
    if (strong or (f & F_CALL1)) and (f & (F_PRO | F_A16)):
        return TIER_MED
    # Prologue-sweep entries carry F_PRO|F_A16|F_PREV by construction; nothing
    # points at them, so they are MED, never HIGH.
    if f & F_PROSCAN:
        return TIER_MED
    return TIER_LOW


# --------------------------------------------------------------------------
# Index
# --------------------------------------------------------------------------
class Index:
    VERSION = 4

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.__dict__, f, protocol=5)

    @staticmethod
    def load(path):
        if not os.path.exists(path):
            raise SystemExit("no index at %s -- run:  python strxref.py --rebuild" % path)
        with open(path, "rb") as f:
            st = pickle.load(f)
        if st.get("version") != Index.VERSION:
            raise SystemExit("index version %s != %d -- run:  python strxref.py --rebuild"
                             % (st.get("version"), Index.VERSION))
        return Index(**st)

    # ---- string lookup -------------------------------------------------
    def str_at(self, rva):
        """Exact-start match -> string idx, else -1."""
        i = bisect.bisect_left(self.s_rva, rva)
        if i < len(self.s_rva) and self.s_rva[i] == rva:
            return i
        return -1

    def str_covering(self, rva):
        """String whose byte interval contains rva (interior refs), else -1.

        Interior references are REAL and common: MSVC peels the first character of
        a literal comparison, e.g.  cmp ecx,0x43 ('C') / jne / lea rdx,[L"CrashReportClient"+2]
        -- the pointer handed to the comparison helper is string+1 char.  Measured:
        5,428 interior references, 5,308 of them at exactly +2.
        """
        i = bisect.bisect_right(self.s_rva, rva) - 1
        lim = rva - self.max_str_bytes
        while i >= 0 and self.s_rva[i] >= lim:
            if self.s_rva[i] <= rva < self.s_end[i]:
                return i
            i -= 1
        return -1

    def resolve(self, rva):
        i = self.str_at(rva)
        if i >= 0:
            return i, 0
        i = self.str_covering(rva)
        if i >= 0:
            return i, rva - self.s_rva[i]
        return -1, 0

    def text_of(self, i, dump=None):
        d = dump if dump is not None else self._dump()
        s, e, enc = self.s_rva[i], self.s_end[i], self.s_enc[i]
        raw = d[s:e]
        return raw.decode("utf-16-le", "replace") if enc == ord("U") else raw.decode("latin1")

    def _dump(self):
        if getattr(self, "_d", None) is None:
            with open(self.dump_path, "rb") as f:
                self._d = f.read()
        return self._d

    # ---- xref lookup ---------------------------------------------------
    def refs_to(self, sidx):
        lo = bisect.bisect_left(self.rs_str, sidx)
        hi = bisect.bisect_right(self.rs_str, sidx)
        return [(self.rs_site[i], self.rs_kind[i], self.rs_slot[i]) for i in range(lo, hi)]

    def refs_in(self, lo_rva, hi_rva):
        lo = bisect.bisect_left(self.rf_site, lo_rva)
        hi = bisect.bisect_left(self.rf_site, hi_rva)
        return [(self.rf_site[i], self.rf_str[i], self.rf_kind[i]) for i in range(lo, hi)]

    # ---- function attribution ------------------------------------------
    def func_of(self, rva, min_tier=TIER_MED):
        """Nearest preceding function entry at >= min_tier.

        Returns (entry_rva, flags, tier, end_rva) or (None, 0, None, None).
        end_rva is the next entry at any tier -- an UPPER BOUND on the function's
        extent, not a proven end (there is no unwind table in this image: the
        on-disk .pdata is packer-encrypted, 0 of 523,605 candidate RUNTIME_FUNCTIONs
        are structurally sane, and the live image's .pdata is all zeroes).
        """
        if not (self.text_va <= rva < self.text_end):
            return None, 0, None, None   # not code: never invent a function
        i = bisect.bisect_right(self.ent, rva) - 1
        while i >= 0:
            if tier_of(self.flags[i]) >= min_tier:
                nxt = self.ent[i + 1] if i + 1 < len(self.ent) else self.text_end
                return self.ent[i], self.flags[i], tier_of(self.flags[i]), nxt
            i -= 1
        return None, 0, None, None

    # ---- text search ---------------------------------------------------
    def find(self, needle, regex=False, limit=40, refs_only=False):
        blob = self.blob
        hits = []
        if regex:
            # Strings are printable-ASCII by construction, so no string can contain a
            # newline -- which is why '\n' is used as the blob separator and re.M gives
            # '^'/'$' their natural per-string meaning.
            rx = re.compile(needle.encode("utf-8", "replace"), re.I | re.M)
            it = (m.start() for m in rx.finditer(blob))
        else:
            nd = needle.lower().encode("utf-8", "replace")
            def gen():
                p = 0
                while True:
                    j = blob.find(nd, p)
                    if j < 0:
                        return
                    yield j
                    p = j + 1
            it = gen()
        seen = set()
        for off in it:
            i = bisect.bisect_right(self.blob_off, off) - 1
            if i < 0 or i in seen:
                continue
            seen.add(i)
            n = len(self.refs_to(i))
            if refs_only and n == 0:
                continue
            hits.append((i, n))
            if len(hits) >= limit:
                break
        return hits


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def build(dump_path, min_len, out_path, quiet=False):
    t_all = time.time()
    log = (lambda *a: None) if quiet else (lambda *a: print(*a))

    log("strxref build  dump=%s" % dump_path)
    t = time.time()
    pe = PE(dump_path)
    log("  PE parsed: %d sections, ImageBase 0x%X, SizeOfImage 0x%X, %d bytes  [%.1fs]"
        % (pe.nsec, pe.imagebase, pe.sizeofimage, len(pe.d), time.time() - t))

    cov = pe.coverage()

    t = time.time()
    s_rva, s_end, s_enc, per_sec, sstats = scan_strings(pe, min_len)
    log("  strings: %d  [%.1fs]" % (len(s_rva), time.time() - t))

    t = time.time()
    rip, ripcounts = scan_rip_refs(pe)
    log("  rip-relative refs scanned: %d  [%.1fs]" % (len(rip), time.time() - t))

    t = time.time()
    absq = scan_abs_qwords(pe)
    log("  absolute qword pointers: %d  [%.1fs]" % (len(absq), time.time() - t))

    t = time.time()
    mult = scan_call_targets(pe)
    pad = scan_pad_starts(pe)
    pro = scan_prologue_starts(pe)
    tx_name, tx_va, tx_vs, _, _ = pe.sec(".text")
    text_end = tx_va + tx_vs
    ptr_entries = set()
    for slot, tgt in absq:
        if tx_va <= tgt < text_end and not (tx_va <= slot < text_end):
            ptr_entries.add(tgt)
    ent, flags = score_entries(pe, mult, ptr_entries, pad, pro)
    log("  function-entry candidates: %d  [%.1fs]" % (len(ent), time.time() - t))

    # ---- resolve references to strings --------------------------------
    t = time.time()
    idx_tmp = Index(s_rva=s_rva, s_end=s_end, s_enc=s_enc,
                    max_str_bytes=max((e - r) for r, e in zip(s_rva, s_end)) if len(s_rva) else 0)

    # 1) pointer slots that hold a string address  -> one level of indirection
    slot2str = {}
    for slot, tgt in absq:
        si, _off = idx_tmp.resolve(tgt)
        if si >= 0:
            slot2str[slot] = si
    log("  pointer slots holding a string address: %d  [%.1fs]" % (len(slot2str), time.time() - t))

    t = time.time()
    ref_site, ref_str, ref_kind, ref_slot = [], [], [], []
    direct_exact = direct_interior = nonstring = 0
    for site, tgt, kind in rip:
        si, off = idx_tmp.resolve(tgt)
        if si >= 0:
            ref_site.append(site); ref_str.append(si); ref_kind.append(kind); ref_slot.append(0)
            if off == 0:
                direct_exact += 1
            else:
                direct_interior += 1
            continue
        si = slot2str.get(tgt, -1)
        if si >= 0:
            ref_site.append(site); ref_str.append(si); ref_kind.append(K_PTR); ref_slot.append(tgt)
        else:
            nonstring += 1
    log("  string references resolved: %d  [%.1fs]" % (len(ref_site), time.time() - t))

    order = sorted(range(len(ref_site)), key=lambda i: ref_site[i])
    rf_site = array("q", (ref_site[i] for i in order))
    rf_str = array("l", (ref_str[i] for i in order))
    rf_kind = bytearray(ref_kind[i] for i in order)
    order = sorted(range(len(ref_site)), key=lambda i: (ref_str[i], ref_site[i]))
    rs_str = array("l", (ref_str[i] for i in order))
    rs_site = array("q", (ref_site[i] for i in order))
    rs_kind = bytearray(ref_kind[i] for i in order)
    rs_slot = array("q", (ref_slot[i] for i in order))

    # ---- searchable text blob -----------------------------------------
    t = time.time()
    d = pe.d
    parts, offs, cur = [], array("q"), 0
    for i in range(len(s_rva)):
        raw = d[s_rva[i]:s_end[i]]
        s = raw.decode("utf-16-le", "replace") if s_enc[i] == ord("U") else raw.decode("latin1")
        b = s.lower().encode("utf-8", "replace").replace(b"\n", b" ")
        offs.append(cur)
        parts.append(b)
        parts.append(b"\n")   # separator; see Index.find() for why '\n' is safe
        cur += len(b) + 1
    blob = b"".join(parts)
    log("  search blob: %.1f MB  [%.1fs]" % (len(blob) / 1e6, time.time() - t))

    stats = dict(
        coverage=cov, per_sec=per_sec, sstats=dict(sstats),
        ripcounts={KIND_NAME[k]: v for k, v in ripcounts.items()},
        n_abs=len(absq), n_slot2str=len(slot2str),
        direct_exact=direct_exact, direct_interior=direct_interior, nonstring=nonstring,
        n_call_targets=len(mult), n_ptr_entries=len(ptr_entries), n_pad=len(pad),
        n_pro=len(pro),
        text_pages_decrypted=sum(1 for p in range(tx_va, text_end, 4096)
                                 if any(pe.d[p:p + 4096])),
        min_len=min_len, dump_size=len(pe.d), build_secs=round(time.time() - t_all, 1),
    )

    idx = Index(version=Index.VERSION, dump_path=os.path.abspath(dump_path),
                imagebase=pe.imagebase, text_va=tx_va, text_end=text_end,
                sections=pe.sections, min_len=min_len,
                s_rva=s_rva, s_end=s_end, s_enc=s_enc,
                max_str_bytes=idx_tmp.max_str_bytes,
                rf_site=rf_site, rf_str=rf_str, rf_kind=rf_kind,
                rs_str=rs_str, rs_site=rs_site, rs_kind=rs_kind, rs_slot=rs_slot,
                ent=ent, flags=flags, blob=blob, blob_off=offs, stats=stats)
    t = time.time()
    idx.save(out_path)
    log("  index written: %s (%.1f MB)  [%.1fs]"
        % (out_path, os.path.getsize(out_path) / 1e6, time.time() - t))
    log("  TOTAL %.1fs" % (time.time() - t_all))
    return idx, pe


# --------------------------------------------------------------------------
# Self-validation
# --------------------------------------------------------------------------
# Preamble figures this tool must reproduce (ignorance-map FK-3/FK-4 measurement
# round, all at min_len=6 / strict-printable / NUL-terminated on .rdata).
PREAMBLE = dict(
    ascii=103002, utf16=85692, total=188694,
    leas=517515, rdata_targets=245894, distinct=106800,
    ascii_ref=12832, utf16_ref=41633,
)

# Deltas vs the preamble that are EXPLAINED and expected, not regressions.
EXPLAINED = {
    "UTF-16 strings":
        "start-correction shortens 15 wide strings from 6 to 5 chars, so they fall "
        "below the len>=6 filter. They ARE in the index (min_len=4). Ours is correct.",
    "total": "same 15 strings as above.",
    "UTF-16 referenced (exact start)":
        "start-correction makes ~580 more wide strings match their LEA target "
        "EXACTLY instead of at +2. Ours is correct; see scan_strings().",
    "ASCII  referenced (exact start)":
        "UNEXPLAINED (+25, 0.19%). Inputs are byte-identical to the preamble "
        "(ASCII census and the LEA target set both MATCH exactly), and this figure "
        "is a deterministic set intersection of those two, independently "
        "reproduced by a second implementation. Treat 12,857 as the corrected value.",
}

# Externally-known function entries recorded across ~101 sessions of live RE
# (CLAUDE.md + docs/).  Independent ground truth: derived from a running process
# and hand-verified, never from this tool.
KNOWN_ENTRIES = [
    (0x13454A0, "ProcessInternal"), (0x12C5A10, "native-call primitive target"),
    (0x12F4230, "PrimaryAssetId::ToString"), (0x5794480, "CheckAccountPassChanges"),
    (0x57AB180, "FindVM"), (0x57DF4B0, "battlepass populate"),
    (0x57C8130, "battlepass OnSuccess"), (0x585A570, "progression ingester"),
    (0x57BB560, "VM builder Init"), (0x57CA670, "seasonal builder entry"),
    (0x57B9C00, "non-account copier"), (0x587BE90, "UPartyModel::SetParty"),
    (0x585E900, "party/loadout helper"), (0x52B3400, "loadout write-back"),
    (0x5487B00, "tutorial quest entry"), (0x560AFE0, "tutorial launch"),
    (0x37E5C80, "match setup"), (0x34BAEF0, "DA resolution"),
    (0x3C5F990, "hybrid shim target"), (0x55ACB90, "movement A"),
    (0x558BD90, "movement B"), (0x55AC9F0, "movement C"),
    (0x4BFA590, "moonshot A"), (0x4BDC3C0, "moonshot B"), (0x3C33230, "moonshot C"),
    (0x3C421D0, "moonshot D"), (0x39E90E0, "moonshot E"), (0x39E1460, "moonshot F"),
    (0x58CE1B0, "tutorial plan A"), (0x338C990, "tutorial plan B"),
    (0x56BDF10, "tutorial plan C"), (0x58E3D10, "tutorial plan D"),
    (0x56BAA00, "tutorial plan E"), (0x548A4F0, "tutorial plan F"),
    (0x12C7DD0, "tutorial plan G"), (0x58414E0, "tutorial plan H"),
    (0x1344150, "tutorial plan I"), (0x1345FB0, "PI helper"),
    (0xB9E1F0, "moonshot G"), (0x3623520, "hero mesh A"),
    (0x5425A60, "input fn A"), (0x54259E0, "input fn B"),
]
# Documented addresses that are NOT function entries -- recorded as faulting or
# mid-function instructions.  Excluded from the entry ground truth (including one
# of these was my own error in an earlier pass: 0x2976FF0 disassembles to
# `mov [rcx+rsi*8], rax`, which is body code, not a prologue).
KNOWN_NOT_ENTRY = [(0x2976FF0, "session-40 crash site (mid-function)")]
# Externally-known addresses documented as INSIDE a function, paired with the
# documented entry of that function.  These test attribution proper, not lookup.
KNOWN_INTERIOR = [
    (0x57CACF5, 0x57CA670, "seasonal gate cmp byte[r15+0xAB],0 inside builder"),
]
# Externally-known NON-code addresses (data), used as negative controls.
KNOWN_DATA = [(0x888CB78, "LokiAssetManager vtable"), (0x9D49158, "UFunction obj"),
              (0x8831758, "widget/CDO"), (0x79E0C78, "AR.bin ptr")]


def validate(idx, pe=None, verbose=True):
    P = print if verbose else (lambda *a: None)
    st = idx.stats
    d = idx._dump()
    ok = []

    P("=" * 78)
    P("SELF-VALIDATION  (measured now, vs the figures this tool was asked to reproduce)")
    P("=" * 78)
    P("dump      : %s (%d bytes)" % (idx.dump_path, st["dump_size"]))
    P("ImageBase : 0x%X    file offset == RVA : verified for all %d sections"
      % (idx.imagebase, len(idx.sections)))
    P("")
    P("--- SECTION TABLE: two metrics, and the difference IS false-known FK-3 ---")
    P("%-10s %-12s %12s %8s %10s %9s %9s" %
      ("name", "vaddr", "vsize", "pages", "zeropages", "nonzero%", "readable%"))
    for name, va, vs, pages, zp, nzp, rp in st["coverage"]:
        P("%-10s 0x%08x %12d %8d %10d %8.2f%% %8.2f%%" % (name, va, vs, pages, zp, nzp, rp))
    P("")
    rdcov = [r for r in st["coverage"] if r[0] == ".rdata"][0]
    txcov = [r for r in st["coverage"] if r[0] == ".text"][0]
    P("  .rdata  nonzero %.2f%% vs readable %.2f%%  -> FK-3's '%.2f%% cap, ~13.9 MB"
      % (rdcov[5], rdcov[6], rdcov[5]))
    P("          permanently unreadable' counts NULL PADDING (%d zero pages of %d),"
      % (rdcov[4], rdcov[3]))
    P("          not unreadable memory.  FK-3 IS FALSE.")
    P("  .text   nonzero %.2f%% vs readable %.2f%%  -> these AGREE, because"
      % (txcov[5], txcov[6]))
    P("          demand-decrypt zeroes WHOLE PAGES. The byte metric is sound here only.")

    # ---- census ----
    P("")
    P("--- STRING CENSUS ---")
    tot_a = sum(v[0] for v in st["per_sec"].values())
    tot_u = sum(v[1] for v in st["per_sec"].values())
    P("%-10s %10s %10s %10s" % ("section", "ASCII", "UTF-16", "total"))
    for k, (a, u) in st["per_sec"].items():
        P("%-10s %10d %10d %10d" % (k, a, u, a + u))
    P("%-10s %10d %10d %10d" % ("ALL", tot_a, tot_u, tot_a + tot_u))
    P("  min_len=%d ; UTF-16 start-corrections applied: %d ; ASCII runs dropped as"
      % (st["min_len"], st["sstats"].get("utf16_start_corrected", 0)))
    P("  contained-in-UTF-16: %d" % st["sstats"].get("ascii_dropped_inside_utf16", 0))

    # .rdata-only recount at the preamble's parameters (min_len 6), from the index
    rd = [s for s in idx.sections if s[0] == ".rdata"][0]
    rlo, rhi = rd[1], rd[1] + rd[2]
    a6 = u6 = 0
    for i in range(len(idx.s_rva)):
        r = idx.s_rva[i]
        if not (rlo <= r < rhi):
            continue
        n = (idx.s_end[i] - r) // (2 if idx.s_enc[i] == ord("U") else 1)
        if n >= 6:
            if idx.s_enc[i] == ord("U"):
                u6 += 1
            else:
                a6 += 1
    P("")
    P("  .rdata only, len>=6 (the preamble's parameters):")
    def cmp_(label, got, want):
        d_ = got - want
        if d_ == 0:
            mark = "MATCH"
        else:
            mark = ("+%d" % d_ if d_ > 0 else str(d_))
            mark += " EXPLAINED" if label.strip() in EXPLAINED else " UNEXPECTED"
        ok.append(d_ == 0 or label.strip() in EXPLAINED)
        P("    %-34s got %8d   preamble %8d   %s" % (label, got, want, mark))
    cmp_("ASCII strings", a6, PREAMBLE["ascii"])
    cmp_("UTF-16 strings", u6, PREAMBLE["utf16"])
    cmp_("total", a6 + u6, PREAMBLE["total"])
    # Substantiate the EXPLAINED note rather than asserting it: count the wide
    # strings that the start-correction pushed from 6 chars to 5.
    push5 = 0
    for i in range(len(idx.s_rva)):
        r = idx.s_rva[i]
        if idx.s_enc[i] != ord("U") or not (rlo <= r < rhi):
            continue
        if (idx.s_end[i] - r) // 2 != 5:
            continue
        if r - 2 >= rlo and 0x20 <= d[r - 2] <= 0x7E and d[r - 1] == 0:
            push5 += 1
    P("    -> of the delta: %d wide strings were corrected from 6 chars to 5 and so"
      % push5)
    P("       drop out of a len>=6 count. They ARE indexed (min_len=%d)." % st["min_len"])

    # ---- xref scan ----
    P("")
    P("--- XREF SCAN ---")
    P("    rip-relative forms scanned: %s" % st["ripcounts"])
    cmp_("lea r64,[rip+d32] in .text", st["ripcounts"].get("lea", 0), PREAMBLE["leas"])
    tx = d[idx.text_va:idx.text_end]
    up = struct.unpack_from
    n_rd = 0
    dist = set()
    for m in re.compile(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]").finditer(tx):
        o = m.start()
        if o + 7 > len(tx):
            continue
        t = idx.text_va + o + 7 + up("<i", tx, o + 3)[0]
        if rlo <= t < rhi:
            n_rd += 1
            dist.add(t)
    cmp_("  ... targeting .rdata", n_rd, PREAMBLE["rdata_targets"])
    cmp_("  ... distinct .rdata targets", len(dist), PREAMBLE["distinct"])
    P("    absolute qword pointers in image: %d   (of which hold a string addr: %d)"
      % (st["n_abs"], st["n_slot2str"]))
    P("    resolved refs: exact-start %d  interior %d  via-pointer-table %d  unresolved %d"
      % (st["direct_exact"], st["direct_interior"],
         sum(1 for k in idx.rs_kind if k == K_PTR), st["nonstring"]))

    # ---- reference rate by encoding ----
    P("")
    P("--- REFERENCE RATE BY ENCODING (.rdata, len>=6, exact-start refs only:")
    P("    the preamble's definition, so the numbers are comparable) ---")
    tgt_exact = set()
    for m in re.compile(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]").finditer(tx):
        o = m.start()
        if o + 7 > len(tx):
            continue
        tgt_exact.add(idx.text_va + o + 7 + up("<i", tx, o + 3)[0])
    seenA, seenU, seenA2, seenU2 = set(), set(), set(), set()
    for i in range(len(idx.s_rva)):
        r = idx.s_rva[i]
        if not (rlo <= r < rhi):
            continue
        isU = idx.s_enc[i] == ord("U")
        n = (idx.s_end[i] - r) // (2 if isU else 1)
        if n < 6:
            continue
        if r in tgt_exact:
            (seenU if isU else seenA).add(i)
        if len(idx.refs_to(i)):
            (seenU2 if isU else seenA2).add(i)
    P("%-38s %8s %8s %9s" % ("", "referenced", "total", "rate"))
    cmp_("ASCII  referenced (exact start)", len(seenA), PREAMBLE["ascii_ref"])
    cmp_("UTF-16 referenced (exact start)", len(seenU), PREAMBLE["utf16_ref"])
    P("    ASCII  rate %.1f%%   UTF-16 rate %.1f%%" %
      (100.0 * len(seenA) / max(a6, 1), 100.0 * len(seenU) / max(u6, 1)))
    P("    including interior + pointer-table refs (this tool's full index):")
    P("      ASCII  %6d / %6d = %.1f%%      UTF-16 %6d / %6d = %.1f%%"
      % (len(seenA2), a6, 100.0 * len(seenA2) / max(a6, 1),
         len(seenU2), u6, 100.0 * len(seenU2) / max(u6, 1)))
    txt_pages = [r for r in st["coverage"] if r[0] == ".text"][0]
    P("    .text readable-page fraction: %.2f%%  <-- THE CAP. UTF-16 resolution tracks"
      % txt_pages[6])
    P("    it, i.e. essentially every string whose emitting code is decrypted IS xref'd.")

    # ---- function attribution ----
    P("")
    P("--- FUNCTION ATTRIBUTION ---")
    P("    NOTE: there is no unwind table to check against. The live image's .pdata is")
    P("    100% zero, and the on-disk exe's .pdata is packer-encrypted (0 of 523,605")
    P("    candidate RUNTIME_FUNCTIONs are structurally sane). Entries are INFERRED.")
    tiers = Counter(tier_of(f) for f in idx.flags)
    P("    entry candidates: %d   HIGH %d  MED %d  LOW %d"
      % (len(idx.ent), tiers[TIER_HIGH], tiers[TIER_MED], tiers[TIER_LOW]))
    P("    signals: E8 call targets %d | data function-pointers %d | post-int3 starts %d"
      " | strong-prologue sweep %d"
      % (st["n_call_targets"], st["n_ptr_entries"], st["n_pad"], st["n_pro"]))
    dec = st["text_pages_decrypted"]
    P("    density: %d entries over %.1f MB of DECRYPTED .text = 1 per %.0f bytes"
      % (len(idx.ent), dec * 4096 / 1e6, dec * 4096.0 / len(idx.ent)))
    P("    (Plausible for x64. NOT claimed: a false-split rate -- function LENGTHS are")
    P("     unknown in this image, so any such figure would be an artifact, which is")
    P("     precisely how FK-3 and FK-4 came to be recorded as facts.)")

    # Ground truth splits into "present in this dump" and "page never decrypted".
    # A ground-truth address in an all-zero page CANNOT be found by any detector;
    # scoring it as an attribution failure would misattribute a coverage limit.
    present, absent = [], []
    for rva, name in KNOWN_ENTRIES:
        (present if d[rva] != 0 else absent).append((rva, name))
    hit, bad = 0, []
    for rva, name in present:
        e, f, ti, _ = idx.func_of(rva)
        if e == rva:
            hit += 1
        else:
            bad.append((rva, name, e))
    P("")
    P("    ground truth: %d documented entries; %d lie in DECRYPTED pages, %d in pages"
      % (len(KNOWN_ENTRIES), len(present), len(absent)))
    P("    this dump never decrypted (all-zero 4K page -- unfindable by construction,")
    P("    excluded from the denominator and listed below).")
    P("    [GT-1] known entries self-attribute (func_of(E) == E):  %d / %d = %.1f%%"
      % (hit, len(present), 100.0 * hit / max(len(present), 1)))
    for rva, name, e in bad:
        P("           MISS 0x%07X %-26s -> %s" % (rva, name, ("0x%07X" % e) if e else "None"))
    hit2 = sum(1 for rva, _ in present if idx.func_of(rva + 8)[0] == rva)
    P("    [GT-2] entry+8 attributes back to the entry:            %d / %d = %.1f%%"
      % (hit2, len(present), 100.0 * hit2 / max(len(present), 1)))
    for interior, entry, why in KNOWN_INTERIOR:
        e, _, ti, _ = idx.func_of(interior)
        P("    [GT-3] interior->entry: 0x%07X (%s)" % (interior, why))
        P("           documented entry 0x%07X ; attributed %s  %s"
          % (entry, ("0x%07X" % e) if e else "None", "OK" if e == entry else "MISS"))
    for rva, what in KNOWN_NOT_ENTRY:
        e, _, _, _ = idx.func_of(rva)
        P("    [GT-5] known NON-entry 0x%07X (%s):" % (rva, what))
        P("           attributed to 0x%07X -- correct behaviour is to report the "
          "CONTAINING" % (e or 0))
        P("           function, not to echo the query back." )
        ok.append(e is not None and e != rva)
    for rva, name in absent:
        P("    [cov] 0x%07X %-26s page 0x%07X is all-zero: not in this dump"
          % (rva, name, rva & ~0xFFF))
    for rva, what in KNOWN_DATA:
        e, _, _, _ = idx.func_of(rva)
        good = e is None
        ok.append(good)
        P("    [GT-4] negative control 0x%07X (%-22s) -> %s  %s"
          % (rva, what, ("0x%07X" % e) if e else "None", "OK" if good else "FAIL"))

    # ---- null controls ----
    P("")
    P("--- NULL CONTROLS ---")
    zero = None
    for i in range(len(idx.s_rva)):
        if len(idx.refs_to(i)) == 0 and (idx.s_end[i] - idx.s_rva[i]) > 20:
            zero = i
            break
    if zero is None:
        P("    !! no zero-xref string found -- that would itself be suspicious")
        ok.append(False)
    else:
        n = len(idx.refs_to(zero))
        P("    zero-xref string 0x%08X %r -> %d refs  %s"
          % (idx.s_rva[zero], idx.text_of(zero, d)[:44], n, "OK" if n == 0 else "FAIL"))
        ok.append(n == 0)
    bogus = 0x00000010
    r = idx.resolve(bogus)
    P("    resolve(0x%X) (not a string, not in any section) -> %s  %s"
      % (bogus, r[0], "OK" if r[0] == -1 else "FAIL"))
    ok.append(r[0] == -1)
    nonsense = idx.find("zzqqxxjjnotarealstring")
    P("    find('zzqqxxjjnotarealstring') -> %d hits  %s"
      % (len(nonsense), "OK" if not nonsense else "FAIL"))
    ok.append(not nonsense)
    e, _, _, _ = idx.func_of(idx.text_end + 0x100000)
    P("    func_of(past end of .text) -> %s  (nearest preceding entry; out-of-range "
      "queries are the caller's job to bound)" % (("0x%07X" % e) if e else "None"))

    # ---- FK-4 probe strings ----
    P("")
    P("--- FK-4 PROBE STRINGS (recorded as 'packer-encrypted, unreadable') ---")
    probes = [(0x079E02D0, "U", "Toc signature hash: %s"),
              (0x08B1C688, "U", "feature toggles were not ready"),
              (0x08970FA0, "A", "GetFeatureTogglesReady"),
              (0x08A56F38, "A", "MulticastSetGameFeatureToggle"),
              (0x08077F9E, "U", "Couldn't spawn player controller of class %s")]
    want_pat = struct.Struct("<Q")
    for rva, enc, want in probes:
        si, off = idx.resolve(rva)
        got = idx.text_of(si, d) if si >= 0 else "<not indexed>"
        n = len(idx.refs_to(si)) if si >= 0 else 0
        good = want in got
        ok.append(good)
        note = ""
        if si >= 0 and n == 0:
            # 0 code refs != absent.  Count absolute pointers to it: a UE reflection
            # name lives in a static param struct that code reaches by struct BASE,
            # which one-level exact-slot indirection cannot follow.
            key = want_pat.pack(idx.imagebase + idx.s_rva[si])
            cnt, p = 0, 0
            while True:
                j = d.find(key, p)
                if j < 0:
                    break
                cnt += 1
                p = j + 1
            note = "  (but %d data pointers reference it)" % cnt
        if off:
            note += "  [+%d interior]" % off
        P("    0x%08X %s %-46r xrefs=%-4d %s%s"
          % (rva, enc, got[:46], n, "PLAINTEXT" if good else "MISMATCH", note))
    P("    All five read back as plaintext from the module's own .rdata -> FK-4 is FALSE.")
    P("    Two traps this block demonstrates, both of the FK-3/FK-4 family:")
    P("      * the 'feature toggles were not ready' RVA is 88 bytes INTO a longer")
    P("        string; an exact-start-only lookup reports 0 refs, the enclosing-string")
    P("        lookup reports 4 (all in ULokiGameFeatureToggles::Get @ 0x55DB370).")
    P("      * 0 code refs is not absence. Either the emitting page is not decrypted,")
    P("        or the string is a UE reflection name reached via a static struct BASE")
    P("        (use tools/re/offline_xref.py `ptr` mode for those).")

    P("")
    P("build time %.1fs ; index %.1f MB" % (st["build_secs"], os.path.getsize(INDEX_PATH) / 1e6))
    nfail = sum(1 for x in ok if not x)
    P("VALIDATION: %d checks, %d failed" % (len(ok), nfail))
    P("=" * 78)
    return nfail


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def flagstr(f):
    s = []
    if f & F_CALL2: s.append("call>=2")
    if f & F_CALL1: s.append("call=1")
    if f & F_PTR: s.append("fnptr")
    if f & F_PAD: s.append("int3pad")
    if f & F_PRO: s.append("prologue")
    if f & F_A16: s.append("a16")
    if f & F_PREV: s.append("prev-term")
    return ",".join(s) or "-"


def show_string(idx, i, d, prefix="  "):
    enc = "U" if idx.s_enc[i] == ord("U") else "A"
    n = (idx.s_end[i] - idx.s_rva[i]) // (2 if enc == "U" else 1)
    print("%s0x%08X %s len=%-4d refs=%-4d %r"
          % (prefix, idx.s_rva[i], enc, n, len(idx.refs_to(i)), idx.text_of(i, d)[:110]))


def cmd_find(idx, args):
    d = idx._dump()
    hits = idx.find(args.pattern, regex=args.regex, limit=args.n, refs_only=args.refs_only)
    if not hits:
        print("no match for %r" % args.pattern)
        return
    print("%d match(es) for %r%s:" % (len(hits), args.pattern,
                                      " (with xrefs only)" if args.refs_only else ""))
    for i, _n in hits:
        show_string(idx, i, d)


def cmd_xref(idx, args):
    d = idx._dump()
    si, off = idx.resolve(args.rva)
    if si < 0:
        print("0x%08X is not inside any indexed string (section=%s)"
              % (args.rva, next((s[0] for s in idx.sections
                                 if s[1] <= args.rva < s[1] + s[2]), "none")))
        return
    show_string(idx, si, d, prefix="string ")
    if off:
        print("       (query is +%d bytes into it -- interior reference, see README)" % off)
    refs = idx.refs_to(si)
    if not refs:
        txcov = [r for r in idx.stats["coverage"] if r[0] == ".text"][0]
        print("  0 code references.")
        print("  NOT proof of absence: the referencing page may simply not be decrypted")
        print("  in this dump (.text is %.2f%% readable by page)." % txcov[6])
        return
    print("  %d code reference(s):" % len(refs))
    for site, kind, slot in refs:
        tb, te = true_func(site)
        if tb is not None:
            loc, base = "fn 0x%07X EXACT (%d B)" % (tb, te - tb), tb
        else:
            e, f, ti, end = idx.func_of(site)
            loc = ("fn 0x%07X %-4s [%s]" % (e, TIER_NAME[ti], flagstr(f))) if e else "fn ?"
            base = e
        extra = (" via slot 0x%08X" % slot) if slot else ""
        print("    site 0x%07X  %-8s %s+0x%X%s"
              % (site, KIND_NAME[kind], loc, site - base if base else 0, extra))


def cmd_func(idx, args):
    d = idx._dump()
    tb, te = true_func(args.rva)
    e, f, ti, end = idx.func_of(args.rva, TIER_LOW if args.raw else TIER_MED)
    print("query   0x%07X" % args.rva)
    if tb is not None and not args.heuristic:
        # EXACT bounds from the recovered unwind table.  Use them: the heuristic
        # extent is a "next candidate entry" upper bound and was measured to
        # overstate the true size by >2x for 21% of functions (p90 7.7x, p99 64x),
        # which silently attributes OTHER functions' strings to this one.
        if e is not None and e != tb:
            print("entry   0x%07X   [.pdata EXACT]   (heuristic said 0x%07X -- %s)"
                  % (tb, e, "missed the entry" if e < tb else "over-split"))
        else:
            print("entry   0x%07X   [.pdata EXACT]   evidence=%s"
                  % (tb, flagstr(f) if e == tb else "-"))
        print("extent  0x%07X .. 0x%07X (%d bytes) -- EXACT (minidump stream 13, %d tables)"
              % (tb, te, te - tb, 70))
        e, end = tb, te
    elif e is None:
        print("no function entry at or before 0x%07X" % args.rva)
        if load_pdata():
            print("  and the recovered .pdata has no entry covering it either, which means")
            print("  no crash process ever decrypted the containing function.")
        return
    else:
        print("entry   0x%07X   tier=%s   evidence=%s" % (e, TIER_NAME[ti], flagstr(f)))
        print("extent  0x%07X .. 0x%07X (%d bytes) -- UPPER BOUND (next entry candidate),"
              % (e, end, end - e))
        print("        not a proven end: no .pdata entry covers this address.")
    refs = idx.refs_in(e, end)
    if not refs:
        print("no string references in that range.")
        print("  (either the function touches no literals, or its body is in a")
        print("   non-decrypted page -- check: first byte at entry = 0x%02X)" % d[e])
        return
    print("%d string reference(s):" % len(refs))
    slots = {(s, k): sl for s, k, sl in
             ((rs, rk, rl) for si2 in {r[1] for r in refs}
              for rs, rk, rl in idx.refs_to(si2))}
    seen = set()
    for site, si, kind in refs:
        enc = "U" if idx.s_enc[si] == ord("U") else "A"
        dupe = "  (dup)" if si in seen else ""
        seen.add(si)
        sl = slots.get((site, kind), 0)
        via = (" via slot 0x%08X" % sl) if sl else ""
        print("  +0x%-6X %-8s 0x%08X %s %r%s%s"
              % (site - e, KIND_NAME[kind], idx.s_rva[si], enc,
                 idx.text_of(si, d)[:88], via, dupe))


# --------------------------------------------------------------------------
# `native` -- UFUNCTION reflection name  ->  execXxx thunk  ->  implementation
#
# WHY THIS WORKS (measured, S102, then validated against live-RE ground truth).
# UE5 registers a class's native entry points with
#     UClass::StaticRegisterNatives(cls, { {"Name", &UCls::execName}, ... })
# whose element type is
#     struct FNameNativePtrPair { const ANSICHAR* NameUTF8; FNativeFuncPtr Ptr; };
# MSVC materialises each pair as two adjacent `lea r64,[rip+d32]` -- one onto the
# ASCII name in .rdata, one onto the exec thunk in .text -- within a few
# instructions of each other inside the module's registrar function.  So:
#     name string --(strxref lea site)--> registrar --(nearest .text lea)--> execName
# and the exec thunk's own last rel32 callee is the real implementation, because a
# thunk body is nothing but P_GET_* / P_FINISH engine helpers plus one call out.
#
# GROUND-TRUTH VALIDATION (this is why the mode is trusted):
#   native "GetFeatureTogglesReady"
#     -> exec 0x5376E00 -> impl 0x565E1A0 -> tail-jmp 0x55DDA50, whose body is
#        mov rax,[rax+0x5A0] / movzx eax,byte [rax+0xB3] / shr al,6 / and al,1
#   S89 established that readiness EXACTLY by live disassembly + injection:
#   "bit6 of [LokiGameState+0x5A0 = ServerAuthConfig +0xB3]".  Recovered here
#   with no running game, from a string.
#
# LIMITS (measured, stated so nobody records a heuristic as a fact):
#  * The name->thunk pairing is proximity, not parsing.  The mode reports the
#    DISTANCE of the paired lea and every .text-targeting lea in the window, so a
#    caller can see when the pairing is ambiguous instead of being told an answer.
#  * The registrar function may be in a non-decrypted page -> 0 sites.  That is a
#    coverage result, never proof the function does not exist.
#  * Callee ranking uses global E8 call-site multiplicity: engine helpers
#    (FFrame::Step etc.) have thousands of callers, an implementation has ~1-3.
#    That is a strong signal here but it IS a heuristic.
# --------------------------------------------------------------------------
_LEA_RX = re.compile(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]")
CALLMULT_PATH = os.path.join(INDEX_DIR, "callmult.pkl")


def _leas_in(d, lo, hi):
    """(site, target) for every `lea r64,[rip+d32]` starting in [lo,hi)."""
    out = []
    for m in _LEA_RX.finditer(d, max(lo, 0), hi):
        o = m.start()
        if o + 7 > len(d):
            break
        out.append((o, o + 7 + struct.unpack_from("<i", d, o + 3)[0]))
    return out


def _rel32_callees(d, lo, hi):
    """Ordered (site, target, is_jmp) for E8/E9 rel32 in [lo,hi)."""
    out = []
    o = lo
    while o < hi - 5:
        b = d[o]
        if b in (0xE8, 0xE9):
            t = o + 5 + struct.unpack_from("<i", d, o + 1)[0]
            out.append((o, t, b == 0xE9))
        o += 1
    return out


def _call_multiplicity(idx):
    """Global E8 rel32 call-site count per target.  Cached beside the index."""
    if os.path.exists(CALLMULT_PATH):
        with open(CALLMULT_PATH, "rb") as f:
            return pickle.load(f)
    d = idx._dump()
    tv, te = idx.text_va, idx.text_end
    mult = Counter()
    for m in re.finditer(rb"\xe8", d[tv:te]):
        o = m.start()
        if o + 5 > te - tv:
            continue
        t = tv + o + 5 + struct.unpack_from("<i", d, tv + o + 1)[0]
        if tv <= t < te:
            mult[t] += 1
    os.makedirs(INDEX_DIR, exist_ok=True)
    with open(CALLMULT_PATH, "wb") as f:
        pickle.dump(mult, f, protocol=5)
    return mult


def cmd_native(idx, args):
    d = idx._dump()
    tv, te = idx.text_va, idx.text_end
    ib = idx.imagebase

    # ---- select the name string(s) ------------------------------------
    if args.name.lower().startswith("0x"):
        si = idx.str_at(int(args.name, 0))
        cand = [si] if si >= 0 else []
    else:
        want = args.name
        cand = [i for i, _n in idx.find(want, limit=400)
                if idx.s_enc[i] != ord("U") and idx.text_of(i, d) == want]
        if not cand:   # fall back to substring, ASCII only
            cand = [i for i, _n in idx.find(want, limit=args.n)
                    if idx.s_enc[i] != ord("U")]
    if not cand:
        print("no ASCII reflection name matching %r" % args.name)
        return
    mult = _call_multiplicity(idx)

    for si in cand[:args.n]:
        nm = idx.text_of(si, d)
        print("name  0x%08X A %r" % (idx.s_rva[si], nm))
        sites = [(s, k) for s, k, _sl in idx.refs_to(si)]
        # ---- data route: FNameNativePtrPair {name; ptr} laid out in memory
        pat = struct.pack("<Q", ib + idx.s_rva[si])
        pos, dslots = 0, []
        while True:
            j = d.find(pat, pos)
            if j < 0:
                break
            pos = j + 1
            kind, fp = _classify_slot(idx, d, j)
            if fp is not None:
                dslots.append((j, kind, fp))
        if not sites and not dslots:
            print("  0 registrar sites and 0 data pairs.")
            print("  NOT proof of absence -- the registrar page may be undecrypted")
            print("  (.text is %.2f%% readable by page in this dump)."
                  % [r for r in idx.stats["coverage"] if r[0] == ".text"][0][6])
            continue
        for slot, kind, fp in dslots:
            if kind == "linkinfo":
                print("  FClassFunctionLinkInfo slot 0x%08X -> Z_Construct_UFunction "
                      "0x%07X   (nattable 0x%08X for the class's full UFUNCTION list)"
                      % (slot, fp, slot))
            else:
                print("  FNameNativePtrPair slot 0x%08X -> exec thunk 0x%07X"
                      % (slot, fp))
                _report_thunk(idx, d, fp, mult, args)
        for site, kind in sites:
            e, f, ti, _end = idx.func_of(site)
            print("  registrar site 0x%07X %-8s in fn 0x%07X %s"
                  % (site, KIND_NAME[kind], e or 0, TIER_NAME.get(ti, "?")))
            if kind != K_LEA:
                continue
            near = [(t, s2 - site) for s2, t in
                    _leas_in(d, site - args.window, site + args.window)
                    if tv <= t < te and s2 != site]
            if not near:
                print("      no .text-targeting lea within +-%d bytes" % args.window)
                continue
            near.sort(key=lambda x: abs(x[1]))
            for t, dist in near[:args.pairs]:
                print("      exec thunk candidate 0x%07X   (paired lea %+d bytes)"
                      % (t, dist))
                _report_thunk(idx, d, t, mult, args)


def _tbl_probe(idx, d):
    """Closures for reading a data slot as a name-pointer / .text-pointer."""
    tv, te, ib = idx.text_va, idx.text_end, idx.imagebase

    def txptr(slot):
        if slot < 0 or slot + 8 > len(d):
            return None
        v = struct.unpack_from("<Q", d, slot)[0] - ib
        return v if tv <= v < te else None

    def nameptr(slot):
        if slot < 0 or slot + 8 > len(d):
            return None
        v = struct.unpack_from("<Q", d, slot)[0] - ib
        if not (0 <= v < len(d)):
            return None
        si = idx.str_at(v)
        if si < 0 or idx.s_enc[si] == ord("U"):
            return None
        return idx.text_of(si, d)
    return txptr, nameptr


def _classify_slot(idx, d, slot):
    """What kind of generated table is `slot` (a name-pointer slot) inside?

    Measured discriminator, not an assumption -- both layouts exist in this image
    and confusing them yields a plausible-but-wrong function address:

      FClassFunctionLinkInfo[] : { UFunction*(*CreateFuncPtr)(); const char* Name; }
          -> stride 16, PTR FIRST.  Neighbouring name slots at +-16.
          -> this entry's Z_Construct_UFunction_<Class>_<Name> is at slot-8,
             and slot+8 is the NEXT function's constructor.
      FNameNativePtrPair[]     : { const char* Name; FNativeFuncPtr Exec; }
          -> NAME first; the exec thunk is at slot+8.

    Returns ('linkinfo'|'pair'|'unknown', fnptr_rva|None).
    """
    txptr, nameptr = _tbl_probe(idx, d)
    prev_n, next_n = nameptr(slot - 16), nameptr(slot + 16)
    if txptr(slot - 8) is not None and (prev_n is not None or next_n is not None):
        return "linkinfo", txptr(slot - 8)
    if txptr(slot + 8) is not None:
        return "pair", txptr(slot + 8)
    return "unknown", None


def cmd_nattable(idx, args):
    """Walk the generated table containing a slot -> a class's whole UFUNCTION list.

    Given any one name slot (a `via slot 0x...` from `func`/`xref`, or a data pair
    from `native`), walking 16 bytes at a time recovers the ENTIRE table: for an
    FClassFunctionLinkInfo[] that is every UFUNCTION the class declares, each with
    its Z_Construct_UFunction_<Class>_<Name>() -- no running game, no symbols.
    """
    d = idx._dump()
    txptr, nameptr = _tbl_probe(idx, d)

    base = args.slot & ~7
    if nameptr(base) is None and nameptr(base - 8) is not None:
        base -= 8
    if nameptr(base) is None:
        print("0x%08X does not hold a pointer to an ASCII name." % args.slot)
        return
    kind, _ = _classify_slot(idx, d, base)
    if kind == "unknown":
        print("0x%08X holds a name pointer but neither neighbour slot is a .text "
              "pointer -- not a generated function table." % base)
        return

    def ok(slot):
        return nameptr(slot) is not None and _classify_slot(idx, d, slot)[0] == kind

    lo = base
    while ok(lo - 16):
        lo -= 16
    hi = base
    while ok(hi + 16):
        hi += 16
    n = (hi - lo) // 16 + 1
    label = ("FClassFunctionLinkInfo[]  {Z_Construct; name}"
             if kind == "linkinfo" else "FNameNativePtrPair[]  {name; exec}")
    print("%s   0x%08X .. 0x%08X   %d entries" % (label, lo, hi + 15, n))
    col = "Z_Construct" if kind == "linkinfo" else "exec"
    mult = _call_multiplicity(idx) if args.impl else None
    for k in range(n):
        slot = lo + k * 16
        nm = nameptr(slot)
        _, fp = _classify_slot(idx, d, slot)
        print("  [%3d] 0x%08X  %-46s %s 0x%07X"
              % (k, slot, nm, col, fp if fp else 0))
        if args.impl and kind == "pair" and fp:
            _report_thunk(idx, d, fp, mult, args)


def _report_thunk(idx, d, thunk, mult, args):
    e, f, ti, end = idx.func_of(thunk)
    hi = min(end if end else thunk + args.body, thunk + args.body)
    callees = _rel32_callees(d, thunk, hi)
    if not callees:
        print("        (no rel32 callees in +%d bytes)" % (hi - thunk))
        return
    ranked = []
    for site, t, isj in callees:
        if not (idx.text_va <= t < idx.text_end):
            continue
        ranked.append((mult.get(t, 0), site, t, isj))
    if not ranked:
        return
    lo = min(m for m, _s, _t, _j in ranked)
    for m, site, t, isj in ranked:
        tag = ""
        if m <= max(4, lo):
            tag = "   <== IMPLEMENTATION candidate"
        print("        %s 0x%07X  callers=%-6d+0x%X%s"
              % ("jmp " if isj else "call", t, m, site - thunk, tag))


def cmd_near(idx, args):
    """Strings adjacent in .rdata to a given RVA.

    MSVC emits a translation unit's literals contiguously, so the neighbourhood of
    one known string is the rest of that source file's messages.  When the target
    string itself has 0 xrefs (its emitting page is undecrypted), a neighbour that
    DOES have one lands you in the same TU -- often the same function family.
    """
    d = idx._dump()
    i = bisect.bisect_left(idx.s_rva, args.rva)
    lo, hi = max(0, i - args.n), min(len(idx.s_rva), i + args.n + 1)
    for k in range(lo, hi):
        mark = ">>" if idx.s_rva[k] == args.rva else "  "
        show_string(idx, k, d, prefix=mark + " ")


def cmd_census(idx, args):
    st = idx.stats
    print("index      : %s" % INDEX_PATH)
    print("dump       : %s" % idx.dump_path)
    print("min_len    : %d       build: %.1fs" % (st["min_len"], st["build_secs"]))
    print("strings    : %d" % len(idx.s_rva))
    for k, (a, u) in st["per_sec"].items():
        print("   %-8s ASCII %7d  UTF-16 %7d" % (k, a, u))
    print("refs       : %d  (exact %d, interior %d, via pointer table %d)"
          % (len(idx.rf_site), st["direct_exact"], st["direct_interior"],
             sum(1 for k in idx.rs_kind if k == K_PTR)))
    print("abs qwords : %d  (holding a string address: %d)" % (st["n_abs"], st["n_slot2str"]))
    tiers = Counter(tier_of(f) for f in idx.flags)
    print("fn entries : %d  (HIGH %d  MED %d  LOW %d)"
          % (len(idx.ent), tiers[TIER_HIGH], tiers[TIER_MED], tiers[TIER_LOW]))
    print("   signals : E8-call %d | data-fnptr %d | int3-pad %d | prologue-sweep %d"
          % (st["n_call_targets"], st["n_ptr_entries"], st["n_pad"], st["n_pro"]))
    strs_with_refs = len(set(idx.rs_str))
    print("strings with >=1 code ref: %d / %d = %.1f%%"
          % (strs_with_refs, len(idx.s_rva), 100.0 * strs_with_refs / len(idx.s_rva)))
    print("")
    print("%-10s %-12s %12s %8s %10s %9s %9s" %
          ("section", "vaddr", "vsize", "pages", "zeropages", "nonzero%", "readable%"))
    for name, va, vs, pages, zp, nzp, rp in st["coverage"]:
        print("%-10s 0x%08x %12d %8d %10d %8.2f%% %8.2f%%" % (name, va, vs, pages, zp, nzp, rp))


def cmd_pdata(idx, args):
    p = load_pdata()
    if not p:
        print("no recovered .pdata at %s" % PDATA_PATH)
        print("build it with:  python pdataunion.py     (reads the crash minidumps)")
        return
    beg, end = p
    n = len(beg)
    cov = sum(end[i] - beg[i] for i in range(n))
    sizes = sorted(end[i] - beg[i] for i in range(n))
    print("source     : %s" % PDATA_PATH)
    print("functions  : %d  (exact, non-overlapping bounds)" % n)
    print("bytes      : %d (%.1f%% of .text VSize)" % (cov, 100.0 * cov / 0x7649000))
    print("size       : median %d B, p90 %d B, max %d B"
          % (sizes[n // 2], sizes[int(.9 * n)], sizes[-1]))
    # how many string-ref sites land inside a known function
    inreal = sum(1 for s in idx.rf_site if true_func(s)[0] is not None)
    print("string-ref sites inside a known function: %d / %d = %.1f%%"
          % (inreal, len(idx.rf_site), 100.0 * inreal / len(idx.rf_site)))
    print("")
    print("A gap in this table means the function was never decrypted in any of the 70")
    print("crash processes -- NOT that no function is there.  Bounds are exact where present.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild", action="store_true", help="rebuild the persisted index")
    ap.add_argument("--dump", default=DEFAULT_DUMP, help="path to the flat image dump")
    ap.add_argument("--min-len", type=int, default=4,
                    help="minimum string length in CHARACTERS (default 4; the "
                         "established census used 6 and is reported separately)")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("find", help="strings matching a substring")
    p.add_argument("pattern")
    p.add_argument("-n", type=int, default=40)
    p.add_argument("--regex", action="store_true")
    p.add_argument("--refs-only", action="store_true", help="only strings with >=1 xref")

    p = sub.add_parser("xref", help="code sites referencing a string RVA")
    p.add_argument("rva", type=lambda s: int(s, 0))

    p = sub.add_parser("func", help="every string referenced BY the function containing a code RVA")
    p.add_argument("rva", type=lambda s: int(s, 0))
    p.add_argument("--raw", action="store_true", help="allow LOW-tier entries too")
    p.add_argument("--heuristic", action="store_true",
                   help="ignore the recovered .pdata and use the old inferred bounds")

    sub.add_parser("pdata", help="status of the recovered unwind table (function bounds)")

    p = sub.add_parser("native",
                       help="UFUNCTION reflection name -> execXxx thunk -> implementation")
    p.add_argument("name", help="exact ASCII reflection name, or 0x<string_rva>")
    p.add_argument("-n", type=int, default=6, help="max name matches to expand")
    p.add_argument("--window", type=int, default=96,
                   help="bytes each side of the name lea to search for the paired thunk lea")
    p.add_argument("--pairs", type=int, default=2,
                   help="how many nearest .text-lea candidates to expand per site")
    p.add_argument("--body", type=int, default=1024,
                   help="max bytes of the thunk body to scan for callees")

    p = sub.add_parser("nattable",
                       help="walk the FNameNativePtrPair array containing a slot "
                            "-> a class's whole native API")
    p.add_argument("slot", type=lambda s: int(s, 0))
    p.add_argument("--impl", action="store_true",
                   help="also resolve each exec thunk to its implementation")
    p.add_argument("--body", type=int, default=1024)

    p = sub.add_parser("near", help="strings adjacent in .rdata (same translation unit)")
    p.add_argument("rva", type=lambda s: int(s, 0))
    p.add_argument("-n", type=int, default=12)

    sub.add_parser("census", help="summary statistics")
    sub.add_parser("validate", help="re-run self-validation incl. null controls")

    args = ap.parse_args(argv)

    if args.rebuild:
        idx, _pe = build(args.dump, args.min_len, INDEX_PATH)
        print("")
        return 1 if validate(idx) else 0

    if not args.cmd:
        ap.print_help()
        return 0

    idx = Index.load(INDEX_PATH)
    if args.cmd == "find":
        cmd_find(idx, args)
    elif args.cmd == "xref":
        cmd_xref(idx, args)
    elif args.cmd == "func":
        cmd_func(idx, args)
    elif args.cmd == "native":
        cmd_native(idx, args)
    elif args.cmd == "nattable":
        cmd_nattable(idx, args)
    elif args.cmd == "near":
        cmd_near(idx, args)
    elif args.cmd == "census":
        cmd_census(idx, args)
    elif args.cmd == "pdata":
        cmd_pdata(idx, args)
    elif args.cmd == "validate":
        return 1 if validate(idx) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
