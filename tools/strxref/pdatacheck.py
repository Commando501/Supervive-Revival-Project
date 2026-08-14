#!/usr/bin/env python3
"""
pdatacheck.py -- validate the minidump-recovered RUNTIME_FUNCTION table and score
strxref.py's heuristic function attribution against it (external ground truth,
524,439 entries instead of 42).
"""
import os
import sys
import glob
import struct
import bisect
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strxref as SX
import mdpdata as MD
from dumpcov import PAGE

  # 2026-08-14 (S121, FK-18/FK-19): merged2 is the canonical cold image -- same ImageBase
  # 0x7FF6AF000000, byte-identical .rdata/.data, and a STRICT .text superset (16,625 vs
  # 15,833 decrypted pages). docs/fk18-fk19-multistate-merge-settled.md
MERGED = r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe"
CRASH = r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes"
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000


def table(dmp):
    d = MD.sane(MD.parse_ft(dmp, quiet=True))
    e = d["entries"]
    n = d["count"]
    beg = [0] * n
    end = [0] * n
    unw = [0] * n
    for i in range(n):
        beg[i], end[i], unw[i] = struct.unpack_from("<III", e, i * 12)
    return beg, end, unw, d["base"]


def main():
    dumps = sorted(glob.glob(os.path.join(CRASH, "UECC-*", "UEMinidump.dmp")))
    ok = []
    for p in dumps:
        try:
            if MD.sane(MD.parse_ft(p, quiet=True)):
                ok.append(p)
        except Exception:
            pass
    print(f"usable minidumps: {len(ok)}")

    print("\n" + "=" * 88)
    print("1. CROSS-DUMP IDENTITY -- do independent crashes agree byte-for-byte on RVAs?")
    print("=" * 88)
    ref = None
    checked = 0
    for p in ok[:8]:
        beg, end, unw, base = table(p)
        sig = (len(beg), beg[0], end[-1], sum(beg) & 0xFFFFFFFFFFFF, sum(end) & 0xFFFFFFFFFFFF)
        tag = os.path.basename(os.path.dirname(p))[13:29]
        if ref is None:
            ref = sig
            print(f"  {tag}  base 0x{base:012X}  n={sig[0]:,}  (reference)")
        else:
            print(f"  {tag}  base 0x{base:012X}  n={sig[0]:,}  "
                  f"{'IDENTICAL' if sig == ref else '*** DIFFERS ***'}")
        checked += 1
    beg, end, unw, base = table(ok[0])
    n = len(beg)

    print("\n" + "=" * 88)
    print("2. GAP ANALYSIS -- the table covers 52.5% of .text bytes; where is the rest?")
    print("=" * 88)
    with open(MERGED, "rb") as f:
        img = f.read()

    def dec(rva):
        p = rva & ~(PAGE - 1)
        return img[p:p + PAGE].strip(b"\0") != b""

    gaps = []
    for i in range(n - 1):
        g = beg[i + 1] - end[i]
        if g > 0:
            gaps.append((g, end[i]))
    gaps.sort(reverse=True)
    tot_gap = sum(g for g, _ in gaps)
    print(f"  inter-function gaps: {len(gaps):,}  total {tot_gap:,} bytes "
          f"({100.0*tot_gap/TEXT_SIZE:.1f}% of .text)")
    hist = collections.Counter()
    for g, _ in gaps:
        b = 0 if g <= 4 else 1 if g <= 16 else 2 if g <= 64 else 3 if g <= 4096 else 4
        hist[b] += g
    lbl = ["<=4 B (alignment)", "5-16 B", "17-64 B", "65-4096 B", ">4 KB"]
    for b in range(5):
        print(f"    {lbl[b]:<20} {hist[b]:>14,} bytes ({100.0*hist[b]/tot_gap:5.1f}% of gap)")
    print("\n  10 largest gaps (and whether that region is decrypted in merged.dump.exe):")
    for g, at in gaps[:10]:
        print(f"    0x{at:08X} .. 0x{at+g:08X}  {g:>10,} B   "
              f"first page {'DECRYPTED' if dec(at) else 'dark'}, "
              f"mid page {'DECRYPTED' if dec(at+g//2) else 'dark'}")

    print("\n" + "=" * 88)
    print("3. FUNCTION SIZE DISTRIBUTION")
    print("=" * 88)
    sizes = sorted(end[i] - beg[i] for i in range(n))
    for q in (0, 5, 25, 50, 75, 90, 95, 99, 100):
        print(f"    p{q:<3} {sizes[min(len(sizes)-1, q*len(sizes)//100)]:>9,} B")
    tiny = sum(1 for s in sizes if s <= 16)
    print(f"    entries <=16 B: {tiny:,} ({100.0*tiny/n:.1f}%)  <- thunks / jump stubs")

    print("\n" + "=" * 88)
    print("4. SCORING strxref.py's HEURISTIC ATTRIBUTION AGAINST THE REAL TABLE")
    print("=" * 88)
    idx = SX.Index.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "index", "strxref.idx"))
    ent = idx.ent
    flags = idx.flags
    truth = set(beg)
    # restrict to functions whose entry page is decrypted -- a heuristic scanner
    # cannot see a zeroed page, so scoring it there measures coverage, not algorithm
    vis = [b for b in beg if dec(b)]
    visset = set(vis)
    print(f"  real functions total           : {n:,}")
    print(f"  ... with a DECRYPTED entry page: {len(vis):,} ({100.0*len(vis)/n:.1f}%)")

    cand_all = set(ent)
    cand_med = set(ent[i] for i in range(len(ent)) if SX.tier_of(flags[i]) >= SX.TIER_MED)
    cand_high = set(ent[i] for i in range(len(ent)) if SX.tier_of(flags[i]) >= SX.TIER_HIGH)
    for label, cand in (("all tiers", cand_all), ("MED+", cand_med), ("HIGH", cand_high)):
        tp = len(cand & visset)
        fp = len(cand - truth)
        print(f"\n  strxref candidates [{label}]: {len(cand):,}")
        print(f"    recall on visible functions : {tp:,}/{len(vis):,} = {100.0*tp/len(vis):.1f}%")
        print(f"    candidates that are NOT real function entries: {fp:,} "
              f"({100.0*fp/len(cand):.1f}%)")

    # func_of correctness: for each visible real function, does func_of(entry+8)
    # return the right entry?
    import random
    rng = random.Random(7)
    sample = rng.sample(vis, 4000)
    beg_sorted = beg  # already ascending
    good = bad = nomap = 0
    for b in sample:
        i = bisect.bisect_right(beg_sorted, b) - 1
        e_ = end[i]
        probe = b + 8 if b + 8 < e_ else b
        f, fl, t, nx = idx.func_of(probe)
        if f is None:
            nomap += 1
        elif f == b:
            good += 1
        else:
            bad += 1
    print(f"\n  func_of(entry+8) on 4,000 random VISIBLE real functions:")
    print(f"    correct {good:,} ({100.0*good/len(sample):.1f}%)   wrong {bad:,}   none {nomap:,}")

    # extent accuracy: strxref reports next-entry as an upper bound
    over = []
    for b in sample:
        i = bisect.bisect_right(beg_sorted, b) - 1
        real = end[i] - beg[i]
        f, fl, t, nx = idx.func_of(b)
        if f == b and nx:
            over.append((nx - f) / max(1, real))
    over.sort()
    if over:
        print(f"\n  strxref extent / real size ratio: median {over[len(over)//2]:.2f}x, "
              f"p90 {over[int(0.9*len(over))]:.2f}x, max {over[-1]:.1f}x")


if __name__ == "__main__":
    main()
