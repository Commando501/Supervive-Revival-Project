# Next session (S78) — DS route: POLISH the moving spectator fly-cam (work through every refinement)

## Where we are (DONE — start here, don't re-derive)
S77 achieved the goal: **a controllable, smooth moving spectator camera over the live SUPERVIVE tutorial world**,
via the dedicated-server-stub (DS) route, dodging the game's anti-tamper. Everything is committed on branch
`dedicated-server-stub` (through commit `f7a168d`). **Read `docs/session-77-spectator-view-possession-falsified.md`
first** (the full story + the refinement list + the reproduce recipe), plus memory `supervive-dedicated-server-status`.

The hard problems are SOLVED (no walls remain — S78 is pure polish):
- **Anti-tamper identified + DODGED.** It's `preloader.dll` (26 KB, unpacked, statically analyzable) + the packed
  exe's code-integrity check — NOT a commercial anti-cheat. The trigger was a PERSISTENT `.text` hook. The dodge:
  no standing `.text` mod (one-shot overlay-hide → uninstall; transient-per-step movement where the `.text` patch
  exists only ~µs/step). Survives long-term (6.6 min + verified).
- **Movement is NOT separately gated** (a single injected `K2_SetActorLocation` teleport survived 2.5 min).
- **The camera follows the `DefaultPawn`** (stub's server-possessed pawn), NOT `PC->SpectatorPawn` — found via
  `ProbeCamera` (`PlayerCameraManager+0x420`). Retargeting the move to the DefaultPawn makes the VIEW FLY.
- **Smoothness:** `SafeWriteFast` (suspend/check ONLY the game thread, not all ~135) made movement ~10x smoother.

The shim: `tools/sigbypass-mod/ds_hybrid.cpp`, `kMode=MODE_SPECTATOR_CAM`, `kEnableTranslation=false` (the worker's
transient-per-step loop is the mover; the per-tick standing-hook movement stays OFF — a standing hook gets caught).

## S78 GOAL: work through every refinement (all polish, no new walls)
Prioritized (the doc has more detail):

1. **★ Mouse-relative steering (biggest UX gap).** Movement is world-axis, steered by the ARROW keys (which rotate
   `g_spYaw2`), NOT the mouse view — disorienting. FIX: read the client's view YAW and set `g_spYaw2 = viewYaw` each
   step so W = "forward" relative to where the user looks. The yaw is a NATIVE FRotator (not a UPROPERTY):
   `AController::ControlRotation` on the PC, or the `PlayerCameraManager` POV.Rotation. RE the offset — extend
   `ProbeCamera` to log candidate FRotators (3 consecutive floats, |val|<360) in the PC/camera-manager that CHANGE
   as the user rotates the mouse; pin the yaw offset; read it in the movement loop.

2. **★ Data/VTABLE hook (durable — removes the jaggedness AND the transient overhead).** The transient-per-step
   toggle degrades when far/high from the map (whole map visible → ProcessInternal hotter → the game-thread
   "unsafe" check hits more → toggle slows to jagged). The durable fix: per-frame game-thread exec WITHOUT a `.text`
   patch — swap a per-frame-ticked object's vtable POINTER (heap field @+0) to a heap vtable copy whose Tick slot is
   our stub. Pure heap mod → no `.text`, no thread-suspend, continuous + smooth. Needs the per-frame vtable slot
   index RE'd (candidate: `APlayerCameraManager::UpdateCamera`, or the PC/pawn TickActor). This replaces the whole
   transient-per-step mechanism. (Risk to check: does the protection validate object vtable pointers? Probably not —
   it's a user-mode integrity check on `.text`, which a heap vtable doesn't touch.)

3. **Start height / speed feel.** Camera sits above the DefaultPawn (elevated drop-select start); holding up rockets
   into the skybox (which triggers #2's jaggedness). Tune the seed / speed / add a soft Z clamp. Current: sp=90
   horiz, 55 vert.

4. **Overlay-hide / inject-timing robustness.** The census needs widgets spawned: the shim self-waits 12s and you
   should inject at up≥35s. A too-early inject gets 0-87 widgets (vs 3438) and hides 0/N → overlay stays. Consider
   polling the widget count until it's high instead of a fixed 12s delay.

5. **Optional:** compare view-target choices (DefaultPawn vs override the camera POV Location directly each step);
   confirm the DefaultPawn move never gets replication-corrected over long sessions (so far it sticks — the static
   server pawn doesn't re-replicate its position).

## Recipe to reproduce the CURRENT moving spectator (elevated PS, Steam UP first — else Auth Failure 14005)
1. ags `server/internal/interactive/interactive.go` `ConnectionDetails.address="127.0.0.1:7777"`,
   `forceTutorialMatch=true` (already the on-disk value).
2. Build stub (KILL `UnrealEditor-Cmd` first — LNK1104): `& "H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat"
   LokiEditor Win64 Development -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" -WarningsAsErrors`.
   Start: `UnrealEditor-Cmd.exe "…\Loki.uproject" /Engine/Maps/Entry?listen -game -server -Port=7777 -nullrhi
   -NoSplash -Unattended -abslog=<log>` → wait "IpNetDriver listening on port 7777" + "swapped WorldSettings ->
   ALokiWorldSettings".
3. Client: `configs\launch-redirect.ps1 -NoHook` (rebuilds ags+certs; returns EARLY via Steam relaunch — find the
   live pid via `Get-Process SUPERVIVE-Win64-Shipping` sorted by StartTime).
4. Wait until the live client is up ≥35s (widgets+camera spawned), then inject:
   `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\ds_hybrid.dll`.
5. The shim: self-waits 12s → reveals the world (one-shot overlay-hide) → ~20s later uninstalls the hook →
   `[move] transient-per-step movement loop LIVE`. Focus the SUPERVIVE window, WASD to fly (arrows steer,
   Space/Ctrl up/down). Marker: `docs/ds-hybrid-marker.txt` (`[SPEC] RETARGET`, `[move] alive steps=N pos=…`).
6. Build the shim after edits: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS ds_hybrid.cpp -o ds_hybrid.dll
   -lkernel32 -luser32` from `tools/sigbypass-mod/`. Can't double-inject → close the client + relaunch per iteration.

## ★ GOTCHAS (will waste time if forgotten)
- **Windows Defender flags `tools/inject/inject.exe` as PUP** and blocks/quarantines it. FIX (user must do — it's a
  security-settings change): add a Defender FOLDER EXCLUSION for `tools\inject\`. If quarantined, rebuild:
  `& "$env:ProgramFiles\Go\bin\go.exe" build -o inject.exe .` from `tools/inject/`.
- **The anti-tamper catches a PERSISTENT `.text` hook** (variable timing, seconds-to-minutes). NEVER hold the
  ProcessInternal hook standing during movement — use the transient-per-step (µs/step) or a data/vtable hook.
  Confirm any crash via `parse_minidump.py` (0x8 + unmapped-execute at the fixed poison addr 0x7FF90E000001 =
  the anti-tamper deliberate crash; the messy caller frame is wiped).
- **In-match anti-tamper blocks external RPM** (Python ctypes) — drive/inspect via the in-process shim + markers,
  not external pokes. `inject.exe`/`usmapdump` (C, SeDebugPrivilege) still work.
- **Inject at up≥35s** so the camera + widgets are spawned (a too-early resolve gets cam=0x0 / 0 widgets).
- **Steam-relaunch pid confusion:** `launch-redirect.ps1` returns early; the real game runs under a NEW pid.
- **Base `0x7FF6B54F0000`-ish is per-launch (ASLR); resolve everything by class/reflection, not hardcoded VAs.**
- The stub was left running at handoff (`UnrealEditor-Cmd` on 7777); kill it before rebuilding the stub.

## Honest framing
S77 turned "we have no choice but to break the anti-tamper" into a working, smooth, controllable fly-cam over the
live tutorial world — the DS route's furthest point by far. S78 is pure polish (mouse-relative steering, the vtable
hook for smoothness, feel tuning). No walls remain; each item is a bounded, self-contained build.
