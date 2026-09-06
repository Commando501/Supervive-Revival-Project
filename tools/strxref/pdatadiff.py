#!/usr/bin/env python3
"""
pdatadiff.py -- why do two crash minidumps disagree about a table with the same entry
count, and what are the 208,385 entries of size <=16 bytes?

Hypothesis under test: the packer materialises the RUNTIME_FUNCTION table LAZILY, in
step with demand-decrypt, so a table snapshot reflects that process's execution
coverage -- meaning the 70 tables can be UNIONED the same way .text pages are.
"""
import os
import sys
import glob
import struct
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
    return [struct.unpack_from("<III", e, i * 12) for i in range(n)], d["base"]


def main():
    dumps = sorted(glob.glob(os.path.join(CRASH, "UECC-*", "UEMinidump.dmp")))
    ok = []
    for p in dumps:
        try:
            if MD.sane(MD.parse_ft(p, quiet=True)):
                ok.append(p)
        except Exception:
            pass

    A, ba = table(ok[0])
    B, bb = table(ok[1])
    print(f"A = {os.path.basename(os.path.dirname(ok[0]))[13:29]}  base 0x{ba:012X}")
    print(f"B = {os.path.basename(os.path.dirname(ok[1]))[13:29]}  base 0x{bb:012X}")

    print("\n" + "=" * 88)
    print("1. WHERE DO TWO TABLES DIFFER?")
    print("=" * 88)
    db = de = du = 0
    for (b1, e1, u1), (b2, e2, u2) in zip(A, B):
        db += b1 != b2
        de += e1 != e2
        du += u1 != u2
    print(f"  differing BeginAddress      : {db:,}")
    print(f"  differing EndAddress        : {de:,}")
    print(f"  differing UnwindInfoAddress : {du:,}")
    if db == 0 and de == 0:
        print("  ==> BEGIN/END ARE IDENTICAL.  Only the unwind-info pointer moves"
              " (it is allocated per-process), so FUNCTION BOUNDS ARE STABLE.")
    else:
        shown = 0
        for i, ((b1, e1, u1), (b2, e2, u2)) in enumerate(zip(A, B)):
            if (b1, e1) != (b2, e2) and shown < 10:
                print(f"    [{i}] A 0x{b1:X}..0x{e1:X}   B 0x{b2:X}..0x{e2:X}")
                shown += 1

    print("\n" + "=" * 88)
    print("2. WHAT ARE THE TINY ENTRIES?")
    print("=" * 88)
    with open(MERGED, "rb") as f:
        img = f.read()

    def dec(rva):
        p = rva & ~(PAGE - 1)
        return img[p:p + PAGE].strip(b"\0") != b""

    sizes = collections.Counter(e - b for b, e, u in A)
    print("  most common exact sizes:")
    for s, c in sizes.most_common(10):
        print(f"    {s:>6} B : {c:>8,} entries ({100.0*c/len(A):5.1f}%)")

    one = [(b, e, u) for b, e, u in A if e - b == 1]
    print(f"\n  size-1 entries: {len(one):,}")
    dec1 = sum(1 for b, e, u in one if dec(b))
    print(f"    on a DECRYPTED page: {dec1:,} ({100.0*dec1/len(one):.1f}%)")
    allb = [(b, e, u) for b, e, u in A if e - b > 1]
    decn = sum(1 for b, e, u in allb if dec(b))
    print(f"  size>1 entries: {len(allb):,}   on a DECRYPTED page: {decn:,} "
          f"({100.0*decn/len(allb):.1f}%)")
    print("\n  first bytes at a size-1 entry (decrypted ones only), top 10:")
    fb = collections.Counter()
    shown = 0
    for b, e, u in one:
        if dec(b):
            fb[img[b:b + 8].hex()] += 1
            shown += 1
        if shown > 40000:
            break
    for k, v in fb.most_common(10):
        print(f"    {k}  {v:,}")
    print("\n  unwind-info RVA for size-1 entries, top 5:")
    uu = collections.Counter(u for b, e, u in one)
    for k, v in uu.most_common(5):
        print(f"    0x{k:X}  {v:,}")
    print("  unwind-info RVA for size>1 entries, top 5:")
    uu2 = collections.Counter(u for b, e, u in allb)
    for k, v in uu2.most_common(5):
        print(f"    0x{k:X}  {v:,}")

    print("\n" + "=" * 88)
    print("3. IS THE TABLE LAZY?  compare size-1 population across dumps")
    print("=" * 88)
    for p in ok[:6]:
        T, bs = table(p)
        n1 = sum(1 for b, e, u in T if e - b == 1)
        cov = sum(e - b for b, e, u in T if e - b > 1)
        print(f"  {os.path.basename(os.path.dirname(p))[13:29]}  size-1 {n1:,}"
              f"  bytes covered by real-size entries {cov:,}")

    print("\n" + "=" * 88)
    print("4. REAL FUNCTION COUNT AND COVERAGE AFTER DROPPING SIZE-1 PLACEHOLDERS")
    print("=" * 88)
    real = allb
    cov = sum(e - b for b, e, u in real)
    print(f"  entries with size>1 : {len(real):,}")
    print(f"  bytes covered       : {cov:,} ({100.0*cov/TEXT_SIZE:.1f}% of .text)")
    # do size-1 entries sit INSIDE a size>1 entry?
    starts = sorted(b for b, e, u in real)
    ends = {}
    for b, e, u in real:
        ends[b] = e
    import bisect
    inside = 0
    for b, e, u in one[:50000]:
        i = bisect.bisect_right(starts, b) - 1
        if i >= 0 and b < ends[starts[i]]:
            inside += 1
    print(f"  of 50,000 sampled size-1 entries, {inside:,} fall INSIDE a size>1 entry")


if __name__ == "__main__":
    main()
