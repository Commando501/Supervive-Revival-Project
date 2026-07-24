// LokiServerAuthConfigStub — S85 (2026-07-22): native mirror of the client's LokiServerAuthConfig, the
// ActorComponent that carries the CLIENT GAME-FEATURE TOGGLES on the dedicated-server route.
//
// WHY THIS EXISTS
// ---------------
// After the DS client possesses + resolves its PlayerState it sits at the "ENTERING THE BREACH"
// match-transition spamming "ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready"
// (112x+). Deep RE (Ghidra, docs/session-85 §10-11) proved: game-feature-toggle readiness is delivered by a
// REPLICATED property. LokiServerAuthConfig is a UActorComponent (default subobject named "ServerAuthConfig"
// of LokiGameState) whose replicated `GameFeatureToggles` array, when it arrives on the client, fires
// `OnRep_GameFeatureToggles` -> marks the client's toggles READY -> broadcasts OnClientGameFeatureTogglesReady
// on the LokiPlayerController. On the stub route the client's local ServerAuthConfig component exists but
// GameFeatureToggles is EMPTY (num=0, live-verified) because the stub never replicated it -> never ready.
// Fix: the stub's ALokiGameState creates a matching replicated "ServerAuthConfig" subobject of THIS class and
// populates GameFeatureToggles, so the client's OnRep fires. NetGUID-by-path (/Script/Loki.LokiServerAuthConfig)
// makes the client resolve this to its own class, same trick as ALokiGameState (S70) / ALokiPlayerState (S85).
//
// SCHEMA (S85 live capture, DS client PID 13764 — netcache_chain + rep_expand_class):
//   Net-cache: UActorComponent 2 reps (bReplicates, bIsActive) + LokiServerAuthConfig 1 rep + 1 net func:
//     [2] GameFeatureToggles          = TArray<bool>  (usmap's "MulticastInlineDelegateProperty" inner was
//                                       WRONG — the known-unreliable container report; it is a plain bool
//                                       array, one entry per ELokiGameFeatureToggle = 151 values)
//     [3] MulticastSetGameFeatureToggle = NetMulticast, Reliable  (empty stub; NetFields index alignment)
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LokiServerAuthConfigStub.generated.h"

// ELokiGameFeatureToggle has 151 values (schema.txt:61484). GameFeatureToggles is indexed by that enum, so
// the array is sized to 151; Get(enum) reads GameFeatureToggles[enumValue].
static constexpr int32 LOKI_GAME_FEATURE_TOGGLE_COUNT = 151;

UCLASS(transient)
class ULokiServerAuthConfig : public UActorComponent
{
	GENERATED_BODY()

public:
	ULokiServerAuthConfig();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// S87 NOTE: forcing a STATIC component NetGUID (overriding IsFullNameStableForNetworking()->true, so
	// FNetGUIDCache::IsDynamicObject is false) was TESTED and did NOT fix the desync — the client read the
	// IDENTICAL phantom class GUID 134524993 and dropped. Both guid 12 (dynamic) and 25 (static) pack to 8
	// bits, so the content-block framing is identical, PROVING the client's ~10-11 extra subobject-read bits
	// are INTRINSIC to its subobject content-block protocol, not guid-static/dynamic-dependent. Override
	// removed. The real fix must MATCH the client's subobject framing (RE its ReadContentBlockHeader). See §S87.

	// [2] client rep — one bool per ELokiGameFeatureToggle. Populated server-side by the GameState so the
	// client's OnRep_GameFeatureToggles fires and toggles become ready. TArray<bool> wire = trivial.
	UPROPERTY(Replicated) TArray<bool> GameFeatureToggles;

	// [3] client own net func — S89: real RE'd signature (was empty). Live RPM reflection (ufunc_params.py)
	// recovered `void MulticastSetGameFeatureToggle(TEnumAsByte<ELokiGameFeatureToggle> Toggle, bool bValue)`
	// on the client's LokiServerAuthConfig (NetMulticast, Reliable, Native; 2-byte frame). We mirror the params
	// as (uint8 Toggle → ByteProperty, bool bValue) so the sent wire matches; the client deserializes per its
	// OWN reflection (TEnumAsByte<ELokiGameFeatureToggle>). This is the RPC-DELIVERY route (S89): the RepLayout
	// property array desyncs the client (S88 — read as GameState field-cache entries), but an RPC uses a
	// different client read path (ReceivedRPC), so it may be accepted where the array isn't.
	UFUNCTION(NetMulticast, Reliable) void MulticastSetGameFeatureToggle(uint8 Toggle, bool bValue);

	// S89: fire MulticastSetGameFeatureToggle for toggles [0,Count) (server → clients). Server-authority only.
	void BroadcastAllToggles(int32 Count);

	// Fill GameFeatureToggles with `Count` entries all set to bValue (server-side). Marks the array so it
	// differs from the CDO (empty) and thus replicates in the initial bunch.
	void SeedAllToggles(bool bValue = true, int32 Count = LOKI_GAME_FEATURE_TOGGLE_COUNT);
};
