#include "LokiPlayerState_Missions.h"
#include "Net/UnrealNetwork.h"
#include "GameFramework/PlayerState.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiMissions, Log, All);

ALokiPlayerState_Missions::ALokiPlayerState_Missions(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// bReplicates must be set in the constructor (SetReplicates() asserts if
	// called there). bAlwaysRelevant guarantees the actor replicates to the
	// connected client regardless of pawn/view location — at the menu there is
	// no gameplay-relevant position, so distance relevancy would never send it.
	bReplicates = true;
	bAlwaysRelevant = true;

	// No tick, no movement — this is a pure data carrier. NetUpdateFrequency is a
	// public member in UE 5.4 (the SetNetUpdateFrequency() accessor is 5.5+).
	PrimaryActorTick.bCanEverTick = false;
	NetUpdateFrequency = 10.0f;
}

void ALokiPlayerState_Missions::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	// Register the two arrays in the SAME order they are declared so their
	// RepIndices (11, 12 after AActor's 0..10 incl. injected ServerState) match
	// the client's LokiPlayerState_Missions. See the header for the alignment
	// rationale. DOREPLIFETIME (not *_CONDITION) — the client is always relevant
	// for its own missions.
	DOREPLIFETIME(ALokiPlayerState_Missions, Missions);
	DOREPLIFETIME(ALokiPlayerState_Missions, FinalMissionProgress);
}

// The server never runs these — RepNotify fires on the RECEIVING (client) side,
// which uses its own compiled class. They exist so ReplicatedUsing has a valid
// UFUNCTION target and to satisfy UHT. Left as no-ops.
void ALokiPlayerState_Missions::OnRep_Missions()
{
}

void ALokiPlayerState_Missions::OnRep_FinalMissionProgress()
{
}
