// LokiPlayerState_Missions — session 54 (2026-07-07): the replicated actor that
// delivers the MISSIONS page to the live SUPERVIVE client over UE replication.
//
// WHY THIS EXISTS
// ---------------
// Missions is the one menu surface with no client-side shortcut (session 52
// proved: no HTTP feed, mission DAs don't resolve as primary assets, and there
// is no safe game-thread native-call primitive). The client's UMissionsModel
// maps are empty at menu; they are populated by the client's native
// OnPSMissionsUpdated, which fires off the RepNotify of a replicated
// LokiPlayerState_Missions actor's `Missions` array. So the DS route is: the
// stub replicates a LokiPlayerState_Missions whose `Missions` (TArray of
// FMissionProgress) carries a granted mission set -> client OnRep(Missions) ->
// OnMissionsUpdated -> OnPSMissionsUpdated -> MissionsModel populates ->
// WBP_UI_MissionModal renders tiles. Full client data path:
// docs/session-52-missions-page-decompiled.txt.
//
// HOW THE CLIENT RECOGNIZES THIS CLASS (the NetGUID resolution trick)
// -------------------------------------------------------------------
// The SUPERVIVE game module is ALSO named "Loki", so the client's real class is
// /Script/Loki.LokiPlayerState_Missions. Our stub module is likewise "Loki"
// (IMPLEMENT_PRIMARY_GAME_MODULE(FLokiModule, Loki, "Loki")), so naming this
// UCLASS `LokiPlayerState_Missions` gives it the SAME path. When the stub opens
// this actor's channel and exports its class NetGUID by path, the client
// resolves that path to ITS OWN class — exactly how the stub already gets stock
// engine classes (PlayerController/PlayerState/...) recognized. No IoStore /
// mod-pak overlay needed.
//
// SCHEMA MATCH (why member-wise FMissionProgress with engine sub-types is safe)
// -----------------------------------------------------------------------------
// NetworkChecksumMode is None (LokiNetDriver::InitBase), so the client won't
// fingerprint-reject our class. But the per-property RepLayout cmd stream still
// has to line up or the client's read cursor desyncs (the session-41 ServerState
// off-by-one lesson). RepLayout is built from each side's property tree:
//   * FPrimaryAssetId and FDateTime are engine (CoreUObject/Core) types — using
//     the engine types here guarantees IDENTICAL cmd expansion on both ends
//     (FPrimaryAssetId -> 2 FName cmds; FDateTime -> 1 int64 Ticks cmd).
//   * FMissionProgress is a plain data struct (no custom NetSerializer expected),
//     so RepLayout recurses member-wise. Mirroring its 9 fields in the exact
//     usmap order (schema.txt:32018) reproduces the client's cmd stream.
// Field order + types are load-bearing — do NOT reorder. If a live test shows a
// cursor desync, the first suspect is FMissionProgress having a custom
// NetSerialize on the client (then this must become a WithNetSerializer mirror).
//
// REP-INDEX ALIGNMENT
// -------------------
// AActor gets ServerState injected at RepIndex 10 (Loki.cpp
// InjectServerStateReplicatedProperty), so a stock-schema AActor has 11 reps
// (0..10). The client's AActor is likewise patched with ServerState, so its
// LokiPlayerState_Missions (: Actor, usmap:27753) has inherited reps 0..10 then
// its 2 CPF_Net props in field order: Missions (field #1) = RepIndex 11,
// FinalMissionProgress (field #5) = RepIndex 12. We declare Missions THEN
// FinalMissionProgress so ForceSetUpReplicationData assigns 11/12 to match.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LokiPlayerState_Missions.generated.h"

// Mirror of SUPERVIVE's FMissionProgress (usmap schema.txt:32018, "9 props").
// Size 0x60 in the client; we don't need the exact C++ offsets (replication is
// by RepLayout cmd, not raw memory), only the field order + reflected types.
USTRUCT()
struct FMissionProgress
{
	GENERATED_BODY()

	// [1] Mission instance id string (e.g. "ArmoryDaily_PlayAGame"). The
	// UMissionsModel.Missions map is keyed by this (GetMissionModel takes Str ID).
	UPROPERTY()
	FString ID;

	// [2] The mission DA's PrimaryAssetId — { Type="Mission", Name=<mission> }.
	// The container reads MissionAsset via this to get Hide/Hero/LobbyWidgetClass.
	UPROPERTY()
	FPrimaryAssetId AssetId;

	// [3] The owning pool's PrimaryAssetId — { Type="MissionPool", Name=<pool> }.
	// The container filters missions to those whose PoolId matches its PoolAsset.
	UPROPERTY()
	FPrimaryAssetId PoolId;

	// [4]/[5] completion flags.
	UPROPERTY()
	bool Complete = false;

	UPROPERTY()
	bool Failed = false;

	// [6] per-objective progress counters.
	UPROPERTY()
	TArray<int64> ObjectiveProgress;

	// [7] ms until this mission's rotation expires (drives the countdown).
	UPROPERTY()
	int64 MillisUntilExpiry = 0;

	// [8]/[9] rotation timestamps. FDateTime(0) == year-0 which makes the client
	// log "DateTime in bad format"; the populate path sets real Utc values.
	UPROPERTY()
	FDateTime Expiry = FDateTime(0);

	UPROPERTY()
	FDateTime GrantedAt = FDateTime(0);
};

// Replicated stand-in for the client's LokiPlayerState_Missions (usmap:27753).
// We declare ONLY the two CPF_Net arrays (Missions, FinalMissionProgress) — the
// client's other 5 fields (delegates, OwningPlayerState obj, two bools) are not
// replicated, so they play no part in the wire layout and are omitted to keep
// the RepLayout minimal and exactly aligned. `transient` mirrors the other stub
// actor classes (no disk serialization).
UCLASS(transient)
class ALokiPlayerState_Missions : public AActor
{
	GENERATED_BODY()

public:
	ALokiPlayerState_Missions(const FObjectInitializer& ObjectInitializer);

	// [RepIndex 11] the granted mission set the client renders as tiles.
	UPROPERTY(ReplicatedUsing = OnRep_Missions)
	TArray<FMissionProgress> Missions;

	// [RepIndex 12] end-of-game final progress (unused at menu; declared to keep
	// the net-prop field order faithful to the client so RepIndices line up).
	UPROPERTY(ReplicatedUsing = OnRep_FinalMissionProgress)
	TArray<FMissionProgress> FinalMissionProgress;

	// Server-side association bookkeeping. NOT replicated (matches usmap — the
	// client's OwningPlayerState is a plain ObjectProperty). Kept so the stub can
	// record which PlayerState this missions actor belongs to; whether the client
	// needs this for model association is an open question (see .cpp header note).
	UPROPERTY()
	TObjectPtr<APlayerState> OwningPlayerState = nullptr;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// RepNotifies exist only so ReplicatedUsing has a target and to log on the
	// (server) side; the client runs its OWN class's OnRep. Empty bodies.
	UFUNCTION()
	void OnRep_Missions();

	UFUNCTION()
	void OnRep_FinalMissionProgress();
};
