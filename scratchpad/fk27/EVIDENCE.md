# FK-27 successor — what this build's GC actually excludes, and why the RootSet poke was inert

**Session S123, 2026-08-15. Read-only RPM against a live menu process (uptime ~3 h at first sample).
No injection, no `.text` write, no launch, no shim. `ags` and the game were left running throughout.**

Instrument: `tools/re/rootset_census.py` (imports the calibrated primitives from `tools/re/item_watch.py`).
Raw output: `scratchpad/fk27/census-run2.txt`. One-off follow-up: `scratchpad/fk27/mine-lowidx.py`.

⚠ Verdicts from the adversarial reviewer are in `scratchpad/fk27/skeptic-review.md`; the offline
disassembly is in `gc-mark-re.md` / `addtoroot-re.md`. **This file records the MEASUREMENTS only.**

---

## 0. What FK-27 settled, and what it did not

FK-27 ("poking `EInternalObjectFlags::RootSet` keeps a shim-loaded asset alive") is **DEAD and stays
dead** — three armed windows, monotone lead times 0.15 s / 2.9 s / 33.1 s, destroyed every time
(`docs/s110-item-watch-gc-mechanism.md` §4d). Nothing here re-opens it.

But it closed on **outcome**, never on **mechanism**, and its own evidence contained a contradiction
that was written down and not chased:

* objects carrying bit 30 *naturally* are never marked (S110: 0% of ~4,915)
* objects on which the shim *poked* bit 30 **are** marked, and are collected

Same bit, opposite treatment. That is the thread this pulls.

---

## 1. [M] There are TWO populations carrying bit 30, not one

Live process, full-resolution census (every index, no striding), `numEl = 207,719`, live `200,437`:

| population | n | index range | carries current reachability value | ever freed |
|---|---|---|---|---|
| never-freed prefix, bit 30 set | 39,275 | `[0, 39295)` | **0** | no |
| never-freed prefix, bit 30 CLEAR | 20 | `[0, 39295)` | **0** | no |
| high-index, bit 30 set | 32 | > 39295 | **32 (100%)** | no |
| high-index, ordinary (sampled) | 5,000 | > 39295 | **5,000 (100%)** | yes |

Global contingency at full resolution, for comparability with S110's 1-in-8 sample:

```
bit30 SET   :  39307 objects,     32 (  0.1%) carry the current reachability value
bit30 CLEAR : 161130 objects, 161110 (100.0%) carry it
```

S110 sampled this and reported `4915 rooted / 0% marked` — the same shape, one eighth the size.

## 2. [M] The prefix boundary is real, and it is 39,295

Two independent signatures:

* **No holes.** `first free slot = 39295`. The array has 7,282 free slots; **not one** of them lies
  below 39,295. If the free slots were uniformly distributed over 207,719 positions,
  `P(zero in the prefix) ≈ 10^-676`. Arithmetic in `mine-lowidx.py`.
* **Never marked.** Every object below 39,295 carries reachability value `0` — *including* the 20
  that lack bit 30.

## 3. ★★★ [M] The 20 unflagged prefix objects are the non-circular proof

This is the load-bearing measurement, because it breaks the circularity in S110's reading (which
identified "rooted" *by* the bit and then concluded things about the bit).

20 objects sit inside the never-freed prefix **without** bit 30:

```
32257  00000000  EdGraphPin_Deprecated        Default__EdGraphPin_Deprecated
33027  00000000  BlendProfile                 Default__BlendProfile
32960  00100000  BlueprintGeneratedClass      DmgTypeBP_Environmental_C
38401  00100000  BlueprintGeneratedClass      BP_ThumbnailGenerator_SkySphere_C
38402  00100000  Function                     ExecuteUbergraph_BP_ThumbnailGenerator_SkySphere
38408  00000000  SimpleConstructionScript     SimpleConstructionScript
38409  00000000  SCS_Node                     SCS_Node
   ... (20 total: CDOs, a BP-generated class and its functions/components/SCS nodes)
```

**All 20 carry reachability value 0 — they are never marked.** If bit 30 were what excluded an
object from marking, these 20 would be marked. They are not.

⇒ **Exclusion from the reachability sweep is by INDEX, not by the flag.** Bit 30 on a prefix object
is a *consequence* of being allocated in the disregard window, not the cause of its exclusion.

[I] The identity of the 20 fits: they are objects created inside the disregard window that were not
tagged `RF_MarkAsRootSet` — the pool boundary is temporal (allocated before
`CloseDisregardForGC()`), and flagging is a separate concern.

## 3b. ★★★★★ [M] STRUCTURAL CONFIRMATION — the boundary is a NAMED ENGINE FIELD

The census-derived boundary was checked against the engine's own bookkeeping, as a **prediction
registered in `mine-guoa.py`'s header comment before the memory was read**.

`GUObjectArray` (the `FUObjectArray` global) is at RVA **`0x9E38920`**, and the stock UE5 layout maps
field-for-field:

```
base+0x9E38920  +0x00  int32 ObjFirstGCIndex             = 39295     <-- == census first_free
base+0x9E38924  +0x04  int32 ObjLastNonGCIndex           = 39294     <-- == census first_free - 1
base+0x9E38928  +0x08  int32 MaxObjectsNotConsideredByGC = 45000     <-- configured budget
base+0x9E3892C  +0x0C  bool  OpenForDisregardForGC       = 0         <-- window closed
base+0x9E38930  +0x10  FChunkedFixedUObjectArray ObjObjects
                         +0x00 FUObjectItem** Objects    = 0x2696B1199A0
                         +0x08 PreAllocatedObjects       = NULL
                         +0x10 int32 MaxElements         = 2162688   (= 33 * 65536)
                         +0x14 int32 NumElements         = 207719
                         +0x18 int32 MaxChunks           = 33
                         +0x1C int32 NumChunks           = 4
```

Two independent instruments — a full census of free slots in the object array, and a named engine
field read from a different address — agree **exactly** on 39,295. `ObjObjects.Objects` also matches
the pointer the census itself walked (`0x2696B1199A0`), so the two readings are of the same array.

⇒ **N2 is no longer an inference about "a disregard pool". The engine says so in a named field, and
the pool is 39,295 objects against a configured budget of 45,000.**

★ Note for the repo: the long-standing project constant `RVA_OBJOBJECTS = 0x9E38930`
(`tutorial_launch.cpp:23`, `item_watch.py:60`, and ~20 shim sources) is `FUObjectArray + 0x10`, i.e.
it points at the *inner* `ObjObjects` member. That is correct for what it is used for, but it is why
nobody had the disregard fields — they sit 0x10 bytes **below** the address everything anchors on.

## 4. ★★★ [M] Real `AddToRoot()` objects ARE marked, every pass

32 bit-30 objects live above the boundary. [I] by class identity they are textbook `AddToRoot()`
callers — `Canvas DebugCanvasObject`, `Canvas CanvasObject`, the blue-noise `Texture2D`s,
`CrowdManager`, `World LVL_LobbyV2_Persistent`, `ImageCache`, `LokiInternalAbilitySystemGlobals`,
`PCGGenSourcePlayer`, several `BP_MainMenu_SceneRotator_C`.

Tracked across real GC rotations, sampling every 3 s. **Positive control on the clock:** the
rotations land ~61 s apart, matching the game's own
`gc.TimeBetweenPurgingPendingKillObjects = 61.1`.

**Run 1** (rotations bit2→bit1→bit0→bit2 at t = 23.8 / 84.4 / 147.4 s):

```
HI-ROOTED (real AddToRoot)   n=32   always-carried-current=32   missed=0
ORDINARY  (control)          n=40   always-carried-current=40   missed=0     <-- VACUOUS
PERMANENT (control)          n=40   always-carried-current=0    missed=40    <-- TAUTOLOGICAL
```

**Run 2**, same probe, same process, ~10 min later (rotations bit1→bit0→bit2 at t = 51.1 / 112.5 s):

```
HI-ROOTED (real AddToRoot)   n=32   always-carried-current=32   missed=0
ORDINARY  (control)          n=40   always-carried-current=21   missed=19    <-- DISCRIMINATES
PERMANENT (control)          n=40   always-carried-current=0    missed=40
```

⚠ **State the weakness plainly: in run 1 the ordinary control was VACUOUS** — it could not fail, so
run 1 alone shows only "rooted objects are always marked", not "more reliably than anything else".
Run 2 is the run that carries the argument, because there the control *does* fail: 19 of 40 ordinary
objects missed at least one rotation while 0 of 32 rooted objects did. Fisher one-tailed on that
2×2 = **1.115e-06**.

⚠ **The between-run variance is itself unexplained** and is under adversarial review. If the control
set is re-selected per run, the two runs are not paired and the Fisher figure applies to run 2 alone.

⚠ The PERMANENT row is a **tautology**, not a finding — prefix objects carry no low bits at all, so
"never carried the current value" is guaranteed. It is printed as a sanity check, nothing more.

[I] Mechanistic reading, falsifiable: root-set objects seed the traversal and are marked **first**,
so a 3 s sampler never catches them stale, while ordinary objects get caught mid-traversal. This
predicts that a faster sampling period makes *more* ordinary objects fail while rooted stays at 0.
Under test.

---

## 4b. [M] The root SEED is a separate registry — and its size is DISPUTED

Offline disassembly (`gc-mark-re.md`) found, at instruction level:

* **The sweep domain is a loop bound, not a flag test.** All three whole-array GC sweeps iterate
  `[GUObjectArray.ObjFirstGCIndex, ObjObjects.NumElements)`, never from 0
  (`0x01259162` loads `ObjFirstGCIndex` as START, `0x0125916D` loads `NumElements` as END).
  `GatherUnreachableObjects` (`0x01250A40`) names the sole exception itself:
  `cmovne r9d, ebx` sets START = 0 when `GExitPurge` (`.data 0x9D29118`) is set.
  `MarkObjectsAsUnreachable` hand-injects `GGCObjectReferencer` at `0x0129B3F9` *precisely because*
  the pool is otherwise never visited. **This independently confirms §2/§3 at the code level.**
* **The traversal is seeded from a `TSet<int32>` of InternalIndices at `.data 0x99D3CA0`**, walked
  with no predicate by mark body A (`0x0123E3B0`). An `InterlockedOr` of bit 30 writes the flag and
  never touches that set.
* Reachability triple `0x99D36A0/A4/A8` = Reachable / Unreachable / MaybeUnreachable, **runtime
  values rotated O(1) per pass** — that is FK-28's bit-0/1/2 rotation, explained.
* Keep mask `0x4E100000` = `RootSet|AsyncLoading|Async|Native|LoaderImport`.

### ✅ RESOLVED — set-identity confirmed, and the conflict below was MY parse error

`0x99D3CA0` is a `TSparseArray`. `Num()` is `ArrayNum - NumFreeIndices`, **not** `ArrayNum`:

```
ArrayNum = 49307   NumFreeIndices = 49275   =>  Num() = 32
```

Both values were sitting in my own first hex dump (`+0x30 FirstFreeIndex = 49197`,
`+0x34 NumFreeIndices = 49275`) and I read straight past them. Walking the **allocation bitmap**
instead of the raw slot array gives 32 allocated elements, and:

```
SET IDENTITY   registry=32  census=32  intersection=32
  in registry but not census : none
  in census but not registry : none
  *** SET-IDENTICAL ***
```

The 32 are exactly the textbook `AddToRoot()` population: `LokiGameEngine`,
`OnlineEngineInterfaceImpl`, engine default textures (`DefaultTexture`, `DefaultBokeh`, `MiniFont`,
`PreintegratedSkinBRDF`, the `STBlueNoise` pair), `SC_Master` / `MasterSubmixDefault` /
`MasterReverbSubmixDefault`, `CanvasObject` / `DebugCanvasObject`, `CrowdManager`,
`World LVL_LobbyV2_Persistent`, `LokiInternalAbilitySystemGlobals`, `ImageCache`, four
`BP_MainMenu_SceneRotator_C`. All read flags `40000001`.

⇒ **Two independent instruments — a flag census over 200,475 objects, and the registry's allocation
bitmap — agree with zero symmetric difference.** Registry membership and bit 30 are the same set,
and the offline reading of 31/29 in the static images was correct all along.

⚠ **Instrument-artifact instance, mine, logged:** I read a `TSparseArray`'s `ArrayNum` as its member
count, derived three false conclusions from it (pool objects in the registry; 4,306 members without
bit 30; "the mirror model is too simple"), and sent all three to the offline agent as a challenge to
its correct result. The tell was available in the same dump I was reading. **`Num()` of a sparse
container is never `ArrayNum`.**

★ **Free RPM receipt for future work, verified:**
`liveRootCount = *(int32*)(base+0x99D3CA8) - *(int32*)(base+0x99D3CD4)` reads **32** and matches the
census exactly. Both `SetRootFlags` and `ClearRootFlags` compute that same expression.

<details><summary>Superseded: the conflicting reading, kept for the record</summary>

**[M] Live reading of `base+0x99D3CA0`, and it CONFLICTS with the offline count:**

```
Elements.Data = 0x2696C350000   ArrayNum = 49307   ArrayMax = 67925
NumBits = 49307  MaxBits = 58240   HashSize = 32768
```

Type identification is solid — the 12-byte records parse as
`TSetElement<int32> { Value@0, HashNextId@4, HashIndex@8 }`, verified three independent ways:
every `HashIndex` < 32768 (matching the `HashSize` field read separately), every `HashNextId` is
`-1` or a valid element index < 49307, and 88.4% of `Value`s are live object indices.

But the **size is 49,307, not the 31 / 29 the offline pass reported** from the static images.
Contents (43,601 members map to live indices):

* contains **all 32** high-index bit-30 objects, zero missing
* 39,263 members are **below** `ObjFirstGCIndex` (disregard-pool objects)
* 4,338 are above it, of which only 32 carry bit 30 ⇒ **~4,306 above-boundary members lack bit 30**
* 90.1% of live members carry bit 30 (live bit-30 total = 39,307; live keep-mask total = 39,321)

⚠⚠ **UNRESOLVED, and deliberately not rounded off.** Three specific consequences:
(i) the offline `Num() = 31` needs re-deriving or withdrawing; (ii) the offline explanation that the
`OpenForDisregardForGC` gate *blocks* pool objects from the registry is contradicted — 39,263 pool
objects are in it; (iii) because ~4,306 members lack bit 30, "the flag is a mirror of registry
membership" is **too simple** and must not be written up as settled. Under re-examination.

## 5. What this corrects

1. **S110's "root-set objects are excluded from marking (0% of 4,915)" is a POOLING ARTIFACT.**
   39,275 never-marked permanent objects swamped 32 always-marked real roots in one bucket labelled
   "rooted". The 0% is the permanent pool's property, reported as the root set's property.

2. **The "CHIMERA" state is normal, not pathological.** `item_watch.py:738` labels
   `RootSet + current mark` "a CHIMERA — 0.03% of the natural population", and S110's verdict text
   flags it as anomalous. It is the **ordinary, healthy state of a genuinely rooted non-permanent
   object** — all 32 real roots are in it, continuously. The instrument emitted that label about the
   shim's object, which therefore had the *correct* flag word all along.

3. **So the shim's failure was never a wrong bit value.** The poked object reached the right flag
   word and was still not re-marked, while genuinely rooted objects are re-marked every pass.
   ⇒ [I] the flag is a **mirror** of a registration that the root *gather* reads elsewhere; setting
   the mirror does not enter the object into the gather. Locating that registration is the offline
   RE task (`gc-mark-re.md`, `addtoroot-re.md`).

4. **`KANIMREF` is re-framed.** Parking the asset in a live `UPROPERTY` is not a workaround for a
   broken mechanism — it is the *same* mechanism real roots use (be reachable by the traversal).
   That is why it works, and it is the correct default.

5. **Prediction available as a free cross-check for the disassembly:**
   `GUObjectArray.ObjFirstGCIndex == 39295` (equivalently `ObjLastNonGCIndex == 39294`) in this
   process. If the disassembly finds a different constant, something here is wrong.

## 6. Live residual in shipping code

`tools/sigbypass-mod/tutorial_launch.cpp:1224` still defaults `KGCROOT 1`, and `GcRoot()` /
`GcRootAllOfClass()` still run on every `play` launch (`:5357`, `:5421`, `:5803`), performing
`InterlockedOr` writes on live `FUObjectItem` flag words that are **measured to do nothing**. The
comment at `:1218` still states the dead belief as the fix. Disposition deferred until the offline RE
says whether a real rooting call exists to replace it with.
