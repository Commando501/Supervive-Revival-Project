# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 28

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 28** of the chapter. Session 27 achieved TWO
architectural wins:

1. **UFunction runtime injection WORKS** — we can modify stock
   APlayerController's UFunction signature at runtime by appending
   FProperties to ChildProperties and calling StaticLink(true).
2. **Class-name resolution problem BYPASSED** — no more session-21
   hard wall, no subclass needed.

Session 27's test: injected a single FStrProperty. UE's error changed
from "Mismatch read" (Reader.GetBitsLeft()!=0) to "Reader.IsError()"
(overflow). Confirms UE's RepLayout picked up our new signature. But
FString is NOT the first param — session 25's decode showed 991 bits
of preceding params in the 2298-bit RPC struct.

Session 28's job: **iterate param orderings until Reader.GetBitsLeft() = 0**.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 27" at bottom)
  #   docs/session-27-injection-test.txt  (17 lines — injection log)
  #   unreal-stub/Source/Loki/Loki.cpp  (has the injector — see
  #     FLokiModule::InjectServerVerifyViewTargetFStringParam)
  #   docs/session-25-bunch-capture.txt  (the raw bunch bytes)
  #   docs/session-25-bunch-decoder.py   (Python decoder)
  #   The hero-roster-blocker memory auto-loads.

WHAT WE KNOW:

- RPC arg struct = 2298 bits starting at bit 41 of the bunch
- Contains FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass" at
  bunch bit 1032 (= RPC-struct bit 991)
- Preceding params: 991 bits worth
- Trailing params: 899 bits worth
- Total: 991 + 408 (FString) + 899 = 2298 ✓

WHAT TO TRY:

Step 1: Generalize the injector. Rename
`InjectServerVerifyViewTargetFStringParam` to
`InjectServerVerifyViewTargetSignature` and support ADDING multiple
FProperty types in order:
- FStrProperty (FString) — 32 + N*8 bits (N chars incl null)
- FStructProperty for FVector, FRotator — need to look up matching UScriptStruct
- FArrayProperty for TArray<uint8> — 32 bits count + N*8 chars
- FIntProperty, FFloatProperty, FBoolProperty for scalars

Step 2: Trial signatures. Watch stub log for `Reader.IsError()` vs
`Mismatch read`:
- `Mismatch read` with leftover count means we consumed too few bits
- `Reader.IsError()` means we tried to read more bits than available

The GOAL is: neither error, meaning all bits consumed exactly.

Trial ideas in order of likelihood:
1. `(FVector, FRotator, FString)` — 96+96+408 = 600 bits (still < 2298)
2. `(FVector, FRotator, FString, FVector, FRotator, ...)` — see how the
   pattern extends
3. `(FVector Location, FRotator Rotation, float Timestamp, int32 Hash,
   FString MapName, TArray<uint8> Signature)` — mixed
4. `(TArray<uint8> AntiCheatBlob, FString MapName, TArray<uint8> Sig2)`
   — variable-size blobs before/after FString

Anti-cheat patterns:
- BattlEye/EAC verify-view-target payloads often contain:
  - Client view position (FVector or FVector_NetQuantize)
  - Client view rotation (FRotator or FQuat)
  - Server time (float or double)
  - Client-computed hash of critical state (uint32 or FMD5Hash)
  - Anti-cheat signature/token (byte array)
  - Current gameplay context (map name, game mode name)

Step 3: Since FString is at bit 991 (= 123.875 bytes into RPC struct),
whatever comes before totals 991 bits. Since 991 is odd, it's a
non-byte-aligned sequence of bit-level params. Look for combinations
that sum to 991 bits.

If assuming byte-aligned params: 991 doesn't fit. So some param is
bit-packed (like FBool = 1 bit, FQuat_NetQuantize = 24 bits, etc.).

Step 4: Also solve TRAILING 899 bits. Similar iterate.

WHAT'S ALREADY BUILT (all working):

- Everything through PC spawn: sessions 17-20
- SUPERVIVE engine mods confirmed via schema extract: session 22
- Full inner-packet hex dump in LokiStatelessConnect::Incoming: session 23
- Per-bunch hex dump in LokiActorChannel: session 25
- Bunch decoder Python + 2298-bit isolation: session 25
- UHT parity constraint confirmed: session 26
- Runtime UFunction injection working: session 27
- FStrProperty successfully appended, StaticLink recomputes ParmsSize: session 27

STUB LAUNCH:

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose, LogNetTraffic VeryVerbose, LogLokiActorChannel Verbose, LogRep VeryVerbose"

Build:

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client:

    cd "G:\git\Supervive Revival Project"
    .\configs\launch-redirect.ps1 -Hook ".\tools\sigbypass-mod\browse_hook.dll"

GUARDRAILS:

- Branch `dedicated-server-stub`. Commit + push each meaningful step.
- Steam running before game launch.
- browse_hook v13 small crash rate; retry.
- Do NOT touch:
  * Session 17: bDisableOutgoingWrap in LokiNetDriver::LowLevelSend
  * Session 19: World/package rename in Loki.cpp
  * Session 20: NetworkChecksumMode=None in LokiNetDriver::InitBase
  * Session 23: hex dump in LokiStatelessConnect::Incoming
  * Session 25: LokiActorChannel + ChannelDefinitions config
  * Session 27: FCoreDelegates::OnPostEngineInit hook for UFunction
    injection

CHAPTER STATE AT END OF SESSION 27:

- Everything through PC spawn: DONE
- Bunch bytes captured + decoded: DONE
- Runtime UFunction injection working: DONE
- Class-name resolution: BYPASSED
- Full RPC parameter list: TODO (session 28 — trial signatures)
- Menu-data replication: TODO (session 29+)

If in doubt about a step, ask the user.
