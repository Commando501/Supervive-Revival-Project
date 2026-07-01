# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 25

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 25** of the chapter. Session 24 wrote a bit-level
packet parser (`docs/session-24-packet-parser.py`) that CORRECTLY decodes
the StatelessConnect prefix + FNetPacketNotify header + JitterClock
(Seq=1577, AckedSeq=354, JitterClockTime=439 — all match UE's log). But
bunch-header parsing hits a wall — reads bControl=1 with bOpen=0
bClose=0 (invalid combo). Rather than continue bit-level RE, session 25
should PIVOT: add server-side instrumentation to capture the RPC's
sub-reader bytes directly at ReceivePropertiesForRPC.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 24" at bottom)
  #   docs/session-24-packet-parser.py  (309 lines — see what works and
  #     what doesn't in the bit-level parser)
  #   docs/session-23-rpc-bunch-bytes.txt  (the raw bytes to decode)
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\DataReplication.cpp
  #     lines 1290-1360 — ReceivedRPC path with the sub-reader
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\Engine\Private\DataChannel.cpp
  #     lines 4905-4930 — ReadFieldHeaderAndPayload (where NumPayloadBits
  #     is read and sub-reader is created)
  #   unreal-stub/Source/Loki/LokiStatelessConnect.cpp  (session 23 hex dump
  #     — we can extend the same technique to log RPC-scope sub-readers)
  #   unreal-stub/Source/Loki/LokiIpConnection.cpp  (session 18 wired
  #     LokiStatelessConnect into UNetConnection — the hookable seam)
  #   The hero-roster-blocker memory auto-loads.

THE EXACT DIAGNOSTIC (still same as session 20):

Client sends ServerVerifyViewTarget RPC on Channel 3. Server's stock
APlayerController::ServerVerifyViewTarget takes 0 args. Client's payload
is ~292 bytes worth. `Reader.GetBitsLeft() != 0` after reading 0 params →
Mismatch read → connection dies.

Confirmed via session-23 hex dump: payload contains
`FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass"` at byte 145
(int32 count=47 + 46 chars + null). Rest of the 292 bytes is bit-packed
data with no other obvious ASCII strings — likely multiple additional
parameters.

STEP-BY-STEP PLAN (Path B pivot):

Step 1 (30 min): Add sub-reader instrumentation.

  We already have `LokiStatelessConnect::Incoming(FBitReader&)` logging
  the full inner packet bytes (session 23). Now add:

  Option A — add a UObject::ProcessEvent hook. When ServerVerifyViewTarget
  dispatches, UE calls ProcessEvent. We can override in LokiStubPlayerController
  to log the args bytes. But this is AFTER deserialization — no help.

  Option B (RECOMMENDED) — add logging INSIDE the RPC dispatch path
  BEFORE ReceivePropertiesForRPC. This requires touching engine code OR
  finding a hook. Since we can't modify engine (Launcher install), we
  need a hook.

  Feasible hook: subclass UActorChannel and override ReceivedBunch.
  UActorChannel::ReceivedBunch is virtual (should be — check via
  UChannel.h). If virtual, we can subclass, override, and manually
  call ReadFieldHeaderAndPayload to get the sub-reader for each RPC,
  log its bytes, then delegate to Super.

  Alternative hook: modify FRepLayout at runtime. Complex.

  Simplest: fork the stub's copy of DataReplication.cpp portions
  into a Loki-side impl that we can extend with logging. Requires
  pulling in the guts of UActorChannel::ReceivedBunch which is huge.

Step 2 (15 min): Once we have sub-reader hex, decode.

  Sub-reader is a properly byte-aligned FBitReader containing exactly
  NumPayloadBits worth of param bytes. Since UE serializes structs
  byte-aligned (mostly), and FString is byte-aligned, we can decode
  visually. Look for FString pattern (int32 count + chars), FVector
  (3 floats), FRotator (3 shorts), uint32 hashes, etc.

  Try the simplest interpretation first: the payload starts with the
  FString we saw (`/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass`),
  then some struct.

Step 3 (30-60 min): Add matching UFUNCTION to LokiStubPlayerController.

Step 4 (30 min): Class-name resolution problem (still open from session
21). Options remain:
- Runtime UClassRedirect
- Class-rename with CDO handling
- Register UFUNCTION on stock APlayerController at runtime (via
  UClass::CreateDefaultObject or similar hackery)

WHAT'S ALREADY BUILT (all working through PC actor spawn on client):

- Full stateless handshake + wrapper strip (sessions 17-18)
- Custom UNetConnection with LokiStatelessConnect (session 18)
- LevelName rewrite via ModifyClientTravelLevelURL (session 19)
- World package + object rename to LobbyV2 path (session 19)
- NetworkChecksumMode=None on GuidCache (session 20)
- Full inner-packet hex dump in LokiStatelessConnect::Incoming (session 23)
- Stock APlayerController as PlayerControllerClass (session 23, RE mode)
- Bit-level packet parser skeleton (session 24)

STUB SERVER LAUNCH COMMAND (from elevated PowerShell):

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose, LogNetTraffic VeryVerbose, LogRepTraffic Verbose"

Build after Loki source changes:

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client launch (elevated PowerShell, Steam running):

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

CHAPTER STATE AT END OF SESSION 24:

  - Handshake, packet handler wiring, control messages, map validation,
    Join, PC spawn, checksum bypass: ALL DONE (sessions 17-20)
  - SUPERVIVE engine mods confirmed: DONE (session 22)
  - RPC bunch bytes captured: DONE (session 23)
  - FString parameter identified: DONE (session 23)
  - Bit-level packet header parsing: PARTIAL (session 24 — header works,
    bunch stuck)
  - Full RPC parameter list identified: TODO (session 25 — pivot to
    server-side sub-reader instrumentation)
  - Add matching UFUNCTION + class-name resolution: TODO (session 25-26)
  - Menu-data replication: TODO (session 27+)

If in doubt about a step, ask the user.
