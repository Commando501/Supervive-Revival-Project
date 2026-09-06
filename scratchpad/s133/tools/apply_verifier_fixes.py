#!/usr/bin/env python3
"""S133: apply the adversarial verifiers' corrections to docs/fk20-coverage-settled.md.
Written to a FILE rather than a heredoc, per method rule S132-e."""
import io

P = 'docs/fk20-coverage-settled.md'
s = io.open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, 'NOT FOUND: ' + a[:80]
    s = s.replace(a, b)


rep(
"""★★★★★ **73.4 % of the dark set (9,984 of 13,592 pages = 39.0 MiB) is U1+R0+U3+R1: SIMD ISA
variants the CPU will never select, editor modules with no entry point in a packaged client, and
third-party libraries. NO game state decrypts any of it — not hero select, not a live match, not
end-of-game.** The reachable ceiling is R2 plus a share of R3/U2, **≈ 4,361 pages ≈ 32 % of dark
≈ 17.0 MiB**, and that assumes a match executes *every line* of every gameplay/net/AI module.""",
"""★★★★★ **67.91 % of the dark set (9,231 of 13,592 pages = 36.06 MiB) is U1+R0+U3+R1: SIMD ISA
variants the CPU will never select, editor modules with no entry point in a packaged client, and
third-party libraries. NO game state decrypts any of it — not hero select, not a live match, not
end-of-game.** The reachable ceiling is R2 plus a share of R3/U2, **4,361 pages = 32.09 % of dark
= 17.04 MiB**, and that assumes a match executes *every line* of every gameplay/net/AI module.
⚠⚠ **An earlier draft said "73.4 %, 9,984 pages, 39.0 MiB" — an ARITHMETIC ERROR that flattered the
conclusion, caught by adversarial verification.** `3613+2357+1845+1416 = 9231`, and the two shares as
first stated summed to **105.54 %**, which is impossible. **9,231 + 4,361 = 13,592 exactly.**
★ *Two complementary shares that fail to sum to 100 % is a free self-check — run it.*""")

rep(
"""| **3,613** | 92.2 % | 26.6 % | **U1** `RVA<0xF7E000` — vectorised SIMD/ISPC kernels (**25 fns/MB** vs 6,126 next door), libpas, libpng, zlib, NVAPI |""",
"""| **3,613** | 92.2 % | 26.6 % | **U1** `RVA<0xF7E000` — **UE's own Chaos ISPC kernels** (**25 fns/MB** vs 6,126 next door), libpas, libpng, zlib, NVAPI |""")

rep(
"""**2c. The one concentrated, reachable target: the Angelscript AOT layer.**""",
"""★★ **U1 (\"Region A\", `0x1000`–`0xB89000`, 2,808 dark pages = 20.7 % of all dark) IS UE CODE, and it
is NAMED [M].** A draft called it *"not UE code at all"* with *"no ISPC-specific string found"*; both
are false from the same bytes. **`ispc` occurs 16× ASCII in `merged6`**, in four byte-identical copies
of one string block (`.rdata 0x7808790 / 0x7808A30 / 0x7808E60 / 0x7809190`) reading
`Runtime/Experimental/Chaos/Private/Chaos/PerParticlePBDCollisionConstraint.ispc:331:2: Assertion
failed:` — verified here at `0x78087B9` — and Region A's own lit code `lea`s to them. ⇒ **it is
Chaos's ISPC-compiled collision kernels, multi-ISA-target, of which the runtime selects one copy**;
the rest is unreachable *on this CPU by construction*, not by game state. Grade **[M]**, not [I].
⚠ The false null came from `strxref.idx`, which was built on `dumps/s129-poolgate` — an image that
lights only **50 of Region A's 144** lit pages, with all five ISPC-referencing sites among the dark
ones. **A string index built on ONE image is a floor, and "verified exhaustively" against it is not.**

**2c. The one concentrated, reachable target: the Angelscript AOT layer.**""")

rep(
"""| era | HIGH base | dumps | LOW base |
|---|---|---:|---|
| Jul (accountpass, loadout, menu, missions, rcb, roster, store, toggles, vmbuild) | `0x7FF90E000000` | 9 | `0xFF760000` |
| Aug 04–09 (tutorial-hero) | `0x7FFD3B400000` | 1 | `0xFF760000` |
| Aug 13–16 (claimflow, heromastery, lobby-dispatch, crash-20260815-*) | `0x7FFA42600000` | 5 | `0xFF760000` |
| Aug 19–20 (s129/s131/s132, crash-2026081920-*) | `0x7FFB57400000` | 9 | `0xFF760000` |""",
"""| era | HIGH base | dumps | LOW base |
|---|---|---:|---|
| Jul (accountpass, loadout, menu, missions, rcb, roster, store, toggles, vmbuild) | `0x7FF90E000000` | 9 | `0xFF760000` |
| Aug 04–09 (tutorial-hero) | `0x7FFD3B400000` | 1 | `0xFF760000` |
| Aug 13–16 (claimflow ×2, heromastery, lobby-dispatch, crash-20260815-* ×2) | `0x7FFA42600000` | 6 | `0xFF760000` |
| Aug 19–20 (s129/s131/s132 ×5, crash-2026081920-* ×5) | `0x7FFB57400000` | 10 | `0xFF760000` |

(9 + 1 + 6 + 10 = **26**. ⚠ A draft printed 9/1/5/9 = 24 ≠ 26 — **a table that partitions a corpus
must sum to it; check it.**)""")

rep(
"""★★ **NEW: `runtime.dll` is mapped TWICE, and the LOW base is INVARIANT — `0xFF760000` in 26/26
manifests and 390/394 minidumps (123/125 distinct crashes).**""",
"""★★ **`runtime.dll` is mapped TWICE and the LOW base is INVARIANT — `0xFF760000` in 26/26 manifests
and 123/124 distinct crashes.** ⚠⚠ **NOT NEW — a draft called this and the shadow-exe mapping below
"never recorded anywhere in this project", and both are in `docs/s109-dump-forensics.md` §5
(2026-08-04/05)**, which already tabulates all three hidden images with the same LOW/HIGH
`EXECUTE_WRITECOPY` vs `EXECUTE_READ` distinction, and `docs/s109-skeptic-review.md:60-70`
re-verified it against UE's own `<CallStack>`. **What IS new is only that the `dumpimage` MANIFESTS
carry it too, 52 times, each marked skipped.** ★ *Grep the repo before writing "NEW".*""")

rep(
"""`SizeOfImage 0x4066000` matches S131 exactly, and 48,136,192 exec bytes matches FK-10's
*"46.6 MB of plaintext x86-64"*.""",
"""`SizeOfImage 0x4066000` matches S131 exactly and matches `runtime.dll` on disk (67,511,496 B,
`ImageBase 0x200000000`, 11 sections). ⚠ Executable content is **48,136,192 B = 45.90 MiB**; a draft
said this "matches FK-10's 46.6 MB" — **it does not match in either unit** (FK-10's 46.6 MB is its
own approximate figure). Do not manufacture agreement across units.""")

rep(
"""⚠ **[M] 96.3 MB of protector code (2 × 48,136,192 B) sat readable under `ReadProcessMemory` in every
capture this project ever took, and `dumpimage` wrote none of it.**""",
"""⚠ **[M] 48,136,192 B (45.90 MiB) of protector executable content sat readable under
`ReadProcessMemory` in every capture this project ever took, and `dumpimage` wrote none of it.**
⚠⚠ A draft said **96.3 MB** by summing both mappings — that **double-counts**: they are two
`SEC_IMAGE` views of the *same* 67,511,496-byte file, and the only observed differentiation between
the views is **57,344 B** (`.rwx` at `+0x7000` and `packer2` at `+0x93F000`). **Two views of one file
are one file's worth of bytes.**""")

rep(
"""★ **A THIRD hidden mapping nobody knew about, and it is a lottery ticket.** In **394/394** minidumps""",
"""★ **A third hidden mapping — recorded in `docs/s109-dump-forensics.md` §5 but never acted on, and it
is a lottery ticket.** In **all** minidumps""")

rep(
"""`READONLY`, a **single** region (no per-section protections), at a heap address, 125 distinct bases
(one per crash). **0 bytes of it were ever captured.**""",
"""`READONLY`, a **single** region (no per-section protections), at a heap address, **124** distinct
bases (one per crash). **0 bytes of it were ever captured.**""")

rep(
"""| **the two combined — the CEILING of everything ever observed** | **16,735** | **55.27 %** |""",
"""| **the two combined — the CEILING of everything ever observed** | **16,735** | **55.27 %** |

⚠⚠ **QUOTE THE UNIT ON 55.27 %: it is "pages KNOWN TO HAVE BEEN DECRYPTED at some moment", not
"pages we hold BYTES for".** The 41 crash-only pages exist **nowhere as bytes** — minidump memory
inside the game image is **0 in 124/124**, no report has a `Memory64ListStream`, and the shadow-exe
and `runtime.dll` allocations carry 0 captured bytes too. **For offline RE the byte figure is
`merged6`'s 16,694 = 55.13 %.**""")

s = s.replace('125 distinct crashes', '124 distinct crashes')
s = s.replace('(125 distinct crashes, 10.57 GiB)', '(124 distinct crashes, 10.57 GiB)')
s = s.replace('396 files / 125 crashes / 10.57 GiB', '396 files / 124 crashes / 10.57 GiB')

io.open(P, 'w', encoding='utf-8').write(s)
print('fk20 doc: all verifier corrections applied')
