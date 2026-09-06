# S138 flight 2 — ARM E FIRED. SpawnBot ran its PREMADE path.

Written 2026-08-21 immediately after the flight, from the artifacts. The pre-registration
`docs/s138-ARME-PREREGISTERED.txt` is UNEDITED. Read `docs/s138-flight1-results.md` first — it
contains the blocker this flight worked around.

## 0. HEADLINE, SCOPED HONESTLY

**`SpawnBot` was called with a non-null `PremadeBotController`, it returned a pawn, and
`AController::Possess` ran on our own `ALokiBotController` — the first time in this project's
history that anything has gone through `SpawnBot` at all.**

**The E5 page receipt stayed DARK.** ⚠⚠ **My first reading of that — "so by rule U2 the
PlayerState-dependent half did not run" — is RETRACTED: see the CORRECTIONS BLOCK (§2b), which
governs this file.** U2 is a **non-sequitur** [M, machine-exhaustive, two independent
disassemblers]: `0x556DEA2` sits `0x4A` bytes past the point where all three PlayerState gates
rejoin, behind three FURTHER guards, so E5 says nothing about the PlayerState block either way.
**Whether that block ran is UNDETERMINED**, because the pre-flight gate that would settle it read
the WRONG OBJECT (a `LokiGameStateUAVComponent`, not the GameState — §2b C3, an error I published).

**I am still NOT claiming the wall is broken** — but the reason is now "undetermined", not "no".

⛔ **This is NOT a working bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
(`0x556DE53 → 0xF7EB60`) are stripped folds and remain so. Say *"SpawnBot ran its premade path"*.

## 1. ★★★★★ THE FIX FOR FLIGHT 1's BLOCKER WORKED — 6/6 PRE-REGISTERED PREDICTIONS

Flight 1 established that ARM E's G6 gate READS `SpawnBot`'s prologue, and that the page is
`PAGE_NOACCESS` until the function has EXECUTED, so G6 could never pass. The fix needed no code
change: run the Blueprint wrapper `Comp_BP_BotSpawner_C::SpawnClassBotAtLoc` first (it calls
`SpawnBot` with `EX_NoObject` in the premade slot), which EXECUTES `SpawnBot` and decrypts its page.

Predictions were written to `docs/s138-f2-PREDICTION.txt` **before** the injection. Measured:

| # | prediction | result |
|---|---|---|
| P1 | `SpawnBot 0x556D910` NOACCESS → READABLE, prologue `40555356574154415541564157488dac` | **HIT** — exact match |
| P2 | `MakeNewBotController 0x5563660` NOACCESS → READABLE | **HIT** |
| P3 | `0x5556D50` STAYS DARK | **HIT** |
| P4 | `OnUnPossess 0x55667F0` STAYS DARK | **HIT** |
| P5 | `OnPossess 0x5565470` STAYS DARK | **HIT** |
| P6 | the two lit controls stay lit | **HIT** |

P3/P4/P5 are the two-sided half: had everything gone readable, P1 alone would not have
discriminated. **6/6, with three predicted negatives holding.**

★ The recovered prologue matches the offline transcription **byte for byte**, which independently
re-confirms that `0x556D910` IS `SpawnBot` — a free identity check the project did not have before.

★★ **REUSABLE:** *to read a never-executed function in a live process, first drive any path that
calls it.* This is S118's steerable-decryption method applied to a READ rather than to coverage.

⚠ **COST OF THE FIX, and it is a real one:** running `botspawn` first also decrypted
`MakeNewBotController`, **destroying its page as a receipt** for "the premade short-circuit skipped
it". That receipt was never one of the pre-registered ones (E5/E6 were), but a future arm wanting
it must NOT use this decryption trick — or must place the receipt on a page the trick does not
touch. My own fix cost an instrument.

## 2. ARM E — WHAT IS MEASURED

    [PS] G1 Possess authority: Role@+0x160=3 (3=ROLE_Authority)  [ctl+0x448]&4=0 -> PASSES
    [PS] G2 PlayerState=0x1E876D62230  PlatformPlayerID.ArrayNum [PS+0x8C8]=0 -> passes
    [PS] G3/G4 LokiGameState=0x1E77700DE30  TeamStates[+0x600].Num=0
    [PS] G5 component = 0x1E878F43000 'Comp_BP_BotSpawner' class='Comp_BP_BotSpawner_C'
    [PS] G6 target=0x7FF7AE09D910 prologue=40 55 53 56 57 41 54 41 55 41 56 41 57 48 8D AC
             -> SIGNATURE MATCHES SpawnBot
    [PS] ARM E CALLING SpawnBot(comp=..., heroClass=..., loc=(1500.0, 0.0, 13240.0), ...)
    [PS] ARM E returned (called=1 faulted=0) ReturnValue=0x1E81C6DAAC0 'BP_HERO_Ronin_C'
    [PS] ARM E premade controller Pawn@0x3F8 is now 0x1E81C6DAAC0  (was 0x1E85F705580 before)

| prediction | result |
|---|---|
| E1 ARM D yields a `LokiBotController` with a PlayerState both sides | **HIT** (`spawns=3 pokeOK=1 restoreOK=1`) |
| E2 all six gates pass and print raw values | **HIT** |
| E3 non-null `ALokiHeroCharacter*` return | **HIT** `0x1E81C6DAAC0` |
| E4 `LokiHeroCharacter`-chain census +1 for ARM E | **HIT** — `dHero=4` total, of which 3 are ARM D's |
| E5 `0x5556D50` DARK → non-zero | **MISS — still NOACCESS** |
| E6 `OnUnPossess 0x55667F0` DARK → non-zero | **HIT** — NOACCESS → EXECUTE_READ |
| E7 premade controller's `Pawn` == SpawnBot's new pawn | **HIT**, two instruments |
| E8 `=LokiBotController` stays at 1 | **HIT** — external census `BotController-chain : 1` |

**7 of 8 hit; E5 is the miss and it is the load-bearing one.**

★ **E6 is a genuine first.** `ALokiBotController::OnUnPossess 0x55667F0` was DARK in every image
this project has ever taken (it is the recorded "correct negative" from S137, never unpossessed).
It is now lit, which proves `Possess` ran on our premade controller and unpossessed its prior pawn.

★ **E7 confirmed by two independently-written instruments:** the shim reported
`Pawn@0x3F8 = 0x1E81C6DAAC0`, and the external `tools/re/playerstate_readout.py` independently read
the live `LokiBotController 0x1E89A2CC870` as possessing **the same pointer** SpawnBot returned.

## 2b. ⚠⚠⚠ CORRECTIONS BLOCK — THIS GOVERNS §3 AND §7 BELOW

Added the same evening, after an offline disassembly pass on `dumps/s138-arme` with adversarial
verification. **Two of my own statements below are wrong. §3's headline is retracted.**

**C1. THE PRE-REGISTRATION'S RULE U2 IS REFUTED, AND SO IS §3's HEADLINE.**
U2 said: *"a non-null return with `0x5556D50` STILL DARK ⇒ execution did NOT pass the PlayerState
gate."* **That is a non-sequitur, and it is now refuted at byte level by two independently-written
disassemblers, machine-exhaustively.** All three PlayerState gates jump **FORWARD** into the same
continuation:

    0x556DD73  0F 84 DF 00 00 00   je 0x556DE58     GATE 1  PlayerState null
    0x556DD83  0F 84 CF 00 00 00   je 0x556DE58     GATE 2  IsA(ALokiPlayerState)
    0x556DD90  0F 8F C2 00 00 00   jg 0x556DE58     GATE 3  PlatformPlayerID.ArrayNum > 1

`0x556DEA2` (the E5 call site) is **`0x4A` bytes PAST the join at `0x556DE58`**, behind three
FURTHER guards (`0x556DE6A`, `0x556DE76`, `0x556DE82`, all → `0x556DED2`). Machine-exhaustive:
branches entering `[0x556DD96,0x556DE58)` from outside = **0**; leaving from inside = **0**.
⇒ **E5 dark says nothing whatsoever about the PlayerState block.** Skipping it and running it
produce the identical observable.

**C2. SO: DID THE PLAYERSTATE BLOCK RUN? UNDETERMINED — not "no", and not "yes".**
A lane concluded it RAN at `[M, strong]`; its refuter downgraded that to **`[I, strong]`**, because
the one gate the bytes cannot see (GATE 0, `GetLokiGameState != null` at `0x556DD63`) was graded
PASS from a pre-flight that **measured the wrong object** — see C3.

**C3. ⚠⚠ AN ERROR I PUBLISHED, AND IT IS THIS REPO'S OWN SUBSTRING-LATCH TRAP.**
§3 and §7 below cite *"`ALokiGameState.TeamStates (+0x600) Num = 0`"*. **The object read was NOT an
`ALokiGameState`.** The marker's actual line is:

    [PS] G3/G4 LokiGameState=0x1E77700DE30 'LokiGameStateUAVComponent'  TeamStates[+0x600].Num=0

and I **quoted it with the class name stripped**, then restated it as a fact about the GameState.
`tutorial_launch.cpp:14339` latches the candidate with
`PhChainHas(cls,"LokiGameState")`, which is `strstr` and first-match — and `"LokiGameState"` is a
substring of `"LokiGameStateUAVComponent"`. **The source's own comment two lines above documents
this exact trap for GameMode and fixes it there (`"LokiRoundGameMode"`), leaving the GameState line
defective.** ⇒ **G4 is VOID** (an offset read on a component), and **G3 is VOID** (wrong object).
★ It is the "a digest is an instrument" failure one level down — compression dropped the single
field that falsifies the reading, exactly as S137's lost gate 3 did.

**C4. WHERE EXECUTION ACTUALLY LEFT IS UNKNOWN.** [M] it returned via one of four early jumps into
the success tail `0x556DED2` (`0x556DD63`, `0x556DE6A`, `0x556DE76`, `0x556DE82`). The last two are
excluded on good grounds (Possess ran; the premade **is** an `ALokiBotController`). Between
`0x556DD63` (no GameState) and `0x556DE6A` (no TeamState) **there is no evidence** — and the two
available readings conflict: the marker's own world read gives `World+0x258 (GameState) = 0` in both
flights, while the client's log shows `BP_LokiGameState_Tutorial_C` entering BeginPlay ~47 s before
the baseline probe. The probe enumerated **4** objects named `LVL_Tutorial` and printed only `[0]` —
first-match again.
⇒ **Do NOT act on "populate `TeamStates` and it will work."** If the divert is `0x556DD63`, that
changes nothing.

**C5. `botName Num=6` IS CONFIRMED AN ARTIFACT — my §3 was right to discard it.** An exhaustive
audit of the `r12` (botName) register shows the ONLY write is at fn offset **+0x123**
(`0x556DA30 → 0xFA2140`, an FString move-assign), and the free at both exits takes only the pointer,
leaving `Num`/`Max` stale and `Data` dangling. **`Num=6` proves reaching +0x123 and nothing more.**

**C6. THE E6 MECHANISM WAS WRONG, AND THE CORRECTION STRENGTHENS IT.** `[vtbl+0x868]` in
`AController::Possess` is **slot 269 = `OnPossess`**, not `UnPossess` (`UnPossess` is slot 270).
`OnUnPossess` is reached three frames deeper, by a **direct, guarded** call at `0x36E1AA8` inside
`AController::OnPossess`. Because that path carries **three** guards, `OnUnPossess` lighting
genuinely entails a *pre-existing different pawn* — which the marker independently records
(`was 0x1E85F705580 before`). **E6's conclusion survives; only its stated mechanism changes.**
Both page receipts are now explained: `OnPossess 0x5565470` **and** `OnUnPossess 0x55667F0` both
went NOACCESS → EXECUTE_READ, and only this chain predicts both.
⚠ This also corrects §1's P5, which predicted `OnPossess` would stay dark: it did **not** stay dark
after ARM E. P5 held after `botspawn` (correctly — that route creates no controller) and was
falsified by ARM E, which is the expected and correct outcome.

**C7. ★★★★★ THE BEST RESULT OF THE PASS, AND IT REMOVES A RISKY TECHNIQUE:**
**`SpawnBot` sets the new pawn's `AIControllerClass` to `ALokiBotController` ITSELF** —
`0x556DC91 call 0x52EA940` (the `ALokiBotController` lazy `StaticClass`) then
`0x556DCAF 48 89 BB D0 03 00 00 mov [rbx+0x3d0], rdi`. Verified independently by two parties.
⇒ **S137's ARM D `Default__Pawn+0x3D0` CDO poke — a process-wide class-default mutation that had to
be poked and restored around every spawn — is UNNECESSARY on the `SpawnBot` route.**

**C8. Free corrections to the repo record**, both from this pass:
- `CLAUDE.md` says `[rsp+0x70]` is *"written in exactly TWO places … and read ONCE"*. It is read
  **twice** — `0x556DA4F` (the short-circuit test) and `0x556DD2F` (the Possess guard). Written
  twice ✓. The conclusion is unaffected; the count is off by one.
- **`MakeNewBotController`'s page cannot serve as a "it never ran" control** — 4 KB granularity, and
  `0x556DB23` is the only call into page `0x5563000` from anything known to have run. The
  short-circuit is `[M]` from the bytes and does not need the page.
- Page census `merged13 → s138-arme`: exactly **2** new `.text` pages (`0x5566000` 0→3672 and
  `0x4656000`). `0x5556000` is 0/4096 in **both**.

⚠ **NOT FIXED IN CODE THIS SESSION, DELIBERATELY.** The `tutorial_launch.cpp:14339` substring defect
is one string, but editing the shim source without rebuilding and re-verifying would leave `build/`
inconsistent with the source and risk a successor flying an unverified arm. **Fix it, rebuild, and
re-record digests as a unit.**

## 3. ⚠⚠ ~~E5 IS DARK — THE PLAYERSTATE HALF DID NOT RUN~~ **RETRACTED — see C1/C2/C3 above**

`0x5556D50` is called at `0x556DEA2`, past the PlayerState-dependent block. It is
**still `PAGE_NOACCESS` after the call**, and the protector decrypts on EXECUTE, so nothing on that
page ran. Pre-registration U2 governs: *"a non-null return with `0x5556D50` STILL DARK ⇒ execution
did NOT pass the PlayerState gate; the interesting half did not run, whatever the return value
says."*

⚠⚠ **AND THE ONE PIECE OF CONTRARY EVIDENCE IS PROBABLY AN ARTIFACT — DO NOT LEAN ON IT.**
The arm printed `ARM E botName FString after the call: Data=0x1E89B4B97C0 Num=6 Max=8`, which looks
like proof that the `"bot%d"` naming block (which sits inside the PlayerState-dependent region) ran.
**But `SpawnBot` FREES that FString with the game's `FMemory::Free` on BOTH exit paths**, so a
post-call read is a read of freed memory and a non-zero `Num` may simply be a not-yet-scrubbed
header. **It contradicts the dark page, it is the favourable-looking reading, and it is the weaker
instrument.** Discarded pending the offline disassembly (running; see §6).

⇒ **The honest statement is: SpawnBot ran, took the premade short-circuit, possessed with our
controller, returned a pawn, and diverted before `0x556DEA2`.** Where it diverted, and whether the
PlayerState block ran at all, is being read from the bytes rather than guessed.

★ **A live lead worth checking there:** G3/G4 read `ALokiGameState.TeamStates (+0x600) Num = 0` —
an EMPTY team array. `SpawnBot` calls its own `GetLokiGameState (0x56F01A0)` and
`GetTeamState (0x5696D60)`; an empty team array is a strong candidate for an early divert that has
**nothing to do with the PlayerState gate**, which would mean U2's inference is too coarse.

## 4. Q2 — SECOND SAMPLE, SECOND CLIENT: THE BOT STILL DOES NOT MOVE

The sample flight 1 owed was taken here, in a different process:

    LokiBotController 0x1E89A2CC870
      bCharacterControllable +0x6A0 = 0     <- THE GATE
      RandomMoveDirection    +0x658 = (0,0,0)
      pawn ControlInputVector +0x418 = (0,0,0)

**Reproduced: n=2 samples across 2 clients.** The bot is inert BY GATE, not by defect. The three
plain `AIController`s in the same run also read `ControlInputVector = 0`, as does the PLAYER's own
pawn — ⚠ so `ControlInputVector` alone does not discriminate; the GATE at `+0x6A0` is what carries
this, and `+0x602` being 0 is what makes it a statement about `LivingState` rather than about a
forced override.

⚠ **STILL NOT MEASURED: why `(LivingState==Alive) && !IsStunned` is false.** The read is cheap
(`LivingState` on the bot pawn, with the player hero as positive control) and was NOT taken — the
client died before it. **This is the single cheapest open item.**

## 5. FLIGHT ECONOMY

| attempt | outcome |
|---|---|
| 1 | FK-31 during staging (dump archived, classified) |
| 2 | FK-31 during staging (dump archived, classified) |
| 3 | STAGED; `spawnbot_readonly`; G6 refusal found; Q2 sample 1; then FK-32 on 4th manual-map |
| 4 | STAGED first try; `botspawn` → `spawnbot_premade`; **ARM E fired**; full capture; then FK-32 on 5th manual-map |

4 launches → 2 armed windows. FK-32 counts across all recorded `0xDEAD` kills are now
**7 / 6 / 4 / 4 / 5** — still **no dose-response**; do not plan an "injection budget".

★ **Capture-as-you-go was decisive.** Flight 4's client died minutes after the last read, and
**nothing was lost**: both page probes, the in-shim marker, the external readout and a full
`dumpimage` were all taken before the kill.

## 6. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-f2-PREDICTION.txt` | the 6 predictions, written before injecting `botspawn` |
| `docs/s138-f2-pageprobe-BASELINE.txt` | 5 dark / 2 lit, before anything |
| `docs/s138-f2-pageprobe-AFTER-botspawn.txt` | **the 6/6 result** |
| `docs/s138-f2-pageprobe-AFTER-premade.txt` | E5 dark, **E6 lit** |
| `docs/s138-f2-marker-staged-sp.txt` / `-botspawn.txt` / `-premade.txt` | in-shim markers per stage |
| `docs/s138-f2-external-AFTER-premade.txt` | external confirmation (E7, E8, Q2 sample 2) |
| `docs/s138-Loki-flight2.log`, `docs/capture.log.s138-flight2` | client + wire |
| **`dumps/s138-arme/SUPERVIVE-Win64-Shipping.dump.exe`** | **169.9 MB, 67.81 % readable — the first image with `SpawnBot` fully decrypted** |

⚠ The `.dump.exe` is the important one: `SpawnBot`'s complete body is readable in it for the first
time, which is what makes §3's question answerable offline with no further launch.

## 7. NEXT — REWRITTEN AFTER THE CORRECTIONS BLOCK

1. ★★ **FIX THE INSTRUMENT FIRST — it is one string and it voided two gate reads.**
   `tutorial_launch.cpp:14339` `PhChainHas(cls,"LokiGameState")` must require the terminal class
   (or match `BP_LokiGameState_`), and the latch must **enumerate all candidates instead of taking
   the first** — for the GameState *and* for the 4 objects named `LVL_Tutorial`. Pick the world the
   component itself caches at `[comp+0xC0]`, which is the world `SpawnBot` uses
   (`0x556DD41 mov rax,[rsi+0xc0]`). Rebuild and re-record digests as a unit.
   **Until then, G3/G4 in any marker are uninterpretable.**
2. **Then re-read `[GS+0x600]/[GS+0x608]` on the REAL GameState.** That, plus `[World+0x258]`,
   discriminates the two surviving divert candidates (`0x556DD63` vs `0x556DE6A`).
   ★ Cheaper still, if a client is live at the time: read **`[PS+0x8C8]`** after the call. G2
   measured it **0** before; the naming block writes `PlatformPlayerID` there. Non-zero ⇒ the block
   ran ⇒ the divert was `0x556DE6A`. Still-zero ⇒ the divert was `0x556DD63`. **One RPM read.**
3. **Drop the ARM D CDO poke from any `SpawnBot`-route arm** — C7 makes it unnecessary, and it
   removes a process-wide class-default mutation from the risk budget.
4. **Read `LivingState` on a bot pawn**, player hero as positive control — Q2's follow-up, and still
   the cheapest open item.
5. Do NOT re-fly ARM E unchanged. It already did what it can do; what is missing now is a correct
   GameState read, not another call.
