# send-wasd.ps1 -- S189-MV-WASD flight. P/Invoke keybd_event driver with
# 30 Hz AUTO-REPEAT during hold windows (critical fix from V1 adversarial verify:
# a single keybd_event Key-Down produces ONE WM_KEYDOWN; UE axis reads only one
# frame of input. For sustained 4s WASD, we must inject repeat KEYDOWN at ~33ms
# intervals across the hold duration, then send KEYUP at the end).
#
# Adapted from scratchpad/s158/tools/s158-send-shift.ps1 (proven S158 primitive).
#
# Params:
#   -Sequence w,d,f13   # which keys to test (in order), each held HoldMs
#   -HoldMs 3000        # duration of each key hold
#   -InterKeyMs 2000    # observation gap between keys (validates rest state)
#   -RepeatMs 33        # auto-repeat interval within hold window (~30 Hz)
#   -SyncFile <path>    # write ARM_<KEY>_START / ARM_<KEY>_END timestamps here
#
# Virtual keys:
#   w=0x57 a=0x41 s=0x53 d=0x44 f13=0x7C (F13 = unbound negative control)

[CmdletBinding()]
param(
    [string]$Sequence = 'w,d,f13',
    [int]$HoldMs = 3000,
    [int]$InterKeyMs = 2000,
    [int]$RepeatMs = 33,
    [string]$SyncFile = ''
)
$ErrorActionPreference = 'Stop'
$ExpectedProcessName = 'SUPERVIVE-Win64-Shipping'

$VK = @{
    'w' = [byte]0x57
    'a' = [byte]0x41
    's' = [byte]0x53
    'd' = [byte]0x44
    'tab' = [byte]0x09
    'lshift' = [byte]0xA0
    'space' = [byte]0x20
    'f13' = [byte]0x7C
}

if (-not ('S189WasdInput' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class S189WasdInput {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")]
    public static extern uint MapVirtualKey(uint code, uint mapType);
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte virtualKey, byte scanCode, uint flags, UIntPtr extraInfo);
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool AllowSetForegroundWindow(int dwProcessId);
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
    [DllImport("kernel32.dll")]
    public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")]
    public static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern void SwitchToThisWindow(IntPtr hWnd, bool fUnknown);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    public const int SW_MINIMIZE = 6;
    public const int SW_RESTORE = 9;
    public const int SW_SHOWNOACTIVATE = 4;
    public const int SW_SHOW = 5;
}
'@
}

function Grab-Foreground([IntPtr]$targetHwnd, [int]$targetPid) {
    # Method 1: SwitchToThisWindow (undocumented but effective)
    [S189WasdInput]::SwitchToThisWindow($targetHwnd, $true)
    Start-Sleep -Milliseconds 200
    $fg = [S189WasdInput]::GetForegroundWindow()
    if ($fg -eq $targetHwnd) { return $true }

    # Method 2: AttachThreadInput trick
    [uint32]$targetTid = [S189WasdInput]::GetWindowThreadProcessId($targetHwnd, [ref]([uint32]0))
    $selfTid = [S189WasdInput]::GetCurrentThreadId()
    if ($targetTid -ne 0) {
        [void][S189WasdInput]::AttachThreadInput($selfTid, $targetTid, $true)
        try {
            [void][S189WasdInput]::BringWindowToTop($targetHwnd)
            [void][S189WasdInput]::SetForegroundWindow($targetHwnd)
            [void][S189WasdInput]::ShowWindow($targetHwnd, [S189WasdInput]::SW_RESTORE)
        } finally {
            [void][S189WasdInput]::AttachThreadInput($selfTid, $targetTid, $false)
        }
    }
    Start-Sleep -Milliseconds 300
    $fg = [S189WasdInput]::GetForegroundWindow()
    if ($fg -eq $targetHwnd) { return $true }

    # Method 3: minimize + restore cycle
    [void][S189WasdInput]::ShowWindow($targetHwnd, [S189WasdInput]::SW_MINIMIZE)
    Start-Sleep -Milliseconds 200
    [void][S189WasdInput]::ShowWindow($targetHwnd, [S189WasdInput]::SW_RESTORE)
    Start-Sleep -Milliseconds 400
    $fg = [S189WasdInput]::GetForegroundWindow()
    return ($fg -eq $targetHwnd)
}

$proc = Get-Process -Name $ExpectedProcessName -ErrorAction Stop
$hWnd = $proc.MainWindowHandle
if ($hWnd -eq [IntPtr]::Zero) { throw "$ExpectedProcessName has no MainWindowHandle" }

Write-Host "target: PID=$($proc.Id) hWnd=0x$($hWnd.ToInt64().ToString('X8'))"

[void][S189WasdInput]::AllowSetForegroundWindow(-1)  # ASFW_ANY
[void][S189WasdInput]::AllowSetForegroundWindow($proc.Id)

$focusOk = Grab-Foreground -targetHwnd $hWnd -targetPid $proc.Id
$fg = [S189WasdInput]::GetForegroundWindow()
[uint32]$fgPid = 0
[void][S189WasdInput]::GetWindowThreadProcessId($fg, [ref]$fgPid)
Write-Host "foreground after grab: hWnd=0x$($fg.ToInt64().ToString('X8')) PID=$fgPid focusOk=$focusOk"

if (-not $focusOk) {
    Write-Host "WARN: could not confirm game foreground -- SENDING KEYS ANYWAY (input may go to wrong window)" -ForegroundColor Yellow
    if ($SyncFile) { Add-Content -Path $SyncFile -Value "FOCUS_FAILED $(Get-Date -Format 'HH:mm:ss.fff') fgPid=$fgPid" }
    # NOTE: proceeding to send anyway; if input doesn't reach the game the probe will show CIV=0 which
    # is the SAME signature as Branch C — will need to disambiguate from the flight log.
}

function Get-NowStamp { (Get-Date -Format 'HH:mm:ss.fff') }

function Send-KeyDown([byte]$vk, [byte]$scan) {
    [S189WasdInput]::keybd_event($vk, $scan, [uint32]0, [UIntPtr]::Zero)
}
function Send-KeyUp([byte]$vk, [byte]$scan) {
    [S189WasdInput]::keybd_event($vk, $scan, [uint32]2, [UIntPtr]::Zero)
}

function Send-KeyHoldRepeat {
    param([string]$KeyName, [int]$Ms, [int]$RepMs)
    $vk = $VK[$KeyName.ToLower()]
    if (-not $vk) { throw "Unknown key: $KeyName" }
    $scan = [byte]([S189WasdInput]::MapVirtualKey([uint32]$vk, [uint32]0))

    $t0 = Get-Date
    $startStamp = Get-NowStamp
    if ($SyncFile) { Add-Content -Path $SyncFile -Value "ARM_$($KeyName.ToUpper())_START $startStamp" }
    Write-Host "[$startStamp] ARM $KeyName START vk=0x$($vk.ToString('X2')) scan=0x$($scan.ToString('X2')) hold=${Ms}ms rep=${RepMs}ms"

    # Auto-repeat: emit KEYDOWN at RepMs intervals across the hold duration
    Send-KeyDown $vk $scan  # initial down
    $repeatCount = 1
    while ((New-TimeSpan -Start $t0 -End (Get-Date)).TotalMilliseconds -lt $Ms) {
        Start-Sleep -Milliseconds $RepMs
        Send-KeyDown $vk $scan  # repeat
        $repeatCount++
    }
    Send-KeyUp $vk $scan
    $endStamp = Get-NowStamp
    if ($SyncFile) { Add-Content -Path $SyncFile -Value "ARM_$($KeyName.ToUpper())_END $endStamp" }
    Write-Host "[$endStamp] ARM $KeyName END repeats=$repeatCount"
}

$sequenceStart = Get-NowStamp
$seqArr = $Sequence -split ','
Write-Host "[$sequenceStart] SEQUENCE START: $($seqArr -join ',')  (hold=${HoldMs}ms rep=${RepeatMs}ms gap=${InterKeyMs}ms)"
if ($SyncFile) { Add-Content -Path $SyncFile -Value "SEQUENCE_START $sequenceStart" }

for ($i = 0; $i -lt $seqArr.Length; $i++) {
    Send-KeyHoldRepeat -KeyName $seqArr[$i].Trim() -Ms $HoldMs -RepMs $RepeatMs
    if ($i -lt $seqArr.Length - 1) {
        Write-Host "[$(Get-NowStamp)] observation gap ${InterKeyMs}ms"
        Start-Sleep -Milliseconds $InterKeyMs
    }
}

$sequenceEnd = Get-NowStamp
if ($SyncFile) { Add-Content -Path $SyncFile -Value "SEQUENCE_END $sequenceEnd" }
Write-Host "[$sequenceEnd] SEQUENCE DONE"
