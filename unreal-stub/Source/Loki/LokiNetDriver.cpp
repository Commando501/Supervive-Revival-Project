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
	// Stock SendToClient sets ConnectionlessHandler->SetRawSend(true) just before
	// calling LowLevelSend, then back to false after. When bRawSend is true,
	// we know we're sending a stateless handshake reply.
	const bool bIsHandshakeReply = ConnectionlessHandler.IsValid()
	                               && ConnectionlessHandler->GetRawSend();

	if (bIsHandshakeReply && Data != nullptr && CountBits > 0)
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

		// Session 15: mirror bytes 1 and 6 from the last incoming packet.
		// If LokiNetSocketSubsystem on the client uses these as session-state
		// identifiers, mirroring them tells the client "this reply is part of
		// the same conversation."
		uint8 Byte1 = static_cast<uint8>(FMath::Rand() % 256);
		uint8 Byte6 = static_cast<uint8>(FMath::Rand() % 256);
		TSharedPtr<StatelessConnectHandlerComponent> SC = StatelessConnectComponent.Pin();
		LokiStatelessConnect* LokiSC = SC.IsValid() ? static_cast<LokiStatelessConnect*>(SC.Get()) : nullptr;
		if (LokiSC != nullptr && LokiSC->bHasLastIncoming)
		{
			Byte1 = LokiSC->LastIncomingByte1;
			Byte6 = LokiSC->LastIncomingByte6;
		}

		TArray<uint8> Wrapped;
		Wrapped.AddZeroed(OuterBytes);
		Wrapped[0] = LokiStatelessConnect::LokiWrapperByte0;
		Wrapped[1] = Byte1;
		Wrapped[2] = LokiStatelessConnect::LokiWrapperByte2;
		Wrapped[3] = LokiStatelessConnect::LokiWrapperByte3;
		Wrapped[4] = LokiStatelessConnect::LokiWrapperByte4;
		Wrapped[5] = LokiStatelessConnect::LokiWrapperByte5;
		Wrapped[6] = Byte6;
		Wrapped[7] = LokiStatelessConnect::LokiWrapperByte7;
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
