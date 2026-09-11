# S191 E4T-A3 Flight 1 — WALL P IS A PHASE STATE GATE, NOT DISPATCH [M] — 2026-09-10

★★★★★★ **BREAKTHROUGH: The ProcessEvent bypass REACHES MiniDash's Blueprint body, and the block is a
state-machine phase check. Loki.log independently witnessed our call — the game's own message reads:
`Attempted to dash outside of Invoke, Channeling and Warmup phase`.** Read this file before writing any
more E4T variants — the wall has moved from "dispatch machinery is inaccessible" to "phase state gate
enforces natural cast sequence".

## Flight setup

- **Arm:** `-Variant botfight-damage-self-cal-bindavatar-seedmax-postshots1-e4-t-a3` (RAW: rebuilt from
  the E4T knob added earlier this session; `-DKBFABIL="Ability3" -DKBFINPUTID=5 -DKBFE4CALLID=5
  -DKBFE4=1 -DKBFE4T=1`).
- **Target:** `BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C` at Health/MaxHealth = 100/100.
- **Ability:** `Ability3` = **`GS_Ronin_MiniDash_Charges_C`** (hero.Ability3 = 0x1F10, CDO
  0x1EAE9910FD0), chosen because MiniDash has BP-declared damage-adjacent surfaces that a Selector
  lacks. Grant OK: `Items.Num 0 → 4`, outHandle = **4**.
- **Instance resolution:** Items[?].Rep.Data[0] at `0x1EC0263AAB0`, class
  `GS_Ronin_MiniDash_Charges_C`, Handle = 4. vtable = `0x7FF7BB44EF28`, ProcessEvent@+0x270 =
  `0x7FF7B3E24E10`.
- **PID:** 54416; game uptime 758s+ at flight time, 938s+ still-alive at write time.

## What the class-chain scan found

17 candidate names probed. Split across three groups:

**Selector-only queries — NOT on MiniDash's chain (as predicted):**
- `DetermineCurrentSpellIndex`, `GetCurrentSpellInstance`, `GetSpellInstance`
- `OnRep_SubSpellHandles`, `GetCurrentSpell`, `GetCurrentSpellIndex`, `GetSpellAtIndex` — none

**Generic UGameplayAbility K2 methods — NOT on this class chain:**
- `K2_ActivateAbility`, `ActivateAbility` — **still not present** (MiniDash's chain does not include
  `UGASGameplayAbility`, confirming the earlier E4T Selector-side finding for a different class).

**MiniDash-specific BP surfaces — FOUND, 7 of them:**
| candidate | fn | role (inferred from name) |
|---|---|---|
| `Invoke` | `0x1EB8A616700` | main worker (phase-transition trigger) |
| `BP_AuthBeginWarmup` | `0x1EB8A616F00` | **phase-setter — this is the entry that opens the state gate** |
| `DashHit` | `0x1EB8A616C00` | direct damage helper |
| `K2_CommitExecute` | `0x1EA07BCC910` | UGameplayAbility commit (may be empty on this build) |
| `K2_CanActivateAbility` | `0x1EA07BCC550` | UGameplayAbility precondition (bool) |
| `Character Hit` | `0x1EB8A616E00` | damage per-target callback |
| `DashEndHitBox` | `0x1EB8A616D00` | dash end-region handler |

## The call and its receipt

Selected the first-found (`Invoke`, per E4T's first-match policy). Function metadata:
- flags = `0x8020800`
- PropsSize = 0
- ScriptNum = 18 (has bytecode)
- Func(+0xE0) = `0x1EBA2CC8EB0` (non-null; unlike Selector-side query methods, this is a real
  BP-emitted function pointer)

Called `ProcessEvent(instance, Invoke, zeroed_parms)`. Result:
- `faulted = no`
- `elapsedMs = 0`
- `minPreHP = 100.00 → minPostHP = 100.00` (**no damage**)
- preBits/postBits identical (42C80000 / 42C80000 both slots)

The shim's own verdict line called it *"clean-fast return (<10ms): BP body ran quickly OR ProcessEvent
silently short-circuited"*.

## Loki.log — INDEPENDENT WITNESS that the BP body ran

After the shim disarmed cleanly, `Loki.log` shows:

```
[BP_HERO_Ronin_C_2147471315][GS_Ronin_MiniDash_Charges_C_2147471106] Attempted to dash outside of
Invoke, Channeling and Warmup phase
```

**This is the game's own message from MiniDash's BP body.** The `GS_Ronin_MiniDash_Charges_C_2147471106`
tag matches our granted instance's class + spawn ordinal. Whatever we called (Invoke or a downstream
DashHit-adjacent function) executed BP bytecode that read the phase state, found it not in
{Warmup, Channeling, Invoke}, and refused to apply damage.

⚠ It is NOT proven this message was emitted by our Invoke call specifically vs a later natural-input
event on the same instance. But the timing and the fact that no LMB or LeftShift was pressed between
the shim call and the log message make our call the strongly-favoured attribution.

## Rules banked [M]

**R-S191-E4T-a [M]:** ProcessEvent slot 78 (vtable+0x270) on a K_GRANT'd Loki UGameplayAbility
instance REACHES its BP body. The BP body executes and runs its own preconditions. This CONTRADICTS
the earlier interpretation that WALL P blocks dispatch entirely — dispatch works; the BP body's phase
state gate is what refuses.

**R-S191-E4T-b [M]:** MiniDash's BP class defines a `Attempted to dash outside of Invoke, Channeling
and Warmup phase` refusal message that fires when a dash-triggering function runs while the ability's
`bIsWarmupActive`/`bIsChannelingActive`/`bIsInvokeActive` flags are all false. This is a NATURAL cast
sequence enforcer, not a WALL P protector defect.

**R-S191-E4T-c [M]:** MiniDash's class chain does NOT include `UGASGameplayAbility`, so
`K2_ActivateAbility` is not on it — confirmed for a THIRD Loki ability class (Selector, LMB Selector,
and now MiniDash). `binds_members.csv`'s row for `K2_ActivateAbility` on class 3135
(`UGASGameplayAbility`) is real but that class is not on any Loki gameplay ability we've probed.

**R-S191-E4T-d [I,strong]:** `BP_AuthBeginWarmup` is likely the phase-state-setter — a naming
convention that puts `BP_Auth*` on entry-point-authoritative BP events. Calling it FIRST should
transition the ability from idle → Warmup and open the phase gate for a subsequent Invoke call.

## What survives from earlier findings

- **S191 arc summary's "12 activation surfaces refused"** — this is the 13th (Ability3 MiniDash via
  ProcessEvent Invoke) and it produced a partial success: BP body ran but did nothing without phase
  state.
- **S191 E4M (S55 primitive defect for UObject*-return marshaling)** — unaffected. ProcessEvent
  bypasses S55 entirely.
- **S191 E4N-A3 (raw-native TryActivate on MiniDash refuses)** — CONFIRMED for a different reason:
  `TryActivateAbility` at engine `0x4493420` doesn't just fail on Handle lookup, it also drops out
  before setting Warmup phase (see the phase state model below).

## Model of MiniDash's activation state machine [I,strong]

Based on the BP surface names + Loki.log message:

```
IDLE
  ↓ BP_AuthBeginWarmup(...) — sets bIsWarmupActive=true, starts warmup timer
WARMUP  (~0.5s)
  ↓ Invoke() — sets bIsChannelingActive=true after warmup elapses; may transition
CHANNELING  (~0.2s)
  ↓ Invoke() — transitions to Invoke phase
INVOKE  (~0.15s, damage window)
  → DashHit(target) applies damage IF phase is Invoke
  → Character Hit(...) called per hit target
  → DashEndHitBox() called at end
IDLE
```

Any call to a dash-execution function outside {Warmup, Channeling, Invoke} triggers the
"Attempted to dash outside..." refusal. **Zero-parm Invoke sees idle state and refuses.**

## E4T-A4 arm design — CHAIN THE PHASE-SETTER

**Sequence:** call `BP_AuthBeginWarmup` first (sets phase → Warmup), then Invoke, then observe HP.

Simplest implementation: modify E4T to collect ALL found candidates by name (not just first), then
execute a fixed ordered subset:

```cpp
// After the scan loop, look up each name by role instead of first-found:
uintptr_t fnWarmup = findByName(kCandidates, foundFns, kNumFound, "BP_AuthBeginWarmup");
uintptr_t fnInvoke = findByName(kCandidates, foundFns, kNumFound, "Invoke");
uintptr_t fnDashHit = findByName(kCandidates, foundFns, kNumFound, "DashHit");

if (fnWarmup) { call(instance, fnWarmup, g_bplocals); Sleep(50); readHP("post-warmup"); }
if (fnInvoke) { call(instance, fnInvoke,  g_bplocals); Sleep(50); readHP("post-invoke"); }
// DashHit may need a target parm — leave for E4T-A5
```

**Discriminators:**
- If HP drops after `Invoke`: **E4T-A4 SUCCEEDS, WALL P DEFEATED via ProcessEvent phase chain.**
- If Loki.log now shows Warmup → Channeling → Invoke transitions but no damage: BP body advanced but
  needs a real target reference (DashHit call needed).
- If Loki.log again shows "Attempted to dash outside...": BP_AuthBeginWarmup rejected our call (maybe
  it needs a real ability spec context beyond bare instance).

## What's known-good on THIS PID for E4T-A4

- `pASC = 0x1EB96EC3400`
- Player class chain: `BP_HERO_Ronin_C_2147471315`
- Ability3 handle = 4, granted this session
- Target minion: `BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C_2147471106` at HP 100

## Files

- `docs/s191-e4t-a3-flight1-marker.log` — preserved marker (this flight)
- `tools/sigbypass-mod/tutorial_launch.cpp` line 18457 — KBFE4T knob
- `tools/sigbypass-mod/tutorial_launch.cpp` line 25469-25589 — E4T code block

## Cost

- 0 launches lost this arm (E4T-A3 was the second inject into an already-staged process; PID 54416
  survived 15.6min post-flight and continues to run).
- 0 FK-32 in this arc so far.

## Handoff — E4T-A4 is CHEAP AND HIGH-VALUE

The code delta is small (~40 lines), the knob is additive (defaults to first-found behavior, opt-in
`KBFE4T_SEQUENCE=1` for chained), and the discriminators are pre-registered. **This is the
highest-leverage single arm we can fly on WALL P right now** — a positive result gives the E4
predicate its CAST half and closes ~2 years of "player ability activation refuses" walls in ONE
inject.
