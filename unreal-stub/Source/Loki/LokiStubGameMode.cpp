#include "LokiStubGameMode.h"
#include "LokiStubPlayerController.h"
#include "LokiPlayerState_Missions.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Engine/NetConnection.h"
#include "Engine/World.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStubGM, Log, All);

// Session 54: build one FMissionProgress. AssetId/PoolId are FPrimaryAssetIds of
// the form Type:Name (session-52 doc). The exact Name portions are the primary
// guess and may need tuning after the first live test — the client's container
// filters missions by PoolId == GetPrimaryAssetIdFromClass(poolClass), so a wrong
// PoolId leaves the model populated but the tile unfiltered-out. Keep them here
// as obvious knobs.
static FMissionProgress MakeMissionProgress(
	const TCHAR* Id, const TCHAR* MissionName, const TCHAR* PoolName)
{
	FMissionProgress P;
	P.ID = Id;
	P.AssetId = FPrimaryAssetId(FPrimaryAssetType(FName(TEXT("Mission"))), FName(MissionName));
	P.PoolId = FPrimaryAssetId(FPrimaryAssetType(FName(TEXT("MissionPool"))), FName(PoolName));
	P.Complete = false;
	P.Failed = false;
	P.ObjectiveProgress.Add(0);          // 1 objective, 0 progress
	// Real timestamps so the client's pool-timer doesn't log "DateTime in bad
	// format (year 0)" and the countdown shows a sane value.
	const FDateTime Now = FDateTime::UtcNow();
	const FTimespan Window = FTimespan::FromHours(24);
	P.GrantedAt = Now;
	P.Expiry = Now + Window;
	P.MillisUntilExpiry = (int64)Window.GetTotalMilliseconds();
	return P;
}

ALokiStubGameMode::ALokiStubGameMode(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Session 26 REVERT: kept stock APlayerController as PlayerControllerClass
	// since we can't override its ServerVerifyViewTarget UFUNCTION with
	// different parameters via UHT-checked subclass. Session 27 will attempt
	// runtime UClass function-table manipulation to add a modified
	// ServerVerifyViewTarget UFunction to the stock APlayerController class.
	PlayerControllerClass = APlayerController::StaticClass();
	UE_LOG(LogLokiStubGM, Display,
	       TEXT("LokiStubGameMode constructed with PlayerControllerClass=APlayerController "
	            "(session 26 revert — UHT rejected override)"));
}

void ALokiStubGameMode::PostLogin(APlayerController* NewPlayer)
{
	Super::PostLogin(NewPlayer);

	// Session 37 experimented with NetDormancy here as Option A' — result
	// was negative (see docs/session-37-option-a-negative.md). Kept the
	// override method as a documented hook site for future intercepts.

	// Session 54: spawn a replicated LokiPlayerState_Missions for this player and
	// seed it with a smoke-test daily mission set. The class path
	// /Script/Loki.LokiPlayerState_Missions matches the client's real class (both
	// modules are "Loki"), so the client resolves the NetGUID to its own class,
	// runs its OnRep(Missions) -> OnMissionsUpdated -> OnPSMissionsUpdated, and
	// (goal) populates the UMissionsModel that WBP_UI_MissionModal renders.
	UWorld* World = GetWorld();
	if (!World || !NewPlayer)
	{
		UE_LOG(LogLokiStubGM, Warning,
		       TEXT("PostLogin: no World or NewPlayer; skipping missions actor spawn."));
		return;
	}

	FActorSpawnParameters SpawnParams;
	// Owned by the connecting PC so the actor is net-owned by that connection
	// (relevancy + correct outbound channel). bAlwaysRelevant on the class is the
	// belt-and-suspenders that guarantees the send at the menu.
	SpawnParams.Owner = NewPlayer;
	SpawnParams.ObjectFlags |= RF_Transient;

	ALokiPlayerState_Missions* MissionsActor =
		World->SpawnActor<ALokiPlayerState_Missions>(
			ALokiPlayerState_Missions::StaticClass(), SpawnParams);
	if (!MissionsActor)
	{
		UE_LOG(LogLokiStubGM, Warning,
		       TEXT("PostLogin: failed to spawn ALokiPlayerState_Missions."));
		return;
	}

	MissionsActor->OwningPlayerState = NewPlayer->PlayerState;

	// Smoke-test seed: 2 Armory dailies in the DailyEasy pool. Names per
	// missions_catalog.json / session-52 doc. Scale to all 6 categories once the
	// first tile renders. (DA_Mission_ArmoryDaily_* live at
	// /Game/Loki/Core/Missions/Armory/ArmoryDailies/, pool DA_MissionPoolDailyEasy
	// at /Game/Loki/Core/Missions/Pools/.)
	MissionsActor->Missions.Add(
		MakeMissionProgress(TEXT("ArmoryDaily_PlayAGame"),
		                    TEXT("ArmoryDaily_PlayAGame"), TEXT("Daily")));
	MissionsActor->Missions.Add(
		MakeMissionProgress(TEXT("ArmoryDaily_GetKnocks"),
		                    TEXT("ArmoryDaily_GetKnocks"), TEXT("Daily")));

	UE_LOG(LogLokiStubGM, Display,
	       TEXT("PostLogin: spawned ALokiPlayerState_Missions %s (owner=%s, %d missions, "
	            "bAlwaysRelevant=%d bReplicates=%d) — replicating to the client."),
	       *MissionsActor->GetName(), *NewPlayer->GetName(),
	       MissionsActor->Missions.Num(),
	       MissionsActor->bAlwaysRelevant ? 1 : 0,
	       MissionsActor->GetIsReplicated() ? 1 : 0);
}
