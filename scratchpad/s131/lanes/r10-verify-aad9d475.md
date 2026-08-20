**Largely sound. 3 of 3 load-bearing claims CONFIRMED at byte level; 4 secondary claims REFUTED or over-graded; 2 items correctly left [I].** I re-derived everything below with my own PE parser and `.data` scanner — I did not import `rectab.py`.

---

## RE-DERIVED — the three load-bearing claims

**1. Record-table layout + the 7/7 control block — CONFIRMED [M]**

Independent method: locate the exact C-string in `.rdata`, index every `.data` qword equal to `ImageBase+name_rva`, read `+8` and `+0x10`. `dumps/s129-poolgate/SUPERVIVE-Win64-Shipping.dump.exe`, ImageBase `0x7ff7b86d0000`, `.text 0x1000+0x7649000`, `.rdata 0x764a000+0x237d000`, `.data 0x99c7000+0x6f0000` (so the report's `0x99c7000..0xa0b7000` is right).

| name | .rdata hits | valid records | impl read | expected |
|---|---|---|---|---|
| SpawnPlayer | 1 | 1 | `0xf7eb50` | `0xf7eb50` ✅ |
| AuthSetSpawnTeamLeader | 1 | 1 | `0xf7ec20` | ✅ |
| SetDropLeader | 1 | 1 | `0xf7ec20` | ✅ |
| OverridePlaneLocations | 1 | 1 | `0xf7ec20` | ✅ |
| GoToPhase | 1 | 1 | `0x5601020` | ✅ |
| BP_AuthSetCurrentPhase | 1 | 1 | `0x567a160` | ✅ |
| OnNewPhase | 1 | 1 | `0x330c56c` | ✅ |

Layout confirmed: `rec+0x08` name, `+0x10` thunk, `+0x18` impl, stride `0x48`. My own scan reproduces **16,277 records / 1,551 runs** (unit: records / runs) exactly, and the fold multiplicities exactly: `0xf7ec20`×371 (top-1), `0xf7eb60`×76 (top-2), `0x3234454`×48 (top-3, `48 8b 01 ff a0 c0 02 00 00` = vtable fwd, not a fold), `0xf7eb50`×40 (top-4), `0xb9e1f0`×15. Near-folds confirmed: `0xfc57d0`×15 = `33 c0 48 89 02 48 89 42`, `0xfc6cf0`×13 = `0f 57 c0 c3`.

**2. THE HEADLINE — all 11 dark-thunk keys resolve; 10 get a verdict — CONFIRMED [M], and stronger than the report claims**

Every one of the 11 reproduced exactly (record RVA / thunk / impl / bytes from s129):

```
AuthPlayerDetachPlayerFromRidable  rec 0x9c1e520 th 0x5456100 impl 0x55cccb0  4885d20f84ae010000488954
AuthPlayerEnterWorld               rec 0x9c1e568 th 0x54561d0 impl 0x55cce70  4885d20f848c060000555741
AuthPlayerEnterWorldAttachedToRid. rec 0x9c1e5b0 th 0x5456380 impl 0x55cd510  4885d20f847a02000048895c
AuthPlayerEnterWorldNew            rec 0x9c1e5f8 th 0x5456460 impl 0xf7ec20   c2 00 00  = ret 0
AuthPlayerPreSpawnOnAddToPlane     rec 0x9c1e640 th 0x5456540 impl 0x55cd800  4885d20f84e601000048895c
ContainsPlayer                     rec 0x9c1e760 th 0x5456700 impl 0x55d0270  488b81200100004863892801
GetLandingTeleportLocation         rec 0x9c1e7a8 th 0x5456c80 impl 0x55d89f0  40555356574157488dac2420
GetByTeamIndex                     rec 0x9c29d98 th 0x5483940 impl 0x56e6740  48895c2408574883ec208bfa
GetDropLeader                      rec 0x9c29de0 th 0x5483c00 impl 0x3259330  ALL-DARK  (page 0x3259000: 0/3)
GetFuzzyPlayerLocationComponent…   rec 0x9c29e28 th 0x5483db0 impl 0x56e7b90  48895c2408574883ec208bfa
SetDropPlane                       rec 0x9bdbd08 th 0x5352f20 impl 0x55e55e0  48895c240848897424104889 (merged2)
```

Thunk-page darkness re-measured, any-nonzero-byte test over the `0x1000` page: `0x5456000`, `0x5483000`, `0x5352000` all **False in all 3 images**. The attribution defect the report worries about **cannot touch this result**: each of the 11 names has exactly **1** `.rdata` occurrence and exactly **1** valid `.data` record image-wide, so no name-set-overlap heuristic is load-bearing here. That is a stronger defence than the report gives itself.

**3. Set-C reconstruction — CONFIRMED [M]**

Over `tools/re/out/uht_funcflags_tuthero.csv` (18,325 rows): `ALokiDropPlane 25 · ULokiPlayerDropPlaneComponent 34 · ULokiRideableComponent 18 · ALokiTeamState_TeamOnly 7 · ALokiDropPodBase 6 · ULokiGameModeDropPlaneComponent 4 · ULokiDropPhaseLibrary 4 · ULokiDropPhaseDebuggingTool 2 = **100**`. Exhaustive 8-subset enumeration over an 11-class drop universe yields **exactly 3** sets summing to 100, the two alternatives swapping `ULokiDropOnDeathComponent (4)` for `GameModeDropPlane (4)` or `DropPhaseLibrary (4)` — precisely as stated. Set C has **14** non-`Native` keys, all `BlueprintEvent`, matching §2.5's BPIE=14 with zero off-diagonal. `COVBLOCKED` appears in **1 of 185** `docs/*.md` files (unit: files) plus the s131 artifacts — the "table is not on disk" honesty claim holds. Residual-coverage claim also confirmed: **0** set-C keys are lit only in `s129`.

Also confirmed: vtable `0x8a22520 +0x4c0..+0x4e8` = `0x56face0, 0xf7ec20, 0x56f26a0, 0x56df250, 0xf7ec20, 0x56fae90` — in **all three** images, not two (report understates).

---

## REFUTED / defective

**A. `ServerLaunchDropPod → 0x56face0` graded REAL. `0x56face0`'s page is ALL-ZERO in all three images.** [M]
```
0x56face0  s129 lit=False  merged2 lit=False  tuthero lit=False   bytes 0000000000000000
0x56fae90  same, 0/3                                              (report lists it ungraded — fine)
```
By the report's own rule this is `IMPL-PAGE-DARK`; it appears as **REAL** in the §0 "eighth control" table and in the 6A `CORRECTED via vtable` cell. Correct verdict: **not a known fold, body unreadable ⇒ COVERAGE-BLOCKED**. Mitigation: the grade is inherited verbatim from `docs/fk22-dropphase-reachability.md:136`, so the defect is upstream — but the report re-published it as its own control without re-measuring coverage, which is the one thing this instrument exists to force. Verdict counts are unaffected (they key on the *record* impl `0x542b530`).

**B. "Confirms CLAUDE.md's S130 note by a fully independent route" — REFUTED.** `fk22:2751-2758` (S130, §25.7) already states `AuthPlayerEnterWorldAttachedToRidable = 0x55CD510`, `AuthPlayerPreSpawnOnAddToPlane = 0x55CD800`, and verbatim *"`AuthPlayerEnterWorldNew` is an empty fold"* — and the very next lines introduce **this same `.data` record table** as the "NEW GENERAL INSTRUMENT" and commission the re-run ("free and unstarted"). Same instrument, same artifacts ⇒ not independent, and `AuthPlayerEnterWorldNew` **is not a new finding**. What is genuinely new: the §2.5 tally correction 13→14, and the 8 impl addresses S130 never printed (`0x55cccb0`, `0x55d0270`, `0x55d89f0`, `0x56e6740`, `0x3259330`, `0x56e7b90`, `0x55e55e0`, and the thunk column).

**C. "Tools … re-runnable from repo root" — REFUTED for the main sweep.** I ran `scratchpad/s131/tools/lane4_sweep.py`: it prints `key count = 105`, because its `DROP_CLASSES` contains `ULokiRideableInterface` and **not** `ULokiDropPhaseDebuggingTool` (99 core, ≠100, ≠ set C), and it emits neither the `in_setC` nor the `thunk_pg`/`impl_pg` columns that `gen_md.py` consumes. `sweep_full.tsv` (112 rows × 11 cols) **cannot** have been produced by the committed script. The 7/7 control block *does* reproduce (`CONTROL HIT RATE: 7/7`, `records=16277 runs=1551 attributed_keys=15720`).

**D. Three of the "seven further undesigned agreements" agree with nothing published.** `AuthSetDropComplete 0x2e09510`, `GetDropPod 0x3078470`, `CanExit 0x525c240` occur in **0 files** across `docs/`, `CLAUDE.md`, `scratchpad/s130/` (unit: files); only `0x55cbb60`, `0x557eae0`, `0x56dd340`, `0x55e59e0` match a prior-published address. The doc records those three only as a *category* (`REAL-INLINED / CONST-BODY`). Their bytes do support the category — `c6 81 d0 00 00 00 01 c3`, `48 8b 81 10 01 00 00 c3`, `0f b6 81 18 01 00 00 c3` — but "reproduces addresses FK-22 derived by disassembly" is **4**, not 7.

**E. Prologue transcription elides five instructions with no ellipsis.** Report: *"`0x55cce70` opens `test rdx,rdx / je / push rbp / lea rbp,[rsp-0x170] / sub rsp,0x270`"*. Actual s129 bytes at `0x55cce70`:
`48 85 d2 | 0f 84 8c 06 00 00 | 55 | **57 | 41 54 | 41 55 | 41 56** | 48 8d ac 24 90 fe ff ff | 48 81 ec 70 02 00 00` — `push rdi; push r12; push r13; push r14` dropped. Displacements are right; the verdict is unaffected. This is the digest-compression pattern (S115-d family), not a wrong-address error.

**F. "Runs are per-UClass and alphabetically sorted within a class" — ~90 %, stated flatly.** [M] 895 of **997** runs of length ≥3 are strictly alphabetical (89.8 %). Not load-bearing (attribution is by name-set overlap, and the 11 headline keys are singletons), but it is an unqualified universal over a measured 9-in-10.

---

## Remaining ungrounded / correctly [I]

| item | status | what would settle it |
|---|---|---|
| Residual 2 keys in the reconciliation | **correctly [I]**, honestly flagged; arithmetic checks out (14+12+7+63+4 = 100) | The doc's actual 100-key list. Confirmed absent: no `scratchpad/s124*` exists and `COVBLOCKED` is in 1 of 185 `docs/*.md`. Only re-deriving §2.5's own key set from its generating agent artifacts closes it. |
| "11 matches the doc's COVBLOCKED-THUNK = 11 exactly" | **[I], not [M]** — the report's "old verdict" column is *reconstructed by its own rule* (`gen_md.py old()`: `thunk_pg=='DARK-ALL3' → COVBLOCKED-THUNK`) over a set that may differ by ~2 keys. Agreement of two independent censuses (doc 18-image vs report 3-image) is real but is corroboration, not identity. | Same as above. |
| 3 `Multicast*` on `ULokiRideableComponent` | **correctly labelled uninterpretable** — that class's vtable was not located | Locate `ULokiRideableComponent`'s vtable and read the three slots, as was done for `0x8a22520`. Offline, free. |
| `15,720/16,277 attributed` | tool-internal; I reproduced the totals but not the per-run attribution | Not load-bearing — the 11 headline keys are record-singletons. |
| Page `0x5456000` dark in **18** images | report verified 3, doc claims 18 — no unit dropped, correctly scoped | — |

**Net:** the instrument is real, the layout is right, the controls are non-degenerate and discriminate both ways, and the headline — 11 impl addresses recovered past a permanently dark thunk page, 10 with definite verdicts — survives byte-level re-derivation intact. The corrections are to framing (B, D), reproducibility (C), one inherited over-grade (A) and two transcription/universality slips (E, F).