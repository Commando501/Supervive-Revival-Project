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
};
