# S191 Option U (AuthGiveAbilityWithSourceObject) REFUTED offline [M] — 2026-09-10

★★★★★★★ **`ULokiAbilitySystemComponent::AuthGiveAbilityWithSourceObject` (S153 CLAIMED REAL at
0x5294750) IS ACTUALLY A UHT WRAPPER OVER A STRIPPED STUB. Its exec wrapper parses FFrame
parameters correctly then tail-calls impl at RVA 0x13D4E60 — the SAME 9-byte stripped stub
that CLAUDE.md's S191 E4B RESULT identified for `BP_AuthGiveAbilityWithInputID`. Both Loki
auth-grant paths converge on this stub, which writes INDEX_NONE to the caller's outHandle and
returns.**

Pure offline byte-verification against `dumps/merged16.dump.exe`. Zero launches, zero shim,
zero live process interaction.

## The evidence

`AuthGiveAbilityWithSourceObject` exec wrapper @ RVA `0x5294750`. The FFrame-parsing prologue
(saving parameters, calling UE step-frame helpers `0x12F3FC0`, `0x1345FB0`, `0x1345FE0`,
`0x133EEA0`) reads AbilityClass, AbilityLevel, and SourceObject correctly. Then at
`0x5294870`:

```
0x0529486B  48 8d 54 24 70            lea    rdx, [rsp + 0x70]     ; rdx = &outHandle
0x05294870  e8 eb 05 14 fc            call   0x13d4e60             ; TAIL CALL to impl
0x05294875  48 8b 5c 24 60            mov    rbx, qword ptr [rsp + 0x60]
0x0529487A  8b 08                     mov    ecx, dword ptr [rax]  ; read *outHandle
0x0529487C  89 0e                     mov    dword ptr [rsi], ecx  ; propagate to return slot
0x0529487E  48 83 c4 40               add    rsp, 0x40
0x05294885  c3                        ret
```

And `0x13D4E60` (byte-verified in merged16):

```
0x013D4E60  c7 02 ff ff ff ff         mov    dword ptr [rdx], 0xFFFFFFFF   ; INDEX_NONE
0x013D4E66  48 8b c2                  mov    rax, rdx
0x013D4E69  c3                        ret
```

**The stub writes `-1` (INDEX_NONE) to the outHandle pointer and returns.** The wrapper then
reads this `-1` and propagates it as the function's return value. `AuthGiveAbilityWithSourceObject`
NEVER GRANTS.

## What this settles

**Option U from E4N follow-up recon is DEAD.** The hypothesis was that
`AuthGiveAbilityWithSourceObject` might do more setup than plain `GiveAbility` (specifically,
populate a Selector's sub-abilities). It cannot — it doesn't grant anything at all.

**All ULokiAbilitySystemComponent auth-grant paths known so far are stripped**:
- `BP_AuthGiveAbilityWithInputID` @ 0x5294B50 → 0x13D4E60 (E4B F1 [M])
- `AuthGiveAbilityWithSourceObject` @ 0x5294750 → 0x13D4E60 (this doc [M])

Both share the same 9-byte stub. Loki's server-side grant path is uniformly stripped in the
shipped client.

## What survives as WORKING grant paths

- **Plain UE `GiveAbility`** via `[ASC.vtable+0x778]` — the engine grant virtual. This is what
  our K_GRANT already uses. Works: adds a spec to Items with Handle, InputID, Ability=CDO.
  Does NOT populate Selector sub-abilities.

That's the only working grant path we have. Anything requiring sub-ability population must
find another mechanism (e.g. an ability's own `OnGiven` hook that self-populates, or a
direct data poke of the sub-abilities array).

## S153 sweep classification correction

The S153 native-UFunction sweep classified `AuthGiveAbilityWithSourceObject` as **REAL** based
on the wrapper prologue at 0x5294750 having a real MSVC prologue. This missed the tail-call
target's stripped nature — the same false-positive class that CLAUDE.md's E4B RESULT flagged
for `BP_AuthGiveAbilityWithInputID` ("S153 sweep grades wrappers not impls").

**Suggested rule**: any S153 sweep re-run should classify BOTH the wrapper's own prologue AND
its tail-call target. For UHT-emitted exec wrappers whose signature is `execFoo(ctx, &frame,
&outResult)`, the wrapper's tail call is the semantically-significant target — a wrapper that
tail-calls a fold stub is FUNCTIONALLY stripped even if its own prologue is real.

**Adds to FK-1 register**:
- Entry #6: `ULokiAbilitySystemComponent::AuthGiveAbilityWithSourceObject` exec 0x5294750 →
  impl 0x13D4E60 (SHARED stripped stub with BP_AuthGiveAbilityWithInputID)

## Session summary — S191 arc (Sep 10, 2026)

Building on prior E4/E4A/E4B/E4C/E4F flights, this session's arc:

| Commit | Milestone |
|---|---|
| a1be19b | E4E arm BUILT (KBFE4E direct-offset NonRep poke) |
| 80578e0 | E4E Flight 1 — apparent NULL readback |
| fc8d9fc | Live spec[0] dump: Rep.Num=1 finding (game auto-instances) |
| 7fc47b5 | Direct disasm: byte model + iterator + GetByInputID VERIFIED |
| d2d922f | **E4K+E4M BREAKTHROUGH: S55 primitive UObject*-return defect** |
| c80c021 | E4N: raw-native TryActivate NON-LETHAL + 'invalid Handle' witness IS REAL |
| fb40bb9 | E4N follow-up: Selector sub-ability population defect |
| 98c76f0 | **E4N-A3 (MiniDash): WALL P is UNIVERSAL, not Selector-specific** |
| (this)  | Option U (AuthGiveAbilityWithSourceObject) REFUTED offline |

**5 flights, 0 launches lost, 0 FK-32 across 5 consecutive direct-injects into PID 55960
over 102min uptime.**

Key findings:
- **R-S191-s [M]** NEW: S55 CallNativeGuarded primitive has UObject*-return marshaling defect
- **R-S191-h REFUTED [M]**: "plain GiveAbility does not populate InputID map" — was S55 artifact
- **R-S191-o [M]**: workflow's 3-gate model at 0x44C28E0 is BYTE-CORRECT
- **R-S191-p [M]**: iterator 0x4476F10 has only InputID filter + priority tie-break
- **R-S191-t/v [M]**: raw-native calls into game code safe over 102min uptime
- **R-S191-u [M]**: 'invalid Handle' witness IS REAL, downstream of 0x5531920 virtuals
- **R-S191-w REVISED [M]**: activation refusal is UNIVERSAL (not Selector-specific)
- **R-S191-x [M]**: `[UGameplayAbility+0x3B0]` = CurrentSpecHandle (Loki-specific offset)

Current wall: something structural in natural-input-granted specs that plain-GiveAbility specs
lack. Both Ability1 (Selector) and Ability3 (MiniDash Charges) refuse activation via raw-native
TryActivateAbilityByInputID even when their instances are populated. Both auth-grant paths are
stripped. Need to identify what natural-input path does that plain-GiveAbility doesn't.
