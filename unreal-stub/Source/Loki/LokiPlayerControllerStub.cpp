#include "LokiPlayerControllerStub.h"
#include "Net/UnrealNetwork.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiPCStub, Log, All);

ALokiBaseController::ALokiBaseController(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// No own replicated props in the S73 baseline (see header). PlayerController already
	// bReplicates=true; leave defaults so the stub behaves like the stock-PC path that S41 got
	// replicating, only now Loki-TYPED so the client's TryGetLocalLokiController cast can succeed.
}

ALokiPlayerController::ALokiPlayerController(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	UE_LOG(LogLokiPCStub, Display,
	       TEXT("ALokiPlayerController constructed (S73 mirror, path /Script/Loki.LokiPlayerController; "
	            "zero own replicated props — diagnostic baseline for the Loki-PC accept test)."));
}

void ALokiPlayerController::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	// Sole CPF_Net prop on the client's LokiPlayerController (S73 live capture). Non-push; base tiers
	// are non-push too (stock-PC path replicated cleanly), so no bIsPushBased clash (cf. S70).
	DOREPLIFETIME(ALokiPlayerController, LokiPlayerCheats);
}

// --- S73: empty _Implementation bodies for the 60 mirrored net RPCs. Present only so the class
// carries the FUNC_Net UFunctions (NetFields index alignment); they intentionally do nothing. Add
// real params/behavior only to the ones that fire + desync in the live test. ---
void ALokiPlayerController::AuthCheatChangeCharacter_Implementation() {}
void ALokiPlayerController::ClientAddPersistentMessage_Implementation() {}
void ALokiPlayerController::ClientDebugMessage_Implementation() {}
void ALokiPlayerController::ClientDebugMessageLocation_Implementation() {}
void ALokiPlayerController::ClientDrawDebugBox_Implementation() {}
void ALokiPlayerController::ClientDrawDebugCapsule_Implementation() {}
void ALokiPlayerController::ClientDrawDebugLine_Implementation() {}
void ALokiPlayerController::ClientDrawDebugSlice_Implementation() {}
void ALokiPlayerController::ClientDrawDebugSphere_Implementation() {}
void ALokiPlayerController::ClientExecuteLocalGameplayCue_Implementation() {}
void ALokiPlayerController::ClientExecuteUnownedGameplayCue_Implementation() {}
void ALokiPlayerController::ClientGetServerPerfInfo_Implementation() {}
void ALokiPlayerController::ClientNotifiesServerTransferCompleted_Implementation() {}
void ALokiPlayerController::ClientNotifyAFKDetected_Implementation() {}
void ALokiPlayerController::ClientNotifyCharacterBountyReceived_Implementation() {}
void ALokiPlayerController::ClientNotifyDamageDealt_Implementation() {}
void ALokiPlayerController::ClientNotifyDamageTaken_Implementation() {}
void ALokiPlayerController::ClientNotifyHealingDealt_Implementation() {}
void ALokiPlayerController::ClientNotifyHealingTaken_Implementation() {}
void ALokiPlayerController::ClientNotifyNonBountyXPReceived_Implementation() {}
void ALokiPlayerController::ClientNotifyStatusUpdate_Implementation() {}
void ALokiPlayerController::ClientNotifyTrainingEvent_Implementation() {}
void ALokiPlayerController::ClientPlatformDisconnect_Implementation() {}
void ALokiPlayerController::ClientPlayAudioAtLocation_Implementation() {}
void ALokiPlayerController::ClientProcessTimestampEcho_Implementation() {}
void ALokiPlayerController::ClientRecordCameraShakeEditor_Implementation() {}
void ALokiPlayerController::ClientUpdateDebugPoints_Implementation() {}
void ALokiPlayerController::ClientUpdateDebugStrings_Implementation() {}
void ALokiPlayerController::DebugServerResetObjects_Implementation() {}
void ALokiPlayerController::NetProfile_Implementation() {}
void ALokiPlayerController::SendPlayerGameLog_Implementation() {}
void ALokiPlayerController::ServerAddAbilityLevelNative_Implementation() {}
void ALokiPlayerController::ServerConsoleCommand_Implementation() {}
void ALokiPlayerController::ServerDebugAdvanceTime_Implementation() {}
void ALokiPlayerController::ServerDebugSetTime_Implementation() {}
void ALokiPlayerController::ServerDebugTimelineAddEvent_Implementation() {}
void ALokiPlayerController::ServerDebugTimelineReset_Implementation() {}
void ALokiPlayerController::ServerDebugTimelineResetAndPause_Implementation() {}
void ALokiPlayerController::ServerDebugTimelineResume_Implementation() {}
void ALokiPlayerController::ServerEchoTimestamp_Implementation() {}
void ALokiPlayerController::ServerFillTeam_Implementation(int32 NewTeamIndex) {}
void ALokiPlayerController::ServerJoinTeam_Implementation(int32 NewTeamIndex) {}
void ALokiPlayerController::ServerLogTrainingAnalytics_Implementation() {}
void ALokiPlayerController::ServerNotifiesClientTransferCompleted_Implementation() {}
void ALokiPlayerController::ServerNotifyDiedToAbyss_Implementation() {}
void ALokiPlayerController::ServerOverrideDropPlaneLocations_Implementation() {}
void ALokiPlayerController::ServerPlatformDisconnect_Implementation() {}
void ALokiPlayerController::ServerRequestAdmin_Implementation() {}
void ALokiPlayerController::ServerRequestEACDisconnectForSelf_Implementation() {}
void ALokiPlayerController::ServerRequestSpawnLocation_Implementation(FVector TargetLocation) {}
void ALokiPlayerController::ServerReturnFromAFK_Implementation() {}
void ALokiPlayerController::ServerSelectItemEvolution_Implementation() {}
void ALokiPlayerController::ServerSelectItemFancyPassive_Implementation() {}
void ALokiPlayerController::ServerSetDebugMode_Implementation() {}
void ALokiPlayerController::ServerSetDebugTarget_Implementation() {}
void ALokiPlayerController::ServerSetGameFeatureToggle_Implementation() {}
void ALokiPlayerController::ServerSpectateNextTeam_Implementation() {}
void ALokiPlayerController::ServerSwitchSpectateTeam_Implementation(int32 TeamIndex) {}
void ALokiPlayerController::ServerToggleDebugMode_Implementation() {}
void ALokiPlayerController::ServerTriggerControllerCheatCommand_Implementation() {}
