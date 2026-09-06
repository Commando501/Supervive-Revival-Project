# S138 flight 3 — the divert is SETTLED, and the latch fix is validated in flight

Written 2026-08-23 from the artifacts, immediately after the flight. Pre-registration:
`docs/s138-f3-PREREGISTERED.txt` (UNEDITED). Predecessors: `docs/s138-flight2-arme-fired.md`
(read its §2b CORRECTIONS block), `docs/s138-latch-fix-rebuild.md`, `docs/s138-offline-followup.md`.

---

## 0. HEADLINE

**`SpawnBot`'s early exit is `0x556DE6A` — `GetTeamState` returning NULL. [M], two independent
readings, both pre-registered.** The PlayerState-dependent block RAN to completion; execution passed
`0x556DD63`; `ServerSetHeroClass` and `SetPlayerTeam` were both REACHED and both are stripped folds,
so they did nothing.

**And the latch fix is validated in flight**: the census now names `BP_LokiGameState_Tutorial_C`
instead of a component, and `TeamStates.Num = 0` is measured on the CORRECT object for the first time.

⇒ Combined with the offline result that `TeamStates` can never be non-empty on a client, **the tail
past `0x556DE6A` — including the `0x5556D50` receipt — is unreachable on this client, full stop.**

⛔ Still **not** a working bot. Say *"SpawnBot ran its premade path to the team-state gate."*

---

## 1. ★★★★★ THE DISCRIMINATOR — pre-registered, and it fired cleanly

`docs/s138-f3-PREREGISTERED.txt` §1, written before launch:

> P1 `[PS+0x8C8]` AFTER the call is NON-ZERO ⇒ the naming block RAN ⇒ execution passed `0x556DD63`
>    ⇒ the divert was `0x556DE6A` (GetTeamState)
> P2 `[PS+0x8C8]` AFTER the call is STILL 0 ⇒ the divert was `0x556DD63` (no GameState)
> P3 If P1: `[PS+0x8C0]` holds an FString reading "bot" followed by a digit.

MEASURED, same PlayerState object the arm itself printed at G2 (`0x2C98A6DCCD0`):

| | before the call (arm, G2) | after the call (external RPM) |
|---|---|---|
| `[PS+0x8C8]` PlatformPlayerID.Num | **0** | **5** |
| `[PS+0x8C0]` FString contents | — | **`'bot0'`** |

**P1 HIT. P3 HIT.** `"bot%d"` is the exact format literal at `.rdata 0x8B12310` that the block uses,
and `Num=5` is `"bot0"` plus its terminator.

★★ **AND IT IS NOT THE FREED BUFFER — that is precisely why this field was chosen.** `SpawnBot`
frees the CALLER's `botName` FString on both exit paths, so the arm's own post-call readback of it
is a read of freed memory and was correctly discarded in flight 2. `[PS+0x8C0]` is a DIFFERENT
object — the PlayerState's own `PlatformPlayerID`, which the naming block WRITES. Reading it is
sound, and the pre-registration said so before the flight rather than after.

### The complete, closed account of the call

    premade non-null -> 0x556DAA4 jne 0x556DB32   MakeNewBotController NEVER CALLED
    0x556DD3C  call AController::Possess          RAN   (E6: OnUnPossess page went dark -> lit)
    0x556DD63  GetLokiGameState != NULL           PASSED  <- proven by the naming block running
    0x556DD73/83/90  the three PlayerState gates  PASSED  <- proven by 'bot0'
    0x556DDAD  component bot counter ++           RAN
    0x556DDB3  Printf(L"bot%d") -> [PS+0x8C0]     RAN     <- MEASURED 'bot0'
    0x556DE43  ServerSetHeroClass -> 0xF7EC20     RAN, void fold, NO EFFECT
    0x556DE53  SetPlayerTeam      -> 0xF7EB60     RAN, false fold, NO EFFECT
    0x556DE5F  call GetTeamState                  RETURNED NULL (TeamStates empty)
    0x556DE6A  je 0x556DED2                       ***** THE DIVERT *****
    0x556DED2  free botName; return the pawn      -> non-null return, 0x5556D50 never reached

Every observable of flights 2 and 3 is now accounted for with nothing left over.

⇒ ⚠⚠ **This RETIRES the pre-registration's rule U2 for good.** U2 said a dark `0x5556D50` means the
PlayerState gate was not passed. It was already refuted structurally (the gates rejoin *upstream* of
the receipt); it is now refuted **empirically** — the gate was passed and the receipt is still dark.

---

## 2. ★★★★★ THE LATCH FIX, VALIDATED IN FLIGHT

    [PS] G3/G4 GameState candidates: 2   (EXACT chain match on 'LokiGameState')
    [PS]   gsCand[0] 0x2C9C76610F0 'BP_LokiGameState_Tutorial_C'  TeamStates Data=0x0 Num=0
    [PS]      chain: BP_LokiGameState_Tutorial_C<-BP_LokiGameStateRounds_C<-BP_LokiGameState_C<-
    [PS]             BP_LokiGameState_Code_C<-LokiGameState_AS<-LokiGameState<-LokiGameStateBase<-
    [PS]             GameStateBase<-Info<-LokiActor<-Actor<-Object
    [PS]   World->GameState = NULL or unreadable -- falling back to the census.

| pre-registered | result |
|---|---|
| F1 new multi-candidate line present, OLD `G3/G4 LokiGameState=0x...` absent | **HIT** |
| F2 **`LokiGameStateUAVComponent` MUST NOT appear** | **HIT — it is gone** |
| F3 each candidate's chain contains an element exactly `LokiGameState` | **HIT** (10th element) |
| F4 a `World->GameState` line or the explicit fallback | **HIT** (fallback fired) |
| F5 the candidate is `BP_LokiGameState_Tutorial_C` | **HIT** — matches the client's own log |
| F6 `TeamStates.Num == 0` on the real GameState | **HIT** — `Data=0x0 Num=0` |

★ **F6 is the first time `TeamStates` has ever been read off an actual `ALokiGameState`.** Flight 2's
`Num=0` came from a component and was void. The value is the same; the *evidence* is now real, and it
independently corroborates the offline finding that the array is永 unpopulatable.

⚠ **A DEFECT IN MY OWN FIX, found by its own output:** `gsCand[0]` and `gsCand[1]` are **the same
pointer** `0x2C9C76610F0`. `BsScanWorld` runs three census passes (A0/A1/A2) and I never reset
`g_psGsCandN` between them, so one object is recorded once per pass and the count is an
inflated duplicate. It then tripped the spurious "more than one GameState candidate … AMBIGUOUS"
warning. **Harmless here** — both entries are the correct object and the chain is printed, so the
finding is unaffected — but the count is wrong and the ambiguity warning is a false positive.
**Fix: reset the candidate counters at the top of each pass, or de-duplicate on insert.**
⚠ `World->GameState` read NULL again, i.e. the S137 wrong-world latch is still unfixed. The fallback
handled it and printed that it was falling back — which is the behaviour the fix was for.

---

## 3. ARM E, REPRODUCED IN A THIRD CLIENT

    G1 Role@+0x160=3, [ctl+0x448]&4=0 -> PASSES
    G2 PlayerState=0x2C98A6DCCD0  [PS+0x8C8]=0 -> passes
    G5 gameMode=BP_LokiGameMode_Tutorial_C  component=Comp_BP_BotSpawner_C 0x2C97C57DC00
    G6 prologue 40 55 53 56 57 41 54 41 55 41 56 41 57 48 8D AC -> SIGNATURE MATCHES SpawnBot
    ARM E returned (called=1 faulted=0) ReturnValue=0x2C97BB00040 'BP_HERO_Ronin_C'
    ARM E premade controller Pawn@0x3F8 is now 0x2C97BB00040  (was 0x2C9B3D05580 before)

Page receipts, before → after: `SpawnBot` NOACCESS → EXECUTE_READ (via `botspawn`, 6/6 again);
**`OnUnPossess 0x55667F0` NOACCESS → EXECUTE_READ** (E6); **`0x5556D50` still NOACCESS** (E5) — and
now explained rather than merely observed.

External confirmation (`tools/re/playerstate_readout.py`, timestamped 00:55:59):
`LokiBotController 0x2C9A1F809F0` → `PlayerState 0x2C98A6DCCD0` (**the exact object I read `'bot0'`
from**) and `Pawn 0x2C97BB00040` (**exactly SpawnBot's return value**). `BotController-chain: 1`, so
SpawnBot created no controller (E8). Two independently-written instruments, same pointers.

**Q2 reproduced a THIRD time, third client:** `bCharacterControllable +0x6A0 = 0`,
`RandomMoveDirection = (0,0,0)`. The bot is inert BY GATE.

---

## 4. ⚠⚠ THREE LAUNCHES LOST TO MY OWN DRIVER — and it nearly became a false finding

I wrote `configs/s138-autostage.ps1` to retry across FK-31. Its verdict check tested the marker for
`done step=4` **immediately** after `fk24-stage.ps1` returned. But `stage complete` prints when the
stager has finished INJECTING `sp`; `sp` then does its spawn+possess work asynchronously and writes
`done step=4` **seconds later** — MEASURED at **12 s** on the successful run.

So the check raced, read a marker containing only the injection header, declared "did not stage",
and **`Stop-Process`'d three clients that had staged perfectly.**

⚠⚠ **I was one attempt away from recording this as a FOURTH CONSECUTIVE FK-31 DEATH** — the exact
threshold (p = 0.005) that the crash classifier itself had nominated for calling FK-31 systematic.
An instrument fault was about to be written down as a property of the game: this project's single
most-repeated error, and I nearly committed it with the rule quoted in my own prompt.
**What caught it was reading the stager's own output instead of trusting my driver's verdict** — the
log plainly said `stage complete` and `OK: manual-map complete` for `sp`.

**Fixed**: poll for `done step=4` with a 180 s budget, and **never kill a client that is still alive**
— if the marker does not appear, leave it running and say so. On the very next run it staged on
**attempt 1**, with the 12 s delay logged.

⇒ ★ **Reusable: a completion message from a stage script means "I finished my step", not "the
injected code finished its work."** Gate on the payload's own receipt, never on the launcher's exit.

---

## 5. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-f3-PREREGISTERED.txt` | predictions, written before launch, unedited |
| **`docs/s138-f3-DISCRIMINATOR.txt`** | **`[PS+0x8C8] = 5`, `'bot0'` — the settling measurement** |
| `docs/s138-f3-marker-premade.txt` | ARM E + the FIXED G3/G4 readout |
| `docs/s138-f3-marker-botspawn.txt` / `-staged-sp.txt` | the page-decrypt step and the staged world |
| `docs/s138-f3-pageprobe-{BASELINE,AFTER-botspawn,AFTER-premade}.txt` | the three page states |
| `docs/s138-f3-external.txt` | external second instrument |
| `docs/s138-Loki-flight3.log`, `docs/capture.log.s138-f3` | client + wire |
| `dumps/s138-f3/SUPERVIVE-Win64-Shipping.dump.exe` | 169.9 MB, **67.87 %** readable |
| `configs/s138-autostage.ps1` | the retry driver, defect fixed and documented in-file |

Arms flown (both from `dumps/s138-arms-v2/`, rebuilt after the latch fix):
`botspawn` RAW `b2203efd62161182` · `spawnbot_premade` RAW `302c2d29dfa3c4c5`.

---

## 6. WHAT IS NOW CLOSED, AND WHAT IS NOT

**CLOSED [M]:**
- The `SpawnBot` divert: `0x556DE6A`, `GetTeamState` NULL. Four-way ambiguity → one branch.
- Rule U2: refuted structurally AND empirically. Do not apply it.
- The substring-latch defect: fixed, flown, validated, with `LokiGameStateUAVComponent` gone.
- `TeamStates.Num = 0` on a genuine `ALokiGameState`.
- Anything past `0x556DE6A` on this client — unreachable, because `TeamStates` is unpopulatable
  (`GetOrCreateTeamState` impl `0x5634BD0` returns nullptr unconditionally; `SetNumTeams` is a fold).

**NOT closed:**
- FK-22 proper: `ServerSetHeroClass` / `SetPlayerTeam` are stripped folds. Reaching them changed
  nothing, which is now measured rather than assumed.
- **Why `bCharacterControllable` is false** — still the cheapest open item. Read `LivingState` on a
  bot pawn with the player hero as a positive control.
- The duplicate-candidate defect in my fix (§2) — one line, not yet done.
- The wrong-world latch (`World->GameState` NULL) — pre-existing, still unfixed.
