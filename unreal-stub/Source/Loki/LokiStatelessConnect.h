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
	 * Strip TheoryCraft's 8-byte wrapper from the front of incoming CONNECTIONLESS
	 * packets (handshake), then delegate to stock IncomingConnectionless.
	 *
	 * Also captures the last received wrapper's bytes 1 and 6 into
	 * LastIncomingByte1/LastIncomingByte6 so LokiNetDriver::LowLevelSend can
	 * echo them in our reply (session 15 mirroring strategy).
	 */
	virtual void IncomingConnectionless(FIncomingPacketRef PacketRef) override;

	/**
	 * Strip TheoryCraft's 8-byte wrapper from the front of incoming CONNECTION
	 * packets (post-handshake game data). Session 17: after handshake completes,
	 * the client keeps wrapping outgoing packets with the client→server signature
	 * (BB ?? DC 21 A6 A3 ?? FB). The UNetConnection's PacketHandler chain calls
	 * this Incoming, not IncomingConnectionless. Without stripping, stock code
	 * reads 0xBB's bits as SessionID/ClientID/handshake — bHandshakePacket=1 →
	 * calls ParseHandshakePacket on garbage → error → connection closed.
	 */
	virtual void Incoming(FBitReader& Packet) override;

public:
	/** Size of TheoryCraft's wrapper prefix on every stateless handshake packet. */
	static constexpr int32 LokiWrapperBytes = 8;
	static constexpr int32 LokiWrapperBits = LokiWrapperBytes * 8;

	/** CLIENT→SERVER wrapper stable signature bytes at the given offsets.
	 *  Derived from session 10 capture analysis (172 packets, all match).
	 */
	static constexpr uint8 ClientToServerByte0 = 0xBB;
	static constexpr uint8 ClientToServerByte2 = 0xDC;
	static constexpr uint8 ClientToServerByte3 = 0x21;
	static constexpr uint8 ClientToServerByte4 = 0xA6;
	static constexpr uint8 ClientToServerByte5 = 0xA3;
	static constexpr uint8 ClientToServerByte7 = 0xFB;

	/** SERVER→CLIENT wrapper stable signature bytes — session 17 hypothesis.
	 *  Derived from bytes 8-15 of the 16-byte constant near LogLokiNet at
	 *  mod-RVA 0x84F2C10 of SUPERVIVE-Win64-Shipping.exe:
	 *    BB 53 DC 21 A6 A3 85 FB | 82 9B F5 4A 34 33 21 93
	 *    └─ client→server ─────┘   └─ server→client ────┘
	 *  Bytes 1 and 6 of EACH half (53/85 and 9B/21) are presumed random
	 *  per-packet (matches our analysis of 172 client→server captures).
	 */
	static constexpr uint8 ServerToClientByte0 = 0x82;
	static constexpr uint8 ServerToClientByte2 = 0xF5;
	static constexpr uint8 ServerToClientByte3 = 0x4A;
	static constexpr uint8 ServerToClientByte4 = 0x34;
	static constexpr uint8 ServerToClientByte5 = 0x33;
	static constexpr uint8 ServerToClientByte7 = 0x93;

	/** Backward-compat aliases for the incoming-strip code (client→server). */
	static constexpr uint8 LokiWrapperByte0 = ClientToServerByte0;
	static constexpr uint8 LokiWrapperByte2 = ClientToServerByte2;
	static constexpr uint8 LokiWrapperByte3 = ClientToServerByte3;
	static constexpr uint8 LokiWrapperByte4 = ClientToServerByte4;
	static constexpr uint8 LokiWrapperByte5 = ClientToServerByte5;
	static constexpr uint8 LokiWrapperByte7 = ClientToServerByte7;

	/**
	 * Last-received wrapper bytes 1 and 6, captured by IncomingConnectionless
	 * for LokiNetDriver::LowLevelSend to echo back in our reply. Mirroring
	 * strategy: if these bytes are session-specific state assigned by the
	 * client's LokiNetSocketSubsystem, echoing them ensures the client
	 * recognizes our reply as part of the same conversation.
	 */
	uint8 LastIncomingByte1 = 0;
	uint8 LastIncomingByte6 = 0;
	bool bHasLastIncoming = false;
};
