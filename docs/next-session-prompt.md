# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 31

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 31** of the chapter. Session 30 achieved a HUGE
breakthrough: the engine's `FBitReader::SetOverflowed` ensure emits a
diagnostic line that tells us EXACTLY how many bits were consumed and
where overflow happened. We now have engine-side feedback for iteration.

Session 30's trial `(AActor* NewViewTarget, FString ClientMapName)`
revealed:
- Sub-reader Max: 2298 bits (confirmed matches session-25 decode)
- AActor* NetGUID consumed exactly **50 bits**
- Need ~941 more bits between AActor* and FString to reach the target
  FString position at bit 991

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 30" at bottom)
  #   docs/session-30-actor-trial.txt   (23-line session-30 log excerpt)
  #   docs/session-25-bunch-capture.txt (raw bunch bytes)
  #   docs/session-25-bunch-decoder.py  (Python decoder)
  #   unreal-stub/Source/Loki/Loki.cpp
  #     (helpers: AppendString/Struct/Vector/Rotator/Int/Float/Byte/Object)
  #   The hero-roster-blocker memory auto-loads.

THE ENGINE DIAGNOSTIC (session 30 discovery):

When our signature is wrong, UE emits an ensure with EXACT bit counts:

    LogOutputDevice: Error: Ensure condition failed: false
        [File:Serialization/BitReader.cpp] [Line: 276]
    LogOutputDevice: Error: FBitReader::SetOverflowed() called!
        (ReadLen: N, Remaining: M, Max: 2298)

Where:
- Max = 2298 = total bit budget of the RPC sub-reader
- Remaining = M = bits left when overflow fired
- ReadLen = N = the read that overflowed (typically FString read amount)

Bits consumed by preceding params = 2298 - M.

For session 30's AActor*+FString trial: M = 2248, so first param = 50 bits.

WHAT TO TRY:

Step 1 (30 min): Iterate the middle param. We need ~941 bits between
AActor* and FString. Try in this order:

Trial A: `(AActor*, AActor*, FString)` — 50 + 50 + FString? Likely not
  enough. Watch diagnostic. Expected: Remaining = 2298 - 100 = 2198 when
  FString fails. If Remaining > 2298 - 991, param sequence is too short.

Trial B: `(AActor*, FRepMovement, FString)` — FRepMovement has custom
  NetSerialize, variable bits, typical ~150-250 bits.
  AppendStructParam(Func, "Movement", "/Script/Engine.RepMovement")

Trial C: `(AActor*, TArray<uint8> Payload, FString)` — TArray reads
  int32 count then N bytes. If count value from wire = ~113, absorbs
  32 + 113*8 = 936 bits ≈ close to 941.
  Need to add AppendArrayParam helper (FArrayProperty of FByteProperty).

Trial D: `(AActor*, int32, int32, ..., int32, FString)` — N int32s
  totaling 941 bits: 941/32 = 29.4, so 29 int32 (928 bits) + a few more.

Watch the diagnostic each iteration:
- Remaining ≥ 2298 - 991 → we haven't reached bit 991 yet, ADD more params
- Remaining < 2298 - 991 → we've passed bit 991, REMOVE some params
- No overflow → we found it! Look for "Received RPC:" log line.

Step 2 (30 min): Add FArrayProperty helper. UE FArrayProperty needs
Inner property set:

```cpp
static void AppendUInt8ArrayParam(UFunction* Func, const TCHAR* Name)
{
    FArrayProperty* Prop = new FArrayProperty(Func, FName(Name),
                                               RF_Public | RF_Transient);
    Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor;
    Prop->ArrayDim = 1;
    // Set Inner property
    FByteProperty* Inner = new FByteProperty(Prop, FName("Inner"),
                                              RF_Public | RF_Transient);
    Inner->PropertyFlags = CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
    Inner->ArrayDim = 1;
    Prop->Inner = Inner;
    AppendToChildProperties(Func, Prop);
}
```

Step 3 (analytical): Once we know exactly where FString goes, we still
need TAIL params (899 bits after FString). Same iteration approach.

Step 4: When entire signature matches, log will show:
- No SetOverflowed ensure
- No "Reader.IsError" from ReceivedRPC
- Possibly `LogRepTraffic: Received RPC: ServerVerifyViewTarget`

Then connection should proceed to Whatever's next!

WHAT'S ALREADY BUILT (all working):

- Sessions 17-29 infrastructure — DO NOT TOUCH
- Session 30 FObjectProperty helper — KEEP
- Session 30 discovered engine diagnostic — LEVERAGE for iteration

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

FEEDBACK LOOP (each iteration):

1. Modify the AppendXxx sequence in InjectServerVerifyViewTargetFStringParam
2. Rebuild (~5s)
3. Launch stub + ags + client (~30s)
4. Wait for the ChIndex=3 bunch to arrive
5. Grep for "FBitReader::SetOverflowed" — read Remaining value
6. Compute bits_consumed = 2298 - Remaining
7. Compare with target 991 (position of FString)
8. Adjust signature; repeat.

CHAPTER STATE AT END OF SESSION 30:

- Everything through PC spawn: DONE
- Bunch bytes captured (2298 bits): DONE
- Runtime UFunction injection (multiple types): DONE
- Engine-side bit-count diagnostic: DISCOVERED (session 30)
- AActor* NetGUID = 50 bits: MEASURED (session 30)
- Middle-param signature (~941 bits): TODO (session 31)
- Tail-param signature (~899 bits after FString): TODO
- Menu-data replication: TODO (session 32+)

If in doubt, ask the user.
