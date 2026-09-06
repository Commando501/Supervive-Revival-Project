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

---

## Amendment 1 — after attempts 1 and 2 (written before attempt 3)

**Attempt 1:** staging failed, game died 9 s after `fo` (FK-31, ~27% of launches). Dump archived to
`dumps/crashpad-20260820-010158-s130-cdopoke-att1`. Not evidence about anything.

**Attempt 2:** staged successfully (hero spawned + possessed), probe injected, armed window opened —
then the client died **silently** partway through the ladder, after the C0-BEFORE census and the
ship-candidate enumeration but **BEFORE the CDO arm ran**. No crashpad dump, no handoff, no Fatal,
no assert; `Loki.log` ends mid-normal-operation with client-config polling still running.
That is the **artifact-less death class (FK-32)**.
⚠ **This run is VOID for C7** — the arm never executed, so it is not evidence about the poke.
⚠ It is also **not attributable to the new arm**, which had not run; but see below.

### What attempt 2 did expose, and what changed because of it
`Default__BP_DropPod_Tutorial_C` **IS loaded in a staged world** (`0x1F20D147910`), unlike at the
menu — so the leaf read is reachable and S130 §12.3's remaining inference really can be closed here.

⚠⚠ **A self-inflicted risk the run surfaced:** the first cut of `PdCdoFlags` called `FindObjExact`
once per name, i.e. **four full `GUObjectArray` sweeps back-to-back on the GAME THREAD**. The C0
census measures ~1,400 ms for a single sweep over ~190k objects, so that was a multi-second frame
hitch inside a live tutorial world — the exact hazard the census code next door already warns about.
The arm had not run when the client died, so it did not cause this death, but four avoidable sweeps
on the game thread is a risk regardless. **Rewritten to ONE pass with an early exit and an
elapsed-ms readout.**

### Amended arms (attempt 3 onward)

| arm | `.text` sha256 | size | KPDCDOPOKE |
|---|---|---|---|
| treatment | **`bc1c1a5b1e66b54a`** | 161,792 | 1 |
| control | **`780da72fbf4d34e7`** | 161,792 | 0 |

Superseded (flown at attempt 2, four-walk shape): poke `f6b16be64a9ef563`, ctrl `39133126f81a696e`.
The amended builds also carry the step-3 label fix, so the arm is now identifiable from the marker
text itself as well as from the hash.

**Predictions are unchanged.** Nothing about P1/P2/P3 depends on the walk shape.

---

## Amendment 2 — attempt 3 died the same way, and the EXPERIMENT IS CHANGED (written before attempt 4)

**Attempt 3:** staged cleanly again (hero spawned + possessed, probe injected, armed window opened),
then died **silently during the ship-candidate enumeration** — further along than attempt 2 (11
candidates listed vs 1) but still **before the CDO arm ran**. No dump, no handoff. **Void for C7.**

⚠ Two consecutive deaths at the same ladder position is not obviously random (the recorded
artifact-less rate is ~3/36 armed windows, so two in a row is ~0.7%). I am NOT claiming a mechanism
for it — but it is enough to stop repeating the same setup.

### ★ The setup was wrong, and checking S127 is what showed it
S127 flew Route E successfully, and its census reads **`DropShip=1`** — because it injected
`dropplane_b1only` FIRST, which creates a live `LokiDropShip`. **Both of my runs read `DropShip=0`:**
only archetypes exist, so `PdResolve` enumerates every `Default__BP_DropPlane_*` candidate and E1 has
no ship to call on. **I omitted a precondition S127 had.**

### ⇒ Switching to the cheapest test of C7, which needs none of that
`RM_POOLSPAWN` calls `SpawnPoolableActorFromClass{,Deferred}` **directly** on
`BP_DropPod_Tutorial_C`. It needs **no live DropShip, no pre-spawned plane, and no ProcessEvent** —
three preconditions that are irrelevant to the question "does clearing bCanEverReplicate make the
pooled spawn return an actor?". S128 flew this exact probe to completion and measured **P1 and P2
both NULL** while the ordinary path (P3) spawned the same class fine.

**So S128 is the historical control and these arms are the same probe with ONE BYTE different.**

| arm | `.text` sha256 | size | KPDCDOPOKE |
|---|---|---|---|
| treatment | **`8d4a81045820ebec`** | 151,040 | 1 |
| control / S128 reproduction | **`4e9c12ae866f5359`** | 151,040 | 0 |

S128 flown baseline for reference: `poolspawn d3e1ffb9623f6352`.

### Amended predictions
**P1 (baseline, at P0c, read-only):** all four CDOs print; `BP_DropPod_Tutorial_C` = **1**.
**P2 (poke, immediately before the pooled spawn):** `1 -> 0`, readback verified, `Default__Actor`
untouched at 1.
**P3 (the headline):** with C7 satisfied, `SpawnPoolableActorFromClassDeferred` / `...FromClass`
should return a NON-NULL actor and the DropPod census should move (S128 measured `dP1 = dP2 = +0`).
⇒ **PASS = a non-null return AND a census delta > 0.**
⚠ A null return with the readback verified at 0 would mean C7 is NOT the only gate on that path —
which is a real result, and points at the remaining branches inside `0x5648050`.
⚠ The `0xA5` return sentinel still distinguishes "nothing wrote a return" from "wrote null"; do not
read a null without checking it.
