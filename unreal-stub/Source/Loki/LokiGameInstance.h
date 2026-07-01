// LokiGameInstance — server-side UGameInstance subclass that rewrites the
// LevelName announced to clients in NMT_Welcome.
//
// Session 19 blocker: our stub runs the stock UE `/Engine/Maps/Entry` map, so
// UWorld::WelcomePlayer sends `LevelName = /Engine/Maps/Entry` in NMT_Welcome.
// The SUPERVIVE client is a cooked shipping build; `/Engine/Maps/Entry` is
// editor-only content and does not exist as a cooked package on the client.
// UEngine::TickWorldTravel calls `MakeSureMapNameIsValid(URL.Map)` which does
// `FPackageName::DoesPackageExist("/Engine/Maps/Entry")` — returns false —
// client bails via `BrowseToDefaultMap` (falls back to LVL_Login) and closes
// the control channel. That's the disconnect at session 18 close.
//
// Fix: override UGameInstance::ModifyClientTravelLevelURL, which
// UWorld::WelcomePlayer calls with the LevelName by reference right before
// sending NMT_Welcome. Rewrite it to `/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent`
// — the actual map path the client originally browsed to and already has
// cooked into its packages. Client receives Welcome with a valid map name,
// MakeSureMapNameIsValid returns true, LoadMap fires, then SendJoin.
//
// Registered via DefaultEngine.ini:
//   [/Script/EngineSettings.GameMapsSettings]
//   GameInstanceClass=/Script/Loki.LokiGameInstance

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "LokiGameInstance.generated.h"

UCLASS(config=Game)
class ULokiGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	virtual void ModifyClientTravelLevelURL(FString& LevelName) override;
};
