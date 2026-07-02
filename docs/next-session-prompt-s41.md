# Session 41 pickup prompt — Path B-lite (schema-inject PC + un-suppress)

Repo: `G:\git\Supervive Revival Project` — branch `dedicated-server-stub`.
Read these first, in order:

1. `CLAUDE.md` — project rules, launch procedure gotchas, DO-NOT list
2. `docs/session-40-path-A1-VERIFIED.txt` — the DEFINITIVE Path A1
   verification: the crash class is a UE 5.4 D3D12 RHI class (vtable
   at exe RVA `+0x7B9E188`), confirmed by head-to-head register comparison
   against the anti-cheat fail-fast signature. **This is ground truth.**
3. `docs/session-40-D3D12-CONFIRMED.txt` — full D3D12 identification chain
   (call stack shows ~10 D3D12Core.dll frames interleaved with SUPERVIVE)
4. `docs/session-40-raytracing-cvar-blocked.txt` — anti-cheat wall on
   cmdline AND `r.RayTracing` CVar; ruled out all user-space renderer
   workarounds
5. `docs/session-40-path-b-lite-analysis.txt` — full B-lite scoping
   (mechanics of `FClassNetCache`, ~8-15 hour engineering estimate,
   three variants: full, RPCs-only, empty-block)
6. `docs/session-22-schema-actor-loki-mods.txt` — SUPERVIVE's AActor
   schema dump (103 properties; ~18 Loki additions vs stock UE 5.4).
   Session 22 didn't emit `CPF_Net` flags, so we can only guess which
   Loki additions are replicated.
7. `docs/dedicated-server-stub.md` — jump to Session 38 → 39 chapters
   at the bottom for the full "route-around fires + suppression works
   + client reaches menu + crash mid-menu-load" chain

Auto-loaded memories:
- `supervive-hero-roster-blocker.md` — session-40 entry now on top with
  full identification + anti-cheat wall summary
- `supervive-rpc-signature-solved.md` — session 32's schema-injection
  pattern for `ServerVerifyViewTarget`. **Same primitives extend to
  UClass property injection for B-lite.**

## Chapter state going in

**What sessions 34-38 achieved:**
- Route-around fires cleanly (skip stock UE's `ReceivePropertiesForRPC`)
- Full `ShouldReplicateActor` + `ShouldReplicateFunction` suppression on
  the session-20 divergent-class set: PC, HUD, GameStateBase, PlayerState,
  DefaultPawn, SpectatorPawn, WorldSettings, GameplayDebuggerCategoryReplicator
- Connection stable through Join for 64s

**What session 39 revealed:**
- Client reaches menu, fetches 25 heroes + inventory + wallet via ags
  Messenger (WebSocket)
- Crashes at 64s post-Join with `EXCEPTION_ACCESS_VIOLATION writing 0x7ff68a55b368`
  at exe `+0x2976FF0` (a `TArray::Add` last instruction: `mov [rcx+8*rsi], rax`)

**What session 40 confirmed:**
- Crash class vtable at RVA `+0x7B9E188` — UE 5.4 D3D12 RHI class
  (very likely `FD3D12CommandContext` or `FD3D12CommandList` descendant;
  15,504-byte object; multi-inheritance; parent = 232-byte `FD3D12CommandList`
  vtable at `+0x7B9DE88`)
- The uninit-TArray victim is a 0x160-byte slot-parent instance (vtable
  `+0x7B9DC48`) with `count=1, capacity=4` but `Data` still pointing at
  `.rdata` const default. Some earlier init step was skipped.
- Anti-cheat blocks all renderer/subsystem cmdline flags (`-DX11`, `-vulkan`,
  `-nullrhi`, `-noraytracing`) AND `r.RayTracing` CVar changes. Any cmdline
  or CVar workaround is dead.
- Ghidra 12.1.2 + JDK 21 installed at `E:\Tools\{ghidra,jdk-21}` and the
  runtime-overlay Ghidra project persists at
  `C:\Users\eastr\Documents\GhidraProjects\SUPERVIVE`.

**What's left:**
- Session 41's task = **Path B-lite** — schema-inject `APlayerController`
  with SUPERVIVE's expected replicated fields, un-suppress PC from
  `IsClassNetCacheDivergent()`, test whether proper PC replication fixes
  the init sequence that leaves the D3D12 class's slot-parent TArray in
  a bad state.

## The task: Path B-lite implementation

Scope per `docs/session-40-path-b-lite-analysis.txt`:

1. **Identify SUPERVIVE's replicated AActor / APlayerController fields.**
   Session 22's dump has property NAMES + TYPES but doesn't distinguish
   `CPF_Net`. Options:
   - Extend `usmapdump.exe extract` to emit `CPF_*` flags (in
     `tools/usmapdump/extract.go` — look for the property-walk that
     writes property type). Small feature addition.
   - Or: read the SUPERVIVE `.usmap` file (session 22 discovered its
     path) and parse it directly for `CPF_Net`.
   - Fallback: incrementally inject the LIKELY-replicated Loki additions
     from session 22's dump (`ServerState`, `LokiReplicationStrategy` are
     the strong candidates by naming convention).

2. **Extend the sessions 27-32 injection primitives from UFunction
   ChildProperties to UClass ClassReps.** Current primitives live in
   `unreal-stub/Source/Loki/Loki.cpp`:
   - `AppendStringParam`, `AppendBoolParam`, `AppendIntParam`,
     `AppendFloatParam`, `AppendByteParam`, `AppendObjectParam`,
     `AppendUInt32Param`, `AppendUInt8ArrayParam`, `AppendStructParam`,
     `AppendVectorParam`, `AppendRotatorParam`
   - All append to `Func->ChildProperties`
   - For B-lite: need parallel `AppendReplicatedPropertyToClass(UClass*, FProperty*)`
     that also updates `Class->ClassReps` and sets `Prop->RepIndex`
   - See `H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\CoreUObject\Private\UObject\Class.cpp`
     `SetUpRuntimeReplicationData()` for the reference build order (native
     classes preserve declaration order; blueprint classes sort by
     memory offset)
   - See `H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\CoreUObject\Private\UObject\CoreNet.cpp`
     `FClassNetCacheMgr::GetClassNetCache` for how NetIndex is
     computed from ClassReps

3. **Handle struct properties (`LokiReplicationStrategy`, `PoolableActorServerState`).**
   `AppendStructParam` already exists but takes a `UScriptStruct` path;
   requires the struct to be registered server-side. Two paths:
   - Register a matching `UScriptStruct` on the stub side (needs UHT'd
     mirror of SUPERVIVE's struct layout)
   - Or use runtime `UScriptStruct` construction (analogous to sessions
     27-32's UFunction construction)

4. **Invalidate the cached `FClassNetCache` after injection.**
   Session 27 used `PCClass->ClearFunctionMapsCaches()` for UFunctions.
   For ClassReps, need `NetDriver->NetCache->ClearClassNetCache()` at
   `OnPostEngineInit` right after the injection runs.

5. **Un-suppress `APlayerController` from `IsClassNetCacheDivergent()`
   in `unreal-stub/Source/Loki/LokiNetDriver.cpp`.** Keep the other
   classes suppressed for now.

6. **Test the launch cycle.** If the client no longer crashes at
   `+0x2976FF0` and instead progresses further (or crashes elsewhere),
   B-lite is working. If it hits the same crash, either:
   - The specific property causing the divergence hasn't been added yet
   - The subsystem's init isn't triggered by AActor replication after all
     (in which case try B-lite on more classes, or accept the ceiling)

Estimated: 8-15 hours engineering. The trickiest step is (3) — struct
property injection. If session time is limited, do step (5) alone first
(un-suppress PC without injecting anything) and observe the FClassNetCache
error to confirm which specific field index the client is complaining
about. That data point may narrow the injection scope significantly.

## The test cycle (memorize; unchanged from sessions 35-40)

Same recipe as `docs/session-35-live-validation.txt` and every session
since. Reference the working launch batch at:

    C:\Users\eastr\AppData\Local\Temp\claude\...\scratchpad\launch-sv-open.bat

Uses `-ini:Engine:...` overrides for AccelByte + Loki URLs (SAFE — anti-
cheat doesn't touch those). The `127.0.0.1:7777` positional URL as the
final arg is the specific detail that made session 35's route-around work
alongside `browse_hook`.

```powershell
# 0. Kill everything first (before anything else)
Get-Process UnrealEditor-Cmd, ags, 'SUPERVIVE-Win64-Shipping', inject, crashpad_handler -EA SilentlyContinue | Stop-Process -Force

# 1. Rebuild + relaunch stub (fresh scratchpad log per session)
& 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' LokiEditor Win64 Development `
  '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' -WaitMutex

$stubLog = 'C:\Users\eastr\AppData\Local\Temp\claude\...\scratchpad\stub-s41.log'
$args_ = @('"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"',
           '/Engine/Maps/Entry?listen', '-game','-server','-log','-Port=7777',
           '-nullrhi','-NoSplash','-Unattended',
           '-LogCmds="LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiActorChannel Verbose, LogLokiNet Verbose, LogNet Verbose, LogRep Verbose"',
           "-abslog=$stubLog")
Start-Process 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $args_

# 2. Delete + regen ags certs, re-append to game cacert bundle from
#    backup (see session 35 for the exact sequence)
Remove-Item 'G:\git\Supervive Revival Project\server\certs\*.crt' -Force -EA SilentlyContinue
Remove-Item 'G:\git\Supervive Revival Project\server\certs\*.key' -Force -EA SilentlyContinue
Start-Process 'G:\git\Supervive Revival Project\server\ags.exe' `
  -WorkingDirectory 'G:\git\Supervive Revival Project\server' `
  -RedirectStandardOutput $agsLog -WindowStyle Hidden
# wait for certs, then:
Copy-Item "$caBundle.supervive-bak" $caBundle -Force
Add-Content -Path $caBundle -Value "`n# SUPERVIVE Revival Root CA" -Encoding ascii
Add-Content -Path $caBundle -Value (Get-Content $certPath -Raw) -Encoding ascii

# 3. Elevated PS spawns inject.exe watch-now — USER MUST CLICK YES ON UAC
$psCmd = "& 'G:\git\Supervive Revival Project\tools\inject\inject.exe' watch-now SUPERVIVE-Win64-Shipping.exe 'G:\git\Supervive Revival Project\tools\sigbypass-mod\browse_hook.dll'"
Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile','-Command',$psCmd

# 4. Client via cmd batch (POSITIONAL URL as final arg before -log)
$batFile = 'C:\Users\eastr\AppData\Local\Temp\claude\...\scratchpad\launch-sv-open.bat'
Start-Process cmd.exe -ArgumentList '/c',"`"$batFile`"" -WindowStyle Hidden
```

Steam must be running first. Hosts file must have SUPERVIVE-REVIVAL
entries.

## What "success" looks like this session

**Scenario A (minimal step 5 only, un-suppress PC, no injection):**

```
[client log] LogRep: Error: ReceivedBunch: Invalid replicated field N
             in PlayerController /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.
             LVL_LobbyV2_Persistent:PersistentLevel.PlayerController_...
```

Where `N` is a specific integer (session 36 saw `N=0`, but that was
without any injection). This data point tells us which NetIndex on the
client resolves to a non-struct non-function. From there, we know the
specific field we need to inject (or, if `N` is 0, we know we need to
add at least one replicated field before whatever's currently first on
our stub side).

**Scenario B (with property injection):**

```
[stub log] LogLokiStub: Display: Injected replicated property "ServerState" onto AActor
[stub log] LogLokiStub: Display: Cleared FClassNetCache
[stub log] ... connection reaches ReceivedJoin, client doesn't hit
           +0x2976FF0 within 90 seconds ...
```

If the timing extends past 64s without hitting the FD3D12CommandContext
crash, B-lite is unwedging the D3D12 init. Then investigate what NEW
behavior emerges (menu render? actual hero grid display?).

## What NOT to do

- **Don't** try any renderer/subsystem cmdline flags — `-DX11`,
  `-nullrhi`, `-vulkan`, `-noraytracing` ALL trigger the anti-cheat
  fail-fast (verified session 40; see `docs/session-40-*-anticheat.txt`).
- **Don't** try `r.RayTracing=0` or similar CVar changes via `-ini:` —
  ALSO anti-cheat-blocked (session 40, `docs/session-40-raytracing-cvar-blocked.txt`).
- **Don't** try to disable D3D12 subsystems via cmdline. They're all
  guarded.
- **Don't** try to `AGameModeBase` to `IsClassNetCacheDivergent()`
  suppression — it's server-only and shouldn't be there anyway
  (documented S38).
- **Don't** compile-error the `ULokiActorChannel::ReplicateActor` route
  — that method is NOT declared virtual in UE 5.4 (S38 verified).
- **Don't** run `launch-redirect.ps1` — it errored on hosts file in
  sessions 31/37 and wiped it. Use the manual step-by-step sequence
  in `docs/ghidra-install.md` if you need to re-verify Ghidra is happy
  or in the S35 sequence for the launch cycle.
- **Don't** propose ScanPrimaryAssetTypesFromConfig-related shims —
  documented dead (see CLAUDE.md).
- **Don't** propose C++-exception-using injection payloads (documented
  dead).
- **Don't** interpret the `Rip = 0xF0400001` / `Rbp = 0x537AC9E1` /
  `R11 = 0x95654773B3BC` register pattern as a natural crash — it's
  SUPERVIVE's anti-cheat fail-fast signature (verified across 4 tests).

## Wrap-up expectations

- If B-lite unwedges the D3D12 crash → commit `Session 41 close: B-lite
  UNSTUCK the FD3D12CommandContext crash` with a `docs/session-41-*.txt`
  evidence log showing the client progressing past 64s.
- If B-lite doesn't work → document the failure mode concretely, and
  either:
  - Escalate to B-full (schema-inject the whole session-20 divergent set)
  - Investigate the anti-cheat mechanism (expensive)
  - Accept the ceiling and pause the project

Chapter's ultimate goal remains: unblock the empty ALL HUNTERS grid /
STORE / COSMETICS / MISSIONS modals (per `memory/supervive-hero-roster-blocker.md`).
Path B-lite is the last cheap-ish path we have.

Good luck!
