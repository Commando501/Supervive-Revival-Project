$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$production = Join-Path $repo 'configs\s150-capture-generation.ps1'

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Assert-BytesEqual([byte[]]$Actual, [byte[]]$Expected, [string]$Message) {
    if ($Actual.Length -ne $Expected.Length -or
        [Convert]::ToBase64String($Actual) -ne [Convert]::ToBase64String($Expected)) {
        throw "$Message (actual=$([Convert]::ToBase64String($Actual)) expected=$([Convert]::ToBase64String($Expected)))"
    }
}

function Assert-Throws([scriptblock]$Action, [string]$Message) {
    $threw = $false
    try { & $Action } catch { $threw = $true }
    Assert-True $threw $Message
}

function Write-SharedCapture([string]$Path, [string]$Text, [datetime]$CreationTimeUtc) {
    $bytes = [Text.Encoding]::ASCII.GetBytes($Text)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
    try {
        $stream.SetLength(0)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    (Get-Item -LiteralPath $Path).CreationTimeUtc = $CreationTimeUtc
}

function Read-SharedCaptureBytes([string]$Path) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    $memory = [IO.MemoryStream]::new()
    try {
        $stream.CopyTo($memory)
        Write-Output -NoEnumerate $memory.ToArray()
    } finally {
        $memory.Dispose()
        $stream.Dispose()
    }
}

function New-FakeProcess(
    [int]$Id,
    [string]$ProcessName,
    [datetime]$StartTimeUtc,
    [string]$Path
) {
    [pscustomobject]@{
        Id = $Id
        ProcessName = $ProcessName
        StartTimeUtc = $StartTimeUtc
        Path = [IO.Path]::GetFullPath($Path)
    }
}

function Assert-StreamReleased([string]$Path, [string]$Message) {
    $moved = "$Path.released"
    try {
        [IO.File]::Move($Path, $moved)
    } catch {
        throw "$Message ($($_.Exception.Message))"
    }
}

function Write-TestCertificates(
    [string]$Directory,
    [string]$Prefix,
    [datetime]$LastWriteTimeUtc
) {
    foreach ($name in @('root.crt', 'server.crt', 'server.key')) {
        $path = Join-Path $Directory $name
        [IO.File]::WriteAllBytes($path, [Text.Encoding]::ASCII.GetBytes("$Prefix-$name"))
        (Get-Item -LiteralPath $path).LastWriteTimeUtc = $LastWriteTimeUtc
    }
}

if (-not (Test-Path -LiteralPath $production -PathType Leaf)) {
    throw "S150 production seam absent: expected capture-generation helper at $production"
}
try {
    . $production
} catch {
    throw "S150 production seam failed to load from ${production}: $($_.Exception.Message)"
}

foreach ($command in @(
    'Open-S150CaptureGeneration',
    'Test-S150CaptureGenerationCompletion',
    'Invoke-S150ControlledLaunch'
)) {
    Assert-True ($null -ne (Get-Command -Name $command -ErrorAction SilentlyContinue)) `
        "S150 production seam missing public command: $command"
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('s150-capture-generation-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    # The public open seam must archive both possible canonical segments without
    # clobbering a prior archive, even when one of the source files is empty.
    foreach ($case in @(
        [pscustomobject]@{ Name = 'nonempty-capture'; Capture = [byte[]](0x53,0x31,0x35,0x30,0x00,0xff); Previous = [byte[]]@() },
        [pscustomobject]@{ Name = 'empty-capture'; Capture = [byte[]]@(); Previous = [byte[]](0x70,0x72,0x65,0x76,0x0a) }
    )) {
        $caseRoot = Join-Path $root $case.Name
        $archiveRoot = Join-Path $caseRoot 'archive'
        New-Item -ItemType Directory -Path $caseRoot, $archiveRoot | Out-Null
        $capture = Join-Path $caseRoot 'capture.log'
        $previous = "$capture.prev"
        [IO.File]::WriteAllBytes($capture, $case.Capture)
        [IO.File]::WriteAllBytes($previous, $case.Previous)
        $generation = [guid]::NewGuid()
        $opened = $null
        try {
            $opened = Open-S150CaptureGeneration -CapturePath $capture -ArchiveDirectory $archiveRoot -Generation $generation
            Assert-True (([guid]$opened.Generation).ToString('N') -eq $generation.ToString('N')) "$($case.Name): generation must be the supplied N-format GUID"
            Assert-True ([bool]$opened.CreatedNew) "$($case.Name): canonical capture must be created with CreateNew"
            Assert-True ([bool]$opened.DurablyFlushed) "$($case.Name): canonical empty capture must be flushed through the OS boundary"
            Assert-True ($opened.Stream -is [IO.FileStream]) "$($case.Name): open seam must retain the canonical FileStream"
            Assert-BytesEqual ([IO.File]::ReadAllBytes($opened.ArchiveCapturePath)) $case.Capture "$($case.Name): capture.log archive bytes must be exact"
            Assert-BytesEqual ([IO.File]::ReadAllBytes($opened.ArchivePreviousPath)) $case.Previous "$($case.Name): capture.log.prev archive bytes must be exact"
            Assert-BytesEqual (Read-SharedCaptureBytes $capture) ([byte[]]@()) "$($case.Name): newly canonical capture must be empty"

            # The held handle may coexist with readers/writers but must deny the
            # delete sharing needed to replace or rename the canonical generation.
            $reader = [IO.File]::Open($capture, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            $reader.Dispose()
            $writer = [IO.File]::Open($capture, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
            $writer.Dispose()
            Assert-Throws { [IO.File]::Move($capture, "$capture.replacement") } "$($case.Name): held canonical stream must deny rename replacement"
        } finally {
            if ($null -ne $opened -and $null -ne $opened.Stream) { $opened.Stream.Dispose() }
        }

        # Reusing a generation collides with the exact destination from the first
        # archival attempt. It must refuse before either source segment changes.
        [IO.File]::WriteAllBytes($capture, $case.Capture)
        [IO.File]::WriteAllBytes($previous, $case.Previous)
        $archivedCaptureBefore = [IO.File]::ReadAllBytes($opened.ArchiveCapturePath)
        $archivedPreviousBefore = [IO.File]::ReadAllBytes($opened.ArchivePreviousPath)
        Assert-Throws {
            Open-S150CaptureGeneration -CapturePath $capture -ArchiveDirectory $archiveRoot -Generation $generation
        } "$($case.Name): archive collision must refuse rather than clobber"
        Assert-BytesEqual ([IO.File]::ReadAllBytes($capture)) $case.Capture "$($case.Name): collision must leave capture.log unchanged"
        Assert-BytesEqual ([IO.File]::ReadAllBytes($previous)) $case.Previous "$($case.Name): collision must leave capture.log.prev unchanged"
        Assert-BytesEqual ([IO.File]::ReadAllBytes($opened.ArchiveCapturePath)) $archivedCaptureBefore "$($case.Name): collision must leave archive destination unchanged"
        Assert-BytesEqual ([IO.File]::ReadAllBytes($opened.ArchivePreviousPath)) $archivedPreviousBefore "$($case.Name): collision must leave .prev archive destination unchanged"
    }

    # A non-file at either canonical source path is a preflight refusal. The
    # sibling source must not move and backend launch must remain unreachable.
    foreach ($nonFileCase in @('capture-directory', 'previous-directory')) {
        $nonFileRoot = Join-Path $root $nonFileCase
        $nonFileArchive = Join-Path $nonFileRoot 'archive'
        New-Item -ItemType Directory -Path $nonFileRoot, $nonFileArchive | Out-Null
        $nonFileCapture = Join-Path $nonFileRoot 'capture.log'
        $nonFilePrevious = "$nonFileCapture.prev"
        $siblingBytes = [Text.Encoding]::ASCII.GetBytes("$nonFileCase sibling evidence")
        if ($nonFileCase -eq 'capture-directory') {
            New-Item -ItemType Directory -Path $nonFileCapture | Out-Null
            [IO.File]::WriteAllBytes($nonFilePrevious, $siblingBytes)
        } else {
            [IO.File]::WriteAllBytes($nonFileCapture, $siblingBytes)
            New-Item -ItemType Directory -Path $nonFilePrevious | Out-Null
        }

        $script:startCalls = 0
        Assert-Throws {
            Invoke-S150ControlledLaunch -CapturePath $nonFileCapture -ArchiveDirectory $nonFileArchive `
                -Generation ([guid]::NewGuid()) -PreStartInventory @() `
                -ExpectedBackendPath (Join-Path $nonFileRoot 'ags.exe') `
                -StartBackend { $script:startCalls++; throw 'non-file source reached backend start' } `
                -ResolveProcess { throw 'non-file source reached resolve' } `
                -PostStartInventory { throw 'non-file source reached post-start inventory' } `
                -ProbeBackend { throw 'non-file source reached probe' } `
                -StopProcess { throw 'non-file source reached stop' } | Out-Null
        } "$nonFileCase must refuse"
        Assert-True ($script:startCalls -eq 0) "$nonFileCase must refuse before backend start"
        Assert-True ((Get-ChildItem -Force -LiteralPath $nonFileArchive).Count -eq 0) "$nonFileCase must refuse before either source moves"
        if ($nonFileCase -eq 'capture-directory') {
            Assert-True (Test-Path -LiteralPath $nonFileCapture -PathType Container) 'capture directory must remain in place'
            Assert-BytesEqual ([IO.File]::ReadAllBytes($nonFilePrevious)) $siblingBytes 'previous sibling file must remain in place'
        } else {
            Assert-BytesEqual ([IO.File]::ReadAllBytes($nonFileCapture)) $siblingBytes 'capture sibling file must remain in place'
            Assert-True (Test-Path -LiteralPath $nonFilePrevious -PathType Container) 'previous directory must remain in place'
        }
    }

    # A source whose injected attribute seam reports ReparsePoint must be
    # refused before either source moves or the canonical generation is created.
    $captureReparseRoot = Join-Path $root 'capture-reparse-source'
    $captureReparseArchive = Join-Path $captureReparseRoot 'archive'
    New-Item -ItemType Directory -Path $captureReparseRoot, $captureReparseArchive | Out-Null
    $captureReparsePath = Join-Path $captureReparseRoot 'capture.log'
    $captureReparseTargetBytes = [byte[]](7, 14, 21, 28, 35)
    [IO.File]::WriteAllBytes($captureReparsePath, $captureReparseTargetBytes)
    $captureReparsePrevious = "$captureReparsePath.prev"
    $captureReparsePreviousBytes = [Text.Encoding]::ASCII.GetBytes('reparse-source previous evidence')
    [IO.File]::WriteAllBytes($captureReparsePrevious, $captureReparsePreviousBytes)
    $captureReparseOpened = $null
    $captureReparseThrew = $false
    $captureReparseMessage = ''
    try {
        try {
            $captureReparseOpened = Invoke-S150CaptureGenerationOpenCore -CapturePath $captureReparsePath `
                -CaptureBaseDirectory $captureReparseRoot -ArchiveDirectory $captureReparseArchive `
                -ArchiveBaseDirectory $captureReparseArchive -Generation ([guid]::NewGuid()) `
                -GetAttributes {
                    param($path)
                    if ([string]::Equals(
                        [IO.Path]::GetFullPath($path),
                        [IO.Path]::GetFullPath($captureReparsePath),
                        [StringComparison]::OrdinalIgnoreCase
                    )) {
                        return ([IO.FileAttributes]::Archive -bor [IO.FileAttributes]::ReparsePoint)
                    }
                    return [IO.File]::GetAttributes($path)
                }
        } catch {
            $captureReparseThrew = $true
            $captureReparseMessage = $_.Exception.Message
        }
    } finally {
        if ($null -ne $captureReparseOpened -and $null -ne $captureReparseOpened.Stream) {
            $captureReparseOpened.Stream.Dispose()
        }
    }
    Assert-True $captureReparseThrew 'reparse-point capture source must refuse'
    Assert-True ($captureReparseMessage -match 'reparse') 'reparse-point capture source refusal must name the unsafe condition'
    Assert-BytesEqual ([IO.File]::ReadAllBytes($captureReparsePath)) $captureReparseTargetBytes 'reported reparse-point capture refusal must preserve source bytes'
    Assert-BytesEqual ([IO.File]::ReadAllBytes($captureReparsePrevious)) $captureReparsePreviousBytes 'reparse-point capture refusal must preserve the sibling source'
    Assert-True ((Get-ChildItem -Force -LiteralPath $captureReparseArchive).Count -eq 0) 'reparse-point capture refusal must leave archive empty'

    # The archive path is pinned at an ordinary base. A junction in a component
    # below that base must be refused before either source is moved.
    $archiveJunctionRoot = Join-Path $root 'archive-junction-component'
    $archivePinnedBase = Join-Path $archiveJunctionRoot 'archive-base'
    $archiveExternalTarget = Join-Path $archiveJunctionRoot 'external-target'
    $archiveExternalLeaf = Join-Path $archiveExternalTarget 'leaf'
    $archiveJunction = Join-Path $archivePinnedBase 'redirect'
    $archiveThroughJunction = Join-Path $archiveJunction 'leaf'
    $archiveSourceRoot = Join-Path $archiveJunctionRoot 'source'
    New-Item -ItemType Directory -Path $archivePinnedBase, $archiveExternalTarget, $archiveExternalLeaf, $archiveSourceRoot | Out-Null
    New-Item -ItemType Junction -Path $archiveJunction -Target $archiveExternalTarget -ErrorAction Stop | Out-Null
    $archiveJunctionCapture = Join-Path $archiveSourceRoot 'capture.log'
    $archiveJunctionPrevious = "$archiveJunctionCapture.prev"
    $archiveJunctionCaptureBytes = [Text.Encoding]::ASCII.GetBytes('archive-junction capture evidence')
    $archiveJunctionPreviousBytes = [Text.Encoding]::ASCII.GetBytes('archive-junction previous evidence')
    $archiveJunctionSentinel = Join-Path $archiveExternalLeaf 'sentinel.bin'
    $archiveJunctionSentinelBytes = [byte[]](101, 102, 103, 104)
    [IO.File]::WriteAllBytes($archiveJunctionCapture, $archiveJunctionCaptureBytes)
    [IO.File]::WriteAllBytes($archiveJunctionPrevious, $archiveJunctionPreviousBytes)
    [IO.File]::WriteAllBytes($archiveJunctionSentinel, $archiveJunctionSentinelBytes)
    $archiveJunctionOpened = $null
    $archiveJunctionThrew = $false
    $archiveJunctionMessage = ''
    try {
        try {
            $archiveJunctionOpened = Open-S150CaptureGeneration -CapturePath $archiveJunctionCapture `
                -CaptureBaseDirectory $archiveSourceRoot -ArchiveDirectory $archiveThroughJunction `
                -ArchiveBaseDirectory $archivePinnedBase -Generation ([guid]::NewGuid())
        } catch {
            $archiveJunctionThrew = $true
            $archiveJunctionMessage = $_.Exception.Message
        }
    } finally {
        if ($null -ne $archiveJunctionOpened -and $null -ne $archiveJunctionOpened.Stream) {
            $archiveJunctionOpened.Stream.Dispose()
        }
    }
    Assert-True $archiveJunctionThrew 'archive junction component must refuse'
    Assert-True ($archiveJunctionMessage -match 'reparse') 'archive junction component refusal must name the unsafe condition'
    Assert-BytesEqual ([IO.File]::ReadAllBytes($archiveJunctionCapture)) $archiveJunctionCaptureBytes 'archive junction refusal must preserve capture source'
    Assert-BytesEqual ([IO.File]::ReadAllBytes($archiveJunctionPrevious)) $archiveJunctionPreviousBytes 'archive junction refusal must preserve previous source'
    Assert-BytesEqual ([IO.File]::ReadAllBytes($archiveJunctionSentinel)) $archiveJunctionSentinelBytes 'archive junction refusal must preserve external target bytes'
    Assert-True ((Get-ChildItem -Force -LiteralPath $archiveExternalLeaf).Count -eq 1) 'archive junction refusal must not create external archive entries'

    # The capture path is likewise pinned. CreateNew must never be redirected
    # through a junction component to an external parent directory.
    $captureParentRoot = Join-Path $root 'capture-parent-junction'
    $capturePinnedBase = Join-Path $captureParentRoot 'capture-base'
    $captureExternalParent = Join-Path $captureParentRoot 'external-parent'
    $captureParentJunction = Join-Path $capturePinnedBase 'redirect'
    $captureThroughJunction = Join-Path $captureParentJunction 'capture.log'
    $captureThroughJunctionPrevious = "$captureThroughJunction.prev"
    $captureParentArchive = Join-Path $captureParentRoot 'archive'
    New-Item -ItemType Directory -Path $capturePinnedBase, $captureExternalParent, $captureParentArchive | Out-Null
    New-Item -ItemType Junction -Path $captureParentJunction -Target $captureExternalParent -ErrorAction Stop | Out-Null
    $captureParentBytes = [Text.Encoding]::ASCII.GetBytes('capture-parent evidence')
    $captureParentPreviousBytes = [Text.Encoding]::ASCII.GetBytes('capture-parent previous evidence')
    [IO.File]::WriteAllBytes((Join-Path $captureExternalParent 'capture.log'), $captureParentBytes)
    [IO.File]::WriteAllBytes((Join-Path $captureExternalParent 'capture.log.prev'), $captureParentPreviousBytes)
    $captureParentOpened = $null
    $captureParentThrew = $false
    $captureParentMessage = ''
    try {
        try {
            $captureParentOpened = Open-S150CaptureGeneration -CapturePath $captureThroughJunction `
                -CaptureBaseDirectory $capturePinnedBase -ArchiveDirectory $captureParentArchive `
                -ArchiveBaseDirectory $captureParentArchive -Generation ([guid]::NewGuid())
        } catch {
            $captureParentThrew = $true
            $captureParentMessage = $_.Exception.Message
        }
    } finally {
        if ($null -ne $captureParentOpened -and $null -ne $captureParentOpened.Stream) {
            $captureParentOpened.Stream.Dispose()
        }
    }
    Assert-True $captureParentThrew 'capture parent junction component must refuse'
    Assert-True ($captureParentMessage -match 'reparse') 'capture parent junction refusal must name the unsafe condition'
    Assert-BytesEqual ([IO.File]::ReadAllBytes((Join-Path $captureExternalParent 'capture.log'))) $captureParentBytes 'capture parent junction refusal must preserve external capture bytes'
    Assert-BytesEqual ([IO.File]::ReadAllBytes((Join-Path $captureExternalParent 'capture.log.prev'))) $captureParentPreviousBytes 'capture parent junction refusal must preserve external previous bytes'
    Assert-True ((Get-ChildItem -Force -LiteralPath $captureParentArchive).Count -eq 0) 'capture parent junction refusal must leave archive empty'

    # A junction cannot be accepted as the controlled certificate root: elevated
    # cleanup must fail before reading, deleting, or otherwise mutating its target.
    $certificateJunctionTarget = Join-Path $root 'certificate-junction-target'
    $certificateJunctionRoot = Join-Path $root 'certificate-junction-root'
    New-Item -ItemType Directory -Path $certificateJunctionTarget | Out-Null
    Write-TestCertificates $certificateJunctionTarget 'junction-target' ([datetime]::UtcNow.AddDays(-1))
    $certificateJunctionSentinel = Join-Path $certificateJunctionTarget 'sentinel.bin'
    $certificateJunctionSentinelBytes = [byte[]](91, 72, 44, 19, 255)
    [IO.File]::WriteAllBytes($certificateJunctionSentinel, $certificateJunctionSentinelBytes)
    $certificateJunctionBytes = @{}
    foreach ($name in @('root.crt', 'server.crt', 'server.key', 'sentinel.bin')) {
        $certificateJunctionBytes[$name] = [IO.File]::ReadAllBytes((Join-Path $certificateJunctionTarget $name))
    }
    New-Item -ItemType Junction -Path $certificateJunctionRoot -Target $certificateJunctionTarget -ErrorAction Stop | Out-Null
    try {
        $certificateJunctionThrew = $false
        $certificateJunctionMessage = ''
        try {
            Clear-S150CertificateArtifacts -CertificateDirectory $certificateJunctionRoot | Out-Null
        } catch {
            $certificateJunctionThrew = $true
            $certificateJunctionMessage = $_.Exception.Message
        }
        Assert-True $certificateJunctionThrew 'certificate cleanup must reject a reparse-point root'
        Assert-True ($certificateJunctionMessage -match 'reparse') 'reparse-point root rejection must name the unsafe condition'
        foreach ($name in $certificateJunctionBytes.Keys) {
            $targetPath = Join-Path $certificateJunctionTarget $name
            Assert-True (Test-Path -LiteralPath $targetPath -PathType Leaf) "reparse-point root rejection must preserve target $name"
            Assert-BytesEqual ([IO.File]::ReadAllBytes($targetPath)) $certificateJunctionBytes[$name] "reparse-point root rejection must not alter target $name"
        }
    } finally {
        if ([IO.Directory]::Exists($certificateJunctionRoot)) {
            [IO.Directory]::Delete($certificateJunctionRoot)
        }
    }

    # Direct child entries are fully validated before any deletion. A nested
    # junction therefore cannot traverse its target or cause partial cleanup.
    $certificateEntryRoot = Join-Path $root 'certificate-entry-root'
    $certificateEntryTarget = Join-Path $root 'certificate-entry-target'
    $certificateEntryJunction = Join-Path $certificateEntryRoot 'linked-certificates'
    New-Item -ItemType Directory -Path $certificateEntryRoot | Out-Null
    New-Item -ItemType Directory -Path $certificateEntryTarget | Out-Null
    Write-TestCertificates $certificateEntryRoot 'entry-root' ([datetime]::UtcNow.AddDays(-1))
    $certificateEntrySentinel = Join-Path $certificateEntryTarget 'sentinel.bin'
    $certificateEntrySentinelBytes = [byte[]](10, 20, 30, 40, 50)
    [IO.File]::WriteAllBytes($certificateEntrySentinel, $certificateEntrySentinelBytes)
    $certificateEntryBytes = @{}
    foreach ($name in @('root.crt', 'server.crt', 'server.key')) {
        $certificateEntryBytes[$name] = [IO.File]::ReadAllBytes((Join-Path $certificateEntryRoot $name))
    }
    New-Item -ItemType Junction -Path $certificateEntryJunction -Target $certificateEntryTarget -ErrorAction Stop | Out-Null
    try {
        $certificateEntryThrew = $false
        $certificateEntryMessage = ''
        try {
            Clear-S150CertificateArtifacts -CertificateDirectory $certificateEntryRoot | Out-Null
        } catch {
            $certificateEntryThrew = $true
            $certificateEntryMessage = $_.Exception.Message
        }
        Assert-True $certificateEntryThrew 'certificate cleanup must reject a direct reparse-point entry'
        Assert-True ($certificateEntryMessage -match 'reparse') 'direct reparse-point rejection must name the unsafe condition'
        Assert-BytesEqual ([IO.File]::ReadAllBytes($certificateEntrySentinel)) $certificateEntrySentinelBytes 'direct reparse-point rejection must not alter the linked target'
        foreach ($name in $certificateEntryBytes.Keys) {
            $entryPath = Join-Path $certificateEntryRoot $name
            Assert-True (Test-Path -LiteralPath $entryPath -PathType Leaf) "direct reparse-point rejection must preserve local $name"
            Assert-BytesEqual ([IO.File]::ReadAllBytes($entryPath)) $certificateEntryBytes[$name] "direct reparse-point rejection must not partially clear local $name"
        }
    } finally {
        if ([IO.Directory]::Exists($certificateEntryJunction)) {
            [IO.Directory]::Delete($certificateEntryJunction)
        }
    }

    # Controlled certificate preparation snapshots the exact expected artifacts
    # and strictly empties the verified directory before backend start.
    $certificateClearRoot = Join-Path $root 'certificate-clear'
    New-Item -ItemType Directory -Path $certificateClearRoot | Out-Null
    Write-TestCertificates $certificateClearRoot 'prior' ([datetime]::UtcNow.AddDays(-1))
    [IO.File]::WriteAllText((Join-Path $certificateClearRoot 'extra.txt'), 'strict clear includes extra files')
    $certificateSnapshot = Clear-S150CertificateArtifacts -CertificateDirectory $certificateClearRoot
    Assert-True ($certificateSnapshot.Artifacts.Count -eq 3) 'certificate clear must snapshot all three exact artifacts'
    Assert-True ((Get-ChildItem -Force -LiteralPath $certificateClearRoot).Count -eq 0) 'certificate clear must leave the directory strictly empty'

    # The immediate pre-start assertion must revalidate directory identity. A
    # post-cleanup swap to a junction cannot be mistaken for the cleared root.
    $certificateSwapRoot = Join-Path $root 'certificate-swapped-root'
    $certificateSwapTarget = Join-Path $root 'certificate-swapped-target'
    New-Item -ItemType Directory -Path $certificateSwapRoot, $certificateSwapTarget | Out-Null
    Write-TestCertificates $certificateSwapRoot 'swap-prior' ([datetime]::UtcNow.AddDays(-1))
    Clear-S150CertificateArtifacts -CertificateDirectory $certificateSwapRoot | Out-Null
    [IO.Directory]::Delete($certificateSwapRoot)
    $certificateSwapSentinel = Join-Path $certificateSwapTarget 'sentinel.bin'
    $certificateSwapSentinelBytes = [byte[]](61, 62, 63, 64, 65)
    [IO.File]::WriteAllBytes($certificateSwapSentinel, $certificateSwapSentinelBytes)
    New-Item -ItemType Junction -Path $certificateSwapRoot -Target $certificateSwapTarget -ErrorAction Stop | Out-Null
    try {
        $certificateSwapThrew = $false
        $certificateSwapMessage = ''
        try {
            Assert-S150CertificateArtifactsAbsent -CertificateDirectory $certificateSwapRoot
        } catch {
            $certificateSwapThrew = $true
            $certificateSwapMessage = $_.Exception.Message
        }
        Assert-True $certificateSwapThrew 'pre-start certificate assertion must reject a junction-swapped root'
        Assert-True ($certificateSwapMessage -match 'reparse') 'junction-swapped certificate root refusal must name the unsafe condition'
        Assert-BytesEqual ([IO.File]::ReadAllBytes($certificateSwapSentinel)) $certificateSwapSentinelBytes 'junction-swapped certificate refusal must preserve target bytes'
    } finally {
        if ([IO.Directory]::Exists($certificateSwapRoot)) {
            [IO.Directory]::Delete($certificateSwapRoot)
        }
    }

    # A handle without delete sharing must make strict cleanup fail rather than
    # silently accepting a surviving cert artifact.
    $certificateLockRoot = Join-Path $root 'certificate-locked'
    New-Item -ItemType Directory -Path $certificateLockRoot | Out-Null
    $lockedCertificate = Join-Path $certificateLockRoot 'root.crt'
    [IO.File]::WriteAllBytes($lockedCertificate, [Text.Encoding]::ASCII.GetBytes('locked-root-certificate'))
    $certificateLock = [IO.File]::Open($lockedCertificate, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    $lockedClearThrew = $false
    $lockedClearMessage = ''
    try {
        try {
            Clear-S150CertificateArtifacts -CertificateDirectory $certificateLockRoot | Out-Null
        } catch {
            $lockedClearThrew = $true
            $lockedClearMessage = $_.Exception.Message
        }
        Assert-True $lockedClearThrew 'locked certificate cleanup must throw'
        Assert-True ($lockedClearMessage -notmatch 'not recognized') 'locked certificate cleanup must fail at strict file removal, not a missing command'
        Assert-BytesEqual ([IO.File]::ReadAllBytes($lockedCertificate)) ([Text.Encoding]::ASCII.GetBytes('locked-root-certificate')) 'locked certificate must survive refused cleanup'
    } finally {
        $certificateLock.Dispose()
    }

    $certificateStartUtc = [datetime]::UtcNow.AddMinutes(-1)
    $certificateCurrentUtc = $certificateStartUtc.AddSeconds(10)

    $staleCertificateRoot = Join-Path $root 'certificate-stale'
    New-Item -ItemType Directory -Path $staleCertificateRoot | Out-Null
    Write-TestCertificates $staleCertificateRoot 'new' $certificateStartUtc.AddTicks(-1)
    $staleCertificates = Test-S150CertificateArtifacts -CertificateDirectory $staleCertificateRoot `
        -BackendStartUtc $certificateStartUtc -CurrentUtc $certificateCurrentUtc
    Assert-True (-not $staleCertificates.Valid) 'certificates with last-write before backend start must be rejected'

    $sameCertificateRoot = Join-Path $root 'certificate-same-hash'
    New-Item -ItemType Directory -Path $sameCertificateRoot | Out-Null
    Write-TestCertificates $sameCertificateRoot 'same' $certificateStartUtc.AddDays(-1)
    $sameCertificateSnapshot = Clear-S150CertificateArtifacts -CertificateDirectory $sameCertificateRoot
    Write-TestCertificates $sameCertificateRoot 'same' $certificateStartUtc.AddSeconds(1)
    $sameCertificates = Test-S150CertificateArtifacts -CertificateDirectory $sameCertificateRoot `
        -PriorSnapshot $sameCertificateSnapshot -BackendStartUtc $certificateStartUtc `
        -CurrentUtc $certificateCurrentUtc
    Assert-True (-not $sameCertificates.Valid) 'certificates matching prelaunch hashes must be rejected'

    $freshCertificateRoot = Join-Path $root 'certificate-fresh'
    New-Item -ItemType Directory -Path $freshCertificateRoot | Out-Null
    Write-TestCertificates $freshCertificateRoot 'prior' $certificateStartUtc.AddDays(-1)
    $freshCertificateSnapshot = Clear-S150CertificateArtifacts -CertificateDirectory $freshCertificateRoot
    Write-TestCertificates $freshCertificateRoot 'fresh' $certificateStartUtc.AddSeconds(1)
    $freshCertificates = Test-S150CertificateArtifacts -CertificateDirectory $freshCertificateRoot `
        -PriorSnapshot $freshCertificateSnapshot -BackendStartUtc $certificateStartUtc `
        -CurrentUtc $certificateCurrentUtc
    Assert-True ([bool]$freshCertificates.Valid) 'fresh nonempty certificates with changed hashes must be accepted'
    Assert-True ($freshCertificates.Artifacts.Count -eq 3) 'fresh certificate receipt must contain all three exact artifacts'

    # Admission revalidates the root rather than following a junction to an
    # otherwise fresh-looking external certificate triplet.
    $certificateAdmissionTarget = Join-Path $root 'certificate-admission-target'
    $certificateAdmissionRoot = Join-Path $root 'certificate-admission-root'
    New-Item -ItemType Directory -Path $certificateAdmissionTarget | Out-Null
    Write-TestCertificates $certificateAdmissionTarget 'admission-target' $certificateStartUtc.AddSeconds(1)
    $certificateAdmissionBytes = @{}
    foreach ($name in @('root.crt', 'server.crt', 'server.key')) {
        $certificateAdmissionBytes[$name] = [IO.File]::ReadAllBytes((Join-Path $certificateAdmissionTarget $name))
    }
    New-Item -ItemType Junction -Path $certificateAdmissionRoot -Target $certificateAdmissionTarget -ErrorAction Stop | Out-Null
    try {
        $certificateAdmission = Test-S150CertificateArtifacts -CertificateDirectory $certificateAdmissionRoot `
            -BackendStartUtc $certificateStartUtc -CurrentUtc $certificateCurrentUtc
        Assert-True (-not $certificateAdmission.Valid) 'certificate admission must reject a reparse-point root'
        Assert-True ($certificateAdmission.Reason -match 'reparse') 'certificate admission root refusal must name the unsafe condition'
        foreach ($name in $certificateAdmissionBytes.Keys) {
            $admissionTargetPath = Join-Path $certificateAdmissionTarget $name
            Assert-BytesEqual ([IO.File]::ReadAllBytes($admissionTargetPath)) $certificateAdmissionBytes[$name] "certificate admission root refusal must preserve target $name"
        }
    } finally {
        if ([IO.Directory]::Exists($certificateAdmissionRoot)) {
            [IO.Directory]::Delete($certificateAdmissionRoot)
        }
    }

    # Each expected admission artifact must itself be an ordinary regular file;
    # a file symlink cannot borrow fresh bytes and metadata from another path.
    $certificateEntryAdmissionRoot = Join-Path $root 'certificate-entry-admission'
    New-Item -ItemType Directory -Path $certificateEntryAdmissionRoot | Out-Null
    $certificateEntryAdmissionTarget = Join-Path $certificateEntryAdmissionRoot 'root.crt'
    $certificateEntryAdmissionTargetBytes = [Text.Encoding]::ASCII.GetBytes('external fresh root certificate')
    [IO.File]::WriteAllBytes($certificateEntryAdmissionTarget, $certificateEntryAdmissionTargetBytes)
    (Get-Item -LiteralPath $certificateEntryAdmissionTarget).LastWriteTimeUtc = $certificateStartUtc.AddSeconds(1)
    foreach ($name in @('server.crt', 'server.key')) {
        $entryCertificatePath = Join-Path $certificateEntryAdmissionRoot $name
        [IO.File]::WriteAllBytes($entryCertificatePath, [Text.Encoding]::ASCII.GetBytes("entry-admission-$name"))
        (Get-Item -LiteralPath $entryCertificatePath).LastWriteTimeUtc = $certificateStartUtc.AddSeconds(1)
    }
    $certificateEntryAdmissionLock = [IO.File]::Open(
        $certificateEntryAdmissionTarget,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::None
    )
    try {
        $certificateEntryAdmission = Test-S150CertificateArtifactsCore `
            -CertificateDirectory $certificateEntryAdmissionRoot `
            -BackendStartUtc $certificateStartUtc -CurrentUtc $certificateCurrentUtc `
            -GetAttributes {
                param($path)
                if ([string]::Equals(
                    [IO.Path]::GetFullPath($path),
                    [IO.Path]::GetFullPath($certificateEntryAdmissionTarget),
                    [StringComparison]::OrdinalIgnoreCase
                )) {
                    return ([IO.FileAttributes]::Archive -bor [IO.FileAttributes]::ReparsePoint)
                }
                return [IO.File]::GetAttributes($path)
            }
    } finally {
        $certificateEntryAdmissionLock.Dispose()
    }
    Assert-True (-not $certificateEntryAdmission.Valid) 'certificate admission must reject a reparse-point expected artifact'
    Assert-True ($certificateEntryAdmission.Reason -match 'reparse') 'certificate admission entry refusal must name the unsafe condition'
    Assert-BytesEqual ([IO.File]::ReadAllBytes($certificateEntryAdmissionTarget)) $certificateEntryAdmissionTargetBytes 'certificate admission entry refusal must preserve source bytes'

    # Completion is accepted only for the exact case-sensitive ASCII N-token and
    # for creation metadata inside both the backend and current-time fences.
    $completionRoot = Join-Path $root 'completion'
    New-Item -ItemType Directory -Path $completionRoot | Out-Null
    $completionCapture = Join-Path $completionRoot 'capture.log'
    $completionGeneration = [guid]::NewGuid()
    $completionGenerationText = $completionGeneration.ToString('N')
    $backendStart = [datetime]::UtcNow.AddMinutes(-2)
    $currentUtc = $backendStart.AddSeconds(45)
    [IO.File]::WriteAllBytes($completionCapture, [byte[]]@())

    Write-SharedCapture $completionCapture "prefix captureGeneration=$completionGenerationText suffix`n" $backendStart.AddSeconds(30)
    $validCompletion = Test-S150CaptureGenerationCompletion -CapturePath $completionCapture `
        -Generation $completionGeneration -BackendStartUtc $backendStart -CurrentUtc $currentUtc
    Assert-True ([bool]$validCompletion.Valid) 'completion must accept the exact N-format token inside the creation window'
    Assert-True ($validCompletion.Generation -ceq $completionGenerationText) 'valid completion must return the exact lowercase N-format generation'
    Assert-True ($validCompletion.CreationUtcTicks -eq $backendStart.AddSeconds(30).Ticks) 'valid completion must return exact creation UTC ticks'

    Write-SharedCapture $completionCapture "captureGeneration=$completionGenerationText`n" $backendStart.AddTicks(-1)
    $stale = Test-S150CaptureGenerationCompletion -CapturePath $completionCapture -Generation $completionGeneration `
        -BackendStartUtc $backendStart -CurrentUtc $currentUtc
    Assert-True (-not $stale.Valid) 'completion must refuse creation before backend start'

    Write-SharedCapture $completionCapture "captureGeneration=$completionGenerationText`n" $backendStart.AddSeconds(60).AddTicks(1)
    $late = Test-S150CaptureGenerationCompletion -CapturePath $completionCapture -Generation $completionGeneration `
        -BackendStartUtc $backendStart -CurrentUtc $backendStart.AddSeconds(61)
    Assert-True (-not $late.Valid) 'completion must refuse creation after backend start plus 60 seconds'

    Write-SharedCapture $completionCapture "captureGeneration=$completionGenerationText`n" $currentUtc.AddSeconds(2).AddTicks(1)
    $future = Test-S150CaptureGenerationCompletion -CapturePath $completionCapture -Generation $completionGeneration `
        -BackendStartUtc $backendStart -CurrentUtc $currentUtc
    Assert-True (-not $future.Valid) 'completion must refuse creation more than two seconds in the future'

    foreach ($invalidToken in @(
        'health probe completed without generation receipt',
        "captureGeneration=$($completionGeneration.ToString('D'))",
        "captureGeneration=$($completionGenerationText.Substring(0, 20))",
        "captureGeneration=$([guid]::NewGuid().ToString('N'))",
        "capturegeneration=$completionGenerationText"
    )) {
        Write-SharedCapture $completionCapture "$invalidToken`n" $backendStart.AddSeconds(30)
        $invalidCompletion = Test-S150CaptureGenerationCompletion -CapturePath $completionCapture `
            -Generation $completionGeneration -BackendStartUtc $backendStart -CurrentUtc $currentUtc
        Assert-True (-not $invalidCompletion.Valid) "completion must refuse near-match token: $invalidToken"
    }

    $expectedBackendPath = [IO.Path]::GetFullPath((Join-Path $root 'server\ags.exe'))

    # One exact fake backend, one exact post-start inventory, and one exact probe
    # must succeed without any stop callback and must release the held stream.
    $successRoot = Join-Path $root 'controlled-success'
    $successArchive = Join-Path $successRoot 'archive'
    New-Item -ItemType Directory -Path $successRoot, $successArchive | Out-Null
    $successCapture = Join-Path $successRoot 'capture.log'
    $successGeneration = [guid]::NewGuid()
    $successStartUtc = [datetime]::UtcNow
    $successBackend = New-FakeProcess 5150 'ags' $successStartUtc $expectedBackendPath
    $script:startCalls = 0
    $script:resolveCalls = 0
    $script:postInventoryCalls = 0
    $script:probeCalls = 0
    $script:stopCalls = 0
    $success = Invoke-S150ControlledLaunch -CapturePath $successCapture -ArchiveDirectory $successArchive `
        -Generation $successGeneration -PreStartInventory @() -ExpectedBackendPath $expectedBackendPath `
        -StartBackend { $script:startCalls++; $successBackend } `
        -ResolveProcess { param($processId) $script:resolveCalls++; $successBackend } `
        -PostStartInventory {
            param($backend)
            $script:postInventoryCalls++
            Assert-True ([object]::ReferenceEquals($backend, $successBackend)) 'post-start inventory must receive the exact resolved backend object'
            @($successBackend)
        } `
        -ProbeBackend {
            param($backend, $generationText)
            $script:probeCalls++
            Assert-True ($generationText -ceq $successGeneration.ToString('N')) 'controlled probe must receive exact N-format generation text'
            Write-SharedCapture $successCapture "captureGeneration=$generationText`n" $successStartUtc
        } `
        -StopProcess { param($process) $script:stopCalls++ }
    Assert-True (-not $success.Refused) 'exact controlled launch must not be refused'
    Assert-True ($script:startCalls -eq 1) 'controlled success must start exactly once'
    Assert-True ($script:resolveCalls -eq 1) 'controlled success must resolve the exact PID once'
    Assert-True ($script:postInventoryCalls -eq 1) 'controlled success must inspect post-start inventory once'
    Assert-True ($script:probeCalls -eq 1) 'controlled success must probe exactly once'
    Assert-True ($script:stopCalls -eq 0) 'controlled success must not stop the backend'
    Assert-True ($success.BackendIdentity.Id -eq $successBackend.Id) 'controlled success must return exact backend PID'
    Assert-True ($success.BackendIdentity.StartUtcTicks -eq $successBackend.StartTimeUtc.Ticks) 'controlled success must return exact backend start ticks'
    Assert-True ($success.BackendIdentity.Path -ceq $expectedBackendPath) 'controlled success must return exact canonical backend path'
    Assert-True ([bool]$success.Completion.Valid) 'controlled success must return a valid completion receipt'
    Assert-StreamReleased $successCapture 'controlled success must release the held capture stream'

    # Once controlled launch returns, every remaining pre-game action stays
    # guarded by the same pinned identity. A continuation failure stops exactly
    # the cleanup-resolved object and preserves the original failure.
    $continuationIdentity = $success.BackendIdentity
    $continuationResolved = New-FakeProcess $continuationIdentity.Id 'ags' `
        $continuationIdentity.StartTimeUtc $continuationIdentity.Path
    $script:continuationCalls = 0
    $script:continuationResolveCalls = 0
    $script:continuationStopCalls = 0
    $script:continuationStoppedObject = $null
    $continuationThrew = $false
    $continuationMessage = ''
    try {
        Invoke-S150ControlledContinuation -BackendIdentity $continuationIdentity `
            -Continuation { $script:continuationCalls++; throw 'synthetic continuation failure' } `
            -ResolveProcess {
                param($processId)
                $script:continuationResolveCalls++
                $continuationResolved
            } `
            -StopProcess {
                param($process)
                $script:continuationStopCalls++
                $script:continuationStoppedObject = $process
            } | Out-Null
    } catch {
        $continuationThrew = $true
        $continuationMessage = $_.Exception.Message
    }
    Assert-True $continuationThrew 'controlled continuation failure must throw'
    Assert-True ($script:continuationCalls -eq 1) 'controlled continuation must run exactly once'
    Assert-True ($script:continuationResolveCalls -eq 1) 'controlled continuation failure must re-resolve once'
    Assert-True ($script:continuationStopCalls -eq 1) 'controlled continuation failure must stop exactly once'
    Assert-True ([object]::ReferenceEquals($script:continuationStoppedObject, $continuationResolved)) 'controlled continuation must stop the exact cleanup-resolved object'
    Assert-True ($continuationMessage -match 'synthetic continuation failure') 'controlled continuation must preserve the original failure'

    $continuationDrifted = New-FakeProcess $continuationIdentity.Id 'ags' `
        $continuationIdentity.StartTimeUtc.AddTicks(1) $continuationIdentity.Path
    $script:continuationResolveCalls = 0
    $script:continuationStopCalls = 0
    $continuationDriftThrew = $false
    $continuationDriftMessage = ''
    try {
        Invoke-S150ControlledContinuation -BackendIdentity $continuationIdentity `
            -Continuation { throw 'synthetic drift continuation failure' } `
            -ResolveProcess {
                param($processId)
                $script:continuationResolveCalls++
                $continuationDrifted
            } `
            -StopProcess { param($process) $script:continuationStopCalls++ } | Out-Null
    } catch {
        $continuationDriftThrew = $true
        $continuationDriftMessage = $_.Exception.Message
    }
    Assert-True $continuationDriftThrew 'controlled continuation drift cleanup must throw'
    Assert-True ($script:continuationResolveCalls -eq 1) 'controlled continuation drift cleanup must re-resolve once'
    Assert-True ($script:continuationStopCalls -eq 0) 'controlled continuation drift cleanup must not stop the mismatched process'
    Assert-True ($continuationDriftMessage -match 'identity mismatch') 'controlled continuation drift cleanup must report identity mismatch'
    Assert-True ($continuationDriftMessage -match 'synthetic drift continuation failure') 'controlled continuation drift cleanup must preserve the original failure'

    $script:continuationStopCalls = 0
    $continuationCleanupMessage = ''
    try {
        Invoke-S150ControlledContinuation -BackendIdentity $continuationIdentity `
            -Continuation { throw 'synthetic original continuation failure' } `
            -ResolveProcess { param($processId) $continuationResolved } `
            -StopProcess {
                param($process)
                $script:continuationStopCalls++
                throw 'synthetic continuation cleanup failure'
            } | Out-Null
    } catch {
        $continuationCleanupMessage = $_.Exception.Message
    }
    Assert-True ($script:continuationStopCalls -eq 1) 'controlled continuation cleanup failure must attempt one exact stop'
    Assert-True ($continuationCleanupMessage -match 'synthetic original continuation failure') 'combined continuation error must preserve the original failure'
    Assert-True ($continuationCleanupMessage -match 'synthetic continuation cleanup failure') 'combined continuation error must preserve the cleanup failure'

    # A completion failure must re-resolve the pinned identity, stop exactly that
    # resolved object once, and only then release the held stream.
    $failureRoot = Join-Path $root 'controlled-completion-failure'
    $failureArchive = Join-Path $failureRoot 'archive'
    New-Item -ItemType Directory -Path $failureRoot, $failureArchive | Out-Null
    $failureCapture = Join-Path $failureRoot 'capture.log'
    $failureGeneration = [guid]::NewGuid()
    $failureStartUtc = [datetime]::UtcNow
    $failureBackend = New-FakeProcess 5250 'ags' $failureStartUtc $expectedBackendPath
    $failureResolved = New-FakeProcess 5250 'ags' $failureStartUtc $expectedBackendPath
    $failureCleanupResolved = New-FakeProcess 5250 'ags' $failureStartUtc $expectedBackendPath
    $script:startCalls = 0
    $script:resolveCalls = 0
    $script:probeCalls = 0
    $script:stopCalls = 0
    $script:stoppedObject = $null
    $failureThrew = $false
    try {
        Invoke-S150ControlledLaunch -CapturePath $failureCapture -ArchiveDirectory $failureArchive `
            -Generation $failureGeneration -PreStartInventory @() -ExpectedBackendPath $expectedBackendPath `
            -StartBackend { $script:startCalls++; $failureBackend } `
            -ResolveProcess {
                param($processId)
                $script:resolveCalls++
                if ($script:resolveCalls -eq 1) { $failureResolved } else { $failureCleanupResolved }
            } `
            -PostStartInventory { @($failureResolved) } `
            -ProbeBackend {
                param($backend, $generationText)
                $script:probeCalls++
                Write-SharedCapture $failureCapture 'probe completed without generation receipt' $failureStartUtc
            } `
            -StopProcess { param($process) $script:stopCalls++; $script:stoppedObject = $process } | Out-Null
    } catch {
        $failureThrew = $true
    }
    Assert-True $failureThrew 'completion failure must throw'
    Assert-True ($script:startCalls -eq 1) 'completion failure must start exactly once'
    Assert-True ($script:probeCalls -eq 1) 'completion failure must probe exactly once'
    Assert-True ($script:resolveCalls -eq 2) 'completion failure must re-resolve the exact PID for cleanup'
    Assert-True ($script:stopCalls -eq 1) 'completion failure must stop exactly once'
    Assert-True ([object]::ReferenceEquals($script:stoppedObject, $failureCleanupResolved)) 'completion failure must stop the exact cleanup-resolved object'
    Assert-StreamReleased $failureCapture 'completion failure must release the held capture stream'

    # Cleanup must fail closed on PID reuse, start-time drift, or path drift. In
    # every case the mismatched cleanup object must remain untouched.
    foreach ($drift in @('pid', 'start', 'path')) {
        $driftRoot = Join-Path $root "controlled-drift-$drift"
        $driftArchive = Join-Path $driftRoot 'archive'
        New-Item -ItemType Directory -Path $driftRoot, $driftArchive | Out-Null
        $driftCapture = Join-Path $driftRoot 'capture.log'
        $driftGeneration = [guid]::NewGuid()
        $driftStartUtc = [datetime]::UtcNow
        $driftBackend = New-FakeProcess 5350 'ags' $driftStartUtc $expectedBackendPath
        $driftResolved = New-FakeProcess 5350 'ags' $driftStartUtc $expectedBackendPath
        switch ($drift) {
            'pid'   { $driftCleanup = New-FakeProcess 5351 'ags' $driftStartUtc $expectedBackendPath }
            'start' { $driftCleanup = New-FakeProcess 5350 'ags' $driftStartUtc.AddTicks(1) $expectedBackendPath }
            'path'  { $driftCleanup = New-FakeProcess 5350 'ags' $driftStartUtc (Join-Path $root 'other\ags.exe') }
        }
        $script:resolveCalls = 0
        $script:stopCalls = 0
        $driftThrew = $false
        $driftMessage = ''
        try {
            Invoke-S150ControlledLaunch -CapturePath $driftCapture -ArchiveDirectory $driftArchive `
                -Generation $driftGeneration -PreStartInventory @() -ExpectedBackendPath $expectedBackendPath `
                -StartBackend { $driftBackend } `
                -ResolveProcess {
                    param($processId)
                    $script:resolveCalls++
                    if ($script:resolveCalls -eq 1) { $driftResolved } else { $driftCleanup }
                } `
                -PostStartInventory { @($driftResolved) } `
                -ProbeBackend { throw 'synthetic probe failure' } `
                -StopProcess { param($process) $script:stopCalls++ } | Out-Null
        } catch {
            $driftThrew = $true
            $driftMessage = $_.Exception.Message
        }
        Assert-True $driftThrew "$drift drift cleanup must throw"
        Assert-True ($script:resolveCalls -eq 2) "$drift drift cleanup must re-resolve the exact PID"
        Assert-True ($script:stopCalls -eq 0) "$drift drift cleanup must not stop a mismatched process"
        Assert-True ($driftMessage -match 'identity') "$drift drift cleanup must report identity mismatch"
        Assert-StreamReleased $driftCapture "$drift drift cleanup must release the held capture stream"
    }

    # Every post-start inventory except exactly the pinned ags and zero go must
    # fail before probing and stop only the exact re-resolved backend object.
    $inventoryStartUtc = [datetime]::UtcNow
    $inventoryBackend = New-FakeProcess 5450 'ags' $inventoryStartUtc $expectedBackendPath
    $otherAgs = New-FakeProcess 5451 'ags' $inventoryStartUtc $expectedBackendPath
    $wrongAgs = New-FakeProcess 5452 'ags' $inventoryStartUtc $expectedBackendPath
    $goProcess = New-FakeProcess 5453 'go' $inventoryStartUtc (Join-Path $root 'go.exe')
    $unrelatedProcess = New-FakeProcess 5454 'other' $inventoryStartUtc (Join-Path $root 'other.exe')
    foreach ($inventoryCase in @(
        [pscustomobject]@{ Name = 'empty'; Processes = @() },
        [pscustomobject]@{ Name = 'two-ags'; Processes = @($inventoryBackend, $otherAgs) },
        [pscustomobject]@{ Name = 'ags-plus-go'; Processes = @($inventoryBackend, $goProcess) },
        [pscustomobject]@{ Name = 'ags-plus-unrelated'; Processes = @($inventoryBackend, $unrelatedProcess) },
        [pscustomobject]@{ Name = 'wrong-ags'; Processes = @($wrongAgs) },
        [pscustomobject]@{ Name = 'go-only'; Processes = @($goProcess) }
    )) {
        $inventoryRoot = Join-Path $root "controlled-inventory-$($inventoryCase.Name)"
        $inventoryArchive = Join-Path $inventoryRoot 'archive'
        New-Item -ItemType Directory -Path $inventoryRoot, $inventoryArchive | Out-Null
        $inventoryCapture = Join-Path $inventoryRoot 'capture.log'
        $inventoryGeneration = [guid]::NewGuid()
        $cleanupResolved = New-FakeProcess 5450 'ags' $inventoryStartUtc $expectedBackendPath
        $script:resolveCalls = 0
        $script:probeCalls = 0
        $script:stopCalls = 0
        $script:stoppedObject = $null
        $inventoryThrew = $false
        try {
            Invoke-S150ControlledLaunch -CapturePath $inventoryCapture -ArchiveDirectory $inventoryArchive `
                -Generation $inventoryGeneration -PreStartInventory @() -ExpectedBackendPath $expectedBackendPath `
                -StartBackend { $inventoryBackend } `
                -ResolveProcess {
                    param($processId)
                    $script:resolveCalls++
                    if ($script:resolveCalls -eq 1) { $inventoryBackend } else { $cleanupResolved }
                } `
                -PostStartInventory { @($inventoryCase.Processes) } `
                -ProbeBackend { $script:probeCalls++ } `
                -StopProcess { param($process) $script:stopCalls++; $script:stoppedObject = $process } | Out-Null
        } catch {
            $inventoryThrew = $true
        }
        Assert-True $inventoryThrew "$($inventoryCase.Name): invalid post-start inventory must throw"
        Assert-True ($script:resolveCalls -eq 2) "$($inventoryCase.Name): invalid inventory must re-resolve for cleanup"
        Assert-True ($script:probeCalls -eq 0) "$($inventoryCase.Name): invalid inventory must fail before probe"
        Assert-True ($script:stopCalls -eq 1) "$($inventoryCase.Name): invalid inventory must stop exactly once"
        Assert-True ([object]::ReferenceEquals($script:stoppedObject, $cleanupResolved)) "$($inventoryCase.Name): invalid inventory must stop only the exact cleanup-resolved backend"
        Assert-StreamReleased $inventoryCapture "$($inventoryCase.Name): invalid inventory must release the held capture stream"
    }

    # A nonempty pre-start inventory is refusal, not cleanup: no archive/open,
    # backend start, resolver, probe, post-inventory, or stop callback may run.
    foreach ($name in @('ags', 'go')) {
        $refusalRoot = Join-Path $root "refusal-$name"
        $refusalCapture = Join-Path $refusalRoot 'capture.log'
        $refusalArchive = Join-Path $refusalRoot 'archive'
        $script:startCalls = 0
        $script:resolveCalls = 0
        $script:postInventoryCalls = 0
        $script:probeCalls = 0
        $script:stopCalls = 0
        $inventory = @(New-FakeProcess 4242 $name ([datetime]::UtcNow) (Join-Path $root "$name.exe"))
        $safeMode = Invoke-S150ControlledLaunch -CapturePath $refusalCapture `
            -ArchiveDirectory $refusalArchive -Generation ([guid]::NewGuid()) `
            -PreStartInventory $inventory -ExpectedBackendPath $expectedBackendPath `
            -StartBackend { $script:startCalls++; throw 'safe mode must refuse before backend launch' } `
            -ResolveProcess { $script:resolveCalls++; throw 'safe mode must refuse before resolve' } `
            -PostStartInventory { $script:postInventoryCalls++; throw 'safe mode must refuse before post-start inventory' } `
            -ProbeBackend { $script:probeCalls++; throw 'safe mode must refuse before probe' } `
            -StopProcess { param($process) $script:stopCalls++ }
        Assert-True ([bool]$safeMode.Refused) "safe mode must refuse a nonempty injected $name inventory"
        Assert-True ($script:startCalls -eq 0) "safe mode must issue zero start calls for injected $name inventory"
        Assert-True ($script:resolveCalls -eq 0) "safe mode must issue zero resolve calls for injected $name inventory"
        Assert-True ($script:postInventoryCalls -eq 0) "safe mode must issue zero post-inventory calls for injected $name inventory"
        Assert-True ($script:probeCalls -eq 0) "safe mode must issue zero probe calls for injected $name inventory"
        Assert-True ($script:stopCalls -eq 0) "safe mode must issue zero stop calls for injected $name inventory"
        Assert-True (-not (Test-Path -LiteralPath $refusalRoot)) "safe mode must refuse injected $name inventory before archive/open mutation"
    }
} finally {
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}

Write-Host 'PASS s150_capture_generation_test'
