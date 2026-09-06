# NEXT SESSION — the ability-system BIND is one call away, and the call has been located

**Read this whole file before touching anything.** Everything below was measured on 2026-08-05 and is
committed on `dedicated-server-stub` (`fde4915`..`5c16224`, all pushed). Branch clean,
`forceTutorialMatch = false`, `ags` rebuilt, nothing running.

> ⚠ **Numbering.** "S111" was consumed by **two parallel sessions on the same day**: an ability-system
> / GC line (`docs/s110-*`, `docs/s111-asc-census.md`) and an FK-8 crash-corpus line
> (`docs/fk8-*`, commit `e5cd820`). Both are real, both are committed, and one point where they
> collided is reconciled in `docs/s111-fk8-s110-reconciliation.md`. This file is the brief for
> whoever comes next; the filename is historical.

---

## 0. ★ TASK ONE — call `InitAbilityActorInfo`. It is at `base+0x447F410`.

**The state of the hero's ability system, all measured** (`docs/s111-asc-census.md`):

| | |
|---|---|
| ASC object | **EXISTS** — but **the shim builds it**: `EnsureHeroAffiliatedCarrier` spawns a `LokiPlayerState_HeroAffiliated`, whose constructor makes the ASC |
| attribute sets | **2**, made by the shim's own `K2_InitStats` calls |
| `ASC.OwnerActor` | set (the carrier) |
| **`ASC.AvatarActor`** | **NULL** ← the gap |
| `ActivatableAbilities` | **0** ← the other gap |
| hero `AbilitySystemComponentStorage@0xF00` | now filled by `KGASSTORAGE` (S111) — **necessary, not sufficient** |

**Nothing in the client-side `LokiPlayerState` path binds the avatar.** `TryUpdateAbilitySystem` and
its same-TU sibling are *change-detect + event broadcast*, both read to the end and confirmed — the
sibling turned out to broadcast `GameEvent_CrewDrop…`, nothing to do with GAS. No reflected function
anywhere does the bind: `ALokiCharacter` has `RemoveFromAbilitySystem` and **no add**;
`LokiPlayerState_HeroAffiliated` has **zero** UFunctions; Angelscript exposes `GetAvatarActorFromASC`
and no setter.

**So the bind must be called directly, and it has been found — by behaviour, not by name:**

```
UAbilitySystemComponent::InitAbilityActorInfo   base+0x447F410
    signature (rcx = ASC, rdx = OwnerActor, r8 = AvatarActor)   __fastcall, 3 pointers, void
    body:  mov rcx,[rdi+0x418]        ; AbilityActorInfo  (TSharedPtr raw ptr)  <- ASC+0x418
           call [r10+8]               ; AbilityActorInfo->InitFromActor(owner, avatar, this)
           mov [rdi+0x410], rbx       ; AvatarActor = avatar
           mov [rdi+0x408], r15       ; OwnerActor  = owner
```

### What to actually do, cheapest first

1. **Read `ASC+0x418` first (read-only, no writes).** If `AbilityActorInfo` is null the call will
   dereference null — `InitAbilityActorInfo` opens by loading it and calling through its vtable.
   `tools/re/ps_gas_fields.py` already walks to the ASC; add one read. **Do this before any call.**
2. **Then the call.** It is a **raw, non-UFunction call**, so the ProcessInternal primitive does not
   apply (no `FFrame`) — but it is less exotic than it sounds: a 3-argument `__fastcall` through a
   function pointer, on the game thread, inside the shim's existing SEH guard. The shim already has
   the game-thread context (the PI-hook piggyback) and `CallNativeGuarded`'s guard pattern to copy.
3. ⚠ **Do NOT hardcode `0x447F410`.** Project rule is resolve-by-name, and here there *is* no name —
   so resolve by **signature scan at runtime**, using the same discriminator that found it:
   a `REX.W mov [reg+0x408], reg` and a `mov [reg+0x410], reg` with the **same base and different
   source registers**, within ~0x100 bytes. `tools/re/find_store_pair.py` is the offline version of
   exactly that scan and can be ported. A hardcoded RVA silently becomes wrong on any game update.
4. **Register the prediction before the run.** Expect: `ASC.AvatarActor` becomes the hero pawn, and
   `IsAbilitySystemInitialized` flips to 1 — that bit is a **trustworthy independent witness**
   (S111 verified it stayed 0 even after `@0xF00` was filled, so it does not merely read the cache).
   **`ActivatableAbilities` may well stay 0** — granting is a separate step
   (`BP_AuthGiveAbilityWithInputID`, reflected and callable). A bind with zero abilities is a
   **success**, not a partial failure. Say so in advance.

---

## 1. What S111 established — do NOT re-derive

### The animation / GC thread — **CLOSED**
* The run anim really is garbage-collected (full destroy pipeline, slot reissued).
* **The poked RootSet bit is INERT.** Phase-locked experiment, only injection phase varied: leads of
  **0.15 / 2.9 / 33.1 s** to the next GC pass, destroyed at that pass **every time**. Do not root harder.
* **"Unreachable" is not a sticky bit here.** Reachability is an **alternating flag rotating through
  bits 0/1/2**, flipped population-wide each pass — a free read-only **GC clock** (~61.1 s at rest).
* **FIXED by `KANIMREF`**: park the asset in the body component's unused `AnimationData.AnimToPlay`
  UPROPERTY. Survives two GC passes, zero `[GCW]` lines, run/idle cycling **at the default
  `KAUTOWALKATMS=20000`**. `play-earlywalk` deleted as redundant.
* `UObjectBase`: **`ObjectFlags@0x0C`, `InternalIndex@0x10`** (and the game's own `RF_Garbage` check
  reads `+0x0C`, confirming it independently).

### The crash thread (FK-8, parallel session)
* 114 death records mined; **`+0x205D` = `catalog_store_fix.dll` `.text` RVA `0x205d`** — closes what
  the previous handoff listed as an open lead.
* ⚠ **The injection-spacing 71× result is under re-examination**: deaths in the 30 s row are
  `catalog_store_fix` launch-time faults, which `-InjectGapSeconds` does not affect. Re-fit before
  citing it.
* **Timing: no `T+<n>` hold rule survives.** Tutorial-route crashpad deaths span **87–524 s** (N=13,
  median 283); the `240–295 / median 264` band in CLAUDE.md describes **one class**, not the
  population. Anchor to `Load map complete …/LVL_Tutorial` and classify by **fault family**
  (`RIP == runtime.dll base + 1`). See `docs/s111-fk8-s110-reconciliation.md`.

---

## 2. Traps that will cost you a run

* **DEPLOYED-vs-BUILD drift — now GUARDED, but know the shape of it.** `build.ps1` writes to
  `tools\sigbypass-mod\build\`; `fk24-stage.ps1` injects the **deployed** copies in
  `tools\sigbypass-mod\`. Two tiers on purpose, but nothing enforced the relationship, so you could
  build a fix, run the standard staging, and test the old binary.
  **FIXED (S111):** `fk24-stage.ps1` now `.text`-hashes every shim it injects against `build\` and
  **ABORTS** on a mismatch (`-AllowStale` overrides). `tutorial_launch_sp` has been synced — but note
  `tools/sigbypass-mod/.gitignore` excludes `*.dll`, so **no shim binary is version-controlled**: that
  copy is machine-local and a fresh clone has to build both tiers anyway. **The guard is the durable
  half of this fix; the copy is housekeeping.**
  MEASURED across the 142 deployed DLLs: **64 `.text`-identical, 68 with no build counterpart,
  10 DRIFTED.** ⚠ **`tutorial_launch_play.dll` is still one of the 10, and it is the dangerous one:**
  deployed `.text` is **`a67239a0d83d9300`** — the hash CLAUDE.md identifies as **`play-statictest`**,
  the S108b diagnostic that faulted every run and disabled anim swapping. Left un-synced deliberately
  (out of scope, and the guard now aborts on it) — **pass `-Probe …\build\tutorial_launch_play.dll`,
  or sync it first.**
  ⚠ Compare `.text`, never whole-file: a file-level `cmp` calls all three staging shims different when
  two are functionally identical (PE-header bytes). That rule is the difference between one real
  problem and three imaginary ones.
* ⚠ **PowerShell `Select-Object -First N` tears down the upstream command.** A probe that ran fine
  exits 255 and looks like a crash, and a script that writes a file at the end writes **nothing**.
  Cost two runs and one capture today, *including one after I had written it into this very file.*
  Use `-Last`, `| Out-Null`, or read the output file.
* ⚠ **`dumps/merged.dump.exe` is a MENU snapshot** — in-world code reads as **zeros** there. Use
  `dumps/tutorial-hero/` (67.42 %, `.text` 53.2 %) with
  `CG_DUMP=… CG_BASE=0x7FF6505C0000` for anything gameplay-shaped. It cannot be merged into
  `merged.dump.exe` (different ImageBase; `mergedumps` rejects that by design).
* ⚠ **`.pdata` is entirely ZERO in this build**, and there is **no int3 padding** between functions
  (171 `0xCC` in a 2 MB sample). Neither the unwind table nor a backward-`CC` scan will give you
  function bounds. Use 16-byte alignment + a shadow-space argument spill, and confirm by disassembly.
  ⚠ The `dumpimage` manifest's `.pdata 100.0%` counts **readable pages, not content**.
* ⚠ **An empty column in an export is not absence of evidence.** The FK-8 corpus CSV has empty
  `exception_code` for all 22 crashpad rows, but those dumps *were* classified from the minidumps
  directly. I read the blank column as "unclassified" and was wrong.
* ⚠ `Marker()` opens `CREATE_ALWAYS` (FK-25) — read the LIVE marker after a run, not the staged copies.
* ⚠ **Set `forceTutorialMatch` back to `false` and rebuild `ags` when done.** It is `false` now.

---

## 3. Tooling added today (all read-only unless noted)

| tool | what it gives you |
|---|---|
| `tools/re/item_watch.py` | watch a UObject's `FUObjectItem` across its death; **prints the GC clock**; decoy controls; VOID gate |
| `tools/re/asc_census.py` | every ASC in the process grouped by owner; the pawn-vs-object distinction |
| `tools/re/ps_gas_fields.py` | the exact fields `TryUpdateAbilitySystem`'s change-detector compares |
| `tools/re/vtable_dump.py` | a live object's C++ vtable as RVAs, for offline slot analysis |
| `tools/re/find_store_pair.py` | **find a function on a stripped binary by the two fields it writes** — this is what located `InitAbilityActorInfo` |
| `tools/re/offline_disasm.py` | now takes `CG_DUMP` / `CG_BASE` env overrides |
| `dumps/tutorial-hero/` | the first non-menu image capture the project owns |

---

## 4. Other open leads, in rough value order

1. **Grant an ability** once the bind lands — `BP_AuthGiveAbilityWithInputID` /
   `AuthGiveAbilityWithSourceObject` are reflected and callable today. Ability *content* is on
   `ALokiCharacter::CharacterAbilities` / `BaseCharacterAbilities` and `BP_HeroAsset_Ronin_C`.
2. **The orphaned second `AnimSingleNodeInstance`** — destroyed at the first GC pass in every run
   including the successful one. Harmless (nothing holds it) but it is a real dangling object.
3. **Re-fit the injection-spacing hazard** after classifying each death by fault family (FK-8 §7.2).
4. **`harvest.py` still enumerates `UECC-*` only** and is blind to the crashpad path.
5. **Bits 0/1/2 as a rotation of three** — an odd design, unexplained, currently harmless.

---

## 5. The rule that earned its keep today

Three times this session I named a function from its call site instead of reading it — a paired
`AddToAbilitySystem` that does not exist, a bind in `PossessedBy` that is stock engine code, and a
"wiring sibling" that broadcasts drop positions. **Each cost a run.** Both things that actually landed
— the `KANIMREF` fix and `InitAbilityActorInfo` — came from reading to the end of a function, or from
searching on *behaviour* rather than on a name.

* **Read to the end of the function before naming it.**
* **Register the prediction and the VOID conditions before the run**, and score them honestly
  afterwards (`docs/s110-prediction-registered.txt` has five, including two that were falsified).
* **Watch things you have no hypothesis about** — the decoy controls in `item_watch.py` caught a wrong
  rule on the first smoke run, before any game time was spent.
* **Prefer the read-only test.** The experiment that falsified my own mechanism hypothesis cost one
  staged run with no writes, and the falsification is what pointed at the answer.

`memory/supervive-instrument-artifact-pattern.md` now carries 19+ confirmed instances. Read it first.
