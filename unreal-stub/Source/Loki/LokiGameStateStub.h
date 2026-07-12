// LokiGameStateStub — session 70 (2026-07-11): the replicated GameState mirror that lets the live
// SUPERVIVE client LEAVE the tutorial loading screen on the dedicated-server route.
//
// WHY THIS EXISTS
// ---------------
// On the DS route the client Joins LVL_Tutorial but sits on "DROP IN, GEAR UP… LOADING" forever
// (session 69): the stub SUPPRESSES AGameStateBase in LokiNetDriver::IsClassNetCacheDivergent to keep
// the connection alive despite schema divergence, so the client has NO replicated GameState and its
// native match-ready check (the ERoundPhase CurrentPhase) never fires. Fix: replicate a native
// ALokiGameState (this class) in a PLAYING state so the client's replica hydrates and the loading
// screen clears (a spectator view of the live tutorial world is the first milestone).
//
// HOW THE CLIENT RECOGNIZES THIS CLASS (the NetGUID-by-path trick)
// ---------------------------------------------------------------
// Same trick as LokiPlayerState_Missions: the stub game module is ALSO named "Loki", so naming this
// UCLASS `LokiGameState` gives it the path /Script/Loki.LokiGameState — when the stub exports this
// actor's class NetGUID by path, the client resolves it to ITS OWN native LokiGameState. No IoStore /
// mod-pak overlay needed. The tutorial's ACTUAL GameStateClass is a Blueprint (BP_LokiGameState_Tutorial_C),
// but the client's loading/match logic is native (on LokiGameState), so a replicated native LokiGameState
// should satisfy it. We derive straight from AGameStateBase: the client's real chain is
// LokiGameState : LokiGameStateBase : GameStateBase, but LokiGameStateBase adds 0 replicated props
// (session-69 live dump), so the RepIndex accumulation is byte-identical either way.
//
// SCHEMA MATCH (session-69 LIVE rep-layout capture — docs/session-69-ds-loadingscreen.txt)
// ----------------------------------------------------------------------------------------
// NetworkChecksumMode is None (LokiNetDriver::InitBase), so the client won't fingerprint-reject this
// class — but the per-property RepLayout cmd stream must line up or the client's read cursor desyncs
// ("ReceivedBunch: Invalid replicated field N"). GameStateBase contributes its stock 4 net props
// (inherited); LokiGameState adds the 43 below (67 leaf cmds) in the EXACT field order captured live.
//   * Enums are FEnumProperty (enum class : uint8) -> the underlying byte serializes on the wire; the
//     mirror enums reproduce the client's value ranges so any CeilLogTwo bit-packing also matches.
//   * ObjectProperty fields (WinningPawn/TeamStates/LokiDebugTarget/DeathCircle) serialize as a single
//     NetGUID cmd regardless of PropertyClass, so TObjectPtr<UObject> aligns (the S54 Missions lesson);
//     kept null unless we later replicate real actors.
//   * MatchStartDetails is a plain member-wise struct (no NetSerializeNative); its members recurse in
//     order. Engine FPrimaryAssetId expands to 2 Name cmds identically on both ends.
// FIELD ORDER + TYPES ARE LOAD-BEARING — do NOT reorder. If a live test desyncs at cmd N, the first
// suspects are the two enum widths and the nested MatchStartDetails element format (RE live with
// tools/re/rep_expand_class.py, exactly like the S54 missions desync).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "UObject/PrimaryAssetId.h"
#include "LokiGameStateStub.generated.h"

// S70: RepIndex parked on inherited replicated props we strip from ClassReps (Loki.cpp StripReplicatedFlag)
// so their lingering GetLifetimeReplicatedProps registration can't collide with a real RepIndex (the
// bIsPushBased assert). Off the ClassReps range; ALokiGameState::GetLifetimeReplicatedProps drops entries
// at this index. Used for AGameStateBase::ReplicatedWorldTimeSeconds (float) — SUPERVIVE replicates only
// the Double, so stripping the float aligns GameStateBase to the client's 4 reps.
static constexpr uint16 LOKI_STRIPPED_REPINDEX_SENTINEL = 0xFFFE;

// Mirror of SUPERVIVE's ERoundPhase (schema.txt, 12 values incl. Count/_MAX). This is the
// LokiGameState.CurrentPhase type and the LIKELY loading-screen gate: S65/S66 found the round stuck at
// EGP_BeginInit=1; the client should reveal the world once CurrentPhase reaches a playing phase
// (EGP_SpawnSelect=4 / EGP_SpawnReveal=5 / EGP_Combat=7). Named ELokiRoundPhase to avoid any clash; the
// enum identity/name is irrelevant to the wire (only the underlying uint8 + value range matter).
UENUM()
enum class ELokiRoundPhase : uint8
{
	EGP_ServerStartup = 0,
	EGP_BeginInit     = 1,
	EGP_Pre           = 2,
	EGP_FinishInit    = 3,
	EGP_SpawnSelect   = 4,
	EGP_SpawnReveal   = 5,
	EGP_Lineup        = 6,
	EGP_Combat        = 7,
	EGP_Post          = 8,
	EGP_Shutdown      = 9,
};

// Mirror of SUPERVIVE's ELokiDayNightState (schema.txt, 4 values). LokiGameState.DayNightState type.
UENUM()
enum class ELokiDayNightStateMirror : uint8
{
	LDNS_Day     = 0,
	LDNS_Night   = 1,
	LDNS_EndGame = 2,
};

// Mirror of SUPERVIVE's SharedMatchStartParticipant (element of MatchStartDetails.Participants).
// Member-wise; every field is serialized by RepLayout in this order. The two FPrimaryAssetId fields'
// exact names weren't captured (only order/type matter for the wire); named descriptively.
USTRUCT()
struct FSharedMatchStartParticipant
{
	GENERATED_BODY()

	UPROPERTY()
	FString PlayerID;

	UPROPERTY()
	FString PartyId;

	UPROPERTY()
	bool IsAnonymous = false;

	UPROPERTY()
	FString PlayerName;

	UPROPERTY()
	int32 AccountLevel = 0;

	UPROPERTY()
	int64 TeamID = 0;

	// FPrimaryAssetId field A (name unconfirmed — likely the hero). Engine type -> 2 Name cmds.
	UPROPERTY()
	FPrimaryAssetId HeroAssetId;

	// FPrimaryAssetId field B (name unconfirmed — likely a skin/banner). Engine type -> 2 Name cmds.
	UPROPERTY()
	FPrimaryAssetId SkinAssetId;

	UPROPERTY()
	int32 KillTotal = 0;

	UPROPERTY()
	int32 HypeTotal = 0;

	UPROPERTY()
	int32 WinStreak = 0;

	UPROPERTY()
	bool IsBot = false;

	UPROPERTY()
	bool IsRanked = false;

	UPROPERTY()
	TArray<FPrimaryAssetId> TitleIds;
};

// Mirror of SUPERVIVE's LokiSharedMatchStartDetails (LokiGameState.MatchStartDetails). Member-wise.
USTRUCT()
struct FLokiSharedMatchStartDetails
{
	GENERATED_BODY()

	UPROPERTY()
	FString MatchID;

	UPROPERTY()
	TArray<int64> TeamIDs;

	UPROPERTY()
	TArray<FSharedMatchStartParticipant> Participants;

	UPROPERTY()
	bool bShouldForceAnonymizeNonTeamParties = false;
};

// Replicated stand-in for the client's LokiGameState. Declares ONLY the 43 replicated (CPF_Net) props,
// in the exact field/RepIndex order from the session-69 live dump. The client's ~93 non-replicated
// LokiGameState props play no part in the wire and are omitted to keep the RepLayout minimal + aligned.
// `transient` mirrors the other stub actor classes (no disk serialization).
UCLASS(transient)
class ALokiGameState : public AGameStateBase
{
	GENERATED_BODY()

public:
	ALokiGameState(const FObjectInitializer& ObjectInitializer);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	// --- LokiGameState own replicated props, EXACT field order (session-69 dump) ---
	UPROPERTY(Replicated) bool  bGetPreventWeaponFire = false;                 // [0]
	UPROPERTY(Replicated) bool  bGetPreventMovement = false;                   // [1]
	UPROPERTY(Replicated) float SpawnSelectEndTime = 0.f;                      // [2]
	UPROPERTY(Replicated) int32 WinningTeam = -1;                              // [3]
	UPROPERTY(Replicated) TObjectPtr<UObject> WinningPawn = nullptr;           // [4] ObjectProperty
	UPROPERTY(Replicated) int32 WinStreak = 0;                                 // [5]
	UPROPERTY(Replicated) TArray<int32> TeamScores;                            // [6] TArray<Int>
	UPROPERTY(Replicated) int32 TeamScoreToWin = 0;                            // [7]
	UPROPERTY(Replicated) TArray<TObjectPtr<UObject>> TeamStates;              // [8] TArray<Object*>
	UPROPERTY(Replicated) bool  bIsSuddenDeath = false;                        // [9]
	UPROPERTY(Replicated) float GameOverWorldTime = 0.f;                       // [10]
	UPROPERTY(Replicated) float GameSuddenDeathOverWorldTime = 0.f;            // [11]
	UPROPERTY(Replicated) float GameDuration = 0.f;                            // [12]
	UPROPERTY(Replicated) float RoundStartTime = 0.f;                          // [13]
	UPROPERTY(Replicated) int32 ReplicatedNumRemainingPlayers = 0;             // [14]
	UPROPERTY(Replicated) int32 MaxPlayersPerTeam = 1;                         // [15]
	UPROPERTY(Replicated) float GameStartWorldTime = 0.f;                      // [16]
	UPROPERTY(Replicated) ELokiDayNightStateMirror DayNightState = ELokiDayNightStateMirror::LDNS_Day; // [17] Enum
	UPROPERTY(Replicated) float LastDayNightChangeTime = 0.f;                  // [18]
	UPROPERTY(Replicated) float TotalDayNightTime = 0.f;                       // [19]
	UPROPERTY(Replicated) int32 EndgamePhase = 0;                              // [20]
	UPROPERTY(Replicated) int32 DeathCirclePhase = 0;                          // [21]
	UPROPERTY(Replicated) FLokiSharedMatchStartDetails MatchStartDetails;      // [22] Struct
	UPROPERTY(Replicated) bool  bDeathCircleRegenerated = false;               // [23]
	UPROPERTY(Replicated) int32 AutomaticRespawnEndPhaseOverride = 0;          // [24]
	UPROPERTY(Replicated) int32 AscendingArmorOverrideTier0 = 0;               // [25]
	UPROPERTY(Replicated) int32 AscendingArmorOverrideTier1 = 0;               // [26]
	UPROPERTY(Replicated) int32 AscendingArmorOverrideTier2 = 0;               // [27]
	UPROPERTY(Replicated) int32 AscendingArmorOverrideTier4 = 0;               // [28] (note: no Tier3)
	UPROPERTY(Replicated) int32 EquipmentUpgradeCostTier0 = 0;                 // [29]
	UPROPERTY(Replicated) int32 EquipmentUpgradeCostTier1 = 0;                 // [30]
	UPROPERTY(Replicated) int32 EquipmentUpgradeCostTier2 = 0;                 // [31]
	UPROPERTY(Replicated) int32 EquipmentUpgradeCostTier3 = 0;                 // [32]
	UPROPERTY(Replicated) int32 EquipmentUpgradeCostTier4 = 0;                 // [33]
	UPROPERTY(Replicated) int32 EquipmentUpgradeCostTier5 = 0;                 // [34]
	UPROPERTY(Replicated) int32 AudioPulseMaxDistance = 0;                     // [35]
	UPROPERTY(Replicated) float AudioPulseCutoffFactorShort = 0.f;            // [36]
	UPROPERTY(Replicated) float AudioPulseCutoffFactorMedium = 0.f;           // [37]
	UPROPERTY(Replicated) float AudioPulseCutoffFactorLong = 0.f;             // [38]
	UPROPERTY(Replicated) int32 NumTeams = 1;                                 // [39]
	UPROPERTY(Replicated) TObjectPtr<UObject> LokiDebugTarget = nullptr;      // [40] ObjectProperty
	UPROPERTY(Replicated) TObjectPtr<UObject> DeathCircle = nullptr;          // [41] ObjectProperty
	UPROPERTY(Replicated) ELokiRoundPhase CurrentPhase = ELokiRoundPhase::EGP_ServerStartup; // [42] Enum — the gate
};
