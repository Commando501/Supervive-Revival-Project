// LokiStatelessConnect — subclass of UE5.4's StatelessConnectHandlerComponent
// that adapts the stock parser to TheoryCraft's wrapped wire format.
//
// Session 14 RE finding: TheoryCraft prepends an 8-byte WRAPPER to every
// stateless handshake packet. The wrapper is:
//
//   byte 0:     0xBB         — stable wrapper magic
//   byte 1:     random       — per-packet random/nonce
//   bytes 2-5:  DC 21 A6 A3  — stable wrapper signature
//   byte 6:     random       — per-packet random/nonce
//   byte 7:     0xFB         — stable wrapper signature
//   bytes 8+:   stock UE5.4 handshake packet (with empty inner MagicHeader)
//
// The 16-byte constant near LogLokiNet in mod-RVA 0x84F2C10 of
// SUPERVIVE-Win64-Shipping.exe is BB 53 DC 21 A6 A3 85 FB ... — the SAME
// signature byte positions match captured packets exactly, with the random
// positions varying per packet.
//
// Bit-decoded inner bytes (capture 1 bytes 8-10: A4 01 02) yielded:
// SessionID=0, ClientID=1, bHandshakePacket=1, bRestartHandshake=0,
// MinVersion=3 (SessionClientId), CurVersion=4 (NetCLUpgradeMessage). Exact
// stock UE5.4 defaults — confirming inner is stock with no inner MagicHeader.
//
// This file: strip the 8-byte wrapper from incoming packets before delegating
// to stock IncomingConnectionless. Pairs with LokiNetDriver.cpp which prepends
// the wrapper on outgoing replies.

#pragma once

#include "CoreMinimal.h"
#include "PacketHandlers/StatelessConnectHandlerComponent.h"

class LokiStatelessConnect : public StatelessConnectHandlerComponent
{
public:
	LokiStatelessConnect();

protected:
	/**
	 * Strip TheoryCraft's 8-byte wrapper from the front of incoming packets,
	 * then delegate to stock IncomingConnectionless.
	 */
	virtual void IncomingConnectionless(FIncomingPacketRef PacketRef) override;

public:
	/** Size of TheoryCraft's wrapper prefix on every stateless handshake packet. */
	static constexpr int32 LokiWrapperBytes = 8;
	static constexpr int32 LokiWrapperBits = LokiWrapperBytes * 8;

	/** Stable signature bytes in the wrapper, at the given offsets. */
	static constexpr uint8 LokiWrapperByte0 = 0xBB;
	static constexpr uint8 LokiWrapperByte2 = 0xDC;
	static constexpr uint8 LokiWrapperByte3 = 0x21;
	static constexpr uint8 LokiWrapperByte4 = 0xA6;
	static constexpr uint8 LokiWrapperByte5 = 0xA3;
	static constexpr uint8 LokiWrapperByte7 = 0xFB;
};
