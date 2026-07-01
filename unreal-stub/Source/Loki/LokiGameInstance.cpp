#include "LokiGameInstance.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiGameInstance, Log, All);

void ULokiGameInstance::ModifyClientTravelLevelURL(FString& LevelName)
{
	// Rewrite whatever our stub is actually running (typically /Engine/Maps/Entry)
	// to the package name the client already has cooked. LobbyV2 was the URL the
	// client browsed to via browse_hook, so it's guaranteed to exist in the
	// client's cooked package set. See header comment for full rationale.
	static const FString ClientExpectedMap =
		TEXT("/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent");

	UE_LOG(LogLokiGameInstance, Display,
	       TEXT("ModifyClientTravelLevelURL: %s -> %s"), *LevelName, *ClientExpectedMap);

	LevelName = ClientExpectedMap;
}
