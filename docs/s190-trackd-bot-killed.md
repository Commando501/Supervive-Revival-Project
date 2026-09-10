# S190 TRACK D — A SPAWNED ENEMY BOT DIES FROM THE GAME'S OWN AdjustHealth (2026-09-09)

★★★★★★ **[M] THE ACCEPTANCE-PREDICATE STEPPING STONE IS MET.** On the tutorial surrogate world, a
floor-spawned enemy `LokiBot` was given a real ASC, seeded to 1000 HP, and driven to **exactly 0 HP
by the game's own `ULokiAbilitySystemComponent::AdjustHealth`** — the first time in this project a
spawned enemy bot has been damaged, and killed, by the game's own damage path. This proves the
**E-and-damage half** of the co-op-vs-AI predicate end to end and isolates **WALL P (a real player
ability cast) as the sole remaining critical-path item.**

⚠ SCOPE: Track D **BYPASSES WALL E** by design. `AdjustHealth` is called directly on the bot's own
ASC (a reflected attribute mutation), NOT a player ability routed through hostility/teams. So this
does NOT resolve "can a player ability damage a hostile bot" — it resolves "a spawned enemy bot is a
valid, seedable, killable damage target," which is the stepping stone the S190 handoff asked for.

## The three flights (all [M])

| flight | build | result | HP | game after |
|---|---|---|---|---|
| non-lethal (clean stage) | `trackd-kill-nonlethal` (-250) | `DMG_APPLIED_NONLETHAL` | 1000 → **750** (`443B8000`, exact) | alive |
| kill (re-inject) | `trackd-kill` (-5000) | `BOT_KILLED` | 1000 → **0** (`00000000/00000000`) | survived kill, FK-32 at 293.4s |
| kill (clean stage) | `trackd-kill` (-5000) | `BOT_KILLED` | 1000 → **0** | survived ~90s post-kill, FK-32 at 290.8s |

Receipt (clean staged kill, preserved at `docs/s190-trackd-BOT_KILLED-staged-marker.txt`):

```
[TRACKD] TRACKD_KILL preHP=1000.00 requestedDelta=-5000.00 postHP=0.00 postBits=00000000/00000000
         observedDeltaHP=-1000.00 expectedClampHP=0.00 arithmeticOK=yes cleanZero=yes faulted=no killed=yes
[TRACKD] TRACKD_COMPLETE RESULT=BOT_KILLED preHP=1000.00 postHP=0.00 killed=yes
```

- **[M] AdjustHealth silently clamps at 0**: requested −5000 on a 1000-HP bot, applied exactly −1000
  to reach 0 (`observedDeltaHP=-1000`, `arithmeticOK=yes`). Same silent-clamp semantic S156-B measured
  at MaxHealth; now confirmed at the 0 floor. Both Base and Current go to 0 (`cleanZero=yes`).
- **[M] The zero-crossing did NOT crash the game.** The kill fired at ~uptime 200s (`faulted=no`); the
  game ran ~90s more and then died of **FK-32** (`exit 0x0000DEAD` at 290.8s / 293.4s — no crashpad
  dump). Every PID this session died at ~285–293s uptime regardless of shim activity, so the death is
  the ambient base-rate protector kill tied to uptime/injection count, **decoupled from the kill**.
  The feared OnDeath-from-zero-crossing crash did not occur.

## What was wrong with the naive arm, and the fix (the load-bearing findings)

The roadmap's proposed `botfight-kill 0x31` (RM_BOTFIGHT) is **degenerate** (workflow `wf_dc4afd5b-8df`
adversarial synthesis + 4 live flights confirmed it): its K_WIREBOT gate refuses (the component-route
bot has no controller/PlayerState), and K_WIREBOT seeds no Health. The genuine arm required a new
`RM_BOTSPAWN` path (`KBFTRACKD` knob), and three live flights localized what AdjustHealth actually
needs on a bot:

1. **[M] The bot must have a controller + PlayerState.** ARM D (`KBSPSARMS & 0x20`) already provides
   both — it runs `BsPsDirectInit`/`BsPsLinkPawn` (ARM B/C) internally on its LokiBot. (Not a new
   KBSPSARMS bit; the synthesizer's `0x38` was wrong — the spawn comes from ARM D's own `BsCallAI`.)
2. **[M] WireAbilitySystem canNOT wire the bot's ASC** — the bot's PlayerState has no HeroAffiliated
   carrier (`@0x4F8 == NULL`) and spawning one FAILS (`carrier spawn FAILED`; S80 recorded it crashes).
3. **[M] The ARM-G-borrowed CDO ASC is NOT AdjustHealth-applicable.** Borrowing the CDO's ASC into
   `bot+0xF00` gives a template ASC with an EMPTY `SpawnedAttributes` (so AdjustHealth's
   `GetSet<ULokiAttributeSetHealth>()` null-derefs → FAULT) AND a null `AbilityActorInfo` TSharedPtr
   (so `InitAbilityActorInfo` FAULTS → no AvatarActor → AdjustHealth cleanly no-ops, 1000→1000).
4. **[M] THE FIX: build a REAL ASC on the bot.** Replicate `EnsureHeroAffiliatedCarrier`'s proven
   creation directly on the bot pawn, skipping the failing carrier spawn:
   `AddComponentByClass(LokiAbilitySystemComponent)` [ctor allocates `AbilityActorInfo`] →
   `K2_InitStats(LokiAttributeSet)` + `K2_InitStats(LokiAttributeSetHealth)` [creates + REGISTERS real
   attribute subobjects in `SpawnedAttributes`] → cache `bot+0xF00` → `InitAbilityActorInfo` (now
   NON-faulting) → seed Health+MaxHealth = 1000 (`healthOff=0x70`, `maxOff=0x80`, S156 [M] offsets) →
   S153-validated AdjustHealth resolve (`wrapperExact` + `tailReachesImpl`, `thunk=base+0x5294270`,
   impl `0x5516610`) → fire. `TRACKD_BUILD asc=... statsOk=2/2 initAAI=ok` is the receipt that the ASC
   is real; then AdjustHealth applies cleanly.

## Rules banked

- **R-S190-a**: a borrowed CDO subobject ASC works for the movement GETTERS (they read `bot+0xF08`
  directly) but NOT for GAS APPLY (AdjustHealth needs a registered `SpawnedAttributes` set AND a bound
  AvatarActor, both of which only a real, `AddComponentByClass`-created ASC provides).
- **R-S190-b**: `EnsureHeroAffiliatedCarrier`'s `AddComponentByClass` + `K2_InitStats` sequence is the
  reusable "give an actor a working ASC with registered attribute sets" primitive; it works on any
  actor when the carrier-spawn path is unavailable.
- **R-S190-c**: FK-32 on this route is uptime/injection-driven (~285–293s / 4th–5th inject), NOT
  triggered by a Health-zero-crossing. A kill that lands well before that window and lets the game run
  ~90s is a genuine kill, not a crash. Verify the death mode via `crashwatch.out.log` exit code.

## Arm / build

- `tools/sigbypass-mod/tutorial_launch.cpp`: `RM_BOTSPAWN` + `KBFTRACKD` block (STATIONS 1–6: provision,
  build-real-ASC, resolve-set, register, seed, validated-resolve, fire). Knobs `KBFTRACKD` (default 0,
  dead-strips), `KBFTRACKD_SEEDBITS` (0x447A0000=1000), `KBFTRACKD_DELTABITS` (0xC59C4000=-5000 kill;
  0xC37A0000=-250 nonlethal). Risk class: DATA writes (aligned, readback-verified, SEH-guarded) +
  reflected `CallNativeGuarded` calls + `AddComponentByClass`/`K2_InitStats`. No module-image write.
- `build.ps1` variants `trackd-kill` (KBSPSARMS=0x20, delta -5000) and `trackd-kill-nonlethal`
  (delta -250). Both KERNEL32-only, `verify_dll` PASS.
- Regression gates BYTE-IDENTICAL (all Track-D code behind `#if KBFTRACKD`, no `#else`):
  `botai b620e0ff3279e673`, `play 31af7667355f39d1`, `gasattr 29f0fa4efffd01da`,
  `gasattr-ctrl 4c0ede610baa4629`, `-seedmax b47d1bfd04e44921`, `-postshots1 1925e9e80646a4fb`.
  Track-D digests move per `KBFTRACKD_DELTABITS` (they are a real treatment pair, `--dupes` clean).

## Cost / next

- 8 launches: 2 clean stages (both produced results) + 4 FK-31 staging deaths (a cluster, as the
  handoff warned — ~27% and streaky) + 2 mid-diagnosis FK-32s on aged re-injected PIDs.
- ⇒ **WALL P is now the sole remaining critical-path item for the full predicate.** Track D deliberately
  bypassed hostility; making a *player ability* damage a *hostile* bot still needs walls E (teams) and
  P (durable cast, the S158/S175–S177 FK-32-protector problem). The damage mechanism, the bot spawn,
  and now "a bot ASC can be built + seeded + killed by the game's own AdjustHealth" are all [M].
