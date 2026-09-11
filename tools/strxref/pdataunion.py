#!/usr/bin/env python3
"""
pdataunion.py -- union the lazily-materialised RUNTIME_FUNCTION tables from all usable
crash minidumps into one maximal .pdata for SUPERVIVE-Win64-Shipping.exe.

Measured facts this rests on (see pdatadiff.py):
  * stream 13 descriptor [exe] has 524,439 slots in every dump
  * a slot with EndAddress == BeginAddress+1 is a PLACEHOLDER for a function the packer
    has not decrypted in that process (12.9% on decrypted pages vs 93.7% for real slots)
  * placeholder count varies 155,497..181,109 across dumps => the table tracks execution
  * UnwindInfoAddress is byte-identical across dumps => one static table, filled in place
  * no placeholder ever falls inside a real entry
Therefore real (size>1) entries from different processes can be UNIONED, exactly like
demand-decrypted .text pages.

Outputs:
  index/pdata_union.csv   begin_rva,end_rva,size,seen_in_n_dumps
  index/pdata_union.bin   RVA-sorted RUNTIME_FUNCTION array (12 B each), Ghidra-importable
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
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index")
TEXT_RVA, TEXT_SIZE = 0x1000, 0x7649000


def main():
    dumps = sorted(glob.glob(os.path.join(CRASH, "UECC-*", "UEMinidump.dmp")))
    tables = []
    for p in dumps:
        try:
            d = MD.sane(MD.parse_ft(p, quiet=True))
        except Exception:
            continue
        if d:
            tables.append((p, d))
    print(f"usable tables: {len(tables)}")

    seen = collections.Counter()     # (begin,end) -> how many dumps
    unwind = {}
    per_dump_real = []
    for p, d in tables:
        e = d["entries"]
        r = 0
        for i in range(d["count"]):
            b, en, u = struct.unpack_from("<III", e, i * 12)
            if en - b > 1:
                seen[(b, en)] += 1
                unwind[(b, en)] = u
                r += 1
        per_dump_real.append((os.path.basename(os.path.dirname(p))[13:29], r))

    ents = sorted(seen)
    print(f"\nUNION: {len(ents):,} distinct real functions")
    best = max(r for _, r in per_dump_real)
    worst = min(r for _, r in per_dump_real)
    print(f"  best single dump : {best:,}")
    print(f"  worst single dump: {worst:,}")
    print(f"  union gain over best single dump: +{len(ents)-best:,} "
          f"({100.0*(len(ents)-best)/best:.1f}%)")

    cov = sum(e - b for b, e in ents)
    print(f"  bytes covered by union: {cov:,} ({100.0*cov/TEXT_SIZE:.1f}% of .text VSize)")

    # overlap sanity: do any two union entries overlap?  (they must not)
    ov = 0
    prev_e = 0
    for b, e in ents:
        if b < prev_e:
            ov += 1
        prev_e = max(prev_e, e)
    print(f"  overlapping entries in the union: {ov}")

    # how universal is each entry?
    hist = collections.Counter(seen.values())
    print(f"\n  entries seen in ALL {len(tables)} dumps : {hist[len(tables)]:,}")
    print(f"  entries seen in exactly 1 dump   : {hist[1]:,}   <- state-specific code")

    # relationship to the cold image's .text decryption (MERGED above; merged2 since S121)
    with open(MERGED, "rb") as f:
        img = f.read()

    def dec(rva):
        p = rva & ~(PAGE - 1)
        return img[p:p + PAGE].strip(b"\0") != b""

    d_yes = d_no = 0
    for b, e in ents:
        if dec(b):
            d_yes += 1
        else:
            d_no += 1
    print(f"\n  union functions whose entry page is DECRYPTED in {os.path.basename(MERGED)}: {d_yes:,}")
    print(f"  union functions in pages {os.path.basename(MERGED)} NEVER decrypted{'':{max(0,14-len(os.path.basename(MERGED)))}}: {d_no:,}")
    print("  ==> the crash tables name functions the image dump cannot even show bytes for.")

    # greedy incremental: how many dumps do you actually need?
    print("\n  greedy incremental union (top 12 contributors):")
    remaining = list(range(len(tables)))
    sets = []
    for p, d in tables:
        e = d["entries"]
        s = set()
        for i in range(d["count"]):
            b, en, u = struct.unpack_from("<III", e, i * 12)
            if en - b > 1:
                s.add((b, en))
        sets.append(s)
    acc = set()
    for step in range(12):
        bi, bg = -1, -1
        for i in remaining:
            g = len(sets[i] - acc)
            if g > bg:
                bg, bi = g, i
        if bi < 0 or bg == 0:
            break
        acc |= sets[bi]
        remaining.remove(bi)
        print(f"    {step+1:2d}. {tables[bi][0].split(os.sep)[-2][13:29]}  "
              f"+{bg:6,}  -> {len(acc):,}")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "pdata_union.csv"), "w") as f:
        f.write("begin_rva,end_rva,size,unwind_rva,seen_in_dumps\n")
        for b, e in ents:
            f.write(f"0x{b:X},0x{e:X},{e-b},0x{unwind[(b,e)]:X},{seen[(b,e)]}\n")
    with open(os.path.join(OUT, "pdata_union.bin"), "wb") as f:
        for b, e in ents:
            f.write(struct.pack("<III", b, e, unwind[(b, e)]))
    print(f"\nwrote {OUT}\\pdata_union.csv and pdata_union.bin "
          f"({len(ents)*12:,} bytes, {len(ents):,} RUNTIME_FUNCTIONs)")


if __name__ == "__main__":
    main()
