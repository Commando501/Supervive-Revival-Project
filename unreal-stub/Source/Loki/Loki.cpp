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

    // Session 27: bypass UHT's UFUNCTION-override-parity constraint by
    // constructing an FStrProperty at runtime and appending it to the existing
    // APlayerController::ServerVerifyViewTarget UFunction's ChildProperties
    // list. Then re-link so UE's RepLayout picks up the new signature.
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

        const int32 OriginalNumProps = Func->NumParms;
        const int32 OriginalPropsSize = Func->ParmsSize;
        UE_LOG(LogLokiStub, Display,
               TEXT("InjectServerVerifyViewTarget: found UFunction on APlayerController "
                    "(NumParms=%d, ParmsSize=%d, FunctionFlags=0x%08X)"),
               OriginalNumProps, OriginalPropsSize, (uint32)Func->FunctionFlags);

        // Construct an FStrProperty as the new parameter. The property's outer
        // is the UFunction itself so it participates in normal FField ownership.
        FStrProperty* NewProp = new FStrProperty(Func,
            FName(TEXT("ClientMapName")), RF_Public | RF_Transient);
        NewProp->PropertyFlags = CPF_Parm | CPF_ConstParm | CPF_ReferenceParm
                               | CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
        NewProp->ArrayDim = 1;

        // Append to ChildProperties linked list (tail append). Existing UFunction
        // might already have some children; we want the FString AFTER them.
        FField** Tail = &Func->ChildProperties;
        while (*Tail)
        {
            Tail = &(*Tail)->Next;
        }
        *Tail = NewProp;

        // StaticLink recomputes ParmsSize, PropertyLink chain, ReturnValueOffset,
        // and MinAlignment. Pass bRelinkExistingProperties=true so the parent's
        // properties are relinked too.
        Func->StaticLink(true);

        // Bind() (re-)computes the native function pointer. Since we're not
        // changing the native impl, keep the existing binding.

        // Clear the class net cache so RepLayout regenerates with the new
        // parameter list. Without this, the cached FClassNetCache would still
        // show 0 args.
        PCClass->ClearFunctionMapsCaches();

        UE_LOG(LogLokiStub, Display,
               TEXT("InjectServerVerifyViewTarget: added FStrProperty ClientMapName. "
                    "New NumParms=%d, ParmsSize=%d"),
               Func->NumParms, Func->ParmsSize);
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FLokiModule, Loki, "Loki");
