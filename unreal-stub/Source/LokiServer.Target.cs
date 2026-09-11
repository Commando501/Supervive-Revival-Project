// Dedicated server target — DEFINED but NOT BUILDABLE with the current UE5.4
// engine install.
//
// First build attempt 2026-06-30 failed with:
//
//   "Server targets are not currently supported from this engine distribution."
//
// The Epic Games Launcher install of UE5.4 (the one at H:\Unreal Engine\UE_5.4)
// includes Editor + Game + Editor targets prebuilt, plus Engine source for
// reference, but NOT Server-target build support. A real Server-target build
// requires the UE5 Source distribution from GitHub
// (https://github.com/EpicGames/UnrealEngine) — ~100GB clone + 1-3 hour
// compile of the engine itself first.
//
// Workaround used this chapter: build the Game target (Loki.Target.cs) and
// launch it with `-server`. UE's Game executable, when launched with `-server`,
// runs as a dedicated-server-emulation mode: no client window, no rendering,
// listens on the configured port, accepts NetConnections. Functionally
// equivalent for our purposes (responding to the client's StatelessConnect
// handshake + replicating LokiPlayerState_Missions).
//
// This target file is kept as documentation of the "right" build path for
// when/if the user later installs UE5 from source.

using UnrealBuildTool;
using System.Collections.Generic;

public class LokiServerTarget : TargetRules
{
	public LokiServerTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Server;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.Add("Loki");
	}
}
