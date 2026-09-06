# Next session (S74) — SUPERVIVE playable tutorial: the DS route reached its ceiling. Decide bank vs. content-overlay.

Paste this whole file as the first message of a fresh Claude session.

---

## READ FIRST (honest framing — do NOT re-grind closed routes)
S73 was a breakthrough session on the **dedicated-server (DS) route**, but it ended by confirming the reasonable-effort
**ceiling**. Your first job is to internalize that and either (a) help the user **bank the milestone**, or (b) commit —
eyes open — to the ONE remaining path (the **content overlay**, large + previously found non-trivial). Do NOT re-open the
closed hypotheses below; the value is the trial-and-error history.

Read in order before touching anything:
1. `memory/supervive-dedicated-server-status.md` — the full DS history; the S73 entries at the END are the current truth.
2. `docs/session-73-lokipc-mirror.txt` + `docs/session-73-lokipc-netcache-capture.txt` — the PC mirror + net-cache RE.
3. `docs/session-73-hero-reconstruction-scope.md` — the hero/round scope + why Phase 1 was a NO-GO.

## WHAT S73 ACHIEVED (the milestone — real, demonstrable)
The DS route now delivers the client into a **stable, sustained LIVE tutorial match** with the full Loki networking stack
mirrored into the stub (`unreal-stub/`, branch `dedicated-server-stub`), all built this session with the NetGUID-by-path
schema-injection technique + a runtime ClassReps rebuild:
- **ALokiPlayerController** mirror (`LokiPlayerControllerStub.{h,cpp}`) — net-cache aligned (1 rep `LokiPlayerCheats` + 60
  RPC stubs; `ServerFillTeam(int32)` + 3 team/spawn RPC sigs RE'd live). `TryGetLocalLokiController` now SUCCEEDS — the
  S41/S71/S72 "client needs a Loki PC" wall is DOWN.
- **ALokiPlayerState** mirror (`LokiPlayerStateStub.{h,cpp}`) — 1 rep `HeroClass` + 7 RPCs; `GetLocalLokiPlayerState`
  SUCCEEDS. (S70 pattern: APlayerState is push-based → register base props by name non-push.)
- **World-Partition level-visibility** bypassed (`LokiGameEngine.{h,cpp}` — a `UGameEngine` subclass overriding
  `NetworkRemapPath` to redirect `…/_Generated_/<cell>` → `/Engine/Maps/Entry` so `DoesPackageExist` passes; wired via
  `DefaultEngine.ini [/Script/Engine.Engine] GameEngine=/Script/Loki.LokiGameEngine`). The `MissingLevelPackage` close is gone.
- Plus the S70 **ALokiGameState** (43 props) — client enters its real LokiGameState, processes phase changes.
The client is STABLE in-match: 0 desync, 0 close, connection healthy. It sits as a **dead spectator on the "DROP IN…"
loading screen** because it never drops in.

## THE CEILING (confirmed from every angle — this is the wall)
A controllable hero needs SUPERVIVE's **server-authoritative round machinery** (round-start → deploy → drop-in →
LokiCharacter spawn+possess), driven by the real `BP_LokiGameMode_Tutorial` + `Comp_GameMode_DropPlane_Tutorial`. S73
proved the client faithfully processes EVERY replicated state we send, but **dropping in is an ACTION the real server
performs, not a STATE we can seed.** Levers tested + FAILED (do NOT retry):
- **Feature toggles via config** (`/configuration` FeatureToggles is `TMap<FString,FFeatureToggle{Config:TMap<FString,FString>}>`;
  served it, hot-swapped ags): config parsed clean but readiness did NOT flip → readiness is **round-gated**, not config-gated.
- **GameState phase seeding** (EGP_SpawnSelect→EGP_Combat): the client RECEIVED it ("Entering combat phase on client") but
  the loading screen/drop-in did NOT change → **not phase-gated**.
- **Possession of a stub pawn**: DefaultPawn replicated but was never possessed (drop-in/hero-gated).
- **★ Hero mirror (Phase 1 go/no-go) — HARD WALL.** Built `ALokiCharacter : ACharacter` (`LokiCharacterStub.{h,cpp}`),
  net-cache ALIGNED (0 desync — incl. stripping SUPERVIVE's modified `ACharacter`: it has 10 reps/7 net funcs vs stock
  11/17, dropped RepRootMotion + 10 legacy movement RPCs; `StripNetFunction` added to `Loki.cpp`; GetLifetimeReplicatedProps
  calls `APawn::Super` + registers ACharacter's 8 conditional reps by name). BUT the client logged **"SpawnActor failed
  because class LokiCharacter is abstract"**. `LokiCharacter` AND `LokiHeroCharacter` are **CLASS_Abstract** (flag @
  UClass+0xDC, calibrated on the engine's own error); the only concrete character classes are the **`BP_HERO_*_C`
  Blueprints** (+ `LokiMinionCharacter`, a minion). The stub (a `/Script` module) can only mirror NATIVE `/Script`
  classes by-path — and the native hero bases are abstract; the concrete heroes are `/Game` **Blueprint content the stub
  lacks**. => the by-path mirror CANNOT deliver a hero. Same wall as the gamemode (both are BP content).

## THE ONLY REMAINING ROUTE = the CONTENT OVERLAY (large, previously non-trivial)
A controllable hero (like the real gamemode) needs the game's **Blueprint content** (`BP_HERO_*_C`,
`BP_LokiGameMode_Tutorial`, `Comp_GameMode_DropPlane_Tutorial`) loaded into the DS stub, so the real classes spawn +
the real round runs. Prereqs already established (don't rediscover):
- `docs/trackb-assetregistry-route.md`: loose-file AR.bin is INERT in this IoStore build; deployment needs an **IoStore
  mod-pak overlay** — non-trivial.
- `docs/findings.md`/`r2-findings.md`: paks are **UNENCRYPTED but SIGNED** (`.sig` per chunk); the shipping install has
  ONLY the CLIENT exe (no dedicated-server binary). Non-standard UObjectBase layout (nameOff=0x20, classOff=0x18).
- The stub is a SEPARATE minimal UE5.4 project WITHOUT the game's cooked content or its native `/Script/Loki` C++.
- **Honest gate:** even if the stub mounts the shipping paks, the cooked BP heroes/gamemode need their NATIVE parent
  classes (`ALokiHeroCharacter`, `ALokiGameMode`, etc.) which live in the shipping exe's packed `/Script/Loki` module —
  not in the paks, and the stub doesn't have them. This is why the content overlay was assessed as likely-blocked (S72–73).
  A cheap first spike (if pursuing): can the stub `UnrealEditor-Cmd` MOUNT the shipping `.utoc/.pak` + `StaticLoadObject`
  a `BP_HERO` class, and does its native parent resolve? If the native `/Script/Loki` parents don't resolve, the overlay
  is blocked and a playable tutorial is likely NOT reachable with the current toolchain — report that plainly.

## RECOMMENDED FIRST ACTION
Present the bank-vs-overlay decision honestly. The networking foundation (all the mirrors + level-visibility + net-cache
RE) is DONE and reusable, so if the overlay is ever pursued the hard netcode is already solved. Recommendation: **bank
the S73 milestone** (client in the live tutorial match with a real Loki PC + PlayerState + GameState) unless the user
wants to commit to the IoStore overlay as a distinct large effort.

## STATE / RECIPE (as left after S73)
- Nothing may still be running (or the stub/ags/client from S73 may be up — check `tasklist`). ags serves featureToggles
  + stub seeds EGP_Combat + PlayerControllerClass=ALokiPlayerController + spawns ALokiCharacter in PostLogin (all harmless
  baselines, kept). Uncommitted git changes exist (many `unreal-stub/Source/Loki/*` + `server/` + docs) — the user may
  want to COMMIT first (branch `dedicated-server-stub`).
- Engine: `H:\Unreal Engine\UE_5.4`. Client base (ASLR, stable): `0x7FF6B54F0000`. NAMEPOOL rva `+0x9D81450`, OBJOBJECTS
  `+0x9E38930`. UFunction.FunctionFlags @ `+0xB8`, UClass.ClassFlags @ `+0xDC`, UStruct.SuperStruct @ `+0x48`.
- Bring the stack up (elevated PS; Steam running FIRST or login dies Auth Failure 14005):
  1. Build stub (~kill UnrealEditor-Cmd first): `Build.bat LokiEditor Win64 Development -Project=<abs>\unreal-stub\Loki.uproject -WaitMutex`.
  2. Run stub FIRST: `UnrealEditor-Cmd.exe <abs>\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi -NoSplash -Unattended -abslog=<repo>\docs\ds-server.log` (poll "listening on port 7777").
  3. Client: `.\configs\launch-redirect.ps1 -NoHook` (self-elevates → UAC; auto-arms the match ~1 min).
  4. Verify: client `Loki.log` (`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`) → "Entering game state
     LokiGameState" = client in the live match. ags rebuild: `go build -C server -o ags.exe ./cmd/ags` (NOT `-o server\ags.exe`).

## REUSABLE ASSETS (S73)
- Mirrors: `LokiPlayerControllerStub`, `LokiPlayerStateStub`, `LokiCharacterStub`, `LokiGameStateStub` (`.{h,cpp}`),
  `LokiGameEngine` (level-visibility). The char net-cache IS aligned (usable under a content overlay).
- Loki.cpp machinery: `DumpClassNetCacheLayout`, `ForceSetUpReplicationData`, `StripReplicatedFlag`, `StripNetFunction`,
  `AddGSBaseLifetimeProp`/`AddPSBaseLifetimeProp`/`AddCharRep` (register push-based engine bases by name non-push).
- RE tools (`tools/re/`, RPM, take PID + base `0x7FF6B54F0000`): `find_uclass.py`, `rep_expand_class.py` (CPF_Net props),
  `netfields_dump.py` (own FUNC_Net funcs), `funcparam_dump.py` (a UFunction's param sig), `gen_lokipc_rpcs.py` (emit
  UFUNCTION stubs from a live class), `obj_by_class.py` (live instances by class substring).
- The by-path mirror PATTERN: name a native class `/Script/Loki.<Name>`; the client resolves it to its own — works for
  CONCRETE native classes only (GameState/PC/PlayerState). Does NOT work for abstract (LokiCharacter) or BP content.

## HONEST FRAMING FOR THE USER
S73 delivered a genuine milestone (client stable in the LIVE tutorial match with a full mirrored Loki networking stack,
past login/PC/PlayerState/GameState/level-visibility). A controllable hero is ONE step further, but that step is BP
content (hero + gamemode) — the content-overlay route, a fundamentally different large effort, likely blocked by the
native `/Script/Loki` parent classes not existing outside the packed shipping exe. Recommend banking S73 as the
reasonable-effort ceiling unless the user commits to the overlay with eyes open.
