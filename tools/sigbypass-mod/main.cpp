// SigBypass — UE4SS C++ mod that patches FPakSignatureFile::Load to return
// success unconditionally, so unsigned mod paks (pakchunk999-WindowsClient_P.pak
// containing our patched AssetRegistry.bin) mount instead of being rejected
// with "Couldn't find pak signature file → Failed to mount, pak is invalid".
//
// The target function was located via tools/usmapdump live-process RE:
//   * L"Couldn't find pak signature file" wide string @ module RVA 0x79E17F0
//   * UE log-record struct (str ptr + file ptr + line + verbosity) @ +0x79E17C8
//   * Unique rip-rel LEA loading that record into rdx @ +0x204836D
//   * Enclosing function entry (FPakSignatureFile::Load) @ +0x2047EE0
//   * Direct callers at +0x2036560 (FPakFile ctor) and +0x2056624 — neither has
//     a conditional gate before the call, so bypass MUST happen inside the
//     function. The simplest patch is to return success on entry.
//
// Patch: 3 bytes at module RVA 0x2047EE0:
//   B0 01      mov al, 1     ; return true
//   C3         ret
// We pad the next 13 bytes with 0x90 (NOP) so the original prologue's overflow
// (push rbp/r12-r15/rbx ...) is overwritten cleanly, even though execution
// never reaches it. Total patch window = 16 bytes.
//
// SIDE-EFFECT RISK: the original function fills out FPakSignatureFile state
// (chunk hashes, encrypted hash). Returning success without populating leaves
// the caller's struct zero-initialized (caller 1 explicitly zero-inits at
// +0x2036544..+0x2036559 before calling). If downstream signature verification
// reads ChunkHashes.Num() and finds 0, it should skip per-chunk verification
// → mount succeeds. If it dereferences anything in the zeroed struct → crash.
// First test: just the patch; if it crashes, escalate to a longer patch that
// also zeroes/populates specific struct fields.
//
// Deployment:
//   <Game>/Loki/Binaries/Win64/ue4ss/Mods/SigBypass/dlls/main.dll
//   plus an entry `SigBypass : 1` in <ue4ss>/Mods/mods.txt
//
// Build (clang++ already used by tools/inject/shim/scan_shim.cpp):
//   clang++ -shared -O2 main.cpp -o main.dll -lkernel32

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <emmintrin.h>   // _mm_pause

// Marker file path — written from DllMain so we can confirm externally (via
// `cat`) that the mod loaded AND the patch landed without relying on the
// game's log output (which only shows runtime errors, not our success).
static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\sigbypass-marker.txt";

// Module-relative offset of FPakSignatureFile::Load entry. Stable per build
// (verified via tools/usmapdump live-process RE this session). If the game
// updates and the function moves, regenerate by:
//   1. wstrings "SUPERVIVE-Win64-Shipping.exe" "Couldn't find pak signature file"
//   2. findptr <in-module hit> → log-record struct address
//   3. xrefstr <log-record-struct addr> → unique LEA RVA
//   4. peek backward to find function entry (40 55 ... push rbp + push r12-r15)
constexpr uintptr_t kPakSigLoadRva = 0x2047EE0;

// Patch bytes: B0 01 C3 (mov al, 1; ret), then NOP padding.
static const uint8_t kPatch[16] = {
    0xB0, 0x01, 0xC3,
    0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90,
};

// Append-mode marker writer. Each call adds a line; the race.ps1 wipes the
// file before launching so we start fresh per run.
static void WriteMarker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &written, nullptr);
    CloseHandle(h);
}

// Check if the page containing `target` is committed and readable. SEH-free
// alternative to wrapping reads in __try (clang's SEH for x64 doesn't reliably
// work in our manual-mapped DLL — observed: __try block hangs the thread when
// an AV fires inside it, no exception handler runs).
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

// SEH-free read of 8 bytes. Returns false if the page isn't readable (per
// VirtualQuery); otherwise reads directly (no exception path).
static bool SafeReadEight(const uint8_t* target, uint8_t out[8]) {
    if (!PageReadable(target)) return false;
    for (int i = 0; i < 8; i++) out[i] = target[i];
    return true;
}

// Wait for the prologue bytes to appear at the target RVA. The packer doesn't
// immediately populate the engine's .text section — when our DllMain runs
// (post manual-map), the packer may still be unpacking, AND the .text page may
// not even be committed yet (= AV on read). We use SEH-protected reads + a
// retry loop that YIELDS THE CPU between iterations (Sleep(0)) so the packer
// thread can make progress; a tight _mm_pause spin starves the packer of
// cycles, defeating the purpose of waiting for it.
// Caps at ~5 seconds of total wall time to avoid hanging if the function moved.
// `notReadable` returns how many iterations failed with AV (page not committed).
static bool WaitForPrologue(uint8_t* target, uint64_t& iterations, uint64_t& notReadable) {
    const DWORD kStart = GetTickCount();
    const DWORD kDeadline = kStart + 5000; // 5 seconds wall time
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
        if (buf[0] == 0x40 && buf[1] == 0x55 && buf[2] == 0x53 &&
            buf[3] == 0x41 && buf[4] == 0x54 && buf[5] == 0x41 &&
            buf[6] == 0x55 && buf[7] == 0x41) {
            return true;
        }
        Sleep(0); // page exists but not patched yet (packer mid-write) — yield
    }
    return false;
}

static bool ApplyPatch() {
    WriteMarker("[1] DllMain entered\r\n");

    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) {
        WriteMarker("[2] FAIL: GetModuleHandleA returned NULL\r\n");
        return false;
    }
    {
        char m[96]; snprintf(m, sizeof(m), "[2] hExe = 0x%p\r\n", (void*) hExe);
        WriteMarker(m);
    }

    uint8_t* target = reinterpret_cast<uint8_t*>(hExe) + kPakSigLoadRva;
    {
        char m[128]; snprintf(m, sizeof(m), "[3] target = 0x%p (mod-RVA 0x%llX)\r\n",
            (void*) target, (unsigned long long) kPakSigLoadRva);
        WriteMarker(m);
    }

    uint8_t initialBytes[16] = {0};
    bool initialOk = PageReadable(target);
    if (initialOk) {
        for (int i = 0; i < 16; i++) initialBytes[i] = target[i];
    }
    {
        char m[256];
        if (initialOk) {
            snprintf(m, sizeof(m),
                "[4] initial-read OK: %02X %02X %02X %02X %02X %02X %02X %02X "
                                     "%02X %02X %02X %02X %02X %02X %02X %02X\r\n",
                initialBytes[0], initialBytes[1], initialBytes[2], initialBytes[3],
                initialBytes[4], initialBytes[5], initialBytes[6], initialBytes[7],
                initialBytes[8], initialBytes[9], initialBytes[10], initialBytes[11],
                initialBytes[12], initialBytes[13], initialBytes[14], initialBytes[15]);
        } else {
            snprintf(m, sizeof(m), "[4] initial: page not committed/readable yet (spin will wait)\r\n");
        }
        WriteMarker(m);
    }

    WriteMarker("[5] spinning for prologue...\r\n");
    uint64_t spinIters = 0, avCount = 0;
    DWORD t0 = GetTickCount();
    bool gotPrologue = WaitForPrologue(target, spinIters, avCount);
    DWORD elapsedMs = GetTickCount() - t0;
    char midmark[128];
    snprintf(midmark, sizeof(midmark), "SigBypass: spin done after %u ms (got=%d iters=%llu avs=%llu)\r\n",
             (unsigned) elapsedMs, gotPrologue ? 1 : 0,
             (unsigned long long) spinIters, (unsigned long long) avCount);
    WriteMarker(midmark);

    char buf[1024];
    snprintf(buf, sizeof(buf),
        "SigBypass:\r\n"
        "  module base : 0x%p\r\n"
        "  patch addr  : 0x%p  (mod-RVA 0x%llX)\r\n"
        "  initial bytes (at DllMain entry): "
            "%02X %02X %02X %02X %02X %02X %02X %02X "
            "%02X %02X %02X %02X %02X %02X %02X %02X\r\n"
        "  prologue wait: %s after %llu spin iter(s), %llu AV (uncommitted)\r\n",
        (void*)hExe, (void*)target, (unsigned long long)kPakSigLoadRva,
        initialBytes[0], initialBytes[1], initialBytes[2], initialBytes[3],
        initialBytes[4], initialBytes[5], initialBytes[6], initialBytes[7],
        initialBytes[8], initialBytes[9], initialBytes[10], initialBytes[11],
        initialBytes[12], initialBytes[13], initialBytes[14], initialBytes[15],
        gotPrologue ? "FOUND" : "TIMEOUT (5s)",
        (unsigned long long) spinIters, (unsigned long long) avCount);

    if (!gotPrologue) {
        strncat_s(buf, sizeof(buf), "  ABORT: prologue never appeared\r\n", _TRUNCATE);
        WriteMarker(buf);
        return false;
    }

    DWORD oldProtect = 0;
    if (!VirtualProtect(target, sizeof(kPatch), PAGE_EXECUTE_READWRITE, &oldProtect)) {
        strncat_s(buf, sizeof(buf), "  FAIL: VirtualProtect RWX denied\r\n", _TRUNCATE);
        WriteMarker(buf);
        return false;
    }
    memcpy(target, kPatch, sizeof(kPatch));
    VirtualProtect(target, sizeof(kPatch), oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(kPatch));

    char tail[256];
    snprintf(tail, sizeof(tail),
        "  after bytes : %02X %02X %02X %02X %02X %02X %02X %02X "
                          "%02X %02X %02X %02X %02X %02X %02X %02X\r\n"
        "  status      : OK (mov al,1; ret + NOP pad applied)\r\n",
        target[0], target[1], target[2], target[3],
        target[4], target[5], target[6], target[7],
        target[8], target[9], target[10], target[11],
        target[12], target[13], target[14], target[15]);
    strncat_s(buf, sizeof(buf), tail, _TRUNCATE);
    WriteMarker(buf);
    return true;
}

// Background worker that polls for the prologue and patches when it appears.
// Spawned from DllMain so DllMain can return immediately — this is critical for
// the CREATE_SUSPENDED-then-inject flow: DllMain blocks the inject_mmap caller,
// and the caller needs to ResumeThread(main) after inject completes. If DllMain
// spun in-line, the packer (which runs on main) would be paused forever and
// the prologue would never appear → deadlock.
static DWORD WINAPI PatchWorker(LPVOID) {
    ApplyPatch();
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID /*reserved*/) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        WriteMarker("[0] DllMain spawning patch worker\r\n");
        HANDLE th = CreateThread(nullptr, 0, PatchWorker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    }
    return TRUE;
}

// UE4SS C++ mod ABI: start_mod is called after DllMain succeeds. We return a
// non-null heap object so uninstall_mod can free it without crashing UE4SS.
// We don't subclass CppUserModBase (would require pulling in UE4SS headers);
// the void* return is treated as opaque by UE4SS as long as uninstall_mod
// handles it. EventViewerMod's exports were verified to be just these two
// symbols, no virtual table required at the ABI boundary.
extern "C" __declspec(dllexport) void* start_mod() {
    return new int(0);
}

extern "C" __declspec(dllexport) void uninstall_mod(void* mod) {
    delete static_cast<int*>(mod);
}
