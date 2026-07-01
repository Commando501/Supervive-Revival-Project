# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 23

Paste the section between the `---` lines below as the first message of
the new session.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 23** of the chapter. Session 22 confirmed via
`usmapdump extract` that TheoryCraft has heavily modified engine base
classes (LokiReplicationStrategy struct + PoolableActorServerState +
actor-pooling props on `AActor`) — but couldn't extract the specific
UFunction parameter list for `ServerVerifyViewTarget` because usmapdump
only dumps FProperty registrations, not UFunction. Session 20's blocker
(RPC "Mismatch read") still stands.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 22" at the
  #     bottom — that's where you pick up)
  #   docs/session-22-schema-actor-loki-mods.txt  (schema excerpt
  #     showing SUPERVIVE's AActor mods + LokiReplicationStrategy)
  #   schema.txt (in repo root, ~71k lines — full class schema of the
  #     live game; not committed but present if session 22 ran)
  #   unreal-stub/Source/Loki/LokiStatelessConnect.h + .cpp  (session 17
  #     wrapper strip — this is where you could add bunch hex logging
  #     for Path A)
  #   unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp  (session 21
  #     subclass — currently bReplicates=false, doesn't work; will change
  #     once we know the RPC signature)
  #   The hero-roster-blocker memory auto-loads and has session 22's
  #   writeup at the top.

THE EXACT BLOCKER (still same as session 20):

Client's SUPERVIVE-modified APlayerController calls `ServerVerifyViewTarget`
RPC on the server-replicated PC. Server's stock APlayerController has
`ServerVerifyViewTarget()` taking 0 args. Client sends ~2894 bits of arg
payload. Server's RepLayout deserializes 0 args, sees Reader.GetBitsLeft()
!= 0, logs `Mismatch read`, closes actor channel.

Session 22 confirmed the mismatch isn't from added FProperties on the
PC class (base APlayerController has 56 stock-vanilla properties in the
schema). Must be either added UFunction parameters OR engine-level RPC
envelope modification.

TWO PATHS FOR SESSION 23:

PATH A (RECOMMENDED — faster): Log the exact bunch bytes to figure out
the param layout empirically.

Step A1: Add a `LogNet Verbose` or `LogNetTraffic VeryVerbose` to the
stub server's -LogCmds. UE's own bunch parser will log each bit consumed.
See if this reveals the parameter layout without any code changes.

Step A2: If UE's built-in logging doesn't help, hex-dump the incoming
RPC bunch bytes by adding logging in
`unreal-stub/Source/Loki/LokiStatelessConnect.cpp` `Incoming()` override
— we already log packet bytes there; extend to log the full inner-packet
hex after wrapper strip.

Step A3: Cross-reference with UE's bunch format:
  - Bunch header: bReliable, bOpen, bClose, ChIndex (variable-bit-encoded)
  - Object refs: NetGUID (compressed) + PathName (if not cached)
  - Function index: FieldHeaderPayload — variable-bit-encoded
  - Function args: FProperty-by-FProperty deserialization

The RPC-args portion is what we care about. If it's 300+ bytes as
inferred from `2894 bits`, likely a big struct — maybe an anti-cheat
snapshot (view pos + rot + velocity + timestamp + hash).

Step A4: Once we know the param types, add matching UFUNCTION to
LokiStubPlayerController. Register as PlayerControllerClass in
LokiStubGameMode. Test.

PATH B (LONGER-HORIZON — more robust): Write a custom UE class dumper.

Walk GUObjectArray from the live process, find every UClass, enumerate
its Children linked list. Each Child is a UField subclass — cast Field
Class to UFunction and dump its own Children (which is the FProperty
parameter list, in order).

Would need to be added to `tools/usmapdump/` or written fresh. See
`tools/usmapdump/objects.go` and `helpers.go` for the GUObjectArray
walker scaffold.

CLASS-NAME RESOLUTION (still open from session 21):

Even after we know the RPC signature, we still need to solve: how do
we get our LokiStubPlayerController's UFUNCTION override to fire when
the server-side is stock APlayerController?

Options:
- Set PlayerControllerClass to `ALokiStubPlayerController` and figure out
  a way to make the client resolve the class GUID (rename to
  /Script/Engine.PlayerController at runtime with careful CDO handling).
- Keep stock APlayerController and register our matching UFUNCTION on the
  stock class at runtime via UClass function-table manipulation.
- Hook FObjectReplicator::ReceivedRPC at the driver level to intercept
  and either swap the function pointer or discard the RPC entirely.

WHAT'S ALREADY BUILT (do not re-derive):

Server-side plumbing (all working through PC actor spawn on client):
- Full stateless handshake + wrapper strip (sessions 17-18)
- Custom UNetConnection with our StatelessConnect (session 18)
- LevelName rewrite via ModifyClientTravelLevelURL (session 19)
- World package + object rename to LobbyV2 path (session 19)
- NetworkChecksumMode=None on GuidCache (session 20)
- LokiStubGameMode + LokiStubPlayerController stubs (session 21 — need
  minor tweaks in session 23: flip bReplicates=true, add RPC overrides)

RE artifacts (from session 22):
- schema.txt in repo root (71k lines, full UClass/UStruct/UEnum schema
  from live process, sensitive info about SUPERVIVE class structure —
  NOT committed to git, treat as scratchpad)
- tools/extractor/mappings.usmap (refreshed .usmap for CUE4Parse-based
  .pak content extraction)

STUB SERVER LAUNCH COMMAND (from elevated PowerShell, works today):

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose, LogNetTraffic Verbose"

The addition for session 23 is `LogNetTraffic Verbose` — see if it
reveals bunch-level param decoding.

Build after Loki source changes (~5-15 sec incremental):

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client launch (from elevated PowerShell, Steam must be running):

    cd "G:\git\Supervive Revival Project"
    .\configs\launch-redirect.ps1 -Hook ".\tools\sigbypass-mod\browse_hook.dll"

GUARDRAILS (per CLAUDE.md):

- Branch `dedicated-server-stub`. Commit + push each meaningful step.
- Steam must be running before game launch.
- browse_hook v13 has small crash rate; retry on crash.
- Do NOT touch:
  * bDisableOutgoingWrap in LokiNetDriver::LowLevelSend (session 17)
  * World/package rename in Loki.cpp (session 19)
  * NetworkChecksumMode=None in LokiNetDriver::InitBase (session 20)

CHAPTER STATE AT END OF SESSION 22:

  - Handshake: DONE (session 17)
  - Post-handshake packet-handler wiring: DONE (session 18)
  - Control-channel messages (Hello / Login / Welcome): DONE (session 18)
  - Post-Welcome map validation: DONE (session 19)
  - NMT_Join / PostLogin / PC spawn server-side: DONE (session 19)
  - Client-side PC actor spawn: DONE (session 20)
  - SUPERVIVE engine modifications confirmed: DONE (session 22)
  - Server-side RPC deserialization for modified RPCs: TODO (session 23 — this session's focus)
  - Replicating hero-roster / mission / store data to client: TODO (session 24+)

TOOLING ALREADY BUILT:

  tools/usmapdump/usmapdump.exe — for future RE. Notably lacks UFunction
    metadata extraction; session 23 may want to extend it OR write a
    separate live class-dumper.
  tools/inject/inject.exe — manual-map DLL injector.
  tools/sigbypass-mod/browse_hook.dll — LobbyV2 browse rewriter (v13).
  unreal-stub/ — UE5.4 project with LokiEditor target.

LARGER CONTEXT REMINDER:

The original goal is to make the SUPERVIVE Missions modal populate after
the official servers were retired. Sessions 1-20 completed the entire
connection handshake through client-side PC instantiation. Session 21
confirmed workarounds don't help — must match SUPERVIVE's RPC signature.
Session 22 confirmed SUPERVIVE ships modified engine classes but couldn't
extract the specific UFunction params.

Session 23: get the RPC signature (Path A or B), match it, unblock the
RPC dispatch. THEN can move to actual menu-data replication.

If you have any doubt about a step, ask the user before running it.
