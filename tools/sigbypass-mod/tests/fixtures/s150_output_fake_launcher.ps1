param(
    [Parameter(Mandatory = $true)][ValidateSet('InheritedBackend', 'IsolatedBackend', 'NativeGame')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$WriterExe,
    [Parameter(Mandatory = $true)][string]$BackendStdoutPath,
    [Parameter(Mandatory = $true)][string]$BackendStderrPath,
    [Parameter(Mandatory = $true)][string]$PidReceiptPath,
    [int]$DelayMs = 150,
    [int]$HoldMs = 6000,
    [string]$StdoutB64 = '-',
    [string]$StderrB64 = '-'
)

# Test-only fake launcher. It reproduces the three launcher/backend output
# shapes the real launcher can produce:
#   InheritedBackend - fixture inherits this launcher's stdout (the Flight 2
#       defect: backend keeps a writer to the launcher's stdout).
#   IsolatedBackend  - fixture stdout/stderr are redirected to distinct backend
#       files (the successor fix).
#   NativeGame       - exact `& $exe @args` GUI invocation that returns while the
#       fixture remains alive.
# This launcher's own stdout/stderr are redirected by the caller.

$ErrorActionPreference = 'Stop'

function Get-QuotedArg([string]$Value) {
    if ($Value -eq '' -or $Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

$argArray = @(
    '--pid-file', $PidReceiptPath,
    '--delay-ms', [string]$DelayMs,
    '--hold-ms', [string]$HoldMs,
    '--stdout-ascii', $StdoutB64,
    '--stderr-ascii', $StderrB64
)
$argString = ($argArray | ForEach-Object { Get-QuotedArg $_ }) -join ' '

switch ($Mode) {
    'InheritedBackend' {
        # stdout is inherited (goes to this launcher's own redirected stdout);
        # only stderr is redirected, exactly like the pre-successor launcher.
        Start-Process -FilePath $WriterExe -ArgumentList $argString `
            -RedirectStandardError $BackendStderrPath -PassThru | Out-Null
    }
    'IsolatedBackend' {
        Start-Process -FilePath $WriterExe -ArgumentList $argString `
            -RedirectStandardOutput $BackendStdoutPath `
            -RedirectStandardError $BackendStderrPath -PassThru | Out-Null
    }
    'NativeGame' {
        & $WriterExe @argArray
    }
}
exit 0
