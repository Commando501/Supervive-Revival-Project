# Getting a `.usmap` from SUPERVIVE (UE4SS + alternatives)

The Track A extractor (`tools/extractor`) needs a real `Mappings.usmap` to read property
values. This is the one blocker. Below is why the obvious routes fail on this game and the
two paths that actually work.

## The constraint (already verified)

`SUPERVIVE-Win64-Shipping.exe` is a **packed binary**: its PE import table lists ONLY
`preloader.dll`; the real UE5.4 engine is decrypted from `runtime.dll` at startup.
Consequences:

- **UE4SS dwmapi proxy never loads** — the exe imports no `dwmapi.dll`/`xinput`/etc., so
  no proxy DLL is ever mapped.
- **LoadLibrary injection is blocked** — the process has a **DLL-signature mitigation**
  (only Microsoft-signed images load through the loader). `tools/inject/` proves this.
- **Manual mapping bypasses the signature block** — it writes the DLL into memory without
  going through the loader's signature check. This is the route that works.
- **No EasyAntiCheat** is present (verified) — manual mapping is safe here.

## The real gotcha: the mapper must be COMPLETE

Manual-mapping is necessary but not sufficient. A minimal mapper (sections + relocs +
imports only) gets the bytes in but leaves the DLL non-functional. For UE4SS especially,
the map must also:

1. **Register a PEB/LDR entry** with the real on-disk path
   (`...\Win64\ue4ss\UE4SS.dll`). UE4SS finds its own folder via `GetModuleFileNameW`;
   an unlinked module returns nothing, so UE4SS can't find `UE4SS-settings.ini` / `Mods`
   / where to write `UE4SS.log` → it silently does nothing ("not linking", no console,
   no log).
2. **Register the exception unwind table** (`RtlAddFunctionTable` over `.pdata`). UE4SS is
   C++-exception-heavy; without this it dies on the first throw.
3. **Run TLS callbacks**, then **call `DllMain(DLL_PROCESS_ATTACH)`**.

Mappers that do all of this out of the box: **Blackbone / Xenos** (DarthTon) and
**GH Injector** — enable *Manual map* plus the *add-to-PEB / link-image* and
*exceptions / TLS* options. A self-rolled mapper missing PEB-linking is the usual reason
UE4SS maps but won't initialize.

Also: **map `ue4ss\UE4SS.dll` itself, not `dwmapi.dll`.** The dwmapi proxy's only job is
to `LoadLibrary` UE4SS.dll — which the signature mitigation blocks — so a mapped proxy
goes nowhere.

---

## Path A — UE4SS (full modding/dumping toolkit)

Install location (already deployed):
`...\SUPERVIVE\Loki\Binaries\Win64\ue4ss\` (settings have `ConsoleEnabled=1`,
`GuiConsoleEnabled=1`; `ModsFolderPath` is absolute).

1. Launch the game; reach the main menu.
2. Manual-map **`ue4ss\UE4SS.dll`** with a complete mapper (PEB-link + exceptions + TLS),
   as above.
3. Confirm it initialized: the **UE4SS GUI console** appears and **`Win64\ue4ss\UE4SS.log`**
   is created. (Run `get-usmap.ps1 -Check` to check the log from this side.)
4. Press **Ctrl + Numpad 6** (`DumpUSMAP` keybind, in
   `ue4ss\Mods\Keybinds\Scripts\main.lua`). UE4SS writes `Mappings.usmap` (the console
   prints the path; usually the Win64 dir).

If the console/log never appear, your mapper isn't PEB-linking — switch to Xenos/GH
Injector or use Path B.

## Path B — a self-contained usmap dumper (fastest unblock)

These are single DLLs with **no external-file dependency**, so the `GetModuleFileNameW`
path problem that breaks manually-mapped UE4SS doesn't apply — they manual-map far more
reliably. Either one produces the same `Mappings.usmap`:

- **UnrealMappingsDumper** (OutTheShade) — purpose-built, usmap only, leanest option.
- **Dumper-7** — larger (full SDK), also emits a usmap.

Steps: launch → reach menu → manual-map the dumper DLL (still needs a complete mapper for
exceptions/TLS/DllMain, but no PEB path requirement) → it writes `Mappings.usmap` to the
game dir / its output folder.

---

## Install the usmap for the extractor

Once any of the above produced a `Mappings.usmap`:

```powershell
# Auto-find the newest *.usmap, clear stale ones, copy into tools\extractor\:
powershell -ExecutionPolicy Bypass -File tools/usmap/get-usmap.ps1

# Then verify (from tools\extractor\extractor):
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release
#   -> "Loaded mappings: ...Mappings.usmap"  (not "No .usmap found")
```

Then `dump` mode reads exact structured JSON (ContentManifest,
`ContentServicePrimaryAsset`, cosmetic bundles, `DA_ArmoryTables_S1`, …) and Track A
unblocks. See `tools/extractor/README.md` and `docs/findings.md`.
