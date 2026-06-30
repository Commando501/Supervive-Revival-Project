// Editor target — builds the project's Loki module as a DLL that
// UnrealEditor.exe (and UnrealEditor-Cmd.exe) can load. This is the path
// we use to RUN the server, since the standalone Loki.exe Game-target
// build hit an engine-content serialization bug on first launch:
//
//   "Seeked past end of file /Engine/EngineMaterials/WorldGridMaterial
//    (30170 / 30169)"
//
// Known UE5.4 Launcher-install issue when a custom non-editor binary
// tries to load uncooked engine content. The prebuilt UnrealEditor
// binary doesn't hit it (it has the right asset version handling
// built in), so we load our Loki module THROUGH that binary instead.
//
// To build:
//   "H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat" `
//     LokiEditor Win64 Development `
//     -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"
//
// To run as a dedicated server (after build completes):
//   "H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
//     "G:\git\Supervive Revival Project\unreal-stub\Loki.uproject" `
//     -game -server -log -Port=7777 -nullrhi -NoSplash -Unattended

using UnrealBuildTool;
using System.Collections.Generic;

public class LokiEditorTarget : TargetRules
{
	public LokiEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.Add("Loki");
	}
}
