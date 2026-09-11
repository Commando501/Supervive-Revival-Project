# Next-session handoff (S87) — SUPERVIVE dedicated-server tutorial route

Branch `dedicated-server-stub`. Last commit `f1a3534` ("S85-86: DS route — char
field-32 + PlayerState desyncs FIXED ... toggle carrier built + parked").

## 30-second status

The DS route delivers the client into the **live tutorial world** with a
**server-authoritative possessed character whose connection now HOLDS** (S85 fixed
the char field-32 desync; S85 also fixed the PlayerState desync). The client sits
at the pre-drop / "ENTERING THE BREACH" match-transition. The one thing blocking
the client's whole gameplay-feature layer — `ULokiGameFeatureToggles` "not ready"
(112×+) — was deeply RE'd and turns out to be a **replicated** mechanism (not the
round-gated dead-end feared). The carrier mirror is **built + boot-verified +
reaches the client**, but is **parked** at a UE 5.4 package-map wall. That fix is
the immediate task.

## THE IMMEDIATE TASK: land the game-feature-toggle carrier

**Goal:** make the client's `LokiServerAuthConfig` component receive its replicated
`GameFeatureToggles` array so `OnRep_GameFeatureToggles` fires → toggles ready → the
"not ready" spam stops → the client progresses past the transition.

**What's built** (all behind `kEnableServerAuthConfig` in `LokiGameStateStub.h`,
default **false** = S85c spectator baseline; flip **true** to work on this):
- `unreal-stub/Source/Loki/LokiServerAuthConfigStub.{h,cpp}` — `ULokiServerAuthConfig
  : UActorComponent` (`/Script/Loki.LokiServerAuthConfig`), 1 rep `TArray<bool>
  GameFeatureToggles` (151) + empty `MulticastSetGameFeatureToggle`; ctor calls
  `SetNetAddressable()`; boot-log diagnostic prints `IsNameStableForNetworking`.
- `LokiGameStateStub` ctor `CreateDefaultSubobject<ULokiServerAuthConfig>("ServerAuthConfig")`;
  `BeginPlay` seeds 151 `true`.
- `Loki.cpp` boot-dumps the component net-cache (verified: ActorComponent 2 reps +
  LokiServerAuthConfig 1 rep + 1 func — client-matched).

**Confirmed facts — DO NOT re-derive (docs/session-85 §11–§14):**
- Server `IsNameStableForNetworking(ServerAuthConfig)=1` (SetNetAddressable took;
  the content-block stable branch, DataChannel.cpp:4460, is correct).
- UE 5.4 registered-subobject-list default is FALSE (GDefaultUseSubObjectReplication
  List, ActorComponent.cpp:98) → the stub uses the legacy ReplicateSubobjects path.
- The client HAS the subobject (Default__LokiGameState creates a "ServerAuthConfig"
  default subobject → every live LokiGameState replica has one; it matches by name).
- `GameFeatureToggles` is a native `TArray<bool>` on both sides (ElementSize 1,
  FieldMask 0xFF) — element type is NOT the bug.
- `ULokiGameFeatureToggles::Get` is a static C++ accessor (no reflected UClass);
  `ELokiGameFeatureToggle` = 151 values.

**The wall (root cause):** the package-map `Bunch << Obj` (DataChannel.cpp:4454,
runs BEFORE the stable bit) exports the component as a **dynamic object** because
`IsFullNameStableForNetworking()` is false (its outer, the runtime-spawned
GameState, is dynamic). The dynamic export needs the component's CLASS NetGUID,
which returns **NOT_IN_CACHE** on the client → the read cursor desyncs before the
stable bit → `ReceiveProperties FAILED: LokiServerAuthConfig` → ConnectionLost.

**Next-session plan (ranked):**
1. **Instrument the NetGUID directly** (grep-of-verbose-log failed — NetGUIDs are
   numeric). Add a stub log of `Connection->PackageMap->GetNetGUIDFromObject(ServerAuthConfig)`
   (or hook the first replicate) to get the subobject's NetGUID NUMBER + the CLASS
   NetGUID number; then grep BOTH verbose logs (`-LogCmds="LogNetPackageMap Verbose"`)
   for those numbers to see the export bytes and where the class miss happens.
2. **Force-export the class GUID early.** If the class `/Script/Loki.LokiServerAuthConfig`
   NetGUID is what misses, pre-export/register it into the guid cache before the
   subobject replicates (and verify the stub's class-net-cache suppression /
   `LokiNetDriver::IsClassNetCacheDivergent` isn't stripping it).
3. **Research whether readiness is GLOBAL vs per-component.** If `Get()` reads a
   global/subsystem/PC state (Ghidra: `SUPERVIVE-deobf.exe` in `dumps/toggles/`,
   loadable in the saved Ghidra project — see below), then a **map-placed
   stably-named** carrier actor becomes viable (stable full-name NetGUID, no dynamic
   outer) — but that needs an IoStore/map edit, a separate effort.

**Reality check:** replicating a component subobject of a dynamic mirror actor is a
capability NO prior stub mirror needed (S70/S71/S73 = actor-level props only). If the
NetGUID export can't be made to resolve, the honest ceiling may be that toggles need
a map-placed carrier or stay unsolved — but the possession + world view already work.

## Environment / how to run

Elevated PowerShell, **Steam running first** (else Auth Failure 14005). ags may
already be up (loopback backend). To exercise the DS route:
1. Flip `forceTutorialMatch = true` in `server/internal/interactive/interactive.go`
   (committed default is false = functional main menu).
2. Flip `kEnableServerAuthConfig = true` in `LokiGameStateStub.h` (to test the carrier).
3. Build the stub (~2–8 min; kill `UnrealEditor-Cmd` first — LNK1104 otherwise):
   `& 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' LokiEditor Win64 Development -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" -WarningsAsErrors`
4. Start the stub on 7777 (⚠ `-abslog` MUST be absolute + SPACE-FREE or it's silently ignored):
   `Start-Process 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"','/Engine/Maps/Entry?listen','-game','-server','-Port=7777','-nullrhi','-NoSplash','-Unattended','-abslog=C:\Temp\Ds.log' -WindowStyle Hidden`
   (add `'-LogCmds=LogNetPackageMap Verbose'` for net tracing). Confirm bind via
   `Get-NetUDPEndpoint -LocalPort 7777`, NOT by finding a log.
5. Launch the client: `.\configs\launch-redirect.ps1 -NoHook` (read-only; it rebuilds
   ags armed + launches the game). The launcher returns early while the game runs on.
6. Client log: `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (fresh per
   launch). Client PID/base for RPM tools: `$g=Get-Process SUPERVIVE-Win64-Shipping;
   "{0} 0x{1:X}" -f $g.Id,[int64]$g.MainModule.BaseAddress`.

**Verify possession still holds (baseline, both flags false is fine for this):** the
client reaches `Entering game state LokiGameState_<n>`, no `ConnectionTimeout`, and
`tools/re/obj_by_class.py <PID> <BASE> LokiMinionCharacter` shows a live replica.

## Key RE tools + artifacts

- `tools/re/netcache_chain.py <PID> <BASE> <ClassName>` — the index-space walker +
  auto-diff (the S85 workhorse; also `find_uclass.py`, `rep_expand_class.py`,
  `obj_by_class.py`, `class_props.py`, `netfields_dump.py`).
- `scratchpad/authcfg_probe.py`, `scratchpad/gft_inner.py` — the component/array probes.
- **Ghidra** (12.1.2, `C:\Users\eastr\Downloads\ghidra_12.1.2_PUBLIC_...`): saved project
  `Ghidra/SuperVive.gpr` (git-ignored, 1.4GB) over `dumps/toggles/SUPERVIVE-deobf.exe`
  (IAT rebuilt). Pull decompilation HEADLESS: `analyzeHeadless <projDir> SuperVive
  -process -noanalysis -scriptPath tools/ghidra_scripts -postScript <Script>.java`
  (⚠ felix flakes on the JDK-25-only box; move `%APPDATA%\ghidra\...\osgi` aside + retry).

## Docs + memory to read first

- `docs/session-85-netcache-chain-diff.md` — the full S85/S86 trail (§1 netcache tool,
  §6 char fix, §7 PlayerState fix, §10 toggle mechanism, §11 mirror scope, §12-§14 the
  carrier build + the package-map wall + the next-session plan). **Read §14 first.**
- Memory `supervive-dedicated-server-status` — the running DS-route record (the tail
  has S84/S85/S86). Also `supervive-tutorial-launch-status`, `supervive-cheat-surface-inventory`.

## The broader frontier (after toggles)

Even with toggles, the deep ceiling is the SERVER-AUTHORITATIVE round: drop-in, and
a real hero. But a controllable server-possessed character in the live tutorial world
is now close — the open threads (docs/session-85 §8) are: (B) GAS attributes are
unreplicated server-side (S80 GetMaxSpeed 0) so measure whether the possessed pawn
MOVES; the client's CMC is already generating movement saved-moves. (C) drop-in /
round-start stays server-authoritative.
