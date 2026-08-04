#!/usr/bin/env python3
"""
yield.py -- how many NEW string->code xrefs does each additional decrypted .text page buy?

Two independent estimates, one MEASURED and one EXTRAPOLATED:

  A. MEASURED marginal yield.  Three dumps (toggles, rcb, vmbuild) contain .text pages
     that merged.dump.exe does not.  Scan ONLY those pages for rip-relative refs into
     .rdata, resolve against the existing string census, and count strings that gain
     their FIRST reference.  This is real data: new-strings-per-new-page.

  B. EXTRAPOLATED total.  Rarefaction over the merged dump's own decrypted pages:
     sample k% of pages, count distinct strings referenced, fit the accumulation curve,
     extrapolate to 100% of .text.  Gives an estimated ceiling for the technique.
"""
import os
import re
import sys
import random
import bisect
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strxref as SX
from dumpcov import Img, page_bits, PAGE

DUMPS = r"G:\git\Supervive Revival Project\dumps"
IDX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "strxref.idx")

LEA = re.compile(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", re.S)


def refs_in_pages(path, text_rva, pages, rdata_lo, rdata_hi):
    """Yield (site_rva, target_rva) for lea r64,[rip+d32] inside the given page indices."""
    out = []
    with open(path, "rb") as f:
        for pi in sorted(pages):
            f.seek(text_rva + pi * PAGE)
            # read the page plus 6 bytes of the next so instructions straddling the
            # boundary are still decoded (only counts if the next page is present too,
            # which is why we read from the same image)
            buf = f.read(PAGE + 8)
            base = text_rva + pi * PAGE
            for m in LEA.finditer(buf):
                o = m.start()
                if o + 7 > len(buf):
                    break
                if o >= PAGE:
                    break
                disp = int.from_bytes(buf[o + 3:o + 7], "little", signed=True)
                tgt = base + o + 7 + disp
                if rdata_lo <= tgt < rdata_hi:
                    out.append((base + o, tgt))
    return out


def main():
    idx = SX.Index.load(IDX)
    d = idx._dump()
    n = len(idx.s_rva)
    refcount = [0] * n
    for si in idx.rs_str:
        refcount[si] += 1
    lit = set(i for i in range(n) if refcount[i])
    print("index: %d strings, %d already lit" % (n, len(lit)))

    merged = os.path.join(DUMPS, "merged.dump.exe")
    im = Img(merged)
    T = im.sec(".text")
    R = im.sec(".rdata")
    text_rva, rd_lo, rd_hi = T[1], R[1], R[1] + R[2]
    mbits, npg = page_bits(merged, T[1], T[2])

    print()
    print("=" * 90)
    print("A. MEASURED MARGINAL YIELD -- .text pages present in other dumps but not merged")
    print("=" * 90)
    tot_new_pages = 0
    all_new_strings = set()
    per_dump = {}
    for name in ("toggles", "rcb", "vmbuild", "accountpass"):
        p = os.path.join(DUMPS, name, "SUPERVIVE-Win64-Shipping.dump.exe")
        b, _ = page_bits(p, T[1], T[2])
        extra = [i for i in range(npg) if b[i] and not mbits[i]]
        refs = refs_in_pages(p, text_rva, extra, rd_lo, rd_hi)
        hitstr = set()
        for site, tgt in refs:
            i, off = idx.resolve(tgt)
            if i >= 0:
                hitstr.add(i)
        new = hitstr - lit
        per_dump[name] = (len(extra), len(refs), len(hitstr), new)
        print(f"  {name:<12} extra pages {len(extra):5d}   lea->.rdata {len(refs):7d}"
              f"   strings hit {len(hitstr):6d}   NEWLY LIT {len(new):6d}")
        tot_new_pages += len(extra)
        all_new_strings |= new
    # union without double counting
    union_pages = set()
    for name in ("toggles", "rcb", "vmbuild", "accountpass"):
        p = os.path.join(DUMPS, name, "SUPERVIVE-Win64-Shipping.dump.exe")
        b, _ = page_bits(p, T[1], T[2])
        union_pages |= set(i for i in range(npg) if b[i] and not mbits[i])
    print(f"\n  UNION extra pages       : {len(union_pages)}")
    print(f"  UNION newly-lit strings : {len(all_new_strings)}")
    if union_pages:
        print(f"  ==> {len(all_new_strings)/len(union_pages):.2f} newly-lit strings per new .text page")
        print(f"  ==> {len(all_new_strings)/(len(union_pages)*PAGE/1048576):.1f} newly-lit strings per MB of new .text")
    # what ARE they?
    print("\n  sample of newly-lit strings (30):")
    for i in sorted(all_new_strings)[:30]:
        s = idx.text_of(i, d)
        s = s if len(s) <= 84 else s[:81] + "..."
        print(f"    0x{idx.s_rva[i]:08X} {chr(idx.s_enc[i])} {s!r}")

    print()
    print("=" * 90)
    print("B. RAREFACTION over merged's own decrypted pages -> extrapolated ceiling")
    print("=" * 90)
    # map every existing reference site -> page index, then subsample pages
    site_page = collections.defaultdict(set)
    for site, si in zip(idx.rf_site, idx.rf_str):
        pi = (site - text_rva) // PAGE
        site_page[pi].add(si)
    covered = [i for i in range(npg) if mbits[i]]
    print(f"  decrypted pages {len(covered)} / {npg} ({100.0*len(covered)/npg:.2f}%)")
    print(f"  pages carrying >=1 string ref: {len(site_page)}")
    rng = random.Random(1234)
    order = covered[:]
    rng.shuffle(order)
    print(f"\n  {'frac of decrypted .text':>24} {'pages':>7} {'distinct strings lit':>21}")
    marks = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    seen = set()
    mi = 0
    curve = []
    for k, pi in enumerate(order, 1):
        seen.update(site_page.get(pi, ()))
        while mi < len(marks) and k >= marks[mi] * len(order):
            print(f"  {marks[mi]*100:23.0f}% {k:7d} {len(seen):21d}")
            curve.append((k, len(seen)))
            mi += 1
    # Chao1-style / linear-tail extrapolation on the last decile
    (k1, s1), (k2, s2) = curve[-3], curve[-1]
    slope = (s2 - s1) / (k2 - k1)
    remaining = npg - len(covered)
    print(f"\n  tail slope over last 20% of pages: {slope:.3f} new strings per page")
    print(f"  undecrypted pages remaining      : {remaining}")
    print(f"  LINEAR extrapolation to 100% .text: +{int(slope*remaining)} strings"
          f"  -> {len(seen)+int(slope*remaining)} total ({100.0*(len(seen)+slope*remaining)/n:.1f}% of census)")


if __name__ == "__main__":
    main()
