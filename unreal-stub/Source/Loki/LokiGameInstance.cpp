#include "LokiGameInstance.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiGameInstance, Log, All);

void ULokiGameInstance::ModifyClientTravelLevelURL(FString& LevelName)
{
	// Rewrite whatever our stub is actually running (typically /Engine/Maps/Entry)
	// to the package name the client already has cooked. The client loads its OWN
	// cooked copy of this map; the stub only needs a name the client has.
	// S62 TUTORIAL RETARGET: point at LVL_Tutorial (was LVL_LobbyV2_Persistent, the
	// missions-lobby use case). The menu route enters this via a real tutorial-match
	// NetConnection, so loading LVL_Tutorial through a proper networked session may
	// clear the S61 local-force-open "PlayerState is null" gate (the client now has a
	// server-provided session). Note: the stub does NOT host tutorial gameplay
	// (bare /Engine/Maps/Entry world + stock gamemode), so this tests "does the map
	// load with a valid session", not a playable hero-drop.
	//   Lobby fallback (missions work): /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent
	static const FString ClientExpectedMap =
		TEXT("/Game/Loki/Maps/Tutorial/LVL_Tutorial");

	UE_LOG(LogLokiGameInstance, Display,
	       TEXT("ModifyClientTravelLevelURL: %s -> %s"), *LevelName, *ClientExpectedMap);

	LevelName = ClientExpectedMap;
}
