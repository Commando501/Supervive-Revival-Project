# Session 76 (2026-07-14) — DS route: the cheat/drop-in lever, run in the strongest-ever position → EXHAUSTED (no crash)

## Goal
Run "the last experiment" (user-chosen fork): in the **DS session** (client has a real Loki PC +
live replicated `LokiGameState` + a valid server Join — the S70/S73 milestone), fire the game's OWN
`LokiPlayerCheats` hero machinery + drive the drop-in flags. This is the one lever never tried with
a valid DS session + a Loki PC + fixed struct-param marshalling all at once. S74 had built the cheat
modes but only ever ran them on the **force-open** client (where the cheat obj is null + the round
gate no-ops). The DS session was the untested, strongest position.

## Setup (all executed live this session)
1. ags: `interactive.go` ConnectionDetails.address `""` → `"127.0.0.1:7777"` (DS route), rebuilt by
   launch-redirect. `forceTutorialMatch=true` unchanged.
2. Stub: `UnrealEditor-Cmd Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi
   -NoSplash -Unattended -abslog=docs/ds-server-s76.log` → **`IpNetDriver listening on port 7777`**
   (UDP 7777 bound, PID 55812). Seeded `ALokiGameState LokiGameState_0 CurrentPhase=EGP_SpawnSelect(4)`.
3. Client: `launch-redirect.ps1 -NoHook` (clean, no shims). Client PID 73512.
4. **DS session reached (verified live, client Loki.log + stub log):** `LVL_Tutorial` +
   `Entering game state LokiGameState` (S70) + `LokiPlayerController_<n>` (S73 Loki PC) + stub
   `Join succeeded`. Client sits as a DEAD SPECTATOR on the "DROP IN… LOADING" screen with the
   `ULokiGameFeatureToggles::Get CursorCharacterAim … not ready` spam — the exact S73 baseline.

## Experiment — two cheat probes injected into the LIVE DS client (tutorial_launch.cpp RM_CHEATSPAWN)
Both built with `-DKRUNMODE=RM_CHEATSPAWN -DKCHEATRESOLVEONLY=false`, injected via `inject.exe mmap 73512`.
The RM_CHEATSPAWN mode is self-contained (no force-open) — it resolves + hooks PI + fires on the game
thread. The native-call primitive **fires cleanly in the DS client** (`hitsGT=1`) both times.

### Probe 1 — CT_SWITCHPLAYING (drive the drop-in / playing-state flags on the Loki PC)
```
[CS] switchPlayingThunk=0x0 finishDropThunk=0x0 pcStateByte@0x160=0
[CS] cheatCDO=0x1F2127DB460 getLocalThunk=0x7FF6BA914F70 schThunk=0x7FF6BA916760 cchThunk=0x7FF6BA83BE80
[CS] heroClass(BP_HERO_Ronin_C)=0x0 worldCtx=0x…1470 (pc=0x…1470) authChangeCharThunk=0x0
[CS] SWITCHPLAYING missing spsThunk=0x0 pc=0x…1470 -> abort
```
★ **The drop-in/state-machine functions DO NOT EXIST on the DS client's PC.** `SwitchToPlayingState`,
`FinishDropPhaseHiding`, `AuthCheatChangeCharacter` all resolve to **0x0**. Root cause: the DS client's
local networked PC is the **bare native `LokiPlayerController`** (the S73 by-path mirror binds the
stub's `ALokiPlayerController` → the client's native class), NOT the `BP_LokiPlayerController_Dev_C`
subclass where S74 found the drop-in machinery (`DropPlaneComponentSetup`/`UpdateIsInDropPod`/
`FinishDropPhaseHiding` @ PC+0xF28). Those functions live one class down, on BP content the stub can't
supply. ⇒ the S74 "drive the drop-in flags" lever is **structurally unavailable on the DS side.**
Also: `BP_HERO_Ronin_C=0x0` — hero classes aren't cooked into a spectator's memory.

### Probe 2 — CT_CHANGEHERONAME (resolve the live cheat obj via GetLocal, then fire CheatChangeHero)
```
[CS] calling GetLocalLokiPlayerCheatsBP...
[CS] GetLocal -> cheatObj=0x0 cls=-
[CS] no cheat object -> abort
[CS] done cheatObj=0x0 (called=1 hitsGT=1)   [game alive, NO crash]
```
★ **`GetLocalLokiPlayerCheatsBP` returns NULL in the DS session too — identical to force-open.** The
local player has no `LokiPlayerCheats` object. It's a server-spawned, replicated sub-object (the 1 rep
prop on `LokiPlayerController`); the stub declares that prop for net-cache alignment (S73) but never
spawns/assigns a real `LokiPlayerCheats` to replicate → the client's replica is null → GetLocal null.
WCO was a valid Loki PC (0x…1470), so this is not a bad-context artifact. **No crash** — clean determination.

## Result — the cheat lever is EXHAUSTED in BOTH routes, converging on the same content/deploy wall
| Blocker | Force-open (S74) | DS session (S76) |
|---|---|---|
| `GetLocalLokiPlayerCheatsBP` | null (no cheat obj) | **null (stub never replicates one)** |
| Drop-in state fns (SwitchToPlaying/FinishDropPhaseHiding) | present on BP_Dev PC, but no-op on round gate | **absent — DS PC is native base, fns are on BP_Dev subclass** |
| Hero class (BP_HERO_*) | loadable (force-open loads content) | **not loaded (spectator)** |
| Deploy state (PS+0x4F8) | null → every spawn null-derefs | server-owned, stub never builds it |

Both bottom out at the SAME thing established since S72/S73/S74: the real deploy/hero machinery is
**BP + Angelscript content** (`BP_LokiPlayerController_Dev_C`, `BP_HERO_*_C`, the server-spawned
`LokiPlayerCheats`, the round drop-in) that the stub can't instantiate, plus server-authoritative
deploy state the stub can't build. A Loki-**typed** PC (S73) is not the same as the Loki **BP_Dev** PC
that carries the drop-in code.

## Conclusion
The last untested lever — the game's own cheat hero machinery, run in the strongest-ever position
(valid DS session + real Loki PC + live GameState + fixed marshalling) — is **exhausted, cleanly, with
the game surviving.** The DS route's honest reasonable-effort ceiling stands at the **S70/S73
spectator-in-the-live-tutorial-world** milestone. A controllable hero requires SUPERVIVE's
Server-target binary / the BP+Angelscript content, which are not in our possession (S73/S74).

## Reusable (this session)
- The `tutorial_launch.cpp` RM_CHEATSPAWN cheat modes work as a **DS-client probe** (self-contained,
  no force-open) — built `tutorial_launch_cheat_switch.dll` (CT_SWITCHPLAYING) +
  `tutorial_launch_cheat_name.dll` (CT_CHANGEHERONAME).
- Full autonomous DS-session reproduction from logs: ags DS-address edit → stub-first → launch-redirect
  -NoHook → poll Loki.log for the S70/S73 milestones → inject. Left running at handoff: stub(55812) +
  ags + client(73512) (client dead-spectator on the loading screen, LVL_Tutorial, Loki PC).
