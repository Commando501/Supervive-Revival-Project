<#
  S178 Move #1 - ETW capture of NtOpenProcess to test companion-process handle sourcing.

  Purpose
  -------
  S177/S178 established that FK-32 fires from a hidden runtime.dll companion process. S178 A3
  narrowed the IPC mechanism to "dynamic open" [I_strong] - companion likely opens the game
  process at runtime via NtOpenProcess rather than inheriting a handle. This capture tests it:
  filter every NtOpenProcess call made by the companion PID and look for target = game PID +
  access mask including PROCESS_TERMINATE (0x0001).

  Providers
  ---------
  - Microsoft-Windows-Kernel-Process
      GUID {22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}
      Gives us ProcessStart/Stop so we can label PID lifecycle in the ETL.
  - Microsoft-Windows-Kernel-Audit-API-Calls
      GUID {E02A841C-75A3-4FA7-AFC8-AE09CF9B7F23}
      Emits NtOpenProcess (event ID 1) with target PID + access mask.

  These are BOTH manifest providers, so we run them in a USER-MODE session with a unique name
  ("S178_OpenProc"). We do NOT touch the classic NT Kernel Logger (reserved single-instance) -
  S177's PROC_THREAD data is already banked.

  Usage
  -----
  # 1) Start (returns immediately):
  powershell -File scratchpad\s178\etw_openprocess.ps1 -Start

  # 2) Fly the FK-32 trigger - launch game, wait menu, install DRs. Wait for kill.

  # 3) Stop and analyze:
  powershell -File scratchpad\s178\etw_openprocess.ps1 -Stop
  # (auto-parses via tracerpt to CSV, then filters and prints the answer)

  Design notes
  ------------
  - We use logman/xperf rather than direct ETW API calls. logman is the built-in equivalent.
  - Session name "S178_OpenProc" is unique per this recipe; a stale prior session is stopped
    automatically before the fresh -Start.
  - We keep the session small: only two providers, no stackwalk. Larger ETL is possible with
    stackwalk but adds ~10x cost and the OpenProcess event body already carries enough to
    answer the question (target PID + access mask).

  Blind spots (banked, S178)
  --------------------------
  - Kernel-Audit-API-Calls fires per Nt-syscall; if the companion uses a NON-Nt entry (e.g.
    directly encodes the syscall number without going through the ntdll wrapper), the provider
    may not observe it. Runtime.dll has 923 raw `0F 05` syscall opcodes - SOME of them may
    bypass the audit hook. If we see NO NtOpenProcess event by the companion, that is
    consistent with EITHER (a) handle inheritance OR (b) raw-syscall open. Discriminator for
    the two: presence of PS_ATTRIBUTE_HANDLE_LIST in the parent's CreateProcess call, or a
    live handle-table snapshot on companion at spawn. (Move #2 from S178 synthesis.)
  - Kernel-Audit-API-Calls provider requires elevation (Administrator). This session runs
    elevated, so it's fine.
#>
[CmdletBinding()]
param(
    [switch]$Start,
    [switch]$Stop,
    [int]$TargetPid = 0,
    [string]$SessionName = "S178_OpenProc",
    [string]$EtlPath = "",
    [string]$CsvOut = ""
)

if (-not $EtlPath -or $EtlPath -eq '') {
    $EtlPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\dumps\s178-etw-openproc.etl'))
}
if (-not $CsvOut -or $CsvOut -eq '') {
    $CsvOut = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\dumps\s178-etw-openproc.csv'))
}

$AuditGUID = '{E02A841C-75A3-4FA7-AFC8-AE09CF9B7F23}'
$ProcGUID  = '{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}'

if ($Start) {
    # Stop any stale session with the same name (logman errors on stopping a non-existent
    # session; we swallow it).
    Write-Host "[etw-op] stopping any prior '$SessionName' session (ignore errors)"
    & logman.exe stop $SessionName -ets 2>&1 | Out-Null

    # Ensure output dir exists.
    $EtlDir = Split-Path -Parent $EtlPath
    if (-not (Test-Path $EtlDir)) { New-Item -ItemType Directory -Path $EtlDir | Out-Null }
    if (Test-Path $EtlPath) { Remove-Item $EtlPath -Force }

    Write-Host "[etw-op] starting user-mode session '$SessionName' -> $EtlPath"
    Write-Host "[etw-op]   providers: Kernel-Process + Kernel-Audit-API-Calls"

    # Create session with the first provider, then add the second (logman requires this
    # two-step for multiple providers in one session on some Windows builds).
    & logman.exe create trace $SessionName -o $EtlPath -p $AuditGUID 0xFFFFFFFFFFFFFFFF 0xFF -ets 2>&1 |
        Write-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "logman create trace returned $LASTEXITCODE"
        exit 3
    }
    & logman.exe update trace $SessionName -p $ProcGUID 0xFFFFFFFFFFFFFFFF 0xFF -ets 2>&1 |
        Write-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "logman update trace (add ProcGUID) returned $LASTEXITCODE"
        # Not fatal - we still have the Audit provider running.
    }

    Write-Host "[etw-op] session running. Run the FK-32 trigger now."
    Write-Host "[etw-op] when the game dies, run this script again with -Stop."
    exit 0
}

if ($Stop) {
    Write-Host "[etw-op] stopping session '$SessionName'"
    & logman.exe stop $SessionName -ets 2>&1 | Write-Host
    if (-not (Test-Path $EtlPath)) {
        Write-Error "ETL file $EtlPath was not produced. Did -Start run?"
        exit 4
    }
    $sz = (Get-Item $EtlPath).Length
    Write-Host "[etw-op] ETL captured: $sz bytes"

    Write-Host "[etw-op] dumping to CSV via tracerpt"
    if (Test-Path $CsvOut) { Remove-Item $CsvOut -Force }
    & tracerpt.exe $EtlPath -o $CsvOut -of CSV -y 2>&1 | Write-Host
    if (-not (Test-Path $CsvOut)) {
        Write-Error "tracerpt did not produce $CsvOut"
        exit 5
    }
    $csvSz = (Get-Item $CsvOut).Length
    Write-Host "[etw-op] CSV size: $csvSz bytes"

    Write-Host ""
    Write-Host "=== NtOpenProcess events (from Kernel-Audit-API-Calls) ==="
    # Kernel-Audit-API-Calls emits events with the provider GUID as the event provider column.
    # Rows contain: EventName, PID (caller), TID (caller), then event-specific User Data
    # including TargetProcessId and DesiredAccess.
    $auditGuidText = $AuditGUID.Trim('{}').ToLower()
    Write-Host "  Filtering for provider $auditGuidText..."
    Select-String -Path $CsvOut -Pattern $auditGuidText |
        Select-Object -First 100 | ForEach-Object { $_.Line }

    if ($TargetPid -gt 0) {
        Write-Host ""
        Write-Host ("=== Rows referencing target PID {0} (0x{0:X}) ===" -f $TargetPid)
        $pidPattern = ",\s*{0}\s*," -f $TargetPid
        $pidPatternHex = "0x{0:X8}" -f $TargetPid
        Select-String -Path $CsvOut -Pattern "$pidPattern|$pidPatternHex" |
            Select-Object -First 50 | ForEach-Object { $_.Line }

        Write-Host ""
        Write-Host ("=== ProcessStart/Stop rows (Kernel-Process) for context ===")
        Select-String -Path $CsvOut -Pattern 'ProcessStart|ProcessStop|Process.Start|Process.Stop' |
            Select-Object -First 20 | ForEach-Object { $_.Line }
    }

    Write-Host ""
    Write-Host "[etw-op] done."
    Write-Host "  raw ETL: $EtlPath"
    Write-Host "  CSV    : $CsvOut"
    Write-Host ""
    Write-Host "Next: grep CSV for NtOpenProcess rows where"
    Write-Host "  - caller PID = companion PID (runtime.dll process)"
    Write-Host "  - target PID = game PID"
    Write-Host "  - DesiredAccess includes PROCESS_TERMINATE (0x0001)"
    Write-Host "One or more such rows confirms dynamic-open [M]; ZERO rows means the companion"
    Write-Host "acquired the handle by another mechanism (inheritance, duplication, or raw syscall)."
    exit 0
}

Write-Host "usage: -Start | -Stop [-TargetPid N]"
exit 1
