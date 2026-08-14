#!/usr/bin/env python3
"""
pdatascore.py -- (a) do PLACEHOLDER slots also mark real function starts?
                 (b) score strxref.py's heuristic attribution against the clean union.
"""
import os
import sys
import glob
import struct
import bisect
import random
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
IDXP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "strxref.idx")
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000


def load_union():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "pdata_union.csv")
    beg, end = [], []
    with open(p) as f:
        next(f)
        for line in f:
            a, b, s, u, k = line.split(",")
            beg.append(int(a, 16))
            end.append(int(b, 16))
    return beg, end


def main():
    beg, end = load_union()
    realset = set(beg)
    print(f"union real functions: {len(beg):,}")

    # ---- (a) placeholder begins ----
    dumps = sorted(glob.glob(os.path.join(CRASH, "UECC-*", "UEMinidump.dmp")))
    ph = set()
    allbeg = set()
    nt = 0
    for p in dumps:
        try:
            d = MD.sane(MD.parse_ft(p, quiet=True))
        except Exception:
            continue
        if not d:
            continue
        nt += 1
        e = d["entries"]
        for i in range(d["count"]):
            b, en, u = struct.unpack_from("<III", e, i * 12)
            allbeg.add(b)
            if en - b == 1:
                ph.add(b)
    print(f"\n== (a) PLACEHOLDER SLOTS ==   ({nt} tables)")
    print(f"  distinct BeginAddress values overall      : {len(allbeg):,}")
    print(f"  ... that are a REAL entry in some dump    : {len(allbeg & realset):,}")
    only_ph = allbeg - realset
    print(f"  ... only ever seen as a placeholder       : {len(only_ph):,}")
    print(f"  distinct placeholder begins               : {len(ph):,}")
    print(f"  placeholder begins later proven real      : {len(ph & realset):,} "
          f"({100.0*len(ph & realset)/len(ph):.1f}%)")
    print("  => a placeholder Begin IS a real function start; only its End is withheld.")
    print(f"\n  TOTAL FUNCTION STARTS KNOWN (real + placeholder): {len(allbeg):,}")
    print(f"  table slots per dump                            : 524,439")

    # ---- (b) score strxref ----
    with open(MERGED, "rb") as f:
        img = f.read()

    def dec(rva):
        p = rva & ~(PAGE - 1)
        return img[p:p + PAGE].strip(b"\0") != b""

    print("\n== (b) strxref.py HEURISTIC ATTRIBUTION vs the recovered table ==")
    idx = SX.Index.load(IDXP)
    ent, flags = idx.ent, idx.flags
    vis = [b for b in beg if dec(b)]
    visset = set(vis)
    print(f"  real functions with a DECRYPTED entry page in merged: {len(vis):,}")
    for label, minsz in (("all real", 0), ("size >= 16 B", 16), ("size >= 64 B", 64)):
        sub = set(b for b, e in zip(beg, end) if e - b >= minsz and dec(b))
        cand = set(ent[i] for i in range(len(ent)) if SX.tier_of(flags[i]) >= SX.TIER_MED)
        tp = len(cand & sub)
        print(f"    recall [{label:<12}] {tp:>7,}/{len(sub):>7,} = {100.0*tp/len(sub):5.1f}%")
    cand = set(ent[i] for i in range(len(ent)) if SX.tier_of(flags[i]) >= SX.TIER_MED)
    fp = cand - allbeg
    print(f"    MED+ candidates: {len(cand):,};  not any known function start: {len(fp):,} "
          f"({100.0*len(fp)/len(cand):.1f}%)")

    # extent error, scored ONLY on functions strxref actually finds
    rng = random.Random(11)
    sample = rng.sample(vis, 6000)
    bs = beg
    ratios = []
    exact = 0
    for b in sample:
        i = bisect.bisect_left(bs, b)
        real = end[i] - beg[i]
        f, fl, t, nx = idx.func_of(b + max(0, min(8, real - 1)))
        if f == b:
            exact += 1
            if nx:
                ratios.append((nx - f) / max(1, real))
    ratios.sort()
    print(f"\n  on 6,000 random visible functions: func_of resolves to the true entry "
          f"{exact:,} times ({100.0*exact/len(sample):.1f}%)")
    if ratios:
        print(f"  reported extent / true size: median {ratios[len(ratios)//2]:.2f}x  "
              f"p75 {ratios[int(.75*len(ratios))]:.2f}x  p90 {ratios[int(.9*len(ratios))]:.2f}x  "
              f"p99 {ratios[int(.99*len(ratios))]:.1f}x")
        bad = sum(1 for r in ratios if r > 2)
        print(f"  extents overstated by >2x: {bad:,}/{len(ratios):,} ({100.0*bad/len(ratios):.1f}%)")

    # ---- (c) what the table buys the string-xref tool ----
    print("\n== (c) EFFECT ON STRING->FUNCTION ATTRIBUTION ==")
    refsite = idx.rf_site
    inreal = 0
    ingap = 0
    per_fn = collections.Counter()
    for s in refsite:
        i = bisect.bisect_right(bs, s) - 1
        if i >= 0 and s < end[i]:
            inreal += 1
            per_fn[beg[i]] += 1
        else:
            ingap += 1
    print(f"  string-reference sites total          : {len(refsite):,}")
    print(f"  inside a KNOWN function's true bounds : {inreal:,} ({100.0*inreal/len(refsite):.1f}%)")
    print(f"  in a gap (function not in the table)  : {ingap:,}")
    print(f"  distinct functions carrying >=1 string: {len(per_fn):,}")
    print(f"  top string-carrying functions:")
    for k, v in per_fn.most_common(8):
        print(f"    0x{k:07X}  {v:5d} refs  size {end[bisect.bisect_left(bs,k)]-k:,} B")


if __name__ == "__main__":
    main()
