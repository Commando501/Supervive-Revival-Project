# S74 Route B — Angelscript inventory: the AS layer is THIN; deploy/round is NATIVE

Goal: decompile the Angelscript (PrecompiledScript.Cache) to understand the SpawnSelect→deploy
sequence and what sets PlayerState+0x4F8 (the Step-0 null), and to gauge Route D feasibility.

## PrecompiledScript.Cache format
UnrealEngine-Angelscript precompiled module: 16-byte content hash header, then length-prefixed
records (module name, class name, `<Class>_AS`, function tables, bytecode). Files:
`PrecompiledScript.Cache` (1.18MB, the compiled AS), `Binds.Cache`(+`.Headers`) (7.8MB, C++↔AS bind sigs).

## ★ THE KEY FINDING — only 18 classes are Angelscript, and they are the HIGH-LEVEL layer
Distinct `*_AS` classes in the cache (18 total):
  ALokiHeroCharacter_AS, ALokiPlayerController_AS, ALokiPlayerCheats_AS, ALokiGameState_AS,
  ULokiMajorStatusEffectComponent_AS, ALokiDayNightController_AS, ALokiAirship_AS,
  ULokiOffscreenTeamIndicatorWidget_AS, ULokiWidgetHighlighterHitTestBlocker_AS (+ __StaticType_ dups).

**There is NO `LokiRoundGameMode_AS` / `LokiGameMode_AS` / `LokiDropInGameMode_AS` / deploy AS class.**
The gamemode / round / spawn-select / drop-in machinery is NATIVE C++ (confirmed: the Step-0 SpawnSelect
crash was native x64 in LokiRoundGameMode; GoToPhase is a native thunk). Deploy actors are native/BP too:
`ALokiDropInGameMode`, `ALokiDropPlane`, `ALokiDropPod*`, `Comp_PC_LokiRespawnComponent`,
`AuthRequestRespawn`, `CheckSetInitialRespawn`, `GetPlayerRespawnComponent` — none carry the `_AS` suffix.

So the architecture is: a THIN Angelscript layer (hero, PC, GameState, day/night, airship, a status-effect
component, 2 widgets, cheats) sitting on a NATIVE C++ core (gamemode, round, deploy, drop-pod, respawn,
most components).

## What this means (honest)
1. **AS decompilation does NOT answer the PS+0x4F8 question.** That null is set (or not) by the NATIVE
   deploy/respawn system (LokiRoundGameMode / DropInGameMode / RespawnComponent), which is not in the AS
   cache. Decompiling the AS would reveal hero/PC/GameState behavior, not the native deploy that crashed.
2. **Route D (AS-fork stub) does NOT escape the wall.** Even with the AS layer decompiled + recompiled and
   the BP content mounted, the stub would still lack the NATIVE C++ core (gamemode/round/deploy/drop-pod) —
   which exists only inside the packed shipping exe, with no source. The AS classes themselves derive from
   native parents (ALokiHeroCharacter_AS : native LokiHeroCharacter, etc.) that are also native-only.
3. **The native C++ deploy/round core is the irreducible blocker** — now confirmed from the AS-structure
   angle, converging with every prior route (DS stub, force-open Step-0, real-exe-as-server, content overlay).

## Options from here (the deploy is native, no source)
- **A′. Native disasm of the deploy** — read the native LokiRoundGameMode/DropInGameMode/RespawnComponent
  code (committed at runtime) to find what SETS PlayerState+0x4F8 + reconstruct the deploy sequence. This is
  "reconstruct the server from disassembly": possible in principle, but each null is a native reconstruction
  and the surface is large + packer-protected. Highest-effort, uncertain.
- **B′. Decompile the AS anyway (for Route D content)** — real work, but Route D is blocked on the native
  core regardless, so this is low marginal value now.
- **C. Accept the ceiling** — a playable tutorial needs SUPERVIVE's native server code, which is not in the
  AS layer, not in the paks, and not in a shipped server binary. The reasonable-effort AND current-artifacts
  ceiling is the S70/S73 spectator milestone; force-open reaches the real gamemode + advances the round via
  GoToPhase but the native deploy is unreconstructable without source.

## Bottom line
Route B's inventory is the decisive result: the game's deploy/round logic is native C++, not Angelscript.
So neither AS decompilation nor an AS-fork stub (Route D) can supply it. The only technical path left is
native-disassembly reconstruction of the deploy (A′) — the largest, least-certain option — or sourcing
SUPERVIVE's server binary.
