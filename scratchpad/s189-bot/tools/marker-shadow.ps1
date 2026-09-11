# marker-shadow.ps1 -- FK-25 defence. docs/tutorial-launch-marker.txt is opened CREATE_ALWAYS by every
# injected shim, so every injection TRUNCATES it and the stager's own copy is a ~650-byte header taken
# 2 s after mapping. This loop keeps a live copy and saves every truncated GENERATION.
#   usage: marker-shadow.ps1 -EvDir <dir> -Label <label> [-Seconds 900]
param([string]$EvDir, [string]$Label, [int]$Seconds = 900)
$m = 'G:\git\Supervive Revival Project\docs\tutorial-launch-marker.txt'
$gen = 0; $last = ''; $t0 = Get-Date
"marker-shadow: $m -> $EvDir\$Label-marker-live.txt (gen files on truncation), $Seconds s"
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
    try {
        $fs = [IO.File]::Open($m, 'Open', 'Read', 'ReadWrite'); $sr = New-Object IO.StreamReader($fs)
        $cur = $sr.ReadToEnd(); $sr.Dispose(); $fs.Dispose()
    } catch { $cur = $null }
    if ($null -ne $cur -and $cur -ne $last) {
        if ($last -and -not $cur.StartsWith($last)) {
            $gen++; [IO.File]::WriteAllText("$EvDir\$Label-marker-gen$gen.txt", $last)
            "$(Get-Date -Format 'HH:mm:ss.fff') generation $gen saved ($($last.Length) bytes)"
        }
        [IO.File]::WriteAllText("$EvDir\$Label-marker-live.txt", $cur); $last = $cur
    }
    Start-Sleep -Milliseconds 250
}
"marker-shadow: done"
