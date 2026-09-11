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

	// ★ S85 CORRECTION: the client's LokiPlayerState has 9 own CPF_Net props, NOT 1. The S73 "1 rep" was an
	// undercount (same family as the LokiCharacter/Character undercounts — tools/re/netcache_chain.py full-walk
	// found all 9; docs/session-85-netcache-chain-diff.md §7). The stub-at-1 left the LokiPlayerState tier 8
	// indices short, so ServerSetReadyToPlay (client field 36 — fired at "ENTERING THE BREACH") landed past the
	// stub's max index (30) => stub-side "ReadFieldHeaderAndPayload: Error reading numbits ... OutField:
	// RemoteRole". All 9 in client field order below. These replicate server->client (owner-relevant, unlike the
	// character's COND_SimulatedOnly), but the stub never writes them, so at default they equal the CDO and are
	// not sent — the slots exist purely to align the FClassNetCache index so ServerSetReadyToPlay lands at 36.
	// The struct/array fields (ParticipantMatchStartDetails=CoreGameParticipantDetails, WalletStorage=TArray)
	// are scalar placeholders: 1 ClassReps entry each, never serialized => exact wire format is a later hydration
	// concern (see §4 of the session doc), not needed to clear the index desync.
	UPROPERTY(Replicated) TSubclassOf<AActor> HeroClass = nullptr;   // ClassProperty (1 NetGUID cmd)
	UPROPERTY(Replicated) FString  PlatformPlayerID;
	UPROPERTY(Replicated) int32    SpectateTeamIndex = 0;
	UPROPERTY(Replicated) int32    ParticipantMatchStartDetails = 0; // placeholder for struct CoreGameParticipantDetails
	UPROPERTY(Replicated) int32    WalletStorage = 0;                // placeholder for TArray (ArrayProperty)
	UPROPERTY(Replicated) int32    GoldSpentValue = 0;
	UPROPERTY(Replicated) int32    ReplicatedTeamIndex = 0;
	UPROPERTY(Replicated) bool     IsAnonymousBot = false;
	UPROPERTY(Replicated) uint8    BattleRoyalePlayerPhase = 0;      // client EnumProperty

	// 7 own net functions (S73 live netfields_dump; engine name-sorts NetFields at runtime). Empty bodies.
	UFUNCTION(Client, Reliable)   void ClientUIEvent();
	UFUNCTION(Client, Reliable)   void ClientUpdateDeathRecapDamage();
	UFUNCTION(Client, Unreliable) void ClientVisibleSetDelta();
	UFUNCTION(Client, Unreliable) void ClientVisionExpirySet();
	UFUNCTION(Server, Reliable)   void ServerSetRankedPointsOverride();
	UFUNCTION(Server, Reliable)   void ServerSetReadyToPlay();
	UFUNCTION(Server, Unreliable) void ServerVisibleSetAck();
};
