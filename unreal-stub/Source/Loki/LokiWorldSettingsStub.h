// Session 76: ALokiWorldSettings — a NON-PUSH mirror of AWorldSettings.
//
// WHY: S76 un-suppressed AWorldSettings (WorldInfo) so the client's replica hydrates (the DS ~2-min crash is the
// S53/S54 garbage-thread AV from a half-hydrated replica). But replicating stock AWorldSettings crashes the STUB:
// its GetLifetimeReplicatedProps calls Super all the way up and registers derived props PUSH-based, which clashes
// with the stub's validation-free ForceSetUpReplicationData rebuild (ClassReps non-push) → "Assertion failed:
// bIsPushBased == Other.bIsPushBased" (CoreNet.h:331) on client connect. S70 hit the identical assert on
// AGameStateBase and fixed it with a non-push mirror (call AActor::GetLifetimeReplicatedProps, then register the
// derived props NON-PUSH). This applies the same pattern to WorldSettings.
//
// The world's WorldSettings is a level actor (serialized in the .umap), so we can't just set
// GEngine->WorldSettingsClass — ULokiGameEngine::LoadMap swaps the live WorldSettings actor to this class after
// the map loads (see LokiGameEngine.cpp).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/WorldSettings.h"
#include "LokiWorldSettingsStub.generated.h"

UCLASS(transient)
class ALokiWorldSettings : public AWorldSettings
{
	GENERATED_BODY()

public:
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
};
