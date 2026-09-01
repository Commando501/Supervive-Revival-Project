param(
    [ValidateSet('FrozenRed', 'PathContract', 'Anchors', 'TerminalLease', 'PartialSeal',
        'ProcessMatrix', 'LauncherLoadIsolation', 'LauncherSource', 'Full')][string]$Section = 'Full',
    [string]$FixtureExe
)

# S150 successor output-ownership tests (real NTFS files and processes).
#
# Sections are added task by task: Task 4 = FrozenRed, PathContract, Anchors,
# TerminalLease, PartialSeal, ProcessMatrix, Full. Task 5 = LauncherLoadIsolation
# and LauncherSource. Every expectation is hand-derived; the historical defect is
# reproduced with real files/processes rather than asserted from prose.

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

$captureHelper = Join-Path $repo 'configs\s150-capture-generation.ps1'
$s149Helper = Join-Path $repo 'configs\s149-bind-gate.ps1'
$successorHelper = Join-Path $repo 'configs\s150-successor-evidence.ps1'
$launcher = Join-Path $repo 'configs\launch-redirect.ps1'
$frozenController = Join-Path $repo '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1'
$captureHelperSha = '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866'
$s149HelperSha = '14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA'
$frozenControllerSha = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'
$emptySha = 'E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855'

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "ASSERT FAILED: $Message" }
}
function Assert-StrEq([string]$Actual, [string]$Expected, [string]$Message) {
    if ($Actual -cne $Expected) { throw "ASSERT FAILED: $Message (actual='$Actual' expected='$Expected')" }
}
function Assert-IntEq($Actual, $Expected, [string]$Message) {
    if ([int64]$Actual -ne [int64]$Expected) { throw "ASSERT FAILED: $Message (actual=$Actual expected=$Expected)" }
}
function Assert-Throws([scriptblock]$Action, [string]$Message) {
    $threw = $false
    try { & $Action } catch { $threw = $true }
    Assert-True $threw "$Message : expected a throw"
}
function Get-Sha256Upper([byte[]]$Bytes) {
    $a = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($a.ComputeHash($Bytes))).Replace('-', '') }
    finally { $a.Dispose() }
}
function Get-FileSha256Held([string]$Path) {
    $s = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $a = [Security.Cryptography.SHA256]::Create()
        try { return ([BitConverter]::ToString($a.ComputeHash($s))).Replace('-', '') } finally { $a.Dispose() }
    } finally { $s.Dispose() }
}
function New-TempRoot([string]$Prefix) {
    $root = Join-Path $repo ('.superpowers\temp\' + $Prefix + '-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($root) | Out-Null
    return $root
}
function Remove-TempRoot([string]$Root) {
    $tempBase = [IO.Path]::GetFullPath((Join-Path $repo '.superpowers\temp'))
    $full = [IO.Path]::GetFullPath($Root)
    if (-not $full.StartsWith($tempBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "refusing to remove temp root outside .superpowers\temp: $full"
    }
    if (($([IO.File]::GetAttributes($full)) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "temp root is a reparse point: $full"
    }
    Remove-Item -LiteralPath $full -Recurse -Force
}
function Write-CreateNewBytes([string]$Path, [byte[]]$Bytes) {
    $s = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { if ($Bytes.Length -gt 0) { $s.Write($Bytes, 0, $Bytes.Length) }; $s.Flush($true) } finally { $s.Dispose() }
}
function Assert-FrozenControllerUnchanged {
    Assert-StrEq (Get-FileSha256Held $frozenController) $frozenControllerSha 'frozen Flight 2 controller unchanged'
}

# ---- FrozenRed: characterize the historical two-sample quiet defect ----
function Invoke-FrozenRedSuite {
    Assert-FrozenControllerUnchanged

    # 1. Static: the PRE-SUCCESSOR controlled launcher (from the immutable
    #    historical baseline, not the possibly-edited live file) redirects only
    #    stderr to docs/server.out.log and has no distinct backend stdout redirect.
    $frozenBaselineJson = Join-Path $repo 'docs\s150-successor-historical-baseline.json'
    $frozenBaseBytes = [Convert]::FromBase64String((Get-Content -LiteralPath $frozenBaselineJson -Raw | ConvertFrom-Json).preEditLauncherRaw.base64)
    $src = [Text.Encoding]::UTF8.GetString($frozenBaseBytes)
    Assert-True ($src -match '(?ms)Start-Process -FilePath \$agsExe .*?-RedirectStandardError \$srvOut -PassThru') `
        'controlled backend redirects only stderr to $srvOut'
    $controlledBlock = [regex]::Match($src, '(?ms)Assert-S150CertificateArtifactsAbsent.*?-RedirectStandardError \$srvOut -PassThru')
    Assert-True $controlledBlock.Success 'controlled StartBackend block located'
    Assert-True ($controlledBlock.Value -notmatch 'RedirectStandardOutput') `
        'controlled backend has NO distinct stdout redirect (the defect)'
    Assert-True ($src -match "\`$srvOut\s*=\s*Join-Path[^\n]*server\.out\.log") `
        'controlled stderr sink is docs/server.out.log'

    # 2. Dynamic: two equal 50 ms samples declare "stable" while a real delayed
    #    descendant append then changes the final bytes.
    $root = New-TempRoot 's150fr'
    try {
        $f = Join-Path $root 'quiet.stdout.log'
        Write-CreateNewBytes $f ([Text.Encoding]::ASCII.GetBytes('launcher-prefix-line' + "`n"))
        $job = Start-Job -ScriptBlock {
            param($p)
            Start-Sleep -Milliseconds 1500
            $s = [IO.File]::Open($p, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
            try { [void]$s.Seek(0, [IO.SeekOrigin]::End); $b = [Text.Encoding]::ASCII.GetBytes('#2 GET /healthz -> 200' + "`n"); $s.Write($b, 0, $b.Length); $s.Flush($true) }
            finally { $s.Dispose() }
        } -ArgumentList $f
        try {
            $sample1 = Get-FileSha256Held $f
            Start-Sleep -Milliseconds 50
            $sample2 = Get-FileSha256Held $f
            Assert-StrEq $sample1 $sample2 'old two-sample logic sees a stable prefix'
            $prefixHash = $sample1
            Wait-Job $job -Timeout 15 | Out-Null
            $finalHash = Get-FileSha256Held $f
            Assert-True ($prefixHash -cne $finalHash) 'quiet two-sample prefix hash differs from the final file hash (defect reproduced)'
        } finally { Remove-Job $job -Force }
    } finally { Remove-TempRoot $root }

    Assert-FrozenControllerUnchanged
    Write-Output 'PASS s150_successor_output_ownership_test FrozenRed'
}

# ---- PathContract ----
function Invoke-PathContractSuite {
    $root = New-TempRoot 's150pc'
    try {
        $retirement = Join-Path $root 'retire'
        [IO.Directory]::CreateDirectory($retirement) | Out-Null
        $archive = Join-Path $retirement 'capture-archive'
        [IO.Directory]::CreateDirectory($archive) | Out-Null

        $contract = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $archive -ExpectedRetirementDirectory $retirement
        Assert-StrEq ([IO.Path]::GetFileName($contract.CaptureArchiveDirectory)) 'capture-archive' 'archive leaf'
        Assert-StrEq $contract.RetirementDirectory ([IO.Path]::GetFullPath($retirement)) 'retirement dir'
        Assert-StrEq ([IO.Path]::GetFileName($contract.LauncherStdoutPath)) 'launcher.stdout.log' 'launcher stdout leaf'
        Assert-StrEq ([IO.Path]::GetFileName($contract.LauncherStderrPath)) 'launcher.stderr.log' 'launcher stderr leaf'
        Assert-StrEq ([IO.Path]::GetFileName($contract.BackendStdoutPath)) 'backend.stdout.log' 'backend stdout leaf'
        Assert-StrEq ([IO.Path]::GetFileName($contract.BackendStderrPath)) 'backend.stderr.log' 'backend stderr leaf'
        foreach ($p in @($contract.LauncherStdoutPath, $contract.LauncherStderrPath, $contract.BackendStdoutPath, $contract.BackendStderrPath)) {
            Assert-True ($p.StartsWith([IO.Path]::GetFullPath($retirement) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) "path inside retirement: $p"
        }

        # nonempty launcher streams + empty backend streams pass -RequireEmpty
        Write-CreateNewBytes $contract.LauncherStdoutPath ([Text.Encoding]::ASCII.GetBytes('launcher output'))
        Write-CreateNewBytes $contract.LauncherStderrPath ([byte[]]::new(0))
        Write-CreateNewBytes $contract.BackendStdoutPath ([byte[]]::new(0))
        Write-CreateNewBytes $contract.BackendStderrPath ([byte[]]::new(0))
        Assert-S150SuccessorControlledBackendOutputState -PathContract $contract -PinnedBaseDirectory $root -RequireEmpty | Out-Null

        # nonempty backend stdout refuses -RequireEmpty
        $root2 = New-TempRoot 's150pc2'
        try {
            $retire2 = Join-Path $root2 'retire'; [IO.Directory]::CreateDirectory($retire2) | Out-Null
            $arch2 = Join-Path $retire2 'capture-archive'; [IO.Directory]::CreateDirectory($arch2) | Out-Null
            $c2 = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch2 -ExpectedRetirementDirectory $retire2
            Write-CreateNewBytes $c2.BackendStdoutPath ([Text.Encoding]::ASCII.GetBytes('leftover'))
            Write-CreateNewBytes $c2.BackendStderrPath ([byte[]]::new(0))
            Assert-Throws { Assert-S150SuccessorControlledBackendOutputState -PathContract $c2 -PinnedBaseDirectory $root2 -RequireEmpty } 'nonempty backend stdout refuses'
        } finally { Remove-TempRoot $root2 }

        # wrong archive leaf refuses in the contract itself
        $wrongArchive = Join-Path $retirement 'not-capture-archive'
        [IO.Directory]::CreateDirectory($wrongArchive) | Out-Null
        Assert-Throws { Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $wrongArchive -ExpectedRetirementDirectory $retirement } 'wrong archive leaf refuses'

        # archive whose parent is not the expected retirement refuses
        $otherRetire = Join-Path $root 'other'
        [IO.Directory]::CreateDirectory($otherRetire) | Out-Null
        Assert-Throws { Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $archive -ExpectedRetirementDirectory $otherRetire } 'archive parent mismatch refuses'
    } finally { Remove-TempRoot $root }
    Write-Output 'PASS s150_successor_output_ownership_test PathContract'
}

# ---- Anchors: continuous no-clobber identity anchors ----
function Invoke-AnchorsSuite {
    # 1. Fresh four-role anchors: sibling paths, writer coexistence, delete/rename denial, release after close.
    $root = New-TempRoot 's150an'
    try {
        $retirement = Join-Path $root 'retire'; [IO.Directory]::CreateDirectory($retirement) | Out-Null
        $archive = Join-Path $retirement 'capture-archive'; [IO.Directory]::CreateDirectory($archive) | Out-Null
        $contract = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $archive -ExpectedRetirementDirectory $retirement
        $state = New-S150SuccessorOutputAnchorState -PathContract $contract
        Assert-StrEq (@($state.Items | ForEach-Object { $_.Role }) -join ',') 'LauncherStdout,LauncherStderr,BackendStdout,BackendStderr' 'anchor role order'
        Open-S150SuccessorCreateNewIdentityAnchors -State $state -PinnedBaseDirectory $root
        try {
            foreach ($item in $state.Items) {
                Assert-True (Test-Path -LiteralPath $item.Path) "anchor created: $($item.Role)"
                Assert-True ($null -ne $item.IdentityStream) "identity stream held: $($item.Role)"
            }
            $bso = $contract.BackendStdoutPath
            $w = [IO.File]::Open($bso, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
            try { $w.WriteByte(0x61); $w.Flush($true) } finally { $w.Dispose() }
            Assert-Throws { [IO.File]::Delete($bso) } 'delete denied while anchored'
            Assert-Throws { [IO.File]::Move($bso, (Join-Path $retirement 'moved.log')) } 'rename denied while anchored'
        } finally { Close-S150SuccessorOutputAnchorState -State $state }
        [IO.File]::Delete($contract.BackendStdoutPath)
        Assert-True (-not (Test-Path -LiteralPath $contract.BackendStdoutPath)) 'backend stdout deletable after close'
        Close-S150SuccessorOutputAnchorState -State $state
    } finally { Remove-TempRoot $root }

    # 2. No-clobber: a pre-existing sentinel refuses, all-path prevalidation before first create.
    $root2 = New-TempRoot 's150an2'
    try {
        $retire2 = Join-Path $root2 'retire'; [IO.Directory]::CreateDirectory($retire2) | Out-Null
        $arch2 = Join-Path $retire2 'capture-archive'; [IO.Directory]::CreateDirectory($arch2) | Out-Null
        $c2 = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch2 -ExpectedRetirementDirectory $retire2
        $sentinel = [Text.Encoding]::ASCII.GetBytes('pre-existing sentinel')
        Write-CreateNewBytes $c2.BackendStderrPath $sentinel
        $s2 = New-S150SuccessorOutputAnchorState -PathContract $c2
        Assert-Throws { Open-S150SuccessorCreateNewIdentityAnchors -State $s2 -PinnedBaseDirectory $root2 } 'pre-existing anchor refuses'
        Close-S150SuccessorOutputAnchorState -State $s2
        Assert-StrEq (Get-Sha256Upper ([IO.File]::ReadAllBytes($c2.BackendStderrPath))) (Get-Sha256Upper $sentinel) 'sentinel unchanged'
        foreach ($p in @($c2.LauncherStdoutPath, $c2.LauncherStderrPath, $c2.BackendStdoutPath)) {
            Assert-True (-not (Test-Path -LiteralPath $p)) "not created due to prevalidation: $([IO.Path]::GetFileName($p))"
        }
    } finally { Remove-TempRoot $root2 }

    # 3. A real junction (reparse) component refuses.
    $root3 = New-TempRoot 's150an3'
    try {
        $realTarget = Join-Path $root3 'real'; [IO.Directory]::CreateDirectory($realTarget) | Out-Null
        $jlink = Join-Path $root3 'jlink'
        New-Item -ItemType Junction -Path $jlink -Target $realTarget | Out-Null
        $retire3 = Join-Path $jlink 'retire'; [IO.Directory]::CreateDirectory($retire3) | Out-Null
        $arch3 = Join-Path $retire3 'capture-archive'; [IO.Directory]::CreateDirectory($arch3) | Out-Null
        $c3 = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch3 -ExpectedRetirementDirectory $retire3
        $s3 = New-S150SuccessorOutputAnchorState -PathContract $c3
        Assert-Throws { Open-S150SuccessorCreateNewIdentityAnchors -State $s3 -PinnedBaseDirectory $root3 } 'junction component refuses'
        Close-S150SuccessorOutputAnchorState -State $s3
    } finally { Remove-TempRoot $root3 }

    # 4. Existing anchors (Arm boundary): reopen existing roles, refuse a missing role.
    $root4 = New-TempRoot 's150an4'
    try {
        $retire4 = Join-Path $root4 'retire'; [IO.Directory]::CreateDirectory($retire4) | Out-Null
        $arch4 = Join-Path $retire4 'capture-archive'; [IO.Directory]::CreateDirectory($arch4) | Out-Null
        $c4 = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch4 -ExpectedRetirementDirectory $retire4
        $s4 = New-S150SuccessorOutputAnchorState -PathContract $c4
        Open-S150SuccessorCreateNewIdentityAnchors -State $s4 -PinnedBaseDirectory $root4
        Close-S150SuccessorOutputAnchorState -State $s4
        $s4b = New-S150SuccessorOutputAnchorState -PathContract $c4
        try {
            Open-S150SuccessorExistingIdentityAnchors -State $s4b -Roles @('LauncherStdout', 'LauncherStderr', 'BackendStdout', 'BackendStderr') -PinnedBaseDirectory $root4
            foreach ($item in $s4b.Items) { Assert-True ($null -ne $item.IdentityStream) "existing anchor held: $($item.Role)" }
            Assert-Throws { [IO.File]::Delete($c4.BackendStdoutPath) } 'delete denied while existing anchor held'
        } finally { Close-S150SuccessorOutputAnchorState -State $s4b }
        [IO.File]::Delete($c4.LauncherStdoutPath)
        $s4c = New-S150SuccessorOutputAnchorState -PathContract $c4
        Assert-Throws { Open-S150SuccessorExistingIdentityAnchors -State $s4c -Roles @('LauncherStdout') -PinnedBaseDirectory $root4 } 'missing existing role refuses'
        Close-S150SuccessorOutputAnchorState -State $s4c
    } finally { Remove-TempRoot $root4 }

    Write-Output 'PASS s150_successor_output_ownership_test Anchors'
}

function New-LooseAnchorItem([string]$Role, [string]$Path) {
    return [pscustomobject][ordered]@{ Role = $Role; Path = $Path; IdentityStream = $null; TerminalLease = $null; TerminalReceipt = $null }
}
function Find-AnchorItem($State, [string]$Role) {
    foreach ($i in $State.Items) { if ($i.Role -ceq $Role) { return $i } }
    throw "no anchor role $Role"
}

# ---- TerminalLease: writer-denying terminal launcher receipts ----
function Invoke-TerminalLeaseSuite {
    $root = New-TempRoot 's150tl'
    try {
        # 1. closed writer permits a real Read/FileShare.Read lease; confirm re-hashes the held stream.
        $line = [Text.Encoding]::ASCII.GetBytes('terminal output line')
        $p1 = Join-Path $root 'a.log'; Write-CreateNewBytes $p1 $line
        $item1 = New-LooseAnchorItem 'LauncherStdout' $p1
        $r1 = Open-S150SuccessorTerminalOutputLease -Item $item1
        try {
            Assert-True $r1.terminal 'receipt terminal=true'
            Assert-StrEq $r1.lease 'Read/FileShare.Read' 'lease mode'
            Assert-IntEq $r1.size $line.Length 'lease size'
            Assert-StrEq $r1.sha256 (Get-Sha256Upper $line) 'lease sha'
            Confirm-S150SuccessorTerminalOutputLease -Item $item1 -ExpectedReceipt $r1
            Assert-Throws { [IO.File]::Open($p1, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite) } 'writer denied while lease held'
        } finally { if ($null -ne $item1.TerminalLease) { $item1.TerminalLease.Dispose() } }

        # 2. held writer refuses throughout the bounded 2000 ms policy; every attempt begins before the deadline.
        $p2 = Join-Path $root 'b.log'; Write-CreateNewBytes $p2 ([Text.Encoding]::ASCII.GetBytes('held'))
        $item2 = New-LooseAnchorItem 'LauncherStdout' $p2
        $writer = [IO.File]::Open($p2, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
        try {
            $attempts = New-Object 'System.Collections.Generic.List[int64]'
            $observer = { param($ms) $attempts.Add([int64]$ms) }.GetNewClosure()
            $sw = [Diagnostics.Stopwatch]::StartNew()
            Assert-Throws { Open-S150SuccessorTerminalOutputLease -Item $item2 -AttemptObserver $observer } 'held writer refuses lease at deadline'
            $sw.Stop()
            Assert-True ($sw.ElapsedMilliseconds -ge 2000) "refusal reached the 2000ms deadline (elapsed=$($sw.ElapsedMilliseconds))"
            Assert-True ($sw.ElapsedMilliseconds -le 8000) "refusal within 8000ms wall bound (elapsed=$($sw.ElapsedMilliseconds))"
            Assert-True ($attempts.Count -ge 2) "multiple retry attempts ($($attempts.Count))"
            foreach ($a in $attempts) { Assert-True ($a -lt 2000) "attempt $a began before deadline" }
            Assert-True ($null -eq $item2.TerminalLease) 'no lease stored on refusal'
        } finally { $writer.Dispose() }

        # 3. out-of-range parameters refuse before any open (zero attempts); boundary values are accepted.
        $p3 = Join-Path $root 'c.log'; Write-CreateNewBytes $p3 ([Text.Encoding]::ASCII.GetBytes('x'))
        foreach ($bad in @(
            @{ MaxOutputBytes = 0 }, @{ MaxOutputBytes = 33554433 },
            @{ TimeoutMilliseconds = 0 }, @{ TimeoutMilliseconds = 2001 },
            @{ RetryMilliseconds = 0 }, @{ RetryMilliseconds = 26 })) {
            $item3 = New-LooseAnchorItem 'LauncherStdout' $p3
            $counter = New-Object 'System.Collections.Generic.List[int64]'
            $obs = { param($ms) $counter.Add([int64]$ms) }.GetNewClosure()
            $callArgs = @{ Item = $item3; AttemptObserver = $obs } + $bad
            Assert-Throws { Open-S150SuccessorTerminalOutputLease @callArgs } "out-of-range param refuses: $($bad.Keys -join ',')"
            Assert-IntEq $counter.Count 0 "zero open attempts for out-of-range: $($bad.Keys -join ',')"
        }
        $item3b = New-LooseAnchorItem 'LauncherStdout' $p3
        $r3b = Open-S150SuccessorTerminalOutputLease -Item $item3b -MaxOutputBytes 1 -TimeoutMilliseconds 1 -RetryMilliseconds 1
        try { Assert-IntEq $r3b.size 1 'min-boundary parameters accepted' } finally { $item3b.TerminalLease.Dispose() }
        $item3c = New-LooseAnchorItem 'LauncherStdout' $p3
        $r3c = Open-S150SuccessorTerminalOutputLease -Item $item3c -MaxOutputBytes 33554432 -TimeoutMilliseconds 2000 -RetryMilliseconds 25
        try { Assert-True $r3c.terminal 'max-boundary parameters accepted' } finally { $item3c.TerminalLease.Dispose() }

        # 4. 32 MiB ceiling refusal.
        $p4 = Join-Path $root 'd.log'; Write-CreateNewBytes $p4 ([Text.Encoding]::ASCII.GetBytes('abcdef'))
        $item4 = New-LooseAnchorItem 'LauncherStdout' $p4
        Assert-Throws { Open-S150SuccessorTerminalOutputLease -Item $item4 -MaxOutputBytes 3 } 'output ceiling refusal'
        Assert-True ($null -eq $item4.TerminalLease) 'no lease stored on ceiling refusal'

        # 5. lease + identity anchor interplay.
        $retire5 = Join-Path $root 'retire5'; [IO.Directory]::CreateDirectory($retire5) | Out-Null
        $arch5 = Join-Path $retire5 'capture-archive'; [IO.Directory]::CreateDirectory($arch5) | Out-Null
        $c5 = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch5 -ExpectedRetirementDirectory $retire5
        $s5 = New-S150SuccessorOutputAnchorState -PathContract $c5
        Open-S150SuccessorCreateNewIdentityAnchors -State $s5 -PinnedBaseDirectory $root
        $ls = Find-AnchorItem $s5 'LauncherStdout'
        try {
            [void](Open-S150SuccessorTerminalOutputLease -Item $ls)
            Assert-Throws { [IO.File]::Open($ls.Path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite) } 'write denied while lease+anchor held'
            Assert-Throws { [IO.File]::Delete($ls.Path) } 'delete denied while lease+anchor held'
            $ls.TerminalLease.Dispose(); $ls.TerminalLease = $null
            $w = [IO.File]::Open($ls.Path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
            try { $w.WriteByte(0x61); $w.Flush($true) } finally { $w.Dispose() }
            Assert-Throws { [IO.File]::Delete($ls.Path) } 'delete still denied by anchor after lease closed'
        } finally { Close-S150SuccessorOutputAnchorState -State $s5 }
        [IO.File]::Delete($ls.Path)
        Assert-True (-not (Test-Path -LiteralPath $ls.Path)) 'deletable after anchor closed'

        # 6. confirmation drift refuses; a correct receipt confirms.
        $p6 = Join-Path $root 'e.log'; Write-CreateNewBytes $p6 ([Text.Encoding]::ASCII.GetBytes('drift-test'))
        $item6 = New-LooseAnchorItem 'LauncherStdout' $p6
        $r6 = Open-S150SuccessorTerminalOutputLease -Item $item6
        try {
            $wrong = [pscustomobject]@{ size = [int64]999; sha256 = ('0' * 64); creationUtcTicks = $r6.creationUtcTicks; lastWriteUtcTicks = $r6.lastWriteUtcTicks }
            Assert-Throws { Confirm-S150SuccessorTerminalOutputLease -Item $item6 -ExpectedReceipt $wrong } 'confirmation drift refuses'
            Confirm-S150SuccessorTerminalOutputLease -Item $item6 -ExpectedReceipt $r6
        } finally { $item6.TerminalLease.Dispose() }
    } finally { Remove-TempRoot $root }
    Write-Output 'PASS s150_successor_output_ownership_test TerminalLease'
}

# ---- fixture/process helpers ----
$protectedNames = @('ags', 'SUPERVIVE-Win64-Shipping', 'usmapdump', 'go', 'inject', 'crashpad_handler')
function Get-ProtectedCensus {
    $sum = 0
    foreach ($n in $protectedNames) { $sum += @(Get-Process -Name $n -ErrorAction SilentlyContinue).Count }
    return $sum
}
function Get-QuotedArgString([string[]]$ArgArray) {
    return ($ArgArray | ForEach-Object { if ($_ -eq '' -or $_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
}
function Start-OutputFixture {
    param([string]$FixtureExe, [string]$PidReceipt, [int]$DelayMs, [int]$HoldMs,
        [string]$StdoutB64, [string]$StderrB64, [string]$RedirectStdout, [string]$RedirectStderr)
    $argStr = Get-QuotedArgString @('--pid-file', $PidReceipt, '--delay-ms', [string]$DelayMs,
        '--hold-ms', [string]$HoldMs, '--stdout-ascii', $StdoutB64, '--stderr-ascii', $StderrB64)
    $sp = @{ FilePath = $FixtureExe; ArgumentList = $argStr; PassThru = $true }
    if ($RedirectStdout) { $sp['RedirectStandardOutput'] = $RedirectStdout }
    if ($RedirectStderr) { $sp['RedirectStandardError'] = $RedirectStderr }
    return Start-Process @sp
}
function Wait-PidReceipt([string]$Path, [int]$TimeoutMs = 8000) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        if (Test-Path -LiteralPath $Path) { return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json) }
        Start-Sleep -Milliseconds 40
    }
    throw "pid receipt not written within ${TimeoutMs}ms: $Path"
}
function Stop-FixtureByIdentity {
    param($Proc, $Receipt, [string]$FixtureExe)
    $live = Get-Process -Id $Proc.Id -ErrorAction Stop
    if ($live.Path -ine $FixtureExe) { throw "fixture path mismatch: $($live.Path)" }
    if ([int64]$live.StartTime.ToUniversalTime().Ticks -ne [int64]$Receipt.creationUtcTicks) { throw 'fixture start-time mismatch' }
    if ([int64]$Receipt.pid -ne [int64]$Proc.Id) { throw 'fixture pid mismatch' }
    $exeSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $FixtureExe).Hash
    if ([string]::IsNullOrEmpty($exeSha)) { throw 'fixture exe unhashable' }
    Stop-Process -Id $Proc.Id -Force
    $Proc.WaitForExit(5000) | Out-Null
}
function Assert-PidAbsentStable([int]$ProcessId) {
    $a = @(Get-Process -Id $ProcessId -ErrorAction SilentlyContinue).Count
    Start-Sleep -Milliseconds 80
    $b = @(Get-Process -Id $ProcessId -ErrorAction SilentlyContinue).Count
    Assert-IntEq $a 0 'absence sample 1'
    Assert-IntEq $b 0 'absence sample 2'
}
function Stop-FixtureByReceipt($Receipt, [string]$FixtureExe) {
    $live = Get-Process -Id ([int]$Receipt.pid) -ErrorAction Stop
    if ($live.Path -ine $FixtureExe) { throw "fixture path mismatch: $($live.Path)" }
    if ([int64]$live.StartTime.ToUniversalTime().Ticks -ne [int64]$Receipt.creationUtcTicks) { throw 'fixture start-time mismatch' }
    [void](Get-FileHash -Algorithm SHA256 -LiteralPath $FixtureExe)
    Stop-Process -Id ([int]$Receipt.pid) -Force
    $live.WaitForExit(5000) | Out-Null
}
function Wait-FileNonEmpty([string]$Path, [int]$TimeoutMs = 5000) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        if ((Test-Path -LiteralPath $Path) -and (Get-Item -LiteralPath $Path).Length -gt 0) { return $true }
        Start-Sleep -Milliseconds 40
    }
    return ((Test-Path -LiteralPath $Path) -and (Get-Item -LiteralPath $Path).Length -gt 0)
}

# ---- ProcessMatrix: real NTFS output ownership across launch shapes ----
function Invoke-ProcessMatrixSuite([string]$FixtureExe) {
    Assert-True (Test-Path -LiteralPath $FixtureExe) "fixture exe exists: $FixtureExe"
    $fx = (Resolve-Path -LiteralPath $FixtureExe).Path
    $ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    $fakeLauncher = (Resolve-Path -LiteralPath (Join-Path $repo 'tools\sigbypass-mod\tests\fixtures\s150_output_fake_launcher.ps1')).Path
    $censusBefore = Get-ProtectedCensus

    function New-Retirement([string]$Prefix) {
        $root = New-TempRoot $Prefix
        $retire = Join-Path $root 'retire'; [IO.Directory]::CreateDirectory($retire) | Out-Null
        $arch = Join-Path $retire 'capture-archive'; [IO.Directory]::CreateDirectory($arch) | Out-Null
        $contract = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch -ExpectedRetirementDirectory $retire
        return [pscustomobject]@{ Root = $root; Retire = $retire; Contract = $contract }
    }

    # 1. Isolated backend (the fix): distinct backend sinks; launcher streams remain terminal.
    $a = New-Retirement 's150pmA'; $procA = $null
    try {
        $state = New-S150SuccessorOutputAnchorState -PathContract $a.Contract
        Open-S150SuccessorCreateNewIdentityAnchors -State $state -PinnedBaseDirectory $a.Root
        try {
            $pidr = Join-Path $a.Root 'fixture.pid.json'
            $procA = Start-OutputFixture -FixtureExe $fx -PidReceipt $pidr -DelayMs 80 -HoldMs 60000 `
                -StdoutB64 ([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('isolated-out'))) `
                -StderrB64 ([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('isolated-err'))) `
                -RedirectStdout $a.Contract.BackendStdoutPath -RedirectStderr $a.Contract.BackendStderrPath
            $receipt = Wait-PidReceipt $pidr
            Assert-True (@(Get-Process -Id $procA.Id -ErrorAction SilentlyContinue).Count -eq 1) 'isolated backend fixture alive'
            [void](Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'LauncherStdout'))
            [void](Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'LauncherStderr'))
            Assert-True (Wait-FileNonEmpty $a.Contract.BackendStdoutPath) 'backend stdout received the fixture output'
            Assert-True (Wait-FileNonEmpty $a.Contract.BackendStderrPath) 'backend stderr received the fixture output (mutable while live)'
            Stop-FixtureByIdentity -Proc $procA -Receipt $receipt -FixtureExe $fx
            Assert-PidAbsentStable $procA.Id
            $bsoFinal = Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'BackendStdout')
            Assert-True ($bsoFinal.size -gt 0) 'backend stdout finalized cleanup-only after stop'
            [void](Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'BackendStderr'))
        } finally { Close-S150SuccessorOutputAnchorState -State $state }
    } finally {
        if ($null -ne $procA -and -not $procA.HasExited) { Stop-Process -Id $procA.Id -Force -ErrorAction SilentlyContinue; $procA.WaitForExit(5000) | Out-Null }
        Remove-TempRoot $a.Root
    }

    # 2. Held backend writer (the defect): a backend holding launcher stdout refuses sealing.
    $b = New-Retirement 's150pmB'; $procB = $null
    try {
        $state = New-S150SuccessorOutputAnchorState -PathContract $b.Contract
        Open-S150SuccessorCreateNewIdentityAnchors -State $state -PinnedBaseDirectory $b.Root
        try {
            $pidr = Join-Path $b.Root 'fixture.pid.json'
            $procB = Start-OutputFixture -FixtureExe $fx -PidReceipt $pidr -DelayMs 80 -HoldMs 60000 `
                -StdoutB64 ([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('leaked-to-launcher'))) -StderrB64 '-' `
                -RedirectStdout $b.Contract.LauncherStdoutPath -RedirectStderr $b.Contract.BackendStderrPath
            $receipt = Wait-PidReceipt $pidr
            Assert-True (@(Get-Process -Id $procB.Id -ErrorAction SilentlyContinue).Count -eq 1) 'held backend fixture alive'
            Assert-Throws { Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'LauncherStdout') -TimeoutMilliseconds 500 } 'held launcher-stdout writer refuses sealing'
            [void](Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'LauncherStderr'))
            Stop-FixtureByIdentity -Proc $procB -Receipt $receipt -FixtureExe $fx
            Assert-PidAbsentStable $procB.Id
            [void](Open-S150SuccessorTerminalOutputLease -Item (Find-AnchorItem $state 'LauncherStdout'))
        } finally { Close-S150SuccessorOutputAnchorState -State $state }
    } finally {
        if ($null -ne $procB -and -not $procB.HasExited) { Stop-Process -Id $procB.Id -Force -ErrorAction SilentlyContinue; $procB.WaitForExit(5000) | Out-Null }
        Remove-TempRoot $b.Root
    }

    # 3. Native `&` GUI invocation returns while the fixture remains alive.
    $c = New-TempRoot 's150pmC'; $receiptC = $null
    try {
        $pidr = Join-Path $c 'fixture.pid.json'
        $argArr = @('--pid-file', $pidr, '--delay-ms', '80', '--hold-ms', '60000', '--stdout-ascii', '-', '--stderr-ascii', '-')
        $sw = [Diagnostics.Stopwatch]::StartNew()
        & $fx @argArr
        $elapsed = $sw.ElapsedMilliseconds
        Assert-True ($elapsed -lt 5000) "native & returned promptly (non-blocking GUI, elapsed=$elapsed)"
        $receiptC = Wait-PidReceipt $pidr
        Assert-True (@(Get-Process -Id ([int]$receiptC.pid) -ErrorAction SilentlyContinue).Count -eq 1) 'fixture remains alive after native & returned'
        Stop-FixtureByReceipt -Receipt $receiptC -FixtureExe $fx
        Assert-PidAbsentStable ([int]$receiptC.pid)
    } finally {
        if ($null -ne $receiptC) { $p = Get-Process -Id ([int]$receiptC.pid) -ErrorAction SilentlyContinue; if ($p) { Stop-Process -Id ([int]$receiptC.pid) -Force -ErrorAction SilentlyContinue; $p.WaitForExit(5000) | Out-Null } }
        Remove-TempRoot $c
    }

    # 4. Fake-launcher mode routing (exercises the three launcher shapes; content lands
    #    before the sandbox reaps the intermediate-launcher grandchild).
    foreach ($mode in @('IsolatedBackend', 'InheritedBackend', 'NativeGame')) {
        $m = New-Retirement 's150pmR'
        try {
            $pidr = Join-Path $m.Root 'fixture.pid.json'
            $ls = $m.Contract.LauncherStdoutPath; $le = $m.Contract.LauncherStderrPath
            $bo = $m.Contract.BackendStdoutPath; $be = $m.Contract.BackendStderrPath
            $flArgs = Get-QuotedArgString @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $fakeLauncher,
                '-Mode', $mode, '-WriterExe', $fx, '-BackendStdoutPath', $bo, '-BackendStderrPath', $be,
                '-PidReceiptPath', $pidr, '-DelayMs', '60', '-HoldMs', '3000',
                '-StdoutB64', ([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('route-out'))),
                '-StderrB64', ([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('route-err'))))
            Start-Process -FilePath $ps -ArgumentList $flArgs -RedirectStandardOutput $ls -RedirectStandardError $le -Wait
            if ($mode -eq 'IsolatedBackend') {
                Assert-True (Wait-FileNonEmpty $bo) 'IsolatedBackend routes stdout to backend.stdout'
                Assert-True (Wait-FileNonEmpty $be) 'IsolatedBackend routes stderr to backend.stderr'
                Assert-IntEq (Get-Item -LiteralPath $ls).Length 0 'IsolatedBackend leaves launcher stdout empty (the fix)'
            } elseif ($mode -eq 'InheritedBackend') {
                Assert-True (Wait-FileNonEmpty $ls) 'InheritedBackend inherits launcher stdout (the defect)'
                Assert-True (Wait-FileNonEmpty $be) 'InheritedBackend routes stderr to backend.stderr'
            } else {
                Assert-True (Wait-FileNonEmpty $ls) 'NativeGame inherits launcher stdout'
                Assert-True (Wait-FileNonEmpty $le) 'NativeGame inherits launcher stderr'
            }
            if (Test-Path -LiteralPath $pidr) {
                $r = Get-Content -LiteralPath $pidr -Raw | ConvertFrom-Json
                $p = Get-Process -Id ([int]$r.pid) -ErrorAction SilentlyContinue
                if ($p) { Stop-Process -Id ([int]$r.pid) -Force -ErrorAction SilentlyContinue; $p.WaitForExit(5000) | Out-Null }
            }
        } finally { Remove-TempRoot $m.Root }
    }

    # 5. Pre-existing and reparse paths refuse with zero child starts.
    $d = New-Retirement 's150pmD'
    try {
        Write-CreateNewBytes $d.Contract.BackendStdoutPath ([Text.Encoding]::ASCII.GetBytes('leftover'))
        $state = New-S150SuccessorOutputAnchorState -PathContract $d.Contract
        Assert-Throws { Open-S150SuccessorCreateNewIdentityAnchors -State $state -PinnedBaseDirectory $d.Root } 'pre-existing backend path refuses (zero child starts)'
        Close-S150SuccessorOutputAnchorState -State $state
    } finally { Remove-TempRoot $d.Root }
    $e = New-TempRoot 's150pmE'
    try {
        $realTarget = Join-Path $e 'real'; [IO.Directory]::CreateDirectory($realTarget) | Out-Null
        $jlink = Join-Path $e 'jlink'; New-Item -ItemType Junction -Path $jlink -Target $realTarget | Out-Null
        $retireJ = Join-Path $jlink 'retire'; [IO.Directory]::CreateDirectory($retireJ) | Out-Null
        $archJ = Join-Path $retireJ 'capture-archive'; [IO.Directory]::CreateDirectory($archJ) | Out-Null
        $cj = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $archJ -ExpectedRetirementDirectory $retireJ
        $sj = New-S150SuccessorOutputAnchorState -PathContract $cj
        Assert-Throws { Open-S150SuccessorCreateNewIdentityAnchors -State $sj -PinnedBaseDirectory $e } 'reparse component refuses (zero child starts)'
        Close-S150SuccessorOutputAnchorState -State $sj
    } finally { Remove-TempRoot $e }

    Assert-IntEq (Get-ProtectedCensus) $censusBefore 'protected process census unchanged before/after'
    Write-Output 'PASS s150_successor_output_ownership_test ProcessMatrix'
}

# ---- PartialSeal: cleanup-only finalization after a partial seal ----
function Invoke-PartialSealSuite([string]$FixtureExe) {
    Assert-True (Test-Path -LiteralPath $FixtureExe) "fixture exe exists: $FixtureExe"
    $fx = (Resolve-Path -LiteralPath $FixtureExe).Path
    $censusBefore = Get-ProtectedCensus
    $root = New-TempRoot 's150ps'
    $proc = $null
    try {
        $retire = Join-Path $root 'retire'; [IO.Directory]::CreateDirectory($retire) | Out-Null
        $arch = Join-Path $retire 'capture-archive'; [IO.Directory]::CreateDirectory($arch) | Out-Null
        $contract = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch -ExpectedRetirementDirectory $retire
        $state = New-S150SuccessorOutputAnchorState -PathContract $contract
        Open-S150SuccessorCreateNewIdentityAnchors -State $state -PinnedBaseDirectory $root
        try {
            $pidReceipt = Join-Path $root 'fixture.pid.json'
            $bo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('backend-stdout-line'))
            $be = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('inherited-stderr-line'))
            # fixture holds launcher.stderr (writer) and backend.stdout (writer); launcher.stdout has no writer.
            $proc = Start-OutputFixture -FixtureExe $fx -PidReceipt $pidReceipt -DelayMs 100 -HoldMs 60000 `
                -StdoutB64 $bo -StderrB64 $be -RedirectStdout $contract.BackendStdoutPath -RedirectStderr $contract.LauncherStderrPath
            $receipt = Wait-PidReceipt $pidReceipt
            Assert-IntEq $receipt.pid $proc.Id 'fixture pid matches receipt'

            $lsItem = Find-AnchorItem $state 'LauncherStdout'
            $leItem = Find-AnchorItem $state 'LauncherStderr'
            $bsoItem = Find-AnchorItem $state 'BackendStdout'
            $bseItem = Find-AnchorItem $state 'BackendStderr'

            # 1-2. launcher stdout seals (no writer); launcher stderr sealing fails (fixture holds it).
            $stdoutSeal = Open-S150SuccessorTerminalOutputLease -Item $lsItem
            Assert-Throws { Open-S150SuccessorTerminalOutputLease -Item $leItem -TimeoutMilliseconds 500 -RetryMilliseconds 25 } 'launcher stderr sealing fails while fixture holds it'
            # 3. stdout lease remains held and re-confirms.
            Assert-True ($null -ne $lsItem.TerminalLease) 'stdout lease remains held after stderr seal failure'
            Confirm-S150SuccessorTerminalOutputLease -Item $lsItem -ExpectedReceipt $stdoutSeal

            # 4. synthetic failed launcher-result.json.
            $failed = Join-Path $retire 'launcher-result.json'
            $failedBytes = [Text.Encoding]::UTF8.GetBytes('{"failure":"partial-seal-cleanup"}')
            Write-CreateNewBytes $failed $failedBytes
            $failedSha = Get-Sha256Upper $failedBytes

            # 5-6. stop the exact fixture PID after identity revalidation; two stable absence samples.
            Stop-FixtureByIdentity -Proc $proc -Receipt $receipt -FixtureExe $fx
            Assert-PidAbsentStable $proc.Id

            # 7. seal launcher stderr (now no writer) and reconfirm stdout.
            $stderrSeal = Open-S150SuccessorTerminalOutputLease -Item $leItem
            Assert-True $stderrSeal.terminal 'launcher stderr sealed after cleanup'
            Confirm-S150SuccessorTerminalOutputLease -Item $lsItem -ExpectedReceipt $stdoutSeal

            # 8. finalize backend logs only after their writer stopped.
            $backendStdoutFinal = Open-S150SuccessorTerminalOutputLease -Item $bsoItem
            $backendStderrFinal = Open-S150SuccessorTerminalOutputLease -Item $bseItem
            Assert-True ($backendStdoutFinal.size -gt 0) 'backend stdout captured the fixture output'

            # 9. cleanup evidence categories.
            $evidence = [ordered]@{
                sealedBeforeCleanup = @('LauncherStdout')
                sealedAfterCleanup = @('LauncherStderr')
                mutableWhileBackendLive = @('BackendStdout', 'BackendStderr')
                cleanupOnly = [ordered]@{ BackendStdout = $backendStdoutFinal.sha256; BackendStderr = $backendStderrFinal.sha256 }
            }
            Assert-IntEq $evidence.sealedBeforeCleanup.Count 1 'sealedBeforeCleanup category'
            Assert-IntEq $evidence.sealedAfterCleanup.Count 1 'sealedAfterCleanup category'
            Assert-IntEq $evidence.mutableWhileBackendLive.Count 2 'mutableWhileBackendLive category'

            # 10. the failed launcher-result hash never changes; cleanup-only hashes cannot upgrade it.
            Assert-StrEq (Get-Sha256Upper ([IO.File]::ReadAllBytes($failed))) $failedSha 'failed launcher-result hash unchanged'
        } finally { Close-S150SuccessorOutputAnchorState -State $state }
    } finally {
        if ($null -ne $proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue; $proc.WaitForExit(5000) | Out-Null }
        Remove-TempRoot $root
    }
    Assert-IntEq (Get-ProtectedCensus) $censusBefore 'protected process census unchanged'
    Write-Output 'PASS s150_successor_output_ownership_test PartialSeal'
}

# ---- Task 5: LauncherLoadIsolation and LauncherSource ----

$s150BaselineJson = Join-Path $repo 'docs\s150-successor-historical-baseline.json'
$launcherBaselineSha = 'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D'
$ctrlStartProcHash = '68E4EB43A7E4F4E1748488B30380B035EDBF9E24839D369AB5BB33BADD9CFDDA'
$nonctrlStartProcHash = '9F997ED61406A30FE0A1D831931F4397A12DC2FBD1B1B3B44E48DB5AFEAC9551'
$nativeAmpHash = 'A090D0C62C77DACAB3E7F0E4831B4F4DF05FD5B5AE0E2D4E9F5C316E79D290DB'
$nonctrlBranchHash = 'FA4FDB3D159AABE905ECB5C1ECAA46E909A250A94ED56A033B55F7EFE0492413'
$nativeRegionHash = '3C8D6D12BED4410A07EFD926B6C0869C349152E72B25426DFDCF8D26BEF6FF60'

# Exact ordered raw-byte replacement map (three entries). This is the immutable
# test expectation, not a normalization or update-to-match mechanism.
$launcherReplacementMap = @(
    [pscustomobject]@{ Name = 'ControlledPreflight'; OldBase64 = 'ICAkbnVsbCA9IEFzc2VydC1TMTUwTm9SZXBhcnNlUGF0aCAtUGlubmVkQmFzZURpcmVjdG9yeSAkczE1MERvY3NSb290IGAKICAgIC1UYXJnZXRQYXRoICIkczE1MENvbnRyb2xsZWRDYXB0dXJlUGF0aC5wcmV2Igp9Cg=='; NewBase64 = 'ICAkbnVsbCA9IEFzc2VydC1TMTUwTm9SZXBhcnNlUGF0aCAtUGlubmVkQmFzZURpcmVjdG9yeSAkczE1MERvY3NSb290IGAKICAgIC1UYXJnZXRQYXRoICIkczE1MENvbnRyb2xsZWRDYXB0dXJlUGF0aC5wcmV2IgoKICAjIFMxNTAgc3VjY2Vzc29yIG91dHB1dCBvd25lcnNoaXA6IGRlcml2ZSBkaXN0aW5jdCBiYWNrZW5kIHNpbmtzIHVuZGVyIHRoZQogICMgcmV0aXJlbWVudCByb290IGFuZCBwaW4gdGhlIHN1Y2Nlc3NvciBldmlkZW5jZSBoZWxwZXIgYmVmb3JlIGFueSBtdXRhdGlvbi4KICAkczE1MFN1Y2Nlc3NvckhlbHBlclBhdGggPSBKb2luLVBhdGggJFBTU2NyaXB0Um9vdCAnczE1MC1zdWNjZXNzb3ItZXZpZGVuY2UucHMxJwogIGlmICgtbm90IChUZXN0LVBhdGggLUxpdGVyYWxQYXRoICRzMTUwU3VjY2Vzc29ySGVscGVyUGF0aCAtUGF0aFR5cGUgTGVhZikpIHsKICAgIHRocm93ICJTMTUwIHN1Y2Nlc3NvciBldmlkZW5jZSBoZWxwZXIgbm90IGZvdW5kOiAkczE1MFN1Y2Nlc3NvckhlbHBlclBhdGgiCiAgfQogICRudWxsID0gQXNzZXJ0LVMxNTBOb1JlcGFyc2VQYXRoIC1QaW5uZWRCYXNlRGlyZWN0b3J5IChbSU8uUGF0aF06OkdldEZ1bGxQYXRoKCRQU1NjcmlwdFJvb3QpKSBgCiAgICAtVGFyZ2V0UGF0aCAoW0lPLlBhdGhdOjpHZXRGdWxsUGF0aCgkczE1MFN1Y2Nlc3NvckhlbHBlclBhdGgpKQogIC4gJHMxNTBTdWNjZXNzb3JIZWxwZXJQYXRoCiAgJHMxNTBFeHBlY3RlZFJldGlyZW1lbnREaXJlY3RvcnkgPSBbSU8uUGF0aF06OkdldEZ1bGxQYXRoKChTcGxpdC1QYXRoIC1QYXJlbnQgJFMxNTBDYXB0dXJlQXJjaGl2ZURpcmVjdG9yeSkpCiAgJHMxNTBPdXRwdXRDb250cmFjdCA9IEdldC1TMTUwU3VjY2Vzc29yT3V0cHV0UGF0aENvbnRyYWN0IC1DYXB0dXJlQXJjaGl2ZURpcmVjdG9yeSAkUzE1MENhcHR1cmVBcmNoaXZlRGlyZWN0b3J5IC1FeHBlY3RlZFJldGlyZW1lbnREaXJlY3RvcnkgJHMxNTBFeHBlY3RlZFJldGlyZW1lbnREaXJlY3RvcnkKICAkczE1MEJhY2tlbmRTdGRvdXRQYXRoID0gJHMxNTBPdXRwdXRDb250cmFjdC5CYWNrZW5kU3Rkb3V0UGF0aAogICRzMTUwQmFja2VuZFN0ZGVyclBhdGggPSAkczE1ME91dHB1dENvbnRyYWN0LkJhY2tlbmRTdGRlcnJQYXRoCiAgJG51bGwgPSBBc3NlcnQtUzE1MFN1Y2Nlc3NvckNvbnRyb2xsZWRCYWNrZW5kT3V0cHV0U3RhdGUgLVBhdGhDb250cmFjdCAkczE1ME91dHB1dENvbnRyYWN0IC1QaW5uZWRCYXNlRGlyZWN0b3J5ICRzMTUwRG9jc1Jvb3QgLVJlcXVpcmVFbXB0eQp9Cg==' }
    [pscustomobject]@{ Name = 'ControlledBackendStart'; OldBase64 = 'ICAgICAgQXNzZXJ0LVMxNTBDZXJ0aWZpY2F0ZUFydGlmYWN0c0Fic2VudCAtQ2VydGlmaWNhdGVEaXJlY3RvcnkgJGNlcnRzRGlyCiAgICAgIFN0YXJ0LVByb2Nlc3MgLUZpbGVQYXRoICRhZ3NFeGUgLUFyZ3VtZW50TGlzdCAkYXJnU3RyaW5nIC1Xb3JraW5nRGlyZWN0b3J5ICRzZXJ2ZXJEaXIgYAogICAgICAgIC1SZWRpcmVjdFN0YW5kYXJkRXJyb3IgJHNydk91dCAtUGFzc1RocnUK'; NewBase64 = 'ICAgICAgQXNzZXJ0LVMxNTBDZXJ0aWZpY2F0ZUFydGlmYWN0c0Fic2VudCAtQ2VydGlmaWNhdGVEaXJlY3RvcnkgJGNlcnRzRGlyCiAgICAgICRudWxsID0gQXNzZXJ0LVMxNTBTdWNjZXNzb3JDb250cm9sbGVkQmFja2VuZE91dHB1dFN0YXRlIC1QYXRoQ29udHJhY3QgJHMxNTBPdXRwdXRDb250cmFjdCAtUGlubmVkQmFzZURpcmVjdG9yeSAkczE1MERvY3NSb290IC1SZXF1aXJlRW1wdHkKICAgICAgU3RhcnQtUHJvY2VzcyAtRmlsZVBhdGggJGFnc0V4ZSAtQXJndW1lbnRMaXN0ICRhcmdTdHJpbmcgLVdvcmtpbmdEaXJlY3RvcnkgJHNlcnZlckRpciBgCiAgICAgICAgLVJlZGlyZWN0U3RhbmRhcmRPdXRwdXQgJHMxNTBCYWNrZW5kU3Rkb3V0UGF0aCBgCiAgICAgICAgLVJlZGlyZWN0U3RhbmRhcmRFcnJvciAkczE1MEJhY2tlbmRTdGRlcnJQYXRoIC1QYXNzVGhydQo=' }
    [pscustomobject]@{ Name = 'ControlledCertificateDiagnostics'; OldBase64 = 'ICAgICAgaWYgKC1ub3QgJGNlcnRpZmljYXRlc0V4aXN0KSB7CiAgICAgICAgaWYgKFRlc3QtUGF0aCAtTGl0ZXJhbFBhdGggJHNydk91dCAtUGF0aFR5cGUgTGVhZikgewogICAgICAgICAgV3JpdGUtSG9zdCAiLS0tIHNlcnZlciBvdXRwdXQgLS0tIiAtRm9yZWdyb3VuZENvbG9yIFJlZAogICAgICAgICAgR2V0LUNvbnRlbnQgLUxpdGVyYWxQYXRoICRzcnZPdXQgfCBXcml0ZS1Ib3N0CiAgICAgICAgfQogICAgICAgIHRocm93ICJTMTUwIGJhY2tlbmQgZGlkIG5vdCBwcm9kdWNlIHJvb3QuY3J0LCBzZXJ2ZXIuY3J0LCBhbmQgc2VydmVyLmtleSB3aXRoaW4gMzAgc2Vjb25kcyAoc2VlICRzcnZPdXQpLiIKICAgICAgfQo='; NewBase64 = 'ICAgICAgaWYgKC1ub3QgJGNlcnRpZmljYXRlc0V4aXN0KSB7CiAgICAgICAgZm9yZWFjaCAoJHMxNTBEaWFnUGF0aCBpbiBAKCRzMTUwQmFja2VuZFN0ZG91dFBhdGgsICRzMTUwQmFja2VuZFN0ZGVyclBhdGgpKSB7CiAgICAgICAgICBpZiAoVGVzdC1QYXRoIC1MaXRlcmFsUGF0aCAkczE1MERpYWdQYXRoIC1QYXRoVHlwZSBMZWFmKSB7CiAgICAgICAgICAgIFdyaXRlLUhvc3QgIi0tLSBiYWNrZW5kIG91dHB1dCAoJHMxNTBEaWFnUGF0aCkgLS0tIiAtRm9yZWdyb3VuZENvbG9yIFJlZAogICAgICAgICAgICBHZXQtQ29udGVudCAtTGl0ZXJhbFBhdGggJHMxNTBEaWFnUGF0aCB8IFdyaXRlLUhvc3QKICAgICAgICAgIH0KICAgICAgICB9CiAgICAgICAgdGhyb3cgIlMxNTAgYmFja2VuZCBkaWQgbm90IHByb2R1Y2Ugcm9vdC5jcnQsIHNlcnZlci5jcnQsIGFuZCBzZXJ2ZXIua2V5IHdpdGhpbiAzMCBzZWNvbmRzIChzZWUgJHMxNTBCYWNrZW5kU3Rkb3V0UGF0aCBhbmQgJHMxNTBCYWNrZW5kU3RkZXJyUGF0aCkuIgogICAgICB9Cg==' }
)

function Get-ByteCensus([byte[]]$b) {
    $crlf = 0; $lf = 0; $cr = 0
    for ($i = 0; $i -lt $b.Length; $i++) {
        if ($b[$i] -eq 13) { if ($i + 1 -lt $b.Length -and $b[$i + 1] -eq 10) { $crlf++; $i++ } else { $cr++ } }
        elseif ($b[$i] -eq 10) { $lf++ }
    }
    return [pscustomobject]@{ Crlf = $crlf; Lf = $lf; Cr = $cr }
}
function Get-Utf8RegionHashes([byte[]]$launcherBytes) {
    $tok = $null; $er = $null
    [IO.Directory]::CreateDirectory((Join-Path $repo '.superpowers\temp')) | Out-Null
    $tmp = Join-Path $repo ('.superpowers\temp\s150ls-' + [guid]::NewGuid().ToString('N') + '.ps1')
    [IO.File]::WriteAllBytes($tmp, $launcherBytes)
    try {
        $ast = [Management.Automation.Language.Parser]::ParseFile($tmp, [ref]$tok, [ref]$er)
        if (@($er).Count -ne 0) { throw "launcher AST parse failed: $(@($er)[0].Message)" }
        $result = [ordered]@{ AstErrors = @($er).Count; Ctrl = ''; NonCtrl = ''; Amp = @(); NonCtrlBranch = ''; NativeRegion = ''; ControlledHasStdoutRedirect = $false }
        $cmds = $ast.FindAll({ param($n) $n -is [Management.Automation.Language.CommandAst] }, $true)
        foreach ($c in $cmds) {
            if ($c.GetCommandName() -eq 'Start-Process' -and ($c.Extent.Text -match 'PassThru') -and ($c.Extent.Text -match 's150BackendStdoutPath')) {
                $result.Ctrl = Get-Sha256Upper ([Text.Encoding]::UTF8.GetBytes($c.Extent.Text.Replace("`r`n", "`n")))
                $result.ControlledHasStdoutRedirect = $true
            }
            if ($c.GetCommandName() -eq 'Start-Process' -and ($c.Extent.Text -match '\$srvOut')) {
                $result.NonCtrl = Get-Sha256Upper ([Text.Encoding]::UTF8.GetBytes($c.Extent.Text.Replace("`r`n", "`n")))
            }
            if ($c.InvocationOperator -eq 'Ampersand' -and $c.Extent.Text -match '@iniArgs') {
                $result.Amp += (Get-Sha256Upper ([Text.Encoding]::UTF8.GetBytes($c.Extent.Text.Replace("`r`n", "`n"))))
            }
        }
        $u8 = [Text.Encoding]::UTF8.GetString($launcherBytes)
        if ($u8.Length -ge 1 -and [int][char]$u8[0] -eq 0xFEFF) { $u8 = $u8.Substring(1) }
        $tl = ($u8.Replace("`r`n", "`n")) -split "`n"
        for ($i = 0; $i -lt $tl.Count; $i++) {
            if ($tl[$i] -eq '} else {' -and $i + 1 -lt $tl.Count -and $tl[$i + 1] -match 'Start-Process -FilePath \$agsExe') {
                for ($j = $i + 1; $j -lt $tl.Count; $j++) { if ($tl[$j] -eq '}') { break } }
                $result.NonCtrlBranch = Get-Sha256Upper ([Text.Encoding]::UTF8.GetBytes(($tl[$i..$j] -join "`n")))
                break
            }
        }
        for ($i = 1; $i -lt $tl.Count; $i++) {
            if ($tl[$i] -match 'Write-Host "Launching SUPERVIVE \(PostAuth' -and $tl[$i - 1] -notmatch 'Launching SUPERVIVE') {
                $result.NativeRegion = Get-Sha256Upper ([Text.Encoding]::UTF8.GetBytes(($tl[$i..($i + 7)] -join "`n")))
                break
            }
        }
        return [pscustomobject]$result
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

function Invoke-LauncherSourceSuite {
    # 1. Baseline authority: decode the immutable historical-baseline raw launcher.
    $baseline = Get-Content -LiteralPath $s150BaselineJson -Raw | ConvertFrom-Json
    $baseBytes = [Convert]::FromBase64String($baseline.preEditLauncherRaw.base64)
    Assert-IntEq $baseBytes.Length 37367 'baseline launcher size'
    Assert-StrEq (Get-Sha256Upper $baseBytes) $launcherBaselineSha 'baseline launcher sha'
    Assert-True ($baseBytes[0] -eq 0xEF -and $baseBytes[1] -eq 0xBB -and $baseBytes[2] -eq 0xBF) 'baseline BOM'
    $baseCensus = Get-ByteCensus $baseBytes
    Assert-IntEq $baseCensus.Crlf 425 'baseline CRLF count'
    Assert-IntEq $baseCensus.Lf 222 'baseline lone-LF count'
    Assert-IntEq $baseCensus.Cr 0 'baseline lone-CR count'
    foreach ($pin in $baseline.pinnedPreState) {
        if ($pin.path -eq 'configs\launch-redirect.ps1') { Assert-StrEq $pin.sha256 $launcherBaselineSha 'baseline pinnedPreState launcher sha' }
    }

    # 2. Apply the exact three-entry replacement map to the baseline bytes.
    $latin1 = [Text.Encoding]::GetEncoding(28591)
    $s = $latin1.GetString($baseBytes)
    $censusDeltaCrlf = 0; $censusDeltaLf = 0; $censusDeltaCr = 0
    $prevIndex = -1
    foreach ($entry in $launcherReplacementMap) {
        $old = $latin1.GetString([Convert]::FromBase64String($entry.OldBase64))
        $new = $latin1.GetString([Convert]::FromBase64String($entry.NewBase64))
        Assert-True ($old.Length -gt 0) "$($entry.Name): old blob nonempty"
        $i = $s.IndexOf($old, [StringComparison]::Ordinal)
        Assert-True ($i -ge 0) "$($entry.Name): old blob present in baseline"
        Assert-True ($s.IndexOf($old, $i + 1, [StringComparison]::Ordinal) -lt 0) "$($entry.Name): old blob occurs exactly once"
        Assert-True ($i -gt $prevIndex) "$($entry.Name): map entries are ordered"
        $prevIndex = $i
        $oldC = Get-ByteCensus ([Convert]::FromBase64String($entry.OldBase64))
        $newC = Get-ByteCensus ([Convert]::FromBase64String($entry.NewBase64))
        $censusDeltaCrlf += ($newC.Crlf - $oldC.Crlf)
        $censusDeltaLf += ($newC.Lf - $oldC.Lf)
        $censusDeltaCr += ($newC.Cr - $oldC.Cr)
        Write-Output ("  map $($entry.Name): oldLen=$([Convert]::FromBase64String($entry.OldBase64).Length) newLen=$([Convert]::FromBase64String($entry.NewBase64).Length) oldSha=$(Get-Sha256Upper ([Convert]::FromBase64String($entry.OldBase64))) newSha=$(Get-Sha256Upper ([Convert]::FromBase64String($entry.NewBase64)))")
    }
    $s2 = $s
    foreach ($entry in $launcherReplacementMap) {
        $old = $latin1.GetString([Convert]::FromBase64String($entry.OldBase64))
        $new = $latin1.GetString([Convert]::FromBase64String($entry.NewBase64))
        $s2 = $s2.Replace($old, $new)
    }
    $targetBytes = $latin1.GetBytes($s2)

    # 3. The constructed target must carry the exact reviewed controlled Start-Process.
    $targetHashes = Get-Utf8RegionHashes $targetBytes
    Assert-StrEq $targetHashes.Ctrl $ctrlStartProcHash 'target controlled Start-Process AST hash'

    # canonical map hash (for evidence)
    $mapConcat = New-Object 'System.Collections.Generic.List[byte]'
    foreach ($entry in $launcherReplacementMap) { $mapConcat.AddRange([Convert]::FromBase64String($entry.OldBase64)); $mapConcat.AddRange([Convert]::FromBase64String($entry.NewBase64)) }
    Write-Output ("  canonical replacement-map hash=" + (Get-Sha256Upper $mapConcat.ToArray()))

    # 4. Whole-file ordinal comparison against the actual launcher.
    $actualBytes = [IO.File]::ReadAllBytes($launcher)
    $isGreen = ($actualBytes.Length -eq $targetBytes.Length) -and ([Linq.Enumerable]::SequenceEqual([byte[]]$actualBytes, [byte[]]$targetBytes))
    if (-not $isGreen) {
        $actualHashes = Get-Utf8RegionHashes $actualBytes
        if (-not $actualHashes.ControlledHasStdoutRedirect) {
            Write-Output 'CONTROLLED_BACKEND_STDOUT_NOT_DISTINCT'
        } else {
            Write-Output 'LAUNCHER_NOT_YET_EQUAL_TO_TARGET'
        }
        exit 1
    }

    # 5. GREEN: verify the unchanged regions on the actual edited launcher.
    $actualHashes = Get-Utf8RegionHashes $actualBytes
    Assert-StrEq $actualHashes.Ctrl $ctrlStartProcHash 'edited controlled Start-Process AST hash'
    Assert-StrEq $actualHashes.NonCtrl $nonctrlStartProcHash 'unchanged non-controlled Start-Process AST hash'
    Assert-True ($actualHashes.Amp.Count -ge 2) 'native & occurrences present'
    foreach ($h in $actualHashes.Amp) { Assert-StrEq $h $nativeAmpHash 'unchanged native & AST hash' }
    Assert-StrEq $actualHashes.NonCtrlBranch $nonctrlBranchHash 'unchanged non-controlled branch region hash'
    Assert-StrEq $actualHashes.NativeRegion $nativeRegionHash 'unchanged native launch region hash'

    # 6. Derived newline census.
    $actualCensus = Get-ByteCensus $actualBytes
    Assert-IntEq $actualCensus.Crlf ($baseCensus.Crlf + $censusDeltaCrlf) 'derived CRLF census'
    Assert-IntEq $actualCensus.Lf ($baseCensus.Lf + $censusDeltaLf) 'derived lone-LF census'
    Assert-IntEq $actualCensus.Cr ($baseCensus.Cr + $censusDeltaCr) 'derived lone-CR census'

    # 7. AST branch scoping: successor derivation only under the controlled branch; no server.out.log in controlled mode; no test-only seams.
    $src = [IO.File]::ReadAllText($launcher)
    Assert-True ($src -match '(?s)if \(\$S150ControlledCapture\).*?s150-successor-evidence\.ps1') 'successor helper referenced under the controlled branch'
    Assert-True ($src -notmatch 'BetweenSamples') 'no BetweenSamples seam in launcher source'
    Assert-True ($src -notmatch 'AttemptObserver') 'no AttemptObserver seam in launcher source'
    # the non-controlled branch (the } else { ... } block) must not reference successor symbols
    $u8 = [Text.Encoding]::UTF8.GetString($actualBytes)
    if ($u8.Length -ge 1 -and [int][char]$u8[0] -eq 0xFEFF) { $u8 = $u8.Substring(1) }
    $tl = ($u8.Replace("`r`n", "`n")) -split "`n"
    for ($i = 0; $i -lt $tl.Count; $i++) {
        if ($tl[$i] -eq '} else {' -and $i + 1 -lt $tl.Count -and $tl[$i + 1] -match 'Start-Process -FilePath \$agsExe') {
            for ($j = $i + 1; $j -lt $tl.Count; $j++) { if ($tl[$j] -eq '}') { break } }
            $branch = ($tl[$i..$j] -join "`n")
            Assert-True ($branch -notmatch 's150Backend') 'non-controlled branch has no successor backend paths'
            Assert-True ($branch -notmatch 's150OutputContract') 'non-controlled branch has no successor contract'
            break
        }
    }

    Write-Output 'PASS s150_successor_output_ownership_test LauncherSource'
}

function Invoke-LauncherLoadIsolationSuite {
    # Dynamic half: this process has S150 + successor loaded but NOT S149.
    Assert-True ($null -eq (Get-Command -Name Get-S149WatcherReceiptResult -ErrorAction SilentlyContinue)) 'S149 parser not loaded (clean isolation state)'
    Assert-True ($null -ne (Get-Command -Name Get-S150SuccessorOutputPathContract -ErrorAction SilentlyContinue)) 'output-path API available without S149'
    $root = New-TempRoot 's150li'
    try {
        $retire = Join-Path $root 'retire'; [IO.Directory]::CreateDirectory($retire) | Out-Null
        $arch = Join-Path $retire 'capture-archive'; [IO.Directory]::CreateDirectory($arch) | Out-Null
        $contract = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $arch -ExpectedRetirementDirectory $retire
        Assert-StrEq ([IO.Path]::GetFileName($contract.BackendStdoutPath)) 'backend.stdout.log' 'output-path API works without S149'
        $flight2Receipt = Join-Path $repo 'docs\s150-retirement-s150captureflight2-20260829-192619\crashwatch.stdout.log'
        $bytes = [IO.File]::ReadAllBytes($flight2Receipt)
        $threw = $false; $msg = ''
        try {
            Get-S150SuccessorWatcherEnvelopeResult -Bytes $bytes -ExpectedGamePid 14512 -ExpectedWatcherPid 37964 `
                -ExpectedWatcherStartUtcTicks 639236573100000000 -ExpectedLogCreationUtcTicks 639236573100000000 `
                -ActualLogCreationUtcTicks 639236573100000000 -ActualLogLastWriteUtcTicks 639236573105000000 `
                -NowUtcTicks 639236573110000000 -ExpectedLokiPath 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log' `
                -ExpectedOutputDir 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s150captureflight2-20260829-192619' | Out-Null
        } catch { $threw = $true; $msg = "$($_.Exception.Message)" }
        Assert-True $threw 'watcher API fails closed without S149'
        Assert-StrEq $msg 'S149 watcher parser is not loaded' 'watcher fail-closed message'
        # load S149 and prove watcher validation works
        Assert-StrEq (Get-FileHash -Algorithm SHA256 -LiteralPath $s149Helper).Hash $s149HelperSha 'S149 bind gate hash'
        . $s149Helper
        $r = Get-S150SuccessorWatcherEnvelopeResult -Bytes $bytes -ExpectedGamePid 14512 -ExpectedWatcherPid 37964 `
            -ExpectedWatcherStartUtcTicks 639236573100000000 -ExpectedLogCreationUtcTicks 639236573100000000 `
            -ActualLogCreationUtcTicks 639236573100000000 -ActualLogLastWriteUtcTicks 639236573105000000 `
            -NowUtcTicks 639236573110000000 -ExpectedLokiPath 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log' `
            -ExpectedOutputDir 'C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project\dumps\crash-s150captureflight2-20260829-192619'
        Assert-True $r.Valid 'watcher validation works after S149 loads'
    } finally { Remove-TempRoot $root }

    # Static half: the controlled launcher branch loads the successor helper; the non-controlled branch does not.
    $src = [IO.File]::ReadAllText($launcher)
    Assert-True ($src -match '(?s)if \(\$S150ControlledCapture\).*?\.\s+\$s150SuccessorHelperPath') 'controlled branch dot-sources the successor helper'
    Assert-True ($src -match "Join-Path \`$PSScriptRoot 's150-capture-generation\.ps1'") 'controlled branch loads the S150 capture helper'
    Assert-True ($src -notmatch 's149-bind-gate') 'launcher never loads S149 directly'

    Write-Output 'PASS s150_successor_output_ownership_test LauncherLoadIsolation'
}

# Successor helpers are dot-sourced at SCRIPT scope so every suite can see them.
Assert-StrEq (Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash $captureHelperSha 'S150 capture helper hash'
. $captureHelper
. $successorHelper

switch ($Section) {
    'FrozenRed' { Invoke-FrozenRedSuite }
    'PathContract' { Invoke-PathContractSuite }
    'Anchors' { Invoke-AnchorsSuite }
    'TerminalLease' { Invoke-TerminalLeaseSuite }
    'PartialSeal' { Invoke-PartialSealSuite $FixtureExe }
    'ProcessMatrix' { Invoke-ProcessMatrixSuite $FixtureExe }
    'LauncherLoadIsolation' { Invoke-LauncherLoadIsolationSuite }
    'LauncherSource' { Invoke-LauncherSourceSuite }
    'Full' {
        Invoke-FrozenRedSuite
        Invoke-PathContractSuite
        Invoke-AnchorsSuite
        Invoke-TerminalLeaseSuite
        Invoke-PartialSealSuite $FixtureExe
        Invoke-ProcessMatrixSuite $FixtureExe
        Invoke-LauncherLoadIsolationSuite
        Invoke-LauncherSourceSuite
    }
    default {
        Write-Output "SECTION_NOT_IMPLEMENTED_YET $Section"
        exit 2
    }
}
