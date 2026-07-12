# Next session — DS route: spawn + possess a HERO PAWN so the tutorial is controllable (drop-in)

Paste this whole file as the first message of a fresh Claude session.

---

## THE MISSION (unchanged)
Keep working, session after session, until the SUPERVIVE tutorial is FULLY PLAYABLE: the map loads, a controllable
hero drops in, you can move/play it. "Done" = a hero you can control.

## WHERE WE ARE — the loading-screen wall is DOWN (S70)
Read `docs/session-70-gamestate-loadingscreen-cleared.txt` FIRST, then memory `supervive-dedicated-server-status`.

The DS route now gets the client **into the live tutorial world**: menu route → connects to the stub (127.0.0.1:7777)
→ travels to LVL_Tutorial → Join → the stub replicates a native **ALokiGameState** mirror
(`unreal-stub/Source/Loki/LokiGameStateStub.{h,cpp}`, 43 replicated props, seeded `CurrentPhase=EGP_SpawnSelect`) →
the client accepts it (no desync), enters its real `LokiGameState`, runs `BeginPlay`, **primes gameplay actor pools,
and sits stable in LVL_Tutorial** (performance snapshots, `[UIREADY] TryUIReady SUCCESS`, 2+ min, no timeout).

**But the local player is a SPECTATOR — no hero pawn** (`LogLokiBlueprint: GetLocalLokiPlayerState failed to get a
player state`). That's the next and likely final gate to "controllable."

## THE TASK — a possessed, controllable hero pawn (server-side)
This is where the DS route pays off: the SERVER runs the spawn/possess/round logic the force-open route couldn't.
1. **Diagnose what the client waits for to get a pawn.** With the game live in LVL_Tutorial, read the client `Loki.log`
   and stub `docs/ds-server.log`: is the server sending a Pawn/possession? Currently `DefaultPawn` is SUPPRESSED in
   `LokiNetDriver::IsClassNetCacheDivergent`, and `LokiStubGameMode` is a stock `AGameModeBase` that spawns no hero.
2. **Server spawns + possesses a hero for the connecting PC.** In `LokiStubGameMode::PostLogin`/`RestartPlayer`, spawn
   a hero pawn and `Controller::Possess` it. The hero pawn class is a Blueprint (`BP_HERO_*_C`) — the stub can't load
   BP content, so this needs the **schema-injection mirror pattern** again (S70 proved it end-to-end): a native pawn
   class mirrored by path, un-suppressed in `IsClassNetCacheDivergent`, with its replicated schema captured live
   (`tools/re/find_uclass.py` → `rep_expand_class.py`) and mirrored cmd-for-cmd. OR: drive the round gamemode so the
   real spawn path runs. Start by RE-ing the client's expected pawn/possession flow in the tutorial.
3. **Trigger the tutorial drop-in.** SUPERVIVE drops in via `Comp_GameMode_DropPlane_Tutorial` (S61) — once a pawn is
   possessed, wire/trigger the drop so the hero is controllable on the ground.

## THE REUSABLE MIRROR PATTERN (proven S41/S54/S70 — follow it, don't reinvent)
Name a native UCLASS to match the client's `/Script/Loki.<Name>` (both modules "Loki" → client binds by path, no
IoStore). Capture its replicated schema LIVE (the usmap lies): `tools/re/find_uclass.py <PID> <BASE> <Name> Class` →
`rep_expand_class.py` (raise its `i<40` cap). Mirror the props in exact field order. **S70 GOTCHAS (critical for the
next mirror):**
- Do NOT call an engine base's `GetLifetimeReplicatedProps` (its push-based FAST macros clash with the stub's runtime
  ClassReps rebuild → `Assertion failed: bIsPushBased == Other.bIsPushBased [CoreNet.h:331]`). Register base props BY
  NAME, non-push: `FindFProperty` → `OutLifetimeProps.Add(FLifetimeProperty(RepIndex))`. Call `AActor::Get...` for the
  AActor tier, then your own props via plain `DOREPLIFETIME`.
- Strip (clear CPF_Net via `StripReplicatedFlag` in Loki.cpp, before the rep-data rebuild) any stock engine replicated
  prop the SUPERVIVE client DOESN'T replicate — verify counts with the boot `DumpClassNetCacheLayout` BEFORE launching
  a client (it caught the GameStateBase 5-vs-4 shift with zero wasted launches).
- `net.IsPushModelEnabled=0` in ini `[ConsoleVariables]` did NOT disable push model here — control the lifetime list
  directly instead.

## RECIPE (elevated PS; Steam running; stub FIRST)
1. Rebuild stub (KILL `UnrealEditor-Cmd` + `SUPERVIVE-Win64-Shipping` first): `Build.bat LokiEditor Win64 Development
   -Project=...\unreal-stub\Loki.uproject -WaitMutex` (incremental ~5s after the S70 full build).
2. Run stub: `UnrealEditor-Cmd.exe ...\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi
   -NoSplash -Unattended -abslog=<repo>\docs\ds-server.log`; poll for "IpNetDriver listening on port 7777".
   (Do NOT `Remove-Item` the abslog path — a sandbox guard blocks it; UE truncates on open anyway.)
3. Client: `.\configs\launch-redirect.ps1 -NoHook` (background; the shipping exe's `& $exe` returns early via Steam
   relaunch, so the launcher "task" completes while the game runs on). Auto-arms the match in ~1 min.
4. Watch client `Loki.log` (`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`) + stub log. SUCCESS =
   the local player possesses a hero pawn and can move (a screenshot — user-gated — confirms; logs show possession).

## STATE AT HANDOFF
Stub built with the S70 ALokiGameState mirror. `ags` address = 127.0.0.1:7777. Game + stub were LEFT RUNNING (client
spectating LVL_Tutorial) so the S70 result can be viewed — kill both before the next rebuild/test. Manual ags rebuild
(if needed): `go build -C server -o ags.exe ./cmd/ags` (NOT `-o server\ags.exe`).
