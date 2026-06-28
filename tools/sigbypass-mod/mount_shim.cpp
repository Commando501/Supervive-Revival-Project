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

// ─── patch step ──────────────────────────────────────────────────────────────

static bool ApplyPatch(uintptr_t modBase) {
    uint8_t* target = reinterpret_cast<uint8_t*>(modBase + kPakSigLoadRva);
    WriteMarker("[patch] waiting for FPakSignatureFile::Load prologue...\r\n");
    uint64_t iters = 0, avs = 0;
    bool got = WaitForPrologue(target, iters, avs);
    {
        char m[160];
        snprintf(m, sizeof(m), "[patch] wait done: got=%d iters=%llu avs=%llu\r\n",
                 got ? 1 : 0, (unsigned long long)iters, (unsigned long long)avs);
        WriteMarker(m);
    }
    if (!got) return false;

    DWORD oldProtect = 0;
    if (!VirtualProtect(target, sizeof(kPatch), PAGE_EXECUTE_READWRITE, &oldProtect)) {
        WriteMarker("[patch] FAIL: VirtualProtect denied\r\n");
        return false;
    }
    memcpy(target, kPatch, sizeof(kPatch));
    VirtualProtect(target, sizeof(kPatch), oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(kPatch));
    WriteMarker("[patch] OK: mov al,1;ret applied at FPakSignatureFile::Load entry\r\n");
    return true;
}

// ─── singleton scanner ───────────────────────────────────────────────────────

// Scan committed MEM_PRIVATE for any qword equal to vtableA. For each hit log the
// surrounding bytes so we can pick the "right" instance if the first attempt fails.
// Returns the first hit whose [+0x10] == vtableB (= validated FPakPlatformFile).
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

    int regions = 0, vtaHits = 0, validated = 0;
    void* firstValid = nullptr;
    const int kMaxLogged = 16; // log up to 16 candidates so all 10 expected ones fit

    while (addr < maxAddr) {
        MEMORY_BASIC_INFORMATION mbi = {0};
        if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) != sizeof(mbi)) break;
        const uintptr_t regionEnd = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;

        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
            (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) != 0 &&
            (mbi.Protect & PAGE_GUARD) == 0) {
            regions++;
            const uintptr_t* p = (const uintptr_t*)mbi.BaseAddress;
            // Stride one qword at a time. -3 to leave headroom for the +0x10/+0x18 reads.
            const uintptr_t* end = (const uintptr_t*)regionEnd - 3;
            for (; p < end; p++) {
                if (*p != vtableA) continue;
                vtaHits++;
                const uintptr_t v8  = p[1]; // [obj + 0x08]
                const uintptr_t v10 = p[2]; // [obj + 0x10]
                const uintptr_t v18 = p[3]; // [obj + 0x18]
                bool isValid = (v10 == vtableB);
                if (isValid) {
                    validated++;
                    if (!firstValid) firstValid = (void*)p;
                }
                if (vtaHits <= kMaxLogged) {
                    char m[224];
                    snprintf(m, sizeof(m),
                        "[scan] cand #%d @%p: +0x08=0x%llX +0x10=0x%llX +0x18=0x%llX valid=%d\r\n",
                        vtaHits, (void*)p,
                        (unsigned long long)v8,
                        (unsigned long long)v10,
                        (unsigned long long)v18,
                        isValid ? 1 : 0);
                    WriteMarker(m);
                }
            }
        }
        addr = regionEnd;
    }

    {
        char m[160];
        snprintf(m, sizeof(m),
                 "[scan] done: regions=%d vtableA-hits=%d validated=%d picked=%p\r\n",
                 regions, vtaHits, validated, firstValid);
        WriteMarker(m);
    }
    return firstValid;
}

// ─── APC body that runs Mount on the game thread ─────────────────────────────

static void NTAPI MountApcCallback(ULONG_PTR /*param*/) {
    if (!g_Mount || !g_singleton || !g_modDir) {
        WriteMarker("[apc] FAIL: globals not set\r\n");
        return;
    }
    {
        char m[224];
        snprintf(m, sizeof(m),
                 "[apc] FIRING on game thread: Mount=%p singleton=%p\r\n"
                 "[apc]   modDir = (see kModDirPath in shim source)\r\n",
                 (void*)g_Mount, g_singleton);
        WriteMarker(m);
    }
    // No SEH wrap — clang's __try on x64 manual-mapped DLL doesn't dispatch
    // reliably; an AV here will crash the game thread and we'll see the
    // failure mode in dr-watson / Loki.log rather than a graceful return.
    bool ok = g_Mount(g_singleton, g_modDir);
    {
        char m[64];
        snprintf(m, sizeof(m), "[apc] Mount returned %d\r\n", ok ? 1 : 0);
        WriteMarker(m);
    }
}

// ─── main worker ─────────────────────────────────────────────────────────────

static DWORD WINAPI Worker(LPVOID) {
    WriteMarker("[0] mount_shim worker started\r\n");

    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) {
        WriteMarker("[0] FAIL: GetModuleHandleA returned NULL\r\n");
        return 1;
    }
    const uintptr_t modBase = (uintptr_t)hExe;
    {
        char m[96]; snprintf(m, sizeof(m), "[0] modBase = 0x%llX\r\n",
                             (unsigned long long)modBase);
        WriteMarker(m);
    }

    // Step 1: patch FPakSignatureFile::Load.
    if (!ApplyPatch(modBase)) return 2;

    // Step 2: find a singleton.
    void* singleton = ScanForSingleton(modBase);
    if (!singleton) {
        WriteMarker("[scan] FAIL: no validated FPakPlatformFile instance found\r\n");
        return 3;
    }
    g_singleton = singleton;
    g_Mount     = (PFN_Mount)(modBase + kMountWrapperRva);
    g_modDir    = kModDirPath;

    // Step 3: read GGameThreadId. Engine sets it early; if we're injected
    // pre-Resume it might still be zero, so poll briefly.
    uint32_t* gameTidSlot = (uint32_t*)(modBase + kGGameTidRva);
    DWORD gameTid = 0;
    {
        const DWORD deadline = GetTickCount() + 10000;
        while (GetTickCount() < deadline) {
            if (PageReadable(gameTidSlot)) {
                uint32_t v = *gameTidSlot;
                if (v != 0) { gameTid = v; break; }
            }
            Sleep(10);
        }
    }
    if (gameTid == 0) {
        WriteMarker("[apc] FAIL: GGameThreadId still 0 after 10s\r\n");
        return 4;
    }
    {
        char m[96]; snprintf(m, sizeof(m), "[apc] GGameThreadId = %lu (0x%lX)\r\n",
                             gameTid, gameTid);
        WriteMarker(m);
    }

    // Step 4: queue the APC.
    HANDLE gameThread = OpenThread(THREAD_SET_CONTEXT, FALSE, gameTid);
    if (!gameThread) {
        char m[96];
        snprintf(m, sizeof(m), "[apc] FAIL: OpenThread(%lu) err=%lu\r\n",
                 gameTid, GetLastError());
        WriteMarker(m);
        return 5;
    }
    DWORD apcOk = QueueUserAPC(MountApcCallback, gameThread, 0);
    CloseHandle(gameThread);
    if (!apcOk) {
        char m[96];
        snprintf(m, sizeof(m), "[apc] FAIL: QueueUserAPC err=%lu\r\n",
                 GetLastError());
        WriteMarker(m);
        return 6;
    }
    WriteMarker("[apc] APC queued; will fire on next alertable wait\r\n");
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
