#include "LokiStubGameMode.h"
#include "LokiStubPlayerController.h"
#include "LokiPlayerControllerStub.h"
#include "LokiPlayerStateStub.h"
#include "LokiCharacterStub.h"
#include "LokiPlayerState_Missions.h"
#include "LokiGameStateStub.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/DefaultPawn.h"
#include "Engine/NetConnection.h"
#include "Engine/World.h"
#include "TimerManager.h"

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
	// Session 73: use the native LokiPlayerController mirror (path /Script/Loki.LokiPlayerController)
	// so the client resolves it to ITS OWN native LokiPlayerController and makes the LOCAL networked
	// PC a Loki-typed controller — the prerequisite for TryGetLocalLokiController to stop returning
	// null (the S71/S72 hero-control wall). This is the SINGLE VARIABLE under test in the S73 spike.
	// The mirror adds ZERO own replicated props for the first live test (see LokiPlayerControllerStub.h):
	// a clean accept proves the by-path bind + initial-bunch alignment; an "Invalid replicated field N"
	// scopes the prop reconstruction. To revert to the S41 stock-PC baseline (roster/menu-safe):
	//   PlayerControllerClass = APlayerController::StaticClass();
	PlayerControllerClass = ALokiPlayerController::StaticClass();

	// Session 73: use the native LokiPlayerState mirror (path /Script/Loki.LokiPlayerState) so the client
	// resolves it to ITS OWN native LokiPlayerState and GetLocalLokiPlayerState succeeds (was stock
	// APlayerState — the "GetLocalLokiPlayerState failed" gate after the PC mirror). PlayerState is already
	// un-suppressed in LokiNetDriver (S53). One rep (HeroClass) + 7 RPCs align the net-cache (S73 live capture).
	PlayerStateClass = ALokiPlayerState::StaticClass();

	// Session 70: use the native LokiGameState mirror (path /Script/Loki.LokiGameState) so the client
	// resolves it to ITS OWN LokiGameState and hydrates a real GameState replica — the prerequisite for
	// leaving the tutorial loading screen on the DS route. Was stock AGameStateBase (which the client
	// couldn't cast to LokiGameState). Must pair with un-suppressing GameState in LokiNetDriver.
	GameStateClass = ALokiGameState::StaticClass();

	UE_LOG(LogLokiStubGM, Display,
	       TEXT("LokiStubGameMode constructed with PlayerControllerClass=ALokiPlayerController "
	            "(s73 Loki-PC mirror, path /Script/Loki.LokiPlayerController), GameStateClass=ALokiGameState (s70)."));
}

void ALokiStubGameMode::InitGameState()
{
	Super::InitGameState();

	// Seed the replicated GameState into a PLAYING state so the client's native match-ready check
	// (ERoundPhase CurrentPhase) passes and the loading screen clears. S65/S66 established the round
	// was stuck at EGP_BeginInit(1); a real round reaches EGP_SpawnSelect(4)/EGP_Combat(7). Start at
	// EGP_SpawnSelect (drop-in select) — if the client still waits, bisect toward EGP_Combat.
	// NOTE (single-variable option): for the FIRST test of whether the bunch even ALIGNS, comment out
	// the seed and ship a default GameState — a clean accept (no "Invalid replicated field N") proves
	// the 43-prop RepLayout matches; THEN re-enable the seed to clear the loading screen.
	ALokiGameState* GS = Cast<ALokiGameState>(GameState);
	if (!GS)
	{
		UE_LOG(LogLokiStubGM, Warning,
		       TEXT("InitGameState: GameState is not ALokiGameState (got %s) — seed skipped."),
		       GameState ? *GameState->GetClass()->GetName() : TEXT("<null>"));
		return;
	}

	const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	// S77: reverted to EGP_SpawnSelect(4) — the S70-PROVEN loading-screen-clear phase (S70 result:
	// "the client LEAVES the loading screen into the live tutorial world"). The S73 lever-2 probe had
	// changed this to EGP_Combat(7) to test whether a later phase dismisses the overlay; the answer was
	// NO — the client RECEIVED EGP_Combat ("Entering combat phase on client") but the loading screen
	// STAYED (live-reconfirmed S77: stable ~90s idle-looping behind the overlay). SpawnSelect is the
	// drop-select spectator phase where the world is visible + the spectator/drop camera is movable —
	// i.e. the state in which the S77 movement-AV test is actually reachable. (Loading-screen dismiss is
	// phase-gated to SpawnSelect, NOT to the server-authoritative drop-in — a real S70/S77 win.)
	GS->CurrentPhase        = ELokiRoundPhase::EGP_SpawnSelect;
	GS->DayNightState       = ELokiDayNightStateMirror::LDNS_Day;
	GS->RoundStartTime      = Now;
	GS->GameStartWorldTime  = Now;
	GS->SpawnSelectEndTime  = Now + 30.f;
	GS->NumTeams            = 1;
	GS->MaxPlayersPerTeam   = 1;
	GS->ReplicatedNumRemainingPlayers = 1;
	GS->MatchStartDetails.MatchID = TEXT("revival-tutorial-0001");

	// S71: AGameModeBase::InitGameState (Super, above) set GS->GameModeClass = LokiStubGameMode. That
	// class does NOT exist in the client, so replicating it makes the client spam
	// "GetObjectFromNetGUID: Forced blocking load ... LokiStubGameMode" — a SYNCHRONOUS blocking load in
	// the netdriver receive path (starves other actor channels, e.g. our possessed DefaultPawn never
	// arrives). Null it so the client never tries to resolve the stub's gamemode. (SpectatorClass stays
	// ASpectatorPawn — a stock class the client resolves fine.)
	GS->GameModeClass = nullptr;

	UE_LOG(LogLokiStubGM, Display,
	       TEXT("InitGameState: seeded ALokiGameState %s -> CurrentPhase=EGP_SpawnSelect(4), "
	            "RoundStartTime=%.1f, NumTeams=1, GameModeClass=null (playing state)."),
	       *GS->GetName(), Now);
}

// S80: walk the round phase SpawnSelect(4) -> SpawnReveal(5) -> Lineup(6) -> Combat(7), one step every
// kPhaseStepSecs, starting once a client has joined. See the header note for why a STATIC seed can't work:
// 4 alone leaves the client in the pre-drop hold; a cold 7 leaves the loading screen up (S73/S77). The real
// server progresses through the states and the client's own phase machine follows that progression — this
// mirrors the "pre-drop view for a while, then it transitions to the world" behaviour of the retail game.
void ALokiStubGameMode::AdvanceRoundPhase()
{
	ALokiGameState* GS = Cast<ALokiGameState>(GameState);
	if (!GS) { return; }

	static const ELokiRoundPhase kSeq[] = {
		ELokiRoundPhase::EGP_SpawnReveal,   // 5
		ELokiRoundPhase::EGP_Lineup,        // 6
		ELokiRoundPhase::EGP_Combat,        // 7 — the playing phase
	};
	const int32 kNum = UE_ARRAY_COUNT(kSeq);
	if (PhaseStep >= kNum)
	{
		if (UWorld* W = GetWorld()) { W->GetTimerManager().ClearTimer(PhaseTimer); }
		UE_LOG(LogLokiStubGM, Display, TEXT("AdvanceRoundPhase: sequence complete, holding at EGP_Combat(7)."));
		return;
	}

	const ELokiRoundPhase Next = kSeq[PhaseStep++];
	GS->CurrentPhase = Next;
	GS->ForceNetUpdate();   // push it now; don't wait for the next natural rep window
	UE_LOG(LogLokiStubGM, Display,
	       TEXT("AdvanceRoundPhase: step %d -> CurrentPhase=%d  (4=SpawnSelect 5=SpawnReveal 6=Lineup 7=Combat)"),
	       PhaseStep, (int32)Next);
}

void ALokiStubGameMode::PostLogin(APlayerController* NewPlayer)
{
	Super::PostLogin(NewPlayer);

	// S80: kick off the round-phase progression now that a client is actually here. Delay the first step
	// so the client finishes hydrating its GameState replica + clears the loading screen at SpawnSelect(4)
	// before we start stepping toward Combat(7).
	if (UWorld* W = GetWorld())
	{
		const float kPhaseFirstDelay = 12.f;   // pre-drop hold, mirroring retail's "wait for players to load"
		const float kPhaseStepSecs   = 4.f;    // then one step every few seconds
		PhaseStep = 0;
		W->GetTimerManager().ClearTimer(PhaseTimer);
		W->GetTimerManager().SetTimer(PhaseTimer, this, &ALokiStubGameMode::AdvanceRoundPhase,
		                              kPhaseStepSecs, /*bLoop=*/true, /*FirstDelay=*/kPhaseFirstDelay);
		UE_LOG(LogLokiStubGM, Display,
		       TEXT("PostLogin: round-phase progression armed (first step in %.0fs, then every %.0fs -> EGP_Combat)."),
		       kPhaseFirstDelay, kPhaseStepSecs);
	}

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
	// S62 TUTORIAL-CONNECT: false — the tutorial-match connect (menu route) has nothing
	// to do with missions; seeding only adds bunch-rejection churn. Keep the empty-actor
	// stable baseline while we validate the menu-route client connects + completes Join.
	const bool bSeedFinalProgress = false;
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

	// S77 MOVEMENT-AV CULPRIT TEST (single-variable): possess a stock ADefaultPawn, NOT the
	// abstract ALokiCharacter. HYPOTHESIS: the movement garbage-thread execute-AV (0x8, unmapped
	// address; docs/session-76-worldsettings-breakthrough.md) is the S53/S54 half-hydrated-replica
	// bug engaged by movement, and the half-hydrated replica is the POSSESSED PAWN itself:
	// S73 proved the client's /Script/Loki.LokiCharacter is CLASS_Abstract ("SpawnActor failed
	// because class LokiCharacter is abstract"), so when the stub possesses ALokiCharacter the
	// client CANNOT instantiate its local pawn replica -> PC->Pawn resolves to a null/half-formed
	// actor -> the moment movement input drives the possession/movement machinery it dereferences
	// that garbage -> the execute-AV. ADefaultPawn is concrete on BOTH sides (S71 verified it
	// replicates cleanly to the client as real DefaultPawn instances), so the client CAN spawn its
	// local replica -> if the abstract-possessed-pawn is the culprit, the movement AV vanishes.
	// SINGLE VARIABLE: only the possessed class changes; the spawn/possess/deferred-ClientRestart
	// flow is otherwise identical to S73. REVERT: swap ADefaultPawn back to ALokiCharacter (both
	// spawn calls). If the AV persists, the culprit is a DIFFERENT replica -> escalate to the
	// route-A diagnostic shim (name the culprit via the async/thread dispatch caller stack).
	// Tutorial has NO PlayerStart (drop-in via DropPlane), so spawn explicitly above origin.
	const FVector SpawnLoc(0.f, 0.f, 500.f);
	FActorSpawnParameters PawnParams;
	PawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ADefaultPawn* Pawn = World->SpawnActor<ADefaultPawn>(
		ADefaultPawn::StaticClass(), SpawnLoc, FRotator::ZeroRotator, PawnParams);
	if (Pawn)
	{
		// S77: stock ADefaultPawn does NOT set bAlwaysRelevant in its ctor (ALokiCharacter did), so set it
		// explicitly here — S71's proven-replicating DefaultPawn config set it, guaranteeing the pawn's
		// initial actor bunch reaches the client regardless of owner-relevancy timing.
		Pawn->bAlwaysRelevant = true;
		// Possess() sets the PC's view target via the ClientSetViewTarget RPC which the stub SUPPRESSES
		// (SUPERVIVE-modified sig); bAlwaysRelevant guarantees the send regardless.
		NewPlayer->Possess(Pawn);
		UE_LOG(LogLokiStubGM, Display,
		       TEXT("PostLogin: spawned + possessed ADefaultPawn (S77 movement-AV test) %s at %s for %s — PC->GetPawn()=%s "
		            "(pawn Role=%d bAlwaysRelevant=%d bReplicates=%d, PC hasConnection=%d)."),
		       *Pawn->GetName(), *SpawnLoc.ToString(), *NewPlayer->GetName(),
		       *GetNameSafe(NewPlayer->GetPawn()), (int32)Pawn->GetLocalRole(),
		       Pawn->bAlwaysRelevant ? 1 : 0, Pawn->GetIsReplicated() ? 1 : 0,
		       NewPlayer->GetNetConnection() ? 1 : 0);

		// S71: the pawn ACTOR replicates to the client (verified: DefaultPawn instances exist on the
		// client), but the client doesn't POSSESS it — the ClientRestart RPC fired at possess time
		// (in PostLogin) races the client PC channel setup. Re-send ClientRestart on a short timer so it
		// lands after the client is ready; the client then possesses + sends ServerAcknowledgePossession.
		if (UWorld* W = GetWorld())
		{
			TWeakObjectPtr<APlayerController> WeakPC(NewPlayer);
			TWeakObjectPtr<APawn> WeakPawn(Pawn);
			FTimerHandle TH;
			W->GetTimerManager().SetTimer(TH, [WeakPC, WeakPawn]()
			{
				if (WeakPC.IsValid() && WeakPawn.IsValid())
				{
					WeakPC->ClientRestart(WeakPawn.Get());
					UE_LOG(LogLokiStubGM, Display,
					       TEXT("Deferred ClientRestart re-sent for %s -> %s."),
					       *WeakPC->GetName(), *WeakPawn->GetName());
				}
			}, 3.0f, false);
		}
	}
	else
	{
		UE_LOG(LogLokiStubGM, Warning, TEXT("PostLogin: failed to spawn ADefaultPawn."));
	}
}
