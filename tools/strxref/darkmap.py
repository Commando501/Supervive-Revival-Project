#!/usr/bin/env python3
"""
darkmap.py -- characterize the UNREFERENCED ("dark") strings in the strxref index
and map them onto .text demand-decrypt coverage.

Question it answers: the string->code xref technique resolves ~49-65% of UTF-16
strings.  WHAT are the other half, and WHICH SUBSYSTEMS are we blind to?

Method (all measured, nothing inferred):
  1. partition the string census into LIT (>=1 code xref) and DARK (0)
  2. cluster by content: Class::Method prefix, source-file path (__FILE__), first token
  3. for LIT strings, record the .text RVA of the referrer  ->  gives a measured
     .rdata-position -> .text-position map
  4. use that map to predict, for each DARK string, which .text region would
     reference it, and check whether that region is decrypted
"""
import os
import re
import sys
import bisect
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strxref as SX

IDX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "strxref.idx")


def load():
    idx = SX.Index.load(IDX)
    d = idx._dump()
    return idx, d


CLS = re.compile(r"^([A-Za-z_][A-Za-z0-9_]{2,})::")
PATH = re.compile(r"([A-Za-z0-9_\-]+)[\\/]([A-Za-z0-9_\-]+\.(?:cpp|h|inl|cc))\s*$", re.I)
ANYPATH = re.compile(r"[\\/]([A-Za-z0-9_\-]+\.(?:cpp|h|inl|cc))", re.I)
TOK = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def main():
    idx, d = load()
    n = len(idx.s_rva)
    print("strings in index: %d" % n)

    # ---- 1. LIT vs DARK ------------------------------------------------
    refcount = [0] * n
    for si in idx.rs_str:
        refcount[si] += 1

    lit_site = [[] for _ in range(n)]
    for site, si in zip(idx.rf_site, idx.rf_str):
        lit_site[si].append(site)

    tot = collections.Counter()
    lit = collections.Counter()
    for i in range(n):
        e = chr(idx.s_enc[i])
        tot[e] += 1
        if refcount[i]:
            lit[e] += 1
    print()
    print("=" * 88)
    print("1. LIT vs DARK by encoding")
    print("=" * 88)
    for e in ("A", "U"):
        print(f"  {e}: total {tot[e]:7d}  lit {lit[e]:7d} ({100.0*lit[e]/tot[e]:5.1f}%)"
              f"  dark {tot[e]-lit[e]:7d}")

    # by length band (UTF-16 only)
    print()
    print("  UTF-16 by character length:")
    bands = [(4, 7), (8, 15), (16, 31), (32, 63), (64, 127), (128, 1 << 30)]
    for lo, hi in bands:
        t = l = 0
        for i in range(n):
            if idx.s_enc[i] != ord("U"):
                continue
            L = (idx.s_end[i] - idx.s_rva[i]) // 2
            if lo <= L <= hi:
                t += 1
                l += 1 if refcount[i] else 0
        if t:
            print(f"    {lo:4d}-{hi if hi < 1<<29 else '+':<5} n={t:7d}  lit {100.0*l/t:5.1f}%")

    # ---- 2. content clustering -----------------------------------------
    print()
    print("=" * 88)
    print("2. SOURCE-FILE (__FILE__) STRINGS -- the sharpest subsystem label")
    print("=" * 88)
    file_lit = collections.Counter()
    file_dark = collections.Counter()
    file_rvas = collections.defaultdict(list)
    nfile = 0
    for i in range(n):
        s = idx.text_of(i, d)
        m = ANYPATH.search(s)
        if not m or len(s) > 300:
            continue
        # a __FILE__ string is a bare path, not prose
        if " " in s.strip() or "%" in s:
            continue
        nfile += 1
        base = m.group(1)
        if refcount[i]:
            file_lit[base] += 1
        else:
            file_dark[base] += 1
        file_rvas[base].append(i)
    print(f"  source-path strings: {nfile}  (lit {sum(file_lit.values())}, dark {sum(file_dark.values())})")
    print(f"  distinct files: {len(set(file_lit) | set(file_dark))}")
    print("\n  --- top 40 DARK source files (no code references this __FILE__) ---")
    for k, v in file_dark.most_common(40):
        print(f"    {v:4d}  {k}")
    print("\n  --- top 25 LIT source files ---")
    for k, v in file_lit.most_common(25):
        print(f"    {v:4d}  {k}")

    print()
    print("=" * 88)
    print("3. Class::Method PREFIX CLUSTERING (UTF-16 strings)")
    print("=" * 88)
    cl_lit = collections.Counter()
    cl_dark = collections.Counter()
    for i in range(n):
        if idx.s_enc[i] != ord("U"):
            continue
        s = idx.text_of(i, d)
        m = CLS.match(s)
        if not m:
            continue
        k = m.group(1)
        if refcount[i]:
            cl_lit[k] += 1
        else:
            cl_dark[k] += 1
    allk = set(cl_lit) | set(cl_dark)
    print(f"  {len(allk)} distinct Class prefixes; "
          f"{sum(cl_lit.values())} lit / {sum(cl_dark.values())} dark messages")
    print("\n  --- classes with the MOST DARK messages (>=6 dark) ---")
    rows = sorted(allk, key=lambda k: -cl_dark[k])
    for k in rows[:45]:
        dk, lk = cl_dark[k], cl_lit[k]
        if dk < 6:
            break
        print(f"    dark {dk:4d} lit {lk:4d}  ({100.0*lk/(lk+dk):5.1f}% lit)  {k}")

    print()
    print("=" * 88)
    print("4. FIRST-TOKEN CLUSTERING of dark UTF-16 strings (subsystem vocabulary)")
    print("=" * 88)
    tk_dark = collections.Counter()
    tk_lit = collections.Counter()
    for i in range(n):
        if idx.s_enc[i] != ord("U"):
            continue
        L = (idx.s_end[i] - idx.s_rva[i]) // 2
        if L < 8:
            continue
        s = idx.text_of(i, d)
        m = TOK.search(s)
        if not m:
            continue
        k = m.group(0)
        if refcount[i]:
            tk_lit[k] += 1
        else:
            tk_dark[k] += 1
    print("  --- 50 most common leading tokens among DARK strings ---")
    for k, v in tk_dark.most_common(50):
        l = tk_lit.get(k, 0)
        print(f"    dark {v:5d}  lit {l:5d}  ({100.0*l/(l+v):5.1f}% lit)  '{k}'")

    return idx, d, refcount, lit_site


if __name__ == "__main__":
    main()
