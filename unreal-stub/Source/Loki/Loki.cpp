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
#include "LokiReplicatedStructs.h"
#include "Modules/ModuleManager.h"
#include "Misc/NetworkVersion.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "UObject/Class.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#include "UObject/EnumProperty.h"
#include "UObject/FieldPathProperty.h"
#include "UObject/UObjectIterator.h"
#include "HAL/IConsoleManager.h"
#include "Algo/Sort.h"
#include "Serialization/BitReader.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStub, Log, All);

// Session 41: FProperty::SetOffset_Internal is protected and only UStruct::Link
// assigns offsets. To place our runtime-injected ServerState property at a valid
// in-object offset (required by FRepLayout, which asserts replicated-property
// offsets are non-decreasing in ClassReps order — RepLayout.cpp:6118) without
// relinking the native AActor, we expose the protected setter via a trivial
// FStructProperty subclass. The FFieldClass (ClassPrivate) is still set by the
// FStructProperty base constructor, so the object is a bona fide StructProperty
// (CastField<FStructProperty> and RepLayout treat it normally).
struct FLokiStructPropertyWithOffset : public FStructProperty
{
	FLokiStructPropertyWithOffset(FFieldVariant InOwner, const FName& InName, EObjectFlags InFlags)
		: FStructProperty(InOwner, InName, InFlags) {}
	void SetRepOffset(int32 InOffset) { SetOffset_Internal(InOffset); }
};

// Custom net serializer for our ServerState mirror. Its ONLY structural job is
// to make RepLayout treat FPoolableActorServerState as a single cmd (via the
// WithNetSerializer trait), matching SUPERVIVE's client layout so the PC's
// replicated handle space lines up. Content is best-effort: 2-bit State (the
// enum's GetMaxNetSerializeBits width) + 32-bit Version. On a freshly-spawned
// PC, ServerState == CDO, so this isn't actually invoked in the initial bunch.
bool FPoolableActorServerState::NetSerialize(FArchive& Ar, UPackageMap* /*Map*/, bool& bOutSuccess)
{
	uint8 S = (uint8)State;
	Ar.SerializeBits(&S, 2);
	if (Ar.IsLoading())
	{
		State = (EPoolableActorServerState)S;
	}
	Ar << Version;
	bOutSuccess = true;
	return true;
}

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

        // Session 32 Trial 32B: full 5-FString signature.
        //
        // Trial 31A validated (in session 32 via self-replay harness): the
        // prefix (AActor*, bool×3, FString) correctly aligns FString #1 at
        // bit 21 and reads "LVL_LobbyV2_PartyMenu" cleanly. FinalPos=421 with
        // 1877 leftover bits to consume.
        //
        // Session 31's structural analysis: after each of the 5 FStrings
        // (except the last) is a 45-bit "state" struct — likely
        // (uint32, uint8, bool×5) = 32 + 8 + 5 = 45 bits per element. After
        // the last FString is a 41-bit trailer, likely (uint32, uint8, bool)
        // = 32 + 8 + 1 = 41 bits.
        //
        // Total: 21 + 400 + 45 + 480 + 45 + 408 + 45 + 392 + 45 + 376 + 41 = 2298 ✓
        //
        // Self-replay tests the full signature without needing a client. If
        // FinalPos=2298 and all 5 FStrings decode as valid sub-level paths,
        // the signature is CORRECT.

        // Prefix: 18-bit AActor* + 3-bit bool padding = 21 bits.
        AppendObjectParam(Func, TEXT("NewViewTarget"), AActor::StaticClass());
        AppendBoolParam(Func, TEXT("PadBit1"));
        AppendBoolParam(Func, TEXT("PadBit2"));
        AppendBoolParam(Func, TEXT("PadBit3"));

        // Element 1: FString + 45-bit state struct.
        AppendStringParam(Func, TEXT("Map1_Name"));
        AppendUInt32Param(Func, TEXT("Map1_U32"));
        AppendByteParam  (Func, TEXT("Map1_U8"));
        AppendBoolParam  (Func, TEXT("Map1_B0"));
        AppendBoolParam  (Func, TEXT("Map1_B1"));
        AppendBoolParam  (Func, TEXT("Map1_B2"));
        AppendBoolParam  (Func, TEXT("Map1_B3"));
        AppendBoolParam  (Func, TEXT("Map1_B4"));

        // Element 2.
        AppendStringParam(Func, TEXT("Map2_Name"));
        AppendUInt32Param(Func, TEXT("Map2_U32"));
        AppendByteParam  (Func, TEXT("Map2_U8"));
        AppendBoolParam  (Func, TEXT("Map2_B0"));
        AppendBoolParam  (Func, TEXT("Map2_B1"));
        AppendBoolParam  (Func, TEXT("Map2_B2"));
        AppendBoolParam  (Func, TEXT("Map2_B3"));
        AppendBoolParam  (Func, TEXT("Map2_B4"));

        // Element 3.
        AppendStringParam(Func, TEXT("Map3_Name"));
        AppendUInt32Param(Func, TEXT("Map3_U32"));
        AppendByteParam  (Func, TEXT("Map3_U8"));
        AppendBoolParam  (Func, TEXT("Map3_B0"));
        AppendBoolParam  (Func, TEXT("Map3_B1"));
        AppendBoolParam  (Func, TEXT("Map3_B2"));
        AppendBoolParam  (Func, TEXT("Map3_B3"));
        AppendBoolParam  (Func, TEXT("Map3_B4"));

        // Element 4.
        AppendStringParam(Func, TEXT("Map4_Name"));
        AppendUInt32Param(Func, TEXT("Map4_U32"));
        AppendByteParam  (Func, TEXT("Map4_U8"));
        AppendBoolParam  (Func, TEXT("Map4_B0"));
        AppendBoolParam  (Func, TEXT("Map4_B1"));
        AppendBoolParam  (Func, TEXT("Map4_B2"));
        AppendBoolParam  (Func, TEXT("Map4_B3"));
        AppendBoolParam  (Func, TEXT("Map4_B4"));

        // Element 5: FString + 41-bit trailer (last element has 1 fewer bool).
        AppendStringParam(Func, TEXT("Map5_Name"));
        AppendUInt32Param(Func, TEXT("Map5_U32"));
        AppendByteParam  (Func, TEXT("Map5_U8"));
        AppendBoolParam  (Func, TEXT("Map5_B0"));

        Func->StaticLink(true);
        PCClass->ClearFunctionMapsCaches();

        UE_LOG(LogLokiStub, Display,
               TEXT("InjectServerVerifyViewTarget: trial signature injected. "
                    "New NumParms=%d, ParmsSize=%d"),
               Func->NumParms, Func->ParmsSize);

        // Session 32: self-replay harness. Feed the captured 2298-bit RPC arg
        // struct directly to a walk of the injected UFunction's properties,
        // without needing a client to send the RPC. Log Pos after each
        // property so we can see exactly where each param starts/ends and
        // whether any overflow fires.
        SelfReplayCapturedRPC(Func);

        // Session 41 Path B-lite step 2: inject SUPERVIVE's AActor.ServerState
        // replicated property so our RepLayout matches the client's. Must run
        // BEFORE DumpClassNetCacheLayout so the dump reflects the injected
        // state (AActor should show 11 reps with ServerState at [10]).
        InjectServerStateReplicatedProperty();

        // Session 41 Path B-lite step 5 support: dump APlayerController's full
        // hierarchical net-index -> field table so the step-5 probe's client
        // error "ReceivedBunch: Invalid replicated field N" can be mapped to a
        // concrete field on our (stock) side. See DumpClassNetCacheLayout.
        DumpClassNetCacheLayout(PCClass);

        // Session 37 Option A / A' / A'' exhaustively tested and ALL FAILED:
        //   A  (strip CPF_Net at runtime)     - crashed stub on client connect
        //                                       ("Array index out of bounds")
        //   A' (PostLogin SetNetDormancy)      - too late; initial actor bunch
        //                                       already sent by then
        //   A'' (CDO NetDormancy = DormantAll) - dormancy doesn't skip initial
        //                                       bunch, only subsequent updates
        //
        // The INITIAL actor bunch is where the property data lives, and
        // there's no simple runtime knob to suppress it. Client hits
        // "Invalid replicated field 0" and closes.
        //
        // Session 38 needs Option B (inject matching replicated properties
        // so our stub's FClassNetCache aligns with SUPERVIVE's client) or a
        // native ReplicateActor patch.
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

    // Session 29: additional scalar helpers for trial signatures.
    static void AppendIntParam(UFunction* Func, const TCHAR* Name)
    {
        FIntProperty* Prop = new FIntProperty(Func, FName(Name), RF_Public | RF_Transient);
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    static void AppendFloatParam(UFunction* Func, const TCHAR* Name)
    {
        FFloatProperty* Prop = new FFloatProperty(Func, FName(Name), RF_Public | RF_Transient);
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    static void AppendByteParam(UFunction* Func, const TCHAR* Name)
    {
        FByteProperty* Prop = new FByteProperty(Func, FName(Name), RF_Public | RF_Transient);
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    // Session 30: FObjectProperty for actor / object pointer params. On the
    // wire an Actor* is serialized as a NetGUID (variable bits, typically
    // 8-40 depending on cache state).
    static void AppendObjectParam(UFunction* Func, const TCHAR* Name,
                                  UClass* PropertyClass)
    {
        FObjectProperty* Prop = new FObjectProperty(Func, FName(Name),
                                                    RF_Public | RF_Transient);
        Prop->PropertyClass = PropertyClass;
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor
                            | CPF_InstancedReference | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    // Session 31: FBoolProperty for single-bit wire params. SetBoolSize with
    // bIsNativeBool=true configures the C++ bool type; on the wire UE writes
    // exactly 1 bit via FBoolProperty::NetSerializeItem.
    static void AppendBoolParam(UFunction* Func, const TCHAR* Name)
    {
        FBoolProperty* Prop = new FBoolProperty(Func, FName(Name),
                                                RF_Public | RF_Transient);
        Prop->SetBoolSize(sizeof(bool), /*bIsNativeBool=*/true, /*InBitMask=*/1);
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor
                            | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    // Session 31: FUInt32Property for uint32 params (32 bits on wire, same
    // as FIntProperty but semantic differs). Provided for clarity when
    // matching an unsigned field.
    static void AppendUInt32Param(UFunction* Func, const TCHAR* Name)
    {
        FUInt32Property* Prop = new FUInt32Property(Func, FName(Name),
                                                    RF_Public | RF_Transient);
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor
                            | CPF_HasGetValueTypeHash;
        Prop->ArrayDim = 1;
        AppendToChildProperties(Func, Prop);
    }

    // Session 31: FArrayProperty<FByteProperty> for TArray<uint8> params.
    // TArray net serialization: uint16 count (16 bits) + count * 8 bits data.
    static void AppendUInt8ArrayParam(UFunction* Func, const TCHAR* Name)
    {
        FArrayProperty* Prop = new FArrayProperty(Func, FName(Name),
                                                  RF_Public | RF_Transient);
        Prop->PropertyFlags = CPF_Parm | CPF_ZeroConstructor;
        Prop->ArrayDim = 1;
        FByteProperty* Inner = new FByteProperty(Prop, FName("Inner"),
                                                 RF_Public | RF_Transient);
        Inner->PropertyFlags = CPF_ZeroConstructor | CPF_HasGetValueTypeHash;
        Inner->ArrayDim = 1;
        Prop->Inner = Inner;
        AppendToChildProperties(Func, Prop);
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

    // Session 32: self-replay harness. Walks the injected UFunction's params
    // over a BitReader wrapping the captured 2298-bit RPC arg struct (from
    // session 25). For each param, calls NetSerializeItem and logs position
    // deltas — this lets us iterate signature trials without needing a live
    // client to send the RPC. FObjectProperty is special-cased: it needs a
    // UPackageMap (client's NetGUID cache), so we can't feed it real bytes;
    // instead we manually skip 18 bits (measured empirically in session 30
    // via the real client's SetOverflowed diagnostic).
    static void SelfReplayCapturedRPC(UFunction* Func)
    {
        // 293-byte captured bunch from session 25 (docs/session-25-bunch-capture.txt).
        // Bunch total = 2339 bits. RPC arg struct = bits 41..2338 (2298 bits).
        static const uint8 kBunchBytes[] = {
            0x8E, 0x90, 0x78, 0xEB, 0x45, 0x16, 0x00, 0x8C, 0x0B, 0x00, 0x00, 0xC0, 0xCB, 0x51, 0x58, 0x5B,
            0xD9, 0x0B, 0xD3, 0xDB, 0x5A, 0xDA, 0x4B, 0x53, 0x18, 0xDC, 0xDC, 0x0B, 0xD3, 0x9B, 0x98, 0x58,
            0x9E, 0x95, 0xCC, 0x0B, 0x93, 0x15, 0xD3, 0x17, 0xD3, 0x9B, 0x98, 0x58, 0x9E, 0x95, 0xCC, 0x17,
            0x54, 0x98, 0x1C, 0x5D, 0x5E, 0x53, 0x99, 0x5B, 0x1D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0xC1,
            0x01, 0x00, 0x00, 0x78, 0x39, 0x0A, 0x6B, 0x2B, 0x7B, 0x61, 0x7A, 0x5B, 0x4B, 0x7B, 0x69, 0x0A,
            0x83, 0x9B, 0x7B, 0x61, 0x7A, 0x13, 0x13, 0xCB, 0xB3, 0x92, 0x79, 0x61, 0xB2, 0x62, 0xFA, 0x62,
            0x7A, 0x13, 0x13, 0xCB, 0xB3, 0x92, 0xF9, 0x42, 0x2A, 0x93, 0x7B, 0x9B, 0x2A, 0x63, 0x2B, 0x1B,
            0xA3, 0xFB, 0x9A, 0x5A, 0xCB, 0x63, 0x0B, 0x73, 0x23, 0x9B, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x30, 0x2F, 0x00, 0x00, 0x00, 0x2F, 0x47, 0x61, 0x6D, 0x65, 0x2F, 0x4C, 0x6F, 0x6B, 0x69, 0x2F,
            0x4D, 0x61, 0x70, 0x73, 0x2F, 0x4C, 0x6F, 0x62, 0x62, 0x79, 0x56, 0x32, 0x2F, 0x4C, 0x56, 0x4C,
            0x5F, 0x4C, 0x6F, 0x62, 0x62, 0x79, 0x56, 0x32, 0x5F, 0x42, 0x61, 0x74, 0x74, 0x6C, 0x65, 0x50,
            0x61, 0x73, 0x73, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xA6, 0x05, 0x00, 0x00, 0xE0, 0xE5, 0x28,
            0xAC, 0xAD, 0xEC, 0x85, 0xE9, 0x6D, 0x2D, 0xED, 0xA5, 0x29, 0x0C, 0x6E, 0xEE, 0x85, 0xE9, 0x4D,
            0x4C, 0x2C, 0xCF, 0x4A, 0xE6, 0x85, 0xC9, 0x8A, 0xE9, 0x8B, 0xE9, 0x4D, 0x4C, 0x2C, 0xCF, 0x4A,
            0xE6, 0x8B, 0x29, 0xED, 0x0C, 0x8D, 0x2E, 0xCD, 0xED, 0x0C, 0x00, 0x00, 0x00, 0x00, 0x00, 0xC0,
            0xAC, 0x00, 0x00, 0x00, 0xBC, 0x1C, 0x85, 0xB5, 0x95, 0xBD, 0x30, 0xBD, 0xAD, 0xA5, 0xBD, 0x34,
            0x85, 0xC1, 0xCD, 0xBD, 0x30, 0xBD, 0x89, 0x89, 0xE5, 0x59, 0xC9, 0xBC, 0x30, 0x59, 0x31, 0x7D,
            0x31, 0xBD, 0x89, 0x89, 0xE5, 0x59, 0xC9, 0x7C, 0x05, 0xC9, 0xB5, 0xBD, 0xC9, 0xE5, 0x01, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00,
        };
        static constexpr int32 kRPCStartBit = 41;
        static constexpr int32 kRPCNumBits  = 2298;

        // Extract kRPCNumBits from kBunchBytes starting at kRPCStartBit into
        // a fresh LSB-packed buffer starting at bit 0.
        constexpr int32 kArgByteCount = (kRPCNumBits + 7) / 8;
        uint8 ArgBytes[kArgByteCount];
        FMemory::Memzero(ArgBytes, kArgByteCount);
        for (int32 i = 0; i < kRPCNumBits; ++i)
        {
            const int32 SrcBit = kRPCStartBit + i;
            const uint8 Bit = (kBunchBytes[SrcBit / 8] >> (SrcBit % 8)) & 1;
            ArgBytes[i / 8] |= (Bit << (i % 8));
        }

        FBitReader Reader(ArgBytes, kRPCNumBits);

        // Allocate params buffer.
        void* Parms = FMemory_Alloca(Func->ParmsSize);
        FMemory::Memzero(Parms, Func->ParmsSize);
        for (TFieldIterator<FProperty> It(Func); It; ++It)
        {
            FProperty* Prop = *It;
            if (!(Prop->PropertyFlags & CPF_Parm)) break;
            if (!(Prop->PropertyFlags & CPF_ZeroConstructor))
            {
                Prop->InitializeValue_InContainer(Parms);
            }
        }

        UE_LOG(LogLokiStub, Display,
               TEXT("SelfReplay START: Func=%s NumParms=%d ParmsSize=%d BitReader.Max=%lld"),
               *Func->GetName(), Func->NumParms, Func->ParmsSize, Reader.GetNumBits());

        int32 ParamIdx = 0;
        for (TFieldIterator<FProperty> It(Func); It; ++It)
        {
            FProperty* Prop = *It;
            if (!(Prop->PropertyFlags & CPF_Parm)) break;

            const int32 PosBefore = Reader.GetPosBits();

            if (FObjectProperty* ObjProp = CastField<FObjectProperty>(Prop))
            {
                // No PackageMap → can't call NetSerializeItem. Skip 18 bits
                // per session 30's real-client measurement of AActor* NetGUID.
                uint8 Skip[8] = {};
                Reader.SerializeBits(Skip, 18);
                UE_LOG(LogLokiStub, Display,
                       TEXT("  [%d] %s (%s) SKIPPED 18 bits: Pos %d -> %d"),
                       ParamIdx, *Prop->GetName(), *Prop->GetClass()->GetName(),
                       PosBefore, Reader.GetPosBits());
            }
            else
            {
                void* PropData = Prop->ContainerPtrToValuePtr<void>(Parms);
                Prop->NetSerializeItem(Reader, /*Map=*/nullptr, PropData);
                const int32 PosAfter = Reader.GetPosBits();
                const bool bError = Reader.IsError();
                UE_LOG(LogLokiStub, Display,
                       TEXT("  [%d] %s (%s) consumed %d bits: Pos %d -> %d error=%d"),
                       ParamIdx, *Prop->GetName(), *Prop->GetClass()->GetName(),
                       PosAfter - PosBefore, PosBefore, PosAfter, bError ? 1 : 0);

                // Log FString content when we hit an FStrProperty (very useful).
                if (Prop->IsA<FStrProperty>() && !bError)
                {
                    const FString& S = *reinterpret_cast<FString*>(PropData);
                    UE_LOG(LogLokiStub, Display, TEXT("      FString = \"%s\""), *S);
                }

                if (bError)
                {
                    UE_LOG(LogLokiStub, Warning,
                           TEXT("  OVERFLOW at param [%d] %s — stopping."),
                           ParamIdx, *Prop->GetName());
                    break;
                }
            }

            ++ParamIdx;
        }

        const int32 FinalPos = Reader.GetPosBits();
        const int32 Leftover = kRPCNumBits - FinalPos;
        UE_LOG(LogLokiStub, Display,
               TEXT("SelfReplay END: FinalPos=%d Leftover=%d IsError=%d (Expected: FinalPos=%d, Leftover=0)"),
               FinalPos, Leftover, Reader.IsError() ? 1 : 0, kRPCNumBits);

        // Destroy allocated params.
        for (TFieldIterator<FProperty> It(Func); It; ++It)
        {
            FProperty* Prop = *It;
            if (!(Prop->PropertyFlags & CPF_Parm)) break;
            Prop->DestroyValue_InContainer(Parms);
        }
    }

    // Session 41 Path B-lite step 2: inject SUPERVIVE's AActor.ServerState
    // replicated property onto stock AActor so our RepLayout matches the
    // client's. Session 41 RE (docs/session-41-supervive-pc-repschema.txt)
    // proved this is the SOLE replicated-schema difference: SUPERVIVE's AActor
    // has 11 CPF_Net props (stock 10) — the extra one is
    //     ServerState : StructProperty(PoolableActorServerState) @ RepIndex 10
    // appended after Instigator. Everything else in the PC hierarchy matches
    // stock counts + names. The missing property resized our RepLayout block
    // and desynced the client's read cursor -> "Invalid replicated field 0"
    // (session 41 N=0 live probe). Adding it should realign the net-index space.
    //
    // Runs at OnPostEngineInit — before any connection/replication, before
    // RepLayouts/FClassNetCaches are built, and before DumpClassNetCacheLayout —
    // so SetUpRuntimeReplicationData rebuilds AActor's ClassReps to include
    // ServerState at the tail (RepIndex 10; native classes preserve field
    // iteration order and we append to the ChildProperties tail).
    static void InjectServerStateReplicatedProperty()
    {
        UClass* ActorClass = AActor::StaticClass();
        if (!ActorClass)
        {
            UE_LOG(LogLokiStub, Warning, TEXT("InjectServerState: AActor class not found"));
            return;
        }

        // Idempotency: skip if a ServerState property already exists on AActor.
        for (FField* F = ActorClass->ChildProperties; F; F = F->Next)
        {
            if (F->GetFName() == FName(TEXT("ServerState")))
            {
                UE_LOG(LogLokiStub, Display,
                       TEXT("InjectServerState: ServerState already present on AActor; skipping."));
                return;
            }
        }

        UScriptStruct* StateStruct = FPoolableActorServerState::StaticStruct();
        if (!StateStruct)
        {
            UE_LOG(LogLokiStub, Warning,
                   TEXT("InjectServerState: FPoolableActorServerState::StaticStruct() is null"));
            return;
        }

        // NOTE: we CANNOT disable the engine's replicated-property validation via
        // the "net.ValidateReplicatedPropertyRegistration" CVar — it is an
        // FAutoConsoleVariable initialized by-VALUE from the file-static
        // GValidateReplicatedProperties (Class.cpp), so setting the CVar does not
        // change the static that SetUpRuntimeReplicationData actually reads.
        // Instead we sidestep validation entirely below by pre-building ClassReps
        // ourselves and setting CLASS_ReplicationDataIsSetUp, so the engine's
        // (validating) SetUpRuntimeReplicationData early-returns. This is required
        // because injecting ServerState onto AActor shifts EVERY AActor subclass's
        // inherited RepIndices, which would trip ValidateGeneratedRepEnums'
        // hard check (UHT compile-time enum indices vs runtime) for any such class.

        // Build a CPF_Net FStructProperty referencing our mirror struct, owned
        // by AActor (via the offset-exposing subclass).
        FLokiStructPropertyWithOffset* Prop = new FLokiStructPropertyWithOffset(
            ActorClass, FName(TEXT("ServerState")), RF_Public | RF_Transient);
        Prop->Struct = StateStruct;
        Prop->PropertyFlags = CPF_Net;
        Prop->ArrayDim = 1;
        Prop->ElementSize = StateStruct->GetStructureSize();

        // Offset: FRepLayout (RepLayout.cpp:6118) asserts replicated-property
        // offsets are NON-DECREASING in ClassReps order. ServerState comes right
        // after Instigator (the last stock AActor rep, which has the highest
        // AActor-rep offset), so we give ServerState Instigator's offset — that
        // satisfies `>= LastOffset` and stays below AController's field offsets.
        // We must NOT relink the native AActor (that would corrupt every
        // property's C++-fixed offset). RepLayout only READS this property to
        // serialize out (the server never writes it), so reading Instigator's
        // 8 bytes is in-bounds and harmless — the VALUE is irrelevant; only the
        // wire size/position must line up with the client.
        int32 RepOffset = 0;
        if (FProperty* Instigator = FindFProperty<FProperty>(ActorClass, TEXT("Instigator")))
        {
            RepOffset = Instigator->GetOffset_ForGC();
        }
        Prop->SetRepOffset(RepOffset);

        // Append to AActor->ChildProperties tail => last in field iteration =>
        // RepIndex 10 after the stock 10, matching the client's ordering.
        FField** Tail = &ActorClass->ChildProperties;
        while (*Tail)
        {
            Tail = &(*Tail)->Next;
        }
        *Tail = Prop;

        // Rebuild replication data for AActor AND every AActor-derived class,
        // bypassing the engine's validating path. First clear any already-set-up
        // flags (so our builder rebuilds fresh), then ForceSetUpReplicationData
        // on every actor class — recursion builds supers first, so ServerState
        // (now on AActor) propagates into every subclass's ClassReps at RepIndex 10.
        int32 Cleared = 0, Built = 0;
        for (TObjectIterator<UClass> It; It; ++It)
        {
            UClass* C = *It;
            if (C->IsChildOf(ActorClass) && C->HasAnyClassFlags(CLASS_ReplicationDataIsSetUp))
            {
                C->ClassFlags &= ~CLASS_ReplicationDataIsSetUp;
                ++Cleared;
            }
        }
        for (TObjectIterator<UClass> It; It; ++It)
        {
            UClass* C = *It;
            if (C->IsChildOf(ActorClass) && !C->HasAnyClassFlags(CLASS_ReplicationDataIsSetUp))
            {
                ForceSetUpReplicationData(C);
                ++Built;
            }
        }

        // Headless wire-width verification: log each struct member's on-wire
        // bit width so we can confirm State packs to 2 bits (matching the
        // client's EPoolableActorServerState) WITHOUT a full live test.
        for (TFieldIterator<FProperty> It(StateStruct); It; ++It)
        {
            FProperty* M = *It;
            if (FEnumProperty* EP = CastField<FEnumProperty>(M))
            {
                UE_LOG(LogLokiStub, Display,
                       TEXT("InjectServerState: struct member '%s' FEnumProperty NetSerializeBits=%llu (expect 2)"),
                       *M->GetName(), (unsigned long long)EP->GetMaxNetSerializeBits());
            }
            else
            {
                UE_LOG(LogLokiStub, Display,
                       TEXT("InjectServerState: struct member '%s' type=%s ElementSize=%d"),
                       *M->GetName(), *M->GetClass()->GetName(), M->ElementSize);
            }
        }

        UE_LOG(LogLokiStub, Display,
               TEXT("InjectServerState: added CPF_Net FStructProperty ServerState "
                    "(struct=%s ElementSize=%d offset=%d) to AActor; rebuilt rep data "
                    "for %d actor class(es) (cleared %d pre-existing) via validation-"
                    "free ForceSetUpReplicationData."),
               *StateStruct->GetName(), Prop->ElementSize, Prop->GetOffset_ForGC(), Built, Cleared);
    }

    // Validation-free mirror of UClass::SetUpRuntimeReplicationData (Class.cpp
    // 4920-5015) MINUS the two GValidateReplicatedProperties blocks
    // (ValidateGeneratedRepEnums + ValidateRuntimeReplicationData). Needed
    // because we inject ServerState onto AActor, which shifts every AActor
    // subclass's inherited RepIndices; the engine's ValidateGeneratedRepEnums
    // would then hard-assert (UHT compile-time enum indices != runtime). We
    // build ClassReps + NetFields identically to the engine and set the
    // CLASS_ReplicationDataIsSetUp flag so the engine's version early-returns.
    // Recurses super-first so inheritance is correct.
    static void ForceSetUpReplicationData(UClass* C)
    {
        if (!C || C->HasAnyClassFlags(CLASS_ReplicationDataIsSetUp))
        {
            return;
        }

        UClass* Super = C->GetSuperClass();
        if (Super)
        {
            ForceSetUpReplicationData(Super);
            C->ClassReps = Super->ClassReps;
            C->FirstOwnedClassRep = C->ClassReps.Num();
        }
        else
        {
            C->ClassReps.Empty();
            C->FirstOwnedClassRep = 0;
        }

        C->NetFields.Empty();

        // This class's own replicated properties (field-iterator order).
        TArray<FProperty*> NetProperties;
        for (TFieldIterator<FField> It(C, EFieldIteratorFlags::ExcludeSuper); It; ++It)
        {
            if (FProperty* P = CastField<FProperty>(*It))
            {
                if ((P->PropertyFlags & CPF_Net) && P->GetOwner<UObject>() == C)
                {
                    NetProperties.Add(P);
                }
            }
        }

        // This class's own net functions (RPCs).
        for (TFieldIterator<UField> It(C, EFieldIteratorFlags::ExcludeSuper); It; ++It)
        {
            if (UFunction* Func = Cast<UFunction>(*It))
            {
                if ((Func->FunctionFlags & FUNC_Net) && !Func->GetSuperFunction())
                {
                    C->NetFields.Add(Func);
                }
            }
        }

        // Blueprint classes sort net props by memory offset; native classes
        // preserve declaration order. All classes we touch here are native.
        if (!C->HasAnyClassFlags(CLASS_Native))
        {
            NetProperties.Sort([](const FProperty& A, const FProperty& B)
            {
                return A.GetOffset_ForGC() < B.GetOffset_ForGC();
            });
        }

        C->ClassReps.Reserve(C->ClassReps.Num() + NetProperties.Num());
        for (int32 i = 0; i < NetProperties.Num(); ++i)
        {
            NetProperties[i]->RepIndex = (uint16)C->ClassReps.Num();
            for (int32 j = 0; j < NetProperties[i]->ArrayDim; ++j)
            {
                C->ClassReps.Emplace(NetProperties[i], j);
            }
        }

        C->NetFields.Shrink();
        Algo::SortBy(C->NetFields, &UField::GetFName, FNameLexicalLess());

        C->ClassFlags |= CLASS_ReplicationDataIsSetUp;
    }

    // Session 41 Path B-lite (read-only diagnostic). Reproduces the exact
    // net-index assignment of FClassNetCacheMgr::GetClassNetCache
    // (Engine CoreNet.cpp) so we can print the index each replicated field /
    // RPC gets on OUR stub side. When the step-5 probe runs with PC
    // un-suppressed, the client logs "ReceivedBunch: Invalid replicated field N
    // in PlayerController ..." (DataReplication.cpp:1182, N =
    // FieldCache->FieldNetIndex). Because our stub is pure stock UE 5.4, this
    // table IS the stock reference — cross-referencing N against it shows
    // whether N lands in the property range or the RPC range, and which stock
    // field sits there. That pinpoints where SUPERVIVE's client-patched
    // APlayerController diverges (its extra CPF_Net props shift every later
    // index), which scopes the step-2 property injection.
    //
    // Index rules (must match GetClassNetCache):
    //   - Recurse to super first; a class's FieldsBase = Super->GetMaxIndex().
    //   - Per class level: owned ClassReps (properties, ArrayDim-expanded but
    //     one index each) FIRST, then NetFields (RPC UFunctions), indices
    //     running cumulatively from the root.
    // Returns this class level's GetMaxIndex() (the next class's FieldsBase).
    static int32 DumpClassNetCacheLayout(UClass* Cls, int32 Base = 0)
    {
        if (!Cls)
        {
            return Base;
        }

        int32 Index = Base;
        if (UClass* Super = Cls->GetSuperClass())
        {
            Index = DumpClassNetCacheLayout(Super, Base);
        }

        // Idempotent (flag-gated by CLASS_ReplicationDataIsSetUp); this is what
        // GetClassNetCache itself calls. Populates ClassReps / NetFields.
        Cls->SetUpRuntimeReplicationData();

        UE_LOG(LogLokiStub, Display,
               TEXT("NetCacheDump: --- %s  FirstOwnedClassRep=%d ClassReps=%d NetFields=%d  (level base index=%d) ---"),
               *Cls->GetName(), Cls->FirstOwnedClassRep, Cls->ClassReps.Num(),
               Cls->NetFields.Num(), Index);

        // Owned replicated properties for this class level.
        for (int32 i = Cls->FirstOwnedClassRep; i < Cls->ClassReps.Num(); ++i)
        {
            FProperty* Prop = Cls->ClassReps[i].Property;
            if (!Prop)
            {
                continue;
            }
            const TCHAR* Kind = CastField<FStructProperty>(Prop)
                                    ? TEXT("PROPERTY(struct: read via NetDelta loop)")
                                    : TEXT("PROPERTY(scalar: read via RepLayout)");
            UE_LOG(LogLokiStub, Display,
                   TEXT("NetCacheDump:  [%3d] %-30s %-24s RepIndex=%d ArrayDim=%d  %s"),
                   Index, *Prop->GetName(), *Prop->GetClass()->GetName(),
                   (int32)Prop->RepIndex, Prop->ArrayDim, Kind);
            ++Index;
            i += (Prop->ArrayDim - 1); // skip static-array extras, as GetClassNetCache does
        }

        // RPC functions for this class level (name-sorted by SetUpRuntimeReplicationData).
        for (int32 f = 0; f < Cls->NetFields.Num(); ++f)
        {
            UField* Field = Cls->NetFields[f];
            UE_LOG(LogLokiStub, Display,
                   TEXT("NetCacheDump:  [%3d] %-30s %-24s  FUNCTION/RPC"),
                   Index, Field ? *Field->GetName() : TEXT("<null>"), TEXT("UFunction"));
            ++Index;
        }

        return Index; // == GetMaxIndex() for this level
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FLokiModule, Loki, "Loki");
