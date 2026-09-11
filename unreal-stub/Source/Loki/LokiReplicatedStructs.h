// Session 41 Path B-lite step 2: runtime-injection mirror of SUPERVIVE's
// AActor.ServerState struct type (PoolableActorServerState), RE'd via the
// usmapdump CPF_Net extraction — see docs/session-41-supervive-pc-repschema.txt
// and docs/session-41-step2-result.txt.
//
// SUPERVIVE's struct is { State: EPoolableActorServerState (enum), Version:
// uint32 }. CRUCIAL wire fact (session 41 iter 2, proven by LogRepProperties):
// on the client PoolableActorServerState is a SINGLE RepLayout cmd, i.e. it has
// a custom NetSerialize (WithNetSerializer) — like stock FRepMovement. Our first
// mirror was a plain member-wise USTRUCT (2 cmds: State + Version), which made
// every replicated handle AFTER ServerState off-by-one: our stub emitted a max
// handle of 22 where the client's layout tops out at 21, so the client rejected
// handle 22 as an invalid property terminator. Giving THIS struct a NetSerializer
// collapses it to one cmd and realigns the whole handle space.
//
// The NetSerialize CONTENT is a best-effort (2-bit State + 32-bit Version) and
// currently only needs to make the struct a single cmd: ServerState equals the
// CDO on a freshly-spawned PC, so it is not actually sent in the initial bunch,
// and NetSerialize isn't invoked. If ServerState ever does replicate, revisit
// the exact bit layout.
#pragma once

#include "CoreMinimal.h"
#include "LokiReplicatedStructs.generated.h"

UENUM()
enum class EPoolableActorServerState : uint8
{
	Spawned = 0,
	SimulatingTearOff = 1,
	Despawned = 2,
};

USTRUCT()
struct FPoolableActorServerState
{
	GENERATED_BODY()

	UPROPERTY()
	EPoolableActorServerState State = EPoolableActorServerState::Spawned;

	UPROPERTY()
	int32 Version = 0;

	// Custom net serializer => RepLayout treats this whole struct as ONE cmd,
	// matching SUPERVIVE's client-side layout. Implemented in Loki.cpp.
	bool NetSerialize(FArchive& Ar, class UPackageMap* Map, bool& bOutSuccess);
};

template<>
struct TStructOpsTypeTraits<FPoolableActorServerState>
	: public TStructOpsTypeTraitsBase2<FPoolableActorServerState>
{
	enum
	{
		WithNetSerializer = true,
	};
};
