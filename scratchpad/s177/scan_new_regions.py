"""S177 Move I-3 (step 2 of 2): Byte-scan pre-kill region dumps for 0xDEAD primitives.

Downstream of diff_snapshots.py. Two usage modes:

1. EXPLICIT — scan a specific list of .bin filenames inside the pre-kill dir:
     python scan_new_regions.py <prekill_dir> <file1.bin> [<file2.bin> ...]

2. AUTO   — diff pre-kill dir's files against a baseline dir and scan only
              files that are NEW in pre-kill (present in pre-kill, absent in
              baseline; matched by BASENAME, since VAs live in the name):
     python scan_new_regions.py <prekill_dir> --auto <baseline_dir>

3. ALL    — scan every .bin in the pre-kill dir (fallback; noisy):
     python scan_new_regions.py <prekill_dir> --all

Patterns scanned (identical to scratchpad/s176/scan_hidden_for_dead.py so
Move M and Move I-3 outputs are directly comparable — do not "improve" the
pattern list without updating both):

  1. `BA AD DE 00 00 0F 05` = mov edx, 0xDEAD; syscall  (the exact FK-32 primitive)
  2. `BA AD DE 00 00`        = mov edx, 0xDEAD          (S161's sole hit was here)
  3. `<opcode> AD DE 00 00`  = mov r32, 0xDEAD for any GP register
  4. `AD DE 00 00`           = bare 0x0000DEAD imm32
  5. `AD DE`                 = 2-byte density measure (encrypted-blob detector)

Discriminator (per docs/next-session-prompt-s177.md NEXT STEP branches):
  hits on pattern 1 in a new MEM_PRIVATE RWX region -> Candidate A CONFIRMED,
                                                       JIT stub identified,
                                                       Move I-5 sets a BP on
                                                       the hit VA on next run.
  hits on 2/3 only                                  -> pre-kill setup wrote a
                                                       constant DE AD somewhere
                                                       but no syscall pair;
                                                       [I] leaning against A.
  zero hits on 1-3                                  -> A refuted for this
                                                       flight; try again with
                                                       a later pre-kill snapshot
                                                       (JIT allocation may fire
                                                       within seconds of kill),
                                                       then move to Move I-4.

Filename convention (dumpimage.go):
  <STEM>.exec_0x<VA>_<SIZE>[_hidden].bin
  VA is a hex integer without 0x fill; SIZE is hex without prefix.
  The scanner parses VA out of the filename so hit addresses print in absolute
  process VA, not file offset.
"""
from __future__ import annotations
import os, sys, glob, argparse

PATTERNS = {
    # Order matters — the report prints in this order.
    "mov_edx_0xDEAD_syscall": b"\xba\xad\xde\x00\x00\x0f\x05",
    "mov_edx_0xDEAD":         b"\xba\xad\xde\x00\x00",
    "ad_de_00_00_raw":        b"\xad\xde\x00\x00",
    "ad_de_bigram":           b"\xad\xde",
}
REG_NAMES_LOW = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"]

def parse_va(fname: str) -> int:
    """Extract VA from `<stem>.exec_0x<VA>_<SIZE>[_hidden].bin`.

    Returns 0 for filenames that don't match the convention (which is fine -
    the scanner still runs; hit addresses just print as file offsets).
    """
    base = os.path.basename(fname)
    for p in base.split("_"):
        if p.startswith("0x"):
            try:
                return int(p, 16)
            except ValueError:
                return 0
    return 0

def scan_one(path: str) -> dict:
    """Scan a single .bin. Returns hit dict per pattern, keyed by name."""
    try:
        with open(path, "rb") as fp:
            data = fp.read()
    except OSError as e:
        # Missing file (a stale filename from --auto?) is a warning, not a fault.
        # Return a hits dict with a synthetic 'read_error' key so the caller
        # can flag it without crashing the whole scan.
        return {"__read_error__": str(e)}
    va = parse_va(path)
    size = len(data)
    hits: dict = {"__size__": size, "__va__": va}
    # Exact patterns first
    for key, pat in PATTERNS.items():
        pos, found = 0, []
        while True:
            i = data.find(pat, pos)
            if i < 0:
                break
            ctx_start = max(0, i - 3)
            ctx_end   = min(len(data), i + len(pat) + 8)
            found.append((va + i, data[ctx_start:ctx_end].hex()))
            pos = i + 1
        hits[key] = found
    # Any-register mov: opcodes B8..BF followed by AD DE 00 00 (32-bit imm)
    # Also REX-prefixed 41 B8..BF for r8d..r15d.
    reg_hits: list = []
    for opcode in range(0xB8, 0xC0):
        # non-REX
        pat = bytes([opcode]) + b"\xad\xde\x00\x00"
        pos = 0
        while True:
            i = data.find(pat, pos)
            if i < 0: break
            reg = REG_NAMES_LOW[opcode & 7]
            ctx = data[max(0, i - 3):min(len(data), i + len(pat) + 8)].hex()
            reg_hits.append((va + i, reg, ctx))
            pos = i + 1
        # REX.B
        pat = b"\x41" + bytes([opcode]) + b"\xad\xde\x00\x00"
        pos = 0
        while True:
            i = data.find(pat, pos)
            if i < 0: break
            reg = f"r{8 + (opcode & 7)}d"
            ctx = data[max(0, i - 3):min(len(data), i + len(pat) + 8)].hex()
            reg_hits.append((va + i, reg, ctx))
            pos = i + 1
    hits["mov_r32_0xDEAD_any"] = reg_hits
    return hits

def discover_new(prekill_dir: str, baseline_dir: str) -> list[str]:
    """Return .bin filenames present in prekill_dir but absent from baseline_dir.

    Matches by BASENAME so an absolute-path list in one dir vs the other still
    correlates correctly.
    """
    pre_files  = {os.path.basename(p) for p in glob.glob(os.path.join(prekill_dir, "*.bin"))}
    base_files = {os.path.basename(p) for p in glob.glob(os.path.join(baseline_dir, "*.bin"))}
    return sorted(pre_files - base_files)

def all_bins(prekill_dir: str) -> list[str]:
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(prekill_dir, "*.bin")))

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Byte-scan pre-kill region dumps for 0xDEAD-producing bytes.",
    )
    ap.add_argument("prekill_dir")
    ap.add_argument("files", nargs="*", help="explicit .bin filenames (basename form)")
    ap.add_argument("--auto", metavar="BASELINE_DIR",
                    help="auto-discover files new in prekill vs baseline")
    ap.add_argument("--all", action="store_true",
                    help="scan every .bin in prekill_dir (noisy - Move M-class)")
    args = ap.parse_args()

    if args.all and args.auto:
        ap.error("--all and --auto are mutually exclusive")
    if args.all and args.files:
        ap.error("--all and explicit files are mutually exclusive")

    if args.auto:
        targets = discover_new(args.prekill_dir, args.auto)
        print(f"[scan] --auto: {len(targets)} new files vs {args.auto}")
    elif args.all:
        targets = all_bins(args.prekill_dir)
        print(f"[scan] --all: {len(targets)} files in {args.prekill_dir}")
    else:
        if not args.files:
            ap.error("provide filenames, --auto BASELINE, or --all")
        targets = args.files
        print(f"[scan] explicit: {len(targets)} files")

    if not targets:
        print("[scan] nothing to scan.")
        print("[scan] If this was --auto, the pre-kill snapshot introduced no new .bin files")
        print("[scan] -> Candidate A (JIT stub in a NEW region) is REFUTED for this flight.")
        print("[scan] Note: an existing region could still have been REWRITTEN in place;")
        print("[scan] re-run with --all to scan every region for the 0xDEAD pattern.")
        return

    all_results = []
    for fname in targets:
        path = os.path.join(args.prekill_dir, fname)
        h = scan_one(path)
        all_results.append((fname, h))

    # Totals across all files scanned, so a successor sees the shape at a
    # glance rather than reading every per-file section.
    totals = {k: 0 for k in list(PATTERNS.keys()) + ["mov_r32_0xDEAD_any"]}
    for fname, h in all_results:
        if "__read_error__" in h:
            continue
        for k in totals:
            totals[k] += len(h.get(k, []))

    print()
    print("=" * 72)
    print("TOTALS ACROSS SCANNED FILES")
    print("=" * 72)
    for k in ["mov_edx_0xDEAD_syscall", "mov_edx_0xDEAD",
              "mov_r32_0xDEAD_any", "ad_de_00_00_raw", "ad_de_bigram"]:
        print(f"  {k}: {totals[k]} hits")

    # Rank 1 output: exact primitive matches (this is the whole point).
    print()
    print("=" * 72)
    print("EXACT 'mov edx, 0xDEAD; syscall' MATCHES  (Candidate A witness)")
    print("=" * 72)
    seen_p1 = False
    for fname, h in all_results:
        matches = h.get("mov_edx_0xDEAD_syscall", [])
        if matches:
            seen_p1 = True
            for va, ctx in matches:
                print(f"  {fname}: VA=0x{va:X}  ctx={ctx}")
    if not seen_p1:
        print("  (no exact primitive hits)")

    # Rank 2 output: mov edx, 0xDEAD without syscall follow-up. S161's sole
    # hit in the whole runtime.dll shipped-image scan was this pattern (at
    # RVA 0x80F80C, inside the known kill primitive). A hit elsewhere is
    # notable but not conclusive.
    print()
    print("--- 'mov edx, 0xDEAD' matches (may be primitive without syscall attached) ---")
    seen_p2 = False
    for fname, h in all_results:
        matches = h.get("mov_edx_0xDEAD", [])
        if matches:
            seen_p2 = True
            for va, ctx in matches:
                print(f"  {fname}: VA=0x{va:X}  ctx={ctx}")
    if not seen_p2:
        print("  (none)")

    # Rank 3 output: any register loaded with 0xDEAD as imm32. edx-specific
    # would produce a duplicate row here, so a successor is expected to
    # cross-reference the two blocks.
    print()
    print("--- 'mov rXX, 0xDEAD' any-register matches ---")
    seen_p3 = False
    for fname, h in all_results:
        matches = h.get("mov_r32_0xDEAD_any", [])
        if matches:
            seen_p3 = True
            for va, reg, ctx in matches:
                print(f"  {fname}: VA=0x{va:X}  reg={reg}  ctx={ctx}")
    if not seen_p3:
        print("  (none)")

    # Bigram density is a proxy for "encrypted blob" — a region with lots of
    # AD-DE bigrams that are NOT part of a mov instruction is almost always
    # random-looking data (encrypted `.rdata`, key material, etc.).
    print()
    print("--- 2-byte AD DE bigram density (context - do not read as a hit) ---")
    for fname, h in all_results:
        if "__read_error__" in h:
            print(f"  {fname}: READ ERROR: {h['__read_error__']}")
            continue
        size = h.get("__size__", 0)
        n = len(h.get("ad_de_bigram", []))
        density = (n / max(1, size)) * 65536
        marker = " ** HIGH DENSITY (encrypted data?) **" if density > 2.0 else ""
        print(f"  {fname}: size={size:>10}  bigrams={n:<6}  density={density:.2f}/64K{marker}")

    # Final verdict text - a successor can grep for VERDICT and know what
    # branch of the discriminator this scan lands on.
    print()
    print("=" * 72)
    print("VERDICT (per S177 discriminator)")
    print("=" * 72)
    if totals["mov_edx_0xDEAD_syscall"] > 0:
        print("HIT: exact FK-32 primitive found in a scanned region.")
        print("  -> Cross-check the VA against diff_snapshots.py's RANK 1 list.")
        print("     If the hit is in a NEW MEM_PRIVATE RWX region: Candidate A (JIT stub) CONFIRMED.")
        print("     If the hit is inside a hidden Image mapping already flagged in Move M: it's")
        print("       one of the two known LOW/HIGH mirrors of runtime.dll +0x80F7F0 - NOT news.")
        print("     Move I-5: install a HW BP on the hit VA on the next armed run and read RIP.")
    elif totals["mov_edx_0xDEAD"] > 0 or totals["mov_r32_0xDEAD_any"] > 0:
        print("PARTIAL: 0xDEAD as an immediate exists somewhere, but no `mov edx, 0xDEAD; syscall`.")
        print("  -> The setup writes the constant but the syscall is elsewhere (register spilled,")
        print("     stored to memory then reloaded, or a wider mov with an ROL/XOR obfuscation).")
        print("  -> [I] leaning against Candidate A. Take a later pre-kill snapshot before ruling it out.")
    else:
        print("MISS: no 0xDEAD-shaped bytes found in the scanned regions.")
        print("  -> Candidate A refuted for THIS pre-kill snapshot timing.")
        print("  -> Two possibilities remain:")
        print("     (a) the JIT allocation happens later than we snapshotted (retry with a later cut)")
        print("     (b) the kill mechanism is not a JIT stub - proceed to Move I-4 (DR poll).")

if __name__ == "__main__":
    main()
