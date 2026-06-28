using CUE4Parse.Compression;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.AssetRegistry;
using CUE4Parse.UE4.AssetRegistry.Objects;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Readers;
using CUE4Parse.UE4.Versions;
using Newtonsoft.Json;

// SUPERVIVE Revival — IoStore enumerator (Track A, pass 1).
//
// The paks are UE5.4, NOT AES-encrypted (EncryptionKeyGuid = 0, ContainerFlags
// lacks the Encrypted bit) and retain their directory index, so we can mount and
// list every packaged file WITHOUT a key and WITHOUT a .usmap. This pass only
// enumerates paths — it answers "is the hero catalog / string tables / storefront
// catalog actually baked into the shipped paks, or delivered at runtime via
// /content-service/manifest?" Reading asset *property values* (DataTable rows)
// comes later and may need a .usmap.

var cmd = args.Length > 0 && (args[0] == "dump" || args[0] == "names" || args[0] == "namesall" || args[0] == "schema" || args[0] == "assetregistry") ? args[0] : null;
var dumpMode = cmd == "dump";
var pakDir = (cmd == null && args.Length > 0)
    ? args[0]
    : @"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Content\Paks";
var outDir = (cmd == null && args.Length > 1)
    ? args[1]
    : @"G:\git\Supervive Revival Project\tools\extractor\out";
Directory.CreateDirectory(outDir);

Console.WriteLine($"Paks: {pakDir}");
Console.WriteLine($"Out:  {outDir}");

// assetregistry mode: read the cooked Loki/AssetRegistry.bin standalone — no paks, no
// .usmap, no Oodle. The cook bakes EVERY content asset (Mission/MissionPool/Hero/
// StoreOffer/Item/cosmetic) into this file with its FAssetData (PackagePath, AssetClass,
// PackageName, AssetName, tags, bundles). LokiAssetManager bypasses the standard
// AssetManager directory scan, so these entries are present but never registered as
// primary assets at runtime — these subcommands let us SEE exactly what's in the
// registry so we can decide which entries to flip and how.
//
//   usage: assetregistry <inspect|stats|namemap|classes|candidates> [ar.bin] [args...]
//          ar.bin defaults to <outDir>\AssetRegistry.bin
if (cmd == "assetregistry")
{
    if (args.Length < 2)
    {
        Console.WriteLine("usage: assetregistry <inspect|stats|namemap|classes|candidates> [ar.bin] [args...]");
        Console.WriteLine($"       (ar.bin defaults to {Path.Combine(outDir, "AssetRegistry.bin")})");
        return;
    }

    var sub = args[1];
    // Path-or-arg disambiguation: args[2] is the bin path iff it points at an existing
    // file; otherwise treat args[2..] as sub-command args and use the default bin path.
    var defaultBin = Path.Combine(outDir, "AssetRegistry.bin");
    var arPath = (args.Length >= 3 && File.Exists(args[2])) ? args[2] : defaultBin;
    var subArgs = args.Skip(arPath == defaultBin ? 2 : 3).ToArray();

    if (!File.Exists(arPath))
    {
        Console.WriteLine($"AssetRegistry.bin not found at {arPath}");
        Console.WriteLine("Pass an explicit path as args[2], or copy the extracted bin to the default location.");
        return;
    }
    Console.WriteLine($"AR bin: {arPath}  ({new FileInfo(arPath).Length:N0} bytes)");

    // EGame.GAME_UE5_4 picks the right version-gated branches in the FAssetRegistryState
    // reader (RemoveAssetPathFNames + ClassPaths + MarshalledTextAsUTF8String + the
    // AddedDependencyFlags dependency-section header). Wrong game → silent misparse.
    using var fs = File.OpenRead(arPath);
    var Ar = new FStreamArchive(arPath, fs, new VersionContainer(EGame.GAME_UE5_4));
    var state = new FAssetRegistryState(Ar);
    var entries = state.PreallocatedAssetDataBuffers;
    Console.WriteLine($"Loaded {entries.Length:N0} FAssetData / "
                    + $"{state.PreallocatedDependsNodeDataBuffers.Length:N0} DependsNode / "
                    + $"{state.PreallocatedPackageDataBuffers.Length:N0} PackageData.");

    // Per-entry formatter shared by inspect & candidates. Tags are pulled from the
    // FStore via FAssetData.TagsAndValues (already string-resolved by the reader).
    // Bundles uses a typed empty array on the null branch so the ternary stays in one
    // anonymous-type family (mixing with object[] breaks C# type inference).
    static object Snapshot(FAssetData a)
    {
        var bundles = (a.TaggedAssetBundles?.Bundles ?? Array.Empty<FAssetBundleEntry>())
            .Select(b => new
            {
                Name = b.BundleName.Text,
                Assets = b.BundleAssets.Select(p => p.ToString()).ToArray(),
            }).ToArray();
        return new
        {
            PackageName = a.PackageName.Text,
            AssetName = a.AssetName.Text,
            PackagePath = a.PackagePath.Text,
            AssetClass = a.AssetClass.Text,
            ChunkIDs = a.ChunkIDs,
            PackageFlags = ((uint) a.PackageFlags).ToString("X8"),
            Tags = a.TagsAndValues?.ToDictionary(kv => kv.Key.Text, kv => kv.Value)
                ?? new Dictionary<string, string>(),
            Bundles = bundles,
        };
    }

    Directory.CreateDirectory(outDir);

    switch (sub)
    {
        case "inspect":
        {
            // Substring filter (case-insensitive) across PackageName / PackagePath /
            // AssetClass / AssetName. Empty filter = dump everything (a few hundred MB
            // of JSON — only useful piped through grep).
            var needle = subArgs.FirstOrDefault() ?? "";
            bool Match(FAssetData a) => needle.Length == 0
                || a.PackageName.Text.Contains(needle, StringComparison.OrdinalIgnoreCase)
                || a.PackagePath.Text.Contains(needle, StringComparison.OrdinalIgnoreCase)
                || a.AssetClass.Text.Contains(needle, StringComparison.OrdinalIgnoreCase)
                || a.AssetName.Text.Contains(needle, StringComparison.OrdinalIgnoreCase);
            var hits = entries.Where(Match).Select(Snapshot).ToList();
            var safe = string.IsNullOrEmpty(needle) ? "ALL" : needle.Replace('/', '_').Replace('\\', '_');
            var outFile = Path.Combine(outDir, $"assetregistry_inspect_{safe}.json");
            File.WriteAllText(outFile, JsonConvert.SerializeObject(hits, Formatting.Indented));
            Console.WriteLine($"  matched {hits.Count:N0} / {entries.Length:N0} entries -> {outFile}");
            // Also surface the first ~20 hits to stdout so the operator sees results
            // immediately without opening the JSON.
            foreach (var h in hits.Take(20)) Console.WriteLine($"    {((dynamic) h).AssetClass,-48} {((dynamic) h).PackageName}");
            if (hits.Count > 20) Console.WriteLine($"    ... +{hits.Count - 20} more in JSON");
            return;
        }

        case "stats":
        {
            // Two histograms: (a) every AssetClass with its entry count, (b) every tag
            // KEY ever attached to ANY entry, with the number of entries carrying it.
            // The tag-key histogram is the smoking gun for "did the cooker bake the
            // PrimaryAssetType / PrimaryAssetName tags into the asset metadata, or did
            // it strip them?". If those keys appear, the data is in the registry and
            // the only thing missing is the runtime registration step.
            var classHisto = entries.GroupBy(e => e.AssetClass.Text)
                .Select(g => new { Class = g.Key, Count = g.Count() })
                .OrderByDescending(x => x.Count).ToList();
            var tagHisto = entries.Where(e => e.TagsAndValues != null)
                .SelectMany(e => e.TagsAndValues.Keys.Select(k => k.Text))
                .GroupBy(k => k)
                .Select(g => new { Tag = g.Key, Count = g.Count() })
                .OrderByDescending(x => x.Count).ToList();

            // Primary-asset suggestive classes — string-match what we know LokiAssetManager
            // declares (Mission / MissionPool / Hero / StoreOffer / Item / cosmetic bundles).
            // Substring match catches Loki* / BP_*Asset_* / DA_* naming variations.
            string[] needles = ["Mission", "MissionPool", "Hero", "StoreOffer", "Item",
                                "HeroCosmetic", "SlotCosmetic", "Emote", "PlayerTitle",
                                "LobbyPlatform", "GameAugment", "Equipment", "Power", "Minion"];
            var primaryCandidates = classHisto.Where(c => needles.Any(n =>
                    c.Class.Contains(n, StringComparison.OrdinalIgnoreCase)))
                .ToList();

            var outFile = Path.Combine(outDir, "assetregistry_stats.json");
            File.WriteAllText(outFile, JsonConvert.SerializeObject(new
            {
                Totals = new { Entries = entries.Length, UniqueClasses = classHisto.Count },
                PrimaryAssetSuggestiveClasses = primaryCandidates,
                AllClassesTop100 = classHisto.Take(100),
                AllClasses = classHisto,
                TagKeyHistogram = tagHisto,
            }, Formatting.Indented));
            Console.WriteLine($"  {classHisto.Count:N0} unique classes; primary-suggestive:");
            foreach (var c in primaryCandidates.Take(30))
                Console.WriteLine($"    {c.Count,6}  {c.Class}");
            Console.WriteLine($"  top tag keys:");
            foreach (var t in tagHisto.Take(15))
                Console.WriteLine($"    {t.Count,6}  {t.Tag}");
            Console.WriteLine($"  -> {outFile}");
            return;
        }

        case "namemap":
        {
            // We need the NameMap as plain text to find indices of class FName strings
            // we want to write into modified FAssetData entries (the surgical patch
            // pre-step). FAssetRegistryState doesn't expose the NameMap directly; we
            // re-read just the header + LoadNameBatch on a fresh stream and write
            // "index : name" lines. (LoadNameBatch is internal-style; re-using the
            // public FAssetRegistryReader is cheaper than reimplementing it.)
            using var fs2 = File.OpenRead(arPath);
            var Ar2 = new FStreamArchive(arPath, fs2, new VersionContainer(EGame.GAME_UE5_4));
            var header = new FAssetRegistryHeader(Ar2);
            var reader = new FAssetRegistryReader(Ar2, header);
            var outFile = Path.Combine(outDir, "assetregistry_namemap.txt");
            using (var sw = new StreamWriter(outFile))
            {
                sw.WriteLine($"# NameMap: {reader.NameMap.Length:N0} entries");
                sw.WriteLine($"# version: {header.Version}");
                for (var i = 0; i < reader.NameMap.Length; i++)
                {
                    sw.WriteLine($"{i,7}  {reader.NameMap[i].Name}");
                }
            }
            Console.WriteLine($"  {reader.NameMap.Length:N0} names -> {outFile}");
            return;
        }

        case "classes":
        {
            // Just the unique AssetClass strings, sorted alphabetically, one per line.
            // Companion to `namemap` — much smaller and easier to grep for primary-
            // asset-type candidates ("LokiDataAsset_", "BP_HeroAsset_", "DA_*").
            var classes = entries.Select(e => e.AssetClass.Text).Distinct()
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
            var outFile = Path.Combine(outDir, "assetregistry_classes.txt");
            File.WriteAllLines(outFile, classes);
            Console.WriteLine($"  {classes.Count:N0} unique AssetClass values -> {outFile}");
            return;
        }

        case "candidates":
        {
            // For one primary-asset-type pattern (substring, case-insensitive), list
            // every FAssetData whose AssetClass matches. Writes a JSON file with full
            // snapshot per hit — that's the input to the future `apply-patch` step.
            //   assetregistry candidates Mission
            //   assetregistry candidates LokiHero
            // The output also surfaces TAGS on each hit, so we can confirm whether the
            // cook baked PrimaryAssetType/PrimaryAssetName tags on these entries.
            if (subArgs.Length < 1)
            {
                Console.WriteLine("usage: assetregistry candidates <classNeedle>");
                Console.WriteLine("       e.g. Mission, LokiDataAsset_Mission, BP_HeroAsset, StoreOffer");
                return;
            }
            var needle = subArgs[0];
            var hits = entries
                .Where(e => e.AssetClass.Text.Contains(needle, StringComparison.OrdinalIgnoreCase))
                .Select(Snapshot).ToList();
            var safe = needle.Replace('/', '_').Replace('\\', '_');
            var outFile = Path.Combine(outDir, $"assetregistry_candidates_{safe}.json");
            File.WriteAllText(outFile, JsonConvert.SerializeObject(hits, Formatting.Indented));
            Console.WriteLine($"  {hits.Count:N0} entries with class matching '{needle}' -> {outFile}");
            foreach (var h in hits.Take(20))
            {
                dynamic d = h;
                var tagKeys = string.Join(",", ((Dictionary<string, string>) d.Tags).Keys.Take(8));
                Console.WriteLine($"    {d.AssetClass,-44} {d.PackageName}  [tags: {tagKeys}]");
            }
            if (hits.Count > 20) Console.WriteLine($"    ... +{hits.Count - 20} more in JSON");
            return;
        }

        case "apply-patch":
        {
            // Walker helper, declared inside this case so top-level statements aren't
            // interrupted by a type declaration. An asset-data FName cell is uint32 index;
            // if the high bit (0x80000000 = AssetRegistryNumberedNameBit) is set, a uint32
            // number follows ⇒ cell width 4 or 8 bytes on the wire.
            static void SkipFName(CUE4Parse.UE4.Readers.FArchive Ar)
            {
                uint raw = Ar.Read<uint>();
                if ((raw & 0x80000000u) != 0) Ar.Read<uint>();
            }
            // Surgical 8-byte flip of one or more FAssetData entries' AssetClass
            // FTopLevelAssetPath (two FName cells: PackageName + AssetName). File length is
            // preserved when neither original NOR replacement uses the numbered-name bit —
            // class names like "Blueprint" or "LokiDataAsset_MissionPool" never do, so the
            // patch is exactly 8 bytes per matched entry, no offset fixups needed in the
            // dependency-block section header.
            //
            //   usage: apply-patch --target <PkgNeedle>[:<AssetExact>] --to <Pkg>:<Asset>
            //                      [--out <patched.bin>]
            //   e.g.  apply-patch --target DA_MissionPoolDailyChallenge
            //                     --to /Script/Loki:LokiDataAsset_MissionPool
            //
            // --target matches entries whose PackageName CONTAINS the pkg needle (case-
            // insensitive). If :AssetExact is given, AssetName must match it exactly (case-
            // insensitive) — useful for picking only the BlueprintGeneratedClass _C entry.
            //
            // Algorithm:
            //   1. Re-parse the header/namemap/FStore via FAssetRegistryReader. After
            //      construction the reader's archive Position sits at int32 numAssetData
            //      (the very next read in CUE4Parse's FAssetRegistryState.Load).
            //   2. Walk each FAssetData manually, mirroring CUE4Parse's reader byte-for-byte
            //      so we can record the byte offset of the AssetClass field for each entry.
            //      Cross-check by reading the entry's PackageName FName indices and confirming
            //      they match the state-parsed entries[i].PackageName.Text via NameMap.
            //   3. For matched entries with non-numbered AssetClass FNames, overwrite 8 bytes
            //      at the recorded offset in a COPY of the file. Original untouched.
            string? targetArg = null, toArg = null, outPath = null;
            for (int i = 0; i < subArgs.Length; i++)
            {
                if (subArgs[i] == "--target" && i + 1 < subArgs.Length) targetArg = subArgs[++i];
                else if (subArgs[i] == "--to" && i + 1 < subArgs.Length) toArg = subArgs[++i];
                else if (subArgs[i] == "--out" && i + 1 < subArgs.Length) outPath = subArgs[++i];
            }
            if (targetArg == null || toArg == null)
            {
                Console.WriteLine("usage: assetregistry apply-patch --target <PkgNeedle>[:<AssetExact>] --to <Pkg>:<Asset> [--out <patched.bin>]");
                Console.WriteLine("       e.g. --target DA_MissionPoolDailyChallenge --to /Script/Loki:LokiDataAsset_MissionPool");
                return;
            }

            var toParts = toArg.Split(':', 2);
            if (toParts.Length != 2) { Console.WriteLine("--to must be PackageName:AssetName"); return; }
            var (toPkg, toAsset) = (toParts[0], toParts[1]);

            string targetPkg; string targetAssetExact = "";
            var tp = targetArg.Split(':', 2);
            targetPkg = tp[0]; if (tp.Length == 2) targetAssetExact = tp[1];

            // Re-load via the same archive instance: FAssetRegistryReader's Position is
            // shared with the underlying FStreamArchive (the reader only overrides FName
            // reads; raw byte reads still go through the stream). After the reader is
            // constructed the archive Position is at numAssetData.
            using var fs3 = File.OpenRead(arPath);
            var Ar3 = new FStreamArchive(arPath, fs3, new VersionContainer(EGame.GAME_UE5_4));
            var hdr = new FAssetRegistryHeader(Ar3);
            var rdr = new FAssetRegistryReader(Ar3, hdr);

            // Resolve the --to PackageName/AssetName to NameMap indices. Case-insensitive
            // match — UE FName comparison is case-insensitive; for our patch we only need
            // some matching index, the runtime treats them as equal.
            var nameIdx = new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);
            for (uint i = 0; i < rdr.NameMap.Length; i++)
            {
                var n = rdr.NameMap[i].Name;
                if (n != null && !nameIdx.ContainsKey(n)) nameIdx[n] = i;
            }
            if (!nameIdx.TryGetValue(toPkg, out uint toPkgIdx))
            {
                Console.WriteLine($"ERROR: --to package '{toPkg}' not in NameMap (no FName to write).");
                return;
            }
            if (!nameIdx.TryGetValue(toAsset, out uint toAssetIdx))
            {
                Console.WriteLine($"ERROR: --to asset '{toAsset}' not in NameMap (no FName to write).");
                return;
            }
            Console.WriteLine($"--to AssetClass FName cells: pkg='{toPkg}'(idx {toPkgIdx})  asset='{toAsset}'(idx {toAssetIdx})");

            // Read numAssetData (sanity check vs. state-parsed length).
            var count = Ar3.Read<int>();
            if (count != entries.Length)
            {
                Console.WriteLine($"ERROR: walker found numAssetData={count} but state has {entries.Length} — abort.");
                return;
            }

            // Walk every entry, recording its AssetClass offset. Cross-check the PackageName
            // first FName index against the state-parsed entries[i] to catch any walker
            // drift early — drift would silently mis-target later entries.
            var hits = new List<(long offset, int idx, string pkgName, string assetName,
                                 uint origPkgIdx, uint origAssetIdx)>();
            int verifiedAlignment = 0;
            for (int idx = 0; idx < count; idx++)
            {
                SkipFName(Ar3); // PackagePath
                long acOffset = Ar3.Position;
                // Inline AssetClass FTopLevelAssetPath read so we can record both indices.
                uint acPkgRaw = Ar3.Read<uint>();
                bool acPkgNumbered = (acPkgRaw & 0x80000000u) != 0;
                uint acPkgIdx = acPkgNumbered ? (acPkgRaw & 0x7FFFFFFFu) : acPkgRaw;
                if (acPkgNumbered) Ar3.Read<uint>();
                uint acAssetRaw = Ar3.Read<uint>();
                bool acAssetNumbered = (acAssetRaw & 0x80000000u) != 0;
                uint acAssetIdx = acAssetNumbered ? (acAssetRaw & 0x7FFFFFFFu) : acAssetRaw;
                if (acAssetNumbered) Ar3.Read<uint>();
                // PackageName (first 4-8 bytes is its FName index — read raw so we can
                // cross-check it against entries[idx].PackageName via NameMap).
                uint pkgNameRaw = Ar3.Read<uint>();
                bool pkgNameNumbered = (pkgNameRaw & 0x80000000u) != 0;
                uint pkgNameIdx = pkgNameNumbered ? (pkgNameRaw & 0x7FFFFFFFu) : pkgNameRaw;
                if (pkgNameNumbered) Ar3.Read<uint>();
                SkipFName(Ar3); // AssetName
                if (!hdr.bFilterEditorOnlyData) SkipFName(Ar3); // OptionalOuterPath
                Ar3.Read<ulong>(); // packed Tags+Bundles header (Num + PairBegin + bHasNumberlessKeys)
                int nBundles = Ar3.Read<int>();
                for (int b = 0; b < nBundles; b++)
                {
                    SkipFName(Ar3); // BundleName
                    int nAssets = Ar3.Read<int>();
                    for (int a = 0; a < nAssets; a++)
                    {
                        SkipFName(Ar3); // FTopLevelAssetPath.PackageName
                        SkipFName(Ar3); // FTopLevelAssetPath.AssetName
                        int slen = Ar3.Read<int>();
                        Ar3.Position += slen >= 0 ? slen : (-slen) * 2;
                    }
                }
                int nChunks = Ar3.Read<int>();
                Ar3.Position += (long) nChunks * 4;
                Ar3.Read<uint>(); // PackageFlags

                // Cross-check: the PackageName FName text via NameMap should match the
                // state-parsed entries[idx].PackageName text. Any mismatch means walker
                // drift — abort with a useful message.
                if (pkgNameIdx < rdr.NameMap.Length)
                {
                    var walkedName = rdr.NameMap[pkgNameIdx].Name;
                    // PackageName is stored as a single FName carrying the full path text
                    // (e.g. "/Game/Loki/Core/Missions/Pools/DA_MissionPoolDailyChallenge").
                    if (walkedName != null && walkedName.Equals(entries[idx].PackageName.Text, StringComparison.OrdinalIgnoreCase))
                        verifiedAlignment++;
                }

                var e = entries[idx];
                var pkgName = e.PackageName.Text;
                var assetName = e.AssetName.Text;
                bool pkgMatch = pkgName.Contains(targetPkg, StringComparison.OrdinalIgnoreCase);
                bool assetMatch = targetAssetExact.Length == 0
                    || assetName.Equals(targetAssetExact, StringComparison.OrdinalIgnoreCase);
                if (pkgMatch && assetMatch)
                {
                    if (acPkgNumbered || acAssetNumbered)
                    {
                        Console.WriteLine($"  SKIP idx={idx} {pkgName}:{assetName} (AssetClass FName is numbered — can't fit 8-byte overwrite)");
                        continue;
                    }
                    hits.Add((acOffset, idx, pkgName, assetName, acPkgIdx, acAssetIdx));
                }
            }
            Console.WriteLine($"  walker alignment verified on {verifiedAlignment:N0} / {count:N0} entries (PackageName FName text matched)");
            Console.WriteLine($"  matched {hits.Count} target entries:");
            foreach (var h in hits)
            {
                var origPkgName = h.origPkgIdx < rdr.NameMap.Length ? rdr.NameMap[h.origPkgIdx].Name : "?";
                var origAssetName = h.origAssetIdx < rdr.NameMap.Length ? rdr.NameMap[h.origAssetIdx].Name : "?";
                Console.WriteLine($"    idx={h.idx,7}  offset=0x{h.offset:X10}  {h.pkgName} : {h.assetName}");
                Console.WriteLine($"      origAssetClass: {origPkgName}.{origAssetName}");
            }
            if (hits.Count == 0) { Console.WriteLine("  no hits — nothing to patch."); return; }

            outPath ??= Path.Combine(Path.GetDirectoryName(arPath)!,
                                     Path.GetFileNameWithoutExtension(arPath) + ".patched.bin");
            File.Copy(arPath, outPath, overwrite: true);
            using (var rwfs = File.Open(outPath, FileMode.Open, FileAccess.ReadWrite))
            {
                var buf = new byte[8];
                BitConverter.GetBytes(toPkgIdx).CopyTo(buf, 0);
                BitConverter.GetBytes(toAssetIdx).CopyTo(buf, 4);
                foreach (var h in hits)
                {
                    rwfs.Position = h.offset;
                    rwfs.Write(buf, 0, 8);
                }
                rwfs.Flush();
            }
            Console.WriteLine($"  wrote patched bin -> {outPath} ({new FileInfo(outPath).Length:N0} bytes)");
            return;
        }

        default:
            Console.WriteLine($"unknown assetregistry subcommand: {sub}");
            Console.WriteLine("known: inspect, stats, namemap, classes, candidates, apply-patch");
            return;
    }
}


// Oodle: the .ucas blocks are Oodle-compressed; CUE4Parse needs oo2core_9_win64.dll.
// The game ships it statically linked, so fetch the redistributable once and init.
var oodlePath = Path.Combine(AppContext.BaseDirectory, OodleHelper.OODLE_DLL_NAME);
if (!File.Exists(oodlePath))
{
    Console.WriteLine("Downloading Oodle dll...");
    // The plain DownloadOodleDll URL is dead; the OodleUE mirror works.
    using var http = new HttpClient();
    OodleHelper.DownloadOodleDllFromOodleUEAsync(http, oodlePath).GetAwaiter().GetResult();
}
OodleHelper.Initialize(oodlePath);

var provider = new DefaultFileProvider(
    pakDir,
    SearchOption.TopDirectoryOnly,
    isCaseInsensitive: true,
    new VersionContainer(EGame.GAME_UE5_4));

provider.Initialize();
// Unencrypted containers mount under the zero GUID.
provider.SubmitKey(new FGuid(), new FAesKey(new byte[32]));
// Lazy serialization: LoadPackage reads the summary + name map + import/export
// maps but does NOT serialize export property bodies. That lets `names` mode read
// the FName vocabulary without a usmap (export bodies would need one).
provider.UseLazyPackageSerialization = true;

// .usmap mappings — REQUIRED to read any property value in this unversioned shipping
// build. Search a few sensible spots, any filename ending in .usmap (UE4SS emits
// "Mappings.usmap"). Drop the file in any of these and it's picked up automatically.
var usmapDirs = new[]
{
    AppContext.BaseDirectory,                                   // beside the built exe
    @"G:\git\Supervive Revival Project\tools\extractor",        // tool root
    @"G:\git\Supervive Revival Project\tools\extractor\extractor",
};
var usmap = usmapDirs
    .Where(Directory.Exists)
    .SelectMany(d => Directory.GetFiles(d, "*.usmap"))
    .FirstOrDefault();
if (usmap != null)
{
    provider.MappingsContainer = new CUE4Parse.MappingsProvider.FileUsmapTypeMappingsProvider(usmap);
    Console.WriteLine($"Loaded mappings: {usmap}");
}
else
{
    Console.WriteLine("No .usmap found — enumeration works; `dump`/`names` need one.");
}

// dump mode: load each given package path and write its exports as JSON (needs usmap).
if (dumpMode)
{
    Directory.CreateDirectory(outDir);
    foreach (var path in args.Skip(1))
    {
        try
        {
            var pkg = provider.LoadPackage(path);
            var exports = pkg.GetExports();
            var json = JsonConvert.SerializeObject(exports, Formatting.Indented);
            var name = path.Split('/').Last().Replace('.', '_') + ".json";
            File.WriteAllText(Path.Combine(outDir, name), json);
            Console.WriteLine($"OK   {path}  ({json.Length} bytes) -> {name}");
        }
        catch (Exception e)
        {
            Console.WriteLine($"FAIL {path}\n     {e.GetType().Name}: {e.Message}");
        }
    }
    return;
}

// schema mode: print the EXACT reflected layout of one or more C++ USTRUCT/UCLASS
// types straight from the loaded .usmap — field names + property types, recursively
// expanding any referenced struct types. This is how we recover the ContentManifest /
// ContentServicePrimaryAsset shape WITHOUT a serialized instance to guess from.
//   run -- schema ContentManifest ContentServicePrimaryAsset
// The usmap type table lives behind MappingsContainer.MappingsForGame.Types; member
// naming in CUE4Parse mixes public fields and properties across versions, so we walk
// it with reflection to stay robust.
if (args.Length >= 2 && args[0] == "schema")
{
    if (provider.MappingsContainer == null)
    {
        Console.WriteLine("No .usmap loaded — drop Mappings.usmap in tools\\extractor\\ first.");
        return;
    }

    // Reflection helper: read a member (field OR property), case-insensitive, by any
    // of the candidate names. Returns null if none match.
    static object? Member(object? obj, params string[] names)
    {
        if (obj == null) return null;
        var t = obj.GetType();
        foreach (var n in names)
        {
            var p = t.GetProperty(n, System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.IgnoreCase);
            if (p != null) return p.GetValue(obj);
            var f = t.GetField(n, System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.IgnoreCase);
            if (f != null) return f.GetValue(obj);
        }
        return null;
    }

    // Format a PropertyType node into a readable type string, e.g.
    //   Map<Str, Struct ContentServicePrimaryAsset>  /  Array<Struct Foo>  /  Str
    string FormatType(object? pt, ISet<string> discovered)
    {
        if (pt == null) return "?";
        var type = Member(pt, "Type", "MappingType")?.ToString() ?? "?";
        var structType = Member(pt, "StructType", "structType")?.ToString();
        var enumName = Member(pt, "EnumName", "enumName")?.ToString();
        var inner = Member(pt, "InnerType", "innerType");
        var value = Member(pt, "ValueType", "valueType");

        if (!string.IsNullOrEmpty(structType)) { discovered.Add(structType); }

        // Strip the trailing "Property" UE convention for readability.
        string Short(string s) => s.EndsWith("Property") ? s[..^"Property".Length] : s;
        var baseName = Short(type);

        switch (baseName)
        {
            case "Struct":
                return $"Struct {structType}";
            case "Array":
            case "Set":
                return $"{baseName}<{FormatType(inner, discovered)}>";
            case "Map":
                return $"Map<{FormatType(inner, discovered)}, {FormatType(value, discovered)}>";
            case "Enum":
            case "Byte" when !string.IsNullOrEmpty(enumName):
                return $"Enum {enumName}";
            default:
                return baseName + (string.IsNullOrEmpty(structType) ? "" : $" {structType}");
        }
    }

    var mappings = Member(provider.MappingsContainer, "MappingsForGame", "MappingsForThisGame");
    var typesObj = Member(mappings, "Types", "types");
    if (typesObj is not System.Collections.IDictionary typeDict)
    {
        Console.WriteLine($"Could not read the usmap type table (got {typesObj?.GetType().FullName ?? "null"}).");
        return;
    }

    // Build a case-insensitive lookup of the type table keys once.
    var keyIndex = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
    foreach (System.Collections.DictionaryEntry e in typeDict)
        keyIndex[e.Key.ToString()!] = e.Key;
    Console.WriteLine($"usmap type table: {typeDict.Count} structs/classes.\n");

    var queue = new Queue<string>(args.Skip(1));
    var printed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var sb = new System.Text.StringBuilder();

    while (queue.Count > 0)
    {
        var want = queue.Dequeue();
        if (!printed.Add(want)) continue;
        if (!keyIndex.TryGetValue(want, out var realKey) || typeDict[realKey] is not object structObj)
        {
            sb.AppendLine($"// NOT FOUND in usmap: {want}");
            // Suggest near-matches to catch naming drift (e.g. F-prefix, plural).
            var near = keyIndex.Keys.Where(k => k.Contains(want, StringComparison.OrdinalIgnoreCase)
                                              || want.Contains(k, StringComparison.OrdinalIgnoreCase))
                                    .Take(8).ToList();
            if (near.Count > 0) sb.AppendLine($"//   near: {string.Join(", ", near)}");
            sb.AppendLine();
            continue;
        }

        var superType = Member(structObj, "SuperType", "superType")?.ToString();
        sb.AppendLine($"struct {want}{(string.IsNullOrEmpty(superType) ? "" : $" : {superType}")}");
        sb.AppendLine("{");

        var discovered = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var props = Member(structObj, "Properties", "properties");
        if (props is System.Collections.IEnumerable propEnum)
        {
            foreach (var prop in propEnum)
            {
                // Properties may be stored as a dict (int->PropertyInfo); unwrap values.
                var pi = prop;
                if (prop is System.Collections.DictionaryEntry de) pi = de.Value;
                var pname = Member(pi, "Name", "name")?.ToString() ?? "?";
                var mtype = Member(pi, "MappingType", "mappingType");
                var arrayDim = Member(pi, "ArrayDim", "arrayDim");
                var dimSuffix = (arrayDim is int ad && ad > 1) ? $"[{ad}]" : "";
                sb.AppendLine($"    {FormatType(mtype, discovered),-48} {pname}{dimSuffix};");
            }
        }
        sb.AppendLine("}");
        sb.AppendLine();

        // Recurse into referenced struct types we haven't printed yet.
        foreach (var d in discovered) if (!printed.Contains(d)) queue.Enqueue(d);
    }

    Directory.CreateDirectory(outDir);
    var schemaOut = Path.Combine(outDir, $"schema_{args[1]}.txt");
    File.WriteAllText(schemaOut, sb.ToString());
    Console.Write(sb.ToString());
    Console.WriteLine($"-> {schemaOut}");
    return;
}

// names mode: dump each package's NameMap — the FName vocabulary (SKUs, IDs,
// string-table keys). Works WITHOUT a usmap, since the name map is part of the
// package summary, not unversioned property data.
if (args.Length > 0 && args[0] == "names")
{
    Directory.CreateDirectory(outDir);
    foreach (var path in args.Skip(1))
    {
        try
        {
            var pkg = provider.LoadPackage(path);
            string[] names = pkg is IoPackage io
                ? io.NameMap.Select(n => n.Name).ToArray()
                : pkg.NameMap.Select(n => n.Name).ToArray();
            var outName = path.Split('/').Last() + ".names.txt";
            File.WriteAllLines(Path.Combine(outDir, outName),
                names.Distinct().OrderBy(x => x, StringComparer.OrdinalIgnoreCase));
            Console.WriteLine($"OK   {path}  ({names.Length} names) -> {outName}");
        }
        catch (Exception e)
        {
            Console.WriteLine($"FAIL {path}\n     {e.GetType().Name}: {e.Message}");
        }
    }
    return;
}

// namesall mode: harvest the combined unique NameMap vocabulary across every
// .uasset whose path contains <substr>, writing per-asset blocks to <outfile>.
// This is how we pull a whole catalog's SKU vocabulary (e.g. all BP_StoreOffer_*)
// in one pass, no usmap-of-values needed.
if (args.Length >= 3 && args[0] == "namesall")
{
    var substr = args[1];
    var outFile = Path.IsPathRooted(args[2]) ? args[2] : Path.Combine(outDir, args[2]);
    var targets = provider.Files.Keys
        .Where(f => f.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)
                    && f.Contains(substr, StringComparison.OrdinalIgnoreCase))
        .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
        .ToList();
    Console.WriteLine($"namesall '{substr}': {targets.Count} assets");
    using var sw = new StreamWriter(outFile);
    var union = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
    int ok = 0;
    foreach (var path in targets)
    {
        try
        {
            var pkg = provider.LoadPackage(path);
            var names = (pkg is IoPackage io ? io.NameMap : pkg.NameMap)
                .Select(n => n.Name).Distinct()
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
            sw.WriteLine($"# {path}");
            foreach (var n in names) { sw.WriteLine("  " + n); union.Add(n); }
            sw.WriteLine();
            ok++;
        }
        catch (Exception e) { sw.WriteLine($"# FAIL {path}: {e.Message}\n"); }
    }
    sw.WriteLine("# ===== UNION (all unique names) =====");
    foreach (var n in union) sw.WriteLine(n);
    Console.WriteLine($"  parsed {ok}/{targets.Count}; {union.Count} unique names -> {outFile}");
    return;
}

var files = provider.Files.Keys.OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
Console.WriteLine($"Mounted. Total files: {files.Count}");

File.WriteAllLines(Path.Combine(outDir, "allfiles.txt"), files);

// Quick-and-dirty buckets for the things this milestone needs. Substring matches
// over the full virtual path, case-insensitive.
void Bucket(string name, params string[] needles)
{
    var hits = files
        .Where(f => needles.Any(n => f.Contains(n, StringComparison.OrdinalIgnoreCase)))
        .ToList();
    File.WriteAllLines(Path.Combine(outDir, name), hits);
    Console.WriteLine($"  {name,-28} {hits.Count}");
}

Console.WriteLine("Buckets:");
Bucket("heroes.txt", "/Characters/Heroes", "/Heroes/");
Bucket("stringtables.txt", "ST_", "StringTable", "/Localization/", ".locres");
Bucket("storefront.txt", "Storefront", "/Store/", "Offer", "Bundle", "Catalog");
Bucket("cosmetics.txt", "Cosmetic", "/Skins/", "Emote", "/Customization/");
Bucket("battlepass.txt", "Battlepass", "BattlePass", "Progression", "RewardTrack");
Bucket("datatables.txt", "/DataTables/", "DT_", "DataTable");

// Top-level directory histogram, so we can see the content layout at a glance.
var topDirs = files
    .Select(f =>
    {
        var idx = f.IndexOf('/', f.StartsWith('/') ? 1 : 0);
        return idx > 0 ? f[..idx] : f;
    })
    .GroupBy(d => d)
    .OrderByDescending(g => g.Count())
    .Select(g => $"{g.Count(),8}  {g.Key}");
File.WriteAllLines(Path.Combine(outDir, "topdirs.txt"), topDirs);

Console.WriteLine("Done.");
