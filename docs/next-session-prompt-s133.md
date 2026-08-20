# NEXT SESSION (S133) — the dismount works. The next question is whether the hero can PLAY from where it lands.

**One line: S132 turned `AuthPlayerDetachPlayerFromRidable` into a working deploy primitive — the hero
leaves the pod, is un-hidden, gets its collision and movement back, and is placed at a chosen actor on
real terrain where it stands still. Read `docs/s132-dismount-settled.md` first. §1 is the experiment.**

Written 2026-08-20 at the end of S132. Everything below is reproducible from commit `bd26146`.

---

## 0. WHAT S132 DID

1. Built **`RM_DISMOUNT` (enum 30)** — appends the PlayerState to `ULokiRideableComponent::PlayersAttached`
   with the GAME'S OWN `ResizeGrow` (`0x00F988D0`, the exact function the fifth wall's own tail calls at
   `0x55CD75B`), then calls `AuthPlayerDetachPlayerFromRidable` (impl `0x55CCCB0`, thunk `0x5456100`)
   through the S55 direct `UFunction.Func` thunk. Risk class **DATA**; zero `.text` writes.
2. **Flight 1 — four dismounts on one launch**, hero X = 1.45 M → 4.86 M → 11.65 M → 14.43 M, each
   matching the flying pod's X at its own call time, run 2's hero Y **bit-identical** to the pod's.
3. **Flight 2 — the dismount is USABLE**: with a `LokiPlayerStart` passed as `LandingLocationActor`
   (1,488,146 uu from the pod at that instant) the hero landed **at the PlayerStart**, settled onto the
   floor and held position bit-for-bit for 9 s. ⇒ `GetLandingTeleportLocation` consumes its actor argument.
4. **A within-run negative control ran before every one of the five calls** — same detach, same
   component, same primitive, `PlayersAttached` EMPTY — and never moved the hero.
5. Seven adversarially-verified offline lanes, which agreed with the lead's independent transcription
   and added five corrections (`scratchpad/s132/lanes/`, doc §6b) — including one that **refuted a
   claim the lead had already propagated into `CLAUDE.md`** (§1 of `docs/method-rules.md`, S132-f).
6. Injected `play` onto the dismounted hero: **it initialises, builds the body and the hero RUNS with
   real locomotion animation** — but `play` relocates the hero first, so this does **not** test the
   landing point. See §1, which is written to stop a successor misreading it the way I first did.

---

## 1. ★★★★ START HERE — CAN THE HERO PLAY *AT THE POINT THE DISMOUNT LANDS IT*?

⚠⚠ **THE OBVIOUS VERSION OF THIS EXPERIMENT WAS ALREADY RUN, AND IT DOES NOT ANSWER THE QUESTION.
Read this whole section before designing it, or you will repeat the mistake.**

### 1.1 What was already measured, and what it does and does not show

At the end of S132 the flight-2 client was still up (1,168 s) with the hero standing at the
PlayerStart, so `tutorial_launch_play.dll` was injected onto it. Result:

```
[PL] teleport hero -> ground (-65,-1770,393)          <-- !!! RM_PLAY's OWN hardcoded teleport
[PL] *** init complete: body=BUILT; camera + WASD active ***
[ANIM] self-driven walk START (so the run anim can be captured with no human at the keyboard)
[ANIM] PlayAnimation(run, loop) ok
```
and RPM sampling then found the hero at `(2880.7, -1770.0, 441.2)` — **+2,945.7 uu in +X from
`play`'s own teleport target**, i.e. it really walked, then stopped when the auto-walk window closed.

**✅ WHAT THIS DOES SHOW [M]: a hero that has been through the full dismount is not left in a broken
state.** `play` initialises on it, builds the body, takes the camera, and the hero **runs with real
locomotion animation**. The dismount costs nothing downstream.

**❌ WHAT IT DOES NOT SHOW: playability AT THE LANDING POINT.** `RM_PLAY`'s first act is a hardcoded
ground-teleport to `(KGROUNDX, KGROUNDY, KGROUNDZ) = (-65, -1770, 393)` — S75's known-solid tutorial
ground (`tutorial_launch.cpp:4822-4830`, applied at `:12315`). **It moved the hero off the landing
point before anything else happened**, so the run says nothing about whether the deploy location is
playable. The `[GCW] anim swapping DISABLED` line that follows is the S110 idle-anim GC behaviour
(`KANIMREF` parks the RUN anim, not the idle one) — pre-existing, unrelated to the dismount.

### 1.2 The experiment that WOULD answer it

Two arms, one launch, both trivial:

```
# A: land the hero, then let play take over WITHOUT relocating it.
build.ps1 -Name tutorial_launch -Variant play -DKGROUNDX=-3206.4 -DKGROUNDY=5070.5 -DKGROUNDZ=140
```
⚠ `build.ps1` takes variants, not raw `-D`s — **add a `play-atlanding` variant** whose
`KGROUNDX/Y/Z` are the PlayerStart's coordinates, so `play`'s teleport becomes a no-op *in effect*
and the hero stays where the dismount put it. Better still, add a **`KPLNOTELE`** knob that skips the
teleport block entirely; then the arm tests the landing point itself rather than a coordinate that
happens to match it. **That is the honest version and it is a ~5-line edit.**
⚠⚠ Changing `play` moves its `.text` hash away from the regression-gated `9bc10a4552c596e1`. Build
it as a **new variant** and leave `play` untouched — it is the hard regression gate for the whole
tutorial route.

```
# B: the control -- the same play arm on a hero that was never dismounted (sp's parked hero).
```
Without B, "the hero walks at the landing point" cannot be separated from "the hero walks anywhere".

**Pre-register the readings:**
- A walks and B walks ⇒ **the deploy location is playable** — the biggest result on this route.
- A does not walk, B walks ⇒ something about the landing point (navmesh, streaming, floor) blocks it.
  Read the movement component's mode and `hero+0x1BE8` before concluding.
- Neither walks ⇒ the arm did not initialise; read `[PL] *** init complete ***` first. A missing
  init line makes the whole sitting VOID, not negative.

### 1.3 The staging that produced all of this

```
forceTutorialMatch = true ; go build -C server -o ags.exe ./cmd/ags      (set back to false after)
.\configs\launch-redirect.ps1 -NoHook
.\configs\fk24-stage.ps1 -Probe "tools\sigbypass-mod\build\tutorial_launch_dropplane_b1only.dll" -Label s133 -AllowStale
tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_droppod_pe_cdopoke.dll
tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_dismount_landstart.dll
tools\inject\inject.exe mmap <pid> <the play-at-landing arm>
```

⚠ **Land the hero EARLY.** Use `dismount-landstart` (`KDXLANDING=2`) and inject it right after
Route E, while the tutorial-start cell is still resident — flight 2 found the `LokiPlayerStart` at
uptime ~390 s and flight 1 found **nothing** at ~860 s.
⚠ Inject everything ≥ 20 s apart (S109). Both `play` and `dismount` take game-thread callbacks by
`Func` swap, and each arms and disarms its own, so they do not race — but keep the gap.

---

## 2. THE MOUNT IS NOW BUILDABLE THE SAME WAY — and it would close the ride end to end

S131 established that the fifth wall's round-game-mode value is a **dead guard** (zero RAX reads
downstream) and that its only persistent component-state output is the `PlayersAttached` append.
S132 proved that append is performable by hand. **Everything else the wall's success tail does is a
real, named function:**

```
0x55CD703  LokiTeleportActor(...)                    [M] REFLECTED UFunction, record table
0x55CD70D  hero->SetActorEnableCollision(true)       [M] 0x339A550
0x55CD719  SpawnAndMoveLokiCharacter_MoveStep(hero, &vec)   ⚠ no record, no exec thunk, 2 folds
0x55CD723  hero->SetActorEnableCollision(false)      [M] -- riding, so collision OFF
0x55CD72B  *(float*)(hero+0x1C10) = GetServerTime()  [M] 0x37D9D40
0x55CD738  PlayersAttached.Add(PS)                   [M] -- S132 does exactly this
```

⇒ **a hand-assembled MOUNT is one step away**: teleport the hero to the pod, turn its collision off,
append it to `PlayersAttached`, stamp `+0x1C10`. Then the pod is carrying a rider, and the S132
detach drops it. **That would be board → fly → dismount, complete, with no `.text` write.**
⚠ Grade honestly: `LokiTeleportActor` and `SetActorEnableCollision` are reflected and callable today;
`SpawnAndMoveLokiCharacter_MoveStep` is **not** reflected (raw native address, different risk class,
2 folds of its own) and may be skippable — the teleport may be sufficient on its own. **Transcribe
`0x55C1B20` before deciding.** Free, offline, unstarted.

---

## 3. THE PROBE UPGRADES — DELIBERATELY DEFERRED, AND WHY

The S132 handoff asked for three upgrades to `PdPodDump` first. **They were not done, on purpose:**
`PdPodDump` is shared with `RM_DROPPOD` / `RM_POOLSPAWN`, so touching it moves
`droppod-pe-cdopoke`'s `.text` hash — and that arm is a **precondition** of the dismount flight, so
changing it mid-session would have invalidated the staging chain that was about to be flown. Do them
first thing next session, when nothing is staged.

- ✅ **The offsets are confirmed [M, lane 4, two disjoint instruments each]:** `AActor::bHidden` →
  `Offset_Internal 0x68`, `ByteMask 0x80`; `bAlwaysRelevant` → `0x68`, `ByteMask 0x08`. Same offset,
  different mask ⇒ unfalsifiable by garbage, exactly as the handoff argued.
- ⚠⚠ **BUT the handoff's implementation route is REFUTED: `FBoolPropertyParams` carries no
  `ByteOffset` / `ByteMask` / `FieldMask` fields at all.** The engine derives them at runtime by
  calling the record's `SetBitFunc` on a zeroed buffer. A decoder written against the assumed field
  list reads padding. **The shim reads LIVE `FBoolProperty` objects (`+0x70..+0x73`)**, which is the
  correct route — see `scratchpad/s132/lanes/L4-offsets.md` §4.2-§4.3 and `L5-probe-upgrades.md` §1.
- ⚠ **And every bool reading `fs=1 bo=0 bm=0x01 fm=0xFF` is CORRECT, not a bug** [M, lane 5]: every
  bool the probe has been pointed at so far is a native `bool`, not a C++ bitfield. The two-sided
  control is still worth adding — it is what turns the decode from [I] to [M] — but it is not fixing
  a defect.
- `AttachedCrewPods (0x490)` as an explicit named field, and `ComponentVelocity` on the location line,
  are unchanged asks. ★ `RM_DISMOUNT` already does the equivalent for its own surface: `DxState`
  prints the pod's and the landing actor's live locations beside the hero's. **When the reference is
  moving, print the reference** — that is what made flight 2's discrimination readable in the marker
  alone, where flight 1 needed an external RPM read.

---

## 4. FK-31 — THE REPLACEMENT LEAD MOVED FORWARD (offline lane 6)

`scratchpad/s132/lanes/L6-fk31-runtime-selfbase.md`, adversarially verified.

- **[M] `runtime.dll` located and identity-confirmed** at
  `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll`
  (67,511,496 B, `ImageBase 0x200000000`, `SizeOfImage 0x4066000`), with FK-10's `packer/3.3.1`
  Sentry DSN byte-identical at its recorded file offset `0x7C1BEC`.
- ⚠⚠ **[M] A HARD INSTRUMENT LIMIT THE TASK DID NOT ANTICIPATE: `ImageBase == 0x200000000 == 2^33`.**
  Every *"is this constant the ImageBase?"* test is therefore aliased with ordinary MBA arithmetic on
  bit 33. **That defeats the constant-search method the lead proposed**, and it is a property of the
  target, not of the tool. All 13 candidate `movabs ±(ImageBase+1)` sites are individually refuted by
  their consuming instruction — they are bit-masks and 2^33 MBA.
- **[M] The protector uses a computed-tail-jump architecture**: 4,769 of 18,580 functions end in
  `jmp <reg>`, with targets carried as `movabs reg, -(ImageBase + RVA)` folded into an MBA polynomial.
  **[I] ⇒ a jump to `base + 1` is the NATIVE OUTPUT SHAPE of that dispatch when the resolved target
  RVA is 1** — FK-31 now has a mechanism class rather than a mystery.
- **[M] FK-10's kill primitive re-verified byte-exact, and its OWNER found**: RVA `0x80F7F0` is
  `NtTerminateProcess([this+0x10], 0xDEAD)`, and it is **slot 4 of a 5-method vtable at
  `packer0 RVA 0x1831C0`**, installed by a **constructor at RVA `0x7F86F0`** — that table's only xref
  image-wide. **That constructor is the next thing to read.**
- **[M] The kill routine itself was NOT found**, reported with its coverage denominator:
  **48,129,536 executable bytes scanned** (`.rwx` + `packer1` + `packer30` + `packer31`), with the
  scanner's structural blind spots enumerated.

---

## 5. STILL OPEN ON THE DISMOUNT ITSELF

- **`GetLandingTeleportLocation` (`0x55D89F0`, 963 B, REAL, 0 folds) is untranscribed.** That it
  *consumes* the `LandingLocationActor` is [M]; *how* it derives the point is not. Transcribing it
  would let the hero be aimed precisely rather than "near that actor". Free, offline.
- **The two `0xF7EC20` folds are unnamed** — one on the hero right after the `IsA` gate, one on the
  PlayerState with `dl=3`. `0xF7EC20` has ~165,789 call sites, so the address identifies nothing.
  ⚠ Note the correction: it is `c2 00 00` = `ret imm16 0`, a **VOID no-op** — it does NOT zero `eax`,
  and the repo's "ret 0" shorthand reads as though it does.
- **`0x5586530(hero)` is REAL and unnamed** (reads `hero+0x460`, then `minsd`/`cvtsd2ss` on a vector
  at `+0x240`). ⚠ It dereferences `hero+0x460 / +0x1978 / +0x1980` with **no null checks** — it
  survived all five S132 calls on `BP_HERO_Ronin_C`, but read those three before arming on any other hero.
- ⛔ **`AuthPlayerEnterWorld` (`0x55CCE70`) is FORECLOSED** [M, lane 7] — its two terminal actions are
  direct calls to the stripped `0xF7EB50` and it writes **no** actor or component transform.
- **`C8`/`C9` in the pooled-spawn chain are still unexercised, not excluded** (S130).

---

## 6. REPO STATE

- ✅ Committed at `bd26146`. `forceTutorialMatch` is back to **`false`**.
- **New builds** (`.text` sha256 — ⚠ diff the hash, never the size; `dismount` and `dismount-podland`
  shared a size of 126,976 B):

| variant | `.text` | note |
|---|---|---|
| `dismount` | `53483e6181bb3583` | at HEAD (127,488 B) |
| `dismount` | `03d807ab6d397537` | **FLIGHT-1 artifact** — reproduce from commit `c2cdc56` |
| `dismount-landstart` | `0d5fa554edac53c5` | **FLIGHT-2 artifact**, `KDXLANDING=2` — **use this one** |
| `dismount-readonly` | resolve + gates + controls, writes nothing |  |
| `dismount-appendonly` | append, do not call the detach |  |
| `dismount-podland` | pass the pod explicitly |  |

- **Regression gates, MATCH throughout**: `play` `9bc10a4552c596e1` · `dropplane_b1only`
  `5b4467b0105dec1a` · `droppod-pe-cdopoke` `249a3cd2190eb334`.
- **New cold image `dumps/merged5.dump.exe`** — `merged4` + both S132 live dumps, +6 `.text` pages,
  **0 conflicts**. `dumps/s132-dismount-live/` and `dumps/s132-landstart-live/` are the seeds.
- **Evidence**: `scratchpad/s132/evidence/` (markers 4–9 for flight 1, `f2-marker-*` for flight 2,
  the lead's independent transcription). Pre-flight `capture.log` is in `dumps/s132-logs/`
  (git-ignored) — ⚠ **`ags` DID truncate it this session, 205 MB → 26.6 MB, so the backup rule earned
  its keep.**
- **5 new instrument artifacts** in `docs/method-rules.md`; tally re-derived with the recorded
  command: **70 → 75**.

⚠ **Two operational gotchas that each cost minutes:** the stager's `-Probe` path is
`tools\sigbypass-mod\build\…`, not `build\…`; and **`usmapdump dumpimage` needs the `.exe` suffix** —
without it it prints `ERROR: process … not found (is the game running?)` **while the client is alive**,
which reads as *your poke killed it*.
