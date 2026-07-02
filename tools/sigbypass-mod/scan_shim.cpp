// scan_shim — force LokiAssetManager to scan the (already-full) AssetRegistry into
// its per-type AssetMaps, so the ALL HUNTERS grid / store / cosmetics / missions
// populate.
//
// Root cause (session 42): the in-game FAssetRegistry is FULL (103,841 entries incl.
// all correctly-tagged heroes), but LokiAssetManager registers each primary-asset
// TYPE's Info from config yet never runs the directory-scan that fills the per-type
// AssetMap — so GetPrimaryAssetIdList(<type>) returns 0 and every grid is empty.
//
// Fix: on the game thread, for each type in the manager's AssetTypeMap, call the
// stock UAssetManager::ScanPathsForPrimaryAssets(type, &Info.ScanPaths, Info.BaseClass,
// bHasBP=1, bEditorOnly=0, bForceSync=1). The registry is full, so each call registers
// that type's assets. All args are read straight from each type's Info block — the
// payload constructs nothing.
//
// Offsets (this build, session-42 RE; stable across launches, ASLR moves base only):
//   ScanPathsForPrimaryAssets  = RVA +0x34CF9F0   (verified via vtable diff + disasm)
//   LokiAssetManager vtable     = RVA +0x88CB78
//   GGameThreadId slot          = RVA +0x9D49158
//   manager+0x478 = AssetTypeMap {Data ptr, Num, Max}, element stride 0x20:
//                   key FName @+0x00, value FPrimaryAssetTypeData* @+0x08
//   FPrimaryAssetTypeData: Info.PrimaryAssetType FName @+0x00, BaseClass UClass* @+0x30,
//                          scan-paths TArray<FString> @+0x70
//
// Build:  clang++ -shared -O2 scan_shim.cpp -o scan_shim.dll -lkernel32
// Inject: tools/inject watch-now / mmap (browse_hook-style). Runs on the game thread
//         via QueueUserAPC. Outcome in the marker file below.

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\scan-shim-marker.txt";

constexpr uintptr_t kScanPathsRva  = 0x34CF9F0; // UAssetManager::ScanPathsForPrimaryAssets
constexpr uintptr_t kLokiMgrVtRva  = 0x888CB78; // LokiAssetManager vtable (0x7FF68B30CB78-base)
constexpr uintptr_t kGGameTidRva   = 0x9D49158; // GGameThreadId (uint32 slot)
constexpr uintptr_t kTypeMapOff    = 0x478;     // AssetTypeMap in the manager instance
constexpr uintptr_t kInfoTypeOff   = 0x00;      // FName PrimaryAssetType in FPrimaryAssetTypeData
constexpr uintptr_t kInfoBaseOff   = 0x30;      // UClass* AssetBaseClassLoaded
constexpr uintptr_t kInfoPathsOff  = 0x70;      // TArray<FString> scan paths

// ScanPathsForPrimaryAssets(this, FPrimaryAssetType (8-byte FName by value),
//   const TArray<FString>& Paths, UClass* BaseClass, bool, bool, bool) -> int32
typedef int32_t (*PFN_ScanPaths)(void* self, uint64_t primaryAssetType, void* paths,
                                 void* baseClass, bool bHasBP, bool bEditorOnly,
                                 bool bForceSync);

static PFN_ScanPaths g_Scan    = nullptr;
static void*         g_manager = nullptr;
static uintptr_t     g_modBase = 0;

static void WriteMarker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &written, nullptr);
    CloseHandle(h);
}

static bool PageReadable(const void* target) {
    MEMORY_BASIC_INFORMATION mbi = {0};
    if (VirtualQuery(target, &mbi, sizeof(mbi)) != sizeof(mbi)) return false;
    if (mbi.State != MEM_COMMIT) return false;
    if (mbi.Protect & PAGE_GUARD) return false;
    const DWORD readMask = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    return (mbi.Protect & readMask) != 0;
}
static bool LooksLikePtr(uintptr_t v) {
    return v >= 0x10000 && v < 0x0001000000000000ULL && (v & 0x7) == 0;
}

// Find the LokiAssetManager singleton: scan MEM_PRIVATE for qword == vtable, pick the
// instance whose AssetTypeMap Num > 0 (the CDO's is 0).
static void* ScanForManager(uintptr_t modBase) {
    const uintptr_t vt = modBase + kLokiMgrVtRva;
    char m[160];
    snprintf(m, sizeof(m), "[scan] LokiAssetManager vtable = 0x%llX\r\n", (unsigned long long)vt);
    WriteMarker(m);

    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
    const uintptr_t maxAddr = (uintptr_t)si.lpMaximumApplicationAddress;
    int hits = 0; void* picked = nullptr; uint32_t pickedNum = 0;

    while (addr < maxAddr) {
        MEMORY_BASIC_INFORMATION mbi = {0};
        if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) != sizeof(mbi)) break;
        const uintptr_t regionEnd = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
            (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) != 0 &&
            (mbi.Protect & PAGE_GUARD) == 0) {
            const uintptr_t* p = (const uintptr_t*)mbi.BaseAddress;
            const uintptr_t* end = (const uintptr_t*)regionEnd - (kTypeMapOff/8 + 2);
            for (; p < end; p++) {
                if (*p != vt) continue;
                hits++;
                const uint8_t* obj = (const uint8_t*)p;
                uintptr_t data = *(const uintptr_t*)(obj + kTypeMapOff);
                uint32_t   num  = *(const uint32_t*)(obj + kTypeMapOff + 8);
                uint32_t   mx   = *(const uint32_t*)(obj + kTypeMapOff + 12);
                char l[224];
                snprintf(l, sizeof(l), "[scan] hit #%d @%p typemap{data=0x%llX num=%u max=%u}\r\n",
                         hits, (void*)p, (unsigned long long)data, num, mx);
                WriteMarker(l);
                if (!picked && num > 0 && num <= 4096 && num <= mx && LooksLikePtr(data)) {
                    picked = (void*)p; pickedNum = num;
                }
            }
        }
        addr = regionEnd;
    }
    snprintf(m, sizeof(m), "[scan] done: %d vtable hits; picked=%p (typemap num=%u)\r\n",
             hits, picked, pickedNum);
    WriteMarker(m);
    return picked;
}

// APC body — runs on the game thread. Iterate the AssetTypeMap and call the scan
// per type with args read from each type's Info block.
static void NTAPI ScanApcCallback(ULONG_PTR) {
    if (!g_Scan || !g_manager || !g_modBase) { WriteMarker("[apc] FAIL globals\r\n"); return; }
    char m[256];
    snprintf(m, sizeof(m), "[apc] FIRING on game thread tid=%lu manager=%p scan=%p\r\n",
             GetCurrentThreadId(), g_manager, (void*)g_Scan);
    WriteMarker(m);

    const uint8_t* mgr = (const uint8_t*)g_manager;
    if (!PageReadable(mgr + kTypeMapOff)) { WriteMarker("[apc] FAIL typemap unreadable\r\n"); return; }
    uintptr_t data = *(const uintptr_t*)(mgr + kTypeMapOff);
    uint32_t  num  = *(const uint32_t*)(mgr + kTypeMapOff + 8);
    uint32_t  mx   = *(const uint32_t*)(mgr + kTypeMapOff + 12);
    snprintf(m, sizeof(m), "[apc] AssetTypeMap data=0x%llX num=%u max=%u\r\n",
             (unsigned long long)data, num, mx);
    WriteMarker(m);
    if (!LooksLikePtr(data) || mx == 0 || mx > 4096) { WriteMarker("[apc] FAIL bad typemap\r\n"); return; }

    int called = 0;
    for (uint32_t i = 0; i < mx; i++) {
        const uint8_t* elem = (const uint8_t*)data + (uintptr_t)i * 0x20;
        if (!PageReadable(elem)) continue;
        uint64_t key = *(const uint64_t*)(elem + 0x00);       // FName type key
        uintptr_t td = *(const uintptr_t*)(elem + 0x08);      // FPrimaryAssetTypeData*
        if (key == 0 || !LooksLikePtr(td) || !PageReadable((void*)td)) continue;

        const uint8_t* info = (const uint8_t*)td;
        uint64_t  type  = *(const uint64_t*)(info + kInfoTypeOff);
        uintptr_t base  = *(const uintptr_t*)(info + kInfoBaseOff);
        void*     paths = (void*)(info + kInfoPathsOff);
        // sanity: the Info type FName must match the map key, and base must be a ptr.
        if (type != key || !LooksLikePtr(base) || !PageReadable((void*)base)) continue;

        int32_t added = g_Scan(g_manager, type, paths, (void*)base, true, false, true);
        called++;
        snprintf(m, sizeof(m), "[apc] scan type_fname=0x%llX base=0x%llX -> added=%d\r\n",
                 (unsigned long long)(type & 0xFFFFFFFF), (unsigned long long)base, added);
        WriteMarker(m);
    }
    snprintf(m, sizeof(m), "[apc] DONE: called scan for %d types\r\n", called);
    WriteMarker(m);
}

static DWORD WaitForGameTid(uintptr_t modBase, DWORD timeoutMs) {
    uint32_t* slot = (uint32_t*)(modBase + kGGameTidRva);
    const DWORD deadline = GetTickCount() + timeoutMs;
    while (GetTickCount() < deadline) {
        if (PageReadable(slot)) {
            uint32_t v = 0; memcpy(&v, slot, sizeof(v));
            if (v != 0) return v;
        }
        Sleep(10);
    }
    return 0;
}

static DWORD WINAPI Worker(LPVOID) {
    WriteMarker("[0] scan_shim worker started\r\n");
    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) { WriteMarker("[0] FAIL GetModuleHandleA\r\n"); return 1; }
    g_modBase = (uintptr_t)hExe;
    char m[96]; snprintf(m, sizeof(m), "[0] modBase=0x%llX\r\n", (unsigned long long)g_modBase);
    WriteMarker(m);

    DWORD gameTid = WaitForGameTid(g_modBase, 60000);
    if (!gameTid) { WriteMarker("[1] FAIL: GGameThreadId stayed 0\r\n"); return 2; }
    snprintf(m, sizeof(m), "[1] gameTid=%lu\r\n", gameTid); WriteMarker(m);

    // Grace: this shim is injected at the MENU (post-init) so the manager is already
    // built; a short settle is plenty.
    Sleep(1500);

    void* mgr = ScanForManager(g_modBase);
    if (!mgr) { WriteMarker("[scan] FAIL: no LokiAssetManager singleton found\r\n"); return 3; }
    g_manager = mgr;
    g_Scan = (PFN_ScanPaths)(g_modBase + kScanPathsRva);

    HANDLE gt = OpenThread(THREAD_SET_CONTEXT, FALSE, gameTid);
    if (!gt) { snprintf(m, sizeof(m), "[apc] OpenThread FAIL err=%lu\r\n", GetLastError()); WriteMarker(m); return 5; }
    DWORD ok = QueueUserAPC(ScanApcCallback, gt, 0);
    CloseHandle(gt);
    if (!ok) { snprintf(m, sizeof(m), "[apc] QueueUserAPC FAIL err=%lu\r\n", GetLastError()); WriteMarker(m); return 6; }
    WriteMarker("[apc] queued on game thread; fires on next alertable wait\r\n");
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        WriteMarker("[+] scan_shim attached, spawning worker\r\n");
        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    }
    return TRUE;
}
extern "C" __declspec(dllexport) void* start_mod() { return new int(0); }
extern "C" __declspec(dllexport) void uninstall_mod(void* mod) { delete static_cast<int*>(mod); }
