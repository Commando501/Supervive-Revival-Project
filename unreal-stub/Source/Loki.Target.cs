// Game target — exists for completeness so a regular client/editor build can
// produce a non-server executable. The chapter's actual target is
// LokiServer.Target.cs below; this one is mostly a no-op placeholder.

using UnrealBuildTool;
using System.Collections.Generic;

public class LokiTarget : TargetRules
{
	public LokiTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.Add("Loki");
	}
}
