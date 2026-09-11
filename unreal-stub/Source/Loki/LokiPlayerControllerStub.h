// LokiPlayerControllerStub — session 73 (2026-07-11): a native mirror of the client's
// LokiPlayerController hierarchy, so the DS-route client's LOCAL networked PlayerController
// is a LOKI-typed controller instead of a stock APlayerController.
//
// WHY THIS EXISTS (the go/no-go for the whole dedicated-server route)
// ------------------------------------------------------------------
// S70 put the client into the live tutorial world as a spectator with a valid replicated
// LokiGameState. S71/S72 then hit the wall: the client REFUSES to grant hero control because
// its local networked PC is a STOCK APlayerController — SUPERVIVE's gameplay logs
// "Attempting to get null controller. Use TryGetLocalLokiController" (a cast to the Loki PC
// type that returns null on a stock PC). Every route (force-open S63, missions-DS, S71 pawn,
// S72 hybrid) converges here: hero control is tied to a LOKI PlayerController.
//
// A networked client's local PC == the SERVER's PlayerControllerClass, resolved by class
// NetGUID. If the stub's PlayerControllerClass is a NATIVE class named LokiPlayerController
// (path /Script/Loki.LokiPlayerController — the stub module is also "Loki"), the client
// resolves that path to ITS OWN native LokiPlayerController and instantiates it locally, so
// the TryGetLocalLokiController cast should finally succeed. This is the same NetGUID-by-path
// trick that made ALokiGameState (S70) and ALokiPlayerState_Missions (S54) work — now applied
// to the PC, which is the exact class S41 had to keep as stock because of RPC-signature
// divergence. The matured S70 schema-injection technique is worth re-attacking it with.
//
// CLIENT HIERARCHY (schema.txt / usmap):
//   BP_LokiPlayerController_Dev_C (BP)  : LokiPlayerController (78 own props)
//                                       : LokiBaseController   (2 own props)
//                                       : PlayerController (stock) : Controller : ...
// We mirror the two NATIVE ancestors (ALokiBaseController, ALokiPlayerController). The client's
// actual tutorial PC is the BP, but its gameplay/control logic is NATIVE on LokiPlayerController,
// so a native LokiPlayerController should satisfy the TryGetLocalLokiController cast (same logic
// as using native LokiGameState in place of BP_LokiGameState_Tutorial_C, S70).
//
// FIRST BUILD = ZERO added replicated props (single-variable diagnostic baseline)
// -------------------------------------------------------------------------------
// The usmap lists all 78+2 props but CANNOT tell us which are CPF_Net (replicated) — and the
// project convention is single-variable + live-verified (the usmap has been wrong for
// replicated shapes repeatedly). So the FIRST build declares NO own replicated props: the
// mirror carries only the inherited stock PC reps + the injected AActor.ServerState. On the
// live test the client resolves its own LokiPlayerController and reads the initial bunch
// against ITS RepLayout; the first Loki-specific replicated field it expects but we don't
// provide surfaces as "ReceivedBunch: Invalid replicated field N in <PC>" — N scopes the prop
// list to reconstruct next (exactly how S41 N=0 -> ServerState, and S69 built the GameState
// prop list). NetworkChecksumMode is None (LokiNetDriver::InitBase) so there is no
// fingerprint-reject; the client attempts deserialize and gives us the diagnostic.
//
// KNOWN NEXT WALL (be honest): the PC is RPC-heavy and bidirectional. Once the client's local
// PC is a LokiPlayerController it will SEND Loki PC RPCs to the stub (ServerVerifyViewTarget —
// already handled via the 40-param inject in Loki.cpp — and likely others). Each unmatched RPC
// desyncs the SERVER's receive path (unlike a one-way GameState prop desync we can suppress).
// The live test's job is to reveal how far the connection gets and on WHAT (prop N vs an RPC),
// which is the data that decides whether the full mirror is tractable.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "LokiPlayerControllerStub.generated.h"

// Mirror of the client's native LokiBaseController : PlayerController. Its 2 usmap props
// (OnGameplayInputReset delegate, AutoMatchmakeComponent object ref) are almost certainly NOT
// replicated, so we add none — but we keep the class in the chain so the stub's ClassNetCache
// super-walk accumulates indices the same way the client's does (LokiBaseController occupies its
// own hierarchy level even with 0 net fields).
UCLASS(transient)
class ALokiBaseController : public APlayerController
{
	GENERATED_BODY()

public:
	ALokiBaseController(const FObjectInitializer& ObjectInitializer);
};

// Mirror of the client's native LokiPlayerController : LokiBaseController. Path
// /Script/Loki.LokiPlayerController so the client binds it to its own class. Registered as
// ULokiStubGameMode::PlayerControllerClass. ZERO own replicated props in this first build (see
// header) — the live "Invalid replicated field N" scopes what to add here next, in the exact
// field order the client expects (capture with tools/re/rep_expand_class.py on LokiPlayerController).
UCLASS(transient)
class ALokiPlayerController : public ALokiBaseController
{
	GENERATED_BODY()

public:
	ALokiPlayerController(const FObjectInitializer& ObjectInitializer);

	// --- S73 reconstruction: 1 replicated prop + 60 net RPCs captured LIVE off the client's
	// LokiPlayerController (docs/session-73-lokipc-netcache-capture.txt) so the mirror's ClassReps +
	// name-sorted NetFields index space matches the client's (closes the 61-field gap that desynced
	// the shared reliable stream: client GetMaxIndex 160 vs stub 99). LokiPlayerCheats is the sole
	// CPF_Net prop (1 NetGUID cmd). The 60 UFUNCTIONs match the client name/direction/reliability;
	// EMPTY bodies suffice for INDEX alignment — add real params only to the ones that fire + desync
	// (ServerVerifyViewTarget-style runtime param inject in Loki.cpp).
	UPROPERTY(Replicated) TObjectPtr<UObject> LokiPlayerCheats = nullptr;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// --- 60 LokiPlayerController own net functions (engine name-sorts NetFields at runtime) ---
	UFUNCTION(Server, Reliable) void AuthCheatChangeCharacter();
	UFUNCTION(Client, Reliable) void ClientAddPersistentMessage();
	UFUNCTION(Client, Reliable) void ClientDebugMessage();
	UFUNCTION(Client, Reliable) void ClientDebugMessageLocation();
	UFUNCTION(Client, Reliable) void ClientDrawDebugBox();
	UFUNCTION(Client, Reliable) void ClientDrawDebugCapsule();
	UFUNCTION(Client, Reliable) void ClientDrawDebugLine();
	UFUNCTION(Client, Reliable) void ClientDrawDebugSlice();
	UFUNCTION(Client, Reliable) void ClientDrawDebugSphere();
	UFUNCTION(Client, Reliable) void ClientExecuteLocalGameplayCue();
	UFUNCTION(Client, Unreliable) void ClientExecuteUnownedGameplayCue();
	UFUNCTION(Client, Unreliable) void ClientGetServerPerfInfo();
	UFUNCTION(Server, Reliable) void ClientNotifiesServerTransferCompleted();
	UFUNCTION(Client, Reliable) void ClientNotifyAFKDetected();
	UFUNCTION(Client, Unreliable) void ClientNotifyCharacterBountyReceived();
	UFUNCTION(Client, Unreliable) void ClientNotifyDamageDealt();
	UFUNCTION(Client, Unreliable) void ClientNotifyDamageTaken();
	UFUNCTION(Client, Unreliable) void ClientNotifyHealingDealt();
	UFUNCTION(Client, Unreliable) void ClientNotifyHealingTaken();
	UFUNCTION(Client, Unreliable) void ClientNotifyNonBountyXPReceived();
	UFUNCTION(Client, Reliable) void ClientNotifyStatusUpdate();
	UFUNCTION(Client, Reliable) void ClientNotifyTrainingEvent();
	UFUNCTION(Client, Reliable) void ClientPlatformDisconnect();
	UFUNCTION(Client, Unreliable) void ClientPlayAudioAtLocation();
	UFUNCTION(Client, Unreliable) void ClientProcessTimestampEcho();
	UFUNCTION(Client, Unreliable) void ClientRecordCameraShakeEditor();
	UFUNCTION(Client, Reliable) void ClientUpdateDebugPoints();
	UFUNCTION(Client, Reliable) void ClientUpdateDebugStrings();
	UFUNCTION(Server, Reliable) void DebugServerResetObjects();
	UFUNCTION(Server, Reliable) void NetProfile();
	UFUNCTION(Client, Unreliable) void SendPlayerGameLog();
	UFUNCTION(Server, Reliable) void ServerAddAbilityLevelNative();
	UFUNCTION(Server, Reliable) void ServerConsoleCommand();
	UFUNCTION(Server, Reliable) void ServerDebugAdvanceTime();
	UFUNCTION(Server, Reliable) void ServerDebugSetTime();
	UFUNCTION(Server, Reliable) void ServerDebugTimelineAddEvent();
	UFUNCTION(Server, Reliable) void ServerDebugTimelineReset();
	UFUNCTION(Server, Reliable) void ServerDebugTimelineResetAndPause();
	UFUNCTION(Server, Reliable) void ServerDebugTimelineResume();
	UFUNCTION(Server, Unreliable) void ServerEchoTimestamp();
	UFUNCTION(Server, Reliable) void ServerFillTeam(int32 NewTeamIndex);              // S73: real sig (fires at match entry; empty stub killed the connection)
	UFUNCTION(Server, Reliable) void ServerJoinTeam(int32 NewTeamIndex);              // S73: real sig (team-setup flow)
	UFUNCTION(Server, Reliable) void ServerLogTrainingAnalytics();
	UFUNCTION(Client, Reliable) void ServerNotifiesClientTransferCompleted();
	UFUNCTION(Client, Unreliable) void ServerNotifyDiedToAbyss();
	UFUNCTION(Server, Reliable) void ServerOverrideDropPlaneLocations();
	UFUNCTION(Server, Reliable) void ServerPlatformDisconnect();
	UFUNCTION(Server, Reliable) void ServerRequestAdmin();
	UFUNCTION(Server, Reliable) void ServerRequestEACDisconnectForSelf();
	UFUNCTION(Server, Reliable) void ServerRequestSpawnLocation(FVector TargetLocation); // S73: real sig (drop-in spawn flow)
	UFUNCTION(Server, Reliable) void ServerReturnFromAFK();
	UFUNCTION(Server, Reliable) void ServerSelectItemEvolution();
	UFUNCTION(Server, Reliable) void ServerSelectItemFancyPassive();
	UFUNCTION(Server, Reliable) void ServerSetDebugMode();
	UFUNCTION(Server, Reliable) void ServerSetDebugTarget();
	UFUNCTION(Server, Reliable) void ServerSetGameFeatureToggle();
	UFUNCTION(Server, Reliable) void ServerSpectateNextTeam();
	UFUNCTION(Server, Reliable) void ServerSwitchSpectateTeam(int32 TeamIndex);        // S73: real sig (spectate flow)
	UFUNCTION(Server, Reliable) void ServerToggleDebugMode();
	UFUNCTION(Server, Reliable) void ServerTriggerControllerCheatCommand();
};
