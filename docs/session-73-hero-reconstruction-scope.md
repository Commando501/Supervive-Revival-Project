# Hero / round reconstruction — scope (S73)

Goal: over the DS route, get the tutorial client to **drop in and control a hero (LokiCharacter)** — the
final step past the converged S65/S66/S73 ceiling (the client is stable in the live tutorial match with a
Loki PC + Loki PlayerState + replicated GameState, but sits as a dead spectator; the loading screen never
dismisses because the player never drops in).

"Done" = the client possesses a LokiCharacter, leaves the loading screen, and can move/aim it.

## What we already have (proven this session, all reusable)
- Client → stub networked session into LVL_Tutorial, stable (handshake/login/join/class-net-cache).
- **The replication path is 100% proven**: the client faithfully processes everything the stub replicates.
  Demonstrated with the ALokiGameState (43 props, phases — client logs "Entering combat phase"), the
  ALokiPlayerController (Loki PC, net-cache aligned, TryGetLocalLokiController works), and the ALokiPlayerState
  (GetLocalLokiPlayerState works). World-Partition level-visibility bypassed (LokiGameEngine NetworkRemapPath).
- The stub can spawn + possess actors server-side (DefaultPawn today).
- Tooling: find_uclass / rep_expand_class / netfields_dump / funcparam_dump / gen_lokipc_rpcs (emit UFUNCTION
  stubs) / obj_by_class, the by-path mirror pattern, the runtime ClassReps-rebuild + DumpClassNetCacheLayout.

## The gap = the server-authoritative round machinery (what the real BP_LokiGameMode_Tutorial does)
The client won't drop in / possess because dropping in is an **action** the real server performs, not a
**state** we can seed (confirmed S73: seeding EGP_Combat and serving feature toggles did nothing). The missing
actions: assign the player a hero, spawn a LokiCharacter, run the DropPlane/DropPod drop-in, possess it,
mark the feature toggles ready. The stub runs LokiStubGameMode, not the real gamemode.

## GROUNDED SIZING (live capture, S73 — the key finding: the schema is SMALL)
- **LokiCharacter: 3 own CPF_Net props + 14 own net functions.** The 182 total props are mostly
  non-replicated. All 14 net funcs are DEBUG/CHEAT/COSMETIC (ServerCheat*/ServerSuicide/ServerGetDebugStat/
  ClientPlayHitReact/ClientPlayJumpCue/ClientEngage-DisengageYawLock/ClientDebugMessage) — NONE gameplay-critical,
  so empty UFUNCTION stubs suffice for index alignment (like the PC's 60).
- Hierarchy: LokiCharacter : Character : Pawn : LokiActor : Actor. So the mirror is `ALokiCharacter : ACharacter`
  — the base tiers are STOCK ACharacter/APawn (+ LokiActor = 0 net props, already handled).
- **Movement RPCs are STOCK ACharacter (inherited):** ServerMovePacked / ClientMoveResponsePacked /
  ClientAdjustPosition live on ACharacter, not LokiCharacter. So the movement RPC SURFACE is stock UE — the
  mirror inherits it. The only open movement question is whether SUPERVIVE customized the move-DATA packing
  (FCharacterNetworkMoveDataContainer on the 218-prop LokiCharacterMovementComponent); if it's stock, movement
  works out of the box; if customized, the ServerMove payload needs RE (testable once possessing).
=> The hero-pawn SCHEMA is ~1 session of work (comparable to the PlayerState mirror), NOT the "182+218-prop
moonshot" earlier feared. The effort + risk concentrate on BEHAVIORAL questions (possession-accept, drop-in,
toggle-readiness), which are cheaply front-loadable.

## Plan — de-risk the make-or-break question FIRST
### Phase 1 — LokiCharacter mirror + spawn/possess (~1–2 sessions) — THE GO/NO-GO
- Build `ALokiCharacter : ACharacter` (by-path /Script/Loki.LokiCharacter): 3 CPF_Net props + 14 net-func stubs
  (gen a la gen_lokipc_rpcs), boot-verify the net-cache aligns, bAlwaysRelevant.
- LokiStubGameMode PostLogin: spawn it (instead of/alongside the DefaultPawn), possess it, ClientRestart.
- **TEST the make-or-break wall:** does the client possess it and engage HERO CONTROL (TryGetLocalLokiController
  hero path, stops being a DeadSpectator, view attaches to the hero)? 
- ★ KILL-CRITERION: if the client refuses to possess/control a Loki-typed character despite a correct bunch +
  correct round state, the reconstruction is likely a HARD WALL (the client requires server-authoritative
  round/assignment state only the real gamemode produces) → stop before the bigger investment. This is the
  single most important uncertainty and it is now cheap to test (was previously buried behind a huge mirror).

### Phase 2 — feature-toggle readiness + "player alive" round state (~1–2 sessions)
- RE how the server marks ULokiGameFeatureToggles ready (round-gated per S73 — find the replicated value / RPC /
  round event that flips it; it's static-store so needs the trigger, not the store). Replicate/trigger it.
- Seed the round/PlayerState so the client considers the player ALIVE + assigned a hero (not a dead spectator).

### Phase 3 — drop-in (or bypass) (~1–3 sessions)
- Either reconstruct the DropPlane/DropPod drop sequence (replicate the drop actor + attach + drop), OR bypass:
  spawn the hero on the ground already "dropped/alive" and convince the client to dismiss the loading screen +
  reveal the world. Which is needed depends on Phase-1/2 findings.

### Phase 4 — movement + control round-trip (~1–3 sessions)
- With the hero possessed, the client sends ServerMovePacked to the stub. Test whether the stock ACharacter
  base parses it. If the LokiCharacterMovementComponent customized the move-data container → RE + mirror the
  packed-move format (the one genuinely hard RE left, but bounded, and only reached if Phase 1 passes).
- Camera / input / aim (CursorCharacterAim) working — depends on the Phase-2 toggle fix.

## Effort + risk
- Total (if no hard wall): ~4–10 focused sessions. The schema work is small; the sessions are behavioral
  iteration (spawn→possess→observe→adjust), the same loop that cleared the PC/PlayerState this session.
- THREE hard-wall risks, in priority order:
  1. **Possession-accept (highest, tested in Phase 1):** the client may refuse to control a stub-spawned hero
     unless the real gamemode produced it. If so → hard wall, no amount of replication fakes it. Front-loaded.
  2. **Move-data format (Phase 4):** custom packed-move on the 218-prop CMC → movement RE. Moderate, bounded.
  3. **Toggle-readiness trigger (Phase 2):** if tied to native round logic with no replicable trigger → wall.
- Any single one can end the effort; but unlike the earlier estimate, the biggest one (possession) is now a
  cheap early test, so the initial commitment to LEARN whether it's possible is only ~1–2 sessions.

## Bottom line + recommendation
The reconstruction is meaningfully smaller than the "182+218-prop moonshot" framing — the hero SCHEMA is a
~1-session mirror and movement is stock-inherited. The real question is a single behavioral one — **will the
client control a hero the stub (not the real gamemode) produced?** — and it is now cheaply testable in Phase 1.
RECOMMENDED: run Phase 1 as a bounded 1–2 session go/no-go spike. If the client takes hero control → the rest
is incremental behavioral iteration (~4–10 sessions total) with two bounded RE risks. If it refuses → that is
the honest, final wall (the client needs the real server), and S73's stable-in-the-live-match milestone is the
ceiling. Either way, ~1–2 sessions buys the decisive answer instead of committing to the whole build blind.
