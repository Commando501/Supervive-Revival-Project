// LokiStubGameMode — minimal AGameModeBase subclass whose only job is to
// specify LokiStubPlayerController as its PlayerControllerClass.
//
// Registered via DefaultEngine.ini:
//   [/Script/EngineSettings.GameMapsSettings]
//   GlobalDefaultGameMode=/Script/Loki.LokiStubGameMode

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LokiStubGameMode.generated.h"

UCLASS(transient)
class ALokiStubGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALokiStubGameMode(const FObjectInitializer& ObjectInitializer);

	// Session 37 Option A': mark the newly-logged-in PC as fully dormant so
	// its actor channel opens (client sees the PC replica) but no property
	// replication ever fires. This dodges the FClassNetCache divergence that
	// crashes the client with "Invalid replicated field 0" (see
	// docs/session-36-close-diagnosis.md).
	virtual void PostLogin(APlayerController* NewPlayer) override;

	// S80: the ROUND-PHASE PROGRESSION. The stub seeded a STATIC phase and never advanced it, so the
	// client sat in the pre-drop hold ("BRALL / DROP LEADER") forever — the real server walks
	// SpawnSelect(4) -> SpawnReveal(5) -> Lineup(6) -> Combat(7) after the load hold, and that walk is
	// what transitions the client into the world.
	// The record only ever tried STATIC seeds, and both fail on their own:
	//   * static EGP_SpawnSelect(4): loading clears, but we're stuck in the pre-drop view (current bug).
	//   * static EGP_Combat(7)     : S73/S77 proved the loading screen NEVER clears (the client got
	//                                "Entering combat phase" but stayed behind the overlay) — a cold jump
	//                                to 7 skips the state machine the client expects to follow.
	// So: keep seeding 4 (the S70-proven loading-clear), then STEP to 7 once a client has joined.
	void AdvanceRoundPhase();
	FTimerHandle PhaseTimer;
	int32 PhaseStep = 0;

	// Session 70: after the GameState is spawned, seed our ALokiGameState mirror into a PLAYING
	// state (CurrentPhase + a minimal MatchStartDetails) so the DS-route client leaves the tutorial
	// loading screen. See LokiGameStateStub.h.
	virtual void InitGameState() override;
};
