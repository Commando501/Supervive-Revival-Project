# Session 75 (2026-07-12/13) — force-open route: WASD movement + feature-toggle readiness → CEILING CONFIRMED

Goal (from the S75 handoff): chase HERO MOVEMENT (WASD) on the S74 force-open tutorial hero.
Outcome: **movement is achievable client-side (velocity puppet), but real movement engages
deploy-gated subsystems (mantle / feature toggles) that the packer + deploy-wiring block. The
client-side force-open route is EXHAUSTED. The DS route is the path forward.**

> NOTE: `docs/session-75-movement-diagnosis.md` is an EARLY artifact of this session and its
> "the CMC is dormant / deploy-gated" conclusion was later **DISPROVEN** (see "Movement" below —
> the CMC works; the hero was just under the map). Read this file for the corrected story.

---

## Part 1 — MOVEMENT: the CMC works; positioning + a custom input pipeline were the real issues

**Early (wrong) diagnosis:** poking `GravityScale=1.0` on the possessed hero produced no fall
(Velocity stayed (0,0,0)) → I concluded the CMC was "dormant / deploy-gated." **This was a
confound:** the hero was at Z≈0.5, *wedged under the terrain* (the S74 lift + a bad spawn spot).

**Corrected (user caught it — "we're under the map"):**
- Read the hero's actual world position (root capsule `RelativeLocation` @ SceneComponent+0x158):
  it was **under the map**. The S74 spawn used the camera-viewpoint XY, a hole.
- **Teleport the hero above ground → it FALLS with real physics** (velocity −588, collision-swept).
  At a good XY (the CapturePoint, −65,−1770) it **landed and entered MOVE_Walking**. So the CMC
  simulates fine — the earlier "dormant" reading was purely the under-map wedge.
- Map spawn points (Actor `RootComponent`@+0x1B0, loc@+0x158): `BP_LokiPlayerStart`(−3206,5070,**100** —
  a HOLE, no walkable floor), `BP_CapturePoint_Tutorial`(−65,−1770,**300** — good ground),
  `BP_LokiRespawnBeacon`(−2723,−2627,0). Tool: `tools/re/actor_locs.py`.

**WASD input does NOT reach the pawn (custom pipeline):**
- `input_watch.py` sampled the pawn's `ControlInputVector`@+0x418 / `LastControlInputVector`@+0x430
  and CMC `Acceleration`@+0x328 while the user held WASD → **all zero.** Jump works, WASD doesn't.
- `IgnoreMoveInput` counter is at **PC+0x449** (found by disasming `ResetIgnoreMoveInput` = PC
  vtable slot +0x8B8 → impl `mov byte[rcx+0x449],0`). Cleared it to 0 (verified) — **still no input.**
- **Forced `AddMovementInput(+X, bForce=true)` 6706× → still zero accel/velocity.** So SUPERVIVE's
  movement does NOT use the stock `ControlInputVector` path in the un-deployed state.
  `GetMovementInputVector` (thunk `0x7FF6BA7FC770` → impl `0x7FF6BAA9CC50`) reads CMC `Acceleration`@+0x328,
  gated on `[[CMC+0x198]+0x160(Role)]>=2` (Authority passes).

**★ Velocity PUPPET makes WASD work (RM_PUPPET):** directly poking CMC `Velocity`@+0xE8 = +X each
game-thread hit MOVES the hero with full collision (X −65→443, then slid along a wall). So a puppet
that reads `GetAsyncKeyState(WASD)` and writes CMC velocity each frame gives WASD movement. Built as
`tutorial_launch.cpp` `RM_PUPPET` (build `-DKRUNMODE=RM_PUPPET -luser32` → `tutorial_launch_puppet.dll`;
`-DKPUPSPEED`/`-DKPUPYAW`). **BUT it CRASHED the game the moment the hero moved:** Loki.log tail =
`ULokiGameFeatureToggles::Get FudgeMantlingSouth called when feature toggles were not ready` burst →
Sentry. `FudgeMantling` = SUPERVIVE's ledge-mantle feature; moving engages the mantle subsystem, which
queries the un-ready feature toggles and crashes. **So the movement puppet is crash-prone, and the real
blocker is feature-toggle readiness.**

---

## Part 2 — FEATURE-TOGGLE READINESS: RE broke the packer wall, but the FIX is blocked

**The RE (callxref defeats the packer for CALL graphs — only string-xref + reflection are dead):**
- `ULokiGameFeatureToggles` is a static C++ store (NOT a UClass, 0 instances, `Get` not a UFunction).
- Found `Get` via callxref on the readiness helper `0x7FF6BAACDA50` → the toggle-query pattern →
  **`0x7FF6BAACB6DE` = the checked `Get` that logs "not ready"** (0 direct callers — indirect dispatch).
- Its gate, disassembled: **`test byte[D+0xB3], 0x40; jz <not-ready>`** (bit 6), where
  `D = [ [obj→vtable[0x188]()→storeGetter 0x7FF6BAB80AC0 (=[+0x258])] + 0x5A0 ]`. Get also bails if
  `C=[B+0x258]` is null (a SECOND failure mode). Readiness is checked on the **passed object's** D,
  so it's **per-object** — deploy sets it across all subsystem objects; force-open doesn't.

**HOOKING Get is PACKER-BLOCKED (definitive):** built a detour on `0x7FF6BAACB6DE` to set the bit.
Crashed hard (no Sentry). Fixed a real stack-align bug (Get is entered via indirect TAIL-JMP →
entry rsp not call-aligned; added rbp-based force-align) — still crashed. Reduced OnGet to
**record-only** (zero game-fn calls, just LooksLikePtr + array) — **still crashed identically.** So
it's the act of patching the `Get` region, not my logic. The ProcessInternal hook (same stub pattern,
`base+0x13454A0`) works, so the packer **tamper-protects the `0x7FF6BAACB...` region** (its
re-encrypting/verifying pages — same behavior that hid the S61 strict-Login page). 3 crashes here.

**PURE-RPM POKE — WORKS + SAFE, fixes ONE category, then hits the deploy wall:**
- D's class is **`LokiServerAuthConfig`** ("ServerAuthConfig"). Resolved D via the CMC **applier**
  (`[CMC+0xC0]`, identity vfn188 `0x7FF6B64719F0`): applier→[+0x258]=C→[+0x5A0]=D.
- Enumerated all 11 `LokiServerAuthConfig` via GUObjectArray (`toggle_d_scan.py`): 10 NOT ready
  (`byte[+0xB3]=0x00`). **Poked bit6 on all 10 → `DeadSpectatorCameraLock` spam STOPPED** (pure RPM,
  no injection, no crash, bits stuck). **This is the demonstrated win — the mechanism is real.**
- **But 3 toggles keep spamming** (FudgeMantlingSouth, CursorCharacterAim, AttachAudioListenerToHero):
  - hero/PC vfn188 (`0x7FF6B887C990`) is a weak-obj-ptr resolver → **B = PersistentLevel**, and
    `[Level+0x258] = NULL` → Get bails at the **C-null check** (failure mode #2 = deploy-time config
    WIRING, not a bit). Poking `[Level+0x258]` to a valid C didn't help (validation/wrong object).
  - CMC vfn188 (`0x7FF6B75B5380`) returns `[CMC+0xC0]`=applier (=LokiServerAuthConfig, already fixed),
    yet FudgeMantling still spams → it's queried via some OTHER object I can't identify (the hook
    that WOULD identify it is packer-blocked).

**HONEST CEILING:** client-side toggle-ready is EXHAUSTED. Mechanism proven + one category fixed
safely, but the full fix needs (a) the packer-blocked hook to enumerate the query objects, and (b)
deploy-time config-pointer wiring on the Level across subsystems — i.e. **replicating deploy**, which
is exactly what a real dedicated server does at round-start.

---

## Key addresses/offsets (this build, base 0x7FF6B54F0000 — stable across relaunches; heap VAs per-launch)
- Movement: `bCharacterMovementEnabled`@LokiChar+0xB59; CMC `MovementMode`+0x231 `MaxWalkSpeed`+0x278
  `GravityScale`+0x1A0 `Velocity`+0xE8 `Acceleration`+0x328 `UpdatedComponent`+0xD0; Actor `Role`+0x160
  `NetDormancy`+0x161 `RootComponent`+0x1B0; SceneComp `RelativeLocation`+0x158 `Mobility`+0x1BB;
  Pawn `ControlInputVector`+0x418 `Controller`+0x400; PC `IgnoreMoveInput`+0x449.
- Feature toggles: checked `Get`=0x7FF6BAACB6DE (gate `byte[D+0xB3]&0x40` + C-null); unchecked Get=
  0x7FF6BAACB6C0; GetSingleton=0x7FF6BABE0330; storeGetter([+0x258])=0x7FF6BAB80AC0; realGetter=
  0x7FF6BAACB370; readinessHelper=0x7FF6BAACDA50. D class = `LokiServerAuthConfig`, readiness byte +0xB3.

## New reusable tools (this session)
`tools/re/`: class_props.py, hero_move_census.py, actor_locs.py, input_watch.py, toggle_d_scan.py,
config_ready_scan.py, resolve_obj_d.py. `tools/sigbypass-mod/tutorial_launch.cpp`: RM_WAKEMOVE,
RM_PUPPET, RM_TOGGLEREADY modes (+ BuildGetHook function-detour infra — note: detouring the Get
region is packer-blocked, but the pattern is reusable for non-protected regions).

## Bottom line → DS route
Force-open delivers: real gamemode init, GoToPhase round-advance (S74), spawn/possess/aim/jump, AND
now **WASD movement via the velocity puppet** — but real movement engages deploy-gated subsystems
(mantle/feature-toggles) that crash, and toggle-readiness is deploy-wiring the packer blocks
client-side. A genuinely playable, non-crashing tutorial needs the server-side deploy. See
`docs/next-session-prompt-s76.md`.
