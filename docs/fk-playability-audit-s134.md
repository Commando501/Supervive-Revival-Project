# FK register, re-read for PLAYABILITY (S134 audit, 2026-08-20)

**Question asked:** which entries in `docs/ignorance-map-s101.md` bear on (T) getting the TUTORIAL
playable, and (L) getting any other LEVEL playable — Breach, Arena, Tournament, Training/warm-up,
Practice Range, Co-op vs AI, or the tutorial missions.

**Method.** 6 mapping lanes over the FK register + the non-FK sections, each adversarially verified
by an independent agent; 3 completeness critics (tutorial chain / other modes / FK-20 stale-claim
re-grade); one synthesis. 18 agents, 745 tool calls, 266 findings. Offline throughout — **zero
launches, zero injections, zero `.text` writes.**

**Scope limit, stated up front.** This is a re-read of documents. It measures nothing about the
game. Every `[M]` below is inherited from the doc cited, not re-measured here, EXCEPT the six
marked `[V]`, which the session lead re-ran against the artifacts:

| `[V]` | Claim | Verified how |
|---|---|---|
| 1 | `ULokiBlueprintLibrary::ServerOnly` impl `0x1311870` = `C6 02 00 C3` = `mov byte [rdx],0; ret`, 18/18 images | read at `docs/fk22-dropphase-reachability.md:589` |
| 2 | `InitAbilityActorInfo` is at `base+0x447F410` and has **never been called** | `docs/s111-asc-census.md:568` + `docs/next-session-prompt-s111.md:15`; `grep -rn "447F410\|InitAbilityActorInfo" tools/sigbypass-mod/` = **0 hits** |
| 3 | `buildTutorialMatchInfo`'s map is a hardcoded const | `server/internal/interactive/interactive.go:981` `const tutorialMapName = "/Game/Loki/Maps/Tutorial/LVL_Tutorial"` |
| 4 | `ALokiGameMode::SpawnPlayer` (a stripped stub) is on the FFA/Arena spawn path too | `docs/angelscript-ffa-bots.md:538` `C = GM.SpawnPlayer(...)`, `:557` "the single native entry point through which every FFA spawn passes" |
| 6 | **THE ENTIRE SPINE, RE-MEASURED FROM THE BYTES IN TWO IMAGES** (`merged10` and `merged2`, flat dumps, file-offset == RVA). All six agree across both: `ServerOnly` `0x1311870` = `c6 02 00 c3` (`mov byte [rdx],0; ret`) · `CheatsEnabledOnly` `0x13852F0` = `c6 01 01 c3` · `LokiIsServer` `0x0F7EB60` = `32 c0 c3` (`xor al,al; ret`, always FALSE) · `LokiIsClient` `0x0B9E1F0` = `b0 01 c3` (`mov al,1; ret`, always TRUE) · `SpawnPlayer` `0x0F7EB50` = `33 c0 c3` (`xor eax,eax; ret`) · void fold `0x0F7EC20` = `c2 00 00` (`ret 0`). ★ Independently corroborated by `strxref.py func 0x1311870`, which reports `first byte at entry = 0xC6` from its own code path. | direct byte read, S134 |
| 5 | `Marker()` does NOT open `CREATE_ALWAYS` at `:4919` | `tools/sigbypass-mod/tutorial_launch.cpp:404` (`FILE_APPEND_DATA \| OPEN_ALWAYS`); the truncate is `:14715` |

⚠ **Everything else is a documentary claim inherited at its recorded grade.** Where this file says a
claim is STALE it means *the artifact it cites no longer supports it*, not that the underlying thing
has been re-measured in the game.

---

# Which FKs Bear on Playability — Tutorial (T) and Any Other Level (L)

**Synthesis of 6 mapping lanes + 6 adversarial verifiers + 3 completeness critics. Status current to S133 (2026-08-20).**

Where a verifier corrected a finder, the verifier's verdict is applied unless noted. Five load-bearing claims I re-measured myself this session are marked **[V]**.

---

## 0. Adjudications and corrections applied

These override what individual lanes reported. Read them first — several invert a lane's headline.

| # | Dispute | Adjudication |
|---|---|---|
| 1 | `changed-since` lane: "the ignorance map contains no S133 joinQueue result" | **REFUTED.** **[V]** `docs/ignorance-map-s101.md:2053` (FK-40 row e) carries the full S133 result verbatim; `grep -c S133` = 4. The finder read line 2053 and mislabelled it "the S122 row at :2050". The map's real gaps are two un-backpropagated rows (FK-5 `:2271`, fk20 §5.4), not "S133". |
| 2 | `fk15-22`: "`matchmakingNotif` is UNBOUND ⇒ **no payload can ever** make it act" **[M]** | **RE-GRADED to [M]-at-the-menu / [I]-for-ever.** Two independent lanes converged on this. The delegate walk (`fk15-bound-delegate-map-20260813.md`) was performed 2026-08-13 on a **menu** client; `joinQueue` first worked 2026-08-20. The table has **never** been read on a client in `EPartyState::Matchmaking`. Boundness is a runtime subscription (`DelegateSize != 0`); a matchmaking subscriber binding at queue-entry is an ordinary lifecycle. S134 rules out the entire push route on this one measurement. |
| 3 | `sections` S-ENABLER-1: S91–S93 tutorial modes arm with "the standing `.text` patch S112 measured at 10/10 lethal" | **MAGNITUDE CORRECTED, SCOPE WIDENED.** They call `UninstallHook()` after 20–60 s — *transient*, so the applicable ladder row is **4/12**, not the 10/10 standing figure. But `RM_SPAWNPOSSESS` (`:15431`) and `RM_FORCEOPEN` (`:15478`) *also* arm with unguarded `InstallHook()` and run on **every** sitting today. The port is still right; the framing was wrong in both directions. |
| 4 | `fk01-07` / `sections`: "`CoreGameBotConfig` is one unserved struct from a tutorial combat target" | **SCOPE CORRECTED.** `CoreGameBotConfig` is match bot-**fill** for `bots`/`arena`. The tutorial's targets are level-placed `BP_LokiSpawner_Basics_{MinionSquad,PopcornSquad,SingleLeader}` + `BP_Tutorial_JouleBotManager`. Nothing connects them. Serve it — for `bots`/`arena`. |
| 5 | `§5.3`: "FFA / Arena-with-bots — no drop plane, no storm, no 60-player replication" | **THE BUNDLE IS THREE THINGS.** `bots` → alias `SkylandsBRBotsGameMode` → `BP_LokiBattleRoyaleGameMode_Skylands_Bots_C`, i.e. a **Skylands battle royale** inheriting the entire drop chain and the never-loaded 2,216-package map. `deathmatch`/ARENA is 4v4 and its host gamemode is **unidentified**. Only `BP_FFAGameMode_C` (MaxPlayersPerTeam=1) matches the justification — and it has **no queue id**. |
| 6 | `fk23-32` / register FK-25: "`Marker()` opens `CREATE_ALWAYS` at `tutorial_launch.cpp:4919`" | **FALSE AS WRITTEN. [V]** `Marker()` is at **`:404`** and uses `FILE_APPEND_DATA \| OPEN_ALWAYS` — it appends. The single `CREATE_ALWAYS` is at **`:14715`**, a one-shot truncate at the top of `Worker()`. The observable defect (per-injection truncation) is real; the fix is **one line at :14715**, not a rewrite. |
| 7 | `fk13`/`fk23-32`: "spawn an `ALokiPlayerCheats` and write `PC+0xA30` — the SAME SHAPE Route B solved" | **CONSTRUCTION ERROR.** `ALokiPlayerCheats` is an **AActor**; Route B's `SpawnObject` was chosen precisely because shipping compiles out `NewObject`'s `ClassWithin` assert. It needs a `SpawnActor` path. The `UObject` sibling that *is* the same shape (`ULokiClientPlayerCheats` @ `GI+0x298`) grades 5/5 REAL — **all five are lobby cosmetics**. |
| 8 | `fk01-07` FK-1a: "script UFunctions are callable by the S55 recipe unchanged" | **MEASURED FALSE for script UFunctions.** `fk22 §19.2`: `SpawnDropPodForTeam UFunction.Func = 0x0 *** NULL ***` against a same-run non-null control. The working route is **`ProcessEvent`, vtable disp `0x270` = SLOT 78** (three instruments), flown at §21.2. ⚠ **`CLAUDE.md:2316` and `CLAUDE.md:2681` ("slot-56 ProcessEvent") are both stale** — this is the primitive documentation every shim is written against. |
| 9 | `fk13.c`: "ALL TEN `ALokiCharacter` exec verbs are dead" | **CORRECTED** — 8 FOLDED + 2 **COVERAGE-BLOCKED**, and `lane-d-empty-impl-census.tsv` grades both blocked ones **REAL**. Folding COVERAGE-BLOCKED into "dead" is the FK-20 error. Per-record for `ALokiPlayerCheats`: **14 REAL / 10 EMPTY / 1 dark**, and the split is not random — every progression/cooldown/teleport verb is EMPTY; the one playability-relevant survivor is **`CheatChangeHero`, REAL, impl `0x1384d50`** (not `0x5611090`, which is `SortActorsByDistance`). |
| 10 | `fk15-22` FK-22c: "the DropPlane bind is dead by construction" | **NARROWED.** `fk22:590`: two further **UNGATED** bind sites of the same handler exist (`SpawnPlane` `[38]-[40]`, zero `ServerOnly`; `OnDeathCircleSet` `[90]-[92]`), plus `BP_LokiHeroCharacter_C` and the AS respawn component both subscribe ungated. **One of three bind sites is dead, not the bind.** |

---

## A. THE TUTORIAL-PLAYABLE SET

### A.1 What is solved, and what it bought

| Item | FK / session | What it bought |
|---|---|---|
| World entry, hands-free | S107/S108, FK-31 stager | `LVL_Tutorial` loads, hero spawns, is possessed, walks and **runs with real locomotion** (S108b/S110 `KANIMREF`). No human at the keyboard. |
| **FK-7 — "the run dies in 1–5 min"** | SETTLED S112 | It was **our own standing `.text` patch**: 10/10 armed windows died with it vs 3/36 without, Fisher **p = 7e-8**. Shipped fix = heap `UFunction.Func` swap; 5/6 windows survived 600 s. **This is what makes any >3-minute in-world experiment possible at all.** |
| **FK-26 — leftover S9x diagnostics** | SETTLED S108b | `KSTATICTEST` was calling `PlayAnimation` on a `StaticMeshComponent`, faulting under SEH every run and printing *"anim swapping DISABLED for the rest of the session"* — **the hero's walk/run animation was dead for weeks and was wired up the whole time.** |
| **FK-27/FK-39 — GC rooting** | SETTLED S123 | The run AnimSequence really was collected; the poked RootSet bit was **inert** (`AddToRoot` inserts into a `TSet<int32>` registry at `.data 0x99D3CA0`; the flag is a mirror). `KANIMREF` (park the asset in a real UPROPERTY) is the shipped fix and is re-framed as *the same mechanism real roots use*. |
| **FK-22 phase machine** | SETTLED S124 | **One `GoToPhase` call self-drives the round to `EGP_Combat`** — six transitions from two calls, `Took 414.264048 seconds to go from EGP_Pre to EGP_Combat`, then mass navmesh generation. Zero `.text` writes. This is a world state the entire S90–S93 lesson programme never had. |
| **FK-11 — Verbose is compiled out** | SETTLED S113 | **FALSE.** `COMPILED_IN_MINIMUM_VERBOSITY = VeryVerbose(7)`; 109/109 Loki categories are VeryVerbose. `[Core.Log]` in the user `Engine.ini` works. **This forecloses the cheapest instrument the project could own, and its own prescribed follow-up — re-test the Class A/GAS categories on a run where the code executes — has never been run.** |
| **FK-13 — the console is stripped** | SETTLED S114 | Outcome true, **every reason false**. A live `UCheatManager` installs with **one aligned heap qword** and **42 REAL exec verbs** are reachable: `Summon`, `Teleport`, `BugItGo`, `DamageTarget`, `DestroyPawns`, `Walk`/`Fly`/`Ghost`, `PlayersOnly`, `StreamLevelIn`. **Never flown in a world** — the only proof is `LogLoc` at the menu. |
| Objectives + camera + visible hero | S93 | Lessons complete and the chain walks **WASD → LMB → Dash_Level → Dash_Use → Jump**; camera fixed top-down; a rendered, animated body built with `AddComponentByClass` + `SetSkeletalMeshAsset`. ⚠ **Completion is SYNTHETIC** — an RPM poke plus the ungated `OnRep_TrainingActive` closer. |

### A.2 What still blocks — ranked by load-bearing

#### ★★★★★ 1. THE BLUEPRINT EXEC-PIN GATE FAMILY — not in any FK register, and it is the single systemic cause of "presentation works, simulation doesn't"

`ULokiBlueprintLibrary`'s four exec-pin gates are how a Blueprint asks *"am I the server?"*. On this client **all four select the non-server pin, always**:

| Gate | thunk → impl | bytes | selects |
|---|---|---|---|
| `ServerOnly` | `0x52E12B0` → `0x1311870` | `C6 02 00 C3` = `mov byte [rdx],0; ret` | **Hidden** (Server=1) |
| `ClientOnly` | same (ICF-folded) | same | Client |
| `ClientServerSplit` | same (ICF-folded) | same | **Client** |
| `CheatsEnabledOnly` | `0x52E0D00` → `0x13852F0` | `C6 01 01 C3` = `mov byte [rcx],1; ret` | **Hidden** |

**[M]** `0x1311870 = C6 02 00 C3`, present and identical in **18 of 18** dump images, with the enum orders read from the UHT records — `docs/fk22-dropphase-reachability.md:589`. **[V]** I confirmed that line verbatim. The internal control: the two-param gates write `rdx`, the one-param gate writes `rcx`, exactly as their `binds_members.csv` signatures predict.

**★★★★★ AND IT IS DECISIVE FOR OBJECTIVE COUNTING — [V], read directly from the shipped bytecode this session:**

```
ProgressObjective  =  EX_LetValueOnPersistentFrame(ProgressAmount)
                      ExecuteUbergraph_Comp_GameState_TrainingBase(768)

ExecuteUbergraph @ StatementIndex 768:
  [31] EX_CallMath  ServerOnly  -> CallFunc_ServerOnly_OutputExecs_1
  [32] EX_LetBool   CmpSuccess_1 = NotEqual_ByteByte(OutputExecs_1, ByteConst 1)
  [33] EX_JumpIfNot CmpSuccess_1 -> CodeOffset 838
  [34] EX_Jump      1391                        <-- EXIT
  [35] EX_Let       Add_IntInt(CurrentObjectiveCount, ProgressAmount)   @838
  [36] EX_Let       CurrentObjectiveCount = ...
```

`ServerOnly` writes **0** ⇒ `NotEqual(0,1)` = TRUE ⇒ `JumpIfNot(TRUE)` does **not** jump ⇒ falls into `[34] EX_Jump 1391` = exit. **Offset 838 is unreachable on every invocation path.** ⇒ `ProgressObjective(N)` can never move `CurrentObjectiveCount`, synthetic FFrame or not.

**This re-attributes three separately-recorded tutorial nulls to one cause, and all three recorded causes are wrong:**

- S92: *"ProgressObjective did nothing because my quests are ORPHANS"* — no; the increment is behind the gate.
- S93: *"its ServerOnly branch skipped when called from the synthetic FFrame"* — no; it skips on every path.
- S93: *"`box.OnActorBeginOverlap InvocationList Num=0` — needs the sequencer/TeamState lifecycle"* — no; **[V]** in `bpdump_ExecuteUbergraph_TrainingQuest_Basics_WASD.txt` the `ClientServerSplit` is at `[50]`, `EX_BindDelegate OnWASDTriggerOverlap` at `[59]` (line 760) and `IncrementObjectiveCount` at `[64]` (line 826) — the bind, the immediate overlap test and the increment are all on the **server arm**; the client arm pushes four presentation flows and never touches the delegate.

**That is the whole tutorial in miniature**, and it matches the coverage audit's own summary exactly: presentation is ~proven, simulation is unmapped. The two halves were never differently hard — they are on opposite sides of one byte.

Blast radius (from the tutorial bpdumps): `Comp_GameState_TrainingBase` ×3 `ServerOnly`, `BP_LokiGameMode_Tutorial` ×2, `TrainingQuest_Basics_WASD` ×1 `ClientServerSplit`, `TrainingQuest_Basics_Base`, the quest sequencer, `Comp_GameMode_DropPlane_Tutorial`, and `BP_LokiHeroCharacter`'s 13 sites. ⚠ It is **engine-wide, not tutorial-specific** — which is why it survives whichever target §9.1 eventually names.

**Lever, and it is cheap and in a measured-safe class:** `EX_CallMath` dispatches through `UFunction.Func`, and the three write-0 gates are **distinct UFunction objects** sharing one folded target — so a per-UFunction **heap Func swap** to a 4-byte stub writing the Server pin is single-variable and touches no module image (the `KFUNCSWAP` primitive, **0/16 deaths at 600 s**). The surgical alternative is a **Blueprint bytecode edit** of one gate (`EX_ByteConst 1` → `0`), the class S111 arm J measured at **0/9**. ⛔ **Do NOT patch `0x1311870` in `.text`** — that is the 7/8-lethal class.

#### ★★★★★ 2. FK-30 / ABILITIES — the bind function was found, disassembled, written up as "TASK ONE", and never called

Register status says **SETTLED** ("the ASC exists, is missing ONE field"). That is the trap. Measured state, unchanged since 2026-08-05:

- ASC exists, `OwnerActor` set, `SpawnedAttributes` Num=2 — **but the ASC, the carrier and both attribute sets are the SHIM'S OWN creations** (`s111-asc-census.md:1-24` retraction). The game wires nothing on this route, because the wiring is inside FK-1's stripped `SpawnPlayer`.
- **`AvatarActor` = NULL**, **`ActivatableAbilities` = 0** ⇒ no ability can activate.
- `s111-asc-census.md §12`: writing the `@0xF00` cache **lands and is not sufficient** — `AvatarActor` still NULL.
- `s111-asc-census.md §13`: **`InitAbilityActorInfo` FOUND at `base+0x447F410`**, `(rcx=ASC, rdx=Owner, r8=Avatar)`, plus `AbilityActorInfo` at `ASC+0x418` and `InitFromActor` at vtable `+0x8`.

**[V] It has never been called: `grep -rn "447F410\|InitAbilityActorInfo" tools/sigbypass-mod/` returns ZERO.** 22 sessions and no handoff since s111 mentions abilities at all.

⚠⚠ **The register row is STALE and hides this**: `ignorance-map-s101.md:1690` still reads *"`InitAbilityActorInfo` is C++-only"* with only the `RemoveFromAbilitySystem`/`TryUpdateAbilitySystem` anchors — **the address from §13 appears nowhere in the register.** A reader of the register alone concludes the bind is unlocated.

⚠ **And the "not reachable" wall stopped applying around S123.** It is narrowly true (no reflected route) and was written before plain direct calls to non-reflected natives became standard: `AddToRoot 0x489F9B0`, `PrimePools 0x3356000`, `ResizeGrow 0x00F988D0` (flown ×7 in S132). This is a DATA-class call, zero `.text` writes.

⚠⚠ **CONFOUND TO CLEAR FIRST — [V] `#define KWIREGAS 1` at `tutorial_launch.cpp:4869`.** It drives `WireAbilitySystem(hero, pc)` on **every** `RM_PLAY` init and `RM_SPAWNPOSSESS` completion — spawning the carrier, building the ASC and two attribute sets, forcing `ROLE_Authority`, writing `@0xF00`. That is exactly why `s111-asc-census.md` needed a retraction banner. An ability-bind result read out of a shim already doing all that is uninterpretable unless KWIREGAS's contribution is separated. ★ Good news: `ReportAscActorInfo` (`:11906`) already reads `OwnerActor`/`AvatarActor` by name and already emits the pre-registered detector `*** AVATAR IS THE HERO -- BOUND ***` — **the arm is half-built.**

#### ★★★ 3. FK-1b — `ALokiGameMode::SpawnPlayer` is the mechanism behind #2

Exec thunk `0x534C070` → impl **`0x0F7EB50` = `xor eax,eax; ret`**. The design routes the **entire GAS bind** through it (`FFA/LokiRespawnComponent::Respawn` null-checks the character but **not** the ASC). Empty-impl base rate is **3.16 %** per record; `Auth*` is enriched to **42.4 % vs 8.30 %**, Fisher **p = 1.6e-28** ⇒ **one decision to remove server authority**, not a decision about deploy.

⇒ Routing consequence, not an experiment: the hero **must** come from the deferred spawn (works), and the GAS bind **must** come from the raw `InitAbilityActorInfo` call. The designed route is bytes-level impossible.

#### ★★★ 4. No combat target — and no census has been run in a phase-advanced world

- **[M]** `s111-asc-census.md:118-131`: with `LVL_Tutorial` loaded via `gft`+`fo` there are **pawn-like = 2, both spectators** — no hero, no AI pawn. 344 initialised ASCs, all scenery.
- **[M]** *"nothing in this world has an ability granted"* across 344 ASCs — so there is **no in-world reference** for granting or activating.
- **[M]** `LVL_Tutorial.json` (persistent level) ships three **`BP_LokiSpawner_Basics_{MinionSquad,PopcornSquad,SingleLeader}`** plus `BP_Tutorial_JouleBotManager`. **No session has ever looked at them.**
- ⚠ **CONFLICT, unresolved:** `tutorial-playability-plan.md:118` claims "bots spawn" (S65/S66) while S111 measured zero. Probably not contradictory (S111's sweep was at `gft`+`fo`, pre-phase), but the census has never been re-run after S124's `GoToPhase → Combat`. ⚠ **[I, strong] against it:** `docs/Loki-s124-phaseladder-SUCCESS.log` — the run that *did* reach `EGP_Combat` — contains **zero** JouleBot / LokiSpawner / AIController lines. So reaching Combat is probably not sufficient either, and the spawner is the next question, not the phase.
- ★ **`SpawnJouleBot` is one of `Comp_PlayerController_TutorialObjectives`'s three `FUNC_Net|FUNC_NetServer` actions** — on the force-open route the client **is** authority, so it executes locally.
- ★ **A cheaper first damage witness than a bot:** a minion's ASC is **self-owned** (`AuthSpawnWave` does `v52.ApplyGameplayEffectToSelf(...)` with no null check), and 344 scenery ASCs are live with readable `LokiAttributeSetHealth`. FK-6 §6's step 2b — `AdjustHealth(asc, −250)` → read back 750 — proves **damage** with no enemy, no spawn and no cheat. **Written S105, never executed.**

#### ★★ 5. The lesson chain has no world to walk through

- **[M]** Only **ONE** training volume streams in (`Move_V2`); S93's five-lesson walk reused the same physical volume. The geographic progression does not exist in-session.
- **[M]** `BP_TutorialTrainingQuestSequencer_C` has **0 instances**; spawning it is measured **not sufficient** (`ReadyToFire` takes a quest class as a parameter; its ubergraph reads `BP_Loki_Team_State_Code` / `SoloAugmentPlayerState`, both 0 instances).
- **[M]** `LVL_Tutorial.json` (persistent) references exactly one `BP_TrainingVolume_*` and **no** `TrainingQuest_Basics_*` — the rest live in World-Partition cells. FK-22 proved those cells are enumerable offline (7,300 packages parsed, 0 failed).
- ⚠ Interacts with **MOVE_Walking**: S94 iter1 crashed on `UWorld::AddToWorld` for a new WP cell in Walking mode — but that measurement predates `gft_ready_fix` on this route, `KANIMREF`, and the removal of the separately-lethal standing `.text` patch.

#### ★★ 6. No on-screen lesson text

`WBP_BasicTutorialOverlay_Root` has **0 instances** while its children (`WBP_Augment_TutorialProgressTracker`, `WBP_TutorialDialogueBox`) **are** instantiated — the content constructs, the container does not. Nobody has read `bpdump_Comp_GameState_TrainingBase_ALL.txt` / `bpdump_Comp_PlayerController_TutorialObjectives_ALL.txt` (both already on disk) for `CreateWidget`/`AddToViewport`.

#### ★★ 7. FK-2 — input: the belief is dead, the successor question was never asked

221 legacy `+ActionMappings` ship against `DefaultPlayerInputClass=EnhancedPlayerInput` (Enhanced **classes**, legacy **data**); 186 actions + 16 axes live per-player. **The table is proven to EXIST and NOT proven to DRIVE.** Today the hero is a **puppet**: `tutorial_launch.cpp:3037` reads WASD with `GetAsyncKeyState` and pokes CMC velocity; `:366` records *"forced AddMovementInput produced ZERO accel/velocity."*

⚠ The S114 `DebugExecBindings` addendum is the standing warning on this exact class: **16 entries config-loaded, correctly parsed, live at Num=16, and read by nothing** (0 accesses at disp `0x1A8` vs a 925-access control).

⚠ **Correction found this session:** S91/S92 record `GetWASDInputs` as *"149 bc, detects W/A/S/D presses"*. The shipped bytecode is **5 entries, `FUNC_BlueprintPure`**, calling `GetPlayerConfigManager` + `GetMovementText` — it **formats the keybind prompt**. The WASD lesson completes by **overlap**, not keypress. Input was never that lesson's blocker.

★ Relevance is higher than FK-2's own row states: **most of the ~30 `TrainingQuest_Basics_*` steps are input-verb lessons** (WASD, Jump, LMB, RMB_Use, Q_Use, Dash_Use, Ult_Level, Glide, Sneak_Use, Ping, Recall, ShopInteract). The tutorial's objectives *are* the input verbs.

#### ★ 8. Cosmetics cascade — real, and already routed around

**[M]** 0 `LokiCosmeticsController` instances; `GetBaseCosmeticsController` returns null; five orchestrators all leave `controller=0, Mesh=0`. ⚠ But S93/S98/S99b built the body directly and confirmed rendering three ways. It blocks weapon-in-hand, ability VFX and team colours — not movement. `tutorial-playability-plan.md:67` explicitly flags it as **neither confirmed nor refuted** since S93.

#### ★ 9. A completed tutorial credits nothing

`NewOnboarding_Complete*` and `CompleteAllTutorialMaps_Base` are in `missions.go`'s **deliberately unmapped** block ("no match stat corresponds"). The only increment route is the admin `POST /revival/missions/match-result`. No document records the client ever POSTing a match result for any mode. `Comp_GameMode_EoGFinisher` is **live and enumerable** (`0x1B37ED25CE0`, from an archived S124 result) and has **never been bpdumped**.

#### ★ 10. FK-24 — re-scoped, deprioritise

The corrupt `ViewTarget.Target` byte was FK-7's suspected killer; FK-7 closed as our own patch, so this is now an **~8 %-per-launch camera-corruption nuisance**, not a killer. ⚠ It is still the player's camera breaking on 1-in-3 sittings, so "nothing on the critical path" is slightly too strong. Cost ≥6 launches at FK-31 rates. **Not worth it before abilities.** ⚠ The probe was killing the game and its kill was filed as a game crash for a full session.

---

## B. THE LEVEL-PLAYABLE SET

### B.0 The structural fact that organises everything (and is stated in no doc)

**The seven queue ids split into TWO CLIENT PATHS, and the split is measured.** Native `UPartyManager::IsSpecialQueue` (fn `0x5854F5F`, 1903 B, `.pdata`-exact) hardcodes the complete set:

```
{ practice, customgame, dropin, tutorialNew, training }   -> TryStartSoloMode -> POST /startSoloMode
{ default, deathmatch, bots, tournament, armorydeathmath } -> TryJoinQueue     -> POST /joinQueue
```

⇒ **PRACTICE and TRAINING are not "another mode to build" — they are the tutorial's own already-working path pointed at a different map.**

### B.1 Solved for every mode

| Item | Status |
|---|---|
| **FK-5 — "QoS UDP ping gates BATTLE/PRACTICE"** | **REFUTED S105.** `QosManagerServerUrl=` empty in all 12 env sections; no `ULatencyMeasurer` had ever been created. It pointed the roadmap at a protocol reimplementation for ~45 sessions. Empirically closed S133: FIND MATCH works with **no UDP responder involved**. |
| **FK-5c — `FParty.State` gate** | **FIXED** (`interactive.go:1911`, `"state": "Default"`). Measured on the wire S133: `POST …/startSoloMode?mode=practice` → **200**. ⚠ Three docs still assert it as a live blocker. |
| **FK-40 — the S60 queue trim** | **RETIRED S122.** All 10 queue ids default; `UPartyModel.Queues` 4→10. ★ Its stated mechanism **does not exist** (`CanControlQueue` calls `GetLevelGameFeatureUnlocked` **once**, with a hardcoded `{GameFeature,"Ranked"}`, only to format text). ★★ **A workaround that removes the TRIGGER is indistinguishable from one that fixes the CAUSE** — the trim made the missing `setTargetQueues` handler unobservable for ~60 sessions. |
| **FK-5d — `TryJoinQueue`'s page is 100 % zero** | **STALE.** `0x5875000` DARK→LIT (S133 party/queue sweep). The most-cited dark address in the repo (11 citations) and every citation is now false. |
| **S133 — FIND MATCH** | **WORKS.** `joinQueue` + `leaveQueue` served; response must be an `FParty` under an advanced `Version` (via `SetParty`'s monotonic gate); the field is **`state: "Matchmaking"`, not `inQueue`**. ★ The ~10–35 s re-POST **is** the rejection symptom. |
| **ARENA level lock** | Openable from the backend: `featureToggles["queue.restrictions.deathmatch"].Config["Level"]="0"` — a **third, runtime-concatenated** toggle key category invisible to both S121 censuses. Flown A-B-A. Default is EMPTY, and `AccountPass.Level` is **0** on the live wire. |
| **FK-41 / S130 — the pooled-spawn NULL** | Not the actor pool. `cmp byte [CDO+0x6C],0; jne -> NULL`; `AActor+0x6C = bCanEverReplicate`. **One CDO byte makes the drop pod spawn** (+2 census). ⛔ Diagnosis, not a shipping fix. |
| **S131 — the pod** | Initialised, alive, **flying at a cooked 20,000 uu/s** — and it flies *because* `StartPodGameplay` never ran, because `LokiIsServer()` is `xor al,al; ret`. |
| **S132 — the dismount** | ★★★★★ **A working deploy primitive.** 7 detach calls / 4 launches / **6 moved the hero**; flight 2 landed it at a chosen `LokiPlayerStart` **1,488,146 uu from the pod**, where it settled to Z=90.15 and held **bit-for-bit across 9 s** — un-hidden, collided, gravity-affected, standing on real terrain. Risk class DATA. |

### B.2 Per mode — the first hard blocker

| Mode | Queue id | Path | First hard blocker | Cost to move |
|---|---|---|---|---|
| **PRACTICE RANGE** | `practice` | **SOLO** ✅ chain works end to end | `buildTutorialMatchInfo` **hardcodes** `MapName=/Game/Loki/Maps/Tutorial/LVL_Tutorial` + `GameMode="tutorialNew"`; nothing reads back `st.SoloMode`. Then: no non-tutorial map has ever been force-opened. | **Two edited lines + one launch** |
| **TRAINING MODE** | `training` | **SOLO** ✅ | Identical. Own alias `TrainingMode` → `BP_PracticeGameMode_Training_C`, own GameState, two maps. | Same |
| **CO-OP VS. AI** | `bots` | matchmaking | ⚠ **It is a Skylands BATTLE ROYALE** (`SkylandsBRBotsGameMode`), not FFA. Nothing answers the queue; past that, the full drop chain + a 2,216-package map never loaded. | High |
| **ARENA** | `deathmatch` | matchmaking | **Host gamemode UNIDENTIFIED.** 4v4 per its own shipped description; `BP_FFAGameMode_C` is MaxPlayersPerTeam=1 so it is **not** FFA; no `Arena`/`Deathmatch` alias among the 34. [S] LastMan family (`BP_DeathCircle_Arena` sits under `Objectives/Lastman/`). Plus the level lock. | Offline dump, then unknown |
| **TOURNAMENT** | `tournament` | matchmaking | Same "nothing matches", then BR bracket chain. ⛔ **Seasons are a dead end** — no packed `LokiDataAsset_Season` in 69k assets. | Low priority |
| **BREACH** | `default` | matchmaking | The deepest stack: no matchmaker → drop phase (subscription + stripped getter) → **Skylands_WP never loaded**, 0 of 2,216 packages carry any drop marker → 60-player replication → the DS, parked at S39. | Correctly last |
| **CUSTOM GAME** | `customgame` | SOLO | S133: *"the entry point is elsewhere and is unidentified"* — **REFUTED, see E-3.** | Backend only |
| **FFA** | *(none)* | — | Fully decompiled and fully wired in the CDO, and **it has no queue id**. Its only spawn primitive is `SpawnPlayer` (a stub). | Blocked on FK-1 |

### B.3 The two blockers common to all four matchmaking modes

1. **Nothing answers the queue.** `playerState.InQueue` has **no reader that arms a match**. `handleCoreGamePlayer`'s gate is `forceTutorialMatch || st.SoloMode != ""`. The mechanism is already proven for the solo path (S107: MatchID armed → client fetched the match doc → attempted travel, 13 s after login).
2. **A match-found signal must be HTTP** — `matchmakingNotif` and `dsNotif` are among the 26 unbound types; 21 of the 23 bound delegates belong to one `USocialManager`. ⚠ **Re-graded per Adjudication #2**: measured at the menu, never in a queued state.

---

## C. THE SHARED SPINE — the dependency chain, in order

This is the most important section. Five separately-tracked walls are **one decision**, and it has a root.

```
ROOT  [M]  Loki::LokiIsServer()  impl 0x0F7EB60 = xor al,al; ret   -> ALWAYS FALSE
           Loki::LokiIsClient()  impl 0x0B9E1F0 = mov al,1;  ret   -> ALWAYS TRUE
           "One decision to remove SERVER AUTHORITY."  Auth* enriched 42.4% vs 8.30%, p=1.6e-28
                 |
   +-------------+---------------------------------+------------------------------+
   |                                               |                              |
 (1) C++ IMPLS STRIPPED                     (2) ONE GETTER DELETED          (3) BLUEPRINT EXEC-PIN
     0x0F7EB50 = xor eax,eax; ret               0xF7EB50, 3 consumers           GATES ALWAYS SAY
     0x0F7EC20 = ret imm16 0 (VOID)             (mount, pre-spawn, enter)       "NOT SERVER"
                 |                                       |                       0x1311870 = mov [rdx],0
                 |                                       |                              |
  SpawnPlayer -> nullptr                     AuthPlayerEnterWorldAttachedToRidable   ServerOnly /
  AuthSetSpawnTeamLeader -> void               -> "failed to get the round game mode" ClientOnly /
  SetDropLeader -> void                        MEASURED 0 -> 2, one per call          ClientServerSplit
  OverridePlaneLocations -> void                       |                              CheatsEnabledOnly
  AuthAddPlayer / AuthRemovePlayer -> void     [M] the OBJECT EXISTS and passes                |
  AuthSetCanJump -> void                           the wall's OWN IsA check.                  |
        |                                          Only the ACCESSOR was deleted.             |
        v                                                                                     v
  * GAS bind never happens  ------------------------------------------------------>  * ProgressObjective
      AvatarActor = NULL, ActivatableAbilities = 0                                       can never count
  * PlayersInside / PlayersAttached read Data=0 Num=0 Max=0                            * overlap binds
      (the ONLY reflected writers of either array do nothing)                            never installed
  * GetTeamDropLeader -> null -> PilotPlayerState null                                 * DropPlane
  * StartPodGameplay never runs -> the pod never stops flying                            ReceiveBeginPlay
                                                                                         bind never runs
```

### The workaround pattern that WORKS — and its measured boundary

> **When a stripped stub sits between you and a behaviour, do NOT try to satisfy the stub. Transcribe the surviving function's SUCCESS TAIL, hand-assemble its persistent output using the game's own allocator/helpers, then invoke the next real function in the chain.**

Proven four times: **S123** (`AddToRoot` registry insert), **S130** (`CDO->bCanEverReplicate = 0`, one byte → the pod spawns), **S132** (`ResizeGrow` + `AuthPlayerDetachPlayerFromRidable` → a hero standing on terrain), and it is what **GAP-1's Func swap** would be a fifth instance of.

**Boundary, measured:** the stripped population is **BOUNDED for deploy** (~23 stubs, enumerated, almost all pure state mutations a data poke can substitute for) and **UNBOUNDED for gameplay** (~200 across 40+ classes). ⚠ The census is **blind to Angelscript entirely** — 0 records for `ALokiDropShip`/`ALokiDropPod` — so it says nothing about the half that works.

### Foreclosures on the spine — do not re-attempt

- ⛔ **`0xF7EB50` cannot be poked**: `33 c0 c3`, three bytes, **zero memory operands**. A `Func` swap is dead too — thunk `0x5456380` has **0 direct callers**; the AS callers reach the impl by rel32.
- ⛔ **`AuthPlayerEnterWorld` is not a way round**: it consumes the same getter un-gated *and* requires the PlayerState already in `PlayersInside`. **No sibling is left to try.**
- ⛔ **The `[TeamState+0x688]` poke is dead**: **[M] ZERO live instances** of any class containing `TeamOnly`.
- ⛔ **The S55 direct-thunk primitive cannot call Angelscript UFunctions** — `Func = 0x0` (Adjudication #8). Use `ProcessEvent`, **slot 78 / disp `0x270`**.
- ⚠ **ORDERING TRAP:** poking `PlayersInside` (`+0x120`) *first* makes `HasEverContainedPlayer` true, turns the wall into a **silent** no-op and destroys the error-line receipt.

---

## D. NOT-PLAYABILITY — method/instrument FKs, considered and excluded

One line each; they are excluded from A/B/C but several **gate** experiments there.

| FK | Why not playability |
|---|---|
| **FK-3, FK-4** | `.rdata` coverage / string-xref. Pure instrument; both settled S104 and both revived a technique. |
| **FK-8** | `SecondsSinceStart` is not always 30. Crash forensics. ★ But it contains a named **gameplay** family — 17 records at one assert, 11 `ALokiGameMode::Login failed to Login` + 6 `PlayerState is null` — that nobody has joined to the spawn path. |
| **FK-9** | Crashpad capture. Fixed and shipped. ⚠ Demoted by FK-20: Sentry dumps hold **0 bytes** of the game image (`Flags = MiniDumpNormal`). |
| **FK-10** | The protector is bespoke `packer/3.3.1`, not VMProtect/Themida; `runtime.dll` is **plaintext** and disassemblable offline. Governs the risk model, not any mechanism. ⚠ Unresolved index-base ambiguity on the `packer0 0x1831C0` vtable — do not build on either index. |
| **FK-12** | "Steam must be running." N=1, never retested, propagated to 8+ files. Lowest-value open item in the register. |
| **FK-16** | Voice. A level is playable without it. |
| **FK-17** | The CEF-shell belief. Refuted three ways. ★ By-product: retiring `missions_fix` removed one manual-map + one transient `.text` patch from every launch. |
| **FK-18, FK-19** | Multi-state merge. Both settled S121; FK-19 recovered 246 pages including character-movement code. |
| **FK-20** | ★★ Instrument, but the **highest-leverage** one — 31 stale "this page is dark" claims, two of them on the playability path. |
| **FK-25** | Marker truncation. Corrupts multi-launch A/B denominators. **[V]** One-line fix at `:14715`. |
| **FK-28, FK-29** | GC reachability bits / SerialNumber semantics. Pure instrument. ★ FK-29's lesson transfers directly: **redundant, disagreeing witnesses are what turn a wrong rule into a caught rule.** |
| **FK-33, FK-34, FK-38, FK-41** | Batched instrument false-knowns. ★ FK-41's `.data` `{name_ptr, exec_thunk, impl}` record table gives REAL/EMPTY **without the page being decrypted** and is under-used. |
| **FK-31, FK-32** | The staging hazard (**22/82 launches**, 27 %) and the `0x0000DEAD` residual (**3/36 armed windows**). **Not playability — the price of every experiment in A and B.** Budget on **armed windows reached** (~2 of 4 launches), never on launches. |
| **FK-14** | usmap container-inner / enum-underlying types ~70 % wrong. ★ Load-bearing: **enum VALUE tables and struct/property names ARE trustworthy** — that is what made `state="Matchmaking"` safe to fly. **`CVars` is a TMap, so the usmap is the wrong oracle for it.** |
| **FK-13** | Console/exec. Instrument, but it **ships 42 live gameplay verbs** — treated as an (A)/(B) lever above. |

---

## E. GAPS — playability blockers with NO FK number

| # | Gap | Why it matters | Cheapest move |
|---|---|---|---|
| **E-1** | **The exec-pin gate family** (§A.2 #1) | The systemic cause of "simulation doesn't run", engine-wide. **The single biggest finding in this audit.** | Heap Func swap / bytecode edit; readback `ProgressObjective` 0→1 |
| **E-2** | **`buildTutorialMatchInfo` hardcodes `LVL_Tutorial`** | The two solo queues that are one step from working both arm a **tutorial** match | ~5-line backend change |
| **E-3** | **The CUSTOM GAME entry point IS identified** | **[M]** `WBP_ActivityPickerScreen::InitializeQueues` stmts 33-38: `GetNextOrCurrentTimespanForAction("startCustomGame")` gates the nav entry. [I, strong] the container is `ClientConfiguration.PlaytestWindows` + `PlaytestEnabled` — **grep for `playtest` in `loki.go` = 0**. Custom games bypass MMR, matchmaking, queue eligibility **and** region latency, and would host any of the 34 gamemode aliases with no matchmaker. **A textbook FK-20 instance: written down at S105, declared unidentified at S133.** | Serve the two fields, bump the (content-hashed) eTag |
| **E-4** | **`InQueue` has no reader that arms a match** | All four matchmaking modes | Extend the `handleCoreGamePlayer` gate behind a knob |
| **E-5** | **The force-open target is a TEXT FILE, not compiled in** | `tutorial_launch.cpp:119` `kCmdFilePath` → `docs/tutorial-launch-cmd.txt`, read by `LoadCommand()` at inject time — *"edit + reinject, no rebuild"*. **0 of 34 non-tutorial `GameModeClassAliases` has ever been used; 1 of 91 `LVL_*` has ever been opened.** ⚠ **Precondition, free to check:** `fo` patches exactly **five** native CDO vtables (`ALokiTutorialGameMode`, `ALokiRoundGameMode`, `ALokiGameMode`, `ALokiBattleRoyaleGameMode`, `ALokiDropInGameMode`) — BREACH is pre-covered; any target whose gamemode does not inherit one of the five dies at `Login`. | One line + one launch |
| **E-6** | **`KWIREGAS` defaults ON** | Every sitting already spawns a GAS carrier, builds an ASC and forces `ROLE_Authority` before anyone reads anything. It is why `s111-asc-census.md` needed a retraction. **The ability arm runs inside the flag it must control for.** | 162-flag audit, KWIREGAS first |
| **E-7** | **The HUD has never been asked about** | No row in any capability ledger. An ability bar drawing four icons would be a one-glance witness for the GAS work. | One read-only census |
| **E-8** | **`Extra.FeatureToggleOverrides` + `GameConfig.CVars`** on `/core-game/matches/{id}` | CRITICAL-ranked at S101, **never served** (`grep` = 0), on a route we already serve. `ELokiGameFeatureToggle` is the **gameplay** toggle enum: `InfiniteMana=95`, `GoldForEverything=100`, `TrainingBattleRoyale=63`, `BotsKeepMatchesAlive=96`, `EnableTalentSystem=12`. ⚠⚠ **Not the same system A-14 closed** — never reason from one to the other. | Backend only; type from `binds_members.csv`, **not** the usmap |
| **E-9** | **`ULokiRespawnComponent::Respawn` / `UFFABotSpawnerComponent::BeginPlay`** unprobed | Named STILL UNPROBED by FK-1 at S113; their sibling `SpawnDropPodForTeam` was probed and produced four sessions of progress. ⚠ Both need **ProcessEvent**, not the S55 thunk. ★ AS UClasses **are** registered in a loaded map (`fk22 §19.1`). | Offline grade first, then one call |
| **E-10** | **`SafeTeamSpawnPathfindingAnchor` map census never run** | FFA hard prerequisite #1. `GeneratePlayerStarts` returns true **unconditionally** even on a zero-hit scan, so an anchorless map fails silently with `% 0` on first respawn. FK-22's 7,300-package sweep already exists. | Minutes, offline |
| **E-11** | **The return leg** | Once `/core-game/players` reports a MatchID it does so **forever** ⇒ the client believes it is already in a match and every START is a silent no-op. **Already observed at S107.** No repeatable playtest loop exists without this. | Read what `CanDisassociate` gates; clear MatchID on match end |
| **E-12** | **No acceptance predicate** | §9.1: *"There is a goal name; there is no acceptance predicate."* §9.2's verdict — the tutorial route is *"a local maximum that has never been scored against alternatives"* — is **still literally true**: LVL_Practice, FFA/Arena-with-bots and custom games have all still never been attempted. ★ Counter-observation §9.1 could not have had: **E-1 is engine-wide**, so its value survives whichever target is chosen. | One paragraph |
| **E-13** | **56 `.mp4` (416 MB) loose and unencrypted** | `InGameTutorial/` has **13 clips mapping 1:1 onto the lesson chain**, and `WBP_InGameTutorialVideo` is one of the tutorial's three shipped widgets. For a (T) goal defined as "the tutorial as a played experience", these **are** the acceptance criteria. **0 hits across the repo in ~32 sessions.** | Watch them |

---

## F. THE STALE RE-GRADE LIST

**Re-grade before believing. Ordered by consequence.**

| Claim | Where | Status |
|---|---|---|
| **`0x5875000` / `TryJoinQueue 0x5875E90` is 100 % zero** — the most-cited dark address (11 citations) | `ignorance-map:401,2271`; `fk5-battle-gate-settled.md:88,420,942`; `coverage-audit:187,685`; +4 | **LIT.** FK-5's own #1 residual, and its prescribed command (`strxref.py func 0x5875E90`) is still unrun. |
| **`0x1F8CFC0` all-zero ⇒ the ping packet format is unreadable offline** `[M]` | 7 sites incl. `fk5-battle-gate-settled.md:664` | **Wrong when written.** It is a ~300-byte wrapper tail-calling `0x1F8BE90`, **LIT in every image this project has ever taken.** ⇒ *check the callee*. |
| **`TryUpdateAbilitySystem` impl `0x56CE5F0` — all-zero page, "clean negative"** | `fk3-fk4-settled.md:529`; `strxref-open-questions.md:198` | **LIT** (and LIT in `merged2`, i.e. stale since 2026-08-14). FK-30's "the bind is not reachable" partly rests on it. **Never read.** |
| **16 COVERAGE-BLOCKED `(class,func)` keys on page `0x5456000`** (the five `AuthPlayer*` + `GetLandingTeleportLocation`) | `fk22:4,154,613,662` | **3,860/4,096 non-zero.** FK-22's own note: the blocked/covered split there is a **page boundary, not a semantic one**. |
| **`InitAbilityActorInfo` is C++-only / the BIND is not reachable** | `ignorance-map:1690`; `fk2-input-settled.md:823` (U6) | Narrowly true, **operationally obsolete** — plain direct calls to non-reflected natives became standard at S123. **And the register never records the found address.** |
| **`Party.State` is never served ⇒ PRACTICE / every solo mode dead** | `coverage-audit:178`; `fk5-battle-practice-gate-s105.md:20,403` | **FIXED** (commit `8e523ab`). Three docs still assert it. |
| **`setTargetQueues` / `joinQueue` NOT SERVED** | `fk5-battle-practice-gate-s105.md:60,68` | Both served (S122 / S133). |
| **"The hero owns no ability system"** | `CLAUDE.md:22-23` | Killed by FK-30 at S111. The auto-loaded digest mis-sizes the frontier. |
| **"script UFunctions are callable by the S55 recipe, unchanged"** + **"slot-56 `ProcessEvent`"** | `CLAUDE.md:2316`, `:2681` | **Both measured false** (`fk22 §19.2`, §20.1). This is the primitive documentation every shim is written against. |
| **"we run no responder — Next task: a UDP echo responder"** | `CLAUDE.md` region block; **and `fk20-coverage-settled.md §5.1`, written S133** | `server/internal/pingecho/pingecho.go` shipped at commit `297b0c5` (2026-08-15). ⚠ The bug worth carrying: five green tests, every real ping dropped — the client sends **30** bytes, stock UE is 22. |
| **"The archiver runs pre-launch AND post-exit"** | `CLAUDE.md:3000`, `:3147` | One call, pre-launch. ⚠ Do **not** "fix" by adding a post-exit call — `launch-redirect.ps1:461-481` records that it was added, measured as pure duplication, and removed. |
| **"The script blocks until the game exits"** | `CLAUDE.md:2799` | False — `& $exe` returns in ~1 s; the staging schedule depends on this. |
| **`Marker()` opens `CREATE_ALWAYS` at `:4919`** | `ignorance-map:1576` | **[V] False.** `Marker()` is `:404`, appends. The truncate is `Worker()` at `:14715`. |
| **"`bots` = FFA-with-bots, no drop plane, no storm"** | `ignorance-map §5.3` | `bots` → `SkylandsBRBotsGameMode`, a full battle royale. |
| **"the CUSTOM GAME entry point is unidentified"** | `s133-joinqueue-find-match.md:210-215` | Identified in a bpdump the project generated at S105 (E-3). |
| **"31 stale claims" / `regrade_blocked.py`** | `fk20-coverage-settled.md`; `scratchpad/s133/tools/` | **The protocol itself is stale**: re-run against `merged10` gives **47 stale of 55**, and the tool's own DARK control (`TryJoinQueue`) now reads **LIT**. ⚠ `dark_cited_functions.txt` is the **still-dark** list, not the stale list — several of its top rows are lit. |
| **Canonical cold image** | `CLAUDE.md` says `merged8`; `strxref.py:66` defaults to **`merged2`** | **[V] `merged10` exists** (Aug 20 21:29, 16,755 / 30,281 = 55.33 %) and is published at `fk22:7`. Every un-flagged `strxref.py func` run has been grading against a **54.95 %** image. |
| **"Tutorial completion — OPEN, never reached"** | `coverage-audit:268` | The chain **was** walked at S93 — synthetically. Rewrite to name what is actually missing. |
| **"Native cheat dispatch is closed"** filed under §4.2 **CONFIRMED** | `ignorance-map:2246` | Supporting facts true; the bucket is wrong — FK-13 opened 42 live verbs on that surface. |
| **`BP_TrainingSkill_*` is practice-mode gated** — filed as a **wall** | `ignorance-map:2247` | True, and **read backwards**. `ValidStates = BP_PracticeGameState_C` means that lesson system is the **designed content of LVL_Practice**, already loaded and idle. **A signpost, not a wall.** |
| **"Combat / abilities / drop phase — BLOCKED by FK-1's four stubs"** | `fk20 §8 row 9`, written S133 | Written **one session after** S132 walked round that exact family. Split into three rows with separate statuses. |
| **`ALokiPlayerCheats` impls "dark everywhere"** | `fk6-cheat-surface-settled.md:740-742` | Re-grade with the `.data` record table, which works on undecrypted pages. `CheatSetTeamEliminated` impl `0x55cf760` = **REAL**; `CheatChangeHero` impl `0x1384d50` = **REAL**. Only `SpawnBot 0x556D910` is genuinely dark. |

**★ And the protocol amendment this audit earned:** FK-20's rule is *"before recording 'this page is dark therefore X is unreadable', CHECK THE CALLEE."* Add a third dimension: **check the WORLD STATE the negative was measured in.** S93's overlap null (measured in a world frozen at `EGP_BeginInit`), FK-15's `matchmakingNotif` null (measured on a client that had never queued) and FK-30's original GAS null (measured in an unloaded world) are all correctly-calibrated instruments aimed at a world that has since changed. **A dark page and a stale world state produce identical-looking `[M]` negatives.**

---

## G. RANKED NEXT LEVERS

### G.1 OFFLINE / FREE — zero launches, zero risk

| # | Lever | Settles |
|---|---|---|
| **1** | Point `regrade_blocked.py` at `merged10`, replace the broken DARK control (`0x5A6AC40` or `0x556D910` both still dark), re-emit. Update `CLAUDE.md`'s canonical pointer **and `strxref.py:66`'s `merged2` default.** | Every "is this claim still true" judgement downstream |
| **2** | Re-grade all 100 drop-class `(class,func)` keys with the S130 `.data` record table **plus** a `merged10` disassembly of page `0x5456000`. | The 16 COVERAGE-BLOCKED keys; the mount's success tail |
| **3** | `strxref.py func 0x5875E90` — transcribe `TryJoinQueue`'s preconditions. | FK-5's own #1 residual; what the client needs before a queue is real |
| **4** | `strxref.py func 0x56CE5F0` — disassemble `TryUpdateAbilitySystem`. | Whether the reflected near-miss on the GAS bind has a usable branch |
| **5** | Transcribe `SpawnAndMoveLokiCharacter_MoveStep 0x55C1B20` + `GetLandingTeleportLocation 0x55D89F0`. | Whether the **MOUNT** can be hand-assembled the way the dismount was |
| **6** | Enumerate `LVL_Tutorial`'s `_Generated_` WP cells for `BP_TutorialTrainingQuestSequencer` + `TrainingQuest_Basics_*`. FK-22's parser already exists. | Turns "never spawned" into a named cell / data layer (§A.2 #5) |
| **7** | `bpdump BP_PracticeGameMode @props` + the four siblings (**never dumped**), and check whether its native parent is among `fo`'s five patched CDO vtables. | The precondition for the whole LVL_Practice route |
| **8** | Audit all **162** `#define K*` defaults in `tutorial_launch.cpp`. **`KWIREGAS` first.** | Makes the ability arm interpretable; two prior ON diagnostics silently damaged every run for weeks |
| **9** | Grep `bpdump_Comp_GameState_TrainingBase_ALL.txt` + `..._TutorialObjectives_ALL.txt` for `CreateWidget`/`AddToViewport`. | Who creates `WBP_BasicTutorialOverlay_Root` |
| **10** | Read `CVars` / `FeatureToggleOverrides` types from `binds_members.csv` (**not** the usmap). | Types E-8 safely; a wrong-typed matched key sinks the whole MatchInfo doc |
| **11** | Re-run FK-22's 7,300-package sweep for `SafeTeamSpawnPathfindingAnchor`. | FFA hard prerequisite #1 |
| **12** | Fix `tutorial_launch.cpp:14715` (marker truncate) and `fkdis.py findptr`'s 200-row cap. | Multi-launch A/B denominators; every stripped-stub grade |
| **13** | Watch the 13 `InGameTutorial/` clips. | The acceptance predicate for (T) — §11 A-1, still undone |

### G.2 BACKEND-ONLY — no shim, no injection, no `.text` write

| # | Lever | Settles |
|---|---|---|
| **14** | Make `buildTutorialMatchInfo` key `MapName`/`GameMode` off `st.SoloMode`; keep `ConnectionDetails.address` **EMPTY**. ⚠ **State the reason in the code** — `OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`, so only the locally-parked route can ever be authority. A successor "improving" this by serving a DS address would silently destroy objective completion. | The single cheapest path to a second map |
| **15** | Serve `ClientConfiguration.PlaytestEnabled` + `PlaytestWindows` with a `startCustomGame` window spanning now. | Whether the CUSTOM GAME nav entry appears (E-3) |
| **16** | Extend `handleCoreGamePlayer`'s gate to `\|\| st.InQueue` behind a knob. | Whether the client escalates to `/core-game/matches` from a queue (E-4) |
| **17** | Serve `Extra.FeatureToggleOverrides` + `GameConfig.CVars` — one key first. | A per-match gameplay control plane (E-8) |
| **18** | Serve `CoreGameBotConfig` on the existing gameConfig — **for `bots`/`arena`, not the tutorial.** | Bot fill |
| **19** | Serve a non-empty `FMatchHistory.Matches` (`AGS_MATCH_HISTORY=minimal`, already shipped). ★ Cheaper variant: the `Cheat.Onboarding.MatchHistoryCount` **cvar**, settable from the user `Engine.ini` with no backend change at all. | Whether the onboarding preselect on BASIC TRAINING releases |

### G.3 COSTS A LAUNCH — ranked by (value × cheapness)

| # | Lever | Pre-registered readout |
|---|---|---|
| **★1** | **Flip `ServerOnly` (and `ClientServerSplit`) via a heap `Func` swap or a bytecode edit**, then call `ProgressObjective(1)` on the live `Comp_GameState_TrainingBase_C`. | `CurrentObjectiveCount` **0 → 1**. Settles E-1, GAP-2 and GAP-3 in one call. ⛔ Never patch `0x1311870` in `.text`. |
| **★2** | **Call `InitAbilityActorInfo` at `base+0x447F410(asc, owner, hero)`** — SEH-guarded, own arm, no grant call in the same build, KWIREGAS accounted for. Resolve by name; do not hardcode. | `ASC.AvatarActor` becomes the hero pawn (the shim already prints `*** AVATAR IS THE HERO -- BOUND ***`). `ActivatableAbilities` **may stay 0** — a bind with zero abilities is a SUCCESS. ⚠ Do **not** use `IsAbilitySystemInitialized` as the witness; it reads the cache the shim writes. |
| **★3** | **Force-open `LVL_Practice`** — edit `docs/tutorial-launch-cmd.txt` + `tutorialMapName`, run the existing stager unchanged. | (a) `Load map complete …/LVL_Practice` ⇒ a second world is reachable and `BP_TrainingSkill_*` should self-arm; (b) `ALokiGameMode::Login failed to Login` ⇒ the slot-285 fix is mode-specific; (c) no travel ⇒ read `capture.log` for the MapName actually requested. |
| **4** | **FK-6 §6 steps 1 + 2b** — read a world ASC's Health, then `AdjustHealth(asc, −250)` and read back. | **750** ⇒ **damage achieved**, no enemy, no spawn, no cheat. ⚠ Step 4 (activation) is the highest-risk step, not the spawn — keep it in a separate run. |
| **5** | **Fly `play-atlanding-walk`** (`.text 944a27728053359e`, `-DKNOTELE=1 -DKFLYMODE=1`) against a never-dismounted control. Built, pre-registered, unflown. | Whether the dismounted hero is **playable where it lands**. ⚠ Only this build can answer it — `KFLYMODE` defaults to 5 = `MOVE_Flying`, and the control "walked" 2,926 uu at a constant Z of **13,240** (13 km in the air). ⚠ Grade a death as the Walking-mode hazard (S75/S81/S94), not the landing point. |
| **6** | **Rebuild `RM_DRIVECHAIN` / `RM_OBJCOMPLETE` from HEAD** (they inherit the non-`.text` Func-swap default), stage with the modern recipe, drive `GoToPhase → Combat` **first**, then re-run the S93 chain walk. ⚠ Diff the `.text` sha256 — three artifacts have shipped identical-but-differently-named. | Whether the lesson system behaves differently in a world that reached Combat |
| **7** | **Fly `cheatmgr` in a staged world** and execute `Summon` (a target dummy), then `Walk`. Verify with `LogLoc` **first**. | A combat target and the Walking-mode question, from an already-shipped build. ⚠ `God` emits nothing — never use a silent verb as the witness. ⚠⚠ **"The call returned ok" is never a success criterion.** |
| **8** | **Fly the `AddToRoot` recipe** (`.text +0x489F9B0`) with the free receipt `*(i32*)(base+0x99D3CA8) − *(i32*)(base+0x99D3CD4)` **+1 per rooted object**. Offline-derived, live-verified reads, **call untested**. ⚠ Confirm `KGCROOT=0` first — the old poke poisons the fix. |

### G.4 FREE RIDERS — read-only RPM on any sitting that is happening anyway

- **Re-walk the `Lobby` delegate table at 8-byte stride while queued** and check `matchmakingNotif`'s slot for `DelegateSize != 0`. Settles Adjudication #2 and either confirms HTTP-only *under the state that matters* or reopens the entire push route. ⚠ A 0x10 stride cannot see `+0x228`.
- **Re-read `OnActorBeginOverlap.InvocationList Num`** on the live trigger box **after** `GoToPhase` reaches Combat.
- **Census `BP_LokiSpawner_Basics` / `BP_Minion` / `WBP_UI_HUD` / `LokiHUDLayout`** in a phase-advanced world.
- **`dumpimage` at the end of every armed window** — S118's steerable decryption; S131 got a whole extra result plus +43 pages for free because a process was still up.

---

## The one-paragraph answer

**(T) The tutorial.** Objectives, camera, a visible animated hero and a five-lesson chain walk were all achieved at S93 and have been **dormant for ~40 sessions**. What blocks the tutorial as a *played* experience is three things, in order: (1) **the Blueprint exec-pin gates always return "not server"**, which is why `ProgressObjective` can never count and why the physical overlap bind is never installed — objective completion today is a synthetic poke, and the fix is one heap `Func` swap in a class measured at 0/16 deaths; (2) **`AvatarActor` is NULL** because the designed GAS bind routes through a stripped `SpawnPlayer` — and the replacement, `InitAbilityActorInfo` at `base+0x447F410`, was found, disassembled and written up as "TASK ONE" 22 sessions ago and **has never been called**; (3) there is **no combat target and only one streamed volume**, both of which are offline-answerable today. FK-7, FK-11, FK-13, FK-26 and FK-27 are the enablers that make those experiments affordable, and FK-31 is the tax on all of them.

**(L) Any other level.** Every gate FK-5 named has cleared: the queue list, `Party.State`, `setTargetQueues`, `joinQueue`, FIND MATCH. The blocker moved to two places. For the four **matchmaking** queues, nothing answers the queue and there is no push route — a match-found signal must be HTTP over a channel that already exists (`/core-game/players` → `/core-game/matches`) and has only ever named `LVL_Tutorial`. For the five **solo** queues — `practice`, `training`, `dropin`, `customgame`, `tutorialNew` — the client path is the tutorial's own, it works end to end today, and the only thing standing between PRACTICE and a second playable map is **a hardcoded string in `buildTutorialMatchInfo` and one line in a text file the force-open shim reads at inject time**. That is the cheapest untried experiment in the entire audit, and §5.3 ranked it #2 thirty-two sessions ago.