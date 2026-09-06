# Ghidra install for SUPERVIVE reverse-engineering

Installed during session 40 to unblock Path A1 (identify the crash class
at `SUPERVIVE-Win64-Shipping.exe +0x2976FF0`). See
`docs/session-40-crash-site-partial.txt` and
`docs/session-40-path-a3-partial.txt` for context.

## Install layout

- **JDK 21** (Eclipse Temurin 21.0.11+10 LTS): `E:\Tools\jdk-21`
  - SHA-256 verified against Adoptium API before extract
- **Ghidra 12.1.2** (public release 2026-06-05): `E:\Tools\ghidra`

Ghidra's `support/launch.properties` has `JAVA_HOME_OVERRIDE=E:\\Tools\\jdk-21`
set — Ghidra uses the bundled JDK, no PATH surgery, no interference with
the system's Java 1.8.

## Launch

- **GUI**: `E:\Tools\ghidra\ghidraRun.bat`
- **Headless (auto-analyze)**:
  ```powershell
  & 'E:\Tools\ghidra\support\analyzeHeadless.bat' `
    <project_dir> <project_name> `
    -import <path-to-exe> `
    -postScript <script>.java
  ```

## First-time analysis of SUPERVIVE

The shipping exe is ~175 MB. Full auto-analysis takes 30-60 minutes on
a typical machine. Recommended one-time step for the RE session:

```powershell
$proj = 'C:\Users\eastr\Documents\GhidraProjects\SUPERVIVE'
if (-not (Test-Path $proj)) { New-Item -ItemType Directory -Path $proj | Out-Null }
& 'E:\Tools\ghidra\support\analyzeHeadless.bat' $proj SV `
  -import 'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe' `
  -analysisTimeoutPerFile 3600
```

Then open the GUI, load the project, navigate to the target function.

## Path A1 lookup target (crash class identification)

Once auto-analysis is done, navigate in Ghidra to:

- **Crash instruction**: RVA `0x2976FF0` — the `mov qword ptr [rcx+8*rsi], rax`
  TArray Add-tail write.
- **Class static vtable**: RVA `0x7B9E188` in `.rdata`. The dtor is slot 0
  (RVA `0x296BD10`), slot 1 is the crashing method (RVA `0x2976F70`).
- **Constructor**: RVA `0x29676C0`. Factory wrapper (allocates 0x3C90
  bytes via FMemory::Malloc, tail-JMPs to ctor) at RVA `0x29BBBC9`.
- **Two live instances at runtime** (per `usmapdump findptr` in session 40):
  addresses vary per process launch, but each instance has offset 0x08
  pointing at a shared config/descriptor structure.

Ghidra should give us:
- The class NAME (via RTTI recovery even in stripped builds, Ghidra's
  data-type inference is generally good enough)
- The parent class / hierarchy
- Symbol names for the crash-chain callers (`+0x2984F45`, `+0x2983C27`,
  `+0x29838BE`, `+0x29CCD3E`)

## Uninstall

Both are self-contained folders. To remove:

```powershell
Remove-Item E:\Tools\ghidra -Recurse -Force
Remove-Item E:\Tools\jdk-21 -Recurse -Force
```

No registry entries, no environment variable changes, no start menu
shortcuts.
