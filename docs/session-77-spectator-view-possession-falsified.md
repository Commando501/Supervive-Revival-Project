# Session 77 — DS route: stable spectator view of the live world REACHED; possession-culprit FALSIFIED; loading-stall root-caused; garbage-thread AV needs route A

Date: 2026-07-15. Continues S76 (stub durably stable via the `ALokiWorldSettings` non-push mirror).
Goal: get *any* functional control in the tutorial — a hero or even just a spectator camera — that
**moves without crashing** over the live tutorial world, via the DS stub. Attack the movement
garbage-thread AV.

## TL;DR
- ★ **MILESTONE: a stable, rotatable spectator view of the live tutorial world** — cleanest yet. Injected
  `ds_hybrid.dll` `MODE_SPECTATOR_CAM` into the DS-connected client: it hid the `WBP_UI_MatchTransition`
  overlay (4/4 loading widgets `SetVisibility(Collapsed)` each tick) → the world rendered fully (portal
  shield, terrain, drop-pads) with **360° camera rotation and ZERO crash for ~2 min** on a genuinely stable
  stub. (S76's fly-cam "win" was confounded by the crashing stub; this one is clean.)
- ✖ **Possession-culprit hypothesis — FALSIFIED.** The stub possessed a concrete `ADefaultPawn` instead of
  the abstract `ALokiCharacter` (S73's `LokiCharacter` is `CLASS_Abstract` → the client can't spawn its local
  replica → half-formed possessed-pawn → suspected movement AV). `ADefaultPawn` replicated cleanly (no
  `abstract` spawn-fail on the client), but **the garbage-thread AV STILL fired** → the culprit half-hydrated
  replica is **NOT** the possessed pawn.
- ✖ **`EGP_SpawnSelect` loading-clear — does NOT reproduce.** Reverted the seed `EGP_Combat(7)` (a stale S73
  lever-2 experiment) → `EGP_SpawnSelect(4)` (the S70-proven loading-clear phase). The client received it but
  the loading overlay **still stayed** — the S70 clear does not reproduce on the current (Loki-PC) config.
- ◆ **Loading-stall ROOT-CAUSED (new):** it is the **Loki PC (S73)** running SUPERVIVE's real, round-gated
  match-entry flow — not the tutorial mode. Specifically the overlay-dismiss hinges on a **lost
  `GameEvent_SpectatorStateChanged_PlayerController` broadcast** (`LogGameEventRouter: Router was not found!`
  fired exactly once at match-entry) — no `GameEventRouterComponent` is registered on the bare-native PC — plus
  round-gated `ULokiGameFeatureToggles`. S70 cleared the overlay only because it ran a **stock PC** (generic
  flow, no Loki match-gate). Loki-PC control and a stock-PC-cleared overlay are mutually exclusive on the stub.
- → **NEXT = route A:** the AV is a half-hydrated replica spinning a stale callback into a thread; the faulting
  thread has RIP=RSP=garbage and **no stack**, so the culprit must be caught at the SPAWN. Build a thread-dispatch
  diagnostic shim.

## The garbage-thread AV — re-confirmed, characterized
`parse_minidump.py` on the fresh dump (`…/.sentry-native/reports/285a05a2-…dmp`):
```
ExceptionCode=0xC0000005  ExceptionAddress=0x7FF90E000001  params=['0x8', '0x7ff90e000001']
faulting thread: RIP=0x7FF90E000001 RSP=0x7FF90E000001
  stack return-address chain (callers):   <empty>
exc_addr 0x7FF90E000001 not in any listed module
```
`0x8` = execute violation at an unmapped address; **RIP and RSP both = the garbage address, empty stack** = a
thread launched with a stale callback pointer as its entry, execute-AVing on the first instruction. Same
signature as S53/S54/S76; the value `0x7FF90E000001` is the **S76 pre-drop-stage** replica (distinct from the
`0x7FF8F04…` earlier-stage one). The AV fired only after the shim hid the overlay and the client advanced into
the spectator/pre-drop-active state (~2 min in) — i.e. advancing the match stage engages the next
half-hydrated replica (the S76 whack-a-mole, one stage deeper). The faulting thread carries no info about who
spawned it → the SPAWNING thread has the info → route A.

## What changed (committed this session)
- `unreal-stub/Source/Loki/LokiStubGameMode.cpp`:
  - `PostLogin`: possess a stock **`ADefaultPawn`** (was abstract `ALokiCharacter`). Falsified as the AV fix but
    a **cleaner baseline** — concrete, replicates, no client `abstract` spawn-fail. Not load-bearing; revert to
    `ALokiCharacter` (both spawn calls) only if hero-typed possession is wanted again.
  - `InitGameState`: seed `CurrentPhase = EGP_SpawnSelect(4)` (was `EGP_Combat(7)`, the stale S73 lever-2
    experiment). `EGP_SpawnSelect` is the S70-documented playing phase; genuine cleanup (loading-clear needs it
    but is not sufficient — the Loki-PC gate dominates).
- `tools/sigbypass-mod/ds_hybrid.cpp`: `kMode = MODE_SPECTATOR_CAM` (the mode that achieved the stable spectator
  view). Build: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS ds_hybrid.cpp -o ds_hybrid.dll -lkernel32 -luser32`.
  Inject: `tools/inject/inject.exe mmap <PID> ds_hybrid.dll`. Marker: `docs/ds-hybrid-marker.txt`.

## MODE_SPECTATOR_CAM live result (marker)
```
[SPEC] totalWidgets=1196 loadCandidates=4 svThunk=0x…(InVisibility@0x0) cam=0x… pc=0x…
[SPEC] moveComp=0x… class=SpectatorPawnMovement velOff=0xE8 vel=(0,0,0) updComp=0x… hwnd=0x0
[SPEC] hit 6200: overlay hidden 4/4; puppet moveComp=0x… yaw=0
```
- Overlay-hide WORKS (4/4 loading widgets collapsed). World rendered; 360° rotation via the native
  dead-spectator camera. NO crash for ~2 min.
- **No translation:** `hwnd=FindWindowA("SUPERVIVE")=0` (title lookup failed, so the focus guard was bypassed —
  puppet reads WASD always), but the `SpectatorPawnMovement` velocity puppet (velOff=0xE8) did NOT translate the
  view — the native dead-spectator camera is rotation-only and the integrator did not move the pawn. (Then the
  AV fired regardless — the client advancing to pre-drop, not the puppet, is the likely trigger.)

## Loading-stall RE detail (the "dig the flow" result)
Compared the S77 client log to S70's (`session-70-gamestate-loadingscreen-cleared.txt`): IDENTICAL ready-state
(`TryUIReady SUCCESS`, hero-skip "not picked in the current match", `GetLocalLokiPlayerState failed`, Barracuda
content primed). The ONE difference: **PlayerController type** — S70 = stock `APlayerController` (generic flow →
overlay dismissed into spectator); S77 = `ALokiPlayerController` (S73, runs the real Loki match-flow → overlay
gated on drop-in/round-start). Schema (`schema.txt`): the "router" is a `GameEventRouterComponent`
(native `ActorComponent`) registered with `GameEventRouterSubsystem` (GameInstanceSubsystem) by a
`GameEventRouterOwnerInterface` owner; the UI listens via `UIEventRouterSubsystem`. `GameEvent_SpectatorStateChanged_PlayerController`
carries a `PlayerController` — its router is expected on the PC. "Router was not found" fired exactly once at
match-entry ⇒ a **lost event**: the spectator-state signal that would dismiss the overlay was dropped because no
router is registered (the DS client's PC is the bare native `LokiPlayerController` — the stub's by-path mirror —
without the `BP_LokiPlayerController_Dev_C` components that register it; same root as S76). Barracuda/BR flavor
is incidental (S70 loaded the same map/content and still cleared). NOT seedable from the stub. A more targeted
client-side lever than the blind overlay-hide would be: register a `GameEventRouterComponent` on the local PC +
re-fire `SpectatorStateChanged` — untested; deferred behind the AV.

## ★★★ ROUTE A RAN (dump analysis) — the crash is the ANTI-TAMPER, NOT a nameable replica. Reframes ~15 sessions. ★★★
Instead of a live thread-hook shim, analyzed the EXISTING dump's ALL-thread contexts + the faulting thread's
EXCEPTION context (scratch tools `dump_threads.py` / `dump_faultstack.py`; the dump has 135 threads w/ stacks +
709 memory regions). NOTE: `parse_minidump.py` line 65 has a print bug (`RSP=%X % (rip and rip or 0)` prints RIP
twice); the REAL exception context is **RIP=0x7FF90E000001, RSP=0x586233FC68** (a valid stack — not garbage).
Four signals reframe the crash:
1. **Fixed crash address across boots (decisive).** `0x7FF8F0400001` = S53/S54 (2026-07-07); `0x7FF90E000001`
   = S76 + S77 (2026-07-14/15). IDENTICAL across launches with DIFFERENT ASLR bases (this launch's SUPERVIVE
   base = 0x7FF6AF000000). A half-hydrated GAME replica's stale callback would be an ASLR'd game `.text` address
   (different every launch). A fixed value in the SYSTEM-DLL GAP is per-boot-stable ⇒ an anti-tamper sentinel,
   not a game pointer. (Two distinct values = two boot sessions a week apart.)
2. **Register state = obfuscated dispatch, not a C++ callback.** EXC regs: RIP=poisoned; RSP==RDI==0x586233FC68;
   RCX=RAX=RSI=R12-15=0 (no valid `this`); high-entropy garbage RDX=0x536023A80BBAEC1F, RBX=R10=0x63F8A7E45EE28AAB
   (EQUAL), R8=0xD8CE70962CCE8F64, R9=0x7B7EDAE45A8CB4F0 — a crypto/integrity routine computing a target then
   jumping to poison. A stale vtable call leaves a structured object ptr in RCX + an intact caller frame.
3. **Caller chain wiped.** The faulting thread's EXC-RSP stack has ZERO game-code return addresses (dispatch
   destroyed the return chain). The `+0x7059xxx` game addrs on its DUMP-TIME stack are sentry's own crash-handler
   frames (sentry-native is linked into SUPERVIVE.exe), NOT the culprit. ⇒ route A's "walk the stack → name the
   culprit replica" is a DEAD END — there is no replica to name.
4. **Crash only WITH injection.** Bare client = stable on the loading screen indefinitely (15+ min observed); the
   crash fires ~2 min AFTER injecting a shim (ds_hybrid S76/S77; browse_hook S53/S54) — the documented ~3-5 min
   code-integrity check reacting to the tamper. Variable timing (S54 noted 37s-150s) = triggered when a
   tampered/checked code path runs, not a fixed clock.

**CONCLUSION:** the "movement garbage-thread AV" that drove ~15 sessions of "hydrate the next replica"
whack-a-mole is very likely a MISDIAGNOSIS. The crashes are an **in-match anti-tamper / obfuscated-dispatch
deliberate crash** reacting to the injected shim, not a hydratable half-hydrated replica — which is exactly why
the whack-a-mole never converged (each "next replica" fix only shifted the timing until the integrity check fired
again; S53's "cure" rested on one lucky 428s run). The genuine REPLICATION work (S70-S73 GameState/PC/PlayerState
mirrors) stands — it got the client stable in the live world with a full Loki net stack — but the VISIBLE moving
spectator via an injected shim is **capped at ~2 min** by the integrity check. Making it persistent (or adding
translation, which also needs the shim) requires DEFEATING the code-integrity check — deep, packer-hostile
(CLAUDE.md: permanent patches get caught; the packer's VEH kills the process). That is the honest ceiling.

## (superseded) Route A plan — live thread-dispatch diagnostic shim
The plan below was the pre-dump-analysis intent; the dump analysis above made it moot (no replica to name; the
crash is anti-tamper). Kept for reference / if the anti-tamper hypothesis is ever revisited.
Identify the culprit half-hydrated replica by catching the SPAWN of the garbage thread:
- New `ds_hybrid` mode (e.g. `MODE_THREADWATCH`): inline-hook **`kernel32!CreateThread`** (and CreateRemoteThreadEx)
  — NOT `ntdll!NtCreateThreadEx` (the preloader anti-tamper hooks that; naive re-hook may conflict — S53). Log
  every thread creation's `lpStartAddress` + whether it is mapped (VirtualQuery) + the creating thread's caller
  stack (`RtlCaptureStackBackTrace`, resolved to SUPERVIVE.exe base+RVA). When a thread is created with an
  UNMAPPED start address (the garbage callback), its caller stack NAMES the code/subsystem that spun it.
- Repro: inject into the DS client, hide the overlay to advance to pre-drop, capture the crash-adjacent thread
  creation. Base for this launch was `0x7FF6AF000000` (ASLR — resolve caller RVAs against the live base, not the
  "stable 0x7FF6B54F0000" from earlier sessions).
- If `CreateThread` doesn't catch it (raw NtCreateThreadEx or an APC/corrupted-call rather than a real thread),
  fall back to hooking the UE async/task dispatch (TaskGraph / FQueuedThreadPool / FRunnableThread::Create) or a
  VEH-based approach.

## Gotchas reconfirmed
- In-match anti-tamper blocks external ctypes RPM (works at menu, fails in-match); `inject.exe`/`usmapdump` (C,
  SeDebugPrivilege) still work → drive via in-process shims + minidumps.
- Steam-relaunch pid swap: `launch-redirect.ps1 -NoHook` returns early (handoff process exits, Steam relaunches
  the real game under a new pid) — find the live pid via `Get-Process SUPERVIVE-Win64-Shipping`.
- ags `interactive.go` `ConnectionDetails.address` = `"127.0.0.1:7777"` (on-disk value; HEAD already has it —
  the "committed baseline is ''" note is stale). `forceTutorialMatch=true`.
- Kill `UnrealEditor-Cmd` before rebuilding the stub (LNK1104). Incremental rebuild ~4-14s.
