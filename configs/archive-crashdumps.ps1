<#
  archive-crashdumps.ps1 -- preserve Sentry/crashpad crash reports before they are destroyed.

  WHY THIS EXISTS (FK-9, S109, 2026-08-04)
  ----------------------------------------
  When the game dies, UE's own handler does NOT always run. In every tutorial-route
  death observed so far, Sentry's crashpad handler takes over instead
  (`LogSentrySdk: handing control over to crashpad` in Loki.log) and writes a FULL
  minidump -- 43.8 MB, with 723 memory ranges -- plus a snapshot of that run's own
  Loki.log, into the GAME directory:

      <GameRoot>\Loki\.sentry-native\reports\<uuid>.dmp
      <GameRoot>\Loki\.sentry-native\attachments\<uuid>\Loki.log

  NO `UECC-*` directory is created. `tools/crashtri/harvest.py` and every hand-rolled
  `Get-ChildItem Saved\Crashes` census enumerates only `UECC-*`, so this entire
  failure mode was invisible for ~108 sessions.

  WHAT DESTROYS THE REPORT (MEASURED, S109) -- this is the load-bearing part
  --------------------------------------------------------------------------
  It is NOT a timer. Earlier notes recorded "uploaded and deleted within ~3 minutes",
  which led to a proposed filesystem watcher racing a clock. That was wrong.

  crashpad's own bookkeeping says exactly what happened. Decoding the 40-byte
  `settings.dat` (crashpad Settings::Data) and the `metadata` report record:

      settings.dat : magic=sdPC version=1 options=0x1 (uploads_enabled=TRUE)
                     last_upload_attempt_time = 14:10:29
      metadata     : creation_time            = 14:10:27   (the crash)
                     last_upload_attempt_time = 14:10:29   (crash + 2 s)
                     upload_attempts          = 1
                     state                    = 2 = Pending   (NOT Completed)

  So crashpad attempted the upload ONCE, two seconds after the crash, the attempt did
  not complete, and the report then sat in Pending for 65+ minutes with no retry.
  It does not retry because `crashpad_handler.exe` is a child of the game and exits
  with it -- once the game is dead nothing is alive to try again. The retry happens
  when a NEW handler starts, i.e. at the next game launch.

  That reconciles both prior observations. Session log timeline, 2026-08-04
  (log-open local / last activity UTC):

      02:07:09 -> died 07:10:53   report cleared by the 02:12:15 relaunch
      02:12:15 -> died 07:17:15   report cleared by the 02:19:58 relaunch
      02:19:58 -> died 07:22:30   report cleared by the 13:55:47 relaunch
      13:55:47 -> died 19:01:07   report cleared by the 14:02:15 relaunch
      14:02:15 -> died 19:10:26   NO relaunch followed -> report SURVIVED 65+ min

  The "~3 minute" figure was the interval to the next launch during a rapid iteration
  cycle, not a retention window. The one surviving report is the last one precisely
  because nothing was launched after it.

  => Archive immediately BEFORE launching. The launch is the destroyer, so this is
     deterministic, not a race. launch-redirect.ps1 calls it there and ONLY there.

  ★ CONFIRMED BY DIRECT EXPERIMENT, 2026-08-04 16:38 (this had been INFERRED only).
  A -NoHook launch was performed with one report pending. In the same second that the
  new crashpad_handler.exe started (16:38:51):

      reports/   1 report (43,804,912 B)  ->  EMPTY
      metadata   150 B, num_records=1     ->  16 B, num_records=0 (bare header)

  The pre-launch sweep had already taken it (SHA-256 f97c584c…, verified). So the rule
  is MEASURED: the launch clears the database, and archiving just before it loses
  nothing. NOTE the actor is the new crashpad_handler starting, not the game per se.

  There is deliberately NO post-exit sweep. `& $exe` does NOT block -- the shipping exe
  detaches and returns in ~1 s -- so a call placed after it runs before the game has
  even mounted its paks, duplicating the pre-launch archive under a misleading name.
  At pre-launch time Saved\Logs\Loki.log is still the DEAD session's log (UE rotates at
  startup), so the pre-launch sweep already captures the correct log for the death it
  is archiving. To grab a dump without waiting for the next launch, run this script by
  hand after the death.

  ⚠ RESIDUAL RISK, stated because an instrument must declare its own blind spot.
  This scheme depends on the upload FAILING. Uploads are globally enabled
  (options bit0 = 1) and the DSN host o566896.ingest.sentry.io IS reachable from this
  machine (TCP 443 OK -> 34.160.81.0); today's attempt failed for a reason we have not
  established (dead project / revoked key / 4xx are all plausible and untested). If an
  upload ever SUCCEEDS, the report is deleted ~2 s after the crash and NO pre-launch or
  post-exit sweep can catch it -- and neither could a filesystem watcher.
  Mitigation implemented here: if a run's Loki.log shows `handing control over to
  crashpad` but this script finds no report, it says so LOUDLY instead of printing the
  reassuring "nothing pending". If you see that warning, uploads have started
  succeeding; add o566896.ingest.sentry.io to the hosts block in launch-redirect.ps1.
  That is deliberately NOT done by default: it is unnecessary while uploads fail, and
  it puts a new variable on the crash path.

  SAFETY: read-only with respect to the crashpad database. The source is never
  deleted or modified -- crashpad owns that directory, and if a copy were ever bad we
  would still have the original. Copies land in <repo>\dumps\ which is git-ignored.

  usage:
    .\configs\archive-crashdumps.ps1                 # archive anything pending
    .\configs\archive-crashdumps.ps1 -Label fk7run3  # tag the destination directory
    .\configs\archive-crashdumps.ps1 -Quiet          # only speak if it finds something
#>
param(
  [string]$GameRoot = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE",
  [string]$Label    = "",
  [switch]$Quiet
)

$ErrorActionPreference = "Continue"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dbDir    = Join-Path $GameRoot "Loki\.sentry-native"
$repDir   = Join-Path $dbDir "reports"

if (-not (Test-Path $dbDir)) {
  if (-not $Quiet) { Write-Host "[crashdump] no crashpad database at $dbDir" -ForegroundColor DarkGray }
  return
}

# Pending reports are the .dmp files under reports\. Attachments/metadata are only
# meaningful alongside one, so an empty reports\ means there is nothing to save.
$dumps = @(Get-ChildItem -Path $repDir -Filter *.dmp -File -ErrorAction SilentlyContinue)
if ($dumps.Count -eq 0) {
  # An absence is only meaningful next to the blind spot that produced it. Before
  # printing the reassuring "nothing pending", check whether the most recent run
  # actually DIED -- if it did and there is no report, we have silently lost a dump
  # and the operator needs to know immediately, not at the next census.
  #
  # The key is `handing control over to crashpad`. NOTE: it is NOT the last line of
  # the log -- in the 2026-08-04 19:10:26 death two further LogTemp lines follow it --
  # so this must scan the whole file, never `tail`. Bare "crashpad" is useless as a
  # key: it also matches the two startup lines present in EVERY session.
  $lokiLog = Join-Path $env:LOCALAPPDATA "SUPERVIVE\Saved\Logs\Loki.log"
  $died = $false
  if (Test-Path $lokiLog) {
    try {
      $died = [bool](Select-String -Path $lokiLog -SimpleMatch `
                       -Pattern "handing control over to crashpad" -List -ErrorAction Stop)
    } catch { $died = $false }
  }
  if ($died) {
    Write-Warning "[crashdump] Loki.log shows a crashpad handoff but NO report is on disk."
    Write-Warning "[crashdump] A dump was almost certainly LOST. Most likely cause: the Sentry"
    Write-Warning "[crashdump] upload started SUCCEEDING (it deletes the report ~2 s after the"
    Write-Warning "[crashdump] crash, which no sweep or watcher can outrun)."
    Write-Warning '[crashdump] Fix: add  o566896.ingest.sentry.io  to $HostsToRedirect in'
    Write-Warning "[crashdump] configs\launch-redirect.ps1, then re-test. See this script's header."
  } elseif (-not $Quiet) {
    Write-Host "[crashdump] no pending crash reports to archive (and no crashpad handoff in Loki.log)." -ForegroundColor DarkGray
  }
  return
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$name  = "crashpad-$stamp"
if ($Label -ne "") { $name = "$name-$Label" }
$dest  = Join-Path $repoRoot "dumps\$name"

Write-Host ""
Write-Host "[crashdump] $($dumps.Count) pending crash report(s) found -- archiving before launch." -ForegroundColor Yellow
foreach ($d in $dumps) {
  Write-Host ("             {0}  {1:N0} bytes  {2}" -f $d.Name, $d.Length, $d.LastWriteTime) -ForegroundColor Yellow
}

try {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null

  # Copy the whole database: reports\, attachments\ (which carry each run's OWN
  # Loki.log -- often the single most useful artifact), plus metadata/last_crash/
  # settings.dat/.run dirs. The .run.lock files may be held open by a live handler;
  # they carry no information, so failures on them are ignored.
  Copy-Item -Path (Join-Path $dbDir "*") -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue

  # ---- also take the SESSION log, because the bundled one is TRUNCATED ----
  # MEASURED S109: the attachments\<uuid>\Loki.log is a byte-exact PREFIX of the real
  # session log, short by the final ~2.5 KB -- and what it drops is the terminal block,
  # INCLUDING the `handing control over to crashpad` line itself. Classifying a death
  # from the bundled log therefore false-negatives on the very key that identifies it.
  # (The UECC crash-dirs' bundled Loki.log has the identical defect: 0 of 80 contain
  # the key, guaranteed by construction, not by anything the game did.)
  #
  # The authoritative full log is Saved\Logs\Loki.log -- which the NEXT launch rotates
  # to Loki-backup-*.log, and UE keeps only ~1 day of those. That purge is why 85 of 87
  # historical crash dirs can never be matched to a session again. Grab it now.
  $lokiLog = Join-Path $env:LOCALAPPDATA "SUPERVIVE\Saved\Logs\Loki.log"
  if (Test-Path $lokiLog) {
    try {
      # -Force: the game may still hold it open for append; ReadWrite share is implied
      # by Copy-Item, and a partial copy still beats the truncated bundled one.
      Copy-Item -Path $lokiLog -Destination (Join-Path $dest "session-Loki.log") -Force -ErrorAction Stop
      $sz = (Get-Item (Join-Path $dest "session-Loki.log")).Length
      Write-Host ("[crashdump]   session log captured  {0:N0} bytes (authoritative; bundled copy is truncated)" -f $sz) -ForegroundColor Green
    } catch {
      Write-Warning "[crashdump] could not copy session Loki.log: $($_.Exception.Message)"
      Write-Warning "[crashdump] the bundled attachments\<uuid>\Loki.log is TRUNCATED -- terminal block will be missing."
    }
  } else {
    Write-Warning "[crashdump] no session Loki.log at $lokiLog -- only the TRUNCATED bundled copy was saved."
  }

  # Verify every .dmp round-tripped byte-for-byte. A silently truncated copy would
  # be worse than no copy at all, because it would read as success.
  $ok = 0; $bad = 0
  foreach ($d in $dumps) {
    $copy = Join-Path $dest ("reports\" + $d.Name)
    if (-not (Test-Path $copy)) {
      Write-Warning "[crashdump] MISSING after copy: $($d.Name)"; $bad++; continue
    }
    $srcHash = (Get-FileHash -Path $d.FullName -Algorithm SHA256).Hash
    $dstHash = (Get-FileHash -Path $copy      -Algorithm SHA256).Hash
    if ($srcHash -eq $dstHash) {
      Write-Host ("[crashdump]   verified {0}  sha256={1}" -f $d.Name, $srcHash.Substring(0,16)) -ForegroundColor Green
      $ok++
    } else {
      Write-Warning "[crashdump] HASH MISMATCH on $($d.Name) -- copy is NOT trustworthy"; $bad++
    }
  }

  # Record provenance next to the copy. Without this a dumps\ directory is just a
  # uuid with no run attached to it, which is how evidence gets orphaned.
  $note = @(
    "archived   : $(Get-Date -Format o)",
    "source     : $dbDir",
    "label      : $(if ($Label -ne '') { $Label } else { '(none)' })",
    "reports    : $($dumps.Count)  verified=$ok  failed=$bad",
    "trigger    : archive-crashdumps.ps1 (pre-launch sweep)",
    "",
    "NOTE: crashpad destroys pending reports at the NEXT game launch, not on a timer.",
    "This copy was taken immediately before a launch, so it is the death of the run",
    "that preceded it. Match it to the Loki-backup-*.log whose body ends with",
    "'handing control over to crashpad' (the key is mid-file, NOT the last line).",
    "Parse with: python tools/crashtri/mdctx.py <reports/*.dmp>"
  )
  Set-Content -Path (Join-Path $dest "ARCHIVE-INFO.txt") -Value $note -Encoding utf8

  if ($bad -eq 0) {
    Write-Host "[crashdump] archived to dumps\$name  ($ok verified)" -ForegroundColor Green
  } else {
    Write-Warning "[crashdump] archived to dumps\$name with $bad FAILURE(S) -- source left intact at $dbDir"
  }
} catch {
  # Never let archiving break a launch. A lost dump costs a run; a failed launch
  # costs a run too, and this is the less important of the two jobs.
  Write-Warning "[crashdump] archive failed: $($_.Exception.Message)"
  Write-Warning "[crashdump] source is UNTOUCHED at $dbDir -- copy it by hand before relaunching."
}
Write-Host ""
