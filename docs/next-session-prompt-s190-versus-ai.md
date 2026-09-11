# Fresh session opening prompt — Versus-AI, the two remaining walls (S190)

You are continuing the SUPERVIVE Revival Project. Read `CLAUDE.md` in full first, then this.

## Where the mission stands (2026-09-09)

**Acceptance predicate** (operator-chosen, `docs/coop-vs-ai-roadmap-s142.md` §0): *on the tutorial
surrogate world, ONE human hero CASTS AN ABILITY that DAMAGES and KILLS at least one HOSTILE ENEMY bot.*
A stationary bot the player kills satisfies it; the bot fighting back is an in-scope stretch, not a
requirement. This collapses to **two walls: (P) the player can cast a real ability, and (E) an enemy bot
is a valid, hostile, damageable target that dies.** Everything else the last ~45 sessions built is done or
off the critical path.

**What is now [M] (do not re-derive):**
- **The damage mechanism works.** S156-B: the game's own `AdjustHealth` applies exact damage back-to-back
  (1000→750→500→250, N=3), heals, clamps at MaxHealth, and fires a safety floor — all measured on a
  seeded `ULokiAttributeSet` (`docs/s156b-*`, `docs/s189-seed-f3-MANASHOT_APPLIED.md`). "A bot dies from
  damage" is a solved mechanism; what is unsolved is the damage coming FROM a player's ability cast (P)
  onto a HOSTILE target (E).
- **The bot exists, walks, and its AI is entirely client-side.** S135–S137: spawn + `ALokiBotController` +
  PlayerState + GAS. S189-BOT (this session): a floor-spawned bot comes up `MOVE_Walking` and walks under
  its own AI; the player walks under WASD at exactly its seeded 487 uu/s. **NEW [M]: the bot's combat AI
  (behaviour tree `BT_HeroBots`, blackboard `BB_HeroBots` with `TargetEnemy`/`AggressionState`/
  `CurrentSpell`, services `BTService_PickSpell`/`ApplyAimError`, tasks `BTT_CastSpell`/`Dodge`, EQS
  `EQS_FindCombatPosition_Bot`, difficulty GEs, and 26 REAL `ALokiBotController` helpers) is all shipped
  Blueprint + real native in OUR client and instantiates live (21 tree nodes, 15 blackboard keys).** Read
  `docs/bot-ai-client-side-settled.md`. ⇒ **"the bot fights back" needs NO AI authored — only walls E+P.**

**What is still the wall:**
- **WALL P — the player casts a real ability durably.** The deepest open item. S158 got the MiniDash body
  to execute end-to-end via natural input (Warmup→Channeling→Invoke→Pre/Post Dash Start) then a **silent
  FK-32 protector kill** (`0x0000DEAD`), ~40-60 s after activation. S175-S177 chased the FK-32 dispatch
  mechanism hard and refuted 8 candidates; it is NOT the runtime.dll kill primitive under the standard
  poke. Read `docs/s158-wallp-natinput-settled.md`, `docs/next-session-prompt-s177.md`.
- **WALL E — a bot is a hostile, damageable target.** Teams are stripped (`GetOrCreateTeamState` returns
  nullptr unconditionally, `SetPlayerTeam`/`SetNumTeams` folds), so nothing is hostile. **The
  decision-critical unknown, never measured: can a player ability DAMAGE a team-0-vs-team-0 (or team-less)
  bot?** If team-vs-team is not required for damage, WALL E is shallow. If hostility gates damage, a shim
  must supply team state by hand (`ALokiPlayerState::IsSpawnTeamLeader` reads `[TeamState+0x688]` — a data
  poke lever, S131, untested for this).

## The decision for this session

Both walls P and E are hard and independent. Pick the track (or ask the operator). Ranked by value×tractability:

**Track D — near-predicate demonstration (cheap, HIGH value, no new wall).** Stitch the proven pieces into
one flight: spawn a floor-Walking bot (S189-BOT `botplay-floor`), seed its ASC Health (S189-SEED
mechanism), then `AdjustHealth(-N)` it to death (S156-B mechanism, via the S55 primitive — the S153
thunkExact fix is in the main worktree, unflown). This proves **"a spawned enemy bot is a valid damage
target that DIES"** end-to-end — the entire E-and-damage half of the predicate, isolating WALL P (a real
player *cast*) as the sole remaining critical-path item. It does NOT use a player ability (it's a direct
AdjustHealth), so it is a stepping stone, not the full predicate. ~1-2 flights. **Recommended first** —
it converts "damage works in isolation" into "a bot dies", and cleanly scopes what P must still deliver.

**Track E — resolve WALL E's decision-critical unknown (medium).** Directly test whether a player ability
(or a raw damage GE application) can damage a team-less spawned bot. If yes, WALL E collapses. If no, test
the `[TeamState+0x688]` / `IsSpawnTeamLeader` data-poke lever. Read `docs/coop-vs-ai-roadmap-s142.md` §3.2.

**Track P — attack WALL P (hard, the deepest wall).** Make the player's ability execute durably past the
FK-32 protector kill. This is the S158 body-executes finding crossed with the S175-S177 FK-32 hunt. The
remaining FK-32 candidates (`docs/next-session-prompt-s177.md`): JIT-generated kill stub (Move I-3 memory
diff), kernel-side termination (ETW), or protector clears DRs before firing. High risk, high reward.

**Track C — tactical polish + map the bot tree (cheap, closes S189-BOT).** (1) The dense bot 487-cap
sample + both-walking overlap — the fix is coded (`docs/next-session-prompt-s189-bot-followup.md`): start
`scratchpad/s189-bot/tools/motion_watch_bot.py --pawn <hex> --cmc <hex>` at the `[SNP] BOT` marker line
during the game-thread hold; F3 died 3× in FK-31 staging so it never ran. (2) **OFFLINE, zero-launch:**
`bpdump`/`rawfile`-extract `BT_HeroBots` + its `BTService_*`/`BTT_*` nodes to map which are Blueprint vs
native and which native leaves they call — the one step that upgrades the "bot fights back is inference"
grade in `bot-ai-client-side-settled.md` to a mapped tree, and tells you in advance whether `BTT_CastSpell`
routes through WALL P.

## Flight logistics (unchanged, honour these)

- `forceTutorialMatch = true` is set in the running `ags` (`server/internal/interactive/interactive.go`);
  leave it for the tutorial route (set false only for a clean menu launch).
- Staging: `gft → fo → sp → <probe>` via `configs/fk24-stage.ps1 -Probe <dll> -Label <label>`. FK-31
  staging death is ~27% and clusters (3 in a row last session) — budget ≥2 launches per armed window.
- FK-32 fires ~289 s after launch (probe+~120 s) on the 4th manual-map — capture as you go; take the
  dumpimage early. Use the marker shadow loop (`scratchpad/s189-bot/tools/marker-shadow.ps1`) for FK-25.
- Pre-warm `send-wasd.ps1`'s P/Invoke type in the sending console before staging (avoids the 35 s cold
  child-PowerShell delay). Elevated shell for SetForegroundWindow parity.
- **Regression gates — the CLAUDE.md-recorded botai/gasattr/gasattr-ctrl/play values are STALE** (source
  drifted at S176 VEH-cleanup `4824c77`). Today's HEAD before-state: `botai b620e0ff3279e673`,
  `gasattr 29f0fa4efffd01da`, `gasattr-ctrl 4c0ede610baa4629`, `play 31af7667355f39d1`,
  `armk 3ff3ba9f77ae1438`, `axisab 01593c0f8f73f1ae`, `sentinel_big 8347a0df17354239`,
  `-seedmax b47d1bfd04e44921`, `-mv-play 87c764b6d235b7a3`. New S189-BOT variants:
  `botplay-floor a37b5a982e522e61`, `botplay-floor-tinykick ec5317d71bc7bf90`,
  `botplay-floor-noai d476b0ab1c0c29af`, `botplay-floor-5th 1dec9197251762fc`, `botwalk 2440b831eaf531af`.
  Re-baseline (rebuild from untouched source, record digests) BEFORE any edit; every new arm goes behind a
  new `#if` knob with no `#else` so the gates stay byte-identical.

## Do NOT

- Do NOT try to author or recover bot combat AI — it is all in `/Game/Loki/Characters/AI/Bots/` already
  (`bot-ai-client-side-settled.md`). The gap is walls E+P, not logic.
- Do NOT re-derive the damage mechanism (S156-B AdjustHealth [M]) or the movement walls (S189-BOT/S141 [M]).
- Do NOT re-run the S175-S177 FK-32 candidates already refuted with [M] (grep CLAUDE.md for "REFUTED").
- Do NOT poke a floor-spawned bot's GravityScale (it's 1.0; leave it).

## Key reading, in order

1. `CLAUDE.md` (the S189-BOT + S189-MV blocks at the top of the WALL P section; the FK-1/WALL E blocks).
2. `docs/bot-ai-client-side-settled.md` — the bot AI is client-side (this session's strategic finding).
3. `docs/s189-bot-botplay-floor-RESULT.md` — the floor-Walking bot + WASD player flight.
4. `docs/coop-vs-ai-roadmap-s142.md` §0/§3.2/§3.3 — the predicate + walls E and the damage pipeline.
5. `docs/s158-wallp-natinput-settled.md` + `docs/next-session-prompt-s177.md` — WALL P + the FK-32 hunt.
