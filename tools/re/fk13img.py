#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk13img.py -- shared OFFLINE image layer for the FK-13 / Route B verification work.

Everything here is read-only static analysis over `usmapdump dumpimage` snapshots.
No game launch, no injection, no RPM.

DESIGN NOTES (audit trail -- read before trusting any number this produces)

* PRIMARY IMAGE = dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe
  ImageBase 0x7FF6505C0000, file-offset == RVA, `.rdata`/`.data`/`.pdata` 100.0%
  readable per its own manifest.  Every `.rdata`/`.data` claim (UHT param structs,
  vtables, class-registration records) is therefore NOT coverage-limited.

* `.text` DEMAND-DECRYPTS.  A 4 KiB page that reads as all-zero was never executed
  by the process that was dumped -- that is COVERAGE-BLOCKED, which is a third
  verdict distinct from "real body" and "folded stub".  Never silently grade a
  zero page.

* `.text` UNION.  .text pages are byte-identical across dumps taken at different
  ASLR bases (measured by tools/re/cheat_impl_census.py: 0 conflicts over every
  page present in >=2 of 10 dumps; x64 code here is 100% RIP-relative so nothing
  in .text is relocated).  We union all 10 dumps' .text to maximise coverage and
  REPORT, per address, whether the answer needed the union.  Conflicts are counted
  and printed -- a non-zero conflict count invalidates the union.

* ⚠ INSTRUMENT NOTE -- the `.pdata` SECTION IS ALL ZERO in every dumpimage snapshot.
  The manifest line `.pdata ... 6283264 (100.0%)` means "100% of those pages were
  READABLE", not "populated": measured here, 523,605 / 523,605 12-byte slots are
  {0,0,0} and the first 64 KiB has exactly ONE distinct byte value.  Positive
  control that this is not an image-wide read failure: in the same file `.rdata`
  is 99.6% non-zero pages and `.reloc` is 100.0%.  So DO NOT parse function bounds
  out of the section.  Exact bounds come instead from
  `tools/strxref/index/pdata_union.csv` -- 382,282 non-overlapping RUNTIME_FUNCTION
  ranges unioned out of the *lazily materialised* tables inside 68 crash minidumps
  (tools/strxref/pdataunion.py).  A missing range there means "no crashed process
  ever materialised this entry", which is a coverage statement, not "no function".

* UNIVERSAL /OPT:ICF FOLDS in this image (established S114 lane 1 / FK-13):
      0x00F7EC20  c2 00 00        ret 0            <- empty `void` body
      0x00F7EB60  32 c0 c3        xor al,al; ret   <- empty `bool` body (false)
  MSVC folds every byte-identical function to one address, so a stub has thousands
  of callers and a real body has one; ranking by call multiplicity INVERTS the
  answer and must not be used.
"""
import bisect
import os
import struct
import sys

ROOT = r"G:\git\Supervive Revival Project"
PRIMARY = os.path.join(ROOT, "dumps", "tutorial-hero",
                       "SUPERVIVE-Win64-Shipping.dump.exe")
PRIMARY_BASE = 0x7FF6505C0000
MERGED = os.path.join(ROOT, "dumps", "merged.dump.exe")
MERGED_BASE = 0x7FF6AF000000

EXTRA_DUMP_DIRS = ("menu", "store", "roster", "missions", "loadout",
                   "accountpass", "vmbuild", "toggles", "rcb")

PAGE = 0x1000
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000
TEXT_END = TEXT_RVA + TEXT_SIZE

# ---- the two universal folded-empty-body addresses (RVAs) ------------------
FOLD_RET0 = 0x00F7EC20      # c2 00 00        -> `ret 0`      (void)
FOLD_FALSE = 0x00F7EB60     # 32 c0 c3        -> xor al,al;ret (bool false)

# ---- FFrame parameter-step / teardown helpers ------------------------------
# Landing on one of these while resolving thunk->impl means the resolution FAILED
# (the real dispatch was indirect), NOT that the impl is this helper.
FRAME_HELPERS = {
    0x012F3FC0, 0x0133EB30, 0x0135F5E0,   # named in the lane-3 brief
    0x01345FB0, 0x01345FE0, 0x0133F840, 0x0133EEA0, 0x0133EBE0,
    0x013759A0, 0x00FF9310,
}

UNION_CACHE = os.path.join(os.environ.get("TEMP", "."),
                           "supervive_fk13_union_text.bin")


# ---------------------------------------------------------------- image ----
class Img:
    """A flat dumpimage snapshot: file offset == RVA."""

    def __init__(self, path, base):
        with open(path, "rb") as f:
            self.d = bytearray(f.read())
        self.base = base
        self.path = path
        pe = struct.unpack_from("<I", self.d, 0x3C)[0]
        nsec = struct.unpack_from("<H", self.d, pe + 6)[0]
        optsz = struct.unpack_from("<H", self.d, pe + 20)[0]
        sh = pe + 24 + optsz
        self.sec = {}
        for i in range(nsec):
            o = sh + i * 40
            nm = self.d[o:o + 8].rstrip(b"\0").decode("latin1")
            va = struct.unpack_from("<I", self.d, o + 12)[0]
            vs = struct.unpack_from("<I", self.d, o + 8)[0]
            self.sec[nm] = (va, vs)
        self.union_stats = {}

    # --- raw access ---------------------------------------------------------
    def rd(self, rva, n):
        if rva < 0 or rva + n > len(self.d):
            return b""
        return bytes(self.d[rva:rva + n])

    def u8(self, rva):
        b = self.rd(rva, 1)
        return b[0] if b else None

    def u16(self, rva):
        b = self.rd(rva, 2)
        return struct.unpack("<H", b)[0] if len(b) == 2 else None

    def u32(self, rva):
        b = self.rd(rva, 4)
        return struct.unpack("<I", b)[0] if len(b) == 4 else None

    def u64(self, rva):
        b = self.rd(rva, 8)
        return struct.unpack("<Q", b)[0] if len(b) == 8 else None

    def ptr(self, rva):
        """Read a pointer field and return it as an RVA, or None if not in-image."""
        v = self.u64(rva)
        if v is None or v == 0:
            return None
        r = v - self.base
        return r if 0 <= r < len(self.d) else None

    def section_of(self, rva):
        for nm, (va, vs) in self.sec.items():
            if va <= rva < va + vs:
                return nm
        return None

    def cstr(self, rva, cap=256):
        o = rva
        if o is None or o < 0 or o >= len(self.d):
            return None
        e = self.d.find(b"\0", o, o + cap)
        if e <= o:
            return None
        s = bytes(self.d[o:e])
        if any(c < 0x20 or c > 0x7E for c in s):
            return None
        return s.decode("ascii")

    def wstr(self, rva, cap=256):
        if rva is None or rva < 0:
            return None
        out = []
        o = rva
        while len(out) < cap and o + 1 < len(self.d):
            c = struct.unpack_from("<H", self.d, o)[0]
            if c == 0:
                break
            if c < 0x20 or c > 0x7E:
                return None
            out.append(chr(c))
            o += 2
        return "".join(out) if out else None

    # --- coverage -----------------------------------------------------------
    def page_decrypted(self, rva):
        p = rva & ~(PAGE - 1)
        return bytes(self.d[p:p + PAGE]).strip(b"\0") != b""

    def range_decrypted(self, lo, hi):
        for p in range(lo & ~(PAGE - 1), hi, PAGE):
            if not self.page_decrypted(p):
                return False
        return True

    # --- .text union --------------------------------------------------------
    def apply_text_union(self, verbose=False):
        """Fill zero .text pages from every other dump.  Returns stats dict."""
        if os.path.exists(UNION_CACHE) and os.path.getsize(UNION_CACHE) == TEXT_SIZE:
            with open(UNION_CACHE, "rb") as f:
                union = bytearray(f.read())
            src = "cache"
            conflicts = -1
        else:
            union = bytearray(self.d[TEXT_RVA:TEXT_END])
            conflicts = 0
            paths = [MERGED] + [
                os.path.join(ROOT, "dumps", d, "SUPERVIVE-Win64-Shipping.dump.exe")
                for d in EXTRA_DUMP_DIRS]
            for p in paths:
                if not os.path.exists(p):
                    continue
                with open(p, "rb") as f:
                    other = f.read()
                for r in range(0, TEXT_SIZE, PAGE):
                    pg = other[TEXT_RVA + r:TEXT_RVA + r + PAGE]
                    if not pg.strip(b"\0"):
                        continue
                    cur = bytes(union[r:r + PAGE])
                    if not cur.strip(b"\0"):
                        union[r:r + PAGE] = pg
                    elif cur != pg:
                        conflicts += 1
                if verbose:
                    print("  unioned %s" % os.path.basename(os.path.dirname(p)))
            with open(UNION_CACHE, "wb") as f:
                f.write(bytes(union))
            src = "built"
        before = sum(1 for r in range(0, TEXT_SIZE, PAGE)
                     if bytes(self.d[TEXT_RVA + r:TEXT_RVA + r + PAGE]).strip(b"\0"))
        self.d[TEXT_RVA:TEXT_END] = union
        after = sum(1 for r in range(0, TEXT_SIZE, PAGE)
                    if bytes(union[r:r + PAGE]).strip(b"\0"))
        total = TEXT_SIZE // PAGE
        self.union_stats = dict(src=src, conflicts=conflicts, pages_before=before,
                                pages_after=after, pages_total=total)
        return self.union_stats


# ---------------------------------------------------------------- pdata ----
PDATA_CSV = os.path.join(ROOT, "tools", "strxref", "index", "pdata_union.csv")


class PData:
    """Exact function bounds from the recovered (minidump-unioned) unwind table.

    See the INSTRUMENT NOTE at the top of this file: the `.pdata` section in the
    dumpimage snapshots is all zero, so the table has to come from elsewhere.
    """

    def __init__(self, path=PDATA_CSV):
        beg, end, seen = [], [], []
        with open(path) as f:
            next(f)
            for line in f:
                p = line.split(",")
                beg.append(int(p[0], 16))
                end.append(int(p[1], 16))
                seen.append(int(p[4]))
        self.beg, self.end, self.seen = beg, end, seen
        self.n = len(beg)
        self.starts = set(beg)

    def raw_entry(self, rva):
        i = bisect.bisect_right(self.beg, rva) - 1
        if i < 0 or rva >= self.end[i]:
            return None
        return i

    def bounds(self, rva):
        """(begin, end) of the function containing rva, merging adjacent fragments.

        pdataunion.py already emits non-overlapping ranges; MSVC emits a separate
        RUNTIME_FUNCTION per code fragment, and a fragment start that is not
        16-byte aligned and abuts its predecessor is a continuation, not a new
        function (the same rule cheat_impl_census.py uses).
        """
        i = self.raw_entry(rva)
        if i is None:
            return None, None
        while i > 0 and self.beg[i] == self.end[i - 1] and self.beg[i] % 16:
            i -= 1
        lo, hi = self.beg[i], self.end[i]
        j = i + 1
        while j < self.n and self.beg[j] == hi and self.beg[j] % 16:
            hi = self.end[j]
            j += 1
        return lo, hi

    def exact_start(self, rva):
        return rva in self.starts

    def seen_in(self, rva):
        i = self.raw_entry(rva)
        return self.seen[i] if i is not None else 0


# ------------------------------------------------------------- singletons ---
_IMG = None
_PD = None


def img(union=True, verbose=False):
    global _IMG
    if _IMG is None:
        _IMG = Img(PRIMARY, PRIMARY_BASE)
        if union:
            _IMG.apply_text_union(verbose=verbose)
    return _IMG


def pdata():
    global _PD
    if _PD is None:
        _PD = PData()
    return _PD


if __name__ == "__main__":
    im = img(verbose=True)
    print("primary : %s" % im.path)
    print("base    : %#x" % im.base)
    for nm, (va, vs) in im.sec.items():
        print("  %-10s rva %#010x size %#x" % (nm, va, vs))
    print("union   : %s" % im.union_stats)
    pd = pdata()
    print("pdata   : %d RUNTIME_FUNCTION entries in .text range" % pd.n)
    for probe in (0x035B7430, 0x0395D790, 0x00F7EC20, 0x00F7EB60):
        lo, hi = pd.bounds(probe)
        print("  %#010x -> bounds %s..%s  (%s B)  bytes=%s" %
              (probe, "%#x" % lo if lo else None, "%#x" % hi if hi else None,
               (hi - lo) if lo else "-", im.rd(probe, 8).hex()))
