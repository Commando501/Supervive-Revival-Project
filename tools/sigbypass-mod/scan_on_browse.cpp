// scan_on_browse — populate LokiAssetManager's per-type AssetMaps at exactly the
// right moment so the ALL HUNTERS grid (and store / cosmetics / missions) render.
//
// THE PROBLEM THIS SOLVES (session 42 diagnosis, final):
//   The in-game FAssetRegistry is FULL (103,841 entries incl. all 25 correctly-tagged
//   heroes). LokiAssetManager registers each primary-asset TYPE's Info from config
//   (AssetTypeMap has all 30 types) but never runs the directory-scan that fills each
//   type's per-type AssetMap. So GetPrimaryAssetIdList(Hero) returns 0 and every grid
//   is empty. The fix is to call the stock UAssetManager::ScanPathsForPrimaryAssets
//   per type against the already-full registry — proven to take Hero 0 -> 25 assets.
//
//   BUT the menu builds its hero catalog ONCE at menu-load, via
//   ChangeBundleStateForPrimaryAssets, which fails ("failed to find NameData") because
//   the AssetMaps are still empty at that instant. A POST-menu scan is too late — the
//   empty catalog is already built and cached (opening HUNTERS does no re-query).
//   So the scan MUST run AFTER the types register but BEFORE the menu-load catalog build.
//
// THE TIMING WINDOW (verified from a normal-client Loki.log, all on the game thread):
//   :40.864  UEngine::Browse  "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent"  <-- HOOK HERE
//   :41.860  LoadMap LobbyV2 complete
//   :42.391  ChangeBundleStateForPrimaryAssets failed to find NameData          <-- catalog build
//   => running the scan at the LobbyV2 Browse (entry) executes it ~1.5s BEFORE the
//      catalog build, on the same game thread, when the process is fully stable.
//
// WHY A BROWSE HOOK (not scan_shim's early APC):
//   scan_shim injected early crashed — its worker brute-force-scanned ALL private
//   memory REPEATEDLY during the volatile early-init/unpack phase (a worker-thread AV
//   on a page decommitted mid-scan takes down the process; the Loki.log tail then
//   misattributes it to whatever the game thread was doing). This payload instead
//   installs a PASSIVE hook early (browse_hook's proven-stable pattern — only reads a
//   fixed RVA at install time) and does the memory-scan + asset-scan LATER, inside the
//   LobbyV2 Browse call, when the process is as stable as the proven post-menu scan.
//   The hook also fires deterministically at the right moment — no APC timing gamble.
//
// Offsets (this build; stable across launches, ASLR moves base only):
//   UEngine::Browse            = RVA +0x3EC57D0  (8-push prologue, 13-byte clean cut)
//   UAssetManager::ScanPathsForPrimaryAssets = RVA +0x34CF9F0
//   LokiAssetManager vtable    = RVA +0x888CB78  (NOT +0x88CB78 — digit-drop typo)
//   GGameThreadId slot         = RVA +0x9D49158
//   manager + 0x478            = AssetTypeMap {Data, Num, Max}, stride 0x20:
//                                key FName @+0x00, value FPrimaryAssetTypeData* @+0x08
//   FPrimaryAssetTypeData      = Type FName @+0x00, BaseClass UClass* @+0x30,
//                                scan-paths TArray<FString> @+0x70
//   FURL.Map (Browse arg r8)   = FString @ r8+0x28  {wchar_t* Data, int32 Num, int32 Max}
//
// Build:  clang++ -shared -O2 scan_on_browse.cpp -o scan_on_browse.dll -lkernel32
// Inject (EARLY, so the hook is installed before the LobbyV2 Browse):
//   tools/inject watch-now SUPERVIVE-Win64-Shipping.exe scan_on_browse.dll
// Marker: docs/scan-on-browse-marker.txt (truncated each load).

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

// POPULATE=1 (default): actually call ScanPathsForPrimaryAssets to populate the
// AssetMaps. POPULATE=0 builds a CONTROL variant that does everything else identically
// (inject, hook, find the manager — same ~game-thread cost) but does NOT populate, to
// isolate whether the post-menu crash comes from the grid rendering 25 heroes vs. from
// the injection/manager-find itself.
#ifndef POPULATE
#define POPULATE 1
#endif

// HERO_ONLY=1 populates ONLY the Hero primary-asset type (25 assets — the ALL HUNTERS
// grid) and skips the other 29 types (thousands of cues/items/cosmetics). Isolates
// whether the post-menu crash comes from the 25 hero preview assets specifically or
// from the bulk of registering/loading everything.
#ifndef HERO_ONLY
#define HERO_ONLY 0
#endif
constexpr uint32_t kHeroFNameId = 0x1A568;   // "Hero" FName id (this build's pool)

// ───────── constants ──────────────────────────────────────────────────

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\scan-on-browse-marker.txt";

constexpr uintptr_t kUEngineBrowseRva = 0x3EC57D0;  // UEngine::Browse entry
constexpr uintptr_t kScanPathsRva     = 0x34CF9F0;  // UAssetManager::ScanPathsForPrimaryAssets
constexpr uintptr_t kLokiMgrVtRva     = 0x888CB78;  // LokiAssetManager vtable
constexpr uintptr_t kGGameTidRva      = 0x9D49158;  // GGameThreadId (uint32 slot)
constexpr size_t    kPatchSize        = 13;         // 8 pushes worth of bytes
constexpr uintptr_t kTypeMapOff       = 0x478;      // AssetTypeMap in the manager instance
constexpr uintptr_t kInfoBaseOff      = 0x30;       // UClass* AssetBaseClassLoaded
constexpr uintptr_t kInfoPathsOff     = 0x70;       // TArray<FString> scan paths
constexpr uintptr_t kFurlMapOff       = 0x28;       // FString Map inside FURL

// ScanPathsForPrimaryAssets(this, FPrimaryAssetType (8-byte FName by value),
//   const TArray<FString>& Paths, UClass* BaseClass, bool, bool, bool) -> int32
typedef int32_t (*PFN_ScanPaths)(void* self, uint64_t primaryAssetType, void* paths,
                                 void* baseClass, bool bHasBP, bool bEditorOnly,
                                 bool bForceSync);

// ───────── globals ────────────────────────────────────────────────────

static uintptr_t     g_modBase    = 0;
static uintptr_t     g_browseAddr = 0;
static uint8_t       g_origBytes[kPatchSize];
static uint8_t*      g_trampoline = nullptr;
static uint8_t*      g_hookStub   = nullptr;
static PFN_ScanPaths g_scan       = nullptr;
static void*         g_manager    = nullptr;
static volatile bool g_scanned    = false;   // one-shot guard (game thread only)
static volatile bool g_unhooked   = false;   // Browse prologue restored after the scan

// ───────── marker file (WORKER-THREAD ONLY — never from the Browse handler) ─────────
//
// Synchronous file I/O from inside the Browse call (a critical map-load path) is
// risky, so the game-thread handler logs into an in-DLL ring buffer and the worker
// thread flushes it to disk. Marker()/Markerf() below are for the worker only.

static void Marker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD wrote = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &wrote, nullptr);
    CloseHandle(h);
}
static void Markerf(const char* fmt, ...) {
    char buf[512];
    va_list ap; va_start(ap, fmt);
    _vsnprintf_s(buf, sizeof(buf), _TRUNCATE, fmt, ap); va_end(ap);
    Marker(buf);
}

// ───────── deferred-log ring (game-thread-safe: memory only, no syscalls) ─────────

constexpr size_t       kLogBufSize = 64 * 1024;
static char            g_logBuf[kLogBufSize];
static volatile LONG64 g_logHead = 0;

static void RingAppend(const char* src, int n) {
    LONG64 pos = InterlockedExchangeAdd64(&g_logHead, (LONG64)n);
    if (pos + n > (LONG64)sizeof(g_logBuf)) return;   // full — drop (scan still runs)
    for (int i = 0; i < n; i++) g_logBuf[pos + i] = src[i];
}
static void RingLog(const char* s) { RingAppend(s, (int)strlen(s)); }
static void RingLogf(const char* fmt, ...) {
    char buf[256];
    va_list ap; va_start(ap, fmt);
    _vsnprintf_s(buf, sizeof(buf), _TRUNCATE, fmt, ap); va_end(ap);
    RingAppend(buf, (int)strlen(buf));
}

// ───────── safe memory helpers ────────────────────────────────────────

static bool SafeReadable(const void* addr, size_t size) {
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(addr, &mbi, sizeof(mbi)) == 0) return false;
    if (!(mbi.State & MEM_COMMIT)) return false;
    if (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return false;
    uintptr_t start = (uintptr_t)addr;
    uintptr_t end   = start + size;
    return end <= (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
}
static bool LooksLikePtr(uintptr_t v) {
    return v >= 0x10000 && v < 0x0001000000000000ULL && (v & 0x7) == 0;
}

// WideContainsAscii — does the wide string [s, s+num) contain the ASCII needle?
static bool WideContainsAscii(const wchar_t* s, int num, const char* needle) {
    int nlen = (int)strlen(needle);
    for (int i = 0; i + nlen <= num; i++) {
        bool m = true;
        for (int j = 0; j < nlen; j++) {
            if ((char)(s[i + j] & 0xFF) != needle[j]) { m = false; break; }
        }
        if (m) return true;
    }
    return false;
}

// ───────── manager find + scan (runs on the game thread inside the Browse hook) ─────

// Find the LokiAssetManager singleton: scan committed MEM_PRIVATE for a qword ==
// vtable, pick the instance whose AssetTypeMap Num > 0 (the CDO's is 0). Same as the
// proven post-menu scan_shim path — safe here because the LobbyV2 Browse fires after
// the process is fully unpacked/stable (unlike scan_shim's crashing early-init scan).
static void* ScanForManager(uintptr_t modBase) {
    const uintptr_t vt = modBase + kLokiMgrVtRva;
    RingLogf("[find] LokiAssetManager vtable = 0x%llX\r\n", (unsigned long long)vt);

    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
    const uintptr_t maxAddr = (uintptr_t)si.lpMaximumApplicationAddress;
    int hits = 0; void* picked = nullptr; uint32_t pickedNum = 0;
    bool strong = false;   // found the real singleton (~30 types) — stop scanning

    // Pick the MOST-populated instance, not the first with num>0: several objects
    // carry the LokiAssetManager vtable (the CDO with num=0, and stray/partial
    // matches — session-43 saw a bogus num=1 hit with a non-heap data ptr). Only the
    // real singleton has ~30 registered types. Validate the typemap data is a
    // readable heap pointer, track max num, and early-out once num>=25 (bounds the
    // full-memory scan cost, which runs on the game thread inside Browse).
    while (addr < maxAddr && !strong) {
        MEMORY_BASIC_INFORMATION mbi = {0};
        if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) != sizeof(mbi)) break;
        const uintptr_t regionEnd = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
            (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) != 0 &&
            (mbi.Protect & PAGE_GUARD) == 0) {
            const uintptr_t* p = (const uintptr_t*)mbi.BaseAddress;
            const uintptr_t* end = (const uintptr_t*)regionEnd - (kTypeMapOff / 8 + 2);
            for (; p < end; p++) {
                if (*p != vt) continue;
                hits++;
                const uint8_t* obj = (const uint8_t*)p;
                uintptr_t data = *(const uintptr_t*)(obj + kTypeMapOff);
                uint32_t   num  = *(const uint32_t*)(obj + kTypeMapOff + 8);
                uint32_t   mx   = *(const uint32_t*)(obj + kTypeMapOff + 12);
                RingLogf("[find]  hit @%p typemap{data=0x%llX num=%u max=%u}\r\n",
                         (void*)p, (unsigned long long)data, num, mx);
                bool valid = num > 0 && num <= 4096 && num <= mx &&
                             LooksLikePtr(data) && SafeReadable((void*)data, 0x20);
                if (valid && num > pickedNum) {
                    picked = (void*)p; pickedNum = num;
                    if (num >= 25) { strong = true; break; }
                }
            }
        }
        addr = regionEnd;
    }
    RingLogf("[find] %d vtable hits; picked=%p (typemap num=%u)\r\n",
             hits, picked, pickedNum);
    return picked;
}

// Find the manager FAST via GEngine->AssetManager — rcx in UEngine::Browse IS GEngine
// (UEngine*), and UEngine holds a UAssetManager* field. Scan only UEngine's own memory
// (a few KB) for a pointer to a LokiAssetManager-vtable object with a populated typemap.
// This is instant (no game-thread freeze), unlike the full-address-space ScanForManager
// (which froze the game thread ~10s and was a base destabilizer — session 43).
static void* FindManagerViaEngine(uintptr_t engine) {
    if (!engine || !LooksLikePtr(engine)) return nullptr;
    const uintptr_t vt = g_modBase + kLokiMgrVtRva;
    for (uintptr_t off = 0; off < 0x8000; off += 8) {   // UEngine is well under 32KB
        if (!SafeReadable((void*)(engine + off), 8)) break;
        uintptr_t cand = *(uintptr_t*)(engine + off);
        if (!LooksLikePtr(cand)) continue;
        if (!SafeReadable((void*)cand, kTypeMapOff + 16)) continue;
        if (*(uintptr_t*)cand != vt) continue;                 // object's vtable matches
        uint32_t num = *(uint32_t*)(cand + kTypeMapOff + 8);   // AssetTypeMap.Num
        if (num >= 25 && num <= 4096) {
            RingLogf("[find] via GEngine+0x%llX -> manager=%p typemap num=%u\r\n",
                     (unsigned long long)off, (void*)cand, num);
            return (void*)cand;
        }
    }
    return nullptr;
}

// Iterate the manager's AssetTypeMap and call ScanPathsForPrimaryAssets per type,
// reading all args straight from each type's Info block (constructs nothing).
static void RunScanForAllTypes() {
    const uint8_t* mgr = (const uint8_t*)g_manager;
    if (!SafeReadable(mgr + kTypeMapOff, 16)) { RingLog("[scan] typemap unreadable\r\n"); return; }
    uintptr_t data = *(const uintptr_t*)(mgr + kTypeMapOff);
    uint32_t  num  = *(const uint32_t*)(mgr + kTypeMapOff + 8);
    uint32_t  mx   = *(const uint32_t*)(mgr + kTypeMapOff + 12);
    RingLogf("[scan] AssetTypeMap data=0x%llX num=%u max=%u\r\n",
             (unsigned long long)data, num, mx);
    if (!LooksLikePtr(data) || mx == 0 || mx > 4096) { RingLog("[scan] bad typemap\r\n"); return; }

    int called = 0; int heroAdded = -1;
    for (uint32_t i = 0; i < mx; i++) {
        const uint8_t* elem = (const uint8_t*)data + (uintptr_t)i * 0x20;
        if (!SafeReadable(elem, 0x10)) continue;
        uint64_t  key = *(const uint64_t*)(elem + 0x00);   // FName type key
        uintptr_t td  = *(const uintptr_t*)(elem + 0x08);  // FPrimaryAssetTypeData*
        if (key == 0 || !LooksLikePtr(td) || !SafeReadable((void*)td, 0x80)) continue;

        const uint8_t* info = (const uint8_t*)td;
        uint64_t  type = *(const uint64_t*)(info + 0x00);
        uintptr_t base = *(const uintptr_t*)(info + kInfoBaseOff);
        void*     paths = (void*)(info + kInfoPathsOff);
        if (type != key || !LooksLikePtr(base) || !SafeReadable((void*)base, 8)) continue;

#if HERO_ONLY
        if ((uint32_t)(type & 0xFFFFFFFF) != kHeroFNameId) continue;   // Hero type only
#endif
#if POPULATE
        int32_t added = g_scan(g_manager, type, paths, (void*)base, true, false, true);
#else
        int32_t added = -2;   // CONTROL: found the type but did NOT scan/populate
        (void)paths; (void)base;
#endif
        called++;
        RingLogf("[scan] type_fname=0x%llX -> added=%d\r\n",
                 (unsigned long long)(type & 0xFFFFFFFF), added);
        if ((type & 0xFFFFFFFF) == 0x1A568) heroAdded = added;   // Hero FName id
    }
    RingLogf("[scan] DONE: called scan for %d types (Hero added=%d)\r\n", called, heroAdded);
}

// ───────── the Browse hook handlers ───────────────────────────────────
//
// PRE: called with the original Browse params in (rcx,rdx,r8,r9). r8 = FURL*. When the
// LobbyV2 map is browsed, run the scan ONCE on this (game) thread, then let Browse run.
// POST: no-op (we do not modify Browse's behavior or the URL — normal-client path).

extern "C" void scan_browse_pre(uintptr_t rcx, uintptr_t /*rdx*/,
                                uintptr_t r8, uintptr_t /*r9*/) {
    if (g_scanned) return;
    if (!SafeReadable((const void*)(r8 + kFurlMapOff), 16)) return;
    wchar_t* mapData = *(wchar_t**)(r8 + kFurlMapOff);
    int32_t  mapNum  = *(int32_t*)(r8 + kFurlMapOff + 8);
    if (!mapData || mapNum <= 0 || mapNum > 1024 || !SafeReadable(mapData, (size_t)mapNum * 2))
        return;
    // Scan on the EARLIEST Browse where the manager is ready (populated typemap) —
    // typically the Login browse — BEFORE the menu widgets enumerate their hero catalog.
    // Populating at the Lobby browse was too late: the RPM dump proved the catalog itself
    // populates correctly (25 heroes under PascalCase PrimaryAssetNames — Alchemist,
    // Wukong, ...), yet the grid stays empty, i.e. the grid's ONE-SHOT enumeration had
    // already cached an empty list. rcx = GEngine (UEngine*); the find is instant and
    // freeze-free. If the manager isn't ready yet at this Browse, retry on the next one
    // (do NOT fall back to the full-memory scan — that froze the game thread).
    void* mgr = FindManagerViaEngine(rcx);
    if (!mgr) { RingLog("[pre] manager not ready at this Browse; will retry next\r\n"); return; }
    char mb[80]; int mc = 0;
    for (int i = 0; i < mapNum && mc < 79; i++) { char c = (char)(mapData[i] & 0x7F); mb[mc++] = (c >= 32 && c < 127) ? c : '.'; }
    mb[mc] = 0;
    RingLogf("[pre] scanning at earliest ready Browse (map=%s)\r\n", mb);
    g_manager = mgr;
    g_scan    = (PFN_ScanPaths)(g_modBase + kScanPathsRva);
    RunScanForAllTypes();
    g_scanned = true;   // set only after a successful attempt
    RingLog("[pre] scan complete; continuing original Browse\r\n");
}

extern "C" void scan_browse_post(uintptr_t /*rcx*/, uintptr_t /*rdx*/,
                                 uintptr_t /*r8*/, uintptr_t /*r9*/) {
    // no-op: we do not alter Browse or the URL on the normal-client path.
}

// ───────── machine-code emitters (verbatim from browse_hook — proven) ──────────

static uint8_t* BuildTrampoline(uintptr_t browseAddr) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x40, MEM_COMMIT | MEM_RESERVE,
                                        PAGE_EXECUTE_READWRITE);
    if (!p) return nullptr;
    // 8 push instructions = original first 13 bytes of UEngine::Browse.
    p[ 0] = 0x40; p[ 1] = 0x55;          // push rbp
    p[ 2] = 0x53;                         // push rbx
    p[ 3] = 0x56;                         // push rsi
    p[ 4] = 0x57;                         // push rdi
    p[ 5] = 0x41; p[ 6] = 0x54;          // push r12
    p[ 7] = 0x41; p[ 8] = 0x55;          // push r13
    p[ 9] = 0x41; p[10] = 0x56;          // push r14
    p[11] = 0x41; p[12] = 0x57;          // push r15
    // mov rax, browseAddr+13 ; jmp rax
    uint64_t back = browseAddr + kPatchSize;
    p[13] = 0x48; p[14] = 0xB8;
    memcpy(p + 15, &back, 8);
    p[23] = 0xFF; p[24] = 0xE0;
    return p;
}

// WRAP: sub rsp,0x48; spill rcx/rdx/r8/r9; call PRE; reload; call trampoline (Browse
// runs, returns here); save rax; reload; call POST; restore rax; add rsp,0x48; ret.
static uint8_t* BuildHookStub(void* preHandler, void* postHandler, void* trampoline) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x200, MEM_COMMIT | MEM_RESERVE,
                                        PAGE_EXECUTE_READWRITE);
    if (!p) return nullptr;
    uint8_t* w = p;

    *w++ = 0x48; *w++ = 0x83; *w++ = 0xEC; *w++ = 0x48;                // sub rsp, 0x48
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;   // mov [rsp+0x20], rcx
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;   // mov [rsp+0x28], rdx
    *w++ = 0x4C; *w++ = 0x89; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;   // mov [rsp+0x30], r8
    *w++ = 0x4C; *w++ = 0x89; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;   // mov [rsp+0x38], r9

    *w++ = 0x48; *w++ = 0xB8;                                          // mov rax, preHandler
    uint64_t pre64 = (uint64_t)preHandler; memcpy(w, &pre64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;                                          // call rax

    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;   // mov rcx, [rsp+0x20]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;   // mov rdx, [rsp+0x28]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;   // mov r8, [rsp+0x30]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;   // mov r9, [rsp+0x38]

    *w++ = 0x48; *w++ = 0xB8;                                          // mov rax, trampoline
    uint64_t t64 = (uint64_t)trampoline; memcpy(w, &t64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;                                          // call rax (Browse)

    *w++ = 0x48; *w++ = 0x89; *w++ = 0x44; *w++ = 0x24; *w++ = 0x40;   // mov [rsp+0x40], rax

    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;   // mov rcx, [rsp+0x20]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;   // mov rdx, [rsp+0x28]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;   // mov r8, [rsp+0x30]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;   // mov r9, [rsp+0x38]

    *w++ = 0x48; *w++ = 0xB8;                                          // mov rax, postHandler
    uint64_t post64 = (uint64_t)postHandler; memcpy(w, &post64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;                                          // call rax

    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x40;   // mov rax, [rsp+0x40]
    *w++ = 0x48; *w++ = 0x83; *w++ = 0xC4; *w++ = 0x48;                // add rsp, 0x48
    *w++ = 0xC3;                                                       // ret
    return p;
}

// ───────── worker ─────────────────────────────────────────────────────

static DWORD WaitForGameTid(uintptr_t modBase, DWORD timeoutMs) {
    uint32_t* slot = (uint32_t*)(modBase + kGGameTidRva);
    const DWORD deadline = GetTickCount() + timeoutMs;
    while (GetTickCount() < deadline) {
        MEMORY_BASIC_INFORMATION mbi{};
        if (VirtualQuery(slot, &mbi, sizeof(mbi)) == 0 ||
            !(mbi.State & MEM_COMMIT) || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
            Sleep(20); continue;
        }
        uint32_t v = 0; memcpy(&v, slot, sizeof(v));
        if (v != 0) return v;
        Sleep(20);
    }
    return 0;
}

static DWORD WINAPI Worker(LPVOID) {
    // Truncate marker at boot for a clean slate.
    HANDLE h = CreateFileA(kMarkerPath, GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    Marker("[0] scan_on_browse worker started\r\n");

    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) { Marker("[0] FAIL: GetModuleHandleA NULL\r\n"); return 1; }
    g_modBase    = (uintptr_t)hExe;
    g_browseAddr = g_modBase + kUEngineBrowseRva;
    Markerf("[0] modBase=0x%llX  UEngine::Browse=0x%llX\r\n",
            (unsigned long long)g_modBase, (unsigned long long)g_browseAddr);

    Marker("[1] waiting for GGameThreadId (60s)...\r\n");
    DWORD gameTid = WaitForGameTid(g_modBase, 60000);
    if (gameTid == 0) { Marker("[1] FAIL: GGameThreadId stayed 0 for 60s\r\n"); return 2; }
    Markerf("[1] gameTid=%lu\r\n", gameTid);

    // Wait for the packer to unpack the .text page holding UEngine::Browse before we
    // read/patch its prologue (GGameThreadId can be set before that page is committed).
    static const uint8_t kExpected[kPatchSize] = {
        0x40, 0x55, 0x53, 0x56, 0x57, 0x41, 0x54, 0x41, 0x55, 0x41, 0x56, 0x41, 0x57
    };
    DWORD deadline = GetTickCount() + 30000;
    int polls = 0; bool unpacked = false;
    while (GetTickCount() < deadline) {
        polls++;
        MEMORY_BASIC_INFORMATION mbi{};
        if (VirtualQuery((void*)g_browseAddr, &mbi, sizeof(mbi)) == 0 ||
            !(mbi.State & MEM_COMMIT) || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
            Sleep(5); continue;
        }
        memcpy(g_origBytes, (const void*)g_browseAddr, kPatchSize);
        if (memcmp(g_origBytes, kExpected, kPatchSize) == 0) { unpacked = true; break; }
        Sleep(5);
    }
    if (!unpacked) { Marker("[2] FAIL: Browse prologue never matched — refusing to patch\r\n"); return 3; }
    Markerf("[2] page unpacked after %d poll(s); prologue matches\r\n", polls);

    g_trampoline = BuildTrampoline(g_browseAddr);
    if (!g_trampoline) { Markerf("[3] FAIL trampoline (err=%lu)\r\n", GetLastError()); return 4; }
    g_hookStub = BuildHookStub((void*)&scan_browse_pre, (void*)&scan_browse_post,
                               (void*)g_trampoline);
    if (!g_hookStub) { Markerf("[3] FAIL hook stub (err=%lu)\r\n", GetLastError()); return 5; }
    Markerf("[3] trampoline @ %p  hook stub @ %p\r\n", (void*)g_trampoline, (void*)g_hookStub);

    // Patch: mov rax, hookStub ; jmp rax ; nop  (13 bytes).
    uint8_t patch[kPatchSize];
    patch[0] = 0x48; patch[1] = 0xB8;
    uint64_t stub64 = (uint64_t)g_hookStub; memcpy(patch + 2, &stub64, 8);
    patch[10] = 0xFF; patch[11] = 0xE0; patch[12] = 0x90;

    DWORD oldProt = 0;
    if (!VirtualProtect((void*)g_browseAddr, kPatchSize, PAGE_EXECUTE_READWRITE, &oldProt)) {
        Markerf("[4] FAIL VirtualProtect (err=%lu)\r\n", GetLastError()); return 6;
    }
    memcpy((void*)g_browseAddr, patch, kPatchSize);
    DWORD discard = 0;
    VirtualProtect((void*)g_browseAddr, kPatchSize, oldProt, &discard);
    FlushInstructionCache(GetCurrentProcess(), (void*)g_browseAddr, kPatchSize);
    Marker("[4] Browse HOOK INSTALLED — waiting for the LobbyV2 Browse to run the scan\r\n");

    // Flush the game-thread ring buffer to disk, plus a heartbeat.
    LONG64 lastFlushed = 0; DWORD lastHeartbeat = GetTickCount();
    DWORD  scannedAtTick = 0;
    while (true) {
        Sleep(200);

        // UN-HOOK after the scan: restore the original Browse prologue so a periodic
        // code-integrity check finds UEngine::Browse pristine. The hook is only needed
        // to trigger the one-shot scan; leaving the patch installed is a candidate base
        // destabilizer (session 43: even the no-populate control crashed ~4.75 min).
        // Wait ~1.5s after the scan so the triggering Browse call has fully returned and
        // no thread is executing inside our stub/trampoline before we revert.
        if (g_scanned && !g_unhooked) {
            if (scannedAtTick == 0) scannedAtTick = GetTickCount();
            else if (GetTickCount() - scannedAtTick >= 1500) {
                DWORD op = 0;
                if (VirtualProtect((void*)g_browseAddr, kPatchSize, PAGE_EXECUTE_READWRITE, &op)) {
                    memcpy((void*)g_browseAddr, g_origBytes, kPatchSize);
                    DWORD d = 0;
                    VirtualProtect((void*)g_browseAddr, kPatchSize, op, &d);
                    FlushInstructionCache(GetCurrentProcess(), (void*)g_browseAddr, kPatchSize);
                    g_unhooked = true;
                    Marker("[unhook] restored original Browse prologue after scan\r\n");
                }
            }
        }

        LONG64 head = g_logHead;
        if (head > (LONG64)sizeof(g_logBuf)) head = (LONG64)sizeof(g_logBuf);
        if (head > lastFlushed) {
            HANDLE f = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                                   FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                                   OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
            if (f != INVALID_HANDLE_VALUE) {
                DWORD wrote = 0;
                WriteFile(f, g_logBuf + lastFlushed, (DWORD)(head - lastFlushed), &wrote, nullptr);
                CloseHandle(f);
                lastFlushed = head;
            }
        }
        DWORD now = GetTickCount();
        if (now - lastHeartbeat >= 5000) {
            Markerf("[hb] scanned=%d head=%lld\r\n", g_scanned ? 1 : 0, (long long)g_logHead);
            lastHeartbeat = now;
        }
    }
}

// ───────── DllMain ────────────────────────────────────────────────────

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    }
    return TRUE;
}
extern "C" __declspec(dllexport) void* start_mod() { return new int(0); }
extern "C" __declspec(dllexport) void uninstall_mod(void* mod) { delete static_cast<int*>(mod); }
