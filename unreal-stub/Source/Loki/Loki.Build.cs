// Loki game module — the primary (and currently only) module. Linked into
// both the Game target and Server target via ExtraModuleNames.Add("Loki")
// in the respective Target.cs files.
//
// NetCore is included up front since this whole stub exists to handle
// network connections; we'll need its types as we add ALokiPlayerState_Missions
// and friends.

using UnrealBuildTool;

public class Loki : ModuleRules
{
	public Loki(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"NetCore",
		});

		// Server-only dependencies can go here later if we need them
		// (e.g., FunctionalTesting, Networking utilities, etc.).
	}
}
