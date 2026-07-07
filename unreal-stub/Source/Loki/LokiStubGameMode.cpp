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
	// One objective at 0/1 progress. FMissionObjectiveProgress is the live-RE'd
	// element type (session 54). SESSION 54 localization test: with the objective
	// seeded, the 22-cmd structure matches the client (verified) but the client STILL
	// rejects the bunch ("Invalid replicated field 0") — a residual LEAF-serialization
	// bit mismatch. bSeedObjective=false leaves ObjectiveProgress EMPTY (count 0, no
	// element serialized) to isolate: if the bunch is ACCEPTED with 0 objectives, the
	// desync is a leaf INSIDE MissionObjectiveProgress; if it still fails, the desync
	// is in the OUTER FMissionProgress leaves (ID/AssetId/PoolId FNames, DateTimes).
	// Localization test DONE (2026-07-07): empty ObjectiveProgress STILL desyncs =>
	// the residual bit mismatch is in the OUTER FMissionProgress leaves (ID/AssetId/
	// PoolId/DateTimes), NOT the MissionObjectiveProgress element. FDateTime ruled out
	// (its NetSerialize is a plain `Ar << Ticks`); FName is self-describing too — so the
	// remaining suspect is a class-level Missions HANDLE misalignment or a SUPERVIVE
	// engine-level serialization diff, resolvable only with a bit-level wire capture.
	// Toggle back to true (seed a real objective) — the desync is independent of it.
	const bool bSeedObjective = true;
	if (bSeedObjective)
	{
		FMissionObjectiveProgress Obj;
		Obj.ObjectiveName = FName(*(FString(Id) + TEXT("_Obj")));
		Obj.Progress = 0.f;
		Obj.MaxProgress = 1.f;
		Obj.StartingProgress = 0.f;
		P.ObjectiveProgress.Add(Obj);
	}
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

	// SESSION 54 (2026-07-07) — three live-RE findings, in order of discovery:
	//  1. The client BINDS /Script/Loki.LokiPlayerState_Missions by path + replicates,
	//     but rejected the seeded bunch ("Invalid replicated field 0").
	//  2. The usmap's FMissionProgress.ObjectiveProgress was wrong (int64 vs the real
	//     struct FMissionObjectiveProgress) — fixed the mirror; cmds matched 22:22 but
	//     it STILL desynced.
	//  3. ROOT CAUSE: Missions is NOT a struct array at all — its inner is an
	//     ObjectProperty (UClass "BaseMission" : AActor), i.e. TArray<ABaseMission*>.
	//     ONLY FinalMissionProgress is TArray<FMissionProgress>. So we now (a) correct
	//     Missions to an object array (aligns the whole class RepLayout) and (b) seed
	//     the CORRECTLY-TYPED FinalMissionProgress to validate the FMissionProgress
	//     wire path. Missions stays empty (populating it needs replicated ABaseMission
	//     actors — a larger, deferred lift). Also un-blocks the s53 garbage-thread
	//     crash question (Finding: even an empty actor re-triggered it ~100s in).
	//
	// Toggle: false = stable empty-actor baseline.
	const bool bSeedFinalProgress = true;
	if (bSeedFinalProgress)
	{
		MissionsActor->FinalMissionProgress.Add(
			MakeMissionProgress(TEXT("ArmoryDaily_PlayAGame"),
			                    TEXT("ArmoryDaily_PlayAGame"), TEXT("Daily")));
		MissionsActor->FinalMissionProgress.Add(
			MakeMissionProgress(TEXT("ArmoryDaily_GetKnocks"),
			                    TEXT("ArmoryDaily_GetKnocks"), TEXT("Daily")));
	}

	UE_LOG(LogLokiStubGM, Display,
	       TEXT("PostLogin: spawned ALokiPlayerState_Missions %s (owner=%s, Missions=%d "
	            "FinalMissionProgress=%d, bAlwaysRelevant=%d bReplicates=%d) — replicating."),
	       *MissionsActor->GetName(), *NewPlayer->GetName(),
	       MissionsActor->Missions.Num(), MissionsActor->FinalMissionProgress.Num(),
	       MissionsActor->bAlwaysRelevant ? 1 : 0,
	       MissionsActor->GetIsReplicated() ? 1 : 0);
}
