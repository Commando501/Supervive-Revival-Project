# S138 flight 1 — results, and why ARM E could never have fired

> ⚠ **SUPERSEDED IN PART — read `docs/s138-flight2-arme-fired.md` and its CORRECTIONS BLOCK (§2b).**
> Flight 2 applied this file's proposed fix (decrypt the page by running the BP wrapper first),
> **6/6 pre-registered predictions hit**, and ARM E then FIRED. §1 of this file (the G6 /
> demand-decryption blocker) STANDS and is the load-bearing result. §7 item 1 is DONE.
> ⚠ §2's Q2 finding stands and was reproduced (n=2, two clients), **but note the sibling control
> added in flight 2: `ControlInputVector = 0` on the player's own pawn too, so that field alone does
> not discriminate — the GATE at `+0x6A0` is what carries it.**

Written 2026-08-21, immediately after the flight, from the artifacts. The pre-registration
`docs/s138-ARME-PREREGISTERED.txt` is UNEDITED, as required; this is the write-up beside it.

## 0. HEADLINE

**Q2 IS ANSWERED: the `ALokiBotController` does NOT move, and it is inert BY GATE, not by defect.**
**Q1 IS NOT ANSWERED, and could not have been: ARM E's G6 gate is UNSATISFIABLE BY CONSTRUCTION
in a live process — `SpawnBot 0x556D910` is `PAGE_NOACCESS` until it has EXECUTED, and G6 READS it.**

That second finding is worth more than the flight it cost. Re-flying the same arm, in any world,
on any launch, refuses identically. It is not bad luck and it is not a staging problem.

## 1. ★★★★★ ARM E's G6 GATE CANNOT PASS ON A COLD PAGE — [M], external, 3 passing controls

`tutorial_launch.cpp:15291`:

    uintptr_t fn = g_modBase + PS_RVA_SPAWNBOT;          // 0x556D910
    if(!SafeReadable((void*)fn,16)){
        Marker("[PS] ARM E REFUSED at G6: target unreadable.\r\n"); g_psSbRefused=1; return; }

and `SafeReadable` (`:407`) returns false for `PAGE_NOACCESS`.

MEASURED live (read-only `VirtualQueryEx` + RPM, PID 19948, base `0x7FF7A8B30000`):

| target | Protect | readable | first 16 bytes |
|---|---|---|---|
| **`SpawnBot 0x556D910`** | **NOACCESS** | **NO** | -- |
| `0x5556D50` (E5 page receipt) | NOACCESS | NO | -- |
| `OnUnPossess 0x55667F0` (E6 receipt) | NOACCESS | NO | -- |
| `MakeNewBotController 0x5563660` (CONTROL) | EXECUTE_READ | YES | `4055564154415541564157488dac2408` |
| `OnPossess 0x5565470` (CONTROL) | EXECUTE_READ | YES | `4055564157488d6c24d04881ec300100` |
| `SpawnAIFromClass 0x4631C50` (CONTROL) | EXECUTE_READ | YES | `405341544155415641574881ecf00000` |
| `AController::Possess 0x36E2B60` (CONTROL) | EXECUTE_READ | YES | `48895c242055565741564157488d6c24` |

Three controls read fine in the same pass, so this is a property of the target, not the instrument.

**MECHANISM:** the protector demand-decrypts `.text` **on EXECUTE**. A READ of a never-executed page
faults as `NOACCESS` and does not trigger decryption. `SpawnBot` has never run in this process, so
its prologue is unreadable, so a signature check on it can never pass. Chicken-and-egg.

⚠⚠ **AND THIS IS A GENERAL TRAP, NOT A ONE-OFF.** Any future arm that validates a NEVER-EXECUTED
raw impl by reading its prologue has the same defect. Vtable-slot validation (ARM B) and
prologue-signature validation (ARM C) both work *because those functions had already run*.

⚠ **`merged12`/`merged13` grading `0x556D910` "LIT" is NOT a statement about any live process.**
The merged image is a UNION across process lifetimes; it is lit there because **S135's own
`botspawn` flight decrypted it** (CLAUDE.md records exactly this: "our own flight decrypted it,
along with `SpawnBot` and `FindValidPositionForCharacter`"). **Offline LIT does not imply live
readable**, and this is the first time that distinction has bitten an arm.

### THE FIX, and it needs no code change

`Comp_BP_BotSpawner_C::SpawnClassBotAtLoc` calls `SpawnBot` internally (with `EX_NoObject` in the
premade slot). So **injecting `tutorial_launch_botspawn.dll` first EXECUTES `SpawnBot`, decrypting
page `0x556D000`**; `spawnbot_premade` injected afterwards then finds G6 readable and can validate
and fire. Order: `gft -> fo -> sp -> botspawn -> spawnbot_premade`.
Verify between the two with the read-only page probe above — it is free and decisive.

⚠ Minor arm defect: the `target unreadable` branch does not set `g_psSbWhy`, so the summary prints
`why=(unset)` rather than naming the gate. The `[PS] ARM E REFUSED at G6` line carries it.

## 2. ★★★★★ Q2 — THE BOT DOES NOT MOVE, AND IT IS GATED SHUT

One staged tutorial world, `spawnbot_readonly` injected. Read externally by
`tools/re/playerstate_readout.py` (read-only RPM), **timestamped 2026-08-21 19:57**:

    LokiBotController 0x2548F887120
      bCharacterControllable        +0x6A0 = 0    <- THE GATE on the ONLY motion driver
      ForceCharacterNotControllable +0x602 = 0    <- NOT forcing it off
      RandomMoveDirection           +0x658 = (0,0,0)  |v|=0
      pawn ControlInputVector       +0x418 = (0,0,0)  |v|=0

Per the S138 transcription of `ALokiBotController::Tick`, the sole motion driver is a random wander
gated on `Blackboard != NULL` (satisfied — the component exists, see §3) **and** on
`bCharacterControllable`. That gate is `(LivingState==Alive) && !IsStunned`, forced FALSE by
`ForceCharacterNotControllable (+0x602)`.

**`+0x602 = 0`, so nothing is forcing it — the underlying `(LivingState==Alive) && !IsStunned` is
itself false.** The wander block never runs. All three reads agree: gate 0, direction 0, motor 0.

⇒ **The bot is inert BY GATE, not by defect.** That is exactly the pre-registered discrimination,
and it points the next work at LivingState, not at the behaviour tree.

⚠ **SCOPE: n=1 sample.** The pre-registered second sample ~8 s later could NOT be taken — the client
was killed by FK-32 in between, and the probe **correctly refused** (`OpenProcess(19948) failed --
err 87. RUN IS VOID.`) rather than printing an artifact. That refusal is the S137 defect fixed and
working as designed. The GATE reading is structural rather than phase-dependent, but a second sample
is still owed; `RandomMoveDirection` re-randomises every 2.0 s, so its zero alone would not carry it.

## 3. ARM D + ARM B + ARM C REPRODUCED IN A FIFTH CLIENT

Two-sided within-run control, all three controllers spawned by the same code within milliseconds:

| | ctrl A `AIController` | **`LokiBotController`** | ctrl C `AIController` |
|---|---|---|---|
| PlayerState (ctl `+0x3C0`) | NULL | **`BP_LokiPlayerState_C`** | NULL |
| PlayerState (pawn `+0x3D8`) | NULL | **same object** | NULL |
| BrainComponent `+0x498` | NULL | **`BTComponent`** | NULL |
| Blackboard `+0x4B0` | NULL | **`BlackboardComponent`** | NULL |
| PerceptionComponent `+0x4A0` | NULL | NULL | NULL |
| PathFollowing / GameplayTasks | present | present | present |

Handshake and PlayerState-match confirmed on both sides for all three. Positive control (the player
hero possessed by `PC_MainMenu_C`) passed in the same run. Chain:
`LokiBotController <- LokiAIController <- AIController <- Controller <- LokiActor <- Actor <- Object`.

## 4. FK-31 / FK-32 THIS SITTING — 4 launches, 1 armed window

| attempt | outcome |
|---|---|
| 1 | **FK-31** protector kill during staging (only `gft`+`fo` resident). Dump archived. |
| 2 | **FK-31**, same. Dump archived. |
| 3 | **STAGED OK**, readonly injected, results above; then **FK-32** (silent `0xDEAD`, no artifact) on the 4th manual-map |

**Both FK-31 dumps classified [M]:** `0xC0000005`, `ExceptionInformation[0]==8` (EXECUTE), faulting
address **`0x7FFB57400001`** in BOTH, `addr & 0xFFF == 1`, no module covers it,
MemoryInfo `MEM_IMAGE / READONLY / AllocationBase == addr-1`. Era 3 of the three known values.

★ **NEW, and it upgrades a recorded finding:** `preloader.dll` MOVED between the two launches
(`0x7FFB4C9F0000` -> `0x7FFB4C7C0000`, delta `0x230000`) while the kill address did not move one
bit — **S131's per-boot-constant signature demonstrated WITHIN a matched pair, with ASLR as the
internal control.**

★ ~~**NEW INSTRUMENT:** the crashpad `MemoryInfoListStream` (stream 16) … **a third, purely offline
route to the protector signature in the Sentry corpus**~~
⚠⚠ **RETRACTED 2026-08-23 — see `docs/s138-offline-followup.md` F3.** Two things are wrong:
**(i) the lookup CAN NEVER MISS** — stream 16 **tiles the entire user address space** (0 gaps,
`0x0 → 0x7FFFFFFF0000`, ~12,644 `MEM_FREE` entries per dump), so "an entry covers the fault" is
**vacuous**; a fabricated address gets a hit too. **Only the SHAPE discriminates.**
**(ii) it carries NO MODULE NAME** — it can only say `RIP == <an unnamed MEM_IMAGE allocation of
0x4066000> + 1`. The name `runtime.dll` still comes from the UECC ModuleList and S131's live read,
so this is a **joint inference, not an independent route to the name.**
★ And the shape alone is not a kill either: **34/34** non-kill crashpad dumps carry the identical
`MEM_COMMIT/READONLY/MEM_IMAGE/EXECUTE_WRITECOPY/0x7000` region at their boot's kill address — the
protector is *always* mapped. **The FK-31 evidence is the CONJUNCTION**: an EXECUTE fault whose
address lands inside it.
★ What IS sound: the conjunction now holds at corpus scale (**368/368** files, zero exceptions), and
the crashpad stream carries **both** `runtime.dll` mappings (LOW invariant `0xFF760000`, 10 regions;
per-boot HIGH, 15 regions totalling `0x4066000`) — previously known only from `dumpimage` manifests.
⚠ LOW is present in **126/127** reports, not all — consistent with CLAUDE.md's own 123/124.

★ **[I] -> [M]:** `LastBootUpTime = 2026-08-19 13:46:45 UTC`, no reboot since; every
`0x7FFB57400001` crash falls inside that one boot session. "Per boot" was recorded as inferred.

★ Era-3 corpus count updates from S133's **8 files / 5 reports** to **14 files / 8 reports**.

⚠ **A framing error of mine, corrected by the classifier:** I read the two deaths' "9 s after `fo`"
as identical and therefore systematic. World-up happens a fixed time after `fo`, so ANY death in
that phase reads ~9 s — it is not independent evidence. The true world-up->crash times differ
(**3.11 s vs 1.83 s**), and two-in-a-row at the documented 27 % base rate is **p = 0.073**, ordinary.
Do not call FK-31 systematic before a fourth consecutive death (p = 0.005).

⚠ The FK-32 death came on the **4th** manual-map, matching S137 flight 4 exactly (4th). Across the
four recorded `0xDEAD` kills the counts are 7 / 6 / 4 / 4 — still **no dose-response**.

## 5. PRE-FLIGHT VERIFICATION (offline, before any launch)

- **Digests 8/8** match the pre-registration under BOTH recipes; **0 duplicate groups**;
  `spawnbot_premade` vs `spawnbot_readonly` differ at **119,120 of 134,656** overlapping `.text`
  bytes (first difference at offset 14, a real `0x1000` code-size shift). Regression gate `botai`
  `5e47c13cf7f0a158` unchanged. Archived copies byte-identical to `build/`.
- **Call site, from the binary, not the source's intent:** the premade arm contains a 7-argument
  `call r15` with r15 provably `g_modBase + 0x556D910` (only two writes to r15 between its
  initialisation and the call); the readonly arm has **no** indirect call at that site, while the
  `Sleep(300)` IAT call in the SAME binary proves the indirect-call detector is live there.
  Banners mutually exclusive; positive control in every row. **Not a repeat of the S135 dead arm.**
- ⚠ **The `0x556D910` constant is a TRAP as a call test** — it reads **2 in BOTH** spawnbot arms
  (the G6 gate's `mov r15d, 0x556d910`, and a `Markerf` "rva=0x%llX" argument). It cannot
  discriminate a calling arm from a non-calling one. Use the call site, not the constant.
- ⚠ **RAW is strictly COARSER than VIRTUALSIZE**, refuting the repo tool's own printed claim that
  the two recipes "induce the SAME equivalence relation". Counterexample on a real arm: growing
  `.text` VirtualSize into the all-zero pad leaves RAW **identical** while VSIZE changes.
  VSIZE-merge implies RAW-merge, never the converse. Over 170 real `build/` DLLs the partitions do
  coincide, so no recorded gate is affected — but RAW is the weaker duplicate detector.

## 6. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-marker-staged-sp.txt` | the staged world (`[SP] done step=4`, `BP_HERO_Ronin_C`) |
| `docs/s138-marker-readonly.txt` | the readonly arm: G1-G5 pass, **G6 refuses**, ARM D census |
| `docs/s138-Loki-flight1.log` | the client's own log for the armed window |
| `docs/capture.log.s138-flight1` | wire evidence (+ `.s138-attempt1-armevidence`, `.s138-attempt2`) |
| `dumps/crashpad-20260821-194515-s138-fk31-staging-death` | FK-31 dump A (41.6 MB, sha verified) |
| `dumps/crashpad-20260821-194917-s138-fk31-death2` | FK-31 dump B (43.9 MB, sha verified) |

## 7. WHAT IS STILL OPEN

1. **Q1 — does `SpawnBot`'s premade path run?** Unchanged and untested. The route is now known:
   decrypt the page with `botspawn` first, then fly `spawnbot_premade`.
2. **Why is `bCharacterControllable` false?** Read `LivingState` on the bot pawn and compare against
   the player hero as a positive control. That is the next question for "does the bot act", and it
   is a read, not an arm.
3. The pre-registered **second movement sample** is still owed.
