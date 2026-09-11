<#
  S177 Move next-1 - ETW capture around an FK-32 kill.

  Purpose
  -------
  If FK-32 is fired by a kernel-mode terminator (Candidate B: a protector driver
  calling PsTerminateProcess from ring 0), the user-mode call chain we've been
  chasing (0x80F7F0, NtTerminateProcess, RtlExitUserProcess, ...) will NEVER
  fire, and no user-mode HW BP can catch it. But the kernel logger DOES observe
  it: PROC_THREAD kernel events + stack-walk on ProcessTerminate should capture
  who called into Ps*TerminateProcess. If the stack top is a driver image, B is
  confirmed. If the stack is all user-mode ntdll+process code, B is refuted and
  the kill came from user mode by some path we haven't identified.

  What this script does
  ---------------------
  1. Start an ETW real-time trace using xperf on the classic kernel providers
     PROC_THREAD (process/thread lifecycle) + LOADER (image loads/unloads),
     with stack-walk enabled on ProcessTerminate events.
  2. Return control to the operator (or another script) so a flight can proceed.
  3. On -Stop or when the caller signals, stop the trace and merge symbol data.
  4. Use xperf -symbols to symbolicate, then dump the trace to CSV so we can
     grep for our target PID's ProcessTerminate row and its stack.

  Requirements
  ------------
  - Elevated PowerShell (verified: this session runs elevated).
  - xperf.exe from Windows Performance Toolkit (found at
    C:\Program Files (x86)\Windows Kits\8.1\Windows Performance Toolkit\xperf.exe).
  - Enough disk to hold a couple hundred MB of ETL (the whole-system PROC_THREAD
    trace is small; we run for at most 3-4 minutes per FK-32 flight).

  Usage
  -----
  # Start:
  powershell -File scratchpad\s177\etw_kernel_process.ps1 -Start
  # ...run the FK-32 flight (game launch + DR install; wait for kill)...
  # Stop and analyze:
  powershell -File scratchpad\s177\etw_kernel_process.ps1 -Stop -TargetPid <PID>

  Design notes
  ------------
  - We use the classic "NT Kernel Logger" session (name "NT Kernel Logger" is
    reserved). Only ONE such session can run at a time system-wide. Any pre-
    existing kernel logger must be stopped first (this script handles that).
  - PROC_THREAD alone would capture the ProcessTerminate event but without the
    call stack. LOADER helps xperf symbolicate stack frames to module+function.
    Stack-walk `ProcessTerminate` records the RIP at the moment PsTerminate is
    called; if that RIP is inside a driver, we have Candidate B.
  - We do NOT use Microsoft-Windows-Kernel-Process (the manifest-based provider)
    because its ProcessStop event does NOT carry a call-stack payload. The
    classic PROC_THREAD provider + kernel stack-walk is the only way to see WHO
    called Terminate.
  - The classic kernel session accepts stack-walk on specific EventName ids;
    xperf's -stackwalk ProcessDelete is the modern name (older docs say
    ProcessTerminate). We pass both to be safe.
  - We register a POST-STOP xperf -merge to fold in module info from the current
    boot, so kernel-mode stack frames resolve to driver names.

  Blind spots (banked)
  --------------------
  - If the protector's driver is unsigned or hides its module list entry, the
    stack frame may show a raw RIP with no symbol. That is still diagnostic
    (raw RIP in a kernel-mode range = a driver we can then hunt for).
  - Kernel stack-walk requires KernelStackWalk registry permission; on modern
    Windows this is default-enabled for Administrators but a Group Policy can
    disable it. If frames come back with "no stack" every time, that's the
    cause, not our script.
#>
[CmdletBinding()]
param(
    [switch]$Start,
    [switch]$Stop,
    [int]$TargetPid = 0,
    [string]$EtlPath = "",
    [string]$CsvOut  = "",
    [string]$Xperf   = "C:\Program Files (x86)\Windows Kits\8.1\Windows Performance Toolkit\xperf.exe"
)

if (-not (Test-Path $Xperf)) {
    Write-Error "xperf.exe not found at $Xperf"
    exit 2
}

# Resolve default paths against the SCRIPT'S directory, then normalize. Using
# defaults with $PSScriptRoot inline at param binding time can produce a bare
# 'G:\' when the script is invoked with a relative path (Split-Path chokes on
# a repeated '..' walk past the root). Recomputing here with an absolute base
# sidesteps that.
if (-not $EtlPath -or $EtlPath -eq '') {
    $EtlPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\dumps\s177-etw-kernel.etl'))
}
if (-not $CsvOut -or $CsvOut -eq '') {
    $CsvOut  = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\dumps\s177-etw-kernel.csv'))
}

# The classic NT Kernel Logger session name is reserved; we don't get to pick.
$KernelSessionName = "NT Kernel Logger"

function Stop-KernelSession {
    # xperf -stop stops the kernel session and flushes to the ETL path it was
    # given at -on time. If none is running the exit code is nonzero; that's
    # not fatal, we just skip.
    & $Xperf -stop | Out-Null
}

if ($Start) {
    # Belt-and-braces: any prior kernel session must be stopped, else -on fails.
    Stop-KernelSession
    # PROC_THREAD: ProcessStart/Stop, ThreadStart/Stop
    # LOADER: DLL/driver loads and unloads, needed for stack symbolication
    # -stackwalk with ProcessTerminate captures the call stack at process kill
    # (the modern event name is ProcessDelete on some builds; pass both - xperf
    # tolerates unknown names by warning).
    $EtlDir = Split-Path -Parent $EtlPath
    if (-not (Test-Path $EtlDir)) { New-Item -ItemType Directory -Path $EtlDir | Out-Null }
    if (Test-Path $EtlPath) { Remove-Item $EtlPath -Force }
    Write-Host "[etw] starting NT Kernel Logger -> $EtlPath"
    Write-Host "[etw]   providers: PROC_THREAD + LOADER"
    Write-Host "[etw]   stackwalk: ProcessDelete (and ProcessTerminate as a legacy alias)"
    # NB: on this build ProcessTerminate may print a warning; still runs.
    & $Xperf -on PROC_THREAD+LOADER -stackwalk ProcessDelete -f $EtlPath 2>&1 |
        Write-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "xperf -on returned $LASTEXITCODE - check output above"
        exit 3
    }
    Write-Host "[etw] session running. Run the FK-32 flight now."
    Write-Host "[etw] when the game dies, run this script again with -Stop."
    exit 0
}

if ($Stop) {
    Write-Host "[etw] stopping kernel session"
    & $Xperf -stop 2>&1 | Write-Host
    if (-not (Test-Path $EtlPath)) {
        Write-Error "ETL file $EtlPath was not produced. Did -Start run?"
        exit 4
    }
    $sz = (Get-Item $EtlPath).Length
    Write-Host "[etw] ETL captured: $sz bytes"
    Write-Host "[etw] merging with local symbol/module data..."
    $Merged = [System.IO.Path]::ChangeExtension($EtlPath, ".merged.etl")
    if (Test-Path $Merged) { Remove-Item $Merged -Force }
    # -merge folds in the current image list so kernel-mode addresses resolve
    # to driver names. Without this, a stack frame in win32k or a protector
    # driver reads as raw RIP only.
    & $Xperf -merge $EtlPath $Merged 2>&1 | Write-Host
    if (-not (Test-Path $Merged)) {
        Write-Warning "merge failed; falling back to raw ETL"
        $Merged = $EtlPath
    }
    Write-Host "[etw] dumping to CSV for grep-friendly analysis"
    if (Test-Path $CsvOut) { Remove-Item $CsvOut -Force }
    # tracerpt is the built-in ETL parser. -of CSV emits a large but greppable
    # text file; the ProcessTerminate/ProcessDelete rows carry the PID + stack.
    & tracerpt.exe $Merged -o $CsvOut -of CSV -y 2>&1 | Write-Host
    if (-not (Test-Path $CsvOut)) {
        Write-Error "tracerpt did not produce $CsvOut"
        exit 5
    }
    $csvSz = (Get-Item $CsvOut).Length
    Write-Host "[etw] CSV size: $csvSz bytes"
    if ($TargetPid -gt 0) {
        Write-Host ""
        Write-Host ("=== rows referencing PID {0} (last 40) ===" -f $TargetPid)
        # A CSV row containing our PID as a field is easy to spot. We match
        # on decimal form; tracerpt CSV writes PIDs as decimals in the
        # standard PROC_THREAD schema.
        $pidPattern = ",\s*{0}\s*," -f $TargetPid
        Select-String -Path $CsvOut -Pattern $pidPattern |
            Select-Object -Last 40 | ForEach-Object { $_.Line }
        Write-Host ""
        Write-Host "=== ProcessTerminate / ProcessDelete / ProcessStop rows ==="
        Select-String -Path $CsvOut -Pattern "ProcessTerminate|ProcessDelete|ProcessStop" |
            Select-Object -First 20 | ForEach-Object { $_.Line }
    }
    Write-Host ""
    Write-Host "[etw] done."
    Write-Host "  raw ETL   : $EtlPath"
    Write-Host "  merged ETL: $Merged"
    Write-Host "  CSV       : $CsvOut"
    Write-Host ""
    Write-Host "Next: grep CSV for ProcessTerminate/ProcessStop of the target PID,"
    Write-Host "      then read the stack frames above/below it. A frame in a driver"
    Write-Host "      image (or a raw kernel-mode RIP) confirms Candidate B."
    exit 0
}

Write-Host "usage: -Start | -Stop [-TargetPid PID]"
Write-Host "  Start begins an NT Kernel Logger trace with PROC_THREAD+LOADER + ProcessDelete stackwalk."
Write-Host "  Stop  flushes the trace, merges it, dumps to CSV, and filters by PID if given."
exit 1
