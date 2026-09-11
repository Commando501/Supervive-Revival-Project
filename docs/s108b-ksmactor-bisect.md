# S108b — the leftover-diagnostic bisect: `KSTATICTEST` owns the fault, `KSMACTOR` is exonerated

**Date:** 2026-08-04 · Lead came from `docs/s108-skeptic-review.md` ("3 of 3 runs that got past the
body build die 0.8–10 s after the shim's own `KSMACTOR` `SetStaticMesh` block; free bisect
`-DKSMACTOR=0`"). Every claim tagged **MEASURED** or **INFERRED**.

---

## 1. Result

| arm | `KSMACTOR` | `KSTATICTEST` | `[SMA]` | `[SMT]` | `[ANIM] FAULTED` | `[NULL] fatal` | survival after probe inject |
|---|---|---|---:|---:|---:|---:|---|
| baseline (`play`-derived, 3 markers copied after death) | **1** | **1** | 2 | 2 | **1** | **1** | 50 s – 290 s |
| `play-nodiag` | 0 | 0 | 0 | 0 | **0** | **0** | ~130 s |
| **`play-nostatictest`** | **1** | 0 | **2** | 0 | **0** | **0** | **> 301 s** |

### ★ The fault is attributed, cleanly and single-variably

**MEASURED: `KSTATICTEST` is the sole owner of the `[NULL] 0xC0000005` / `[ANIM] PlayAnimation
FAULTED` pair.** The `nostatictest` arm ran the `[SMA]` `KSMACTOR` block to completion (`SMA=2`) and
still produced **zero** faults. So **`KSMACTOR` is EXONERATED** — the skeptic's lead named the wrong
sibling, and the correct one is its neighbour.

**Mechanism, from the source and confirmed by the faulting registers:** `KSTATICTEST`
(`tutorial_launch.cpp:4960`, default **1**) calls `BuildHeroBody(g_wmHero, smCls, 0, false)` at `:4970`
with `smCls = StaticMeshComponent`, and `BuildHeroBody` unconditionally drives `PlayAnimation` — on a
component that has no animation at all. One marker names the class outright:

```
[NULL] cls RAX=- RBX=StaticMeshComponent RCX=- RDX=- RSI=- RDI=StaticMeshComponent
```

Like `KTESTACTOR` (defaulted to 0 in S106 for the same class of reason), `KSTATICTEST` and `KSMACTOR`
are **S95 spawn-vs-component diagnostics that still default to 1**. They answer a rendering question
that was settled long ago, and one of them faults every run. **Recommendation: default `KSTATICTEST`
to 0.** `KSMACTOR` may stay on; it is measured harmless.

---

## 2. What this does NOT establish — stated so it is not over-read

**The death is NOT attributed.** Survival did not track the flags:

* `nodiag` (both diagnostics OFF) died at **~130 s**;
* `nostatictest` (only `KSTATICTEST` OFF) lived **> 301 s**.

If `KSTATICTEST` were the killer, `nodiag` should have been the *longest* arm. It was the shortest.
With **n = 1 per arm** and a baseline spread of 50–290 s, survival time is dominated by something
else. ⇒ **"Turning off the diagnostic fixes the crash" is NOT established.** What is established is
that it removes an SEH-caught access violation the shim was inflicting on itself every run.

Both bisect deaths went to Sentry's crashpad (`handing control over to crashpad`, no `UECC-*` dir),
and the crashpad minidump for `nodiag1` was **already uploaded and deleted** when I looked ~3 min
later — so neither death has a named frame. That is the S108-c instrument blind spot, now costing
real evidence rather than merely mis-describing it. **A future sitting should copy the crashpad
database aside within ~60 s of a death**, or the dump is gone.

### ⚠ A sampling artifact I nearly committed, again

The bisect arms show a live top-down camera tracking the hero
(`cam=(2852,-541,3201)`, `cam=(-8,-626,3228)`), where earlier runs showed `cam=(0,0,0)`. **That is
NOT evidence the camera was broken before and is fixed now.** The earlier runs contain exactly **one**
`[DIAG]` sample, taken immediately at init before the camera actor is placed; these arms contain
**91**. It is a difference in sampling depth, not in behaviour — the identical error shape to S108-b
in `memory/supervive-instrument-artifact-pattern`. Nothing about the camera is claimed here.

---

## 3. ★ The consequence that actually matters: the hero's walk/run animation was DEAD

**MEASURED, and independently confirmed visually by the user.** The `[NULL]` fault is SEH-caught, so
it never killed the process — which is why it survived so long. What it did instead was quieter and
worse. The handler's response to a faulting `PlayAnimation` is to switch animation swapping off **for
the whole session**:

| arm | `[ANIM]` lines |
|---|---|
| baseline (`KSTATICTEST=1`) | `PlayAnimation(A_Ronin_Cosmetic_HeroSelect_Breathe, loop) ok` → `PlayAnimation(...) FAULTED -> anim swapping DISABLED for the rest of the session` → `run anim A_Ronin_Movement_OutOfCombat_N = 0x…` loaded, and then **nothing**: zero run/idle swaps |
| `KSTATICTEST=0` (both arms) | no fault, then **repeated** `PlayAnimation(run, loop) ok` / `PlayAnimation(idle, loop) ok` cycling for the life of the run |

⇒ **The run animation asset was being loaded and then never played, in every session, because a
leftover S95 diagnostic faulted on a component that has no animation.** The hero slid around without
locomotion animation and it read as "animation isn't wired up yet". It was wired up; a diagnostic was
switching it off. With the flag off the hero walks and runs — the user confirmed this on screen, and
the marker's run/idle cycling is the corresponding measurement.

This is the second time an S9x diagnostic left switched on has quietly damaged every later run
(`KTESTACTOR` built a second degenerate body, S106). **Both were found by asking what the shim itself
was doing, not what the game was doing.**

---

## 4. `KSTATICTEST` now DEFAULTS TO 0 — and the variant table is inverted

Done in `tutorial_launch.cpp:4034`, mirroring the `KTESTACTOR` precedent. `build.ps1` changes with it:
`play-nostatictest` and `play-nodiag` are **deleted** (they would now be byte-identical to `play` and
to `play-nosmactor` respectively — the identical-DLL footgun the table explicitly warns about), and
the control is inverted to `play-statictest` (`-DKSTATICTEST=1`).

**The rename is proven exactly variable-preserving by a three-way hash identity** (MEASURED):

| | new hash | equals | old artifact |
|---|---|---|---|
| `play` | `ae532866e15fd8ac` | **=** | old `play-nostatictest` |
| `play-statictest` | `a67239a0d83d9300` | **=** | old `play` (the long-standing candidate hash) |
| `play-nosmactor` | `23318fa6be628e55` | **=** | old `play-nodiag` |

⚠ **`a67239a0d83d9300` is no longer `play`.** Every earlier document that cites it as "the candidate,
unchanged" now refers to `play-statictest`. The FK-7 A/B baseline moves with it.

Full set after the flip — 10 DLLs, 10 distinct `.text` hashes, `verify_dll.py` **PASS 10/10**:

| DLL | `.text` | sha256[:16] |
|---|---:|---|
| `…_play.dll` ★ candidate | 161,280 | `ae532866e15fd8ac` |
| `…_play_statictest.dll` | 162,816 | `a67239a0d83d9300` |
| `…_play_nosmactor.dll` | 159,744 | `23318fa6be628e55` |
| `…_play_novtguard.dll` | 158,720 | `b931e1de2733aee3` |
| `…_play_testactor.dll` | 161,792 | `88eecc9943ad475f` |
| `…_play_wprobe.dll` | 173,056 | `6bd374e2d81fde3d` |
| `…_play_wprobe2.dll` | 173,056 | `20fa2a7d79bdd748` |
| `…_play_wprobe2_v66.dll` | 173,056 | `f4228a29f9c048cd` |
| `…_play_wprobe_v66.dll` | 173,056 | `40953d51eea081df` |
| `…_play_wprobe_noxformfix.dll` | 173,056 | `28128f5a937e50ca` |

The two previously-stale `wprobe_v66` / `wprobe_noxformfix` builds are regenerated here, so the
"can kill the process" warning on them is **discharged**.

---

## 5. Next

1. Repeat each arm **≥3×** before saying anything about survival; the n=1 arms disagree (§2).
2. Capture the crashpad DB within ~60 s of any death, or lose the dump.
3. Re-run the FK-7 controls against the **new** `play` baseline — the old hash is now a control.
