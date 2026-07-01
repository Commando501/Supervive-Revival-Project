#include "LokiNetDriver.h"
#include "LokiStatelessConnect.h"
#include "PacketHandler.h"
#include "PacketHandlers/StatelessConnectHandlerComponent.h"
#include "Net/Core/Misc/DDoSDetection.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiNet, Log, All);

void ULokiNetDriver::InitConnectionlessHandler()
{
	// Replicates stock UNetDriver::InitConnectionlessHandler (UE5.4 NetDriver.cpp
	// line 1926) but constructs LokiStatelessConnect directly instead of going
	// through Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent).
	check(!ConnectionlessHandler.IsValid());

#if !UE_BUILD_SHIPPING
	if (!FParse::Param(FCommandLine::Get(), TEXT("NoPacketHandler")))
#endif
	{
		ConnectionlessHandler = MakeUnique<PacketHandler>(&DDoS);

		if (ConnectionlessHandler.IsValid())
		{
			ConnectionlessHandler->NotifyAnalyticsProvider(AnalyticsProvider, AnalyticsAggregator);
			ConnectionlessHandler->Initialize(UE::Handler::Mode::Server, MAX_PACKET_SIZE, /*bConnectionlessOnly*/ true,
			                                  /*Provider*/ nullptr, /*DDoS*/ nullptr, GetNetDriverDefinition());

			TSharedPtr<HandlerComponent> NewComponent = MakeShareable(new LokiStatelessConnect);
			ConnectionlessHandler->AddHandler(NewComponent, /*bDeferInitialize*/ true);

			StatelessConnectComponent = StaticCastSharedPtr<StatelessConnectHandlerComponent>(NewComponent);

			if (StatelessConnectComponent.IsValid())
			{
				StatelessConnectComponent.Pin()->SetDriver(this);
			}

			ConnectionlessHandler->InitializeComponents();

			UE_LOG(LogLokiNet, Display,
			       TEXT("LokiNetDriver: connectionless handler initialized with LokiStatelessConnect."));
		}
	}
}

void ULokiNetDriver::LowLevelSend(TSharedPtr<const FInternetAddr> Address,
                                  void* Data, int32 CountBits, FOutPacketTraits& Traits)
{
	// Session 17 (attempt 3): test one-directional wrap hypothesis. Client sent
	// 30 seconds of Initial retries with our server-signature wrapper reply — no
	// PacketHandler rejection (progress vs sessions 14-16) but no ChallengeResponse
	// either. Maybe the client's LokiNet FSocket only WRAPS outgoing, doesn't
	// STRIP incoming. If so, our wrapped reply arrives at client's PacketHandler
	// as garbage (wrapper bytes read as SessionID/ClientID/handshake bit fields).
	// Try sending stock UE5.4 packets without any wrap — client should process
	// them normally if hypothesis is correct.
	constexpr bool bDisableOutgoingWrap = true;
	const bool bIsHandshakeReply = ConnectionlessHandler.IsValid()
	                               && ConnectionlessHandler->GetRawSend();

	if (!bDisableOutgoingWrap && bIsHandshakeReply && Data != nullptr && CountBits > 0)
	{
		// Prepend the 8-byte TheoryCraft wrapper:
		//   byte 0: 0xBB  (stable signature)
		//   byte 1: random (per-packet nonce)
		//   byte 2: 0xDC  (stable)
		//   byte 3: 0x21  (stable)
		//   byte 4: 0xA6  (stable)
		//   byte 5: 0xA3  (stable)
		//   byte 6: random (per-packet nonce)
		//   byte 7: 0xFB  (stable)
		// Bytes 1 and 6 are random in captures (per-packet nonce/checksum). Random
		// values should work if the client doesn't validate them strictly. If
		// validation rejects, we'll need to compute them properly.
		const int32 InnerBytes = (CountBits + 7) / 8;
		const int32 OuterBytes = LokiStatelessConnect::LokiWrapperBytes + InnerBytes;

		// Session 17: server-direction wrapper signature CONFIRMED via
		// experiment (client stopped outright rejecting our replies, connection
		// timed out normally at 30s stock UE5.4 timeout instead of failing in 1s).
		// Now testing the fixed byte 1 and byte 6 hypothesis: the raw 16-byte
		// constant bytes 8-15 = 82 9B F5 4A 34 33 21 93. Try using 9B and 21
		// literally (instead of random) to see if server-direction bytes 1 and 6
		// are actually FIXED validation values (different from client-direction
		// where they're random per our 172-packet analysis).
		const uint8 Byte1 = 0x9B;
		const uint8 Byte6 = 0x21;

		TArray<uint8> Wrapped;
		Wrapped.AddZeroed(OuterBytes);
		Wrapped[0] = LokiStatelessConnect::ServerToClientByte0;
		Wrapped[1] = Byte1;
		Wrapped[2] = LokiStatelessConnect::ServerToClientByte2;
		Wrapped[3] = LokiStatelessConnect::ServerToClientByte3;
		Wrapped[4] = LokiStatelessConnect::ServerToClientByte4;
		Wrapped[5] = LokiStatelessConnect::ServerToClientByte5;
		Wrapped[6] = Byte6;
		Wrapped[7] = LokiStatelessConnect::ServerToClientByte7;
		FMemory::Memcpy(Wrapped.GetData() + LokiStatelessConnect::LokiWrapperBytes, Data, InnerBytes);

		const int32 NewCountBits = CountBits + LokiStatelessConnect::LokiWrapperBits;

		// Session 16: hex-dump the full wrapped packet for diagnostics. Compare
		// against captured client→server bytes to find structural mismatches.
		FString FullHex;
		FullHex.Reserve(OuterBytes * 3);
		for (int32 i = 0; i < OuterBytes; ++i)
		{
			FullHex.Appendf(TEXT("%02X "), Wrapped[i]);
		}

		UE_LOG(LogLokiNet, Verbose,
		       TEXT("LowLevelSend: wrapping handshake reply %d bits -> %d bits (wrapper bytes %02X %02X %02X %02X %02X %02X %02X %02X)"),
		       CountBits, NewCountBits,
		       Wrapped[0], Wrapped[1], Wrapped[2], Wrapped[3], Wrapped[4], Wrapped[5], Wrapped[6], Wrapped[7]);
		UE_LOG(LogLokiNet, Verbose, TEXT("LowLevelSend: full %d bytes: %s"), OuterBytes, *FullHex);

		Super::LowLevelSend(Address, Wrapped.GetData(), NewCountBits, Traits);
	}
	else
	{
		Super::LowLevelSend(Address, Data, CountBits, Traits);
	}
}
