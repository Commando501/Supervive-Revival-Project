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
	       TEXT("ALokiCharacter constructed (/Script/Loki.LokiCharacter mirror; 2 own reps + 14 RPCs over stock "
	            "ACharacter — S73 Phase 1 hero go/no-go)."));
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
	// Our 2 own props: COND_SimulatedOnly (never sent to the autonomous owner → enum bit-width can't desync).
	DOREPLIFETIME_CONDITION(ALokiCharacter, OutOfBoundsBufferTimeRemaining, COND_SimulatedOnly);
	DOREPLIFETIME_CONDITION(ALokiCharacter, CustomAnimationState, COND_SimulatedOnly);
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
