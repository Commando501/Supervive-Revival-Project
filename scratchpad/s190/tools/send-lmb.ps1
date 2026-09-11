# send-lmb.ps1 -- S190 E4 predicate flight. Natural-input LMB TAP driver.
#
# Fires GS_Ronin_LightAttack1 as the game's own input would, with the shim out of the way
# (S158 SETUP_ABORT already ran). A player cast via natural input runs the ability body;
# a shim-originated TryActivate dies (WALL P sub-part 1). We drive the LMB the same way
# S189-MV-WASD drove keys: grab foreground (SwitchToThisWindow + AttachThreadInput +
# minimize/restore fallback), then synthesize the click via user32 mouse_event.
#
# CRITICAL: GS_Ronin_LightAttack1 is bIsPressOrHold with HoldMinimumDuration=0.24s. A hold
# >=0.24s fires a RANGED FIREBLAST PROJECTILE (a skillshot); a TAP (<0.24s) fires the 360uu/
# 110-deg melee CONE we want. So -TapMs MUST stay well under 240 (default 150).
#
# Usage:
#   powershell -File send-lmb.ps1 [-ExpectedProcessName SUPERVIVE-Win64-Shipping] [-TapMs 150] [-Taps 2] [-InterTapMs 500]
param(
  [string]$ExpectedProcessName = 'SUPERVIVE-Win64-Shipping',
  [int]$TapMs      = 150,     # LMB down->up hold; MUST be < 240 to fire the cone, not the fireblast
  [int]$Taps       = 2,       # number of taps (LightAttack1 has a short internal cooldown; 1-2 is safe)
  [int]$InterTapMs = 500      # gap between taps
)
if ($TapMs -ge 230) { throw "TapMs=$TapMs is too close to the 240ms hold threshold -- would fire the fireblast projectile, not the melee cone. Use <=200." }

if (-not ('S190LmbInput' -as [type])) {
  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class S190LmbInput {
    [DllImport("user32.dll", SetLastError=true)] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool AllowSetForegroundWindow(int dwProcessId);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern void SwitchToThisWindow(IntPtr hWnd, bool fUnknown);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    // mouse_event: dwFlags LEFTDOWN=0x0002 LEFTUP=0x0004
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
    public const int SW_MINIMIZE=6; public const int SW_RESTORE=9;
    public const uint MOUSEEVENTF_LEFTDOWN=0x0002; public const uint MOUSEEVENTF_LEFTUP=0x0004;
}
'@
}

function Grab-Foreground([IntPtr]$hWnd) {
  [S190LmbInput]::SwitchToThisWindow($hWnd, $true); Start-Sleep -Milliseconds 200
  if ([S190LmbInput]::GetForegroundWindow() -eq $hWnd) { return $true }
  [uint32]$ttid = [S190LmbInput]::GetWindowThreadProcessId($hWnd, [ref]([uint32]0))
  $stid = [S190LmbInput]::GetCurrentThreadId()
  if ($ttid -ne 0) {
    [void][S190LmbInput]::AttachThreadInput($stid, $ttid, $true)
    try { [void][S190LmbInput]::BringWindowToTop($hWnd); [void][S190LmbInput]::SetForegroundWindow($hWnd); [void][S190LmbInput]::ShowWindow($hWnd, [S190LmbInput]::SW_RESTORE) }
    finally { [void][S190LmbInput]::AttachThreadInput($stid, $ttid, $false) }
  }
  Start-Sleep -Milliseconds 300
  if ([S190LmbInput]::GetForegroundWindow() -eq $hWnd) { return $true }
  [void][S190LmbInput]::ShowWindow($hWnd, [S190LmbInput]::SW_MINIMIZE); Start-Sleep -Milliseconds 200
  [void][S190LmbInput]::ShowWindow($hWnd, [S190LmbInput]::SW_RESTORE); Start-Sleep -Milliseconds 400
  return ([S190LmbInput]::GetForegroundWindow() -eq $hWnd)
}

$proc = Get-Process -Name $ExpectedProcessName -ErrorAction Stop
$hWnd = $proc.MainWindowHandle
if ($hWnd -eq [IntPtr]::Zero) { throw "$ExpectedProcessName has no MainWindowHandle" }
Write-Host "target: PID=$($proc.Id) hWnd=0x$($hWnd.ToInt64().ToString('X8'))  TapMs=$TapMs Taps=$Taps"
[void][S190LmbInput]::AllowSetForegroundWindow(-1)
[void][S190LmbInput]::AllowSetForegroundWindow($proc.Id)
$ok = Grab-Foreground -hWnd $hWnd
Write-Host "focus grab: $ok (fg=0x$(([S190LmbInput]::GetForegroundWindow()).ToInt64().ToString('X8')))"
if (-not $ok) { Write-Host "WARNING: could not confirm foreground; sending taps anyway (AttachThreadInput may still deliver)" }

for ($i=1; $i -le $Taps; $i++) {
  [S190LmbInput]::mouse_event([S190LmbInput]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds $TapMs
  [S190LmbInput]::mouse_event([S190LmbInput]::MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
  Write-Host "LMB tap $i/$Taps sent (down ${TapMs}ms up)"
  if ($i -lt $Taps) { Start-Sleep -Milliseconds $InterTapMs }
}
Write-Host "done"
