// LokiCharacterStub — session 73 Phase 1 (2026-07-11): native mirror of the client's LokiCharacter (the
// HERO pawn), so the stub can spawn + possess a Loki-typed hero and test whether the DS client takes hero
// control. THE GO/NO-GO for the whole hero/round reconstruction (docs/session-73-hero-reconstruction-scope.md).
//
// WHY / WHAT WE'RE TESTING
// -----------------------
// The client sits as a dead spectator because it never drops in / possesses a hero. The stub's DefaultPawn
// possession is refused (SUPERVIVE gates possession on its drop-in/hero flow). Phase 1 asks the make-or-break
// question cheaply: if the stub spawns + possesses a Loki-TYPED character (ALokiCharacter, path
// /Script/Loki.LokiCharacter — the by-path trick as with the PC/PlayerState/GameState), will the client take
// HERO CONTROL of it (leave the loading screen / dead-spectator, attach view, engage input)? If yes → the rest
// of the reconstruction is incremental. If no → the client requires the real server's round machinery = the
// honest final wall.
//
// SCHEMA (S73 live capture) — SMALL:
//   LokiCharacter : Character : Pawn : LokiActor : Actor  → mirror is ALokiCharacter : ACharacter (stock base).
//   Own CPF_Net props (2): OutOfBoundsBufferTimeRemaining (float), CustomAnimationState (enum).
//   Own net functions (14): all DEBUG/CHEAT/COSMETIC (ServerCheat*/ServerSuicide/ServerGetDebugStatString/
//     ServerSetCharacterDebugMode/ClientDebugMessage/ClientUpdateDebugString/ClientPlayHitReact/ClientPlayJumpCue/
//     ClientSetJumpZ/ClientEngage-DisengageYawLock) — none gameplay-critical, so empty stubs align the NetFields
//     index (like the PC's 60). Movement RPCs (ServerMovePacked/ClientMoveResponsePacked/ClientAdjustPosition)
//     are STOCK ACharacter, inherited — Phase 4 concern.
//   The base ACharacter/APawn/AActor tiers matched STOCK UE5.4 live (10 char props + 7 char net funcs, all
//   non-push DOREPLIFETIME_CONDITION), so calling Super preserves the exact conditions. The two own props are
//   registered COND_SimulatedOnly: the client OWNS this character (autonomous proxy), so COND_SimulatedOnly
//   props are NEVER sent to it — they stay in ClassReps for index alignment but their wire format (incl. the
//   enum bit-width) can't desync the owner. Refine to real conditions later if a simulated proxy is ever added.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "LokiCharacterStub.generated.h"

// Placeholder for LokiCharacter.CustomAnimationState (FEnumProperty). Never sent to the owning client
// (COND_SimulatedOnly), so the value range/bit-width is irrelevant for Phase 1; kept minimal.
UENUM()
enum class ELokiCustomAnimationStateMirror : uint8
{
	LCAS_None = 0,
};

UCLASS(transient)
class ALokiCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ALokiCharacter(const FObjectInitializer& ObjectInitializer);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// --- LokiCharacter own CPF_Net props (S73 live), in field order. COND_SimulatedOnly (see header). ---
	UPROPERTY(Replicated) float OutOfBoundsBufferTimeRemaining = 0.f;
	UPROPERTY(Replicated) ELokiCustomAnimationStateMirror CustomAnimationState = ELokiCustomAnimationStateMirror::LCAS_None;

	// --- 14 own net functions (S73 live netfields_dump; engine name-sorts NetFields). Empty stubs. ---
	UFUNCTION(Client, Reliable)       void ClientDebugMessage();
	UFUNCTION(Client, Unreliable)     void ClientDisengageYawLock();
	UFUNCTION(Client, Unreliable)     void ClientEngageYawLock();
	UFUNCTION(NetMulticast, Unreliable) void ClientPlayHitReact();
	UFUNCTION(NetMulticast, Unreliable) void ClientPlayJumpCue();
	UFUNCTION(NetMulticast, Reliable)   void ClientSetJumpZ();
	UFUNCTION(Client, Reliable)       void ClientUpdateDebugString();
	UFUNCTION(Server, Reliable)       void ServerCheatExperience();
	UFUNCTION(Server, Reliable)       void ServerCheatInfinite();
	UFUNCTION(Server, Reliable)       void ServerCheatResetCooldowns();
	UFUNCTION(Server, Reliable)       void ServerCheatTeleportNear();
	UFUNCTION(Server, Reliable)       void ServerGetDebugStatString();
	UFUNCTION(Server, Reliable)       void ServerSetCharacterDebugMode();
	UFUNCTION(Server, Reliable)       void ServerSuicide();
};
