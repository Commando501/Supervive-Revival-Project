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

// Mirror of the client's ECharacterCustomAnimationState (LokiCharacter.CustomAnimationState).
//
// ★ S84 — THE VALUE COUNT IS LOAD-BEARING. This enum previously had ONE value with the comment
// "never sent to the owning client (COND_SimulatedOnly), so the bit-width is irrelevant". That was
// WRONG and it cost a live run: UE serialises an FEnumProperty at CeilLogTwo(NumValues) bits, so a
// 1-value mirror is NARROWER on the wire than the client's 3-value enum, and the stub's RECEIVE path
// desynced -> "ReceivedBunch: Invalid replicated field 32 in LokiMinionCharacter" -> channel closed.
// COND_SimulatedOnly governs what we SEND to the owner; it gives no protection when we READ.
// Same bug class S70 solved on the GameState mirror's ERoundPhase/ELokiDayNightState ("matching
// value ranges keeps CeilLogTwo aligned").
//
// Values from usmapdump schema.txt:58612 (enum VALUE LISTS are reliable in the usmap — its known
// unreliability is CONTAINER ELEMENT types). The _MAX sentinel is part of the client's 3, so it is
// reproduced here verbatim to keep GetMaxEnumValue/CeilLogTwo identical.
UENUM()
enum class ELokiCustomAnimationStateMirror : uint8
{
	LCAS_None = 0,
	LCAS_CustomAbility_1 = 1,
	LCAS_MAX = 2,
};

UCLASS(transient)
class ALokiCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ALokiCharacter(const FObjectInitializer& ObjectInitializer);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// --- LokiCharacter own CPF_Net props, in client field order. COND_SimulatedOnly (see header). ---
	// ★ S85 CORRECTION: the client's LokiCharacter has 13 own CPF_Net props, NOT 2. S73/S84's "2" was a
	// rep_expand_class.py i<40 child-walk CAP BUG (the other 11 sit at ChildProperties positions 49..158;
	// tools/re/netcache_chain.py full-walk found all 13; docs/session-85-netcache-chain-diff.md). The
	// stub-at-2 left LokiCharacter's field-cache 11 indices short, which would desync the NEXT bunch after
	// the Character-tier field-32 fix. All 13 are COND_SimulatedOnly => never sent to the autonomous owner,
	// so they hold ClassReps slots purely to align the index space; their wire format cannot desync the owner.
	// The 4 client StructProperty fields (RepMovement{FollowActor,Glide,Grind} + ServerRotation) are declared
	// here as scalar placeholders: each is still ONE ClassReps entry (index alignment is by property count,
	// not leaf-cmd count) and, being COND_SimulatedOnly, is never serialized — so exact struct wire format is
	// a later hydration concern, not needed to clear the index desync. Real struct types (for future
	// simulated-proxy work): LokiRepCharacterMovement_FollowActor / _Glide / _Grind (member-wise) + Rotator.
	UPROPERTY(Replicated) float OutOfBoundsBufferTimeRemaining = 0.f;
	UPROPERTY(Replicated) ELokiCustomAnimationStateMirror CustomAnimationState = ELokiCustomAnimationStateMirror::LCAS_None;
	UPROPERTY(Replicated) bool    bIdle = false;
	UPROPERTY(Replicated) bool    bCharacterMovementEnabled = false;
	UPROPERTY(Replicated) int32   MaxLevel = 0;
	UPROPERTY(Replicated) int32   Experience = 0;
	UPROPERTY(Replicated) int32   RepMovementFollowActor = 0;      // placeholder for LokiRepCharacterMovement_FollowActor
	UPROPERTY(Replicated) int32   RepMovementGlide = 0;            // placeholder for LokiRepCharacterMovement_Glide
	UPROPERTY(Replicated) int32   RepMovementGrind = 0;            // placeholder for LokiRepCharacterMovement_Grind
	UPROPERTY(Replicated) int32   RepMovementServerRotation = 0;   // placeholder for Rotator (NetSerialize)
	UPROPERTY(Replicated) uint8   LivingState = 0;
	UPROPERTY(Replicated) int32   DebugModes = 0;                  // client UInt32Property
	UPROPERTY(Replicated) bool    bWallJumped = false;

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

// ---------------------------------------------------------------------------------------------------
// ALokiMinionCharacter — S84. THE POSSESSED CLASS. ALokiCharacter above CANNOT be possessed:
// the CLIENT's /Script/Loki.LokiCharacter is CLASS_Abstract (ClassFlags@+0xDC = 0x30D008A5, bit0 set;
// offset pinned + cross-validated in docs/session-84-hero-mirror-scope.txt §5, and independently
// confirmed by the S77 live log "SpawnActor failed because class LokiCharacter is abstract"). An
// abstract class cannot be instantiated CLIENT-SIDE, so the replica never forms -> PC->Pawn is
// null/half-formed -> the movement machinery dereferences garbage -> execute-AV. That is exactly why
// S77 reverted the GameMode to a stock ADefaultPawn.
//
// LokiHeroCharacter is ALSO abstract (0x30D008A5, byte-identical), so it is NOT usable either.
// Live enumeration of every UClass descending from LokiCharacter found exactly two, and
// **LokiMinionCharacter (0x30D000A4) is the ONLY CONCRETE one** — so it is the only Loki-typed
// character the client can actually spawn, and therefore the only one we can possess.
//
// WHAT THIS TESTS: whether SERVER-AUTHORITATIVE possession + replicated movement works at all in this
// session. A minion is not a hero (no kit/abilities), but the mechanism is identical, and every prior
// movement attempt was a CLIENT-side hack that froze the CMC (S81). If the client possesses this and
// WASD produces replicated movement, the DS route has real character control for the first time.
//
// SCHEMA (S84 live capture, docs/s84-lokiminioncharacter-schema.txt): 3 own CPF_Net props + 1 net func.
// COND_SimulatedOnly on the props for the same reason as the base: this pawn is the AUTONOMOUS proxy of
// the owning client, so simulated-only props are never sent to it — they hold their ClassReps slots for
// index alignment but cannot desync the owner on the wire.
UCLASS(transient)
class ALokiMinionCharacter : public ALokiCharacter
{
	GENERATED_BODY()

public:
	ALokiMinionCharacter(const FObjectInitializer& ObjectInitializer);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// --- own CPF_Net props, in field order (S84 live) ---
	UPROPERTY(Replicated) float AggroRange = 0.f;
	UPROPERTY(Replicated) bool bIsCowering = false;
	// LootMajorReward is a ClassProperty on the client. Any UClass reference serialises as ONE
	// PropertyObject cmd, so the exact TSubclassOf<T> does not affect the wire (the S54 Missions lesson:
	// object/class refs are 1 cmd regardless of the pointee type).
	UPROPERTY(Replicated) TSubclassOf<AActor> LootMajorReward;

	// --- 1 own net function (Multicast, Reliable) — empty stub, NetFields index alignment only ---
	UFUNCTION(NetMulticast, Reliable) void LostLastAggroTarget();
};
