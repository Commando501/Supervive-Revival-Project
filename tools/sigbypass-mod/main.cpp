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

static void WriteMarker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &written, nullptr);
    CloseHandle(h);
}

static bool ApplyPatch() {
    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) {
        WriteMarker("FAIL: GetModuleHandleA returned NULL for shipping exe\r\n");
        return false;
    }

    uint8_t* target = reinterpret_cast<uint8_t*>(hExe) + kPakSigLoadRva;

    // Save original bytes for diagnostics + to detect if someone else patched.
    char buf[512];
    snprintf(buf, sizeof(buf),
        "SigBypass:\r\n"
        "  module base : 0x%p\r\n"
        "  patch addr  : 0x%p  (mod-RVA 0x%llX)\r\n"
        "  before bytes: %02X %02X %02X %02X %02X %02X %02X %02X "
                          "%02X %02X %02X %02X %02X %02X %02X %02X\r\n",
        (void*)hExe, (void*)target, (unsigned long long)kPakSigLoadRva,
        target[0], target[1], target[2], target[3],
        target[4], target[5], target[6], target[7],
        target[8], target[9], target[10], target[11],
        target[12], target[13], target[14], target[15]);

    // The expected prologue is "40 55 53 41 54 41 55 41 56 41 57 48 8D 6C 24 F8"
    // (push rbp + push r12-r15 + push rbx + lea rbp,[rsp-8]) — bail if we see
    // something completely unexpected so we don't trash a different function.
    if (target[0] != 0x40 || target[1] != 0x55) {
        strncat_s(buf, sizeof(buf), "  ABORT: prologue mismatch (function moved?)\r\n", _TRUNCATE);
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

// Patch from DllMain so we land as early as possible — UE4SS loads our DLL
// during its mod-init phase, which fires before the engine's pak mount loop.
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID /*reserved*/) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        ApplyPatch();
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
