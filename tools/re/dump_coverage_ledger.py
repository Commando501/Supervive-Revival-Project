#!/usr/bin/env python3
"""dump_coverage_ledger.py -- is every captured image actually folded into the merge?

WHY THIS EXISTS (FK-20, S133 2026-08-20)
----------------------------------------
Ten `dumpimage` snapshots sat on disk unmerged for six days and nobody could tell, because
`mergedumps` manifests name their donors by BASENAME only -- `merged2.dump.exe.txt` lists
"SUPERVIVE-Win64-Shipping.dump.exe" twelve times, which identifies nothing. A ledger FILE
would drift the same way. So this tool does not read manifests at all: it asks the BYTES
whether an image's decrypted pages are already present in the merge.

A .text page at RVA R is decrypted in a snapshot iff the 4096 bytes at file offset R are not
all zero (file offset == RVA in a dumpimage snapshot; the tool asserts this from the PE
section header before it measures anything).

An image is an ORPHAN iff it holds >=1 decrypted page the reference merge lacks. That is
exact, needs no bookkeeping, and cannot go stale.

USAGE
  python tools/re/dump_coverage_ledger.py                 # audit against the newest merged*.dump.exe
  python tools/re/dump_coverage_ledger.py --ref dumps/merged6.dump.exe
  python tools/re/dump_coverage_ledger.py --value         # also print per-image leave-one-out value
                                                          # (slower: O(n^2) over the corpus)

EXIT CODE: 0 if no orphans, 1 if any image is unmerged -- so it can gate a workflow.

MEASURED BASELINE (2026-08-20, dumps/merged6.dump.exe):
  26 state images, union == 16,694 / 30,281 .text pages (55.13 %), 0 orphans.
  12 images reach the union; 14 contribute 0 pages; only 8 images are irreplaceable at all,
  for 82 pages between them. An image's own coverage % does NOT predict its contribution --
  `toggles` (50.61 %, lowest non-outlier) holds the most unique pages (42), while
  menu/store/roster/missions (~52 %) are worth 0 each.
"""
import argparse
import glob
import os
import struct
import sys

PAGE = 4096


def section_text(path):
    """Return (vrva, vsize, rawptr) for .text, from the PE headers. Positive control that
    file offset == RVA lives here: the caller asserts vrva == rawptr."""
    with open(path, "rb") as f:
        d = f.read(0x400)
    if d[:2] != b"MZ":
        raise ValueError(f"{path}: not a PE")
    e = struct.unpack_from("<I", d, 0x3C)[0]
    if d[e:e + 4] != b"PE\0\0":
        raise ValueError(f"{path}: no PE signature")
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    base = e + 24 + optsz
    for i in range(nsec):
        o = base + i * 40
        nm = d[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
        vsz, vrva, rawsz, rawptr = struct.unpack_from("<IIII", d, o + 8)
        if nm == ".text":
            return vrva, vsz, rawptr
    raise ValueError(f"{path}: no .text section")


def bitmap(path, vrva, npages):
    bm = bytearray(npages)
    with open(path, "rb") as f:
        f.seek(vrva)
        for i in range(npages):
            b = f.read(PAGE)
            if not b:
                break
            if b.count(0) != len(b):
                bm[i] = 1
    return bm


def union(bms, npages):
    u = bytearray(npages)
    for bm in bms:
        for i in range(npages):
            if bm[i]:
                u[i] = 1
    return u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dumps", default="dumps", help="dumps root (default: dumps)")
    ap.add_argument("--ref", default=None,
                    help="reference merged image (default: newest dumps/merged*.dump.exe)")
    ap.add_argument("--value", action="store_true",
                    help="also compute per-image leave-one-out value (slower)")
    a = ap.parse_args()

    imgs = sorted(p.replace(os.sep, "/")
                  for p in glob.glob(os.path.join(a.dumps, "*", "SUPERVIVE-Win64-Shipping.dump.exe")))
    if not imgs:
        print(f"no state images under {a.dumps}/*/", file=sys.stderr)
        return 2

    ref = a.ref
    if ref is None:
        merged = sorted(glob.glob(os.path.join(a.dumps, "merged*.dump.exe")), key=os.path.getmtime)
        if not merged:
            print("no merged*.dump.exe found; pass --ref", file=sys.stderr)
            return 2
        ref = merged[-1].replace(os.sep, "/")

    vrva, vsize, rawptr = section_text(imgs[0])
    npages = vsize // PAGE + (1 if vsize % PAGE else 0)
    print(f"[CTRL] .text VRVA={vrva:#x} VSize={vsize:#x} RawPtr={rawptr:#x} -> "
          f"file offset == RVA: {'PASS' if vrva == rawptr else 'FAIL'}")
    if vrva != rawptr:
        print("       ABORT: this tool assumes file offset == RVA for .text", file=sys.stderr)
        return 2
    print(f"[CTRL] pages in .text: {npages}")
    print(f"reference merge : {ref}")
    print(f"state images    : {len(imgs)}")
    print()

    refbm = bitmap(ref, vrva, npages)
    bms = {}
    orphans = []
    print(f"{'image':40s} {'pages':>7s} {'  %':>7s}  {'not in ref':>10s}")
    for p in imgs:
        name = p.split("/")[-2]
        bm = bitmap(p, vrva, npages)
        bms[name] = bm
        n = sum(bm)
        miss = sum(1 for i in range(npages) if bm[i] and not refbm[i])
        flag = "  <-- ORPHAN" if miss else ""
        print(f"{name:40s} {n:7d} {n / npages * 100:6.2f}% {miss:10d}{flag}")
        if miss:
            orphans.append((name, miss))

    u = union(bms.values(), npages)
    print()
    print(f"union of all {len(imgs)} images : {sum(u)} pages ({sum(u) / npages * 100:.2f}%)")
    print(f"reference merge            : {sum(refbm)} pages ({sum(refbm) / npages * 100:.2f}%)")
    extra = sum(1 for i in range(npages) if refbm[i] and not u[i])
    if extra:
        print(f"NOTE: the reference holds {extra} pages no state image has "
              f"(a donor was deleted, or the ref was seeded from an older merge).")

    if a.value:
        print()
        print("LEAVE-ONE-OUT VALUE (pages lost from the union if this image were deleted):")
        any_val = False
        for name in bms:
            others = union([b for k, b in bms.items() if k != name], npages)
            lost = sum(1 for i in range(npages) if u[i] and not others[i])
            if lost:
                any_val = True
                print(f"  {name:40s} {lost:5d}")
        if not any_val:
            print("  (every image is redundant with the rest of the corpus)")

    print()
    if orphans:
        gain = sum(1 for i in range(npages) if u[i] and not refbm[i])
        print(f"RESULT: {len(orphans)} ORPHAN IMAGE(S).")
        print(f"  Re-merging them raises the reference by {gain} page(s).")
        print(f"  WARNING: the per-image 'not in ref' column is NOT ADDITIVE -- orphans share "
              f"missing pages. Those columns sum to {sum(m for _, m in orphans)}, the real "
              f"union gain is {gain}. Quote the union gain, never the column sum.")
        print("  tools/usmapdump/usmapdump.exe mergedumps <newmerged> " + ref + " \\")
        for name, _ in orphans:
            print(f"      {a.dumps}/{name}/SUPERVIVE-Win64-Shipping.dump.exe \\")
        return 1
    print("RESULT: no orphans -- every captured image is folded into the reference merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
