// LokiGameEngine — session 73 (2026-07-11): UGameEngine subclass whose only job is to survive the
// client's World-Partition level-visibility reports on the DS route.
//
// WHY (the gate after the LokiPlayerState mirror)
// -----------------------------------------------
// With the Loki PC + PlayerState mirrors in place the client progresses into LOADING the real
// LVL_Tutorial, whose World Partition runtime streams cells and reports each to the server via
// APlayerController::ServerUpdateLevelVisibility(/Game/Loki/Maps/Tutorial/LVL_Tutorial/_Generated_/<cell>).
// The stub runs a BARE world (/Engine/Maps/Entry renamed), so those cell packages don't exist here →
// UNetConnection::UpdateLevelVisibility → ValidateLevelVisibility bLevelExists=false → Close(MissingLevelPackage).
// The RPC (ServerUpdateLevelVisibility) is UFUNCTION(...SealedEvent) + its _Implementation is non-virtual,
// and UNetConnection::UpdateLevelVisibility + ValidateLevelVisibility are non-virtual/file-static — so the
// only clean interception is the VIRTUAL UEngine::NetworkRemapPath(UNetConnection*, FString&, bool), which
// ServerUpdateLevelVisibility_Implementation calls (via GEngine->NetworkRemapPath) on BOTH the PackageName
// and FileName before validating. We redirect any WP _Generated_ cell path to /Engine/Maps/Entry — a package
// that EXISTS on disk — so ValidateLevelVisibility's DoesPackageExist() passes (bLevelExists=true) and the
// connection survives. All stub actors are bAlwaysRelevant, so real level-visibility tracking isn't needed.
//
// Registered via DefaultEngine.ini: [/Script/Engine.Engine] GameEngine=/Script/Loki.LokiGameEngine
// (the stub boots as UGameEngine — "Game Engine Initialized" — even under UnrealEditor-Cmd -game).
#pragma once

#include "CoreMinimal.h"
#include "Engine/GameEngine.h"
#include "LokiGameEngine.generated.h"

UCLASS(transient)
class ULokiGameEngine : public UGameEngine
{
	GENERATED_BODY()

public:
	// Bring both UEngine::NetworkRemapPath overloads into scope so overriding one doesn't hide the
	// UPendingNetGame overload (used during travel) — avoids a -WarningsAsErrors hidden-overload error.
	using UGameEngine::NetworkRemapPath;
	virtual bool NetworkRemapPath(UNetConnection* Connection, FString& Str, bool bReading = true) override;
};
