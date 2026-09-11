# Next-session handoff (S90) — A/B the loading-screen wall: does the toggle carrier / readiness shim change the S70 clear?

Branch `dedicated-server-stub`. Continues S89 (docs/session-89-rpc-route-readiness-shim.md). S89 ended with a
sharp open question: with the game-feature-toggle readiness QUERY flipped, the DS client **loads the entire drop-in
world** (drop-plane/drop-pod UI, HUD, LokiPlayerController + full component suite, `Comp_GameMode_DropPlane_Tutorial`)
but is **STUCK on the "DROP IN, GEAR UP… LOADING…" screen** — the world loads but never reveals. This is a possible
regression from the S70 milestone (which cleared the loading screen into a spectator world WITHOUT the toggle carrier).

---

## PASTE-ABLE OPENING PROMPT (for the fresh session)

> Continue the SUPERVIVE dedicated-server work on branch `dedicated-server-stub`. Read first, in order:
> (1) `docs/next-session-prompt-s90.md` (this file), (2) `docs/session-89-rpc-route-readiness-shim.md` §5 "Drop-in
> probe", (3) memory `supervive-dedicated-server-status` (tail = S89).
>
> Task: an A/B controlled test to explain why the DS client is STUCK on the "DROP IN, GEAR UP… LOADING…" screen even
> though it loads the full drop-in world behind the overlay (S89 §5). Isolate whether the toggle carrier
> (`kEnableServerAuthConfig=true`, the ServerAuthConfig subobject replication) and/or the `gft_ready_fix.dll`
> readiness shim changed the S70 loading-screen-clear behavior, by running three single-variable configs and
> comparing whether the loading screen clears into a spectator/drop-select world:
>   A. pure S70 baseline — `kEnableServerAuthConfig=false`, launch `-NoHook` (no shim).
>   B1. carrier, no shim — `kEnableServerAuthConfig=true`, launch `-NoHook`.
>   B2. carrier + shim — `kEnableServerAuthConfig=true`, launch `-Hook …\gft_ready_fix.dll` (= the current stuck state).
> A vs B1 isolates the subobject carrier; B1 vs B2 isolates the shim. For each, observe: the loading screen
> (screenshot — the game window is on monitor "MAG 325CQF (2)"), the client log ("Entering game state LokiGameState",
> "were not ready" spam count, spectator markers, "Router was not found"), and the live drop-UI/spectator actors via
> RPM. Confirmed facts + recipe + tooling are in the handoff — don't re-derive (don't re-open the RPC route, the
> readiness-bit RE, or the S88 array wall).
>
> Env: elevated PS, Steam first. Revert to baseline when done.

---

## 30-second status

- S89 DELIVERED: RPC signature RE'd; RPC content-block delivery works at the wire level (sidesteps the S88 array
  wall) but can't populate the array; readiness is a BIT (`bit6 of [LokiServerAuthConfig+0xB3]`, disassembly-proven,
  NOT array Num); `gft_ready_fix.dll` shim flips that bit automatically on launch (11/11 verified).
- OPEN (the S90 task): the readiness BIT ≠ the readiness EVENT. The client loads the full drop-in world but the
  loading overlay never lifts, gated on `OnClientGameFeatureTogglesReady` (latents `WaitForFeatureToggles` /
  `LoopForFeatureTogglesReady` / `PollForFeatureTogglesReady`), which the bit doesn't fire. Possible regression vs S70.

## THE TASK — the A/B (three single-variable configs)

Goal: fill this matrix (loading screen CLEARS into a world vs STAYS stuck), then read the interpretation.

| config | kEnableServerAuthConfig | shim | expectation to test |
|---|---|---|---|
| **A** (pure S70) | **false** | none (`-NoHook`) | per S70, loading clears → spectator world |
| **B1** (carrier) | **true** | none (`-NoHook`) | isolates the subobject carrier's effect |
| **B2** (carrier+shim) | **true** | `-Hook gft_ready_fix.dll` | = current stuck state |

Per-config recipe (elevated PS, Steam running first — else Auth Failure 14005):
1. Set `kEnableServerAuthConfig` (LokiGameStateStub.h) for the config; keep `forceTutorialMatch=true` (interactive.go).
2. Rebuild the stub ONLY when `kEnableServerAuthConfig` changed (config A needs a rebuild; B1→B2 does not):
   `cmd /c '"H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat" LokiEditor Win64 Development -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" -WarningsAsErrors > C:\Temp\build.log 2>&1'` (kill UnrealEditor-Cmd first; ~5-20s; exit 0).
3. Kill `SUPERVIVE-Win64-Shipping` + `UnrealEditor-Cmd`; delete the client log + `docs/gft-ready-marker.txt`.
4. Start the stub on 7777:
   `Start-Process 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"','/Engine/Maps/Entry?listen','-game','-server','-Port=7777','-nullrhi','-NoSplash','-Unattended','-toggleseed=0','-rpccount=0','-abslog=C:\Temp\DsAB.log' -WindowStyle Hidden` — confirm bind via `Get-NetUDPEndpoint -LocalPort 7777`.
5. Launch the client: `configs\launch-redirect.ps1 -NoHook` (A, B1) OR `-Hook "G:\git\Supervive Revival Project\tools\sigbypass-mod\gft_ready_fix.dll"` (B2). Returns early; connect ~60-90s.
6. Wait ~2-3 min, then OBSERVE (below). RELAUNCH the game per config (the client doesn't auto-re-arm after a DS retry).

Observables per config (client log = `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`, fresh per launch):
- **Screenshot** (the decisive signal): the game window is on monitor **"MAG 325CQF (2)"**. computer-use:
  `request_access ["supervive-win64-shipping.exe"]` → `switch_display "MAG 325CQF (2)"` → `screenshot`. Stuck =
  "DROP IN, GEAR UP… LOADING…"; cleared = the tutorial world / a drop-select / spectator cam.
- **Log greps**: `Entering game state LokiGameState` (world loaded); count `were not ready` (toggle spam); spectator
  markers (`SpectatorStateChanged`, `Router was not found`, `TryUIReady`); any world-reveal / `StopLoadingScreen` /
  `remove.*loading`.
- **RPM** (PID/base via `$g=Get-Process SUPERVIVE-Win64-Shipping; "{0} 0x{1:X}" -f $g.Id,[int64]$g.MainModule.BaseAddress`):
  `tools/re/obj_by_class.py <PID> <BASE> DropPlane` / `SpectatorPawn` / `LokiCharacter` — did the drop UI / a
  spectator pawn spawn?

Interpretation:
- **A clears, B1 & B2 stuck** ⇒ the subobject carrier (`kEnableServerAuthConfig=true`) regressed the S70 clear →
  fix the carrier (or deliver toggles without the subobject) rather than chasing the event.
- **A & B1 clear, B2 stuck** ⇒ the `gft_ready_fix.dll` shim regressed it (setting bit6 prematurely breaks the
  reveal) → the shim is harmful; back off the bit and chase the readiness EVENT instead.
- **A also stuck** ⇒ the S70 loading-screen clear does NOT reproduce on the current build/config; the stuck-loading
  is the true baseline and the toggle work is orthogonal → pivot to firing `OnClientGameFeatureTogglesReady`
  (option #1: RE what `PollForFeatureTogglesReady` on `LokiCharacter` checks + fire the event).

## Confirmed facts — DO NOT re-derive (docs/session-89)

- Readiness QUERY = bit6 of [LokiServerAuthConfig+0xB3]; `GameState+0x5A0` = its ServerAuthConfig (live-verified).
  The `gft_ready_fix.dll` shim sets it (11/11). `GameFeatureToggles.Num()>0` is NOT the readiness (wrong first hypothesis).
- The RPC route (hand-rolled + 11-bit spliced content block) reads cleanly (survives 1 & 151 RPCs) but can't POPULATE
  the array — don't re-run that. The S88 property array is a client-side deserialization wall — don't re-open.
- The loading-screen/hero-setup waits on the readiness EVENT (`OnClientGameFeatureTogglesReady`), NOT the query bit;
  the getter `ULokiGameFeatureToggles::Get` has its OWN readiness check (the spam), also distinct from the bit.
- `GetFeatureTogglesReady`'s native thunk IS readable (disasm OK); only the S87/S88 content-block RCB code is anti-tamper-locked.

## Tooling inventory (all present)

- `tools/re/ufunc_params.py` (UFunction sig), `tools/re/class_props.py` (UClass property layout), `tools/re/poke_toggles.py`
  (RPM set-bit + array fill), `tools/re/{obj_by_class,find_uclass,netfields_dump}.py` (instance/class/net-field dumps),
  capstone-via-RPM disasm one-liners (see session-89 §3 for the pattern).
- `tools/sigbypass-mod/gft_ready_fix.cpp`/`.dll` — the readiness shim (built; `-DFILL_VALUES` opt-in for array fill).
- Stub levers behind `kEnableServerAuthConfig`: `-injectbits -postbits -paybits -toggleseed -rpccount -rpcdelay`.

## Revert to baseline when done

`kEnableServerAuthConfig=false` (LokiGameStateStub.h) + `forceTutorialMatch=false` (interactive.go) + rebuild the stub
restore the committed baseline (functional main menu + S85c spectator). Kill `SUPERVIVE-Win64-Shipping`,
`UnrealEditor-Cmd`, `ags`. (Config A already sets `kEnableServerAuthConfig=false`; just add `forceTutorialMatch=false`.)

## Env at handoff

All DS processes STOPPED. Flags currently ON (`kEnableServerAuthConfig=true`, `forceTutorialMatch=true`). `gft_ready_fix.dll`
built. Stub source has all S89 changes (rebuild before first run). Fresh session should start from config A (set
`kEnableServerAuthConfig=false`, rebuild, run).
