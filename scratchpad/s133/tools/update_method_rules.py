#!/usr/bin/env python3
"""S133: update S133-d with the full verifier tally and add S133-f."""
import io

P = 'docs/method-rules.md'
s = io.open(P, encoding='utf-8').read()

OLD = """corrected in both files within the hour, and the crashwatch grade downgraded [M]→[I] in the same pass."""
NEW = """corrected in both files within the hour, and the crashwatch grade downgraded [M]→[I] in the same pass. ⚠⚠ **AND THE FINAL THREE VERIFIERS, WHICH LANDED AFTER I HAD ALREADY WRITTEN THE SUMMARY, CAUGHT SEVEN MORE — so the true cost of not waiting was ten corrections, not three.** In `docs/fk20-coverage-settled.md` and `CLAUDE.md` alike: *"73.4 % of the dark set (9,984 pages, 39.0 MiB) is unreachable"* was **arithmetic** (`3613+2357+1845+1416 = 9231 = 67.91 % = 36.06 MiB`, and the two complementary shares as stated summed to **105.54 %**); *"Region A is not UE code at all"* is **[M] false** (it is UE's own Chaos ISPC kernels — `ispc` ×16 ASCII in merged6, naming `PerParticlePBDCollisionConstraint.ispc`); *"96.3 MB of protector code"* **double-counted two `SEC_IMAGE` views of one 67,511,496-byte file** (real: 48,136,192 B, views differ by 57,344 B); *"48,136,192 matches FK-10's 46.6 MB"* matches in **neither unit**; *"NEW: runtime.dll is mapped twice"* and *"a third hidden mapping nobody knew about"* are **both in `docs/s109-dump-forensics.md` §5 since 2026-08-04**; the era table printed 9/1/5/9 = **24 ≠ 26**; and `125 distinct crashes` is **124**. **Every one of the ten flattered or inflated the finding; none made it worse.** ★ *That asymmetry is the tell — an unverified lane's errors are not random noise, they drift toward the conclusion the lane was hired to reach.*"""
assert OLD in s
s = s.replace(OLD, NEW)

# --- new row S133-f, inserted after S133-e
anchor = '| **★★★ S133-e** |'
i = s.index(anchor)
j = s.index('\n', i)
row = """| **★★★★ S133-f** | **a partition table whose parts were never summed** | six mutually exclusive buckets (U1, R0, U2, U3, R1, R2, R3) covering all 13,592 dark pages, published with two derived headline shares — *"73.4 % unreachable"* and *"32 % reachable"* | **105.54 %.** The unreachable share was overstated by **753 pages / 5.54 pp / 2.94 MiB**, and it was carried into `CLAUDE.md`, a settled doc and a session summary before anyone added two numbers | `3613+2357+1845+1416 = 9231` (**67.91 %**) and `1397+1091+1873 = 4361` (**32.09 %**); `9231 + 4361 = 13592` **exactly**, so the partition itself was sound and only the headline was wrong. ★★ **Rule: whenever you publish a share of a whole, publish or at least CHECK its complement. Two complementary percentages that do not sum to 100 % is a free, instant, arithmetic-only self-check** — it needs no instrument, no control and no second opinion, and it would have caught this before the number left the paragraph it was computed in. ⚠ This sits one row below S133-d for a reason: the error survived *because* the lane that made it was propagated before its verifier landed |
"""
s = s[:j + 1] + row + s[j + 1:]

io.open(P, 'w', encoding='utf-8').write(s)
print('method-rules updated')
