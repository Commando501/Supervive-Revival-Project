#include "LokiServerAuthConfigStub.h"
#include "Net/UnrealNetwork.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiAuthCfgStub, Log, All);

// Register a UActorComponent inherited replicated prop BY NAME, non-push (bIsPushBased=false), COND_None —
// the S70 pattern (LokiGameStateStub AddGSBaseLifetimeProp). Keeps the lifetime list consistent + avoids any
// push/non-push mismatch assert (CoreNet.h:331). The wire is identical (push is a server-side dirty-tracking
// optimization only).
static void AddCompBaseLifetimeProp(TArray<FLifetimeProperty>& Out, const TCHAR* Name)
{
	if (FProperty* P = FindFProperty<FProperty>(UActorComponent::StaticClass(), Name))
	{
		Out.Add(FLifetimeProperty(P->RepIndex));
	}
	else
	{
		UE_LOG(LogLokiAuthCfgStub, Warning, TEXT("AddCompBaseLifetimeProp: UActorComponent::%s not found."), Name);
	}
}

ULokiServerAuthConfig::ULokiServerAuthConfig()
{
	SetIsReplicatedByDefault(true);

	// S86: force stably-named-for-networking. On the stub the mirror GameState's runtime by-path construction
	// does NOT yield an effective RF_DefaultSubObject-stable component, so IsNameStableForNetworking() returned
	// FALSE (engine-source-verified: the client hit "Unable to read sub-object class" at DataChannel.cpp:4777,
	// reachable only when the server took the NON-stable else-branch at DataChannel.cpp:4460 because the object
	// wasn't name-stable). bNetAddressable=true makes UActorComponent::IsNameStableForNetworking() (ActorComponent
	// .cpp:2204) return true UNCONDITIONALLY, so WriteContentBlockHeader takes the WriteBit(1) early-return
	// (DataChannel.cpp:4460-4463): NO class NetGUID (kills the NOT_IN_CACHE) and NO EngineNetVer-gated destroy/
	// outer-chain header bits (kills the Handle=8352 payload-cursor desync). Server-side only; the client keeps
	// resolving the subobject by its existing name — the normal path for a replicated component on a net actor.
	SetNetAddressable();

	PrimaryComponentTick.bCanEverTick = false;
	UE_LOG(LogLokiAuthCfgStub, Display,
	       TEXT("ULokiServerAuthConfig constructed (/Script/Loki.LokiServerAuthConfig mirror; 1 rep "
	            "GameFeatureToggles TArray<bool> + 1 RPC over UActorComponent)."));
}

void ULokiServerAuthConfig::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	// Register UActorComponent's 2 replicated props (bReplicates, bIsActive) BY NAME non-push, then our own,
	// instead of calling UActorComponent::Super — same reasoning as the S70 GameState mirror. This class is
	// NOT AActor-derived, so the stub's ForceSetUpReplicationData (Actor-only) leaves its ClassReps to the
	// engine's SetUpRuntimeReplicationData; a fully non-push lifetime list stays consistent with that.
	AddCompBaseLifetimeProp(OutLifetimeProps, TEXT("bReplicates"));
	AddCompBaseLifetimeProp(OutLifetimeProps, TEXT("bIsActive"));
	DOREPLIFETIME(ULokiServerAuthConfig, GameFeatureToggles);
}

// Empty stub — present only so the class carries the FUNC_Net UFunction for NetFields index alignment.
void ULokiServerAuthConfig::MulticastSetGameFeatureToggle_Implementation() {}

void ULokiServerAuthConfig::SeedAllToggles(bool bValue, int32 Count)
{
	GameFeatureToggles.Init(bValue, Count);
	UE_LOG(LogLokiAuthCfgStub, Display,
	       TEXT("ULokiServerAuthConfig::SeedAllToggles: GameFeatureToggles set to %d entries = %s (replicates "
	            "to the client -> OnRep_GameFeatureToggles -> toggles ready)."),
	       Count, bValue ? TEXT("true") : TEXT("false"));
}
