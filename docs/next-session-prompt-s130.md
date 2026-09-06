# NEXT SESSION (S130) — FK-22: read the actor-pool gate

**Written 2026-08-20, at the end of S124–S129.** Read `docs/fk22-dropphase-reachability.md` §17–§24
before doing anything. This file is the plan; that file is the evidence.

---

## 0. START HERE — first task, offline, no launch

**Read `ActorPoolManagerPrimingConfig` and find out whether the actor-pool feature is enabled by a
CONFIG value.** If it is, the fix needs **no injection at all** — this project's cheapest fix class.

```
.rdata 0x07DDCB20  U  'ActorPoolManagerPrimingConfig'   refs=1
   registrar (GetPrivateStaticClass-shaped)  0x32A7AC0  (55 B)
image  dumps/s129-poolgate/SUPERVIVE-Win64-Shipping.dump.exe   ImageBase 0x7FF7B86D0000
       (fresh live dump taken WHILE the pooling code was decrypted; .text 52.9 % readable)
tool   python tools/strxref/strxref.py --dump <that image> find|xref      (index already built)
```

Questions, in order: is it a `UDeveloperSettings` / config-backed UObject? What properties does it
declare? Does anything on `UActorPoolManager`'s gate path read it? Is it ini-backed — and if so, which
section/key, so it can be set the way FK-11 set `[Core.Log]` and S114 set `[ConsoleVariables]` in the
USER ini (`%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Engine.ini`)?

⚠ Do **not** assume it is the gate. It is a strong lead in the same module, nothing more. §24.4 grades it.

---

## 1. THEN — resolve the gate itself (needs one staged launch)

**The gate is located and machine-verified [M]** (§24.1). In `UActorPoolManager::PrimePools`
(`0x3356000`, 1284 B):

```
0x33560C5  49 8b 06              mov  rax,[r14]              ; r14 = this
           49 8b ce              mov  rcx,r14
           ff 90 d0 02 00 00     call qword ptr [rax+0x2D0]  ; <== THE GATE: virtual, slot 0x2D0 (idx 90), bool
0x33560CB  84 c0 / 75 25         test al,al / jne            ; FALSE -> log + return
0x33560DC  lea rdx,[rip+..] -> slot 0x7F14B20 -> 0x7F14B40
           = 'UActorPoolManager::PrimePools : Feature is not enabled, skipping.'
```

**NOT DONE: resolving what slot `0x2D0` points to.** Do it LIVE — unambiguous, about a minute:

1. stage a tutorial world (recipe in §3),
2. walk `GUObjectArray` (`RVA 0x9E38920`, `ObjObjects` at `+0x10`, chunk table, stride 24, class at
   obj`+0x18`, name id at obj`+0x20`) for a live `ULokiActorPoolManager`,
3. read `[obj]` = vtable, then `[vtable+0x2D0]`, then disassemble that target.

⚠⚠ **`ULokiActorPoolManager` EXISTS** (`.rdata 0x0886F320`, registrar `0x52975D0`) alongside engine
`UActorPoolManager` (`0x07DDDB60`, registrar `0x32A8570`). **Slot `0x2D0` on the live object is
probably the LOKI OVERRIDE** — resolving the engine class's vtable answers the wrong question.

⚠ **`PrimePools` is NOT virtual** — 0 qword pointers to `IB+0x3356000` image-wide [M] — so no vtable
contains it, and the vtable cannot be recovered that way.

⚠ The offline route (class name → `GetPrivateStaticClass` → `InternalConstructor` →
`lea rax,[rip->vtable]`, the S106b technique) was tried and did **not** land: `0x52975D0`'s code-`lea`
targets are `0xF7EC20` (universal fold, ×2), `0x11A5FA0`, `0x32A8570`, `0x5299D00` — and `0x5299D00`
is a **thunk region** (`mov rcx,[rcx]; test rcx,rcx; jne` repeated), not a single constructor.
**That is a route not walked correctly, NOT evidence the vtable is unfindable.**

If the gate reads a **member byte** → a DATA poke on a live object, the safest measured write class in
this project (nothing 0/22 · bytecode 0/9 vs standing `.text` 7/8), then call `PrimePools` directly.
If it reads **config/ini** → no injection needed at all.

---

## 2. ⚠ THE QUESTION THAT COULD CHANGE THE WHOLE REPAIR — ask it early

**Nothing yet ties the null-returning spawn helpers to this gate.** §23 measured
`SpawnPoolableActorFromClass{,Deferred}` returning NULL; §24 located `PrimePools`'s gate. They may be
different mechanisms. **"Priming never ran" and "the helper declines" are different fixes.**

Disassemble `SpawnPoolableActorFromClassDeferred`'s impl (thunk was `0x7FF7BDA4F1A0` in that run's
base — re-resolve, ASLR) and see whether it consults slot `0x2D0` or merely wants a primed pool.

★ **An independent lever that ALREADY WORKS:** the ordinary spawn path spawns this exact class fine
(§23, `dP3 = +2`, a real `BP_DropPod_Tutorial_C` created). If the pool cannot be enabled, hand-spawn
the pod and wire it — `InitializeDropPod` is separately graded (FK-22 §3; the null-`DropShip` guard exists).

---

## 3. HOW TO RUN A SITTING (current — older docs are not)

```powershell
# 1. FLIP THE FLAG FIRST -- it is committed as `false` (the safe baseline):
#    server\internal\interactive\interactive.go -> const forceTutorialMatch = true
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags
# 2. ELEVATED. Steam must already be running.
.\configs\launch-redirect.ps1 -NoHook
# 3. ELEVATED, as soon as it parks (see the timing note below):
.\configs\fk24-stage.ps1 -Probe <dll> -Label <tag> -AllowStale
```

⚠⚠ **`-AllowStale` IS REQUIRED.** Shared edits to `tutorial_launch.cpp` move `fo`/`sp`'s `.text`, but
the DEPLOYED copies (`fo fa184b20934cc4b0`, `sp 4285c0dd22ae9976`) are the known-good ones that staged
successfully all session. **Do not swap staging infrastructure mid-experiment.**

★★ **STAGE PROMPTLY AFTER PARK — [I], n=4, but free to act on.** FK-31 took 2 of 4 staging attempts,
both on long-parked clients; both successes staged near 110 s uptime:

| stage attempt | uptime at staging | outcome |
|---|---|---|
| s127 #1 | 4798 s | died 9 s after `fo` |
| s127 #2 | **113 s** | **succeeded** |
| s128 #1 | 3293 s | died 9 s after `fo` |
| s128 #2 | **110 s** | **succeeded** |

Archive the crashpad dump BEFORE relaunching (`configs\archive-crashdumps.ps1 -Label <tag>`) — the
next launch clears it.

**The stager was broken and is now fixed (S127).** Its park gate used TAIL windows for PRESENCE tests:
`TryUIReady SUCCESS` sat at offset 188,609 of a 1.29 MB `Loki.log` behind a 400 KB window, and
`core-game/matches` at 44,791 of a 79 MB `capture.log` behind a 40 MB window. Both aborted an
**already-parked** client at 420 s each. Replaced with `Test-FileContains` (streaming, whole file).

⚠⚠ Do **not** "fix" the other two `Read-Locked` callers the same way — `Load map complete
.../LVL_Tutorial` is a **RECENCY** test, and a whole-file scan would match a STALE load from an
earlier run. **Presence → whole file; recency → window.** They are different questions.

---

## 4. BUILT ARTIFACTS (imports CLEAN, `verify_dll.py` PASS, `play` = `9bc10a4552c596e1`)

In `tools\sigbypass-mod\build\` — ⚠ **diff `.text`, never size**; several share sizes.

| variant | `.text` | what it does |
|---|---|---|
| `poolspawn` | `d3e1ffb9623f6352` | P0c control + pooled-deferred + pooled + non-pooled ref + census |
| `poolspawn-collmatch` | `365fce2091dbddb0` | same at `collision=2` (the confound-killer) |
| `dropplane_b1only` | `5b4467b0105dec1a` | calls `SpawnPlane`; **creates a `LokiDropShip`** (measured twice) |
| `droppod_pe` / `_pe_ctrl` | `e7771c1705141656` / `ac5b4584066cd927` | Route E ProcessEvent arms |
| `phaseladder` / `-a5` | `8d1821f8c0ddbd63` / `ef0615e76343bce0` | round-phase ladder |

---

## 5. REPO STATE — READ FIRST

- ✅ **Everything from S124–S129 is COMMITTED** — `docs/fk22-dropphase-reachability.md` (§17–§24),
  the S125–S128 markers and session logs, `tools/sigbypass-mod/tutorial_launch.cpp` + `build.ps1`,
  `configs/fk24-stage.ps1`, `tools/re/phase_readout.py`, and this handoff. The tree is clean; start
  from a clean `git status`. ⚠ Built `.dll`s under `tools/sigbypass-mod/build/` are **git-ignored** —
  the hashes in §4 are the record, and a variant must be REBUILT (`build.ps1 -Name tutorial_launch
  -Variant <v>`) and its `.text` diffed against §4 before it is flown.
- ✅ **`forceTutorialMatch` is committed as `false`** (the safe baseline, per CLAUDE.md), and `ags` is
  built from it. **Flip it to `true` and rebuild `ags` before any tutorial sitting**, then set it back
  when done — otherwise a normal launch auto-parks into the tutorial loading screen and looks broken.
- `FPROP_ELEMSIZE` was corrected `0x30` → **`0x34`** (`0x30` is `ArrayDim`, which reads 1 for every
  non-C-array property and made every parameter print `size=1`). That is why `fo`/`sp` read as stale.

---

## 6. TRAPS FROM THIS SESSION — all cost real time

1. ★★ **A reference points at a string's START.** I scanned `0x7F14B66` (where the *substring*
   "PrimePools" begins) instead of `0x7F14B40` (the enclosing string) and got **0 xrefs three times,
   across two images** — one step from filing "COVERAGE-BLOCKED" as a property of the game.
   `strxref.py` had printed a warning about the mirror-image defect **in the same session**.
2. ★★ **Hand-rolled `lea` scans miss `4C 8D`.** `UE_LOG` passes args in `r8`/`r9` (REX.WR). Widening
   was necessary but **not sufficient** — trap 1 masked it, so the widened scan still returned zero and
   **read as confirmation**. ⇒ use `tools/strxref/strxref.py` for string→code work: it found this as
   `refs=1` via a **`ptr-tbl` slot**, a reference class a byte scan cannot see (the code `lea`s the
   SLOT, not the string).
3. **A control that compares two zeros is not a control.** S126's C0c "AGREED" at `(0,0,0)` on a
   positionless ship. Probes now require a NON-ZERO reference and print `WEAK CONTROL (origin)`.
4. **Pre-registered confounds must actually be flown.** §23's collision confound (`P3` used
   `CollisionHandlingOverride=2`, `P1`/`P2` used `0`) was declared before the flight and then flown —
   the only reason "the pool is the wall" is a measurement and not a story.
5. **`build.ps1 -Variant X` without `-Name` used to build the DEFAULT SET and report success.** It now
   refuses. Still: **diff `.text` after every rebuild.**
6. **"The call returned ok" is never a result.** Use the census delta or the verb's own log output. The
   `0xA5` return sentinel is what separated "nothing wrote a return" from "wrote null" — reuse it.

---

## 7. WHERE FK-22 STANDS (all [M] unless marked)

markers (**refuted** — they exist in `LVL_Tutorial`; `Skylands_WP` has none)
→ phase (**solved** — one `GoToPhase` call self-drives the round to `EGP_Combat`)
→ subscription (**dead by construction** — `ServerOnly` is `mov byte [rdx],0; ret`, so the DropPlane
  bind in `ReceiveBeginPlay` is unreachable; the component was measured absent from the 7-subscriber
  invocation list)
→ `SpawnPlane` (**faults**, null-deref at rva `0x13495DD`, because 2 of its 3 tagged markers are
  **not streamed in**; reproduced exactly on two independent launches — and it still creates a
  half-constructed plane)
→ `SpawnDropPodForTeam` (**runs via ProcessEvent slot 78 and returns `false`**; the S55 direct-thunk
  route is dead for Angelscript — `Func == 0`)
→ bail 2 = **the pooled spawn declines** (measured; collision confound eliminated)
→ **why the pool declines** ← **YOU ARE HERE**
