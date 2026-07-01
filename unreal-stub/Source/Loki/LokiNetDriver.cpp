#include "LokiNetDriver.h"
#include "LokiIpConnection.h"
#include "LokiStatelessConnect.h"
#include "PacketHandler.h"
#include "PacketHandlers/StatelessConnectHandlerComponent.h"
#include "Net/Core/Misc/DDoSDetection.h"
#include "Engine/PackageMapClient.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/HUD.h"
#include "GameFramework/DefaultPawn.h"
#include "GameFramework/SpectatorPawn.h"
#include "GameFramework/WorldSettings.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiNet, Log, All);

bool ULokiNetDriver::InitBase(bool bInitAsClient, FNetworkNotify* InNotify,
                              const FURL& URL, bool bReuseAddressAndPort,
                              FString& Error)
{
	const bool bOk = Super::InitBase(bInitAsClient, InNotify, URL, bReuseAddressAndPort, Error);
	if (!bOk)
	{
		return false;
	}

	// Session 20: disable per-class NetworkChecksum so the client doesn't reject
	// server actors whose UClass replication schema fingerprint differs. The
	// SUPERVIVE shipping client has modified engine base classes (APlayerController,
	// APlayerState, AGameStateBase, AHUD, ADefaultPawn, ASpectatorPawn) with extra
	// replicated properties, so a stock UE5.4 stub sends "wrong" checksums.
	// Setting mode to None makes the server omit bHasNetworkChecksum in its
	// NetGUID exports (PackageMapClient.cpp:883), which makes client's
	// PackageMapClient.cpp:3633 skip the check (`NetworkChecksum != 0` guard).
	if (GuidCache.IsValid())
	{
		GuidCache->SetNetworkChecksumMode(FNetGUIDCache::ENetworkChecksumMode::None);
		UE_LOG(LogLokiNet, Display,
		       TEXT("LokiNetDriver: NetworkChecksumMode set to None (bypasses per-class schema fingerprint check on client)."));
	}
	else
	{
		UE_LOG(LogLokiNet, Warning,
		       TEXT("LokiNetDriver::InitBase: GuidCache invalid after Super — checksum override skipped."));
	}
	return true;
}

ULokiNetDriver::ULokiNetDriver(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Force per-connection instantiation of our LokiIpConnection subclass so
	// each UNetConnection's PacketHandler chain gets LokiStatelessConnect
	// (which strips the 8-byte TheoryCraft wrapper) instead of the stock
	// StatelessConnectHandlerComponent (which misreads wrapper bytes as
	// handshake bit fields and fails ParseHandshakePacket).
	//
	// UNetDriver::InitConnectionClass() checks `NetConnectionClass == NULL`
	// before loading from NetConnectionClassName, so this assignment
	// short-circuits the config-driven default (IpConnection).
	NetConnectionClass = ULokiIpConnection::StaticClass();
}

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

// Session 38 iter 3 + session 39 iter 4: session 20 identified per-class
// NetworkChecksum divergence on APlayerController, AHUD, AGameStateBase,
// AGameModeBase, APlayerState, ADefaultPawn, ASpectatorPawn. Iter 2 proved
// the divergence is real (client failure moved from PlayerController to
// GameStateBase + PlayerState after we suppressed PC replication). Iter 3
// stabilized the connection past Join with the session-20 set. But iter 3
// stub log also showed the client sending NMT_ActorChannelFailure for two
// MORE server-opened channels immediately after Join:
//   Channel 3 = WorldSettings (WorldInfo_1)
//   Channel 4 = GameplayDebuggerCategoryReplicator (GameplayDebuggerCategoryReplicator_0)
// Iter 4 adds both to the divergent set. WorldSettings is available via
// GameFramework/WorldSettings.h. GameplayDebuggerCategoryReplicator lives
// in the GameplayDebugger module — matched by class-name string here to
// avoid adding a module dependency for a runtime pattern that never actually
// needs the concrete UClass.
static bool IsClassNetCacheDivergent(AActor* Actor)
{
	if (!Actor) return false;
	// GameModeBase is server-only, doesn't replicate. Left out on purpose.
	if (Actor->IsA<APlayerController>()
	 || Actor->IsA<AGameStateBase>()
	 || Actor->IsA<APlayerState>()
	 || Actor->IsA<AHUD>()
	 || Actor->IsA<ADefaultPawn>()
	 || Actor->IsA<ASpectatorPawn>()
	 || Actor->IsA<AWorldSettings>())
	{
		return true;
	}
	// String-match to avoid pulling in the GameplayDebugger module dependency.
	static const FName GameplayDebuggerCategoryReplicatorName(
		TEXT("GameplayDebuggerCategoryReplicator"));
	return Actor->GetClass()->GetFName() == GameplayDebuggerCategoryReplicatorName;
}

bool ULokiNetDriver::ShouldReplicateActor(AActor* Actor) const
{
	// Session 38: suppress replication of every actor whose class SUPERVIVE
	// has patched in ways that make its FClassNetCache diverge from stock
	// UE 5.4. See the header comment on this override for the full rationale
	// and session-38 notes for the exhaustive session-37 negative-result table.
	// Iter 3: expanded from just APlayerController to session-20's full list
	// after iter 2's client log showed the failure moved to GameStateBase +
	// PlayerState once the PC path was closed.
	//
	// Log once per unique actor name so the stub log confirms we're taking
	// the skip path without spamming every ServerReplicateActors tick.
	if (IsClassNetCacheDivergent(Actor))
	{
		static TSet<FName> LoggedNames;
		const FName ActorName = Actor->GetFName();
		if (!LoggedNames.Contains(ActorName))
		{
			LoggedNames.Add(ActorName);
			UE_LOG(LogLokiNet, Display,
			       TEXT("ShouldReplicateActor: SUPPRESSING replication for %s (%s) "
			            "to avoid FClassNetCache divergence with SUPERVIVE's client-patched class. "
			            "See session-38 iter 3 notes."),
			       *Actor->GetName(), *Actor->GetClass()->GetName());
		}
		return false;
	}
	return Super::ShouldReplicateActor(Actor);
}

bool ULokiNetDriver::ShouldReplicateFunction(AActor* Actor, UFunction* Function) const
{
	// Session 38 iter 2/3: also block RPC-dispatch-driven channel creation
	// for every actor class in the divergent set. See the header comment on
	// this override for the full rationale — ShouldReplicateActor is not
	// enough because the RPC path in ProcessRemoteFunction opens a fresh
	// channel independent of the network object list, and the very first
	// bunch on that channel is the initial actor replication with the bad
	// property block.
	if (IsClassNetCacheDivergent(Actor))
	{
		static TSet<FName> LoggedFuncs;
		const FName FuncName = Function ? Function->GetFName() : NAME_None;
		if (!LoggedFuncs.Contains(FuncName))
		{
			LoggedFuncs.Add(FuncName);
			UE_LOG(LogLokiNet, Display,
			       TEXT("ShouldReplicateFunction: SUPPRESSING RPC %s on %s (%s) "
			            "to prevent RPC-dispatch-driven actor channel open + initial bunch. "
			            "See session-38 iter 2/3 notes."),
			       *FuncName.ToString(), *Actor->GetName(), *Actor->GetClass()->GetName());
		}
		return false;
	}
	return Super::ShouldReplicateFunction(Actor, Function);
}
