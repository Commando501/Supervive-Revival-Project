<#
.SYNOPSIS
  Guarantee that docs\capture.log is FRESH under our clock before ags opens it.

.DESCRIPTION
  S149 flight 1 refused at "capture-generation admission" because the launcher
  killed the prior ags and then handed the SAME path (docs\capture.log) to the
  fresh backend without touching the on-disk file. The fresh ags opened the
  existing directory entry -- Go's os.Create/append semantics preserve
  CreationTime -- so the S149 admission gate saw the capture's stale
  CreationTimeUtc (~3 hours older than the new backend's process start) and
  refused. Measured delta: -10849.32 s
  (docs\s149-bind-bootstrap-flight1.md:230-234).

  This gate, invoked BETWEEN backend build and Start-Process, replaces the
  on-disk entry with a fresh one and stamps CreationTimeUtc under OUR clock:

    1. Archive any existing docs\capture.log to
       docs\capture.log.pre-<label>-<UTC-stamp> via IO.File.Move. This is the
       same "docs/capture.log.pre-<label>" naming convention the repo already
       uses for one-off backups, so no evidence is clobbered.

    2. Create a new capture.log with IO.File.Open(CreateNew) -- fails loudly
       if a file with the canonical name still exists (i.e. the archive step
       above did not run for some reason).

    3. Force CreationTimeUtc = UtcNow via IO.File.SetCreationTimeUtc. The
       explicit override defeats NTFS File-System Tunneling (KB 172190)
       deterministically -- verifier flagged the earlier "rename moves the
       tunnel key" claim as WRONG, so we do not rely on that behaviour. Even
       if tunneling somehow re-applied a stale CreationTime, this override
       stamps the file under UtcNow.

    4. Assert that the resulting file's CreationTimeUtc is <= 5 s old. This is
       a proof-of-freshness for the S149 gate; any drift beyond 5 s means
       something is seriously wrong with the local clock or the file system
       and the flight would otherwise silently refuse anyway.

  The gate is off by default. It runs only when launch-redirect.ps1 is
  invoked with -ResetCapture (which the S149 flight helper will do).

.PARAMETER CapturePath   Absolute path to the docs\capture.log file to gate.
.PARAMETER Label         Tag appended to the archive name for provenance
                         (typically the flight label -- e.g. 's149-bind').
#>
param(
    [Parameter(Mandatory=$true)][string]$CapturePath,
    [Parameter(Mandatory=$true)][string]$Label
)

$ErrorActionPreference = 'Stop'

$canonical = [IO.Path]::GetFullPath($CapturePath)
$dir       = Split-Path -Parent $canonical
$stamp     = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$archive   = Join-Path $dir ("capture.log.pre-{0}-{1}" -f $Label, $stamp)

if (Test-Path -LiteralPath $canonical) {
    # No-clobber: if the archive path already exists, someone else has already
    # taken this timestamp -- refuse rather than overwrite evidence.
    if (Test-Path -LiteralPath $archive) {
        throw "capture-gate: archive already exists: $archive"
    }
    [IO.File]::Move($canonical, $archive)
}
# The launcher also creates a rolling ".prev" (per docs/capture.log.prev in
# .gitignore). Archive it alongside if present so the next capture.log doesn't
# inherit a mismatched sibling.
if (Test-Path -LiteralPath "$canonical.prev") {
    $prevArchive = "$archive.prev"
    if (Test-Path -LiteralPath $prevArchive) {
        throw "capture-gate: prev archive already exists: $prevArchive"
    }
    [IO.File]::Move("$canonical.prev", $prevArchive)
}

# CreateNew + explicit SetCreationTimeUtc: deterministic freshness even if
# NTFS File-System Tunneling activates. The verifier established that Move
# does NOT migrate the tunnel key, so the SetCreationTimeUtc below is the
# actual guarantor.
$fs = [IO.File]::Open(
    $canonical,
    [IO.FileMode]::CreateNew,
    [IO.FileAccess]::ReadWrite,
    [IO.FileShare]::ReadWrite
)
try {
    $fs.Flush($true)
} finally {
    $fs.Dispose()
}

$now = [datetime]::UtcNow
[IO.File]::SetCreationTimeUtc($canonical, $now)

# Proof-of-freshness. The S149 gate compares CreationTimeUtc to backend
# process-start UTC and requires the file to have been created within a 60 s
# window. 5 s here is well inside that budget.
$info   = [IO.FileInfo]::new($canonical)
$ageSec = ([datetime]::UtcNow - $info.CreationTimeUtc).TotalSeconds
if ($ageSec -gt 5) {
    throw "capture-gate: CreationTimeUtc stale after force-set (age = $ageSec s)"
}

Write-Host ("capture-gate: archived -> {0}; fresh CreationTimeUtc age {1:N2}s" -f $archive, $ageSec) `
    -ForegroundColor Cyan
