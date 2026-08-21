# S135 (2026-08-21) — the matchmaking QUEUE arms a match, and `UTravelManager` fires

**One line: CO-OP VS. AI now produces a match. `POST /joinQueue` → 8 s → armed MatchID → pushed →
the client refetched, escalated to the match document, and attempted to travel. Backend-only: no
relaunch, no injection, no `.text` write, no shim.**

This is the first time in this project's history that the **matchmaking** path (as opposed to the
solo `startSoloMode` path) has armed anything.

---

## 0. What was flown

One `ags` restart with `AGS_ARM_QUEUE=arm`, on a client that had already been up **3.4 hours** at the
menu. One human click on FIND MATCH. Nothing else.

```
AGS_ARM_QUEUE=arm  AGS_ARM_QUEUE_DELAY=8s  AGS_ARM_QUEUE_QUEUES=bots
```

Code: `server/internal/interactive/armqueue.go` (new), plus the widened gate in
`handleCoreGamePlayer` and `SetResourceNotifier` wiring in `server/cmd/ags/main.go`.

## 1. The result — all seven pre-registered predictions

The predictions were written down **before** the click, precisely so a null would be interpretable
(S133's own lesson). Every one hit.

```
00:45:25  #2895 POST /party/parties/party-9b9d.../joinQueue -> 200
00:45:25  interactive: joinQueue player=9b9d... queue="bots"
00:45:25  interactive: armqueue: will arm player=9b9d... queue="bots" in 8s (mode=1)
00:45:33  interactive: armqueue: ARMED player=9b9d... queue="bots"
                       matchID="match-9b9d..." version=1787291133 mode=1
00:45:33  interactive: armqueue: pushed /core-game/players/9b9d... version=1787291133 label=armqueue
00:45:33  * WS NOTIFY[armqueue] -> /core-game/players/9b9d...
                       {"Resource":"/core-game/players/9b9d...","Version":1787291133,"Payload":""}
          #3031 GET /core-game/players/9b9d...                  <- THE CLIENT REFETCHED
          #3033 GET /core-game/matches/match-9b9d...            <- AND ESCALATED

[2026.08.21-05.45.33:416][1] LogTravelManager: Attempting to travel to Match:
    ID:"match-9b9d2c887e2524f918e383a895f2f1c2" Address:"" Fleet:"revival-fleet-0001" Region:"na"
```

### Receipts, and why each is the discriminating one

| receipt | measured | why this value and not another |
|---|---|---|
| `joinQueue` request count | **1** | S133 established the client re-POSTs every 10–35 s while REJECTED. Exactly one ⇒ the `FParty` response under an advanced `Version` was accepted. |
| `/core-game/players` fetches | **1 → 2** | The single most important number here. **Zero** additional would mean the push is dead. An unbounded stream would mean the too-high-`Version` refetch loop `push.go` warns about. **Exactly one** is the only value consistent with a correct push. |
| `/core-game/matches` | **1** | The client believed the MatchID and escalated. |
| `leaveQueue` | **0** | Nothing cancelled; the state came from the arm. |
| canaries | `Fatal` 0 · `Deserialization failure` 0 · `Unable to import` 0 · `Invalid response received` 0 | The document was accepted whole. |
| processes | game + ags both alive after | No crash. |

## 2. TWO `[S]` QUESTIONS SETTLED TO `[M]`

### 2.1 `NotifyResource` drives `/core-game/players/` — [S] → [M]

The messenger-resource **registration** was [M] offline (`UCoreGameManager`'s init `0x57BD610`
registers `/core-game/players/` and `/core-game/matches/` as resource prefixes). That a **push**
actually triggers the refetch was only **[I, strong]**, by analogy with `/match-history/players/`
(S117). **Nobody had ever pushed this resource.**

It works. And the built-in discriminator was never needed — the fallback plan (if the push did
nothing, drop the socket via admin and see whether *that* refetches, measured 4/4 elsewhere) is
recorded here only because it is the right design, not because it was used.

### 2.2 The client accepts a positive push from a `Version: 0` baseline — [S] → [M]

This was flagged in the recon as *"the most likely cause of a false null."* We serve `Version: 0`
while idle; whether the client caches 0 and adopts any positive push, or ignores the resource until
it holds a non-zero baseline, was untested. **It adopted `1787291133` from a 0 baseline.**

## 3. What this does NOT show — scope, stated plainly

- ⚠ **`Address:""` is CORRECT and is not a failure.** With an empty `ConnectionDetails.address` the
  client **parks locally** rather than opening a NetConnection (S62: zero NetConnection attempts).
  That park is the precondition the force-open route needs.
- ⚠ **NO MAP LOADED, and none was expected.** [M] `GameConfig.MapName` / `GameConfig.GameMode`
  cannot select the client's world — the travel URL is built from `ConnectionDetails.Address` alone,
  and the only `?game=` literal in the image belongs to MovieRenderPipeline. The world still comes
  from the force-open shim reading `docs/tutorial-launch-cmd.txt`.
  ⇒ **What is proven is the MATCH-ARMING half. The WORLD half is unchanged.**
- ⚠ **No bot was spawned and none was attempted.** That is `RM_BOTSPAWN`, which needs a staged
  tutorial world and was not part of this flight.
- ⚠ **`bots` IS Breach.** [M] `BP_LokiBattleRoyaleGameMode_Skylands_Bots_C` inherits
  `..._Skylands_Breach_C` and adds exactly one CDO property. Arming a `bots` match does not make
  Breach playable; it makes the queue *answerable*.

## 4. Method notes worth keeping

- ★ **The attribution is the CLIENT'S OWN LOG.** `LogTravelManager` is in `Loki.log`, so the
  User-Agent trap — which has produced a fabricated headline **twice** in this project — cannot
  apply here. When a result can be read off the client's own log instead of off `capture.log`,
  prefer it; it removes the whole question of who made the request.
- ★ **The knob's controlled negative exists and was built in the same commit.** `AGS_ARM_QUEUE=empty`
  serves a valid document with an ADVANCING `Version` and an EMPTY `MatchID`, i.e. it moves exactly
  one field. Reverting to `off` changes the document *and* the version together and is
  uninterpretable — the `AGS_PLAYER_RANK=0` mistake S122 recorded. It was not needed for a positive
  result; it is there for the negative that did not happen.
- ⚠ **`docs/capture.log` was 226 MB and was backed up to `docs/capture.log.pre-armqueue-s135`
  BEFORE the restart**, per the documented truncation hazard. The copy is a consistent prefix (the
  source grew 1,357 bytes mid-copy because ags was live) — that is expected, not corruption.
- ⚠ The pre-flight check that mattered: the client was verified to be at the **menu**
  (`LVL_LobbyV2_Persistent`, no `LVL_Tutorial` in `Load map complete`) and the persisted
  `selectedQueueId` was verified to be `bots` BEFORE the click. Had the selected queue been anything
  else, `AGS_ARM_QUEUE_QUEUES=bots` would have declined to arm and the null would have looked like a
  dead route.

## 5. Next

1. **The return leg.** `POST /core-game/players/{id}/disassociate/{...}` (fn `0x57A0EE0`, 502 B,
   verb POST) is a real unserved endpoint. Serving it converts this from a one-shot into a
   repeatable loop. Today the only clear is `leaveQueue` → `cancelArm`.
2. **`RM_BOTSPAWN`** on a staged tutorial world (`forceTutorialMatch = true`, relaunch, then
   `gft` → `fo` → `sp` → the arm). Built and verified, not yet flown:
   `botspawn ae89d06b91164e5f` · `botspawn-readonly f5f9896feeac45dc`.
3. **What the armed match does with a world.** The two halves have never been combined: this flight
   armed a match with no world, and every prior tutorial sitting force-opened a world with no armed
   match. Combining them is untried and free.


---

# ADDENDUM — A HERO PAWN SPAWNED (attempt 3, 2026-08-21)

**`Comp_BP_BotSpawner_C::SpawnClassBotAtLoc` works. It spawned a hero pawn at the exact location we
asked for. There is no AI controller on it — which is a localised, offline-answerable result, not a
dead end.**

## The measurement

One-shot ladder, one game-thread hit, in a staged tutorial world (gft → fo → sp → probe) that was
itself reached **with `forceTutorialMatch = false`**, using the queue-armed MatchID to satisfy the
stager's preflight.

```
A0  BotController=0  LokiHeroCharacter=2   (136,483 objects)
A1  BotController=0  LokiHeroCharacter=2   <- STABILITY CONTROL PASSED (750 ms, no call)
    THE CALL: SpawnClassBotAtLoc(team=0, loc=(600,0,13240), diff=1, BP_HERO_Ronin_C, lvl=1)
A2  BotController=0  LokiHeroCharacter=3   (136,952 objects, +469)
```

★★★★★ **PAYLOAD FINGERPRINT — the new pawn is at the location this arm computed and nothing else in
the process knows:**

```
player   0x296C33D8020  loc = (0.0,   0.0, 13240.0)
NEW BOT  0x297FCD1AAC0  loc = (600.0, 0.0, 13240.0)   = player.X + KBSOFFSET(600)
```

Both are `BP_HERO_Ronin_C`; `obj_by_class` confirms exactly **2** live `BP_HERO_` instances where A0
saw one. +469 objects is a character's component tree. Same evidence class as S131's
`CurrPodDestination` and S132's landing point.

## The negative, and it is NOT an instrument artifact

`BotController` delta = **0**. Before recording that, it was checked against a *second, independent*
instrument with a *different matching strategy*:

| instrument | strategy | BotController | AIController |
|---|---|---|---|
| the arm's own census | class **CHAIN** contains | 0 | — |
| `tools/re/obj_by_class.py` | class **LEAF NAME** contains | **0** | **0** |

Two strategies, same answer, on a live world of 192,337 objects. ⚠ `obj_by_class`'s detail list caps
at 60 rows — the `found N` line was parsed, never the line count (the documented saturation trap).

⇒ **[M] A pawn spawned and nothing controls it.** A pawn with no AI is not yet a bot.

## ★ THE BY-PRODUCT: `SpawnBot` IS NOW READABLE, PERMANENTLY

`ULokiBotSpawnerComponent::SpawnBot` impl **`0x556D910`** was **all-zero in all 50 images on disk** —
the repo graded it DARK-not-stripped (fold multiplicity 1). Driving the path decrypted it (S118's
steerable decryption):

```
merged10 : 00 00 00 00 00 00 00 00 00 00 00 00        <- dark in every prior image
NEW      : 40 55 53 56 57 41 54 41 55 41 56 41        <- push rbp/rbx/rsi/rdi/r12/r13/r14...
```

Captured to `dumps/s135-botspawn/` and merged to **`dumps/merged11.dump.exe`** (+6 pages, **0 overlap
conflicts**, so the strict-superset property holds). ⇒ **the question "why is there no controller"
is now answerable OFFLINE, with zero launches**, by reading `0x556D910` and finding whether it calls
a stripped `MakeNewBotController`.

## What the flight-1 repair bought

Both flight-1 defects are fixed and the fixes are validated in flight:

- **One-shot ladder.** `hitsGT=1` again — the world still delivers exactly one game-thread hit — but
  the whole ladder now completes inside it. The paced version produced no verdict from the same
  input.
- **Hero resolution by class CHAIN**, in the same world pass, with per-candidate diagnostics:
  ```
  heroCand[0] 'LokiHeroCharacterGrid' root=0x0 -> no readable location
  heroCand[1] 'BP_HERO_Ronin_C' root=0x29661B511E0 -> USABLE
  ```
  Flight 1's `FindInstByClass("LokiHeroCharacter")` matched the LEAF name only, and the possessed
  hero is `BP_HERO_Ronin_C` — the class-lookup blind-spot family for the sixth time.
- **Census cost.** One pass per census with a per-UClass memo (1,024 classes memoised): ~3.8–5.0 s
  per pass over 136k objects, vs an unmemoised two-passes-per-census design that would have held the
  game thread for ~12–15 s.

⚠ `playerTeam` read **-1** (`teamOff=0xE88`), so the bot was spawned on team 0 against an unassigned
player. That is not known to matter for the spawn, and it IS a reason not to read "the bot did not
fight" off this run.

## Open, and cheap

1. **Read `0x556D910` offline** in `merged11` — does it call a stripped impl where the controller
   would be created? That is the whole remaining question and it costs nothing.
2. `SpawnBotTeamAtLoc` / `Spawn Random Bot At Loc` — the roster is populated (**Num=13, Max=16**), so
   both are reachable; they were the pre-registered escalation ladder.
3. Whether a controller-less pawn can be made to act, or whether possession is a separate stripped path.

## ★ AND THE OFFLINE READ WAS DONE IMMEDIATELY — `SpawnBot` CONTAINS TWO STRIPPED CALLS

Scanning the newly-decrypted `0x556D910` in `merged11` for rel32 calls to the four known folds:

```
0x556DE43: e8 d8 0d a1 fb        call 0x0F7EC20      ret imm16 0     (STRIPPED, void)
           44 8b 44 24 50        mov  r8d,[rsp+0x50]
           48 8b d7              mov  rdx,rdi
           49 8b cd              mov  rcx,r13
0x556DE53: e8 08 0d a1 fb        call 0x0F7EB60      xor al,al; ret  (STRIPPED, returns false)
```

**[M] `SpawnBot` calls two stripped-fold functions, adjacently: one void, one returning false with
THREE arguments (`rcx`, `rdx`, `r8d`).**

⚠⚠ **DO NOT WRITE THIS UP AS "SpawnBot calls `LokiIsServer`."** That was the first reading and it is
WRONG: `LokiIsServer()` takes **no arguments**, and this call site sets up three. `0x0F7EB60` has
**26,444 call sites image-wide** — it is a shared `xor al,al; ret` stub that ICF folds many distinct
stripped functions onto one address, so **the address identifies nothing by itself**. This is the
repo's own recorded rule (*"always print fold multiplicity next to a folded RVA"*, the 91-way-folded
`execFoo 0x5254180` case) and it was nearly re-committed here.

What IS supportable: **[M]** the bot-spawn path runs through the same stripped server-authority cut
that FK-1 named and FK-42 generalised — a 3-argument bool-returning function that always returns
false, immediately after a void stub, inside the function that should create the controller.
**[I, strong]** that pair is the controller-creation branch. Naming the two functions requires the
UHT `.data` record table (which grades REAL/EMPTY without decryption) or the AS symbol table.

⚠ **Scope on the scan:** the window was an arbitrary `0x600` bytes from the entry — `.pdata` has no
row for `0x556D910` in `pdata_union.csv`, so the true extent is unconfirmed and the scan may overrun
into a neighbour. The two fold sites sit ~`0x533` in, which is plausible for a function with this
prologue, but that is not a measurement.


---

# ADDENDUM 2 — A THREE-HERO ENEMY TEAM SPAWNED (same client, 2026-08-21)

**`SpawnBotTeamAtLoc` spawned THREE bots of three DIFFERENT, GAME-CHOSEN hero classes in one call.**

```
fn='SpawnBotTeamAtLoc' 0x297B18C7A00
   params: Team@0x0 Loc@0x8 Diff@0x20 Class@0xFFFFFFFF Num@0x24 Level@0x28 CreatedBotTeam@0x30
'SpawnBotTeamAtLoc' takes no HeroClassToSpawn -- Hero-class guard SKIPPED, not failed
NumBots@0x24 = 3
CreatedBotTeam TArray: Data=0x29786F45660  Num=3  Max=4
A0=4  ->  A1=4 (stability control PASSED)  ->  A2=7      (+3 heroes, +1,414 objects)
```

★★★★★ **THE FINGERPRINT IS THE CLASS SET, AND IT IS STRONGER THAN ANY COUNT.** An independent
`obj_by_class` census finds six live `BP_HERO_` instances:

| class | count | origin |
|---|---|---|
| `BP_HERO_Ronin_C` | 3 | the player + the two explicit single spawns (Ronin was passed both times) |
| `BP_HERO_Sniper_C` | 1 | **game-chosen** |
| `BP_HERO_Void_C` | 1 | **game-chosen** |
| `BP_Hero_Storm_C` | 1 | **game-chosen** |

**This call passed NO class (`Class@0xFFFFFFFF`).** The three new pawns are three *different* heroes
the game selected itself from its own 13-entry roster (`GetSpawnableBots -> Array_NRandom -> loop ->
SpawnClassBotAtLoc`). The arm could not have produced Sniper/Void/Storm by accident.

★ **Three agreeing readouts:** the out-param (`CreatedBotTeam.Num=3`), the arm's own census (+3), and
an independent `obj_by_class` walk (3 new classes). ~471 objects per hero, matching the +469 measured
for the single spawn.

⚠ `BotController` / `AIController` remain **0** on both instruments. **Three uncontrolled pawns.**

## Param offsets, predicted then confirmed

Predicted from the re-dumped signature *before* the flight, confirmed live:
`TeamIndex@0x0 · Location@0x8 · Difficulty@0x20 · NumBots@0x24 · BotLevel@0x28 · CreatedBotTeam@0x30`.
The re-dump was only possible because of the CUE4Parse `Name`-field fix made this session — the
pre-fix dump printed `?` for all 18 properties.

## Two defects of mine, and how each was caught

1. **`#define KBSFUNC` was spliced INSIDE the existing `#ifndef KBSOFFSET` guard**, so it redefined
   the macro and silently overrode `-DKBSFUNC` from the command line. The run looked like a team test
   and was actually a repeat of the single spawn. **Caught by the arm's own diagnostics** — the
   printed `params:` list showed `Class@0x28` (the single-call signature) and no `Num`.
   ⚠ The rebuilt DLL had an **identical `.text` SIZE** (182,272 both ways); only the hash moved
   (`a94fc4cf890c5b07` -> `892a4c67014facfd`). This is the repo's "diff the hash, never the size"
   rule earning itself in real time.
2. **The params guard still required `HeroClassToSpawn`** after GUARD 4 had been made conditional, so
   it refused a perfectly resolvable call. The arm **refused rather than writing a params blob at
   guessed offsets** — the guard behaving correctly on my own oversight.

⚠ **Cosmetic, unfixed:** the `---- THE CALL: SpawnClassBotAtLoc ----` banner is a hardcoded string
and does NOT follow `KBSFUNC`. The authoritative line is `fn='<name>' 0x...`. Do not read the banner.

## ⚠⚠ AND A CORRECTION TO ADDENDUM 1's DIAGNOSIS

Addendum 1 attributed flight 2's failure to **game-thread starvation**. **That was wrong**, and an
adversarial verification lane refuted it with the artifact:

> flight 2's marker continues past where it was read — `[FS] t=+30s hitsGT=2 called=1`, `census A1`,
> `STEP 3`, `[FS] t=+45s hitsGT=194 called=193`, `census A2`, `done (step=4 ...)`.

**The ladder completed.** It was read MID-RUN and the truncation point was taken for the end — the
instrument-artifact pattern, committed while writing about it. The genuine failure was the
hero/location resolve, and flight 2's own verdict line said exactly that: `NOT RESOLVED -- nothing
was called`.

★ **The real mechanism [M]: self-inflicted game-thread BLOCKING, not starvation.** Step 0 ran ~6 full
`GUObjectArray` sweeps at 1.2–2.6 s each and held the game thread 15–30 s. **`allThreadCalls` is the
discriminator, not `hitsGT`**: `allThreadCalls>0 && called<allThreadCalls` means *we are inside our
own step*, which is the opposite diagnosis from starvation. The staged world dispatches ~13–17 BP
UFunctions/s — corroborated by this file's own `KPLHOLDHITS` note.

⇒ **The one-shot restructure was not needed for the reason given.** It works, and the hero-resolution
fix (which WAS the real defect) is why bots spawn — but the arm now holds the game thread ~12–16 s
per run, and it is the ONLY mode that violates the codebase's established pattern:
**resolve + before-census on the WORKER thread before `FsArm()`; only the CALL on the game thread;
after-census in `*FinalReport()` on the worker after `FsDisarm()` + a settle `Sleep`.**
`RM_POOLSPAWN`, `RM_DROPPOD`, `RM_RIDEABLE` and `RM_DISMOUNT` all do it that way and say so in
comments. **Restructuring RM_BOTSPAWN to match is the outstanding cleanup — offline, no launch.**


---

# ADDENDUM 3 — WHY THERE IS NO CONTROLLER. THE CHAIN IS CLOSED, OFFLINE.

**`MakeNewBotController` RUNS and bails at its FIRST guard, on a stripped `F(UWorld*) -> nullptr`.
That is the same fold, the same shape and [I, strong] the same getter as FK-22's round-game-mode
wall — so the bot spawn and the drop-pod rider handoff are blocked by ONE function.**

All of this is offline, from the page the flight itself decrypted. Zero launches.

## The chain, end to end

```
SpawnClassBotAtLoc / SpawnBotTeamAtLoc          (BP)      -> works
  -> ULokiBotSpawnerComponent::SpawnBot  0x556D910        -> RUNS (pawn appears)
       0x556DB23  call MakeNewBotController 0x5563660     -> RUNS  [M, see below]
            0x55636A8  call 0x35AFC40           GetWorld()      r13 = UWorld*
            0x55636B0  mov  rcx, r13
            0x55636BB  call 0x0F7EB50           STRIPPED -> NULL          <== THE WALL
            0x55636C5  test rax, rax
            0x55636C8  je   0x5563d0c           NULL => jump to the EXIT
       0x556DBD1  call 0x39C3DB0                UWorld::SpawnActor -> the PAWN still spawns
       0x556DD69  mov  rdi,[rbx+0x3D8]          PlayerState
       0x556DD73  test rdi,rdi / je 0x556DE58   NULL => SKIP the next two calls
       0x556DE43  call 0x0F7EC20                STRIPPED void   (skipped on our runs)
       0x556DE53  call 0x0F7EB60                STRIPPED false  (skipped on our runs)
       0x556DE5F  call ALokiGameState::GetTeamState  [REAL]
```

⇒ **no controller -> no PlayerState -> the team/hero-class assignment is branched around -> an
uncontrolled hero pawn.** Every observation from the flights falls out of this one bail.

## [M] `MakeNewBotController` really did execute

`.text` decryption is MONOTONE within a process, so a page that is zero before and non-zero after is
proof of execution (S118's steerable decryption):

| function | merged10 (pre-flight) | post-flight capture | verdict |
|---|---|---|---|
| `MakeNewBotController 0x5563660` | all zero | `40 55 56 41 54 41 55 41 56 41 57 …` | **NEWLY DECRYPTED -> IT RAN** |
| `FindValidPositionForCharacter 0x5656580` | all zero | `48 8b c4 f3 0f 11 58 20 …` | **NEWLY DECRYPTED -> IT RAN** |
| `SpawnBot 0x556D910` | all zero | `40 55 53 56 57 41 54 41 55 …` | **NEWLY DECRYPTED -> IT RAN** |

The census had all three as `IMPL-PAGE-DARK` — **not** EMPTY. Grading them "stripped" would have been
the FK-20 error; they were simply never executed by anything, ever, until now.

## The two calls in `SpawnBot`, named — and they are NOT the blocker

⚠ **They never execute on our runs** (the `PlayerState == NULL` branch at `0x556DD73` jumps past both),
so they are downstream of the real failure. Named anyway, for the record:

**`0x556DE53` = `ALokiGameState::SetPlayerTeam(ALokiPlayerState* Player, int32 TeamIndex)`**
*Argument shape and provenance are [M]; the NAME is [I, strong].*
1. **[M] `this` (r13) is an `ALokiGameState*`** — proven not by inference but because
   `ALokiGameState::GetTeamState` (REAL, named in the census) is called with the SAME `r13` as `this`
   two instructions later, at `0x556DE5F`. Provenance: `[rsi+0xC0]` (WorldPrivate) -> `0x56F01A0`.
2. **[M] arg1 (`rdi`) = `[rbx+0x3D8]` = the PlayerState** — and `0x3D8` is the exact offset the shim
   printed live this session (`PlayerState@0x3D8 is NULL`). Two instruments, same offset.
3. **[M] arg2 (`r8d`) = `[rsp+0x50]` = spilled `r9d`** = SpawnBot's 4th x64 argument = `TeamIndex`,
   matching the BP call order `SpawnBot(HeroClass, Location, TeamIndex, …)`.
4. Signature filter over the **76** false-fold records joined to the UHT bind table, keeping
   `bool F(<objptr>, <int>)`: **2 survivors**, the other being `URigVM::GetParameterValueBool`
   (Control Rig VM; first param is an `FName&`) — trivially implausible here.

**`0x556DE43` = `ALokiPlayerState::ServerSetHeroClass(TSubclassOf<ALokiCharacter>)`** — **[I]**, weaker.
`this` (rcx) = the PlayerState [M]; one argument passed BY REFERENCE (`lea rdx,[rsp+0x78]`, a slot
holding a just-dereferenced object pointer), which is how MSVC passes a `const TSubclassOf<X>&`.
Filtering the **371** void-fold records to PlayerState classes with one non-scalar param gives **2**
survivors; the other is `SetMissionProgress(const FMissionInfo&)`. Semantics and the `Server*` prefix
fit, but this rests on a narrower argument than the `SetPlayerTeam` identification.

⚠⚠ **HARD LIMITATION ON BOTH NAMES:** the candidate pools contain only **reflected UFunctions**. A
direct rel32 call to a folded impl means the caller was linked against a C++ symbol, which need not
be reflected at all — so the true callee may simply not be in the pool. Neither name is [M].

⚠⚠ **AND A FOLDED RVA NAMES NOTHING BY ITSELF.** `0x0F7EB50` has ~27,217 call sites, `0x0F7EC20`
~165,789, `0x0F7EB60` ~26,444. An earlier draft of this work nearly published *"SpawnBot calls
`LokiIsServer`"* — false, because `LokiIsServer()` takes no arguments and that site sets up three.

## ★★★★★ THE UNIFICATION, and it is the useful part

CLAUDE.md records FK-22's wall as **"[M] ONE GETTER, THREE CONSUMERS"** —
`AuthPlayerEnterWorldAttachedToRidable` (gates on it), `AuthPlayerPreSpawnOnAddToPlane` (gates on it),
`AuthPlayerEnterWorld` (consumes it un-gated), all calling `0x0F7EB50` and bailing.

**There is a FOURTH consumer: `ULokiBotSpawnerComponent::MakeNewBotController`** — same fold, same
`F(World) -> ptr` shape, same null-test-and-bail. **[I, strong]**, not [M], precisely because the fold
address is non-identifying; what makes it strong is the identical argument shape (a `UWorld*`), the
identical use (null-tested, immediate bail), and that FK-22's getter is already established as taking
the world and returning the round game mode.

⇒ **The drop-pod rider handoff and the AI-bot controller are the SAME blocker.** Fixing one getter
fixes both.

## What this makes possible next

⛔ **Do not try to satisfy the getter.** CLAUDE.md is explicit and it still holds: `0x0F7EB50` is
`33 c0 c3` — three bytes, **zero memory operands**, so there is nothing to poke; and a `Func` swap is
dead because the AS callers reach the impl by rel32.

★ **But the object exists.** FK-22 measured **[M]** that the round game mode is live, is the object
S124 flew `GoToPhase` on, PASSES the wall's own `IsA<ALokiRoundGameMode>` check, and is cached at
`Comp_GameMode_DropPlane_Tutorial+0xE0`. Only the ACCESSOR was deleted.

⇒ The project's proven workaround pattern applies (S123 `AddToRoot`, S130 the CDO byte, S132 the
`PlayersAttached` append): **do not satisfy the stub — hand-assemble its persistent output and invoke
the next real function.** Here that means creating the controller ourselves and possessing the pawn:
`APawn::SpawnDefaultController` / spawn an `AIController` + `AController::Possess`, both engine
functions. Whether they are real in this image is the next free offline check.

⚠ **AND A BLIND SPOT IN MY OWN CENSUS, STATED:** I counted only classes whose chain/leaf contains
`BotController` or `AIController`. A controller of some other class name would have been missed. The
live client is gone, so this cannot be re-checked now; the `Controller`-substring census returned
**196** objects and only 3 were displayed (the 60-row cap). Re-run it with the full list next time a
world is staged before treating "no controller of any kind" as settled. The narrower claim —
`MakeNewBotController` bailed before creating anything — rests on the disassembly, not the census.


---

# ADDENDUM 4 — THE `SpawnAIFromClass` ARM IS BUILT (not yet flown)

**Route: stop trying to satisfy the stripped getter; use a different, intact entry point.**
That is the S123/S130/S132 pattern, applied to the controller.

## Why this route

The component route's failure is now read end-to-end from the binary (Addendum 3):
`MakeNewBotController` bails on a stripped `F(UWorld*) -> nullptr` at `0x55636BB`, so the controller
is NULL, so `AController::Possess` — **which is REAL and which `SpawnBot` already calls at
`0x556DD3C`** — is skipped by `test rcx,rcx / je` at `0x556DD37`.

## The three-state grading that picked the target

⚠ Graded fold / real / **DARK** — never a two-state "is it a fold?" test. That two-state test printed
a FALSE "REAL CODE" for an all-zero page during this very investigation and had to be corrected.

| function | rva | verdict |
|---|---|---|
| `AController::Possess` (vtable slot **267** = `+0x858`) | `0x36E2B60` | **REAL** — `48 89 5c 24 20 55 56 57 41 56 41 57` |
| `APawn::SpawnDefaultController` (slot **280** = `+0x8C0`) | `0x3BBF3C0` | **DARK** — page never decrypted. NOT stripped, NOT confirmed real. |
| **`UAIBlueprintHelperLibrary::SpawnAIFromClass`** | `0x4631C50` | **REAL**, 2,133 B, **0 stripped-fold calls** |
| its callees `0x4607AB0` / `0x4609C40` / `0x45CCB60` / `0x39C5280` | — | all **REAL**, 0 folds |

Slots came from `tools/strxref/vtables.py name AController|APawn`. ⚠⚠ **Do NOT sample a byte offset
across unrelated vtables** — an earlier attempt scanned `+0x858` over 589 long-enough vtables and
reported "173 point at a fold", which is MEANINGLESS: offset `0x858` is a different method in every
unrelated hierarchy. Resolve the SPECIFIC class's vtable.
⚠ And `.rdata` in a dumped image holds **absolute VAs**, not RVAs — a first scan that forgot to
subtract `ImageBase` found "2 vtable candidates" in a 170 MB UE image (the real number is 7,830).

## The arm

`build.ps1 -Name tutorial_launch -Variant botai` — `KBSAI=1` inside `RM_BOTSPAWN`, so it REUSES the
whole proven harness: the one-shot ladder, the A0/A1 stability control, the A2 census and the verdict.
Only the resolve+call is swapped.

`SpawnAIFromClass` is `BlueprintCallable` + **STATIC** on a `UBlueprintFunctionLibrary` ⇒ a NATIVE
UFunction ⇒ the **S55 direct thunk** (`CallNativeGuarded`) with **context = the CDO**
(`Default__AIBlueprintHelperLibrary`), the same shape the shim already uses for the static
`GetLocalLokiPlayerCheatsBP`. **Not** `CallBPGuarded` (BP bytecode) and **not** ProcessEvent slot 78
(Angelscript). Risk class: CALL-ONLY, no module-image write, refuses under `KFUNCSWAP=0`.

**Artifacts** (⚠ `botspawn` and `botteam` share a `.text` SIZE of 182,272 — diff the HASH):

| variant | `.text` sha256 |
|---|---|
| `botai` | `c55cb560cc602e31` |
| `botspawn` | `e48c90bc6cf17c93` |
| `botteam` | `0c16652dc0338d33` |

Regression gates re-verified after the edit: `play 76e5c1093c390536` and `dismount 7fbe025cad6e7ca3`
both **UNCHANGED**. `verify_dll.py` VERDICT **PASS** (no C++ exception machinery, no CRT import).

## ★ PRE-REGISTERED PREDICTIONS — written before the flight

| # | prediction | why it is the discriminator |
|---|---|---|
| **P1** | **BotController/AIController census delta > 0** | **THE POINT.** The component route measures 0 on two independent instruments. If this route also gives 0, the controller is unreachable by ANY spawn entry point and the blocker is deeper than the entry point. |
| P2 | `LokiHeroCharacter` delta +1 | `SpawnAIFromClass` spawns the pawn itself. |
| P3 | `ReturnValue` is a non-null `APawn*` | corroborator, **not** the verdict. |
| **P4** | **`APawn::SpawnDefaultController 0x3BBF3C0` goes DARK -> DECRYPTED** | a free, permanent, OFFLINE-checkable receipt that the engine's controller path executed — independent of any census. `dumpimage` before the client exits, either way. |

⚠ `BehaviorTree` is deliberately **null**: the engine spawns the pawn and its default controller
first and only runs a BT if one is supplied. A controller that appears but does nothing is a
BEHAVIOUR question, not a spawn failure — do not conflate the two.
⚠ `bNoCollisionFail = true` is **required**: the staged hero sits at Z≈13,240 and a colliding spawn
would fail for a reason unrelated to the stripped code.

## Two instrument notes from building it

- ⚠ **A string-presence test is NOT a call test.** `SpawnBotTeamAtLoc` appears in the `botspawn`
  binary — not because it is called, but because the literal sits in this arm's own success-verdict
  MESSAGE (`tutorial_launch.cpp:14695`), which compiles into every variant. The decisive half of the
  check is that `SpawnAIFromClass` is present in `botai` and **absent** from `botspawn`/`botteam`,
  because that literal exists only inside the `#if KBSAI` block.
- ⚠ The `botai` binary is ~11 KB SMALLER than the others, which is the independent corroboration
  that the `#if` really excluded the component route.

## Standing cleanup, unchanged

`RM_BOTSPAWN` still holds the game thread ~12–16 s per run and is the only mode violating the
codebase pattern (resolve + before-census on the WORKER thread before `FsArm()`, only the CALL on the
game thread, after-census in `*FinalReport()` after `FsDisarm()`). Restructuring it is offline and
costs no launch.


---

# ADDENDUM 5 — ★★★★★ `SpawnBot` HAS A `PremadeBotController` PARAMETER, AND IT SKIPS THE BROKEN FUNCTION

**The game ships its own bypass for the exact wall we hit, and the Blueprint layer is what hides it.**

## The declaration nobody had read

`tools/asdump/out/binds_members.csv`:

```
ULokiBotSpawnerComponent::SpawnBot(
    const TSubclassOf<ALokiHeroCharacter> HeroClass,
    const FVector Location,
    const int TeamIndex,
    const uint8 Difficulty = 4,
    AController PremadeBotController = nullptr,     <== THE BYPASS
    FString BotName = "")
```

⇒ ★ **The decisive move was not disassembly — it was reading the function's own declaration.** Method
rule #2 ("read the shipped artifacts first") applies to a UHT signature table exactly as it does to a
`.ini` or a `.uasset`.

## Verified from the bytes, three links

```
0x556D943  mov  rcx, qword ptr [rbp + 0x1a8]   <- stack arg 6 = PremadeBotController
0x556D957  mov  qword ptr [rsp + 0x70], rcx    <- spilled into the "controller to use" slot
...
0x556DAA1  test rax, rax                       <- PremadeBotController
0x556DAA4  jne  0x556db32                      <- NON-NULL => JUMP PAST MakeNewBotController
0x556DB23  call 0x5563660                      <- MakeNewBotController (bails on the stripped getter)
0x556DB28  mov  qword ptr [rsp + 0x70], rax    <- ONLY the new-controller path overwrites the slot
...
0x556DD2F  mov  rcx, qword ptr [rsp + 0x70]    <- the SAME slot
0x556DD34  test rcx, rcx / je 0x556dd41
0x556DD3C  call 0x36E2B60                      <- AController::Possess  [REAL]
```

**`[rsp+0x70]` is written in exactly two places image-wide within this function** (`0x556D957` from
the parameter, `0x556DB28` from `MakeNewBotController`) and read once, at the `Possess` guard.

⇒ **[M] Passing a non-null `PremadeBotController`:**
1. skips `MakeNewBotController` entirely — the function that bails on the stripped `F(UWorld*)->nullptr`;
2. leaves the parameter sitting in the slot `Possess` reads;
3. therefore reaches **`AController::Possess`, which is REAL** (`0x36E2B60`).

★ Arg ordering corroborated three ways: `Difficulty` (uint8) at `[rbp+0x1a0]`, `PremadeBotController`
at `[rbp+0x1a8]`, `BotName` (FString ops + `FMemory::Free`) at `[rbp+0x1b0]` — consecutive 8-byte
stack slots, textbook MSVC x64.

## ⇒ WHY THE BLUEPRINT ROUTE CAN NEVER WORK

`Comp_BP_BotSpawner_C::SpawnClassBotAtLoc` calls
`SpawnBot(HeroClass, Location, TeamIndex, Conv_IntToByte(Difficulty), **EX_NoObject**, "")` —
it **hardcodes null** for `PremadeBotController`. Every BP entry point on that component does. So the
BP layer always takes the broken branch, by construction. **That is the whole reason the pawns spawn
uncontrolled**, and no amount of work at the Blueprint level could have changed it.

`SpawnBot` is itself a reflected UFunction, so the **S55 direct thunk reaches it with our own
controller** — bypassing the BP wrapper entirely.

## Two arms, complementary — not competing

`ULokiBotSpawnerComponent` has exactly ONE property (`SpawnedTeamCount`) and no controller-class
field, so a premade controller has to come from somewhere. That makes the order natural:

1. **`botai` (built, `c55cb560cc602e31`)** — `SpawnAIFromClass`, which spawns a pawn **and** its
   default controller. Its P1 (controller census delta > 0) answers the prerequisite question:
   *can a controller be created on this client at all?* If yes, it also supplies a live controller
   and its concrete class.
2. **`botpremade` (not yet built)** — spawn/borrow a controller, then call native `SpawnBot` with
   `PremadeBotController` set. This is the game's designed path and yields a proper Loki bot
   (correct hero class, team, name) rather than a generic engine AI pawn.

⚠ Do not fly (2) before (1): without a known-good controller source, a null in (2) would be
uninterpretable — it could be "the bypass does not work" or simply "we passed a bad controller".

## Corrections this pass produced

- ⚠ **`MakeNewBotController`'s page is LIT in `merged11` — the S131 census row (`IMPL-PAGE-DARK`) is
  STALE.** It was decrypted by our own flight. Re-grade before quoting that census on this page.
- ⚠ **Page `0x556E000` is DARK**, so the lit window here is only `0x556D000..0x556DFFF`. `SpawnBot`
  ends at `0x556DF17`, **0xE9 bytes short of the cliff — luck, not design.** Check `page_lit` before
  reading any neighbour.
- The true extent is `0x556D910..0x556DF17` = **1,544 bytes** (established six ways: 8 pushes ↔ 8 pops,
  security cookie set/checked, exactly one `ret`, 100 % recursive-descent coverage, the previous
  function's `ret` at `0x556D90F`, the next prologue at `0x556DF20`). My earlier "1,552" used the next
  function's start rather than the last byte.
- Call census over the true extent: **39 direct calls / 28 distinct targets / 2 folds**. I said 27
  distinct; 28 is right (the extra is almost certainly `__security_check_cookie`).
- ★ **The `SetPlayerTeam` bool result is DISCARDED [M]** — `0x556DE58` is a join point with three
  incoming branches that bypass the call, and `GetTeamState` overwrites `rax` before any read. It is a
  fire-and-forget mutation, **not a gate**. So even reaching it would not have gated anything.
