# CO-OP VS. AI — research + implementation plan (S134/S135, 2026-08-20)

**Produced by:** 5 offline recon lanes (bot system · gamemode+map · backend path · tile accessibility ·
prior art) each adversarially verified, then a planning pass. 11 agents, 649 tool calls.
**Zero launches, zero injections, zero `.text` writes.**

## Session-lead verification (re-measured from the artifacts, not inherited)

| claim | verified how | result |
|---|---|---|
| `SpawnClassBotAtLoc` exists, is `BlueprintCallable`, and is NOT authority-gated | `tools/extractor/out/bpdump_Comp_BP_BotSpawner_ALL.txt:101-102` | `FUNC_Public, FUNC_HasOutParms, FUNC_HasDefaults, FUNC_BlueprintCallable, FUNC_BlueprintEvent` — **no `FUNC_Net`, no `FUNC_BlueprintAuthorityOnly`**. Param chain int/struct/int/class/int/object matches the stated signature. |
| the bot spawner is free of the FK-42 exec-pin gates and of FK-1's stripped `SpawnPlayer` | `grep -c "ServerOnly\|ClientServerSplit\|HasAuthority\|SpawnPlayer"` on the component's full dump AND its ubergraph, **with a positive control** | **0 and 0**, control `bpdump_ExecuteUbergraph_BP_LokiGameMode_Tutorial.txt` = **8**. The grep works; the zero is real. |
| the component is on the TUTORIAL gamemode | `BP_LokiGameMode_Tutorial.json` | `Comp_BP_BotSpawner_C'BP_LokiGameMode_Tutorial_C:Comp_BP_BotSpawner_GEN_VARIABLE'` — 15 occurrences. ⚠ note `_GEN_VARIABLE`: the archetype coexists with the live instance, which is exactly the class-lookup trap §5.3 guard 2 warns about. |
| roster offset `+0xD8` | raw bytes, `dumps/merged10.dump.exe` | `GetSpawnableBots 0xFCCE40` = `48 8d 81 d8 00 00 00 c3` (`lea rax,[rcx+0xd8]; ret`) and `SetSpawnableBots 0x52EC260` = `48 81 c1 d8 00 00 00 e9` (`add rcx,0xd8; jmp`). **Two disjoint functions, same offset.** |
| `SpawnBot 0x556D910` is DARK, not stripped | raw bytes | **all zero** — a stripped impl would read as a known fold (`c2 00 00` / `33 c0 c3`), so "dark" is the right grade. `TrySpawnTeam 0x5570390` reads `41 55 41 56 48 81 ec …` = real prologue. |

⚠ **Grade discipline:** everything else below is the planning agent's, at the grade it states. The
lanes disagreed in places and those adjudications are in the plan body — read them, they are
load-bearing (notably: `bots` IS Breach, and `GameConfig.MapName` cannot select the client's map).

---

# CO-OP VS. AI — IMPLEMENTATION PLAN (S135)

*Planning output. Every lane verdict below has been re-checked against the repo; where I disagree with a lane I say so and show the bytes. Two new measurements were made during planning and are marked ★NEW.*

---

## 1. THE VERDICT IN ONE PARAGRAPH

**CO-OP VS. AI is already accessible and it is reachable as a *playable world*, but not by shipping the `bots` queue's own gamemode.** The tile is selectable today and FIND MATCH already works [M — `server/internal/interactive/joinqueue.go:19-24` is a live wire capture of the click; `server/state/interactive.json` still holds `selectedQueueId:"bots"`]. What is missing is that **nothing in our own server ever arms a match for a queued player**: `interactive.go:938` gates on `forceTutorialMatch || st.SoloMode != ""`, and `SoloMode` is written only by `POST /startSoloMode`, which `bots` structurally never sends. The decisive framing correction is Lane C's C8, which I re-verified: **`GameConfig.MapName` / `GameConfig.GameMode` cannot select the client's map** — the travel URL is built from `ConnectionDetails.Address` alone and the only `?game=` literal in the image belongs to MovieRenderPipeline — so on the empty-address (locally-parked) route **the world is chosen by `docs/tutorial-launch-cmd.txt`, not by the match document**. That decouples the queue id from the gamemode completely, which is what makes this session cheap. **CHOSEN PAIR: `BP_PracticeGameMode_C` on `LVL_Training`** (`open LVL_Training?game=/Game/Loki/Core/GameModes/BP_PracticeGameMode.BP_PracticeGameMode_C`). Defence: its native ancestor is `ALokiDropInGameMode`, which is one of the five CDO vtables `fo` de-overrides at slot 285 [M — `tools/sigbypass-mod/tutorial_launch.cpp:138-145`]; it is `LVL_Training`'s **own** `DefaultGameMode`, so the `?game=` is belt-and-braces rather than a coercion; it starts players as **pawns, not spectators**, and ships **no `DeathCircleClass` and no phase durations**, so it sidesteps FK-22's drop/phase ladder and the S131/S132 rideable wall entirely; it carries `RespawnTag "PlayerDefaultStart"` which `LVL_Training`'s persistent level satisfies; the map holds **19 `BP_LokiPlayerStart_C` and 10 `SafeTeamSpawnPathfindingAnchor` actors in the PERSISTENT package** (no cell-streaming race, unlike `LVL_Tutorial`'s `TrainingStart`); and — the fact that collapses the plan from two flights to one — **it carries `Comp_BP_BotSpawner_C`** [M, re-verified: 14 gamemode assets contain it, `BP_PracticeGameMode.json` and `BP_LokiGameMode_Tutorial.json` among them]. **Runners-up rejected:** `SkylandsBRBotsGameMode` on `LVL_Skylands_WP` is the "correct" answer and the wrong first move — it is a 2,215-cell Breach map never once loaded by this project, with 21 gameplay components, the full drop chain, and a bot roster gated behind `AuthGetMatchStartDetails` whose backing field (`GameState+0x5A0`) has **no identified writer** on this client; `FreeForAll` on `LVL_Training` owns the anchors but starts spectators, sets `MaxPlayersPerTeam=1`, and routes respawn through the empty `ALokiGameMode::SpawnPlayer` stub (`0x0F7EB50`); `Holdout` has 0 persistent PlayerStarts and needs a death circle; `BRQuickGameMode` **is not shipped** (0 of 107,123 packaged files are Skunkworks). ⚠ And one route beats all of them for *sequencing*: **the bot spawn itself should be proven on `LVL_Tutorial` first**, because the identical `Comp_BP_BotSpawner_C` is already resident on the world we stage every session — zero new map, zero new Login question.

---

## 2. THE DEPENDENCY CHAIN

| # | Step | Status | Evidence |
|---|---|---|---|
| 1 | Tile **CO-OP VS. AI** renders with name/description/icon | **WORKS** | [M] `ST_Parties.json` `queue.bots.name = "Co-op vs. AI"`; `DT_QueueDisplayDataTable.json` row `bots` → `TX_UI_TutorialGraphic_BotGame`. Client-local assets; nothing to serve. |
| 2 | Tile is unlocked (no level gate) | **WORKS** | [M] `bots` is in neither the `queue.restrictions.*` toggle set (`AGS_QUEUE_UNLOCK` defaults empty, `loki.go:357`) nor the 3-row `QueueToGameFeature` CDO map → it falls to `IsQueueIDPremadeOrOverQueueLevel`'s unconditional `CanQueue = EX_True` arm (stmt [61] @ offset 2433). ⚠ **Serving `queue.restrictions.bots` would be a REGRESSION** — see §6. |
| 3 | Click persists the selection | **WORKS** | [M] `POST .../setTargetQueues` served since S122 (`interactive.go:163`); live store holds `bots`. |
| 4 | **FIND MATCH** button enabled | **WORKS** | [M] `CanControlQueue` returns `EX_True` at exactly one statement ([129]) and every gate on the path passes for `bots`; corroborated end-to-end by S122's ARENA A-B-A. |
| 5 | Click → `POST .../joinQueue`, client enters a timed, cancellable queued state | **WORKS** | [M] S133, `joinqueue.go`. Response = `FParty` + `state:"Matchmaking"` under an advanced Version. Free receipt: `joinQueue` fires **once** when accepted, retries every 10–35 s when not. |
| 6 | Something answers the queue with a MatchID | **NEEDS-BACKEND** | [M] `interactive.go:938` — `InQueue` has no reader. This is the accessibility→playability boundary. |
| 7 | Client re-fetches `GET /core-game/players/{id}` and sees the MatchID | **NEEDS-BACKEND (push)** | ★NEW [M] **`POST /startSoloMode` does NOT trigger a refetch.** `scratchpad/s133/evidence/capture-phase2.log`: two solo-starts at `19:19:50.558` (`mode=dropin`) and `19:19:51.089` (`mode=practice`), and the *only* `/core-game/players` in the whole file is `#10 18:56:14.318` — **23 minutes earlier, at login**, with one messenger connection for the entire session. ⇒ `docs/endpoints.md:49`'s "active poller ~17/s" is **stale**; the write-and-wait model fails. The refetch must be pushed. |
| 8 | Client escalates to `GET /core-game/matches/{matchId}` | **WORKS (once 7 fires)** | [M] `capture-pre-queue-sweep.log`: players-fetch `14:32:38.886` → match-fetch `14:32:39.277` (**+391 ms**) → presence flips `"a":"InMatch"` at `14:32:39.696`. Handler already registered, `interactive.go:218`. |
| 9 | `UTravelManager` attempts travel | **WORKS (expected)** | [M] the game ships the mechanism in a cvar description — `CheatPreventAutoTravelToMatch`: *"Will prevent the travel manager from automatically traveling to a match when the match state changes."* Decision fn `0x58A99C3`, travel fn `0x58B9D30`, both LIT, 8 greppable literals (§4). |
| 10 | With an EMPTY `ConnectionDetails.address`, the client **parks locally** instead of opening a NetConnection | **WORKS** | [M] S62: `Attempting to travel to Match: Address:''` → parked, no map loaded, zero NetConnection attempts. This park is the precondition the force-open needs. |
| 11 | `fo` force-opens the chosen (map, gamemode) | **WORKS for the 5 covered native bases** | [M] `tutorial_launch.cpp:119` reads `docs/tutorial-launch-cmd.txt` at inject time; `:138-145` de-overrides slot 285 on `{ALokiTutorialGameMode, ALokiRoundGameMode, ALokiGameMode, ALokiBattleRoyaleGameMode, ALokiDropInGameMode}` → stock `AGameModeBase::Login`. `BP_PracticeGameMode_C → BP_PracticeGameMode_Code_C → ALokiDropInGameMode` is covered. ⚠ `LVL_Training` + PracticeMode has **never been force-opened** — this is the one genuinely unknown step. |
| 12 | Hero spawns with a body, camera and WASD | **WORKS on tutorial; UNKNOWN on Training** | [M] S107/S108b on `LVL_Tutorial` via `sp` + `play`. On PracticeMode the mode itself starts players as pawns (`bStartPlayersAsSpectators` absent from its CDO, present and `true` on FFA/Holdout), which is *more* favourable, but unmeasured. |
| 13 | Bot roster (`SpawnableBots`) is populated | **WORKS, no backend needed** | ★ [M, re-derived from bytecode] `bpdump_ExecuteUbergraph_Comp_BP_BotSpawner.txt`: `[2] IsASoft(GetOwner(), BP_LokiBattleRoyaleGameMode_C)` → `[6] EX_JumpIfNot → 430` on `ItIsNot(1)` → **`[12] "Initialize Bot Options"` UNCONDITIONALLY**. On any non-BR gamemode (Tutorial, Practice) the roster self-initialises from the 13-entry `AvailableBots` CDO array → `LoadClassAsset_Blocking` → native `SetSpawnableBots`. The `BotConfig` gate at `[9]`/`[10]` is on the **BR arm only**. |
| 14 | A bot hero is spawned | **NEEDS-SHIM** | [M] one `CallBPGuarded` on `SpawnClassBotAtLoc`. See §5. |
| 15 | The bot is fightable (has an ability system, acts) | **UNKNOWN [S]** | The bot path does not pass through the empty `ALokiGameMode::SpawnPlayer` stub, and `ALokiBotController::{GetUsableSpells, TryToDash, SetHeroBotCompInitialized}` are all REAL — but native `SpawnBot` (`0x556D910`) is **dark in 50 of 50 images on disk** and cannot be read offline. This is the single irreducible unknown and it is settled by flying, not by more RE. |
| 16 | The player can damage it | **BLOCKED-ish / out of scope** | The player hero's own ASC is the standing FK-1 problem (`AvatarActor` NULL). Do not conflate: step 15 asks whether the *bot* has abilities, which is a different and possibly easier question. |

---

## 3. PHASE 1 — BACKEND ONLY, NO LAUNCH RISK

All six changes below are **default OFF and byte-identical to today when off**. Each ships with its controlled negative in the same commit.

### 1.0 — Two prerequisite hygiene commits (separate, single-variable, do these first)

**(a) `interactive.go:1887` — `"fillTeam": false` is a bool written into an enum property.**
[M] usmap `Party[5] FillTeam : Enum<EPartyFillPreference:Byte>` (`Fill=0, PreferNoFill=1, NoFill=2`). A matched key with a wrong type is the whole-document-rejection class. It has been shipping and surviving unexplained, which makes it an unexploded charge sitting under every party experiment in this plan. **Fix: omit the key** (omission is always safe). Watch `LogJson` for one session. **Do not bundle this with queue work.**

**(b) `joinqueue.go:142` and `:170` — the two `inQueue` writes are dead keys.**
[M] `FParty` has 17 props and `FPartyMember` has 23; **neither contains `inQueue`**. Both writes are silently ignored; `state` is doing 100 % of the work. Replace the writes with a comment recording the measurement so a successor cannot re-believe them. Also correct the comment at `joinqueue.go:154-156`: **`FParty.State` is an `FString`, not an enum** — a wrong `state` value changes the state machine but *cannot* reject the document, so future `state` sweeps are cheaper than recorded and a `state` null can never mean "the doc was rejected".

### 1.1 — `server/internal/interactive/store.go`: three transient fields

```go
// ARMED MATCH (S135). Transient (json:"-") for exactly the reason SoloMode and
// InQueue are: a persisted MatchID would make a FRESH boot claim an active match
// with no matchmaker to clear it, and /core-game/players would report it forever.
// That failure mode is already on record (S107: once a MatchID is served, every
// subsequent START is a silent no-op).
MatchID      string `json:"-"`
MatchVersion int64  `json:"-"`
MatchQueue   string `json:"-"` // the queue id the match was armed FOR
```

### 1.2 — `interactive.go:938`: widen the gate; serve the armed values

```go
active := forceTutorialMatch || (st != nil && (st.SoloMode != "" || st.MatchID != ""))
...
if active {
    if st != nil && st.MatchID != "" {
        resp["MatchID"] = st.MatchID
        resp["Version"] = st.MatchVersion
    } else {
        resp["MatchID"] = tutorialMatchID(id)
        resp["Version"] = matchStateVersion   // unchanged legacy path
    }
}
```
The `SoloMode`/`forceTutorialMatch` branches stay **byte-identical**. With `AGS_ARM_QUEUE` unset, `st.MatchID` is never written, so the endpoint is unchanged.

Export the version so the push and the document cannot drift — this is the documented `push.go:431-465` footgun, and the pattern to copy is `interactive.MatchHistoryVersion` (`interactive.go:579`):

```go
// CoreGamePlayerVersion returns the exact Version /core-game/players/{id} will
// serve. lobby.NotifyResource MUST be passed this, never a clock and never +1.
func CoreGamePlayerVersion(id string) int64
```

### 1.3 — `server/internal/interactive/armqueue.go` (new file)

| knob | default | meaning |
|---|---|---|
| `AGS_ARM_QUEUE` | **`off`** | `off` \| `arm` \| **`empty`** |
| `AGS_ARM_QUEUE_DELAY` | `8s` | delay from joinQueue to arming, so the searching UI is visibly real |
| `AGS_ARM_QUEUE_QUEUES` | `bots` | comma list of queue ids that may arm |
| `AGS_ARM_QUEUE_GAMEMODE` | *(empty)* | override `GameConfig.GameMode` |
| `AGS_ARM_QUEUE_MAP` | *(empty)* | override `GameConfig.MapName` |
| `AGS_ARM_QUEUE_VERSION` | *(empty)* | pin the Version to isolate the monotonic gate |

★ **`AGS_ARM_QUEUE=empty` IS THE CONTROLLED NEGATIVE, and it is the whole point.** It serves a **valid, fully-shaped `FCoreGamePlayer` with an ADVANCING `Version` and an EMPTY `MatchID`**. Reverting to `off` changes the document *and* the version at once and is therefore uninterpretable — that is precisely the `AGS_PLAYER_RANK=0` mistake S122 recorded. `empty` moves exactly one field.

```go
func (s *Service) armQueuedMatch(id, queue string) {
    s.store.update(id, func(st *playerState) {
        st.MatchID      = tutorialMatchID(id)
        st.MatchQueue   = queue
        st.MatchVersion = nextCoreGamePlayerVersion(st)  // strictly monotonic
        st.InQueue      = false                          // the queue resolved
    })
    if s.matchArmed != nil { s.matchArmed(id) }
}
```

`nextCoreGamePlayerVersion` must be **strictly monotonic within a process and seeded above any previously served value** (`matchStateVersion` is already `time.Now().Unix()`); seed from `max(matchStateVersion, prev)+1`.

### 1.4 — `joinqueue.go`: schedule and cancel

`handleJoinQueue`: after `st.InQueue = true`, if the knob is `arm` **and** the selected queue is in `AGS_ARM_QUEUE_QUEUES`, start a `time.AfterFunc(delay, ...)` stored per player. `handleLeaveQueue` **must** stop the timer *and* clear `MatchID`, bump `MatchVersion`, and push — otherwise the S107 stickiness (`E-11`) returns permanently.

### 1.5 — `server/cmd/ags/main.go`: wire the push beside the existing notifier

```go
interSvc.SetPartyDirtyNotifier(lobbySvc.MarkDirty)                       // main.go:99, existing
interSvc.SetMatchArmedNotifier(func(id string) {
    _ = lobbySvc.NotifyResource(id, "/core-game/players/"+id,
        interactive.CoreGamePlayerVersion(id), "match-armed")
})
```

⚠⚠ **The resource string must be byte-exact.** The registered client handler is `fn 0x57C3450`: it builds `"/core-game/players/" + mgr[+0xD0]` and runs a **wide-char exact-compare loop at `0x57C34B0`** before storing `notif.Version` into `mgr[+0xC8]` and refetching when `[+0xC8] > [+0xF0]`. A near-miss string is an invisible no-op. ⚠ **FK-15's "that handler has no resource equality check" (`fk15-ws-push-audit.md:552`) describes the `/progression` handler and does NOT generalise here** — that is the first thing to check on a null, before reaching for the socket drop.
★ Good news from the same decode: the pushed value lands in `+0xC8` while the compare target is `+0xF0`, and `handleCoreGamePlayer` serves `Version: 0` while idle — so **any positive push clears the gate** and the `/party` unbounded-refetch mode does not obviously reproduce.
★ The messenger is healthy: `enableTextHeartbeatReply = true` is shipped (`lobby/lobby.go:142`) and `capture-phase2.log` shows **one** messenger connection surviving 25+ minutes. Lane C's open question 7 is closed.

### 1.6 — `buildTutorialMatchInfo` → `buildMatchInfo(..., queue string)`

Key `GameConfig.GameMode`, `GameConfig.MapName` and `QueueID` off the armed queue rather than hardcoding `"tutorialNew"` / `tutorialMapName` (`interactive.go:981`). Add a `queue → (gamemode, map)` table with the `AGS_ARM_QUEUE_*` overrides on top:

```
bots   -> ("PracticeMode", "/Game/Loki/Maps/Training/LVL_Training")     // the pair we can actually reach
default-> unchanged
```

⚠⚠ **Write a comment stating that these two fields DO NOT select the client's map on the empty-address route.** [M] the travel fn `0x58B9D30`'s 17 string refs are all `Address`-derived (`ConnectionSecret=%s` @ `+0x90F`, `ClientBuildVersion=%s` @ `+0x94F`), the single `?game=` literal in the image (`0x08D429B8`, 1 ref) belongs to MovieRenderPipeline, and no `MapName` UTF-16 literal reaches this path. They are almost certainly dedicated-server inputs [I]. **`docs/tutorial-launch-cmd.txt` is the load-bearing half.** Serve them anyway (they are free, they may matter to a listen/DS route later, and `MapName` is what the loading screen reads) — but do not expect them to steer travel.

### 1.7 — `GameConfig.BotConfig` — serve it, knob-gated

[M, two oracles] `FCoreGameBotConfig` = `{BotTeams int32, FillPartialTeamsWithBots bool, BotTeamDifficulty int32, AllyBotDifficulty int32}`. **Zero enums, zero containers, zero `FPrimaryAssetId`** — it cannot sink the document through any FK-14 failure class.

```
AGS_BOT_CONFIG        default ""  →  e.g. "teams=2,fill=true,botdiff=1,allydiff=1"
```

⚠ **Serve it, but do not expect it to do anything on the chosen route** — the roster gate it feeds is on the **BR arm only** (step 13). It matters for the eventual Skylands target, and it is cheap. ⚠ And the gap Lane C's verifier found is real and unresolved: `AuthGetMatchStartDetails` (impl `0x564d430`, REAL) reads `World+0x258` → GameState → **`GameState+0x5A0`**, and **nothing is known to write `+0x5A0` in a locally-opened world** (`SetSharedMatchStartDetails` writes `+0x738`, a different field). **Free offline task, do it before ever relying on BotConfig: transcribe the writer of `ALokiGameState+0x5A0`.**

### 1.8 — `POST /core-game/players/{id}/disassociate/{rest...}` — the repeatable loop

[M, upgraded from the lane's [I]] the concat order is readable in the LIT function `0x57A0EE0` (502 B, verb POST): `0x057A0F19` fetch id from `this[+0x30]` → `0x057A0F21` `lea rdx, <'/core-game/players/'>` + concat → `0x057A0F31` `lea r8, <'/disassociate/'>` + concat → `0x057A0F45` `mov r8, rbx` (the caller's arg2) + concat. So the shape is `POST /core-game/players/{playerId}/disassociate/{arg2}`.

Handler: clear `MatchID`, bump `MatchVersion`, `NotifyResource`, and **log the full raw path** so `arg2`'s identity is settled from the wire rather than inferred. Register with a wildcard tail. Without this, the only way to clear an armed match is to restart `ags`, and every playtest iteration costs a relaunch.

### 1.9 — Regression gates for Phase 1

* `AGS_ARM_QUEUE` unset ⇒ diff the served `/core-game/players`, `/core-game/matches`, `/party/parties` bodies against a pre-change capture: **byte-identical**.
* `TestMatchResultKeysAreServable`-style: add a test asserting `CoreGamePlayerVersion(id)` equals the `Version` the handler serves, and that it is strictly monotonic across two arms. (The S121 `Version int32` overflow and the S123 `push Version 7` staleness were both caught late; pin it.)
* Canaries on every arm: `LogJson "Unable to import"`, `Deserialization failure`, `Invalid response received`, `Fatal` — all must be **0**.

---

## 4. PHASE 2 — CONFIG / FORCE-OPEN, ONE LAUNCH

### 4.1 `docs/tutorial-launch-cmd.txt`

Replace the active line (currently the tutorial full-mode line) with:

```
open LVL_Training?game=/Game/Loki/Core/GameModes/BP_PracticeGameMode.BP_PracticeGameMode_C
```

Keep every existing line as a commented rollback, and add above it:

```
# S135 ACTIVE: PracticeMode on LVL_Training. Native base ALokiDropInGameMode is one of
#   fo's five slot-285 vtables (tutorial_launch.cpp:138-145). LVL_Training's OWN
#   DefaultGameMode is BP_PracticeGameMode_C, so the ?game= is redundant-by-design.
#   19 BP_LokiPlayerStart_C + 10 SafeTeamSpawnPathfindingAnchor in the PERSISTENT package
#   (no cell-streaming race). No spectator start, no DeathCircle, no phase durations.
# ROLLBACK (proven): the LVL_Tutorial line below.
```

⚠⚠ **THE FILE READ IS FLAKY BY THE SOURCE'S OWN ADMISSION** (`tutorial_launch.cpp:121-124`), and on failure it **silently falls back to `kDefaultCommand`, which is the tutorial**. Every other marker line looks normal. `LoadCommand` prints `[0] LoadCommand: open failed ... -> default fallback` (`:1386`). **Grep the marker for that line before interpreting anything.** If it fired, the flight is void, not negative.

### 4.2 Invocation

```powershell
# 1. server/internal/interactive/interactive.go -> forceTutorialMatch stays FALSE.
#    Instead: AGS_ARM_QUEUE=arm  AGS_ARM_QUEUE_QUEUES=bots  AGS_ARM_QUEUE_DELAY=8s
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags

# 2. ELEVATED. Steam already running. Back up capture.log first (ags truncates/appends
#    unreliably in BOTH directions -- the recorded behaviour is not trustworthy).
Copy-Item docs\capture.log docs\capture-preS135.log
.\configs\launch-redirect.ps1 -NoHook

# 3. Click PLAY -> PRACTICE -> CO-OP VS. AI -> FIND MATCH.  Watch capture.log.
# 4. ONLY once the client has parked (see readout R3), stage + inject:
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\tutorial_launch_botspawn.dll -Label s135-training
```
⚠ `fk24-stage.ps1` pre-flights `forceTutorialMatch == true` and refuses otherwise. Either flip it for this sitting (and flip it back) **or** add an `-AllowArmedQueue` bypass — the queue path arms the match through a different field now. Decide before the launch; discovering it at T+0 costs the window.
⚠ The stager's `-Probe` path is `tools\sigbypass-mod\build\…`, and `-AllowStale` is required for the deployed `fo`/`sp` pair.

### 4.3 PRE-REGISTERED READOUTS — write these down before the flight

**SUCCESS ladder (all four, in order):**

| id | signal | source | meaning |
|---|---|---|---|
| R1 | `GET /core-game/players/{id}` with `User-Agent: Loki/UE5-CL-0`, within ~3 s of the push | `capture.log` | the push landed and the version beat the cache |
| R2 | `GET /core-game/matches/match-{id}`, ~400 ms after R1 | `capture.log` | MatchID adopted; the doc parsed |
| R3 | `/lobby setUserStatusRequest` whose base64 `activity` decodes to `"a":"InMatch"` | `capture.log` | the client's own state machine agrees it is in a match — **a free readout nobody has been using** |
| R4 | `Attempting to travel to Match: ID:"match-…" Address:""` | `Loki.log` | `UTravelManager` ran |
| R5 | `Load map complete /Game/Loki/Maps/Training/LVL_Training` | `Loki.log` | the force-open worked on a map never loaded before |
| R6 | `Game class: BP_PracticeGameMode_C` and **no** `ALokiGameMode::Login failed to Login` | `Loki.log` | slot-285 coverage held for `ALokiDropInGameMode` |

**FAILURE disjunction — each mode is distinguishable, say which one you got:**

| observation | verdict | next move | cost |
|---|---|---|---|
| R1 absent | **push string or version fault, NOT a dead route.** Check the pushed resource is exactly `/core-game/players/<id>` (exact wide compare at `0x57C34B0`), then check `CoreGamePlayerVersion` > 0 | re-push by hand from the admin panel; if a `POST /api/ws/drop/{handle}` refetches and the push does not, **the push is the fault** | 0 launches |
| R1 present, R2 absent | MatchID was read and **rejected**. It is a Version problem, not a shape problem | pin with `AGS_ARM_QUEUE_VERSION` | 0 launches |
| R1+R2, no R3/R4 | the match doc parsed but `UTravelManager`'s state gate refused | sweep `tutorialMatchState`; `0x58A99C3` branches on `5 (InProgress)` and `0` at `0x058A9A9A/0x058A9AA1` — the derived bool's polarity is **unread [I]** | 0 launches (env knob) |
| R4 present with a **non-empty** Address | we served an address; the client will try a NetConnection and fail | ensure `ConnectionDetails.address` stays `""` | 0 launches |
| R4 present, R5 absent, marker shows `LoadCommand: open failed` | **VOID** — the cmd file was not read, `fo` flew the tutorial | fix the file/path, re-inject on the same PID | ~0 (re-inject) |
| R5 present, R6 shows `ALokiGameMode::Login failed to Login` | **slot-285 coverage does NOT extend to this base** | add `BP_PracticeGameMode_Code_C`'s native CDO vtable RVA to `kMatchVtRvas`; one-line change | 1 rebuild + 1 window |
| R5 present, then `failed to get ULokiServerPlatformInstance` + `Browse` back to lobby within ~300 ms | **the client was not parked on a valid match model** | this is the S63 revert; it means step 6/7 did not really arm. Do NOT read it as a map problem | 1 window |
| process dies before injection, only `gft`+`fo` resident | **FK-31 staging hazard (~27 %)** | nothing learned; re-launch | 1 launch |
| exit code `0x0000DEAD`, no artifact | **FK-32** | nothing learned; re-launch | 1 launch |

★ **The single most important line to write down first:** *"R1 absent does not mean the arming failed; it means the client did not ask."* Given ★NEW (two `startSoloMode` POSTs produced zero refetches), that is the **most likely** null in this whole plan, and without the disjunction it will be recorded as "arming the queue does nothing".

---

## 5. PHASE 3 — THE BOT SPAWN

★★ **This phase is INDEPENDENT of Phase 2 and should be flown FIRST, on the tutorial route we already own.** `Comp_BP_BotSpawner_C` is on `BP_LokiGameMode_Tutorial` [M — SCS_Node_1, `InternalVariableName "Comp_BP_BotSpawner"`, export `Comp_BP_BotSpawner_GEN_VARIABLE`], and the roster initialises unconditionally there (step 13). So `configs\fk24-stage.ps1` as-is, on `LVL_Tutorial`, with `forceTutorialMatch = true`, tests the entire bot chain with **zero new map, zero new Login question, zero backend dependency**. Do that before spending a window on `LVL_Training`.

### 5.1 The call

New run mode `RM_BOTSPAWN = 31` in `tools/sigbypass-mod/tutorial_launch.cpp` (`:169`; the enum currently ends at `RM_DISMOUNT=30`).

```
Comp_BP_BotSpawner_C::SpawnClassBotAtLoc(
    int32                              TeamIndex,        // [0]
    FVector                            Location,         // [1]
    int32                              Difficulty,       // [2]
    TSubclassOf<ALokiHeroCharacter>    HeroClassToSpawn, // [3]
    int32                              BotLevel,         // [4]
    ALokiHeroCharacter*&               CreatedBot)       // [5] OUT
```
Parameter names and order are [M] from `tools/extractor/out/bpdump_SpawnClassBotAtLoc.txt` (regenerated after the `bpdump` FField-name fix; every earlier dump printed `?` for every parameter). Flags: `FUNC_Public | FUNC_HasOutParms | FUNC_HasDefaults | FUNC_BlueprintCallable | FUNC_BlueprintEvent` — **no `FUNC_BlueprintAuthorityOnly`, no `FUNC_Net`**, and **zero `ServerOnly` / `HasAuthority` occurrences** across all 8 functions of the asset.

**Invoke with `CallBPGuarded`** (`tutorial_launch.cpp:1167`) — it is a BP-bytecode UFunction, so this is the right primitive; the S55 direct-`Func` thunk is for native UFunctions and ProcessEvent (vtable disp `0x270`, slot 78) is for Angelscript.

### 5.2 Risk class

**HEAP / no writes at all.** `CallBPGuarded` performs a call; it writes nothing to the module image and pokes no game data. The arm's only standing modification is the shim's existing `KFUNCSWAP` heap `UFunction.Func` swap used to reach the game thread — the **0/9 measured row**. ⛔ **No `.text` write of any kind.** Build it from the `dismount`/`rideable` template, not from `RM_GOTOPHASE` (enum 2), which arms with `InstallHook()`, a standing `ProcessInternal` `.text` patch — the 10/10-vs-3/36 hazard.

### 5.3 Guards (all read-only, all printed before the call; refuse rather than guess)

1. **GameMode** from `World->AuthorityGameMode` (`UWorld+0x250` [M, S131]); print its class name. Refuse unless it resolves.
2. **Component by NAME off the live GameMode's class** — walk the reflected `ObjectProperty` named `Comp_BP_BotSpawner` and read the pointer. ⛔ **Do NOT find it by `GUObjectArray` name search**: the archetype `Comp_BP_BotSpawner_GEN_VARIABLE` coexists with the live instance and `obj_by_class.py`-style substring matching returns the template. This is the fifth member of the class-lookup blind-spot family and it has produced a false result four times in this repo. Print the resolved address **and** its outer.
3. **Roster readout** `[BotSpawner+0xD8]` as a `TArray` header ([M], two disjoint functions: `GetSpawnableBots 0xFCCE40 = lea rax,[rcx+0xd8]; ret` and `SetSpawnableBots 0x52EC260 = add rcx,0xd8; jmp`). `Num > 0` proves `Initialize Bot Options` ran. `SpawnClassBotAtLoc` does **not** need it (it takes an explicit class), so a zero is informative but not disqualifying — and it is the pre-registered discriminator if `SpawnBot` returns null.
4. **`HeroClassToSpawn`** — resolve `BP_HERO_Ronin_C` (already loaded on the tutorial route) and verify by class-chain walk that it derives from `ALokiHeroCharacter`. Refuse on null. ⚠ On `LVL_Training` under PracticeMode the default hero is `Hero:'flex'`, not Ronin — read what is actually loaded rather than hardcoding.
5. **`TeamIndex`** — ⛔ **do NOT use `4`.** That is `UFFABotSpawnerComponent::GetNextTeamIndex_Implementation`'s `SpawnedTeamCount + 4` convention, and `Comp_BP_BotSpawner_C` **does not override `GetNextTeamIndex`** (0 occurrences in its 8-function export list) — it inherits the native one. Importing an FFA constant onto a non-FFA component is the exact "generalise from the variant you opened" failure FK-22 recorded. **Read the local player's team index off its PlayerState and pick a different one**; print both. A bot on the player's team means no combat and would read as "bots don't fight".
6. **`Difficulty = 1`, `BotLevel = 1`.** ⚠ `Difficulty`'s legal range is unsourced [S]. ⚠ `BotLevel` is a **no-op** [M]: `SetBotToLevelX`'s only effect is `ALokiCharacter::AuthGrantLevel`, whose impl is `0xF7EC20` (the universal `ret imm16 0` void fold, 371 records) against the same-class REAL control `GetCharacterLevel 0x55a9e40`.
7. **`Location`** — the player hero's live position + ~500 uu, or a resolved `BP_LokiPlayerStart_C`. ⛔ Do **not** use `"Spawn AI Hero Bot"` as the first arm: its location comes from `GetAllActorsOfClassWithTag(BP_LokiRespawnBeacon_Unlimited_C, "BotSpawnStart")` and `LVL_Tutorial` contains **zero** of those across the persistent level and all 67 World-Partition cells (4 positive controls passing in the same pass) ⇒ the bot would spawn at world origin.

### 5.4 ⚠⚠ THE INTERPRETABILITY TRAP — PRE-REGISTER THIS OR THE WINDOW IS WASTED

Traced from the bytecode myself:

* `[2] EX_LetObj CallFunc_SpawnBot_ReturnValue ← EX_FinalFunction SpawnBot(HeroClass, Location, TeamIndex, Conv_IntToByte(Difficulty), EX_NoObject, "")`
* **that local is assigned once and NEVER READ AGAIN** — 2 occurrences in the whole dump, the declaration and the assignment.
* `[5] GetPlayerStatesOnTeam(self, TeamIndex)` → `[8] EX_JumpIfNot → 739`
* found branch: `[17] IsBotControlled` ∧ `[18] ObjectIsA(HeroClassToSpawn)` → `[21] SetBotToLevelX` → **`[22] CreatedBot = <the hero>`** → `[23] Jump 829`
* not-found branch: **`[24] CreatedBot = EX_NoObject`** → `[25] Jump 829`

⇒ **A NULL `CreatedBot` DOES NOT MEAN THE SPAWN FAILED.** It means no PlayerState on that team owned a pawn that was both `IsBotControlled` and `ObjectIsA(HeroClassToSpawn)` **at that instant** — which a fully successful spawn will also produce if the bot's PlayerState has not yet joined the team array synchronously. Conversely, if a bot of that class already exists on that team, the loop returns the **pre-existing** one.

**Therefore the arm must carry a second, independent readout that does not depend on the scan:** a **`GUObjectArray` census delta of `ALokiBotController` and `ALokiHeroCharacter` instances across the call**, taken by exact-ancestor walk (`asc_census.py`'s `is_pawnlike` pattern), never by leaf-name substring.

### 5.5 Free receipts

* ★★★ **STRUCTURAL BASELINE OF ZERO.** Across the full 1,126-file log corpus, `SpawnBots` / `MakeNewBotController` / `TrySpawnTeam` / `SpawnBot` / `BotSpawner` / `AIController` / `SetSpawnableBots` all read **0 files**, against passing positive controls in the identical sweep (`LogNavigation` 284, `BotNavLink` 174, `Recast` 191). And the tutorial's own 296-statement ubergraph never references any bot function [I — 5 of 32 UFunctions dumped]. ⇒ **nothing measured after the call can be background activity**, the property that made S132's dismount attributable.
* `"No valid spawn location found for bot team"` (UE log record `.rdata 0x08B12320`, emitted from `TrySpawnTeam 0x055703EA→0x0557040B`) — **greppable, zero corpus baseline**. Only fires on the `TrySpawnTeam` route, so its absence on the `SpawnClassBotAtLoc` route is expected, not negative.
* ⚠ **Do not build the ability readout on `AbilitySystemComponentStorage @ +0xF00`** — `s111-asc-census.md §12` already measured that writing it *lands and is not sufficient* (`AvatarActor` still NULL). Use the existing **`AvatarActor`-identity** detector `ReportAscActorInfo` (`tutorial_launch.cpp:11906`), which already emits the pre-registered `*** AVATAR IS THE HERO -- BOUND ***`. ⚠ **And read the bot's ASC BEFORE injecting `play`** — `KWIREGAS` defaults to `1` (`:4869`) and builds an ASC + forces `ROLE_Authority` on every `RM_PLAY` init, which makes any ability reading taken afterwards uninterpretable.

### 5.6 Within-run negative controls

1. **Sibling-team control.** Census team `T_bot` **and** team `T_player` before and after. `T_player` must **not** gain a bot-controlled pawn. A move on both means the census is measuring something else.
2. **Read-only pre-arm.** Sequence the injection as: `A0` = full guard readout + both censuses + roster `Num`, **no call**; wait one tick; `A1` = the call; `A2` = both censuses again. If the census moves between `A0` and `A1` the sitting is **VOID** — the tutorial spawned a bot on its own and the baseline is not zero.
3. **The `ObjectIsA` control comes free.** Print, before the call, how many bot-controlled pawns of `HeroClassToSpawn` already exist on `T_bot`. Baseline is 0; if not, `CreatedBot` is uninterpretable and say so up front.

### 5.7 Escalation ladder for one sitting (each step's precondition is the previous step's result)

1. `SpawnClassBotAtLoc` — one bot, explicit class, needs no roster.
2. `Spawn Random Bot At Loc` — proves `Initialize Bot Options` ran and `SetSpawnableBots` landed (`[0] GetSpawnableBots` → `[1] Array_Random` → `[2] SpawnClassBotAtLoc`).
3. `SpawnBotTeamAtLoc` — `Array_NRandom` over the roster then N × `SpawnClassBotAtLoc`: **a whole enemy team**.

**Builds:** `build.ps1 -Name tutorial_launch -Variant botspawn`. ⚠⚠ **`-Variant X` WITHOUT `-Name tutorial_launch` silently builds the default set and reports "11 built, 0 failed"**, which reads like success. ⚠ **Diff the `.text` sha256, never the size** — `dismount` and `dismount-podland` share a size. Regression gates to re-verify after the edit: `play 9bc10a4552c596e1`, `dropplane_b1only 5b4467b0105dec1a`, `droppod-pe-cdopoke 249a3cd2190eb334`, `dismount 03d807ab6d397537`.

---

## 6. WHAT WILL PROBABLY GO WRONG (ranked)

| # | Failure | How to tell it apart from success | Cost |
|---|---|---|---|
| 1 | **The client never re-fetches `/core-game/players` even after the push.** ★NEW makes this the single most likely null: two `startSoloMode` POSTs produced **zero** refetches, and the resource is fetched exactly once per messenger connection across 8 captures. | R1 absent. Distinguish push-fault from channel-fault with the built-in control: `POST /api/ws/drop/{handle}` (S85/S120, measured refetching this resource 4/4). **Drop refetches + push does not ⇒ the push string or version is wrong**, not the channel. | 0 launches |
| 2 | **`SpawnClassBotAtLoc` returns a null `CreatedBot` on a successful spawn.** §5.4. Native `SpawnBot` is dark in 50/50 images and cannot be pre-validated. | The object census delta (§5.4) is the discriminator. `+N ALokiBotController` with `CreatedBot == null` ⇒ **success with a lagging PlayerState**, not failure. | 0 extra (the readout is in the same arm) |
| 3 | **`LVL_Training` + PracticeMode has never been force-opened** and hits a new Login/PlayerState gate. | `ALokiGameMode::Login failed to Login` ⇒ slot-285 coverage gap (add the vtable RVA, one line). `PlayerState is null` ⇒ the S61/S63 `InitPlayerState` de-override needs extending to this PC class. Both are named, both are cheap. | 1 window each |
| 4 | **FK-31 staging hazard, ~27 % of launches.** | Process dies with only `gft`+`fo` resident, `0xC0000005`, `RIP == runtime.dll base + 1`. Nothing learned. | 1 launch, budget on **armed windows** (~2 per 4 launches) |
| 5 | **The cmd file read fails and `fo` silently flies the tutorial.** | `LoadCommand: open failed ... -> default fallback` in the marker (`:1386`), plus `Load map complete .../LVL_Tutorial` instead of `LVL_Training`. **Grep the marker before interpreting anything.** | ~0 (re-inject on the same PID) |
| 6 | **The armed MatchID sticks and bricks the menu.** `/core-game/players` reports it forever; every subsequent START becomes a silent no-op (observed at S107). | The menu stops responding to FIND MATCH after the first arm. `MatchID` is `json:"-"` so a restart clears it, and §1.8's disassociate route clears it live. | 1 `ags` restart |
| 7 | **`queue.restrictions.bots` gets served by accident** (hand-added, or copied from the `deathmatch` knob without the `Level` sub-key). | The tile **locks** and FIND MATCH **greys**, showing `Requires Hunter's Journey level 3`. `bots` moves off its unconditional-TRUE arm onto `AccountLevel >= SelectInt(Config["Level"], 3, found)`, and `FPartyMember.AccountLevel` has never been served (reads 0). ⇒ **keep `AGS_QUEUE_UNLOCK` empty for `bots`.** | 1 flight if it slips in |
| 8 | **The bot spawns on the player's team** because someone imported FFA's `TeamIndex = 4`. | The bot stands there and does nothing. Reads exactly like "bots don't fight". Prevented by guard 5 and detected by the sibling-team census. | 1 window |
| 9 | **The bot spawns and cannot act** (no ability system). | `AvatarActor` readout on the bot's ASC, taken **before** `play` is injected. This is the [S] step and the honest expected outcome is "unknown". | 0 extra |
| 10 | **A `MOVE_Walking` traversal crash** if anyone tries to test terrain. S94 iter1 died ~50 s in on `UWorld::AddToWorld` for a newly streamed WP cell; the shipped workaround is `KFLYMODE 5`, which is *also* the confound that makes any traversal reading meaningless. The two cannot both be satisfied by defaults. | Sentry handler on `AddToWorld`. Measurement predates `gft_ready_fix` on this route and is unverified in either direction. | 1 window |
| 11 | **`FJsonObjectConverter` rejects the whole match document** on a wrong-typed matched key. | `LogJson: Unable to import JSON value into property <name>` names it verbatim. `BotConfig` is the safest struct available (4 scalars); the risk is in `GameConfig`'s neighbours. **Fly `AGS_BOT_CONFIG` in its own batch.** | 0 (env knob) |
| 12 | **A grep-based corpus negative is a silent SIGABRT zero.** On this Git-Bash setup `find … -exec grep {} +` *and* `xargs -n40 grep` both abort and return nothing; one file with 718 hits reads as 0. | **Use `rg --no-ignore` (ripgrep 14.1.1 is present and works), never `grep` for a corpus sweep, never `2>/dev/null`, and always carry a positive control in the SAME sweep.** `dumps/` is git-ignored so `--no-ignore` is mandatory or the denominator silently drops from 1,126 to ~88. | would cost a whole finding |

---

## 7. WHAT WE ARE NOT DOING, AND WHY

* **`SkylandsBRBotsGameMode` on `LVL_Skylands_WP`** — the "real" `bots` world. 2,215 WP cells, never loaded; 29 exports / 21 gameplay components (DeathCircle, DropPlane, Bosses, Vaults, SupplyDrop…); requires the whole FK-22 drop chain and the S131/S132 rideable wall; and its bot roster is gated on `AuthGetMatchStartDetails` → `GameState+0x5A0`, whose writer is unidentified. **Ship here last, not first.**
* **`FreeForAll` on `LVL_Training`** — owns the only `SafeTeamSpawnPathfindingAnchor`s in the game (10, persistent), but `bStartPlayersAsSpectators = true`, `MaxPlayersPerTeam = 1`, and respawn routes through the empty `ALokiGameMode::SpawnPlayer` stub `0x0F7EB50`. `angelscript-ffa-bots.md:1005-1015` lists **five** hard prerequisites, not one.
* **`Holdout` / `LVL_Holdout`** — 0 persistent PlayerStarts, spectator start, mandatory `DeathCircleClass`.
* **`BRQuickGameMode`** — the most attractive-sounding alias in `DefaultEngine.ini:146` and **not shipped**: `grep -ci skunkworks allfiles.txt` = 0 over 107,123 files.
* **`Battlefield` / `LastMan` / `Domination` / `Barracuda`** — native bases outside `fo`'s five vtables ⇒ Login-dead [I, strong; the vtable RVAs were never located, so this excludes rather than proves].
* **`UFFABotSpawnerComponent::BeginPlay` (Angelscript)** — still unprobed and needs ProcessEvent, but it supplies a **roster, not a spawn**, and nothing identifies its owner object. The Blueprint spawner does the same job with an owner we can resolve.
* **`ULokiBotSpawnerComponent::TrySpawnTeam` (native, `0x5570390`)** — fully transcribed, fold-free, no authority check, but gated on the **dark** location provider `0x5557070` whose null is its only failure path. `SpawnClassBotAtLoc` takes an explicit Location and skips it.
* **`BP_LokiGameMode_Tutorial_C::"Spawn AI Hero Bot"`** — would spawn at world origin (`BotSpawnStart` tag: 0 packages of 68).
* **`ALokiPlayerCheats::SpawnBot`** — **does not exist.** `0x556D910` is `ULokiBotSpawnerComponent::SpawnBot`; `ALokiPlayerCheats` has no bot verb (the session brief was wrong). Its nearest relative `ServerCheatSpawnActor` (impl `0x541bda0`, REAL and **lit in `merged10`**, contra `fk6-cheat-surface-settled.md:744`'s "dark everywhere") is `Net|NetReliable|NetServer`, so it would attempt net routing through ProcessEvent — usable only via the S55 direct thunk, and it is not a bot route.
* **`BP_LokiSpawner_Basics_*` / `BP_Tutorial_JouleBotManager`** — three of the four ship in `LVL_Tutorial`'s persistent level and no session has ever probed them, but they are minion/creep spawners, not hero-bot spawners. Free offline `bpdump` if the main route stalls. ⚠ Grade the `ULokiBlueprintLibrary::ServerOnly` exec pin (`impl 0x1311870 = mov byte [rdx],0; ret`, 18/18 images) **before** building anything on them.
* **`BP_PatrolBotSpawner_C`** (5 in `LVL_Training`, 5 in `LVL_Practice`) — derives from plain `AActor`, lives under `Objectives/Practice/Spike/`, drives patrol dummies. **Named here specifically so "the training map is full of bot actors" is not read as confirmation.**
* **`Cheat.Onboarding.MatchHistoryCount`** — registered with default **-1** and flags word **1** (very likely `ECVF_Cheat`, dead under shipping's `DISABLE_CHEAT_CVARS`). Drop the cvar shortcut; use `AGS_MATCH_HISTORY=minimal` if games-played is ever needed.
* **Serving match history to "release the BASIC TRAINING preselect"** — the prescription at `fk-playability-audit-s134.md:388` is **unsupported**. `Get Number of Games Played`'s only consumer is a once-per-profile tutorial auto-start, and that branch is already dead on this machine (`UserSettings.ini:3 HasPlayedTutorial=True`). The preselect actually comes from the client's own `?defaultQueue=tutorialNew` seeding `SelectedQueueID` (`interactive.go:1231-1233`).
* **Any `.text` write.** The measured ladder at a 320 s hold is: nothing **0/22** · heap & bytecode **0/9** · transient `.text` **4/12** · standing `.text` **7/8**. Phase 3 is a pure call.

---

### Free offline checks to run BEFORE any launch (each closes a named unknown for zero windows)

1. **`extractor bpdump BP_PracticeGameMode @props` + its full UFunction list** — does its spawn path route through the empty `ALokiGameMode::SpawnPlayer` stub like FFA's does? This single fact decides whether the chosen pair puts a hero on the ground.
2. **Grade `ULokiBlueprintLibrary::ServerOnly` inside `BP_PracticeGameMode`'s and `Comp_BP_BotSpawner`'s bodies** — 0 hits across the 8 bot-spawner functions is [M], but the *positive control matters*: `ServerOnly` appears in 9 of 703 bpdump files **including the tutorial GameMode's own ubergraph**, so the instrument works. (`HasAuthority` appears in **0 of 703** — that half of the grep is degenerate and contributes nothing.)
3. **Transcribe the writer of `ALokiGameState+0x5A0`** — decides whether `GameConfig.BotConfig` can ever reach the BR roster gate.
4. **Locate `ALokiDropInGameMode`'s CDO vtable slot 285** and confirm it is one of `fo`'s five (the chain `BP_PracticeGameMode_C → BP_PracticeGameMode_Code_C → Class'LokiDropInGameMode'` is [M]; the vtable identity is inherited-by-name and worth one read).
5. **Dump `LVL_Tutorial` and `LVL_Holdout` persistent packages** to settle their PlayerStart counts — Lane B asserted 0 as [M] but never dumped them, and the NameMap census contradicts it.

### Two standing pointers to fix while here (both one-line, both currently misleading)

* `docs/endpoints.md:49` still calls `/core-game/players` an *"active poller (~17/s)"*. ★NEW measurement refutes it. Mark it **stale, S62-era, contingent on startSoloMode's client-side flow**.
* `CLAUDE.md:1015` still quotes `merged8` in the canonical ladder. `dumps/merged10.dump.exe` exists (55.33 %, +41 pages) and both `strxref.py:77` and `CLAUDE.md:3000-3003` were already moved — only the historical ladder line lags. ⚠ **`ls dumps/merged*.dump.exe | tail -6` sorts `merged10` second and hides it**; I hit this exact artifact during planning, and Lane E's verifier hit it too. Never conclude "file absent" from a truncated sorted listing.