// LokiIpConnection — UIpConnection subclass that installs our
// LokiStatelessConnect into the per-connection PacketHandler chain.
//
// Session 18 blocker: stock UNetConnection::InitHandler (UE5.4
// NetConnection.cpp:687-712) hardcodes the string
//   "Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)"
// when adding the outermost handshake component. Our session-13 override at
// the DRIVER level (LokiNetDriver::InitConnectionlessHandler) only affects
// the driver's connectionless handler chain — NOT the per-connection chain
// that gets created when a client passes the handshake and a UNetConnection
// is spawned.
//
// So after handshake completes:
//   - UNetConnection is created, its Handler->AddHandler installs the STOCK
//     StatelessConnectHandlerComponent
//   - Client's first post-handshake packet is still wrapped
//     (BB ?? DC 21 A6 A3 ?? FB prefix + inner stock UE5.4 game data)
//   - Stock reads 0xBB's bits as SessionID/ClientID/bHandshakePacket,
//     misinterprets bit 5 as bHandshakePacket=1, calls ParseHandshakePacket
//     on the wrapper — fails at size-variance check — connection dies.
//
// This subclass overrides InitHandler to construct LokiStatelessConnect
// directly instead of loading stock via the factory string. Wired into
// LokiNetDriver via NetConnectionClass = ULokiIpConnection::StaticClass()
// in the driver's constructor.

#pragma once

#include "CoreMinimal.h"
#include "IpConnection.h"
#include "LokiIpConnection.generated.h"

UCLASS(transient, config=Engine)
class ULokiIpConnection : public UIpConnection
{
	GENERATED_BODY()

public:
	virtual void InitHandler() override;
};
