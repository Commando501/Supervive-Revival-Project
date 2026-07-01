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

	// Session 26 FINDING: Cannot override stock APlayerController's
	// ServerVerifyViewTarget with different parameters via UFUNCTION macro.
	// UHT rejects with: "Override of UFUNCTION 'ServerVerifyViewTarget' in
	// parent 'APlayerController' cannot have a UFUNCTION() declaration above
	// it; it will use the same parameters as the original declaration."
	//
	// UE forces subclass UFUNCTION overrides to match parent's signature.
	// To add different parameters, we need either:
	//   (a) Runtime UClass function-table manipulation (add UFunction with
	//       same name but different signature to subclass's FuncMap)
	//   (b) Rename our subclass's UClass path to /Script/Engine.PlayerController
	//       so client sees stock class and dispatches normally, then hook
	//       ProcessEvent to intercept the RPC name
	//   (c) Use engine source patch (not possible with Launcher install)
	//
	// Session 27 will attempt option (a) via UClass::CreateNetFunctions and
	// manual UFunction construction.
};
