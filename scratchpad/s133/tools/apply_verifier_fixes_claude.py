#!/usr/bin/env python3
"""S133: propagate the adversarial verifiers' corrections into CLAUDE.md."""
import io

P = 'CLAUDE.md'
s = io.open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, 'NOT FOUND: ' + a[:80]
    s = s.replace(a, b)


# --- 1. the arithmetic error + Region A identification
rep(
"""- ★★★★★ **73.4 % OF THE DARK SET IS UNREACHABLE BY ANY GAME STATE** (9,984 of 13,592 pages,
  39.0 MiB): vectorised SIMD/ISPC kernels the CPU will never select (26.6 % of dark, but only **0.4 %
  of dark FUNCTIONS** — quote the unit), editor/authoring modules with no entry point in a packaged
  client (PCG, MeshModelingTools, Sequencer, MovieRenderPipeline), and third-party libs (ICU 64,
  OpenEXR, OpenSSL, Oodle, libwebm, crashpad). **The reachable ceiling is ≈ 4,361 pages ≈ 32 % of
  dark**, and that assumes a match runs every line of every gameplay module.""",
"""- ★★★★★ **67.91 % OF THE DARK SET IS UNREACHABLE BY ANY GAME STATE** (9,231 of 13,592 pages,
  36.06 MiB): **UE's own Chaos ISPC-compiled collision kernels**, multi-ISA-target so ~2/3 is
  unreachable *on this CPU by construction* (26.6 % of dark, but only **0.4 % of dark FUNCTIONS** —
  quote the unit); editor/authoring modules with no entry point in a packaged client (PCG,
  MeshModelingTools, Sequencer, MovieRenderPipeline); and third-party libs (ICU 64, OpenEXR, OpenSSL,
  Oodle, libwebm, crashpad). **The reachable ceiling is 4,361 pages = 32.09 % of dark = 17.04 MiB**,
  and that assumes a match runs every line of every gameplay module.
  ⚠⚠ **A first draft of this line said "73.4 %, 9,984 pages, 39.0 MiB" — ARITHMETIC ERROR, and it
  flattered the conclusion.** `3613+2357+1845+1416 = 9231`; the two complementary shares as first
  stated summed to **105.54 %**. `9231 + 4361 = 13592` exactly. ★ **Two shares of one whole that do
  not sum to 100 % is a free self-check — run it before publishing either.**
  ★★ **"Region A" (`0x1000`–`0xB89000`) is NAMED [M], and calling it "not UE code" was false**:
  `ispc` occurs **16× ASCII** in `merged6`, in four copies of a block reading
  `Runtime/Experimental/Chaos/Private/Chaos/PerParticlePBDCollisionConstraint.ispc` (verified at
  `0x78087B9`). ⚠ The "no ISPC string exists" null came from `strxref.idx`, built on ONE image
  (`s129-poolgate`) that lights only **50 of Region A's 144** lit pages — **a string index built on
  one image is a floor.**""")

# --- 2. the 55.27% unit qualifier
rep(
"""  exactly). Union over all crashes **16,434 (54.27 %)**; combined with `merged6` **16,735 = 55.27 %**;
  only **41** pages were ever decrypted at a crash and are zero in `merged6`.""",
"""  exactly). Union over all crashes **16,434 (54.27 %)**; combined with `merged6` **16,735 = 55.27 %**;
  only **41** pages were ever decrypted at a crash and are zero in `merged6`.
  ⚠⚠ **QUOTE THE UNIT: 55.27 % is "pages KNOWN TO HAVE BEEN DECRYPTED at some moment", NOT "pages we
  hold BYTES for".** Those 41 pages exist nowhere as bytes — minidump memory inside the game image is
  **0 in 124/124**. **For offline RE the byte figure is `merged6`'s 16,694 = 55.13 %.**""")

# --- 3. protector byte double-count + "NEW" claims + era table
rep(
"""  `0x7FF90E000000` (9 dumps) · `0x7FFD3B400000` (1) · `0x7FFA42600000` (5) · `0x7FFB57400000` (9) —
  **the last three are exactly S131's three constant kill addresses minus 1**, plus a **FOURTH era base
  S131's minidump-only corpus could not see**. ★★ **`runtime.dll` is mapped TWICE and the LOW base is
  INVARIANT at `0xFF760000`** (26/26 manifests, 390/394 minidumps); the HIGH copy alone shows split
  `READWRITE`/`WRITECOPY` ⇒ [I, strong] HIGH is the executing view, consistent with the kill jumping to
  HIGH+1. ⚠ **[M] 96.3 MB of protector code sat readable under RPM in every capture and none was
  written.**""",
"""  `0x7FF90E000000` (9 dumps) · `0x7FFD3B400000` (1) · `0x7FFA42600000` (6) · `0x7FFB57400000` (10),
  summing to 26 — **the last three are exactly S131's three constant kill addresses minus 1**, plus a
  **FOURTH era base S131's minidump-only corpus could not see**. ★★ **`runtime.dll` is mapped TWICE and
  the LOW base is INVARIANT at `0xFF760000`** (26/26 manifests, 123/124 distinct crashes); the HIGH copy
  alone shows split `READWRITE`/`WRITECOPY` ⇒ [I, strong] HIGH is the executing view, consistent with the
  kill jumping to HIGH+1. ⚠⚠ **THE DOUBLE MAPPING AND THE SHADOW-EXE MAPPING BELOW ARE *NOT* NEW —
  `docs/s109-dump-forensics.md` §5 (2026-08-04/05) already tabulates all three hidden images**, with the
  same LOW/HIGH `EXECUTE_WRITECOPY` vs `EXECUTE_READ` distinction, re-verified at
  `docs/s109-skeptic-review.md:60-70` against UE's own `<CallStack>`. **What is new is only that the
  `dumpimage` MANIFESTS carry it too, 52 times, each marked skipped.** ★ *Grep before writing "NEW".*
  ⚠ **[M] 48,136,192 B (45.90 MiB) of protector executable content sat readable under RPM in every
  capture and none was written.** A draft said **96.3 MB** by summing both mappings — that
  **double-counts two `SEC_IMAGE` views of the same 67,511,496-byte file** (observed differentiation
  between views: **57,344 B**).""")

# --- 4. shadow exe count
rep(
"""  there is exactly one `MEM_IMAGE` allocation of `0xA9E1000` — **the game's own `SizeOfImage`** —
  `READONLY`, a **single** region with no per-section protections, at a heap address, 125 distinct
  bases. **0 bytes ever captured.**""",
"""  there is exactly one `MEM_IMAGE` allocation of `0xA9E1000` — **the game's own `SizeOfImage`** —
  `READONLY`, a **single** region with no per-section protections, at a heap address, **124** distinct
  bases. **0 bytes ever captured.** ⚠ Also recorded in `docs/s109-dump-forensics.md` §5 and never acted
  on — the lottery ticket has been on the table since 2026-08-04.""")

# --- 5. FK-31 census field/date corrections
rep(
"""and missed ~329 files / 84 reports dated 2026-08-04 → 08-07.**""",
"""and missed **310 files / 83 reports** dated 2026-08-04 → 08-07.** ⚠ "329" is `342 − 13` — *files S131
did not see* — relabelled as a date range; and era-1 files dated 08-08/08-09 number **32**, so 13 is
not "all of 08-08/09" either.""")

rep(
"""of which **14 are `addr & 0xFFFF == 0x205d`** — `catalog_store_fix.dll`'s own heap scan""",
"""of which **14 are `RIP & 0xFFFF == 0x205d`** (⚠ **`RIP`, not the faulting address** — the faulting
addresses are 16 distinct values and `0x205d` appears among them zero times; this file's own rule is
*"classify each death by `RIP & 0xFFFF`"*) — `catalog_store_fix.dll`'s own heap scan""")

io.open(P, 'w', encoding='utf-8').write(s)
print('CLAUDE.md: all verifier corrections applied')
