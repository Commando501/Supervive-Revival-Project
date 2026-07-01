# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 27

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 27** of the chapter. Session 26 discovered UE's UHT
enforces UFUNCTION parameter parity across override — meaning we CAN'T
just add a differently-parametered `ServerVerifyViewTarget` UFUNCTION to
a subclass of APlayerController. Session 27 needs to bypass UHT via
runtime UClass function-table manipulation.

Session 25 has confirmed the RPC arg struct is **2298 bits (287.25 bytes)**
starting at bit 41 of the bunch, containing at least an FString
`/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass` (408 bits) plus ~1890
bits of additional parameters.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 26" at bottom)
  #   docs/session-25-bunch-capture.txt  (18 lines — the bunch bytes)
  #   docs/session-25-bunch-decoder.py   (212 lines — Python decoder)
  #   unreal-stub/Source/Loki/LokiStubPlayerController.h + .cpp  (has
  #     the session-26 comment explaining the UHT constraint)
  #   H:\Unreal Engine\UE_5.4\Engine\Source\Runtime\CoreUObject\Public\UObject\Class.h
  #     — UClass::AddFunctionToFunctionMap, UClass::CreateNetFunctions
  #     — UFunction::Bind, UFunction::Link
  #     — how to construct a UFunction at runtime with an arbitrary
  #       property list
  #   The hero-roster-blocker memory auto-loads.

THE PATH FORWARD:

Session 26 dead-end confirmed: subclass UFUNCTION override with different
parameters is impossible via UHT. UE forces param parity.

But we CAN construct a UFunction at runtime with any signature we want
and inject it into an existing UClass's FuncMap. UE Blueprint compiler
does this all the time. See UBlueprintFunctionLibrary in UE source, or
`UEdGraphNode_Reference::CreateAndInjectFunction`.

BROAD APPROACH:

Step 1 (60 min): Research the exact API to inject a UFunction at runtime.
Look at:
- UClass::AddFunctionToFunctionMap
- UFunction::Bind
- UClass::CreateDefaultObject
- Class registration flow in UObject::CreateNativeFunction

Ideally, in FLokiModule::StartupModule:
```cpp
UClass* PCClass = APlayerController::StaticClass();
UFunction* OldFunc = PCClass->FindFunctionByName("ServerVerifyViewTarget");
UFunction* NewFunc = NewObject<UFunction>(PCClass, "ServerVerifyViewTarget", RF_Public);
// Set up NewFunc's Children linked list with FStringProperty etc.
NewFunc->FunctionFlags = FUNC_Net | FUNC_NetServer | FUNC_NetValidate | FUNC_NetReliable;
NewFunc->Bind();
NewFunc->StaticLink(true);
PCClass->AddFunctionToFunctionMap(NewFunc);
PCClass->ClassNetCacheMgr->ClearClassNetCache(PCClass); // invalidate cache
```

Step 2 (30 min): Author a matching signature. We know the arg struct is
2298 bits. Try:
- `void ServerVerifyViewTarget(FString ClientMapName)` — 408 bits ≠ 2298
- Add FVector, FRotator, etc. until 2298 exactly

Or a big struct-based approach:
- Define a USTRUCT containing (FString, FVector, FRotator, ...)
- Register the RPC as taking this struct

Step 3 (test iterate): Test end-to-end. Watch stub log for
`Reader.GetBitsLeft()` — every mismatch tells us how many bits are still
unconsumed. Iterate on signature until 0.

Step 4 (30 min): Also solve the class-name issue if using subclass.
Options same as session 21/25:
- Client cannot resolve /Script/Loki.LokiStubPlayerController → ActorChannelFailure
- Stick with stock APlayerController and inject into ITS FuncMap directly
- Rename LokiStubPlayerController's UClass path via UPackage::Rename

Recommended: inject into stock APlayerController::StaticClass()'s FuncMap.
No subclass needed; no class-name resolution issue.

WHAT'S ALREADY BUILT (all working):

- Full stateless handshake + wrapper strip (sessions 17-18)
- Custom UNetConnection with LokiStatelessConnect (session 18)
- LevelName rewrite via ModifyClientTravelLevelURL (session 19)
- World package + object rename (session 19)
- NetworkChecksumMode=None (session 20)
- LokiStubGameMode + LokiStubPlayerController (session 21)
- Full inner-packet hex dump in LokiStatelessConnect::Incoming (session 23)
- LokiActorChannel per-bunch hex dump (session 25)
- Bunch bit-level decoder confirming 2298-bit RPC struct with FString (session 25)
- UHT-constraint confirmed (session 26)

STUB LAUNCH COMMAND:

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
  * Session-23 hex dump in LokiStatelessConnect::Incoming
  * Session-25 LokiActorChannel hex dump + ChannelDefinitions config
- Do NOT re-attempt subclass UFUNCTION override with different params
  (session 26 established UHT rejects it).

CHAPTER STATE AT END OF SESSION 26:

- Everything through PC spawn: DONE
- SUPERVIVE engine mods confirmed: DONE
- RPC bunch bytes captured + decoded: DONE
- Bunch content-block + field header decoded: DONE
- RPC arg struct isolated (2298 bits, FString + ~236 more bytes): DONE
- UFUNCTION subclass override strategy: DEAD-END (session 26)
- Runtime UClass function-table injection: TODO (session 27 — this session)
- Full RPC parameter list: TODO
- Menu-data replication: TODO

If in doubt about a step, ask the user.
