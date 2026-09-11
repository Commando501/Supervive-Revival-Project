# S138 — the LivingState sweep: NOTHING is alive on the force-open route

Written 2026-08-23. Read-only RPM, one staged world, zero `.text` writes.
Tool: `tools/re/livingstate_sweep.py` (new). Predecessor: `docs/s138-flight4-v3-validated.md` §2,
whose reading had a FAILED positive control and was correctly recorded as uninterpretable.

---

## 0. HEADLINE

**[M] The enum is `ELivingState`, resolved LIVE, and `0 = ELivingStateDead`.**
**[M] EVERY live character on this route reads DEAD — 6 of 6, twice, 25 s apart, identical.**
That includes the **player hero**, which is possessed by a real `BP_LokiPlayerController_Dev_C`,
walks, and animates.

⇒ **Flight 4's [I] becomes [M] for this route: the bot is NOT specially gated — the whole world
is.** `bCharacterControllable = (LivingState==Alive) && !IsStunned` is false for *everyone* because
nothing is Alive, and **`IsStunned` is irrelevant**: the first conjunct already fails.

⇒ *"Why is the bot inert?"* was the wrong question, and it is now retired.

---

## 1. THE ENUM — settled by reading it, not by guessing

Flight 4 guessed `ELokiLivingState`, which occurs **0 times** in the image (controls: `ERoundPhase`
12, `ELokiActivityState` 7), leaving two candidates and no way to choose. The sweep resolves it live
off **`FEnumProperty::Enum` at `*(prop+0x78)`** [FK-14 measured offset]:

    ELivingState        (on all 36 LokiCharacter-chain objects)

with the value table read offline from the UHT `{const char* Name; int64 Value}` pairs:

    ELivingState:  ELivingStateDead=0   ELivingStateAlive=1   ELivingStateKnocked=2   Count=3

⇒ **`LivingState = 0` is `ELivingStateDead`.** The other candidate (`EPlayerLivingState`, where
`NoCharacter=0`, `Alive=3`) is **not** the one this property uses — a real disambiguation, not a
coin-flip that happened to agree.

---

## 2. THE SWEEP

Deliberately over the whole `LokiCharacter` chain, **not just heroes** — restricting to heroes would
have re-created flight 4's failure, where every sample came from the same family and no control
existed. A minion, spectator or CDO reading Alive would have settled it instantly.

| | count | `LivingState` |
|---|---|---|
| **LIVE** `LokiCharacter`-chain objects | **6** | **0 (Dead) × 6** |
| CDOs / archetypes | 30 | 0 (Dead) × 30 |

The 6 live objects are: the **player hero**, ARM D's three spawned pawns, ARM E's `SpawnBot` pawn,
and `botspawn`'s Blueprint-route pawn — i.e. every distinct way this project knows how to put a
character in this world.

**Stability:** two full sweeps 25 s apart, `diff` of the LIVE rows **IDENTICAL**. This is not a
single-moment artifact.

★ **The CDO row is the mechanism, not a footnote.** All 30 shipped class defaults are also `0`.
So `Dead` is the **default**, nothing has to set it — and something must actively set `Alive`.
On the force-open route that something never runs, which is exactly what FK-1's stripped
`SpawnPlayer` predicts. The observation and the known wall agree without needing a new hypothesis.

---

## 3. ⚠⚠ THE HONEST LIMITS — read these before quoting the headline

**L1. THERE IS NO POSITIVE CONTROL, AND I COULD NOT MANUFACTURE ONE.** Nothing in the process reads
non-zero, so I cannot demonstrate that the probe would *discriminate* an Alive value if one existed.
What IS established about the instrument: the by-name resolve **AGREES with the independently
recorded `+0x1090` on 36/36 objects**, the enum type resolved live, and flight 4's completely
separate tool (`obj_scalars.py`) read the same value on the same field. So the read mechanism is
sound; what is missing is a known-non-zero sample. **Treat "every character is Dead" as measured for
this route and NOT as proof that the probe can see Alive.**

**L2. `IsStunned` was never read.** No such property surfaced (`obj_scalars` found only
`SlamPendingTotalStunDuration = 0.0`, on both bot and player), so it is likely a function or a
gameplay-tag query rather than a field. **This does not weaken the conclusion** — with
`LivingState != Alive` the AND is false regardless — but the second conjunct remains unmeasured and
must not be claimed either way.

**L3. ONE WORLD, ONE ROUTE.** This says nothing about a real match. It is a statement about the
force-open staged tutorial, which is the only route this project can reach.

**L4. It does NOT identify what would set `Alive`.** That is the open question this creates.

---

## 4. WHAT THIS CHANGES

- **Retires** "why is the bot's LivingState wrong" — it isn't the bot's.
- **Explains** Q2's `bCharacterControllable = 0` completely, and explains it for the *player* too,
  which nothing previously did.
- **Predicts**, falsifiably: any future character spawned on this route by any means will also read
  `Dead` until whatever sets `LivingState` is made to run. A spawn method that produced an Alive
  character would refute this and would be a significant find.
- **Reframes the next question** to: *what writes `LivingState`, and is that writer reachable?*
  That is an offline disassembly question — find the writers of `+0x1090` on `LokiCharacter`, grade
  them fold/REAL/DARK exactly as the `TeamStates` sweep did, and check whether any is reachable on a
  client. The `TeamStates` precedent says the honest prior is that the writer is a stripped
  server-authority stub; the honest position is that this has **not been checked**.

⚠ Do NOT jump from here to "so the bot would work if it were Alive." Making a character Alive is
unproven to be sufficient for anything, and `ServerSetHeroClass` / `SetPlayerTeam` remain stripped
folds regardless.

---

## 5. ARTIFACTS

| path | what |
|---|---|
| `tools/re/livingstate_sweep.py` | the probe; carries its own rationale, controls and honest-verdict text |
| `docs/s138-f5-sweep-BASELINE.txt` | bare staged world (1 live: the player hero) |
| `docs/s138-f5-sweep-POPULATED.txt` | **after both arms — 6 live, all Dead** |
| `docs/s138-f5-sweep-RESAMPLE.txt` | +25 s, LIVE rows byte-identical |
| `docs/s138-f5-marker-premade.txt` | v3 ARM E on this client |
| `docs/s138-Loki-flight5.log` | client log |

★ Incidental: **v3's `G3/G4 GameState candidates: 1` reproduced a second time** on a different
client, so the duplicate-candidate fix is now confirmed twice.

Client ended in FK-32 after the reads were taken, as every S137/S138 sitting has.
