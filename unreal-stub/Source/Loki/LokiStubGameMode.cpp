#include "LokiStubGameMode.h"
#include "LokiStubPlayerController.h"
#include "GameFramework/PlayerController.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStubGM, Log, All);

ALokiStubGameMode::ALokiStubGameMode(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Session 23: use STOCK APlayerController so the client can resolve the class
	// GUID and spawn a PC actor. This lets the client actually SEND the
	// ServerVerifyViewTarget RPC to us (session 20 established this works up to
	// the RPC deserialization). Session 23 goal is capturing the RPC bytes for
	// signature RE — we need the RPC to actually fire on the server first.
	//
	// LokiStubPlayerController is retained for session 24 when we'll swap back
	// to it (with the matching UFUNCTION signature).
	PlayerControllerClass = APlayerController::StaticClass();
	UE_LOG(LogLokiStubGM, Display,
	       TEXT("LokiStubGameMode constructed with PlayerControllerClass=APlayerController (session 23 RE mode)"));
}
