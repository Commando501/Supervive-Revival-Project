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

	virtual void InitConnectionlessHandler() override;

	virtual void LowLevelSend(TSharedPtr<const FInternetAddr> Address,
	                          void* Data,
	                          int32 CountBits,
	                          FOutPacketTraits& Traits) override;
};
