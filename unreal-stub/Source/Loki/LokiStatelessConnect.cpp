#include "LokiStatelessConnect.h"
#include "PacketHandler.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStateless, Log, All);

LokiStatelessConnect::LokiStatelessConnect()
	: StatelessConnectHandlerComponent()
{
	UE_LOG(LogLokiStateless, Display,
	       TEXT("LokiStatelessConnect constructed — handshake size adapter active."));
}

void LokiStatelessConnect::IncomingConnectionless(FIncomingPacketRef PacketRef)
{
	FBitReader& Packet = PacketRef.Packet;
	const int64 OriginalBits = Packet.GetNumBits();

	if (OriginalBits > StockMaxHandshakeBits && OriginalBits >= TheoryCraftExtraPaddingBits)
	{
		// Copy current data to a temp buffer; SetData below Empty()s the FBitReader's
		// internal buffer before copying from src, so we can't pass GetData() directly
		// (use-after-free). The copy is fine — handshake packets are 60ish bytes.
		const int64 OriginalBytes = (OriginalBits + 7) / 8;
		TArray<uint8> Truncated;
		Truncated.Append(Packet.GetData(), OriginalBytes);

		const int64 NewBits = OriginalBits - TheoryCraftExtraPaddingBits;

		UE_LOG(LogLokiStateless, Verbose,
		       TEXT("Truncating handshake packet from %lld bits to %lld bits"),
		       OriginalBits, NewBits);

		Packet.SetData(Truncated.GetData(), NewBits);
	}

	StatelessConnectHandlerComponent::IncomingConnectionless(PacketRef);
}
