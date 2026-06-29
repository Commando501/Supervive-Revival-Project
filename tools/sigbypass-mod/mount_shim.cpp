// mount_shim — combined sig-bypass + runtime Mount + AR-reload-via-delegate.
//
// Sequence:
//   1. DllMain spawns a worker thread (CREATE_SUSPENDED-compatible: doesn't block).
//   2. Worker waits for FPakSignatureFile::Load page commit at module RVA 0x2047EE0,
//      then VirtualProtect+memcpy patches the entry to `mov al,1; ret` so unsigned
//      paks pass the engine's signature check.
//   3. Worker scans MEM_PRIVATE for qword == module_base + 0x79E0C78 (FPakPlatformFile
//      vtable A). For each match it logs structural info; picks the first match whose
//      [+0x10] == module_base + 0x79E0C80 (vtable B) — definitive FPakPlatformFile.
//   4. Worker reads GGameThreadId from slot at module_base + 0x9D49158 and queues a
//      user-mode APC on that thread.
//   5. The APC body calls FPakPlatformFile::Mount wrapper at module_base + 0x204FFD0
//      with (singleton, kModDirPath). The wrapper supplies the default "*.pak" mask.
//   6. Inside Mount the engine scans kModDirPath for *.pak, finds our mod pak, calls
//      the per-pak inner mount; FPakSignatureFile::Load returns true (patched), pak
//      mounts; engine fires FCoreDelegates::OnPakFileMounted2.Broadcast which the
//      FAssetRegistry listens to and runs ScanPathsSynchronous on the new pak's
//      paths — automatic AR reload, no separate call needed.
//
// All offsets come from tools/usmapdump live-process RE (see
// docs/trackb-assetregistry-route.md and supervive-milestone3-trackb-status memory
// file). They're STABLE across launches per prior work; only ASLR base moves.
//
// Marker file lets us pinpoint outcome without needing the game's own log:
//   docs/mount-shim-marker.txt
//
// Build:
//   clang++ -shared -O2 mount_shim.cpp -o mount_shim.dll -lkernel32
//
// Deploy (suspended-launch flow same as sigbypass-mod):
//   tools/sigbypass-mod/race-mount-suspended.ps1

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

// ─── constants ────────────────────────────────────────────────────────────────

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\mount-shim-marker.txt";

// Directory containing ONLY our mod pak. Mount's default mask is L"*.pak" so any
// other .pak file present here would also be mounted — keep this clean.
// race-mount-suspended.ps1 creates it + copies pakchunk999-WindowsClient_P.pak in.
static const wchar_t kModDirPath[] =
    L"G:\\git\\Supervive Revival Project\\tools\\extractor\\out\\modpaks";

// Module-relative offsets (stable per build).
constexpr uintptr_t kPakSigLoadRva    = 0x2047EE0; // FPakSignatureFile::Load entry
constexpr uintptr_t kMountWrapperRva  = 0x204FFD0; // FPakPlatformFile::Mount 2-arg wrapper
constexpr uintptr_t kVtableARva       = 0x79E0C78; // FPakPlatformFile vtable A start
constexpr uintptr_t kVtableBRva       = 0x79E0C80; // FPakPlatformFile vtable B (MI second base)
constexpr uintptr_t kGGameTidRva      = 0x9D49158; // GGameThreadId (uint32 slot)

// Patch: B0 01 C3 (mov al, 1; ret) + NOP pad covering the original 16-byte prologue.
static const uint8_t kPatch[16] = {
    0xB0, 0x01, 0xC3,
    0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90,
};

// FPakSignatureFile::Load prologue we wait for:
//   40 55 53 41 54 41 55 41 56 41 57 48 8D 6C 24 F8
static const uint8_t kPrologue8[8] = {0x40, 0x55, 0x53, 0x41, 0x54, 0x41, 0x55, 0x41};

// ─── globals shared with APC ─────────────────────────────────────────────────

// Windows x64 calling convention IS __fastcall by default for free functions.
typedef bool (*PFN_Mount)(void* singleton, const wchar_t* mountDir);

static PFN_Mount      g_Mount     = nullptr;
static void*          g_singleton = nullptr;
static const wchar_t* g_modDir    = nullptr;

// ─── marker logging ──────────────────────────────────────────────────────────

static void WriteMarker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &written, nullptr);
    CloseHandle(h);
}

// ─── SEH-free read helpers ───────────────────────────────────────────────────

// Clang's __try/__except in our manual-mapped DLL doesn't dispatch reliably (the
// SEH chain isn't set up the way Windows expects despite registered .pdata). So
// we gate every read on VirtualQuery instead of catching AVs.
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

static bool SafeReadEight(const uint8_t* target, uint8_t out[8]) {
    if (!PageReadable(target)) return false;
    for (int i = 0; i < 8; i++) out[i] = target[i];
    return true;
}

// ─── wait for sig-load function bytes to appear ──────────────────────────────

static bool WaitForPrologue(uint8_t* target, uint64_t& iterations, uint64_t& notReadable) {
    const DWORD kDeadline = GetTickCount() + 30000; // 30s — generous; the packer is fast
    uint8_t buf[8];
    notReadable = 0;
    iterations = 0;
    while (GetTickCount() < kDeadline) {
        iterations++;
        if (!SafeReadEight(target, buf)) {
            notReadable++;
            Sleep(0); // yield so the packer (other threads) can make progress
            continue;
        }
        bool ok = true;
        for (int i = 0; i < 8; i++) {
            if (buf[i] != kPrologue8[i]) { ok = false; break; }
        }
        if (ok) return true;
        Sleep(0);
    }
    return false;
}

// ─── patch step (called from APC, runs on game thread post-init) ─────────────
// Earlier design patched from the worker thread during early init — this
// caused the process to crash because the cooked pak mount loop calls
// FPakSignatureFile::Load for each .pak; returning success without filling
// the FPakSignatureFile struct (chunk hashes etc.) left zero-initialized
// data that downstream chunk-verification code dereferenced → fatal.
//
// Fix: patch ONLY at APC time, by which point all cooked paks are already
// mounted (we don't want our patch active during their mount). The page is
// long-committed by then so no prologue-wait needed.
static bool ApplyPatchInPlace(uintptr_t modBase) {
    uint8_t* target = reinterpret_cast<uint8_t*>(modBase + kPakSigLoadRva);
    if (!PageReadable(target)) {
        WriteMarker("[apc] PATCH FAIL: page not readable\r\n");
        return false;
    }
    DWORD oldProtect = 0;
    if (!VirtualProtect(target, sizeof(kPatch), PAGE_EXECUTE_READWRITE, &oldProtect)) {
        WriteMarker("[apc] PATCH FAIL: VirtualProtect denied\r\n");
        return false;
    }
    memcpy(target, kPatch, sizeof(kPatch));
    VirtualProtect(target, sizeof(kPatch), oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(kPatch));
    WriteMarker("[apc] PATCH OK: mov al,1;ret applied\r\n");
    return true;
}

// ─── singleton scanner ───────────────────────────────────────────────────────

// Heuristic: does `v` look like a user-mode heap/code pointer? Used to filter
// out small ints that show up at +0x08 of per-pak wrappers vs. real LowerLevel
// pointers in the master singleton.
static bool LooksLikePtr(uintptr_t v) {
    return v >= 0x10000 && v < 0x0001000000000000ULL && (v & 0x7) == 0;
}

// Scan committed MEM_PRIVATE for any qword equal to vtableA. Pick the first
// validated candidate whose [+0x08] ALSO looks like a real pointer (= LowerLevel
// is set). If none qualify, return null and let APC body abort cleanly with
// diagnostics — better than crashing on a bad Mount call.
static void* ScanForSingleton(uintptr_t modBase) {
    const uintptr_t vtableA = modBase + kVtableARva;
    const uintptr_t vtableB = modBase + kVtableBRva;
    {
        char m[160];
        snprintf(m, sizeof(m), "[scan] looking for vtableA=0x%llX vtableB=0x%llX\r\n",
                 (unsigned long long)vtableA, (unsigned long long)vtableB);
        WriteMarker(m);
    }

    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
    const uintptr_t maxAddr = (uintptr_t)si.lpMaximumApplicationAddress;

    int regions = 0, vtaHits = 0, validated = 0, ptrAt8 = 0;
    void* firstValid = nullptr;          // first with vtableB match (may have bad +0x08)
    void* firstValidWithPtr = nullptr;   // first ALSO with +0x08 looking like a ptr
    const int kMaxLogged = 32;

    while (addr < maxAddr) {
        MEMORY_BASIC_INFORMATION mbi = {0};
        if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) != sizeof(mbi)) break;
        const uintptr_t regionEnd = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;

        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
            (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) != 0 &&
            (mbi.Protect & PAGE_GUARD) == 0) {
            regions++;
            const uintptr_t* p = (const uintptr_t*)mbi.BaseAddress;
            const uintptr_t* end = (const uintptr_t*)regionEnd - 3;
            for (; p < end; p++) {
                if (*p != vtableA) continue;
                vtaHits++;
                const uintptr_t v8  = p[1]; // [obj + 0x08]
                const uintptr_t v10 = p[2]; // [obj + 0x10]
                const uintptr_t v18 = p[3]; // [obj + 0x18]
                bool isValid = (v10 == vtableB);
                bool v8IsPtr = LooksLikePtr(v8);
                if (isValid) {
                    validated++;
                    if (!firstValid) firstValid = (void*)p;
                    if (v8IsPtr) {
                        ptrAt8++;
                        if (!firstValidWithPtr) firstValidWithPtr = (void*)p;
                    }
                }
                if (vtaHits <= kMaxLogged) {
                    char m[256];
                    snprintf(m, sizeof(m),
                        "[scan] cand #%d @%p: +0x08=0x%llX +0x10=0x%llX +0x18=0x%llX valid=%d v8ptr=%d\r\n",
                        vtaHits, (void*)p,
                        (unsigned long long)v8,
                        (unsigned long long)v10,
                        (unsigned long long)v18,
                        isValid ? 1 : 0, v8IsPtr ? 1 : 0);
                    WriteMarker(m);
                }
            }
        }
        addr = regionEnd;
    }

    void* picked = firstValidWithPtr ? firstValidWithPtr : firstValid;
    {
        char m[256];
        snprintf(m, sizeof(m),
                 "[scan] done: regions=%d vtableA-hits=%d validated=%d "
                 "ptrAt8=%d picked=%p (with-ptr=%p)\r\n",
                 regions, vtaHits, validated, ptrAt8, picked, firstValidWithPtr);
        WriteMarker(m);
    }
    return picked;
}

// Secondary scan: find every qword in committed memory equal to `target`.
// We use this to find slots that REFERENCE one of our per-pak instances —
// those slots are typically inside the parent singleton's PakFiles[] array,
// giving us a path to the actual mount-everything FPakPlatformFile.
static void ScanForReferences(const void* target, int maxHits) {
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
    const uintptr_t maxAddr = (uintptr_t)si.lpMaximumApplicationAddress;
    uintptr_t wantVal = (uintptr_t)target;

    int hits = 0;
    while (addr < maxAddr && hits < maxHits) {
        MEMORY_BASIC_INFORMATION mbi = {0};
        if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) != sizeof(mbi)) break;
        const uintptr_t regionEnd = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
            (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) != 0 &&
            (mbi.Protect & PAGE_GUARD) == 0) {
            const uintptr_t* p = (const uintptr_t*)mbi.BaseAddress;
            const uintptr_t* end = (const uintptr_t*)regionEnd;
            for (; p < end && hits < maxHits; p++) {
                if (*p == wantVal) {
                    hits++;
                    // p-1 and p-2 give hints about what struct this is inside.
                    uintptr_t prev1 = (p > (const uintptr_t*)mbi.BaseAddress) ? p[-1] : 0;
                    uintptr_t prev2 = ((const uintptr_t*)p - 2 >= (const uintptr_t*)mbi.BaseAddress) ? p[-2] : 0;
                    char m[224];
                    snprintf(m, sizeof(m),
                        "[refs] @%p ← target=%p (prev2=0x%llX prev1=0x%llX)\r\n",
                        (void*)p, target,
                        (unsigned long long)prev2, (unsigned long long)prev1);
                    WriteMarker(m);
                }
            }
        }
        addr = regionEnd;
    }
    char m[96];
    snprintf(m, sizeof(m), "[refs] done: %d hit(s) for %p\r\n", hits, target);
    WriteMarker(m);
}

// ─── APC body: patch + Mount, both on game thread ────────────────────────────

// Module base stored at APC-queue time so APC body can reach it without
// re-resolving (GetModuleHandleA from APC should also work, but this avoids
// any module-handle-validity gotcha).
static uintptr_t g_modBase = 0;

static void NTAPI MountApcCallback(ULONG_PTR /*param*/) {
    if (!g_Mount || !g_singleton || !g_modDir || !g_modBase) {
        WriteMarker("[apc] FIRE FAIL: globals not set\r\n");
        return;
    }
    {
        char m[256];
        snprintf(m, sizeof(m),
                 "[apc] FIRING on game thread tid=%lu: Mount=%p singleton=%p\r\n",
                 GetCurrentThreadId(), (void*)g_Mount, g_singleton);
        WriteMarker(m);
    }

    // Step 1: patch FPakSignatureFile::Load now that cooked-pak mount is done.
    if (!ApplyPatchInPlace(g_modBase)) return;

    // Step 2: revalidate the singleton's first qword — make sure it still has
    // vtable A. If the engine destructed/reconstructed it between scan and APC,
    // we'd crash inside Mount. Better to abort cleanly.
    if (!PageReadable(g_singleton)) {
        WriteMarker("[apc] FAIL: singleton ptr no longer readable\r\n");
        return;
    }
    uintptr_t firstQword = *(const uintptr_t*)g_singleton;
    uintptr_t expectedVtableA = g_modBase + kVtableARva;
    if (firstQword != expectedVtableA) {
        char m[128];
        snprintf(m, sizeof(m),
                 "[apc] FAIL: singleton vtable changed (got 0x%llX want 0x%llX)\r\n",
                 (unsigned long long)firstQword,
                 (unsigned long long)expectedVtableA);
        WriteMarker(m);
        return;
    }

    // Also dump the singleton's first 0x40 bytes — by APC time the engine
    // should have populated +0x08 (LowerLevel etc.). If it's still zero we
    // know our scan picked an uninitialized instance.
    {
        const uintptr_t* p = (const uintptr_t*)g_singleton;
        char m[256];
        snprintf(m, sizeof(m),
                 "[apc] singleton @APC time: +0=0x%llX +8=0x%llX +10=0x%llX "
                 "+18=0x%llX +20=0x%llX +28=0x%llX +30=0x%llX +38=0x%llX\r\n",
                 (unsigned long long)p[0], (unsigned long long)p[1],
                 (unsigned long long)p[2], (unsigned long long)p[3],
                 (unsigned long long)p[4], (unsigned long long)p[5],
                 (unsigned long long)p[6], (unsigned long long)p[7]);
        WriteMarker(m);
    }

    // Step 3: SAFETY CHECK. Mount's impl reads `[this+0x08]` (LowerLevel in
    // vanilla UE) and calls a method on it. If that field isn't a real pointer
    // we'll AV inside Mount and crash the game (observed last run on a per-pak
    // wrapper whose +0x08 was 0x2). Abort cleanly instead.
    uintptr_t v8 = ((const uintptr_t*)g_singleton)[1];
    if (!LooksLikePtr(v8)) {
        char m[256];
        snprintf(m, sizeof(m),
                 "[apc] ABORT: singleton +0x08=0x%llX doesn't look like a pointer.\r\n"
                 "[apc]   This is a per-pak wrapper, not the master singleton.\r\n"
                 "[apc]   Running secondary scan to find slots that reference it...\r\n",
                 (unsigned long long)v8);
        WriteMarker(m);
        ScanForReferences(g_singleton, 30);
        return;
    }

    // Step 4: call Mount. No SEH wrap — clang's __try in our manual-mapped
    // DLL doesn't dispatch reliably. If Mount AVs we'll see it in Loki.log /
    // a crash dump rather than a graceful return.
    WriteMarker("[apc] singleton +0x08 looks like a real ptr, calling Mount...\r\n");
    bool ok = g_Mount(g_singleton, g_modDir);
    {
        char m[64];
        snprintf(m, sizeof(m), "[apc] Mount returned %d\r\n", ok ? 1 : 0);
        WriteMarker(m);
    }
}

// ─── main worker ─────────────────────────────────────────────────────────────

// Wait for GGameThreadId slot to contain a non-zero TID. This is the cleanest
// signal that engine init has started executing on the main thread. Heavy
// diagnostics — the prior run mysteriously dropped between [scan] done and
// the polling loop's outcome, so we want every step visible.
static DWORD WaitForGameTid(uintptr_t modBase, DWORD timeoutMs) {
    uint32_t* gameTidSlot = (uint32_t*)(modBase + kGGameTidRva);
    {
        char m[128];
        snprintf(m, sizeof(m), "[gametid] slot ptr = %p (mod-RVA 0x%llX)\r\n",
                 (void*)gameTidSlot, (unsigned long long)kGGameTidRva);
        WriteMarker(m);
    }

    // Initial VirtualQuery dump so we see what the page state is.
    {
        MEMORY_BASIC_INFORMATION mbi = {0};
        SIZE_T qr = VirtualQuery(gameTidSlot, &mbi, sizeof(mbi));
        char m[256];
        snprintf(m, sizeof(m),
                 "[gametid] VirtualQuery: ret=%llu base=%p regsize=0x%llX "
                 "state=0x%lX protect=0x%lX type=0x%lX\r\n",
                 (unsigned long long)qr,
                 (void*)mbi.BaseAddress, (unsigned long long)mbi.RegionSize,
                 mbi.State, mbi.Protect, mbi.Type);
        WriteMarker(m);
    }

    const DWORD deadline = GetTickCount() + timeoutMs;
    int loop = 0;
    int lastReadable = -1;
    while (GetTickCount() < deadline) {
        loop++;
        bool readable = PageReadable(gameTidSlot);
        if ((int)readable != lastReadable) {
            char m[96];
            snprintf(m, sizeof(m), "[gametid] loop=%d readable=%d\r\n",
                     loop, readable ? 1 : 0);
            WriteMarker(m);
            lastReadable = (int)readable;
        }
        if (readable) {
            // Use memcpy to defeat any compiler reordering of the read vs. the
            // PageReadable check (function calls act as memory barriers anyway,
            // but explicit is safer).
            uint32_t v = 0;
            memcpy(&v, gameTidSlot, sizeof(v));
            if (v != 0) {
                char m[96];
                snprintf(m, sizeof(m), "[gametid] FOUND tid=%lu at loop=%d\r\n",
                         (unsigned long)v, loop);
                WriteMarker(m);
                return v;
            }
        }
        if (loop % 200 == 0) {
            char m[96];
            snprintf(m, sizeof(m), "[gametid] loop=%d still waiting\r\n", loop);
            WriteMarker(m);
        }
        Sleep(10);
    }
    return 0;
}

static DWORD WINAPI Worker(LPVOID) {
    WriteMarker("[0] mount_shim worker started\r\n");

    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) {
        WriteMarker("[0] FAIL: GetModuleHandleA returned NULL\r\n");
        return 1;
    }
    const uintptr_t modBase = (uintptr_t)hExe;
    g_modBase = modBase;
    {
        char m[96]; snprintf(m, sizeof(m), "[0] modBase = 0x%llX\r\n",
                             (unsigned long long)modBase);
        WriteMarker(m);
    }

    // Step 1: wait for game thread to start running engine code (GGameThreadId
    // becomes non-zero). This also ensures cooked-pak mount + early init are
    // well underway, so the FPakPlatformFile singleton is fully constructed
    // by the time we scan for it. DO NOT patch yet — patching during cooked-
    // pak mount caused the prior run to crash (empty FPakSignatureFile struct
    // returned from patched function → downstream chunk-verify AVs).
    WriteMarker("[1] waiting for GGameThreadId to be non-zero (60s)...\r\n");
    DWORD gameTid = WaitForGameTid(modBase, 60000);
    if (gameTid == 0) {
        WriteMarker("[1] FAIL: GGameThreadId stayed 0 for 60s — wrong RVA?\r\n");
        return 2;
    }

    // Step 2: extra grace period — let cooked-pak mount + AR-init complete so
    // the FPakPlatformFile singleton's fields (notably +0x08 LowerLevel) are
    // populated. Cooked mount loop is ~80ms, AR init a couple seconds. 5s is
    // generous.
    WriteMarker("[2] sleeping 5s to let cooked-pak mount + AR-init complete...\r\n");
    Sleep(5000);

    // Step 3: scan for the singleton (now in steady state).
    void* singleton = ScanForSingleton(modBase);
    if (!singleton) {
        WriteMarker("[scan] FAIL: no validated FPakPlatformFile instance found\r\n");
        return 3;
    }
    g_singleton = singleton;
    g_Mount     = (PFN_Mount)(modBase + kMountWrapperRva);
    g_modDir    = kModDirPath;

    // Step 4: Run the secondary scan DIRECTLY from the worker thread (it's
    // pure reads, doesn't need game-thread context). This gives us the
    // structural data we need regardless of whether the APC ever fires —
    // the prior run had the APC queued but never dispatched (UE's main tick
    // uses non-alertable Sleep + the alertable waits in MsgWait/Vivox weren't
    // being hit during the LOGIN screen state).
    {
        // Sanity-check our picked singleton's +0x08 first — if it's not a
        // pointer, log + run the secondary scan to find the master singleton.
        uintptr_t v8 = ((const uintptr_t*)singleton)[1];
        if (!LooksLikePtr(v8)) {
            char m[256];
            snprintf(m, sizeof(m),
                     "[main] picked singleton +0x08=0x%llX isn't a pointer.\r\n"
                     "[main] Running secondary scan to find slots that reference it...\r\n",
                     (unsigned long long)v8);
            WriteMarker(m);
            ScanForReferences(singleton, 30);

            // Also dump the singleton's full first 0x40 bytes for context.
            const uintptr_t* p = (const uintptr_t*)singleton;
            char m2[256];
            snprintf(m2, sizeof(m2),
                     "[main] singleton dump: +0=0x%llX +8=0x%llX +10=0x%llX "
                     "+18=0x%llX +20=0x%llX +28=0x%llX +30=0x%llX +38=0x%llX\r\n",
                     (unsigned long long)p[0], (unsigned long long)p[1],
                     (unsigned long long)p[2], (unsigned long long)p[3],
                     (unsigned long long)p[4], (unsigned long long)p[5],
                     (unsigned long long)p[6], (unsigned long long)p[7]);
            WriteMarker(m2);
        }
    }

    // Step 5: queue the APC on the game thread anyway. If it fires, the APC
    // body will patch sig-load + (if singleton[+0x8] looks like a ptr) call
    // Mount. If it doesn't fire we already have the diagnostic data.
    HANDLE gameThread = OpenThread(THREAD_SET_CONTEXT, FALSE, gameTid);
    if (!gameThread) {
        char m[96];
        snprintf(m, sizeof(m), "[apc] OPEN FAIL: OpenThread(%lu) err=%lu\r\n",
                 gameTid, GetLastError());
        WriteMarker(m);
        return 5;
    }
    DWORD apcOk = QueueUserAPC(MountApcCallback, gameThread, 0);
    CloseHandle(gameThread);
    if (!apcOk) {
        char m[96];
        snprintf(m, sizeof(m), "[apc] QUEUE FAIL: QueueUserAPC err=%lu\r\n",
                 GetLastError());
        WriteMarker(m);
        return 6;
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
        WriteMarker("[+] mount_shim DLL attached, spawning worker\r\n");
        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    }
    return TRUE;
}

// UE4SS-compatible exports so the same DLL can also be loaded via UE4SS Mods
// (not currently used — the shipping exe's import dir is stripped so UE4SS
// itself never loads — but kept for parity with sigbypass-mod/main.cpp).
extern "C" __declspec(dllexport) void* start_mod() {
    return new int(0);
}

extern "C" __declspec(dllexport) void uninstall_mod(void* mod) {
    delete static_cast<int*>(mod);
}
