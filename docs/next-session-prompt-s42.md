# Session 42 pickup prompt — the D3D12 crash is the last wall

Repo: `G:\git\Supervive Revival Project` — branch `dedicated-server-stub`.
Copy this whole file into a fresh Claude session's first message.

## TL;DR of where we are

Session 41 was a breakthrough. The dedicated-server-stub path now works
**end-to-end at the networking layer**: the SUPERVIVE client does the stateless
handshake → login (via `ags`) → PlayerController replication → **loads the
LobbyV2 map → fetches 25 heroes**, with ZERO replication/RPC errors. The
long-standing FClassNetCache/RepLayout divergence that blocked this since
session 20 is SOLVED.

The **only remaining wall** is the session-40 D3D12 crash: a few seconds after
the lobby loads, the client crashes inside a D3D12 RHI class (crash module list =
`dxgi.dll` + `d3d12.dll` + `D3D12Core.dll` + `nvgpucomp64.dll`, `CEF GPU
acceleration enabled` right before). Session 41 DISPROVED the Path B-lite
hypothesis that proper PC replication would unwedge this crash — it fires with no
network error preceding it, so it's INDEPENDENT of networking.

## FIRST: commit the last uncommitted bit

Before doing anything, commit the ClientSetViewTarget suppression:
```
git -C "G:\git\Supervive Revival Project" add unreal-stub/Source/Loki/LokiNetDriver.cpp docs/session-41-step2-BREAKTHROUGH.txt
git -C "G:\git\Supervive Revival Project" commit -m "Session 41: suppress ClientSetViewTarget RPC (SUPERVIVE-modified sig); networking path now clean end-to-end"
```
(Most of session 41 is already committed: `26c6302`, `761005c`.)

## Read these first, in order

1. `CLAUDE.md` — project rules, launch procedure gotchas, DO-NOT list.
2. `docs/session-41-step2-BREAKTHROUGH.txt` — **THE key doc.** The full
   root-cause chain (N=0 → handle-22 → fixed), what the client does now, and the
   two downstream blockers (A: ClientSetViewTarget = FIXED; B: D3D12 crash =
   remaining).
3. `docs/session-41-supervive-pc-repschema.txt` — the DEFINITIVE RE that made it
   work: SUPERVIVE's APlayerController replicated schema differs from stock by
   exactly one property (`AActor.ServerState`, a custom-NetSerialize struct).
   Don't re-derive this.
4. `docs/session-41-netcache-stock-table.txt` — the stock UE 5.4 net-index table.
5. `docs/session-40-path-A1-VERIFIED.txt` + `docs/session-40-D3D12-CONFIRMED.txt`
   — the D3D12 crash identification (vtable RVA `+0x7B9E188`, ~15,504-byte object,
   the uninit-TArray victim: 0x160-byte slot-parent instance vtable `+0x7B9DC48`,
   `count=1 capacity=4` but `Data` still pointing at a `.rdata` const default —
   "some earlier init step was skipped"). This is the target of Session 42.
6. `docs/session-40-raytracing-cvar-blocked.txt` — the anti-cheat wall: ALL
   cmdline renderer flags (`-DX11`, `-vulkan`, `-nullrhi`, `-noraytracing`) AND
   `r.RayTracing` CVar changes trigger SUPERVIVE's anti-cheat fail-fast. User-
   space renderer workarounds are DEAD. (The `-ini:` AccelByte/Loki URL overrides
   are SAFE — anti-cheat doesn't touch those.)
7. Supporting journey docs if useful: `docs/session-41-probe-result-N0.txt`,
   `docs/session-41-step2-result.txt`, `docs/session-41-blite-step5-armed.txt`,
   `docs/ghidra-install.md`.

Auto-loaded memories (already in context):
- `supervive-hero-roster-blocker.md` — has the Session 41 breakthrough entry on
  top (PC replication fixed, ClientSetViewTarget fixed, D3D12 remaining).
- `supervive-rpc-signature-solved.md` — ServerVerifyViewTarget signature.

## What the stub does now (current code state — all committed except the CSVT bit)

- `unreal-stub/Source/Loki/LokiNetDriver.cpp`:
  - `IsClassNetCacheDivergent()` suppresses GameStateBase/PlayerState/HUD/
    DefaultPawn/SpectatorPawn/WorldSettings/GameplayDebuggerCategoryReplicator —
    but NOT APlayerController (un-suppressed in session 41 step 5).
  - `ShouldReplicateActor` / `ShouldReplicateFunction` gate on that.
  - `ShouldReplicateFunction` also suppresses the `ClientSetViewTarget` RPC by
    name (session 41 fix — modified signature, not needed for the lobby).
  - `InitBase` sets NetworkChecksumMode=None.
- `unreal-stub/Source/Loki/LokiReplicatedStructs.h`: `FPoolableActorServerState`
  { `EPoolableActorServerState State` (UENUM) + `int32 Version` } with a custom
  `NetSerialize` + `WithNetSerializer=true` trait (=> single RepLayout cmd,
  matching the client). DON'T change this — it's what fixed handle-22.
- `unreal-stub/Source/Loki/Loki.cpp`:
  - `InjectServerStateReplicatedProperty()` (OnPostEngineInit): injects the
    `ServerState` CPF_Net FStructProperty onto AActor at RepIndex 10, offset =
    Instigator's offset (via `FLokiStructPropertyWithOffset`), then
    `ForceSetUpReplicationData()` on all 239 actor classes (a validation-free
    mirror of UClass::SetUpRuntimeReplicationData that bypasses the
    ValidateGeneratedRepEnums hard-assert triggered by the shifted RepIndices).
  - `FPoolableActorServerState::NetSerialize`.
  - `DumpClassNetCacheLayout()` — dumps the net-index table at startup.
  - `InjectServerVerifyViewTargetFStringParam()` — sessions 27-32 RPC injection.
- `tools/usmapdump/extract.go` — now emits `<<NET ...>>` CPF_Net flags per
  property (rebuilt `usmapdump.exe`).

## The Session 42 task: the D3D12 crash

### Step 1 (cheap, do first): confirm the lobby crash == session-40 crash

Run the live cycle (below), let the client reach the lobby and crash, then grab
the crash minidump and confirm it's the same `+0x2976FF0` access-violation in the
same D3D12 class as session 40.
- Crash dumps: look under
  `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\` (UE) and/or the Sentry
  crashpad DB. The client uses Sentry + crashpad (see `LogSentrySdk` in the
  client Loki.log).
- Tooling from session 40 (in a PRIOR session's scratchpad — may need to recreate
  from the docs): `parse-any-dump.py` (minidump register + module extractor),
  `verify-a1.py` (anti-cheat vs legit-crash comparator). The Python `minidump`
  package was installed in session 40.
- Expected: `Rip = SUPERVIVE + 0x2976FF0`, `*Rbx` (vtable) at RVA `+0x7B9E188`,
  `Rcx` (failed write target) at `.rdata +0x7ADB368`, ~10 D3D12Core.dll frames.
- DO NOT confuse it with the anti-cheat fail-fast signature
  (`Rip=0xF0400001 / Rbp=0x537AC9E1 / R11=0x95654773B3BC`) — that only appears
  when a forbidden renderer flag/CVar is set, which we are NOT doing.

### Step 2: attack the D3D12 crash (the hard part)

Session 40 established: the crash is a real D3D12 RHI class holding a TArray that
was never initialized (`count=1, capacity=4, Data` = `.rdata` default), because
"some earlier init step was skipped". The renderer-workaround routes are all
anti-cheat-blocked. So the remaining avenues are NATIVE:

- **Native patch via injection.** `browse_hook.dll` proves we can mmap-inject a
  no-throw DLL past CIG (verified sessions 35-41). A native D3D12-init patch DLL
  could: (a) initialize that TArray before the crash instruction, or (b) hook the
  init function that's being skipped and force it to run, or (c) NOP/guard the
  crashing `TArray::Add` at `+0x2976FF0`. Ghidra (E:\Tools) has the decompiled
  crash site from session 40 — start there to find the skipped init.
  DO-NOT: no C++-exception-using payloads (packer's VEH kills the process —
  proven dead, 3 canary variants).
- **Find WHY the init is skipped.** The skipped step may be conditional on some
  state the stub isn't providing, OR a subsystem that isn't initialized in the
  `-nullrhi`-server ↔ real-D3D12-client asymmetry. Worth an hour of Ghidra on
  the caller chain of the uninit TArray before writing a patch.

### Strategic reality check (raise with the user early)

Two honest caveats the user should weigh before sinking hours into D3D12:
1. Session 40 spent a whole session on this crash and concluded the user-space
   workarounds are dead. A native patch is the only route left and it may be
   hard/fragile.
2. EVEN IF the D3D12 crash is beaten, the ORIGINAL empty-ALL-HUNTERS-grid root
   cause (`LokiAssetManager` bypasses the enumeration scan — see the top of this
   memory file / `docs/hero-roster-attempts.md`) is a SEPARATE issue. The 25
   heroes are FETCHED (data present), but whether the grid ENUMERATION populates
   is unproven and may still be empty. So "beat D3D12" ≠ "grid renders".
3. Alternative framings worth offering: (a) accept that the dedicated-server path
   reached its natural ceiling (huge progress: full networking + lobby load), and
   (b) reconsider the IoStore mod-pak overlay route for the enumeration issue
   (CLAUDE.md flags it as a remaining open route), which may be the more direct
   path to a populated grid than fighting D3D12.

Recommend: do Step 1 (confirm the crash, cheap), then have the strategic
conversation with the user before committing to Step 2.

## The live test cycle (refined in session 41 — memorize)

Steam must be running first (else Auth Failure 14005). Hosts file must have the
SUPERVIVE-REVIVAL entries (accounts.projectloki + client-config, both 127.0.0.1).
Do NOT run `launch-redirect.ps1` (it wiped hosts in S31/S37); use the manual
sequence.

```powershell
# 0. Kill everything
Get-Process UnrealEditor-Cmd,ags,'SUPERVIVE-Win64-Shipping',inject,crashpad_handler -EA SilentlyContinue | Stop-Process -Force

# 1. Rebuild stub (only if code changed)
& 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' LokiEditor Win64 Development `
  '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' -WaitMutex
# NOTE: kill any running UnrealEditor-Cmd BEFORE building or the DLL link fails (LNK1104, file locked).

# 2. Launch stub (listen server). Add "LogRepProperties VeryVerbose" to LogCmds
#    if you need the sent-handle list; add "LogRep Verbose, LogNet Verbose".
$stub = 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$stubArgs = @('"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"',
  '/Engine/Maps/Entry?listen','-game','-server','-log','-Port=7777','-nullrhi','-NoSplash','-Unattended',
  '-LogCmds="LogLokiStub Verbose, LogLokiNet Verbose, LogNet Verbose, LogRep Verbose"',
  '-abslog=<your-scratchpad>\stub.log')
Start-Process $stub -ArgumentList $stubArgs
# Wait for "listening on port 7777" in the stub log.
# The -nullrhi is on the SERVER (safe). The anti-cheat is on the CLIENT only.

# 3. ags backend. It's often already running (HTTP :8080 + HTTPS :443). If not,
#    regen certs + re-trust:
$certDir = 'G:\git\Supervive Revival Project\server\certs'
Remove-Item "$certDir\*.crt","$certDir\*.key" -Force -EA SilentlyContinue
Start-Process 'G:\git\Supervive Revival Project\server\ags.exe' -WorkingDirectory 'G:\git\Supervive Revival Project\server' -WindowStyle Hidden
# wait for certs to regen, then re-trust in the game cacert bundle:
$ca = 'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Content\Certificates\cacert.pem'
Copy-Item "$ca.supervive-bak" $ca -Force
Add-Content $ca "`n# SUPERVIVE Revival Root CA" -Encoding ascii
Add-Content $ca (Get-Content "$certDir\root.crt" -Raw) -Encoding ascii
# (Probe: Invoke-WebRequest http://localhost:8080/  -> expect HTTP 200.)

# 4. Elevated inject.exe watch-now — USER MUST CLICK YES ON UAC
$psCmd = "& 'G:\git\Supervive Revival Project\tools\inject\inject.exe' watch-now SUPERVIVE-Win64-Shipping.exe 'G:\git\Supervive Revival Project\tools\sigbypass-mod\browse_hook.dll'"
Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile','-Command',$psCmd
# Wait for "waiting for ..." in its log before launching the client.

# 5. Client via the cmd batch (contents below — recreate in your scratchpad).
Start-Process cmd.exe -ArgumentList '/c','"<your-scratchpad>\launch-sv-open.bat"' -WindowStyle Hidden
```

`launch-sv-open.bat` contents (the positional `127.0.0.1:7777` as the final URL
arg is the specific detail that makes the route-around work):
```bat
@echo off
set EXE="G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
set AB=/Script/AccelByteUe4Sdk.AccelByteSettings
set LOKI=/Script/Loki.LokiGameProjectSettings
set LOCAL=http://localhost:8080
start "" %EXE% ^
  "-ini:Engine:[%AB%]:BaseUrl=%LOCAL%" ^
  "-ini:Engine:[%AB%]:IamServerUrl=%LOCAL%/iam" ^
  "-ini:Engine:[%AB%]:PlatformServerUrl=%LOCAL%/platform" ^
  "-ini:Engine:[%AB%]:BasicServerUrl=%LOCAL%/basic" ^
  "-ini:Engine:[%AB%]:LobbyServerUrl=ws://localhost:8080/lobby/" ^
  "-ini:Engine:[%LOKI%]:ProdPostAuthURL=%LOCAL%" ^
  "-ini:Engine:[%LOKI%]:ProdClientConfigURL=%LOCAL%" ^
  "-ini:Game:[%LOKI%]:ProdPostAuthURL=%LOCAL%" ^
  "-ini:Game:[%LOKI%]:ProdClientConfigURL=%LOCAL%" ^
  127.0.0.1:7777 ^
  -log
```

Client log (READ THIS for results): `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`
Stub log: your `-abslog` path.

### Two flaky-retry gotchas (NOT bugs — just re-run)

- **Injection race**: `inject.exe watch-now` occasionally catches the game
  process too early (before ntdll is in the module list) and fails with
  `FAILED: resolve RtlAddFunctionTable: ntdll.dll not loaded in target`. The
  game then runs WITHOUT the hook. Fix: kill the game, re-spawn inject (UAC
  again), re-launch the client. It usually works on the 2nd try.
- **Login flake**: the game sometimes exits at the Steam login screen
  ("Attempting to login with Steam" then nothing). Transient ags/Steam login
  issue, unrelated to the stub. Just re-launch the client (inject must be
  re-spawned since watch-now exits after one attempt).

## What "success" looks like this session

- **Step 1 success**: a minidump confirming the lobby crash is the same
  `+0x2976FF0` / vtable `+0x7B9E188` D3D12 crash as session 40 (or a surprise —
  a DIFFERENT crash, which would reopen the analysis). Commit a
  `docs/session-42-*.txt` with the register/module comparison.
- **Step 2 success (stretch)**: any native intervention that gets the client PAST
  the D3D12 crash and renders SOMETHING (even a broken menu). Then check whether
  the ALL HUNTERS grid populates.
- **Also a valid outcome**: a clear-eyed writeup that the D3D12 crash is
  intractable on this path, plus a recommendation (accept ceiling / pivot to
  IoStore mod-pak for the enumeration issue).

## What NOT to do

- Don't try renderer/subsystem cmdline flags (`-DX11`, `-vulkan`, `-nullrhi`,
  `-noraytracing`) on the CLIENT — all trigger the anti-cheat fail-fast (S40).
- Don't try `r.RayTracing=0` or renderer CVars via `-ini:` on the client — also
  anti-cheat-blocked (S40).
- Don't propose C++-exception-using injection payloads (packer VEH kills them).
- Don't propose `ScanPrimaryAssetTypesFromConfig` as a shim target (documented
  dead in CLAUDE.md — `__report_gsfailure`s regardless of thread context).
- Don't re-derive the replicated schema — it's settled in
  `docs/session-41-supervive-pc-repschema.txt` (divergence = one property,
  `AActor.ServerState`, custom-NetSerialize struct).
- Don't break the ServerState injection / `ForceSetUpReplicationData` /
  `WithNetSerializer` — that's the hard-won fix that makes replication work.
- Don't run `launch-redirect.ps1` (wiped hosts in S31/S37).
- Don't interpret the `Rip=0xF0400001 / Rbp=0x537AC9E1 / R11=0x95654773B3BC`
  register pattern as a natural crash — it's the anti-cheat fail-fast signature.

## Wrap-up expectations

- Write a `docs/session-42-*.txt` evidence log for whatever you find.
- Update `memory/supervive-hero-roster-blocker.md` (top entry).
- Commit as you go (the user commits per session; small single-purpose commits).
- If the D3D12 crash proves intractable, say so plainly and give the user the
  strategic options rather than grinding.

Good luck. The networking is done — this is the last wall on the
dedicated-server path.
