# S138 session prompt — LIVE FLIGHT FIRST

Copy everything below the line into a fresh Claude session.

---

Continue the SUPERVIVE revival project. **This session opens with a LIVE FLIGHT, not offline work.**
Everything needed is already built, committed and pre-registered; the job is to fly it and read it.

**Read `docs/s138-ARME-PREREGISTERED.txt` FIRST — it is the flight plan, and it must not be edited
after the flight.** Then `docs/next-session-prompt-s138.md` §0 for state and §3 for traps. The
CORRECTIONS block of `docs/s137-playerstate-and-lokibot-settled.md` governs any S137 claim.

## The two questions this sitting answers, in one staged client

**Q1 — does `SpawnBot`'s PREMADE path run?** The Loki bot pipeline has always died at
`SpawnBot → MakeNewBotController → the stripped getter 0x55636BB → null controller → Possess
skipped`. [M] a non-null `PremadeBotController` short-circuits at `0x556DAA4` **before** that call.
S137 can now manufacture the argument: ARM D makes an `ALokiBotController` that possesses a hero,
ARM B gives it the `BP_LokiPlayerState_C` that `SpawnBot` consumes from `+0x3C0`.

**Q2 — does the bot MOVE?** `ALokiBotController::Tick` has exactly one motion driver, a random
wander, gated on `Blackboard != NULL` (**already measured satisfied**) and on a blackboard bool
mirrored at `controller+0x6A0`. Never measured. S137 tried and got an instrument artifact.

Both are answerable from ONE staged world, because ARM D runs in both arms.

## Flight order — do it in this order, it is deliberate

```powershell
# ELEVATED PowerShell. Steam must already be running (it is; PID 6908 at handoff).
cd "G:\git\Supervive Revival Project"
Copy-Item docs\capture.log docs\capture.log.pre-s138 -ErrorAction SilentlyContinue
$env:AGS_ARM_QUEUE='arm'; $env:AGS_ARM_QUEUE_DELAY='8s'; $env:AGS_ARM_QUEUE_QUEUES='bots'
.\configs\launch-redirect.ps1 -NoHook
```
It returns promptly (the shipping exe detaches). **Settle gate: uptime ≥ 125 s AND ≥1
`TryUIReady SUCCESS` AND ≥1 `LobbyV2_Persistent` map load** in
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`. Then arm the queue (the persisted
`targetQueueId` is already `bots`):

```bash
curl -X POST -A "s138-arm-NOT-THE-GAME" http://127.0.0.1:8080/party/parties/party-9b9d2c887e2524f918e383a895f2f1c2/joinQueue
```
Confirm `MatchID` non-empty at `/core-game/players/9b9d…` and a `GET /core-game/matches/` in
`docs\capture.log`. Then stage the world **without a probe**, so staging is decoupled from the
injection decision:

```powershell
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_spawnbot_readonly.dll -Label s138 -AllowStale -SkipProbe
```
Wait for **`[SP] done step=4 spawnedPawn=0x… cls=BP_HERO_Ronin_C`** in
`docs\tutorial-launch-marker.txt`. Then inject by hand, re-using the same staged client:

```
tools\inject\inject.exe mmap <PID> "G:\git\Supervive Revival Project\tools\sigbypass-mod\build\tutorial_launch_spawnbot_readonly.dll"
```

1. **`spawnbot-readonly` first** (`a6cad1bb25f78c52`). It runs ARM D + every ARM E gate and **calls
   nothing** — it tells you for free whether the flight would work. Wait for **`[BS] done`**, then
   check **`called=`**.
2. **Read Q2 now**, while a live `LokiBotController` exists:
   `python tools/re/playerstate_readout.py <PID> <BASE>` — it prints the motion chain
   (`+0x6A0` gate · `+0x602` force-off · `+0x658` direction · pawn `+0x418` motor output) plus the
   components and the PlayerState pair, and it carries its own positive control (the player's real
   possession). Sample it **twice, ~8 s apart**.
3. **`spawnbot-premade` second** (`ec6ca40c8b46297a`), into the same client.
4. **`dumpimage` afterwards EITHER WAY** — the two page receipts are the strongest evidence and are
   only recoverable from a capture:
   `tools\usmapdump\usmapdump.exe dumpimage SUPERVIVE-Win64-Shipping.exe dumps\s138-arme`
5. `python tools/re/obj_by_chain.py <PID> <BASE> =LokiBotController all`

## The readouts that decide it

| read | meaning |
|---|---|
| `0x5556D50` page 0/4096 → non-zero | ★★ execution passed the PlayerState gate — where FK-22's route has **never** reached |
| `0x55667F0` page 0/4096 → non-zero | ★★ `Possess` ran on our premade controller (`OnUnPossess`, dark in every image) |
| `LokiHeroCharacter`-chain census delta | the primary verdict for the spawn — **not** the return value |
| `controller+0x6A0` | the gate on the only motion driver. FALSE ⇒ inert BY GATE, not by defect |
| `controller+0x658` / `pawn+0x418` | direction / motor output — separates "not driving" from "driving but not moving" |

⚠⚠ **A non-null return with `0x5556D50` STILL DARK means execution did NOT pass the PlayerState
gate** — the interesting half did not run, whatever the return says. Check the page before claiming
anything about the wall.

## Traps that would burn the launch

1. **Wait for `[BS] done`, then read `called=`.** S136's flight 1 printed a clean `0/0/0` census
   under a confident VERDICT and was a **no-op**. A census delta with `called=0` is UNINTERPRETABLE.
2. **Do NOT rebuild before flying.** The arms are built, archived in `dumps/s138-arms/` and their
   digests are in the pre-registration. If you must rebuild, diff the digest — `botai` must stay
   `5e47c13cf7f0a158`, and an A/B against a copy of itself has burned a live run here before.
3. **Capture as you go.** Both S137 sittings ended in FK-32 (`0x0000DEAD`) protector kills, at the
   6th manual-map/1144 s and the 4th/334 s. No dose-response — do not plan an "injection budget",
   just read out after every step.
4. **Do not `tee` over an evidence file.** S137 destroyed one that way.
5. **Every probe must refuse when the process is dead.** S137's throwaway movement probe printed
   `UNREADABLE` for a dead client and it read like a null. `playerstate_readout.py` has the check.
6. `usmapdump dumpimage` needs the **`.exe` suffix**; without it it prints "process not found" while
   the game is alive.
7. The stager's `-N-probe-` marker copy is taken at injection and holds only the header; the full
   ladder is in the live `docs/tutorial-launch-marker.txt`, and **every injection truncates it**
   (FK-25) — snapshot it after each step.

## If the client dies before you get a result

Say so plainly and re-launch; that is normal here, not a failure. The offline queue if you'd rather
not spend another launch immediately is in `docs/next-session-prompt-s138.md` §4, plus: read the
`ULokiCharacterGlobals` CDO fields (`HeroBotBehaviorTree @0x240`, `BotCheatEffects @0x320`) to settle
whether the bot is *configured* to get abilities and effects at all — [M] the GameplayEffect apply at
`0x4467B90` never executed in S137, and the two candidates (empty `BotCheatEffects` vs a NULL ASC at
`hero+0xF00`) are discriminated by two RPM reads.

## Scope discipline

⛔ Even on full success this is **not a complete bot**. `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`)
and `SetPlayerTeam` (`0x556DE53 → 0xF7EB60`) are stripped folds and stay that way. Say *"SpawnBot ran
its premade path"* — never *"the bot spawner works"*.
⚠ ARM E is **NOT call-only**: 7 non-stack writes across four objects. It is a diagnosis, not a
shipping fix, and it must not go into the default shim set.
