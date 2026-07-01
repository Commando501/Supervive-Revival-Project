// LokiStubPlayerController — PC subclass that DOES NOT REPLICATE.
//
// Session 21 blocker: after sessions 17-20 unblocked handshake + login + PC
// spawn + client-side actor instantiation, the client's PC calls
// ServerVerifyViewTarget RPC back to server. SUPERVIVE ships MODIFIED engine
// base classes (session 20 confirmed via per-class NetworkChecksum mismatches
// on PlayerController, HUD, GameStateBase, GameModeBase, PlayerState, etc.).
// The RPC deserialization fails at Reader.GetBitsLeft() != 0 because stock
// APlayerController::ServerVerifyViewTarget takes 0 parameters but the
// SUPERVIVE version sends ~2894 bits of arguments.
//
// First-attempt fix: don't replicate the PC at all. The server still spawns
// a PC (needed for AGameModeBase::PostLogin plumbing and Connection->PlayerController
// bookkeeping), but the client never receives it, so it never spawns a
// client-side PC, so no PC-level RPCs come back.
//
// Registered as the PlayerControllerClass on ULokiStubGameMode.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "LokiStubPlayerController.generated.h"

UCLASS(transient)
class ALokiStubPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ALokiStubPlayerController(const FObjectInitializer& ObjectInitializer);
};
