// registration_shim — direct LokiAssetManager::AddDynamicAsset invocation.
//
// Goal: register primary assets that the manifest can't carry (Mission /
// MissionPool — no map in the ContentServiceContentManifest struct) by calling
// LokiAssetManager::AddDynamicAsset directly on the game thread, bypassing the
// manifest-only registration limit that empties the Missions modal / ALL HUNTERS
// grid / STORE carousel / COSMETICS browser.
//
// SMOKE TEST scope (this build): register all 16 MissionPool primary assets.
// The 16 paths + per-asset _C class names are pre-resolved to FName indices
// in the table below (see docs/lokiassetmanager-vtable-dump.md for the
// extraction methodology and the full validated dataset).
//
// If smoke test produces ChangeBundleStateForPrimaryAssets activity for our
// MissionPool:* IDs AND the Missions modal populates → scale the same pattern
// to the 105 missions + 25 heroes + 25 cosmetics bundles + store offers.
// If activity appears but UI stays empty → downstream UI kill criterion
// (per MISSION PROBE #2): modal widget enumerates AR directly, ignoring
// RegisteredPrimaryAssets. Route closes at UI layer; pivot to WBP_UI_*_C
// blueprint RE.
//
// Sequence:
//   1. DllMain spawns a worker thread (CREATE_SUSPENDED-compatible).
//   2. Worker waits for GGameThreadId to be non-zero (engine init started),
//      then sleeps a grace period so LokiAssetManager finishes init.
//   3. Worker scans MEM_PRIVATE for qword == module_base + 0x888CB78
//      (LokiAssetManager UClass vtable) and filters out the CDO by checking
//      [+0x0C] & 0x10 == 0. Picks the first remaining match = real singleton.
//   4. Worker reads GGameThreadId and queues an APC on that thread.
//   5. The APC body iterates the kRegistrations table and for each entry
//      constructs FPrimaryAssetId + FSoftObjectPath + empty TArray<FName>
//      on its own stack, then calls vtable[94] with (singleton, &id, &path,
//      &bundles). Per-call result logged to the marker file.
//
// All FName indices come from `usmapdump nameid` lookups against the live pool
// — see docs/lokiassetmanager-vtable-dump.md for the encoding
// (id = (block << 16) | (offset_in_block / 2)). FName.Number is always 0 for
// these cooked asset names.
//
// Build:
//   clang++ -shared -O2 registration_shim.cpp -o registration_shim.dll -lkernel32
//
// Deploy (suspended-launch flow same as sigbypass-mod):
//   tools/sigbypass-mod/race-register-suspended.ps1   (TODO: orchestrator)

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

// ─── constants ────────────────────────────────────────────────────────────────

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\registration-shim-marker.txt";

// Module-relative offsets (stable per build).
constexpr uintptr_t kLokiAssetMgrVTableRva = 0x888CB78;  // LokiAssetManager UClass vtable
constexpr uintptr_t kAddDynamicAssetVtSlot = 94;         // vtable slot for AddDynamicAsset
constexpr uintptr_t kGGameTidRva           = 0x9D49158;  // GGameThreadId (uint32 slot)

// Object-flag bits we care about (this build: ObjectFlags @ +0x0C of UObject).
constexpr uintptr_t kObjFlagsOffset        = 0x0C;
constexpr uint32_t  kRfClassDefaultObject  = 0x10;

// PrimaryAssetType FName ComparisonIndex (kType_MissionPool only used by smoke test).
// Full set in docs/lokiassetmanager-vtable-dump.md.
constexpr uint32_t kType_MissionPool       = 0x00016F06;

// ─── UE struct layouts (this build) ─────────────────────────────────────────
// FName: 8 bytes. Verified by AddDynamicAsset disasm reading 16 bytes for
// FPrimaryAssetId (mov rbx,[rdx]; mov rax,[rdx+8]) — 2 FNames × 8.

struct FName {
    uint32_t ComparisonIndex;
    uint32_t Number;  // ~always 0 for pooled cooked asset names
};
static_assert(sizeof(FName) == 8, "FName must be 8 bytes in this build");

struct FPrimaryAssetId {
    FName PrimaryAssetType;
    FName PrimaryAssetName;
};
static_assert(sizeof(FPrimaryAssetId) == 16, "FPrimaryAssetId must be 16 bytes");

struct FTopLevelAssetPath {
    FName PackageName;
    FName AssetName;
};
static_assert(sizeof(FTopLevelAssetPath) == 16, "FTopLevelAssetPath must be 16 bytes");

// FString { TCHAR* Data; int32 Num; int32 Max; } — 16 bytes (16-byte aligned).
struct FString {
    wchar_t* Data;
    int32_t  Num;
    int32_t  Max;
};
static_assert(sizeof(FString) == 16, "FString must be 16 bytes");

struct FSoftObjectPath {
    FTopLevelAssetPath AssetPath;
    FString            SubPath;  // empty for top-level asset references
};
static_assert(sizeof(FSoftObjectPath) == 32, "FSoftObjectPath must be 32 bytes");

// TArray<T> header { T* Data; int32 Num; int32 Max; } — 16 bytes.
template <typename T>
struct TArray {
    T*      Data;
    int32_t Num;
    int32_t Max;
};
static_assert(sizeof(TArray<FName>) == 16, "TArray header must be 16 bytes");

// ─── registration table ───────────────────────────────────────────────────────
// All 16 LokiDataAsset_MissionPool primary assets. FName indices baked from
// `usmapdump nameid` against the live pool. See
// docs/lokiassetmanager-vtable-dump.md for the extraction batch.

struct RegEntry {
    const char* debugName;       // for marker log only
    uint32_t    primaryAssetName;
    uint32_t    packageName;
    uint32_t    assetName;       // _C class name within package
};

static const RegEntry kRegistrations[] = {
    {"DA_MissionPoolArmoryOnboarding",         0x004A410E, 0x00406765, 0x003E2594},
    {"DA_MissionPoolDailyChallenge",           0x0013D7DA, 0x0027D732, 0x003B33DC},
    {"DA_MissionPoolDailyChallenge_Planbee",   0x0034A90E, 0x00426CF9, 0x004DD67F},
    {"DA_MissionPoolDailyEasy",                0x0029D2DA, 0x00355360, 0x0050BDB8},
    {"DA_MissionPoolDailyEasy_Planbee",        0x000646D1, 0x00127AF4, 0x004944F2},
    {"DA_MissionPoolDailyPCB",                 0x0056032C, 0x00436F2C, 0x002C083F},
    {"DA_MissionPoolDailyPCB_Armory",          0x00148041, 0x00421565, 0x003B33EC},
    {"DA_MissionPoolHunterMissions",           0x0047A890, 0x00277C5B, 0x0025291C},
    {"DA_MissionPoolOnboarding",               0x0025292C, 0x002FFEC2, 0x00243D2E},
    {"DA_MissionPoolOnboardingPlanbee",        0x001F4BD2, 0x0025D9AE, 0x00475708},
    {"DA_MissionPoolTutorialMaps",             0x00117A37, 0x001C6167, 0x003E7C8E},
    {"DA_MissionPoolWeekly",                   0x0025D9CE, 0x003250D0, 0x00191515},
    {"DA_MissionPoolWeeklyChallenge",          0x002EFC99, 0x002880BE, 0x00112689},
    {"DA_MissionPoolWeeklyChallenge_Planbee",  0x002F52FC, 0x0053106F, 0x003051C1},
    {"DA_MissionPoolWeekly_Planbee",           0x00137B5D, 0x00252939, 0x000FD34A},
    {"DA_MissionPool_Tournament",              0x00148033, 0x00243D04, 0x00074446},
};
constexpr size_t kRegCount = sizeof(kRegistrations) / sizeof(kRegistrations[0]);

// ─── marker logging ──────────────────────────────────────────────────────────

static void WriteMarker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &written, nullptr);
    CloseHandle(h);
}

// ─── SEH-free page-readability check ─────────────────────────────────────────
// Clang's __try/__except in our manual-mapped DLL doesn't dispatch reliably
// (the SEH chain isn't set up the way Windows expects despite registered
// .pdata). Gate every speculative read on VirtualQuery instead.

static bool PageReadable(const void* target) {
    MEMORY_BASIC_INFORMATION mbi = {0};
    if (VirtualQuery(target, &mbi, sizeof(mbi)) != sizeof(mbi)) return false;
    if (mbi.State != MEM_COMMIT) return false;
    if (mbi.Protect & PAGE_GUARD) return false;
    const DWORD readMask =
        PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    return (mbi.Protect & readMask) != 0;
}

// ─── globals shared with APC ─────────────────────────────────────────────────

static void*     g_singleton  = nullptr;
static uintptr_t g_modBase    = 0;
static uintptr_t g_vtableAddr = 0;

// ─── singleton scanner ───────────────────────────────────────────────────────

// Heuristic: does `v` look like a real user-mode heap pointer (8-byte aligned,
// non-trivial, below the userland cap)? Used to filter spurious qword matches
// where ClassPrivate@+0x18 is random bytes rather than a real UClass*.
static bool LooksLikePtr(uintptr_t v) {
    return v >= 0x10000 && v < 0x0001000000000000ULL && (v & 0x7) == 0;
}

// Scan committed MEM_PRIVATE for any qword equal to vtableA. **Self-match
// problem:** our own injected DLL has the kLokiAssetMgrVTableRva-derived
// constant baked in (so its memory matches the search), and stack/heap regions
// can have coincidental qword sequences. Filter aggressively:
//   1. Skip qwords inside our own DLL's region (range: [g_selfBase, g_selfBase + g_selfSize)).
//   2. ClassPrivate@+0x18 must look like a real heap pointer.
//   3. Reading [+0x18] as a pointer + dereferencing its first qword must succeed
//      (real UClass instances have their own vtable; spurious "ClassPrivate" values
//      that are random bytes will fault → PageReadable returns false).
//   4. Then split by ObjectFlags@+0x0C: bit 0x10 set = CDO; clear = real singleton.
//   5. Pick the first remaining non-CDO hit. (Matches the `findptr` + filter
//      result from recon: 2 total hits, 1 CDO + 1 real singleton.)
static uintptr_t g_selfBase = 0;
static uintptr_t g_selfSize = 0;

static void* ScanForSingleton(uintptr_t vtableAddr) {
    char m[160];
    snprintf(m, sizeof(m),
             "[scan] looking for LokiAssetManager singleton with vtable=0x%llX "
             "(skip self range 0x%llX..0x%llX)\r\n",
             (unsigned long long)vtableAddr,
             (unsigned long long)g_selfBase,
             (unsigned long long)(g_selfBase + g_selfSize));
    WriteMarker(m);

    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
    const uintptr_t maxAddr = (uintptr_t)si.lpMaximumApplicationAddress;

    int regions = 0, vtHits = 0, selfSkips = 0, badClassSkips = 0,
        cdoHits = 0, validatedSingletons = 0;
    void* pickedSingleton = nullptr;
    void* pickedCdo = nullptr;

    while (addr < maxAddr) {
        MEMORY_BASIC_INFORMATION mbi = {0};
        if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) != sizeof(mbi)) break;
        const uintptr_t regionEnd = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;

        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
            (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) != 0 &&
            (mbi.Protect & PAGE_GUARD) == 0) {
            regions++;
            const uintptr_t* p = (const uintptr_t*)mbi.BaseAddress;
            const uintptr_t* end = (const uintptr_t*)regionEnd - 4;
            for (; p < end; p++) {
                if (*p != vtableAddr) continue;
                vtHits++;
                uintptr_t pAddr = (uintptr_t)p;

                // Filter 1: skip qwords inside our own DLL.
                if (g_selfSize > 0 && pAddr >= g_selfBase && pAddr < g_selfBase + g_selfSize) {
                    selfSkips++;
                    continue;
                }

                // Filter 2: ClassPrivate@+0x18 must look like a real heap ptr.
                uintptr_t classPtr = p[3]; // [obj + 0x18]
                if (!LooksLikePtr(classPtr)) {
                    badClassSkips++;
                    continue;
                }

                // Filter 3: ClassPrivate must point to a readable region (its
                // own vtable lives there).
                if (!PageReadable((const void*)classPtr)) {
                    badClassSkips++;
                    continue;
                }

                // Read ObjectFlags at [obj + 0x0C].
                const uint8_t* objBytes = (const uint8_t*)p;
                uint32_t objFlags = 0;
                memcpy(&objFlags, objBytes + kObjFlagsOffset, sizeof(objFlags));
                bool isCdo = (objFlags & kRfClassDefaultObject) != 0;

                // NamePrivate@+0x20 — log for diagnostics (validates real UObject
                // identity without strict gating).
                uintptr_t nameQw = p[4]; // [obj + 0x20]
                uint32_t  nameCmpIdx = (uint32_t)(nameQw & 0xFFFFFFFFu);

                if (isCdo) {
                    cdoHits++;
                    if (!pickedCdo) pickedCdo = (void*)p;
                } else {
                    validatedSingletons++;
                    if (!pickedSingleton) pickedSingleton = (void*)p;
                }
                {
                    char d[256];
                    snprintf(d, sizeof(d),
                        "[scan]   validated hit @%p flags=0x%08X cdo=%d "
                        "class=0x%llX name.idx=0x%08X\r\n",
                        (void*)p, objFlags, isCdo ? 1 : 0,
                        (unsigned long long)classPtr, nameCmpIdx);
                    WriteMarker(d);
                }
            }
        }
        addr = regionEnd;
    }

    snprintf(m, sizeof(m),
             "[scan] done: regions=%d vtHits=%d selfSkips=%d badClassSkips=%d "
             "cdo=%d singletons=%d picked=%p (cdo=%p)\r\n",
             regions, vtHits, selfSkips, badClassSkips,
             cdoHits, validatedSingletons, pickedSingleton, pickedCdo);
    WriteMarker(m);
    return pickedSingleton;
}

// ─── APC body: register every entry ──────────────────────────────────────────

typedef void (*PFN_AddDynamicAsset)(
    void* self,
    const FPrimaryAssetId* assetId,
    const FSoftObjectPath* assetPath,
    const TArray<FName>* bundles);

static void NTAPI RegisterApcCallback(ULONG_PTR /*param*/) {
    if (!g_singleton || !g_modBase || !g_vtableAddr) {
        WriteMarker("[apc] FIRE FAIL: globals not set\r\n");
        return;
    }
    char m[256];
    snprintf(m, sizeof(m), "[apc] FIRING on game thread tid=%lu, singleton=%p\r\n",
             GetCurrentThreadId(), g_singleton);
    WriteMarker(m);

    // Re-validate the singleton's first qword — if the engine destructed it
    // between scan and APC, calling vtable[N] would AV.
    if (!PageReadable(g_singleton)) {
        WriteMarker("[apc] FAIL: singleton ptr no longer readable\r\n");
        return;
    }
    uintptr_t curVtable = *(const uintptr_t*)g_singleton;
    if (curVtable != g_vtableAddr) {
        snprintf(m, sizeof(m),
                 "[apc] FAIL: singleton vtable changed (got 0x%llX want 0x%llX)\r\n",
                 (unsigned long long)curVtable, (unsigned long long)g_vtableAddr);
        WriteMarker(m);
        return;
    }

    // Resolve AddDynamicAsset via vtable[94]. Vtable layout: 8-byte fn pointers.
    if (!PageReadable((const void*)curVtable)) {
        WriteMarker("[apc] FAIL: vtable page not readable\r\n");
        return;
    }
    const uintptr_t* vt = (const uintptr_t*)curVtable;
    PFN_AddDynamicAsset addDynamicAsset = (PFN_AddDynamicAsset)vt[kAddDynamicAssetVtSlot];
    snprintf(m, sizeof(m), "[apc] vtable[%llu] = AddDynamicAsset @ %p\r\n",
             (unsigned long long)kAddDynamicAssetVtSlot, (void*)addDynamicAsset);
    WriteMarker(m);

    // Empty TArray<FName> Bundles — shared across all registrations (read-only).
    TArray<FName> bundles{};
    bundles.Data = nullptr;
    bundles.Num  = 0;
    bundles.Max  = 0;

    int ok = 0;
    for (size_t i = 0; i < kRegCount; i++) {
        const RegEntry& e = kRegistrations[i];

        // Construct FPrimaryAssetId on the stack.
        FPrimaryAssetId id{};
        id.PrimaryAssetType.ComparisonIndex = kType_MissionPool;
        id.PrimaryAssetType.Number          = 0;
        id.PrimaryAssetName.ComparisonIndex = e.primaryAssetName;
        id.PrimaryAssetName.Number          = 0;

        // Construct FSoftObjectPath on the stack.
        // PackageName = full /Game/... path FName
        // AssetName   = ClassName_C FName within the package
        // SubPath     = empty FString
        FSoftObjectPath path{};
        path.AssetPath.PackageName.ComparisonIndex = e.packageName;
        path.AssetPath.PackageName.Number          = 0;
        path.AssetPath.AssetName.ComparisonIndex   = e.assetName;
        path.AssetPath.AssetName.Number            = 0;
        path.SubPath.Data = nullptr;
        path.SubPath.Num  = 0;
        path.SubPath.Max  = 0;

        snprintf(m, sizeof(m),
                 "[apc] [%2zu/%zu] calling AddDynamicAsset for %s "
                 "(id-Name=0x%08X pkg=0x%08X cls=0x%08X)\r\n",
                 i + 1, kRegCount, e.debugName,
                 e.primaryAssetName, e.packageName, e.assetName);
        WriteMarker(m);

        // The call. No SEH wrap — if AddDynamicAsset AVs we'll see it in
        // Loki.log / crash dump rather than a graceful return.
        addDynamicAsset(g_singleton, &id, &path, &bundles);

        ok++;
        snprintf(m, sizeof(m), "[apc] [%2zu/%zu] returned cleanly\r\n",
                 i + 1, kRegCount);
        WriteMarker(m);
    }

    snprintf(m, sizeof(m), "[apc] DONE: %d / %zu registrations completed\r\n",
             ok, kRegCount);
    WriteMarker(m);
}

// ─── worker ───────────────────────────────────────────────────────────────────

static DWORD WaitForGameTid(uintptr_t modBase, DWORD timeoutMs) {
    uint32_t* gameTidSlot = (uint32_t*)(modBase + kGGameTidRva);
    char m[160];
    snprintf(m, sizeof(m), "[gametid] slot ptr = %p (mod-RVA 0x%llX)\r\n",
             (void*)gameTidSlot, (unsigned long long)kGGameTidRva);
    WriteMarker(m);

    const DWORD deadline = GetTickCount() + timeoutMs;
    int loop = 0;
    int lastReadable = -1;
    while (GetTickCount() < deadline) {
        loop++;
        bool readable = PageReadable(gameTidSlot);
        if ((int)readable != lastReadable) {
            snprintf(m, sizeof(m), "[gametid] loop=%d readable=%d\r\n",
                     loop, readable ? 1 : 0);
            WriteMarker(m);
            lastReadable = (int)readable;
        }
        if (readable) {
            uint32_t v = 0;
            memcpy(&v, gameTidSlot, sizeof(v));
            if (v != 0) {
                snprintf(m, sizeof(m), "[gametid] FOUND tid=%lu at loop=%d\r\n",
                         (unsigned long)v, loop);
                WriteMarker(m);
                return v;
            }
        }
        if (loop % 200 == 0) {
            snprintf(m, sizeof(m), "[gametid] loop=%d still waiting\r\n", loop);
            WriteMarker(m);
        }
        Sleep(10);
    }
    return 0;
}

static DWORD WINAPI Worker(LPVOID) {
    WriteMarker("[0] registration_shim worker started\r\n");

    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) {
        WriteMarker("[0] FAIL: GetModuleHandleA returned NULL\r\n");
        return 1;
    }
    const uintptr_t modBase = (uintptr_t)hExe;
    g_modBase = modBase;
    g_vtableAddr = modBase + kLokiAssetMgrVTableRva;
    {
        char m[160];
        snprintf(m, sizeof(m),
                 "[0] modBase=0x%llX  LokiAssetManager-vtable=0x%llX\r\n",
                 (unsigned long long)modBase, (unsigned long long)g_vtableAddr);
        WriteMarker(m);
    }

    // Step 1: wait for game thread to be running (GGameThreadId non-zero).
    WriteMarker("[1] waiting for GGameThreadId to be non-zero (60s)...\r\n");
    DWORD gameTid = WaitForGameTid(modBase, 60000);
    if (gameTid == 0) {
        WriteMarker("[1] FAIL: GGameThreadId stayed 0 for 60s — wrong RVA?\r\n");
        return 2;
    }

    // Step 2: extra grace period so LokiAssetManager finishes its own init
    // (it gets created during UE engine init, before main menu loads). 10s is
    // generous; if APC fires during init we'd crash on partially-built TMaps.
    WriteMarker("[2] sleeping 10s to let LokiAssetManager finish init...\r\n");
    Sleep(10000);

    // Step 3: scan for singleton.
    void* singleton = ScanForSingleton(g_vtableAddr);
    if (!singleton) {
        WriteMarker("[3] FAIL: no non-CDO LokiAssetManager instance found\r\n");
        return 3;
    }
    g_singleton = singleton;
    {
        char m[96];
        snprintf(m, sizeof(m), "[3] singleton picked: %p\r\n", singleton);
        WriteMarker(m);
    }

    // Step 4: queue APC on the game thread.
    HANDLE gameThread = OpenThread(THREAD_SET_CONTEXT, FALSE, gameTid);
    if (!gameThread) {
        char m[96];
        snprintf(m, sizeof(m), "[apc] OPEN FAIL: OpenThread(%lu) err=%lu\r\n",
                 gameTid, GetLastError());
        WriteMarker(m);
        return 4;
    }
    DWORD apcOk = QueueUserAPC(RegisterApcCallback, gameThread, 0);
    CloseHandle(gameThread);
    if (!apcOk) {
        char m[96];
        snprintf(m, sizeof(m), "[apc] QUEUE FAIL: QueueUserAPC err=%lu\r\n",
                 GetLastError());
        WriteMarker(m);
        return 5;
    }
    {
        char m[96];
        snprintf(m, sizeof(m),
                 "[apc] APC queued on tid=%lu; fires on next alertable wait\r\n",
                 gameTid);
        WriteMarker(m);
    }
    return 0;
}

// ─── DllMain ─────────────────────────────────────────────────────────────────

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID /*reserved*/) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);

        // Capture our own image base + size so the singleton scanner can skip
        // matches inside our own DLL (we have the LokiAssetManager vtable
        // address baked in as a constant — its byte representation in our code
        // would otherwise look like a vtable ptr match).
        g_selfBase = (uintptr_t)hModule;
        const uint8_t* hdrs = (const uint8_t*)hModule;
        // PE header: DOS at +0, e_lfanew@+0x3C → IMAGE_NT_HEADERS;
        // OptionalHeader.SizeOfImage at +0x50 from NT headers (for PE32+).
        uint32_t e_lfanew = *(const uint32_t*)(hdrs + 0x3C);
        const uint8_t* nt = hdrs + e_lfanew;
        uint32_t sizeOfImage = *(const uint32_t*)(nt + 0x50);
        g_selfSize = sizeOfImage;

        char m[160];
        snprintf(m, sizeof(m),
                 "[+] registration_shim attached at 0x%llX size=0x%llX, spawning worker\r\n",
                 (unsigned long long)g_selfBase, (unsigned long long)g_selfSize);
        WriteMarker(m);

        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    }
    return TRUE;
}

// UE4SS-compatible exports for parity with sigbypass-mod/main.cpp (UE4SS
// itself doesn't load in this shipping build — import dir stripped — but
// these allow the same DLL to be reused if a future loader changes that).
extern "C" __declspec(dllexport) void* start_mod() {
    return new int(0);
}

extern "C" __declspec(dllexport) void uninstall_mod(void* mod) {
    delete static_cast<int*>(mod);
}
