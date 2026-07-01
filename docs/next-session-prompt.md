# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 24

Paste the section between the `---` lines below as the first message of
the new session.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 24** of the chapter. Session 23 executed Path A of
session 22's plan: logged full RPC bunch bytes on the stub, confirmed the
failing bunch is on Channel 3 with size 5.8+292.4 (bunch header + payload
in bytes), and identified an ASCII FString `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass`
at byte offset 145 with proper UE FString encoding (int32 length prefix 47
= 46 chars + null). Session 24's job is to fully decode the payload
structure and identify the exact param list.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 23" at the bottom)
  #   docs/session-23-rpc-bunch-bytes.txt  (15 lines — the captured bunch
  #     bytes + observations)
  #   scratchpad/decode_rpc_bunch.py  (basic Python decoder session 23
  #     started; extends to bit-level parse)
  #   unreal-stub/Source/Loki/LokiStatelessConnect.cpp  (session 23's hex
  #     dump additions — useful reference for what we log)
  #   unreal-stub/Source/Loki/LokiStubGameMode.cpp  (session 23 swapped
  #     to stock APlayerController; keep that for session 24 tests
  #     until we have matching UFUNCTION signature)
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\DataChannel.cpp
  #     line 4905-4930 — UActorChannel::ReadFieldHeaderAndPayload. Shows:
  #     - Field header identifies which UFunction (variable-bit)
  #     - SerializeIntPacked reads NumPayloadBits (variable-bit)
  #     - Payload is NumPayloadBits worth of param bits
  #   The hero-roster-blocker memory auto-loads.

THE EXACT DIAGNOSTIC (from session 23):

Captured packet (2026-07-01 05.22.25:265, session-23c run):

    Inner 362 bytes: 1C 88 05 29 C6 3F 00 00 C0 DB D2 00 25 66 1E 49 8E 90 78 EB 45 16 00 8C 0B 00 00 C0 CB 51 58 5B D9 0B D3 DB 5A DA 4B 53 18 DC DC 0B D3 9B 98 58 9E 95 CC 0B 93 15 D3 17 D3 9B 98 58 9E 95 CC 17 54 98 1C 5D 5E 53 99 5B 1D 00 00 00 00 00 80 C1 01 00 00 78 39 0A 6B 2B 7B 61 7A 5B 4B 7B 69 0A 83 9B 7B 61 7A 13 13 CB B3 92 79 61 B2 62 FA 62 7A 13 13 CB B3 92 F9 42 2A 93 7B 9B 2A 63 2B 1B A3 FB 9A 5A CB 63 0B 73 23 9B 03 00 00 00 00 00 30 2F 00 00 00 2F 47 61 6D 65 2F 4C 6F 6B 69 2F 4D 61 70 73 2F 4C 6F 62 62 79 56 32 2F 4C 56 4C 5F 4C 6F 62 62 79 56 32 5F 42 61 74 74 6C 65 50 61 73 73 00 00 00 00 00 00 A6 05 00 00 E0 E5 28 AC AD EC 85 E9 6D 2D ED A5 29 0C 6E EE 85 E9 4D 4C 2C CF 4A E6 85 C9 8A E9 8B E9 4D 4C 2C CF 4A E6 8B 29 ED 0C 8D 2E CD ED 0C 00 00 00 00 00 C0 AC 00 00 00 BC 1C 85 B5 95 BD 30 BD AD A5 BD 34 85 C1 CD BD 30 BD 89 89 E5 59 C9 BC 30 59 31 7D 31 BD 89 89 E5 59 C9 7C 05 C9 B5 BD C9 E5 01 00 00 00 00 00 20 00 52 FC 2F 80 13 2E 44 00 00 00 9E C4 D4 CA C6 E8 A4 CA E0 D8 D2 C6 C2 E8 DE E4 A4 CA C6 CA D2 EC CA C8 84 EA DC C6 D0 8C C2 D2 D8 00 0A 02 40 C5 FF 02 00 20

    Reliable Bunch, Channel 3 Sequence 549: Size 5.8+292.4
    Function: ServerVerifyViewTarget → Mismatch read (stock 0-arg vs. client's payload)

Confirmed FString at offset 145: `2F 00 00 00 2F 47 61 6D 65 2F 4C 6F 6B 69 2F 4D 61 70 73 2F 4C 6F 62 62 79 56 32 2F 4C 56 4C 5F 4C 6F 62 62 79 56 32 5F 42 61 74 74 6C 65 50 61 73 73 00`
= FString(count=47, "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass\0")

Payload sections:
- Bytes 0-90: bit-packed structured data (structure unknown)
- Bytes 91-137: FString (the map name)
- Bytes 138-292: more bit-packed data (structure unknown)

STEP-BY-STEP PLAN:

Step 1 (15 min): Get NumPayloadBits directly.

  Add LogRepTraffic Verbose to stub -LogCmds. That log category includes
  "Received RPC: %s" AND the specific NumPayloadBits value:

    -LogCmds="... LogRepTraffic Verbose ..."

  Relaunch stub + client (session-23 launch commands work). Look for a
  line like:
    LogRepTraffic: Log: Received RPC: ServerVerifyViewTarget
  and nearby FInBunch/FBitReader trace showing the sub-reader size.

Step 2 (30-60 min): Write a bit-level packet parser.

  Extend `scratchpad/decode_rpc_bunch.py`. UE packet format
  (post-PacketHandler chain):

  1. Bit 0: bReplay flag (1 bit)
  2. FNetPacketNotify header (variable bits — Seq numbers, Ack, History)
  3. Bunch loop:
     - bControl (1 bit) — is a control bunch?
     - bOpen (1 bit), bClose (1 bit), bIsReplicationPaused (1 bit)
     - bReliable (1 bit)
     - ChIndex — SerializeInt(MaxChannels) — variable bits
     - bHasPackageMapExports, bHasMustBeMappedGUIDs, bPartial (1 bit each)
     - if bPartial: bPartialInitial, bPartialFinal (1 bit each), ChSequence variable
     - if bReliable: ChSequence — SerializeInt(MAX_SEQUENCE)
     - NumBits — SerializeInt(NetMaxConstructedPartialBunchSizeBytes*8)
     - NumBits worth of bunch payload

  4. Bunch payload (for actor channels post-open):
     - Repeat until end:
       - ReadFieldHeaderAndPayload:
         - RepIndex — variable bits (via FNetFieldExportGroup)
         - NumPayloadBits — SerializeIntPacked
         - Payload — NumPayloadBits worth

  Reference implementations:
  - `H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\NetConnection.cpp`
    (FBitReader, packet parsing)
  - `H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\DataChannel.cpp:4900-4930`
    (ReadFieldHeaderAndPayload)

Step 3 (30 min): Trial-and-error signature matching.

  Start with `void ServerVerifyViewTarget(FString ClientMapName)`. Add
  to `ALokiStubPlayerController`:

    UFUNCTION(reliable, server, WithValidation)
    void ServerVerifyViewTarget(const FString& ClientMapName);
    void ServerVerifyViewTarget_Implementation(const FString& ClientMapName) {}
    bool ServerVerifyViewTarget_Validate(const FString& ClientMapName) { return true; }

  Flip `LokiStubGameMode::PlayerControllerClass` back to
  `ALokiStubPlayerController::StaticClass()`. Test.

  If we still see "Mismatch read" with a smaller leftover bit count,
  try adding more parameters. Common candidates:
  - `FVector Location`
  - `FRotator Rotation` (or `FVector2D ViewAngles`)
  - `int32 Timestamp` or `uint32 Timestamp`
  - `TArray<uint8> Payload` (opaque byte array — matches variable bit count)
  - `FName MapName` (would appear as name-pool index, not a full FString)

  If we see NO more mismatch, connection continues. There will likely be
  additional RPCs after (SUPERVIVE probably modified several) — iterate.

Step 4: Address the class-name resolution problem.

  Same as session 22 pickup — we need our Loki subclass's UFUNCTION
  overrides to fire when the server-spawned PC is our class. But the
  client needs to spawn the PC too. Options:
  - Set `PlayerControllerClass = ALokiStubPlayerController` and hope the
    client's SUPERVIVE-modified PC spawn logic somehow works (maybe
    class-inheritance resolution treats it as a stock APlayerController
    subclass — worth testing).
  - Runtime class rename with careful CDO handling.
  - Hook `FObjectReplicator::ReceivedRPC` at driver level to intercept
    RPCs before dispatch.

WHAT'S ALREADY BUILT (all working):

Server-side plumbing (all working through PC actor spawn):
- Full stateless handshake + wrapper strip (sessions 17-18)
- Custom UNetConnection with LokiStatelessConnect (session 18)
- LevelName rewrite via ModifyClientTravelLevelURL (session 19)
- World package + object rename to LobbyV2 path (session 19)
- NetworkChecksumMode=None on GuidCache (session 20)
- LokiStubGameMode + LokiStubPlayerController stubs (session 21)
- Full inner-packet hex dump in LokiStatelessConnect::Incoming (session 23)
- Stock APlayerController as PlayerControllerClass (session 23, for RE mode)

STUB SERVER LAUNCH COMMAND (from elevated PowerShell):

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose, LogNetTraffic VeryVerbose, LogRep VeryVerbose, LogRepTraffic Verbose"

  Note the addition of `LogRepTraffic Verbose` vs session 23 — this should
  give us NumPayloadBits directly.

Build after Loki source changes:

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client launch (from elevated PowerShell, Steam must be running):

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

CHAPTER STATE AT END OF SESSION 23:

  - Handshake, packet handler wiring, control messages, map validation,
    Join, PC spawn, checksum bypass: ALL DONE (sessions 17-20)
  - SUPERVIVE engine mods confirmed: DONE (session 22)
  - RPC bunch bytes captured: DONE (session 23)
  - FString parameter identified in payload: DONE (session 23)
  - Exact RPC parameter LIST identified: TODO (session 24 — this session's focus)
  - Add matching UFUNCTION + solve class-name: TODO (session 24-25)
  - Menu-data replication: TODO (session 26+)

LARGER CONTEXT REMINDER:

The end goal is populating the SUPERVIVE menu after the official servers
went down. Sessions 17-23 solved the entire connection handshake up to
PC actor instantiation. Session 24 focuses on the last protocol obstacle:
matching SUPERVIVE's modified PC RPC signatures. After that, the work
becomes normal UE dev — write custom PlayerState/GameState classes that
replicate the menu content.

If in doubt about a step, ask the user.
