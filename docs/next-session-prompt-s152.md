# S151→S152 — Move 4 flown, value-seeding wall beaten, thunkExact identified

**Paste this whole file as the opening prompt of a fresh session.**

You are continuing the SUPERVIVE revival project at
`G:\git\Supervive Revival Project` on branch `dedicated-server-stub`.
Read `CLAUDE.md` (auto-loaded); its "Current-frontier override" at the top
is stale from before S151 lifted it for versus-AI work. Read this doc for
the current state.

---

## 0. What happened last session

Move 4 (S148 self-damage flight) was flown from the S151 handoff. The flight
produced **four major measured findings** and one significant FK-1 register
update, without a HEALTH_APPLIED headline but with the "how" of the wall now
fully mechanistic. Full evidence in
`docs/move4-external-poke-PREREGISTERED.txt` (start there).

### Flights (attempts 1, 2, 3)
- Attempt 1: helper binder defect (fixed in `configs/s148-move4.ps1` —
  passes `-Probe $S148Dll` as a placeholder since `-SkipProbe` doesn't relax
  fk24-stage.ps1's Mandatory attribute).
- Attempt 2: FK-31 staging kill at T+12s-post-fo. Dump preserved at
  `dumps/crash-20260901-215624/` (66.09% readable — highest single-dump
  coverage in project history).
- Attempt 3: **staging cleared, bind persisted 10h+, S148 preflight refused
  on `issues=0x200 = S148_ISSUE_MAX_HEALTH_BELOW_SEED`**. Because both
  Health and MaxHealth read 0.0 — nothing on the shipped force-open path
  seeds attribute VALUES. See `s148_damage_calibration.h:398`.

### The external-poke arc (novel, session-original)
User authorized poking Health/MaxHealth externally on the still-alive Move 4
attempt-3 process:
- 4× `WriteProcessMemory` seeded `Health.Base/Current + MaxHealth.Base/
  Current = 1000.0` (bits `0x447A0000`). Readback-verified. Persistent
  through S148's full lifecycle (setup → preflight → resolve → refuse →
  disarm) for 12+ seconds and unchanged across 11h uptime.
- Re-injected S148. **Preflight PASSED (`issues=0x0`, first time ever on
  the force-open route, all 22 preflight bits clean).**
- New downstream refusal: **`RESULT=ADJUST_UNRESOLVED (thunkExact=NO)`** —
  see mechanism below.
- Data-poke bypass: wrote `Health.CurrentValue = 750.0` (matches S148's
  `expectedCurrent=0x443B8000`), stable across 4 samples over 12s. Simulates
  a successful AdjustHealth(-250) outcome via pure data writes. Doesn't
  prove the game's own AdjustHealth path works, but proves the state model
  from bind→registration→values→post-adjust is coherent and data-drivable.

### The thunkExact bug (offline-verified)

`tools/sigbypass-mod/tutorial_launch.cpp:21224` (codex worktree):
```
bool thunkExact = adjustThunk == g_modBase + 0x5516610;
```

Comment at line 17261 documents `0x5516610` as "AdjustHealth [M] REAL". That
IS the IMPL address — but `adjustThunk` is the reflected `Func @+0xE0`,
which for a reflected native function with parameters is always a UHT-
generated exec WRAPPER, not the impl. Verified live:
- Reflected Func RVA = `0x5294270` (decrypted, MSVC prologue, obvious FFrame
  unpacker shape)
- Impl RVA = `0x5516610` (PAGE_NOACCESS on this build — never executed)
- Wrapper CALLS impl: `0x52942DF: call 0x5516610` (disassembled live)

The check is unsatisfiable by UE construction on this build (and any UE
version that emits exec wrappers for reflected natives with params).

### FK-1 register — 5th entry added

`ULokiCharacter::AuthCheatSetHealth` (Func RVA `0x52FD620`) is a **stripped
stub**. UHT-generated exec wrapper (real MSVC prologue, unpacks the
`NewHealth` float from FFrame), tail-calls the void_ret fold at
`0x52FD68F: call 0xF7EC20`. Discovered offline (no injection cost) BEFORE
building a shim that would have wasted an injection to observe "AuthCheat-
SetHealth call succeeded, Health unchanged".

**New instrument-artifact instance:** a prologue-signature check for known
folds MISSES a stripped stub whose exec wrapper has a real MSVC prologue.
Only full-body disassembly to the tail call reveals it. CLAUDE.md FK-1
block has been updated with this entry.

---

## 1. Live process state (as of handoff writing)

Game is **still alive** at PID 41816, uptime ~11.2h+, in the tutorial world
with:
- Bind live (verifier PASS, `Num=2` SpawnedAttributes)
- Health = 1000.0 Base / 750.0 Current (poked)
- MaxHealth = 1000.0 Base / 1000.0 Current (poked)
- 6 injections resident (gft, fo, sp, bind-only, S148, S148-r2)
- 5 external pokes
- No crashes, no FK-32, no protector-kill signature

Reusable RPM tools created this arc:
- `scratchpad/move4_health_read.py` — read Health/MaxHealth from a live
  attribute set at any PID
- `scratchpad/move4_poke_maxhealth.py` — 4× seed poke
- `scratchpad/move4_poke_current_750.py` — 1× data-poke bypass
- `scratchpad/move4_authcheat_probe.py` — find any UFunction by name, grade
  its Func against known folds (blind to the wrapper-hides-stub pattern —
  see caveat)
- `scratchpad/move4_authcheat_disasm.py` — full-body disassembly of a
  reflected UFunction's Func chain; catches the wrapper-hides-stub pattern
- `scratchpad/move4_thunk_disasm.py` + `move4_thunk_walk.py` — thunk-vs-impl
  RVA comparison + call-chain enumeration
- `scratchpad/move4_page_query.py` — VirtualQueryEx on any RVA, reports
  COMMIT/RESERVE + protection (useful for spotting PAGE_NOACCESS pages that
  encode "this function has never executed in this process")

---

## 2. Recommended next actions (fresh session)

### High-value: rebuild S148 with corrected thunkExact
The frozen S148 DLL from the codex worktree hard-codes the wrong RVA for the
thunkExact check. Two ways to correct it:
- Change the check to compare against the exec wrapper's RVA (build-specific:
  `0x5294270` on this build).
- Change the check to READ the wrapper's tail call at `wrapper + 0x6F` (offset
  of `0x52942DF - 0x5294270 = 0x6F`) and extract the rel32 to derive the impl
  address dynamically. Portable across builds.

Requires codex worktree access (source is at `C:\Users\eastr\.codex\
worktrees\78d0\Supervive Revival Project\tools\sigbypass-mod\
tutorial_launch.cpp:21224`).

After rebuild, re-fly Move 4 with the new S148. Expected: preflight passes
(as it did in S152) AND `RESULT=HEALTH_APPLIED` (game's own AdjustHealth
runs). WALL E Phase 1a proved end-to-end via the game's own code.

### Medium: bypass S148 with a CALL-ONLY AdjustHealth shim
Build a minimal shim (~20 lines) that:
1. Finds the possessed hero
2. Resolves `AdjustHealth` on hero's ASC class via `ResolveFuncNative` (same
   as S148 does)
3. Calls it via `CallNativeGuarded` (S55 primitive) with a single
   FloatProperty arg (HealthDelta = -250)

The S55 primitive TRUSTS reflection and does NO thunkExact check — so this
approach works with the current build. Would prove the game's own
AdjustHealth path works with one new injection.

### FK-1 hunt candidate (offline)
The S152 discovery pattern (disassemble the reflected UFunction's body,
check if the tail call lands on a known fold) is highly reusable. Any of
the 42 reflected exec verbs the FK-13 block enumerates could be a hidden
FK-1 stub. Sweep them all with `scratchpad/move4_authcheat_disasm.py` as a
template. Purely offline; zero injections.

---

## 3. Files created / modified this session

**New files:**
- `docs/move4-external-poke-PREREGISTERED.txt` — full preregistration +
  three post-flight results sections
- `docs/next-session-prompt-s152.md` — this file
- `docs/move4-poke-20260902T140747Z/` — evidence dir (markers, poke log,
  S148 inject log, disassembly)
- `dumps/crash-20260901-215624/`, `dumps/crash-20260901-220045/` — two FK-31
  dumps (60+ MB each) — potentially git-ignored, verify

**Modified:**
- `CLAUDE.md` — FK-1 register updated with 5th entry (AuthCheatSetHealth)
- `docs/coop-vs-ai-roadmap-s142.md` — §3.3 updated with S152 findings
- `configs/s148-move4.ps1` — binder-fix: passes `-Probe $S148Dll` as
  placeholder to satisfy fk24-stage.ps1's Mandatory attribute

**Scratchpad tools (not for git, but reusable):**
- `scratchpad/move4_*.py` — 7 read-only RPM probes described above

---

## 4. What NOT to do (fresh session pitfalls)

- **Don't restart the game if it's still alive when the fresh session opens
  and the user wants to continue.** The 11h+ uptime process is a precious
  RE resource with the bind + values still poked.
- **Don't reuse `scratchpad/move4_authcheat_probe.py` as-is for FK-1 sweeps
  without extending it** — its "grade against known folds" check is only
  looking at the Func's first 8 bytes, which for a stripped UHT exec-
  wrapper stub is INDISTINGUISHABLE from a real function's prologue. Use
  the disasm variant that catches the tail-call-to-fold pattern.
- **Don't re-fly Move 4 with the frozen S148 DLL and expect
  `HEALTH_APPLIED`** — thunkExact is unsatisfiable on this build. Fix the
  shim first.
- **Don't test AuthCheatSetHealth via a shim.** Already proven stripped
  offline (FK-1 family). Any call to it will succeed with no Health change,
  which reads like "the call worked but did nothing" — the classic FK-1
  false-positive shape.

---

## 5. Session evidence for cross-checking

If the fresh session's user disputes any claim above, verification paths:
- `bind live`: `python tools/re/move4_bind_verify.py <PID> --hero 0x15FF153D560`
  (if game still alive)
- `values seeded`: `python scratchpad/move4_health_read.py <PID> 0x15F109D5500`
- `thunkExact bug`: read `tutorial_launch.cpp:21224` in codex worktree
- `AuthCheatSetHealth stripped`: `python scratchpad/move4_authcheat_disasm.py
  <PID>` on any live game

The docs/move4-external-poke-PREREGISTERED.txt file is the primary evidence
document — everything above is a summary of it.


---

## 6. LATE ADDITION — post-commit FK-1 batch hunt (2026-09-02, still same session)

After the main S152 commit was pushed, the user requested one more experiment
on the still-alive process. Ran the FK-1 batch hunt described in section 2 above,
plus two smaller probes:

### FK-1 batch hunt (`scratchpad/move4_fk1_batch_hunt.py`)
- Live disassembled 746 UFunctions matching `Auth*|Server*|Grant*|Kick*|Ban*|
  Force*|Debug*|Broadcast*|Init*|*Cheat*` (v1+v2 sweeps)
- **95 STRIPPED entries confirmed live** (12.7% rate — 11x the image-wide 1.2%
  base rate for empty impls)
- Fold distribution: 80 → `0xF7EC20` (void), 12 → `0xF7EB60` (LokiIsServer false),
  2 → `0xF7EB50` (nullptr getter), 1 → `0xFC6CF0` (0.0f)
- Full evidence: `docs/fk1-batch-hunt-s152.md`
- CLAUDE.md FK-1 block updated with summary + tool pointer

### Widget hunt (`scratchpad/move4_widget_hunt.py`)
- Enumerated live UUserWidget instances; found multiple Health-related widgets:
  `ProgressBar_Health`, `BAR_Health`, `WBP_HUD6_Healthbar`, `HealthBarWidget`
  (world-space LokiWidgetComponent)
- Widget infrastructure IS instantiated in the tutorial world; UMG binding
  verification would need visual (screenshot) confirmation

### Death probe (`scratchpad/move4_death_probe.py`)
- Wrote Health.CurrentValue = 0.0 for 8s
- **Zero game-side reaction**: no self-healing, no OnRep, no death path, no
  log line about damage/dying/state change (18 new Loki.log lines during
  window, all unrelated — Vivox/AccelByte/PartyManager)
- Restored to 1000.0 cleanly

### Key implication for fresh session
The FK-1 batch hunt independently confirmed several CLAUDE.md open items
(S131 rideable stubs, WALL E hostility stubs, dismount block). Any shim
design that plans to call one of these 95 UFunctions is a wasted injection.
**Cross-check the full list at `docs/fk1-batch-hunt-s152.md` before building
ANY new shim.**

### Notable new FK-1 entry from v2 sweep
**`LokiCharacter::ForceDeath` is stripped** (Func RVA `0x05289020` →
`0xF7EC20` void). Combined with the death-probe finding, the "kill hero"
path is fully closed client-side by two independent mechanisms.


---

## 7. FURTHER ADDITIONS — dumpimage + AS census + AS Func probe (2026-09-02)

Three more probes on the live process after commit 5919e35, before cleanup.

### dumpimage (`dumps/move4-post-s152-12h-20260902T142000Z/`)
- Captured the 12h-uptime Move 4 process at 67.47% .text readable — highest
  single-dump coverage this project has ever taken.
- Merged into `dumps/merged14.dump.exe`: **+14 pages of new coverage** (57,344
  bytes of decrypted .text that no prior dump captured), 0 conflicts.
- `merged14.dump.exe.txt`: 169.9 MB, 51.94% non-zero (all-section metric;
  the .text metric alone is higher).
- Every future offline RE benefits from these pages. Update `strxref.py`'s
  DEFAULT_DUMP to `dumps/merged14.dump.exe` if desired.

### AS UClass census (`scratchpad/move4_as_census.py` +
`scratchpad/move4-as-census.out.log`)
- Answers CLAUDE.md's S113 open question: are AS UClasses registered in a
  LOADED MAP (S113 measured "not at menu")?
- **YES. 5 AS UClasses live in the tutorial world:**
  - `LokiDropShip`, `LokiDropPod`, `LokiRespawnComponent`, `LokiGem`,
    `FFABotSpawnerComponent` — all with class `ASClass` (Angelscript
    class-generator UClass)
- Also 3 non-AS classes with matching names live: `LokiTutorialGameMode`,
  `LokiDropInGameMode`, `LokiAirship` (regular `Class` = native).
- 2 AS UFunctions live: `Respawn` (on LokiRespawnComponent), `SpawnDropPod-
  ForTeam` (on LokiDropShip) — class `ASFunction_NotThreadSafe_JIT`. The
  `_JIT` suffix independently confirms CLAUDE.md's claim that AS is AOT-
  compiled.

### AS Func probe (`scratchpad/move4_as_func_probe.py` +
`scratchpad/move4-as-func-probe.out.log`)
- For both live AS UFunctions found above, read `Func @+0xE0`.
- **Both read NULL.** Page is NOACCESS.
- **Confirms CLAUDE.md's FK-22 note** (previously [I, strong] from menu-only
  measurement): the S55 direct-thunk primitive does NOT reach AS UFunctions
  even in a loaded tutorial world. The NULL Func is durable, not a menu-
  scoping artifact.
- **Any future AS-callability test must use `ProcessEvent` slot 78** (per
  FK-22 §21.2), not S55.

### Combined implication for the fresh session
The AS layer's callability route is now measured live and specifically:
- UClass registration: **only in loaded map** (measured both directions)
- UFunction dispatch: **ProcessEvent slot 78 only** (NULL Func rules out
  S55, measured on 2/2 AS UFunctions in a loaded map)

For the recommended S148-rebuild-or-bypass path in section 2 above, this
doesn't change the AdjustHealth analysis (AdjustHealth is native, not AS).
But if any successor arm targets the AS-layer respawn/pod chain from
CLAUDE.md's FK-1 SETTLED block (`LokiRespawnComponent::Respawn`,
`LokiDropShip::SpawnDropPodForTeam`), it must use ProcessEvent, not S55.

### Files added
- `dumps/move4-post-s152-12h-20260902T142000Z/` — dumpimage output
  (gitignored; ~169 MB + private exec regions)
- `dumps/merged14.dump.exe` (gitignored — 169 MB)
- `scratchpad/move4_as_census.py` + `move4_as_func_probe.py` (reusable
  live-process probes)
- `scratchpad/move4-as-census.out.log` + `move4-as-func-probe.out.log`
