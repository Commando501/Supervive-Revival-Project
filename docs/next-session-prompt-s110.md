# S110 — start with the SerialNumber probe: is the anim asset COLLECTED, or torn down out of band?

**Read this whole file before touching anything.** Everything below was measured live on
2026-08-04/05 (S109) and is committed on `dedicated-server-stub` (`b7dee38`..`a43f9d8`, all pushed).
Branch is clean, `forceTutorialMatch = false`, nothing running.

---

## 0. ★ TASK ONE — the probe, and why it is the right next move

**The question:** the tutorial hero's run animation dies because its `AnimSequence` stops being a
valid object ~2–10 s after the body is built. S109 established the *when* precisely and eliminated
two explanations. **What is still unknown is the mechanism**, and one read-only probe separates the
three remaining candidates without a single write.

**What `GcAlive` actually tests** (`tutorial_launch.cpp:1392`) — this is the whole ambiguity:

```c
vt = *(uintptr_t*)obj;  if(vt < g_modBase || (vt-g_modBase) > 0x0B000000) return false;  // vtable
if(*(uint32_t*)(obj+NAME_OFF) == 0) return false;                                        // NamePrivate
```

Vtable-out-of-image **or** `NamePrivate == 0`. That fires for a GC collection, a package unload, an
explicit teardown, **or** a slot recycled under a new object. It cannot tell them apart, and every
S109 conclusion about "garbage-collected" rests on it.

**The probe.** Model it on `tools/re/uobjitem_layout.py` (S109, read-only RPM, no injection — it
already has the `FUObjectArray` walk, the FName reader, and the OpenProcess/RPM helpers). Watch ONE
loaded `AnimSequence` from body build across its death, sampling every ~250 ms:

| sample | read from |
|---|---|
| `Flags` | `item+0x08` |
| `ClusterRootIndex` | `item+0x0C` |
| `SerialNumber` | `item+0x10` |
| `*(uintptr_t*)obj` (vtable) | the object |
| `*(uint32_t*)(obj+0x20)` (NamePrivate) | the object |

**The discriminator:**

* **`SerialNumber` changes** ⇒ the slot was **recycled**: the object was really destroyed and the
  index reissued. Decisive for "real destruction".
* **`Unreachable` (bit 28) appears** ⇒ reachability **GC** ran and did not consider it rooted —
  which would prove the poked `RootSet` bit is not honoured.
* **Neither moves** while vtable/NamePrivate go bad ⇒ **out-of-band teardown** (package unload,
  stream-out, explicit destroy) and GC was never involved at all.

⚠ **Sample the SerialNumber BEFORE you need it.** If you only start reading once `GcAlive` fails you
cannot tell a recycled slot from a destroyed one — you need the baseline from t=0.

**How to get a live target cheaply.** You do NOT need a tutorial sitting to develop the probe: the
object array is fully populated **at the menu**. Launch `-NoHook`, attach, iterate. Only the final
measurement needs the tutorial route, because that is where the body-build anim load happens.

---

## 1. What S109 established about this thread — do NOT re-derive it

Full write-up: `docs/s109-dump-forensics.md` §22–§25. Memory:
`supervive-crashpad-capture-runtime-family` (S109 addendum), `supervive-tutorial-crash-fk7`.

1. **The timing is measured.** Run anim collected **6.9 / 6.9 / 7.8 s** after body build (unrooted),
   **5.5 / 2.1 s** (rooted). `KAUTOWALKATMS = 20000` starts the only unattended motion at 20 s, so the
   asset was dead ~13 s before anything asked to play it. That is the whole "no locomotion animation"
   symptom.
2. **`KGCROOT` had been silently INERT since S106** — fixed in `969acef`. Its corroboration was
   `AND(native classes) & ~OR(64 sampled ordinary objects)` on the false premise that ordinary objects
   are never rooted. **19% of them are** (measured), so `P(all 64 clean) = 0.81^64 ≈ 1.2e-6`: the
   guard was **arithmetically doomed**, not unlucky. Now a frequency test (`KGCROOTMAXPCT`, default
   33); `-DKGCROOTSTRICT=1` restores the old one, and `play-strictroot` is a registered control.
3. **⚠ RETRACTED: "rooting fails ⇒ the asset is collected" was only half right.** Fixing the rooting
   gives `rooted=5 failed=0` with every poke readback-verified (`flags 00000004 -> 40000004 OK`) —
   **and the asset still dies, if anything sooner.** The S106-inherited premise that a poked `RootSet`
   bit protects the object is **not established in this build**.
4. **The flag-word layout is CORRECT — that hypothesis is eliminated** (`a43f9d8`).
   `FUObjectItem{Object@0x00, Flags@0x08, ClusterRootIndex@0x0C, SerialNumber@0x10}`, stride `0x18`;
   bit 30 is RootSet-like (**100% on native UClasses, `AND(native)=0x40000000` exactly; 19% ordinary**).
   We were poking the right bit in the right field.
5. **`play-earlywalk` (`-DKAUTOWALKATMS=4000`) makes the swap fire, 3/3 vs 0/3 for `play`** — the
   *ordering* is the proof (same asset pointer resolves → swaps → is then collected). It is a
   **DIAGNOSTIC, not a fix**: it races the collection rather than preventing it, and t+4 s overlaps the
   three idle screenshots the 20 s was protecting.
6. **Unexplained, recorded, not chased:** bit 1 is set on **81% of ordinary objects and 0% of natives**
   and is not a value in the stock `EInternalObjectFlags`.

**This thread is cosmetic locomotion only.** No S109 crash conclusion depends on it.

---

## 2. Traps that will cost you a run

* ⚠ **`play`'s `.text` hash has moved TWICE. Current: `7bc4df9236ead0ac`.** `ae532866e15fd8ac` was
  `play` only between S108b and S109; `a67239a0d83d9300` is `play-statictest`. **Verify by `.text`
  hash, never whole-file and never size** — `play`/`play-strictroot` share a 161,792-byte `.text`, and
  `play`/`play-earlywalk` had byte-identical whole-file *and* `.text` sizes. Use
  `tools/sigbypass-mod/verify_dll.py`, or the inline scanner in `docs/s109-dump-forensics.md` §23.
* ⚠ **FK-25 is still live and it has now cost three comparisons.** `Marker()` opens `CREATE_ALWAYS`,
  and `fk24-stage.ps1` copies the marker **2 s after** each injection — so step-N copies routinely
  capture the file *before the probe wrote anything* (the S108b step-4 copy is **406 bytes**). Do not
  compare marker copies across sessions; read the live `docs/tutorial-launch-marker.txt` after the run.
* ⚠ **`Copy-Item` preserves the SOURCE's LastWriteTime.** Do not derive timings from copied-marker
  mtimes; that is how a "+41,742 s injection gap" appeared in S109.
* ⚠ **Tutorial sittings: budget on ARMED WINDOWS, not launches.** S109 got 3/4, 2/3, 3/3 — better than
  the documented ~2 of 4, but a NOSTAGE attempt is not a data point.
* ⚠ **Set `forceTutorialMatch` back to `false` and rebuild `ags` when done.** It is `false` now.

---

## 3. Everything else S109 settled (so you do not re-open it)

* **FK-9 SOLVED.** Crashpad dumps land in `<GameRoot>\Loki\.sentry-native\`, survive until the **next
  launch** (the "~3-minute window" is **retracted**), and `configs/archive-crashdumps.ps1` now archives
  them automatically pre-launch. Do NOT re-add a post-exit sweep — `& $exe` does not block.
* **The injection burst was the cause of the instrumented-run deaths.** Not shim identity, not `.text`
  patching, not the PI hook — each was exonerated individually. Spacing the secondary manual-maps cuts
  the hazard **~71×** (`P = 8.6e-5`); default `GapSeconds` is now **20** in `inject-secondaries.ps1`
  and `fk24-stage.ps1`. ⚠ **Mitigation, NOT a cure** — residual ~1 death per 3,054 s.
* **Every tutorial death ever captured is the protector** — `runtime.dll+1`, zero SUPERVIVE frames,
  **nine** independent deaths at `pc=0x7FFD3B400001`. **FK-7 has never had a confirmed instance.**
  The bar for any future FK-7 claim: *a dump with SUPERVIVE frames on the faulting stack.*
* **Denominators corrected: 85 / 79 / 74, not 87.** ~13% of the census is protector control flow with
  no game frames and should be excluded from FK-7 analysis entirely.

## 4. Other open leads, in rough value order

1. **`chain = 888cee8 8831758`** — the first Family B specimen carrying SUPERVIVE frames (dump
   `590cfd83`, in `dumps/crashpad-20260804-182004-shimrun3-DEATH`). Matches no known FK-7 family.
   Nobody has looked up those two RVAs. **Cheap and possibly decisive.**
2. **6 chainless-but-parseable UECC dumps** were walked in S109 §11; the other **7 are zero-byte**.
   The `+0x205D` family (6 members) has never been characterised beyond "executes in an unmapped
   64 KB-aligned region".
3. **Anti-tamper vs protector defect is still OPEN** — 487 s ≠ the documented ~285 s integrity kill.
4. **`harvest.py` still enumerates `UECC-*` only** and is blind to the crashpad path. S109 deliberately
   did not rebuild it; the numbers were computed by hand first.

---

## 5. The rule that governed S109, and should govern S110

The session logged **five** instrument artifacts, and **three were mine**: a `strings` gate that
printed "absent (good)" for all four symbols *without ever running* because `strings` is not installed;
a `find | tail -25` read as a corpus fact; arms labelled by shim identity and then read as a mechanism;
a `{12}` format index that silently produced an empty summary for a 90-minute arm; and a VOID rule that
discarded two real deaths because they died before the instrument could measure them.

Each was caught by asking the same question: **is this a fact about the game, or a fact about my
instrument?** Two of them were caught only because the *next* experiment contradicted the last.

So, non-negotiably:

* **A gate that cannot fail is not a gate.** Verify the tool exists and the check can return false.
* **Instrument the variable you are claiming.** `armedPIhook=N` and `observedGaps=[...]` turned two
  assumptions into measurements; without them, two arms would have been scored backwards.
* **Register the prediction before the run**, and keep the control in hand.
* **When a summary column looks clean, check whether the run died before the column could be filled.**

`memory/supervive-instrument-artifact-pattern.md` now carries 13+ confirmed instances. Read it first.
