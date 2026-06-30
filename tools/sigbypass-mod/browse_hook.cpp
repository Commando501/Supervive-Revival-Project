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

// ───────── deferred-log ring ──────────────────────────────────────────
//
// File I/O from the engine thread crashed the game (v2+v3 both lost when the
// handler called CreateFile/WriteFile/FlushFileBuffers). UE's main thread
// likely can't tolerate synchronous disk syscalls inside a Browse call —
// possibly because Browse is part of a critical map-load path that has its
// own I/O state machine, possibly because the watchdog fires on a delayed
// frame. Either way the fix is to keep file I/O off the engine thread.
//
// Pattern: handler appends bytes to a fixed-size in-DLL buffer with an
// atomic position counter. The worker thread polls the buffer every 200ms
// and dumps any new bytes to the marker file. Zero file I/O from the
// handler's thread of execution.
constexpr size_t kLogBufSize = 64 * 1024;     // 64KB — enough for many calls
static char           g_logBuf[kLogBufSize];
static volatile LONG64 g_logHead = 0;          // monotonic-ish byte count

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

// FormatHex8 — turn a 64-bit value into a 16-char hex string. Pure register
// arithmetic, no CRT, no TLS. Output is upper-case hex with no prefix.
static void FormatHex8(uintptr_t val, char* out16) {
    static const char kHex[] = "0123456789ABCDEF";
    for (int i = 15; i >= 0; i--) {
        out16[i] = kHex[val & 0xF];
        val >>= 4;
    }
}

// SafeReadable: VirtualQuery-based bounds check. Returns true if the page
// containing [addr, addr+size) is committed AND has read access. Avoids the
// SEH-from-clang reliability question by checking BEFORE we touch the page.
static bool SafeReadable(const void* addr, size_t size) {
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(addr, &mbi, sizeof(mbi)) == 0) return false;
    if (!(mbi.State & MEM_COMMIT)) return false;
    if (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return false;
    // Crude: trust that the region is contiguous (good enough for stack /
    // heap / data sections).
    uintptr_t start = (uintptr_t)addr;
    uintptr_t end   = start + size;
    return end <= (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
}

// AppendBytes: copy a byte range into g_logBuf via atomic head bump. Returns
// the position we wrote at; returns -1 if the buffer is full.
static LONG64 AppendBytes(const char* src, int n) {
    LONG64 pos = InterlockedExchangeAdd64(&g_logHead, (LONG64)n);
    if (pos + n > (LONG64)sizeof(g_logBuf)) return -1;
    for (int i = 0; i < n; i++) g_logBuf[pos + i] = src[i];
    return pos;
}

// v10: static buffer in our DLL's writable data segment. UE's FString
// destructor may call free() on this pointer later — that'll AV — but the
// engine's NetConnection attempt fires FIRST, and we'll see the LogNet*
// activity in Loki.log before the eventual crash. For probe purposes the
// failure mode IS the win.
static wchar_t g_redirect_host[]   = L"127.0.0.1";
static int32_t g_redirect_host_num = 10;   // 9 chars + null
static int32_t g_redirect_host_max = 10;

extern "C" void browse_hook_handler(uintptr_t rcx, uintptr_t rdx,
                                    uintptr_t r8, uintptr_t r9) {
    // v9: deref FURL at *r8 — layout VERIFIED from v8 hex dump 2026-06-29:
    //   +0x00 FString Protocol  (16B = TCHAR*, int32 Num, int32 Max)
    //   +0x10 FString Host
    //   +0x20 int32 Port (default 7777) + int32 Valid (=1)
    //   +0x28 FString Map         <-- THE URL we want to capture/rewrite
    //   +0x38 FString RedirectURL
    //   +0x48 TArray<FString> Op  (16B header)
    //   +0x58 FString Portal
    //   total: 0x68 = 104 bytes
    //
    // The 8-byte miss in v8 came from assuming each "section" is 16-byte
    // aligned. UE's FURL packs Port+Valid into the 8 bytes following Host
    // (no extra padding), so Map starts at +0x28.
    //
    // Strategy: log the 4 registers, then for each FString-shaped field at
    // 0x00, 0x10, 0x30, 0x40, 0x60 — if its Data pointer is page-readable,
    // copy the wchar_t bytes (up to 200 chars) as low-byte ASCII into the log.
    char line[1024];
    int p = 0;

    auto append = [&](const char* s, size_t n) {
        for (size_t i = 0; i < n; i++) line[p++] = s[i];
    };
    auto append_hex8 = [&](uintptr_t v) {
        FormatHex8(v, line + p); p += 16;
    };

    append("[browse] rcx=", 13);
    append_hex8(rcx);
    append(" rdx=", 5);
    append_hex8(rdx);
    append(" r8=", 4);
    append_hex8(r8);
    append(" r9=", 4);
    append_hex8(r9);
    append("\r\n", 2);

    // Dump first 96 bytes of *r8 (the FURL) as both hex AND low-byte ASCII —
    // we want to spot the URL string regardless of which field carries it.
    if (SafeReadable((const void*)r8, 96)) {
        uint8_t furl[96];
        memcpy(furl, (const void*)r8, sizeof(furl));
        append("[furl] hex:", 11);
        for (int i = 0; i < 96; i++) {
            line[p++] = ' ';
            static const char kHex[] = "0123456789ABCDEF";
            line[p++] = kHex[(furl[i] >> 4) & 0xF];
            line[p++] = kHex[furl[i] & 0xF];
        }
        append("\r\n", 2);

        // Correct FString offsets (verified from v8 hex dump):
        static const int kOffsets[] = {0x00, 0x10, 0x28, 0x38, 0x58};
        static const char* kNames[] = {
            "Protocol", "Host    ", "Map     ", "Redirect", "Portal  "
        };
        for (size_t i = 0; i < sizeof(kOffsets)/sizeof(kOffsets[0]); i++) {
            int off = kOffsets[i];
            // FString = TCHAR* Data (8 bytes), int32 Num (4 bytes), int32 Max (4 bytes)
            wchar_t* data = *(wchar_t**)(furl + off);
            int32_t  num  = *(int32_t*)(furl + off + 8);
            append("[fstring] ", 10);
            append(kNames[i], 8);
            append(" off=0x", 7);
            FormatHex8((uintptr_t)off, line + p); p += 16;
            append(" data=", 6);
            FormatHex8((uintptr_t)data, line + p); p += 16;
            append(" num=", 5);
            FormatHex8((uintptr_t)(uint32_t)num, line + p); p += 16;
            if (data && num > 0 && num < 1024 && SafeReadable(data, num * 2)) {
                append(" str=\"", 6);
                int copy = num > 200 ? 200 : num;
                for (int j = 0; j < copy; j++) {
                    wchar_t c = data[j];
                    if (c == 0) break;
                    line[p++] = (char)(c & 0x7F);
                }
                append("\"", 1);
            }
            append("\r\n", 2);
        }
    } else {
        append("[furl] r8 not safely readable\r\n", 31);
    }

    // ───── v10 REDIRECT ─────────────────────────────────────────────────
    // If Map is a local "/Game/..." URL, mutate FURL.Host in place to make
    // the engine treat this as a remote URL. FURL lives on the caller's
    // stack (r8 pointed at stack memory in v8 capture) — that's RW so the
    // write is safe at the page level. Engine's Browse logic checks
    // Host.IsEmpty() to decide local vs. NetConnection: a non-empty Host
    // flips it to NetConnection mode using Host:Port (Port is already
    // 7777 from the FURL we captured).
    if (SafeReadable((const void*)r8, 0x28 + 16)) {
        wchar_t* map_data  = *(wchar_t**)((const uint8_t*)r8 + 0x28);
        int32_t  map_num   = *(int32_t*)((const uint8_t*)r8 + 0x30);
        bool isLocalGame = false;
        if (map_data && map_num >= 6 && SafeReadable(map_data, 12)) {
            // Match L"/Game/" literally — UTF-16 LE.
            isLocalGame = map_data[0] == L'/' && map_data[1] == L'G' &&
                          map_data[2] == L'a' && map_data[3] == L'm' &&
                          map_data[4] == L'e' && map_data[5] == L'/';
        }
        if (isLocalGame) {
            // FURL.Host @ +0x10: Data (8), Num (4), Max (4)
            *(wchar_t**)((uint8_t*)r8 + 0x10) = g_redirect_host;
            *(int32_t*)((uint8_t*)r8 + 0x18)  = g_redirect_host_num;
            *(int32_t*)((uint8_t*)r8 + 0x1C)  = g_redirect_host_max;
            append("[REWRITE] FURL.Host set to 127.0.0.1; "
                   "engine should switch to NetConnection\r\n", 78);
        } else {
            append("[REWRITE] skipped (Map not local /Game/...)\r\n", 45);
        }
    }
    append("\r\n", 2);

    // Single-writer per slot via the atomic bump — multiple handler calls in
    // flight can't tread on each other's range.
    AppendBytes(line, p);
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

    // Wait for the packer to actually unpack the .text page containing
    // UEngine::Browse before we try to read its prologue. With CREATE_SUSPENDED
    // launch (inject launch) — and even with watch-now timing — GGameThreadId
    // can be set BEFORE the packer commits the page our patch target is in,
    // so a naive memcpy would AV the worker thread and silently kill it.
    //
    // Poll on (a) page committed-and-readable, then (b) first 13 bytes match
    // the known prologue. Either condition false → sleep + retry. 30s timeout.
    static const uint8_t kExpected[kPatchSize] = {
        0x40, 0x55, 0x53, 0x56, 0x57,
        0x41, 0x54, 0x41, 0x55, 0x41, 0x56, 0x41, 0x57
    };
    DWORD deadline = GetTickCount() + 30000;
    int unpackPolls = 0;
    bool unpacked = false;
    while (GetTickCount() < deadline) {
        unpackPolls++;
        MEMORY_BASIC_INFORMATION mbi{};
        if (VirtualQuery((void*)g_browseAddr, &mbi, sizeof(mbi)) == 0 ||
            !(mbi.State & MEM_COMMIT) ||
            (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
            Sleep(5);
            continue;
        }
        // Page committed & readable. Snapshot and compare.
        memcpy(g_origBytes, (const void*)g_browseAddr, kPatchSize);
        if (memcmp(g_origBytes, kExpected, kPatchSize) == 0) {
            unpacked = true;
            break;
        }
        Sleep(5);
    }
    if (!unpacked) {
        Marker("[2] FAIL: prologue never matched (packer / wrong RVA) — refusing to patch\r\n");
        return 3;
    }
    Markerf("[2] page unpacked after %d poll(s); orig 13 bytes match expected\r\n",
            unpackPolls);
    Markerf("[2] orig 13 bytes: %02X %02X %02X %02X %02X %02X %02X "
            "%02X %02X %02X %02X %02X %02X\r\n",
            g_origBytes[ 0], g_origBytes[ 1], g_origBytes[ 2],
            g_origBytes[ 3], g_origBytes[ 4], g_origBytes[ 5],
            g_origBytes[ 6], g_origBytes[ 7], g_origBytes[ 8],
            g_origBytes[ 9], g_origBytes[10], g_origBytes[11],
            g_origBytes[12]);

    // (Prologue-match check is now done during the unpack-poll above.)

    // Build trampoline + hook stub.
    g_trampoline = BuildTrampoline(g_browseAddr);
    if (!g_trampoline) {
        Markerf("[3] FAIL: VirtualAlloc trampoline (err=%lu)\r\n",
                GetLastError());
        return 4;
    }
    Markerf("[3] trampoline @ %p\r\n", (void*)g_trampoline);

    // DIAGNOSTIC v4 (2026-06-29): v3 with kBypassHandler=true PROVED the
    // patch+trampoline mechanics are sound (party menu opened cleanly when
    // we skipped the handler). Re-enable the C handler — now with an empty
    // body in v4 — to test whether the stub→handler call sequence itself
    // is the problem (vs. the file I/O inside the handler).
    g_hookStub = BuildHookStub((void*)&browse_hook_handler, (void*)g_trampoline);
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

    // v5: deferred-log flush loop. Poll g_logHead every 200ms and append any
    // new bytes to the marker file. This runs forever on the worker thread
    // (the only thread that touches the marker file post-install).
    //
    // Also: emit a heartbeat once per ~3s with g_logHead so we can tell from
    // the marker file whether the handler is firing at all (a flat g_logHead
    // for many seconds = handler isn't being called = function we hooked
    // isn't on the path we expected).
    LONG64 lastFlushed   = 0;
    DWORD  lastHeartbeat = GetTickCount();
    while (true) {
        Sleep(200);
        LONG64 head = g_logHead;
        if (head > (LONG64)sizeof(g_logBuf)) head = (LONG64)sizeof(g_logBuf);

        // Flush any new bytes.
        if (head > lastFlushed) {
            HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                                   FILE_SHARE_READ | FILE_SHARE_WRITE,
                                   nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL,
                                   nullptr);
            if (h != INVALID_HANDLE_VALUE) {
                DWORD wrote = 0;
                WriteFile(h, g_logBuf + lastFlushed,
                          (DWORD)(head - lastFlushed), &wrote, nullptr);
                CloseHandle(h);
                lastFlushed = head;
            }
        }

        // Heartbeat every ~3s.
        DWORD now = GetTickCount();
        if (now - lastHeartbeat >= 3000) {
            char hb[64];
            int hbp = 0;
            static const char kHbPrefix[] = "[hb] head=";
            for (size_t i = 0; i < sizeof(kHbPrefix) - 1; i++)
                hb[hbp++] = kHbPrefix[i];
            FormatHex8((uintptr_t)g_logHead, hb + hbp); hbp += 16;
            hb[hbp++] = '\r'; hb[hbp++] = '\n';

            HANDLE h = CreateFileA(kMarkerPath, FILE_APPEND_DATA,
                                   FILE_SHARE_READ | FILE_SHARE_WRITE,
                                   nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL,
                                   nullptr);
            if (h != INVALID_HANDLE_VALUE) {
                DWORD wrote = 0;
                WriteFile(h, hb, (DWORD)hbp, &wrote, nullptr);
                CloseHandle(h);
            }
            lastHeartbeat = now;
        }
    }
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
