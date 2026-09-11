# S191 E4B — BP_AuthGiveAbilityWithInputID IS A STRIPPED STUB [M] (2026-09-10)

★★★★★★★★ **CRITICAL FK-1 REGISTER EXTENSION**: the reflected InputID-aware grant
`ULokiAbilitySystemComponent::BP_AuthGiveAbilityWithInputID` (offline design's proposed
fix for the InputID→spec map, per R-S191-h1) is a **STRIPPED STUB**. The wrapper at
`base+0x5294B50` (S153-graded REAL) tail-calls impl `base+0x13D4E60`, which is a
**9-byte fold** that writes `0xFFFFFFFF` (INDEX_NONE) to the outHandle pointer and
returns. Two live flights confirm: retHandle=0, dItems=+0, whether or not our K_GRANT
had already registered a plain spec.

This is a NEW FK-1 register entry. **Option B is a dead end.** The offline design in
`docs/s191-lmb-input-binding-mapped.md` was correct that BP_AuthGiveAbilityWithInputID
is architecturally what would populate the InputID→spec map — but it can't, because it
doesn't do anything.

## The stripped impl (verbatim, byte-level)

Disassembled from `dumps/merged14.dump.exe` at RVA `0x13D4E60`:

```
0x013D4E60  c7 02 ff ff ff ff  mov dword ptr [rdx], 0xFFFFFFFF   ; outHandle->Handle = -1
0x013D4E66  48 8b c2           mov rax, rdx                       ; return outHandle*
0x013D4E69  c3                 ret
```

The wrapper at `0x5294B50` packs 5 params via UHT machinery, then at `0x5294D27` calls
`0x13d4e60`, then `0x5294D34 mov ecx, [rax]` reads the -1 from outHandle, then
`0x5294D36 mov [r14], ecx` writes it to the CALLER's result pointer. The wrapper's
return is the -1 handle from the stripped impl.

## Two flights, both refuting the "map-not-populated" and "duplicate-detection"
   hypotheses in favor of "STUBBED IMPL":

### E4B flight 1 (KBFARMS=0xC6, K_GRANT ON, `docs/s191-e4b-flight1-marker.log`)

```
[E4B] pre-grant  hero.Ability1@0x1F00 = 0x17F051185F0(GS_Ronin_LMB_Selector_C) pASC=0x17E8D526700
[E4B] E4B_CALL_ISSUE: BP_AuthGiveAbilityWithInputID(Class=0x17F051185F0,Level=1,InputID=3,Source=hero,Priority=0) ; target=base+0x5294B50 ; Items pre=1 ; param offsets AC=0x0 AL=0x8 ID=0xC SO=0x10 PR=0x18
[E4B] E4B_RESULT   faulted=no retHandle=0 ItemsPre=1 ItemsPost=1 dItems=+0
[E4A] E4A_GETBYID  faulted=no return=0x0(NULL) ; E4A_RESULT retBool=0
```

I initially interpreted this as "duplicate detection" because K_GRANT had already added
a spec (Items=1 pre-E4B). Fly-2 test.

### E4B flight 2 / e4-b2 (KBFARMS=0xC2, K_GRANT OFF, `docs/s191-e4b2-flight1-marker.log`)

```
[BF] player ActivatableAbilities Num = 0                              ← K_GRANT correctly skipped
[E4B] pre-grant  hero.Ability1@0x1F00 = 0x261FDEE2380(GS_Ronin_LMB_Selector_C) pASC=0x2619BF29A00
[E4B] E4B_CALL_ISSUE: BP_AuthGiveAbilityWithInputID(...) ; Items pre=0 ; param offsets AC=0x0 AL=0x8 ID=0xC SO=0x10 PR=0x18
[E4B] E4B_RESULT   faulted=no retHandle=0 ItemsPre=0 ItemsPost=0 dItems=+0   ← SAME REFUSAL with clean slate
[E4A] E4A_GETBYID  faulted=no return=0x0(NULL) ; E4A_RESULT retBool=0
```

Duplicate detection REFUTED. Same result on a completely empty Items TArray. This
motivated the offline disasm that found the stripped impl.

## Why S153 sweep missed this stub

S153's sweep grades a UFunction by:
- Loading its `Func` pointer from `.data`
- Reading the impl bytes at that address
- Checking for known fold signatures (`0xF7EC20` void_ret, `0xF7EB60` LokiIsServer FALSE,
  `0xF7EB50` null-return, `0xFC6CF0` zero-float, plus prologue-then-tail-call patterns
  for the S152 AuthCheatSetHealth case)

`BP_AuthGiveAbilityWithInputID` at `0x5294B50` starts with a real MSVC prologue
`48895c2408 555657415641574883ec60` — passes the "not a fold prologue" test → graded
REAL. The sweep then looks for tail-calls to known fold RVAs; the wrapper's tail-call
is to `0x13d4e60` (not a known fold RVA), so it's graded REAL there too.

But `0x13d4e60` is itself a NOVEL 9-byte stripped stub with the shape `mov [rdx],
0xFFFFFFFF ; mov rax,rdx ; ret`. Not any of the fold signatures the sweep knew about.

**⇒ R-S191-l**: the S153 sweep's "REAL" grade for an UFunction whose Func points at a
wrapper is only reliable UP TO the wrapper's own bytes. Whether the wrapper's
tail-called impl is stripped requires a second-order check. Add "write-INDEX_NONE-and-
return" to the sweep's fold signature set, and follow tail-calls one level.

## Rule banked

- **R-S191-l** (new [M]): `ULokiAbilitySystemComponent::BP_AuthGiveAbilityWithInputID`
  wrapper `0x5294B50` → impl `0x13D4E60` = 9-byte stripped stub
  (`c702ffffffff 488bc2 c3` = write `0xFFFFFFFF` to `[rdx]` = outHandle, return outHandle
  pointer). Same class as S152's `AuthCheatSetHealth` (stub tail-called from a real
  wrapper). Cannot grant an ability, cannot populate the InputID→spec map. Registered in
  the FK-1 register.
- **R-S191-m** (methodology): the S153 native-UFunction sweep grades WRAPPERS, not
  IMPLS. A UFunction whose wrapper tail-calls a novel stub is graded "REAL" though its
  body-work does nothing. To close this gap, extend the sweep's fold-signature set to
  include "write-INDEX_NONE-and-return" and other short-stub patterns, and follow
  wrapper tail-calls one level before grading.

## What is now the definitive path forward

Three remaining Option-C-family paths, in order of plausibility given the finding:

**Option C — `Comp_PlayerController_Abilities.HandleAbilityActivation(3)`.** The BP
dispatcher on the PlayerController's abilities component. It internally consults
`GetAbilityByInputID` (which returns NULL for us per E4A) — but the ubergraph shows it
ALSO has `TryActivateAbilityByClass` and `TryActivateAbilityBySourceObject` code paths.
If any branch fires those (and both are REAL on the ASC), the ability may activate. The
BP dispatcher is BP-authored, not native, so it isn't at risk of the same stripped-stub
class. Cheap flight: add a `KBFE4C` knob that calls it via S55.

**Option E (new) — populate the InputID→spec map DIRECTLY.** Since
BP_AuthGiveAbilityWithInputID's impl is stripped, we need to find the InputID→spec map
on the ASC (offsetwise) and insert `{3 → &spec}` ourselves after K_GRANT. Requires
reading `ULokiAbilitySystemComponent::GetAbilityByInputID`'s impl at `0x5295330` (S153
REAL — but this is the query getter, not the grant, so its impl should be REAL).
Whatever offset it reads is the map to write.

**Option F — activate `GetAbilityBy*` variants and see which finds our spec.**
`GetAbilityBySourceObject` / `TryActivateAbilityBySourceObject` (impl `0x5297230` REAL)
match on `spec.SourceObject` (which our K_GRANT sets = hero). If that path works, we
have a shim-driven activation without needing to fix the InputID map at all.

**⇒ Priority: Option F (cheapest — one probe call), then Option C, then Option E.**

## Cost

- 2 launches, 0 losses to FK-31 (both first-try successes)
- 0 collateral damage (both games alive past 275s, cleanly killed post-flight)
- 1 offline disasm session (unblocks the whole understanding)

## Regression gates + digests

- `botai b620e0ff3279e673` — UNCHANGED throughout
- `e4-b RAW=39f1ae3c41fbc1ad` — verify_dll PASS, KERNEL32-only
- `e4-b2 RAW=5827bc3863157d25` — verify_dll PASS, KERNEL32-only
- `e4-a RAW=2d7efa4cde249f2e` — UNCHANGED (the KBFE4B block truly dead-strips)
- `e4 RAW=69197ce6e9e38dda` — UNCHANGED (E4B block truly dead-strips)
- `--dupes` clean

## Files

- `docs/s191-e4b-flight1-marker.log` — shim marker (K_GRANT ON, Items=1 pre-E4B)
- `docs/s191-e4b-flight1-loki.log` — game log
- `docs/s191-e4b2-flight1-marker.log` — shim marker (K_GRANT OFF, Items=0 pre-E4B)
- `docs/s191-e4b2-flight1-loki.log` — game log
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFE4B knob + `#if KBFE4B` block in
  BfE4SpawnSeedTarget's E4A section
- `tools/sigbypass-mod/build.ps1` — `e4-b` and `e4-b2` variants
