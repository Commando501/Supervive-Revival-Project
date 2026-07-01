# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 22

Paste the section between the `---` lines below as the first message of
the new session. It bootstraps the agent fully without re-reading dozens
of files.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 22** of the chapter. Session 21 explored whether the
client-side PC RPC problem (session 20 blocker: ServerVerifyViewTarget
"Mismatch read" — SUPERVIVE ships modified engine APlayerController with
different RPC args) could be worked around by preventing PC replication
entirely. It CAN'T: AGameModeBase::PostLogin unconditionally opens an
ActorChannel for the PC, and if the class GUID is a custom subclass the
client hits `NMT_ActorChannelFailure` for the unknown class. If it's
stock APlayerController the client spawns fine but then RPC mismatch
kills the connection.

Both paths proven closed in session 21. Session 22's job is to actually
RE and MATCH SUPERVIVE's modified ServerVerifyViewTarget signature.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -8
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 21" at the bottom —
  #     that's where you pick up. Session 20 has the NetworkChecksumMode fix.
  #     Session 19 has the world-rename + LevelName-rewrite fixes.)
  #   docs/session-21-stub-log-excerpt.txt  (46-line filtered stub log
  #     showing bReplicates=false PC + ActorChannelFailure + 
  #     ControlChannelPlayerChannelFail close reason)
  #   unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp  (session-21
  #     subclass — currently bReplicates=false; session 22 will need to flip
  #     this back to true and add matching RPC signatures)
  #   unreal-stub/Source/Loki/LokiStubGameMode.h + .cpp  (session-21 GameMode
  #     wiring — keep this, it's the mechanism for registering PC class)
  #   unreal-stub/Source/Loki/LokiNetDriver.h + .cpp  (session-20
  #     NetworkChecksumMode=None override)
  #   unreal-stub/Source/Loki/LokiGameInstance.h + .cpp  (session-19
  #     ModifyClientTravelLevelURL override)
  #   unreal-stub/Source/Loki/Loki.cpp  (session-19 world/package rename)
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Classes\GameFramework\PlayerController.h
  #     — check stock signatures: ServerVerifyViewTarget (line 1536, takes 0
  #     args), ServerAcknowledgePossession, ServerCameraLookAt, etc.
  #   The hero-roster-blocker memory auto-loads and has session 21's writeup
  #   at the top.

THE EXACT BLOCKER:

Stock UE's `APlayerController::ServerVerifyViewTarget()` takes zero args.
SUPERVIVE's client-side APlayerController calls it with ~2894 bits of
payload (a bunch, so subtract some header overhead — the actual param
struct is probably 200-400 bytes). Server's RepLayout deserializes 0
args because our stock signature has none, then sees Reader.GetBitsLeft()
!= 0, logs `ReceivedRPC: ReceivePropertiesForRPC - Mismatch read`,
returns bSuccess=false, ObjectReplicator closes the actor channel with
`ObjectReplicatorReceivedBunchFail`, connection tears down.

Both class-substitution paths are dead:
- Custom class name → client can't resolve GUID → ActorChannelFailure.
- Stock class → succeeds through spawn but RPC signature mismatch kills it.

The ONLY remaining path: match SUPERVIVE's exact param list.

RECOMMENDED SESSION 22 APPROACH:

Step 1 (30-60 min): RE the signature via usmapdump on a LIVE game process.

  usmapdump attaches to a running process, not a static exe. Launch the
  SUPERVIVE client (may need to wait until it's fully loaded — the packer
  needs to unpack). Then:

    # in one terminal — launch game via launch-redirect.ps1 or manually
    # (see chapter for the launch commands)
    
    # in another terminal:
    tools\usmapdump\usmapdump.exe wstrings SUPERVIVE-Win64-Shipping.exe "ServerVerifyViewTarget" 10
    tools\usmapdump\usmapdump.exe wstrings SUPERVIVE-Win64-Shipping.exe "VerifyViewTarget"      10
    
    # If those don't find hits, try nameid (searches FNamePool):
    tools\usmapdump\usmapdump.exe nameid SUPERVIVE-Win64-Shipping.exe "VerifyView" 20

  For each hit, use `xrefstr` to find code that references the string,
  then `disasm` to look for the FProperty registrations near the function
  definition. UE generated code registers UFunction parameters near the
  UClass::StaticRegisterNativesA*PlayerController area — grep for
  "NewProp_" style symbols.

  ALTERNATIVE: usmapdump extract runs the "get every UClass's schema"
  extractor. This gives us a full schema.txt with every registered
  UFUNCTION and its FProperty parameter list. Look for
  APlayerController::ServerVerifyViewTarget in the output.

    tools\usmapdump\usmapdump.exe extract SUPERVIVE-Win64-Shipping.exe
    # produces some output file — see tools/usmapdump for details

Step 2 (30-60 min): Add matching UFUNCTION to LokiStubPlayerController.

  ALokiStubPlayerController currently has no UFUNCTIONs. Add:

    UFUNCTION(reliable, server, WithValidation)
    void ServerVerifyViewTarget(<SUPERVIVE_PARAMS>);
    void ServerVerifyViewTarget_Implementation(<SUPERVIVE_PARAMS>) {}
    bool ServerVerifyViewTarget_Validate(<SUPERVIVE_PARAMS>) { return true; }

  Where <SUPERVIVE_PARAMS> matches whatever session-22 step-1 discovered.

Step 3 (10 min): Solve the class-name-resolution problem.

  Option A: Ship LokiStubPlayerController class but use ActiveClassRedirects
  in DefaultEngine.ini so the client resolves stock APlayerController requests
  to our class. Doesn't work — client's config isn't ours to modify.

  Option B: Keep PlayerControllerClass = APlayerController::StaticClass()
  (stock). Register our RPC-matching UFUNCTIONs on the STOCK class at
  runtime via UClass function-table manipulation. Feasible but hacky.

  Option C (recommended): Try renaming ALokiStubPlayerController's UClass
  path to `/Script/Engine.PlayerController` at runtime, similar to session
  19's world-package rename. Would need to first UNLOAD/rename the existing
  APlayerController CDO to a different path, then rename our subclass into
  the /Script/Engine.PlayerController slot. Fragile — test carefully.

  Option D: Server-side ObjectReplicator hook that intercepts RPCs and
  discards ones we don't recognize. This requires overriding UNetDriver's
  packet processing or hooking into FObjectReplicator::ReceivedBunch. Too
  invasive for this session probably.

Step 4 (test iterate): Build, launch stub + client, watch for the next
signature-mismatch error (there will likely be MORE RPCs to match —
SUPERVIVE probably modified ServerAcknowledgePossession, ServerUpdateCamera,
etc. too). Match each as they surface.

WHAT'S ALREADY BUILT (all working through PC spawn):

Server-side plumbing (all working through PC actor spawn on client):
- Full stateless handshake + wrapper strip (sessions 17-18)
- Custom UNetConnection with our StatelessConnect (session 18)
- LevelName rewrite via ModifyClientTravelLevelURL (session 19)
- World package + object rename to LobbyV2 path (session 19)
- NetworkChecksumMode=None on GuidCache (session 20)
- LokiStubGameMode + LokiStubPlayerController stubs (session 21 — need
  minor tweaks in session 22: flip bReplicates=true, add RPC overrides)

STUB SERVER LAUNCH COMMAND (from elevated PowerShell, works today):

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose"

Build after Loki source changes (~5-15 sec incremental):

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client launch (from elevated PowerShell, Steam must be running):

    cd "G:\git\Supervive Revival Project"
    .\configs\launch-redirect.ps1 -Hook ".\tools\sigbypass-mod\browse_hook.dll"

Alternative iterative flow (used through session 21):
    # 1. ags backend
    # 2. inject watch-now (BEFORE game launch, single-quoted args due to path spaces)
    # 3. game exe with -ini overrides

GUARDRAILS (per CLAUDE.md):

- Branch `dedicated-server-stub`. Commit + push each meaningful step.
- Don't mutate the running game without warning the user.
- Hosts file redirect is active; don't run launch-redirect.ps1 -Revert casually.
- Steam must be running before the game launches.
- browse_hook v13 has small crash rate; retry on crash.
- Do NOT touch:
  * bDisableOutgoingWrap in LokiNetDriver::LowLevelSend (session 17)
  * World/package rename in Loki.cpp (session 19)
  * NetworkChecksumMode=None in LokiNetDriver::InitBase (session 20)

CHAPTER STATE AT END OF SESSION 21:

  - Handshake: DONE (session 17)
  - Post-handshake packet-handler wiring: DONE (session 18)
  - NMT_Hello / NMT_Login / NMT_Welcome control-channel messages: DONE (session 18)
  - Post-Welcome map validation: DONE (session 19)
  - NMT_Join / PostLogin / PC spawn server-side: DONE (session 19)
  - Client-side PC actor spawn (stock class): DONE (session 20)
  - Server-side RPC deserialization for modified engine RPCs: TODO (session 22 — this session's focus)
  - Replicating hero-roster / mission / store data to client: TODO (session 23+)

TOOLING ALREADY BUILT (do not duplicate):

  tools/usmapdump/usmapdump.exe — RE tool. CRITICAL for session 22 — needs
    to find SUPERVIVE's modified ServerVerifyViewTarget signature.
    Subcommands: strings, wstrings, xrefstr, nameid, extract, disasm, peek.
    See `usmapdump` with no args for full help.
  tools/inject/inject.exe — manual-map DLL injector.
  tools/sigbypass-mod/browse_hook.dll — LobbyV2 browse rewriter (v13).
  unreal-stub/ — UE5.4 project with LokiEditor target.

LARGER CONTEXT REMINDER:

The original goal is to make the SUPERVIVE Missions modal (and other content
panels) populate after the official servers were retired. Sessions 1-20
completed the entire connection handshake through client-side PC instantiation.
Session 21 confirmed the RPC-signature-mismatch blocker requires actual
signature matching (workarounds via class substitution don't work). Session
22 needs to RE the specific signature.

Remaining gap between us and "SUPERVIVE menu with missions populated":
  1. Session 22: match SUPERVIVE's modified PC RPC signatures (this session).
  2. Session 23+: normal UE5.4 dev work. Write Loki module's LobbyState or
     LokiPlayerState classes that replicate mission/hero-roster data.

If you have any doubt about a step, ask the user before running it.
