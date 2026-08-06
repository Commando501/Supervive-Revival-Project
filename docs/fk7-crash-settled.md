# FK-7 SETTLED — the tutorial crash is deterministic, not flaky

**Date:** 2026-07-27 (S106) · **§0 closure decision added 2026-07-29 (S106e)**
**Supersedes the "~2 of 3 launches die, budget retries" framing in 8 places** (banners inserted in each).
**Status:** belief settled FALSE. The **crash fix is NOT closed** — see **§0**, which governs and
overrides the scoreboard in §1.3 and the open-items table in §8 wherever they disagree.

Every claim below is tagged **MEASURED** (I or a prior agent read it out of a dump, a log, a binary, or
the source), **INFERRED** (derived from measurements, could still be wrong), or **OPEN**.

> **Reading rule for this document.** Two diagnosis passes and two skeptic passes fed into it. Where
> they disagreed, **the skeptics won** — that is recorded inline at each point, not hidden. Several
> confident-sounding claims from the diagnosis passes are marked RETRACTED below. They are left visible
> on purpose; the retraction history is the value.

---

# 0. CLOSURE STATUS — **OPEN** (do NOT close)

**Decided 2026-07-29 (S106e).** Two adversarial hunts (writer-attribution, silent-deaths), one
hardening pass and one closure skeptic ran against §1–§8. **The skeptic's verdict governs and it is
DO-NOT-CLOSE.**

| | |
|---|---|
| **FK-7 the BELIEF** (*"flaky, ~2 of 3 die, budget retries"*) | **CLOSED — CONFIRMED FALSE.** Unchanged from §1.1, and now stronger: the RM_PLAY route's real rate is **4 launches / 4 crashes** (§0.2). |
| **FK-7 the FIX** (does the tutorial route survive?) | **OPEN.** **Zero live runs of any fix exist.** |
| **Blocker 1 — who writes the corrupt byte** | **NARROWED, not removed.** One of two candidates falsified; the survivor is unnamed. |
| **Blocker 2 — the 5 dumpless deaths** | **REMOVED.** Not a failure mode — a denominator error (§0.3). |
| **Blocker 3 — the artifact footguns** | **REMOVED.** Verified on disk by two independent passes (§0.4). |

### 0.1 The governing reason, in one paragraph

The camera fix repairs a **symptom** whose **writer is unidentified**, and the corpus now shows the
corruption is **conditional at roughly 1-in-3 to 1-in-2 per launch** — so a quiet run cannot be read as
a repair. Worse, and found only in this pass: **the four camera dumps come from three build vintages,
none of them the candidate's** (§0.2). It is therefore **not yet known that the candidate build
reproduces the bug at all**, which makes the `novtguard` positive control **mandatory rather than
optional**. Closing on a compiled DLL and zero launches would repeat FK-7's original sin — a mechanism
claim with no artifact opened — in the identical shape.

### 0.2 What was established since the first pass

**★ The `+0x3F` delta discriminator does not discriminate. RETRACTED.** (MEASURED, and it was run.)
`delta = (live & 0xFF) − 0x01` whenever byte 0 is replaced by `0x01`, and the live low byte is `0x40`
in **3 of 3** observations — *including the clean control dump*. Both candidate writers emit literally
the same 8 bytes. §7 Step 3's *"⇒ a writer aimed at `&ViewTarget.Target`"* is **false attribution** and
is corrected in place. The line still has value as a **signature match** (*"same bug, not a new one"*),
and nothing else.

**Candidate (b) — the one-byte heap overrun — is FALSIFIED structurally.** (MEASURED + deduction.)
The corrupt byte sits `0x420` bytes **inside the PlayerCameraManager's own live allocation** (PCM+0x00
holds the `APlayerCameraManager` vtable, `.rdata` RVA `0x7EC5B88`; `PendingViewTarget.Target` is a
further `0x820` higher at PCM+0xC40 — both `FTViewTarget`s located independently via the
`FMinimalViewInfo` default signature FOV 90.0 / DesiredFOV 90.0 / OrthoWidth 512.0 at PCM+0x460 and
PCM+0xC80 in all four dumps). **A one-byte overrun writes one byte past the end of its own block; heap
blocks do not overlap.** The only surviving variant is a wild indexed write — and a wild write cannot
land on the same byte of the same object in 4 of 4 launches whose heap bases differ (`0x23A…`, `0x1E6…`,
`0x2639…`, `0x1A56…`). ⇒ **§7 Step 3's *"the `+0.14 s` timing favours the heap-overrun candidate
substantially"* and §8 item 1's same clause are RETRACTED.** They favoured a mechanism that cannot
reach the middle of a live allocation.

**The write is deterministic in value and offset, with zero collateral.** (MEASURED, new.) Low byte of
PCM+0x420 across the four camera dumps: `01, 01, 01, 01`. Low byte of the two neighbouring heap
pointers in the *same* four dumps: PCM+0x390 = `70/40/20/C0`, PCM+0x398 = `00/00/80/80` — normal
pointers' low bytes vary, this one does not, and `0x01` is not a legal UObject alignment. Cross-dump
byte diff of `PCM[0x300..0x480)`: **290 offsets byte-identical in 4/4**; the only differing offsets are
heap-pointer bytes and the POV region. ⇒ rules out a memset, a struct-assign, and any 32/64-bit store,
and gives a live watchpoint a length of **exactly 1 byte**.

**A negative control exists in the corpus and nobody had found it.** (MEASURED.) Only **5 of 86** dumps
capture an `APlayerCameraManager` at all (the minidump dumps memory around register values). Four are
the camera crashes. The fifth — `FF9CF623`, ANIM family, chain `3495973 3405f13 3691a72`,
`SecondsSinceStart=195` — has `ViewTarget.Target = 0x1CB9A088D40`: **8-aligned, low byte `0x40`,
clean**, and `*(void**)Target` = module RVA `0x7F96428` with the **same FName** as the object the
corrupt pointers resolve to at `Target+0x3F`. Two consequences: the view target's identity is now
confirmed **three** ways, and **the write is CONDITIONAL** — a mesh-build session reached 195 s with the
pointer intact.

**The corruption is already present at the top of `DoUpdateCamera` in 4/4, so the writer is not in the
camera chain.** (MEASURED.) `strxref func 0x12C7E2D` → a 95-byte leaf whose only literal is
`Mismatch NumStructBasesInChainMinusOne:…` = `FStructBaseChain` / `UStruct::IsChildOf`, i.e. a `Cast<>`
type check; its caller `0x3C2AD51` is reached from `0x3C34B0C`, and the other family's `0x3C34B22` lies
in the **same `.pdata` extent** `0x3C34AE2..0x3C34B95` — two call sites in one function. And the
`3c5dc52` family's *"POV default, never computed"* state is what `UpdateViewTarget` **itself writes**
(`OutVT.POV = FMinimalViewInfo()` at its top; the same 90/90/512 triple sits untouched in
`PendingViewTarget.POV`). ⇒ **§2.4's split is an artifact and §8 item 6 is retired *as a mechanism
question*** — same corruption, consumed at two points in one frame.

> ### ⚠ 0.2a — BUT the sub-family split is CONFOUNDED WITH BUILD VINTAGE, and that is why the positive control is mandatory
>
> **MEASURED by the closure skeptic, re-verified here from `crash_census.csv` mtimes + `git log`:**
>
> | sub-family | dumps | local time | build window |
> |---|---|---|---|
> | `12c7e2d` | `B61ED1A7`, `AABE886D` | 07-24 14:45:35, 07-26 01:44:54 | **before** `a8d23f2` |
> | `3c5dc52` | `BE345EC2`, `7E6FDF97` | 07-26 04:29:11, 07-26 04:39:25 | **after** `a8d23f2` (between `2921ac5` 04:23 and `d61d325` 04:44) |
>
> `a8d23f2` (*"S99b: idle animation VERIFIED; run animation; GAS scope corrected"*, 07-26 02:27) falls
> **exactly between the two cohorts**. The split correlates perfectly with build vintage and **cannot be
> resolved from the corpus** (INFERRED). The mechanism argument above is structurally sound, but if they
> *are* two bugs the guard may repair one and not the other. And the candidate is **≥4 commits plus all
> uncommitted S106d work past both cohorts** ⇒ **it is not yet known that the candidate build reproduces
> FK-7 at all.**

**Blocker 1's residue, stated honestly.** The writer is **NOT named**. What is boxed: *a deterministic
**1-byte** store of the literal value **`0x01`** at a **fixed displacement from the PCM**, ~0.15 s after
the body build, **outside** the camera chain, **conditional** per launch, with **zero** collateral.*
The instruction-shape search is now **exhaustive over the decrypted half** of `.text` for every
byte-width store form at `disp32 == 0x420` (`C6 /0` imm8, `88 /r`, `80 /1|/4|/6` imm8, `0F 9x` setcc,
each ± REX): **34 sites, 8 with imm8 == 1**, three of them `rbp`/`r13`-based (large stack frames, not
object fields), the rest in Slate (`0x14B7F60`), a minimap plugin (`0x4953C00`) and four literal-free
functions. Not a negative result (`.text` is 52.29% decrypted) — and note the real search space is
**wider** than `disp32==0x420` anyway, because the structural finding fixes the **address**, not the
encoded displacement. **Offline effort on this encoding is now spent.**

**★ ROOT-CAUSE-GRADE CODE DEFECT FOUND AND FIXED — the spawn `FTransform` was truncated at
`Scale3D.Z`.** (MEASURED.) `SpawnActorCls` and `DoSpawnSeq` copied `const uint32_t xfsz=0x50` out of an
FTransform whose aligned layout in this build puts `Scale3D` at `0x40/0x48/**0x50**` — truncating
**exactly at `Scale.Z`**. Every actor `SpawnActorCls` ever produced spawned at `(x, y, **0**)` —
*including the top-down `CameraActor` that becomes `ViewTarget.Target`* (at `(1,1,0)`), the KTESTACTOR
body actor `(1,1,0)`, and the KSMACTOR StaticMeshActor `(3,3,0)`. Four call sites additionally wrote
`Scale3D` at the pre-S98 offsets `0x38/0x40/0x48`. **★ And a third instance the hunt had not found:**
`BuildHeroBody`'s `savedXform[0x50]` + `memcpy(…,0x50)` made the deferred `FinishAddComponent`
**re-apply `Scale.Z = 0` at component registration**, silently undoing the S98
`RelativeScale3D=(1,1,1)` fix ~55 lines earlier. **⇒ the standing order-of-operations question
("does the body get built BEFORE the `Scale3D=1` fix lands?") is answered: YES — registration
overwrote the fix.** All of it is now behind `KXFORMFIX` (default **1**), with `[XF]` instrumentation
logging the copy size, the scale offset, and the `Scale3D` **registration actually receives**, tagged
`*** DEGENERATE ***`.

**Half the "perfect separation" antecedent was a false-known.** (MEASURED.)
`LogPhysics "Scale3D is (nearly) zero"` appears in **0 of 14** log files, and `LogPhysics` itself in
**0 of 14** — the string exists in the image (`.rdata 0x0817DAF0`, refs=1) and is simply never emitted.
**No degenerate *physics* body is ever reported; only cloth is.** `LogChaosCloth` fires exactly **1×**
in each of the four crashing sessions and **0×** in each of the five non-crashing ones, always
immediately after `FlushAsyncLoading(2523)`, and its object name is **EMPTY** in this shipping build —
**so the warning cannot tell you which body it is about.** ⇒ §4.3's second-order finding and §8 item 5
are corrected in place: the count is cleanly **ONE** body, and the shim's `ClothingSimulationFactory =
null` is both **mis-ordered and inert** (UE repopulates it from
`p.Cloth.DefaultClothingSimulationFactoryClass` at `OnRegister` — which is why the log names **Chaos**
while `:3257` says Ronin's mesh carries the **Nv** factory). **INFERRED**, from UE semantics.

**`KTESTACTOR` was a leftover S94 diagnostic building a SECOND, degenerate skeletal body — now default
OFF.** (STRONG_INFERENCE.) The hero's body cannot be the degenerate one (its parent is the **game's
own** pawn at `(1,1,1)`, `tutorial_launch.cpp:1013`, and the S98 component fix applies); the test
actor's cannot be anything else (its parent spawns at `(1,1,0)` per the defect above, so its
`ComponentToWorld` scale is non-uniform whatever its relative scale is — and `SetWorldScale3D(1,1,1)`
on a zero-Z parent drives `RelativeScale3D.Z` **back to 0** via UE's `GetSafeScaleReciprocal`).

**Blocker 2 — the 5 dumpless deaths are a DENOMINATOR ERROR, not a failure mode. REMOVED.** (MEASURED;
independently re-verified by the skeptic.) The 9 "tutorial sessions" are **two different experiments**:
all 4 crash logs have `FlushAsyncLoading=5, LogChaosCloth=1` with flush #5 at T+173.5…177.2 s; all 5
dumpless logs have `=4, =0` and **no 5th flush at any time** — so §4.3 was measuring the **shim MODE**,
not a cloth variable. `docs/tutorial-launch-marker.txt` is **tracked in git**, and
`git show <commit>:docs/tutorial-launch-marker.txt` recovers 3 of the 5 directly: all three ran
**RM_SPAWNPOSSESS** and all three **ran to completion** (`[SP] done step=4 …`), with the commit landing
**+3 s, +3 s, +9 s** after that session's own last log line. The remaining 2 died at T+148.5 s and
T+165.9 s — **before** the T+173.5 s mesh build that is the necessary antecedent of both families.
Every alternative mechanism was excluded (`ConsoleCtrl`=0 and `INTERRUPTED`=0 in all 11 logs though
UE's handler exists; no `fastfail`/`gsfailure`/`LowLevelFatalError`; no hang — final-20 s cadence 30.0,
225.2, 30.0, 29.9, 51.8 fps with no timestamp gap > 0.6 s, and one session logged an HTTP request 16 ms
after its last log line). **Four positive controls** show the same zero-exit-marker tail in sessions
with **no tutorial shim at all** (07-26 09:22 and 20:16 menu-only, plus 07-05 `Loki_3`/`Loki_4`). ⇒
**§4.4 and §8 item 2 are RETRACTED.** The integrity-check confound (§8 item 3) is **re-scoped**: it
never operated in any of the 9 sessions (patch uptime 60–79 s vs the ~285 s observed kill latency) and
its signature is a **dump** at the fixed poison address `0x7FF90E000001` (present exactly once in the
corpus), not a silent death — but it **is** a live hazard for the T+300 s hold (§0.5 stop rule).

**Two zero-cost family discriminators, usable live without opening a minidump.** (MEASURED, 2/2 and
2/2.) The `RequestExit` reason string: `FRunnableThreadWin::GuardedRun.ExceptionHandler` = **ANIM**
(worker) vs `LaunchWindowsStartup.ExceptionHandler` = **CAMERA** (game thread). And the screenshot
count in `Saved/Screenshots/WindowsClient` — `KSHOT` fires at {3000, 8000, 14000, 22500} ms after the
body build, so **3 PNGs** = an ANIM session killed at +20.2 s before shot 4, **0 PNGs** = a CAMERA
session killed at +0.15 s.

**★ MEASURED — the camera bug is CONDITIONAL, at roughly 1-in-3 to 1-in-2 per launch.** Grouping the
corpus by PID and local time: cohort 07-26 04:09–04:55 = **2 camera / 4**; cohort 07-26 01:44–02:24 =
**1 camera / 5**. The ANIM sessions reached **194–201 s** — they **passed through** the 173–185 s camera
window unharmed. ⇒ `P(quiet camera outcome | guard does nothing) ≈ 0.5–0.8`. **A single quiet run is
nearly uninformative**, which is why §0.5 gates every read on the guard's own detection line.

### 0.3 Blocker 2's residue — filed, not dropped

Nothing about the dumpless deaths needs explaining for FK-7 to close: **all 5 lack the necessary
antecedent** (the mesh build) for both crash families, so they are outside FK-7 **by construction**.
What *does* deserve a permanent item is the **instrument** that made the denominator error possible —
`Marker()` opens with `CREATE_ALWAYS` (`tutorial_launch.cpp:4919`), so every injection truncates
`docs/tutorial-launch-marker.txt` and a session's mode survives only by accident of someone committing
the file. Two sessions are now **permanently mode-unattributable**. **Split out as FK-25** (§0.6).

### 0.4 The hardened artifact matrix — 6 DLLs, 6 distinct `.text` hashes

**All rows MEASURED on disk 2026-07-29 by two independent passes** (PE parse + string counts + section
hashes). Footguns A/B/C from §5.7 are **gone**: `_play_gcroot.dll` (the self-A/B) and
`_play_vtguard.dll` are **deleted**; `play` is a **fresh** build (was the stale pre-fix binary);
`nogcroot` is now **single-variable** (`[PIM]` stays 4). All six: `verify_dll.py` **PASS**, imports
**KERNEL32 + USER32 only**, **zero** CRT, **zero** `__CxxFrameHandler` / `_CxxThrowException` /
`__C_specific_handler`. All 23 `RunMode`s preserved (`RM_FORCEOPEN=0 … RM_PLAY=22`).

| DLL (`tools/sigbypass-mod/`) | Δ vs `play` | isolates | bytes | `.pdata` | `.text` sha256 | VTG | GC | GCW | PIM | XF | testbody |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| `tutorial_launch_play.dll` | — **the candidate** | all four fixes ON | 236,544 | 442 | `a67239a0` | 8 | 8 | 4 | 4 | 2 | 0 |
| `…_play_novtguard.dll` | `KVTGUARD=0` | **the camera guard** — ★ positive control | 232,448 | 439 | `7bb7c67e` | **0** | 8 | 4 | 4 | 2 | 0 |
| `…_play_nogcroot.dll` | `KGCROOT=0` | the anim GC-root arm (§7 Step 6) | 230,400 | 438 | `c347bf64` | 8 | **2** | **1** | 4 | 2 | 0 |
| `…_play_nopimutex.dll` | `KPIMUTEX=0` | the PI-hook mutex only | 235,520 | 441 | `cd7fb6a0` | 8 | 8 | 4 | **0** | 2 | 0 |
| `…_play_noxformfix.dll` | `KXFORMFIX=0` | **the spawn-`FTransform` fix** — reproduces the old `Scale.Z=0` | 236,544 | 442 | `ad76bf92` | 8 | 8 | 4 | 4 | 2 | 0 |
| `…_play_testactor.dll` | `KTESTACTOR=1` | **the 2nd, degenerate skeletal body** — restores the S94 diagnostic | 237,056 | 442 | `321c71de` | 8 | 8 | 4 | 4 | 2 | **1** |

> ⚠ **`play_noxformfix` is identical to `play` in size AND `.pdata` count** — by design, because
> `KXFORMFIX` only changes folded constants. **Its distinctness rests solely on the `.text` hash
> `ad76bf92` vs `a67239a0`**, recorded here for exactly that reason: anyone eyeballing the directory
> will think it is a duplicate. Proven distinct two further ways: a same-named rebuild differs in
> **142,617 bytes** (140,869 in `.text`), and the emitted asm references `g_xform+56` (`0x38`, the bug
> offset) **4× with `=0` and 0× with `=1`**. Determinism control: rebuilding `play` with identical flags
> to an identical name differs in **2 bytes** (PE `TimeDateStamp`).

> ⚠ **18 other `tutorial_launch_*.dll` in that directory are pre-S106d and UNREPRODUCIBLE**
> (`tutorial_launch.dll`, `_camera`, `_meshcam`, `_quest`, … dated 07-12 … 07-24). They were built with
> ad-hoc `-D` flags that have no `$Variants` entry, so `build.ps1` cannot regenerate them, and they
> still carry the `0x38` scale bug and the `s_tries` latch. **Do not reach for an un-suffixed name.**

**Source-side fixes verified in `tutorial_launch.cpp`:** `s_tries` promoted to file scope as
`g_vtTries` (`:1048`) **and reset in the stand-down path** (`:1108`) — the reset is the actual fix, the
promotion only enables it — plus a reset on successful resolve (`:1063`) so the 200-hit budget is
per-attempt. `KXFORMFIX 1` (`:167`) with `kXfScaleOff` (`:170`), `kXfSize` (`:172`) and `XfSize()`
(`:182`) replacing every hard-coded `0x50`; the `BuildHeroBody` bound check raised `0x50 → 0x60` (at
`0x50` a high-offset param would have passed the check and overrun `g_gsbuf`). `KTESTACTOR 0` (`:2860`).
⇒ **§8 item 7 is CLOSED.**

> ⚠ **Residual, MEASURED, not a blocker:** `DoCheatSpawn` (`:4335`) still hand-rolls `xfsz` (with a
> correct `0x60` fallback) and `memset`s `g_xform` **without ever writing `Scale3D`** ⇒ its spawns get
> `Scale3D = (0,0,0)`. Gated to `RM_CHEATSPAWN` (`:514`), so it is **off the RM_PLAY path** — but it is a
> fourth instance of the family `KXFORMFIX` closed. Fix when RM_CHEATSPAWN is next touched.

**Three flags the candidate still leaves ON** (`KCHEATSPAWN` `:2872`, `KSMACTOR` `:2878`,
`KSTATICTEST` `:2881`) — all S94-vintage, all executing inside the **single** post-build hook hit
(`if(!g_plInit)`), together spawning an extra StaticMeshActor, an extra StaticMeshComponent and a
cheat-RPC-spawned `BP_HERO_Ronin_C` right in the +0.15 s window. **If the writer lives in one of those
three, the candidate still contains it and the guard is masking it** — the exact "repair a symptom"
failure. §0.5 Run 5 bisects them.

### 0.5 THE VERIFICATION RUN — ordered, single-variable, ready to paste

**~50 min, 4 launches, every outcome interpretable.** Nothing here patches `.text` persistently or
touches game files. Read §0.4 first; do not reach for an un-suffixed DLL name.

```powershell
# ── REVERT POINT 0: rebuild the matrix from source, then confirm it is single-variable ──
cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"
.\build.ps1 -Name tutorial_launch          # rebuilds all 14 registered variants in place
python verify_dll.py tutorial_launch_play.dll tutorial_launch_play_novtguard.dll
```
**One-bit gate:** both `VERDICT: PASS`, and the `.text` sha256 of every row in §0.4 is **distinct**.
Anything else ⇒ the A/B is not single-variable; **stop**.

---

**RUN 0 — the free log read. DO THIS FIRST; it changes what the A/B means.** (~4 min, no crash needed,
no marker needed, the session need not survive.)

| | |
|---|---|
| DLL | `tutorial_launch_play_testactor.dll` (`KTESTACTOR=1`) vs `tutorial_launch_play.dll` (`=0`) |
| hold | until past the mesh build (T+180 s) — that is all |
| read | `grep -c LogChaosCloth "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"` (delete the log first) |

**One-bit:** `testactor` → **1** and `play` → **0** ⇒ the single degenerate cloth body was the **leftover
S94 test actor's**, and `KTESTACTOR` is the real antecedent. `play` → **1** ⇒ it is the **hero's** body
and the remaining scale defect is elsewhere in `BuildHeroBody`. *Either answer is worth more than the
next three runs and costs less.*

---

**RUNS 1–2 — the POSITIVE CONTROL. Mandatory (§0.2a), not optional.**

| | |
|---|---|
| DLL | `tutorial_launch_play_novtguard.dll` — inject `gft_ready_fix.dll` first |
| hold | **T+220 s** (clear of the 173–201 s band, short of the integrity window) |
| read | fault RVA via `python tools\crashtri\harvest.py`; **which sub-family**; the `RequestExit` reason string; screenshot count |

**One-bit:** ≥1 of the 2 runs dies at RVA `3c5dc52` **or** `12c7e2d`
⇒ **the candidate's build vintage reproduces FK-7** and Runs 3–4 are meaningful.
**Both runs quiet ⇒ THE WHOLE SITTING IS VOID.** The vintage no longer reproduces the bug; **do not
read Runs 3–4 as a pass.** Re-open with the writer probe (§0.6 FK-24) instead.

---

**RUNS 3–4 — the fix run.**

| | |
|---|---|
| DLL | `tutorial_launch_play.dll` — inject `gft_ready_fix.dll` first |
| hold | **T+300 s** |
| read | `docs\tutorial-launch-marker.txt` — **and commit it after each run** (§0.3) |

**Gate (from §7 Step 1, still binding):** the line `[VTG] pcm=0x… ViewTarget@0x…` must appear, reading
**`(reflection)`** with offset `0x420`. Absent ⇒ **run VOID**, the guard never resolved.
**`FALLBACK CONSTANT`** ⇒ every offset-derived conclusion in §2 needs re-checking first.

**One-bit — detection-gated, and this is what makes n=2 sufficient instead of n≈6:**

| outcome | verdict |
|---|---|
| quiet past T+300 s **AND** `[VTG] *** ViewTarget.Target INVALID … lowbyte=0x01` present in **both** | ★ **the strongest available close** — symptom repaired under demonstrated corruption; writer still unidentified |
| quiet **WITHOUT** `[VTG] INVALID` | **VOID, not a pass.** The writer never fired — ~50–80% likely by chance (§0.2). Re-run. |
| `[VTG] INVALID` fires **and it still dies at** `3c5dc52`/`12c7e2d` | the guard is **racing** the writer. Blocker 1 becomes **mandatory**; go to §0.6 FK-24. |
| `[VTG]` repairs in **bursts of hundreds** | the writer re-corrupts every frame, or the guard is writing into a torn-down PCM. **Revert to `novtguard`** (§7 rollback). |
| death at a **fixed unmapped RIP in the `0x7FF90E000001` family** | **integrity kill — run VOID.** See the stop rule. |

**Also required in Runs 3–4** (positive controls carried from §7 Step 2, survival is necessary not
sufficient): the four `KSHOT` screenshots show the hero **in frame**; logged hero + camera world
positions are **finite** with the camera **above** the hero; **no** `[GCW] *** … WAS
GARBAGE-COLLECTED` line; and the new `[XF]` lines report `Scale3D` **`(1,1,1)`, not `*** DEGENERATE ***`**.

---

**RUN 5 — only if Runs 3–4 land in the "guard is racing the writer" row.** Bisect the three leftover
S94 diagnostics still ON, **one variable at a time**, most-to-least suspicious:
`-DKSTATICTEST=0`, then `-DKSMACTOR=0`, then `-DKCHEATSPAWN=0`.
**One-bit:** the `3c5dc52`/`12c7e2d` fault **and** the `[VTG] INVALID` line both stop on **exactly one**
flag ⇒ that block contains or triggers the writer.

---

**⛔ STOP RULE.** Halt the sitting and write up on **any** of:
1. **Runs 1–2 both quiet** — void by construction; nothing to validate (§0.2a).
2. **Any death at a fixed unmapped RIP** (`0x7FF90E000001` family) — integrity kill, not a guard
   failure. RM_PLAY holds its 5-byte `ProcessInternal` patch for the full **600,000 ms**
   (`tutorial_launch.cpp:5145`) against a **~285 s** observed kill latency
   (`docs/session-43-scan-on-browse.txt:72`), so at T+300 s the margin is only ~100 s. **Shorten the
   hold to T+220 s and re-run** rather than reinterpreting. Log the wall-clock instant of `InstallHook`
   so patch uptime is separable from process uptime.
3. **`[VTG]` bursts of hundreds**, or the guard-armed run dying **earlier** than the control.
4. **Three consecutive VOIDs** of any kind — the harness, not the fix, is the problem.

**Capture per launch, without exception:** `Loki.log` (delete before each run), the wall-clock injection
time, `docs\tutorial-launch-marker.txt` (**and `git add` + commit it** — FK-25), the 5th
`FlushAsyncLoading` timestamp, the `LogChaosCloth` count, the `RequestExit` reason string, the
screenshot count, process uptime at death, and `python tools\crashtri\harvest.py`.

**REVERT POINTS.** (i) Guard off with **no source edit**: `-DKVTGUARD=0` / use `_play_novtguard.dll`.
(ii) Scale fix off: `_play_noxformfix.dll`. (iii) Full stop: **stop injecting and relaunch** — the guard
is data-only reads plus one aligned 8-byte store, all in-process; there is no game-file or config state
to undo.

### 0.6 What was SPLIT OUT — so it cannot be lost

Both are filed in `docs/ignorance-map-s101.md` §2 in the same table style as FK-1…FK-23.

| item | what it is | why it left FK-7 |
|---|---|---|
| **FK-24 — the writer of the corrupt byte** | *Belief:* the writer is one of two candidates and the `+0x3F` delta discriminates them. *Actual:* the delta is allocator-forced (3/3), candidate (b) is structurally impossible, candidate (a) is unnamed. Carries the **DR-watchpoint probe** — a 1-byte hardware write watchpoint on `&PCM->ViewTarget.Target` armed after the body build and caught by the VEH the shim **already installs** (`CrashVEH`, `:391`); data-only, no `.text` patch, no C++ EH. ⚠ Packed builds commonly poll/clear DR registers — if `Dr7` reads back zero, or the trap never fires while `[VTG]` still repairs, the probe is **void** (itself a one-bit result); software fallback is a ~1 s `PAGE_READONLY` flip on the PCM page. | It is a **live-instrumentation RE question with its own probe and its own risk of being void**, not a step in verifying a built fix. It will outlive FK-7's close either way. |
| **FK-25 — session-mode attribution is not durable** | `Marker()` uses `CREATE_ALWAYS` (`:4919`), so every injection truncates `docs/tutorial-launch-marker.txt`. A session's mode + flags survive only if someone commits the file. **This produced the Blocker-2 denominator error**, and 2 of 9 sessions are permanently mode-unattributable. Fix: append with PID + wall-clock, or write per-PID markers. | It is an **instrument defect that manufactures false-knowns**, orthogonal to the crash. Cheap, and it prevents the next denominator error. |

### 0.7 Method note — FK-7's original sin, and the general fix

FK-7 began as *"~2 of 3 launches die"* — **a mechanism claim (stochastic failure) built from an outcome
rate, with no crash ever opened.** One `mdctx.py` run inverted it. **The general fix: open the artifact
before describing the mechanism.** A rate is a symptom; a chain, a faulting operand and a byte are a
mechanism.

That rule has now bitten **five more times inside this investigation**, always in the same shape — *an
instrument's artifact recorded as a property of the game*:

| the artifact | what was claimed about the game |
|---|---|
| `LogGarbage` never checked for (0 files) | *"the trigger is the first GC after map load"* — refuted (§3.4) |
| `delta = live − corrupt`, allocator-forced | *"`+0x3F` ⇒ a writer aimed at the field"* — retracted (§0.2) |
| `LogPhysics` string never emitted (0/14) | *"a degenerate physics body"* as half the antecedent — retracted (§0.2) |
| `UpdateViewTarget`'s own `POV` reset | *"two sub-families ⇒ two bugs"* — an artifact (§0.2), though **still build-confounded** (§0.2a) |
| shim MODE varying with `FlushAsyncLoading` count | *"cloth==1 ⇒ crash"* as a **cloth** law — it was a **mode** law (§0.2) |

**The operational consequence for §0.5:** every one-bit criterion is gated on a **positive detection
line the instrument itself emits** (`[VTG] INVALID`, `LogChaosCloth`, `[XF] DEGENERATE`, the fault RVA),
never on the **absence** of a bad outcome. Absence of a crash in a bug that fires ~50% of the time is
not evidence, and this document's own §7 Step 2 had to be re-gated twice before that was true.

---

## 1. Verdict

### 1.1 The belief is false

> *"The tutorial route is flaky — ~2 of 3 launches die on the first shim. Budget retries."*

**FALSE as a description of mechanism. Roughly right as an outcome rate, for reasons that are not
random.** MEASURED, from `tools/crashtri/crash_census.csv` (86 dumps) and re-derived by me:

| measurement | value |
|---|---|
| dumps in corpus | 86 |
| dumps carrying a game-frame chain | 73 |
| **distinct full chains among those 73** | **34** |
| crashes sharing their full chain with ≥1 other crash | **50 / 73 = 68%** |
| largest repeat groups | 17×, 7×, 5×, 4×, 4×, 3× |

A stochastic failure does not produce byte-identical return-address chains across independent launches
with different ASLR-era heap states. **68% of chained crashes are exact repeats of another crash.**

In the FK-7 window specifically (2026-07-24 → 07-26), **all 10 crashes fall in a 28-second band**:

```
07-24 14:45  194s  12c7e2d 3c2adb9 3c34b0c 3c596b3 39c7884 37f8b8c …   CAMERA family
07-26 01:44  185s  12c7e2d 3c2adb9 3c34b0c 3c596b3 39c7884 37f8b8c …   CAMERA family
07-26 01:50  195s  3495973 3405f13 3691a72 3691704 367b462 f84697 …    ANIM family
07-26 02:11  196s  34713aa 3496da2 34178ba 3405efc 3691a72 3691704 …   ANIM family
07-26 02:19  194s  349596d 3405f13 3691a72 3691704 367b462 f84697 …    ANIM family
07-26 02:24  201s  3495973 3405f13 3691a72 3691704 367b462 f84697 …    ANIM family
07-26 04:09  195s  3495973 3405f13 3691a72 3691704 367b462 f84697 …    ANIM family
07-26 04:14  194s  (no frames — Rip=0, EXECUTE @ 0)                    ANIM family by regs
07-26 04:29  175s  3c5dc52 3c5d255 3c34b22 3c596b3 39c7884 37f8b8c …   CAMERA family
07-26 04:39  173s  3c5dc52 3c5d255 3c34b22 3c596b3 39c7884 37f8b8c …   CAMERA family
```

Ten crashes, 173–201 s, **two stack families**. That is the opposite of flaky.

> ### ⚠ CORRECTIONS 2026-08-05 (S111) — the band reproduces; two things about it do not.
> Source: `docs/fk8-crash-timing-mined.md` §3.5, §4.1. Both re-verified in-session.
>
> 1. ❌ **"ANIM family" is a MISNOMER, and it is not two members but one.** `0x3495973` and
>    `0x349596d` resolve to **the same function `0x3494B40`** (4,336 B, an **EXACT** `.pdata` extent
>    from minidump stream 13). Its string literals are `"Ticking Group [%s] GroupLeader [%d]"` and
>    `"Invalid position from Leader %d. Trying next leader"` — it is the **tick task-graph
>    dispatcher**, which matches its `Foreground Worker #0` crashed thread. There is no animation code
>    in this family. Reproduce in seconds: `python tools/strxref/strxref.py func 0x3495973`.
>    (The positive control for that tool: `0x3ee9cf5` → `UEngine::LoadMap`, which agrees with the
>    row's own assert file.)
> 2. ⚠ **Effective N is ~2, not 10.** Nine of these ten rows are a **single 2 h 55 m sitting**.
>    Independence was assumed and does not hold.
> 3. ⚠ **The band is in the LAUNCH clock**, which carries the operator's staging schedule (measured
>    +33.0 s July→August). The band is era-B-specific. Re-anchored to `Load map complete
>    …/LVL_Tutorial`, era-B deaths are **49.5–73.5 s after the map load** — use that form. ⚠ Two
>    independent re-anchorings **disagree** (73.1→88.8 s vs 49.5–73.5 s); until that is adjudicated
>    (write-up §7.1) **do not cite either re-anchored number as settled**.

### 1.2 The two signatures

| | **Family A — worker thread** | **Family B — game thread** |
|---|---|---|
| count in window | 6 | 4 |
| thread | task-graph worker (`Foreground Worker #0/#1`, `Background Worker #5`) | GameThread |
| subsystem | `FAnimSync::TickAssetPlayerInstances` | `APlayerCameraManager` per-frame camera update |
| fault | virtual dispatch `call [rax+0x2F8]` through a **freed `UAnimationAsset`** | virtual dispatch `call [rax+0x700]` through a **corrupted `ViewTarget.Target`** |
| mechanism | **use-after-free** (MEASURED — destructed object) | **single-byte pointer corruption** (MEASURED — *not* a UAF) |
| trigger | +20.2 s after the mesh/body build | +0.15 s after the mesh/body build |
| shared antecedent | **the shim's blocking mesh load** (MEASURED, perfect separation — §4.3) | same |

**They are NOT the same bug.** Different threads, different objects, different mechanisms, different
latencies. Two fixes are genuinely required; neither closes the other.

### 1.3 The honest scoreboard

| item | status |
|---|---|
| "flaky / stochastic" belief | **SETTLED FALSE** (MEASURED) |
| Family B (camera) — diagnosis | **SETTLED to the field, the object, and the byte** (MEASURED) |
| Family B — fix | **WRITTEN + COMPILED, NOT LIVE-VERIFIED** |
| Family B — the *writer* of the corrupt byte | **OPEN** — not reachable offline |
| Family A (anim) — diagnosis | **object identified, mechanism identified** (MEASURED) |
| Family A — fix | **WRITTEN + COMPILED; causal premise UNCONFIRMED** (§3.4) |
| Third failure mode (dumpless deaths) | **UNTOUCHED, and it is ~half the observed rate** (§4.4) |
| Build system | **EXISTS, reproduces committed DLLs byte-for-byte** (MEASURED) |

**FK-7 is at best HALF closed.** A compiled DLL is not a fixed bug.

> **⚠ 2026-07-29 (S106e): two rows of this scoreboard have moved — see §0.** *"Third failure mode
> (dumpless deaths)"* is **RETRACTED** (not a failure mode — §4.4 banner). *"Family B — the writer"* is
> **SPLIT OUT as FK-24**, narrowed but unnamed. *"Build system"* now reads **6 single-variable DLLs, 6
> distinct `.text` hashes** (§0.4). The headline sentence is unchanged and still governs: **a compiled DLL
> is not a fixed bug, and zero live runs exist.**

---

## 2. Family B — the GameThread camera crash

### 2.1 The chain, every frame named by measurement

Previously this chain was "INFERRED identification" with one frame explicitly unidentified. It is now
named end to end. **MEASURED**, via `tools/re/vtables.py` against `dumps/merged.dump.exe`
(ImageBase `0x7FF6AF000000`, file offset == RVA):

```
FEngineLoop::Tick
 └ UGameEngine::Tick                          0x37F8820  (slot 96 of UGameEngine + ULokiGameEngine vtables)
    └ UWorld::Tick(LEVELTICK_All)             0x39C6E70  (direct call, edx=2; strings: ConnectionFailed,
      │                                                   "Your connection to the host has been lost.")
      └ APlayerController::UpdateCameraManager           (tail-call)
         └ APlayerCameraManager::UpdateCamera            slot 260
            └ DoUpdateCamera                             slot 280
               └ UpdateViewTarget                        slot 286
                  └ UpdateViewTargetInternal  0x3C5DBC0  slot 312
                     └ Target->CalcCamera     0x33790F0  slot 224  ← FAULTS
```

Corroboration, all MEASURED:
- `0x3C59650 / 0x3C349A0 / 0x3C5CFC0 / 0x3C5DBC0` are slots 260/280/286/312 of **one** vtable at
  `.rdata 0x07EC5B88`, independently named `APlayerCameraManager` (`vtables.py who 0x7EC5B88`,
  313 slots).
- The byte before each return address is `call [rax+0x820 / 0x8C0 / 0x8F0 / 0x9C0]` — **the same
  slots**. The displacements chain exactly.
- Slot 224 (`+0x700`) → `0x33790F0`, whose body is `test byte [rcx+0x6A],0x20` plus a 0x128-byte stack
  buffer = `AActor::CalcCamera`'s `bFindCameraComponentWhenViewTarget` + `TInlineComponentArray`.
  It appears at slot 224 of **295** vtables — i.e. it is the non-overridden default.
- Live from the dumps: `rbx − rdi == 0x420`, `r8 == rbx+0x10`, `[rdi] == ` the `APlayerCameraManager`
  vtable.

⇒ **`FTViewTarget ViewTarget` sits at `APlayerCameraManager+0x420`, with `Target` at `+0x00` and
`POV` at `+0x10`.** (MEASURED for the 2026-07-26 build; the shim re-derives it by reflection at
runtime and logs which source it used — see §7.)

The faulting instruction:

```asm
48 8b 0b              mov  rcx, [rbx]              ; ViewTarget.Target
4c 8d 43 10           lea  r8,  [rbx+0x10]         ; &ViewTarget.POV
0f 28 ce              movaps xmm1, xmm6            ; DeltaTime
48 8b 01              mov  rax, [rcx]              ; load vtable  <-- reads 0 out of zero padding
ff 90 00 07 00 00     call qword ptr [rax+0x700]   ; AV reading 0x700, rax == 0
```

### 2.2 What the view target actually is — positively identified

This is the strongest single result of the whole pass, and it came from the **crash skeptic**, not
from either diagnosis block. **MEASURED:**

> `ViewTarget.POV.Rotation == (-66.00, -90.00, 0.00)` in dumps `AABE886D` and `B61ED1A7`.

`tutorial_launch.cpp:2384` — `#define KCAMPITCH -66.0` — and line 2427 writes exactly
`R[0]=KCAMPITCH; R[1]=-90.0; R[2]=0.0`. **That triple is a shim-private constant that nothing else in
the process writes.** I verified both the source constant and the write site.

Before this, the object's identity rested on "most available suspect." It now rests on a private
constant recovered from crash memory. **The view target is the shim's own force-spawned camera actor.**

Supporting shape evidence (MEASURED): a fully-formed `UObject` sits at `Target + 0x3F` with vtable RVA
`0x07F96428`, 248 slots, ending exactly at `0x07F96BE8` = `UCameraComponent`'s vtable (MSVC emits in
TU order), differing from a plain `AActor` vtable in **6 of 248** slots.

> **RETRACTED — the name.** Diagnosis block 1 called this vtable `ACameraActor` and traced it through
> `GetPrivateStaticClass`. The crash skeptic checked the project's own vtable index: it is
> `<unnamed>`, and there is **no `ACameraActor`** among the 84 named Camera classes. The *shape* is
> measured; the *name* is INFERRED. Nothing downstream depends on the name.

### 2.3 The mechanism: a single-byte overwrite, NOT a use-after-free

> **RETRACTED — "use-after-free."** The task brief and the earlier FK-3/FK-4 work both framed Family B
> as a UAF on a garbage-collected `CameraActor`. **That is falsified.** MEASURED:
> - The camera actor is **registered in `GUObjectArray`** with `FUObjectItem::Flags == 2`
>   (UE 5.4 `EInternalObjectFlags::ReachabilityFlag1` = marked reachable on the most recent GC pass).
> - Its **clean pointer is still held by its own `FUObjectItem`**.
> - The object was never collected. **What is wrong is the stored pointer, not the object.**
>
> Consequence: **`KGCROOT` (the Family A fix) cannot fix Family B.** Rooting an object that was never
> collected does nothing.

The corruption, MEASURED across the dumps:

```
stored : 01 8d 31 9e 3a 02 00 00      = 0x0000023A9E318D01
live   : 40 8d 31 9e 3a 02 00 00      = 0x0000023A9E318D40   (the actual object)
         ^^
         bytes 1..7 byte-identical; ONLY byte 0 differs
```

A 32-bit or 64-bit store cannot produce that. **It is a one-byte write of `0x01`.** All four
Family-B dumps carry `Target & 0xFF == 0x01`:
`0x23A9E318D01`, `0x1E79523F301`, `0x2640B5BF301`, `0x1A4F94FD901`.

Every downstream step follows without further assumption (INFERRED, but tightly):
1. `Cast<ACameraActor>` reads `[Target+0x18]` out of zero padding → null → **fails without faulting**,
   which is why `UpdateViewTarget` falls through to `UpdateViewTargetInternal` instead of taking its
   camera-actor branch.
2. `if (OutVT.Target)` passes — garbage is non-null.
3. `BlueprintUpdateCamera` never dereferences the target.
4. `mov rax,[rcx]` reads 0 from that same padding → `call [0+0x700]` → **the recorded AV, rax == 0.**

> **RETRACTED — the `TObjectPtr` low-bit-tag theory** (diagnosis block 2). A tag on `…40` would read
> `…41`, not `…01`, and bytes 1–7 are byte-identical to the live object. Dead. Both skeptics agree.

> **RETRACTED — the negative evidence.** Block 1 leaned on "`ptrhunt` found the clean pointer in
> exactly ONE slot" and "**ZERO** slots hold `Target & ~0xFF`." The dumps carry **6.80–7.03 MB** across
> ~4,000 ranges out of a multi-gigabyte process. `ULevel::Actors` simply is not in the dump. **Absence
> proves nothing here.** (Same trap: `injected=NONE` in the module list — the shim is manually mapped,
> so it never gets an LDR entry.)

### 2.4 The split inside Family B — two faults, not one

> ## ⚠ CORRECTED 2026-07-29 (S106e) — see §0.2 / §0.2a. Read this subsection with both corrections.
> **(a) The "POV default, never computed" discriminator is an ARTIFACT.** MEASURED: that state is what
> `UpdateViewTarget` **itself writes** at its top (`OutVT.POV = FMinimalViewInfo()`), and the same
> `(90, 90, 512)` triple sits untouched in `PendingViewTarget.POV` at PCM+0xC80 in all four dumps. The
> `12c7e2d` frame is a `Cast<>` type check (`FStructBaseChain`/`UStruct::IsChildOf`) whose caller shares
> the **same `.pdata` extent** `0x3C34AE2..0x3C34B95` as the other family's frame — **two call sites in
> one function.** ⇒ same corruption, consumed at two points in one frame; and the corruption is
> **already present at the top of `DoUpdateCamera` in 4/4**, so the writer is **not** in the camera chain.
> **(b) BUT the split is CONFOUNDED WITH BUILD VINTAGE and cannot be resolved from the corpus.**
> `12c7e2d` = 07-24 14:45 + 07-26 01:44 (both **before** commit `a8d23f2`); `3c5dc52` = 07-26 04:29 +
> 04:39 (both **after** it). `a8d23f2` falls exactly between. **The mechanism argument does not license
> dropping the positive control** — if they are two bugs the guard may repair one and not the other.

**The crash skeptic wins here and it changes the hunt.** "4/4 camera crashes" pooled two different
bugs. I verified the chains diverge:

| | `3c5dc52` (×2) | `12c7e2d` (×2) |
|---|---|---|
| chain | `3c5dc52 3c5d255 3c34b22 3c596b3 …` | `12c7e2d 3c2adb9 3c34b0c 3c596b3 …` |
| fault operand | `0x700` | `0xFFFFFFFFFFFFFFFF` / `0x1000040` |
| `ViewTarget.POV` | **default, never computed** — Loc `(0,0,0)`, Rot `(0,0,0)`, FOV 90, OrthoWidth 512 | **live, shim-written** (the `-66/-90/0` triple) |
| reading | the **first** `CalcCamera` on that target crashed | the target went bad **after** being driven |

They converge only at `3c596b3 39c7884 37f8b8c` (the outer camera-tick frames). That is the difference
between *"a good pointer went bad"* and *"the pointer was bad at assignment."* **They need different
hunts.** The guard in §5 addresses both symptoms but neither root cause.

---

## 3. Family A — the worker-thread animation UAF

### 3.1 The real faulting PC

**MEASURED:** crash `063228F6`'s minidump `CONTEXT.Rip = 0x7FF6EB1C596D`, base `0x7FF6E7D30000`
→ RVA **`0x349596D`**. Four other dumps record `3495973` — which is **+6, the return address.**

```asm
0x3495960: mov rbx,[r15+rsi*8]     ; UngroupedActivePlayerArrays[i]
           add rbx,r14             ; += 0x70  (sizeof FAnimTickRecord)
           mov rcx,[rbx]           ; the UAnimationAsset*
           mov rax,[rcx]           ; its vtable
           call [rax+0x2F8]        ; <-- FAULTS. a virtual dispatch, not a data read.
```

> **Process rule established.** Take the faulting PC from the minidump `CONTEXT`, **never** from the
> `CrashContext` XML frame list — the XML mixes faulting PCs and return addresses, and a 6-byte error
> puts you in the wrong instruction.

### 3.2 The function and the object

**MEASURED.** `strxref func 0x3495973` → entry `0x3494B40`, extent 4336 B exact, touching
`"Ticking Group [%s] GroupLeader [%d]"`, `"Invalid position from Leader %d. Trying next leader"`,
`"[PreviousMarker %s, NextMarker %s] : %0.2f"` — all three are `AnimSync.cpp` literals.
⇒ **`FAnimSync::TickAssetPlayerInstances`**, running on a task-graph worker.

The dereferenced object is **destructed and freed**, identically in 5 of 5 dumps:

| offset | reads | meaning |
|---|---|---|
| `+0x00` vtable | a **heap** address chaining to same-size blocks | allocator free-list link (5/5) |
| `+0x20` NamePrivate | **0** | `~UObjectBase` → `LowLevelRename(NAME_None)` (5/5) |
| `+0x18` ClassPrivate | intact, same page offset `0xD00` across launches | (5/5) |
| `+0x30`, `+0x38` | module `.rdata` vtables RVA `0x7CA73C0`, `0x7F2F208` | the two interface mixins that follow the `UObject` subobject of a **`UAnimationAsset`** (byte-identical across 5 independent launches) |

Meanwhile `r12` (the anim proxy) holds a **valid module vtable** (RVA `0x7F5A260`) in 5/5 — **the proxy
is alive; only the asset is dead.** This is a genuine UAF.

The tick record is the shim's own call (MEASURED): `PlayRate=1.00`, `EffectiveBlendWeight=1.00`,
`RootMotionWeightModifier=1.00`, `bLooping=1`, array `Num=1, Max=4` — matching
`tutorial_launch.cpp`'s `PlayAnimation(anim, bLooping=1)` on a SingleNode component.

### 3.3 Why it is shim-caused

**STRONG_INFERENCE**, four independent legs:
1. The signature appears **only** on 2026-07-26 in a corpus spanning 2026-06-25 → 07-26. Zero
   occurrences in the 75 earlier crashes.
2. `grep -E 'AddToRoot|RootSet|GUObjectArray' tutorial_launch.cpp` → **0 hits for any rooting** (I
   re-verified; there is still **no `RemoveFromRoot` anywhere in the file**).
3. The only asset-acquisition path is `LoadMeshByPath` → `UKismetSystemLibrary::LoadAsset_Blocking`,
   which returns a **raw `UObject*` and holds no reference**. The result lives only in the DLL's plain
   C globals, **which UE's GC cannot see.**
4. The shim's own S99b comment already recorded the game-thread twin: *"PlayAnimation(idle) fault four
   times in a row with RIP=0x0 access=EXEC addr=0x0"* — that is crash `154E12A5`'s exact exception.

The existing `g_plAnimDead` latch only protects the **shim's own** call. The game's parallel anim tick
keeps dereferencing the dead asset every frame, which is why the process still dies.

### 3.4 ⚠ The trigger is NOT a garbage collection — and this undercuts the fix's premise

> **RETRACTED — "the first GC after map load."** Diagnosis block 2 built its causal story on
> `gc.TimeBetweenPurgingPendingKillObjects:61.1` and "map load T+121..128 s ⇒ crash exactly one purge
> later." **The crash skeptic refuted it and I independently confirmed the refutation:**
>
> - **`LogGarbage` appears in ZERO log files.** I grepped every `.log` in
>   `…\SUPERVIVE\Saved\Logs\` — `grep -l LogGarbage *.log | wc -l` → **0**. No GC event is observable
>   anywhere in the corpus. The story is arithmetic on an **unobserved** event.
> - The arithmetic also misses: 61.1 s predicts ~182–188 s; observed is 173–201 s.
>
> The real clock, MEASURED from the per-crash `Loki.log` snapshots — latency after the mesh/cloth build:
>
> | family | latency | note |
> |---|---|---|
> | camera (`3c5dc52`) | **+0.14 s, +0.17 s** | two independent launches agreeing to ~0.1 s |
> | anim (`349596d`) | **+20.21 s, +20.30 s** | two independent launches agreeing to ~0.1 s |
>
> And `tutorial_launch.cpp:2911`:
> ```c
> #define KAUTOWALKATMS 20000  // ms after body build when the self-driven walk starts
> ```
> **The anim family's trigger is the shim's own hardcoded 20 s self-walk timer** — which fires the
> run/idle `PlayAnimation` swap — not a garbage collection. I verified the constant and its use at
> line 3722.

**Why this matters for the fix:** `KGCROOT` roots objects *so the GC will not collect them*. But no GC
has been observed, and the trigger is a timer. This refutes the **timing argument**, not necessarily
the **mechanism** — the asset could still have been collected during those 20 s, with the timer merely
being *when the dead pointer gets used*. **That distinction is untested, and it decides whether half
the built fix is aimed correctly.** §7 Step 6 is the one-run, zero-code probe that settles it.

### 3.5 Shared or independent?

**Shared antecedent, independent mechanisms.** Both families occur only in mesh-build sessions (§4.3).
But they have different latencies (+0.15 s vs +20.2 s), different triggers (assignment vs timer),
different threads, and different objects. **Neither fix closes the other.** Presenting either alone as
closing FK-7 would be a partial result dressed as a full one.

---

## 4. The 86-dump corpus

### 4.1 Signature distribution

**MEASURED** (`tools/crashtri/crash_census.csv`, 86 rows; re-derived by me):

| | |
|---|---|
| dumps | 86 |
| with a game-frame chain | 73 |
| distinct full chains | **34** |
| distinct 3-frame prefixes | 33 |
| sharing a full chain with another crash | **50 (68%)** |
| repeat-group sizes | 17, 7, 5, 4, 4, 3, 2, 2, … |

The largest cluster (**23× `115604d`**, code `0x00004000`) is **not an access violation at all** — it is
UE's fatal-assert path: *"Fatal error: [UnrealEngine.cpp][Line: 15551] Couldn't spawn player: ALoki…"*
(06-29 → 07-11). Three other long-standing families are unrelated to the tutorial era:
`FAsyncLoadingThread fe1746` ×5, worker `107d500` ×7, RHIThread ×6.

> ⚠ **CORRECTION 2026-08-05 (S111): the `107d500` ×7 are SHUTDOWN-PATH crashes — remove them from
> every game-bug denominator.** All 7 carry `<IsRequestingExit>true</IsRequestingExit>`, and that set
> is **set-identical 7/7 both ways** to the `107d500` chain (independently re-verified in-session with
> a second parser: `{3EF4049A, 45C23461, 5CAD7A20, 64A6BCAC, 6AA0F217, DE62E243, F86B2A5B}`). The
> engine was already tearing down — this is "the game AVs on quit", which also explains the otherwise
> absurd 11.8 h `SecondsSinceStart` values (42387, 8403, 3216).
> **Also newly named: 6 rows carry `IsStuck == true` with `StuckThreadId == the GameThread` — UE's
> `FThreadHeartBeat` firing, i.e. the GameThread stopped ticking BEFORE the fault.** Four are
> tutorial-route, and one (`C82D6169`, 184 s) is a row previously used as in-window FK-7 evidence.
> Pooling hangs with instantaneous faults pools two mechanisms. Both columns are in
> `docs/fk8-crash-corpus.csv` (`is_requesting_exit`, `is_stuck`) and neither had ever been read.

### 4.2 `SecondsSinceStart` is usable — FK-8 corrected

> **RETRACTED (FK-8): "`SecondsSinceStart` is always 30."** **FALSE.** MEASURED: populated and
> meaningful in **74 of 85** records, ranging **0 → 42,387 s** (observed: 13, 14, 24, 49, 84, 173, 175,
> 185, 194, 195, 201, 259, 654, 834, 3216, 3334, 8403, 42387). It is 0 in exactly 11 records — and
> those same 11 carry no `<IsCrashed>true</IsCrashed>` thread, so 0 means *"never populated for this
> record,"* not *"died at 0 s."*
>
> This field is what made the 173–201 s clustering visible at all. The false-known had suppressed the
> single most informative column in the corpus.

### 4.3 The antecedent — a 9-session natural experiment

Better than "last log line before 4 crashes." **MEASURED by me, independently**, across the retained
backup logs (`grep -c` per session):

```
Loki-backup-2026.07.26-09.09.27.log   flushAsync=5  cloth=1  tutorial=341   -> CRASH 04:09 (195s)
Loki-backup-2026.07.26-09.14.35.log   flushAsync=5  cloth=1  tutorial=341   -> CRASH 04:14 (194s)
Loki-backup-2026.07.26-09.29.11.log   flushAsync=5  cloth=1  tutorial=185   -> CRASH 04:29 (175s)
Loki-backup-2026.07.26-09.39.24.log   flushAsync=5  cloth=1  tutorial=185   -> CRASH 04:39 (173s)
Loki-backup-2026.07.26-09.33.23.log   flushAsync=4  cloth=0  tutorial=185   -> no crash
Loki-backup-2026.07.26-09.36.18.log   flushAsync=4  cloth=0  tutorial=275   -> no crash
Loki-backup-2026.07.26-09.44.28.log   flushAsync=4  cloth=0  tutorial=185   -> no crash
Loki-backup-2026.07.26-09.55.23.log   flushAsync=4  cloth=0  tutorial=191   -> no crash
Loki.log                              flushAsync=4  cloth=0  tutorial=221   -> no crash
```

```
flushAsync==5 && cloth==1   ⟺   crash        4/4 crashed
flushAsync==4 && cloth==0   ⟺   no crash     0/5 crashed
```

**Perfect separation**, and the four crashing sessions map **1:1** onto the four 04:xx crash dumps by
timestamp. Both families occur only in mesh-build sessions. UPHELD and strengthened.

> ## ⚠ RE-INTERPRETED 2026-07-29 (S106e) — the separation is REAL, the VARIABLE was misnamed. See §0.2.
> **This table is measuring the shim's `RunMode`, not a cloth variable.** MEASURED: all four
> `flushAsync=5 / cloth=1` sessions ran **RM_PLAY** (which does the blocking Ronin mesh build); all five
> `flushAsync=4 / cloth=0` sessions ran a **non-mesh** mode — 3 of them recovered from git as
> **RM_SPAWNPOSSESS**, each having **run to completion** (`[SP] done step=4 …`). There is no `flushAsync=5`
> at any time in the five. ⇒ read the law as *"the blocking mesh build is the antecedent"* (true, and it
> is the `RunMode` that decides whether it happens), **not** *"cloth is the discriminator."*
>
> **And half the antecedent does not exist.** `LogPhysics "Scale3D is (nearly) zero"` appears in
> **0 of 14** log files; `LogPhysics` in **0 of 14**. The string is in the image (`.rdata 0x0817DAF0`,
> refs=1) and is simply never emitted. **No degenerate *physics* body is ever reported.** `LogChaosCloth`
> fires exactly **1×** per crashing session (so: **ONE** non-uniform body, cleanly, 4/4) and its object
> name is **EMPTY** in this shipping build — **the line cannot tell you which body it is about.**

**Second-order finding (crash skeptic, MEASURED):** the shim *intends* to disable cloth
(`tutorial_launch.cpp:3257–3262`), yet `LogChaosCloth` fires in **4/4** crashing sessions. **The
cloth-disable step is failing.** Repairing a pointer masks a mesh the shim was never supposed to have
built in that state.

> ## ✅ MECHANISM FOUND 2026-07-29 (S106e) — the cloth-disable is both MIS-ORDERED and INERT.
> MEASURED order in `BuildHeroBody`: `AddComponentByClass` → `RelativeScale3D=1` → `SetWorldScale3D` →
> `SetSkeletalMeshAsset` → **`ClothingSimulationFactory = null`** → `SetAnimationMode` → **registration**.
> On the default route (`KUSEBPCOMP=1`) the null lands before registration and the warning **still**
> fires 4/4. INFERRED from UE semantics: `OnRegister` repopulates a null factory from
> `p.Cloth.DefaultClothingSimulationFactoryClass` — which is why the log names **Chaos** while `:3257`
> says Ronin's mesh carries the **Nv** factory. **Nulling the `TSubclassOf` cannot disable cloth.**
> ⇒ The real lever is the **scale** (`KXFORMFIX`, §0.2) or deleting the body that should not exist
> (`KTESTACTOR=0`, §0.5 Run 0) — not the component field.

### 4.4 ⚠ Does the corpus explain the observed rate? **No — it explains at most half.**

> ## ❌ RETRACTED IN FULL — 2026-07-29 (S106e). There is no invisible second failure mode. See §0.2.
> **This subsection is a denominator error and it is the largest single correction of the closure pass.**
> The 5 dumpless sessions are not failures of the tutorial route:
> - **3 of 5 ran a DIFFERENT shim mode and FINISHED.** `docs/tutorial-launch-marker.txt` is **tracked in
>   git**; `git show d61d325:…` / `f6a7985:…` / `6e8a7df:…` each show **RM_SPAWNPOSSESS** ending
>   `[SP] done step=4 spawnedPawn=0x… (called=1 hitsGT=1)`. Each session's last log line is followed
>   **+3 s, +3 s, +9 s** later by the commit that carries **that same session's marker**. The user shut a
>   completed experiment down.
> - **2 of 5 died BEFORE the antecedent** — T+148.5 s and T+165.9 s, vs the earliest observed mesh build
>   at T+173.5 s. `FlushAsyncLoading=4`, `LogChaosCloth=0`: the build never happened. **Censored
>   observations, robust to their unrecovered mode.**
> - **Every alternative mechanism is excluded.** `ConsoleCtrl`=0 and `INTERRUPTED`=0 in all 11 logs
>   (UE's handler **does** exist in this build — fn `0x113EF10`, and `SetConsoleCtrlHandler` is in the
>   rebuilt import table); no `fastfail`/`gsfailure`/`buffer overrun`/`LowLevelFatalError`/`Assertion
>   failed` anywhere; no hang (final-20 s cadence 30.0 / 225.2 / 30.0 / 29.9 / 51.8 fps at 131–1340
>   lines/s, zero timestamp gaps > 0.6 s, one session logging an HTTP request **16 ms** after its last
>   log line; one file ends **mid-timestamp** at 1340 lines/s = killed mid-flush).
> - **★ FOUR POSITIVE CONTROLS.** The identical zero-exit-marker tail occurs in sessions with **no
>   tutorial shim at all**: 07-26 09:22 (234 s) and 20:16 (163 s) are menu-only (`LVL_Tutorial`=0,
>   `LVL_Login`=9), and 07-05 `Loki_3`/`Loki_4` predate the route entirely. Meanwhile `Loki_2` (a clean
>   quit) logs **all four** exit markers, proving the markers are emitted when they apply.
>
> ⇒ **"No exception record" is the signature of a process that was TERMINATED, not one that FAILED.**
> Same instrument-artifact shape as the other five (§0.7). **The RM_PLAY route's real rate is 4/4 =
> 100%.** What survives is an *instrument* gap, split out as **FK-25** (§0.3/§0.6) — not a failure mode.

**This is the largest scope correction of the pass, and it is the crash skeptic's.** I verified it
directly:

- **9 tutorial sessions** in the retained window. **4 produced a crash dump.**
- The 4 dumps map 1:1 onto the 4 sessions containing `ExceptionHandler` (I confirmed:
  `09.29.11` has `ExceptionHandler` ×2 + 3 exit markers).
- **The other 5 tutorial sessions have ZERO exit markers and ZERO `ExceptionHandler`** — I confirmed
  each ends mid-line on a routine `LogTemp: Error: ULokiGameFeatureToggles:` spam line. They died with
  **no clean shutdown and no crash handler**, at 149 / 166 / 235 / 307 / 304 s — and **3 of those ran
  straight past the 173–201 s band.**

⇒ **"~2 of 3 launches die" is roughly right as an outcome rate, but at most half the failures are in
the crash corpus at all.** There is a **second failure mode — the process disappearing without
invoking its own exception handler** — that is invisible to every conclusion in this document and is
**untouched by both fixes.**

Candidate explanations for the dumpless deaths, all **OPEN**: the code-integrity check killing the
process (§8), an anti-tamper fast-fail, or a stack-overflow/`__fastfail` path that bypasses the VEH.

---

## 5. The fix

### 5.1 What was built

Two guards, both behind compile-time flags, both defaulting **ON**, in
`tools/sigbypass-mod/tutorial_launch.cpp`. **All 23 `RunMode`s preserved.**

**`KVTGUARD` — Family B (camera).** `VtGuard()` runs on the game thread once per `ProcessInternal`
hook hit, ahead of the camera tick:
- `VtResolve` finds `PC → PlayerCameraManager` and the byte offsets of `ViewTarget` /
  `PendingViewTarget` **by reflection**, with the measured `0x420` as an **explicitly logged** fallback
  (so a layout change is visible, not silent), and a bounded 200-hit retry so it never latches off
  before the PC exists.
- `VtValid` = `LooksLikePtr` (8-alignment) + `GcAlive` (vtable must be in-image, `NamePrivate` ≠
  `NAME_None`). **The measured corruption makes the pointer unaligned, so the alignment check alone
  already rejects it** — and `GcAlive` additionally catches a genuine UAF if one ever appears.
- On invalid: **logs the corrupt value, its alignment, its low byte, ms-since-last-good, and the delta
  to the replacement BEFORE writing**, then stores the preferred camera / last-known-good / the PC.
- `PendingViewTarget` is cleared to **NULL**, which is exactly what
  `APlayerCameraManager::SetViewTarget` writes for an instant cut — the engine's own no-blend state.

**`KGCROOT` — Family A (anim).** Sets `EInternalObjectFlags::RootSet` on the shim's loaded assets via
`GUObjectArray`, verifying the bit reads back, refusing to poke anything if a corroboration check
fails.

**`KPIMUTEX` — the mutex bug from the brief.** `HookLock`/`HookUnlock` over
`CreateMutexA("Local\\SuperviveMissionsPIHook")` wired into `InstallHook`/`UninstallHook`, so all ~23
modes are covered by one change, with a bounded 30 s wait then proceed-and-log (it can never become a
new hard failure).

### 5.2 Why this approach

The corruption is a **pointer-validity** problem, not a lifetime problem. An 8-alignment + live-UObject
check catches the measured signature **deterministically** (the corrupt value is unaligned by
construction), needs no `.text` patch, no new hook, and no C++ exceptions. It restores the same
invariant UE's own `FTViewTarget::CheckViewTarget` maintains.

Two design decisions worth recording:
- **The ViewTarget check is deliberately NOT throttled.** A single-byte store from an unknown writer
  can land on any frame; the entire value of the guard is repairing it *before the next camera tick
  dispatches through it*. Measured cost is ~3 `VirtualQuery` per hit against the 2–4 full `UFunction`
  invocations the mode already makes per hit.
- **The PCM liveness re-check IS throttled (4 Hz)**, because a destroyed `PlayerCameraManager` can stay
  **committed** while freed — `SafeReadable`/`SafeWritable` both still pass — and writing 8 bytes into
  a recycled allocation is *strictly worse* than the deterministic AV being fixed. On failure the guard
  stands down and re-resolves rather than writing.

### 5.3 What it does NOT fix

1. **The writer of the corrupt byte.** OPEN, and **not reachable offline** — `.text` in
   `dumps/merged.dump.exe` is only **52.29% decrypted**. A scan for `mov byte [reg+0x420], imm8` found
   30 sites (8 with `imm==1`), none in camera code — **not a negative result**, since the write could
   equally be `lea` + `mov byte [reg],1` from the undecrypted half. The guard **repairs a symptom.**
2. **The `12c7e2d` sub-family** (§2.4), where the pointer was bad *at assignment* — the guard may repair
   it, but the root cause is upstream.
3. **The race.** `+0.14 s` after the mesh build means the crash is on the **first** `CalcCamera` after
   assignment, while `VtGuard` only runs on hook hits. **It is not guaranteed to win that race.** And
   if the writer is the degenerate cloth solve, it will re-corrupt every frame and the guard will fight
   it forever (visible as `[VTG]` repairs in bursts of hundreds — see rollback, §7).
4. **The failing cloth-disable** (§4.3).
5. **The dumpless second failure mode** (§4.4) — ~half the observed rate.
6. **Family A's causal premise** (§3.4) — `KGCROOT` may be treating the wrong cause.

> **⚠ Amended 2026-07-29 (S106e).** Item **1** stands and is now **split out as FK-24** — the scan is
> exhaustive over the decrypted half for *every* byte-width store form (34 sites, 8 with imm8==1), and the
> `+0x3F` discriminator is retracted. Item **2** is retired as a mechanism question but is now
> **build-confounded** (§0.2a). Item **3**'s *"if the writer is the degenerate cloth solve"* is
> **RETRACTED** — a heap overrun cannot reach `0x420` inside a live allocation (§0.2); the burst symptom
> and its rollback still stand. Item **4** now has a **mechanism** (mis-ordered **and** inert — §4.3
> banner) and the physics half of its antecedent **never existed** (0 of 14 logs). Item **5** is
> **RETRACTED IN FULL** — not a failure mode (§4.4 banner). Item **6** is unchanged. **New item 7: the
> guard has never run.**

### 5.4 The leak / lifecycle trade-off — `KGCROOT` is not free

**MEASURED** (crash skeptic; I re-verified legs 1 and 2):

- **No un-root path exists anywhere in the file.** `grep RemoveFromRoot` → 0 hits. **Rooting is
  permanent for the process lifetime.**
- `GcRootAllOfClass("AnimSingleNodeInstance", 4, …)` roots by **class-name substring, not identity** —
  it can root **game-owned** instances, not just the shim's.
- Rooting a *component* pins its Outer chain: component → actor → level → **World**. The in-file
  comment states this pinning as *the point* without noting that **exit-to-menu or a second map load
  then cannot collect the old world.**
- `GcFindItem` is an **O(n) linear scan of the entire `GUObjectArray` per root call**, on the game
  thread, with `GcRootAllOfClass` nesting another scan per match. `InternalIndex` is at `obj+0x10`, so
  `chunk[idx>>16] + (idx&0xFFFF)*0x18` would be **O(1)**. Given S81's history of game-thread stalls
  causing netdriver timeouts, worth fixing before it ships widely.

**Trade:** `KGCROOT` swaps a deterministic UAF crash for a permanent world leak. Acceptable for a
single ≤10-minute tutorial experiment; **not** acceptable for a session that returns to menu or loads a
second map — which is precisely the ">3-minute in-world experiment" this whole effort exists to enable.
Narrow to `KGCROOTCOMP=0` (assets only) if retained-object counts grow across purges.

### 5.5 ⚠ Known defect in the shipped guard — `s_tries` never resets

**MEASURED by me, still present in the built DLLs.** `tutorial_launch.cpp:920` declares
`static int s_tries` **inside `VtResolve`**. The dead-PCM stand-down at line 967 resets
`g_vtPCM/g_vtOff/g_vtPendOff/g_vtGood/g_vtRes` — **but not `s_tries`.** Across repeated
stand-down → re-resolve cycles the counter accumulates; once it crosses 200 it latches `g_vtRes=true`
with `g_vtPCM=0`, and line 917 then returns false forever. **The guard is dead for the rest of the
session** — after exactly the event (an actor teardown) it was extended to handle.

> The fix skeptic proposed adding `s_tries=0;` at line 967. **That does not compile as stated** —
> `s_tries` is function-scoped inside `VtResolve` and is not visible in `VtGuard`. The correct patch is
> to promote it to file scope (`static int g_vtTries=0;` beside `g_vtRes`) and reset it in the
> stand-down block.

**Severity: second-order.** It requires ≥200 cumulative resolve failures, which needs the PCM to die
repeatedly. It does **not** affect the primary A/B. **Left unfixed on purpose:** rebuilding now would
invalidate the byte-level verification already performed on these exact artifacts (236,032 B,
442 `RUNTIME_FUNCTION`s). Fix it **after** the first verification run, not before.

> ## ✅ FIXED 2026-07-29 (S106e). The "fix after the first run" deferral is moot — the run had not
> happened, and three of the five artifacts it was protecting have since been deleted as footguns (§0.4).
> `s_tries` is now file-scope `g_vtTries` (`tutorial_launch.cpp:1048`) **and reset in the stand-down
> path** (`:1108`) — **the reset is the actual fix**; the promotion only makes it reachable. Also reset on
> a successful resolve (`:1063`) so the 200-hit budget is per-attempt rather than cumulative. `s_tries`
> now appears only in the comment recording the bug. **§8 item 7 CLOSED.**

### 5.6 Did it actually build? **Yes — verified independently.**

I re-checked the artifacts on disk rather than trusting the report:

```
tutorial_launch_play_vtguard.dll      236032 B   VTG=8  GC=8  GCW=4  PIM=4   CxxFrame=0  Throw=0
tutorial_launch_play_novtguard.dll    232960 B   VTG=0  GC=8  GCW=4  PIM=4   CxxFrame=0  Throw=0
tutorial_launch_play_gcroot.dll       236032 B   VTG=8  GC=8  GCW=4  PIM=4   CxxFrame=0  Throw=0
tutorial_launch_play_nogcroot.dll     229376 B   VTG=8  GC=2  GCW=1  PIM=0   CxxFrame=0  Throw=0
tutorial_launch_play.dll  (STALE)     197120 B   VTG=0  GC=0  GCW=0  PIM=0   CxxFrame=0  Throw=0
```

Also verified by the fix skeptic with an independent PE parser: imports **KERNEL32 (95) + USER32 (3),
zero CRT**; exports `start_mod`/`uninstall_mod`; no `__CxxFrameHandler3/4`, `_CxxThrowException`,
`__std_terminate`, `_Unwind_Resume`, `__gxx_personality`, `std::bad_alloc`. `.pdata` holds **442**
`RUNTIME_FUNCTION`s vs **439** in the control — **exactly the 3 new functions**
(`VtResolve`/`VtValid`/`VtGuard`), corroborating the source diff against the binary.

`RaiseException` and `AddVectoredExceptionHandler` **are** imported — both **pre-existing**
(`tutorial_launch.cpp:4726` installs `CrashVEH`) and untouched. The shim uses Windows **SEH**
(`__try`/`__except`), which needs no C++ EH machinery. **The constraint holds.**

### 5.7 ⚠ THREE FOOTGUNS — disarm before launching

> ## ✅ ALL THREE DISARMED 2026-07-29 (S106e). Current matrix: **§0.4** (6 DLLs, 6 distinct `.text`
> hashes, verified by two independent passes). **A** — `_play_gcroot.dll` and `_play_vtguard.dll` were
> confirmed identical (2,048 differing bytes, entirely the embedded export filename) and **both deleted**;
> the `play-gcroot` / `play-vtguard` aliases are gone from `$Variants`. **B** — `nogcroot` is now
> single-variable (`[PIM]` stays **4**, was 0). **C** — `tutorial_launch_play.dll` was confirmed stale two
> ways (PE stamp a day behind; **zero** `[VTG]` strings, so it could not contain the guard at all),
> deleted and regenerated as **the candidate**. New hazard introduced by the fix, recorded in §0.4:
> `_play_noxformfix.dll` is identical to `play` in **size and `.pdata` count** by design — only the
> `.text` hash separates them.

All three **MEASURED by me**, all three would have silently corrupted the run:

| # | problem | proof |
|---|---|---|
| **A** | **`play_gcroot` and `play_vtguard` are the SAME BINARY.** | Both 236,032 B; the 2048 differing bytes are entirely the embedded export filename and the uniform RVA shift it causes. Identical `[VTG]`=8, `[GC]`=8, `[PIM]`=4. **A/B-ing these two compares a DLL with itself.** |
| **B** | **`play-nogcroot` is a TWO-variable control** (`KGCROOT=0` **and** `KPIMUTEX=0`). | `[PIM]`=0 and the mutex string is **absent** (`SuperviveMissionsPIHook` count 0 vs 1 in vtguard). The mutex change is **not separable** from the GC-root fix — exactly the bundled-test ambiguity CLAUDE.md warns against. |
| **C** | **`tutorial_launch_play.dll` is the STALE PRE-FIX build** — and has the most obvious name. | 197,120 B, Jul 26, `[VTG]`=0 `[GC]`=0 `[PIM]`=0. Injection is manual, so reaching for the un-suffixed name silently runs the **old** shim and reads as *"the fix failed."* |

**The `vtguard` A/B is clean**: `novtguard` differs only by `KVTGUARD=0`, with `[PIM]`=4 and `[GC]`=8
intact. **Use that pair.** For the GC arm, build a proper single-variable control first (§7 Step 0).

---

## 6. The build system

`tools/sigbypass-mod/build.ps1` + `BUILD.md` now exist. Previously **63 shim `.cpp` files had no build
script and no build system**; every DLL was built ad hoc and none were in git.

```powershell
cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"

.\build.ps1 -List                                  # the shim -> variant registry
.\build.ps1 -Name tutorial_launch                  # one shim, all registered variants
.\build.ps1 -Name tutorial_launch -Variant play-vtguard
.\build.ps1 -All                                   # every .cpp        (80 targets, 0 failed)
.\build.ps1 -Verify                                # build, then diff against the committed .dll
.\build.ps1 -Name missions_fix -InPlace            # write beside the sources (where injectors load from)
```

**Proof it builds real shims (MEASURED):** `-Verify` rebuilds all six default-set shims and each
reproduces the committed DLL **byte-for-byte except 6 bytes** (3 of PE `TimeDateStamp` + its
debug-directory mirror): `catalog_store_fix` 142,336 · `mainmenu_refresh_pi8` 152,064 ·
`catalog_pick_fix` 137,216 · `loadout_fix` 193,536 · `missions_fix` 178,688 ·
`battlepass_adopt_fix` 145,920.

### Toolchain — the brief was wrong, and so was the first `build.ps1`

> **RETRACTED — "build it with MSVC 2019 BuildTools `cl.exe`."** MSVC **cannot** build
> `tutorial_launch.cpp`. MEASURED, exit code 2:
> `error C3861: '__builtin_sqrt': identifier not found` (also `__builtin_cos`/`__builtin_sin`),
> 8 errors. These are deliberate — `__builtin_sqrt` emits a bare `sqrtsd` with **no CRT call**, which
> is why every shim links `-lkernel32` only and imports no C runtime.

> **RETRACTED — "these shims are clang-only."** The first `build.ps1` asserted the opposite absolute.
> Also wrong: **`cl.exe` builds 61 of 63 shims fine** (`/LD /MT /O2`). It fails on exactly two —
> `tutorial_launch.cpp` (`__builtin_*`) and `browse_hook.cpp` (`__attribute__((ms_abi))`, C2143). Only
> **1 file of 63** uses `__builtin_`; **zero** use `#pragma clang`. The claim was real but ~30×
> narrower than stated.

**Actual toolchain (MEASURED):** **clang++ 21.1.6**, shipped inside the Swift toolchain
(`%LOCALAPPDATA%\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`). The linker is
**`link.exe` 14.42 from a VS2022 Enterprise install** at the non-default path
`C:\Program Files\Tools\Microsoft Visual Studio\2022\Enterprise` — proven by decoding the **Rich
header** the DLLs carry (lld-link emits none; `link.exe` does), and VS2019's 14.29 does not match.
`build.ps1` is clang-first with `-Toolchain msvc` as a documented fallback that refuses those two by
name.

Direct command for the primary artifact (reproduces byte-identical at 236,032 B):
```
clang++ -shared -O2 -w -DKRUNMODE=RM_PLAY tutorial_launch.cpp \
        -o tutorial_launch_play_vtguard.dll -lkernel32 -luser32
```

### Structural findings

- **The per-file `// Build:` comments are unreliable.** `tutorial_launch.cpp` says `-lkernel32` only,
  but `RM_PLAY`/`RM_PUPPET` fail with LNK2019 without `user32` (confirmed both ways). Fixed
  structurally: **unused import libs cost nothing** (MEASURED — linking all six against
  `gft_ready_fix` gave an identical-size DLL importing only `KERNEL32`), so every shim links one
  universal set and no per-shim table can go stale.
- **Binary-diff trap:** shims export symbols, so the output *filename* is embedded in the export
  directory — building the same source to a differently-named DLL shifts data and inflates the diff
  (~2048 bytes). Same-name rebuilds differ by 3. `-Verify` compares like-for-like. *(This is exactly
  what makes footgun A look like a real difference.)*
- **The exception gate was too narrow** — widened to match `verify_dll.py`
  (`__CxxFrameHandler4`, `__std_terminate`, `_Unwind_Resume`), confirmed clean on all seven known-good
  DLLs.
- **`ds_hybrid.cpp` is the remaining mutex gap** — it hooks `ProcessInternal` (29 refs) with **zero**
  mutex usage. Not in the default set, so it does not race today, but injecting it alongside the
  default set would.

### Git recommendation

**Source only; do not commit DLLs.** The build is reproducible, the binaries are 141 files / tens of
MB, and a stale committed DLL that silently disagrees with its `.cpp` is worse than none — the exact
failure mode that made 135 untracked DLLs unauditable. `.gitignore` now covers
`*.dll/*.exp/*.lib/*.obj/*.pdb/*.ilk`, `build/`, `build_err.txt`. Three artifacts predate the rules and
are still tracked; **this needs a human call, not staged:**
```
git rm --cached tools/sigbypass-mod/main.exp tools/sigbypass-mod/main.lib tools/sigbypass-mod/build_err.txt
```
`build.ps1`, `BUILD.md`, `verify_dll.py` are untracked and want committing.

---

## 7. Verification plan

> ## ⚠ SUPERSEDED BY §0.5 — 2026-07-29 (S106e). **Run §0.5, not this.**
> §0.5 is the ordered sitting with the footguns removed, the positive control promoted to **mandatory**
> (§0.2a), detection-gated one-bit criteria, and a stop rule. This section is retained because four of its
> parts are still load-bearing and are cited from §0.5: **Step 1**'s armed/`(reflection)` gate, **Step 2**'s
> three positive controls, **Step 6** (the `KGCROOT` probe — still the cheapest high-value bit, item 4),
> and the **rollback** + **mutex caveat** below. **Step 0** is done (§0.4). **Step 3** is retracted as an
> attribution test (banner below). **Steps 4/5** are absorbed into §0.5 Runs 1–2 and the `KXFORMFIX` pair.

Ordered. Each step has a **one-bit criterion**. Do not skip Step 0 — three of the DLLs on disk are
traps (§5.7).

### Step 0 — disarm the footguns (before launching anything)

```powershell
cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"
del tutorial_launch_play.dll                              # stale pre-fix build (footgun C)
.\build.ps1 -Name tutorial_launch -Variant play-novtguard
.\build.ps1 -Name tutorial_launch -Variant play
```
Then confirm the pair differs **only** in the guard:
```
python -c "d=lambda f:open(f,'rb').read(); a=d('tutorial_launch_play.dll'); b=d('tutorial_launch_play_novtguard.dll'); print(a.count(b'[VTG]'), b.count(b'[VTG]'), a.count(b'[PIM]'), b.count(b'[PIM]'))"
```
**One-bit:** prints `8 0 4 4`. Anything else ⇒ the A/B is not single-variable; stop.

### Step 1 — armed check (gates everything else)

Inject `gft_ready_fix.dll`, then `tutorial_launch_play_vtguard.dll`. Read
`docs/tutorial-launch-marker.txt`.

**One-bit:** the line `[VTG] pcm=0x… ViewTarget@0x…` appears.
- **Absent ⇒ the run is VOID.** The guard never resolved; survival would prove nothing.
- If it reads **`FALLBACK CONSTANT`** rather than **`(reflection)`**, every offset-derived conclusion
  in §2 needs re-checking before the result is trusted. *(This doubles as the §2.1 offset probe: it
  should read `(reflection)` with offset `0x420`, i.e. the constant and the reflected layout agree.)*

### Step 2 — the fix run

Same injection; hold to **T+300 s** process uptime (clear air past the 173–201 s band **and** past the
~3–5 min integrity window — see §8).

**One-bit (primary):** alive at T+300 s **AND** ≥1 `[VTG] *** ViewTarget.Target INVALID` line.

> Survival alone is **not** the criterion — it cannot separate *"repaired"* from *"didn't happen this
> run."* Given §4.4 (only ~4 of 9 tutorial sessions crash at all), a single quiet run is weak evidence.

**Positive controls — all three required** (survival is necessary, not sufficient):
1. The four `KSHOT` screenshots in `Saved/Screenshots/WindowsClient/` show the hero **in frame**.
2. Each shot's logged hero and camera world positions are **finite**, and the camera is **above** the
   hero.
3. **No** `[GCW] *** … WAS GARBAGE-COLLECTED` line.

### Step 3 — writer attribution (free, same run)

> ## ❌ RETRACTED AS AN ATTRIBUTION TEST — 2026-07-29 (S106e). **This step cannot discriminate anything.**
> **It was run** (offline, against the 2 dumps that captured the live camera object) **and returned
> `+0x3F` in 2/2** — which is worthless, because `delta = (live & 0xFF) − 0x01` **whenever** byte 0 is
> replaced by `0x01`, and the live low byte is `0x40` in **3 of 3** observations *including the clean
> control dump* `FF9CF623` (`0x1CB9A088D40`). Both candidate writers — `mov byte [reg+0x420],1` and a
> 1-byte overrun writing 1 — emit **literally the same 8 bytes**.
>
> **Keep the line for SIGNATURE MATCHING only** — `delta=+63 lowbyte=0x01` does confirm *"this is the same
> bug, not a new one,"* and any other shape is still a different bug. **Delete the attribution claim.**
> Left visible because a reader who runs it will see `+63` and, without this banner, read it as
> *"a writer aimed at the field is CONFIRMED."*
>
> **The weighting paragraph below is RETRACTED too, and inverted.** Candidate (b) — the heap overrun — is
> **falsified structurally** (§0.2): the byte sits `0x420` **inside the PCM's own live allocation**, and a
> one-byte overrun writes one byte past the end of its **own** block. Candidate (a) — a field-aimed store
> — is the **only survivor**. The actual writer hunt is split out as **FK-24** with a DR-watchpoint probe
> (§0.6); it is **not** answerable from a `[VTG]` line.

Read the `[VTG]` repair lines — each prints the corrupt value, alignment, low byte, ms-since-last-good,
and delta.

**One-bit:** `delta=+63` (`0x3F`) **and** `lowbyte=0x01` ⇒ a writer aimed at `&ViewTarget.Target`.
Any other shape ⇒ a **different bug**; do not file it under FK-7.

> The two candidates are **not** equally weighted. `+0.14 s` after a cloth sim initialising on a
> non-uniformly-scaled body favours the **heap-overrun** candidate substantially over a field-aimed
> writer. The failing cloth-disable (§4.3) is a concrete, named suspect.

### Step 4 — is the camera guard load-bearing?

Same scenario, `tutorial_launch_play_novtguard.dll`. **Single variable** (verified in Step 0).

**One-bit:** dies at T+173–201 s with fault RVA `3c5dc52` or `12c7e2d`
(`python tools/crashtri/harvest.py`) ⇒ the guard is load-bearing. If it **survives**, the guard was
never the reason.

### Step 5 — is the blocking mesh load the true antecedent?

Rebuild the fix with `-DKNOMESH=1` (flag exists, `tutorial_launch.cpp:2845`) and hold past T+300 s.

**One-bit:** no crash **and** no `[VTG]` repair ⇒ the corruption is downstream of the blocking load,
and the hunt moves to the load/cloth path rather than a hypothetical field-aimed writer.

### Step 6 — ★ is `KGCROOT` aimed at the right cause? (the cheapest high-value bit)

**The shim already contains this probe. No new code, one run.** `tutorial_launch.cpp:3738–3740` prints:
```
[GCW] *** IDLE ANIM 0x… WAS GARBAGE-COLLECTED (t=…ms after body build) ***
```
Run `RM_PLAY` with **`-DKGCROOT=0`** (build a proper single-variable control — **not**
`play-nogcroot`, which is two-variable per footgun B) and read the marker.

**One-bit:**
- **Line appears** ⇒ the asset really was collected; `KGCROOT` targets the right thing, and `t=` prints
  the true death window, replacing the refuted 61.1 s arithmetic.
- **Line absent but the crash still fires at +20.2 s** ⇒ **the asset was never collected**, `KGCROOT`
  is treating the wrong cause, and the bug is in the run/idle swap itself.

Given §3.4, this decides whether half the built fix is aimed correctly. **Run it early.**

### Step 7 — does rooting leak a world? (only if Steps 2/6 pass)

After 300+ s, compare `RemoveUnreachableObjects` retained counts against a control run; watch working
set.

**One-bit:** retained-object count grows without bound across successive purges ⇒ narrow to
`KGCROOTCOMP=0` (assets only).

### Capture every run

`docs/tutorial-launch-marker.txt`; `Loki.log` (delete before each run); process uptime at death;
`python tools/crashtri/harvest.py`; the four screenshots; **and the injection wall-clock time** —
without it you cannot separate process-uptime-driven causes from hook-lifetime-driven ones, which is
exactly what the §8 integrity-check confound turns on.

### Rollback

Nothing here patches `.text` or persists. The guard is data-only reads plus one aligned 8-byte store,
all in-process. **To revert: stop injecting and relaunch.** No game-file or config state to undo.
`-DKVTGUARD=0` is the kill switch and needs no source edit.

**If the guard makes things worse** — dies earlier, or `[VTG]` repairs fire in **bursts of hundreds** —
that means it is repairing into a torn-down camera manager faster than the 4 Hz `GcAlive` re-check
catches, **or** the writer is re-corrupting every frame (§5.3 item 3). Use `play-novtguard`.

### Mutex caveat

The 30 s bounded wait then proceed-and-log means it can never become a new hard failure — that design
is right. But **`RM_PLAY` holds the mutex for its full 600 s hold**, so any menu shim injected during a
tutorial session blocks for up to 10 minutes. Before running the tutorial alongside a normal launch,
confirm `mainmenu_refresh_pi8` / `missions_fix` / `loadout_fix` each use a **bounded** wait; **if any
waits INFINITE, that is a hang, not a stall.**

---

## 8. What remains open

> **⚠ Re-adjudicated 2026-07-29 (S106e). The `status (S106e)` column governs.** Items are left with their
> original wording; six changed status. Full reasoning in **§0**.

| # | open item | status | status (S106e) |
|---|---|---|---|
| 1 | **The writer of the corrupt byte** | OPEN. Not reachable offline (`.text` 52.29% decrypted). Two candidates: a stray 1-byte `true` at `&ViewTarget.Target` from undecrypted code, or a **one-byte heap overrun** out of the degenerate cloth/physics bodies. The `+0.14 s` timing favours the overrun. Step 3 discriminates. | **SPLIT OUT → FK-24.** Candidate (b) **FALSIFIED structurally** (§0.2) ⇒ *"the timing favours the overrun"* **RETRACTED**; candidate (a) is the only survivor and is **unnamed**. *"Step 3 discriminates"* **RETRACTED** — it cannot (§7 Step 3 banner). Offline instruction-shape search now **exhaustive over the decrypted half**. Needs the **DR watchpoint**. |
| 2 | **★ The dumpless second failure mode** | OPEN and **largest**. 5 of 9 tutorial sessions died with no exit marker and no `ExceptionHandler`, 3 of them past the crash band. **~Half the observed failure rate is invisible to this entire investigation** and untouched by both fixes. | **❌ RETRACTED — NOT A FAILURE MODE.** A denominator error: 3 of 5 ran RM_SPAWNPOSSESS **to completion** and were shut down 3–9 s before the commit carrying their own marker; 2 died **before** the mesh-build antecedent. Four shim-free positive controls show the same tail. **RM_PLAY's real rate = 4/4.** Residue = an instrument gap → **FK-25**. |
| 3 | **★ The code-integrity-check confound** | OPEN. **Neither diagnosis considered it.** `RM_PLAY` holds a 5-byte `.text` patch at `ProcessInternal` for **600,000 ms** (`tutorial_launch.cpp:4947`) — 2–3× the documented ~3–5 min integrity interval — and the 173–201 s band (2.9–3.35 min) sits **right on it**. Pre-existing, not introduced here, but a live alternative explanation for a deterministic ~3-minute death, and a strong candidate for item 2. | **RE-SCOPED — it never operated.** MEASURED: patch install ≈ the `LVL_Tutorial` load (T+115.3…120.0 s), crashes at T+176.7…195.1 s ⇒ only **60–79 s** of patch uptime vs the **~285 s** observed kill latency; and the kill signature is a **dump** at the fixed poison RIP `0x7FF90E000001` (**1** such dump in the corpus), not a silent death. **Refuted as an explanation for item 2; retained as a hazard for the T+300 s hold** (§0.5 stop rule 2). Current line is `:5145`, not `:4947`. |
| 4 | **`KGCROOT`'s causal premise** | OPEN. No GC event is observable anywhere (`LogGarbage` = 0 files); the anim trigger is a shim timer. Step 6 settles it for one run's cost. | **STILL OPEN, unchanged.** Step 6's control is now a genuine single-variable DLL (`_play_nogcroot.dll`, `[PIM]`=4 — §0.4). |
| 5 | **The failing cloth-disable** | OPEN. The shim intends to disable cloth (`:3257–3262`); `LogChaosCloth` fires in 4/4 crashing sessions anyway. Likely upstream of item 1. | **MECHANISM FOUND** (§4.3 banner): mis-ordered **and inert** — `OnRegister` repopulates a null `ClothingSimulationFactory` from `p.Cloth.DefaultClothingSimulationFactoryClass` (which is why the log names **Chaos**, not the mesh's **Nv** factory). ⚠ `LogPhysics "Scale3D is (nearly) zero"` = **0 of 14** logs; the physics half of the antecedent **never existed**. Real levers: `KXFORMFIX`, `KTESTACTOR=0`. |
| 6 | **The `12c7e2d` sub-family** | OPEN. POV never computed ⇒ the pointer was bad **at assignment**, a different hunt from the `3c5dc52` "good pointer went bad." | **RETIRED AS A MECHANISM QUESTION** — "POV never computed" is what `UpdateViewTarget` itself writes; both frames are call sites in **one** `.pdata` extent. **⚠ BUT NOW BUILD-CONFOUNDED** (§0.2a): the split correlates perfectly with build vintage across `a8d23f2`, unresolvable from the corpus ⇒ **the positive control is mandatory.** |
| 7 | **`s_tries` never resets** (§5.5) | KNOWN DEFECT, deliberately unfixed pending Step 2. Promote to file scope and reset in the stand-down block. | **✅ CLOSED.** `g_vtTries` file-scope `:1048`; reset at `:1108` (the fix) and `:1063`. |
| 8 | **`KGCROOT` lifecycle** | OPEN. No un-root path; substring-matched rooting; pins the World; `GcFindItem` is O(n) on the game thread where O(1) is available. | **STILL OPEN, unchanged.** |
| 9 | **`ds_hybrid.cpp` mutex gap** | OPEN. Hooks `ProcessInternal` with zero mutex usage. | **STILL OPEN, unchanged.** |
| 10 | **The camera actor's class name** | OPEN, cosmetic. Vtable shape measured; name unresolved in the project index. | **STILL OPEN**, and now less important: the object's identity is confirmed **three** ways (KCAMPITCH triple, vtable shape, and the clean control pointer with matching vtable **and FName**). |
| 11 | **★ NEW — the guard has never run** | — | **OPEN and now the top item.** Zero live runs of any fix exist. §0.5 is the ordered sitting. |
| 12 | **NEW — spawn-`FTransform` truncation** | — | **FIXED behind `KXFORMFIX`** (default 1) — `xfsz 0x50→0x60`, four `Scale3D` offsets `0x38→0x40`, and `BuildHeroBody`'s `savedXform` truncation that made **registration re-apply `Scale.Z=0`**. ⚠ **Residual:** `DoCheatSpawn` (`:4335`) still leaves `Scale3D=(0,0,0)`; RM_CHEATSPAWN only, off the RM_PLAY path. |
| 13 | **NEW — three leftover S94 diagnostics still ON** | — | **OPEN.** `KCHEATSPAWN` (`:2872`), `KSMACTOR` (`:2878`), `KSTATICTEST` (`:2881`) all execute inside the single post-build hook hit, in the +0.15 s window. `KTESTACTOR` was flipped to **0**; these three were not. §0.5 Run 5 bisects them. |
| 14 | **NEW — `PendingViewTarget` arm is untested** | — | **OPEN, minor.** `PendingViewTarget.Target` (PCM+0xC40) is **NULL in 4/4** dumps, so one of the guard's two write arms has never been exercised by the measured signature. A run in which only that line fires is a **new phenomenon**, not a repair of FK-7. |

### Process lessons

1. **Take the faulting PC from the minidump `CONTEXT`, never the `CrashContext` XML** — the XML mixes
   faulting PCs with return addresses (§3.1).
2. **`tools/re/parse_minidump.py` reads `MINIDUMP_THREAD` at the wrong offsets** (MEASURED). It uses
   `Teb@+16` as stack base and `StartOfMemoryRange@+24` as `{DataSize,Rva}`. Correct layout:
   `Tid@0, Susp@4, PriCls@8, Pri@12, Teb@16, Stack{Start@24,DataSize@32,Rva@36},
   Context{DataSize@40,Rva@44}`. With the wrong offsets, 123 of 4009 ranges land past EOF and the range
   total reads **170,996 MB for a 13.7 MB file**; corrected, 0 bad and 6.82 MB. **Any earlier
   conclusion from that script's stack-walk or per-thread contexts should be re-checked.**
   `tools/crashtri/mdctx.py` supersedes it. (The exception-stream context, stream 6 + 160, was
   unaffected and correct.)
3. **Negative evidence from a ~7 MB minidump is worthless** for a multi-GB process (§2.3).
4. **Do not pool crashes by "family" before checking the faulting PC and the fault operand** — §2.4
   pooled two different bugs and hid a real split.
5. **A number that matches is not a mechanism.** The 61.1 s GC story fit the window and was still
   wrong; the confirming event (`LogGarbage`) was never once checked for, and it never appears.
6. **Added S106e — check the DENOMINATOR before the correlation.** *"cloth==1 ⇒ 4/4 crashed"* had perfect
   separation and was measuring the shim's `RunMode`. Before believing a 4/4-vs-0/5 split, ask **what else
   differs between the two cohorts** — here, the entire experiment did.
7. **Added S106e — before trusting a discriminator, compute what it returns when the hypothesis is
   FALSE.** `delta=+0x3F` is arithmetically forced by the allocator; it returns the "confirming" value for
   *both* candidates and for the clean control. A test that cannot fail is not a test. This one shipped
   inside the fix's own instrumentation and would have produced a false positive on the first run.
8. **Added S106e — a fix's build vintage is a variable.** The four camera dumps span three builds, none of
   them the candidate's, and the sub-family split correlates perfectly with a commit boundary. **A positive
   control on the exact artifact under test is not optional**; without it, "it survived" cannot be
   separated from "this build never had the bug."
9. **Added S106e — `git show <commit>:<path>` is a per-session instrument.** `docs/tutorial-launch-marker.txt`
   is tracked, so the shim mode and flags of past sessions were recoverable in one command for the whole
   investigation, and were never looked up. It answered Blocker 2 outright. See **FK-25**.

### Tooling produced

`tools/crashtri/{harvest,mdctx,deadobj,ptrhunt}.py`, `crash_census.csv` (86 rows), `README.md`;
`tools/re/crash_corpus.py` (`survey` / `cluster` / `ctx`); `tools/sigbypass-mod/{build.ps1, BUILD.md,
verify_dll.py}`.

**Nothing was launched or injected. The 86 crash dumps were opened read-only.**
