param(
    [ValidateSet('Pure', 'Snapshot', 'Combined', 'Full')][string]$Section = 'Full'
)

# S150 successor watcher-envelope tests.
#
# Task 2 implements the Pure section: the pure canonical five-line envelope
# validator wrapped around the unchanged S149 semantic parser, plus the
# load-time S149 isolation contract. Snapshot/Combined/Full are added by
# Task 3. Every expectation is hand-derived; the two authoritative positive
# fixtures are the real preserved Flight 2 (352 byte) and historical S149
# (348 byte) watcher receipts.

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "ASSERT FAILED: $Message" }
}
function Assert-StrEq([string]$Actual, [string]$Expected, [string]$Message) {
    if ($Actual -cne $Expected) { throw "ASSERT FAILED: $Message (actual='$Actual' expected='$Expected')" }
}
function Assert-IntEq($Actual, $Expected, [string]$Message) {
    if ([int64]$Actual -ne [int64]$Expected) { throw "ASSERT FAILED: $Message (actual=$Actual expected=$Expected)" }
}
function Assert-Throws([scriptblock]$Action, [string]$ExpectedMessage, [string]$Message) {
    $threw = $false
    $caught = ''
    try { & $Action } catch { $threw = $true; $caught = "$($_.Exception.Message)" }
    Assert-True $threw "$Message : expected a throw"
    if ($ExpectedMessage) {
        Assert-True ($caught -ceq $ExpectedMessage) "$Message : expected message '$ExpectedMessage' got '$caught'"
    }
}

# --- Pinned helper paths and hashes ---
$captureHelper = Join-Path $repo 'configs\s150-capture-generation.ps1'
$s149Helper = Join-Path $repo 'configs\s149-bind-gate.ps1'
$successorHelper = Join-Path $repo 'configs\s150-successor-evidence.ps1'
$captureHelperSha = '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866'
$s149HelperSha = '14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA'
$flight2ReceiptPath = Join-Path $repo 'docs\s150-retirement-s150captureflight2-20260829-192619\crashwatch.stdout.log'
$flight2ReceiptSha = 'CE5A4D371130F9C023BFDAD3528877E9596F246F322A0BE1356564A51EEE4461'
$historicalSha = '750F7AC145FE5916935C16212378940FE9034D2AACCAD6ABC853B38BFC24A304'

function Get-Sha256Upper([byte[]]$Bytes) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($Bytes))).Replace('-', '') }
    finally { $algorithm.Dispose() }
}
function Assert-HelperHash([string]$Path, [string]$Expected, [string]$Label) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    Assert-StrEq $actual $Expected "$Label hash"
}

# Test-side canonical renderer. This is TEST code, independent of the code under
# test; it lets us build synthetic positives and negatives with known reasons.
function New-CanonicalEnvelopeBytes([uint32]$GamePid, [string]$Loki, [string]$OutDir, [string]$OffsetText) {
    $lines = @(
        ('crashwatch: pid {0} (SUPERVIVE-Win64-Shipping.exe)' -f $GamePid),
        ('  log     : ' + [IO.Path]::GetFullPath($Loki)),
        ('  outDir  : ' + [IO.Path]::GetFullPath($OutDir)),
        '  poll    : 50 ms   suspend-on-trigger: true',
        ('  log tail starts at offset {0} (older markers ignored)' -f $OffsetText)
    )
    $text = ($lines -join "`n") + "`n" + "`n"
    return [Text.Encoding]::ASCII.GetBytes($text)
}

function Invoke-Envelope($Bytes, $GamePid, $T) {
    return Get-S150SuccessorWatcherEnvelopeResult `
        -Bytes $Bytes `
        -ExpectedGamePid $GamePid `
        -ExpectedWatcherPid $T.WatcherPid `
        -ExpectedWatcherStartUtcTicks $T.WatcherStart `
        -ExpectedLogCreationUtcTicks $T.ExpCreation `
        -ActualLogCreationUtcTicks $T.ActCreation `
        -ActualLogLastWriteUtcTicks $T.ActWrite `
        -NowUtcTicks $T.Now `
        -ExpectedLokiPath $T.Loki `
        -ExpectedOutputDir $T.OutDir
}
function Assert-Refusal($Result, [string]$ExpectedReason, [string]$Message) {
    Assert-True (-not $Result.Valid) "$Message : expected Valid=`$false (got Reason='$($Result.Reason)')"
    Assert-StrEq $Result.Reason $ExpectedReason "$Message : reason"
}

function Invoke-PureIsolation {
    # S150 capture helper and the successor helper are already dot-sourced at
    # script scope WITHOUT S149. Prove the helper is usable and that a watcher
    # call fails closed with the exact programming error until S149 loads.
    Assert-True ($null -ne (Get-Command -Name Get-S150SuccessorWatcherEnvelopeResult -ErrorAction SilentlyContinue)) `
        'successor helper defines Get-S150SuccessorWatcherEnvelopeResult without S149'
    Assert-True ($null -eq (Get-Command -Name Get-S149WatcherReceiptResult -ErrorAction SilentlyContinue)) `
        'S149 parser is not loaded during the isolation phase'
    $loki = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
    $out352 = 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s150captureflight2-20260829-192619'
    $isoBytes = [IO.File]::ReadAllBytes($flight2ReceiptPath)
    $T352 = @{
        WatcherPid = 37964; WatcherStart = 639236573100000000; ExpCreation = 639236573100000000
        ActCreation = 639236573100000000; ActWrite = 639236573105000000; Now = 639236573110000000
        Loki = $loki; OutDir = $out352
    }
    Assert-Throws { Invoke-Envelope $isoBytes 14512 $T352 } 'S149 watcher parser is not loaded' `
        'watcher call fails closed without S149'
}

function Invoke-PureCases {
    $loki = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
    $out352 = 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s150captureflight2-20260829-192619'
    $out348 = 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s149-bind-flight1-20260826-0305'

    Assert-True ($null -ne (Get-Command -Name Get-S149WatcherReceiptResult -ErrorAction SilentlyContinue)) `
        'S149 parser loaded before pure cases'
    $T352 = @{
        WatcherPid = 37964; WatcherStart = 639236573100000000; ExpCreation = 639236573100000000
        ActCreation = 639236573100000000; ActWrite = 639236573105000000; Now = 639236573110000000
        Loki = $loki; OutDir = $out352
    }

    # ---- Positive: preserved 352-byte Flight 2 receipt ----
    $bytes352 = [IO.File]::ReadAllBytes($flight2ReceiptPath)
    Assert-IntEq $bytes352.Length 352 'flight2 receipt length'
    Assert-StrEq (Get-Sha256Upper $bytes352) $flight2ReceiptSha 'flight2 receipt sha'
    $r = Invoke-Envelope $bytes352 14512 $T352
    Assert-True $r.Valid 'flight2 352-byte envelope is valid'
    Assert-StrEq $r.Reason 'EXACT' 'flight2 reason'
    Assert-StrEq $r.S149Reason 'EXACT' 'flight2 S149 reason'
    Assert-StrEq $r.Newline 'LF' 'flight2 newline'
    Assert-IntEq $r.ParsedOffset 2962913 'flight2 parsed offset'
    Assert-IntEq $r.RawLength 352 'flight2 raw length'
    Assert-StrEq $r.RawSha256 $flight2ReceiptSha 'flight2 raw sha (uppercase)'

    # ---- Positive: historical 348-byte S149 receipt (literal reconstruction, sha-checked) ----
    $bytes348 = New-CanonicalEnvelopeBytes 39928 $loki $out348 '278441'
    Assert-IntEq $bytes348.Length 348 'historical receipt length'
    Assert-StrEq (Get-Sha256Upper $bytes348) $historicalSha 'historical receipt sha matches pinned 750F7AC1'
    $T348 = @{
        WatcherPid = 34272; WatcherStart = 639233283384772527; ExpCreation = 639233283384704311
        ActCreation = 639233283384704311; ActWrite = 639233283393281221; Now = 639233283400000000
        Loki = $loki; OutDir = $out348
    }
    $r = Invoke-Envelope $bytes348 39928 $T348
    Assert-True $r.Valid 'historical 348-byte envelope is valid'
    Assert-StrEq $r.Reason 'EXACT' 'historical reason'
    Assert-IntEq $r.ParsedOffset 278441 'historical parsed offset'
    Assert-IntEq $r.RawLength 348 'historical raw length'

    # ---- Positive: synthetic canonical offset zero ----
    $bytesZero = New-CanonicalEnvelopeBytes 12345 $loki $out352 '0'
    $Tzero = @{
        WatcherPid = 4242; WatcherStart = 639236573100000000; ExpCreation = 639236573100000000
        ActCreation = 639236573100000000; ActWrite = 639236573105000000; Now = 639236573110000000
        Loki = $loki; OutDir = $out352
    }
    $r = Invoke-Envelope $bytesZero 12345 $Tzero
    Assert-True $r.Valid 'synthetic offset-zero envelope is valid'
    Assert-IntEq $r.ParsedOffset 0 'synthetic offset zero parsed'

    # ---- Negatives keyed to their exact first-failure reason ----
    $baseText = [Text.Encoding]::ASCII.GetString($bytes352)

    # WATCHER_RAW_LIMIT: more than 4096 bytes
    $tooBig = [byte[]]::new(4097)
    for ($i = 0; $i -lt $tooBig.Length; $i++) { $tooBig[$i] = 0x61 }
    Assert-Refusal (Invoke-Envelope $tooBig 14512 $T352) 'WATCHER_RAW_LIMIT' 'over 4096 bytes'
    $r = Invoke-Envelope $tooBig 14512 $T352
    Assert-IntEq $r.RawLength 4097 'limit raw length recorded'

    # WATCHER_RAW_ASCII: BOM (its first byte 0xEF is non-ASCII) and a raw non-ASCII byte
    $bom = [byte[]](@(0xEF, 0xBB, 0xBF) + $bytes352)
    Assert-Refusal (Invoke-Envelope $bom 14512 $T352) 'WATCHER_RAW_ASCII' 'UTF-8 BOM'
    $nonAscii = $bytes352.Clone(); $nonAscii[10] = 0xE9
    Assert-Refusal (Invoke-Envelope $nonAscii 14512 $T352) 'WATCHER_RAW_ASCII' 'non-ASCII byte'
    $unicodeDigitText = $baseText.Replace('2962913', ([char]0x0662 + '962913'))
    $unicodeBytes = [Text.Encoding]::UTF8.GetBytes($unicodeDigitText)
    Assert-Refusal (Invoke-Envelope $unicodeBytes 14512 $T352) 'WATCHER_RAW_ASCII' 'unicode digit in offset'

    # WATCHER_RAW_FORBIDDEN_BYTE: CRLF, lone CR, NUL
    $crlf = [Text.Encoding]::ASCII.GetBytes($baseText.Replace("`n", "`r`n"))
    Assert-Refusal (Invoke-Envelope $crlf 14512 $T352) 'WATCHER_RAW_FORBIDDEN_BYTE' 'CRLF'
    $loneCr = $bytes352.Clone(); $loneCr[20] = 0x0D
    Assert-Refusal (Invoke-Envelope $loneCr 14512 $T352) 'WATCHER_RAW_FORBIDDEN_BYTE' 'lone CR'
    $withNul = $bytes352.Clone(); $withNul[20] = 0x00
    Assert-Refusal (Invoke-Envelope $withNul 14512 $T352) 'WATCHER_RAW_FORBIDDEN_BYTE' 'NUL byte'

    # WATCHER_RAW_SHAPE: missing final blank line, extra blank line, missing 5th line,
    # sixth nonempty line, truncation
    $noFinalBlank = [Text.Encoding]::ASCII.GetBytes(($baseText.TrimEnd([char]0x0A) + "`n"))
    Assert-Refusal (Invoke-Envelope $noFinalBlank 14512 $T352) 'WATCHER_RAW_SHAPE' 'missing final blank line'
    $extraBlank = [Text.Encoding]::ASCII.GetBytes($baseText + "`n")
    Assert-Refusal (Invoke-Envelope $extraBlank 14512 $T352) 'WATCHER_RAW_SHAPE' 'extra blank line'
    $fourLine = New-CanonicalEnvelopeBytes 14512 $loki $out352 '2962913'
    $fourLineText = [Text.Encoding]::ASCII.GetString($fourLine)
    $fourLineText = $fourLineText.Replace("  log tail starts at offset 2962913 (older markers ignored)`n", '')
    Assert-Refusal (Invoke-Envelope ([Text.Encoding]::ASCII.GetBytes($fourLineText)) 14512 $T352) 'WATCHER_RAW_SHAPE' 'four nonempty lines'
    $sixLineText = $baseText.TrimEnd([char]0x0A) + "`n  extra sixth line`n`n"
    Assert-Refusal (Invoke-Envelope ([Text.Encoding]::ASCII.GetBytes($sixLineText)) 14512 $T352) 'WATCHER_RAW_SHAPE' 'six nonempty lines'
    $truncated = $bytes352[0..300]
    Assert-Refusal (Invoke-Envelope $truncated 14512 $T352) 'WATCHER_RAW_SHAPE' 'truncated receipt'

    # WATCHER_OFFSET_GRAMMAR: -1, +1, 00, missing digits, trailing space, prose change
    foreach ($bad in @('-1', '+1', '00', '')) {
        $b = New-CanonicalEnvelopeBytes 14512 $loki $out352 $bad
        Assert-Refusal (Invoke-Envelope $b 14512 $T352) 'WATCHER_OFFSET_GRAMMAR' "offset grammar '$bad'"
    }
    $trailingSpace = [Text.Encoding]::ASCII.GetBytes($baseText.Replace('offset 2962913 (older', 'offset 2962913  (older'))
    Assert-Refusal (Invoke-Envelope $trailingSpace 14512 $T352) 'WATCHER_OFFSET_GRAMMAR' 'offset trailing space'
    $proseChange = [Text.Encoding]::ASCII.GetBytes($baseText.Replace('(older markers ignored)', '(older markers ignore)'))
    Assert-Refusal (Invoke-Envelope $proseChange 14512 $T352) 'WATCHER_OFFSET_GRAMMAR' 'fifth-line prose change'

    # WATCHER_OFFSET_RANGE: 19-digit value above Int64 max
    $overflow = New-CanonicalEnvelopeBytes 14512 $loki $out352 '9999999999999999999'
    Assert-Refusal (Invoke-Envelope $overflow 14512 $T352) 'WATCHER_OFFSET_RANGE' 'offset overflow'

    # WATCHER_CANONICAL_MISMATCH: duplicate line, reordered lines, wrong pid/loki/outdir/poll/suspend
    $lines = $baseText.TrimEnd([char]0x0A).Split("`n")
    $dupText = (@($lines[0], $lines[0], $lines[2], $lines[3], $lines[4]) -join "`n") + "`n`n"
    Assert-Refusal (Invoke-Envelope ([Text.Encoding]::ASCII.GetBytes($dupText)) 14512 $T352) 'WATCHER_CANONICAL_MISMATCH' 'duplicate line'
    $reorderText = (@($lines[0], $lines[2], $lines[1], $lines[3], $lines[4]) -join "`n") + "`n`n"
    Assert-Refusal (Invoke-Envelope ([Text.Encoding]::ASCII.GetBytes($reorderText)) 14512 $T352) 'WATCHER_CANONICAL_MISMATCH' 'reordered lines'
    Assert-Refusal (Invoke-Envelope $bytes352 99999 $T352) 'WATCHER_CANONICAL_MISMATCH' 'wrong game pid'
    $Twrongloki = $T352.Clone(); $Twrongloki.Loki = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Other.log'
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Twrongloki) 'WATCHER_CANONICAL_MISMATCH' 'wrong loki path'
    $Twrongout = $T352.Clone(); $Twrongout.OutDir = 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-other'
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Twrongout) 'WATCHER_CANONICAL_MISMATCH' 'wrong outdir'
    $wrongPoll = [Text.Encoding]::ASCII.GetBytes($baseText.Replace('poll    : 50 ms', 'poll    : 60 ms'))
    Assert-Refusal (Invoke-Envelope $wrongPoll 14512 $T352) 'WATCHER_CANONICAL_MISMATCH' 'wrong poll value'
    $wrongSuspend = [Text.Encoding]::ASCII.GetBytes($baseText.Replace('suspend-on-trigger: true', 'suspend-on-trigger: false'))
    Assert-Refusal (Invoke-Envelope $wrongSuspend 14512 $T352) 'WATCHER_CANONICAL_MISMATCH' 'wrong suspension value'

    # WATCHER_S149_REFUSAL: creation mismatch, stale generation, zero watcher identity, now<watcherStart
    $Tcreation = $T352.Clone(); $Tcreation.ActCreation = $T352.ExpCreation + 10000000
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Tcreation) 'WATCHER_S149_REFUSAL' 'creation tick mismatch'
    $Tstale = $T352.Clone(); $Tstale.ExpCreation = $T352.WatcherStart + 100000000; $Tstale.ActCreation = $Tstale.ExpCreation
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Tstale) 'WATCHER_S149_REFUSAL' 'stale generation'
    $Tzerowatcher = $T352.Clone(); $Tzerowatcher.WatcherPid = 0
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Tzerowatcher) 'WATCHER_S149_REFUSAL' 'zero watcher identity'
    $Tnow = $T352.Clone(); $Tnow.Now = $T352.WatcherStart - 10000000
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Tnow) 'WATCHER_S149_REFUSAL' 'now before watcher start'

    # WATCHER_TIME_ORDER: last write before creation while S149 still accepts
    $Torder = @{
        WatcherPid = 37964; WatcherStart = 639236573100000000; ExpCreation = 639236573120000000
        ActCreation = 639236573120000000; ActWrite = 639236573100000000; Now = 639236573130000000
        Loki = $loki; OutDir = $out352
    }
    Assert-Refusal (Invoke-Envelope $bytes352 14512 $Torder) 'WATCHER_TIME_ORDER' 'last write before creation'

    Write-Output 'PASS s150_successor_watcher_envelope_test Pure'
}

# ---- Task 3: coherent held-handle snapshots and combined admission ----

$EmptySha = 'E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855'
$Sha352 = 'CE5A4D371130F9C023BFDAD3528877E9596F246F322A0BE1356564A51EEE4461'

function New-TempRoot {
    $root = Join-Path $repo ('.superpowers\temp\s150snap-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($root) | Out-Null
    return $root
}
function Remove-TempRoot([string]$Root) {
    $tempBase = [IO.Path]::GetFullPath((Join-Path $repo '.superpowers\temp'))
    $full = [IO.Path]::GetFullPath($Root)
    if (-not $full.StartsWith($tempBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "refusing to remove temp root outside .superpowers\temp: $full"
    }
    $attr = [IO.File]::GetAttributes($full)
    if (($attr -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "temp root is a reparse point: $full" }
    Remove-Item -LiteralPath $full -Recurse -Force
}
function Write-CreateNewBytes([string]$Path, [byte[]]$Bytes) {
    $s = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { if ($Bytes.Length -gt 0) { $s.Write($Bytes, 0, $Bytes.Length) }; $s.Flush($true) } finally { $s.Dispose() }
}
function Append-SharedByte([string]$Path, [byte]$Value) {
    $w = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
    try { [void]$w.Seek(0, [IO.SeekOrigin]::End); $w.WriteByte($Value); $w.Flush($true) } finally { $w.Dispose() }
}

function Invoke-SnapshotSuite {
    $loki = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
    $out352 = 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s150captureflight2-20260829-192619'
    $canonical = New-CanonicalEnvelopeBytes 14512 $loki $out352 '2962913'
    $root = New-TempRoot
    try {
        # --- coherent snapshot returns exact metadata/hash for stdout and empty stderr ---
        $stdoutPath = Join-Path $root 'a.stdout.log'
        $stderrPath = Join-Path $root 'a.stderr.log'
        Write-CreateNewBytes $stdoutPath $canonical
        Write-CreateNewBytes $stderrPath ([byte[]]::new(0))
        $handles = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $stdoutPath -StderrPath $stderrPath
        try {
            $snap = Get-S150SuccessorCoherentStreamSnapshot -Handle $handles.Stdout -MaxBytes 4096
            Assert-IntEq $snap.Size 352 'snapshot stdout size'
            Assert-StrEq $snap.Sha256 $Sha352 'snapshot stdout sha'
            $snapE = Get-S150SuccessorCoherentStreamSnapshot -Handle $handles.Stderr -MaxBytes 4096
            Assert-IntEq $snapE.Size 0 'snapshot stderr size'
            Assert-StrEq $snapE.Sha256 $EmptySha 'snapshot stderr empty sha'
            # a legitimate writer coexists with the evidence handle (ReadWrite sharing)
            Append-SharedByte $stdoutPath 0x61
            # while the evidence handle is held, delete and rename refuse (no delete sharing)
            Assert-Throws { [IO.File]::Delete($stdoutPath) } '' 'delete refuses while evidence handle held'
            Assert-Throws { [IO.File]::Move($stdoutPath, (Join-Path $root 'renamed.log')) } '' 'rename refuses while evidence handle held'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $handles }
        # after close, the leaf can be deleted (no lingering handle)
        [IO.File]::Delete($stdoutPath)
        Assert-True (-not (Test-Path -LiteralPath $stdoutPath)) 'stdout deletable after close'
        # close is idempotent
        Close-S150SuccessorWatcherEvidenceHandles -Handles $handles

        # --- BetweenSamples append changes length/hash and refuses ---
        $p2 = Join-Path $root 'b.stdout.log'
        Write-CreateNewBytes $p2 $canonical
        $e2 = Join-Path $root 'b.stderr.log'; Write-CreateNewBytes $e2 ([byte[]]::new(0))
        $h2 = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $p2 -StderrPath $e2
        try {
            Assert-Throws {
                Get-S150SuccessorCoherentStreamSnapshot -Handle $h2.Stdout -MaxBytes 4096 -BetweenSamples { Append-SharedByte $p2 0x62 }
            } '' 'append between samples refuses'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h2 }

        # --- timestamp-only mutation refuses ---
        $p3 = Join-Path $root 'c.stdout.log'
        Write-CreateNewBytes $p3 $canonical
        $e3 = Join-Path $root 'c.stderr.log'; Write-CreateNewBytes $e3 ([byte[]]::new(0))
        $h3 = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $p3 -StderrPath $e3
        try {
            Assert-Throws {
                Get-S150SuccessorCoherentStreamSnapshot -Handle $h3.Stdout -MaxBytes 4096 -BetweenSamples {
                    [IO.File]::SetLastWriteTimeUtc($p3, ([IO.File]::GetLastWriteTimeUtc($p3).AddSeconds(37)))
                }
            } '' 'timestamp-only mutation refuses'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h3 }

        # --- more than MaxBytes refuses before an unbounded read ---
        $p4 = Join-Path $root 'd.stdout.log'
        Write-CreateNewBytes $p4 $canonical
        $e4 = Join-Path $root 'd.stderr.log'; Write-CreateNewBytes $e4 ([byte[]]::new(0))
        $h4 = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $p4 -StderrPath $e4
        try {
            Assert-Throws { Get-S150SuccessorCoherentStreamSnapshot -Handle $h4.Stdout -MaxBytes 100 } '' 'over MaxBytes refuses'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h4 }

        # --- partial open: stderr missing disposes stdout ---
        $p5 = Join-Path $root 'e.stdout.log'
        Write-CreateNewBytes $p5 $canonical
        $missingStderr = Join-Path $root 'e.stderr.missing.log'
        Assert-Throws {
            Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $p5 -StderrPath $missingStderr
        } '' 'partial open with missing stderr refuses'
        [IO.File]::Delete($p5)
        Assert-True (-not (Test-Path -LiteralPath $p5)) 'stdout disposed after partial open failure (deletable)'
    } finally {
        Remove-TempRoot $root
    }
    Write-Output 'PASS s150_successor_watcher_envelope_test Snapshot'
}

function Invoke-CombinedSuite {
    $loki = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
    $out352 = 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s150captureflight2-20260829-192619'
    $canonical = New-CanonicalEnvelopeBytes 14512 $loki $out352 '2962913'
    $T = @{
        WatcherPid = 37964; WatcherStart = 639236573100000000; ExpCreation = 639236573100000000
        ActCreation = 639236573100000000; ActWrite = 639236573105000000; Now = 639236573110000000
    }
    $invoke = {
        param($Handles, $Admitted)
        $callArgs = @{
            Handles = $Handles; ExpectedGamePid = 14512; ExpectedWatcherPid = $T.WatcherPid
            ExpectedWatcherStartUtcTicks = $T.WatcherStart; ExpectedLogCreationUtcTicks = $T.ExpCreation
            ActualLogCreationUtcTicks = $T.ActCreation; ActualLogLastWriteUtcTicks = $T.ActWrite
            NowUtcTicks = $T.Now; ExpectedLokiPath = $loki; ExpectedOutputDir = $out352
        }
        if ($null -ne $Admitted) { $callArgs['AdmittedWatcherEvidence'] = $Admitted }
        return Get-S150SuccessorWatcherEvidenceResult @callArgs
    }
    $root = New-TempRoot
    try {
        # --- canonical stdout plus exact-empty stderr admits ---
        $so = Join-Path $root 'ok.stdout.log'; Write-CreateNewBytes $so $canonical
        $se = Join-Path $root 'ok.stderr.log'; Write-CreateNewBytes $se ([byte[]]::new(0))
        $h = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $so -StderrPath $se
        $admission = $null
        try {
            $r = & $invoke $h $null
            Assert-True $r.Valid 'combined admits canonical stdout + empty stderr'
            Assert-StrEq $r.Reason 'EXACT' 'combined reason'
            Assert-True $r.Envelope.Valid 'combined envelope valid'
            Assert-True ($r.Envelope -isnot [array]) 'combined envelope is a single object (helper invoked once)'
            Assert-StrEq $r.Admission.schema 's150-successor-watcher-admission/v1' 'admission schema'
            Assert-StrEq $r.Admission.stdoutSha256 $Sha352 'admission stdout sha'
            Assert-StrEq $r.Admission.stderrSha256 $EmptySha 'admission stderr sha'
            Assert-IntEq $r.Admission.parsedOffset 2962913 'admission parsed offset'
            # admission is serializable and holds no live handles
            $json = $r.Admission | ConvertTo-Json -Depth 8
            Assert-True ($json -notmatch 'FileStream') 'admission holds no live handles'
            $admission = $r.Admission
            # re-admission against the admitted record still equals (fields compared, not refreshed)
            $r2 = & $invoke $h $admission
            Assert-True $r2.Valid 'combined re-admits unchanged evidence against admitted record'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h }

        # --- nonempty stderr refuses ---
        $so2 = Join-Path $root 'ne.stdout.log'; Write-CreateNewBytes $so2 $canonical
        $se2 = Join-Path $root 'ne.stderr.log'; Write-CreateNewBytes $se2 ([byte[]](0x61))
        $h2 = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $so2 -StderrPath $se2
        try {
            $r = & $invoke $h2 $null
            Assert-True (-not $r.Valid) 'combined refuses nonempty stderr'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h2 }

        # --- delayed stderr append after admission refuses revalidation ---
        $so3 = Join-Path $root 'ds.stdout.log'; Write-CreateNewBytes $so3 $canonical
        $se3 = Join-Path $root 'ds.stderr.log'; Write-CreateNewBytes $se3 ([byte[]]::new(0))
        $h3 = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $so3 -StderrPath $se3
        try {
            $ra = & $invoke $h3 $null
            Assert-True $ra.Valid 'stderr-append case admits first'
            Append-SharedByte $se3 0x61
            $rb = & $invoke $h3 $ra.Admission
            Assert-True (-not $rb.Valid) 'combined refuses delayed stderr append against admitted record'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h3 }

        # --- delayed stdout append after admission refuses revalidation ---
        $so4 = Join-Path $root 'do.stdout.log'; Write-CreateNewBytes $so4 $canonical
        $se4 = Join-Path $root 'do.stderr.log'; Write-CreateNewBytes $se4 ([byte[]]::new(0))
        $h4 = Open-S150SuccessorWatcherEvidenceHandles -PinnedBaseDirectory $root -StdoutPath $so4 -StderrPath $se4
        try {
            $ra = & $invoke $h4 $null
            Assert-True $ra.Valid 'stdout-append case admits first'
            Append-SharedByte $so4 0x61
            $rb = & $invoke $h4 $ra.Admission
            Assert-True (-not $rb.Valid) 'combined refuses delayed stdout append against admitted record'
        } finally { Close-S150SuccessorWatcherEvidenceHandles -Handles $h4 }
    } finally {
        Remove-TempRoot $root
    }
    Write-Output 'PASS s150_successor_watcher_envelope_test Combined'
}

# Helpers are dot-sourced at SCRIPT scope so every suite function can see them.
switch ($Section) {
    'Pure' {
        Assert-HelperHash $captureHelper $captureHelperSha 'S150 capture helper'
        Assert-True (Test-Path -LiteralPath $successorHelper) "successor helper exists: $successorHelper"
        . $captureHelper
        . $successorHelper
        Invoke-PureIsolation
        Assert-HelperHash $s149Helper $s149HelperSha 'S149 bind gate'
        . $s149Helper
        Invoke-PureCases
    }
    'Snapshot' {
        Assert-HelperHash $captureHelper $captureHelperSha 'S150 capture helper'
        Assert-HelperHash $s149Helper $s149HelperSha 'S149 bind gate'
        Assert-True (Test-Path -LiteralPath $successorHelper) "successor helper exists: $successorHelper"
        . $captureHelper
        . $s149Helper
        . $successorHelper
        Invoke-SnapshotSuite
    }
    'Combined' {
        Assert-HelperHash $captureHelper $captureHelperSha 'S150 capture helper'
        Assert-HelperHash $s149Helper $s149HelperSha 'S149 bind gate'
        Assert-True (Test-Path -LiteralPath $successorHelper) "successor helper exists: $successorHelper"
        . $captureHelper
        . $s149Helper
        . $successorHelper
        Invoke-CombinedSuite
    }
    'Full' {
        Assert-HelperHash $captureHelper $captureHelperSha 'S150 capture helper'
        Assert-True (Test-Path -LiteralPath $successorHelper) "successor helper exists: $successorHelper"
        . $captureHelper
        . $successorHelper
        Invoke-PureIsolation
        Assert-HelperHash $s149Helper $s149HelperSha 'S149 bind gate'
        . $s149Helper
        Invoke-PureCases
        Invoke-SnapshotSuite
        Invoke-CombinedSuite
    }
}
