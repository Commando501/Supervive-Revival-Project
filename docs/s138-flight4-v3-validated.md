# S138 flight 4 — v3 validated (5/5), and a LivingState read whose control failed

Written 2026-08-23 from the artifacts. Pre-registration: `docs/s138-f4-PREREGISTERED.txt` (UNEDITED).
Predecessors: `docs/s138-flight3-divert-settled.md`, `docs/s138-latch-fix-rebuild.md` §7.

---

## 0. HEADLINE

**The duplicate-candidate fix works: 5/5 pre-registered predictions hit, including the
discriminating one.** And a bonus attempt at the cheapest open item produced a **[M] measurement
with a FAILED POSITIVE CONTROL** — which makes it uninterpretable as stated, but points somewhere
more interesting than the question it was asked about.

---

## 1. ★★★★★ v3 VALIDATED IN FLIGHT — 5/5

    [PS] G3/G4 GameState candidates: 1   (EXACT chain match on 'LokiGameState')
    [PS]   gsCand[0] 0x24DFCA260A0 'BP_LokiGameState_Tutorial_C'  TeamStates Data=0x0 Num=0
    [PS]      chain: BP_LokiGameState_Tutorial_C<-BP_LokiGameStateRounds_C<-BP_LokiGameState_C<-
    [PS]             BP_LokiGameState_Code_C<-LokiGameState_AS<-LokiGameState<-LokiGameStateBase<-
    [PS]             GameStateBase<-Info<-LokiActor<-Actor<-Object
    [PS]   World->GameState = NULL or unreadable -- falling back to the census.

| # | prediction | result |
|---|---|---|
| **D1** | **`candidates: 1`** (flight 3 read **2**, both the same pointer) | **HIT** |
| D2 | exactly ONE `gsCand`, `BP_LokiGameState_Tutorial_C`, chain has an exact `LokiGameState` element | **HIT** |
| **D3** | **NO `AMBIGUOUS` line** (flight 3 emitted a false positive) | **HIT** |
| D4 | `LokiGameStateUAVComponent` still absent — the v2 latch fix must not regress | **HIT** |
| D5 | `TeamStates Data=0x0 Num=0` | **HIT** |

★ D1/D3 are the discriminating pair and both moved in the predicted direction. The standalone
10/10 logic test written before the flight was **predictive of live behaviour** — cheap, and it is
what turned "I think the dedupe is right" into a checked claim before spending a launch.

★ ARM E itself reproduced unchanged for the **fourth** time: G6 signature matched, `called=1
faulted=0`, `ReturnValue=0x24C1DB65580 'BP_HERO_Ronin_C'`, and the premade controller re-possessed
it (`was 0x24D1858AAC0 before`). `botspawn` decrypted `SpawnBot` again (prologue exact).

⚠ **Still unfixed, pre-existing:** `World->GameState = NULL or unreadable` again. The wrong-world
latch from S137 remains; the fallback handled it and announced itself, which is the designed
behaviour, but the underlying selection defect is untouched.

---

## 2. ⚠⚠ THE LivingState READ — [M] VALUES, FAILED CONTROL, HONEST VERDICT

Q2 established [M] over three clients that the `LokiBotController` is inert **BY GATE**:
`bCharacterControllable (+0x6A0) = 0` while `ForceCharacterNotControllable (+0x602) = 0`, so nothing
is forcing it and the gate's own term `(LivingState==Alive) && !IsStunned` is false. The open
question was *which term*. This flight read it, with the player hero as the pre-registered control:

| object | | `LivingState` (+0x1090, EnumProperty) |
|---|---|---|
| BOT pawn `0x24C1DB65580` | `BP_HERO_Ronin_C` | **0** |
| PLAYER hero `0x24DA09E5580` | `BP_HERO_Ronin_C` | **0** ← the POSITIVE CONTROL |

Enumerator values read from the UHT `{const char* Name; int64 Value}` tables in
`dumps/s138-f3/…dump.exe` (ImageBase `0x7FF6EE290000`, fileoffset == RVA):

    EPlayerLivingState:  NoCharacter=0  Dead=1  Knocked=2  Alive=3  Count=4
    ELivingState:        ELivingStateDead=0  ELivingStateAlive=1  ELivingStateKnocked=2  Count=3

⇒ **[M] Under EITHER candidate enum, `0` is NOT "Alive".**

⇒ ⚠⚠ **AND THE CONTROL FAILED — so this does NOT answer the question it was asked.**
The pre-registration said (L2, written before the flight):
> *"The player hero is possessed and alive, so if the probe cannot show a sane value THERE, any bot
> reading is UNINTERPRETABLE rather than a null."*
The player hero reads the same `0`. **By my own rule, the bot's value is uninterpretable as a
statement about the BOT.** My prediction L3 — that the bot would differ from the player — is
**FALSIFIED**, and the pre-registered alternative branch applies.

★★ **BUT THE FAILED CONTROL IS THE MORE INTERESTING RESULT, AND IT REFRAMES THE QUESTION.**
The player hero in this world is possessed by a real `BP_LokiPlayerController_Dev_C`, walks, and
animates (S108b) — yet it is **not marked Alive either**. The likeliest reading is that **nothing in
a force-open staged world is ever marked Alive**, because whatever sets `LivingState` lives in the
spawn/round flow that FK-1's stripped `SpawnPlayer` never runs. If so, the bot is **not specially
gated — the whole world is**, and "why is the bot inert" was the wrong question.
**Grade: [I]. It is a hypothesis the data is consistent with, not a measurement.**

### ⚠ WHAT IS NOT RESOLVED, AND MUST NOT BE PAPERED OVER
- **Which enum `LokiCharacter::LivingState` actually uses.** `ELokiLivingState` — the name I
  guessed — occurs **0 times** in the image, against passing controls (`ERoundPhase` 12,
  `ELokiActivityState` 7), so that guess is simply wrong. Two candidates exist and a UHT
  params-adjacency scan did not place either enum's name pointer within ±0x180 of the
  `LivingState` property-name pointer. **`0` is not-Alive under both, which is why the conclusion
  survives the ambiguity — but the enum identity is OPEN.**
- **Whether `IsStunned` is also false.** Not read. The gate has two terms and only one was sampled.
- Everything above rests on **one sample per object, in one world**.

### THE CHEAP NEXT CHECK, and it is now a different check
Not "why is the bot's LivingState wrong" but **"is ANY character ever Alive on this route?"**
Sample `LivingState` on every `LokiHeroCharacter`-chain object in a staged world, plus a spectator
if one exists. If the answer is uniformly 0, the [I] above becomes [M] and the bot's inertness is
fully explained by the world, not by the bot. If some object reads Alive, that object is the control
this flight lacked, and the comparison becomes meaningful.

---

## 3. FLIGHT ECONOMY AND ARTIFACTS

Staged on **attempt 1** for the second flight running, with the driver's fixed poll observing
`[SP] done step=4` **12 s** after `stage complete` — the same 12 s that, unpolled, destroyed three
clients in flight 3. Client died afterwards with **no crashpad handoff and no `Fatal`** — FK-32
again, on the 5th manual-map, after every read had been taken.

Arms flown, both from `dumps/s138-arms-v3/`:
`botspawn` RAW `b2203efd62161182` · `spawnbot_premade` RAW `6cb296bbf3c8c696`.

| path | what |
|---|---|
| `docs/s138-f4-PREREGISTERED.txt` | D1–D5 and L1–L3, written before launch, unedited |
| `docs/s138-f4-marker-premade.txt` | **the 1-candidate G3/G4 readout** + ARM E |
| `docs/s138-f4-LIVINGSTATE.txt` | both readings, both enum tables, and the failed-control note |
| `docs/s138-f4-marker-staged-sp.txt`, `-pageprobe-AFTER-botspawn.txt` | staging + page decrypt |
| `docs/s138-Loki-flight4.log`, `docs/capture.log.s138-f4` | client + wire |

---

## 4. STATE

**Closed:** the duplicate-candidate defect (validated in flight, 5/5). The divert (flight 3). The
TeamStates route (offline). The G6 demand-decryption blocker (flight 2).

**Open:** the wrong-world latch (`World->GameState` NULL, pre-existing S137). Which enum
`LivingState` uses. Whether *anything* is Alive on the force-open route — now the cheapest and
best-shaped question on this surface. `IsStunned` unread. And FK-22 proper is untouched:
`ServerSetHeroClass` / `SetPlayerTeam` remain stripped folds.

⛔ Still not a working bot.
