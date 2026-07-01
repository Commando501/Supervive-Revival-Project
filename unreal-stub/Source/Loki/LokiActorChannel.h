// LokiActorChannel — UActorChannel subclass that hex-dumps every incoming
// bunch's raw bytes with ChIndex + ChSequence + NumBits metadata.
//
// Session 25 goal: capture the exact byte-aligned RPC payload for
// ServerVerifyViewTarget so we can decode SUPERVIVE's modified signature.
// LokiStatelessConnect already dumps whole packets, but we need per-bunch
// resolution so we can correlate with UE's own log line
//   "Reliable Bunch, Channel 3 Sequence N: Size 5.8+292.4"
// and pinpoint the failing RPC's bytes.
//
// Registered via DefaultEngine.ini:
//   [/Script/OnlineSubsystemUtils.IpNetDriver]
//   !ChannelDefinitions=CLEAR_ARRAY
//   +ChannelDefinitions=(ChannelName=Control, ClassName=/Script/Engine.ControlChannel, ...)
//   +ChannelDefinitions=(ChannelName=Actor, ClassName=/Script/Loki.LokiActorChannel, ...)

#pragma once

#include "CoreMinimal.h"
#include "Engine/ActorChannel.h"
#include "LokiActorChannel.generated.h"

UCLASS(transient)
class ULokiActorChannel : public UActorChannel
{
	GENERATED_BODY()

public:
	virtual void ReceivedBunch(FInBunch& Bunch) override;
};
