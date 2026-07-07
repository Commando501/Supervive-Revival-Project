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

	// Smoke-test seed: 2 Armory dailies in the DailyEasy pool. Names per
	// missions_catalog.json / session-52 doc. Scale to all 6 categories once the
	// first tile renders. (DA_Mission_ArmoryDaily_* live at
	// /Game/Loki/Core/Missions/Armory/ArmoryDailies/, pool DA_MissionPoolDailyEasy
	// at /Game/Loki/Core/Missions/Pools/.)
	//
	// SESSION 54 LIVE RESULTS (2026-07-07) — two findings, both reproduced live:
	//
	// FINDING 1 (schema): with these 2 seeded, the client BINDS the class by path
	// (NetGUID resolves /Script/Loki.LokiPlayerState_Missions -> its own class) and
	// the actor REPLICATES, but the client rejects the property bunch:
	//   "ReceivedBunch: Invalid replicated field 0 in LokiPlayerState_Missions" ->
	//   "Replicator.ReceivedBunch failed. Closing connection. Channel: 4" -> the
	//   client drops into a ~1s connect/fail/reconnect loop.
	// ISOLATION TEST (bSeedMissions=false, empty arrays == CDO => no element bytes
	// on the wire) => ZERO field-0 errors, connection STABLE. CONFIRMED: the desync
	// is the FMissionProgress ELEMENT serialization, NOT the class rep layout (the
	// RepIndex 11/12 alignment is correct — verified at boot). Our member-wise
	// mirror does not match the client's FMissionProgress wire format. NEXT: the
	// client's FMissionProgress almost certainly has a custom NetSerialize (single
	// RepLayout cmd) — RE that function's exact byte layout and mirror it as a
	// WithNetSerializer struct (like FPoolableActorServerState in LokiReplicatedStructs.h).
	//
	// FINDING 2 (crash): even the EMPTY missions actor eventually triggers the
	// session-53 garbage-thread execute-AV (RIP=0x7FF8F0400001) ~100s after Join —
	// the same crash un-suppressing PlayerState was thought to have cured. So merely
	// binding a LokiPlayerState_Missions replica (client half-inits its missions
	// subsystem off it, then fires a stale/garbage callback) re-introduces it.
	// HYPOTHESIS: fully hydrating the actor with VALID mission data (Finding 1 fix)
	// may also resolve Finding 2 (no half-initialized object). If not, the missions
	// actor may need to stay un-spawned until its data path is complete, or the
	// association delegate suppressed. Both are next-session work.
	//
	// Toggle: seed real data (true) to iterate the NetSerialize fix; false gives the
	// stable empty-actor baseline (useful for isolating the Finding-2 crash).
	const bool bSeedMissions = true;
	if (bSeedMissions)
	{
		MissionsActor->Missions.Add(
			MakeMissionProgress(TEXT("ArmoryDaily_PlayAGame"),
			                    TEXT("ArmoryDaily_PlayAGame"), TEXT("Daily")));
		MissionsActor->Missions.Add(
			MakeMissionProgress(TEXT("ArmoryDaily_GetKnocks"),
			                    TEXT("ArmoryDaily_GetKnocks"), TEXT("Daily")));
	}

	UE_LOG(LogLokiStubGM, Display,
	       TEXT("PostLogin: spawned ALokiPlayerState_Missions %s (owner=%s, %d missions, "
	            "bAlwaysRelevant=%d bReplicates=%d) — replicating to the client."),
	       *MissionsActor->GetName(), *NewPlayer->GetName(),
	       MissionsActor->Missions.Num(),
	       MissionsActor->bAlwaysRelevant ? 1 : 0,
	       MissionsActor->GetIsReplicated() ? 1 : 0);
}
