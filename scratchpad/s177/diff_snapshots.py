"""S177 Move I-3 (step 1 of 2): Diff two dumpimage snapshots.

Purpose
-------
Compare a MENU-BASELINE dumpimage snapshot against a PRE-KILL dumpimage snapshot
and print exactly what is NEW in pre-kill. Any newly-present executable region
(especially MEM_PRIVATE|PAGE_EXECUTE_READWRITE or a new hidden MEM_IMAGE mapping)
is a candidate for a JIT-generated kill stub.

Discriminator (per docs/next-session-prompt-s177.md):
  - New MEM_PRIVATE RWX region containing `mov edx, 0xDEAD; syscall`
      -> Candidate A (JIT stub) CONFIRMED
  - New MEM_PRIVATE RWX region WITHOUT the pattern
      -> pre-kill allocations exist but do not host the primitive; try Move I-4
  - No new regions at all
      -> JIT hypothesis refuted; try Move I-4 (DRs cleared) or ETW (kernel-side)

Input format
------------
Each snapshot directory must contain the standard dumpimage output
`<STEM>.dump.txt` with the manifest block:

    Executable region inventory (private-extern = candidate unpacked code):
    VA                 SIZE         PROT   TYPE     DUMPED
    0xFF760000         0x7000       0x2    Image    <filename>|(skip: ...)
    ...

Usage
-----
  python diff_snapshots.py <baseline_dir> <prekill_dir>

The result is written to stdout AND to `<prekill_dir>/../s177_diff.txt` (with
the current PID/base header lifted from the pre-kill manifest so we can tell
snapshots apart later).

Design notes
------------
- Parses ONLY the exec-region inventory (the block after the "VA SIZE PROT
  TYPE DUMPED" header). Everything else in the manifest (section table, data
  directories, coverage %) is ignored by design — it's parsable but not
  diff-relevant for this move.
- Regions are matched by *exact VA*. Under ASLR neither the game exe nor the
  protector's hidden runtime.dll mapping is guaranteed to sit at the same VA
  across launches, so this script is only meaningful when comparing snapshots
  from THE SAME PROCESS LIFETIME. That is the S177 recipe (baseline at menu
  -> stage -> pre-kill in one uptime).
- Prints "changed size" separately from "new region" — a region that grew is a
  weaker signal than a brand-new allocation but still worth flagging.

Blind spots (banked, S177):
- A snapshot taken >20 s before the kill window may miss the JIT allocation if
  the protector allocates it immediately before firing. Take the pre-kill
  snapshot AT LEAST ~20 s AFTER the reinject that historically produces FK-32
  (Move F fired at ~t+146s post-reinject; earlier flights at t+35s). Err on
  the side of a late snapshot; if kill happens during dumpimage the file is
  still usable up to the kill point.
- A "skip: Image - other module" line is a real loaded DLL, and the diff
  intentionally IGNORES its filename (which is empty). We diff by VA+SIZE only.
- The manifest also lists regions dumpimage skipped for being >169 MB. Those
  are the raw whole-image SEC_IMAGE view from S131 - not a JIT stub candidate.
"""
from __future__ import annotations
import os, re, sys, argparse
from dataclasses import dataclass

# Values from Windows Memory Basic Info Protect field. Kept as a small map for
# the human-readable column in the diff report — matched against the manifest's
# raw hex, so any protector fiction like PAGE_TARGETS_INVALID (0x40000000) will
# still print, just without a symbolic name.
PROT_NAMES = {
    0x01: "NOACCESS",
    0x02: "READONLY",
    0x04: "READWRITE",
    0x08: "WRITECOPY",
    0x10: "EXECUTE",
    0x20: "EXECUTE_READ",
    0x40: "EXECUTE_READWRITE",
    0x80: "EXECUTE_WRITECOPY",
}

# The inventory line format is fixed by dumpimage.go. Two columns of interest:
#   0xVA           0xSIZE        0xPROT   TYPE    DUMPED-or-(skip: reason)
# TYPE is one of {Image, Private, Mapped} (dumpimage only ever emits these three).
LINE_RE = re.compile(
    r"^\s*(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)\s+(\S+)\s+(.*)$"
)

@dataclass(frozen=True)
class Region:
    va: int
    size: int
    prot: int
    type_: str      # 'Image' | 'Private' | 'Mapped'
    dumped: str     # filename or "(skip: ...)" text

    @property
    def is_rwx(self) -> bool:
        # PAGE_EXECUTE_READWRITE (0x40) is the classic JIT-stub protection.
        # PAGE_EXECUTE_WRITECOPY (0x80) is the initial state of a SEC_IMAGE
        # writable-executable page - also worth flagging.
        return self.prot in (0x40, 0x80)

    @property
    def is_private_exec(self) -> bool:
        # Any executable Private region is inherently interesting - MEM_IMAGE
        # regions are backed by files (even the hidden protector runtime.dll)
        # while MEM_PRIVATE|PAGE_EXECUTE_* is only produced by VirtualAlloc.
        return self.type_ == "Private" and (self.prot & 0xF0) != 0

    @property
    def is_hidden_image(self) -> bool:
        # Manifest filenames with the `_hidden` suffix are the S164 flag's
        # output: MEM_IMAGE regions whose base is not in the loaded module
        # list, i.e. manually mapped. The protector's runtime.dll is these.
        return "_hidden" in self.dumped

    def key(self) -> int:
        return self.va

    def as_row(self) -> str:
        prot_name = PROT_NAMES.get(self.prot, f"?0x{self.prot:X}")
        return (
            f"  VA=0x{self.va:<12X} "
            f"SIZE=0x{self.size:<10X} "
            f"PROT=0x{self.prot:02X} ({prot_name:<18}) "
            f"TYPE={self.type_:<8} "
            f"{self.dumped}"
        )


def parse_manifest(path: str) -> tuple[dict, list[Region]]:
    """Parse the header + the exec-region inventory block.

    Returns (header_dict, regions). header_dict has 'base', 'pid', 'generated'
    when present in the manifest; regions is a list in file order (which is
    address-sorted by dumpimage).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"manifest missing: {path}")
    header: dict = {"path": path}
    regions: list[Region] = []
    in_inventory = False
    with open(path, "r", encoding="utf-8", errors="replace") as fp:
        for raw in fp:
            line = raw.rstrip("\n")
            # Header — grab a few fields for later reporting.
            if not in_inventory:
                if line.startswith("generated"):
                    header["generated"] = line.split(":", 1)[1].strip()
                elif line.startswith("module"):
                    header["module"] = line.split(":", 1)[1].strip()
                elif line.startswith("base"):
                    header["base"] = line.split(":", 1)[1].strip()
                if line.startswith("Executable region inventory"):
                    in_inventory = True
                    continue
                continue
            # In-inventory: skip the header row, blank lines, or any trailing
            # text after the block (the manifest ends after regions on this
            # build so we just eat what we can and don't try to detect end-of-
            # block explicitly).
            if line.startswith("VA") or not line.strip():
                continue
            m = LINE_RE.match(line)
            if not m:
                # Anything that doesn't match the row format ends the block.
                # This is defensive: dumpimage today writes regions until EOF,
                # but future dumpimage changes might add sections below.
                break
            va_s, size_s, prot_s, type_, dumped = m.groups()
            regions.append(Region(
                va=int(va_s, 16),
                size=int(size_s, 16),
                prot=int(prot_s, 16),
                type_=type_,
                dumped=dumped.strip(),
            ))
    return header, regions


def find_manifest(dirpath: str) -> str:
    """Locate the single `*.dump.txt` manifest inside `dirpath`.

    We do NOT assume the SUPERVIVE-Win64-Shipping stem — future runs might
    dump other processes into their own subdirs.
    """
    if not os.path.isdir(dirpath):
        raise FileNotFoundError(f"snapshot dir missing: {dirpath}")
    hits = [f for f in os.listdir(dirpath) if f.endswith(".dump.txt")]
    if not hits:
        raise FileNotFoundError(
            f"no *.dump.txt manifest in {dirpath} "
            "(did dumpimage complete? check baseline vs pre-kill dir arg order)"
        )
    if len(hits) > 1:
        # A snapshot dir with 2 manifests means multiple modules were dumped
        # into the same dir - refuse rather than pick one silently.
        raise RuntimeError(
            f"multiple manifests in {dirpath}: {hits}. "
            "Give each dumpimage its own output dir."
        )
    return os.path.join(dirpath, hits[0])


def diff(baseline_dir: str, prekill_dir: str) -> int:
    base_manifest = find_manifest(baseline_dir)
    pre_manifest  = find_manifest(prekill_dir)
    bh, bregs = parse_manifest(base_manifest)
    ph, pregs = parse_manifest(pre_manifest)

    print("=" * 78)
    print("S177 Move I-3 — snapshot diff (menu baseline vs pre-kill)")
    print("=" * 78)
    print(f"BASELINE : {base_manifest}")
    print(f"           generated={bh.get('generated','?')}  base={bh.get('base','?')}  regions={len(bregs)}")
    print(f"PRE-KILL : {pre_manifest}")
    print(f"           generated={ph.get('generated','?')}  base={ph.get('base','?')}  regions={len(pregs)}")
    print()

    # Fast identity check - if bases differ, the two snapshots are from
    # DIFFERENT PROCESS LIFETIMES and the diff is nearly meaningless (ASLR
    # rebase makes every VA look "new"). Warn loudly but do not refuse - a
    # human might genuinely want the raw output.
    if bh.get("base") and ph.get("base") and bh["base"] != ph["base"]:
        print("!" * 78)
        print("!! WARNING: BASELINE and PRE-KILL have DIFFERENT process bases.")
        print("!! This diff is only reliable within one process lifetime (ASLR).")
        print(f"!!   baseline base = {bh['base']}")
        print(f"!!   pre-kill base = {ph['base']}")
        print("!! Every VA will appear 'new'. Proceed with skepticism.")
        print("!" * 78)
        print()

    base_by_va = {r.va: r for r in bregs}
    pre_by_va  = {r.va: r for r in pregs}
    new_vas       = sorted(pre_by_va.keys() - base_by_va.keys())
    dropped_vas   = sorted(base_by_va.keys() - pre_by_va.keys())
    changed       = []  # (baseline_region, prekill_region)
    for va in sorted(pre_by_va.keys() & base_by_va.keys()):
        b, p = base_by_va[va], pre_by_va[va]
        if b.size != p.size or b.prot != p.prot or b.type_ != p.type_:
            changed.append((b, p))

    # Emit sections, most-suspicious first. Every candidate JIT stub lands in
    # one of the first two sections; everything else is corroborating context.
    def emit(title: str, rows: list[str]) -> None:
        print(f"--- {title} ({len(rows)}) ---")
        for r in rows:
            print(r)
        if not rows:
            print("  (none)")
        print()

    # RANK 1 — new MEM_PRIVATE|PAGE_EXECUTE_READWRITE regions. These are the
    # exact signature of `VirtualAlloc(NULL, sz, MEM_COMMIT, PAGE_EXECUTE_READWRITE)`
    # followed by a byte write into the page, i.e. a JIT stub.
    new_regions = [pre_by_va[v] for v in new_vas]
    priv_rwx = [r for r in new_regions if r.is_private_exec and r.is_rwx]
    priv_x   = [r for r in new_regions if r.is_private_exec and not r.is_rwx]
    hidden_i = [r for r in new_regions if r.is_hidden_image and not r.is_private_exec]
    other    = [r for r in new_regions if r not in priv_rwx and r not in priv_x and r not in hidden_i]

    emit("NEW MEM_PRIVATE + PAGE_EXECUTE_READWRITE/_WRITECOPY (RANK 1 CANDIDATES)",
         [r.as_row() for r in priv_rwx])
    emit("NEW MEM_PRIVATE + PAGE_EXECUTE_READ/_EXECUTE (rank 2 - rare, worth flagging)",
         [r.as_row() for r in priv_x])
    emit("NEW MEM_IMAGE hidden mappings (Move M-class - the protector's own DLL family)",
         [r.as_row() for r in hidden_i])
    emit("NEW OTHER (loaded 3rd-party DLLs etc. - almost never the answer)",
         [r.as_row() for r in other])
    emit("DROPPED regions (present in baseline, absent in pre-kill)",
         [f"  VA=0x{v:X}  {base_by_va[v].dumped}" for v in dropped_vas])
    emit("CHANGED regions (same VA, different size/prot/type)",
         [f"  VA=0x{b.va:X}: "
          f"size 0x{b.size:X} -> 0x{p.size:X}, "
          f"prot 0x{b.prot:X} -> 0x{p.prot:X}, "
          f"type {b.type_} -> {p.type_}"
          for (b, p) in changed])

    # Return the RANK 1 candidate list to the caller as a filename list so the
    # scanner can operate directly on those regions.
    rank1_files = [r.dumped for r in priv_rwx if r.dumped and not r.dumped.startswith("(")]
    rank2_files = [r.dumped for r in priv_x   if r.dumped and not r.dumped.startswith("(")]
    hidden_files = [r.dumped for r in hidden_i if r.dumped and not r.dumped.startswith("(")]

    print("=" * 78)
    print("NEXT STEP")
    print("=" * 78)
    if not priv_rwx and not priv_x and not hidden_i:
        print("No new executable regions at all - Candidate A (JIT stub) is REFUTED.")
        print("Proceed to Move I-4 (DR poll) to test Candidate C (DRs cleared).")
    else:
        print("Scan the new region dumps for 0xDEAD-producing patterns:")
        print()
        target_list = rank1_files + rank2_files + hidden_files
        print(f"  python scratchpad/s177/scan_new_regions.py {prekill_dir} \\")
        for i, f in enumerate(target_list):
            comma = " \\" if i < len(target_list) - 1 else ""
            print(f"      {f}{comma}")
        print()
        print("Or omit the filename list to scan every NEW file the diff surfaced:")
        print()
        print(f"  python scratchpad/s177/scan_new_regions.py {prekill_dir} --auto {baseline_dir}")

    # Also write the report so it survives shell scrollback.
    out_path = os.path.join(os.path.dirname(os.path.abspath(prekill_dir)),
                            "s177_diff.txt")
    try:
        # Re-run the whole print into a file - cheap and keeps the two paths
        # (stdout, file) identical without threading an output stream through.
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            diff._reentry = True  # sentinel - not used; guard against infinite recursion below
        # We already streamed to stdout; just serialise our known state.
        with open(out_path, "w", encoding="utf-8") as fp:
            fp.write(f"# s177_diff.txt written {ph.get('generated','?')}\n")
            fp.write(f"# baseline={base_manifest}\n# prekill={pre_manifest}\n\n")
            fp.write(f"NEW_RANK1_PRIV_RWX ({len(priv_rwx)}):\n")
            for r in priv_rwx: fp.write(r.as_row() + "\n")
            fp.write(f"\nNEW_PRIV_EXEC ({len(priv_x)}):\n")
            for r in priv_x: fp.write(r.as_row() + "\n")
            fp.write(f"\nNEW_HIDDEN_IMAGE ({len(hidden_i)}):\n")
            for r in hidden_i: fp.write(r.as_row() + "\n")
            fp.write(f"\nNEW_OTHER ({len(other)}):\n")
            for r in other: fp.write(r.as_row() + "\n")
            fp.write(f"\nDROPPED ({len(dropped_vas)}):\n")
            for v in dropped_vas:
                fp.write(f"  VA=0x{v:X}  {base_by_va[v].dumped}\n")
            fp.write(f"\nCHANGED ({len(changed)}):\n")
            for b, p in changed:
                fp.write(
                    f"  VA=0x{b.va:X}: size 0x{b.size:X}->0x{p.size:X}, "
                    f"prot 0x{b.prot:X}->0x{p.prot:X}, "
                    f"type {b.type_}->{p.type_}\n"
                )
        print()
        print(f"[diff] report also written to {out_path}")
    except OSError as e:
        # Don't fail the diff if we can't write the report - stdout is authoritative.
        print(f"[diff] WARN: could not write report file: {e}")

    # Exit code: 0 always, so callers can chain shell commands. The
    # discriminator lives in the "NEXT STEP" section, not the exit code.
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Diff two dumpimage snapshots (menu baseline vs pre-kill).",
    )
    ap.add_argument("baseline_dir", help="directory holding the MENU baseline snapshot")
    ap.add_argument("prekill_dir",  help="directory holding the PRE-KILL snapshot")
    args = ap.parse_args()
    sys.exit(diff(args.baseline_dir, args.prekill_dir))


if __name__ == "__main__":
    main()
