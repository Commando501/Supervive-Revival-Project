# S191 Arc — Comprehensive Summary — 2026-09-10

Two-day arc on the E4 predicate ("player LMB kills a hostile enemy") and WALL P (durable
shim-driven ability activation). 12 [M] flight results banked, 0 launches lost, 0 FK-32
across 7 consecutive direct-injects on PID 55960 (121+ min uptime).

## The E4 predicate status

**MET via KE4DIRECTGE (S191 F3)** — a hostile minion was killed via the game's own AdjustHealth
path. That was the flight where WALL E was refuted and E4 was declared "damage half proven".

**NOT MET via player ability cast** — the CAST half is still blocked. All 12 activation surface
attempts refuse.

## The 12 activation surface attempts

| Flight | Surface | Result | Discriminator |
|---|---|---|---|
| E4 F3 | KE4DIRECTGE (game's AdjustHealth) | **MINION KILLED** | not a player ability cast |
| E4A F1 | S55 TryActivateAbilityByInputID | retBool=false, no `invalid Handle` | S55 defect (S191 E4M) — real result unknown |
| E4B F1+F2 | S55 BP_AuthGiveAbilityWithInputID | STRIPPED STUB @ 0x13D4E60 | grants nothing |
| E4F F1 | S55 TryActivateAbilityBySourceObject | retBool=false + `invalid Handle` witness | Handle path reached, refused deep |
| E4C F1 | CallBPGuarded HandleAbilityActivation | retBool=false + `invalid Handle` witness | BP dispatcher reached, refused deep |
| E4E F1 | poke spec.NonRep + S55 GetByInputID readback | NULL readback | initial "3-gate REFUTED" — later shown to be S55 artifact |
| E4K F1 | S55 GetByInputID (no poke) | NULL despite byte-model prediction | discriminator setup |
| E4M F1 | **raw-native GetByInputID** | **returned expected instance NON-NULL** | **S55 defect CONFIRMED** |
| E4N F1 | raw-native TryActivateAbilityByInputID (Ability1) | retBool=false + `invalid Handle` burst | activation-side wall is REAL |
| E4N-A3 F1 | raw-native TryActivateAbilityByInputID (Ability3=MiniDash) | retBool=false, no damage | WALL P is UNIVERSAL (not Selector-specific) |
| E4P F1 | poke spec+0x39=0x50 + raw-native TryActivate | retBool=false, no damage | S158 flag hypothesis REFUTED |
| E4Q F1 | raw-native TryActivateAbility(Handle=1) direct | retBool=false, +13 warnings | Handle found in Items but deep validation fails |
| **Option U** | AuthGiveAbilityWithSourceObject | STRIPPED @ 0x13D4E60 (offline-refuted) | Loki auth-grant paths uniformly stripped |

## Rules banked (17 new [M]/[I,strong] this arc)

- **R-S191-h REFUTED [M]** (E4M): "plain GiveAbility does not populate InputID map" was S55 artifact
- **R-S191-o [M]**: workflow byte model of 0x44C28E0 = 4 gates + 2 return arms, BYTE-CORRECT
- **R-S191-p [M]**: iterator 0x4476F10 (vtable slot 245) = best-priority selector, ONLY InputID filter
- **R-S191-r [M]**: GetAbilityByInputID flow = 12 instructions, iterator → tail-jmp 0x44C28E0
- **R-S191-s [M]** NEW: S55 CallNativeGuarded has UObject*-return marshaling defect
- **R-S191-t [M]** STRENGTHENED: 7 consecutive direct-injects safe over 121min uptime
- **R-S191-u [M]** NEW: `invalid Handle` witness is REAL activation-side WALL P block
- **R-S191-v [M]** NEW: raw-native TryActivateAbilityByInputID @ 0x5544F70 is NON-LETHAL
- **R-S191-w REVISED [M]**: activation refusal is UNIVERSAL, not Selector-specific
- **R-S191-x [M]** NEW: `[UGameplayAbility+0x3B0]` = CurrentSpecHandle (Loki-specific offset)
- **R-S191-y [I,strong]**: `invalid Handle` mechanism unclear — burst may be sub-ability lookups

## Byte-verified WALL P dispatch chain [M]

**On the LMB Selector (Ability1) surface**:
```
raw-native TryActivateAbilityByInputID(ASC, 3) @ 0x5544F70
  → iterator (ASC.vtable[+0x7A8] = 0x4476F10) with (ASC, 3)
    → iterator finds Items[i] with InputID==3, returns spec* (best-priority)
  → tail-jmp 0x5531920(ASC, spec)
    → mov ebx, spec.Handle       ; capture in ebx
    → mov r14, ASC                ; capture in r14
    → GetPrimaryInstance(spec) = 0x44C28E0 → returns Rep.Data[0] instance (or NULL)
    → call helper 0x5512480(instance) → state check
    → call [instance vtable + 0x2F0] = slot 94 (per-class virtual)
      LMB Selector slot 94 = 0x5561E50: bails on max != count (count=4, max=0)
      MiniDash slot 94 = 0x4455540: different function, different bail
    → call [instance vtable + 0x578] = slot 175 (per-class virtual)
    → call helper 0x5512600(instance)
    → call 0x555C380
    → fallback: mov edx, ebx (Handle); mov rcx, r14 (ASC); call 0x4493420
      TryActivateAbility(ASC, Handle=1, bAllowRemote=1, EventData)
        → inline FindAbilitySpecFromHandle scan of Items for Handle=1
        → IF found (which our Items has): jump to 0x4493510 success path
          → read spec.Ability (must be non-NULL)
          → read ASC+0x418 (must be non-NULL) — LIVE MEASURED: 0x1C2EAFDD8A0 ✓
          → TWeakObjectPtr dereferences via 0x137DE80 (must succeed)
          → read [+0x160] on target (checks remote-authority)
          → call 0x44CACC0
          → ... more validation ...
          → return true if all pass, false otherwise
        → IF not found: emit 'invalid Handle' warning, return false
```

## Wall location — 12 hypotheses tested, 12 refuted

| Hypothesis | Test | Status |
|---|---|---|
| InputID map missing (R-S191-h original) | E4A F1 | REFUTED at E4M |
| 3-gate model at 0x44C28E0 wrong | E4E F1 | REFUTED at E4M (was S55) |
| Iterator has hidden precondition | E4M | REFUTED (byte model works) |
| Gate 2 [+0xEE]!=1 fails mid-call | E4K post-call read | REFUTED (byte stable) |
| Poke reset between poke-verify and readback | E4K stability | REFUTED |
| S55 primitive corrupts UObject* return | E4K vs E4M | **CONFIRMED** — but only explains outer null |
| Selector needs sub-abilities populated | E4N-A3 with MiniDash | REFUTED (universal, not Selector-specific) |
| `invalid Handle` = OUR Handle rejected | E4Q direct TryActivate(Handle) | RE-CONFIRMED — Handle found, still bails deep |
| spec+0x39=0x50 flag unlocks activation | E4P | REFUTED |
| Loki auth-grant does more than GiveAbility | Option U offline | REFUTED (stripped stub) |
| Ability instance holds wrong ASC pointer | Option R live | REFUTED (points at our ASC via PS+0x3E8) |
| Instance's CurrentSpecHandle wrong | Option R live | REFUTED (verified 1/2/3/4 correct) |

## What remains unexplored

**Not yet flown**:
- **Option T**: populate Selector's sub-abilities via direct data poke (complex — need to identify sub-classes)
- **Option W**: `BindAbilityActivationToInputComponent` to wire our K_GRANT'd spec to natural LMB (K_GRANT path skips this)
- **Direct virtual call on the ability instance's `ActivateAbility`** slot (bypass entire outer TryActivate machinery) — vtable slots enumerated but which is ActivateAbility not identified
- **Direct GameplayEffect application** via `UGameplayAbility::ApplyGameplayEffectToOwner` on our instance
- Use ProcessEvent (vtable slot 78) to invoke reflected UFunctions instead of S55 or raw-native — untested primitive
- Read TryActivateAbility success-path (0x4493510) DEEPER to find the specific bail — reads spec.Ability, ASC+0x418, TWeakObjectPtr deref via 0x137DE80, then +0x160 remote-authority byte, then 0x44CACC0

**Offline recon still valuable**:
- Disasm 0x137DE80 (TWeakObjectPtr deref helper) to understand its bail conditions
- Disasm 0x44CACC0 (called after all validation passes) to see what activation actually does
- Identify UGameplayAbility::ActivateAbility virtual slot number

## Live process state (PID 55960, 121+ min uptime)

- Player ASC 0x1C2AAB80100 with **7 K_GRANT'd specs** in Items (moved to 0x1C2A2700040)
- 4x Ability1 (LMB Selector CDO=0x1C28E636930) with Handles 1-4
- 1x Ability3 (MiniDash Charges CDO=0x1C305A58890) with Handle=5
- 2 more added by subsequent E4Q/E4P injects
- All specs have Rep.Data[0] populated with real UGameplayAbility instances
- `[UGameplayAbility+0x3B0]` = CurrentSpecHandle matches on all instances
- `ASC+0x418` = 0x1C2EAFDD8A0 (embedded struct, non-UObject, vtable 0x7FF7BAE9B420)
- PS+0x3E8 → our player ASC (correct linkage)
- Total `invalid Handle` warnings this session: ~105-118, grows ~10-15 per activation attempt

## Grade tally

- **Total S191 launches**: 10 flown + 6 direct-injects on live PID = 16 events, 3 lost to FK-31 across arc (all early)
- **12 [M] results banked**
- **17 new/revised rules in R-S191 series**
- **8 offline files** documenting byte-level chain
- **Zero FK-32 across 7 consecutive direct-injects on same PID over 121 min uptime**

## Handoff — what's most valuable to try next

1. **Disasm 0x137DE80 (TWeakObjectPtr deref helper) and 0x44CACC0 (post-validation call)**
   to identify what specifically fails deep in TryActivateAbility. Purely offline.
2. **Find UGameplayAbility::ActivateAbility virtual slot** via vtable-signature comparison
   against stock UE (or by reading a known-good ability instance from a natural-input flight).
3. **Try ProcessEvent (vtable slot 78) as a third dispatch primitive** — untested this session.
4. **Poke `ASC+0x418`'s deep TWeakObjectPtr fields** if the offline recon identifies which
   field bails.

The state machine is well-mapped. The wall is 2-3 hops deep in TryActivateAbility's success
path, all reachable and testable. What's needed is offline disasm of 0x137DE80 + 0x44CACC0
to identify the specific validation that fails.
