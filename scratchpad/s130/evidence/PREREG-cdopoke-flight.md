# PRE-REGISTRATION — the C7 CDO poke + Route E dispatch (S130)

**Written BEFORE the marker was read.** Anything not in this file is a post-hoc reading and must be
labelled as one.

## Arms

| arm | build | `.text` sha256 | KPDCDOPOKE |
|---|---|---|---|
| treatment (FLOWN FIRST) | `tutorial_launch_droppod_pe_cdopoke.dll` | **`f6b16be64a9ef563`** | 1 |
| control (built, not yet flown) | `tutorial_launch_droppod_pe_cdoctrl.dll` | **`39133126f81a696e`** | 0 |

Both are 264,704 bytes with a **161,280-byte `.text` of identical size** — only the hash separates
them, which is the exact trap `CLAUDE.md` records. Both `verify_dll.py` PASS, KERNEL32-only imports.
Staging infrastructure is the deployed known-good pair, verified this run:
`fo fa184b20934cc4b0`, `sp 4285c0dd22ae9976` (matches the S130 handoff), `gft 6b2fe2c2a747c19f`.

## Why the treatment flies first

`PdCdoFlags` is called **twice**: read-only at ladder step 3, and again at step 6 with the poke.
So the treatment build alone yields the baseline read *and* the treatment. The separate control build
is only needed if the treatment's spawn result is ambiguous.

## Predictions

**P1 — the baseline read (step 3, read-only, both arms).**
`Default__BP_DropPod_Tutorial_C` = **1** · `Default__BP_DropPod_C` = **1** ·
`Default__LokiDropPod` = **1** · `Default__Actor` = **1** (root control, never written).
★ This is the read that **closes S130's last inference**: the leaf CDO is not loaded at the menu, so
it was only ever inferred from its ancestors. In a staged world it should be loaded and readable.
⚠ If the leaf reads **0**, the S130 model is wrong and nothing downstream may be interpreted.

**P2 — the poke (step 6).** `1 -> 0` on the three pod CDOs, **readback verified**, `Default__Actor`
untouched at **1**.

**P3 — E1, the headline.** With C7 satisfied, `SpawnDropPodForTeam` via ProcessEvent should no longer
bail at the pooled spawn. **PASS = a DropPod census delta > 0** (`dE` in the after-E1 mini-census).

## What would falsify, and what is NOT a result

* `Default__Actor` reading 0 at any point ⇒ something other than this arm mutates AActor ⇒ **VOID**.
* poke written but readback ≠ 0 ⇒ the write did not stick ⇒ **downstream is UNATTRIBUTABLE**.
* **A census delta of 0 is NOT "the poke failed."** C7 was only ever the *first* of three null
  branches; **C8 (`PoolMgr->GetWorld()==null`) and C9 (`SpawnActor` null / skipped at `0x5648E34`)
  have NEVER been reached in this project's history**, so the expected outcome is that the wall
  *moves*, not that a pod appears. A new failure mode is the modal result and it is a success for the
  investigation.
* ⚠ **The positive control gates everything:** the run is only interpretable if E0 (the Route-E
  `K2_GetActorLocation` control through ProcessEvent) reports agreement. A silent or disagreeing E0
  ⇒ the sitting is **VOID**, exactly as S126/S128 required.
* ⚠ Staging fails ~50 % of the time (FK-31, 22/82 launches die before the probe is injected). A run
  that never arms is **not evidence about anything**.

## Known defect in the FLOWN artifact (label only, not behaviour)

The flown DLL's **step-3** line reads `read-only (KPDCDOPOKE=0 -- this is the CONTROL arm)` even in
the **poke** build, because the label was derived from the per-call argument rather than the build
constant. **That text is FALSE about the build; the behaviour is correct** (step 3 is read-only by
design in both arms). The source is already fixed — the label now prints the build constant and the
per-call behaviour as two separate facts — but the fix is NOT in the flown binary.
**Identify the arm by the step-6 line and by the `.text` hash, never by the step-3 label.**
