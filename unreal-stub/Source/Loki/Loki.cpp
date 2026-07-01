// Loki module implementation — declares this as the project's primary game
// module so the engine can find an entry point at server startup.
//
// Session 10: NetCL override. Session 9 proved the SUPERVIVE client
// successfully sends UDP handshake packets to the stub server, but the
// StatelessConnect handshake parser rejected them with
// "IncomingConnectionless: Error reading handshake packet" because the
// server's network checksum (derived from UE5.4.4's NetCL=33043543) differs
// from the client's (derived from NetCL=0). The fix: override both the
// LocalNetworkVersion (so the server REPORTS the same checksum the client
// reports) AND the IsNetworkCompatible check (belt-and-suspenders permissive
// fallback). The client's captured checksum is 3716198887 (from session 5's
// v10 hook capture of LogNetVersion: "NetCL: 0, EngineNetworkVersion: 34,
// GameNetworkVersion: 0 (Checksum: 3716198887)").

#include "Loki.h"
#include "Modules/ModuleManager.h"
#include "Misc/NetworkVersion.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "UObject/Class.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#include "UObject/FieldPathProperty.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStub, Log, All);

// Session 19 blocker (session 18 unblocked stateless handshake, session 19
// unblocked NMT_Welcome/Login/Join via LokiGameInstance::ModifyClientTravelLevelURL,
// but the client's actor channel for the server-spawned PlayerController fails
// because the actor's outer package resolves as /Engine/Maps/Entry.Entry which
// doesn't exist in the client's cooked shipping build). Fix attempt: rename our
// stub's game world package at post-init to the map path the client expects.
static const FString kLokiExpectedWorldPackage =
    TEXT("/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent");

// Captured from the SUPERVIVE client at LobbyV2 browse — the network
// checksum the client computes for itself and expects to match. Composed
// of NetCL=0 + EngineNetworkVersion=34 + GameNetworkVersion=0 + project
// "Loki 1.0.0.0". By overriding the server's locally computed version
// with this exact value, the StatelessConnect handshake's checksum
// comparison succeeds.
static constexpr uint32 kLokiClientNetworkChecksum = 3716198887U;

class FLokiModule : public FDefaultGameModuleImpl
{
public:
    virtual void StartupModule() override
    {
        FDefaultGameModuleImpl::StartupModule();

        // Force the local network version (which is what gets reported in
        // the StatelessConnect handshake) to the client's captured checksum.
        FNetworkVersion::GetLocalNetworkVersionOverride.BindStatic(
            &FLokiModule::GetLocalNetworkVersion);

        // Belt-and-suspenders: also accept any remote version. This catches
        // future client builds that may compute a different checksum, and
        // makes the handshake more forgiving during recon iterations.
        FNetworkVersion::IsNetworkCompatibleOverride.BindStatic(
            &FLokiModule::IsNetworkCompatible);

        // Force a rehash on next handshake to pick up our override.
        FNetworkVersion::InvalidateNetworkChecksum();

        UE_LOG(LogLokiStub, Display,
               TEXT("Loki stub: NetCL overrides bound. Local checksum forced to %u; "
                    "IsNetworkCompatible accepts any remote."),
               kLokiClientNetworkChecksum);

        // Session 19: rename the game world's outer package so replicated actors
        // (PlayerController especially) reference a package path the client has
        // cooked. Without this, the client's ActorChannel fails on the PC because
        // /Engine/Maps/Entry.Entry doesn't exist in the shipping client.
        WorldInitHandle = FWorldDelegates::OnPostWorldInitialization.AddStatic(
            &FLokiModule::OnPostWorldInitialization);

        // Session 27: inject a modified ServerVerifyViewTarget signature onto
        // stock APlayerController. Session 25 decoded that the RPC arg struct is
        // 2298 bits containing an FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass".
        // Stock UE's ServerVerifyViewTarget takes 0 args → mismatch. Session 26
        // proved subclass UFUNCTION override with different params is UHT-rejected.
        // Session 27 approach: add an FStrProperty to the existing stock UFunction's
        // ChildProperties list and re-link, so deserialization consumes the FString.
        //
        // Runs from OnPostEngineInit so APlayerController's UClass is fully loaded.
        PostEngineInitHandle = FCoreDelegates::OnPostEngineInit.AddStatic(
            &FLokiModule::InjectServerVerifyViewTargetFStringParam);
    }

    virtual void ShutdownModule() override
    {
        FNetworkVersion::GetLocalNetworkVersionOverride.Unbind();
        FNetworkVersion::IsNetworkCompatibleOverride.Unbind();
        FWorldDelegates::OnPostWorldInitialization.Remove(WorldInitHandle);
        FCoreDelegates::OnPostEngineInit.Remove(PostEngineInitHandle);
        FDefaultGameModuleImpl::ShutdownModule();
    }

private:
    static uint32 GetLocalNetworkVersion()
    {
        return kLokiClientNetworkChecksum;
    }

    static bool IsNetworkCompatible(uint32 LocalVersion, uint32 RemoteVersion)
    {
        UE_LOG(LogLokiStub, Verbose,
               TEXT("IsNetworkCompatible(local=%u, remote=%u) -> true (override)"),
               LocalVersion, RemoteVersion);
        return true;
    }

    static void OnPostWorldInitialization(UWorld* World, const UWorld::InitializationValues)
    {
        if (!World || !World->IsGameWorld())
        {
            return;
        }
        UPackage* Pkg = World->GetOutermost();
        if (!Pkg)
        {
            return;
        }
        const FString OldPkgName = Pkg->GetName();
        if (OldPkgName != kLokiExpectedWorldPackage)
        {
            UE_LOG(LogLokiStub, Display,
                   TEXT("Renaming game world package: %s -> %s"),
                   *OldPkgName, *kLokiExpectedWorldPackage);
            Pkg->Rename(*kLokiExpectedWorldPackage, nullptr,
                        REN_ForceNoResetLoaders | REN_DoNotDirty | REN_DontCreateRedirectors);
        }

        // Also rename the world object inside the package so replicated actor
        // paths look like /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.LVL_LobbyV2_Persistent:PersistentLevel.PC
        // instead of ...LVL_LobbyV2_Persistent.Entry:PersistentLevel.PC. The
        // client's cooked package has ONE world object whose name matches the
        // package basename, so its ActorChannel resolver expects the same shape.
        const FString ExpectedWorldName = TEXT("LVL_LobbyV2_Persistent");
        const FString OldWorldName = World->GetName();
        if (OldWorldName != ExpectedWorldName)
        {
            UE_LOG(LogLokiStub, Display,
                   TEXT("Renaming world object: %s -> %s"),
                   *OldWorldName, *ExpectedWorldName);
            World->Rename(*ExpectedWorldName, Pkg,
                          REN_ForceNoResetLoaders | REN_DoNotDirty | REN_DontCreateRedirectors);
        }
    }

    FDelegateHandle WorldInitHandle;
    FDelegateHandle PostEngineInitHandle;

    // Session 27-28: bypass UHT's UFUNCTION-override-parity constraint by
    // constructing FProperties at runtime and appending them to the existing
    // APlayerController::ServerVerifyViewTarget UFunction's ChildProperties
    // list. Then re-link so UE's RepLayout picks up the new signature.
    //
    // Session 28 goal: iterate parameter orderings until Reader.GetBitsLeft()
    // == 0 and no Reader.IsError. Session 25 established the RPC arg struct
    // is 2298 bits containing FString "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass"
    // at bit 991 (byte-aligned in raw bunch).
    //
    // Signature trial for session 28: (TArray<uint8> Preamble, FString MapName)
    //   - TArray reads int32 count + count*8 bits of data
    //   - Then FString at whatever bit position remains
    // If the first 32 bits happen to be a reasonable count value that ends
    // the TArray near bit 991, then FString will land at the right spot.
    // Otherwise we'll see IsError or Mismatch, telling us to try a different
    // combination.
    //
    // First 32 bits of payload = 0x05C6000B = 96862219 (unreasonably big for
    // TArray count). So TArray<uint8> first isn't going to work as-is.
    // Trying (FString, ..., FString) or (FVector, FRotator, FString, ...) next.
    static void InjectServerVerifyViewTargetFStringParam()
    {
        UClass* PCClass = APlayerController::StaticClass();
        if (!PCClass)
        {
            UE_LOG(LogLokiStub, Warning,
                   TEXT("InjectServerVerifyViewTarget: APlayerController class not found"));
            return;
        }

        UFunction* Func = PCClass->FindFunctionByName(
            FName(TEXT("ServerVerifyViewTarget")),
            EIncludeSuperFlag::ExcludeSuper);
        if (!Func)
        {
            UE_LOG(LogLokiStub, Warning,
                   TEXT("InjectServerVerifyViewTarget: ServerVerifyViewTarget UFunction not "
                        "found on APlayerController"));
            return;
        }

        UE_LOG(LogLokiStub, Display,
               TEXT("InjectServerVerifyViewTarget: found UFunction on APlayerController "
                    "(NumParms=%d, ParmsSize=%d, FunctionFlags=0x%08X)"),
               Func->NumParms, Func->ParmsSize, (uint32)Func->FunctionFlags);

        // Signature trial: (FVector Location, FRotator Rotation, FString MapName)
        // Rationale: common anti-cheat "verify view target" pattern is
        // (camera position, camera rotation, current view target name).
        // 96 + 96 + 32 + N*8 bits = 224 + 408 (for our 46-char string+null) = 632 bits.
        // Total 2298 bits - 632 = 1666 bits still unconsumed. But this gets us
        // FString-consumption at bit 224, and if IsError fires we know the
        // structure has DIFFERENT prefix.
        AppendVectorParam(Func, TEXT("CameraLocation"));
        AppendRotatorParam(Func, TEXT("CameraRotation"));
        AppendStringParam(Func, TEXT("ClientMapName"));

        Func->StaticLink(true);
        PCClass->ClearFunctionMapsCaches();

        UE_LOG(LogLokiStub, Display,
               TEXT("InjectServerVerifyViewTarget: added FVector+FRotator+FString params. "
                    "New NumParms=%d, ParmsSize=%d"),
               Func->NumParms, Func->ParmsSize);
    }

    // Helper: append an FStrProperty to a UFunction's ChildProperties tail.
    static void AppendStringParam(UFunction* Func, const TCHAR* Name)
    {
        FStrProperty* Prop = new FStrProperty(Func, FName(Name), RF_Public | RF_Transient);
        Prop->PropertyFlags = CPF_Parm | CPF_ConstParm | CPF_ReferenceParm
                            | CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    // Helper: append an FStructProperty referencing a UScriptStruct by path.
    static void AppendStructParam(UFunction* Func, const TCHAR* Name,
                                  const TCHAR* StructPath)
    {
        UScriptStruct* Struct = FindObject<UScriptStruct>(nullptr, StructPath);
        if (!Struct)
        {
            UE_LOG(LogLokiStub, Warning,
                   TEXT("AppendStructParam: UScriptStruct not found at %s"), StructPath);
            return;
        }
        FStructProperty* Prop = new FStructProperty(Func, FName(Name), RF_Public | RF_Transient);
        Prop->Struct = Struct;
        Prop->PropertyFlags = CPF_Parm | CPF_ConstParm | CPF_ReferenceParm
                            | CPF_ZeroConstructor | CPF_NoDestructor;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    static void AppendVectorParam(UFunction* Func, const TCHAR* Name)
    {
        AppendStructParam(Func, Name, TEXT("/Script/CoreUObject.Vector"));
    }

    static void AppendRotatorParam(UFunction* Func, const TCHAR* Name)
    {
        AppendStructParam(Func, Name, TEXT("/Script/CoreUObject.Rotator"));
    }

    // Tail-append to a UFunction's ChildProperties linked list.
    static void AppendToChildProperties(UFunction* Func, FField* Prop)
    {
        FField** Tail = &Func->ChildProperties;
        while (*Tail)
        {
            Tail = &(*Tail)->Next;
        }
        *Tail = Prop;
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FLokiModule, Loki, "Loki");
