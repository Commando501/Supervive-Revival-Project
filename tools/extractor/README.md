# IoStore extractor (Track A)

A headless [CUE4Parse](https://github.com/FabianFG/CUE4Parse) (.NET 9) tool that reads
the SUPERVIVE UE5.4 IoStore paks at
`G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Content\Paks`.

## Why this exists

The menu's empty grids (Hunters, Store, owned cosmetics, Passes) and the
`<MISSING STRING TABLE ENTRY>` / "ITEM NAME" placeholders are NOT backend bugs — the
client already has the string tables and catalogs packed. What it's missing is the
**IDs/SKUs the backend must send back** so its lookups resolve. This tool reads those
IDs/SKUs out of the packed assets.

## Key facts (verified)

- The paks are **NOT AES-encrypted** (`EncryptionKeyGuid = 0`; `ContainerFlags = 0x0D`
  = Compressed|Signed|Indexed, no Encrypted bit) and keep their **directory index**, so
  they mount with **no key** and full file paths.
- `.ucas` blocks are **Oodle-compressed** → the tool auto-downloads `oo2core_9_win64.dll`
  from the OodleUE mirror on first run (the plain `DownloadOodleDll` URL is dead; use
  `DownloadOodleDllFromOodleUEAsync`).
- This is a **shipping build with unversioned properties**, so reading any asset's
  *property values* (DataTable rows, string-table entries, prices) requires a
  **`.usmap` mappings file**. The `IoPackage` constructor throws
  `Package has unversioned properties but mapping file is missing` without one — you
  can't even reach `NameMap` through CUE4Parse without it.

## Run

```sh
cd tools/extractor/extractor
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release            # enumerate -> out/
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- names <pkgpath...>   # dump NameMap (needs usmap in this build)
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- dump  <pkgpath...>   # dump exports as JSON (needs usmap)
```

`out/` holds `allfiles.txt` (107,123 entries), `topdirs.txt`, `heroes_codenames.txt`
(25 heroes), and themed buckets (stringtables/storefront/cosmetics/battlepass/datatables).

## The usmap (the one blocker)

Drop a `mappings.usmap` next to the built exe (`bin/Release/net9.0/`) and `dump`/`names`
modes work. Generate it with a runtime dumper against the live game — see
`docs/findings.md` Track A section. Anti-cheat risk is ~nil here (dead official servers,
local fake backend, direct-exe launch → EAC not enforcing).

## Key assets to read once a usmap exists

- `Loki/Content/Loki/Core/Armory/S1/DA_ArmoryTables_S1` — Armory/cosmetics catalog.
- `.../Monetization/Shared/ST_Cosmetics_Names`, `ST_Cosmetics_Categories` — cosmetic
  display-name + category string tables (keys = the SKU/ID vocabulary).
- `.../Monetization/Store/Shared/ST_Storefront`, plus `ST_MainMenu`, `ST_Currencies`,
  `ST_Items`, `ST_Rarities`, `ST_ShopNames`, `ST_Armory` — UI string tables.
- Per-hero cosmetics live at `Characters/Heroes/<Codename>/Cosmetics/<SkinName>/`.
