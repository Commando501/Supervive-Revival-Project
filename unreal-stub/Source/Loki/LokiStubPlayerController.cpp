#include "LokiStubPlayerController.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStubPC, Log, All);

ALokiStubPlayerController::ALokiStubPlayerController(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Session 26 finding: cannot override ServerVerifyViewTarget with different
	// UFUNCTION params via subclass — UHT enforces parameter parity. See header
	// comment for details and session 27 plan.
	UE_LOG(LogLokiStubPC, Display,
	       TEXT("LokiStubPlayerController constructed (session 26 — stock override enforced)"));
}
