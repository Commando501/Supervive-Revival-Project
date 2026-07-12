// LokiPlayerStateStub — session 73 (2026-07-11): native mirror of the client's LokiPlayerState so the
// DS-route client's local PlayerState is a LOKI-typed PlayerState instead of a stock APlayerState.
//
// WHY (the gate after the S73 LokiPlayerController mirror)
// -------------------------------------------------------
// With the Loki-PC mirror in place the client sits stable in LVL_Tutorial with a real LokiPlayerController,
// but logs "GetLocalLokiPlayerState failed to get a player state" — its PlayerState is the stub's default
// stock APlayerState, so the cast to LokiPlayerState returns null (same shape as the TryGetLocalLokiController
// wall the PC mirror fixed). Fix: set the stub's PlayerStateClass to this native ALokiPlayerState (path
// /Script/Loki.LokiPlayerState) so the client resolves it to ITS OWN native LokiPlayerState and the cast
// succeeds. Same NetGUID-by-path trick as ALokiGameState (S70) / ALokiPlayerController (S73).
//
// CLIENT HIERARCHY + SCHEMA (S73 live capture off the running client)
// -------------------------------------------------------------------
//   LokiPlayerState : PlayerState : Info : LokiActor : Actor : Object   (94 total props)
// Replicated (CPF_Net) subset — TINY: LokiPlayerState adds exactly 1 rep + 7 own net functions:
//   rep:  HeroClass (ClassProperty -> 1 NetGUID cmd)
//   RPCs: ClientUIEvent, ClientUpdateDeathRecapDamage, ClientVisibleSetDelta, ClientVisionExpirySet,
//         ServerSetRankedPointsOverride, ServerSetReadyToPlay, ServerVisibleSetAck
// The stock APlayerState base level already replicates cleanly in this stub (S53 un-suppressed PlayerState),
// so only LokiPlayerState's own 1 rep + 7 RPCs need adding to align the FClassNetCache index space. Empty RPC
// bodies suffice for INDEX alignment; add real params to any that fire + desync (cf. the PC's ServerFillTeam).
// KNOWN CANDIDATE TO FIRE: ServerSetReadyToPlay (client tells server it's ready — like the PC's ServerFillTeam).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"
#include "LokiPlayerStateStub.generated.h"

UCLASS(transient)
class ALokiPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	ALokiPlayerState(const FObjectInitializer& ObjectInitializer);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// Sole CPF_Net prop on the client's LokiPlayerState (S73 live). ClassProperty == 1 NetGUID cmd; kept null
	// (the cast to LokiPlayerState is what matters, not the value).
	UPROPERTY(Replicated) TSubclassOf<AActor> HeroClass = nullptr;

	// 7 own net functions (S73 live netfields_dump; engine name-sorts NetFields at runtime). Empty bodies.
	UFUNCTION(Client, Reliable)   void ClientUIEvent();
	UFUNCTION(Client, Reliable)   void ClientUpdateDeathRecapDamage();
	UFUNCTION(Client, Unreliable) void ClientVisibleSetDelta();
	UFUNCTION(Client, Unreliable) void ClientVisionExpirySet();
	UFUNCTION(Server, Reliable)   void ServerSetRankedPointsOverride();
	UFUNCTION(Server, Reliable)   void ServerSetReadyToPlay();
	UFUNCTION(Server, Unreliable) void ServerVisibleSetAck();
};
