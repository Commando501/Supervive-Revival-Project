#include "LokiStubGameMode.h"
#include "LokiStubPlayerController.h"
#include "GameFramework/PlayerController.h"
#include "Engine/NetConnection.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStubGM, Log, All);

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
}
