# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 29

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 29** of the chapter. Session 27 proved runtime UFunction
injection works. Session 28 generalized the injector with helpers for
FStrProperty, FStructProperty, FVector, FRotator. First multi-param trial
`(FVector, FRotator, FString)` still failed with Reader.IsError() — the
first 32 bits of RPC payload (0x05C6000B) don't fit FVector.X.

Today: expand injector helpers, iterate signatures more systematically,
consider that SUPERVIVE's RPC may use a Loki-specific USTRUCT.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 28" at bottom)
  #   docs/session-28-injection-trial.txt  (21-line trial log)
  #   docs/session-25-bunch-capture.txt  (raw RPC bunch bytes)
  #   docs/session-25-bunch-decoder.py   (Python bunch decoder)
  #   unreal-stub/Source/Loki/Loki.cpp
  #     (has InjectServerVerifyViewTargetFStringParam +
  #      AppendStringParam/AppendStructParam/AppendVectorParam helpers)
  #   docs/session-22-schema-actor-loki-mods.txt  (SUPERVIVE-added
  #      AActor props — could hint at custom struct types)
  #   The hero-roster-blocker memory auto-loads.

WHAT WE KNOW:

- RPC arg struct = 2298 bits (session 25)
- First 32 bits = 0x05C6000B = 96862219 (int32) — not a plausible FString
  count, FVector.X, or int32 hash
- FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass" at bit 991
- Session 28 confirmed first param is NOT FVector (would need X ≈ 0)
- Tried: `FString` (session 27), `(FVector, FRotator, FString)` (session 28)
  — both IsError

STEP-BY-STEP PLAN:

Step 1 (30 min): Expand injector helper coverage. Add:
```cpp
static void AppendByteParam(UFunction*, const TCHAR*);           // FByteProperty
static void AppendIntParam(UFunction*, const TCHAR*);            // FIntProperty
static void AppendUInt32Param(UFunction*, const TCHAR*);         // FUInt32Property
static void AppendFloatParam(UFunction*, const TCHAR*);          // FFloatProperty
static void AppendBoolParam(UFunction*, const TCHAR*);           // FBoolProperty (1-bit)
static void AppendUInt8ArrayParam(UFunction*, const TCHAR*);     // FArrayProperty(FByteProperty)
static void AppendNameParam(UFunction*, const TCHAR*);           // FNameProperty
```

Step 2 (60 min): Systematic trial matrix. Add a debug CVar or config
option to select which signature to test, then rebuild+launch:

Trials to try:
- `(TArray<uint8> Data, FString MapName)` — TArray absorbs 991 bits
  minus 32 (count) = 959 bits. But 959/8 = 119.875 (not integer). Fails.
- `(FVector_NetQuantize100, FVector_NetQuantize100, FString)` — variable
  bit encoding, might land at 991
- `(FQuat, FVector_NetQuantize100, FString)` — quaternion + position
- `(FString First, ..., FString ClientMapName)` — maybe first param
  is another FString with N=? Compute N: 32 + N*8 = 991 → N = 119.875. Nope.
- `(int32, int32, FVector, FRotator, FString)` — 32+32+96+96+... = 256+
- `(FRepMovement, FString)` — FRepMovement has NetSerialize; may match

Step 3 (30 min): Look at SUPERVIVE-specific USTRUCTs from
`docs/session-22-schema-actor-loki-mods.txt`:
- `LokiReplicationStrategy` (5 fields: enum + 4 bools)
- `PoolableActorServerState` (2 fields)

Check if any of these match. Look up their FBitReader consumption via
extracted schema.txt (in repo root, ~71k lines).

Step 4 (analytical): Since 991 mod 8 = 7, ONE preceding param must
contribute an odd bit count. Candidates:
- FBoolProperty: 1 bit
- Bit-packed struct member
- FVector_NetQuantize with variable bits

For example, `(FBool, FVector, FRotator, FVector, FRotator, ..., FString)`:
1 + N*96 + 32 + M*8 = 991
N=6, M=54: 1 + 576 + 32 + 432 = 1041 (no)
N=5, M=66: 1 + 480 + 32 + 528 = 1041 (no)

Actually 991 - 1 (bool) = 990. 990 / 96 = 10.3 → not clean.

Trial with `(FBool, FString)`:
1 + 32 + N*8 = 991 → N*8 = 958 → N = 119.75. Nope.

None of my back-of-envelope combos work. May need to actually match
SUPERVIVE's custom USTRUCT.

WHAT'S ALREADY BUILT:

- All sessions 17-27 infrastructure — DO NOT TOUCH:
  * bDisableOutgoingWrap in LokiNetDriver::LowLevelSend (session 17)
  * World/package rename in Loki.cpp (session 19)
  * NetworkChecksumMode=None in LokiNetDriver::InitBase (session 20)
  * Session-23 hex dump in LokiStatelessConnect::Incoming
  * Session-25 LokiActorChannel + ChannelDefinitions
  * Session-27 FCoreDelegates::OnPostEngineInit hook for UFunction injection
  * Session-28 generalized injector helpers in Loki.cpp

STUB LAUNCH:

    Stop-Process -Name UnrealEditor-Cmd -Force -ErrorAction SilentlyContinue
    & 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        '/Engine/Maps/Entry?listen' -game -server -log -Port=7777 `
        -nullrhi -NoSplash -Unattended `
        -LogCmds="LogHandshake Verbose, LogNet Verbose, LogLokiNet Verbose, LogLokiStateless Verbose, LogLokiIpConnection Verbose, LogLokiGameInstance Verbose, LogLokiStub Verbose, LogLokiStubGM Verbose, LogLokiStubPC Verbose, LogNetTraffic VeryVerbose, LogLokiActorChannel Verbose"

Build:

    & 'H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat' `
        LokiEditor Win64 Development `
        '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"' `
        -WaitMutex

Client:

    cd "G:\git\Supervive Revival Project"
    .\configs\launch-redirect.ps1 -Hook ".\tools\sigbypass-mod\browse_hook.dll"

GUARDRAILS:

- Steam must be running.
- browse_hook v13 crash rate ~10%; retry on crash.
- Branch `dedicated-server-stub`; commit each meaningful step.

CHAPTER STATE AT END OF SESSION 28:

- Everything through PC spawn: DONE
- Bunch bytes captured + decoded (2298 bits): DONE
- Runtime UFunction injection working (single and multi-property): DONE
- FString-alone trial: IsError (session 27)
- (FVector, FRotator, FString) trial: IsError (session 28)
- Correct RPC signature: TODO (session 29 — expand helpers + more trials)
- Menu-data replication: TODO (session 30+)

If in doubt about a step, ask the user.
