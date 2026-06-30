// Dedicated server target — THE TARGET this chapter exists to build.
//
// `Type = TargetType.Server` tells UnrealBuildTool to produce a headless
// server binary (LokiServer.exe under Binaries/Win64/) instead of a client
// executable. The compiled server reuses the engine's GameNetDriver (=
// IpNetDriver) — which is exactly the NetDriverDefinition the SUPERVIVE
// client's StatelessConnect handshake reports (per Loki.log captured in
// session 5: "NetDriverDefinition 'GameNetDriver' CachedClientID: 7").
//
// To build:
//   "H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat" `
//     LokiServer Win64 Development `
//     -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"
//
// To launch:
//   Binaries\Win64\LokiServer.exe -log -Port=7777

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
