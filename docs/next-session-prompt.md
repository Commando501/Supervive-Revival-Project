# Next session prompt — SUPERVIVE Revival dedicated-server stub, session 30

Paste the section between the `---` lines below as the first message.

---

We're continuing the SUPERVIVE Revival dedicated-server-stub chapter on
branch `dedicated-server-stub` at `G:\git\Supervive Revival Project`.
This is **session 30** of the chapter. Session 29 analytically ruled out
plain scalar types (FVector, FRotator, FQuat as 3-4 floats) as the first
RPC param — their bit-level interpretations produce impossible values
like 1e+27. Bit 0 = 1 is consistent with FVector_NetQuantize OR NetGUID.
Session 29's trial (FVector_NetQuantize100, int32, FString) also failed
with Reader.IsError.

Session 30: try FObjectProperty (Actor pointer) or a specific
SUPERVIVE-Loki-USTRUCT.

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -10
  # Then read:
  #   docs/dedicated-server-stub.md   (jump to "Session 29" at bottom)
  #   docs/session-29-trials.txt      (session 29 log + summary)
  #   docs/session-25-bunch-capture.txt   (raw RPC bunch bytes)
  #   docs/session-25-bunch-decoder.py    (Python decoder)
  #   docs/session-22-schema-actor-loki-mods.txt  (SUPERVIVE-added props)
  #   unreal-stub/Source/Loki/Loki.cpp
  #     (has InjectServerVerifyViewTargetFStringParam +
  #      AppendString/Struct/Vector/Rotator/Int/Float/Byte helpers)
  #   schema.txt (repo root, ~71k lines — search for USTRUCTs that might
  #     be first param)
  #   The hero-roster-blocker memory auto-loads.

WHAT WE KNOW:

- RPC arg struct = 2298 bits
- FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass" at bit 991
- First 32 bits = 0x05C6000B (int32) — not FString count, not float
- First 96 bits as FVector: impossible coordinates
- Bit 0 = 1 (non-zero-vector flag or NetGUID valid flag)
- **Confirmed: first param is variable-bit-encoded** (NetSerialize custom
  struct OR FObjectProperty NetGUID)

STEP-BY-STEP PLAN:

Step 1 (30 min): Add FObjectProperty helper to Loki.cpp:

```cpp
static void AppendObjectParam(UFunction* Func, const TCHAR* Name,
                              UClass* PropertyClass)
{
    FObjectProperty* Prop = new FObjectProperty(Func, FName(Name),
                                                 RF_Public | RF_Transient);
    Prop->PropertyClass = PropertyClass;
    Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor;
    Prop->ArrayDim = 1;
    AppendToChildProperties(Func, Prop);
}
```

Then trial: `(AActor* NewViewTarget, FString ClientMapName)`.

If IsError persists but changes byte offset, we may be closer.

Step 2 (30 min): Explore SUPERVIVE-Loki USTRUCTs from schema.txt. Grep
for likely first-param structs:

```
grep -E "^  LokiViewTarget|^  LokiCameraInfo|^  Loki.*Verify|
        ^  LokiPlayerState" schema.txt | head -20
```

Any struct with 6-15 fields and a mix of scalars is a candidate. Try
`AppendStructParam(Func, ..., "/Script/Loki.LokiXxxxxx")`.

Step 3 (60 min): Python offline signature-matcher. Write
`scratchpad/decode_bunch_v3.py`:
- Load captured bunch bytes (docs/session-25-bunch-capture.txt)
- Extract RPC payload bit stream (2298 bits starting at bit 41)
- For each SIGNATURE CANDIDATE (list of param types + bit lengths):
  - Simulate FRepLayout::ReceivePropertiesForRPC reading
  - Check if all bits consumed AND intermediate values plausible
  - Emit "candidate: X params, N bits consumed, sanity check pass/fail"

Signatures to try:
- (FObjectProperty[Actor], FString): ~30 bits NetGUID + 32+N*8 FString
- (FUniqueNetIdRepl, FVector_NetQuantize100, FString): ~50+100+FString
- (SUPERVIVE-Loki-USTRUCT, FString): unknown struct bits + FString
- Many-scalar combos: (int32, float, int32, float, ..., FString)

Step 4: Debugger route (fallback). Attach Visual Studio to LokiEditor,
set breakpoint at `FRepLayout::ReceivePropertiesForRPC` in
RepLayout.cpp:6972. Watch Reader.GetPosBits() before/after each property
read. This tells us EXACTLY where FString read begins and what property
type matches SUPERVIVE's first param.

WHAT'S ALREADY BUILT (all working):

- Sessions 17-28 infrastructure — DO NOT TOUCH:
  * All engine overrides (session 17-20)
  * Bunch hex dumps (session 23, 25)
  * UFunction injection hook + helpers (session 27-29)

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

CHAPTER STATE AT END OF SESSION 29:

- Everything through PC spawn: DONE
- Bunch bytes captured + decoded (2298 bits): DONE
- Runtime UFunction injection: DONE
- Plain scalar first-param types: RULED OUT (session 29)
- Variable-bit type identified: TODO (session 30 — Actor* / NetGUID
  / Loki struct)
- Menu-data replication: TODO (session 31+)

If in doubt about a step, ask the user.
