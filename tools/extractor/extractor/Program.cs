using CUE4Parse.Compression;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Objects.Core.Misc;
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

var cmd = args.Length > 0 && (args[0] == "dump" || args[0] == "names" || args[0] == "namesall" || args[0] == "schema") ? args[0] : null;
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
