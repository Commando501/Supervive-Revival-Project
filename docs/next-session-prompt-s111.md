# S111 — the tutorial hero is complete except for SIMULATION. Start at the `[GAS]` chain.

**Read this whole file before touching anything.** Everything below was measured live on 2026-08-05
(S110) and is committed on `dedicated-server-stub` (`fde4915`..`2690822`, all pushed). Branch is clean,
`forceTutorialMatch = false`, `ags` rebuilt, nothing running.

**S110 in one line:** the run-animation defect is *solved* — root-caused to a real GC collection, the
inherited "just root it" premise falsified with a phase-locked experiment, and fixed by giving the
asset a reference the GC can actually reach. The hero now walks and runs with locomotion animation at
the default timing, with no diagnostic build.

---

> ## ✅ TASK ONE STEP 1 IS DONE — and it INVERTED the premise. Read `docs/s111-asc-census.md` first.
> **The hero DOES have an ability system.** `LokiAbilitySystemComponent 0x274BDE53400`, owned by the
> `LokiPlayerState_HeroAffiliated` companion, with `SpawnedAttributes` **Num=2**. The three fields
> every existing tool reads (`@0xF00/0xF08/0xF10` on the pawn) are a **CACHE**, and both the shim and
> `gas_recon.py` mistook them for the ability system. That is FK-30.
>
> **The real gap is two things, not a subsystem:** `AvatarActor` is **NULL** (so the ASC is never bound
> to the pawn — the second half of `InitAbilityActorInfo`), and `ActivatableAbilities` is **Num=0**.
> Start at §5 of `docs/s111-asc-census.md`: call `TryUpdateAbilitySystem` (native, parameterless,
> already resolved by the shim) and see whether the bind and the caches populate.
>
> Also measured: **344 initialised ability systems** exist in the loaded tutorial world (brush, trees,
> `BP_CapturePoint_Tutorial_C`), so GAS runs here constantly — and the world has **no game-spawned hero
> or AI pawn** at this stage, only spectators, so the spawn-path comparison below could not be run and
> is no longer the question. The `SpawnPlayer` route is NOT indicated by this evidence.
>
> ⚠ The "would we be first" verdict this probe emits in a **parked** process is an artifact of the world
> not being loaded. A negative measured in an empty world is not a negative.

## 0. ★ TASK ONE — the hero has no ability system, and the shim already tells you exactly where it stops
### ⚠ SUPERSEDED — the premise of this section is false; see the banner above. Kept as the record.

**Why this and not stability:** S109/S110 established that **every tutorial death ever captured is the
protector** (`runtime.dll+1`, zero SUPERVIVE frames, now nine-plus independent instances). FK-7 has
never had a confirmed instance. Chasing "stability" risks chasing the anti-tamper. Meanwhile runs are
now lasting **338–434 s** (§2), which is plenty of window to do real work in. Simulation is the actual
milestone: the hero moves and animates but cannot *do* anything.

**The blocker is already instrumented.** From the last armed run's marker, verbatim:

```
[GAS] hero Role@0x160=3
[GAS] GetHeroAsset -> 0x2AC084EFC40 (BP_HeroAsset_Ronin_C)          <- resolves fine
[GAS] AFTER  AbilitySystemComponentStorage  @0xF00 = 0x0 (NULL)
[GAS] AFTER  AttributeSetStorage            @0xF08 = 0x0 (NULL)
[GAS] AFTER  AttributeSetHealthStorage      @0xF10 = 0x0 (NULL)
[GAS] AFTER  IsAbilitySystemInitialized -> parm@0x0=0 res=0
[GAS] GetLokiAbilitySystem_BP -> 0x0 (NULL)
[GAS] ===== RESULT: initialised 0 -> 0  *** STILL NOT INITIALISED *** =====
```

`tutorial_launch.cpp:4565` onward ("S101: driving LokiPlayerState's own ability-system wiring chain")
already: finds the PlayerState, resolves the hero class and `GetHeroAsset`, builds a carrier object,
writes `PlayerState.HeroAffiliatedObject`, and tries `K2_InitStats` on the attribute sets. The three
storage slots stay NULL regardless. **So the question is not "where is the ASC" — it is "which step of
the game's own wiring is not running", and every step is already logged.**

**The hypothesis worth testing first, and it is cheap and READ-ONLY.** The shim spawns the hero itself
(`SpawnActorCls` + possess) rather than through the game's own path, so it plausibly skips whatever
initialises the ability system. `ALokiGameMode::SpawnPlayer` is the real hero-spawn primitive and is
**Angelscript, fully decompiled** (`tools/asdump`; memory `supervive-angelscript-layer`).

> **Step 1, no shim, no armed window needed:** find a pawn in the tutorial world that the GAME spawned
> — a bot, an AI, a training dummy — and read its `AbilitySystemComponentStorage@0xF00`. If the game's
> own pawns have a live ASC and ours does not, the spawn path IS the difference and the route is to
> spawn through `SpawnPlayer`. If *nothing* in the map has an ASC, the ability system is not running at
> all in this mode and the target moves to whatever gates it. **This is a read-only RPM probe** —
> `tools/re/gas_probe.py` and `gas_recon.py` already exist; `obj_by_class.py` finds the pawns.
> **One menu-or-tutorial attach, ~30 minutes, and it splits the problem in half.**

⚠ Register which outcome you expect before you look. Both are informative; only one is a surprise.

### A 30-minute OFFLINE warm-up, if you want a cheap win first

* **`chain = 888cee8 8831758`** — the first Family B specimen carrying SUPERVIVE frames (dump
  `590cfd83`, in `dumps/crashpad-20260804-182004-shimrun3-DEATH`). **Nobody has looked up those two
  RVAs in three sessions.** If they land in game code it is the first real FK-7 evidence that exists.
  `tools/re/offline_xref.py` / `disasm_live.py` against `dumps/merged.dump.exe`. Cheap, possibly decisive.
* **Audit `KGCROOT`.** It is now MEASURED INERT (§1). It still runs a full root-bit corroboration and
  pokes flags on every load, and prints `[GC] ROOT loaded-asset … OK` lines that *look* like they are
  protecting something. That is precisely the instrument-artifact hazard this project keeps tripping
  over. Either delete it or re-label the log lines "poked (measured inert, kept as telemetry)". Leave
  the corroboration code — it is correct now and it measures a real bit.

---

## 1. What S110 established — do NOT re-derive any of it

Full write-up: `docs/s110-item-watch-gc-mechanism.md`. Memory: `supervive-gc-reachability-mechanism`.
Ignorance map: **FK-27, FK-28, FK-29** are new entries in `docs/ignorance-map-s101.md`.

1. **The asset really IS garbage-collected.** Full pipeline observed in order: `RF_BeginDestroyed` →
   `RF_FinishDestroyed` → `LowLevelRename(NAME_None)` → `FreeUObjectIndex`, then the slot reissued to a
   new object ~20 s later. "Torn down out of band" is **eliminated**.
2. **★ The poked `RootSet` bit is INERT.** Phase-locked experiment, only the injection phase varied,
   three armed windows: lead from verified poke to the next GC pass **0.15 s / 2.9 s / 33.1 s — destroyed
   at that pass every time.** In the last it sat through six clean 5 s heartbeats and died 708 ms after
   the flip. The engine zeroes bit 30 with the rest of the word on free. **Do not root harder.**
3. **★★ "Unreachable" is not a sticky bit in this build.** Reachability is an **alternating value**
   rotating through bits 0/1/2, flipped population-wide on each GC pass. An object is unreachable when it
   fails to carry the *current* one. Bit 28 was never seen set on anything. This is what S109 recorded as
   the unexplained `flags == 0x00000004` and "bit 1 on 81% of ordinary objects, 0% of natives".
4. **Rooted and marked are mutually exclusive naturally**: 4,915 rooted objects of which **0%** carry the
   current flag; 17,237 unrooted of which **100%** do. Root-set objects are *excluded* from marking, so a
   poked object never joins that set — it keeps a stale mark and is collected on the merits of its refs.
5. **★★★ THE FIX (`KANIMREF`, default ON in `play`)** — park the run `AnimSequence` in the body
   component's unused `AnimationData.AnimToPlay` UPROPERTY. Confirmed: re-marked at **two** consecutive
   GC passes, zero `[GCW]` lines, and `PlayAnimation(run/idle, loop) ok` cycling **at the default
   `KAUTOWALKATMS=20000`**. Control arm `play-noanimref`. Why that slot: `PlayAnimation` writes the
   single-node instance's `CurrentAsset`, which holds exactly **one** asset — which is why the *idle*
   anim always survived and the run anim never did.
6. **`UObjectBase` layout completed**: `ObjectFlags@0x0C`, `InternalIndex@0x10` (calibrated 400/400 and
   100%/0% against controls that could fail), alongside the known `ClassPrivate@0x18`, `NamePrivate@0x20`.
   An object's array slot is now readable **straight out of the object**, no scan.
7. **The load does NOT provoke the GC.** The staging pipeline is deterministic and the clock is ~61.1 s
   from launch, so the load phase was near-constant across runs — that, not a load-triggered collection,
   is why S109's deaths all clustered 1.1–7.8 s after body build.

---

## 2. Numbers that change how you budget a sitting

* **★ The "~285 s code-integrity kill" is too pessimistic.** MEASURED across S110's seven tutorial
  launches: deaths at **293 s, 338 s, 434 s**, plus two runs still alive at **≥361 s and ≥408 s** when
  deliberately killed. Nothing died near 285 s. Budget on ~330 s conservatively, not 285 — it buys a
  whole extra GC cycle of observation. (CLAUDE.md's 285 s figure is left in place as the *integrity
  check* timing; it is evidently not a reliable death predictor.)
* **Armed-window yield: 4 of 7 tutorial launches** (2 NOSTAGE force-open failures — FK-26; 1 staged but
  died before body build). Slightly better than the documented "~2 of 4", same order. Still budget on
  **armed windows, never launches**.
* **★ The GC clock is predictable and now instrumented.** Passes land at **uptime ≈ 75 s, then every
  ~61.1 s**, disturbed by the tutorial map load (which shows up as a purge of ~125,000 objects, and two
  short 29–32 s intervals around it). `tools/re/item_watch.py --marker` prints them live.
* **★ Phase-locked injection works and is reusable.** `fk24-stage.ps1 -SkipProbe` stages the world, then
  `tools\inject\inject.exe mmap <pid> <dll>` whenever you choose. Body build lands ~13 s after injection.
  That is how the 33.1 s lead in §1.2 was obtained; use it whenever an experiment needs a known phase.

---

## 3. Traps that will cost you a run

* ⚠ **`play`'s `.text` hash has moved a THIRD time. Current: `513c6277c3ae88f3`.** `7bc4df9236ead0ac`
  was `play` only between S109 and S110; `ae532866e15fd8ac` only between S108b and S109;
  `a67239a0d83d9300` is `play-statictest`. **Verify by `.text` hash, never whole-file and never size** —
  `play-strictroot` and `play-noanimref` share a 161,792-byte `.text`.
* ⚠ **`play-earlywalk` was DELETED** (it only raced a collection that no longer happens). Docs written
  before 2026-08-05 that recommend it are stale. `-DKAUTOWALKATMS=<ms>` still works for a one-off.
* ⚠ **FK-25 is still live**: `Marker()` opens `CREATE_ALWAYS`, so every injection truncates
  `docs/tutorial-launch-marker.txt` and `fk24-stage.ps1`'s step-N copies routinely capture the file
  *before the probe wrote anything*. Read the LIVE marker after the run. (`item_watch.py --marker`
  handles the truncation correctly — a shrinking file is a rewind, not an error.)
* ⚠ **`Copy-Item` preserves the SOURCE's LastWriteTime.** Never derive timings from copied-marker mtimes.
* ⚠ **PowerShell `Select-Object -First N` kills the upstream pipeline**, so a probe that ran fine exits
  255 and looks like a crash. Use `-Last`, `Out-File`, or read the log file. This cost two runs in S110.
* ⚠ **Set `forceTutorialMatch` back to `false` and rebuild `ags` when done.** It is `false` now.

---

## 4. Other open leads, in rough value order

1. **The orphaned second `AnimSingleNodeInstance`.** The shim creates two; one is referenced by the live
   component and survives, the other is destroyed at the first GC pass in **every** run including the
   successful one (`VERDICT: A SLOT RECYCLED at t=244.554`). Harmless today — the shim keeps no pointer
   to it — but it is a real dangling object that `GcRootAllOfClass` "roots" and believes is alive. Worth
   ten minutes to find why two are made.
2. **6 chainless-but-parseable UECC dumps** were walked in S109 §11; another **7 are zero-byte**. The
   `+0x205D` family (6 members) has never been characterised beyond "executes in an unmapped 64 KB-aligned
   region".
3. **Anti-tamper vs protector defect is still OPEN** — 487 s ≠ the documented ~285 s integrity kill, and
   §2's survival spread makes that discrepancy more interesting, not less.
4. **`harvest.py` still enumerates `UECC-*` only** and is blind to the crashpad path (44 archived dumps
   in `dumps/crashpad-*` it cannot see). S109 deliberately did not rebuild it.
5. **Bits 0/1/2 as a rotation of three** is an odd design. Whether the third value is a real third state
   or something else is unresolved and does not matter yet.

---

## 5. The rule that governed S110, and should govern S111

S110 caught **three** instrument artifacts, and two were caught by controls *before* they cost anything:

* *"`SerialNumber` changes ⇒ the slot was recycled"* — the S110 brief's own headline discriminator, and
  **wrong**. UE allocates serial numbers lazily on first weak pointer; a live, untouched decoy went
  `0 → 3373` at the menu. Caught on the first smoke run by 256 decoy objects nobody had a hypothesis about.
* *`SerialNumber N → 0`* is the **free** clearing it, not a reissue. This one **did** cost a verdict — the
  first tutorial log prints `SLOT RECYCLED` where the truth was `FREED`. Caught only because the other
  signals (`RF_FinishDestroyed`, `item.Object → 0`) disagreed with it.
* `Select-Object -First` faking two crashes (§3).

So, non-negotiably, and it is exactly what made S110 work:

* **A gate that cannot fail is not a gate.** Every offset `item_watch.py` uses is calibrated against a
  control that can return false, and it prints `UNRESOLVED` rather than guessing.
* **Watch things you have no hypothesis about.** The decoys cost nothing and caught the first artifact.
* **Register the prediction before the run** (`docs/s110-prediction-registered.txt` has four of them, all
  scored honestly afterwards) and **state the VOID conditions in advance** — S110 declared one run void
  for a reason written down before it started, rather than reading a death that came too early.
* **Print the aliasing bound**, and make no negative claim stronger than it.

`memory/supervive-instrument-artifact-pattern.md` now carries 16+ confirmed instances. Read it first.
