#include "LokiPlayerStateStub.h"
#include "Net/UnrealNetwork.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiPSStub, Log, All);

// Register one APlayerState inherited replicated property BY NAME as a non-push (bIsPushBased=false),
// COND_None lifetime prop — the S70 pattern (LokiGameStateStub AddGSBaseLifetimeProp). APlayerState
// registers its props PUSH-BASED (DOREPLIFETIME_WITH_PARAMS_FAST: Score/PlayerId/UniqueId/...), which
// clashes with our runtime ClassReps rebuild + non-push own props -> "bIsPushBased == Other.bIsPushBased"
// assert (CoreNet.h:331). Registering by name non-push keeps the lifetime list consistent; the wire is
// identical (push is a server-side dirty-tracking optimization only).
static void AddPSBaseLifetimeProp(TArray<FLifetimeProperty>& Out, const TCHAR* Name)
{
	if (FProperty* P = FindFProperty<FProperty>(APlayerState::StaticClass(), Name))
	{
		Out.Add(FLifetimeProperty(P->RepIndex));
	}
	else
	{
		UE_LOG(LogLokiPSStub, Warning, TEXT("AddPSBaseLifetimeProp: APlayerState::%s not found."), Name);
	}
}

ALokiPlayerState::ALokiPlayerState(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	bReplicates = true;
	UE_LOG(LogLokiPSStub, Display,
	       TEXT("ALokiPlayerState constructed (/Script/Loki.LokiPlayerState mirror; 1 rep HeroClass + 7 RPCs "
	            "over stock APlayerState — S73 schema)."));
}

void ALokiPlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	// S70 pattern: APlayerState is push-based, so DELIBERATELY skip APlayerState::Super. Register the AActor
	// tier, then APlayerState's 11 replicated props BY NAME non-push, then our own HeroClass. RepIndex
	// alignment comes from field-declaration order (ForceSetUpReplicationData), not this list.
	AActor::GetLifetimeReplicatedProps(OutLifetimeProps);
	static const TCHAR* const PSProps[] = {
		TEXT("Score"), TEXT("bIsSpectator"), TEXT("bOnlySpectator"), TEXT("bFromPreviousLevel"),
		TEXT("StartTime"), TEXT("PlayerNamePrivate"), TEXT("CompressedPing"), TEXT("PlayerId"),
		TEXT("bIsABot"), TEXT("bIsInactive"), TEXT("UniqueId"),
	};
	for (const TCHAR* N : PSProps)
	{
		AddPSBaseLifetimeProp(OutLifetimeProps, N);
	}
	DOREPLIFETIME(ALokiPlayerState, HeroClass);
}

// --- S73: empty _Implementation bodies for the 7 mirrored net RPCs (NetFields index alignment only;
// they intentionally do nothing). Add real params to any that fire + desync (e.g. ServerSetReadyToPlay). ---
void ALokiPlayerState::ClientUIEvent_Implementation() {}
void ALokiPlayerState::ClientUpdateDeathRecapDamage_Implementation() {}
void ALokiPlayerState::ClientVisibleSetDelta_Implementation() {}
void ALokiPlayerState::ClientVisionExpirySet_Implementation() {}
void ALokiPlayerState::ServerSetRankedPointsOverride_Implementation() {}
void ALokiPlayerState::ServerSetReadyToPlay_Implementation() {}
void ALokiPlayerState::ServerVisibleSetAck_Implementation() {}
