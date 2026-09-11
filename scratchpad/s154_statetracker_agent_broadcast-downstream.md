## State-tracker class analysis (WALL P)

**Key finding: `0x4453EC0` is `UGameplayAbility::GetAvatarActorFromActorInfo`** (REAL, BP-pure getter — `scratchpad/s131/lane-d-empty-impl-census.tsv:6749`). Confirmed via `ret 0x9b02a30`-based UHT record. This rewrites the chain in fn `0x5515C55`:

```
rsi = spell (ULokiGameplaySpell)
r14 = GetAvatarActorFromActorInfo(spell)         ; = AVATAR ACTOR (character)
validate via 0x54F8DC0                            ; IsChildOfUsingStructArray (per symbols.csv:513, "Mismatch NumStructBasesInChainMinusOne")
r14 = [r14 + 0x400]                               ; deref: avatar-actor member at +0x400
validate via 0x5512380                            ; LokiCharacterMovementComponent-related helper (symbols.csv:515 explicitly labels this fn LokiCharacterMovementComponent)
propagate: [r14 + 0xC0D] = [spell + 0xC76]
```

### 1. Estimated size range
Accessed offset range on state-tracker (from `scratchpad/s154_statetracker_access_map.md`): **0xBEC, 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC04, 0xC0C, 0xC0D**. Highest = 0xC0D (byte). Minimum class size aligned to 8: **0xC10 = 3,088 B**. But this is only a floor — the class extends beyond what this state-machine slice touches.

### 2. Candidate class + rationale
**Best candidate: `ULokiCharacterMovementComponent`.** Rationale, all measured, not inferred:
- The `0x5512380` post-deref validator is explicitly labelled `LokiCharacterMovementComponent` in `docs/symbols.csv:515` (`0x5512397 = 0x5512380 + 0x17`, interior of that fn). The gate is *"after the +0x400 deref, is this a LokiCMC?"* — which forces r14 ≡ ULokiCMC by the validator's own type.
- ULokiCMC is already documented far larger than 0xC10 in this repo: `+0x12B0 TimeSinceFallingStart`, `+0x16B0 Velocity snapshot`, `+0x16C8` latch — a ~5.9 KB class easily contains a state-tracker slice at 0xBEC..0xC0D.
- The state-byte semantics (montage/timer/dash callback transitions) fit a movement-component-adjacent execution buffer, not a plain UObject.

**Weaker alternatives ruled out:**
- ULokiAbilitySystemComponent — no evidence of `+0x400` on ASC pointing to a state-tracker; ASC is on the CHARACTER at `+0xF00`, not on the AVATAR at +0x400.
- ULokiGameplaySpell subobject — rsi IS the spell (offsets to 0xF5B); r14 must be a different class since the validator explicitly demands LokiCMC-shape.

### 3. What `validated_object` is (before the +0x400 deref)
**The AVATAR ACTOR** — for MiniDash and every spell the project has flown, this is a **`ULokiHeroCharacter`** (which extends `ALokiCharacter` → `ACharacter`). `[ULokiHeroCharacter + 0x400]` is therefore this build's `CharacterMovement` UPROPERTY slot (ACharacter's stock `CharacterMovement` pointer, re-laid-out in this Loki build), pointing to the `ULokiCharacterMovementComponent`.

### 4. Measurement vs inference
- **[M]** `0x4453EC0 = GetAvatarActorFromActorInfo` (census tsv row 6749, REAL, bytecount/flags recorded).
- **[M]** `0x54F8DC0` is the IsChildOfUsingStructArray helper (symbols.csv:513 quotes the diagnostic string).
- **[M]** `0x5512380` sits inside a function symbols.csv classifies under `LokiCharacterMovementComponent`.
- **[M]** state-tracker offset range 0xBEC..0xC0D from the S154 access map.
- **[I, strong]** the identity `[AvatarActor+0x400] == CharacterMovement pointer` — not directly measured this session; supported by the LokiCMC-validator gate on r14 post-deref.
- **NOT DONE:** allocation-site scan — the CSVs supplied don't carry class-size or UHT-outer offsets in a byte-scannable form, and a full `merged14` disassembly sweep for `mov ecx, 0xC10 / call <alloc>`-shaped sites was out of scope for this pass. **Recommended next step:** the alloc site will be `CreateDefaultSubobject<ULokiCharacterMovementComponent>` in ULokiCharacter's C++ ctor — search `merged14` for calls to `UObject::CreateDefaultSubobject` with an FName-class arg resolving to `LokiCharacterMovementComponent`, not for raw malloc.