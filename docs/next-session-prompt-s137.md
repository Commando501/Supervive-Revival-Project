# NEXT SESSION (S137) — an AI-controlled pawn exists. The next blocker is ONE CDO BIT.

**One line: `SpawnAIFromClass` produces a generic engine `AAIController` that possesses a hero pawn,
and the reason it has no `PlayerState` is now measured end-to-end — stock UE clears
`bWantsPlayerState`, so the fix is one aligned CDO write, not a stripped stub.**

⚠ **It is NOT a Loki bot.** Read §1.3 before promising one.

Written 2026-08-21 at the end of S136. **Read `docs/s136-ai-controller-settled.md` first** — its
CORRECTIONS block governs, and its §2/§3 are the reason S136 did not publish a false null.

**STATE AT HANDOFF:** no client is running (the operator right-clicked in the staged world and it
died — user input, and the SECOND recorded instance of that; artifact-less, 0 `Fatal`, 0 crashpad, so
the artifacts alone cannot separate it from FK-32). `ags` may still be up with `AGS_ARM_QUEUE=arm`
and a MatchID armed in memory — **if so, a fast arm on relaunch is NOT a fresh reproduction.**
Everything S136 measured is on disk (§7); nothing was lost.

---

## 0. WHAT S136 ESTABLISHED (do not re-derive)

| result | grade |
|---|---|
| `SpawnAIFromClass` → `APawn::SpawnDefaultController` (slot 280) creates a **GENERIC ENGINE `AAIController`** that **possesses** a freshly-spawned `BP_HERO_Ronin_C` — ⚠ **NOT a Loki bot**: `AIControllerClass` is the engine default on the player hero too, and `obj_by_chain BotController` = **0 LIVE** | **[M]**, reproduced 2× in one client |
| The possession handshake is **bidirectional** — controller `Pawn`/`Character`/`Instigator` == the exact returned pointer; pawn `Controller`/`PreviousController`/`Owner` == that controller | **[M]** |
| ⇒ **`AController::Possess 0x36E2B60` RAN** (S135 measured it as skipped on the component route) | **[M]** |
| **P4:** page `0x3BBF000` **0/4096** non-zero in `merged11` (union of EVERY image; 53 of 55 images dark, incl. `s135-botspawn`) → **3714/4096** after | **[M]** for the page; **[M, strong]** for "it executed" only WITH the `call [rax+0x8c0]` call-site disasm |
| The pawns are physically real — **bot 2 rests ON bot 1, ΔZ = 176.1008 = 2 × 88.0504 capsule half-heights** (⚠ `Z=90.15` alone is floor flatness, NOT a fingerprint) | **[M]** |
| The shipped `botai` arm was **statically incapable of calling** (clang DCE'd `BsCallAI`) | **[M]** |
| The arm's census predicate was **blind to `AIController`** — S135's own deferred blind spot, now settled | **[M]** |
| **`AController::InitPlayerState = 0x36DEE20`, vtable slot 273, REAL, 778 B, 14/14 callees REAL, ZERO folds** — it names itself in its own UE_LOG | **[M]**, triple-confirmed by 3 parties via 3 routes |
| **The PlayerState is NULL because stock UE clears `bWantsPlayerState` (bit `0x20` @ `+0x488`)** — NOT a Loki strip. Cleared in `AAIController` and `ALokiBotController` ctors | **[M]** |
| A **second** wall past it: `SpawnBot`'s protected block calls two stripped folds ([I, strong] `ServerSetHeroClass` / `SetPlayerTeam`) | **[M]** that both sites are folds |
| **UE's own `GetNetMode() != NM_Client`** — a different fact from Loki's hardcoded `LokiIsClient`/`LokiIsServer` stubs | **[M]**; *which* mode is **NOT** measured |
| `dumps/s133-phase2-{BASE,AFTER}` are mis-named (content confirms the swap) but **no published S133 conclusion is wrong** | **[M]** |
| **Two DEGENERATE control arms found**: `play ≡ play_nopimutex ≡ play_strictroot` — both knobs inert (S112 / S123) | **[M]**, each with a passing positive control |
| **TWO** `.text` digest recipes exist on disk (RAW at `fk24-stage.ps1:77` + `fk7-ab-run.ps1:94`; VIRTUALSIZE at `method-rules.md:213`). The S135 bot gates came from VIRTUALSIZE. ⚠ S136 first published "they appear nowhere" — **FALSE, retracted** | **[M]** |

**Arms.** `botai` = **`5e47c13cf7f0a158`** (RAW recipe; guard + census + verdict-string fixed).
⚠ See §5 — there are two recipes, and `botspawn_readonly` matches **neither** today.

---

## 1. ★ START HERE — THE BLOCKER IS **ONE CDO BIT**, AND IT IS ALREADY MEASURED

S136 answered its own open question offline. **Do not re-derive any of §1.** Full evidence:
`docs/s136-ai-controller-settled.md` §7.

### 1.1 The chain, end to end

```
SpawnAIFromClass 0x4631C50
  -> UWorld::SpawnActor 0x39C5280                       ; the PAWN
  -> APawn::SpawnDefaultController (slot 280) 0x3BBF3C0 ; the CONTROLLER  [S136: DARK -> DECRYPTED]
       bails if Controller != NULL / GetNetMode()==NM_Client / AIControllerClass == NULL
  -> AController::Possess 0x36E2B60                     ; possession  [RAN, bidirectional handshake]

AAIController::PostInitializeComponents 0x45D6D10   (REAL)
  0x45D6D1E  f6 83 88 04 00 00 20   test byte [rbx+0x488], 0x20   ; bWantsPlayerState
  0x45D6D25  74 25                  je  0x45D6D4C                 ; <== THE BLOCKER
  0x45D6D46  call qword [rax+0x888] ; AController::InitPlayerState (slot 273) 0x36DEE20  [REAL, 0 folds]
```

**[M] `AController::InitPlayerState = 0x36DEE20`, slot 273, REAL, 778 B, all 14 callees REAL, ZERO
folds.** Triple-confirmed by three parties via three routes — it names itself in its own UE_LOG
(`.rdata 0x8018A50`, `Controller.cpp:0x268`, exactly one LEA site at `0x36DEF82`), it reads
`UWorld::AuthorityGameMode` at FK-22's `+0x250` and `PlayerStateClass` at `AGameModeBase+0x3E0`, it
calls `UWorld::SpawnActor`, and it writes `[controller+0x3C0]`.

**[M] `bWantsPlayerState` = bit `0x20` at `+0x488`**, from its own UHT `SetBitFunc`:
`0x45CFA10 = 83 89 88 04 00 00 20 c3` (`or dword [rcx+0x488],0x20; ret`), with the adjacent bit
`0x45CFA20` writing `0x40` at the same offset as a passing control.
**And it is explicitly CLEARED in the ctors:** `AAIController` `0x45D19AD and ecx,~0x20`;
`ALokiBotController` `0x554B5A9 and dword [rdi+0x488],~0x20`; `ALokiAIController` never touches it.

⇒ **NO STRIPPED STUB IS INVOLVED. The PlayerState is NULL because stock UE defaults
`bWantsPlayerState = false` on AI controllers.**

### 1.2 ★ THE ARM — one aligned CDO write, the S130 pattern

**Poke `CDO(<the pawn's AIControllerClass>) + 0x488 |= 0x20` before spawning, then run the existing
`botai` arm unchanged.**

Ordering is why this works: `SpawnActor` runs `PostInitializeComponents` (→ `InitPlayerState`)
**before** `SpawnDefaultController` calls `Possess`, and `APawn::PossessedBy`/`SetPawn`
(`APawn::SetPlayerState 0x3BBD9F0`, REAL) then copies `controller+0x3C0` → `pawn+0x3D8`.

Risk class: **one aligned CDO byte/dword, readback-verifiable, class-default scope** — identical to
S130's `bCanEverReplicate` fix, this project's safest measured write class.
⚠ It is a CLASS DEFAULT — it affects every controller of that class for the process lifetime.
⚠⚠ **Read `pawn CDO + 0x3D0` (`AIControllerClass`) LIVE first** to learn *which* controller CDO to
poke. `APawn::APawn 0x3B809D0` zeroes `+0x3D0` then re-reads it **from the `APawn` CDO chain**
(`0x3B80C0D` → `call 0x3BA4CE0` → `[rax+0x178]` → `[+0x3D0]`) — **not** a hard-coded
`AAIController::StaticClass()`. Resolving it offline was attempted and failed; do it live.
⚠ S136 measured `AIControllerClass` = the engine default `AIController` on the spawned pawns **and on
the player hero**, so that is the likely CDO — but confirm, do not assume.

**Alternative, no CDO write:** after `SpawnAIFromClass` returns, take `pawn->Controller` (`pawn+0x400`)
and call `0x36DEE20` directly as `void __fastcall(AController*)`.
⚠ **This is NOT "CALL-ONLY" in the read-only sense** — `InitPlayerState` performs a `SpawnActor`
(`RF_Transient`) and writes `controller+0x3C0`. File it accordingly.

**Pre-register the readout:** `controller+0x3C0` NULL → non-null, and `pawn+0x3D8` NULL → the same
pointer. Both are read-only RPM, both were measured NULL in S136, so the baseline is established.

### 1.3 ⚠⚠ A SECOND WALL SITS PAST IT — both are real and SEQUENTIAL

Do not expect a full Loki bot from §1.2 alone. Everything `SpawnBot`'s PlayerState gate protects is
a `"bot%d"` name, one real virtual, and **two stripped folds**:
```
0x556DE43  call 0x0F7EC20   ; VOID fold   -- [I, strong] ALokiPlayerState::ServerSetHeroClass
0x556DE53  call 0x0F7EB60   ; FALSE fold  -- [I, strong] SetPlayerTeam
```
Independently, the reflection table shows both those impls stripped (exec thunks `0x5438720` /
`0x538AA70` tail-calling the same folds), with matching argument shapes.
⚠ **[I, strong], NOT [M], on the naming** — `0x0F7EC20` has 165,789 stored-pointer occurrences,
`0x0F7EB60` has 106,924. A folded RVA names nothing. What is **[M]** is that both call sites are folds.

⇒ **A PlayerState buys REACHABILITY of that branch, not hero-class or team assignment.** The pawn
already spawns with the right hero class (S135); what is missing is the *PlayerState-side* record —
which is exactly what `CreatedBot`'s `GetPlayerStatesOnTeam` scan reads.

### 1.4 ⛔ THERE IS NO "THIRD GATE" — refuted in review, do not pre-register one

An offline lane read `[PS+0x8C0]` as the PlayerName FString and warned that
`0x556DD89 cmp dword [rdi+0x8c8],1 / jg` would skip the block after `InitPlayerState` names the
PlayerState. **Wrong.** `+0x8C0` is `ALokiPlayerState::PlatformPlayerID` (UHT rec `0x8A252D8`;
`binds_members.csv:44578`). The engine name is `APlayerState::PlayerNamePrivate @ +0x450`, and the
virtual `InitPlayerState` calls (slot 257 `0x3CA9D10`, not overridden) ends `lea rcx,[rbx+0x450]`.
⇒ `[PS+0x8C8]` stays 0, the `jg` falls through, **the block RUNS**. Do NOT zero `[PS+0x8C8]` — that
would clobber the `Num` of a live replicated FString while leaving its `Data` pointer.

### 1.5 The other half — does the bot ACT? (separate question, still open)

`BrainComponent` / `Blackboard` / `PerceptionComponent` are NULL **by design** (the arm passes
`BehaviorTree = null`); both pawns read `vel = (0,0,0)`. `PathFollowingComponent` **is live**.
Pass a real `BehaviorTree` (`BT@0x10` in the params blob), or drive
`UAIBlueprintHelperLibrary::SimpleMoveToLocation`, and read the pawn location twice.
⚠ **A controller that exists but does not act is a BEHAVIOUR result, not a spawn failure.**
⚠ `LogAI`/`PathFollowing` occur **0** times in the client log **with no positive control**, so that
silence is UNINTERPRETABLE. Pin the category first (FK-11: user `Engine.ini` `[Core.Log]`;
`-LogCmds` does not parse).

---

## 2. THE FLIGHT PROCEDURE (unchanged and now 4× reproduced)

```powershell
# ELEVATED PowerShell. Steam must already be running.
cd "G:\git\Supervive Revival Project"
$env:AGS_ARM_QUEUE        = 'arm'
$env:AGS_ARM_QUEUE_DELAY  = '8s'
$env:AGS_ARM_QUEUE_QUEUES = 'bots'
.\configs\launch-redirect.ps1 -NoHook
```

Settle gate: uptime ≥ 118 s **AND** `TryUIReady SUCCESS` ≥ 1 **AND** one
`Load map complete .*LobbyV2_Persistent`. Then arm (the persisted `targetQueueId` is already `bots`):

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8080/party/parties/party-9b9d2c887e2524f918e383a895f2f1c2/joinQueue" -Method POST -UseBasicParsing -UserAgent "s137-arm-NOT-THE-GAME" | Out-Null
```

Confirm before staging: `MatchID` non-empty at `/core-game/players/9b9d…` **and** ≥1
`GET /core-game/matches/` in `docs\capture.log`. Then:

```powershell
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_botai.dll -Label s137 -AllowStale
```

★ **You can re-inject into the SAME client repeatedly** — S136 did three probe injections into one
process with 0 `Fatal` and 0 crashpad, and the world stays staged. **Do not relaunch to iterate.**
Use `tools\inject\inject.exe mmap <pid> <dll>` directly for injections after the first.

⚠ Back up `docs\capture.log` before restarting `ags` (S136 backed up 36.9 MB to
`docs/capture.log.pre-s136-botai`).

---

## 3. ⚠⚠ TRAPS S136 PAID FOR — DO NOT RE-PAY THEM

1. ★★★★★ **WAIT FOR `[BS] done`, AND THEN READ `called=`.** Flight 1's census read a clean
   `0/0/0` with a confident VERDICT line. It was a **no-op**. `called=0` is the only field that
   exposed it. Reading the census alone would have published *"the controller is unreachable by any
   spawn entry point"* — false.
2. ★★★★★ **A CONFIDENT FAILURE STRING IS AN INSTRUMENT.** `"(KBSARMS gated it off)"` was hardcoded
   on a generic path and named a knob that was **correct** (`0x0F`, bit 2 set). It sent S136 hunting
   the wrong thing. **A message that asserts a cause it did not test is worse than no message.**
3. ★★★★ **THE BINARY'S STRING TABLE IS A COMPILE-TIME COVERAGE INSTRUMENT.** "Is this branch even in
   the build?" is one offline byte scan, with the sibling branch's literals as the positive control.
   That is what turned "the call did not happen" into "the call was never compiled."
4. ⚠⚠ **`strings` IS NOT INSTALLED HERE.** It returns silence for every token in every file. S136's
   first census read 0 for `SpawnClassBotAtLoc` in `botspawn` — which provably calls it — and was
   caught only because `KERNEL32` also read 0. **Python byte scan + positive control.**
5. ⚠⚠ **AN EDIT THAT DOES NOT MOVE `.text` IS AMBIGUOUS** (cached build vs semantic no-op). Insert a
   deliberately observable marker string to separate them.
6. ⚠⚠ **CRLF.** `CLAUDE.md` and `tutorial_launch.cpp` are all-CRLF. A patch script anchored on `\n`
   silently matches nothing; a heredoc mangled `\r\n` into a real newline and broke the build.
   Anchor with CRLF and verify the anchor count is exactly 1.
7. ⚠ **Grade three-state: fold / REAL / DARK.** And never sample a byte offset across unrelated
   vtables (`+0x858` is a different method in every hierarchy).
8. ⚠ **`InternalIndex` adjacency is NOT a creation-order signal** — `GUObjectArray` reuses freed
   slots (S110). The S136 controller sits at 177838 while its pawn sits at 80214.
9. ⚠ The stager's `-N-probe-` marker copy is taken **at injection** and holds only the header. The
   full ladder is in the live `docs/tutorial-launch-marker.txt` — snapshot that, and remember every
   injection truncates it (FK-25).

---

## 4. STANDING CLEANUP (offline, no launch)

- **`RM_BOTSPAWN` still violates the codebase pattern**: resolve + before-census belong on the
  WORKER thread before `FsArm()`, only the CALL on the game thread, after-census in `*FinalReport()`
  after `FsDisarm()` + a settle `Sleep`. It holds the game thread ~15 s per run.
  `RM_POOLSPAWN` / `RM_DROPPOD` / `RM_RIDEABLE` / `RM_DISMOUNT` all do it correctly and say so.
  **This is the largest remaining code-hygiene item and it costs no launch.**
- `POST /core-game/players/{id}/disassociate/{...}` (fn `0x57A0EE0`, 502 B, POST) is still unserved.
  Serving it turns the arm-a-match loop from one-shot into repeatable (today the only clear is
  `leaveQueue` → `cancelArm`, or restarting `ags`).
- ⚠ **`botspawn_readonly` reproduces under NEITHER digest recipe** — that artifact has changed since
  its gate was recorded. Re-record it before using it as a control.
- ✅ DONE in S136: `strxref.py DEFAULT_DUMP` → `merged12` (after a verified strict-superset check,
  0 pages lost / +17 gained); the stale `"A BOT SPAWNED / BotController +N / STRUCTURAL ZERO"`
  verdict string; two `\\r\\n` over-escapes; the `g_bsFn`-only DCE comment.

---

## 5. ARTIFACT DIGESTS — THERE ARE **TWO** RECIPES, AND BOTH ARE IN USE

| | definition | on disk |
|---|---|---|
| **RAW** | `sha256(.text[PointerToRawData, +SizeOfRawData))[:16]` | `configs/fk24-stage.ps1:77 Get-TextHash` (prints only inside a stale-shim abort) and **`configs/fk7-ab-run.ps1:94`, which EMITS it at :131 into the A/B CSV column `probe_text_sha`** |
| **VIRTUALSIZE** | `sha256(.text[PointerToRawData : +min(VirtualSize, SizeOfRawData)])[:16]` | **`docs/method-rules.md:213` (S134-d)** — its four quoted outputs recompute 4/4 |

Both are implemented in **`tools/sigbypass-mod/text_digest.py`** (new).

| variant | RAW | VIRTUALSIZE | recorded gate |
|---|---|---|---|
| `botai` (S136, working) | **`5e47c13cf7f0a158`** | — | (new) |
| `botai` (as S135 shipped, DEAD) | `0f310c58cd0e0941` | — | `c55cb560cc602e31` |
| `botspawn` | `1a8fa5fe06f87019` | **`e48c90bc6cf17c93`** | `e48c90bc6cf17c93` ✅ VIRTUALSIZE |
| `botteam` | `160f067d697b545b` | **`0c16652dc0338d33`** | `0c16652dc0338d33` ✅ VIRTUALSIZE |
| `botspawn_readonly` | `319ac875af229f46` | `d96480ad64c1a403` | `f5f9896feeac45dc` ❌ **NEITHER** |

⚠⚠ **RETRACTION S136 MADE ABOUT ITSELF:** it first published *"the four S135 bot digests appear
NOWHERE in the repo"*. **That is FALSE** — all four are recorded in `CLAUDE.md`,
`docs/s135-queue-arms-a-match.md` and `docs/next-session-prompt-s136.md`. The error came from a
`grep -rl` over `docs/` that **timed out at 2 minutes**, read as a negative. **Scope your greps and
check the exit code.**

★ **NEW [M]: `botspawn_readonly` reproduces under NEITHER recipe** ⇒ that artifact has changed since
its gate was recorded. **Re-record it before using it as a control.**

⛔ **Do not repeat "9/9 verbatim"** — a selection effect. Honest: **48/87** `tutorial_launch_*.dll`
and **55/132** corpus tokens under RAW; **6** VirtualSize-only; **0** for whole-file sha256/md5/sha1.
⚠ **"Canonical" is a DECISION, not a measurement.** ≥4 artifacts (`play`, `dismount`,
`dropplane_b1only`, `droppod_pe_cdopoke`) have BOTH digests recorded as the same gate in different
files — choosing RAW **silently invalidates six recorded gates. Say which, in the same commit.**
⚠ **Degenerate case:** a DLL with `VirtualSize == SizeOfRawData` cannot discriminate the recipes.
⚠⚠ **THE "A/B AGAINST A COPY OF ITSELF" HAZARD IS LIVE RIGHT NOW** — `play` / `play_nopimutex` /
`play_strictroot` share `9bc10a4552c596e1`; `poolspawn` / `poolspawn_cdoctrl` share
`85f3cee44c31b1cd`; `droppod_pe` / `droppod_pe_cdoctrl` share `61fd0745c23e89f0`. **A digest tool
must flag duplicate digests across differently-named variants.**
⚠ Regression gates re-verified unchanged in S136: `play 9bc10a4552c596e1`,
`dismount 53483e6181bb3583`.
⚠ **`build/` is gitignored and three S136 builds overwrote each other** — only source-reproducibility
(`git show HEAD:` + unmodified `build.ps1`) recovered the flight-1 artifact. **Archive every A/B arm
before rebuilding.**

---

## 5b. THE OFFLINE QUEUE — WHAT S136 CLOSED, AND WHAT IS LEFT

**✅ CLOSED IN S136 (do not redo):**
1. **`CLAUDE.md`'s broken section-hash pointer** — it sent readers to `verify_dll.py` (0 hash lines)
   and `s109-dump-forensics.md §23` (no snippet). **That was the root cause of the entire digest
   confusion**: two sessions followed it, found nothing, and concluded no recipe existed. Fixed, with
   all four real implementations named.
2. **`dumps/s133-phase2-*` audit** — mis-named, content confirms it (`AFTER` 15,459 pages is a strict
   subset of `BASE` 15,512; only-BASE 53; 0 conflicts). **But `0x5879000` is LIT in BOTH images**, so
   the S133 DARK→LIT headline came from the CANCEL→phase2 diff, not this pair. **Filename defect
   only; no published conclusion is wrong.** ⛔ Do not restate it as "the before/after method is
   threatened" — it is not.
3. **Digest recipes settled**, `text_digest.py` hardened (`--dupes` / `--verify` / `--altrecipes`).
4. **`AController::InitPlayerState` graded** (§1) and **`0x54F8E40` named** — it is
   `IsA<ALokiPlayerState>` (`0x5430F70` → `.rdata 0x8A2430A` = `LokiPlayerState`), with
   `0x54F8DC0` → `LokiHeroCharacter` reproducing S132 exactly as the positive control.
5. **Netmode corollary banked** (§1 / `settled §6b`).

**🔲 STILL OPEN, offline and free:**
- **Which netmode is it?** `!= NM_Client` is [M]; Standalone(0) vs ListenServer(2) is not. **If
  Standalone, engine `HasAuthority()` plausibly passes and the reachable "server-only" surface is
  larger than the repo assumes.** This half-answers the question written down twice and never
  actioned at `CLAUDE.md:2513` / `docs/fk22-dropphase-reachability.md:1253`.
- **Can a `LokiBotController` be instantiated at all?** Its CDO exists, 0 LIVE. One
  `SpawnObject`/`SpawnActor` probe answers it, and it is the real precondition for a *Loki* bot as
  opposed to an engine one.
- **Re-record `botspawn_readonly`'s gate** (see §4).

---

## 6. THE ONE-PARAGRAPH STATE OF CO-OP VS. AI

The tile, the click, the queue, the timer and the cancel all work. The queue **answers** — four
reproductions, `UTravelManager` firing, the client parking locally as designed — and a staged
tutorial world is reachable with `forceTutorialMatch = false` off the queue-armed MatchID. Bot
**pawns** spawn, singly and as a randomised team of three. As of S136 a pawn is also **possessed by a
real `AIController`**: the handshake is bidirectional, `AController::Possess` ran, and
`APawn::SpawnDefaultController` executed for the first time across 55 captured images. **But it is an
engine `AAIController`, not a Loki bot** — no `PlayerState`, no team, no hero-class record, no
`BehaviorTree`, and zero `BotController`-derived objects exist. Two walls remain and both are named
from the bytes: `bWantsPlayerState` (one CDO bit, §1.2) and, past it, the stripped
`ServerSetHeroClass` / `SetPlayerTeam` pair (§1.3). The first is a one-line arm in this project's
safest measured write class; the second is FK-1's authority cut again, and it is the real boundary
between "an AI pawn exists" and "a bot exists".

---

## 7. ARTIFACTS S136 LEFT ON DISK

| path | what |
|---|---|
| `docs/s136-ai-controller-settled.md` | the settled doc — **its CORRECTIONS block governs** |
| `docs/s136-botai-flight1-DEADARM-marker.txt` | flight 1 — the full ladder, `called=0` |
| `docs/s136-botai-flight2-CONTROLLER-marker.txt` | flight 2 — first successful call |
| `docs/s136-flight3-PREREGISTERED.txt` | flight 3 predictions, written before injection |
| `docs/s136-botai-flight3-REPLICATION-marker.txt` | flight 3 — `dCtl=1 dHero=1`, 7/7 |
| `dumps/merged12.dump.exe` | canonical image, `.text` **16,772 / 30,281 = 55.39 % pages** |
| `dumps/s136-botai/` | the P4 capture |
| `tools/re/obj_by_chain.py` | census by class DERIVATION CHAIN (new) |
| `tools/sigbypass-mod/text_digest.py` | both digest recipes + `--dupes` (new) |
| `docs/capture.log.pre-s136-botai` | capture.log backed up before the `ags` restart |
