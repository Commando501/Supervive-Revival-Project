#!/usr/bin/env python3
"""
statecov.py -- estimate how much .text a RICHER runtime state decrypts, using the crash
minidumps' function tables as a proxy for execution coverage.

A crash table's real (size>1) entries mark code the packer had already decrypted in THAT
process.  Converting each table to the set of 4 KiB pages its entries span gives a
page-coverage estimate for that process -- directly comparable to the page coverage of
dumps/merged.dump.exe.  The crashes come from real sessions (DS/tutorial/deploy work),
i.e. states we have never captured an image dump from.
"""
import os
import sys
import glob
import struct
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdpdata as MD
from dumpcov import PAGE

CRASH = r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "pagecov.json")
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000
NPG = (TEXT_SIZE + PAGE - 1) // PAGE


def pages_of(d):
    e = d["entries"]
    s = set()
    for i in range(d["count"]):
        b, en, u = struct.unpack_from("<III", e, i * 12)
        if en - b > 1:
            for p in range((b - TEXT_RVA) // PAGE, (en - 1 - TEXT_RVA) // PAGE + 1):
                s.add(p)
    return s


def main():
    with open(CACHE) as f:
        cov = {k: bytes.fromhex(v) for k, v in json.load(f).items()}
    m = cov["merged"]
    mset = set(i for i in range(len(m)) if m[i])
    # 2026-08-14 (S121): these two lines used to hardcode "merged.dump.exe" and "all 9 IMAGE
    # dumps". Both numbers came from a cache that had silently frozen on 2026-07-26, so the
    # labels were wrong AND the figures were stale -- it printed 15,833 / 54.27% for months
    # after the real values were 16,638 / 54.95%. Derive both from the data.
    from dumpcov2 import MERGED_NAME, NAMES as _STATES
    print(f"{MERGED_NAME} decrypted .text pages : {len(mset):,} / {NPG:,} "
          f"({100.0*len(mset)/NPG:.2f}%)")
    imgunion = set()
    for k, v in cov.items():
        if k != "merged":
            imgunion |= set(i for i in range(len(v)) if v[i])
    print(f"union of all {len(_STATES)} IMAGE dumps            : {len(imgunion):,} "
          f"({100.0*len(imgunion)/NPG:.2f}%)")

    dumps = sorted(glob.glob(os.path.join(CRASH, "UECC-*", "UEMinidump.dmp")))
    tabs = []
    for p in dumps:
        try:
            d = MD.sane(MD.parse_ft(p, quiet=True))
        except Exception:
            continue
        if d:
            tabs.append((os.path.basename(os.path.dirname(p))[13:29],
                         os.path.getmtime(p), pages_of(d)))
    tabs.sort(key=lambda t: -len(t[2]))
    print(f"\n{len(tabs)} crash tables.  Pages spanned by their REAL function entries:")
    print(f"  {'crash':<18} {'pages':>7} {'% .text':>9} {'NEW vs merged':>14}")
    for tag, mt, s in tabs[:12]:
        print(f"  {tag:<18} {len(s):7,} {100.0*len(s)/NPG:8.2f}% {len(s-mset):14,}")
    print("  ...")
    for tag, mt, s in tabs[-3:]:
        print(f"  {tag:<18} {len(s):7,} {100.0*len(s)/NPG:8.2f}% {len(s-mset):14,}")

    allp = set()
    for tag, mt, s in tabs:
        allp |= s
    print(f"\n  UNION of all crash tables            : {len(allp):,} "
          f"({100.0*len(allp)/NPG:.2f}% of .text)")
    print(f"  ... NEW vs merged.dump.exe           : {len(allp-mset):,} pages "
          f"({(len(allp-mset))*PAGE/1048576:.1f} MB)")
    print(f"  ... NEW vs the union of all 9 images  : {len(allp-imgunion):,} pages "
          f"({(len(allp-imgunion))*PAGE/1048576:.1f} MB)")
    grand = allp | imgunion
    print(f"  GRAND union (images + crash tables)   : {len(grand):,} "
          f"({100.0*len(grand)/NPG:.2f}% of .text)")
    print(f"  still never seen by anything          : {NPG-len(grand):,} pages "
          f"({100.0*(NPG-len(grand))/NPG:.2f}%)")
    print("\n  NOTE: a crash table page means 'the packer had decrypted a function there',")
    print("  which is EXECUTION coverage.  The minidumps do NOT contain .text bytes")
    print("  (MemoryList is ~60 KB), so these pages are known to exist but are not readable.")
    print("  They quantify what an IMAGE dump from that state would capture.")


if __name__ == "__main__":
    main()
