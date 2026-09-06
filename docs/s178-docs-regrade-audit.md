# S178 A4 — Docs regrade audit (offline, `merged14` baseline)

**Session:** S178 · **Date:** 2026-09-05 · **Tool:** `scratchpad/s133/tools/regrade_blocked.py`
**Full output preserved at:** [scratchpad/s177/regrade_output.txt](../scratchpad/s177/regrade_output.txt) (191 lines, 61 stale-claim flags)

## Headline

**61 stale-claim flags across 21 files**, of which many are FALSE POSITIVES (the regex matches text inside historical/correction paragraphs). Actionable subset is smaller.

Ladder (comparison to prior audits):
- S133 (2026-08-20): 43 stale claim-instances (against `merged13`)
- S153 (2026-09-02): 58 stale (against `merged14`)
- S178 (2026-09-05): **61 stale** (against current `merged14` — 3 new since S153)

Growth is small — most decryption progress is already reflected. `merged15` (S158) would add more.

## Per-file breakdown (sorted by flag count)

| flags | file | note |
|--:|---|---|
| 12 | `docs/fk22-dropphase-reachability.md` | Highest offender. FK-22 predates S155/S157 companion-process finding by 25+ sessions. |
| 7 | `docs/fk-playability-audit-s134.md` | S134 baseline is old; many packer coverage lines outdated. |
| 6 | `docs/fk5-battle-gate-settled.md` | SUPERSEDED banner already present. Low-priority. |
| 5 | `docs/ignorance-map-s101.md` | Living index, updated frequently; flags likely already noted. |
| 4 | `docs/coverage-audit-s101.md` | Historical baseline doc; won't be touched. |
| 4 | `docs/method-rules.md` | Instrument-artifact register cites addresses that are now readable — those citations are HISTORICAL, not claims. Real false positives. |
| 3 | **`CLAUDE.md`** | **All 3 are FALSE POSITIVES** — the regex matches text inside S133 correction paragraphs that DISCUSS the staleness. |
| 3 | `docs/strxref-open-questions.md` | Old open-questions doc; low priority for update. |
| 2 | each of: `fk20-coverage-settled.md`, `fk3-fk4-settled.md`, `fk5-battle-practice-gate-s105.md`, `fk5-latency-subsystem-re.md` | Mixed; some real, some historical. |
| 1 | 9 misc. files | Most are historical/note-form. |

## What actually needs editing (adjudicated)

### High priority — active docs users read

None of the 61 flags are in ACTIVE handoff docs (`docs/next-session-prompt-*.md`) or currently-referenced settled docs beyond `fk22-dropphase-reachability.md`. The one meaningful priority is:

**`docs/fk22-dropphase-reachability.md`** — the 12 flags name pages that are now readable. Most claim "COVERAGE-BLOCKED" against pages the tool now reads. Since FK-22 is closed (drop chain works per S150-drop), these are historical annotations that could be preserved as "was COVERAGE-BLOCKED at S124, now readable in merged14."

### Medium priority — settled docs cited in current work

**`docs/fk-playability-audit-s134.md` (7 flags)** — was current until S143+. If a successor cites it, they might build on stale coverage claims. Worth an addendum block referencing merged14.

### Low priority / false positives

- **CLAUDE.md's 3 flags are all inside the S133 corrections paragraph** (lines 2938, 2961, 4306). The paragraph is EXPLAINING the staleness of the older claim — the regex sees both the old citation and the surrounding correction as one blob. **Do not edit.**
- **`docs/method-rules.md`** — the flagged citations are inside the instrument-artifact REGISTER entries (S130-c, S133-b etc). These entries are HISTORICAL RECORDS of what an instrument once said, not present-tense claims. **Do not edit.**
- **`docs/fk5-battle-gate-settled.md`** — already carries a SUPERSEDED banner. Its 6 flags are inside the pre-supersede body.

## New pattern found (deserves its own instrument-rule)

**S178-a: `regrade_blocked.py` matches on citation text regardless of whether the citation is in an ACTIVE claim or an EXPLICITLY-REFUTED historical quote.** Any claim of the form "X was previously said to be Y" — even inside a correction that starts "This is wrong because..." — still trips the tool. Adjudicate each hit by reading its surrounding paragraph; the flag alone is a floor, not a truth.

## Companion-process specific docs updates (from S177/S178 workflow synthesis)

Independent of `regrade_blocked.py`, S178 Tier-A's A2 analysis identifies additional docs updates that the tool does NOT catch (because they're about model correctness, not coverage):

### Priority 1: Correct S162 claim "13 CALL TARGETS behind one integrity check"

**Locations:**
- `CLAUDE.md` line ~2470 (S162 block)
- `docs/s162-seh-kill-dispatch-unified-settled.md`

**Correction:** the 16 SCOPE ranges route via **TWO dispatch families**: SHA-256 integrity (5 of 16 reach `runtime.dll` RVA `0x920C10`) and WinHTTP phone-home (7 of 16 call packer0 name-pointer table at `0x8148..0x8190`). Not one integrity check — two.

### Priority 2: Upgrade FK-10 Wall #7 SHA-256 hasher to [M]

**Locations:**
- `CLAUDE.md` FK-10 block
- `docs/fk10-protector-identified.md`

**Correction:** Wall #7 hasher at `runtime.dll` RVA `0x920C10` is now [M] linked to FK-32 dispatch (was [I]). 5 of 16 S162 kill-scope ranges reach it directly or via one hop. Cite `0x920C10` (body) with `0x920C00` as trampoline.

### Priority 3: Expand runtime.dll import summary

**Locations:**
- `CLAUDE.md` FK-10 block
- `docs/fk10-protector-identified.md`

**Add:** runtime.dll's KERNEL32 import list = only `CloseHandle`; total = 17 symbols across 6 DLLs. Zero process/handle-manipulation APIs. All process/syscall work is via 923 raw `0F 05` syscall sites with dynamic syscall-number computation (per S169 XOR-key mechanism).

### Priority 4: Preloader.dll entry-point mystery

**Locations:** CLAUDE.md, `docs/s177-fk32-mechanism-CONFIRMED-companion-process.md`

**New note:** preloader.dll `AddressOfEntryPoint` = RVA `0x3BD0` in `.rdata`, bytes `0F 0B C3` = `UD2; RET` — a decoy. Real mapper at RVA `0x1520` has **zero static E8/E9 callers**. Entry via non-standard dispatch (CFG hook via `LoadConfig` at RVA `0x3BE0` size `0x140`, or base-relocation-installed pointer). Both `preloader_link_func` (`0x24F0`) and the hash-named export (`0x3BB0`) are decoys too. **11 REAL functions** in preloader, biggest is `fn 0x1520..0x2322` (3.6KB) which walks PEB/LDR — this is the API resolution engine.

### Priority 5: Companion IPC — handle inheritance is REFUTED

**Locations:** `docs/s177-fk32-mechanism-CONFIRMED-companion-process.md` §What we still don't know

**Correction:** originally listed handle-inheritance as leading hypothesis. Now REFUTED [I_strong]: preloader.dll's ntdll import list contains ZERO of `DuplicateHandle`, `NtDuplicateObject`, `UpdateProcThreadAttribute`, `InitializeProcThreadAttributeList`. Preloader is architecturally incapable of setting up an inheritable handle. Combined with runtime.dll's **923 raw syscall sites + 40 `mov rcx, -1` (NtCurrentProcess) patterns**, dynamic `NtOpenProcess` from within runtime.dll is now leading hypothesis. Confirmation: live ETW `NtOpenProcess` on companion PID (Tier-B Move #1).

### Priority 6: Runtime.dll ships its own X.509 verification

**New note:** X.509 signing-algorithm OID `ecdsa-with-SHA256` present at `runtime.dll` packer0 file offset `0x382412`. Consistent with FK-10 BOM entry for mbedtls (bundled CA store as `.rsrc RT_RCDATA 10001`, 579,410 B DER). Runtime.dll's phone-home during its 4.1s life is TLS with pinned certs — explains the 2.34s silent phase in the ETW capture.

## Cost analysis

- Full docs-update pass (all 6 priorities): ~2-3 hours of editing, mostly mechanical
- Just P1+P2 (correct S162 misattribution + upgrade Wall #7 to [M]): ~30 minutes
- Priorities 3-6: adds addenda to existing docs, not rewrites

## Recommendation

Skip a full docs-update pass this session. Land the 6 priorities as ADDENDA in S178's synthesis doc (already done — [docs/s178-tier-a-synthesis.md](s178-tier-a-synthesis.md) §5 has them). Future sessions that cite S162, FK-10, or the companion doc will encounter the addenda naturally.

The `regrade_blocked.py` output is preserved at [scratchpad/s177/regrade_output.txt](../scratchpad/s177/regrade_output.txt) for anyone doing a docs-cleanup pass.
