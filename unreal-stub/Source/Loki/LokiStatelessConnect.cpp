#include "LokiStatelessConnect.h"
#include "PacketHandler.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStateless, Log, All);

LokiStatelessConnect::LokiStatelessConnect()
	: StatelessConnectHandlerComponent()
{
	UE_LOG(LogLokiStateless, Display,
	       TEXT("LokiStatelessConnect constructed — 8-byte wrapper adapter active."));
}

void LokiStatelessConnect::IncomingConnectionless(FIncomingPacketRef PacketRef)
{
	FBitReader& Packet = PacketRef.Packet;
	const int64 OriginalBits = Packet.GetNumBits();

	// Only strip if packet is at least 8 bytes (wrapper) + something. Smaller
	// packets are not TheoryCraft-wrapped (or are too small to contain anything
	// meaningful) — pass through unchanged.
	if (OriginalBits < LokiWrapperBits)
	{
		StatelessConnectHandlerComponent::IncomingConnectionless(PacketRef);
		return;
	}

	const uint8* Data = Packet.GetData();
	const int64 OriginalBytes = (OriginalBits + 7) / 8;

	// Sanity-check wrapper signature bytes. If they don't match we may be
	// receiving non-TheoryCraft traffic — log and pass through.
	const bool bSignatureValid =
		Data[0] == LokiWrapperByte0 &&
		Data[2] == LokiWrapperByte2 &&
		Data[3] == LokiWrapperByte3 &&
		Data[4] == LokiWrapperByte4 &&
		Data[5] == LokiWrapperByte5 &&
		Data[7] == LokiWrapperByte7;

	if (!bSignatureValid)
	{
		UE_LOG(LogLokiStateless, Warning,
		       TEXT("Wrapper signature mismatch (got %02X ?? %02X %02X %02X %02X ?? %02X), passing packet through."),
		       Data[0], Data[2], Data[3], Data[4], Data[5], Data[7]);
		StatelessConnectHandlerComponent::IncomingConnectionless(PacketRef);
		return;
	}

	// Copy inner packet (bytes 8+) to a temp buffer — SetData below Empty()s
	// the FBitReader's internal buffer before copying from src, so passing
	// GetData() + 8 would be a use-after-free.
	const int64 InnerBytes = OriginalBytes - LokiWrapperBytes;
	const int64 InnerBits = OriginalBits - LokiWrapperBits;

	TArray<uint8> Inner;
	Inner.Append(Data + LokiWrapperBytes, InnerBytes);

	UE_LOG(LogLokiStateless, Verbose,
	       TEXT("Stripping wrapper: %lld bits -> %lld bits (wrapper bytes: %02X %02X %02X %02X %02X %02X %02X %02X)"),
	       OriginalBits, InnerBits,
	       Data[0], Data[1], Data[2], Data[3], Data[4], Data[5], Data[6], Data[7]);

	Packet.SetData(Inner.GetData(), InnerBits);

	StatelessConnectHandlerComponent::IncomingConnectionless(PacketRef);
}
