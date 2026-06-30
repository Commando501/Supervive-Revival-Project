// LokiNetDriver — subclass of UIpNetDriver that wires up our custom
// LokiStatelessConnect handler in place of stock StatelessConnectHandlerComponent.
//
// Stock UE5.4's UNetDriver::InitConnectionlessHandler() hardcodes
// "Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)" as
// the handler name and produces an instance of the stock class. We override
// InitConnectionlessHandler() to construct LokiStatelessConnect directly,
// skipping the factory path. The rest of the engine continues to work
// unchanged — StatelessConnectComponent stays valid because LokiStatelessConnect
// is-a StatelessConnectHandlerComponent.
//
// For outgoing connectionless packets (challenge/ack replies the server sends
// back to the client during handshake), we also override LowLevelSend to pad
// 8 extra bytes onto the tail. The SUPERVIVE client expects 56-64 byte
// handshake packets; if our reply is 48-57 bytes (stock UE5.4 output) the
// client's parser rejects it for being too small. Padding with 8 random
// bytes after stock's normal output lands us in TheoryCraft's accepted range.
//
// Registered via DefaultEngine.ini's [/Script/Engine.GameEngine]
// NetDriverDefinitions: DriverClassName="/Script/Loki.LokiNetDriver".

#pragma once

#include "CoreMinimal.h"
#include "IpNetDriver.h"
#include "LokiNetDriver.generated.h"

UCLASS(transient, config=Engine)
class ULokiNetDriver : public UIpNetDriver
{
	GENERATED_BODY()

public:
	/**
	 * Stock UNetDriver::InitConnectionlessHandler hardcodes the stateless
	 * handler component class. Override to register our LokiStatelessConnect
	 * subclass instead.
	 */
	virtual void InitConnectionlessHandler() override;

	/**
	 * For outgoing connectionless (handshake) packets, pad 8 bytes onto the
	 * tail so the SUPERVIVE client's parser (which expects TheoryCraft's
	 * larger random-padding range) accepts our reply.
	 */
	virtual void LowLevelSend(TSharedPtr<const FInternetAddr> Address,
	                          void* Data,
	                          int32 CountBits,
	                          FOutPacketTraits& Traits) override;

private:
	/** Match LokiStatelessConnect's truncation amount. */
	static constexpr int32 TheoryCraftExtraPaddingBits = 64;
};
