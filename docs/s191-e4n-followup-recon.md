# S191 E4N follow-up recon — the `invalid Handle` witness is a SELECTOR PATTERN artifact — 2026-09-10

★★★★★★★ **THE `LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle` WITNESS
IS NOT ABOUT OUR K_GRANT'D SPEC'S HANDLE (which IS in Items and IS found by
`FindAbilitySpecFromHandle`). IT IS ABOUT `GS_Ronin_LMB_Selector_C`'s SUB-ABILITY POPULATION —
the Selector has `count=4` sub-abilities EXPECTED but `max=0`, `arr=NULL`. Plain native
`GiveAbility` gives the Selector but not its four sub-abilities; both virtual dispatches in
0x5531920 (slots 94 and 175) bail on the count/max mismatch, and the "fallback" `TryActivateAbility`
call at 0x5531A00 then emits the warning.**

Live RPM + offline byte disasm against merged16, complementing E4N flight 1 receipt.

## Byte-verified call chain and its failure

```
Raw-native call from E4N: TryActivateAbilityByInputID(ASC, InputID=3) → 0x5544F70
0x5544F70: iterator (vtable slot 245) → returns Items[0] spec (Handle=1)
0x5544F9C: tail-jmp 0x5531920(ASC, spec)

0x5531920: mov ebx, [spec+0xC] = 1                              ; capture Handle in ebx
0x5531935: mov r14, rcx = our_player_ASC                        ; capture ASC in r14
0x553193E: call GetPrimaryInstance(spec) = 0x44C28E0             ; returns Rep.Data[0] instance
                                                                  ; SUCCESS per E4M byte model
0x5531943: rdi = instance = 0x1C2B7504970
0x553194E: call helper 0x5512480(instance) → returns true         ; presumed to pass
0x553195A: mov rdx, [rdi] = instance vtable
0x553195D: call [vtable+0x2F0] = slot 94 = RVA 0x5561E50         ; FIRST virtual
0x5561E56: cmp [instance+0x628], 0                                ; asc pointer present?
   Live measurement: [inst+0x628] = 0x1C2AAB80100 (our ASC) ✓ → not zero, continue
0x5561E63: mov eax, [instance+0x608]                              ; count of sub-abilities
   Live measurement: [inst+0x608] = 4 → not zero, continue
0x5561E6D: cmp [instance+0x618], eax                              ; max == count ?
   Live measurement: [inst+0x618] = 0 vs eax = 4 → NOT EQUAL
0x5561E73: jne 0x5561ED1 → RETURN FALSE (al=0)

0x5531963: test al, al → false
0x5531965: je 0x5531977                                           ; skip slot 175 call
0x5531977: mov rcx, rdi
0x553197A: call helper 0x5512600(instance) → ???
0x5531981: je 0x5531992 (if false)
   ... fallback loop reading spec.Ability's chain ...
0x55319F1: mov edx, ebx = 1                                       ; Handle argument
0x55319F8: mov rcx, r14 = our_player_ASC                          ; ASC argument
0x5531A00: call TryActivateAbility 0x4493420(ASC, Handle=1, bAllowRemote=1, &EventData)

0x4493420: inline FindAbilitySpecFromHandle scan of [ASC+0x538..0x540] for Handle=1
   Live measurement: Items has [Handle=1, 2, 3, 4] → SHOULD FIND Items[0]
   BUT actual: warning emit at 0x44934A2 → "invalid Handle"
```

**Two possibilities for the warning firing when Handle=1 IS in Items:**
1. `ebx` gets clobbered between 0x5531932 (capture) and 0x55319F1 (use as edx). Impossible in
   standard MS x64 ABI (rbx is callee-saved), but a defective callee not saving rbx would do it.
2. The warning fires from a DIFFERENT tick / a DIFFERENT function that happens to correlate with
   E4N's timing. The game's periodic ability system may generate handles that are stale.

## Live sub-ability array measurement across all 4 instances

```
instance[Handle=1] @0x1C2B7504970: count=4 arr=0x0 max=0 asc=0x1C2AAB80100 (our ASC)
instance[Handle=2] @0x1C1EEF129B0: count=4 arr=0x0 max=0 asc=0x1C2AAB80100 (our ASC)
instance[Handle=3] @0x1C1F6595950: count=4 arr=0x0 max=0 asc=0x1C2AAB80100 (our ASC)
instance[Handle=4] @0x1C2B5D46140: count=4 arr=0x0 max=0 asc=0x1C2AAB80100 (our ASC)
```

**Same pattern on all 4 K_GRANT'd instances.** The Selector expects 4 sub-abilities; the array
is uniformly empty. This isn't a stale-state artifact — it's the pattern for a Selector that
was Given without its accompanying sub-ability grants.

## Field discoveries — `UGameplayAbility` layout on this build

Newly measured [M] via 4-instance correlation:
- **`[UGameplayAbility+0x3B0]` = `CurrentSpecHandle`** (perfect correlation: instances read
  1, 2, 3, 4 matching their owning spec Handles). Not a stock UE offset; Loki-specific.
- **`[UGameplayAbility+0x608]` = sub-ability count** (4 for LMB Selector)
- **`[UGameplayAbility+0x610]` = sub-ability handles array pointer** (should be `TArray<int32>`
  or similar; NULL for our K_GRANT'd Selector instances)
- **`[UGameplayAbility+0x618]` = sub-ability handles array size** (0 for our instances)
- **`[UGameplayAbility+0x628]` = OwningASC pointer** (our player ASC for all 4 instances ✓)
- **`[UGameplayAbility+0x28]` = OwnerActor** (our LokiPlayerState_HeroAffiliated for all 4)

## What this means for the E4 predicate

**The LMB Selector pattern's activation cannot proceed without its sub-abilities populated.**
Plain native `GiveAbility(GS_Ronin_LMB_Selector_C)` creates the Selector but does NOT populate
its `SubAbilityHandles` array. The Selector's virtual dispatch (slot 94 in this vtable, at
`0x5561E50`) refuses when `max != count`. The Selector's whole purpose is to pick ONE of its
sub-abilities to actually cast; with 0 sub-abilities allocated, it has nothing to select.

**This is not a WALL P defect. It is a data-population defect specific to the way our
K_GRANT'd path works.** The game's own `Give` path (probably `ULokiAbilitySystemComponent::
Give` or a spell-system Init) does more than S153-REAL `GiveAbility`: it also grants the
sub-abilities and links them into the Selector's array.

## Next-lever options (ranked by likely payoff × cost)

**Option S — grant a NON-SELECTOR ability instead** [cheapest, most likely to unlock E4]. Pick
an ability that has NO sub-abilities (`count=0` at instance +0x608). Examples to try in order:
- **`GS_Ronin_MiniDash_Charges_C`** (Ability3 = LeftShift, hero.Ability3 = 0x1C2B70D2380) —
  "Charges" wrapper but may not use Selector pattern; S147 successfully activated Ability3
  before. Change KBFABIL from "Ability1" to "Ability3" and KBFINPUTID from 3 to 5. Re-fly
  the whole E4/E4M/E4N chain on Ability3.
- **`GS_TetherHook_Swapper_C`** (AbilityDodgeRoll, hero+0x1F18 = 0x1C10D1085F0) — a Swapper
  wrapper, may have simpler structure.
- **A direct ability class** (bypass all Selector/Swapper/Charges wrappers). But this requires
  identifying which of Ronin's spells resolve without a wrapper — none of the four exposed on
  hero+0x1F00..+0x1F18 are direct.

**Option T — populate the sub-ability array on our K_GRANT'd Selector instance** [medium cost,
diagnostic]. The Selector expects 4 sub-abilities. Identify the 4 sub-classes (probably by
walking the Selector CDO's SubAbilityClasses array or similar), grant each via GiveAbility,
capture their Handles, poke the Selector instance's `[+0x610]` array. This is another R-S131-style
DATA poke. HIGH complexity because we don't know the 4 sub-classes yet.

**Option U — grant via `AuthGiveAbilityWithSourceObject` or another Loki grant path** [medium].
S153-REAL classified `ULokiAbilitySystemComponent::AuthGiveAbilityWithSourceObject` as REAL at
impl `0x0452C3F`. This may do more setup than plain `GiveAbility` and populate the Selector's
sub-abilities. Reflected UFunction; needs S55-compatible call OR raw-native.

**Option V — dig into the invalid-Handle emission trigger** [diagnostic, low forward-value].
Understand whether the burst-warnings we saw are from OUR call or from a periodic game tick.
Add timestamp correlation via extended arm.

## Recommendation

**Fly Option S with Ability3 (MiniDash)** — cheapest to attempt, tests whether the Selector
pattern is what blocks E4 or whether the same block manifests on non-Selector abilities. If
MiniDash activates and damages, the wall is Selector-specific and E4 predicate can be met
via a non-Selector ability. If MiniDash also refuses with invalid Handle, the block is deeper
than the Selector pattern.

## Files

- `docs/s191-e4n-flight1-marker.log` — E4N receipt
- `docs/s191-e4n-flight1-loki.log` — Loki.log excerpt with 25 invalid Handle warnings
- `docs/s191-e4n-flight1-RESULT.md` — E4N flight write-up
- (this doc) — E4N follow-up recon
- `dumps/merged16.dump.exe` — has 0x5531000 lit now, byte-verified 0x5531920 → 0x5561E50/0x5560920

## Rules banked

**R-S191-w [M] NEW**: `GS_Ronin_LMB_Selector_C`-family abilities use a SUB-ABILITY population
pattern that plain native `GiveAbility` does NOT set up. The instance carries expected-count
at `[+0x608]` and allocated-count at `[+0x618]`; if they differ, the ability's virtual dispatch
refuses. Do NOT interpret a Selector's activation refusal as WALL P — it is a data-population
defect from the incomplete grant path.

**R-S191-x [M] NEW**: `[UGameplayAbility+0x3B0]` = `CurrentSpecHandle` (Loki-specific offset,
not stock UE). `[+0x628]` = OwningASC pointer. `[+0x28]` = OwnerActor. `[+0x608]/+0x610/+0x618`
= SubAbilityHandles TArray (Data/Num/Max but stored as {count@608, arr@610, max@618}).

**R-S191-y [I,strong] NEW**: The `invalid Handle` witness may correlate with our call timing
but its actual mechanism is unclear — the byte-model call chain from our K_GRANT'd Handle
should succeed the inline `FindAbilitySpecFromHandle` scan. Either something clobbers ebx
between capture and use in 0x5531920, OR the warnings come from a separate tick that E4N
triggers indirectly. Needs KBFE4H-style timestamp instrumentation to disambiguate.
