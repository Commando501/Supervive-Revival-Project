#include "LokiGameEngine.h"
#include "LokiWorldSettingsStub.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "GameFramework/WorldSettings.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiGameEngine, Log, All);

bool ULokiGameEngine::LoadMap(FWorldContext& WorldContext, FURL URL, UPendingNetGame* Pending, FString& Error)
{
	const bool bOk = Super::LoadMap(WorldContext, URL, Pending, Error);

	// After the map is up, replace the stock WorldSettings actor with the non-push ALokiWorldSettings mirror.
	// The world's WorldSettings is serialized in the .umap, so this runtime swap is the only reliable path.
	// Runs before any client connects, so the RepLayout the stub later builds for WorldSettings uses the mirror's
	// non-push GetLifetimeReplicatedProps → no CoreNet.h:331 assert. ALokiWorldSettings is a native class present
	// at module startup, so InjectServerStateReplicatedProperty already rebuilt its ClassReps (ServerState@[10]).
	if (bOk)
	{
		UWorld* W = WorldContext.World();
		if (W && W->PersistentLevel)
		{
			AWorldSettings* Old = W->GetWorldSettings(/*bCheckStreamingPersistent*/ false, /*bChecked*/ false);
			if (Old && !Old->IsA<ALokiWorldSettings>())
			{
				FActorSpawnParameters SP;
				SP.OverrideLevel = W->PersistentLevel;
				SP.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				ALokiWorldSettings* New = W->SpawnActor<ALokiWorldSettings>(ALokiWorldSettings::StaticClass(), SP);
				if (New)
				{
					// Carry over the load-bearing gameplay settings from the stock WS so nothing that already
					// read the old one breaks (GameMode override etc.).
					New->DefaultGameMode = Old->DefaultGameMode;
					New->KillZ = Old->KillZ;
					New->WorldGravityZ = Old->WorldGravityZ;
					New->bGlobalGravitySet = Old->bGlobalGravitySet;
					W->PersistentLevel->SetWorldSettings(New);
					Old->Destroy();
					UE_LOG(LogLokiGameEngine, Display,
					       TEXT("LoadMap: swapped WorldSettings for %s -> ALokiWorldSettings (non-push mirror; "
					            "avoids the CoreNet.h:331 bIsPushBased assert on WorldSettings replication)."),
					       *URL.Map);
				}
				else
				{
					UE_LOG(LogLokiGameEngine, Warning, TEXT("LoadMap: failed to spawn ALokiWorldSettings replacement."));
				}
			}
		}
	}

	return bOk;
}

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
