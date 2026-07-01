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
};
