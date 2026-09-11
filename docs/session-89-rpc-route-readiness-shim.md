# S89 (2026-07-23) — DS toggle carrier: RPC route + readiness RE + the `gft_ready_fix` shim + drop-in probe

Branch `dedicated-server-stub`. Continues S88 (docs/session-88-toggle-payload-fixed-offset.md), which proved the
`GameFeatureToggles` **property array** can't be delivered on the DS route (the client reads the subobject
content-block payload as GameState field-cache entries — a client-side deserialization wall). This session pivoted
to alternate delivery, RE'd what "toggle readiness" actually is, built a working shim, and probed how far the DS
client gets toward drop-in.

## TL;DR (what's true now)

1. **RPC signature RE'd** — `void ULokiServerAuthConfig::MulticastSetGameFeatureToggle(TEnumAsByte<ELokiGameFeatureToggle> Toggle, bool bValue)` (NetMulticast, Reliable, Native). Tool: `tools/re/ufunc_params.py`.
2. **RPC delivery route WORKS at the wire level** — a hand-rolled, 11-bit-header-spliced RPC content block reads cleanly on the client (connection survives 1 AND 151 RPCs, 0 errors) — the S88 property-array wall is sidestepped. BUT it can't POPULATE the client's `GameFeatureToggles` array (the per-toggle setter presupposes a pre-sized array), so it alone doesn't make toggles "ready".
3. **Readiness is a BIT, not the array size** — `LokiGameplayStatics::GetFeatureTogglesReady` disassembles to `return bit6 of [GameState.ServerAuthConfig + 0xB3]`. Disassembly-proven + live-verified (set bit 0→1 → the query returns true).
4. **`gft_ready_fix.dll` shim built + live-verified** — auto-sets that bit on every `LokiServerAuthConfig` on launch (11/11 set, independent RPM read). Flips the readiness QUERY.
5. **Drop-in probe** — with readiness (query) flipped, the DS client LOADS the entire drop-in world (drop-plane/drop-pod UI, HUD, `LokiPlayerController` + full component suite, `Comp_GameMode_DropPlane_Tutorial`) BEHIND the loading overlay, but is **STUCK on "DROP IN, GEAR UP… LOADING…"**. The bit ≠ the readiness **EVENT** (`OnClientGameFeatureTogglesReady`) that the loading-screen/hero-setup latents (`WaitForFeatureToggles`/`LoopForFeatureTogglesReady`/`PollForFeatureTogglesReady`) await. So the world loads but never reveals.

## 1. RPC signature (RE'd via live RPM reflection — no anti-tamper)

`tools/re/ufunc_params.py <PID> <BASE> <UFuncAddr>` walks a UFunction's `ChildProperties`. Find the addr with
`find_uclass.py <PID> <BASE> MulticastSetGameFeatureToggle Function`.
- FunctionFlags 0x00024CC0 = Net | NetReliable | Native | NetMulticast; 2 params / 2-byte frame / void return.
- param0 `Toggle` = ByteProperty (enum `ELokiGameFeatureToggle`) @ frame 0; param1 `bValue` = BoolProperty @ frame 1.
- Outer = `LokiServerAuthConfig` (confirmed — the only UFunction of that name in ~187k UObjects).

## 2. RPC delivery route (in the stub, guarded by `kEnableServerAuthConfig`)

`ALokiGameState::ReplicateSubobjects` (LokiGameStateStub.cpp): after the property block, when `PendingToggleRPCUpdates>0`
it hand-builds an RPC content block via the ENGINE_API helpers into a scratch bunch and reuses the S87 11-bit header
splice, then emits it:
```
Driver->NetCache->GetClassNetCache(ULokiServerAuthConfig::StaticClass()) -> GetFromField(func)  // ClassCache + FieldCache
Driver->GetFunctionRepLayout(func)->SendPropertiesForRPC(func, Channel, ParamWriter, {uint8 Toggle; uint8 bValue})
Channel->WriteFieldHeaderAndPayload(FieldWriter, ClassCache, FieldCache, nullptr, ParamWriter)
Channel->WriteContentBlockPayload(ServerAuthConfig, RpcScratch, /*bHasRepLayout=*/false, FieldWriter)
// then splice InjectBits (11) after the GUID + emit into the real Bunch (same mechanism as the property splice)
```
Armed by a PostLogin timer (`-rpccount=N -rpcdelay=S` cmdline → sets `ToggleRPCCount`/`PendingToggleRPCUpdates` + ForceNetUpdate).
Two bugs fixed on the way: (a) the engine's own `ProcessRemoteFunction` write omits the 11-bit field → client
`Read NumPayloadBits FAILED` (hence hand-rolling); (b) `ReplicateSubobjects` early-returned when the empty seed=0
array wrote nothing, so the RPC path never ran — fixed (don't early-return while a broadcast is armed; return
`bWrote||bEmittedRPC`).
- LIVE: toggleseed=0 (array holds), the spliced RPC block reads CLEANLY — client survives 1 and 151 RPCs, 0 errors.
- BUT the component's `GameFeatureToggles` (@+0x130) stays num=0 — the per-toggle setter can't POPULATE an unsized
  array; `GameFeatureToggleDelegates` (@+0x140) is client-init'd to 149. So the RPC delivers but doesn't make toggles ready.

## 3. Readiness = a bit flag (disassembly-proven)

`GetGameFeatureToggleValue`/`GetFeatureTogglesReady` are on `LokiServerAuthConfig`/`LokiGameplayStatics` (tool:
`tools/re/class_props.py`, and a broad object-name sweep found the whole family incl. `PollForFeatureTogglesReady`
on `LokiCharacter`, `WaitForFeatureToggles`, `OnClientGameFeatureTogglesReady__DelegateSignature`). Disassembling
`GetFeatureTogglesReady`'s native thunk (`Func@+0xE0` IS readable — only the S87/S88 content-block RCB code is
anti-tamper-locked):
```
World = WorldContext->GetWorld();  obj = getObj(0x…3c0ac0)(World);  sac = *(obj + 0x5A0);  return bit6(*(sac + 0xB3))
```
Verified LIVE that `LokiGameState + 0x5A0` == its `ServerAuthConfig`. So **readiness (the QUERY) = bit 6 of
[LokiServerAuthConfig + 0xB3]** (an unreflected bool; `class_props` shows only reflected UActorComponent bools there).
`GameFeatureToggles.Num()>0` was the WRONG first hypothesis — sizing the array does nothing.

## 4. The `gft_ready_fix.dll` shim (WORKS)

`tools/sigbypass-mod/gft_ready_fix.cpp` — built `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS gft_ready_fix.cpp -o
gft_ready_fix.dll -lkernel32`. A GUObjectArray-polling shim (reuses ds_hybrid's FName/ForEachObject/SafeReadable
helpers; NO hooks, NO native-call primitive — pure walk + a 1-bit write) that finds every `LokiServerAuthConfig` and
sets bit6 of [+0xB3], re-applying every 2s. Bit-only by default; `-DFILL_VALUES` also fills GameFeatureToggles@+0x130
with 151 trues (off by default — a non-UE buffer would crash if the game frees the array).
- LIVE: `launch-redirect.ps1 -Hook …\gft_ready_fix.dll` (stub on 7777) → shim tracked components 0→11 as they
  spawned, set the bit; independent RPM read = 11/11 bit6 set; client stable. `GetFeatureTogglesReady()` = TRUE.
- Marker: `docs/gft-ready-marker.txt`. Confirmation poke tool (bit + optional array): `tools/re/poke_toggles.py`.

## 5. Drop-in probe (readiness query flipped)

Live DS session (stub 7777, toggleseed=0 rpccount=0, gft_ready_fix.dll) — RPM of live actors: the FULL drop-in world
is instantiated behind the loading overlay:
- Drop UI: `WBP_UI_DropPlane_SpinningDonut/Slices`, `WBP_UI_DropPodIndicator_Animated`, `WBP_UI_DropPodControls`.
- `Comp_GameMode_DropPlane_Tutorial_C` (the drop-plane gamemode component — instantiated on the client).
- The client's own `LokiPlayerController` + full ~60 `Comp_PlayerController_*` suite; in-game HUD widgets; `LokiCursorCharacterAimSubsystem`.
- NO hero pawn (only DefaultPawn/SpectatorPawnMovement; the 474 `LokiCharacterMovementComponent` are the world's minions/bots).

During load, hero-setup queried toggles `AttachAudioListenerToHero` (3064x) + `CursorCharacterAim` (1794x) →
"feature toggles were not ready" spam (~4860x, 19:10:36–19:11:27) WHILE the readiness bit was set, then stopped;
`GameEvent_SpectatorStateChanged_PlayerController` FAILED to broadcast ("Router was not found"). The client then idled
~14 min on the loading screen (only LogMessenger/storefront background polls). Screenshot: stuck on "DROP IN, GEAR UP…
LOADING…".

**Interpretation:** the loading-screen dismissal / hero-setup is gated on the game-feature-toggle READY **EVENT**
(`OnClientGameFeatureTogglesReady`; latents `WaitForFeatureToggles`/`LoopForFeatureTogglesReady`/`PollForFeatureTogglesReady`
await it), NOT on the `GetFeatureTogglesReady` query bit I flipped. So the bit makes the QUERY true but never fires the
EVENT → the wait never completes → the world loads but never reveals. Also note: the getter `ULokiGameFeatureToggles::Get`
(the spam source) has its OWN readiness check, ALSO distinct from the bit (it spammed with the bit set).

⚠ This is a possible REGRESSION from the S70 milestone (which cleared the loading screen into a spectator world WITHOUT
the toggle carrier). The current session (kEnableServerAuthConfig=true + shim) is stuck on loading. Whether the toggle
carrier and/or the shim changed the S70 behavior is exactly what the S90 A/B test resolves (see the S90 handoff).

## Tooling built this session (all present)

- `tools/re/ufunc_params.py` — dump any UFunction's parameter signature via RPM.
- `tools/re/class_props.py` — dump a UClass's full property layout (own + inherited): name/type/Offset_Internal/flags.
- `tools/re/poke_toggles.py <PID> <BASE>` — external RPM proof: set the readiness bit (+ optional array fill) on all LokiServerAuthConfig.
- `tools/re/s87/{decode_payload,sweep_seed,sweep_post,sweep_combo}.py` — S88 content-block payload decoder + robust DS-cycle sweep harness.
- `tools/sigbypass-mod/gft_ready_fix.cpp` + `.dll` — the readiness shim (durable, auto-applies on launch).
- Stub levers (LokiGameStateStub.cpp, guarded by `kEnableServerAuthConfig`): `-injectbits -postbits -paybits -toggleseed -rpccount -rpcdelay`.

## Env at handoff

Flags ON for DS work: `kEnableServerAuthConfig=true` (LokiGameStateStub.h) + `forceTutorialMatch=true` (interactive.go).
Revert BOTH to false to restore the committed baseline (functional main menu + S85c spectator). Stub build:
`Build.bat LokiEditor Win64 Development -Project=…\Loki.uproject` (kill UnrealEditor-Cmd first). ags rebuilds itself on
`launch-redirect`. Full memory: `supervive-dedicated-server-status` (tail = this session). Next: docs/next-session-prompt-s90.md.
