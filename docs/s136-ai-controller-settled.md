# S136 (2026-08-21) — AN AI-CONTROLLED HERO PAWN EXISTS (it is NOT a bot)

**One line: `UAIBlueprintHelperLibrary::SpawnAIFromClass` spawns a `BP_HERO_Ronin_C` and tail-calls
`APawn::SpawnDefaultController` (vtable slot 280 = `0x3BBF3C0`), which constructs a GENERIC ENGINE
`AAIController` and possesses it — bypassing `MakeNewBotController`'s stripped getter entirely. The
possession handshake is bidirectional, that function was all-zero in the union of every image this
project has ever captured, and the result reproduced twice in one client with no `.text` write.**

⚠⚠ **SCOPE, up front: this is NOT a Loki bot.** `AIControllerClass` is the engine default on the
player hero too; `PlayerState`, `BrainComponent`, `Blackboard` and `PerceptionComponent` are all
NULL; there are **zero** `BotController`-derived objects in the process; and the
`MakeNewBotController → BotController → ServerSetHeroClass / SetPlayerTeam` pipeline is untouched.
**Never write "the bot spawner works".**

⚠⚠ **AND THE ARM THE SESSION WAS HANDED COULD NEVER HAVE DONE THIS.** The shipped
`tutorial_launch_botai.dll` was **statically incapable of making its call** — clang dead-code-
eliminated `BsCallAI()` — and its own runtime verdict blamed the wrong thing. The first flight was a
no-op that *looked* like a clean P1 null. **Read §2 before anything else.**

---

## ⚠⚠ CORRECTIONS — THIS BLOCK GOVERNS THE REST OF THE FILE

Written after an adversarial verification pass (4 refutation lanes + adjudication) that went back to
the primary artifacts. **Where this block and the body disagree, this block wins.**

**C1. THE HEADLINE IS RESCOPED: this is an AI-CONTROLLED HERO PAWN, NOT A BOT.**
[M] `APawn::AIControllerClass @+0x3D0` reads the **engine default `AIController`** on both spawned
pawns **and on the player hero**. [M] `obj_by_chain BotController` = **0 LIVE** (CDO present as a
passing search-term control). `MakeNewBotController → BotController → ServerSetHeroClass /
SetPlayerTeam` is **untouched and still blocked on FK-22's stripped getter.**
⛔ Do not write *"a bot spawned"*, *"the first AI hero in this project's history"* as a bot-pipeline
result, or *"the bot spawner works"*.

**C2. THREE SUPPORTS IN THE BODY ARE REFUTED — do not repeat them.**
- ⛔ **`Z = 90.15` is worthless as a fingerprint** (§1.4). A pawn rests on the floor with or without a
  controller, and S132's number is at a different XY — it is floor flatness. **The strong form is the
  one the body buried:** bot 2 rests ON bot 1, `ΔZ = 266.2508 − 90.1500 = 176.1008 = 2 × 88.0504`
  capsule half-heights.
- ⛔ **`Outer = PersistentLevel` is meaningless** (§1.5) — 98.8 % (1343/1360) of live actors have it.
- ⛔ **"exactly 1 AIController-derived object" is [M] AT TIME T ONLY** — it read 2 minutes later,
  because flight 3 flew. **Timestamp every census.**

**C3. THE DECISIVE "IT IS NEW" EVIDENCE IS NOT IN THE BODY. Three ways, all [M]:**
1. ★★ **`FName.Number` (obj+0x24) is a strictly-DECREASING runtime spawn counter** — 6/6 monotone over
   known-order objects; **AIC#1 `2147470967` < botpawn#1 `2147471035` ⇒ the controller was created
   AFTER the pawn**, from a single post-hoc snapshot. A pre-registered prediction on botpawn#2 hit.
   ⚠ `obj_by_chain.objname()` reads only the ComparisonIndex and **discards the Number** — read obj+0x24.
2. `AIC+0x198 Instigator = the pawn`, written only by `SpawnActor` from `FActorSpawnParameters`;
   `Possess`/`SetPawn` never write it. A controller predating the pawn cannot carry it.
3. The call site `0x4631DD2 cmp [rax+0x400],rbx` / `0x4631DE1 call [rax+0x8c0]` is **guarded on
   `Controller == NULL`**, and `SpawnDefaultController` early-outs on the same test.

**C4. `InternalIndex` IS NOT MONOTONE — refuted from inside this corpus.** AIC#2 was created later
(measured) and has index **172033 < 177838**. §8's warning was right; it is now proven.

**C5. P4's GRADE SPLITS.** The page census is [M] (`0x3BBF000`: **0/4096** non-zero in `merged11`,
**3714/4096** after — reproduced by two verifiers with independently written code; **53 of 55 images
dark, including `dumps/s135-botspawn`**). But *"`SpawnDefaultController` executed"* is **[I] from the
bytes alone** — 4 KiB page granularity, and the function starts `0x3C0` into its page. It is
**[M, strong]** only WITH the `call [rax+0x8c0]` call-site disassembly plus the live possessed pawn.
**Cite both.** ⛔ Do not quote `merged12`'s "51.85 % non-zero" beside a page delta — wrong instrument;
cite **`.text` 16,772 / 30,281 = 55.39 % pages**.

**C6. THREE DOWNGRADES INSIDE §2.**
- ⛔ *"the `KBSARMS`-disabled banner did not print"* is **[S], NOT runtime evidence** — with
  `KBSARMS = 0x0F` the test `if(!(0x0F&0x4))` is constant-folded, so that string is absent **by
  construction**. The conclusion was right; that evidence was invalid. (An instrument artifact
  committed in the very section describing them.)
- ⛔ *"+3,072 is consistent with emitting `BsCallAI`"* is **[I], contaminated** — the single-variable
  cost is **+2,560**; two different source states both land on 111,104.
- ⛔ **Byte-absence is NOT a general string test.** `"SpawnAIFromClass"` is materialised as split,
  out-of-order `movabs` immediates. The method is valid only for LONG strings passed as pointers to a
  non-inlined call — which the 53-byte banner is. And the flight-1 marker (`resolved=1 called=0`) is
  **non-discriminating on its own**; only the byte evidence separates "never compiled" from "compiled
  but `g_bsFn` happened to be 0".

**C7. THE DCE MECHANISM IS NON-UNIQUE.** *"because `g_bsFn` is provably 0"* is true but not
exclusive: **either guard term alone folds constant-true**, shown by build bisection. Do not "fix"
this class of defect by deleting one term.
★ And the stores are unreachable because they sit **after an unconditional `return;`** — not because
of `#else`. "Unreachable under KBSAI" reads as preprocessor removal and is not.

**C8. §4 (the digest section) CONTAINED A FLATLY FALSE CLAIM — see the rewritten §4 below.**

**C9. THREE WORKING-TREE DEFECTS FOUND AND FIXED** (all verified in the rebuilt binary):
`tutorial_launch.cpp` had **two `\\r\\n` over-escapes** in S136's own new verdict block (they would
have printed literal `\r\n` into the marker — in the two lines added specifically to stop a null
being misread); the success VERDICT string still said *"A BOT SPAWNED / BotController +N / from a
STRUCTURAL ZERO baseline"* on a renamed predicate whose A0 read **1**; and the gate-fix comment
attributed deadness to `g_bsFn` alone. Arm is now **`5e47c13cf7f0a158`**.

---

## 0. What was flown

| # | arm `.text` | what happened |
|---|---|---|
| 1 | `0f310c58cd0e0941` (the S135 shipped artifact) | resolved everything, **called nothing** — dead-code eliminated |
| 2 | `7d67ac549ec8b2bf` (guard fixed) | **called** — pawn + controller created; controller found by external probes |
| 3 | `d2d07d5e85dfe4b3` (guard + census predicate fixed) | **called** — arm's OWN census reads `dCtl=+1 dHero=+1`; 7/7 pre-registered predictions hit |

All three into **one** client (PID 43456), one staged tutorial world, reached with
`forceTutorialMatch = false` via a queue-armed MatchID. No relaunch between flights. Risk class
CALL-ONLY: no module-image write, no data poke, no PI hook.

Client health end to end: **0 `Fatal`, 0 crashpad handoffs**, both processes alive throughout
(~23 min uptime at the last read).

---

## 1. THE RESULT

### 1.1 The possession handshake is complete and bidirectional

`obj_props_dump` of the `AIController` at `0x1B3F58BC5E0`:

```
+0x0490 PathFollowingComponent = 0x1B38CCCE080 (PathFollowingComponent)
+0x0498 BrainComponent         = NULL
+0x04A0 PerceptionComponent    = NULL
+0x04A8 ActionsComp            = 0x1B392BA13C0 (PawnActionsComponent)
+0x04B0 Blackboard             = NULL
+0x03C0 PlayerState            = NULL
+0x03F8 Pawn                   = 0x1B3E6922AE0 (BP_HERO_Ronin_C)
+0x0408 Character              = 0x1B3E6922AE0 (BP_HERO_Ronin_C)
+0x0198 Instigator             = 0x1B3E6922AE0 (BP_HERO_Ronin_C)
```

`obj_props_dump` of the pawn `0x1B3E6922AE0` — the **reciprocal**:

```
+0x0400 Controller         = 0x1B3F58BC5E0 (AIController)
+0x0408 PreviousController = 0x1B3F58BC5E0 (AIController)
+0x0150 Owner              = 0x1B3F58BC5E0 (AIController)
+0x03D8 PlayerState        = NULL
```

★★ **`0x1B3E6922AE0` is the exact pointer `SpawnAIFromClass` returned**, printed by the arm as
`ReturnValue` *before* anything looked at a controller. That is a **payload fingerprint** — the same
evidence class as S131's `CurrPodDestination` and S132's landing point: no other code path in the
process knows that value.

★★ **`PreviousController` and `Owner` are written by the possession path**, so `AController::Possess`
(`0x36E2B60`, REAL) **ran** — the exact call S135 measured as skipped on the component route
(`0x556DD34 test rcx,rcx / je`).

⚠ `BrainComponent` / `Blackboard` / `PerceptionComponent` are NULL **and that is expected**: the arm
passes `BehaviorTree = null` deliberately. A controller that exists but does not act is a
**BEHAVIOUR** question, not a spawn failure. Do not conflate them.

### 1.2 P4 — the census-independent offline receipt

`APawn::SpawnDefaultController` at RVA `0x3BBF3C0`, read at file offset == RVA in the cold images:

| function | `merged11` (before) | `s136-botai` (after) | verdict |
|---|---|---|---|
| **`APawn::SpawnDefaultController 0x3BBF3C0`** | `0000000000000000000000` | `405553488d6c24984881ec` | **DARK → DECRYPTED** |
| `AController::Possess 0x36E2B60` (control) | `48895c2420555657415641` | same | lit both |
| `SpawnAIFromClass 0x4631C50` (control) | `4053415441554156415748` | same | lit both |
| fold `0x0F7EB50` (control) | `33c0c34883ec20e8f7ffff` | same | lit both |
| fold `0x0F7EC20` (control) | `c200004c8bdc498943d848` | same | lit both |

★★★ **The baseline is the strongest form available.** `merged11` is the **union of every image ever
captured** by this project, so all-zero there means the page had never been decrypted in *any* prior
process. `.text` decryption is monotone within a process ⇒ zero-before / non-zero-after is proof of
execution. The function whose entire job is to create and possess a default controller **ran for the
first time in this project's history.**

⚠ **`SpawnBot 0x556D910` and `MakeNewBotController 0x5563660` read NON-ZERO in `merged11` and
ALL-ZERO in the fresh `s136` image. That is NOT a contradiction and NOT a bad read** — `merged11` is
a UNION carrying S135's decrypted pages, while `s136` is a single process that never ran the
component route. Comparing a merge to a single image is the wrong test for those two.

Merged to **`dumps/merged12.dump.exe`**: +11 pages, **0 overlap conflicts**.
⛔ **Cite `.text` 16,772 / 30,281 = 55.39 % PAGES, never the manifest's "51.85 % non-zero"** — the byte metric is the wrong instrument beside a page delta (the repo's own standing rule).

### 1.3 Replication with a fixed instrument — 7/7 pre-registered

Predictions written to `docs/s136-flight3-PREREGISTERED.txt` **before** injection:

```
census A0  BotOrAIController-chain=1  LokiHeroCharacter-chain=3     <- INSTRUMENT-FIX RECEIPT
census A1  BotOrAIController-chain=1  LokiHeroCharacter-chain=3     <- stability control PASSED
---- THE CALL: UAIBlueprintHelperLibrary::SpawnAIFromClass ----
SpawnAIFromClass -> ReturnValue=0x1B302F7D560 'BP_HERO_Ronin_C'     <- a DIFFERENT pawn
census A2  BotOrAIController-chain=2  LokiHeroCharacter-chain=4
VERDICT: A BOT SPAWNED.    dCtl=1 dHero=1          <- ⚠ THE ARM'S OWN STRING, AND IT IS FALSE
```

⚠⚠ **The `A BOT SPAWNED` line above is quoted verbatim as the arm's output and is FALSE in both
halves** — its own census row two lines up reads `A0=1`, not a structural zero, and there are
**zero** `BotController`-derived objects in the process. The predicate had been renamed and the
verdict string had not. **Fixed in the source** (§C9); the arm now prints `AN AI-CONTROLLED PAWN
EXISTS` with the scope stated inline.

★★★★★ **`A0 = 1` is the decisive number, not `A2 = 2`.** The *old* predicate read **0** for that very
object, in that very world. Same world, same object, **only the predicate changed** ⇒ the earlier `0`
is an instrument artifact **as a within-world, single-variable measurement**, not as an argument.

### 1.4 The pawns are physically real

Read-only RPM of `RootComponent + 0x158`, three samples 3 s apart, **bit-identical**, `vel = 0`:

```
bot 1  0x1B3E6922AE0 -> (600.0000, 0.0000,  90.1500)
bot 2  0x1B302F7D560 -> (600.0000, 0.0000, 266.2508)
player 0x1B399FF5580 -> (0.0000,   0.0000, 13240.0000)
```

- **X and Y are exactly the requested spawn point** (`heroX + KBSOFFSET(600)`, `Y = 0`).
- **Z is not.** Both were asked for `Z = 13240` and both **fell to the floor**. `Z = 90.15` is the
  exact rest height S132 recorded for a hero capsule settled on the tutorial floor.
- ★ **Bot 2 is resting ON bot 1** — same X/Y, `Δ Z = 176.10` ≈ one capsule. Two solid colliding
  bodies, independently corroborating that these are real physical actors and not phantoms.

### 1.5 Independent census agreement

`tools/re/obj_by_chain.py` (read-only RPM, walks **SuperStruct**, unlike `obj_by_class.py` which
matches the class LEAF name only):

```
NumElements=192379   objects walked (readable class ptr)=155177   CDOs matched and EXCLUDED: 8
found 2 LIVE (non-CDO) instance(s) whose CLASS CHAIN contains 'AIController'
   chain: AIController <- Controller <- LokiActor <- Actor <- Object
```

1 after flight 2, **2** after flight 3 — agreeing exactly with the arm's own census, from a different
instrument with a different matching strategy.

⚠ The chain is `AIController <- Controller <- **LokiActor** <- Actor`, i.e. the game's own actor
hierarchy, not a bare engine `AController`.

---

## 2. ⚠⚠ THE ARM WAS DEAD. READ THIS BEFORE FLYING ANY `#if`-GATED VARIANT.

### 2.1 What flight 1 printed

```
[BS] SpawnAIFromClass fn=0x1B220766590 thunk=0x7FF60D577EC0 cdo=0x1B220AE1520
[BS]   params: WCO@0x0 PawnClass@0x8 BT@0x10 Loc@0x18 Rot@0x30 NoColl@0x48 Owner@0x50 Ret@0x58
[BS] ARGS: pawnClass='BP_HERO_Ronin_C' spawnLoc=(600.0, 0.0, 13240.0) BT=null noCollisionFail=1
[BS] ---- NO CALL: resolve failed. ... Read the REFUSE(...) line above ... ----
[BS] resolved=1 roster=-1 team=-1(player=-999) called=0 faulted=0 refused=0
[BS] botControllers A0=0 A1=0 A2=0 | heroCharacters A0=2 A1=2 A2=2
[BS] VERDICT: the call was never made (KBSARMS gated it off).
```

Everything resolved. **`resolved=1`, `refused=0`, and no `REFUSE(...)` line exists anywhere above.**
`KBSARMS` defaults to `0x0F` (`tutorial_launch.cpp:14130`) — **bit 2 (THE CALL) was SET the whole
time**, and the `THE CALL IS DISABLED by KBSARMS` banner never printed. **The verdict named a knob
that was correct.**

### 2.2 The mechanism [M]

`BsResolve` (`:14441`):

```c
static void BsResolve(uintptr_t hero){
#if KBSAI
    BsResolveAI(hero); return;          // component route never runs
#endif
```

`BsResolveAI` stores into **`g_bsAiFn`** (`:14373`) and **never touches `g_bsFn`**. Every store to
`g_bsFn` (`:14488, 14504, 14518, 14523, 14533, 14563`) and the single store to `g_bsComp` (`:14462`)
lives in the component route — **unreachable under `KBSAI`**.

The dispatch gate at `:14608` read:

```c
} else if(!g_bsResolved||!g_bsFn||!LooksLikePtr(g_bsComp)){
```

`g_bsFn` is a **file-static with no reachable store** ⇒ clang `-O2` proves it is always 0 ⇒ `!g_bsFn`
folds to **constant true** ⇒ the whole `else` branch, containing `BsCallAI()`, is
**dead-code-eliminated**.

★★★★★ **MEASURED, not inferred — the binary's own string table settles it.** In the shipped
`tutorial_launch_botai.dll`:

| literal | belongs to | count |
|---|---|---|
| `THE CALL: UAIBlueprintHelperLibrary::SpawnAIFromClass` | `BsCallAI` branch | **0** |
| `SpawnAIFromClass fn=` | `BsResolveAI` (positive control) | 2 |
| `playerHero/WorldContext=` | `BsResolveAI` (positive control) | 1 |
| `gameMode=0x` / `REFUSE(component)` / `SpawnableBots` / `THE CALL: %s` | component `#else` branch | **0** |

**Neither branch of the `#if KBSAI / #else` was compiled.** The positive controls are what make the
zeros interpretable.

⚠ **`strings` is NOT installed on this machine.** A first pass using it returned 0 for *every* token
in *every* DLL — including `SpawnClassBotAtLoc`, which `botspawn` provably calls — and was caught
only by a positive control (`KERNEL32` also read 0, and the tool printed 0 total lines). **Use a
python byte scan. Demand a positive control on any string census.**

### 2.3 The fix

```c
} else if(!g_bsResolved
#if KBSAI
          ||!g_bsAiFn||!g_bsAiThunk||!LooksLikePtr(g_bsAiCDO)
#else
          ||!g_bsFn||!LooksLikePtr(g_bsComp)
#endif
         ){
```

`.text` `0f310c58cd0e0941 → 7d67ac549ec8b2bf`; raw `.text` **108,032 → 111,104 (+3,072)** — the
newly-emitted call path. `THE CALL: UAIBlueprintHelperLibrary` **0 → 1**. `verify_dll.py` **PASS**.

⚠⚠ **A PARTIAL FIX LOOKED LIKE A NO-OP AND NEARLY DERAILED THIS.** Removing only the `g_bsComp` term
(`#if !KBSAI`) left `.text` **byte-identical** — because `!g_bsFn` still folded true. The build
reported `1 built, 0 failed` and the hash did not move, which reads exactly like a cached build.
★ **What distinguished them:** a deliberately observable change (a `BUILDSTAMP` string) moved the
hash `0f310c58cd0e0941 → 499c46a8854de895`, proving the build *does* read source edits — so the
unchanged hash was a real semantic no-op, not a stale artifact. **When an edit does not move the
hash, insert a marker before concluding the build is broken.**

### 2.4 The verdict line was fixed too

`if(!g_bsCalled)` asserted `(KBSARMS gated it off)` unconditionally. It now distinguishes
"bit 2 CLEAR ⇒ read-only arm by construction" from "bit 2 SET ⇒ **a PRE-CALL GUARD blocked it, NOT
the knob** — THE CENSUS DELTA IS UNINTERPRETABLE, NOT A NULL."

---

## 3. ⚠⚠ THE CENSUS PREDICATE WAS BLIND TO EXACTLY THIS CONTROLLER

`BsClassify` (`:14208`) tested **only** `PhChainHas(cls,"BotController")`. The arm's own header
writes P1 as *"BotController/**AIController** census delta"*, but an engine `AIController`'s chain is
`AIController <- Controller <- LokiActor <- Actor <- Object` — **no `BotController` substring
anywhere**. There was no `AIController` bucket and no broad `Controller` bucket in the arm.

⇒ **Flight 2's `dCtl=0` was an instrument artifact.** Recorded as a P1 null it would have read:
*"the controller is unreachable by ANY spawn entry point and the blocker is deeper than the entry
point"* — the exact sentence the handoff pre-registered as P1's failure meaning, and it would have
been **false**.

★ **This is precisely the blind spot S135 wrote down and asked to be settled** — *"I counted only
classes whose chain/leaf contains BotController or AIController. A controller of some other class
name would have been missed… Re-run it with the full list next time a world is staged."* Settled:
the narrow predicate says 0, the correct answer is 1.

**Fixed** (`.text d2d07d5e85dfe4b3`) — the predicate now matches `BotController` **OR**
`AIController`, and the labels read `BotOrAIController-chain` / `botOrAIControllers` so the number
cannot be misread.

⚠ The second term is deliberately **narrow**. A bare `"Controller"` substring also matches the ~190
`Comp_PlayerController_*_C` components and `BP_LokiPlayerController_Dev_C`, which would swamp the
delta with world noise.

⚠ **Cosmetic, unfixed:** the success VERDICT message still says `"BotController +1"` (a hardcoded
string). The authoritative counters are the `botOrAIControllers A0/A1/A2` line and `dCtl=`.

★ **New instrument: `tools/re/obj_by_chain.py`** — censuses live UObjects by **class DERIVATION
CHAIN**, the missing member of the class-lookup blind-spot family (`obj_by_class` substring ·
`cheat_reach_probe` endswith · `class_props` class-of-class · `bpframe_readout` first-match).

---

## 4. TWO `.text` DIGEST RECIPES, BOTH ON DISK — AND A RETRACTION

⚠⚠ **RETRACTED: S136 first published *"the four S135 bot digests are NOT canonical and appear
NOWHERE in the repo"*. THE SECOND HALF IS FALSE.** All four are recorded — in `CLAUDE.md`, in
`docs/s135-queue-arms-a-match.md`, and in `docs/next-session-prompt-s136.md`. The error came from a
`grep -rl` over `docs/` that **timed out at 2 minutes**, whose partial output was read as a negative,
and from conflating *"my computed RAW values are unrecorded"* (true) with *"the handoff's values are
unrecorded"* (false). **Scope your greps and check the exit code.**

**There are TWO recipes, differing only in the file-alignment tail:**

| | definition | where it lives on disk |
|---|---|---|
| **RAW** | `sha256(.text[PointerToRawData, +SizeOfRawData))[:16]` | `configs/fk24-stage.ps1:77 Get-TextHash` (prints only inside a stale-shim abort) and **`configs/fk7-ab-run.ps1:94`, which EMITS it at :131 into the A/B CSV column `probe_text_sha`** |
| **VIRTUALSIZE** | `sha256(.text[PointerToRawData : +min(VirtualSize, SizeOfRawData)])[:16]` | **`docs/method-rules.md:213` (S134-d)**, whose four quoted outputs recompute 4/4 |

**[M] The S135 bot gates were produced by the VIRTUALSIZE recipe** — it reproduces
`botspawn e48c90bc6cf17c93` and `botteam 0c16652dc0338d33` **exactly** from today's binaries.

★ **NEW [M]: `botspawn_readonly` matches NEITHER recipe today** — raw `319ac875af229f46`, minVS
`d96480ad64c1a403`, recorded `f5f9896feeac45dc`. **That artifact has changed since its gate was
recorded.** Re-record it before using it as a control.

⛔ **"9/9 verbatim" was a SELECTION EFFECT.** Honest numbers: **48/87** `tutorial_launch_*.dll` and
**55/132** corpus tokens match under RAW; **6** are VirtualSize-only; **0** for whole-file
sha256/md5/sha1. `cheatmgr`'s own CLAUDE.md table matches **1 of 4**.

⚠ **"Canonical" is a DECISION, not a measurement.** At least four artifacts (`play`, `dismount`,
`dropplane_b1only`, `droppod_pe_cdopoke`) have **both** digests recorded in different files as the
same gate, so declaring RAW canonical **silently invalidates six recorded gates**. If you choose one,
say which gates the choice invalidates, in the same commit.

⚠ **Degenerate case:** any DLL with `VirtualSize == SizeOfRawData` cannot discriminate the two
recipes. Check per file before citing a match as recipe evidence.

⚠⚠ **THE DIGEST IS NOT AN ARTIFACT IDENTIFIER TODAY, AND THE "A/B AGAINST A COPY OF ITSELF" HAZARD
IS LIVE RIGHT NOW:** `play` / `play_nopimutex` / `play_strictroot` share `9bc10a4552c596e1`;
`poolspawn` / `poolspawn_cdoctrl` share `85f3cee44c31b1cd`; `droppod_pe` / `droppod_pe_cdoctrl` share
`61fd0745c23e89f0`. **Any digest tool must flag duplicate digests across differently-named variants.**

⚠⚠ **ROOT CAUSE OF THE "no recipe on disk" BELIEF IS A BROKEN POINTER IN `CLAUDE.md`** — it directs
readers to *"`verify_dll.py` or the section-hash snippet in `docs/s109-dump-forensics.md` §23"*, and
**`verify_dll.py` contains no hash code and §23 contains no snippet.** Two sessions followed it, found
nothing, and concluded none existed. **Fix that line in the same commit as any digest work.**

⚠ **`build/` is gitignored and three S136 builds overwrote each other.** Only source-reproducibility
(`git show HEAD:` + an unmodified `build.ps1`) recovered the flight-1 artifact for measurement.
**Archive every A/B arm before rebuilding.**

**Arm digests after the S136 fixes** (RAW recipe): `botai` **`5e47c13cf7f0a158`**.
Regression gates re-verified unchanged: `play 9bc10a4552c596e1`, `dismount 53483e6181bb3583`.

## 5. The queue armed a match again — 4th reproduction

Backend-only, no shim, no relaunch. One `joinQueue` POST, on a fresh client:

```
02:42:07  POST /party/parties/party-9b9d.../joinQueue -> 200      (ONCE — retry-is-rejection receipt)
02:42:15  armqueue: ARMED  version=1787298135 ; WS NOTIFY[armqueue]
          GET /core-game/players/...        <- client refetched
          GET /core-game/matches/match-...  <- and escalated
07:42:15  LogTravelManager: Attempting to travel to Match ... Address:""
```

`joinQueue` = 1, `leaveQueue` = 0, `/core-game/matches` = 1, `LogTravelManager` = 1. Six
`/core-game/players` fetches total (3 pre-arm, one per messenger connection; 1 push-driven; 2 from
reconnects) — **not** a runaway refetch loop.

★ **The stager's preflight passed on the queue-armed MatchID with `forceTutorialMatch = false`**,
printing the MatchID it found — confirming S135's finding that the documented "set the flag and
relaunch" step is obsolete.

---

## 6. What this does NOT show

- ⚠ **The bot does nothing.** `BrainComponent`/`Blackboard`/`Perception` are NULL by design
  (`BehaviorTree = null`), and both bots read `vel = (0,0,0)` at rest. **Whether a Loki bot can be
  made to ACT is untouched.**
- ⚠ **This is not the game's own bot.** `SpawnAIFromClass` is an engine helper; it produces a generic
  `AIController` + hero pawn, **not** a Loki bot with a team, difficulty, hero-class assignment or
  bot name. Those come from native `SpawnBot`, and reaching them is §7.
- ⚠ **`LogAI` / `PathFollowing` / `AIController` appear 0 times in the client log — and that silence
  is UNINTERPRETABLE, not negative.** There is no positive control for those categories in this log.
- ⚠ **No claim is made about `MakeNewBotController` being fixed.** It is still bailing on the
  stripped getter; this route goes *around* it.
- ⚠ `roster=-1 team=-1 (player=-999)` on every flight — the AI route never reads the roster or the
  player team. Not a defect, just not applicable.

---

## 6b. ★★★ FREE COROLLARY — UE ITSELF DOES NOT THINK THIS CLIENT IS `NM_Client`

`APawn::SpawnDefaultController` has exactly three early-outs before it spawns anything (bytes read
from `merged12` at file offset == RVA):

```
0x3BBF3DD  48 83 b9 00 04 00 00 00 / 0f 85 c8 02 00 00   cmp qword [rcx+0x400],0 / jne  -> bail if Controller != NULL
0x3BBF3EE  e8 5d f3 7c ff                                call <GetNetMode>
0x3BBF3F3  83 f8 03 / 0f 84 ba 02 00 00                  cmp eax,3 / je                 -> bail if NM_Client
0x3BBF404  48 8b bb d0 03 00 00 / 48 85 ff / 0f 84 ...   mov rdi,[rbx+0x3d0] / test/je  -> bail if AIControllerClass == NULL
0x3BBF414  e8 27 24 af ff                                call <spawn>                   -> creates the controller
```

**[M] A controller WAS created ⇒ all three early-outs were passed ⇒ `GetNetMode() != 3`.**

★★ **THIS IS NOT THE SAME FACT AS `LokiIsServer` BEING HARDCODED FALSE, AND THE DIFFERENCE MATTERS.**
`LokiIsClient` (`0x0B9E1F0` = `mov al,1; ret`) and `LokiIsServer` (`0x0F7EB60` = `xor al,al; ret`)
are **Loki's own stripped helpers** — they answer "client/server" by fiat. `GetNetMode()` is **the
engine's real netmode**, and it is measured NOT-client. ⇒ the FK-1 / FK-22 / FK-42 walls are *Loki's*
authority stubs, **not** UE refusing authority to a client.

⚠ **Grade it exactly.** `!= NM_Client` is **[M]**; *which* mode it is (`NM_Standalone` 0 /
`NM_DedicatedServer` 1 / `NM_ListenServer` 2) is **NOT measured** — nobody has read the return value.
**One read settles it.** If it is Standalone, engine-level `HasAuthority()`
(`GetLocalRole() == ROLE_Authority`) plausibly passes, which would reframe how much of the
"server-only" surface is actually reachable. **Do not assume it — read it.**

★ **This speaks directly to an already-open question the repo wrote down twice and never answered:**
`CLAUDE.md:2513` and `docs/fk22-dropphase-reachability.md:1253` both propose *"grade
`ULokiBlueprintLibrary::ServerOnly`'s impl and read what it tests; if it reads a role/NetMode byte on
a client-resident object, that is a DATA poke."* Nothing in the repo had ever measured the netmode.
Now something has.

---

## 7. ★★★★★ WHY THE PlayerState IS NULL — SETTLED OFFLINE, AND IT IS **ONE BIT**

**[M] It is NOT a Loki strip. `AController::InitPlayerState` is REAL, its entire call graph is REAL,
and the only reason it never runs on an AI controller is that stock UE defaults
`bWantsPlayerState = false`.**

### 7.1 `AController::InitPlayerState` = `0x36DEE20`, `AController` vtable slot 273 — TRIPLE-CONFIRMED

Three parties derived this independently (session lead, an offline lane, and an adversarial verifier),
by three different routes, and agreed:

- **It names itself.** `.rdata 0x8018A50` holds
  `"AController::InitPlayerState: the PlayerStateClass of game mode %s is null, falling back to
  APlayerState."`; the `FStaticBasicLogRecord` at `0x8018A30` = `{Format=0x8018A50,
  File=…\Engine\Source\Runtime\Engine\Private\Controller.cpp, Line=0x268, Verbosity=5}`, and a
  full rip-relative-LEA index of `.text` gives that record **exactly one** LEA site — `0x36DEF82`,
  inside the function starting at `0x36DEE20`. (VA→RVA arithmetic checked; positive and
  impossible-token controls both run.)
- **Behaviour, not proximity.** It reads `UWorld::AuthorityGameMode` at FK-22's measured **`+0x250`**
  (and `GameState` at `+0x258` as the fallback), reads `PlayerStateClass` at
  **`AGameModeBase+0x3E0`**, calls `UWorld::SpawnActor 0x39C5280` with `RF_Transient`, and
  **writes `[controller+0x3C0]`** — the exact field measured NULL on both S136 controllers. It is
  the ONLY slot of 400 that stores to `this+0x3C0` via a non-frame base register.
- **Dispatch corroboration.** `AAIController::PostInitializeComponents` calls `[rax+0x888]`
  (273 × 8 = `0x888`) at `0x45D6D46`.

**GRADE: REAL.** Extent `0x36DEE20..0x36DF12A` = 778 B. **All 14 call targets REAL — ZERO folds.**

### 7.2 THE BLOCKER, from the bytes — and every one re-verified by the session lead

```
AAIController::PostInitializeComponents  0x45D6D10   (REAL)
  0x45D6D19  call 0x36E3000                        ; AController::PIC -- does NOT call InitPlayerState
  0x45D6D1E  f6 83 88 04 00 00 20                  ; test byte [rbx+0x488], 0x20   <- bWantsPlayerState
  0x45D6D25  74 25                                 ; je   0x45D6D4C                <== THE BLOCKER
  0x45D6D36  call 0x338E750 ; cmp eax,3 ; je       ; != NM_Client
  0x45D6D46  call qword ptr [rax+0x888]            ; InitPlayerState()   (slot 273)
```

**`bWantsPlayerState` is bit `0x20` of the dword at `+0x488` [M] — from its OWN UHT bool record's
`SetBitFunc`:**
```
0x45CFA10  83 89 88 04 00 00 20 c3   or dword [rcx+0x488], 0x20 ; ret     <- bWantsPlayerState
0x45CFA20  83 89 88 04 00 00 40 c3   (CONTROL: the next bit, same offset) <- passes
```
★ That is the correct instrument for a bool UPROPERTY — `FBoolPropertyParams` carries **no**
`ByteOffset`/`ByteMask` fields (the engine derives them by calling `SetBitFunc` on a zeroed buffer),
a trap this repo already recorded in S132.

**And it is explicitly CLEARED in the constructors:**
```
AAIController::AAIController       0x45D19AD   83 e1 df                  and ecx, ~0x20
ALokiBotController::ALokiBot...    0x554B5A9   83 a7 88 04 00 00 df      and dword [rdi+0x488], ~0x20
ALokiAIController                  0x56196C0   no +0x488 access at all -- inherits false
```

⇒ **No stripped stub is involved anywhere in this chain.**

### 7.3 THE LEVER: ONE CDO BIT — the S130 pattern exactly

**Poke `CDO(<the pawn's AIControllerClass>) + 0x488 |= 0x20` before spawning.**

Ordering is what makes it work: `SpawnActor` runs `PostInitializeComponents` (→ `InitPlayerState`)
**before** `SpawnDefaultController` calls `Possess`, and `APawn::PossessedBy` / `SetPawn` then copies
`controller+0x3C0` → `pawn+0x3D8`.

Risk class: **one aligned CDO write, readback-verifiable, class-default scope** — the same class as
S130's `bCanEverReplicate` byte, this project's safest measured write.
⚠ It IS a class default: it affects every controller of that class for the process lifetime.
⚠ **Read `pawn CDO + 0x3D0` (`AIControllerClass`) live first** to know which controller CDO to poke.
`APawn::APawn` (`0x3B809D0`) zeroes `+0x3D0` then reads it back **from the `APawn` CDO chain**
(`0x3B80C0D` → `call 0x3BA4CE0` → `[rax+0x178]` → `[+0x3D0]`) — it is **not** a hard-coded
`AAIController::StaticClass()`, so resolve it live rather than assuming.

**Alternative with no CDO write at all:** after `SpawnAIFromClass` returns, take `pawn->Controller`
(`pawn+0x400`) and call `0x36DEE20` **directly** as `void __fastcall(AController*)`.
⚠ That is **not** "CALL-ONLY" in the read-only sense — `InitPlayerState` performs a `SpawnActor` and
writes `controller+0x3C0`. Say so rather than filing it beside the read-only arms.

### 7.4 ⚠⚠ A SECOND WALL SITS PAST IT — both walls are real and SEQUENTIAL

Everything gates 1+2 protect inside `SpawnBot` is: stamp a `"bot%d"` name, one real virtual, and
**two stripped folds**:
```
0x556DE43  mov rcx,rdi ; lea rdx,[rsp+0x78] ; call 0x0F7EC20    ; VOID fold
0x556DE53  mov rcx,r13 ; mov rdx,rdi ; mov r8d,[rsp+0x50] ; call 0x0F7EB60   ; FALSE fold
```
Independently, from the reflection table: `ALokiPlayerState::ServerSetHeroClass` (exec thunk
`0x5438720`) and `SetPlayerTeam` (exec thunk `0x538AA70`) both tail-call those same folds — **their
impls are stripped**, and the argument shapes match the two call sites exactly (2-arg `(this,
struct*)` and 3-arg `(this, Object*, int32)`).
⚠ **Grade [I, strong], NOT [M], on the naming** — `0x0F7EC20` has 165,789 stored-pointer occurrences
and `0x0F7EB60` has 106,924; **a folded RVA names nothing**. What is **[M]** is that both call sites
are folds and that both named functions are independently stripped.

⇒ **A PlayerState buys REACHABILITY of that branch, not hero-class or team assignment.** The pawn
already spawns with the correct hero class (S135), so what is lost is the *PlayerState-side* hero/team
record — which is exactly what `CreatedBot`'s `GetPlayerStatesOnTeam` scan reads.

### 7.5 ⛔ REFUTED IN REVIEW: there is NO "third gate"

An offline lane warned of a third gate at `0x556DD89 cmp dword [rdi+0x8c8],1 / jg`, read `[PS+0x8C0]`
as the PlayerName FString, and told the next session to pre-register it or zero the field.
**That is wrong.** `+0x8C0` is **`ALokiPlayerState::PlatformPlayerID`** (UHT record `0x8A252D8`,
`Offset=0x8C0`; `binds_members.csv:44578` agrees). The engine's player name is
**`APlayerState::PlayerNamePrivate @ +0x450`**, and `InitPlayerState`'s tail writes *there* — the
virtual it calls (slot 257, `0x3CA9D10`, not overridden by `ALokiPlayerState`) ends
`lea rcx,[rbx+0x450]`.
⇒ **`[PS+0x8C8]` stays 0, the `jg` falls through, and the block RUNS. One fewer obstacle.**
★ The lane inferred the field's identity **from the write it saw** instead of from the property
table it already had open. The correction is *favourable*, which is exactly why it had to be made
rather than quietly dropped.

### 7.6 Two stale-doc corrections that fell out

- ⚠⚠ **`APawn::SpawnDefaultController 0x3BBF3C0` has NO `.pdata` row**, which is *why* a pdata-based
  grader reports the wrong entry point for it — `pdataunion.py` drops size-1 placeholder slots **by
  construction**. That is the mechanism behind `strxref.py func 0x3BBF3C0` answering
  `entry 0x3BBDFA0` (reproduced live this session). **[M] it is pawn vtable slot 280 in `APawn`,
  `ACharacter`, `ALokiCharacter` and `ALokiHeroCharacter` alike — none overrides it.**
- ⚠ **`.rdata` class literals are UHT PREFIX-STRIPPED.** The bytes at `0x899A832` / `0x8A2430A` /
  `0x81B4B9A` are `LokiHeroCharacter` / `LokiPlayerState` / `PlayerState` — **not** the `A`-prefixed
  forms. CLAUDE.md's FK-13 note already records this trap producing false ABSENTs; do not propagate
  the prefixed form.

### 7.7 ⚠ AND ONE MEASUREMENT THAT IS **[M]** BUT WHOSE **LABEL** IS **[I]**

`ALokiPlayerController`'s slot 273 is the void fold `0x0F7EC20`, while `AController`,
`APlayerController`, `AAIController`, `ALokiAIController` and `ALokiBotController` all carry the real
`0x36DEE20`. **The measurement reproduces exactly.** But calling it "a new FK-1-family strip" is
[I], not [M], for two reasons a fold-density control exposed:
- Empty virtuals are **ordinary** here — `AController`'s own vtable has **62 of 289** fold slots,
  `APlayerController` 56/289, `ALokiPlayerController` 112/586. From the bytes alone you cannot
  separate *"`WITH_SERVER_CODE`-stripped"* from *"Loki authored `virtual void InitPlayerState()
  override {}`"*. (Replacing a real base impl with an empty one IS rare: 2 of ~84 overrides.)
- FK-1's signature is a **reflected UFunction** whose registered impl is a fold. `InitPlayerState` is
  **not reflected at all** — an image-wide name census gives ascii 0 / wide 0 against five passing
  positive controls — so there is no thunk and no `.data` record for FK-1's instrument to grade.
**State it as:** slot 273 is a void no-op on `ALokiPlayerController` alone **[M]**; therefore Loki
gets its PlayerState by another route **[I]**. ★ The AI-controller chain keeps the real engine impl,
which is the half that matters here.

---

## 8. Method notes worth keeping

- ★★★★★ **WAITING FOR `[BS] done` IS WHAT SAVED THIS SESSION.** Flight 1's census read `0/0/0` with a
  confident-looking VERDICT line. Read as a P1 null it would have produced *"the controller is
  unreachable by any spawn entry point"* — published, wrong, and expensive. The `called=0` field is
  what exposed it, and it only exists in the completed summary.
- ★★★★★ **A CONFIDENT VERDICT STRING IS AN INSTRUMENT.** `"(KBSARMS gated it off)"` was hardcoded on
  a generic failure path and named a knob that was set correctly. **A failure message that asserts a
  cause it did not test is worse than no message.**
- ★★★★ **THE BINARY'S STRING TABLE IS A COMPILE-TIME COVERAGE INSTRUMENT.** "Is this branch even in
  the build?" is answerable offline, in one byte scan, with the sibling branch's literals as the
  positive control. That is what turned "the call did not happen" into "the call was never compiled."
- ★★★ **AN EDIT THAT DOES NOT MOVE `.text` IS AMBIGUOUS.** Cached build vs semantic no-op look
  identical. Insert a deliberately observable marker string to separate them (§2.3).
- ★★★ **`strings` is not installed here.** It returns silence, and silence reads like a negative.
  Positive control caught it (§2.2).
- ★★ **Two agreeing instruments beat one.** The arm's own census and `obj_by_chain.py` — different
  code, different matching strategy — agree at 1 and at 2.
- ★★ **The pre-flight audit workflow independently derived both defects** (the dead arm AND the blind
  predicate) from source alone, before the second flight. Its arm-source lane headline was *"`botai`
  CANNOT MAKE ITS CALL. The dispatch gate is not `#if KBSAI`-aware."*
- ⚠⚠ **`InternalIndex` adjacency is NOT usable as a creation-order signal here.** The AIController
  (177838) and its components (177831, 177832) cluster, but the pawn sits at 80214 next to the
  staged hero at 77751 — because `GUObjectArray` **reuses freed slots** (S110's `FreeUObjectIndex`).
  The "it is new" claim rests on P4 and the possession fingerprint, **not** on indices.

---

## 9. Artifacts

| path | what |
|---|---|
| `docs/s136-botai-flight1-DEADARM-marker.txt` | flight 1 — the full ladder, `called=0` |
| `docs/s136-botai-flight2-CONTROLLER-marker.txt` | flight 2 — first successful call |
| `docs/s136-flight3-PREREGISTERED.txt` | flight 3 predictions, written before injection |
| `docs/s136-botai-flight3-REPLICATION-marker.txt` | flight 3 — `dCtl=1 dHero=1`, 7/7 |
| `dumps/s136-botai/` | the P4 capture |
| `dumps/merged12.dump.exe` | merged11 + s136, +11 pages, 0 conflicts |
| `tools/re/obj_by_chain.py` | class-derivation-chain census (new) |
| `tools/sigbypass-mod/text_digest.py` | the canonical `.text` digest recipe (new) |
| `docs/capture.log.pre-s136-botai` | capture.log backed up before the `ags` restart |
