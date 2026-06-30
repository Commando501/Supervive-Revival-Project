// LokiStatelessConnect — subclass of UE5.4's StatelessConnectHandlerComponent
// that adapts the stock packet-size variance check to accept TheoryCraft's
// SUPERVIVE client handshake packets.
//
// Session 11 RE established that SUPERVIVE compiles stock UE5.4 source for
// StatelessConnectHandlerComponent.cpp (build path
// C:\TheoryCraft\build-staging\..., log call-site line numbers match stock at
// 441/493/579/878/1053). Session 11 packet-size analysis suggests TheoryCraft
// bumped BaseRandomDataLengthBytes from stock 16 to 24 — captured packets are
// 56-64 bytes (= +8 byte shift on stock's 48-57 byte expected range, 9-byte
// variance matching stock's RandomDataLengthVarianceBytes=8).
//
// Session 12 attempted to test by editing engine source + rebuilding. That
// path is dead-end for Launcher installs (no .lib import files shipped). This
// file is session 13's workaround: stay on stock engine, fix the protocol
// mismatch via a subclass that lives in our game module.
//
// Approach: override IncomingConnectionless to truncate 8 trailing bytes off
// incoming packets before delegating to the stock parent. The 8 truncated
// bytes are the EXTRA random padding TheoryCraft adds — stock's parser
// treats remaining bits beyond fixed handshake fields as random padding
// anyway. After truncation the packet falls back into stock's expected size
// variance range and ParseHandshakePacket succeeds.

#pragma once

#include "CoreMinimal.h"
#include "PacketHandlers/StatelessConnectHandlerComponent.h"

class LokiStatelessConnect : public StatelessConnectHandlerComponent
{
public:
	LokiStatelessConnect();

protected:
	/**
	 * Intercept incoming connectionless packets. If the packet is larger than
	 * stock's max accepted handshake size, truncate the trailing random padding
	 * by 64 bits (8 bytes) and delegate to parent's IncomingConnectionless.
	 */
	virtual void IncomingConnectionless(FIncomingPacketRef PacketRef) override;

private:
	/**
	 * Stock UE5.4 HANDSHAKE_PACKET_SIZE_BITS (307) + MagicHeader/SessionID/
	 * ClientID prefix (13 bits) + max stock random padding (128 bits) + 1
	 * termination bit = 449 bits. Packets above this threshold are likely
	 * TheoryCraft's enlarged handshake; truncate 64 bits off them.
	 */
	static constexpr int64 StockMaxHandshakeBits = 449;

	/** TheoryCraft adds 8 bytes (64 bits) of extra random padding vs stock. */
	static constexpr int64 TheoryCraftExtraPaddingBits = 64;
};
