// LokiNetDriver — UIpNetDriver subclass that wires up our custom
// LokiStatelessConnect handler and adapts outgoing traffic to TheoryCraft's
// 8-byte wrapper wire format.
//
// On InitConnectionlessHandler: construct LokiStatelessConnect directly
// (bypassing stock's hardcoded Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)
// factory lookup).
//
// On LowLevelSend for connectionless (handshake) replies: prepend the 8-byte
// TheoryCraft wrapper so the client's parser, which expects the wrapper,
// accepts our reply.
//
// Registered via DefaultEngine.ini [/Script/Engine.GameEngine] NetDriverDefinitions
// DriverClassName="/Script/Loki.LokiNetDriver".

#pragma once

#include "CoreMinimal.h"
#include "IpNetDriver.h"
#include "LokiNetDriver.generated.h"

UCLASS(transient, config=Engine)
class ULokiNetDriver : public UIpNetDriver
{
	GENERATED_BODY()

public:
	// Session 18: constructor sets NetConnectionClass = ULokiIpConnection so
	// per-connection PacketHandler chains get our LokiStatelessConnect instead
	// of the stock class. Without this the driver-level override in
	// InitConnectionlessHandler only affects connectionless packets — post-
	// handshake UNetConnection-level packets go through the stock class and
	// die when they encounter our 8-byte wrapper.
	ULokiNetDriver(const FObjectInitializer& ObjectInitializer);

	// Session 20: after Super::InitBase creates the GuidCache, disable per-class
	// network checksums so the client's stock-vs-Loki APlayerController /
	// AGameStateBase / APlayerState schema fingerprints don't get checked.
	// SUPERVIVE's shipping build has modified those core classes with extra
	// replicated properties, so their checksums differ from our stock UE5.4 stub.
	virtual bool InitBase(bool bInitAsClient, FNetworkNotify* InNotify,
	                      const FURL& URL, bool bReuseAddressAndPort,
	                      FString& Error) override;

	virtual void InitConnectionlessHandler() override;

	virtual void LowLevelSend(TSharedPtr<const FInternetAddr> Address,
	                          void* Data,
	                          int32 CountBits,
	                          FOutPacketTraits& Traits) override;

	// Session 38: suppress replication of APlayerController actors entirely.
	//
	// Session 36 diagnosed the client-initiated close as an FClassNetCache
	// divergence — our stock UE 5.4 APlayerController's NetIndex→field mapping
	// disagrees with SUPERVIVE's client-patched version, so any state bunch we
	// send trips "Invalid replicated field 0" on the client and it tears down
	// the connection. Session 37 tried three Option A variants at the CDO /
	// dormancy / property-flag levels — none could suppress the INITIAL bunch,
	// which UE sends whenever a PC is added to the NetworkObjectList.
	//
	// The session-38 prompt asked for `ULokiActorChannel::ReplicateActor` as
	// an override, but UE 5.4's UActorChannel::ReplicateActor is NOT declared
	// virtual (ActorChannel.h:190). ShouldReplicateActor on the NetDriver is
	// the higher-level gate that has the same effect: returning false here
	// prevents FNetworkObjectList::FindOrAdd from ever registering the PC as
	// a replicated actor (NetworkObjectList.cpp:102), so no actor channel is
	// opened for it and no initial bunch is ever emitted.
	//
	// Hypothesis (unchanged from session 38's prompt): the client's local
	// PlayerController_* was spawned client-side by its own Join flow with
	// its own NetGUID; c→s RPCs like ServerVerifyViewTarget may route via
	// that NetGUID without needing any server-sent replica. If the client
	// silently opens its OWN actor channel to its local PC's NetGUID, our
	// existing ULokiActorChannel::ReceivedBunch route-around (session 34)
	// still catches the incoming bunch. If instead the client refuses to
	// send RPCs to an unknown-to-server actor, we fall back to Option B
	// (runtime FProperty injection matching SUPERVIVE's PC schema).
	virtual bool ShouldReplicateActor(AActor* Actor) const override;

	// Session 38 iter 2: ShouldReplicateActor alone is NOT sufficient. Even
	// though returning false there keeps the PC out of FNetworkObjectList (so
	// the periodic ServerReplicateActors tick never picks it up),
	// UNetDriver::ProcessRemoteFunction (NetDriver.cpp:2536) still creates a
	// fresh actor channel and binds the PC to it whenever ANY server-side code
	// calls a client RPC on the PC (e.g. PostLogin's ClientMessage,
	// ClientReceiveDialogueEvent, etc.). The first bunch on that channel is
	// still the initial actor replication bunch with the property block whose
	// field NetIndex 0 diverges from SUPERVIVE's client PC — same close.
	//
	// AActor::CallRemoteFunction (Actor.cpp:5065) and
	// UActorComponent::CallRemoteFunction (ActorComponent.cpp:834) BOTH gate
	// on ShouldReplicateFunction. Returning false here for any PlayerController
	// (or PC-owned component) short-circuits the whole RPC path before
	// ProcessRemoteFunction ever creates a channel. Net effect: NO outbound
	// bunches for the PC at all — actor or RPC.
	virtual bool ShouldReplicateFunction(AActor* Actor, UFunction* Function) const override;
};
