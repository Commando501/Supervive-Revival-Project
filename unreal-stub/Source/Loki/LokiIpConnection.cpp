#include "LokiIpConnection.h"
#include "LokiStatelessConnect.h"
#include "Engine/NetDriver.h"
#include "PacketHandler.h"
#include "PacketHandlers/StatelessConnectHandlerComponent.h"
#include "Net/NetConnectionFaultRecovery.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiIpConnection, Log, All);

void ULokiIpConnection::InitHandler()
{
	// Session 18: replicates stock UNetConnection::InitHandler (UE5.4
	// NetConnection.cpp:675-745) but constructs LokiStatelessConnect directly
	// instead of going through the hardcoded
	// "Engine.EngineHandlerComponentFactory(StatelessConnectHandlerComponent)"
	// factory string. Everything else matches stock verbatim so the connection
	// initialization contract is preserved.
	using namespace UE::Net;

	LLM_SCOPE_BYTAG(NetConnection);

	check(!Handler.IsValid());

#if !UE_BUILD_SHIPPING
	if (!FParse::Param(FCommandLine::Get(), TEXT("NoPacketHandler")))
#endif
	{
		Handler = MakeUnique<PacketHandler>();

		if (Handler.IsValid())
		{
			UE::Handler::Mode Mode = Driver->ServerConnection != nullptr
			                         ? UE::Handler::Mode::Client
			                         : UE::Handler::Mode::Server;

			FPacketHandlerNotifyAddHandler NotifyAddHandler;

			NotifyAddHandler.BindLambda([this](TSharedPtr<HandlerComponent>& NewHandler)
			{
				if (NewHandler.IsValid())
				{
					NewHandler->InitFaultRecovery(GetFaultRecovery());
				}
			});

			Handler->InitializeDelegates(
				FPacketHandlerLowLevelSendTraits::CreateUObject(this, &UNetConnection::LowLevelSend),
				MoveTemp(NotifyAddHandler));

			Handler->NotifyAnalyticsProvider(Driver->AnalyticsProvider, Driver->AnalyticsAggregator);
			Handler->Initialize(Mode, MaxPacket * 8, false, nullptr, nullptr,
			                    Driver->GetNetDriverDefinition());

			// THE ONE LINE THAT CHANGES vs stock — construct LokiStatelessConnect
			// directly instead of loading stock via the factory string.
			TSharedPtr<HandlerComponent> NewComponent = MakeShareable(new LokiStatelessConnect);
			Handler->AddHandler(NewComponent, /*bDeferInitialize*/ true);

			StatelessConnectComponent = StaticCastSharedPtr<StatelessConnectHandlerComponent>(NewComponent);

			if (StatelessConnectComponent.IsValid())
			{
				StatelessConnectHandlerComponent* CurComponent = StatelessConnectComponent.Pin().Get();

				CurComponent->SetDriver(Driver);

				CurComponent->SetHandshakeFailureCallback([this](FStatelessHandshakeFailureInfo HandshakeFailureInfo)
				{
					if (HandshakeFailureInfo.FailureReason == EHandshakeFailureReason::WrongVersion)
					{
						this->HandleReceiveNetUpgrade(HandshakeFailureInfo.RemoteNetworkVersion,
						                              HandshakeFailureInfo.RemoteNetworkFeatures,
						                              ENetUpgradeSource::StatelessHandshake);
					}
				});
			}

			Handler->InitializeComponents();

			MaxPacketHandlerBits = Handler->GetTotalReservedPacketBits();

			UE_LOG(LogLokiIpConnection, Display,
			       TEXT("LokiIpConnection: per-connection PacketHandler initialized with LokiStatelessConnect (reserved bits: %d)."),
			       MaxPacketHandlerBits);
		}
	}
}
