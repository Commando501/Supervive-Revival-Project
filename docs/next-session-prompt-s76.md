# Next session (S76) — PIVOT to the DS route: complete client possession + the deploy layer

## Why we pivoted (S75 conclusion)
The client-side **force-open** route is EXHAUSTED (full story: `docs/session-75-summary.md`). What S75
proved on the force-open hero:
- **WASD movement DOES work** via a velocity puppet (poke CMC `Velocity`@+0xE8 each frame → the hero
  moves with collision). `tutorial_launch.cpp` RM_PUPPET. The earlier "CMC is dormant" reading was a
  confound — the hero was under the map (bad spawn spot).
- **BUT real movement engages deploy-gated subsystems (mantle / feature toggles) that crash.** The
  root is **feature-toggle readiness**: `ULokiGameFeatureToggles::Get` (=0x7FF6BAACB6DE) gates on
  `byte[D+0xB3] bit6` (D = per-object config, class `LokiServerAuthConfig`) + a C-null check.
  - Hooking Get to set the bit is **packer-blocked** (the Get region is tamper-protected — record-only
    hook still crashed).
  - Pure-RPM poke of the readiness bit **works and is safe** — it fixed `LokiServerAuthConfig`
    (stopped the DeadSpectatorCameraLock spam) — but the remaining toggles need **deploy-time config
    WIRING** (null `[PersistentLevel+0x258]`) across subsystems, and the objects can't be enumerated
    (the hook that would is packer-blocked). = replicating deploy. Dead end client-side.

So: the force-open route can spawn/possess/aim/jump/**move (puppet)** a hero, but a genuinely playable,
non-crashing tutorial needs the **server-side deploy** (round-start → feature-toggle init → drop-in).

## Where the DS route is ([[supervive-dedicated-server-status]], S70–S74)
The dedicated-server stub (`unreal-stub/`, branch `dedicated-server-stub`) has climbed far:
- **S70:** client leaves the loading screen into the LIVE tutorial world with a real replicated
  `ALokiGameState` (mirror `LokiGameStateStub.{h,cpp}`). Stable spectator-in-world. ★ milestone.
- **S73:** the S41/S71/S72 "client needs a Loki PC" wall is **BROKEN** — `LokiPlayerControllerStub.{h,cpp}`
  mirrors `ALokiPlayerController` (by-path bind) with the net-cache reconstructed (60 same-named net
  UFUNCTION stubs via `gen_lokipc_rpcs.py` + the `LokiPlayerCheats` rep) so `TryGetLocalLokiController`
  succeeds and the FClassNetCache index space aligns index-for-index. Server-side possession done.
- **S74:** the content-overlay AND "real exe as server" routes are **CLOSED** (no Server-target binary
  ships; overlay needs the native round code that isn't in the paks). So the deploy layer must be
  RECONSTRUCTED in the stub (native mirrors), not obtained.

## The DS frontier = the SAME deploy layer S75 hit, but reconstructable server-side
The remaining DS work (from S73/S74 NEXT lists) is exactly the layer force-open can't fake:
1. **`LokiPlayerState` by-path mirror** (client PlayerState is still stock `APlayerState`; the real one
   is `LokiPlayerState`). Same S70/S73 mirror pattern (rep_expand_class.py → member-wise, non-push,
   register base props by name).
2. **Complete client-side possession** of the replicated pawn (server possession is done; the client's
   drop-in/hero-assignment flow needs to engage — see S74's drop-in RE).
3. **Feature-toggle init + round drop-in** — the deploy layer. ★ S75 GIVES YOU THE TARGET: "ready" =
   `LokiServerAuthConfig::byte[+0xB3] bit6` set + the config pointers WIRED (e.g. `[Level+0x258]`).
   On the DS the SERVER owns this — reconstruct `ALokiRoundGameMode`'s phase-advance
   (EGP_ServerStartup→…→SpawnSelect→Combat) + the feature-toggle set application in the stub gamemode,
   OR replicate a ready state. This is the true frontier and it's LARGE (native round logic), but it's
   the honest path to a playable hero.

## S75 reusable assets (if a HYBRID is chosen — DS session + client shim)
The DS route gives the client a valid server session + live world; a client shim could do the parts the
server can't easily drive:
- **Velocity puppet** (`RM_PUPPET`, `tutorial_launch_puppet.dll`) → WASD movement, IF the mantle/toggle
  crash is first resolved (which the DS's real feature-toggle init would fix).
- **Pure-RPM toggle poke** (`toggle_d_scan.py` / `resolve_obj_d.py`) → set `LokiServerAuthConfig`
  readiness bits (safe, no injection). Partial, but proven.
- **S75 RE map** of the movement + feature-toggle internals (addresses/offsets in session-75-summary.md).

## Recipe (DS route; elevated PS, Steam up)
1. Stub-first: `Build.bat LokiEditor Win64 Development -Project=…\Loki.uproject` (~240s; kill any running
   `UnrealEditor-Cmd` first — LNK1104), then run
   `UnrealEditor-Cmd.exe …\Loki.uproject /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi
   -NoSplash -Unattended -abslog=<log>` (wait "listening on port 7777").
2. Client: `configs\launch-redirect.ps1 -NoHook` (ags `forceTutorialMatch=true`, ConnectionDetails.address
   `127.0.0.1:7777`; stub `ModifyClientTravelLevelURL`→LVL_Tutorial). Client auto-arms the match (~1min).
3. Watch client Loki.log for `Entering game state` (S70), `LokiPlayerController_<n>` +
   `TryGetLocalLokiController` (S73), then the next mirror's "Invalid replicated field N" (scopes the work).
- base `0x7FF6B54F0000` stable across relaunches; heap VAs per-launch. RE tools: rep_expand_class.py,
  find_uclass.py, netfields_dump.py, gen_lokipc_rpcs.py, obj_by_class.py, class_funcs.py, class_props.py.

## Honest framing
Both routes converge on SUPERVIVE's server-authoritative **deploy layer** (round-start / feature-toggle
init / drop-in). Force-open can't reach it (packer + client-only). The DS route can HOST it — but the
layer is native server code we must reconstruct in the stub (the Server-target binary isn't shipped).
The reasonable-effort ceiling banked so far is **spectator-in-the-live-tutorial-world with a Loki-typed
PC**; a controllable, moving hero is the next large milestone, gated on reconstructing the deploy layer.
