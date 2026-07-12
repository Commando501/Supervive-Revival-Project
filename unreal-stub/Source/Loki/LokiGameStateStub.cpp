#include "LokiGameStateStub.h"
#include "Net/UnrealNetwork.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiGameStateStub, Log, All);

// Register one AGameStateBase inherited property by NAME as a non-push (bIsPushBased=false), COND_None
// lifetime prop. We do this instead of calling AGameStateBase::GetLifetimeReplicatedProps because the
// engine registers those props as PUSH-BASED (DOREPLIFETIME_WITH_PARAMS_FAST) and also registers the
// deprecated float ReplicatedWorldTimeSeconds. After we rebuild ClassReps at runtime + strip the float,
// the push-based inherited entries collide with our non-push scheme → "Assertion failed: bIsPushBased ==
// Other.bIsPushBased" (CoreNet.h:331). Registering by name, non-push, keeps the whole lifetime list
// consistent. Push model is a server-side dirty-tracking optimization only — the wire is identical.
static void AddGSBaseLifetimeProp(TArray<FLifetimeProperty>& Out, const TCHAR* Name)
{
	if (FProperty* P = FindFProperty<FProperty>(AGameStateBase::StaticClass(), Name))
	{
		Out.Add(FLifetimeProperty(P->RepIndex)); // COND_None, RepNotify default, bIsPushBased=false
	}
	else
	{
		UE_LOG(LogLokiGameStateStub, Warning,
		       TEXT("AddGSBaseLifetimeProp: AGameStateBase::%s not found."), Name);
	}
}

ALokiGameState::ALokiGameState(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// AGameStateBase already sets bReplicates=true + bAlwaysRelevant=true + NetUpdateFrequency=100
	// in its constructor; restate them so the intent is explicit and robust to base changes.
	bReplicates = true;
	bAlwaysRelevant = true;

	UE_LOG(LogLokiGameStateStub, Display,
	       TEXT("ALokiGameState constructed (/Script/Loki.LokiGameState mirror; 43 replicated props "
	            "over stock GameStateBase's 4 — session-69 schema)."));
}

void ALokiGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	// S70: DELIBERATELY skip AGameStateBase::GetLifetimeReplicatedProps (Super = AGameStateBase). It
	// registers its props push-based + registers the deprecated float ReplicatedWorldTimeSeconds, which
	// (with our runtime ClassReps rebuild + float strip) trips the CoreNet.h:331 bIsPushBased assert.
	// Instead register AActor's props, then exactly the 4 GameStateBase props the SUPERVIVE client
	// replicates, BY NAME, non-push — keeping the lifetime list consistent + float-free.
	AActor::GetLifetimeReplicatedProps(OutLifetimeProps);
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("GameModeClass"));
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("SpectatorClass"));
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("bReplicatedHasBegunPlay"));
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("ReplicatedWorldTimeSecondsDouble"));

	// All 43 in field-declaration order (COND_None). The RepIndex assignment that must align with the
	// client comes from declaration order (ForceSetUpReplicationData / SetUpRuntimeReplicationData), not
	// from this list; this list only enables replication + sets conditions.
	DOREPLIFETIME(ALokiGameState, bGetPreventWeaponFire);
	DOREPLIFETIME(ALokiGameState, bGetPreventMovement);
	DOREPLIFETIME(ALokiGameState, SpawnSelectEndTime);
	DOREPLIFETIME(ALokiGameState, WinningTeam);
	DOREPLIFETIME(ALokiGameState, WinningPawn);
	DOREPLIFETIME(ALokiGameState, WinStreak);
	DOREPLIFETIME(ALokiGameState, TeamScores);
	DOREPLIFETIME(ALokiGameState, TeamScoreToWin);
	DOREPLIFETIME(ALokiGameState, TeamStates);
	DOREPLIFETIME(ALokiGameState, bIsSuddenDeath);
	DOREPLIFETIME(ALokiGameState, GameOverWorldTime);
	DOREPLIFETIME(ALokiGameState, GameSuddenDeathOverWorldTime);
	DOREPLIFETIME(ALokiGameState, GameDuration);
	DOREPLIFETIME(ALokiGameState, RoundStartTime);
	DOREPLIFETIME(ALokiGameState, ReplicatedNumRemainingPlayers);
	DOREPLIFETIME(ALokiGameState, MaxPlayersPerTeam);
	DOREPLIFETIME(ALokiGameState, GameStartWorldTime);
	DOREPLIFETIME(ALokiGameState, DayNightState);
	DOREPLIFETIME(ALokiGameState, LastDayNightChangeTime);
	DOREPLIFETIME(ALokiGameState, TotalDayNightTime);
	DOREPLIFETIME(ALokiGameState, EndgamePhase);
	DOREPLIFETIME(ALokiGameState, DeathCirclePhase);
	DOREPLIFETIME(ALokiGameState, MatchStartDetails);
	DOREPLIFETIME(ALokiGameState, bDeathCircleRegenerated);
	DOREPLIFETIME(ALokiGameState, AutomaticRespawnEndPhaseOverride);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier0);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier1);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier2);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier4);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier0);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier1);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier2);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier3);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier4);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier5);
	DOREPLIFETIME(ALokiGameState, AudioPulseMaxDistance);
	DOREPLIFETIME(ALokiGameState, AudioPulseCutoffFactorShort);
	DOREPLIFETIME(ALokiGameState, AudioPulseCutoffFactorMedium);
	DOREPLIFETIME(ALokiGameState, AudioPulseCutoffFactorLong);
	DOREPLIFETIME(ALokiGameState, NumTeams);
	DOREPLIFETIME(ALokiGameState, LokiDebugTarget);
	DOREPLIFETIME(ALokiGameState, DeathCircle);
	DOREPLIFETIME(ALokiGameState, CurrentPhase);
}
