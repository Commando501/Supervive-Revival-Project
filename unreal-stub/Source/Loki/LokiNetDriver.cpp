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
	// calling LowLevelSend, then back to false after. So when bRawSend is true,
	// we know we're sending a handshake reply packet that needs TheoryCraft
	// padding.
	const bool bIsHandshakeReply = ConnectionlessHandler.IsValid()
	                               && ConnectionlessHandler->GetRawSend();

	if (bIsHandshakeReply && Data != nullptr && CountBits > 0)
	{
		const int32 OriginalBytes = (CountBits + 7) / 8;
		const int32 PaddedBytes = OriginalBytes + (TheoryCraftExtraPaddingBits / 8);

		TArray<uint8> Padded;
		Padded.AddZeroed(PaddedBytes);
		FMemory::Memcpy(Padded.GetData(), Data, OriginalBytes);
		// Append 8 random bytes — stock CapHandshakePacket uses FMath::Rand so
		// match the entropy style. Predictable values would still parse fine
		// (TheoryCraft's parser treats them as random padding), but random is
		// closer to what the client sees from a real server.
		for (int32 i = OriginalBytes; i < PaddedBytes; ++i)
		{
			Padded[i] = static_cast<uint8>(FMath::Rand() % 255);
		}

		const int32 NewCountBits = CountBits + TheoryCraftExtraPaddingBits;

		UE_LOG(LogLokiNet, Verbose,
		       TEXT("LowLevelSend: padding handshake reply %d bits -> %d bits"),
		       CountBits, NewCountBits);

		Super::LowLevelSend(Address, Padded.GetData(), NewCountBits, Traits);
	}
	else
	{
		Super::LowLevelSend(Address, Data, CountBits, Traits);
	}
}
