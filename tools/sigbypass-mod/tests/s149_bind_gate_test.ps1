$ErrorActionPreference = 'Stop'

$gateModule = Join-Path $PSScriptRoot '..\..\..\configs\s149-bind-gate.ps1'
. $gateModule

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$valid = @'
[BF] ===== RM_BOTFIGHT: minimum bot-fight loop (roadmap-s142) =====
[S149] BIND_ONLY pid=4242 run=0123456789ABCDEF arms=0x02 forbidden=0xFD naturalInput=0 selfCal=0 ownerMode=0
[BF] ---- K_BIND: WireAbilitySystem + InitAbilityActorInfo (the S111 never-run bind) ----
[S149] CALL_ISSUED pid=4242 run=0123456789ABCDEF callCount=1 asc=0x9999AAAABBBBCCCC owner=0xDDDDEEEEFFFF0001 avatar=0x5555666677778888 persistentSetup=yes
[BF] post census: botOrAIControllers 0 -> 0 ; heroCharacters 1 -> 1
[S149] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=10 of 10 swapped (scan 1 ms, 10 UFunctions live)
[S149] callbacks SEALED; delayed prefetched thunk roots are no-dispatch
[S149] CLEANUP restoreCountExact=1 repairScanComplete=1 verifyScanComplete=1 callbacksSealed=1 cleanupFaulted=0 postRestoreQuiesced=1 swapped=10 restored=10 residualRepaired=0 residualRemaining=0 postRestoreEntries=0 entryPendingRemaining=0 parkedRemaining=0 activeRemaining=0 mutationRootsRemaining=0
[S149] terminal witness collected after sealed callback drain
[S149] POST_BIND pid=4242 run=0123456789ABCDEF callCount=1 setupFaulted=0 initFaulted=0 terminalRevalidated=1 localAuthorityStable=1 pcLive=1 possessedHeroStable=1 heroLive=1 ascLive=1 ascStorageResolved=1 ascStorageReadable=1 ascStable=1 avatarPropertyResolved=1 avatarSlotReadable=1 avatarLive=1 avatarMatchesHero=1 pc=0x1111222233334444 hero=0x5555666677778888 asc=0x9999AAAABBBBCCCC avatar=0x5555666677778888
[S149] POST_BIND_OWNER pid=4242 run=0123456789ABCDEF ownerPropertyResolved=1 ownerSlotReadable=1 ownerLive=1 ownerMatchesCarrier=1 carrierPropertyResolved=1 carrierSlotReadable=1 carrierLive=1 carrierStable=1 carrierAscPropertyResolved=1 carrierAscSlotReadable=1 carrierAscStable=1 carrier=0xDDDDEEEEFFFF0001 owner=0xDDDDEEEEFFFF0001
[S149] RESULT pid=4242 run=0123456789ABCDEF outcome=BIND_READY issues=0x00000000 funcsRestoreVerified=yes postRestoreQuiesced=yes residualRemaining=0 postRestoreEntries=0
[BF] worker done (hits=1 hitsGT=1)
'@

$result = Get-S149BindGateResult -Text $valid -ExpectedPid 4242
Assert-True $result.Ready "an exact single current-process bind witness must open the gate: $($result.Reason)"
Assert-True ($result.Run -eq '0123456789ABCDEF') 'the accepted gate must return the exact run identity'

$wrongPid = Get-S149BindGateResult -Text $valid -ExpectedPid 4243
Assert-True (-not $wrongPid.Ready -and $wrongPid.Reason -eq 'PID_MISMATCH') `
    'a marker from another process must refuse'

$broad = $valid.Replace('arms=0x02 forbidden=0xFD', 'arms=0x03 forbidden=0xFC')
$broadResult = Get-S149BindGateResult -Text $broad -ExpectedPid 4242
Assert-True (-not $broadResult.Ready -and $broadResult.Reason -eq 'POLICY_MISMATCH') `
    'the legacy spawn+bind policy must not pass as bind-only'

$faultLied = $valid.Replace('initFaulted=0', 'initFaulted=1')
$faultResult = Get-S149BindGateResult -Text $faultLied -ExpectedPid 4242
Assert-True (-not $faultResult.Ready -and $faultResult.Reason -eq 'WITNESS_MISMATCH') `
    'a READY line cannot override a faulting witness'

$authorityDrift = $valid.Replace('localAuthorityStable=1', 'localAuthorityStable=0')
$authorityResult = Get-S149BindGateResult -Text $authorityDrift -ExpectedPid 4242
Assert-True (-not $authorityResult.Ready -and $authorityResult.Reason -eq 'WITNESS_MISMATCH') `
    'a stale unique-local-owner or LocalPlayer membership proof must keep the gate closed'

$staleTerminalWitness = $valid.Replace('terminalRevalidated=1', 'terminalRevalidated=0')
$staleTerminalResult = Get-S149BindGateResult -Text $staleTerminalWitness -ExpectedPid 4242
Assert-True (-not $staleTerminalResult.Ready -and $staleTerminalResult.Reason -eq 'WITNESS_MISMATCH') `
    'a pre-drain or otherwise stale witness must never open the gate'

$noCall = $valid.Replace('callCount=1', 'callCount=0')
$noCallResult = Get-S149BindGateResult -Text $noCall -ExpectedPid 4242
Assert-True (-not $noCallResult.Ready -and $noCallResult.Reason -eq 'WITNESS_MISMATCH') `
    'a pre-existing bound state without the one intended call must not pass'

$driftedAvatar = $valid.Replace('avatar=0x5555666677778888', 'avatar=0xAAAAAAAAAAAAAAAA')
$driftResult = Get-S149BindGateResult -Text $driftedAvatar -ExpectedPid 4242
Assert-True (-not $driftResult.Ready -and $driftResult.Reason -eq 'IDENTITY_MISMATCH') `
    'the gate must independently compare AvatarActor with the possessed hero identity'

$driftedOwner = $valid.Replace('owner=0xDDDDEEEEFFFF0001', 'owner=0xAAAAAAAAAAAAAAAA')
$ownerResult = Get-S149BindGateResult -Text $driftedOwner -ExpectedPid 4242
Assert-True (-not $ownerResult.Ready -and $ownerResult.Reason -eq 'OWNER_IDENTITY_MISMATCH') `
    'the gate must independently compare OwnerActor with the exact call carrier'

$carrierDrift = $valid.Replace('carrierAscStable=1', 'carrierAscStable=0')
$carrierDriftResult = Get-S149BindGateResult -Text $carrierDrift -ExpectedPid 4242
Assert-True (-not $carrierDriftResult.Ready -and $carrierDriftResult.Reason -eq 'OWNER_WITNESS_MISMATCH') `
    'the fresh carrier ASC relation must remain exact after callback drain'

$duplicate = Get-S149BindGateResult -Text ($valid + $valid) -ExpectedPid 4242
Assert-True (-not $duplicate.Ready -and $duplicate.Reason -eq 'POLICY_COUNT') `
    'duplicate/stale terminal transcripts must not pass'

$duplicateCall = Get-S149BindGateResult -Text ($valid.Replace(
    '[S149] POST_BIND pid=',
    '[S149] CALL_ISSUED pid=4242 run=0123456789ABCDEF callCount=1 asc=0x9999AAAABBBBCCCC owner=0xDDDDEEEEFFFF0001 avatar=0x5555666677778888 persistentSetup=yes' + "`n" +
    '[S149] POST_BIND pid=')) -ExpectedPid 4242
Assert-True (-not $duplicateCall.Ready -and $duplicateCall.Reason -eq 'CALL_COUNT') `
    'more than one native-call receipt must keep the S148 gate closed'

$missingCleanup = Get-S149BindGateResult -Text ($valid.Replace(
    '[S149] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate' + "`n" +
    '[FS] disarm: restored=10 of 10 swapped (scan 1 ms, 10 UFunctions live)' + "`n" +
    '[S149] callbacks SEALED; delayed prefetched thunk roots are no-dispatch' + "`n" +
    '[S149] CLEANUP restoreCountExact=1 repairScanComplete=1 verifyScanComplete=1 callbacksSealed=1 cleanupFaulted=0 postRestoreQuiesced=1 swapped=10 restored=10 residualRepaired=0 residualRemaining=0 postRestoreEntries=0 entryPendingRemaining=0 parkedRemaining=0 activeRemaining=0 mutationRootsRemaining=0' + "`n", '')) `
    -ExpectedPid 4242
Assert-True (-not $missingCleanup.Ready -and $missingCleanup.Reason -eq 'DRAIN_COUNT') `
    'a claimed READY result without independently observed drain/disarm evidence must refuse'

$earlyResultLine = '[S149] RESULT pid=4242 run=0123456789ABCDEF outcome=BIND_READY issues=0x00000000 funcsRestoreVerified=yes postRestoreQuiesced=yes residualRemaining=0 postRestoreEntries=0'
$reordered = $valid.Replace($earlyResultLine + "`n", '').Replace(
    '[S149] CALL_ISSUED pid=', $earlyResultLine + "`n" + '[S149] CALL_ISSUED pid=')
$reorderedResult = Get-S149BindGateResult -Text $reordered -ExpectedPid 4242
Assert-True (-not $reorderedResult.Ready -and $reorderedResult.Reason -eq 'ORDER_MISMATCH') `
    'the terminal result must follow the call, witnesses, callback drain, and Func restoration'

$refused = $valid.Replace('outcome=BIND_READY issues=0x00000000',
                          'outcome=BIND_REFUSED issues=0x00000800')
$refusedResult = Get-S149BindGateResult -Text $refused -ExpectedPid 4242
Assert-True (-not $refusedResult.Ready -and $refusedResult.Reason -eq 'OUTCOME_REFUSED') `
    'an explicit bind refusal must keep the S148 gate closed'

$zeroRestore = $valid.Replace(
    '[FS] disarm: restored=10 of 10 swapped (scan 1 ms, 10 UFunctions live)',
    "[FS] disarm: restored=0 of 10 swapped (scan 1 ms, 10 UFunctions live)  (the shortfall is objects GC'd during the hold -- expected)")
$zeroRestoreResult = Get-S149BindGateResult -Text $zeroRestore -ExpectedPid 4242
Assert-True (-not $zeroRestoreResult.Ready -and $zeroRestoreResult.Reason -eq 'DISARM_MISMATCH') `
    'restored=0 of N must never pass via the generic expected-GC suffix'

$residualCleanup = $valid.Replace(
    'restoreCountExact=1 repairScanComplete=1 verifyScanComplete=1 callbacksSealed=1 cleanupFaulted=0 postRestoreQuiesced=1 swapped=10 restored=10 residualRepaired=0 residualRemaining=0 postRestoreEntries=0 entryPendingRemaining=0 parkedRemaining=0 activeRemaining=0 mutationRootsRemaining=0',
    'restoreCountExact=1 repairScanComplete=1 verifyScanComplete=1 callbacksSealed=1 cleanupFaulted=0 postRestoreQuiesced=1 swapped=10 restored=10 residualRepaired=0 residualRemaining=1 postRestoreEntries=0 entryPendingRemaining=0 parkedRemaining=0 activeRemaining=0 mutationRootsRemaining=0')
$residualCleanup = $residualCleanup.Replace(
    'funcsRestoreVerified=yes postRestoreQuiesced=yes residualRemaining=0 postRestoreEntries=0',
    'funcsRestoreVerified=NO postRestoreQuiesced=yes residualRemaining=1 postRestoreEntries=0')
$residualResult = Get-S149BindGateResult -Text $residualCleanup -ExpectedPid 4242
Assert-True (-not $residualResult.Ready -and $residualResult.Reason -eq 'CLEANUP_MISMATCH') `
    'a BIND_READY claim cannot override a complete scan that found a residual FsThunk pointer'

$notQuiesced = $valid.Replace(
    'callbacksSealed=1 cleanupFaulted=0 postRestoreQuiesced=1 swapped=10 restored=10 residualRepaired=0 residualRemaining=0 postRestoreEntries=0 entryPendingRemaining=0 parkedRemaining=0 activeRemaining=0 mutationRootsRemaining=0',
    'callbacksSealed=1 cleanupFaulted=0 postRestoreQuiesced=0 swapped=10 restored=10 residualRepaired=0 residualRemaining=0 postRestoreEntries=1 entryPendingRemaining=1 parkedRemaining=1 activeRemaining=0 mutationRootsRemaining=1')
$notQuiesced = $notQuiesced.Replace(
    'funcsRestoreVerified=yes postRestoreQuiesced=yes residualRemaining=0 postRestoreEntries=0',
    'funcsRestoreVerified=yes postRestoreQuiesced=NO residualRemaining=0 postRestoreEntries=1')
$notQuiescedResult = Get-S149BindGateResult -Text $notQuiesced -ExpectedPid 4242
Assert-True (-not $notQuiescedResult.Ready -and $notQuiescedResult.Reason -eq 'CLEANUP_MISMATCH') `
    'parked callback roots must be released and quiescent before terminal readiness'

$notSealed = $valid.Replace('callbacksSealed=1 cleanupFaulted=0',
                            'callbacksSealed=0 cleanupFaulted=0')
$notSealedResult = Get-S149BindGateResult -Text $notSealed -ExpectedPid 4242
Assert-True (-not $notSealedResult.Ready -and $notSealedResult.Reason -eq 'CLEANUP_MISMATCH') `
    'a quiet pass-through phase cannot substitute for the irreversible no-dispatch seal'

$cleanupFault = $valid.Replace('callbacksSealed=1 cleanupFaulted=0',
                               'callbacksSealed=1 cleanupFaulted=1')
$cleanupFaultResult = Get-S149BindGateResult -Text $cleanupFault -ExpectedPid 4242
Assert-True (-not $cleanupFaultResult.Ready -and $cleanupFaultResult.Reason -eq 'CLEANUP_MISMATCH') `
    'an SEH-contained cleanup fault must remain a terminal refusal'

Assert-True (-not (Test-S149BindTerminalReceiptPresent -Text '[S149] RESULT ')) `
    'a partially written result prefix must remain transient rather than aborting the flight'
Assert-True (Test-S149BindTerminalReceiptPresent -Text $valid) `
    'one complete exact result line must be recognized as terminal'

$oversizedPid = $valid.Replace('pid=4242', 'pid=999999999999999999999999999999')
$oversizedPidResult = Get-S149BindGateResult -Text $oversizedPid -ExpectedPid 4242
Assert-True (-not $oversizedPidResult.Ready) `
    'oversized numeric fields must produce a controlled refusal rather than a throwing conversion'

$forbidden = $valid + "`n[BF] ---- K_SPAWN: SpawnClassBotAtLoc ----`n"
$forbiddenResult = Get-S149BindGateResult -Text $forbidden -ExpectedPid 4242
Assert-True (-not $forbiddenResult.Ready -and $forbiddenResult.Reason -eq 'FORBIDDEN_ARM') `
    'evidence that any non-bind arm ran must keep the gate closed'

$crossPhase = $valid + "`n[S148] CALL_ISSUED AdjustHealth`n"
$crossPhaseResult = Get-S149BindGateResult -Text $crossPhase -ExpectedPid 4242
Assert-True (-not $crossPhaseResult.Ready -and $crossPhaseResult.Reason -eq 'FORBIDDEN_PHASE') `
    'the setup receipt must be isolated from any S148 or S147 execution'

$identity = Get-S149ProcessIdentityResult -ExpectedPid 4242 -ExpectedStartTicks 638602272000000000 `
    -ActualPid 4242 -ActualStartTicks 638602272000000000 `
    -ActualName 'SUPERVIVE-Win64-Shipping' -MatchingProcessCount 1
Assert-True $identity.Valid 'one exact PID/start/name process identity must pass'
$reused = Get-S149ProcessIdentityResult -ExpectedPid 4242 -ExpectedStartTicks 638602272000000000 `
    -ActualPid 4242 -ActualStartTicks 638602272000000001 `
    -ActualName 'SUPERVIVE-Win64-Shipping' -MatchingProcessCount 1
Assert-True (-not $reused.Valid -and $reused.Reason -eq 'START_TIME_MISMATCH') `
    'PID reuse with a changed process start tick must refuse'
$ambiguous = Get-S149ProcessIdentityResult -ExpectedPid 4242 -ExpectedStartTicks 638602272000000000 `
    -ActualPid 4242 -ActualStartTicks 638602272000000000 `
    -ActualName 'SUPERVIVE-Win64-Shipping' -MatchingProcessCount 2
Assert-True (-not $ambiguous.Valid -and $ambiguous.Reason -eq 'PROCESS_COUNT') `
    'multiple matching game processes must refuse the controlled flight'

$runtimeIdentity = Get-S149RuntimeProcessIdentityResult `
    -ExpectedPid 5000 -ExpectedStartTicks 638602272000000000 `
    -ExpectedName 'ags' -ExpectedPath 'C:\worktree\server\ags.exe' `
    -ActualPid 5000 -ActualStartTicks 638602272000000000 `
    -ActualName 'ags' -ActualPath 'C:\worktree\server\ags.exe' -MatchingProcessCount 1
Assert-True $runtimeIdentity.Valid 'the exact backend/watcher PID, start, name, and executable path must pass'
$runtimePathDrift = Get-S149RuntimeProcessIdentityResult `
    -ExpectedPid 5000 -ExpectedStartTicks 638602272000000000 `
    -ExpectedName 'ags' -ExpectedPath 'C:\worktree\server\ags.exe' `
    -ActualPid 5000 -ActualStartTicks 638602272000000000 `
    -ActualName 'ags' -ActualPath 'C:\other\ags.exe' -MatchingProcessCount 1
Assert-True (-not $runtimePathDrift.Valid -and $runtimePathDrift.Reason -eq 'PROCESS_PATH') `
    'a same-name process from another executable path must refuse'

Assert-True ((Get-S149IdentityFailureExitCode -S148Attempted $false) -eq 6) `
    'an identity failure before the S148 ledger/map boundary must use the no-attempt exit'
Assert-True ((Get-S149IdentityFailureExitCode -S148Attempted $true) -eq 11) `
    'an identity failure after the durable S148 attempt boundary must forbid retry as post-arm loss'

$gameStartUtc = [datetime]'2026-08-26T05:03:57.7589713Z'
$nowUtc = [datetime]'2026-08-26T05:05:00Z'
$lokiCurrent = "[2026.08.26-05.04.09:424][123]LogUI: TryUIReady SUCCESS"
$lokiGate = Get-S149LokiEvidenceResult -Text $lokiCurrent -Needle 'TryUIReady SUCCESS' `
    -NotBeforeUtc $gameStartUtc -NowUtc $nowUtc
Assert-True $lokiGate.Valid 'the timestamp on the matching current-process Loki line must pass'
$lokiStaleTouched = @'
[2026.08.26-05.00.09:424][123]LogUI: TryUIReady SUCCESS
[2026.08.26-05.04.30:000][123]LogMissions: unrelated fresh traffic
'@
$lokiStaleGate = Get-S149LokiEvidenceResult -Text $lokiStaleTouched `
    -Needle 'TryUIReady SUCCESS' -NotBeforeUtc $gameStartUtc -NowUtc $nowUtc
Assert-True (-not $lokiStaleGate.Valid -and $lokiStaleGate.Reason -eq 'NO_CURRENT_MATCH') `
    'an unrelated post-start append must not freshen a stale TryUIReady token'

$backendStartUtc = [datetime]'2026-08-26T05:03:50Z'
$captureCurrent = "#37 00:04:10.468  GET /core-game/matches/current"
$captureGate = Get-S149CaptureEvidenceResult -Text $captureCurrent `
    -Needle 'core-game/matches' -CaptureCreationUtc $backendStartUtc.AddMilliseconds(25) `
    -BackendStartUtc $backendStartUtc -NotBeforeUtc $gameStartUtc -NowUtc $nowUtc `
    -LocalUtcOffsetMinutes -300
Assert-True $captureGate.Valid 'a matching request in the exact backend generation after game start must pass'
$captureStaleTouched = @'
#37 00:03:10.468  GET /core-game/matches/stale
#99 00:04:30.000  GET /revival/missions/progress
'@
$captureStaleGate = Get-S149CaptureEvidenceResult -Text $captureStaleTouched `
    -Needle 'core-game/matches' -CaptureCreationUtc $backendStartUtc.AddMilliseconds(25) `
    -BackendStartUtc $backendStartUtc -NotBeforeUtc $gameStartUtc -NowUtc $nowUtc `
    -LocalUtcOffsetMinutes -300
Assert-True (-not $captureStaleGate.Valid -and $captureStaleGate.Reason -eq 'NO_CURRENT_MATCH') `
    'fresh missions traffic must not make an old match request satisfy the current-game gate'
$wrongGeneration = Get-S149CaptureEvidenceResult -Text $captureCurrent `
    -Needle 'core-game/matches' -CaptureCreationUtc $backendStartUtc.AddMinutes(-5) `
    -BackendStartUtc $backendStartUtc -NotBeforeUtc $gameStartUtc -NowUtc $nowUtc `
    -LocalUtcOffsetMinutes -300
Assert-True (-not $wrongGeneration.Valid -and $wrongGeneration.Reason -eq 'CAPTURE_GENERATION') `
    'a capture file not created by the bound backend generation must refuse'

$watcherLog = @'
crashwatch: pid 4242 (SUPERVIVE-Win64-Shipping.exe)
  log     : C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log
  outDir  : C:\evidence\dumps\crash-s149
  poll    : 50 ms   suspend-on-trigger: true
'@
$watcher = Get-S149WatcherReceiptResult -Text $watcherLog -ExpectedGamePid 4242 `
    -ExpectedWatcherPid 5050 -ExpectedWatcherStartUtcTicks ([datetime]'2026-08-26T05:03:58Z').Ticks `
    -ExpectedLogCreationUtcTicks ([datetime]'2026-08-26T05:03:57.950Z').Ticks `
    -ActualLogCreationUtcTicks ([datetime]'2026-08-26T05:03:57.950Z').Ticks `
    -ActualLogLastWriteUtcTicks ([datetime]'2026-08-26T05:03:58.050Z').Ticks `
    -NowUtcTicks ([datetime]'2026-08-26T05:03:59Z').Ticks `
    -ExpectedLokiPath 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log' `
    -ExpectedOutputDir 'C:\evidence\dumps\crash-s149'
Assert-True $watcher.Valid 'the watcher must name the exact game PID, log, output directory, 50 ms poll, and suspension'
$wrongWatcher = Get-S149WatcherReceiptResult -Text ($watcherLog.Replace('pid 4242','pid 4243')) `
    -ExpectedGamePid 4242 -ExpectedWatcherPid 5050 `
    -ExpectedWatcherStartUtcTicks ([datetime]'2026-08-26T05:03:58Z').Ticks `
    -ExpectedLogCreationUtcTicks ([datetime]'2026-08-26T05:03:57.950Z').Ticks `
    -ActualLogCreationUtcTicks ([datetime]'2026-08-26T05:03:57.950Z').Ticks `
    -ActualLogLastWriteUtcTicks ([datetime]'2026-08-26T05:03:58.050Z').Ticks `
    -NowUtcTicks ([datetime]'2026-08-26T05:03:59Z').Ticks `
    -ExpectedLokiPath 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log' `
    -ExpectedOutputDir 'C:\evidence\dumps\crash-s149'
Assert-True (-not $wrongWatcher.Valid) 'a watcher attached to another PID must refuse the flight'
$slowWatcher = Get-S149WatcherReceiptResult -Text ($watcherLog.Replace('poll    : 50 ms','poll    : 500 ms')) `
    -ExpectedGamePid 4242 -ExpectedWatcherPid 5050 `
    -ExpectedWatcherStartUtcTicks ([datetime]'2026-08-26T05:03:58Z').Ticks `
    -ExpectedLogCreationUtcTicks ([datetime]'2026-08-26T05:03:57.950Z').Ticks `
    -ActualLogCreationUtcTicks ([datetime]'2026-08-26T05:03:57.950Z').Ticks `
    -ActualLogLastWriteUtcTicks ([datetime]'2026-08-26T05:03:58.050Z').Ticks `
    -NowUtcTicks ([datetime]'2026-08-26T05:03:59Z').Ticks `
    -ExpectedLokiPath 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log' `
    -ExpectedOutputDir 'C:\evidence\dumps\crash-s149'
Assert-True (-not $slowWatcher.Valid) 'a watcher not polling at the required 50 ms must refuse'

$s148Terminal = @'
[S148] PREFLIGHT_REFUSED RESULT=PREFLIGHT_REFUSED issues=0x00000001; no Health write and no AdjustHealth call
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=10 of 10 swapped (scan 1 ms, 10 UFunctions live)
[BF] worker done (hits=1 hitsGT=1)
'@
$s148Result = Get-S148TerminalGateResult -Text $s148Terminal -HostGenerationValid $true
Assert-True ($s148Result.Complete -and $s148Result.Outcome -eq 'PREFLIGHT_REFUSED') `
    'one S148 result followed by drain, disarm, and worker completion must be archivable'
$canonicalS148 = Join-Path $PSScriptRoot `
    '..\..\..\docs\tutorial-launch-marker.s148-self-damage-flight4-PREFLIGHT_REFUSED-ASC-AVATAR-UNBOUND-NO-MUTATION.txt'
$canonicalResult = Get-S148TerminalGateResult -Text (Get-Content -LiteralPath $canonicalS148 -Raw) `
    -HostGenerationValid $true
Assert-True ($canonicalResult.Complete -and $canonicalResult.Outcome -eq 'PREFLIGHT_REFUSED') `
    'the exact frozen Flight4 terminal generation must satisfy the new cleanup gate offline'
$s148Duplicate = Get-S148TerminalGateResult -Text ($s148Terminal + "`n" + $s148Terminal) `
    -HostGenerationValid $true
Assert-True (-not $s148Duplicate.Complete -and $s148Duplicate.Reason -eq 'RESULT_COUNT') `
    'duplicate S148 result generations must not pass'
$s148NoCleanup = Get-S148TerminalGateResult -Text `
    '[S148] PREFLIGHT_REFUSED RESULT=PREFLIGHT_REFUSED issues=0x1' -HostGenerationValid $true
Assert-True (-not $s148NoCleanup.Complete -and $s148NoCleanup.Reason -eq 'DRAIN_MISSING') `
    'an S148 result emitted before cleanup must not be treated as terminal evidence'

$ledgerPath = Join-Path $PSScriptRoot ('.s149-ledger-' + [IO.Path]::GetRandomFileName() + '.json')
try {
    $firstLedger = New-S149AttemptLedger -Path $ledgerPath -GamePid 4242 `
        -StartTicks 638602272000000000 `
        -S148Sha256 'C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E' `
        -OnCreateNew { }
    Assert-True $firstLedger.Created 'the first exact process identity must create one durable arm ledger'
    $secondLedger = New-S149AttemptLedger -Path $ledgerPath -GamePid 4242 `
        -StartTicks 638602272000000000 `
        -S148Sha256 'C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E' `
        -OnCreateNew { throw 'must not run for an existing ledger' }
    Assert-True (-not $secondLedger.Created -and $secondLedger.Reason -eq 'ALREADY_EXISTS') `
        'a rerun for the same PID/start identity must refuse a second S148 arm'
} finally {
    if (Test-Path -LiteralPath $ledgerPath) { Remove-Item -LiteralPath $ledgerPath -Force }
}

Write-Host 'PASS s149_bind_gate_test'
