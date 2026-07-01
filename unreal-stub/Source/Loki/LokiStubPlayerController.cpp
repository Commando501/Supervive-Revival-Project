#include "LokiStubPlayerController.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStubPC, Log, All);

ALokiStubPlayerController::ALokiStubPlayerController(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Session 21 experiment A: bReplicates=false + NetDormancy=DormantAll.
	// Outcome: still hit ActorChannelFailure(3) because CustomClass name doesn't
	// resolve client-side (SUPERVIVE has no /Script/Loki.LokiStubPlayerController
	// in its cooked package registry). Result=ControlChannelPlayerChannelFail.
	//
	// TODO (session 22): either RE SUPERVIVE's ServerVerifyViewTarget signature
	// via usmapdump on live game process and add a matching UFUNCTION to this
	// subclass, OR keep the class as stock APlayerController (via a runtime
	// class-rename or by removing this subclass) and find an RPC-suppression
	// mechanism.
	bReplicates = false;
	bAlwaysRelevant = false;
	NetDormancy = DORM_DormantAll;
	UE_LOG(LogLokiStubPC, Display,
	       TEXT("LokiStubPlayerController constructed (bReplicates=false, NetDormancy=DormantAll)"));
}
