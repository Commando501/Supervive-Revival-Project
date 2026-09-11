// Loki game module — the primary (and currently only) module. Linked into
// both the Game target and Server target via ExtraModuleNames.Add("Loki")
// in the respective Target.cs files.

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
			// Session 13: LokiStatelessConnect subclasses StatelessConnectHandlerComponent
			// (defined in PacketHandler module + lives in Engine module's
			// PacketHandlers header dir). PacketHandler exposes the
			// HandlerComponent base + FIncomingPacketRef.
			"PacketHandler",
			// LokiNetDriver subclasses UIpNetDriver from the OnlineSubsystemUtils plugin
			"OnlineSubsystemUtils",
			// SetDriver / NetDriver base requires Sockets for FInternetAddr
			"Sockets",
		});
	}
}
