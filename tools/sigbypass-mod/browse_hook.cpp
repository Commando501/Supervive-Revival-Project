// browse_hook — manual-mapped DLL that hooks UEngine::Browse and logs every
// call's parameters to a marker file.
//
// Why: probes #1-7 of the dedicated-server-stub chapter proved shipping UE5.4
// in this build is hardened against arbitrary network connections from the
// command line. Both -ExecCmds="open <url>" and positional URL forms reach
// the CommandLine string (logged at engine init) but UEngine::Browse is
// never called for our target — the engine silently drops them in favor of
// the configured DefaultMap browse. Hooking Browse externally is the
// substantial-but-feasible bypass: once we intercept the call, we can either
// LOG every Browse (so we understand the natural call surface during a
// normal menu→match flow) or REWRITE specific URLs to redirect travel to
// our stub server.
//
// First-pass scope (this file): LOG only. Verify the hook fires by checking
// the marker file after a normal game launch — we should see one Browse
// for /Game/Loki/Maps/LVL_Login at startup, then another for
// /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent when the menu loads.
//
// Patch design:
//   - UEngine::Browse @ mod-RVA 0x3EC57D0 (function entry, found by xrefstr
//     on ANSI "UEngine::Browse" at +0x8248AC0 → unique LEA at +0x3EC586C →
//     scan back to prologue at +0x3EC57D0).
//   - Prologue starts with 8 push instructions taking exactly 13 bytes:
//        40 55       push rbp     (2)
//        53          push rbx     (1)
//        56          push rsi     (1)
//        57          push rdi     (1)
//        41 54       push r12     (2)
//        41 55       push r13     (2)
//        41 56       push r14     (2)
//        41 57       push r15     (2)
//     13 bytes is a clean instruction-boundary cut — no half-instructions.
//   - Patch = 13 bytes: `mov rax, hookStub ; jmp rax ; nop` (10+2+1 bytes).
//     This is an ABSOLUTE 64-bit jump, so the hook stub can live anywhere in
//     virtual address space (no ±2GB displacement constraint, which a 5-byte
//     E9 disp32 patch would impose).
//   - Trampoline = 25 bytes: replays the 8 push instructions, then
//     `mov rax, browseAddr+13 ; jmp rax` to continue the original function.
//   - Hook stub = ~70 bytes of hand-emitted x64 machine code that:
//        save volatile regs (rcx/rdx/r8/r9) on its own stack
//        call C handler (browse_hook_handler) with the 4 saved regs as args
//        restore the volatile regs
//        jump to trampoline
//
// Build:
//   clang++ -shared -O2 browse_hook.cpp -o browse_hook.dll -lkernel32
//
// Inject (game already running, ELEVATED PowerShell):
//   .\tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe `
//     .\tools\sigbypass-mod\browse_hook.dll
//
// Marker file: docs/browse-hook-marker.txt. Truncated on each shim load.

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

// ───────── constants ─────────────────────────────────────────────────

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\browse-hook-marker.txt";

// Module-relative offsets (stable per build).
constexpr uintptr_t kUEngineBrowseRva = 0x3EC57D0;  // function entry
constexpr uintptr_t kGGameTidRva       = 0x9D49158;  // GGameThreadId (uint32 slot)
constexpr size_t    kPatchSize         = 13;        // 8 pushes worth of bytes

// ───────── marker file logging ────────────────────────────────────────
//
// Use Win32 CreateFile/WriteFile rather than fopen/fprintf so we don't depend
// on CRT static state from the injected DLL's perspective. ATTRIBUTE_NORMAL +
// FILE_APPEND_DATA gives us append-only semantics for log lines.

static void Marker(const char* msg) {
    HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                           FILE_SHARE_READ | FILE_SHARE_WRITE,
                           nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL,
                           nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD wrote = 0;
    WriteFile(h, msg, (DWORD)strlen(msg), &wrote, nullptr);
    CloseHandle(h);
}

static void Markerf(const char* fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(buf, sizeof(buf), _TRUNCATE, fmt, ap);
    va_end(ap);
    Marker(buf);
}

// ───────── globals ───────────────────────────────────────────────────

static uintptr_t g_modBase     = 0;
static uintptr_t g_browseAddr  = 0;       // module_base + kUEngineBrowseRva
static uint8_t   g_origBytes[kPatchSize]; // saved prologue
static uint8_t*  g_trampoline  = nullptr;
static uint8_t*  g_hookStub    = nullptr;

// ───────── C hook handler ─────────────────────────────────────────────
//
// Called by g_hookStub with the original parameters in (rcx, rdx, r8, r9).
// Cdecl-ish through MSVC x64 calling convention — first 4 args go in rcx,
// rdx, r8, r9 which matches what the stub already has loaded.
//
// rdx = FWorldContext*
// r8  = FURL* (passed by address even though declared by value — UE5 calling
//       convention spills any struct larger than 8 bytes to a hidden stack
//       slot and passes its address). FURL contains FString Map (offset ~48
//       on UE5) which we'd dereference to read the requested URL.
// r9  = FString* (Error output)
//
// For probe #8 (log-only) we just print the pointer values plus a few words
// of memory at *r8 so the next iteration knows the FURL layout.

extern "C" void browse_hook_handler(uintptr_t rcx, uintptr_t rdx,
                                    uintptr_t r8, uintptr_t r9) {
    // First-pass safety: NO memory dereferences. Just log the four register
    // values and return. This verifies the hook stub itself is sound (correct
    // calling convention, no shadow-space corruption, marker file writeable
    // from arbitrary engine threads). The next iteration will add the FURL
    // deref once we know the surrounding plumbing works.
    Markerf("[browse] rcx=%p rdx=%p r8=%p r9=%p\r\n",
            (void*)rcx, (void*)rdx, (void*)r8, (void*)r9);
}

// ───────── machine-code emitters ─────────────────────────────────────
//
// We hand-emit the hook stub and trampoline rather than depending on inline
// asm — clang on Windows has limited inline-asm support for x64 anyway. The
// stub is small (~70 bytes) and the encoding is straightforward.

// Build the trampoline: replay the 8 push instructions (13 bytes) then
// abs-jump to (g_browseAddr + 13) to continue executing the original
// function past the patched region.
static uint8_t* BuildTrampoline(uintptr_t browseAddr) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x40,
                                       MEM_COMMIT | MEM_RESERVE,
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

    // mov rax, browseAddr+13  ;  jmp rax  (12 bytes)
    uint64_t back = browseAddr + kPatchSize;
    p[13] = 0x48; p[14] = 0xB8;          // mov rax, imm64
    memcpy(p + 15, &back, 8);
    p[23] = 0xFF; p[24] = 0xE0;          // jmp rax

    return p;
}

// Build the hook stub: save volatile regs, call C handler, restore, jmp
// trampoline.
//
// CRITICAL LAYOUT NOTE — fixed after first-launch crash 2026-06-29:
// The four spill slots for rcx/rdx/r8/r9 must live ABOVE the callee's shadow
// space [rsp+0x00 .. rsp+0x1F]. Win64 ABI lets the callee freely overwrite
// shadow space (it's allocated for the callee's use, even though our caller
// "owns" the bytes), so if we spill INTO the shadow region the C handler can
// (and will) clobber our saved values when it spills its own params. When the
// hook stub reloads after the call, rcx/rdx/r8/r9 are garbage; the trampoline
// jumps into Browse+13 with corrupt args → AV → game crash.
//
//   sub rsp, 0x48              ; 0x20 shadow + 0x20 spill above + 0x8 align
//   mov [rsp+0x20], rcx        ; spill ABOVE callee's shadow space
//   mov [rsp+0x28], rdx
//   mov [rsp+0x30], r8
//   mov [rsp+0x38], r9
//   mov rax, handler           ; call C handler
//   call rax
//   mov rcx, [rsp+0x20]        ; reload originals (untouched by handler)
//   mov rdx, [rsp+0x28]
//   mov r8,  [rsp+0x30]
//   mov r9,  [rsp+0x38]
//   add rsp, 0x48
//   mov rax, trampoline        ; tail-jump to trampoline
//   jmp rax
//
// Alignment: at hook stub entry rsp is 16-aligned-+8 (CALL pushed RA on the
// way in). sub rsp, 0x48 makes rsp 16-aligned (0x48 mod 16 = 8). Inside the
// CALL to handler, rsp is 16-aligned-+8 — standard.
static uint8_t* BuildHookStub(void* handler, void* trampoline) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x100,
                                       MEM_COMMIT | MEM_RESERVE,
                                       PAGE_EXECUTE_READWRITE);
    if (!p) return nullptr;
    uint8_t* w = p;

    // sub rsp, 0x48
    *w++ = 0x48; *w++ = 0x83; *w++ = 0xEC; *w++ = 0x48;

    // mov [rsp+0x20], rcx — spill ABOVE the callee's 0x20-byte shadow space
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;
    // mov [rsp+0x28], rdx
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;
    // mov [rsp+0x30], r8
    *w++ = 0x4C; *w++ = 0x89; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;
    // mov [rsp+0x38], r9
    *w++ = 0x4C; *w++ = 0x89; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;

    // mov rax, handler ; call rax
    *w++ = 0x48; *w++ = 0xB8;
    uint64_t h64 = (uint64_t)handler;
    memcpy(w, &h64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;

    // Reload volatile regs from spill slots (callee couldn't touch these).
    // mov rcx, [rsp+0x20]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;
    // mov rdx, [rsp+0x28]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;
    // mov r8, [rsp+0x30]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;
    // mov r9, [rsp+0x38]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;
    // add rsp, 0x48
    *w++ = 0x48; *w++ = 0x83; *w++ = 0xC4; *w++ = 0x48;

    // mov rax, trampoline ; jmp rax
    *w++ = 0x48; *w++ = 0xB8;
    uint64_t t64 = (uint64_t)trampoline;
    memcpy(w, &t64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xE0;

    return p;
}

// ───────── worker ───────────────────────────────────────────────────

static DWORD WaitForGameTid(uintptr_t modBase, DWORD timeoutMs) {
    uint32_t* gameTidSlot = (uint32_t*)(modBase + kGGameTidRva);
    const DWORD deadline = GetTickCount() + timeoutMs;
    while (GetTickCount() < deadline) {
        // Bail-out cheap if the page isn't readable yet.
        MEMORY_BASIC_INFORMATION mbi{};
        if (VirtualQuery(gameTidSlot, &mbi, sizeof(mbi)) == 0 ||
            !(mbi.State & MEM_COMMIT) ||
            (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
            Sleep(20);
            continue;
        }
        uint32_t v = 0;
        memcpy(&v, gameTidSlot, sizeof(v));
        if (v != 0) return v;
        Sleep(20);
    }
    return 0;
}

static DWORD WINAPI Worker(LPVOID) {
    // Truncate marker file at boot so each shim load gets a clean slate.
    HANDLE h = CreateFileA(kMarkerPath, GENERIC_WRITE, FILE_SHARE_READ,
                          nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL,
                          nullptr);
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);

    Marker("[0] browse_hook worker started\r\n");

    HMODULE hExe = GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if (!hExe) {
        Marker("[0] FAIL: GetModuleHandleA returned NULL\r\n");
        return 1;
    }
    g_modBase = (uintptr_t)hExe;
    g_browseAddr = g_modBase + kUEngineBrowseRva;
    Markerf("[0] modBase=0x%llX  UEngine::Browse=0x%llX\r\n",
            (unsigned long long)g_modBase,
            (unsigned long long)g_browseAddr);

    // Wait for engine init (game thread running).
    Marker("[1] waiting for GGameThreadId (60s)...\r\n");
    DWORD gameTid = WaitForGameTid(g_modBase, 60000);
    if (gameTid == 0) {
        Marker("[1] FAIL: GGameThreadId stayed 0 for 60s — wrong RVA?\r\n");
        return 2;
    }
    Markerf("[1] gameTid=%lu\r\n", gameTid);

    // Snapshot original prologue bytes.
    memcpy(g_origBytes, (const void*)g_browseAddr, kPatchSize);
    Markerf("[2] orig 13 bytes: %02X %02X %02X %02X %02X %02X %02X "
            "%02X %02X %02X %02X %02X %02X\r\n",
            g_origBytes[ 0], g_origBytes[ 1], g_origBytes[ 2],
            g_origBytes[ 3], g_origBytes[ 4], g_origBytes[ 5],
            g_origBytes[ 6], g_origBytes[ 7], g_origBytes[ 8],
            g_origBytes[ 9], g_origBytes[10], g_origBytes[11],
            g_origBytes[12]);

    // Sanity-check: the bytes MUST match the recon expectation
    // (40 55 53 56 57 41 54 41 55 41 56 41 57). If a future game patch
    // shifts the function, our patch would land mid-instruction and
    // crash the engine — refuse to install instead.
    static const uint8_t kExpected[kPatchSize] = {
        0x40, 0x55, 0x53, 0x56, 0x57,
        0x41, 0x54, 0x41, 0x55, 0x41, 0x56, 0x41, 0x57
    };
    if (memcmp(g_origBytes, kExpected, kPatchSize) != 0) {
        Marker("[2] FAIL: prologue bytes don't match recon expectation; "
               "refusing to patch (RVA may need update for this build)\r\n");
        return 3;
    }

    // Build trampoline + hook stub.
    g_trampoline = BuildTrampoline(g_browseAddr);
    if (!g_trampoline) {
        Markerf("[3] FAIL: VirtualAlloc trampoline (err=%lu)\r\n",
                GetLastError());
        return 4;
    }
    Markerf("[3] trampoline @ %p\r\n", (void*)g_trampoline);

    g_hookStub = BuildHookStub((void*)&browse_hook_handler,
                               (void*)g_trampoline);
    if (!g_hookStub) {
        Markerf("[3] FAIL: VirtualAlloc hook stub (err=%lu)\r\n",
                GetLastError());
        return 5;
    }
    Markerf("[3] hook stub @ %p (handler @ %p)\r\n",
            (void*)g_hookStub, (void*)&browse_hook_handler);

    // Build the patch: mov rax, hookStub ; jmp rax ; nop  (13 bytes).
    uint8_t patch[kPatchSize];
    patch[ 0] = 0x48; patch[ 1] = 0xB8;        // mov rax, imm64
    uint64_t stub64 = (uint64_t)g_hookStub;
    memcpy(patch + 2, &stub64, 8);
    patch[10] = 0xFF; patch[11] = 0xE0;        // jmp rax
    patch[12] = 0x90;                          // nop

    // Apply patch via VirtualProtect.
    DWORD oldProt = 0;
    if (!VirtualProtect((void*)g_browseAddr, kPatchSize,
                        PAGE_EXECUTE_READWRITE, &oldProt)) {
        Markerf("[4] FAIL: VirtualProtect (err=%lu)\r\n", GetLastError());
        return 6;
    }
    memcpy((void*)g_browseAddr, patch, kPatchSize);
    DWORD discard = 0;
    VirtualProtect((void*)g_browseAddr, kPatchSize, oldProt, &discard);
    FlushInstructionCache(GetCurrentProcess(),
                          (void*)g_browseAddr, kPatchSize);

    Marker("[4] HOOK INSTALLED\r\n");
    return 0;
}

// ───────── DllMain ───────────────────────────────────────────────────

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        Marker("[+] browse_hook attached, spawning worker\r\n");
        HANDLE th = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (th) CloseHandle(th);
    }
    return TRUE;
}

// UE4SS-compatible exports for parity with sigbypass-mod/main.cpp.
extern "C" __declspec(dllexport) void* start_mod() {
    return new int(0);
}
extern "C" __declspec(dllexport) void uninstall_mod(void* mod) {
    delete static_cast<int*>(mod);
}
