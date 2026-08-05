# S110 §1 — TASK ONE ANSWERED: the run anim is really garbage-collected, and the poked RootSet bit is inert

**2026-08-05.** `docs/next-session-prompt-s110.md` §0 asked one question: when the tutorial hero's run
`AnimSequence` stops passing `GcAlive`, is it **collected**, **recycled**, or **torn down out of band**?
`GcAlive` cannot tell those apart, and every S109 conclusion about "garbage-collected" rested on it.

**Answer: it is a real, complete garbage collection**, and all three of the sketch's discriminators fired
in sequence on one target. Discriminator **D (out-of-band teardown) is eliminated.** The prediction
registered before the run is in `docs/s110-prediction-registered.txt`; P1, P2 and P3 all held.

Instrument: `tools/re/item_watch.py` (new, read-only RPM, no injection, no writes, no thread suspension).
Raw data: `docs/s110-itemwatch-tut2-20260805-142308.{log,csv}` (the tutorial sitting) and
`docs/s110-itemwatch-{smoke,menu,reach,state,cont}-*.log` (menu development).

---

## 1. The measurement

One armed tutorial window, `tutorial_launch_play.dll` (`.text 7bc4df9236ead0ac`, the registered current
`play`), staged hands-free by `fk24-stage.ps1 -Label s110itemwatch`. The watcher followed every UObject
the shim printed, sampling each one's `FUObjectItem` and its `UObjectBase` header every 50 ms, with a
1-in-8 population sweep every 250 ms alongside.

```
t=187.224  +TARGET AnimSequence/A_Ronin_Movement_OutOfCombat_N#189822  obj=0x21785F7DC00
           BASELINE item{obj=0x21785F7DC00 flags=00000004 cluster=0 serial=63939}    <- t=0 baseline, as required
t=187.845  item.Flags 00000004 -> 40000004   [+bit30 RootSet]          <- the shim's GcRoot poke lands
t=187.946  state LIVE -> ROOTED+MARK
t=187.996  the FOUR OTHER shim-rooted objects go 40000004 -> 40000002   <- GC pass: they are RE-MARKED
t=188.046  item.SerialNumber 63939 -> 0
t=188.046  obj.NamePrivate 2056833 -> 0                                 <- ~UObject ran LowLevelRename(NAME_None)
t=188.046  obj.ObjectFlags 0028000B -> 0029800B  [+BeginDestroyed +FinishDestroyed]
t=188.046  *** GcAlive() would now return FALSE ***                     <- the shim notices, here
t=188.096  item.Object 0x21785F7DC00 -> 0        [FreeUObjectIndex ran]
t=188.096  item.Flags 40000004 -> 00000000       [the engine zeroes the word, RootSet included]
t=188.096  obj.vtable -> 0x217FA4FE800           [OUT OF IMAGE — memory freed and reused]
t=188.197  *** GC PASS #5 *** reachability flag bit2 -> bit1 (population-wide)
t=207.916  item.Object 0 -> 0x2177B6BDB80        [the slot is REUSED by a new object, 20 s later]
```

**251 ms from the verified root to destruction. 872 ms from load to destruction** (the shim's own
`[GCW]` line says `t=1109ms after body build`, consistent).

### Why this is a collection and nothing else

`RF_BeginDestroyed` and `RF_FinishDestroyed` appear **before** the free, in that order, followed by
`LowLevelRename(NAME_None)` and `FreeUObjectIndex`. That is UE's purge pipeline —
`ConditionalBeginDestroy` → `ConditionalFinishDestroy` → `~UObject` → the array slot released — executed
in full. A package unload, a stream-out, or a stray overwrite does not produce that sequence, and it
does not release the array index. Discriminator **B**, then **A** twenty seconds later when the index was
reissued, with **C** concurrent.

⚠ One caveat worth keeping: at `t=188.449` the freed memory briefly held an **in-image** vtable again
(`0x7FF688E04A30`) before reverting to heap residue. `GcAlive`'s "vtable inside the image" test can
therefore transiently pass on memory that has already been freed and reused. It is a sound *dead*
detector, not a sound *alive* detector.

---

## 2. ★★ The poked RootSet bit did not protect the object — and it was zeroed by the free

The object carried `bit30` continuously from `t=187.845` to `t=188.096` (no intervening flag change was
sampled, at a **117 ms aliasing bound**), and was destroyed anyway. The engine then cleared the whole
flag word, `40000004 -> 00000000`, RootSet included, as part of `FreeUObjectIndex`.

So S109's candidate #1 — *"the GC does not honour a directly-poked flag here"* — is **confirmed as an
observation**: an object with `EInternalObjectFlags::RootSet` set and readback-verified went through the
complete destruction pipeline.

⚠ **What is NOT separable from this single run:** whether the bit is *structurally* inert, or merely
arrived too late for a GC pass that had already gathered its root set. The poke landed 151 ms before the
marking phase became visible. S109's runs died 2.1–7.8 s after body build, which is more room, but no
run has yet rooted an asset and then survived a *subsequent* pass. See §5 for the cheap experiment that
separates them.

---

## 3. ★★★ Why everything else the shim rooted survived — and it is not the rooting

Four other objects were poked identically in the same run. **All four survived; both anim instances did
not.** The within-run control is the pair of `AnimSingleNodeInstance`s:

| object | poked RootSet | re-marked at the GC pass | outcome |
|---|---|---|---|
| `BP_Ronin_DefaultSKMeshComponent_C` (class) | yes | `40000004 -> 40000002` | **alive** |
| `BP_Ronin_DefaultSKMeshComponent_C` (component) | yes | `40000004 -> 40000002` | **alive** |
| `A_Ronin_Cosmetic_HeroSelect_Breathe` (AnimSequence) | yes | `40000004 -> 40000002` | **alive** |
| `AnimSingleNodeInstance#189850` | yes | `40000004 -> 40000002` | **alive** |
| `AnimSingleNodeInstance#189868` | yes | *not re-marked* | **destroyed at t=188.046** |
| `A_Ronin_Movement_OutOfCombat_N` (the run anim) | yes | *not re-marked* | **destroyed at t=188.046** |

Two objects of the *same class*, poked by the *same code path*, in the *same GC pass* — one lives, one
dies. The discriminator is not the poke. It is **whether the object-graph traversal reached it**: the
survivors are referenced (the component is owned by the hero actor, the cosmetic anim and the live
instance hang off the component), while the run anim is referenced by nothing but a C global inside the
DLL, which UE cannot see.

**⇒ The fix is not "root harder". It is to give the asset a real reference from a reachable UObject**
(assign it into a UPROPERTY on something live — e.g. the component's own animation slot — or retain the
`FStreamableHandle`), or to reload it on demand when `GcAlive` fails. Rooting has now been measured not
to work in this build, twice: S109 by outcome, S110 by mechanism.

---

## 4. ★★ Three findings about this build that are worth more than the animation bug

### 4a. `UObjectBase` layout — two more fields, calibrated live

`docs/r2-findings.md` records `classOff=0x18, nameOff=0x20` (non-standard; stock is `0x10/0x18`). The
other two are now measured, each against a control that could have failed:

| field | offset | how it was corroborated |
|---|---|---|
| vtable | `0x00` | — |
| **`ObjectFlags`** | **`0x0C`** | `RF_ClassDefaultObject` on **100%** of sampled `Default__*` objects and **0%** of the rest |
| **`InternalIndex`** | **`0x10`** | equals the object's own `FUObjectArray` slot for **400/400** sampled objects |
| `ClassPrivate` | `0x18` | (already known) |
| `NamePrivate` | `0x20` | (already known) |

`ObjectFlags@0x0C` decodes sensibly on sight: every loaded asset reads `0028000B` =
`Public|Standalone|Transactional|WasLoaded|LoadCompleted`. `InternalIndex@0x10` means **an object's array
slot can be read straight out of the object** — no scan needed — which is a cheap primitive for any
future shim.

### 4b. ★★★ "Unreachable" is not a sticky bit in this build — reachability is an ALTERNATING low-bit flag

The stock-UE mental model (`EInternalObjectFlags::Unreachable == 1<<28`, set on garbage) is **wrong here**,
and it is why S109's `flags == 0x00000004` and *"bit 1 is set on 81% of ordinary objects and 0% of
natives — unexplained"* never made sense.

MEASURED: the whole live population carries exactly one of **bits 0, 1 and 2**, and swaps which one on
every GC pass — `bit1 -> bit0 -> bit2 -> bit1 -> …`, with 232 of 256 control objects flipping inside a
single 250 ms sweep. "Reachable" is therefore a **value, not a bit**: an object is unreachable when it
fails to carry the *current* one. Bit 28 was never seen set on anything.

That gives a **GC clock, free and read-only**: six passes in the sitting at `t = 1.0, 62.1, 90.4, 123.1,
188.2, 249.1`. The quiet-period spacing is **61.1 s and 65.1 s**, matching the game's own
`gc.TimeBetweenPurgingPendingKillObjects = 61.1` (recorded at `tutorial_launch.cpp:1204`); the short gaps
(28.3 s, 32.7 s) are the extra collections the tutorial map load forces. The map load itself is visible as
a purge of **125,472 objects** at `t=89.9`.

### 4c. ★★ Rooted and marked are mutually exclusive in the natural population

Over 22,152 sampled live objects at the menu:

```
rooted (bit30)  4915 objects, of which     6 (  0%) carry the current reachability flag
not rooted     17237 objects, of which 17234 (100%) carry it
```

Root-set objects are **excluded** from marking, not marked. So `GcRoot`'s `InterlockedOr` produces a
state — RootSet **and** a reachability value at once — that **0.03% of the natural population is in**.
The shim's rooted objects do not look like the engine's rooted objects; they look like ordinary objects
wearing a RootSet bit, and that is exactly how the GC treated them (§3: all six were traversed, four were
re-marked, two were not and died).

---

## 4d. ★★★ RUN 2 — the phase-locked experiment: INERT, not raced. FK-27 closes.

**Run 1 could not separate** *"the poked bit is structurally inert"* from *"the poke raced a pass whose
root set was already gathered"* — it landed 151 ms before the marking. Prediction registered before the
sitting (`docs/s110-prediction-registered.txt`, RUN 2): Q1 lead > 20 s; Q2 survive ⇒ raced, die ⇒ inert;
Q3 I expect inert.

**Method.** Nothing about the game changed — same DLL, same staging, **only the injection phase**. Stage
the world with `fk24-stage.ps1 -SkipProbe`, read the GC clock `item_watch.py` prints live, and inject the
probe by hand at a chosen point in the cycle. The clock made this predictable: passes land at
`uptime ≈ 73 + 61.1k`, and because the staging pipeline is deterministic **the load phase is nearly
constant across runs** — which is why S109's deaths all clustered 1.1–7.8 s after body build. It was
never that the load provokes a GC (Q4 answered, negative); the load simply always landed at the same
point in the cycle. Shifting the injection by ~35 s moves it anywhere in the period.

**Result — three armed windows, a clean monotone series:**

| run | lead: root → next GC pass | outcome at that pass |
|---|---:|---|
| run 1 (`tut2`) | **0.15 s** | destroyed |
| run 2 (`phase3`) | **2.9 s** | destroyed |
| **run 3 (`phase5`, phase-locked)** | **33.1 s** | **destroyed** |

```
t=277.089  item.Flags 00000004 -> 40000004   [+bit30 RootSet]      poke, readback verified
t=281.080  alive … flags=40000004 gcAlive          ] six consecutive heartbeats, 33 s,
t=286.083 / 291.088 / 296.134 / 301.184 / 306.232 ] nothing touching the object
t=310.170  *** GC PASS #6 *** bit2 -> bit1;  state ROOTED+MARK -> ROOTED+STALE
t=310.322  RF_BeginDestroyed;  NamePrivate -> 0
t=310.525  RF_FinishDestroyed; SerialNumber 63947 -> 0
t=310.878  item.Object -> 0, item.Flags 40000004 -> 00000000       destroyed, 708 ms after the pass
```

**The bit was set and readback-verified 33.1 s before the pass began**, the object sat untouched through
six heartbeats, and the pass destroyed it anyway. A root set gathered 33 s ahead of a reachability pass
that completes inside one 250 ms sweep is not a credible reading. ⇒ **Q2 = inert. Q3 confirmed. FK-27
closes:** poking `EInternalObjectFlags::RootSet` does not enter an object into this build's root set.

**The mechanism, independent of any timing argument** (and replicated in both armed runs): at the pass,
**every** shim-poked object is traversed like an ordinary object. In run 2, six objects all carrying
bit 30 went into pass #5 — four were re-marked (`40000001 → 40000004`) and survived, two were not
(`ROOTED+STALE`) and were destroyed within 3 s. Meanwhile the engine's own ~4,913 root-set objects carry
**no reachability bit at all** and are never marked. A poked object never joins that set; it keeps its
stale mark and is collected on the merits of its references. The bit is a no-op in both directions.

---

## 4e. ★★★ THE FIX — confirmed end to end. The run anim now survives, and locomotion animates.

If rooting is inert and reachability is what matters, the fix writes itself: **put the asset somewhere
the traversal will find it.** `KANIMREF`, one 8-byte write, no new objects, no native call.

**The slot: `USkeletalMeshComponent::AnimationData.AnimToPlay`.** Three reasons that one:
* the component is **reachable and measured to survive every pass** (it is owned by the hero actor);
* the component is **ours** — the shim created it via `AddComponentByClass` — so nothing else reads it;
* `AnimationData` is **unused by us**: the swap drives `PlayAnimation()`, which writes the single-node
  instance's `CurrentAsset`. That is a one-asset slot, and it is exactly why the **idle** anim already
  survived and the run anim did not — the run anim is not the current asset until the walk starts,
  ~20 s after it has already been collected.

Both offsets are resolved **by name** (`PropOffsetSuper` on the component for `AnimationData`, then on
the `SingleAnimationPlayData` `UScriptStruct` for `AnimToPlay` — never "it's the first member"), the
slot must already read as null-or-pointer, and the write is verified by readback. Any failure refuses
and says so instead of putting 8 bytes over playback state.

**MEASURED, one armed window** (`tutorial_launch_play.dll`, `.text 513c6277c3ae88f3`; control arm
`play-noanimref` = `86c07ede88380697`). Predictions R1–R4 registered beforehand; all four held.

```
[REF] SingleAnimationPlayData=0x2AB3DC482C0 AnimToPlay@0x0
[REF] run-anim: AnimationData.AnimToPlay @comp+0xAB8 (struct 0xAB8 + 0x0) 0 -> 2AD3900EE00 OK

t=236.111  item.Flags 00000001 -> 40000001   the GcRoot poke (inert, harmless)
t=241.776  item.Flags 40000001 -> 40000004   *** GC PASS #5: RE-MARKED (bit0 -> bit2) ***
t=302.863  item.Flags 40000004 -> 40000002   *** GC PASS #6: RE-MARKED (bit2 -> bit1) ***
```

**Two full GC passes survived**, the asset tracking the population's reachability value exactly like the
four objects that always survived. It never entered `ROOTED+STALE` — the state that preceded destruction
within ~1 s in all three prior runs. **Zero `[GCW]` lines**: nothing was ever declared dead.

And the point of the whole exercise, from the marker:

```
[ANIM] PlayAnimation(run, loop) ok
[ANIM] PlayAnimation(idle, loop) ok
[ANIM] self-driven walk START
[ANIM] PlayAnimation(run, loop) ok
[ANIM] PlayAnimation(idle, loop) ok
```

Four swaps, **at the default `KAUTOWALKATMS = 20000`** — not the `play-earlywalk` diagnostic that had to
race the collection. The hero walks with real locomotion animation, and the idle screenshots the 20 s
was protecting are back. **`play-earlywalk` has therefore been DELETED** — it existed only to out-run a
collection that no longer happens, and it was the worst of the identical-size artifact pairs (byte-equal
whole-file *and* `.text` sizes with `play`). `-DKAUTOWALKATMS=<ms>` still works for a one-off.

⚠ **`play`'s `.text` hash has moved again: `7bc4df9236ead0ac` → `513c6277c3ae88f3`.** And
`play-noanimref` shares a 161,792-byte `.text` with `play-strictroot`. Diff hashes, never sizes.

---

## 5. What is still open, and the cheap experiments

1. ~~**Inert vs raced.**~~ **ANSWERED — see §4d. Inert.** FK-27 in `docs/ignorance-map-s101.md` is closed.
2. ~~**The real fix.**~~ **DONE AND CONFIRMED — see §4e.** `KANIMREF`, default on in `play`.
3. ~~**Does the load provoke the GC?**~~ **ANSWERED, negative (§4d).** The staging pipeline is
   deterministic and the clock is ~61.1 s from launch, so the load phase was near-constant across runs.
   That, not a load-triggered collection, is why the deaths clustered 1.1–7.8 s after body build.
4. **Bits 0/1/2 as a rotation of three** is an odd design; whether the third value is a real third state
   or something else (e.g. a two-bit counter plus a carry) is unresolved and does not matter yet.

---

## 6. Instrument artifacts caught during this session — all three by controls, before they cost a verdict

`memory/supervive-instrument-artifact-pattern.md`, 13+ instances and counting. Three more:

1. **"`SerialNumber` changes ⇒ the slot was recycled" is WRONG as stated in the S110 sketch.** UE
   allocates serial numbers **lazily**, on first `FWeakObjectPtr`. A live, untouched decoy went
   `0 -> 3373` inside 20 s at the menu with nothing else changing. Caught by the decoy control on the
   *first* smoke run, before any tutorial time was spent.
2. **`SerialNumber N -> 0` is the FREE clearing it, not a reissue.** This one *did* cost a verdict: the
   first tutorial run printed "SLOT RECYCLED" for the run anim when the truth was "FREED". Fixed; only a
   non-zero → non-zero change now counts as a reissue.
3. **`Select-Object -First N` kills the upstream pipeline in PowerShell**, so two probe runs "crashed"
   with exit 255 that had nothing wrong with them. Mine, not the game's.

And the instrument's own gates, each of which can return false: the `InternalIndex` and `ObjectFlags`
calibrations, the `item=` address the shim prints checked against the one the probe computes, 256 decoy
control objects (**1855 events** in the tutorial run — the watcher demonstrably sees change), a printed
**aliasing bound** (117 ms) that every negative claim above is explicitly weaker than, and a **VOID**
verdict when nothing moves anywhere rather than a quiet "nothing happened".

---

## 7. Reproducing

```powershell
# menu, no game time needed -- development, calibration, the population census
python tools\re\item_watch.py --cls AnimSequence --duration 120

# a tutorial sitting: start the watcher first, then stage. It follows every UObject the shim prints.
python tools\re\item_watch.py --marker --duration 900 --post-death 150 --label myrun
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_play.dll -Label myrun
```

`--marker` handles FK-25 (the file is reopened `CREATE_ALWAYS` by every injection: a shrinking file is a
rewind, not an error) and refuses pointers from a stale previous-run marker. Output lands in `docs/` as
`s110-itemwatch-<label>-<stamp>.{log,csv}`.

⚠ Do not read the probe's stdout through `Select-Object -First`; use `-Last`, `Out-File`, or the log file.
