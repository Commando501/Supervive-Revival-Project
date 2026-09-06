#include "LokiCharacterStub.h"
#include "Net/UnrealNetwork.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiCharStub, Log, All);

ALokiCharacter::ALokiCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	bReplicates = true;
	SetReplicateMovement(true);
	bAlwaysRelevant = true; // guarantee the send to the one connection (Possess drives view target via the
	                        // ClientSetViewTarget RPC the stub suppresses; alwaysRelevant is belt-and-suspenders)
	UE_LOG(LogLokiCharStub, Display,
	       TEXT("ALokiCharacter constructed (/Script/Loki.LokiCharacter mirror; S85: 13 own reps + 14 RPCs over "
	            "a 12-rep Character tier — client-matched net-cache)."));
}

// Register an ACharacter inherited replicated prop BY NAME with its stock condition, non-push. We do NOT call
// ACharacter::GetLifetimeReplicatedProps because it registers RepRootMotion via DOREPLIFETIME_CONDITION — which
// FATALs ("Attempt to replicate property not tagged") now that we strip RepRootMotion's CPF_Net (Loki.cpp) to
// match SUPERVIVE's ACharacter (10 reps, no RepRootMotion). So we call APawn::Super (no RepRootMotion) and
// re-register ACharacter's OTHER 8 conditional props by name with the exact stock conditions. (JumpMaxHoldTime/
// JumpMaxCount are CPF_Net-in-ClassReps but NOT in ACharacter's lifetime list on either side — leave them out.)
static void AddCharRep(TArray<FLifetimeProperty>& Out, const TCHAR* Name, ELifetimeCondition Cond)
{
	if (FProperty* P = FindFProperty<FProperty>(ACharacter::StaticClass(), Name))
	{
		Out.Add(FLifetimeProperty(P->RepIndex, Cond));
	}
}

void ALokiCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	// APawn/AActor tier (non-push; no stripped props there).
	APawn::GetLifetimeReplicatedProps(OutLifetimeProps);
	// ACharacter's 8 conditional reps by name, EXCLUDING the stripped RepRootMotion, exact stock conditions:
	AddCharRep(OutLifetimeProps, TEXT("ReplicatedBasedMovement"),                    COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("ReplicatedServerLastTransformUpdateTimeStamp"), COND_SimulatedOnlyNoReplay);
	AddCharRep(OutLifetimeProps, TEXT("ReplicatedMovementMode"),                     COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("bIsCrouched"),                                COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("bProxyIsJumpForceApplied"),                   COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("AnimRootMotionTranslationScale"),             COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("ReplicatedGravityDirection"),                 COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("ReplayLastTransformUpdateTimeStamp"),         COND_ReplayOnly);
	// S85: the two SUPERVIVE-only Character reps injected onto ACharacter by Loki.cpp InjectCharacterExtraReps
	// (ReplicatedCharacterMovement + ReplicatedGravityScale). Register COND_SimulatedOnly by name so they are
	// NEVER sent to the autonomous owner — they exist only to make the Character tier 12 reps (client-matched)
	// so ServerMovePacked lands at field-cache index 32 on both sides. Without these two the stub errors
	// "Invalid replicated field 32 in LokiMinionCharacter" (docs/session-85-netcache-chain-diff.md).
	AddCharRep(OutLifetimeProps, TEXT("ReplicatedCharacterMovement"),                COND_SimulatedOnly);
	AddCharRep(OutLifetimeProps, TEXT("ReplicatedGravityScale"),                     COND_SimulatedOnly);
	// Our 13 own props (S85: was 2; the client has 13 — see LokiCharacterStub.h). ALL COND_SimulatedOnly
	// (never sent to the autonomous owner → wire format / enum bit-width can't desync; slots align the index).
	DOREPLIFETIME_CONDITION(ALokiCharacter, OutOfBoundsBufferTimeRemaining, COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, CustomAnimationState,           COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, bIdle,                          COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, bCharacterMovementEnabled,      COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, MaxLevel,                       COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, Experience,                     COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, RepMovementFollowActor,         COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, RepMovementGlide,               COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, RepMovementGrind,               COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, RepMovementServerRotation,      COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, LivingState,                    COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, DebugModes,                     COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, bWallJumped,                    COND_SimulatedOnly);
}

// --- S73: empty _Implementation bodies for the 14 mirrored net RPCs (NetFields index alignment only). ---
void ALokiCharacter::ClientDebugMessage_Implementation() {}
void ALokiCharacter::ClientDisengageYawLock_Implementation() {}
void ALokiCharacter::ClientEngageYawLock_Implementation() {}
void ALokiCharacter::ClientPlayHitReact_Implementation() {}
void ALokiCharacter::ClientPlayJumpCue_Implementation() {}
void ALokiCharacter::ClientSetJumpZ_Implementation() {}
void ALokiCharacter::ClientUpdateDebugString_Implementation() {}
void ALokiCharacter::ServerCheatExperience_Implementation() {}
void ALokiCharacter::ServerCheatInfinite_Implementation() {}
void ALokiCharacter::ServerCheatResetCooldowns_Implementation() {}
void ALokiCharacter::ServerCheatTeleportNear_Implementation() {}
void ALokiCharacter::ServerGetDebugStatString_Implementation() {}
void ALokiCharacter::ServerSetCharacterDebugMode_Implementation() {}
void ALokiCharacter::ServerSuicide_Implementation() {}

// ===================================================================================================
// ALokiMinionCharacter (S84) — the ONLY CONCRETE Loki-typed character on the client, hence the only
// one the client can instantiate as a replica, hence the only one we can possess. See the header for
// why ALokiCharacter / LokiHeroCharacter (both CLASS_Abstract) cannot be used.
// ===================================================================================================
ALokiMinionCharacter::ALokiMinionCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Base ctor already sets bReplicates / SetReplicateMovement(true) / bAlwaysRelevant.
	UE_LOG(LogLokiCharStub, Display,
	       TEXT("ALokiMinionCharacter constructed (/Script/Loki.LokiMinionCharacter mirror; 3 own reps + 1 RPC "
	            "over ALokiCharacter — S84 possession test; this is the CONCRETE class the client can spawn)."));
}

void ALokiMinionCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	// Super = ALokiCharacter, which already does the APawn tier + ACharacter's 8 by-name conditional reps
	// (skipping the stripped RepRootMotion) + its own 2. Safe to chain — it is all non-push.
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	// Our 3 own props, COND_SimulatedOnly (never sent to the autonomous owner; slots kept for alignment).
	DOREPLIFETIME_CONDITION(ALokiMinionCharacter, AggroRange, COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiMinionCharacter, bIsCowering, COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiMinionCharacter, LootMajorReward, COND_SimulatedOnly);
}

// Empty stub — present only so the class carries the FUNC_Net UFunction for NetFields index alignment.
void ALokiMinionCharacter::LostLastAggroTarget_Implementation() {}
