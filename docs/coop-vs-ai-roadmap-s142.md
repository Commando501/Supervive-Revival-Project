# CO-OP VS. AI — the roadmap, with an acceptance predicate at last (2026-08-24)

**Last updated:** 2026-08-25 (S147 canonical-input activation receipt and post-receipt `0xDEAD`).

**Produced by** a 5-lane adversarially-verified research pass (10 agents, `bot` / `hero` / `match` /
`push` / `ded`, each lane + a verifier) over the primary docs, then a determination pass. Zero
launches, zero injections. Every load-bearing claim below is graded `[M]` measured / `[I]` inferred /
`[S]` speculative and cites `file:line`. This doc answers ignorance-map **A-1** ("write the acceptance
predicate for done"), which had been open since S101.

---

## 0. THE ACCEPTANCE PREDICATE (operator-chosen, 2026-08-24)

> **DONE = the "Minimum bot-fight loop": on the tutorial surrogate world, ONE human-controlled hero
> CASTS AN ABILITY that DAMAGES and KILLS at least one HOSTILE ENEMY bot.**

That is the whole target for now. **Explicitly OUT of scope** (deferred to later targets — see §7):
scoreboard / objectives / score-counting, win detection, end-of-game screen, respawn, the full round
lifecycle, the `ags`->resident-shim live command channel, world SELECTION / Skylands / `LVL_Training`,
the `disassociate` return-leg, and autonomous bot locomotion-from-rest (the S138-S142 movement wall).
A stationary enemy bot the player kills SATISFIES this predicate; the bot fighting BACK is an in-scope
stretch, not a requirement.

⇒ **This collapses the problem to the TWO hardest walls and nothing else: (P) the player hero can
cast, and (E) an enemy bot is a valid, hostile damage target that dies.** Everything the last ~40
sessions built (bot spawn, controller, PlayerState, phase drive, walk-with-a-kick, the whole match-arm
chain) is either already done or not on the critical path to THIS predicate.

---

## 1. THE ARCHITECTURE DETERMINATION

**Route 3 (HYBRID): the client simulates the match locally; `ags` is the match director.** For the
Minimum bot-fight loop the `ags` half is nearly trivial (arm a match, already done) — the work is
client-side shim reimplementation of the two stubbed walls. The "server pushes and maintains state"
ambition is real but belongs to the LATER "server-maintained match" target (§7), not this one.

Why the other two routes are out:

| Route | Verdict | Basis |
|---|---|---|
| **2 — server-authoritative UE dedicated server** (`dedicated-server-stub` branch) | **Stay parked** | Reached server-authoritative POSSESSION of a Loki-typed character in the live tutorial world, held 3+ min (`coverage-audit-s101.md:305`, `next-session-prompt-s77`) — further than its own session-39 menu-crash implies. But **measured** structural ceilings no revival clears: no SUPERVIVE Server-target binary exists and `IsRunningDedicatedServer()` folds to constant false (`coverage-audit-s101.md:307` — acquisition, not engineering); only `ALokiMinionCharacter` is possessable (real heroes are `CLASS_Abstract` Blueprints the stub can't instantiate, `:305`); `OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`; pure-replication movement crashes. **The server-side gameplay code is `WITH_SERVER_CODE`-stripped from the only binary we have — absent whether we build a server or not.** It already donated its GAS movement recipe (`ds_hybrid.cpp:2370-2430`) to the local route. It adds nothing to Co-op vs AI at the highest cost. |
| **1 — client-authoritative local sim** | **The substrate** | `[M]` the client is `NM_Standalone` / `ROLE_Authority(3)` and engine `HasAuthority()` PASSES (`s137:314-329`, read off the client's own `Loki.log` `World NetMode = Standalone`). It HAS all the gameplay code. |

**The single root cause behind the walls:** `Loki::LokiIsServer()` is hardcoded FALSE
(`0x0F7EB60 = xor al,al; ret`; `LokiIsClient 0x0B9E1F0 = mov al,1; ret`). The `Auth*` stub family is
enriched 42.4% vs 8.30% empty (Fisher p=1.6e-28, `coverage-audit §C`) — a deliberate "strip server
authority from the client build." **The ENGINE grants authority; LOKI refuses it in code.** So the
walls are not UE denying a client authority — they are Loki's own empty stubs, and the fix is to
hand-reimplement each one on the client, which is exactly what the local-sim route does.

---

## 2. STATE OF PLAY — what is already `[M]` for this predicate

| Capability | Status | Evidence |
|---|---|---|
| World force-opens + stays loaded (`LVL_Tutorial` + `BP_LokiGameMode_Tutorial_C`) | **WORKS [M]** | active line `docs/tutorial-launch-cmd.txt:53`; login bypass = GameMode CDO vtable slot 285 + PC vtable slots **260 AND 273** (`tutorial-playability-plan.md:114-116`). ⚠ the S135 `LVL_Training`/PracticeMode line was never applied. |
| Hero spawns, possessed, walks + animates | **WORKS [M]** | S107/S108b via `sp` + `play`. ⚠ WASD is a **puppet velocity-poke** (`tutorial_launch.cpp:3046`, writes `CMC+0xE8` directly), NOT `AddMovementInput`; the player has no stock-chain input driver (`s141:643-648`). Irrelevant to this predicate (a stationary cast is enough). |
| Enemy bot **pawn** spawns with correct hero class | **WORKS [M]** | `SpawnClassBotAtLoc` / `SpawnBotTeamAtLoc` (3 game-chosen classes, three agreeing readouts, `s135:255-278`); flags `FUNC_Public|BlueprintCallable`, no `FUNC_Net`/`FUNC_BlueprintAuthorityOnly` (`coop-vs-ai-plan-s135.md:11,278`). |
| Bot gets a real `ALokiBotController` (live 21-node BT + 15-key Blackboard) + a real `BP_LokiPlayerState_C` | **WORKS [M]** | ARM D engine-CDO poke + ARM B/C (`s137:255-396`), external `obj_by_chain =LokiBotController` confirms. ⚠ **non-shipping** — process-wide CDO poke; a diagnosis, not a durable fix. |
| Match-arm chain (FIND MATCH -> MatchID push -> refetch -> `UTravelManager`) | **WORKS [M]** | S135 (`armqueue.go`, `s135:41/50/58`). ⚠ Not needed for the bot-fight loop — the world comes from force-open regardless; the arm just satisfies `fk24-stage.ps1`. |
| `ags` push channel (`NotifyResource` version-bump refetch) | **WORKS [M]** | `push.go:466`, wired `main.go:104`; drives `/core-game/players`, `/party`, `/progression`, `/match-history`. ⚠ match-*adjacent* only; no in-match channel. |

**Nothing above is a blocker for the predicate.** The predicate lives entirely in §3.

---

## 3. THE TWO WALLS THAT ARE THE WHOLE JOB

### 3.1 WALL P — the player hero cannot cast an ability

**Current status (S147): FIRST REAL ACTIVATION STATE MEASURED; STRICT ABILITY3-BP WITNESS OPEN [M].**
The AvatarActor bind (S143), native engine grant (S144), every measured MiniDash eligibility gate
(S145), and now a real active/cost transition are solved. After two exact Tab controls, a bounded
LeftShift hold changed the exact InputID-5 spec `ActiveCount 0 -> 1`, primary raw state `0/0/0 ->
1/1/1`, and registered Mana `10/10 -> 0/0`; the selected DLL contains no activation call. The exact
Ability3 Blueprint node remained absent, so the pre-registered strict BP-witnessed provenance label
is still incomplete. The process exited `0xDEAD` about 51 s after the last marker write, after CDO
restoration; no damage/kill receipt exists. The bullets immediately below are the historical S142
baseline; the S143–S147 result blocks later in this section supersede their open-status wording.

- `[M]` The ASC exists but is the SHIM's own (built by `KWIREGAS`, not the game — `s111` retraction),
  `AvatarActor @ASC+0x410` is **NULL**, `ActivatableAbilities = 0` (`s111-asc-census.md:508-514`).
  Writing `@0xF00` lands but binds nothing.
- `[M]` The bind was FOUND at S111 and **has never been called in 31 sessions**:
  `InitAbilityActorInfo @ base+0x447F410`, `rcx=ASC / rdx=Owner / r8=Avatar`, `AbilityActorInfo @
  ASC+0x418` (`s111-asc-census.md:568-607`). Grep of `tools/sigbypass-mod` for `447F410` /
  `InitAbilityActorInfo` = **0 hits** (re-verified live this pass).
- `[M]` The designed route (`ALokiGameMode::SpawnPlayer 0x0F7EB50 = xor eax,eax; ret`) that would
  wire the whole GAS bind is a stripped stub (`fk1-angelscript-settled.md:278-288`).
  `NM_Standalone`/`ROLE_Authority` does **not** bypass it — the stub never consults netmode. The
  wiring must be re-implemented by hand.
- `[I]` The grant/activate functions ARE reflected `[Native,BPCallable]` UFunctions on the ASC and
  are thunk-callable: `AuthGiveAbilityWithSourceObject` (`session-100-gas-api-dump.txt:13`),
  `TryActivateAbilityByClass/ByInputID` (`:67-68`). None ever called. Their impls are UNGRADED `[S]`.
  ⚠ the "42.4% `Auth*` empty" fold-risk is from a **different** (`drop/rideable`) population — GAS
  `Auth*` are client-PREDICTION bodies, almost certainly real; grade them offline for free.

⚠⚠ **`InitAbilityActorInfo` is NOT a UFunction** (absent from the S100 ASC UFunction dump), so the
existing `CallNativeGuarded` (UFunction/`FFrame`-shaped) will **not** serve it — the bind needs
**new SEH-guarded raw-call scaffolding**. "one launch" for the bind presumes that scaffolding is
written first. Risk class = **DATA, zero `.text` writes** (`fk-playability-audit-s134.md:130`), the
repo's safest write class.

⚠ **Control `KWIREGAS`** (default 1, `tutorial_launch.cpp:4870`): it already builds the ASC and forces
`ROLE_Authority`, so any bind reading taken with it uncontrolled is uninterpretable
(`fk-playability-audit-s134.md:132`). Gate it off (or hold every one of its writes constant) so the
bind is single-variable.

### 3.2 WALL E — no bot can be a HOSTILE, DAMAGEABLE enemy

**Status: BLOCKED [M], and this is the deepest and least server-substitutable wall.**

- `[M]` In `SpawnBot`'s LIVE run: `ServerSetHeroClass 0x556DE43 -> 0xF7EC20` (void fold) RAN with NO
  EFFECT; `SetPlayerTeam 0x556DE53 -> 0xF7EB60` (false fold) RAN with NO EFFECT; `GetTeamState`
  RETURNED NULL; that is the divert (`s138-flight3-divert-settled.md:57-62`).
- `[M]` `GetOrCreateTeamState 0x5634BD0` returns `nullptr` **unconditionally** — read from its 16
  instructions, NOT a fold-test artifact (it is a "sixth stub shape" that DEFEATS the two-state fold
  test, `next-session-prompt-s139.md:97-105`, the strongest form of this `[M]`); `SetNumTeams` is a
  void fold ⇒ `TeamStates` can NEVER be non-empty on a client. Measured `Data=0x0 Num=0`
  (`s138-flight3:76`).
- ⚠⚠ **THE decision-critical UNKNOWN, never measured: can the player DAMAGE a bot that has NO team
  index?** If team-0-vs-team-0 (or team-less) still allows damage, WALL E is far shallower than it
  looks and the predicate needs no team fix at all. If hostility gates damage, `ags`/a shim must
  supply team state by hand. **This one read reorders the whole E-track.**

### 3.3 The damage pipeline itself — never exercised, but cheaply provable INDEPENDENTLY

- `[M]` No character has ever taken damage on this route (`coverage-audit-s101.md:265`).
- `[M]` A self-contained witness exists that needs NO enemy/spawn/ability: write a live ASC's
  `Health=1000` (proves the field), then `AdjustHealth(-250)` — the game's own GE wrapper, one float
  — and read back `750` (`fk6-cheat-surface-settled.md:656-658,679-682`). ⚠ the readback depends on
  the starting Health, so step 2a (write 1000) MUST precede step 2b. `AdjustHealth` grep in the shim
  = 0 hits (never run).

★★★★★ **S152 MOVE 4 — VALUE-SEEDING WALL BEATEN VIA EXTERNAL POKE; ONE UPSTREAM SUB-WALL NAMED.**
Read `docs/move4-external-poke-PREREGISTERED.txt` for the full mechanism.
- **[M] Bind + AttributeSet REGISTRATION are live on the force-open route** (Move 4 flight 3).
- **[M] Attribute VALUES are ZERO on the shipped path** — no native code seeds `Health/MaxHealth` on
  hero spawn here. Stable state, unchanged across 11h uptime. This corrects the note above about
  writing `Health=1000` "to prove the field" — the FIELD is fine; nothing SEEDS it. The 4× external
  `WriteProcessMemory` (`Health.Base/Current + MaxHealth.Base/Current = 1000.0`) works, readback-
  verifies, and persists through S148's full lifecycle. Substitute for whatever native step is
  missing.
- **[M] S148's preflight (22 bits) reached `issues=0x0` for the first time on the force-open route.**
- **[M] S148's `thunkExact` check is UNSATISFIABLE by UE construction** — `tutorial_launch.cpp:21224`
  in the codex worktree tests `adjustThunk == g_modBase + 0x5516610`, but `adjustThunk` is the
  reflected `Func @+0xE0` (the UHT `execAdjustHealth` wrapper at RVA `0x5294270`), NOT the impl. For
  a reflected native function with parameters, the wrapper CALLS the impl (verified:
  `0x52942DF: call 0x5516610`). Rebuild path: either compare against the wrapper RVA, or walk the
  wrapper's tail-call chain to derive the impl dynamically. `0x5516610` itself is `PAGE_NOACCESS` on
  this build because nothing has ever executed it.
- **[M] `ULokiCharacter::AuthCheatSetHealth` is a FK-1-family stripped stub** — added to the FK-1
  register (5th entry). Not a Health-writing path. See CLAUDE.md FK-1 block.
- **The mover end-state IS data-drivable end-to-end.** Externally poked `Health.CurrentValue = 750.0`
  achieves the exact S148-expected outcome (matches `expectedCurrent=0x443B8000`), stable across
  4 samples. Doesn't prove the game's own AdjustHealth works, but proves the state model is coherent
  from bind→registration→values→post-adjust via pure external writes.

**Two viable paths to a CASE-H (game-native AdjustHealth) result:**
- REBUILD S148 with the `thunkExact` check corrected (compare against wrapper RVA, or derive impl
  dynamically), then re-fly. Requires codex worktree access.
- BYPASS S148 with a tiny CALL-ONLY shim that dispatches AdjustHealth via the S55 primitive (which
  trusts reflection and does no `thunkExact` check). One new injection, ~30 min build cycle.
- ★ **NEW candidate for a live target nobody has looked at:** `LVL_Tutorial.json` ships three
  `BP_LokiSpawner_Basics_*` + `BP_Tutorial_JouleBotManager`, and `SpawnJouleBot` is a `FUNC_NetServer`
  action that executes locally on the authority client (`fk-playability-audit-s134.md:144-146`). A
  possible pre-existing damage target, never probed.

---

## 4. ROADMAP TO THE PREDICATE (dependency-ordered, cheapest de-risking first)

### Phase 0 — FREE / OFFLINE (zero launches; settles what to build before building it)

1. **Grade the GAS grant/activate impls** (`AuthGiveAbilityWithSourceObject`,
   `TryActivateAbilityByClass`) and the `AdjustHealth` GE wrapper against `dumps/merged14.dump.exe` —
   real bodies or folds? (Expected real; confirm.) Free; de-risks WALL P and the damage pipeline.
2. **`bpdump` the hero kit ability classes** for a chosen enemy (e.g. `BP_HERO_Ronin` Ability1..3) to
   know what to grant. ⚠ kit classes currently serialize as `[0,5,0,...]` (the CUE4Parse container/enum
   defect, FK-14) — plan to read them **live off the CDO** instead, or apply the extractor CDO-default
   fix first.
3. **Grade `ULokiRespawnComponent::Respawn 0x5A6AC40`** offline (not in the predicate, but its status
   informs whether a killed bot's slot behaves) — still dark in `merged13`; re-grade against
   `merged14` or via the `.data` record table.

#### Phase 0 — RESULTS (2026-08-24, offline against `dumps/merged14.dump.exe`)

★ **DONE. The whole WALL-P + damage machinery grades REAL — not stubbed.** Method = the proven
`cheat_impl_census.py` approach (resolve exec-thunk -> final dispatch -> classify impl body against the
ICF fold set), cross-checked against `uesymbols.json`'s `secondary` and confirmed by hand-disasm where
the auto-resolver mis-picked a teardown. Grades:

| function (`ULokiAbilitySystemComponent` unless noted) | impl RVA | verdict |
|---|---|---|
| `AuthGiveAbilityWithSourceObject` / `BP_AuthGiveAbilityWithInputID` (grant) | impl **`0x13d4e60`** | ⚠⚠ **RETRACTED S143 — STRIPPED, not REAL.** This row first read "REAL, shared `0x1258bf0`" — WRONG. `0x1258bf0` (mult 11025) is a shared atomic FUObjectItem-flag helper called only conditionally with its return discarded; the actual impl is `0x13d4e60` (mult 2) = `mov [rdx],-1; ret` → returns `InvalidHandle` unconditionally. **Both reflected grants are FK-1-family stubs.** See the Phase-1 grant sub-wall below. |
| `TryActivateAbilityByClass` (`UAbilitySystemComponent`, stock) | `0x4493730` | **REAL [M]** — 60 ins / 237 B / 3 calls, exact pdata bounds |
| `TryActivateAbilityByInputID` | `0x5544f70` | **REAL [M]** |
| `TryActivateAbilityBySourceObject` | `0x5544fb0` | **REAL [M]** — 97 ins / 363 B / 5 calls |
| `AdjustHealth` (the damage GE wrapper) | `0x5516610` | **REAL [M]** — takes the float delta in `xmm1`, `ucomiss` vs 0, real 0x80 frame + branching |
| `AdjustArmor` (sibling control) | `0x5516160` | **REAL [M]** — `GetWorld`->call chain (confirms the grader on a known-real sibling) |

> ⛔ **S143–S147 RETRACTION OF THE PHASE-0 CONCLUSION:** WALL P was not “only the bind.” The table's
> reflected-grant row is stripped; S144 required stock native `GiveAbility`; S145 required explicit
> instance/attribute/Mana/charge eligibility work; and S146 shows that a valid activation called from
> the injected callback does not return and is followed by `0xDEAD`. S147 then measured a real
> InputID-5 activation/cost transition during controlled LeftShift with no shim activation call,
> although the named Ability3 BP event was absent and the process later exited `0xDEAD`. A REAL
> offline body proves code exists, not that the whole runtime route will work once the bind lands.
> `AdjustHealth` remains REAL, so the independent damage witness is still well-founded.

★ **Grant targets identified (`tools/asdump/out/binds_members.csv`):** `ALokiHeroCharacter` props 62-65 =
`TSubclassOf<UGameplayAbility> Ability1/Ability2/Ability3/AbilityDodgeRoll`; `ALokiCharacter` props 28-29 =
`TArray<TSubclassOf<UGameplayAbility>> CharacterAbilities / BaseCharacterAbilities`; and a
`LokiAbilityInputID` enum feeds `TryActivateAbilityByInputID`. **Read the class refs LIVE off the hero
CDO/instance** (the FK-14 container defect corrupts them in static JSON). No full `bpdump` was needed.

⚠ **`ULokiRespawnComponent::Respawn 0x5A6AC40` is UNVERIFIABLE — its page is never decrypted in `merged14`**
(consistent with "still dark"). Out of scope for the predicate; grade it later from a dump that drove the
path, or via the `.data` record table.

### Phase 1 — STAGED CLIENT, the live tests (each is one injection; capture as you go; FK-32 gives ~1 injection per staging — see §6)

Sequence deliberately: prove the pipeline pieces INDEPENDENTLY, cheapest first, then integrate.

- **1a — DAMAGE works at all (no hero-ASC, no team dependency).** On a live self-owned ASC (scenery or
  a spawned bot): write `Health=1000`, then `CallNativeGuarded(AdjustHealth, ctx=that ASC, -250f)`,
  read back `750`. **Proves the damage pipeline runs client-side with no server authority.** Lowest
  risk, highest information; do this first.
- **1b — WALL E resolve: is a bot damageable / hostile?** Spawn a bot (existing arms). Read-only:
  does the player's PlayerState team index == the bot's? Then apply damage to the bot's ASC (via
  `AdjustHealth`, or better via a real damage GE) and watch its Health drop to 0 and the bot die.
  If damage lands on a team-less bot ⇒ **WALL E is shallow, no team fix needed.** If it does not ⇒
  build the team data-poke (poke `GameState.TeamStates` by hand, `PlayersAttached`-poke risk class,
  or `ags`-authoritative team assignment via a shim).
- **1c — WALL P resolve: the player casts.** Write the raw-call SEH scaffolding, then (KWIREGAS
  controlled) call `InitAbilityActorInfo(ASC, Owner, hero)` at `base+0x447F410`; witness =
  `ReportAscActorInfo` -> `*** AVATAR IS THE HERO -- BOUND ***` (`tutorial_launch.cpp:11930-11947`,
  already built). Then, in SEPARATE builds (activation is the highest-risk step,
  `fk6:674-678`): `AuthGiveAbility...` a kit ability -> read `ActivatableAbilities 0->N` by RPM on
  the array (not a getter) -> `TryActivateAbilityByClass`.
- **1d — INTEGRATE = the acceptance test.** Player (WALL P wired) casts an ability that produces a
  damage effect; the bot (WALL E resolved) is in range and hostile; the bot's Health reaches 0 and it
  dies. **Predicate met.**

#### Phase 1 — ARMS BUILT (S143, 2026-08-24; unflown)

★ **`RM_BOTFIGHT` (enum 32) is built.** ONE source arm (`DoBotFight` in `tutorial_launch.cpp`): all
read-only recon runs unconditionally; each destructive step is gated by a `KBFARMS` bit
(bit0 spawn · bit1 bind · bit2 grant · bit3 activate · bit4 damage · bit5 wire-bot). No `.text`
write, no PI hook (the `botspawn` funcswap route; refuses under `KFUNCSWAP=0`); `InitAbilityActorInfo`
is a raw SEH-guarded native call at `g_modBase+0x447F410`. Every address/signature was graded REAL
offline (Phase-0 results above). **Fly the escalation across sittings — no source edit.**

| variant | `KBFARMS` | `.text` RAW | what it does |
|---|---|---|---|
| `botfight` | `0x00` | `e88a2b413522b6b7` | pure read-only recon (resolution, player ASC/AvatarActor, team index, ability classes, census) |
| `botfight-probe` | `0x03` | `da19b5529a95708c` | **recommended first real flight** — K_SPAWN (bot-vs-player team read) + K_BIND (the never-run `InitAbilityActorInfo`) |
| `botfight-cast` | `0x0E` | `58983669fad81017` | WALL P full: bind → grant Ability1 → activate |
| `botfight-kill` | `0x31` | `51adbf93f1f47705` | WALL E full: spawn → wire bot ASC → `AdjustHealth` to kill |
| `botfight-full` | `0x3F` | `fb1cef0c39388eab` | whole minimum loop in one injection |

Extra knobs: `-DKBFOWNER` (bind Owner: 0=carrier/1=PlayerState/2=hero) · `-DKBFDMG` (HealthDelta) ·
`-DKBFDMGTGT` (0=self/1=bot) · `-DKBFABIL` (`Ability1`..`AbilityDodgeRoll`) · `-DKBFHERO`.
All KERNEL32-only imports; `text_digest.py --dupes` = **0 hazard/degenerate** (no "A/B against a copy
of itself"). ✅ **Regression gates re-verified byte-identical after the edit: `botai
5e47c13cf7f0a158`, `play 9bc10a4552c596e1`** — so `DoBotFight` dead-strips and no shared code moved.

#### Phase 1 — FLIGHT RESULTS (S143, 2026-08-24; ONE staged client, 6 injections, still alive)

Staged `gft→fo→sp→botfight` then injected `botfight-probe` and `botfight-cast` into the same live
process (evidence in `docs/tutorial-launch-marker.s143-{read,probe-AVATARBOUND,cast}.txt`). No crash,
no `Fatal`, no crashpad. **The arm works and produced a breakthrough.**

★★★★★ **WALL P STEP 1 IS SOLVED — the `AvatarActor` bind works, first time in 31+ sessions [M].**
Single-variable, no fault:
```
BEFORE (WireAbilitySystem ran): Avatar@ASC+0x410 = NULL   ("STILL NOT INITIALISED")
InitAbilityActorInfo(ASC, Owner=carrier, Avatar=hero) -> ok
AFTER:  Avatar@ASC+0x410 = BP_HERO_Ronin_C   *** AVATAR IS THE HERO -- BOUND ***
```
The bind found at S111 (`base+0x447F410`) and never called binds the hero as the ASC's AvatarActor.
`OwnerActor@0x408` is the `LokiPlayerState_HeroAffiliated` carrier; `AvatarActor@0x410` is the hero.
★ It **persisted across injections** (still bound at the next injection's PLAYER-PRE read).

★ **WALL E — the bot pawn spawns [M].** `SpawnClassBotAtLoc` resolved on the live
`Comp_BP_BotSpawner_C` (roster Num=13/16), spawned at `(600,0,13240)`, and the census moved
**LokiHeroCharacter 2→3** — a hero pawn appeared. ⚠ `CreatedBot=NULL` (the pre-registered
lagging-PlayerState trap; census delta is the verdict), so the **bot-team read did not fire** and
`BotOrAIController` stayed 0→0 (the known stripped-controller wall). Next arm must find the spawned
pawn by census (the new LokiHeroCharacter that isn't the player) to read its team.

⚠⚠ **NEW SUB-WALL — the grant no-ops, and OFFLINE ANALYSIS SETTLED THE CAUSE: THE REFLECTED
`Auth*` GRANT IS STRIPPED (returns `InvalidHandle`), FK-1 FAMILY [M].** `AuthGiveAbilityWithSourceObject`
returned `ok` but `ActivatableAbilities 0 → 0`; `TryActivateAbilityByClass` returned 0. Reading
`execAuthGiveAbilityWithSourceObject`'s tail (`0x5294750`) against `merged14`:
```
0x529483f cmp byte [0x9E25427], 0 / je      ; conditional-call gate
0x5294856 call 0x1258bf0                     ; multiplicity 11025 = a shared atomic FUObjectItem-flag
                                             ;   helper (lock cmpxchg/or [item+8]) -- NOT the grant; return discarded
0x5294868 mov rcx,ASC / lea rdx,[rsp+0x70]
0x5294870 call 0x13d4e60                     ; the IMPL -> body: mov [rdx],-1; mov rax,rdx; ret
0x529487a mov ecx,[rax] / mov [rsi],ecx      ; Result = -1 = InvalidHandle, UNCONDITIONALLY
```
⇒ **the impl (`0x13d4e60`, multiplicity 2 — shared only with `BP_AuthGiveAbilityWithInputID`) writes
`InvalidHandle` and adds no spec.** Both reflected grants (`AuthGiveAbilityWithSourceObject`,
`BP_AuthGiveAbilityWithInputID`) are stubbed; **there is NO reflected non-Auth grant** on the Loki ASC
(session-100 + `binds_members.csv`). This is the same server-authority strip as `SpawnPlayer`: in the
real game the SERVER grants and replicates `ActivatableAbilities` to the client, so the client's `Auth*`
wrappers are hollow. ⚠ **CORRECTS Phase-0:** the grant was graded REAL by mis-identifying the atomic
helper `0x1258bf0` as the body — the real impl `0x13d4e60` is a stub. (Attribute sets / carrier-role /
selector-type were the pre-analysis hypotheses; all three are moot — the impl never runs.)

★ **NET:** WALL P **step 1 (AvatarActor bind) is DONE** [M]; **step 2 (grant) is an FK-1 strip** — the
route is the engine's **non-reflected `UAbilitySystemComponent::GiveAbility(const FGameplayAbilitySpec&)`**
(stock UE, not stripped), which needs: its native address; an `FGameplayAbilitySpec` constructed
(ability CDO + level + inputID + source); and the ASC **authoritative** (force the **carrier's** role=3,
since `WireAbilitySystem` forces only the PlayerState's). A real next arm, not a poke. WALL E: pawn
spawns; controller + team remain the S135–S138 walls. ⇒ **the minimum bot-fight loop's "player casts"
half now hinges on the native `GiveAbility` route; the AvatarActor bind that gated it is solved.**

#### Phase 1 — S144 RESULT: WALL P STEP 2 (GRANT) IS SOLVED. Read `docs/s144-giveability-grant-works.md`.

★★★★★ **The engine `GiveAbility` route works — the player hero has a granted ability, first time ever.**
`ActivatableAbilities.Items` went **0 → 1**; the committed spec's `Ability == Default__GS_Ronin_LMB_Selector_C`,
`Handle == 1`, `ReplicationID == 1` (FastArraySerializer-stamped ⇒ real `Items.Add`). Flown into the golden
client, one game-thread hit, no fault. Recipe (all [M], live-verified): build the spec with the game's own
ctor **`base+0x44ABED0`** (`void*(spec* sret, UClass** ppClass BY POINTER, i32 Level, i32 InputID, UObject*
Source)` — Ability@+0x10=CDO(`*(class+0x178)`), Handle@+0xC, Level@+0x20, InputID@+0x24, Source@+0x30, sizeof
0xF8), then call the grant VIRTUAL at **ULokiASC vtable disp 0x778** (`0x552DC80`, the slot the engine's own
AbilityPendingAdds flush uses), read `Items.Num@ASC+0x540`. No `.text` write, no PI hook.
- ⚠ **The authority worry was moot:** `IsOwnerActorAuthoritative` = disp 0x688 = `0x4481990` = stock
  `!*(u8*)(ASC+0x800)`, NOT a Loki override; `ASC+0x800 == 0` live ⇒ gate OPEN, no forcing. The reflected Auth
  grant no-op'd because its impl `0x13d4e60` is a stub, NOT because the gate refused. **RETRACTS the "force the
  carrier's role=3" line above — no forcing is needed.**
- ⚠⚠ **The grant DEFERS in-hook** (`AbilityScopeLockCount>0` → `AbilityPendingAdds.Add; return Handle`) and
  commits to Items after the hook returns; an in-hook Num read is too early. A post-flight live read confirmed
  Num=1. (Also fixed `BfCountActivatable`, which read the wrong offset — a second instrument artifact.)
- ⚠ **Historical S144 status, superseded by S145:** `TryActivateAbilityByClass` returned 0 even with
  the ability granted and the hero Alive. NULL attribute sets and the apparent missing instance were
  the leads then. S145 wired the attributes, found the real MiniDash primary at the corrected
  `spec+0x90` array, and opened full eligibility; do not carry these as current blockers.
- Arm: `build.ps1 -Variant botfight-cast` (`.text 08084ead999736b1`), `botfight-alivecast` (0x48),
  `botfight-activate` (0x08). Gates `botai 5e47c13cf7f0a158` / `play 9bc10a4552c596e1` byte-identical.

#### Phase 1 — S145 RESULT: WALL P STEP 3 PRE-ACTIVATION ELIGIBILITY IS SOLVED. Read `docs/s145-wallp3-canactivate-open.md`.

★★★★★ **Every measured MiniDash eligibility predicate can be made true [M].** S145 corrected the full
`CanActivateAbility` receiver to the exact ability CDO and found a receiver split: the granted primary
instance had `CurrentCharges=1` and leaf gates `1/1`, but the CDO had `CurrentCharges=0`, gates `1/0`,
base CanActivate `0`, and exact failure tags `Ability.Fail.NoCharges + Ability.Fail.Cost`. Disassembly
confirmed MiniDash CheckCost (`base+0x551BA70`, CDO vtbl+0x3C0) directly reads `this+0x622/+0x628`.

In one fresh-process, single-variable A/B, a temporary exact CDO CurrentCharges `0 -> 1` changed CDO
gates `1/0 -> 1/1`, base CanActivate `0 -> 1`, cleared the failure tags, and made full Loki
CanActivate (CDO vtbl+0x2F8 = `base+0x551AD70`) return `1`. The shared CDO field was restored `1 -> 0`
with readback before return; all `17,563/17,563` funcswaps restored; the client survived. The selected
binary contained **no activation body**. Evidence:
`docs/tutorial-launch-marker.s145-wallp3-minidash-FULL-CANACT-OPEN-CDO-CHARGE1-RESTORED.txt`
(`SHA-256 4FEB692E...D21B8F75`); arm `botfight-castalive-dash-mana10-candecomp-cdocharge1`, RAW `.text`
`f477dc10d58e9e4e`.

Prerequisites now proved together: AvatarActor bound, durable engine grant with an InstancedPerActor
primary instance, Alive, GAS AttributeSets wired, ASC-registered Mana `10/10`, primary charge `1`, and
CDO charge positive during the precheck. ⚠ The raw CDO charge write is a reversible **diagnostic**, not
a canonical initialization recipe: it is shared replicated/RepNotify state and bypasses timers,
delegates, authority, and replication.

⚠ **ACTIVATION ITSELF IS STILL NOT PROVED.** Two earlier fresh flights entered reflected
TryActivate after primary leaf gates `1/1` and ended FK-32 before return, at `10.7938 s` and `10.7917 s`
after the last pre-call marker. Neither produced an activation/body/cost/damage receipt. Both the
negative-full and this positive-full no-Try controls survived, so the repeated death is strongly
TryActivate-or-downstream associated; its exact mechanism is unknown. **S146 has now superseded the
then-next-flight wording:** it ran the first all-gates-open native-handle treatment and the matched
`INDEX_NONE` control described immediately below. An explicit activation/body/active-state/cost/
damage receipt is still required.

#### Phase 1 — S146 RESULT: NATIVE-HANDLE A/B LOCALIZES THE `0xDEAD` BOUNDARY. Read `docs/s146-wallp3-native-handle-fk32.md`.

★★★★★ **Wrapper entry/ABI is not the deterministic trigger [M].** Two fresh flights bypassed
reflected `TryActivateAbilityByClass` and called the exact native handle wrapper
`base+0x4493420` once with `allowRemote=false` and a zeroed aligned `0x30` auxiliary object. Both
required local control `1`, Role `3`, exact live spec membership, primary inactive, charge/Mana
state, and full Loki CanActivate `1` at the final boundary.

- Valid Handle `1` (one exact matching spec): no return marker; PID `62916` exited
  `57005 / 0xDEAD`; no UE crash artifact and no activation receipt.
- `INDEX_NONE=-1` (zero matching specs, while the real Handle-1 spec remained present): wrapper
  returned `AL=0`; CDO charge restored `1 -> 0`; valid spec, ActiveCount/flags, active state, charge,
  and Mana remained unchanged; `17,563/17,563` funcswaps restored; PID `56008` later exited cleanly
  with code `0` after `52,540.2 s` (~14.6 h), now preserved by crashwatch.

Therefore the reflected route, native wrapper entry, ABI, `allowRemote=false`, and auxiliary-object
shape are not sufficient causes. The valid-handle branch—valid-spec resolution,
`InternalTryActivateAbility(base+0x4480B30)` or below, possibly combined with injected-call-stack
provenance—is implicated. Because the invalid branch returns before downstream activation, this does
not validate the aux object's downstream semantics. **Do not bank that activation began.** Evidence:

- `docs/tutorial-launch-marker.s146-wallp3-native-handle-CALL-0xDEAD-NO-RETURN.txt`
- `docs/crashwatch.s146-wallp3-native-handle-0xDEAD.log`
- `docs/tutorial-launch-marker.s146-wallp3-native-handle-INDEX_NONE-RETURNS0-SURVIVES.txt`
- `docs/crashwatch.s146-wallp3-native-handle-INDEX_NONE-clean-exit.log`

#### Phase 1 — S147 RESULT: INPUTID-5 ACTIVATION STATE EXISTS WITHOUT A SHIM ACTIVATION CALL. Read `docs/s147-natural-input-build-evidence.md`.

★★★★★ **A real MiniDash activation receipt was measured [M].** The verified artifact grants the
spec with `InputID=5` and contains none of the reflected ByClass, native handle,
`InternalTryActivateAbility`, or `InternalDoActivateAbility` calls. Flight 5 began from exact
inactive/eligible state; two Tab key pairs produced two ordered exact Toggle Map BP receipts. During
the subsequent 350 ms LeftShift hold, the continuous raw sampler measured at `t=+469 ms`:

- exact live spec `ActiveCount 0 -> 1`;
- primary active/cancelable/blocking `0/0/0 -> 1/1/1`;
- registered Mana Base/Current `10/10 -> 0/0`;
- identity still valid (`issue=0x0`, InputID `5`, charges `1/1`), receipt mask `0x19E`.

The post-key-up sample retained that state, then the worker restored shared CDO charge `1 -> 0`.
The exact Ability3 BP node count was `0`, so the arm's strict BP-witnessed natural-input predicate is
not met; likely ordering/consumption below the shared input action remains to be explained. This does
not erase the raw activation state. Crashwatch later measured `0xDEAD` at process age `290.5 s`,
about 51 s after the marker's final write, with no UE crash marker; localize it only to after the
activation and CDO-restoration receipts. There is still no ability-body/effect/damage/bot-kill
receipt. Therefore WALL P has its first cast-state receipt, while WALL E and the integrated minimum
bot-fight predicate remain open.

### Phase 2 — durability (optional for the predicate, required to hand `ags` the "maintain" role later)

Convert the diagnostic pokes (bot spawn/controller/PlayerState/GAS, ability bind) into
**restore-safe, `ags`-orchestrated** shims. This is the seam to the later "server-maintained match"
target and the `ags`->resident-shim command channel (§7).

---

## 5. VERIFIER CORRECTIONS BANKED (so a successor does not regress on these)

- ★ The bot's ASC `+0xF00` is **MEASURED NULL** (`s139-flight1:72`, `s139-flight3:64,67`), not "very
  likely NULL" — so `OnPossess`'s 3 ability grants land in nothing. STRENGTHENS "bot can't fight."
- ★ The DS GAS CDO-borrow recipe, ported to force-open (S139-f4), delivers correct `Acceleration`
  (input x50000) but **`Velocity (0,0,0)` and 0.00 uu translation** — the recipe ALONE does NOT move
  the hero (`s139-flight4:36-40,97-98`). Do not cite it as "player movement is a solved recipe."
- ★ The movement clean-test arm is **`armk_v2` RAW `988fd61853669d5c`** (vertical-from-rest WITH the
  `AnalogInputModifier` read), NOT `axisab 83bcf5c178846022`, which FAILED its within-sitting A/B
  (defect S141-l). (Movement is out of scope for THIS predicate anyway.)
- ★ The objective Func-swap safety `0/16 deaths @600s` is `[M]` for `KFUNCSWAP`-as-HOOK but only `[I]`
  for the novel 4-byte-CUSTOM-stub swap the lever proposes (same one-heap-pointer write class, novel
  target). (Objectives are out of scope for THIS predicate.)
- ★ "No Combat(7)->Post(8) timer exists" is **COVERAGE-BLOCKED, not measured-absent** (`fk22:569`
  refutes the sibling form; the flown run reached Combat via dark-page callers). Do not restate as a
  hard fact.
- ★ Rank/career badge refetch is via **WS-drop RESYNC (~40s)**, not a proven `NotifyResource` push
  (`s122:206-210`); whether `NotifyResource` drives `/mmr` is untested `[I]`.
- ★ The DS route did NOT "park at the July session-39 menu-crash" — it continued ~6 weeks to
  server-authoritative possession in the live world (S54/S76/S85-87), then was RE-SCOPED as a
  strategy. Its water-mark is HIGH-but-ceilinged. Conclusion (stay parked) unchanged and strengthened.

---

## 6. FLIGHT / STAGING NOTES

- Stage with `configs/s138-autostage.ps1` (or `fk24-stage.ps1`); gate on **`[SP] done step=4` AND a
  live process**, never the stager's completion message.
- ⚠⚠ **FK-32 gives roughly ONE injection per staging** (`0xDEAD` at 7/6/4/4/4/4/4 injections). Plan
  each sitting around a single arm; **take the `dumpimage` EARLY**; copy the marker off after every
  phase.
- ~27% of launches die in staging (FK-31) before the probe injects — budget on **armed windows**, not
  launches.
- Diff `.text` sha256, never size. Build arms from the `dismount`/`rideable`/`botps` templates
  (CALL-ONLY, no module-image write), never from `RM_GOTOPHASE` (standing `.text` patch, 10/10 lethal).

---

## 7. DEFERRED TARGETS (after the Minimum bot-fight loop)

In ascending scope, each a superset of the last:

1. **Bot fights back** — wire the bot's ASC BEFORE possession (so `OnPossess`'s grants + `BotCheatEffects`
   attach), then confirm the 21-node BehaviorTree drives combat; resolve autonomous locomotion
   (`armk_v2`).
2. **Full single match** — objectives/score (the `ServerOnly` Func-swap lever ->
   `ProgressObjective 0->1`, the highest-value unflown match experiment), win detection, EoG
   (`bpdump Comp_GameMode_EoGFinisher` — now possible offline), respawn, the `disassociate` return-leg
   for a repeatable loop.
3. **Server-maintained match** — the `ags`->resident-shim **live command channel** (shim polls a
   loopback `ags` endpoint, applies match-level deltas via the S55 primitive), so `ags` holds and
   pushes authoritative phase/score/spawn/team state. This is the literal reading of the original
   goal; it is the architecture-3 keystone and it is UNBUILT.

---

## 8. Pointers to fix in the wider repo (proposed, not yet applied)

- `docs/ignorance-map-s101.md` A-1 ("write the acceptance predicate") is now satisfied by §0 here —
  update it to point at this file.
- `endpoints.md` `/core-game/players` "~17/s poller" row is stale — `[M]` it is fetched exactly ONCE
  per messenger connection (`armqueue.go:28`).
- `armqueue.go:44-48` carries a stale `[S]` pre-flight comment ("nobody has ever pushed this
  resource") superseded by the S135 flight (`s135:58`).
