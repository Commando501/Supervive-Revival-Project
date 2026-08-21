# NEXT SESSION (S138) — a Loki bot controller exists. Now make it a BOT.

**One line: `ALokiBotController` now possesses a hero pawn and carries a real `BP_LokiPlayerState_C`
on both sides. The next arm is `SpawnBot(..., PremadeBotController = ours, ...)`, which
[M] short-circuits FK-22's stripped getter entirely.**

Written 2026-08-21 at the end of S137. **Read `docs/s137-playerstate-and-lokibot-settled.md` first —
its CORRECTIONS block GOVERNS.**

⚠⚠ **BEFORE ANYTHING ELSE: S137's OWN HANDOFF WAS WRONG, AND SO MIGHT THIS ONE BE.**
`docs/next-session-prompt-s137.md` §1.2 proposed a `bWantsPlayerState` CDO poke as *"one aligned CDO
write … the same risk class as S130's `bCanEverReplicate`"*. **It is MEASURED REFUTED.** It was
written with confidence, it had a clean-looking offline derivation behind it, and it does not work.
The reason it does not work was found by an offline lane *before* the flight and confirmed *by* the
flight. **Treat everything below as a hypothesis with an address attached, not a plan.**

**STATE AT HANDOFF:** no client running — the last one was killed by the protector (`0x0000DEAD`,
FK-32) ~8 s after the final capture, on the **6th** manual-map into that process. `ags` may still be
up with a `MatchID` armed in memory; **if so, a fast arm on relaunch is NOT a fresh reproduction.**
Nothing was lost — every result is on disk (§6).

---

## 0. WHAT S137 ESTABLISHED

| result | grade |
|---|---|
| **ARM A — the S137 handoff's `bWantsPlayerState` CDO poke — DOES NOT WORK.** Poke lands (readback OK, dword delta exactly `0x20`); the spawned instance still reads the bit CLEAR | **[M]**, within-run control |
| MECHANISM, predicted offline *before* the flight: `FObjectInitializer::InitProperties` branches into **PostConstructLink** only, and `UStruct::Link` never puts a property **owned by a native class** into that chain. No bulk CDO→instance memcpy exists on the allocation path | **[M]** |
| ⇒ **THE REUSABLE RULE: a CDO poke reaches a new instance ONLY IF THE CONSUMER READS THE CDO DIRECTLY** | **[M]** |
| **ARM B** — `AController::InitPlayerState` (`0x36DEE20`) called directly through the vtable ⇒ `controller+0x3C0` = a real `BP_LokiPlayerState_C`. [M] it does **not** test `bWantsPlayerState` | **[M]**, 3× |
| **ARM C** — `APawn::SetPlayerState` (`0x3BBD9F0`, NON-VIRTUAL, prologue-signature-validated) ⇒ `pawn+0x3D8` == the same PlayerState | **[M]**, 2× |
| **ARM D** — poke `Default__Pawn+0x3D0` → `LokiBotController` UClass, then spawn ⇒ **an `ALokiBotController` possesses a hero pawn.** Full A-B-A (baseline `AIController` → treatment → restore → reversal `AIController`), `pokeOK=1 restoreOK=1`, 6/6 predictions | **[M]**, 2 instruments |
| `obj_by_chain =LokiBotController` → `found 1 … obj=0x17443C931A0` — **the same pointer the shim reported** | **[M]** |
| **`OnPossess 0x5565470` and `Tick 0x556E9F0` went DARK → LIT** (0/4096 → 3782 and 3509) — the S118 steerable-decryption method. `OnUnPossess` still dark (correct negative); 3 lit controls unchanged | **[M]** |
| **NetMode = `NM_Standalone`** — from the client's own `LogWorldPartition` line, present in EVERY log this project ever took; corroborated from the bytes (`0x338E750` defaults to `xor eax,eax` = 0) | **[M]** |
| `=BotController` is a **degenerate query** — reads 0 with a live bot in the process, and has **no positive control** (`CDOs matched and EXCLUDED: 0`) | **[M]** |
| `62 vs 69` AController fold slots is **not a discrepancy** — 4-fold set vs 5-fold set (42+17+3 vs +7) | **[M]** |
| **FLIGHT 4: ARM D reproduced in a FRESH client** (different process/ASLR), same A-B-A | **[M]** |
| **The `LokiBotController` builds its own `BehaviorTreeComponent` (`NodeInstances=21`) and `BlackboardComponent` (real `BlackboardData`, `KeyInstances=15`)** while both plain `AIController`s spawned either side of it have **NULL** for both — a two-sided within-run control. We passed `BehaviorTree = null`. **Its AI machinery is not gutted.** | **[M]** |
| Whether the bot **ACTS / moves** | **NOT MEASURED** — see §1 |

**STATE OF THE CLIENT AT HANDOFF, honestly:** both S137 launches ended in FK-32 (`0x0000DEAD`)
protector kills, at the **6th** manual-map / 1144 s and the **4th** / 334 s. Across the three
recorded `0xDEAD` kills (S132's was the 7th) there is **no dose-response**, so do not plan around
"injection budget" — but do expect a multi-injection tutorial sitting to end this way, and **capture
every result as you go rather than at the end.** Both S137 sittings did, and lost nothing.

**Arms** (RAW digests): `botps` `445fb5ce5b902bc3` · `botps-link` `e287d7ae8c5f4814` ·
`lokibot` `3119d75ae2ca1859` · `botps-readonly` `f860411a6ef7cb49` · `botps-arma` `623252907a68fd08` ·
`botps-armb` `c574c8ce5c3ccf95`. All DISTINCT (`text_digest.py --dupes` over the archive: **0 duplicate groups**),
all archived in `dumps/s137-arms/`.
⚠ **THE FLOWN `lokibot` IS `3119d75ae2ca1859`.** After the flight, two defects in the arm were fixed
(see §4) and it rebuilt to **`f8ab43b040ea8a12`**, archived as `tutorial_launch_lokibot_v2_defectfix.dll`
and **never flown**. Fly the v2 — but do not cite its digest as the one that produced the S137 result.
Regression gate **`botai` `5e47c13cf7f0a158` UNCHANGED** across all three source patches.

---

## 1. ★ THE NEXT ARM — `SpawnBot` WITH A PREMADE CONTROLLER

Everything this needs now exists:
1. **`ALokiBotController` is intact and instantiable** — registered, non-abstract, `sizeof 0x6A8`,
   ctor `0x554B430` REAL 577 B, and its entire four-deep construction chain has **zero folds and
   zero dark callees** across 26 callees. Its UClass (`0x173B8595100`) and CDO (`0x173B3D21B00`)
   were read **live in the tutorial world** — which answers a lane's open question.
2. **We can make one, possess a hero with it, and give it a PlayerState** (ARM D + ARM B + ARM C).
3. **[M] `SpawnBot`'s `AController* PremadeBotController` parameter SHORT-CIRCUITS EARLIER than the
   repo recorded, and `MakeNewBotController` (`0x5563660`, blocked by the stripped getter at
   `0x55636BB → 0xF7EB50`) IS NEVER CALLED AT ALL.** The Blueprint route cannot pass it —
   `Comp_BP_BotSpawner_C::SpawnClassBotAtLoc` hardcodes `EX_NoObject` there — but `SpawnBot` is
   itself reflected, so the S55 direct thunk reaches it.
4. **[M] `SpawnBot` consumes the premade controller's PlayerState from `+0x3C0`** — exactly the
   field ARM B fills.

★ **THAT WORK IS DONE — the follow-up landed (64 CONFIRMED / 25 DOWNGRADE / 10 REFUTED). Read
`docs/s137-playerstate-and-lokibot-settled.md` §7c before re-deriving any of it.** The build-ready
essentials:

**Call the RAW IMPL, not the exec thunk.** `0x556D910`, 7 native args:
`(comp, &heroClassCell, locXYZ, teamIndex, difficulty, premadeController, &botName)`, with
`difficulty`/`premade`/`&botName` at `[rsp+0x20]`/`[rsp+0x28]`/`[rsp+0x30]`.
**It RETURNS the spawned `ALokiHeroCharacter*` directly** — so the `CreatedBot` out-param trap below
does not apply to a direct call (it still applies to the BP wrapper).

⚠⚠ **`BotName` MUST be a ZEROED 16-byte FString `{nullptr,0,0}`.** SpawnBot fills it and **FREES it
with the game's own `FMemory::Free` (`0xFF9310`) on BOTH exit paths** — a shim-CRT-allocated buffer
there is heap corruption.

⚠⚠ **IT IS NOT CALL-ONLY.** The lane claimed CALL-ONLY and **its own refuter REFUTED that**: an
exhaustive operand scan finds **7 non-stack writes across FOUR objects**. Budget it as a
state-mutating call and pre-register a restore where you can.

★ **The premade short-circuit is confirmed from the bytes:** `0x556DA4F mov rax,[rsp+0x70]` /
`0x556DAA1 test rax,rax` / `0x556DAA4 jne 0x556DB32` skips `0x556DAAA..0x556DB30`, whose only memory
writes are three stores to SpawnBot's own stack frame ⇒ **`MakeNewBotController` is never called.**

★ **Counts, corrected by the refuter** (the lane said 39/25/22): **43 call instructions = 39 direct +
4 indirect, 28 distinct direct targets, 25 REAL / 2 FOLD / 1 DARK.** The two folds are
`ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam` (`0x556DE53 → 0xF7EB60`); the dark
one is `0x5556D50` at `0x556DEA2`, whose page going non-zero is a **free binary receipt** that
execution got that far.

★★ **AND A SECOND, CHEAPER ARM FELL OUT OF `OnPossess`:** it broadcasts a multicast delegate at
`ALokiPlayerState+0x5B0` with the hero **only if PlayerState is non-null**. S137 installs the
PlayerState (ARM B) *after* possession, so that branch has never run. **Give the controller a
PlayerState BEFORE it possesses and it lights up.**

⚠ **PRE-REGISTER THE READOUT.** `SpawnBot`'s `CreatedBot` out-param is filled by a
`GetPlayerStatesOnTeam` scan requiring `IsBotControlled ∧ ObjectIsA(HeroClassToSpawn)` **at that
instant**, so **a NULL `CreatedBot` does NOT mean the spawn failed.** The verdict must come from a
`GUObjectArray` census delta.

### ★ DO THIS FIRST: **DOES THE BOT MOVE?**
S137 flight 4 measured, with a two-sided within-run control, that the `LokiBotController` builds its
own **`BehaviorTreeComponent` (`NodeInstances = 21`)** and **`BlackboardComponent`
(`BlackboardAsset` = a real `BlackboardData`, `KeyInstances = 15`)**, cross-wired to itself, while
the two plain `AIController`s spawned milliseconds either side have **NULL** for both.
**Its AI machinery is not gutted.** What was NOT measured is whether it ACTS.

**The read is trivial and read-only: sample the bot pawn's `RootComponent->RelativeLocation` twice,
~8 s apart, with the two plain-`AIController` pawns from the same A-B-A as within-run controls.**
S137 attempted exactly this and got `UNREADABLE` for a purely instrumental reason — the client had
already been FK-32'd and **the throwaway probe had no RUN-IS-VOID check**, so it reported an
artifact instead of refusing. ⚠ **Put the liveness check in first**; `playerstate_readout.py` has
one and is the model.
⚠ `LogBehaviorTree` / `LogAIModule` occur **0** times **with no positive control** — that zero is
UNINTERPRETABLE, not evidence. Pin the category (FK-11: user `Engine.ini` `[Core.Log]`) if you want
a log-side view.
⚠ A controller that exists but does not act is a BEHAVIOUR result, not a spawn failure — do not let
it re-open the settled part.

★ **AND THE OFFLINE READ NOW TELLS YOU EXACTLY WHAT TO WATCH.** `ALokiBotController::Tick`
(`0x556E9F0`, 1,261 B, zero folds) has **one motion driver and it is a RANDOM WANDER** — no
targeting, no ability use, no combat. It gates on `Blackboard != NULL` (**satisfied**, §7b) **AND**
on a blackboard bool key at `.data 0xA0348F0`, the `bCharacterControllable`-family key written by
`UpdateCharacterControllable` (`0x5570B80`). **That bool is the remaining unknown**, so if the pawn
does not move, read that key rather than concluding the bot is inert.
⚠ Also read `pawn+0x658` (`RandomMoveDirection`, the cached direction the tick passes to the movement
component) — a non-zero value there with a stationary pawn localises the failure past the tick.

### Other cheap things
- **Pass a real `BehaviorTree`** to `SpawnAIFromClass` (the `BT@0x10` params slot, deliberately left
  null in S137) and compare against the tree the controller builds for itself from `Cfg->[0x240]`.
- **`OnPossess` reads NO difficulty, team index or hero class** — everything bot-specific comes from
  one process-wide config CDO reached via `UWorld->[0x2D0]` / `ULokiGameInstance->[0x1D8]->CDO->[0x38]->CDO`.
  Reading that CDO is free and offline-ish, and it names the BT asset (`[0x240]`), the granted
  ability classes (`[0x2C0]`/`[0x2B0]`/`[0x2B8]`) and the applied GameplayEffects (`[0x320]`).

### ⚠ ONE LESSON FROM S137'S OWN LANES, WORTH MORE THAN ANY OF THE ADDRESSES
Two S137 lanes contradicted each other on whether `OnPossess` starts a behaviour tree. The losing one
searched for a **direct** call to `0x3316AF0` and for **direct** writes to `+0x498`/`+0x4B0` inside
`OnPossess`. The real call is **indirect through vtable disp `0x940`**, and the components are
created in the **callee** — so that scan was blind by construction and produced a confident
`NULL Blackboard` verdict. It was caught by (a) the adversarial pass and (b) **the live measurement**.
⇒ **When an offline scan says a thing is ABSENT, ask whether the scan could have seen it if it were
present — and prefer a live read when one is cheap.** `0x3316AF0` is also a **4-way ICF-folded
dispatch shim**, so naming disp `0x940` from it is the folded-RVA error the register warns about;
the sound naming is the callee's own `BTComponent` literal plus the live object's name.

---

## 2. FLIGHT PROCEDURE (unchanged, 4× reproduced)

```powershell
# ELEVATED PowerShell. Steam must already be running.
cd "G:\git\Supervive Revival Project"
$env:AGS_ARM_QUEUE='arm'; $env:AGS_ARM_QUEUE_DELAY='8s'; $env:AGS_ARM_QUEUE_QUEUES='bots'
.\configs\launch-redirect.ps1 -NoHook
```
Settle gate: uptime ≥ 125 s **AND** `TryUIReady SUCCESS` ≥ 1 **AND** ≥1 `LobbyV2_Persistent` map load.
Then arm (the persisted `targetQueueId` is already `bots`):
```bash
curl -X POST -A "s138-arm-NOT-THE-GAME" http://127.0.0.1:8080/party/parties/party-9b9d2c887e2524f918e383a895f2f1c2/joinQueue
```
Confirm `MatchID` non-empty at `/core-game/players/9b9d…` and a `GET /core-game/matches/` in
`docs\capture.log`, then:
```powershell
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_lokibot.dll -Label s138 -AllowStale
```
★ **Stage once with `-SkipProbe`, then inject by hand** (`tools\inject\inject.exe mmap <pid> <dll>`) —
that decouples the slow staging from the injection decision and lets you re-inject repeatedly into
the same staged world. S137 did three probe injections into one client that way.
⚠ **Back up `docs\capture.log` before restarting `ags`** — `launch-redirect.ps1` kills and restarts it.
⚠ **`launch-redirect.ps1` returns promptly** (the shipping exe detaches); it does NOT block.

---

## 3. ⚠⚠ TRAPS — the ones S137 paid for, on top of S136's list

1. ★★★★★ **A CDO POKE IS NOT ONE TECHNIQUE, IT IS TWO.** If the consumer reads the CDO *directly*
   (S130 `bCanEverReplicate`; S137 ARM D `AIControllerClass`) it works. If it relies on
   `InitProperties` copying CDO→instance, **it does not, for any property owned by a native class.**
   The S137 handoff conflated them and proposed the broken one. **Ask WHO READS THE CDO.**
2. ★★★★★ **AN EXACT-NAME CENSUS CAN HAVE NO POSITIVE CONTROL AND STILL PRINT A CONFIDENT 0.**
   `obj_by_chain =BotController` returns `found 0` / `CDOs matched and EXCLUDED: 0` **with a live
   `LokiBotController` in the process.** Always check the tool reported a matching CDO (or some
   other known positive) before believing a 0.
3. ⚠ **WAIT FOR `[BS] done`, THEN READ `called=`.** Still true (S136's flight 1 was a silent no-op).
4. ⚠ **Do NOT `tee` over an evidence file.** S137 destroyed one that way, re-running a probe after
   the client had died.
5. ⚠ **Quote the right delta.** `mergedumps` printed "44 pages" for what it took from donors while
   the coverage gain over `merged12` was **+28**. Different quantities.
6. ⚠ **Quote the fold set with any fold-slot count** (62 four-fold vs 69 five-fold).
7. ⚠ **`strxref.py func` on a previously-DARK function reports a WRONG entry point** —
   `pdataunion.py` drops size-1 placeholder rows by construction, so it is blind on exactly those
   pages. It does this for `0x5565470` today. Establish extents by disassembly.
8. ⚠ **In DUMPED images the ASCII `KERNEL32` byte-scan control returns 0** — use UTF-16 `KERNEL32`
   (2 hits) or ASCII `kernel32` (2 hits). In the shim DLLs ASCII `KERNEL32` works fine. Different
   artifacts, different controls.
9. ⚠ **`TerminateProcess`/`ExitProcess` are in every shim's import table** (0 in the source).
10. ⚠ **CRLF.** `CLAUDE.md` and `tutorial_launch.cpp` are all-CRLF; patch with explicit `\r\n` and
    verify the anchor count is exactly 1. Check for `\\r\\n` over-escapes afterwards.
11. ⚠ **Archive every arm before rebuilding** — `build/` is gitignored.

---

## 4. STANDING CLEANUP (offline, no launch)

- **`RM_BOTSPAWN` still violates the codebase pattern**: resolve + before-census belong on the
  WORKER thread before `FsArm()`, only the CALL on the game thread, after-census in the final report
  after `FsDisarm()`. It holds the game thread ~15–20 s per run. `RM_POOLSPAWN` / `RM_DROPPOD` /
  `RM_RIDEABLE` / `RM_DISMOUNT` all do it correctly. **Largest remaining hygiene item; costs no launch.**
- **A defect in S137's own arm:** `BsPsDumpPair` is called for the CONTROL spawn *before*
  `BsPsResolveAiClass` has resolved the bit, so the control's L2 line prints
  `UNREADABLE [byte@+0xFFFFFFFF]`. Harmless (the value is recoverable from the ARM-B re-read) but
  it should resolve the bit first.
- **The `BsPsPrecondition` World latch is unreliable** — it takes the FIRST object whose class leaf
  name is exactly `World`, and read `AuthorityGameMode = 0` / `GameState = 0` on a world named
  `LVL_Tutorial` **while `InitPlayerState` was concurrently succeeding** (there are 345 objects whose
  class name contains `World`). It flagged itself correctly ("a null below is UNINTERPRETABLE") so it
  cost nothing, but it is not a usable precondition read as written.
- `POST /core-game/players/{id}/disassociate/{...}` (fn `0x57A0EE0`) still unserved — serving it
  makes the arm-a-match loop repeatable instead of one-shot.
- `botspawn_readonly` still reproduces under NEITHER digest recipe — re-record before using it as a
  control.

---

## 5. THE ONE-PARAGRAPH STATE OF CO-OP VS. AI

The tile, the click, the queue, the timer and the cancel all work; the queue answers; a staged
tutorial world is reachable off the queue-armed MatchID with `forceTutorialMatch = false`. Bot
**pawns** spawn. As of S136 one is **possessed** by a real controller. As of S137 that controller can
be an **`ALokiBotController`** — the first `BotController`-derived object this project has ever
produced — and it carries a real `BP_LokiPlayerState_C` on both the controller and the pawn. What is
still missing is everything the *Loki* bot pipeline does with that: `ServerSetHeroClass` and
`SetPlayerTeam` are stripped folds, nothing has gone through `SpawnBot` yet, and no bot has been
shown to ACT (no BehaviorTree was ever supplied, and the bot's own Brain/Blackboard/Perception were
never read). The route past all of that is now specified and its every precondition is measured: pass
our controller to `SpawnBot` as `PremadeBotController`, which skips FK-22's stripped getter outright.

---

## 6. ARTIFACTS S137 LEFT ON DISK

| path | what |
|---|---|
| `docs/s137-playerstate-and-lokibot-settled.md` | the settled doc — **its CORRECTIONS block governs** |
| `docs/s137-PREREGISTERED.txt` / `docs/s137-ARMD-PREREGISTERED.txt` | predictions, written before injection |
| `docs/s137-marker-flight1-botps.txt` | ARM A refuted / ARM B worked |
| `docs/s137-marker-flight2-botps-link.txt` | ARM C worked |
| `docs/s137-marker-flight3-lokibot.txt` | ARM D — the A-B-A |
| `docs/s137-external-BASELINE.txt` + `-AFTER-flight1/2/3.txt` | external confirmations (⚠ flight3 is a labelled reconstruction) |
| `dumps/merged13.dump.exe` | **new canonical** — 16,800/30,281 pages (55.48 %), strict superset of `merged12` |
| `dumps/s137-lokibot/` | the capture that decrypted the Loki bot code |
| `dumps/s137-arms/` | all six arms archived |
| `tools/re/playerstate_readout.py` | the external instrument (new; carries its own positive control) |
| `docs/capture.log.pre-s137` | capture.log backed up before the `ags` restart |

⚠ **Nothing is committed.** The working tree carries the S137 source patches
(`tools/sigbypass-mod/tutorial_launch.cpp`, `build.ps1`, `tools/strxref/strxref.py`, `CLAUDE.md`)
plus all the docs above.
