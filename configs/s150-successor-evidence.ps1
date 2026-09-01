# S150 successor evidence primitives (identity-neutral).
#
# This helper repairs the two terminal S150 Flight 2 trust-boundary defects
# without a live identity:
#
#   1. A pure canonical five-line watcher-envelope validator layered over the
#      unchanged S149 semantic parser (this file, Task 2). It compares canonical
#      raw bytes before decoding and never relaxes the exact-five-line grammar.
#   2. (Tasks 3-4) held-handle coherent watcher snapshots plus output-path,
#      identity-anchor, and writer-denying terminal-lease primitives.
#
# ASCII only; Windows PowerShell 5.1 compatible. No load-time S149 dependency:
# each public function checks only the dependency it actually consumes, and does
# so at the point it is consumed.

function New-S150SuccessorWatcherEnvelopeResult {
    param(
        [bool]$Valid,
        [string]$Reason,
        [int64]$RawLength,
        [string]$RawSha256,
        [int64]$ParsedOffset,
        [int64]$ExpectedLogCreationUtcTicks,
        [int64]$ActualLogCreationUtcTicks,
        [int64]$ActualLogLastWriteUtcTicks,
        [int64]$NowUtcTicks,
        [string]$S149Reason
    )
    return [pscustomobject][ordered]@{
        Valid = $Valid
        Reason = $Reason
        RawLength = $RawLength
        RawSha256 = $RawSha256
        Newline = 'LF'
        ParsedOffset = $ParsedOffset
        ExpectedLogCreationUtcTicks = $ExpectedLogCreationUtcTicks
        ActualLogCreationUtcTicks = $ActualLogCreationUtcTicks
        ActualLogLastWriteUtcTicks = $ActualLogLastWriteUtcTicks
        NowUtcTicks = $NowUtcTicks
        S149Reason = $S149Reason
    }
}

function Get-S150SuccessorWatcherEnvelopeResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][uint32]$ExpectedGamePid,
        [Parameter(Mandatory = $true)][uint32]$ExpectedWatcherPid,
        [Parameter(Mandatory = $true)][int64]$ExpectedWatcherStartUtcTicks,
        [Parameter(Mandatory = $true)][int64]$ExpectedLogCreationUtcTicks,
        [Parameter(Mandatory = $true)][int64]$ActualLogCreationUtcTicks,
        [Parameter(Mandatory = $true)][int64]$ActualLogLastWriteUtcTicks,
        [Parameter(Mandatory = $true)][int64]$NowUtcTicks,
        [Parameter(Mandatory = $true)][string]$ExpectedLokiPath,
        [Parameter(Mandatory = $true)][string]$ExpectedOutputDir
    )

    # Compute the uppercase SHA-256 for every result; the size limit is still the
    # first admission decision.
    $rawLength = [int64]$Bytes.Length
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $rawSha256 = ([BitConverter]::ToString($hashAlgorithm.ComputeHash($Bytes))).Replace('-', '')
    } finally { $hashAlgorithm.Dispose() }

    $mk = {
        param([string]$reason, [int64]$offset, [string]$s149Reason)
        New-S150SuccessorWatcherEnvelopeResult `
            -Valid ($reason -ceq 'EXACT') -Reason $reason -RawLength $rawLength -RawSha256 $rawSha256 `
            -ParsedOffset $offset -ExpectedLogCreationUtcTicks $ExpectedLogCreationUtcTicks `
            -ActualLogCreationUtcTicks $ActualLogCreationUtcTicks `
            -ActualLogLastWriteUtcTicks $ActualLogLastWriteUtcTicks -NowUtcTicks $NowUtcTicks `
            -S149Reason $s149Reason
    }

    # 1. Reject more than 4,096 bytes.
    if ($rawLength -gt 4096) { return (& $mk 'WATCHER_RAW_LIMIT' ([int64]-1) '') }

    # 3. Reject any non-ASCII byte, then any BOM/NUL/CR forbidden byte.
    for ($i = 0; $i -lt $Bytes.Length; $i++) {
        if ($Bytes[$i] -gt 127) { return (& $mk 'WATCHER_RAW_ASCII' ([int64]-1) '') }
    }
    for ($i = 0; $i -lt $Bytes.Length; $i++) {
        if ($Bytes[$i] -eq 0x00 -or $Bytes[$i] -eq 0x0D) {
            return (& $mk 'WATCHER_RAW_FORBIDDEN_BYTE' ([int64]-1) '')
        }
    }

    # 4. Require exactly six LF bytes and terminal bytes 0A 0A.
    $lfOffsets = New-Object 'System.Collections.Generic.List[int]'
    for ($i = 0; $i -lt $Bytes.Length; $i++) {
        if ($Bytes[$i] -eq 0x0A) { $lfOffsets.Add($i) }
    }
    if ($lfOffsets.Count -ne 6 -or $Bytes.Length -lt 2 -or
        $Bytes[$Bytes.Length - 1] -ne 0x0A -or $Bytes[$Bytes.Length - 2] -ne 0x0A) {
        return (& $mk 'WATCHER_RAW_SHAPE' ([int64]-1) '')
    }

    # 5. Locate the fifth line directly in bytes and require the exact ASCII grammar.
    $fifthStart = $lfOffsets[3] + 1
    $fifthEnd = $lfOffsets[4]
    $fifthLine = [Text.Encoding]::ASCII.GetString($Bytes, $fifthStart, $fifthEnd - $fifthStart)
    $offsetMatch = [regex]::Match($fifthLine,
        '^  log tail starts at offset (0|[1-9][0-9]{0,18}) \(older markers ignored\)$')
    if (-not $offsetMatch.Success) { return (& $mk 'WATCHER_OFFSET_GRAMMAR' ([int64]-1) '') }

    # 6. Parse invariantly into a nonnegative Int64; reject overflow.
    $parsedOffset = [int64]0
    if (-not [int64]::TryParse($offsetMatch.Groups[1].Value,
            [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture,
            [ref]$parsedOffset)) {
        return (& $mk 'WATCHER_OFFSET_RANGE' ([int64]-1) '')
    }

    # 7. Render the canonical envelope with ASCII + LF and require exact byte identity.
    $canonicalLines = @(
        ('crashwatch: pid {0} (SUPERVIVE-Win64-Shipping.exe)' -f $ExpectedGamePid),
        ('  log     : ' + [IO.Path]::GetFullPath($ExpectedLokiPath)),
        ('  outDir  : ' + [IO.Path]::GetFullPath($ExpectedOutputDir)),
        '  poll    : 50 ms   suspend-on-trigger: true',
        ('  log tail starts at offset {0} (older markers ignored)' -f
            $parsedOffset.ToString([Globalization.CultureInfo]::InvariantCulture))
    )
    $canonicalText = ($canonicalLines -join "`n") + "`n" + "`n"
    $canonicalBytes = [Text.ASCIIEncoding]::new().GetBytes($canonicalText)
    if ($canonicalBytes.Length -ne $Bytes.Length -or
        -not [Linq.Enumerable]::SequenceEqual([byte[]]$canonicalBytes, [byte[]]$Bytes)) {
        return (& $mk 'WATCHER_CANONICAL_MISMATCH' $parsedOffset '')
    }

    # 8. Only now consume the unchanged S149 parser. Fail closed if it is absent.
    if ($null -eq (Get-Command -Name Get-S149WatcherReceiptResult -CommandType Function -ErrorAction SilentlyContinue)) {
        throw 'S149 watcher parser is not loaded'
    }
    $decoded = [Text.Encoding]::ASCII.GetString($Bytes)
    $s149 = Get-S149WatcherReceiptResult -Text $decoded `
        -ExpectedGamePid $ExpectedGamePid -ExpectedWatcherPid $ExpectedWatcherPid `
        -ExpectedWatcherStartUtcTicks $ExpectedWatcherStartUtcTicks `
        -ExpectedLogCreationUtcTicks $ExpectedLogCreationUtcTicks `
        -ActualLogCreationUtcTicks $ActualLogCreationUtcTicks `
        -ActualLogLastWriteUtcTicks $ActualLogLastWriteUtcTicks `
        -NowUtcTicks $NowUtcTicks -ExpectedLokiPath $ExpectedLokiPath -ExpectedOutputDir $ExpectedOutputDir
    if (-not $s149.Valid) {
        return (& $mk 'WATCHER_S149_REFUSAL' $parsedOffset ([string]$s149.Reason))
    }

    # 9. Independently require last write not before creation.
    if ($ActualLogLastWriteUtcTicks -lt $ActualLogCreationUtcTicks) {
        return (& $mk 'WATCHER_TIME_ORDER' $parsedOffset ([string]$s149.Reason))
    }

    return (& $mk 'EXACT' $parsedOffset ([string]$s149.Reason))
}

# ---- Task 3: coherent held-handle watcher snapshots ----

function Open-S150SuccessorSingleWatcherEvidenceHandle {
    param(
        [Parameter(Mandatory = $true)][string]$PinnedBaseDirectory,
        [Parameter(Mandatory = $true)][string]$Role,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $full = [IO.Path]::GetFullPath($Path)
    $state = Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $full
    if (-not $state.Exists) { throw "S150 watcher evidence leaf is absent: $full" }
    if (($state.Attributes -band [IO.FileAttributes]::Directory) -ne 0) {
        throw "S150 watcher evidence leaf is not an ordinary file: $full"
    }
    # Persistent read-only identity handle: FileShare.ReadWrite permits the legitimate
    # live writer, but omitting FileShare.Delete blocks delete/rename/replacement.
    $stream = [IO.File]::Open($full, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    return [pscustomobject][ordered]@{
        Role = $Role
        Path = $full
        Stream = $stream
    }
}

function Open-S150SuccessorWatcherEvidenceHandles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$PinnedBaseDirectory,
        [Parameter(Mandatory = $true)][string]$StdoutPath,
        [Parameter(Mandatory = $true)][string]$StderrPath
    )
    $stdout = Open-S150SuccessorSingleWatcherEvidenceHandle -PinnedBaseDirectory $PinnedBaseDirectory -Role 'Stdout' -Path $StdoutPath
    try {
        $stderr = Open-S150SuccessorSingleWatcherEvidenceHandle -PinnedBaseDirectory $PinnedBaseDirectory -Role 'Stderr' -Path $StderrPath
    } catch {
        if ($null -ne $stdout -and $null -ne $stdout.Stream) { $stdout.Stream.Dispose() }
        throw
    }
    return [pscustomobject][ordered]@{
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Get-S150SuccessorCoherentStreamSnapshot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Handle,
        [Parameter(Mandatory = $true)][int64]$MaxBytes,
        [scriptblock]$BetweenSamples
    )
    if ($MaxBytes -lt 0) { throw 'S150 coherent snapshot MaxBytes must be nonnegative.' }
    $stream = $Handle.Stream
    $path = $Handle.Path

    $readSample = {
        param([int64]$expectLength)
        $info = [IO.FileInfo]::new($path)
        $info.Refresh()
        $creation = [int64]$info.CreationTimeUtc.Ticks
        $lastWrite = [int64]$info.LastWriteTimeUtc.Ticks
        $pathLength = [int64]$info.Length
        $streamLength = [int64]$stream.Length
        if ($streamLength -gt $MaxBytes) { throw "S150 coherent snapshot exceeds MaxBytes: $path ($streamLength > $MaxBytes)" }
        if ($expectLength -ge 0 -and $streamLength -ne $expectLength) { throw "S150 coherent snapshot length changed: $path" }
        [void]$stream.Seek(0, [IO.SeekOrigin]::Begin)
        $buffer = New-Object byte[] $streamLength
        $total = 0
        while ($total -lt $streamLength) {
            $n = $stream.Read($buffer, $total, [int]($streamLength - $total))
            if ($n -le 0) { break }
            $total += $n
        }
        if ($total -ne $streamLength) { throw "S150 coherent snapshot short read: $path" }
        $info.Refresh()
        if ([int64]$info.CreationTimeUtc.Ticks -ne $creation -or
            [int64]$info.LastWriteTimeUtc.Ticks -ne $lastWrite -or
            [int64]$info.Length -ne $pathLength -or
            [int64]$stream.Length -ne $streamLength) {
            throw "S150 coherent snapshot metadata changed during read: $path"
        }
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try { $sha = ([BitConverter]::ToString($algorithm.ComputeHash($buffer))).Replace('-', '') }
        finally { $algorithm.Dispose() }
        return [pscustomobject][ordered]@{
            Creation = $creation; LastWrite = $lastWrite; PathLength = $pathLength
            StreamLength = $streamLength; Sha256 = $sha; Bytes = $buffer
        }
    }

    $first = & $readSample ([int64]-1)
    if ($null -ne $BetweenSamples) { & $BetweenSamples | Out-Null }
    $second = & $readSample $first.StreamLength
    if ($second.Creation -ne $first.Creation -or $second.LastWrite -ne $first.LastWrite -or
        $second.PathLength -ne $first.PathLength -or $second.StreamLength -ne $first.StreamLength -or
        $second.Sha256 -cne $first.Sha256) {
        throw "S150 coherent snapshot changed between samples: $path"
    }
    return [pscustomobject][ordered]@{
        Role = $Handle.Role
        Path = $path
        Size = $first.StreamLength
        Sha256 = $first.Sha256
        CreationUtcTicks = $first.Creation
        LastWriteUtcTicks = $first.LastWrite
        Bytes = $first.Bytes
    }
}

function Close-S150SuccessorWatcherEvidenceHandles {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Handles)
    foreach ($role in @('Stderr', 'Stdout')) {
        $item = $Handles.$role
        if ($null -ne $item -and $null -ne $item.Stream) {
            $item.Stream.Dispose()
            $item.Stream = $null
        }
    }
}

$script:S150EmptyStreamSha256 = 'E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855'

function Get-S150SuccessorWatcherEvidenceResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Handles,
        [Parameter(Mandatory = $true)][uint32]$ExpectedGamePid,
        [Parameter(Mandatory = $true)][uint32]$ExpectedWatcherPid,
        [Parameter(Mandatory = $true)][int64]$ExpectedWatcherStartUtcTicks,
        [Parameter(Mandatory = $true)][int64]$ExpectedLogCreationUtcTicks,
        [Parameter(Mandatory = $true)][int64]$ActualLogCreationUtcTicks,
        [Parameter(Mandatory = $true)][int64]$ActualLogLastWriteUtcTicks,
        [Parameter(Mandatory = $true)][int64]$NowUtcTicks,
        [Parameter(Mandatory = $true)][string]$ExpectedLokiPath,
        [Parameter(Mandatory = $true)][string]$ExpectedOutputDir,
        [object]$AdmittedWatcherEvidence
    )

    # Coherent held-handle snapshots of both watcher streams. The stdout stream
    # is bounded to the 4,096-byte envelope ceiling.
    $stdoutSnapshot = Get-S150SuccessorCoherentStreamSnapshot -Handle $Handles.Stdout -MaxBytes 4096
    $stderrSnapshot = Get-S150SuccessorCoherentStreamSnapshot -Handle $Handles.Stderr -MaxBytes 4096

    # Invoke the pure envelope helper exactly once, with the caller-supplied Loki
    # generation timestamps (never the watcher stdout file timestamps).
    $envelope = Get-S150SuccessorWatcherEnvelopeResult `
        -Bytes $stdoutSnapshot.Bytes -ExpectedGamePid $ExpectedGamePid `
        -ExpectedWatcherPid $ExpectedWatcherPid -ExpectedWatcherStartUtcTicks $ExpectedWatcherStartUtcTicks `
        -ExpectedLogCreationUtcTicks $ExpectedLogCreationUtcTicks `
        -ActualLogCreationUtcTicks $ActualLogCreationUtcTicks `
        -ActualLogLastWriteUtcTicks $ActualLogLastWriteUtcTicks -NowUtcTicks $NowUtcTicks `
        -ExpectedLokiPath $ExpectedLokiPath -ExpectedOutputDir $ExpectedOutputDir

    $admission = [pscustomobject][ordered]@{
        schema = 's150-successor-watcher-admission/v1'
        stdoutPath = $stdoutSnapshot.Path
        stdoutSize = [int64]$stdoutSnapshot.Size
        stdoutSha256 = [string]$stdoutSnapshot.Sha256
        stdoutCreationUtcTicks = [int64]$stdoutSnapshot.CreationUtcTicks
        stdoutLastWriteUtcTicks = [int64]$stdoutSnapshot.LastWriteUtcTicks
        stdoutNewline = 'LF'
        parsedOffset = [int64]$envelope.ParsedOffset
        stderrPath = $stderrSnapshot.Path
        stderrSize = [int64]$stderrSnapshot.Size
        stderrSha256 = [string]$stderrSnapshot.Sha256
        stderrCreationUtcTicks = [int64]$stderrSnapshot.CreationUtcTicks
        stderrLastWriteUtcTicks = [int64]$stderrSnapshot.LastWriteUtcTicks
        envelopeReason = [string]$envelope.Reason
    }

    $reason = 'EXACT'
    if ($stderrSnapshot.Size -ne 0 -or ([string]$stderrSnapshot.Sha256) -cne $script:S150EmptyStreamSha256) {
        $reason = 'WATCHER_STDERR_NONEMPTY'
    } elseif (-not $envelope.Valid) {
        $reason = 'WATCHER_ENVELOPE_REFUSAL'
    } elseif ($null -ne $AdmittedWatcherEvidence) {
        $fields = @(
            'schema', 'stdoutPath', 'stdoutSize', 'stdoutSha256', 'stdoutCreationUtcTicks',
            'stdoutLastWriteUtcTicks', 'stdoutNewline', 'parsedOffset', 'stderrPath', 'stderrSize',
            'stderrSha256', 'stderrCreationUtcTicks', 'stderrLastWriteUtcTicks', 'envelopeReason'
        )
        foreach ($field in $fields) {
            if (([string]$admission.$field) -cne ([string]$AdmittedWatcherEvidence.$field)) {
                $reason = 'WATCHER_ADMISSION_DRIFT'
                break
            }
        }
    }

    return [pscustomobject][ordered]@{
        Valid = ($reason -ceq 'EXACT')
        Reason = $reason
        StdoutSnapshot = $stdoutSnapshot
        StderrSnapshot = $stderrSnapshot
        Envelope = $envelope
        Admission = $admission
    }
}

# ---- Task 4: output path contract and controlled-backend output state ----

function Get-S150SuccessorOutputPathContract {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$CaptureArchiveDirectory,
        [Parameter(Mandatory = $true)][string]$ExpectedRetirementDirectory
    )
    $sep = [IO.Path]::DirectorySeparatorChar
    $archive = [IO.Path]::GetFullPath($CaptureArchiveDirectory).TrimEnd($sep)
    $retirement = [IO.Path]::GetFullPath($ExpectedRetirementDirectory).TrimEnd($sep)

    # The archive leaf is compared ordinally and case-sensitively.
    if ([IO.Path]::GetFileName($archive) -cne 'capture-archive') {
        throw "S150 output contract requires the exact 'capture-archive' leaf: $archive"
    }
    $archiveParent = [IO.Path]::GetDirectoryName($archive)
    if (-not [string]::Equals($archiveParent, $retirement, [StringComparison]::OrdinalIgnoreCase)) {
        throw "S150 capture-archive parent is not the expected retirement directory: $archiveParent (expected $retirement)"
    }

    $launcherStdout = $retirement + $sep + 'launcher.stdout.log'
    $launcherStderr = $retirement + $sep + 'launcher.stderr.log'
    $backendStdout = $retirement + $sep + 'backend.stdout.log'
    $backendStderr = $retirement + $sep + 'backend.stderr.log'
    $leaves = @($launcherStdout, $launcherStderr, $backendStdout, $backendStderr)
    if (@($leaves | Sort-Object -Unique).Count -ne 4) { throw 'S150 output leaves are not distinct.' }

    return [pscustomobject][ordered]@{
        CaptureArchiveDirectory = $archive
        RetirementDirectory = $retirement
        LauncherStdoutPath = $launcherStdout
        LauncherStderrPath = $launcherStderr
        BackendStdoutPath = $backendStdout
        BackendStderrPath = $backendStderr
    }
}

function Assert-S150SuccessorControlledBackendOutputState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$PathContract,
        [Parameter(Mandatory = $true)][string]$PinnedBaseDirectory,
        [switch]$RequireEmpty
    )
    # Independently recanonicalize and revalidate the archive/retirement relation
    # every call rather than trusting the stored object.
    $recheck = Get-S150SuccessorOutputPathContract `
        -CaptureArchiveDirectory $PathContract.CaptureArchiveDirectory `
        -ExpectedRetirementDirectory $PathContract.RetirementDirectory

    $components = @(
        $recheck.RetirementDirectory, $recheck.CaptureArchiveDirectory,
        $recheck.BackendStdoutPath, $recheck.BackendStderrPath
    )
    foreach ($component in $components) {
        $state = Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $component
        if (-not $state.Exists) { throw "S150 controlled backend output component is absent: $component" }
    }
    $archiveState = Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $recheck.CaptureArchiveDirectory
    if (($archiveState.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
        throw "S150 capture-archive is not a directory: $($recheck.CaptureArchiveDirectory)"
    }
    foreach ($backendPath in @($recheck.BackendStdoutPath, $recheck.BackendStderrPath)) {
        $item = Get-Item -LiteralPath $backendPath -Force -ErrorAction Stop
        if ($item.PSIsContainer) { throw "S150 backend output is not an ordinary file: $backendPath" }
        if ($RequireEmpty -and [int64]$item.Length -ne 0) {
            throw "S150 controlled backend output is not empty: $backendPath ($($item.Length) bytes)"
        }
    }
    return $recheck
}

# ---- Task 4: continuous no-clobber identity anchors ----

$script:S150OutputAnchorRoles = @('LauncherStdout', 'LauncherStderr', 'BackendStdout', 'BackendStderr')

function New-S150SuccessorOutputAnchorState {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$PathContract)
    $roleMap = [ordered]@{
        LauncherStdout = $PathContract.LauncherStdoutPath
        LauncherStderr = $PathContract.LauncherStderrPath
        BackendStdout = $PathContract.BackendStdoutPath
        BackendStderr = $PathContract.BackendStderrPath
    }
    $items = New-Object 'System.Collections.Generic.List[object]'
    foreach ($role in $script:S150OutputAnchorRoles) {
        $items.Add([pscustomobject][ordered]@{
            Role = $role
            Path = [string]$roleMap[$role]
            IdentityStream = $null
            TerminalLease = $null
            TerminalReceipt = $null
        })
    }
    return [pscustomobject][ordered]@{ Items = $items.ToArray() }
}

function Open-S150SuccessorCreateNewIdentityAnchors {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$State,
        [Parameter(Mandatory = $true)][string]$PinnedBaseDirectory
    )
    # Prevalidate all four paths (absent + component-no-reparse) BEFORE the first
    # file is created, so a single pre-existing/reparse leaf creates nothing.
    foreach ($item in $State.Items) {
        $full = [IO.Path]::GetFullPath($item.Path)
        [void](Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $full)
        if (Test-Path -LiteralPath $full) { throw "S150 identity anchor path already exists: $full" }
    }
    foreach ($item in $State.Items) {
        $full = [IO.Path]::GetFullPath($item.Path)
        [void](Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $full)
        if (Test-Path -LiteralPath $full) { throw "S150 identity anchor path appeared before create: $full" }
        $creator = [IO.File]::Open($full, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
        try {
            $creator.Flush($true)
            # Open the persistent read-only identity handle WHILE the creator is
            # still open, so there is no unanchored close/reopen interval.
            $identity = [IO.File]::Open($full, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            $item.IdentityStream = $identity
        } finally { $creator.Dispose() }
    }
}

function Open-S150SuccessorExistingIdentityAnchors {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$State,
        [Parameter(Mandatory = $true)][string[]]$Roles,
        [Parameter(Mandatory = $true)][string]$PinnedBaseDirectory
    )
    foreach ($role in $Roles) {
        $item = $null
        foreach ($candidate in $State.Items) {
            if ($candidate.Role -ceq $role) { $item = $candidate; break }
        }
        if ($null -eq $item) { throw "S150 unknown output anchor role: $role" }
        $full = [IO.Path]::GetFullPath($item.Path)
        $pathState = Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $full
        if (-not $pathState.Exists) { throw "S150 existing identity anchor role is absent: $role ($full)" }
        if (($pathState.Attributes -band [IO.FileAttributes]::Directory) -ne 0) {
            throw "S150 existing identity anchor is not a file: $full"
        }
        $identity = [IO.File]::Open($full, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        $item.IdentityStream = $identity
    }
}

function Close-S150SuccessorOutputAnchorState {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$State)
    if ($null -eq $State -or $null -eq $State.Items) { return }
    $reversed = @($State.Items)
    [Array]::Reverse($reversed)
    # Terminal leases are disposed before identity anchors, in reverse role order.
    foreach ($item in $reversed) {
        if ($null -ne $item.TerminalLease) { $item.TerminalLease.Dispose(); $item.TerminalLease = $null }
    }
    foreach ($item in $reversed) {
        if ($null -ne $item.IdentityStream) { $item.IdentityStream.Dispose(); $item.IdentityStream = $null }
    }
}

# ---- Task 4: writer-denying terminal launcher-output leases ----

function Open-S150SuccessorTerminalOutputLease {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Item,
        [ValidateRange(1, 33554432)][int64]$MaxOutputBytes = 33554432,
        [ValidateRange(1, 2000)][int]$TimeoutMilliseconds = 2000,
        [ValidateRange(1, 25)][int]$RetryMilliseconds = 25,
        [scriptblock]$AttemptObserver
    )
    # Repeat the bounds inside the function so reflection/dynamic invocation cannot
    # broaden the ceiling, deadline, or retry policy.
    if ($MaxOutputBytes -lt 1 -or $MaxOutputBytes -gt 33554432) { throw 'S150 terminal lease MaxOutputBytes is out of range.' }
    if ($TimeoutMilliseconds -lt 1 -or $TimeoutMilliseconds -gt 2000) { throw 'S150 terminal lease TimeoutMilliseconds is out of range.' }
    if ($RetryMilliseconds -lt 1 -or $RetryMilliseconds -gt 25) { throw 'S150 terminal lease RetryMilliseconds is out of range.' }

    $full = [IO.Path]::GetFullPath($Item.Path)
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    $lease = $null
    while ($true) {
        $elapsed = [int64]$stopwatch.ElapsedMilliseconds
        if ($elapsed -ge $TimeoutMilliseconds) { break }
        if ($null -ne $AttemptObserver) { & $AttemptObserver $elapsed | Out-Null }
        try {
            # The only proof of writer absence: a held Read/FileShare.Read open.
            $lease = [IO.File]::Open($full, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            break
        } catch [IO.IOException] {
            $lease = $null
            $remaining = $TimeoutMilliseconds - [int64]$stopwatch.ElapsedMilliseconds
            if ($remaining -le 0) { break }
            $sleep = [Math]::Min($RetryMilliseconds, $remaining)
            if ($sleep -gt 0) { Start-Sleep -Milliseconds $sleep }
        }
    }
    if ($null -eq $lease) { throw "S150 terminal output lease deadline expired (writer still present): $full" }

    try {
        $length = [int64]$lease.Length
        if ($length -gt $MaxOutputBytes) {
            throw "S150 terminal output exceeds the ceiling: $full ($length > $MaxOutputBytes)"
        }
        $position = $lease.Position
        [void]$lease.Seek(0, [IO.SeekOrigin]::Begin)
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try { $sha = ([BitConverter]::ToString($algorithm.ComputeHash($lease))).Replace('-', '') }
        finally { $algorithm.Dispose() }
        [void]$lease.Seek($position, [IO.SeekOrigin]::Begin)
        $info = [IO.FileInfo]::new($full); $info.Refresh()
        $receipt = [pscustomobject][ordered]@{
            path = $full
            size = $length
            sha256 = $sha
            creationUtcTicks = [int64]$info.CreationTimeUtc.Ticks
            lastWriteUtcTicks = [int64]$info.LastWriteTimeUtc.Ticks
            terminal = $true
            lease = 'Read/FileShare.Read'
            recordedUtc = [datetime]::UtcNow.ToString('o')
        }
        $Item.TerminalLease = $lease
        $Item.TerminalReceipt = $receipt
        return $receipt
    } catch {
        if ($null -ne $lease) { $lease.Dispose() }
        $Item.TerminalLease = $null
        throw
    }
}

function Confirm-S150SuccessorTerminalOutputLease {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Item,
        [Parameter(Mandatory = $true)][object]$ExpectedReceipt
    )
    $lease = $Item.TerminalLease
    if ($null -eq $lease) { throw 'S150 terminal output lease is not held.' }
    $position = $lease.Position
    [void]$lease.Seek(0, [IO.SeekOrigin]::Begin)
    $length = [int64]$lease.Length
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { $sha = ([BitConverter]::ToString($algorithm.ComputeHash($lease))).Replace('-', '') }
    finally { $algorithm.Dispose() }
    [void]$lease.Seek($position, [IO.SeekOrigin]::Begin)
    $full = [IO.Path]::GetFullPath($Item.Path)
    $info = [IO.FileInfo]::new($full); $info.Refresh()
    if ($length -ne [int64]$ExpectedReceipt.size -or
        $sha -cne [string]$ExpectedReceipt.sha256 -or
        [int64]$info.CreationTimeUtc.Ticks -ne [int64]$ExpectedReceipt.creationUtcTicks -or
        [int64]$info.LastWriteTimeUtc.Ticks -ne [int64]$ExpectedReceipt.lastWriteUtcTicks) {
        throw "S150 terminal output lease confirmation drifted: $full"
    }
}
