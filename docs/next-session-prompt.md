# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 21

Paste the section between the `---` lines below as the first message of
the new session. It bootstraps the agent fully without re-reading dozens
of files.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 21** of the chapter. Session 20 unblocked the
client-side `ActorChannelFailure` on the server-replicated PlayerController
(via `GuidCache->SetNetworkChecksumMode(None)` — SUPERVIVE ships modified
engine base classes so the stock-vs-Loki class checksum comparison always
failed). Client now instantiates the PC actor and starts sending RPCs
back. NEW blocker: SUPERVIVE's `APlayerController` has modified RPC
signatures. The client's `ServerVerifyViewTarget` RPC arguments don't
deserialize against stock UE5.4's `ServerVerifyViewTarget` signature. Today's
job is to give the server a PC class whose RPC signatures match SUPERVIVE's.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -8
  # Then read:
  #   docs/dedicated-server-stub.md   (full chapter — jump to
  #     "Session 20" at the bottom, that's where you pick up.
  #     Session 19 solved the map/world rename problem. Session 18 solved
  #     the UNetConnection PacketHandler wiring. Session 17 solved the
  #     stateless handshake wrapper.)
  #   docs/session-20-stub-log-excerpt.txt  (the filtered stub log
  #     showing NetworkChecksumMode=None + Join succeeded + PC actor
  #     spawn + ServerVerifyViewTarget RPC mismatch — 17 lines)
  #   unreal-stub/Source/Loki/LokiNetDriver.cpp + .h  (session-20
  #     InitBase override that sets NetworkChecksumMode=None)
  #   unreal-stub/Source/Loki/LokiGameInstance.h + .cpp  (session-19
  #     ModifyClientTravelLevelURL override)
  #   unreal-stub/Source/Loki/Loki.cpp  (session-19 world/package
  #     rename hook)
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Classes\GameFramework\PlayerController.h
  #     — find stock ServerVerifyViewTarget signature (look for
  #     UFUNCTION(Server, Reliable, WithValidation)). Compare with
  #     SUPERVIVE's version by RE'ing the exe.
  #   The hero-roster-blocker memory auto-loads and has session 20's
  #   writeup at the very top.

THE EXACT BLOCKER:

Client instantiates the server-replicated `APlayerController` cleanly, then
calls RPCs on it. First RPC arriving server-side is `ServerVerifyViewTarget`
(stock UE APlayerController RPC). Server's `UObjectReplicator::ReceivedRPC`
tries to deserialize the RPC arguments against `APlayerController::ExecServerVerifyViewTarget`
signature — mismatch. Byte-stream parse fails at the arg-count or arg-type
level. UE closes the actor channel with:

    LogNet: Error: ReceivedRPC: ReceivePropertiesForRPC - Mismatch read.
        Function: ServerVerifyViewTarget,
        Object: PlayerController .../LVL_LobbyV2_Persistent:PersistentLevel.PlayerController_0
    LogNet: Error: UActorChannel::ProcessBunch: Replicator.ReceivedBunch failed.
        Closing connection. RepObj: PlayerController, Channel: 3
    LogNet: UNetConnection::Close: ... Result=ObjectReplicatorReceivedBunchFail
    LogNet: SetClientLoginState: ReceivedJoin -> CleanedUp

Note: This is the SAME class-modification pattern that caused
session-19's `ActorChannelFailure` (which was the class-schema checksum
comparison). Session 20 disabled the checksum check, but the RPC
signature check is structural — you can't disable byte-stream parsing
of arguments against a struct that doesn't match.

RECOMMENDED SESSION 21 APPROACH:

Step 1 (30 min): RE SUPERVIVE's ServerVerifyViewTarget signature.

    tools\usmapdump\usmapdump.exe wstrings "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe" | grep -iE "ServerVerify|VerifyViewTarget"

  Also look at LogNet Verbose output on the server — the RPC bunch size
  is 2894 bits post-wrapper-strip = 361 bytes. Stock ServerVerifyViewTarget
  takes 1 param (AActor* TargetActor). If SUPERVIVE's takes an extra
  FVector or FQuat, the size delta explains the mismatch.

  Alternative: look at UE-modified games with published sources
  (Ark Ascended, some UE5 games have -Shipping symbol tables) for how
  they modify ServerVerifyViewTarget — often it's for anti-cheat.

Step 2 (60-120 min): Author a stub PC class with matching RPCs. Plan:
  - Create `unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp`
    Subclass of `APlayerController`. Override `ServerVerifyViewTarget_Implementation`
    with the SUPERVIVE-matched parameters. If need be, use SUPERVIVE's
    class name via `UCLASS(hidedropdown, config=Engine)` or via a runtime
    UPackage::Rename similar to session 19's world rename.
  - Create `unreal-stub/Source/Loki/LokiStubGameMode.h + .cpp`
    Custom `AGameModeBase` subclass. Constructor:
      PlayerControllerClass = ULokiStubPlayerController::StaticClass();
  - Register the GameMode:
    DefaultEngine.ini:
        [/Script/EngineSettings.GameMapsSettings]
        GlobalDefaultGameMode=/Script/Loki.LokiStubGameMode
  - If SUPERVIVE calls MORE modified RPCs after ServerVerifyViewTarget,
    add them as you see each new error. Iterate.

Step 3 (fallback if RPC RE is intractable): Reject client RPCs entirely.
  Override `AGameModeBase::PostLogin` to spawn a PC with `bBlockClientRPCs`
  or similar. Or set `bDisableRPCs` on the PC. This may leave the
  connection alive without letting the client's RPCs work, but the
  server-side actors still replicate to the client. Menu-population
  server → client should still work.

WHAT'S ALREADY BUILT (all working):

  Session 20 additions:
  - `ULokiNetDriver::InitBase` override → `GuidCache->NetworkChecksumMode = None`.
    Server omits per-class checksums, client skips checksum check.

  Sessions 17-19 (see previous session's pickup prompt for context):
  - Full stateless handshake + wrapper strip both directions
  - Custom UNetConnection subclass with our StatelessConnect in the chain
  - LevelName rewrite via ModifyClientTravelLevelURL
  - World package + object rename to /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent

STUB SERVER LAUNCH COMMAND (from elevated PowerShell, works today):

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose"

Build after Loki source changes (~5-15 sec incremental):

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client launch (from elevated PowerShell, Steam must be running):

    # Simplest: launch-redirect.ps1 (handles cert + hosts + ags + client + hook)
    cd "G:\git\Supervive Revival Project"
    .\configs\launch-redirect.ps1 -Hook ".\tools\sigbypass-mod\browse_hook.dll"

Alternative iterative flow (used through session 20):
    # 1. ags backend
    # 2. inject watch-now (BEFORE game launch, single-quoted args due to path spaces)
    # 3. game exe with -ini overrides
    # See launch-redirect.ps1:130-165 for the exact args.

GUARDRAILS (per CLAUDE.md):

  - Branch is `dedicated-server-stub`. Commit + push each meaningful
    step. Push needs `gh auth` or system git credential helper.
  - Don't mutate the running game without warning the user first.
  - Hosts file redirect is already active; don't run
    `configs/launch-redirect.ps1 -Revert` casually.
  - Steam must be running before the game launches.
  - browse_hook v13 has a small (<10%) crash rate on the client during
    Browse rewrite. Retry on crash.
  - Do NOT touch:
    * bDisableOutgoingWrap in LokiNetDriver::LowLevelSend (session 17)
    * World/package rename in Loki.cpp (session 19)
    * NetworkChecksumMode=None in LokiNetDriver::InitBase (session 20)
    All are required for the current progress point.

CHAPTER STATE AT END OF SESSION 20:

  - Handshake: DONE (session 17)
  - Post-handshake packet-handler wiring: DONE (session 18)
  - NMT_Hello / NMT_Login / NMT_Welcome control-channel messages: DONE (session 18)
  - Post-Welcome map validation: DONE (session 19)
  - NMT_Join / PostLogin / PC spawn server-side: DONE (session 19)
  - Client-side PC actor spawn: DONE (session 20, NetworkChecksumMode=None)
  - Server-side RPC deserialization for modified engine RPCs: TODO (session 21 — this session's focus)
  - Replicating hero-roster / mission / store data to client: TODO (session 22+)

TOOLING ALREADY BUILT (do not duplicate):

  tools/usmapdump/usmapdump.exe — RE tool. Session 21 will USE this to find
    SUPERVIVE's modified ServerVerifyViewTarget signature and any other
    modified RPCs.
  tools/inject/inject.exe — manual-map DLL injector.
  tools/sigbypass-mod/browse_hook.dll — LobbyV2 browse rewriter (v13).
  unreal-stub/ — UE5.4 project with LokiEditor target.

LARGER CONTEXT REMINDER:

The original goal of this multi-chapter project is to make the SUPERVIVE
Missions modal (and other content panels — All Hunters, Store, Cosmetics)
populate after the official servers were retired. Sessions 1-20 completed
the entire connection handshake through client-side PlayerController
instantiation. Only client→server RPCs currently fail.

Remaining gap between us and "SUPERVIVE menu with missions populated":
  1. Session 21: match SUPERVIVE's PC RPC signatures OR suppress client
     RPCs entirely (this session's focus).
  2. Session 22+: normal UE5.4 dev work. Write Loki module's LobbyState or
     LokiPlayerState classes that replicate mission/hero-roster data.

If you have any doubt about a step, ask the user before running it.
