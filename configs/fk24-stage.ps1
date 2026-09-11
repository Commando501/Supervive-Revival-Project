<#
  fk24-stage.ps1 — stage the tutorial world and inject a probe/candidate DLL into it.

  WHY THIS EXISTS (S108, 2026-08-04)
  ----------------------------------
  The S107 recipe (docs/next-session-prompt-s108.md §0) needs a HUMAN to press
  PLAY -> TUTORIALS -> BASIC TRAINING -> START before anything can be injected, because
  RM_PLAY and RM_SPAWNPOSSESS are CONTINUATION modes: they attach to an already-running
  tutorial and `return 0` before the force-open block, so `-Hook <play dll>` alone cannot work.

  The button press has exactly ONE backend effect: POST /party/parties/{id}/startSoloMode sets
  playerState.SoloMode, and handleCoreGamePlayer's gate is `forceTutorialMatch || SoloMode != ""`.
  So setting `forceTutorialMatch = true` in server/internal/interactive/interactive.go substitutes
  for the press exactly, and the client parks itself with nobody at the keyboard. That flag MUST be
  true for this script to fire — it checks, and refuses to run if the backend is not serving a match.

  ORDER IS LOAD-BEARING, and every step is gated on MEASURED evidence rather than a fixed sleep:
    1. tutorial_launch_fo.dll   force-opens LVL_Tutorial into the parked match model
    2. gft_ready_fix.dll        game-feature-toggle ready marker
    3. tutorial_launch_sp.dll   spawn + possess  (ONE-SHOT, no retry loop -- inject only once the
                                world is genuinely up, or you get [SP] gm=0x0 pc=0x0 and the run is dead)
    4. <-Probe>                 the play/probe build under test

  ⚠ docs/tutorial-launch-marker.txt is opened CREATE_ALWAYS, so EVERY injection TRUNCATES it (FK-25).
    This script copies it off after each stage into docs/fk24-stage-<Label>-<n>-<shim>.txt so no
    stage's output is lost, and that is the only reason the earlier stages' lines survive at all.

  Read-only w.r.t. the game otherwise. Run from an ELEVATED PowerShell.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Probe,       # path to the DLL under test (usually build\tutorial_launch_play*.dll)
  [string]$Label = "run",                           # tag for the copied-off marker files
  [int]$MinUptimeSec   = 110,                       # login+lobby settle before we touch anything
  [int]$WaitProcSec    = 300,                       # how long to wait for the game to appear
  [int]$WaitParkedSec  = 420,                       # how long to wait for the parked match model
  [int]$WaitWorldSec   = 180,                       # how long to wait for LVL_Tutorial after force-open
  [switch]$SkipProbe,                               # stage the world only (fo+gft+sp), inject nothing else
  [int]$InjectGapSeconds = 20,                      # S109: MINIMUM seconds between successive manual-maps.
                                                    # Evidence-gate waits count toward it, so this only
                                                    # sleeps the shortfall. 20 matches the new default in
                                                    # inject-secondaries.ps1. Pass 5 to reproduce the old
                                                    # gft->fo spacing. See docs/s109-dump-forensics.md 18-20.
  [switch]$AllowStale,                              # inject anyway when a shim's .text differs from build\
  [string]$Fo = ""                                  # S112: alternate force-open DLL (e.g. the
                                                    # `fo-nologinvt` arm, which drops the slot-285
                                                    # `.rdata` vtable write). Empty = the deployed
                                                    # tutorial_launch_fo.dll, i.e. unchanged behaviour.
  ,[string]$BindOnly = ""                          # S149 opt-in: isolated bind setup injected before unchanged S148
  ,[string]$ExpectedBindOnlySha256 = ""            # mandatory whole-file pin when -BindOnly is used
  ,[string]$ExpectedProbeSha256 = 'C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E'
  ,[switch]$PlanOnly                                # emit the side-effect-free S149 action plan as JSON and exit
  ,[int]$WaitBindReadySec = 120
  ,[int]$WaitS148TerminalSec = 180
  ,[string]$RuntimeRepo = ""                       # explicit proven runtime tree for injector/staging shims/hard-coded marker
  ,[string]$EvidenceDir = ""                       # separate destination for immutable stage receipts
  ,[string]$CapturePath = ""                       # current backend capture; bind mode pins it to this worktree
  ,[uint32]$ExpectedBackendPid = 0
  ,[int64]$ExpectedBackendStartTicks = 0
  ,[uint32]$ExpectedWatcherPid = 0
  ,[int64]$ExpectedWatcherStartTicks = 0
  ,[string]$WatcherLogPath = ""
  ,[string]$ExpectedWatcherOutputDir = ""
  ,[string]$ExpectedControllerWorktree = ""
  ,[string]$ExpectedStagerSha256 = ""
  ,[string]$ExpectedS149GateSha256 = ""
  ,[string]$ExpectedPowerShellPath = ""
  ,[string]$ExpectedPowerShellSha256 = ""
  ,[string]$ExpectedS149ContractSha256 = ""
  ,[string]$ExpectedS148ContractSha256 = ""
)

$ErrorActionPreference = 'Stop'
$repo    = Split-Path -Parent $PSScriptRoot
$s149Gate = Join-Path $PSScriptRoot 's149-bind-gate.ps1'

function Assert-S149StageNoReparseFile {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$PinnedBase,
        [Parameter(Mandatory=$true)][string]$Path)
  $base=[IO.Path]::GetFullPath($PinnedBase).TrimEnd('\')
  $target=[IO.Path]::GetFullPath($Path)
  if(-not $target.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){
    throw "stager provenance path escapes its pinned base: $target"
  }
  $baseAttributes=[IO.File]::GetAttributes($base)
  if(($baseAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
     ($baseAttributes -band [IO.FileAttributes]::Directory) -eq 0){
    throw "stager provenance base is not an ordinary directory: $base"
  }
  $relative=$target.Substring($base.Length+1)
  $parts=@($relative.Split([char[]]@('\','/'),[StringSplitOptions]::RemoveEmptyEntries))
  if($parts.Count -eq 0){ throw "stager provenance target must be a file below its base: $target" }
  $candidate=$base
  for($index=0;$index -lt $parts.Count;$index++){
    $candidate=Join-Path $candidate $parts[$index]
    $attributes=[IO.File]::GetAttributes($candidate)
    if(($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
      throw "stager provenance path contains a reparse component: $candidate"
    }
    if($index -lt ($parts.Count-1) -and ($attributes -band [IO.FileAttributes]::Directory) -eq 0){
      throw "stager provenance path component is not a directory: $candidate"
    }
  }
  if(($attributes -band [IO.FileAttributes]::Directory) -ne 0){
    throw "stager provenance target is not a regular file: $target"
  }
  return $target
}

function Assert-S149StagePinnedFile {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$PinnedBase,
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$ExpectedSha256)
  if($ExpectedSha256 -notmatch '\A[0-9A-Fa-f]{64}\z'){
    throw "stager provenance expected hash is malformed: $Path"
  }
  $full=Assert-S149StageNoReparseFile -PinnedBase $PinnedBase -Path $Path
  $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash
  if($actual -cne $ExpectedSha256.ToUpperInvariant()){
    throw "stager provenance mismatch path=$full expected=$($ExpectedSha256.ToUpperInvariant()) actual=$actual"
  }
  return [pscustomobject]@{Path=$full;Sha256=$actual;Length=[int64]([IO.FileInfo]::new($full).Length)}
}

function Assert-S149StagerBootstrap {
  [CmdletBinding()]
  param()
  foreach($required in @($ExpectedControllerWorktree,$ExpectedStagerSha256,$ExpectedS149GateSha256,
      $ExpectedPowerShellPath,$ExpectedPowerShellSha256,$ExpectedS149ContractSha256,$ExpectedS148ContractSha256)){
    if([string]::IsNullOrWhiteSpace([string]$required)){ throw 'bind mode requires the complete stager bootstrap provenance argv' }
  }
  $worktree=[IO.Path]::GetFullPath($ExpectedControllerWorktree).TrimEnd('\')
  $actualRepo=[IO.Path]::GetFullPath($repo).TrimEnd('\')
  if(-not $actualRepo.Equals($worktree,[StringComparison]::OrdinalIgnoreCase)){
    throw "stager worktree mismatch expected=$worktree actual=$actualRepo"
  }
  $expectedConfigs=Join-Path $worktree 'configs'
  if(-not ([IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')).Equals(
      ([IO.Path]::GetFullPath($expectedConfigs).TrimEnd('\')),[StringComparison]::OrdinalIgnoreCase)){
    throw 'stager configs directory is not inside the exact controller worktree'
  }
  $stager=[IO.Path]::GetFullPath($PSCommandPath)
  $gate=Join-Path $worktree 'configs\s149-bind-gate.ps1'
  $s149Contract=Join-Path $worktree 'tools\sigbypass-mod\tests\s149_bind_contract_test.ps1'
  $s148Contract=Join-Path $worktree 'tools\sigbypass-mod\tests\s148_build_contract_test.ps1'
  $canonicalPowerShell='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
  $powerShell=[IO.Path]::GetFullPath($ExpectedPowerShellPath)
  if(-not $powerShell.Equals($canonicalPowerShell,[StringComparison]::OrdinalIgnoreCase)){
    throw "stager PowerShell path is not the reviewed executable: $powerShell"
  }
  $current=[Diagnostics.Process]::GetCurrentProcess()
  try{ $currentPowerShell=[IO.Path]::GetFullPath([string]$current.MainModule.FileName) }
  finally{ $current.Dispose() }
  if(-not $currentPowerShell.Equals($powerShell,[StringComparison]::OrdinalIgnoreCase)){
    throw "stager host process path mismatch expected=$powerShell actual=$currentPowerShell"
  }
  [void](Assert-S149StagePinnedFile -PinnedBase $worktree -Path $stager -ExpectedSha256 $ExpectedStagerSha256)
  [void](Assert-S149StagePinnedFile -PinnedBase $worktree -Path $gate -ExpectedSha256 $ExpectedS149GateSha256)
  [void](Assert-S149StagePinnedFile -PinnedBase $worktree -Path $s149Contract -ExpectedSha256 $ExpectedS149ContractSha256)
  [void](Assert-S149StagePinnedFile -PinnedBase $worktree -Path $s148Contract -ExpectedSha256 $ExpectedS148ContractSha256)
  [void](Assert-S149StagePinnedFile -PinnedBase 'C:\Windows' -Path $powerShell -ExpectedSha256 $ExpectedPowerShellSha256)
  $script:verifiedControllerWorktree=$worktree
  $script:verifiedPowerShellPath=$powerShell
  $script:verifiedS149ContractPath=$s149Contract
  $script:verifiedS148ContractPath=$s148Contract
}

if($BindOnly){
  Assert-S149StagerBootstrap
  . $s149Gate
}

if($PlanOnly){
  if(-not $BindOnly){ throw '-PlanOnly for the controlled route requires -BindOnly' }
  New-S149FlightPlan -InjectGapSeconds $InjectGapSeconds | ConvertTo-Json -Depth 5
  return
}
if($BindOnly -and $SkipProbe){ throw '-BindOnly cannot be combined with -SkipProbe' }
if($BindOnly -and $InjectGapSeconds -lt 20){ throw 'bind-then-S148 mode requires InjectGapSeconds >= 20' }

$canonicalRuntimeRepo = 'G:\git\Supervive Revival Project'
if($BindOnly){
  if([string]::IsNullOrWhiteSpace($RuntimeRepo)){
    throw "bind mode requires explicit -RuntimeRepo '$canonicalRuntimeRepo'"
  }
  $runtimeFull = [IO.Path]::GetFullPath($RuntimeRepo).TrimEnd('\')
  if(-not $runtimeFull.Equals($canonicalRuntimeRepo,[StringComparison]::OrdinalIgnoreCase)){
    throw "bind mode requires explicit -RuntimeRepo '$canonicalRuntimeRepo'; actual='$runtimeFull'"
  }
  $RuntimeRepo = $runtimeFull
} elseif(-not $RuntimeRepo){ $RuntimeRepo = $repo }
$runtimeDocs = Join-Path $RuntimeRepo 'docs'
if(-not $EvidenceDir){ $EvidenceDir = Join-Path $repo 'docs' }
$inject  = Join-Path $RuntimeRepo 'tools\inject\inject.exe'
$shimDir = Join-Path $RuntimeRepo 'tools\sigbypass-mod'
$docs    = $EvidenceDir
$lokiLog = Join-Path $env:LOCALAPPDATA 'SUPERVIVE\Saved\Logs\Loki.log'
$marker  = Join-Path $runtimeDocs 'tutorial-launch-marker.txt'
$capture = if($CapturePath){
  $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CapturePath)
} else {
  Join-Path $repo 'docs\capture.log'
}
$ledgerDir = Join-Path $runtimeDocs 's149-ledgers'
$watcherExe = Join-Path $repo 'tools\usmapdump\usmapdump.exe'
$expectedWatcherSha256 = '6DAA73BF7238C0A0D91490CA10C38096F88CAA3841C333BBA89B8C55A57B2FCF'

if($BindOnly){
  if($Label -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'){
    throw 'bind-mode -Label must be 1-64 safe filename characters'
  }
  $expectedCapture = [IO.Path]::GetFullPath((Join-Path $repo 'docs\capture.log'))
  if(-not ([IO.Path]::GetFullPath($capture)).Equals($expectedCapture,[StringComparison]::OrdinalIgnoreCase)){
    throw "bind mode pins -CapturePath to the current worktree backend generation: $expectedCapture"
  }
  if($ExpectedBackendPid -eq 0 -or $ExpectedBackendStartTicks -le 0){
    throw 'bind mode requires explicit -ExpectedBackendPid and -ExpectedBackendStartTicks'
  }
  if($ExpectedWatcherPid -eq 0 -or $ExpectedWatcherStartTicks -le 0 -or
     [string]::IsNullOrWhiteSpace($WatcherLogPath) -or
     [string]::IsNullOrWhiteSpace($ExpectedWatcherOutputDir)){
    throw 'bind mode requires the exact watcher PID/start, log path, and output directory'
  }
  $WatcherLogPath=[IO.Path]::GetFullPath($WatcherLogPath)
  $ExpectedWatcherOutputDir=[IO.Path]::GetFullPath($ExpectedWatcherOutputDir).TrimEnd('\')
  $worktreeDocsRoot=[IO.Path]::GetFullPath((Join-Path $repo 'docs')).TrimEnd('\')+'\'
  if(-not $WatcherLogPath.StartsWith($worktreeDocsRoot,[StringComparison]::OrdinalIgnoreCase)){
    throw "watcher log must be preserved under the worktree docs root: $worktreeDocsRoot"
  }
  $worktreeDumpRoot=[IO.Path]::GetFullPath((Join-Path $repo 'dumps')).TrimEnd('\')+'\'
  if(-not ($ExpectedWatcherOutputDir+'\').StartsWith($worktreeDumpRoot,[StringComparison]::OrdinalIgnoreCase)){
    throw "watcher output must be a child of the worktree dump root: $worktreeDumpRoot"
  }
}

function Say($m){ Write-Host "[stage] $m" }
trap {
  if($script:s148Attempted){
    Say "post-ledger failure is terminal and forbids retry: $($_.Exception.Message)"
    exit 11
  }
  throw $_
}

function Get-S149MapPinnedBase([string]$Path){
  $full=[IO.Path]::GetFullPath($Path)
  foreach($base in @($repo,$RuntimeRepo)){
    if([string]::IsNullOrWhiteSpace([string]$base)){ continue }
    $baseFull=[IO.Path]::GetFullPath($base).TrimEnd('\')
    if($full.StartsWith($baseFull+'\',[StringComparison]::OrdinalIgnoreCase)){ return $baseFull }
  }
  throw "map provenance path is outside the reviewed worktree/runtime roots: $full"
}

function Assert-S149MapPathProvenance([string]$Path,[string]$ExpectedSha256){
  $base=Get-S149MapPinnedBase -Path $Path
  return Assert-S149StagePinnedFile -PinnedBase $base -Path $Path -ExpectedSha256 $ExpectedSha256
}

function Confirm-S149StagerContractPin([string]$ContractPath,[string]$ExpectedContractSha256,
                                       [string]$ArtifactPath,[string]$ExpectedArtifactSha256){
  [void](Assert-S149StagePinnedFile -PinnedBase 'C:\Windows' -Path $script:verifiedPowerShellPath `
      -ExpectedSha256 $ExpectedPowerShellSha256)
  [void](Assert-S149StagePinnedFile -PinnedBase $script:verifiedControllerWorktree -Path $ContractPath `
      -ExpectedSha256 $ExpectedContractSha256)
  [void](Assert-S149MapPathProvenance -Path $ArtifactPath -ExpectedSha256 $ExpectedArtifactSha256)
}

function Assert-S149ProcessIdentity {
  Assert-S149TargetMapIdentity
}

function Assert-S149TargetMapIdentity {
  if(-not $BindOnly -or -not $script:gamePid -or -not $script:gameStartTicks){ return }
  $matches = @(Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)
  $actual = Get-Process -Id $script:gamePid -ErrorAction SilentlyContinue
  $actualPid = if($actual){ [uint32]$actual.Id } else { 0 }
  $actualTicks = if($actual){ [int64]$actual.StartTime.ToUniversalTime().Ticks } else { 0 }
  $actualName = if($actual){ $actual.ProcessName } else { '' }
  $actualPath=''
  if($actual){ try{$actualPath=$actual.Path}catch{} }
  $identity = Get-S149RuntimeProcessIdentityResult `
      -ExpectedPid ([uint32]$script:gamePid) -ExpectedStartTicks ([int64]$script:gameStartTicks) `
      -ExpectedName 'SUPERVIVE-Win64-Shipping' -ExpectedPath $script:gamePath `
      -ActualPid $actualPid -ActualStartTicks $actualTicks -ActualName $actualName -ActualPath $actualPath `
      -MatchingProcessCount $matches.Count
  if(-not $identity.Valid){
    Say "S149 PROCESS IDENTITY REFUSED: $($identity.Reason) expectedPid=$($script:gamePid) expectedStartTicks=$($script:gameStartTicks)"
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
}

function Assert-S149BackendIdentity {
  if(-not $BindOnly){ return }
  $matches=@(Get-Process ags -ErrorAction SilentlyContinue)
  $actual=Get-Process -Id $ExpectedBackendPid -ErrorAction SilentlyContinue
  $actualPid=if($actual){[uint32]$actual.Id}else{0}
  $actualTicks=if($actual){[int64]$actual.StartTime.ToUniversalTime().Ticks}else{0}
  $actualName=if($actual){$actual.ProcessName}else{''}
  $actualPath=''
  if($actual){ try{$actualPath=$actual.Path}catch{} }
  $expectedPath=Join-Path $repo 'server\ags.exe'
  $identity=Get-S149RuntimeProcessIdentityResult `
      -ExpectedPid $ExpectedBackendPid -ExpectedStartTicks $ExpectedBackendStartTicks `
      -ExpectedName 'ags' -ExpectedPath $expectedPath `
      -ActualPid $actualPid -ActualStartTicks $actualTicks -ActualName $actualName `
      -ActualPath $actualPath -MatchingProcessCount $matches.Count
  if(-not $identity.Valid){
    Say "S149 BACKEND IDENTITY REFUSED: $($identity.Reason)"
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
  if($script:backendSha256){
    $backendHash=(Get-FileHash -Algorithm SHA256 -LiteralPath $expectedPath).Hash
    if($backendHash -ne $script:backendSha256){
      Say "S149 BACKEND HASH REFUSED expected=$($script:backendSha256) actual=$backendHash"
      exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
    }
  }
}

function Assert-S149WatcherIdentity {
  if(-not $BindOnly -or -not $script:gamePid){ return }
  $matches=@(Get-Process usmapdump -ErrorAction SilentlyContinue)
  $actual=Get-Process -Id $ExpectedWatcherPid -ErrorAction SilentlyContinue
  $actualPid=if($actual){[uint32]$actual.Id}else{0}
  $actualTicks=if($actual){[int64]$actual.StartTime.ToUniversalTime().Ticks}else{0}
  $actualName=if($actual){$actual.ProcessName}else{''}
  $actualPath=''
  if($actual){ try{$actualPath=$actual.Path}catch{} }
  $identity=Get-S149RuntimeProcessIdentityResult `
      -ExpectedPid $ExpectedWatcherPid -ExpectedStartTicks $ExpectedWatcherStartTicks `
      -ExpectedName 'usmapdump' -ExpectedPath $watcherExe `
      -ActualPid $actualPid -ActualStartTicks $actualTicks -ActualName $actualName `
      -ActualPath $actualPath -MatchingProcessCount $matches.Count
  if(-not $identity.Valid){
    Say "S149 WATCHER IDENTITY REFUSED: $($identity.Reason)"
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
  $watcherHash=(Get-FileHash -Algorithm SHA256 -LiteralPath $watcherExe).Hash
  if($watcherHash -ne $expectedWatcherSha256){
    Say "S149 WATCHER HASH REFUSED expected=$expectedWatcherSha256 actual=$watcherHash"
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
  $cim=Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $ExpectedWatcherPid) -ErrorAction SilentlyContinue
  $commandLine=if($cim){[string]$cim.CommandLine}else{''}
  $commandGate=Get-S149WatcherCommandResult -CommandLine $commandLine `
      -ExpectedExecutablePath $watcherExe -ExpectedGameName 'SUPERVIVE-Win64-Shipping.exe' `
      -ExpectedOutputDir $ExpectedWatcherOutputDir -ExpectedLokiPath $lokiLog
  if(-not $commandGate.Valid){
    Say "S149 WATCHER COMMAND REFUSED: $($commandGate.Reason)"
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
  $watcherLogItem=Get-Item -LiteralPath $WatcherLogPath -ErrorAction SilentlyContinue
  if($null -eq $watcherLogItem){
    Say 'S149 WATCHER RECEIPT REFUSED: WATCHER_LOG_MISSING'
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
  $watcherText=Read-Locked $WatcherLogPath 100000
  $receipt=Get-S149WatcherReceiptResult -Text $watcherText `
      -ExpectedGamePid ([uint32]$script:gamePid) -ExpectedWatcherPid $ExpectedWatcherPid `
      -ExpectedWatcherStartUtcTicks $ExpectedWatcherStartTicks `
      -ExpectedLogCreationUtcTicks $script:watcherLogCreationUtcTicks `
      -ActualLogCreationUtcTicks ([int64]$watcherLogItem.CreationTimeUtc.Ticks) `
      -ActualLogLastWriteUtcTicks ([int64]$watcherLogItem.LastWriteTimeUtc.Ticks) `
      -NowUtcTicks ([datetime]::UtcNow.Ticks) -ExpectedLokiPath $lokiLog `
      -ExpectedOutputDir $ExpectedWatcherOutputDir
  if(-not $receipt.Valid){
    Say "S149 WATCHER RECEIPT REFUSED: $($receipt.Reason)"
    exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
  }
}

function Assert-S149FlightIdentity {
  Assert-S149ProcessIdentity
  Assert-S149BackendIdentity
  Assert-S149WatcherIdentity
}

function Copy-S149ImmutableFile([string]$Source,[string]$Destination){
  if(-not (Test-Path -LiteralPath $Source)){ throw "required evidence source missing: $Source" }
  if(Test-Path -LiteralPath $Destination){ throw "immutable evidence destination already exists: $Destination" }
  $sourceStream=[IO.File]::Open($Source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try{
    $destinationStream=[IO.File]::Open($Destination,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
    try{
      $sourceStream.CopyTo($destinationStream)
      $destinationStream.Flush($true)
      [void]$sourceStream.Seek(0,[IO.SeekOrigin]::Begin)
      [void]$destinationStream.Seek(0,[IO.SeekOrigin]::Begin)
      $shaSource=[Security.Cryptography.SHA256]::Create()
      $shaDestination=[Security.Cryptography.SHA256]::Create()
      try{
        $sourceHash=([BitConverter]::ToString($shaSource.ComputeHash($sourceStream))).Replace('-','')
        $destinationHash=([BitConverter]::ToString($shaDestination.ComputeHash($destinationStream))).Replace('-','')
      } finally { $shaSource.Dispose(); $shaDestination.Dispose() }
      if($sourceHash -ne $destinationHash){ throw "evidence hash changed during immutable copy source=$sourceHash destination=$destinationHash" }
    } finally { $destinationStream.Dispose() }
  } finally { $sourceStream.Dispose() }
  return $destinationHash
}

function Copy-StageMarker([string]$suffix,[bool]$Required=$true){
  if(-not (Test-Path $marker)){
    if($Required){ throw "required stage marker missing for $suffix" }
    return
  }
  $dst = Join-Path $docs ("fk24-stage-{0}-{1}.txt" -f $Label,$suffix)
  Copy-Item -LiteralPath $marker -Destination $dst -Force
  Say "    marker -> $(Split-Path -Leaf $dst)"
}

function Get-S149MarkerSnapshot {
  $snapshot=Get-S149StableFileSnapshot -Path $marker -MaxBytes 500000 -AllowMissing
  if(-not $snapshot.Valid){ throw "marker pre-map snapshot refused: $($snapshot.Reason)" }
  $beforeHash=if($snapshot.Exists){[string]$snapshot.Sha256}else{''}
  return [pscustomobject]@{
    BeforeExists=[bool]$snapshot.Exists
    BeforeSha256=$beforeHash
  }
}

function Get-S149StageMarkerGeneration([int]$StageNumber){
  if(-not $script:stageMarkerSnapshots.ContainsKey($StageNumber)){
    return [pscustomobject]@{ Valid=$false; Reason='MAP_SNAPSHOT_MISSING' }
  }
  $snapshot=$script:stageMarkerSnapshots[$StageNumber]
  $currentSnapshot=Get-S149StableFileSnapshot -Path $marker -MaxBytes 500000
  $generation=Get-S149MarkerGenerationResult `
      -BeforeExists ([bool]$snapshot.BeforeExists) -BeforeSha256 ([string]$snapshot.BeforeSha256) `
      -CurrentSnapshot $currentSnapshot `
      -MapNotBeforeUtcTicks ([int64]$snapshot.MapNotBeforeUtcTicks) `
      -GameStartUtcTicks ([int64]$script:gameStartTicks) -NowUtcTicks ([datetime]::UtcNow.Ticks)
  if($generation.Valid){ $script:lastMarkerSnapshots[$StageNumber]=$generation }
  return $generation
}

function Write-S149ImmutableSnapshot($Snapshot,[string]$Destination){
  if($null -eq $Snapshot -or -not $Snapshot.Valid -or $Snapshot.Sha256 -notmatch '^[0-9A-Fa-f]{64}$'){
    throw 'required accepted marker snapshot is missing or malformed'
  }
  if(Test-Path -LiteralPath $Destination){ throw "immutable evidence destination already exists: $Destination" }
  $bytes=[byte[]]$Snapshot.Bytes
  if($bytes.LongLength -ne [int64]$Snapshot.Length){ throw 'accepted marker snapshot length mismatch' }
  $sha=[Security.Cryptography.SHA256]::Create()
  try{ $sourceHash=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','') }
  finally{ $sha.Dispose() }
  if($sourceHash -ne $Snapshot.Sha256){ throw 'accepted marker snapshot hash mismatch' }
  $destinationStream=[IO.File]::Open($Destination,[IO.FileMode]::CreateNew,
      [IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try{
    $destinationStream.Write($bytes,0,$bytes.Length)
    $destinationStream.Flush($true)
    [void]$destinationStream.Seek(0,[IO.SeekOrigin]::Begin)
    $shaDestination=[Security.Cryptography.SHA256]::Create()
    try{ $destinationHash=([BitConverter]::ToString($shaDestination.ComputeHash($destinationStream))).Replace('-','') }
    finally{ $shaDestination.Dispose() }
    if($destinationHash -ne $sourceHash){ throw 'immutable marker snapshot destination hash mismatch' }
  } finally { $destinationStream.Dispose() }
  return $destinationHash
}

function Save-S149StageMarkerOrExit([string]$suffix,[int]$FailureCode,$Snapshot){
  try {
    $dst=Join-Path $docs ("fk24-stage-{0}-{1}.txt" -f $Label,$suffix)
    [void](Write-S149ImmutableSnapshot -Snapshot $Snapshot -Destination $dst)
    Say "    marker -> $(Split-Path -Leaf $dst)"
  }
  catch {
    Say "required immutable marker archive REFUSED suffix=$suffix error=$($_.Exception.Message)"
    exit $FailureCode
  }
}

# ---- S111: THE DEPLOYED-vs-BUILD STALENESS GUARD -------------------------------------------------
# `build.ps1` writes to tools\sigbypass-mod\build\, but this script injects the DEPLOYED copies in
# tools\sigbypass-mod\. Those are two tiers on purpose (build output vs blessed artifact) -- but
# nothing enforced the relationship, so they drifted silently and you could BUILD A FIX, RUN THE
# STANDARD STAGING, AND TEST THE OLD BINARY.
#
# MEASURED 2026-08-05 across the 142 deployed DLLs: 64 `.text`-identical to build, 68 with no build
# counterpart at all, and 10 DRIFTED -- including `tutorial_launch_sp.dll` (root d0d3cc140c4f4286 vs
# build 4285c0dd22ae9976, i.e. missing KGASSTORAGE) and, worse, `tutorial_launch_play.dll`, whose
# deployed `.text` is a67239a0d83d9300 -- the hash CLAUDE.md identifies as `play-statictest`, the
# S108b diagnostic that faulted every run and disabled anim swapping.
#
# Compare `.text` ONLY. A whole-file compare says all three staging shims differ when two of them are
# functionally identical (the delta is PE-header/debug bytes), which is the project's standing
# "diff .text, never whole-file" rule -- here it is the difference between one real problem and three.
function Get-TextHash([string]$path){
  if(-not (Test-Path $path)){ return $null }
  $d = [IO.File]::ReadAllBytes($path)
  $pe = [BitConverter]::ToInt32($d, 0x3C)
  $ns = [BitConverter]::ToUInt16($d, $pe + 6)
  $opt= [BitConverter]::ToUInt16($d, $pe + 20)
  $off = $pe + 24 + $opt
  for($i = 0; $i -lt $ns; $i++){
    $s = $off + $i * 40
    $nm = ([Text.Encoding]::ASCII.GetString($d, $s, 8)).TrimEnd([char]0)
    if($nm -eq '.text'){
      $sz = [BitConverter]::ToInt32($d, $s + 16)
      $pr = [BitConverter]::ToInt32($d, $s + 20)
      $sha = [Security.Cryptography.SHA256]::Create()
      $h = $sha.ComputeHash($d, $pr, $sz)
      return (($h | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0,16)
    }
  }
  return $null
}
# Refuses by default: a silent wrong-binary test costs an armed window, and armed windows are the
# scarce resource here. -AllowStale overrides when the older artifact is genuinely what you want.
function Assert-Fresh([string]$dll){
  $bld = Join-Path (Split-Path -Parent $dll) ('build\' + (Split-Path -Leaf $dll))
  if(-not (Test-Path $bld)){ return }                       # historic variant, nothing to compare
  $a = Get-TextHash $dll; $b = Get-TextHash $bld
  if($null -eq $a -or $null -eq $b -or $a -eq $b){ return }
  $msg = ("STALE DEPLOYED SHIM: {0}`n" -f (Split-Path -Leaf $dll)) +
         ("           deployed .text {0}`n" -f $a) +
         ("           build\   .text {0}`n" -f $b) +
          "           build.ps1 wrote a newer binary than the one about to be injected."
  if($AllowStale){ Say "WARNING - $msg"; Say "           (-AllowStale given; injecting the deployed copy anyway)" }
  else {
    Say "ABORT - $msg"
    Say "           Fix: copy the build\ artifact over the deployed one, or pass -AllowStale,"
    Say "           or point -Probe directly at the build\ path."
    throw "stale shim: $dll"
  }
}

# Loki.log is held open by the game with a share mode we must match, so Get-Content can hard-fail
# mid-run. Read through an explicit FileShare::ReadWrite handle instead.
function Read-Locked([string]$path,[int]$tailBytes = 400000){
  if(-not (Test-Path $path)){ return '' }
  try{
    $fs = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{
      if($fs.Length -gt $tailBytes){ [void]$fs.Seek(-$tailBytes,[IO.SeekOrigin]::End) }
      $sr = New-Object IO.StreamReader($fs)
      return $sr.ReadToEnd()
    } finally { $fs.Dispose() }
  } catch { return '' }
}

function Read-LockedFromOffset([string]$path,[int64]$offset){
  if(-not (Test-Path -LiteralPath $path)){ return [pscustomobject]@{Valid=$false;Text=''} }
  try{
    $fs=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{
      if($offset -lt 0 -or $fs.Length -lt $offset){ return [pscustomobject]@{Valid=$false;Text=''} }
      [void]$fs.Seek($offset,[IO.SeekOrigin]::Begin)
      $sr=New-Object IO.StreamReader($fs)
      return [pscustomobject]@{Valid=$true;Text=$sr.ReadToEnd()}
    } finally { $fs.Dispose() }
  } catch { return [pscustomobject]@{Valid=$false;Text=''} }
}

# S127 FIX. `Read-Locked` SEEKS FROM THE END, so every caller is a TAIL window and any
# "is this token present anywhere?" test silently becomes "is it present recently?".
# This bit TWICE on the same gate: S114 raised the capture window 200 KB -> 40 MB when logs were
# ~2 MB (i.e. "the whole file" in practice), and S127 hit it again at 79 MB -- the ONE early
# /core-game/matches fetch sat at byte 44,791 while the 40 MB window started at 39,042,477, so the
# gate could never pass and the stager aborted a perfectly good, already-parked client.
# ⇒ A SIZE-DEPENDENT CONSTANT IS THE DEFECT. This streams the whole file and cannot be outgrown.
function Test-FileContains([string]$path,[string]$needle){
  if(-not (Test-Path $path)){ return $false }
  try{
    $fs = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{
      $sr = New-Object IO.StreamReader($fs)
      while(($line = $sr.ReadLine()) -ne $null){ if($line.Contains($needle)){ return $true } }
      return $false
    } finally { $fs.Dispose() }
  } catch { return $false }
}

function Wait-For([string]$what,[int]$timeoutSec,[scriptblock]$test){
  $t0 = Get-Date
  while(((Get-Date) - $t0).TotalSeconds -lt $timeoutSec){
    if($BindOnly -and $script:identityBound){ Assert-S149FlightIdentity }
    if(& $test){
      if($BindOnly -and $script:identityBound){ Assert-S149FlightIdentity }
      Say "$what -> OK ($([int]((Get-Date)-$t0).TotalSeconds)s)"
      return $true
    }
    # ★ S112 LIVENESS GUARD. Every gate below polls a LOG or a MARKER, and a dead process writes
    #   neither -- so when the game dies mid-staging (measured: frequently, within ~1 s of the map
    #   load) the gate cannot tell "not yet" from "never again" and burns its whole timeout. Worse,
    #   `Stage-Inject` discards inject.exe's exit code, so an injection into an exited PID logs
    #   `FAILED: OpenProcess: The parameter is incorrect.` and the run sails on to wait 120 s for a
    #   marker line nothing is alive to write. Fail fast instead; the caller's abort paths are
    #   already correct, they were just being reached three minutes late.
    if($script:gamePid -and -not (Get-Process -Id $script:gamePid -ErrorAction SilentlyContinue)){
      Say "$what -> *** GAME PROCESS GONE after $([int]((Get-Date)-$t0).TotalSeconds)s -- aborting the wait ***"
      return $false
    }
    Start-Sleep -Seconds 3
  }
  Say "$what -> *** TIMEOUT after ${timeoutSec}s ***"
  return $false
}

$foDll = if($Fo){ (Resolve-Path $Fo).Path } else { Join-Path $shimDir 'tutorial_launch_fo.dll' }
foreach($p in @($inject,$foDll,
                (Join-Path $shimDir 'gft_ready_fix.dll'),
                (Join-Path $shimDir 'tutorial_launch_sp.dll'))){
  if(-not (Test-Path $p)){ throw "missing required file: $p" }
}
if(-not $SkipProbe){
  if(-not (Test-Path $Probe)){ throw "probe DLL not found: $Probe" }
  $Probe = (Resolve-Path $Probe).Path
}
if($BindOnly){
  $EvidenceDir=[IO.Path]::GetFullPath($EvidenceDir)
  $docs=$EvidenceDir
  if(-not (Test-Path -LiteralPath $EvidenceDir)){
    New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
  }
  if(-not (Test-Path -LiteralPath $ledgerDir)){
    New-Item -ItemType Directory -Path $ledgerDir -Force | Out-Null
  }
  if(-not (Test-Path -LiteralPath $watcherExe)){ throw "watcher executable missing: $watcherExe" }
  if(-not (Test-Path -LiteralPath $WatcherLogPath)){ throw "watcher log missing: $WatcherLogPath" }
  $watcherLogGeneration=Get-Item -LiteralPath $WatcherLogPath
  $script:watcherLogCreationUtcTicks=[int64]$watcherLogGeneration.CreationTimeUtc.Ticks
  if(-not (Test-Path -LiteralPath $ExpectedWatcherOutputDir)){
    throw "watcher output directory missing: $ExpectedWatcherOutputDir"
  }
  $evidenceCollisions=@(Get-ChildItem -LiteralPath $EvidenceDir -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Name.StartsWith("fk24-stage-$Label-",[StringComparison]::OrdinalIgnoreCase) })
  if($evidenceCollisions.Count -ne 0){
    throw "bind-mode evidence label already exists and is immutable: $Label"
  }
  if(-not (Test-Path -LiteralPath $BindOnly)){ throw "bind-only DLL not found: $BindOnly" }
  $BindOnly = (Resolve-Path $BindOnly).Path
  if($ExpectedBindOnlySha256 -notmatch '^[0-9A-Fa-f]{64}$'){
    throw '-ExpectedBindOnlySha256 must contain exactly 64 hex characters in bind mode'
  }
  $frozenS148 = 'C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E'
  if($ExpectedProbeSha256.ToUpperInvariant() -ne $frozenS148){
    throw "bind mode pins unchanged S148 Flight4 exactly: expected hash must be $frozenS148"
  }
  $bindActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $BindOnly).Hash
  $probeActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Probe).Hash
  if($bindActual -ne $ExpectedBindOnlySha256.ToUpperInvariant()){
    throw "bind-only artifact hash mismatch expected=$($ExpectedBindOnlySha256.ToUpperInvariant()) actual=$bindActual"
  }
  if($probeActual -ne $frozenS148){
    throw "unchanged S148 artifact hash mismatch expected=$frozenS148 actual=$probeActual"
  }
  $runtimePins = [ordered]@{
    $inject = '180D4EE1E87CB344F7BADA7D88EFD50B0EB251C5C23D75BB464229A6D57E571E'
    (Join-Path $shimDir 'gft_ready_fix.dll') = 'A8F2E1BC2EC67551461A685FF15A607245514B1C5BDB235335C8322DE12F0816'
    $foDll = 'CFB1B0B5EF37E910FBFE043184F6B72BF7F42C645FE6B841500190171FB7157B'
    (Join-Path $shimDir 'tutorial_launch_sp.dll') = 'A6C1BA97265662A3306C1A23BEF7BD74131716A6FE462D7A10FFEAAC00343DA7'
  }
  foreach($runtimePath in $runtimePins.Keys){
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runtimePath).Hash
    if($actualHash -ne $runtimePins[$runtimePath]){
      throw "S149 runtime-tool provenance mismatch path=$runtimePath expected=$($runtimePins[$runtimePath]) actual=$actualHash"
    }
  }
  $watcherActual=(Get-FileHash -Algorithm SHA256 -LiteralPath $watcherExe).Hash
  if($watcherActual -ne $expectedWatcherSha256){
    throw "S149 watcher provenance mismatch expected=$expectedWatcherSha256 actual=$watcherActual"
  }
  $backendExe=Join-Path $repo 'server\ags.exe'
  if(-not (Test-Path -LiteralPath $backendExe)){ throw "bound backend executable missing: $backendExe" }
  $script:backendSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $backendExe).Hash
  Assert-S149BackendIdentity
  $s149Contract = $script:verifiedS149ContractPath
  $s148Contract = $script:verifiedS148ContractPath
  Confirm-S149StagerContractPin -ContractPath $s149Contract `
      -ExpectedContractSha256 $ExpectedS149ContractSha256 `
      -ArtifactPath $BindOnly -ExpectedArtifactSha256 $bindActual
  & $script:verifiedPowerShellPath -NoProfile -ExecutionPolicy Bypass -File $s149Contract `
      -ArtifactPath $BindOnly -ExpectedArtifactSha256 $bindActual
  $s149ContractExit=$LASTEXITCODE
  Confirm-S149StagerContractPin -ContractPath $s149Contract `
      -ExpectedContractSha256 $ExpectedS149ContractSha256 `
      -ArtifactPath $BindOnly -ExpectedArtifactSha256 $bindActual
  if($s149ContractExit -ne 0){ throw "S149 artifact-only contract failed: exit $s149ContractExit" }
  Confirm-S149StagerContractPin -ContractPath $s148Contract `
      -ExpectedContractSha256 $ExpectedS148ContractSha256 `
      -ArtifactPath $Probe -ExpectedArtifactSha256 $probeActual
  & $script:verifiedPowerShellPath -NoProfile -ExecutionPolicy Bypass -File $s148Contract `
      -ArtifactPath $Probe -ExpectedArtifactSha256 $probeActual
  $s148ContractExit=$LASTEXITCODE
  Confirm-S149StagerContractPin -ContractPath $s148Contract `
      -ExpectedContractSha256 $ExpectedS148ContractSha256 `
      -ArtifactPath $Probe -ExpectedArtifactSha256 $probeActual
  if($s148ContractExit -ne 0){ throw "unchanged S148 artifact-only contract failed: exit $s148ContractExit" }
  Say "S149 artifact preflight green bindSHA256=$bindActual unchangedS148SHA256=$probeActual"
}

# ---- PRE-FLIGHT: the backend must actually be arming a match, or the client never parks and the
#      force-open reverts to the lobby in ~300 ms (the S63/S64 failure this whole route depends on
#      avoiding). Measure it rather than assuming the source flag was rebuilt into the binary.
Say 'pre-flight: is ags serving an armed match?'
$armed = $false
try{
  $me = (Invoke-WebRequest -Uri 'http://127.0.0.1:8080/revival/admin/state' -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue)
} catch { }
foreach($pid_ in @('9b9d2c887e2524f918e383a895f2f1c2')){
  try{
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/core-game/players/$pid_" -UseBasicParsing -TimeoutSec 5
    $j = $r.Content | ConvertFrom-Json
    Say ("  /core-game/players -> MatchID='{0}' Version={1}" -f $j.MatchID,$j.Version)
    if($j.MatchID){ $armed = $true }
  } catch { Say "  /core-game/players query failed: $($_.Exception.Message)" }
}
if(-not $armed){
  throw "ags is NOT arming a match (MatchID empty). Set forceTutorialMatch=true in server/internal/interactive/interactive.go, rebuild ags, restart it. Without this the client never parks and force-open reverts."
}

# ---- 1. the game process
Say 'waiting for game process...'
$proc = $null
if($BindOnly){
  if(-not (Wait-For 'exactly one game process' $WaitProcSec {
    $candidates = @(Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)
    if($candidates.Count -eq 1){ $script:proc = $candidates[0]; return $true }
    return $false
  })){ exit 2 }
} else {
  if(-not (Wait-For 'game process' $WaitProcSec { $script:proc = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue | Select-Object -First 1; $null -ne $script:proc })){ exit 2 }
}
$script:gamePid = $proc.Id
$gamePid = $script:gamePid
$start   = $proc.StartTime
$script:gameStartTicks = [int64]$start.ToUniversalTime().Ticks
$script:gamePath = ''
if($BindOnly){
  try { $script:gamePath = [string]$proc.Path } catch { }
  if([string]::IsNullOrWhiteSpace($script:gamePath)){
    Say 'S149 PROCESS IDENTITY REFUSED: PROCESS_PATH_UNREADABLE'
    exit 6
  }
}
$script:identityBound = [bool]$BindOnly
Assert-S149FlightIdentity
Say "game PID=$gamePid started=$start"
if($BindOnly){
  $ledgerPath = Join-Path $ledgerDir ("s149-s148-arm-{0}-{1}.json" -f $gamePid,$script:gameStartTicks)
  $ledgerAdmission=Get-S149LedgerAdmissionResult -LedgerExists (Test-Path -LiteralPath $ledgerPath)
  if(-not $ledgerAdmission.Valid){
    Say "S149 PRE-MAP LEDGER REFUSED reason=$($ledgerAdmission.Reason) path=$ledgerPath; no DLL was mapped"
    exit 9
  }
}

# ---- 2. the PARKED state. Three independent signals, all required:
#         (a) the UI is up          -> Loki.log 'TryUIReady SUCCESS'
#         (b) the match was fetched -> capture.log GET /core-game/matches AFTER this process started
#         (c) enough uptime for login+lobby to settle
$parked = Wait-For 'parked match model (uiready + match fetched + uptime)' $WaitParkedSec {
  $up = ((Get-Date) - $start).TotalSeconds
  if($up -lt $MinUptimeSec){ return $false }
  if($BindOnly){
    if(-not (Test-Path -LiteralPath $lokiLog) -or -not (Test-Path -LiteralPath $capture)){
      return $false
    }
    $nowUtc=[datetime]::UtcNow
    $lokiText=Read-Locked $lokiLog ([int]::MaxValue)
    $lokiGate=Get-S149LokiEvidenceResult -Text $lokiText -Needle 'TryUIReady SUCCESS' `
        -NotBeforeUtc $start.ToUniversalTime() -NowUtc $nowUtc
    if(-not $lokiGate.Valid){ return $false }

    $captureItem=Get-Item -LiteralPath $capture -ErrorAction SilentlyContinue
    if($null -eq $captureItem){ return $false }
    $captureText=Read-Locked $capture ([int]::MaxValue)
    $backendStartUtc=[datetime]::new($ExpectedBackendStartTicks,[DateTimeKind]::Utc)
    $localOffsetMinutes=[int]([TimeZoneInfo]::Local.GetUtcOffset($start).TotalMinutes)
    $captureGate=Get-S149CaptureEvidenceResult -Text $captureText `
        -Needle 'core-game/matches' -CaptureCreationUtc $captureItem.CreationTimeUtc `
        -BackendStartUtc $backendStartUtc -NotBeforeUtc $start.ToUniversalTime() `
        -NowUtc $nowUtc -LocalUtcOffsetMinutes $localOffsetMinutes
    if(-not $captureGate.Valid){ return $false }
  } else {
    if(-not (Test-FileContains $lokiLog 'TryUIReady SUCCESS')){ return $false }
    if((Test-Path $capture) -and -not (Test-FileContains $capture 'core-game/matches')){ return $false }
  }
  return $true
}
if(-not $parked){ Say 'proceeding anyway is NOT safe -- aborting'; exit 3 }
Say ("uptime={0}s" -f [int](((Get-Date) - $start).TotalSeconds))

# ★ MINIMUM INJECTION GAP (S109, 2026-08-05). Injecting DLLs in quick succession is what provokes
#   the protector's `runtime.dll+1` / `+0x205D` kills. MEASURED on the menu route: a 3 s gap between
#   manual-maps gave 1 death per 43 s; >=10 s gaps gave 1 per 3,054 s -- a 71x reduction, P = 8.6e-5.
#   docs/s109-dump-forensics.md sections 18-20.
#
#   This stager was NOT a uniform burst, so it needed measuring rather than assuming. Real spacing:
#       gft -> fo     ~5 s   (Stage-Inject's Sleep 2 + the Sleep 3 below)  <-- LETHAL REGIME
#       fo  -> sp     19 s   (19/19/19/19/19 across five S108 runs)        <-- already safe
#       sp  -> probe  7-17 s (17/15/17/7)                                  <-- borderline
#   ⚠ Do NOT try to re-derive those from docs/fk24-stage-*-N-*.txt mtimes: Copy-Item preserves the
#   SOURCE file's LastWriteTime, and step 1 copies a stale tutorial-launch-marker that gft never
#   writes -- which is why that delta reads as +210 s or even +41,742 s. Steps 2-4 are real.
#
#   We enforce a MINIMUM gap measured from the previous injection, so the existing evidence gates
#   (world-load, [SP] done) COUNT TOWARD IT and we only sleep the remainder. That buys the safe
#   spacing for ~15-30 s of added staging rather than ~50 s of unconditional sleeps -- which matters,
#   because the code-integrity kill lands ~285 s in and every second spent staging is armed-window
#   budget spent. The evidence gates themselves are untouched; they are load-bearing (see below).
$script:lastInjectAt = $null
$script:lastInjectStamp = $null
$script:stageMarkerSnapshots = @{}
$script:lastMarkerSnapshots = @{}
$script:acceptedMarkerSnapshots = @{}
function Stage-Inject([string]$dll,[int]$n,[string]$tag,[string]$ExpectedSha256='',
                      [scriptblock]$BeforeMap=$null){
  if(($BindOnly -and $null -ne $script:lastInjectStamp) -or
     (-not $BindOnly -and $null -ne $script:lastInjectAt)){
    if($BindOnly){
      for(;;){
        Assert-S149FlightIdentity
        $nowStamp=[Diagnostics.Stopwatch]::GetTimestamp()
        $needMs=Get-S149RemainingGapMilliseconds -LastTimestamp $script:lastInjectStamp `
            -NowTimestamp $nowStamp -Frequency ([Diagnostics.Stopwatch]::Frequency) `
            -MinimumSeconds $InjectGapSeconds
        if($needMs -le 0){ break }
        Say ("    precise spacing: waiting {0} ms more (minimum {1}s)" -f $needMs,$InjectGapSeconds)
        Start-Sleep -Milliseconds $needMs
      }
      $elapsedMs=[Math]::Floor((([Diagnostics.Stopwatch]::GetTimestamp()-$script:lastInjectStamp)*1000.0)/
          [Diagnostics.Stopwatch]::Frequency)
      Say ("    precise spacing satisfied: {0} ms since prior verified map" -f $elapsedMs)
    } else {
      $since = [int]((Get-Date) - $script:lastInjectAt).TotalSeconds
      $need  = $InjectGapSeconds - $since
      if($need -gt 0){ Say ("    spacing: {0}s since last inject, waiting {1}s more (min gap {2}s)" -f $since,$need,$InjectGapSeconds); Start-Sleep -Seconds $need }
      else           { Say ("    spacing: {0}s since last inject, min gap {1}s already satisfied" -f $since,$InjectGapSeconds) }
    }
  }
  Assert-S149FlightIdentity
  Assert-Fresh $dll
  if($BindOnly){
    if($ExpectedSha256 -notmatch '^[0-9A-Fa-f]{64}$'){
      Say "map boundary REFUSED tag=$tag missing exact artifact hash"
      exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
    }
    foreach($pin in @(@($inject,$runtimePins[$inject]),@($dll,$ExpectedSha256.ToUpperInvariant()))){
      $pathReceipt=Assert-S149MapPathProvenance -Path $pin[0] -ExpectedSha256 $pin[1]
      $actualHash=$pathReceipt.Sha256
      if($actualHash -ne $pin[1]){
        Say "map boundary provenance REFUSED tag=$tag path=$($pin[0]) expected=$($pin[1]) actual=$actualHash"
        exit (Get-S149IdentityFailureExitCode -S148Attempted ([bool]$script:s148Attempted))
      }
    }
    if($null -ne $BeforeMap){ & $BeforeMap }
    # The callback may durably cross the one-arm boundary. Revalidate both target identity and exact
    # bytes after it, immediately before mmap, so PID reuse or file replacement cannot hide in I/O.
    Assert-S149FlightIdentity
    $markerBefore=Get-S149MarkerSnapshot
  }
  Say ">>> inject $tag"
  if($BindOnly){
    $lockedArtifacts=New-Object 'Collections.Generic.List[object]'
    $mapExit=-1; $mapLines=@(); $mapVerified=$false
    try{
      # Open the exact injector and DLL once with FileShare.Read. These handles allow the
      # child to read both files but deny every write/delete/rename until mmap returns.
      foreach($pin in @(@($inject,$runtimePins[$inject]),@($dll,$ExpectedSha256.ToUpperInvariant()))){
        [void](Assert-S149MapPathProvenance -Path $pin[0] -ExpectedSha256 $pin[1])
        $locked=Open-S149LockedArtifact -Path $pin[0]
        $lockedArtifacts.Add($locked)
        if($locked.Sha256 -ne $pin[1]){
          throw "final map boundary provenance REFUSED tag=$tag path=$($pin[0]) expected=$($pin[1]) actual=$($locked.Sha256)"
        }
      }
      $mapNotBeforeUtcTicks=[datetime]::UtcNow.Ticks
      $script:stageMarkerSnapshots[$n]=[pscustomobject]@{
        BeforeExists=[bool]$markerBefore.BeforeExists
        BeforeSha256=[string]$markerBefore.BeforeSha256
        MapNotBeforeUtcTicks=[int64]$mapNotBeforeUtcTicks
      }
      # All backend/watcher/provenance/snapshot work is complete. This exact target-only
      # PID/start/name/path assertion and the held-byte path checks form one final boundary.
      Assert-S149TargetMapIdentity
      foreach($locked in $lockedArtifacts){
        [void](Assert-S149MapPathProvenance -Path $locked.Path -ExpectedSha256 $locked.Sha256)
      }
      $mapLines = @(& $inject mmap $gamePid $dll 2>&1)
      $mapExit = $LASTEXITCODE
      $mapText = $mapLines -join [Environment]::NewLine
      $mapVerified = $mapExit -eq 0 -and
          $mapText.Contains('DllMain remote-thread exit: 0x1') -and
          $mapText.Contains('verify: MZ at ') -and
          $mapText.Contains('OK: manual-map complete (DllMain returned).')
      if($mapVerified){
        Assert-S149FlightIdentity
        for($lockIndex=0; $lockIndex -lt $lockedArtifacts.Count; $lockIndex++){
          $postMapHash=Get-S149StreamSha256 -Stream $lockedArtifacts[$lockIndex].Stream
          if($postMapHash -ne $lockedArtifacts[$lockIndex].Sha256){
            throw "held artifact stream hash changed after mmap path=$($lockedArtifacts[$lockIndex].Path)"
          }
        }
      }
    } catch {
      $mapExit=-1; $mapLines=@($_.Exception.Message)
      $mapVerified=$false
    } finally {
      foreach($locked in $lockedArtifacts){ $locked.Stream.Dispose() }
    }
    $mapLines | ForEach-Object { Say "    $_" }
    if(-not $mapVerified){
      $exitCode = if($script:s148Attempted){ 10 } else { 7 }
      Say "manual-map receipt REFUSED tag=$tag exit=$mapExit; no retry is permitted (exit $exitCode)"
      exit $exitCode
    }
    $script:lastInjectStamp=[Diagnostics.Stopwatch]::GetTimestamp()
  } else {
    & $inject mmap $gamePid $dll 2>&1 | ForEach-Object { Say "    $_" }
    $script:lastInjectAt = Get-Date
  }
  Start-Sleep -Seconds 2
  Assert-S149FlightIdentity
  if($BindOnly){
    $markerGeneration=Get-S149StageMarkerGeneration $n
    if($markerGeneration.Valid){
      $dst=Join-Path $docs ("fk24-stage-{0}-{1}.txt" -f $Label,("{0}-{1}" -f $n,$tag))
      [void](Write-S149ImmutableSnapshot -Snapshot $markerGeneration -Destination $dst)
      Say "    marker -> $(Split-Path -Leaf $dst)"
    }
  } else {
    $dst = Join-Path $docs ("fk24-stage-{0}-{1}-{2}.txt" -f $Label,$n,$tag)
    if(Test-Path $marker){ Copy-Item $marker $dst -Force; Say "    marker -> $(Split-Path -Leaf $dst)" }
  }
}

# ---- 3. gft_ready_fix FIRST, then force-open, then WAIT for the world before the one-shot spawn+possess.
#
# ★ S108 ORDER CORRECTION (MEASURED 2026-08-04, run wp2r1). The documented recipe is fo -> gft -> sp,
#   and S107 got away with it only because it injected all four back to back, so gft landed DURING the
#   5.7 s LoadMap and was resident before the tutorial GameState came up. This script originally
#   inserted a world-gate between fo and gft -- which delayed gft past LoadMap, and the run died ~60 ms
#   after "LogLokiGameMode: Display: Client is ready to play", with the log full of
#   "ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready" and NO UE crash dump
#   (Sentry's crashpad took the process, so it is invisible to the dump census -- FK-25 class).
#   gft_ready_fix re-applies its bit every ~2 s for the whole session and needs no world, so injecting
#   it BEFORE the force-open removes the race entirely rather than merely winning it by luck.
$gftDll=Join-Path $shimDir 'gft_ready_fix.dll'
$spDll=Join-Path $shimDir 'tutorial_launch_sp.dll'
Stage-Inject $gftDll 1 'gft' $(if($BindOnly){$runtimePins[$gftDll]}else{''})
Start-Sleep -Seconds 3
Say ("force-open DLL: {0}" -f (Split-Path -Leaf $foDll))
if($BindOnly){
  Stage-Inject $foDll 2 'fo' $runtimePins[$foDll] {
    Assert-S149FlightIdentity
    if(-not (Test-Path -LiteralPath $lokiLog)){ exit 6 }
    $script:foLogOffset=[int64](Get-Item -LiteralPath $lokiLog).Length
    $script:foNotBeforeUtc=[datetime]::UtcNow
  }
} else { Stage-Inject $foDll 2 'fo' }

# ★ Gate on the LOAD COMPLETING, not on the string 'LVL_Tutorial' -- the force-open's own console
#   command ('open LVL_Tutorial?game=...') contains that substring and is echoed to the log, so the
#   old test passed 3 s in, before the map had loaded at all. Question the key you grepped for.
$worldUp = Wait-For 'LVL_Tutorial load complete' $WaitWorldSec {
  if($BindOnly){
    $slice=Read-LockedFromOffset $lokiLog $script:foLogOffset
    if(-not $slice.Valid){ return $false }
    $loadGate=Get-S149LokiEvidenceResult -Text $slice.Text `
        -Needle 'Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial' `
        -NotBeforeUtc $script:foNotBeforeUtc -NowUtc ([datetime]::UtcNow)
    return $loadGate.Valid
  }
  $log=Read-Locked $lokiLog
  return $log -match 'Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial'
}
if(-not $worldUp){ Say 'no tutorial world -> injecting sp now would be a wasted one-shot. ABORTING.'; exit 4 }
Start-Sleep -Seconds 8   # let the gamemode finish init before the one-shot resolve

Stage-Inject $spDll 3 'sp' $(if($BindOnly){$runtimePins[$spDll]}else{''})

# ---- 4. the DLL under test.
#
# ★ S108 GATE (MEASURED 2026-08-04, run wp2r2). A fixed 5 s wait after `sp` is NOT enough: the probe
#   went in while spawn+possess was still running, RM_PLAY found no possessed hero, printed
#   "[PL] ResolveWakeMove failed (no possessed hero -- spawn+possess first) -> abort" and aborted
#   WITHOUT arming. RM_PLAY's resolve is one-shot, so that silently wasted the launch. Gate on sp's own
#   completion line instead. Read the marker BEFORE injecting -- the injection truncates it (FK-25).
if(-not $SkipProbe){
  $spDone = Wait-For '[SP] done step=4 (hero possessed)' 120 {
    if(-not (Test-Path $marker)){ return $false }
    if($BindOnly){
      $spGeneration=Get-S149StageMarkerGeneration 3
      if(-not $spGeneration.Valid){ return $false }
      $mk = $spGeneration.Text
    } else {
      $mk = Read-Locked $marker 200000
    }
    $spReady=($mk -match '\[SP\]\s+done step=4') -and ($mk -match 'spawnedPawn=0x[0-9A-Fa-f]+')
    if($spReady -and $BindOnly){ $script:acceptedMarkerSnapshots[3]=$spGeneration }
    return $spReady
  }
  if(-not $spDone){ Say 'spawn+possess never completed -> RM_PLAY would abort. ABORTING.'; exit 5 }
  if($BindOnly){
    Save-S149StageMarkerOrExit '3-sp-ready' 6 $script:acceptedMarkerSnapshots[3]
    Assert-S149FlightIdentity
    Stage-Inject $BindOnly 4 ('bind-' + [IO.Path]::GetFileNameWithoutExtension($BindOnly)) `
        $ExpectedBindOnlySha256.ToUpperInvariant()

    $script:bindGate = $null
    $bindObserved = Wait-For 'S149 bind terminal receipt' $WaitBindReadySec {
      if(-not (Test-Path $marker)){ return $false }
      $bindGeneration=Get-S149StageMarkerGeneration 4
      if(-not $bindGeneration.Valid){ return $false }
      $text = $bindGeneration.Text
      $gate = Get-S149BindGateResult -Text $text -ExpectedPid ([uint32]$gamePid)
      if($gate.Ready){
        $script:bindGate = $gate
        $script:acceptedMarkerSnapshots[4]=$bindGeneration
        return $true
      }
      if(Test-S149BindTerminalReceiptPresent -Text $text){
        $script:bindGate = $gate
        if($gate.Reason -eq 'WORKER_COUNT'){ return $false }
        return $true
      }
      return $false
    }
    if(-not $bindObserved){
      Say 'S149 bind terminal timed out; unchanged S148 was NOT attempted and must not be armed manually.'
      exit 8
    }
    if($null -eq $script:bindGate -or -not $script:bindGate.Ready){
      $why = if($script:bindGate){ $script:bindGate.Reason } else { 'NO_GATE_RESULT' }
      Say "S149 bind REFUSED reason=$why; unchanged S148 was NOT attempted."
      exit 8
    }
    Save-S149StageMarkerOrExit '4-bind-ready' 8 $script:acceptedMarkerSnapshots[4]
    Say "S149 exact bind gate READY run=$($script:bindGate.Run); S148 remains unarmed"

    Stage-Inject $Probe 5 ('s148-' + [IO.Path]::GetFileNameWithoutExtension($Probe)) `
        $ExpectedProbeSha256.ToUpperInvariant() {
      # This callback runs after the precise spacing wait and final identity/freshness checks, at the
      # last host-controlled boundary before inject.exe. CreateNew makes an interruption or unknown
      # native result conservative: the ledger survives and forbids a second map for this PID/start.
      Assert-S149FlightIdentity
      $bindRehash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BindOnly).Hash
      $probeRehash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Probe).Hash
      if($bindRehash -ne $ExpectedBindOnlySha256.ToUpperInvariant() -or
         $probeRehash -ne $ExpectedProbeSha256.ToUpperInvariant()){
        Say "artifact provenance changed at final pre-map boundary; S148 NOT attempted bind=$bindRehash probe=$probeRehash"
        exit 8
      }
      $ledger = New-S149AttemptLedger -Path $ledgerPath -GamePid ([uint32]$gamePid) `
          -StartTicks ([int64]$script:gameStartTicks) -S148Sha256 $probeRehash `
          -OnCreateNew { $script:s148Attempted = $true }
      if(-not $ledger.Created){
        Say "S148 one-arm ledger REFUSED reason=$($ledger.Reason) path=$ledgerPath"
        exit 9
      }
      Say "S148 one-arm ledger durably created at final pre-map boundary: $ledgerPath"
    }
    Say 'unchanged S148 injected exactly once; ledger remains authoritative on every outcome'

    $script:s148Terminal = $null
    $s148Observed = Wait-For 'one complete S148 terminal generation' $WaitS148TerminalSec {
      if(-not (Test-Path $marker)){ return $false }
      $s148Generation=Get-S149StageMarkerGeneration 5
      if(-not $s148Generation.Valid){ return $false }
      $text = $s148Generation.Text
      $terminal = Get-S148TerminalGateResult -Text $text -HostGenerationValid $true
      if($terminal.Complete){
        $script:s148Terminal = $terminal
        $script:acceptedMarkerSnapshots[5]=$s148Generation
        return $true
      }
      return $false
    }
    if(-not $s148Observed){
      Save-S149StageMarkerOrExit '5-s148-timeout' 11 $script:lastMarkerSnapshots[5]
      Say 'S148 terminal/cleanup timed out or process ended; ledger remains and a second arm is forbidden.'
      exit 11
    }
    Save-S149StageMarkerOrExit '5-s148-terminal' 11 $script:acceptedMarkerSnapshots[5]
    Say "stage complete: one S148 terminal outcome=$($script:s148Terminal.Outcome); no retry branch exists"
    exit 0
  } else {
    Start-Sleep -Seconds 3
    Stage-Inject $Probe 4 ('probe-' + [IO.Path]::GetFileNameWithoutExtension($Probe))
    Say 'probe injected; armed window begins'
  }
} else {
  Say 'SkipProbe: world staged, nothing further injected'
}
Say 'stage complete'
