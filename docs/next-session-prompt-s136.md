# NEXT SESSION (S136) — relaunch, arm the queue, and fly `botai`

**One line: bots SPAWN but have NO CONTROLLER, the cause is read out of the binary, and the fix is one
call. Fly `tutorial_launch_botai.dll` into a staged tutorial world and read ONE number: the
BotController census delta.**

Written 2026-08-21 at the end of S135. Read `docs/s135-queue-arms-a-match.md` first — its five
addenda are the evidence for everything below.

---

## 0. WHAT S135 ACHIEVED (do not re-derive any of this)

| result | grade | where |
|---|---|---|
| **The matchmaking QUEUE arms a match.** `joinQueue` → 8 s → MatchID → push → client refetches → fetches the match doc → `LogTravelManager: Attempting to travel to Match` | **[M]**, reproduced **3×** | `server/internal/interactive/armqueue.go` |
| `lobby.NotifyResource` DOES drive `/core-game/players/` — was `[S]`, nobody had ever pushed it | **[M]** | fetches went 1 → 2, **exactly one** refetch |
| The client accepts a positive push from a **`Version: 0`** baseline — the flagged "most likely false-null cause" | **[M]** | adopted `1787291133` from 0 |
| `GET /core-game/players/{id}` is fetched **ONCE per messenger connection**, never polled — `interactive.go`'s own comments are REFUTED | **[M]** | 1:1 over 8 captures |
| **The stager's preflight passes on a queue-armed MatchID with `forceTutorialMatch = false`** — the documented "set the flag and relaunch" step is no longer needed | **[M]** | `fk24-stage.ps1:199` gates on MatchID only |
| **Bot PAWNS spawn.** `SpawnClassBotAtLoc` → +1 hero at the exact passed location; `SpawnBotTeamAtLoc` → **+3 heroes of 3 game-chosen classes** (Sniper/Void/Storm) with `CreatedBotTeam.Num=3` | **[M]** | 3 agreeing readouts |
| `SpawnBot`, `MakeNewBotController`, `FindValidPositionForCharacter` decrypted by driving the path | **[M]** | merged into **`dumps/merged11.dump.exe`** |

⚠ **`bots` IS Breach** — `BP_LokiBattleRoyaleGameMode_Skylands_Bots_C` inherits `..._Skylands_Breach_C`
and adds one CDO property. Arming a `bots` match does NOT make Breach playable; it makes the queue
answerable. The bot work rides on the TUTORIAL world.

---

## 1. THE BLOCKER, READ END TO END FROM THE BINARY

```
Comp_BP_BotSpawner_C::SpawnClassBotAtLoc / SpawnBotTeamAtLoc   (BP)  -> works
 -> ULokiBotSpawnerComponent::SpawnBot 0x556D910                     -> RUNS, pawn appears
      0x556DAA1 test rax,rax / jne 0x556db32   PremadeBotController non-null => SKIP the next line
      0x556DB23 call MakeNewBotController 0x5563660
           0x55636A8 call GetWorld()
           0x55636BB call 0x0F7EB50    STRIPPED -> nullptr        <== THE WALL
           0x55636C8 je  0x5563d0c     NULL => jump to the EXIT
      0x556DB28 mov [rsp+0x70], rax    (only this path writes the slot)
      0x556DD2F mov rcx,[rsp+0x70]     <- the controller
      0x556DD34 test rcx,rcx / je      NULL => SKIP Possess
      0x556DD3C call 0x36E2B60         AController::Possess   [REAL, never reached]
      0x556DD73 test rdi,rdi / je      PlayerState NULL => skip ServerSetHeroClass + SetPlayerTeam
```

**[I, strong] the stripped `F(UWorld*) -> nullptr` is the SAME getter FK-22 recorded as "ONE GETTER,
THREE CONSUMERS". `MakeNewBotController` is a FOURTH consumer.** ⚠ NOT [M] — `0x0F7EB50` has ~27,217
call sites and the address names nothing by itself.

⛔ The getter cannot be poked (`33 c0 c3`, three bytes, **zero memory operands**); a `Func` swap is
dead (AS callers reach the impl by rel32). So do NOT try to satisfy it — use a different entry point.

---

## 2. ★ START HERE — FLY `botai`

### 2.1 The exact procedure

⚠ **Set the env in the SAME PowerShell call as the launcher** — `launch-redirect.ps1:209` kills any
running `ags` and starts its own, which inherits your environment. Shell state does NOT persist
between tool calls.

```powershell
# ELEVATED PowerShell. Steam must already be running (else Auth Failure 14005).
cd "G:\git\Supervive Revival Project"
$env:AGS_ARM_QUEUE        = 'arm'
$env:AGS_ARM_QUEUE_DELAY  = '8s'
$env:AGS_ARM_QUEUE_QUEUES = 'bots'
.\configs\launch-redirect.ps1 -NoHook
```

Wait for the client to settle — **uptime >= 118 s AND `TryUIReady SUCCESS` >= 1 AND one
`Load map complete .*LobbyV2_Persistent`** in `%LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log`.

Then arm the match. Either click **PLAY -> CO-OP VS. AI -> FIND MATCH**, or do it yourself (the
persisted `selectedQueueId` is already `bots`):

```powershell
$party = "party-9b9d2c887e2524f918e383a895f2f1c2"
Invoke-WebRequest -Uri "http://127.0.0.1:8080/party/parties/$party/joinQueue" -Method POST -UseBasicParsing -UserAgent "s136-arm-NOT-THE-GAME" | Out-Null
# wait ~14 s, then CONFIRM before staging:
#   MatchID non-empty at /core-game/players/9b9d2c887e2524f918e383a895f2f1c2
#   >=1 'GET /core-game/matches/' in docs\capture.log   (stager gate 3)
```

Then stage + inject:

```powershell
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_botai.dll -Label s136botai -AllowStale
```

`-AllowStale` is REQUIRED (the deployed `fo`/`sp` differ from `build\`; the deployed pair is what every
recorded flight used — keep it for comparability).

### 2.2 Read exactly ONE number

```
grep -E "^\[BS\]" docs/tutorial-launch-marker.txt
```

⚠⚠ **WAIT FOR `[BS] done` BEFORE INTERPRETING ANYTHING.** In S135 the marker was read MID-RUN and the
truncation point was taken for the end, producing a fabricated "game-thread starvation" diagnosis that
an adversarial lane later refuted. The ladder is one-shot and each census sweep takes ~4 s, so give it
**~40 s** after injection.

### 2.3 PRE-REGISTERED PREDICTIONS (written before the flight — do not revise them after)

| # | prediction | meaning |
|---|---|---|
| **P1** | **BotController / AIController census delta > 0** | **THE POINT.** The component route measures **0** on two independent instruments. If this route ALSO gives 0, the controller is unreachable by any spawn entry point and the blocker is deeper than the entry point. |
| P2 | `LokiHeroCharacter` delta **+1** | `SpawnAIFromClass` spawns the pawn itself. |
| P3 | `ReturnValue` = non-null `APawn*` | corroborator, **NOT** the verdict. |
| **P4** | **`APawn::SpawnDefaultController 0x3BBF3C0` goes DARK -> DECRYPTED** | a free, permanent, OFFLINE receipt that the engine controller path executed, independent of any census. |

★ **P4 costs one command and must be taken EITHER WAY, before the client exits:**

```powershell
.\tools\usmapdump\usmapdump.exe dumpimage SUPERVIVE-Win64-Shipping.exe dumps\s136-botai
```
⚠ The `.exe` suffix is REQUIRED — without it the tool prints "process not found" while the game is
alive. Then check `0x3BBF3C0` in that dump vs `merged11` (all-zero -> non-zero = it ran), and merge:
```powershell
.\tools\usmapdump\usmapdump.exe mergedumps dumps\merged12.dump.exe dumps\merged11.dump.exe dumps\s136-botai\SUPERVIVE-Win64-Shipping.dump.exe
```

⚠ A NULL `BehaviorTree` is deliberate and expected to be fine — the engine spawns the pawn and its
default controller first and only runs a BT if given one. **A controller that appears but does nothing
is a BEHAVIOUR question, not a spawn failure. Do not conflate them.**

---

## 3. IF P1 SUCCEEDS -> BUILD `botpremade` (the game's own designed bypass)

**[M] `SpawnBot` has a `PremadeBotController` parameter and it SKIPS the broken function:**

```
SpawnBot(const TSubclassOf<ALokiHeroCharacter> HeroClass, const FVector Location,
         const int TeamIndex, const uint8 Difficulty = 4,
         AController PremadeBotController = nullptr,      <== THE BYPASS
         FString BotName = "")
```

`[rsp+0x70]` is written in exactly TWO places in the whole function — `0x556D957` from that parameter
and `0x556DB28` from `MakeNewBotController` — and read ONCE, at the `Possess` guard. So a non-null
premade controller skips the stripped path **and lands in the slot `Possess` reads**.

⇒ **This is why the Blueprint route can never work:** `SpawnClassBotAtLoc` hardcodes `EX_NoObject`
for that parameter. Every BP entry point on the component does. `SpawnBot` is itself a reflected
UFunction, so **the S55 direct thunk reaches it with our own controller**, bypassing the BP wrapper.

⚠ **Do NOT fly `botpremade` before `botai` succeeds.** `ULokiBotSpawnerComponent` has exactly one
property (`SpawnedTeamCount`) and no controller-class field, so without a known-good controller source
a null is uninterpretable: "the bypass does not work" and "we passed a bad controller" look identical.
`botai` supplies both the answer and a live controller instance + its concrete class.

---

## 4. THE ARM — what it is and what to trust

`build.ps1 -Name tutorial_launch -Variant botai` (`RM_BOTSPAWN` + `KBSAI=1`). Risk class **CALL-ONLY**:
no module-image write, no data poke, no PI hook; it REFUSES under `KFUNCSWAP=0`.

`UAIBlueprintHelperLibrary::SpawnAIFromClass 0x4631C50` is **REAL, 2,133 B, 0 stripped-fold calls**,
and its four notable callees (`0x4607AB0 / 0x4609C40 / 0x45CCB60 / 0x39C5280`) are all REAL with 0
folds. It is `BlueprintCallable` + **STATIC** on a `UBlueprintFunctionLibrary` ⇒ NATIVE UFunction ⇒
**S55 direct thunk (`CallNativeGuarded`) with context = the CDO** (`Default__AIBlueprintHelperLibrary`).
NOT `CallBPGuarded` (BP bytecode) and NOT ProcessEvent slot 78 (Angelscript).

**Artifacts** — ⚠ `botspawn` and `botteam` share a `.text` SIZE of 182,272. **Diff the HASH, never the size.**

| variant | `.text` sha256[:16] |
|---|---|
| `botai` | `c55cb560cc602e31` |
| `botspawn` | `e48c90bc6cf17c93` |
| `botteam` | `0c16652dc0338d33` |

⚠⚠ **THESE DIGESTS COME FROM AN INLINE HASHER, NOT FROM A VETTED TOOL, AND THEY DO NOT REPRODUCE THE
REPO'S RECORDED VALUES.** `build.ps1` emits no digest and `verify_dll.py` prints no section hash, so
there is no canonical recipe on disk. The recorded gates (`play 9bc10a4552c596e1` etc.) were produced
by some other method. **The only sound gate check is a BEFORE/AFTER differential inside ONE method:**
build from `git show HEAD:` source, hash; restore, rebuild, hash; compare. Under that test S135's
edits moved **nothing** (`play 76e5c1093c390536`, `dismount 7fbe025cad6e7ca3` identical both ways).
★ Writing the canonical digest recipe into a script is a real, cheap, outstanding task.

---

## 5. TRAPS THAT COST TIME IN S135 — do not re-pay them

1. ⚠⚠ **Read the marker only after `[BS] done`.** Reading mid-run produced a fabricated starvation
   diagnosis. The discriminator is **`allThreadCalls`**, not `hitsGT`: `allThreadCalls > 0 &&
   called < allThreadCalls` means *we are inside our own step*, the OPPOSITE of starvation.
2. ⚠⚠ **A folded RVA names NOTHING.** `0x0F7EB50` ~27,217 sites, `0x0F7EC20` ~165,789, `0x0F7EB60`
   ~26,444. "SpawnBot calls `LokiIsServer`" was nearly published — false: `LokiIsServer()` takes no
   arguments and that site sets up three.
3. ⚠⚠ **Grade three-state: fold / REAL / DARK.** A two-state "is it a fold?" test printed a false
   "REAL CODE" for the all-zero `APawn::SpawnDefaultController`. DARK is NOT stripped and NOT real.
4. ⚠⚠ **`.rdata` in a dumped image holds ABSOLUTE VAs, not RVAs.** Forgetting `ImageBase` found "2
   vtable candidates" in a 170 MB UE image (real answer: 7,830).
5. ⚠⚠ **Never sample a byte offset across unrelated vtables** — `+0x858` is a different method in
   every hierarchy. Use `tools/strxref/vtables.py name <Class>`.
6. ⚠ **A string-presence test is NOT a call test.** `SpawnBotTeamAtLoc` appears in the `botspawn`
   binary only because the literal sits in a verdict MESSAGE (`tutorial_launch.cpp:14695`).
7. ⚠ **`MakeNewBotController`'s census row (`IMPL-PAGE-DARK`) is STALE** — our own flight decrypted it.
   Re-grade before quoting `scratchpad/s131/lane-d-empty-impl-census.tsv` on this page.
8. ⚠ Page `0x556E000` is DARK. `SpawnBot` ends at `0x556DF17`, 0xE9 bytes short of the cliff — luck.
   Check `page_lit` before reading neighbours.
9. ⚠ **Back up `docs\capture.log` before restarting `ags`** (it was 226 MB; truncation is documented
   and behaves unreliably in both directions).
10. ⚠ A user left/right-clicking in the staged world crashed the client once. That was **user input,
    not FK-31/FK-32 and not the shims** — do not file it as a protector kill.

---

## 6. STANDING CLEANUP (offline, no launch)

- **`RM_BOTSPAWN` violates the codebase pattern.** Every other mode does resolve + before-census on the
  **WORKER** thread before `FsArm()`, only the CALL on the game thread, and the after-census in
  `*FinalReport()` after `FsDisarm()` + a settle `Sleep`. `RM_BOTSPAWN` does all of it on the game
  thread and holds it ~12–16 s. `RM_POOLSPAWN` / `RM_DROPPOD` / `RM_RIDEABLE` / `RM_DISMOUNT` all say
  so in comments — copy one.
- The `---- THE CALL: SpawnClassBotAtLoc ----` banner is a hardcoded string and does NOT follow
  `KBSFUNC`. The authoritative line is `fn='<name>' 0x...`.
- **The return leg:** `POST /core-game/players/{id}/disassociate/{...}` (fn `0x57A0EE0`, 502 B, POST)
  is a real unserved endpoint. Serving it turns the arm-a-match loop from a one-shot into a repeatable
  one. Today the only clear is `leaveQueue` -> `cancelArm`, or restarting `ags` (MatchID is `json:"-"`).
- `strxref.py`'s `DEFAULT_DUMP` was moved to `merged10` in S135; **`merged11` now supersedes it** and
  a `merged12` will exist after §2.3. Keep the default current or pass the image explicitly.

---

## 7. THE ONE-PARAGRAPH STATE OF CO-OP VS. AI

The tile, the click, the queue, the timer and the cancel all work and always did. The queue now
**answers** — backend-only, reproduced three times, with `UTravelManager` firing and the client
parking locally exactly as designed. A staged tutorial world can now be reached **with
`forceTutorialMatch = false`**, using the queue-armed MatchID to satisfy the stager. Bot **pawns**
spawn, singly and as a randomised team of three drawn from the game's own 13-entry roster. The single
remaining gap is the **AI controller**, its cause is read out of the binary end to end
(`MakeNewBotController` bails on a stripped world-getter, so the REAL `AController::Possess` is
skipped), and there are two independent routes past it — one built and unflown (`botai`), one designed
by the game itself and not yet built (`PremadeBotController`). **Fly `botai` and read one number.**
