#include "LokiGameEngine.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiGameEngine, Log, All);

bool ULokiGameEngine::NetworkRemapPath(UNetConnection* Connection, FString& Str, bool bReading)
{
	// Only touch INCOMING (bReading) World-Partition cell paths. The client reports LVL_Tutorial's streamed
	// cells (…/_Generated_/<cell>) which don't exist on the bare stub; redirect them to /Engine/Maps/Entry
	// (guaranteed on disk) so ValidateLevelVisibility's DoesPackageExist() → bLevelExists=true → no
	// Close(MissingLevelPackage). Leave the main map + all other paths to the stock UGameEngine remap.
	if (bReading && Str.Contains(TEXT("/_Generated_/")))
	{
		static bool bLoggedOnce = false;
		if (!bLoggedOnce)
		{
			bLoggedOnce = true;
			UE_LOG(LogLokiGameEngine, Display,
			       TEXT("NetworkRemapPath: redirecting World-Partition cell '%s' -> /Engine/Maps/Entry "
			            "(first of many; suppresses ServerUpdateLevelVisibility MissingLevelPackage close)."), *Str);
		}
		Str = TEXT("/Engine/Maps/Entry");
		return true;
	}
	return Super::NetworkRemapPath(Connection, Str, bReading);
}
