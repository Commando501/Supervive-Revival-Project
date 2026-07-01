#include "LokiStubGameMode.h"
#include "LokiStubPlayerController.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStubGM, Log, All);

ALokiStubGameMode::ALokiStubGameMode(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PlayerControllerClass = ALokiStubPlayerController::StaticClass();
	UE_LOG(LogLokiStubGM, Display,
	       TEXT("LokiStubGameMode constructed with PlayerControllerClass=LokiStubPlayerController"));
}
