# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 26

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 26** of the chapter. Session 25 successfully captured
the exact bunch bytes AND decoded the RPC field header: the
ServerVerifyViewTarget RPC arg struct is **2298 bits (287.25 bytes)**
starting at bit 41 of the bunch, containing at least an FString
"/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass" (408 bits) plus ~1890
bits of additional parameters. Today: iterate on trial UFUNCTION
signatures until Reader.GetBitsLeft() == 0.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 25" at bottom)
  #   docs/session-25-bunch-capture.txt  (18-line log excerpt + decode)
  #   docs/session-25-bunch-decoder.py   (212-line Python decoder)
  #   unreal-stub/Source/Loki/LokiActorChannel.h + .cpp  (session-25 hook)
  #   unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp
  #     (session-21 subclass — currently bReplicates=false; we'll flip
  #     that back and add the RPC override in session 26)
  #   unreal-stub/Source/Loki/LokiStubGameMode.cpp  (currently uses
  #     stock APlayerController for RE mode; may need to flip back)
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\DataReplication.cpp
  #     lines 1340-1360 (Reader.GetBitsLeft() check)
  #   The hero-roster-blocker memory auto-loads.

THE EXACT BLOCKER (still same as session 20 at protocol level):

Stock APlayerController::ServerVerifyViewTarget takes 0 args. SUPERVIVE's
version takes SOMETHING that occupies exactly 2298 bits. Server reads 0,
sees 2298 leftover, logs "Mismatch read", closes connection.

DECODED so far:
- Bunch total: 2339 bits (Channel 3, Sequence varies per test)
- Content block header: bOutHasRepLayout=0, bIsActor=1 (2 bits)
- Outer NumPayloadBits: 2321 (SerializeIntPacked at bits 2-17)
- Field header: RepIndex=94 (SerializeInt(MaxIndex+1)) + inner
  NumPayloadBits=2298 (bits 18-40)
- RPC arg struct: bits 41-2338, exactly 2298 bits, 287.25 bytes

Within the RPC arg struct, byte-aligned bytes at bunch offset 128
contain a proper UE FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass"
(int32 count=47 + 46 chars + null = 408 bits total).

STEP-BY-STEP PLAN:

Step 1 (30 min): Confirm the FString hypothesis by adding a matching
UFUNCTION.

  Modify `unreal-stub/Source/Loki/LokiStubPlayerController.h`:
    - Set bReplicates=true (session 21 disabled it)
    - Add: UFUNCTION(reliable, server, WithValidation)
           void ServerVerifyViewTarget(const FString& ClientMapName);
    - Also add _Implementation (empty body) and _Validate (return true).

  Modify `unreal-stub/Source/Loki/LokiStubGameMode.cpp` to use
  LokiStubPlayerController instead of stock APlayerController.

  DON'T EXPECT this to work end-to-end yet — the client sends class GUID
  /Script/Loki.LokiStubPlayerController which the SUPERVIVE cooked package
  can't resolve (ActorChannelFailure per session 21). But the RPC won't
  fire because ActorChannelFailure kills before RPC dispatch. So we need
  BOTH signature match AND class-name resolution before this works.

Step 2 (30 min): Alternative — capture with stock APlayerController but
enhance server logging to show how many bits remain unused. This tells us
if 408-bit FString consumes correctly. If yes, we know FString is the
first param and can iterate.

  Modify `LokiActorChannel::ReceivedBunch` to catch the Mismatch error
  path and log the sub-reader position on failure. Or hook via
  UNetConnection error handler.

  Actually simpler: add an override on APlayerController's ProcessEvent
  via UClass::AddNativeFunction hackery — assign a runtime function
  pointer to ServerVerifyViewTarget's UFUNCTION entry in APlayerController's
  UClass. Complex but avoids class-name-resolution.

Step 3 (30-60 min): Given the bit budget (2298 total, FString ~408 bits),
try iterating signatures. Since we don't have a good way to test each
without full end-to-end connection, use the OFFLINE Python decoder to
try interpretations of the raw bytes:

  Decoder reads bit-by-bit starting at bit 41:
  - Try `FString ClientMapName` first (408 bits) — check if next 32 bits
    look like a valid FString count, an int32 hash, or float bit pattern.
  - Iterate. Look for patterns.

  The bunch bytes are already saved to
  `docs/session-25-bunch-capture.txt`. The parser
  `docs/session-25-bunch-decoder.py` gives us the byte-shifted RPC payload
  starting at bit 41.

Step 4: Class-name resolution.

  Options remain from session 21 (all still open):
  - Runtime UClassRedirect (client-side config we can't modify)
  - Rename ULokiStubPlayerController's UClass path to
    /Script/Engine.PlayerController at runtime — session 21 warned about
    CDO collision, but might be feasible with careful handling
  - Register the modified ServerVerifyViewTarget UFUNCTION on the stock
    APlayerController UClass at Loki module init via reflection hackery
  - Hook FObjectReplicator dispatch — but FObjectReplicator isn't a
    UObject, so we can't override its ReceivedRPC directly

WHAT'S ALREADY BUILT (all working through PC actor spawn on client):

- Full stateless handshake + wrapper strip (sessions 17-18)
- Custom UNetConnection with LokiStatelessConnect (session 18)
- LevelName rewrite via ModifyClientTravelLevelURL (session 19)
- World package + object rename to LobbyV2 path (session 19)
- NetworkChecksumMode=None on GuidCache (session 20)
- LokiStubGameMode + LokiStubPlayerController (session 21 — but PC needs
  updates in session 26)
- Full inner-packet hex dump in LokiStatelessConnect::Incoming (session 23)
- Stock APlayerController config for RE mode (session 23)
- LokiActorChannel per-bunch hex dump (session 25 — KEEP THIS)
- Bunch bit-level decoder (session 25 — Python offline)

STUB SERVER LAUNCH COMMAND:

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose, LogNetTraffic VeryVerbose, LogLokiActorChannel Verbose"

Build after Loki source changes:

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client launch (elevated PS, Steam running):

    cd "G:\git\Supervive Revival Project"
    .\configs\launch-redirect.ps1 -Hook ".\tools\sigbypass-mod\browse_hook.dll"

GUARDRAILS:

- Branch `dedicated-server-stub`. Commit + push each meaningful step.
- Steam must be running before game launch.
- browse_hook v13 has small crash rate; retry on crash.
- Do NOT touch:
  * bDisableOutgoingWrap in LokiNetDriver::LowLevelSend (session 17)
  * World/package rename in Loki.cpp (session 19)
  * NetworkChecksumMode=None in LokiNetDriver::InitBase (session 20)
  * Session-23 hex dump in LokiStatelessConnect::Incoming (needed for RE)
  * Session-25 LokiActorChannel hex dump + ChannelDefinitions config
    (needed for RE)

CHAPTER STATE AT END OF SESSION 25:

- Everything through PC spawn: DONE (sessions 17-20)
- SUPERVIVE engine mods confirmed: DONE (session 22)
- RPC bunch bytes captured + decoded: DONE (sessions 23-25)
- Bunch content-block + field header decoded: DONE (session 25)
- RPC arg struct isolated (2298 bits, FString + ~236 more bytes): DONE (session 25)
- Full RPC parameter list: TODO (session 26 — trial signatures)
- Class-name resolution: TODO (session 26-27)
- Menu-data replication: TODO (session 28+)

LARGER CONTEXT:

The goal is populating SUPERVIVE's Missions modal after official servers
went down. Sessions 17-25 have surgically decoded the last protocol
obstacle: SUPERVIVE's modified ServerVerifyViewTarget RPC signature. We
now have the EXACT byte-aligned 287-byte arg struct. Session 26 needs to
identify the param types (FString confirmed, rest TBD), add matching
UFUNCTION, and solve the class-name issue so the RPC actually dispatches
to our override.

If in doubt about a step, ask the user.
