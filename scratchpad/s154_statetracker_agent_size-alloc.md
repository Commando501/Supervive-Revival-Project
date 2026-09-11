## BEST-GUESS CLASS NAME: **`ALokiPlayerController`** (the Loki-side native PlayerController base of `BP_LokiPlayerController_Dev_C`)

### Confidence: **MEASURED**

### Evidence chain (each independently reproducible)

1. **Ctor installs a vtable whose identity is already documented.** `0x56777B0` opens with `call 0x559790` (base ctor, dark), then `lea rax, [rip + 0x33a36f6]` → **vtable RVA `0x8A1AEE0`** stored at `[rdi+0]`. That exact RVA is what `tools/sigbypass-mod/tutorial_launch.cpp:23624` reads live from `Default__BP_LokiPlayerController_Dev_C`'s CDO across 30+ stage markers over months (`docs/fk24-stage-*-gft.txt`: `lokiCDO=... (vt rva 0x8A1AEE0)`), against the STOCK `Default__PlayerController` vt at `0x81A82F8`. BP classes inherit the C++ base's vtable ⇒ the C++ class whose ctor this is = the base of `BP_LokiPlayerController_Dev_C` = **`ALokiPlayerController`**.

2. **The 4-gate chain closes the "how do we reach this from a pawn" question.** Gate 3 `0x54F8DC0` = `IsChildOfUsingStructArray` with `.rdata 0x899A832 = "LokiHeroCharacter"` literal (CLAUDE.md, S132) ⇒ `validated_object` is a `LokiHeroCharacter` (pawn). `r14 = [pawn + 0x400]` = **`APawn::Controller`** (S135 disassembly of `APawn::SpawnDefaultController`: `cmp qword [rcx+0x400],0`). The tracker is the pawn's Controller.

3. **Size fits, and only fits, a PC-family class.** Ctor writes up through `[rdi + 0xFA0]/[rdi + 0xFA8]` ⇒ SizeOf ≥ 0xFA8. Consistent with `ALokiPlayerController` (stock `APlayerController` alone is already ~0x800). All 8 state offsets `[+0xBEC..+0xC0D]` sit comfortably in that range.

4. **Reachability shape.** rel32 scan of `.text`: **exactly ONE reference** to ctor `0x56777B0` (a `jmp` at `0x541995E` in the same TU) and **exactly TWO** `lea` refs to vtable `0x8A1AEE0` (ctor `0x56777E3` + dtor-area `0x5419FC4`). That is the "class-only-reachable-via-FClassParams-hook" shape — as expected for a UClass whose CDO is instantiated by `NewObject`/`FObjectInitializer`.

5. **Vtable body matches a Loki UObject-derived class.** Slot 0 = `0x541A4F0` (real dtor in the same TU as the sole thunk). Slots 1/7/12/17 = `0xF7EC20` (`ret 0` fold — the FK-1-family stripped-virtual pattern that CLAUDE.md documents extensively on Loki classes). Slot 4 = `0xF7EB60` (`xor al,al; ret` = `LokiIsServer` fold). Non-null through slot ≥399, i.e. a large class layered above `AController`/`AActor`.

### UPROPERTY offset match
Not resolved from `binds_members.csv` directly — that file has **no `Offset` column** (schema: `owner_kind, member_kind, declaration, unreal_name, ...`), so it cannot answer this. The specific UPROPERTY names for `[+0xBEC..+0xC0D]` are **unresolved** here; the four sibling handlers' shape (`{double, double}` time-pair pushed to callback `0x5E5370`, each toggling a distinct boolean pair) plus the ctor's default-write constants (`0.3`, `0.7`, `0.25`, `0.05`, `250.0`, `1.0`) are consistent with **input tap-vs-hold / charge state**, i.e. this is `ALokiPlayerController`'s embedded per-input state block.

### Anti-candidates ruled out
- **Stock `APlayerController`** — its vt is `0x81A82F8`, not `0x8A1AEE0` (per shim `[PREP]` markers).
- **`ALokiBotController`** — different vtable (S137 measured `ALokiBotController::OnPossess 0x5565470` in a different TU).
- **`ALokiHeroCharacter`** — this is the *pawn* that gate 3 accepts as `validated_object`, not the object reached at `+0x400`.
- **A UActorComponent-derived subobject** — the vtable is bound to the *PC CDO's first qword*, not stored inside a component-holding UPROPERTY.

### Instrument that would resolve the UPROPERTY name offline
Walk `ALokiPlayerController`'s `FClassParams` → `PropPointers[]` in the UHT registration table (methodology used by `docs/s136-ai-controller-settled.md` §7 for `bWantsPlayerState @ +0x488`). Anchor: find the `UClass::StaticClassInternal` for `ALokiPlayerController` by scanning `.rdata` for the vtable VA `0x7FF611_95_AEE0` as an argument to `Z_Construct_UClass_ALokiPlayerController_Statics` — then decode each `FPropertyParams` with `Offset ∈ {0xBEC, 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC04, 0xC0C, 0xC0D}`.