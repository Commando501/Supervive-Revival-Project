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
#include <tlhelp32.h>
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

// v12: whitelist the g_redirect_host buffer in FMallocBinned2::Realloc so the
// engine's destructor of URL.Host (which calls Realloc(_, 0, _) on our static
// pointer) doesn't trip the canary panic. Realloc-zero-size internally calls
// a free-helper that emits the "Attempt to realloc an unrecognized block"
// fatal — patching Realloc entry catches it before the internal route.
//
// Realloc entry disasm (verified 2026-06-30):
//   0xFE25A9  48 83 EC 78      sub rsp, 0x78         (4 bytes)
//   0xFE25AD  48 8B C2         mov rax, rdx           (3 bytes)
//   0xFE25B0  40 53            push rbx               (2 bytes)
//   0xFE25B2  56               push rsi               (1 byte)
//   0xFE25B3  57               push rdi               (1 byte)
//   0xFE25B4  41 56            push r14               (2 bytes)
//   ===== 13 bytes — clean cut boundary =====
//   0xFE25B6  48 83 EC 38      sub rsp, 0x38
// Signature: (rcx=this, rdx=Original, r8=NewSize, r9d=Alignment)
constexpr uintptr_t kReallocRva       = 0xFE25A9;
constexpr size_t    kReallocPatchSize = 13;

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

// v12 Realloc whitelist
static uintptr_t g_reallocAddr            = 0;
static uint8_t   g_reallocOrig[kReallocPatchSize];
static uint8_t*  g_reallocTrampoline      = nullptr;
static uint8_t*  g_reallocHookStub        = nullptr;
static volatile LONG g_reallocInstalled   = 0;  // 1 once patch is live

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
//
// v11 update: the destructor DOES fire (verified session 7 with UDP listener
// — zero packets reached the wire pre-crash). v11 wraps Browse via call+ret
// (PRE mutates URL.Host to point at this buffer, Browse copies it into
// Pending->URL.Host via FString::operator= → FMemory::Malloc → proper
// FMallocBinned2 allocation, POST restores URL.Host to {nullptr,0,0} before
// the caller's frame destructs FURL → destructor is a no-op).
static wchar_t g_redirect_host[]   = L"127.0.0.1";
static int32_t g_redirect_host_num = 10;   // 9 chars + null
static int32_t g_redirect_host_max = 10;

// Forward decl: defined below BuildHookStub.
static void InstallReallocPatchOnce();

// v11: track whether PRE mutated this Browse so POST knows to restore.
// Browse is called only on the game thread (single-threaded for map travel)
// so a single global is safe. If Browse becomes re-entrant (unlikely in
// startup map-travel paths), this would need TLS or stack-locality.
static volatile bool g_pre_mutated = false;

extern "C" void browse_hook_handler(uintptr_t rcx, uintptr_t rdx,
                                    uintptr_t r8, uintptr_t r9) {
    // v12.4 diagnostic: synchronous markers around each phase so we can
    // localize the post-install crash. Loses some perf vs. deferred buffer
    // but every line lands on disk before the next line of C runs.
    Markerf("[PRE] entered r8=0x%llX\r\n", (unsigned long long)r8);
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
            Marker("[PRE] /Game/ map detected, calling Install...\r\n");
            InstallReallocPatchOnce();
            Marker("[PRE] Install returned; about to mutate URL.Host\r\n");

            // FURL.Host @ +0x10: Data (8), Num (4), Max (4)
            *(wchar_t**)((uint8_t*)r8 + 0x10) = g_redirect_host;
            *(int32_t*)((uint8_t*)r8 + 0x18)  = g_redirect_host_num;
            *(int32_t*)((uint8_t*)r8 + 0x1C)  = g_redirect_host_max;
            g_pre_mutated = true;
            Marker("[PRE] URL.Host mutated, appending [REWRITE]\r\n");
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
    Marker("[PRE] AppendBytes done; PRE returning to hook stub\r\n");
}

// v11 POST handler: runs after Browse returns. If PRE mutated URL.Host (i.e.
// this was a /Game/... local browse we redirected), zero out URL.Host so the
// caller's FURL destructor sees an empty FString (Data=nullptr, Num=0, Max=0)
// and the TArray destructor's `if (Data) free(Data)` short-circuits on null.
//
// At this point Browse has already copied URL.Host into Pending->URL.Host via
// FString::operator=, which allocated a proper FMallocBinned2 buffer holding
// "127.0.0.1". That copy lives in Pending and the engine will free it cleanly
// later through its normal allocator path. We're only cleaning up the
// CALLER's stack-resident FURL so its destructor doesn't crash.
extern "C" void browse_hook_post(uintptr_t rcx, uintptr_t rdx,
                                 uintptr_t r8, uintptr_t r9) {
    Markerf("[POST] entered (mutated=%d)\r\n", g_pre_mutated ? 1 : 0);
    if (!g_pre_mutated) return;
    g_pre_mutated = false;
    char line[128];
    int p = 0;
    auto append = [&](const char* s, size_t n) {
        for (size_t i = 0; i < n; i++) line[p++] = s[i];
    };
    if (SafeReadable((const void*)(r8 + 0x10), 16)) {
        // Restore URL.Host to {nullptr, 0, 0} — safe empty FString form.
        *(wchar_t**)((uint8_t*)r8 + 0x10) = nullptr;
        *(int32_t*)((uint8_t*)r8 + 0x18)  = 0;
        *(int32_t*)((uint8_t*)r8 + 0x1C)  = 0;
        append("[RESTORE] FURL.Host zeroed; destructor will short-circuit on null Data\r\n\r\n", 76);
    } else {
        append("[RESTORE] r8+0x10 not readable; restore skipped (LEAK RISK)\r\n\r\n", 64);
    }
    AppendBytes(line, p);
    Marker("[POST] returning\r\n");
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

// v11 WRAP layout — call-trampoline-then-POST, with proper return value
// preservation and alignment. Replaces v10's tail-jump pattern so Browse
// returns into our stub and we can run a POST handler before returning to
// the original caller.
//
// CRITICAL LAYOUT NOTE — carried from v10:
// The four spill slots for rcx/rdx/r8/r9 must live ABOVE the callee's shadow
// space [rsp+0x00 .. rsp+0x1F]. Win64 ABI lets the callee freely overwrite
// shadow space, so spilling into it would let the C handler clobber our
// saved values.
//
// Stack layout after `sub rsp, 0x48`:
//   [rsp+0x40] = saved Browse return value (rax)
//   [rsp+0x38] = spilled r9
//   [rsp+0x30] = spilled r8
//   [rsp+0x28] = spilled rdx
//   [rsp+0x20] = spilled rcx
//   [rsp+0x00 .. rsp+0x1F] = callee shadow space for child handlers
//
// Alignment: entry rsp mod 16 = 8 (post-call). sub rsp, 0x48 → rsp mod 16 = 0.
// Every subsequent `call` pushes 8 bytes; callees enter with rsp mod 16 = 8
// (Win64 standard for callee entry). When `call trampoline` returns, rsp is
// back at our 0x48 frame.
//
// Trampoline-return flow: `call trampoline` pushes RA. Trampoline pushes 8
// regs + jmps to Browse+13. Browse runs, then 8 pops + ret. The ret pops the
// RA we pushed with `call trampoline` and jumps to the instruction after it
// — back inside our stub. ✓
static uint8_t* BuildHookStub(void* preHandler, void* postHandler,
                              void* trampoline) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x200,
                                       MEM_COMMIT | MEM_RESERVE,
                                       PAGE_EXECUTE_READWRITE);
    if (!p) return nullptr;
    uint8_t* w = p;

    // sub rsp, 0x48 — frame: 0x20 shadow + 0x20 spill + 0x8 saved rax (overlap
    //                 with last spill slot is avoided by placing rax at 0x40).
    *w++ = 0x48; *w++ = 0x83; *w++ = 0xEC; *w++ = 0x48;

    // Spill volatile regs at [rsp+0x20 .. rsp+0x38]
    // mov [rsp+0x20], rcx
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;
    // mov [rsp+0x28], rdx
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;
    // mov [rsp+0x30], r8
    *w++ = 0x4C; *w++ = 0x89; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;
    // mov [rsp+0x38], r9
    *w++ = 0x4C; *w++ = 0x89; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;

    // mov rax, preHandler ; call rax
    *w++ = 0x48; *w++ = 0xB8;
    uint64_t pre64 = (uint64_t)preHandler;
    memcpy(w, &pre64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;

    // Reload volatile regs (handler may have used them)
    // mov rcx, [rsp+0x20]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;
    // mov rdx, [rsp+0x28]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;
    // mov r8, [rsp+0x30]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;
    // mov r9, [rsp+0x38]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;

    // mov rax, trampoline ; call rax  (Browse runs and returns here)
    *w++ = 0x48; *w++ = 0xB8;
    uint64_t t64 = (uint64_t)trampoline;
    memcpy(w, &t64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;

    // Save Browse's return value at [rsp+0x40]
    // mov [rsp+0x40], rax
    *w++ = 0x48; *w++ = 0x89; *w++ = 0x44; *w++ = 0x24; *w++ = 0x40;

    // Reload Browse args for POST handler (same shape as PRE — we want
    // POST to see the same FURL pointer it had at entry)
    // mov rcx, [rsp+0x20]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x20;
    // mov rdx, [rsp+0x28]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x54; *w++ = 0x24; *w++ = 0x28;
    // mov r8, [rsp+0x30]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x30;
    // mov r9, [rsp+0x38]
    *w++ = 0x4C; *w++ = 0x8B; *w++ = 0x4C; *w++ = 0x24; *w++ = 0x38;

    // mov rax, postHandler ; call rax
    *w++ = 0x48; *w++ = 0xB8;
    uint64_t post64 = (uint64_t)postHandler;
    memcpy(w, &post64, 8); w += 8;
    *w++ = 0xFF; *w++ = 0xD0;

    // Restore Browse's return value
    // mov rax, [rsp+0x40]
    *w++ = 0x48; *w++ = 0x8B; *w++ = 0x44; *w++ = 0x24; *w++ = 0x40;

    // add rsp, 0x48
    *w++ = 0x48; *w++ = 0x83; *w++ = 0xC4; *w++ = 0x48;

    // ret — return to original Browse caller with Browse's actual return val
    *w++ = 0xC3;

    return p;
}

// v12 Realloc whitelist trampoline: replays Realloc's first 13 bytes, then
// jumps to Realloc+13 to continue the original function.
//
// v12.5: use r10 (volatile scratch) instead of rax for the jump trampoline,
// so we PRESERVE rax = rdx (Original) that the original prologue's
// `mov rax, rdx` at byte 4 just set. The body downstream may read rax
// expecting Original — clobbering it with the jump target would corrupt
// state. r10 is caller-saved/volatile in Win64, so we can use it freely.
static uint8_t* BuildReallocTrampoline(uintptr_t reallocAddr) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x40,
                                       MEM_COMMIT | MEM_RESERVE,
                                       PAGE_EXECUTE_READWRITE);
    if (!p) return nullptr;

    // Original 13 bytes of FMallocBinned2::Realloc prologue
    p[ 0] = 0x48; p[ 1] = 0x83; p[ 2] = 0xEC; p[ 3] = 0x78;  // sub rsp, 0x78
    p[ 4] = 0x48; p[ 5] = 0x8B; p[ 6] = 0xC2;                 // mov rax, rdx
    p[ 7] = 0x40; p[ 8] = 0x53;                                // push rbx
    p[ 9] = 0x56;                                              // push rsi
    p[10] = 0x57;                                              // push rdi
    p[11] = 0x41; p[12] = 0x56;                                // push r14

    // mov r10, reallocAddr+13 ; jmp r10 (10+3 = 13 bytes)
    // REX.W+B = 0x49, mov r10, imm64 = 49 BA + imm64
    // jmp r10 = 41 FF E2
    uint64_t back = reallocAddr + kReallocPatchSize;
    p[13] = 0x49; p[14] = 0xBA;
    memcpy(p + 15, &back, 8);
    p[23] = 0x41; p[24] = 0xFF; p[25] = 0xE2;
    return p;
}

// v12 Realloc whitelist hook stub: compares rdx (Original ptr arg) to the
// address of our g_redirect_host buffer. If equal → return NULL immediately
// (Realloc(g_redirect_host, 0, ...) becomes a no-op from the caller's view —
// engine's TArray destructor sees Data <- NULL and is happy). If not equal →
// tail-jump to trampoline to execute the real Realloc.
//
// Hand-emitted x64:
//   mov rax, &g_redirect_host         ; 10 bytes
//   cmp rdx, rax                       ; 3  bytes
//   jne .normal                        ; 2  bytes (75 disp8)
//   xor eax, eax                       ; 2  bytes (33 C0)
//   ret                                 ; 1  byte (C3)
//  .normal:
//   mov rax, trampoline                ; 10 bytes
//   jmp rax                             ; 2  bytes
//
// No stack frame needed — this is a pure leaf stub; the cmp+ret happens
// before any state is altered, so callee's expectation of "I get rsp+8 on
// entry" is preserved for both branches.
static uint8_t* BuildReallocHookStub(void* trampoline, void* whitelistAddr) {
    uint8_t* p = (uint8_t*)VirtualAlloc(nullptr, 0x40,
                                       MEM_COMMIT | MEM_RESERVE,
                                       PAGE_EXECUTE_READWRITE);
    if (!p) return nullptr;
    uint8_t* w = p;

    // mov rax, whitelistAddr
    *w++ = 0x48; *w++ = 0xB8;
    uint64_t wl = (uint64_t)whitelistAddr;
    memcpy(w, &wl, 8); w += 8;

    // cmp rdx, rax
    *w++ = 0x48; *w++ = 0x39; *w++ = 0xC2;

    // jne .normal (skip 3 bytes — xor eax, eax + ret)
    *w++ = 0x75; *w++ = 0x03;

    // xor eax, eax ; ret (early return with NULL)
    *w++ = 0x33; *w++ = 0xC0;
    *w++ = 0xC3;

    // .normal: mov r10, trampoline ; jmp r10  (preserves rax for trampoline)
    // r10 is volatile in Win64 — free to clobber.
    *w++ = 0x49; *w++ = 0xBA;
    uint64_t t = (uint64_t)trampoline;
    memcpy(w, &t, 8); w += 8;
    *w++ = 0x41; *w++ = 0xFF; *w++ = 0xE2;

    return p;
}

// AnyRipInRange — given a list of suspended thread handles, returns true
// if any thread's RIP is currently inside [lo, hi). Threads whose RIP we
// can't read are assumed safe.
static bool AnyRipInRange(HANDLE* list, int n, uintptr_t lo, uintptr_t hi) {
    for (int i = 0; i < n; i++) {
        CONTEXT ctx;
        memset(&ctx, 0, sizeof(ctx));
        ctx.ContextFlags = CONTEXT_CONTROL;
        if (GetThreadContext(list[i], &ctx)) {
            if (ctx.Rip >= lo && ctx.Rip < hi) {
                Markerf("[5b]   thread %d/%d RIP=0x%llX IN patch range\r\n",
                        i, n, (unsigned long long)ctx.Rip);
                return true;
            }
        }
    }
    return false;
}

// SuspendOtherThreads — enumerate every thread in this process EXCEPT the
// caller, OpenThread+SuspendThread each. Returns the handles in `out` so
// the caller can resume + close. Capacity bounded at 256 threads (SUPERVIVE
// peaks around ~140 from observation).
static int SuspendOtherThreads(HANDLE* out, int cap) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;
    DWORD myPid = GetCurrentProcessId();
    DWORD myTid = GetCurrentThreadId();
    THREADENTRY32 te;
    te.dwSize = sizeof(te);
    int n = 0;
    if (Thread32First(snap, &te)) {
        do {
            if (te.th32OwnerProcessID == myPid &&
                te.th32ThreadID != myTid &&
                n < cap) {
                HANDLE h = OpenThread(THREAD_SUSPEND_RESUME, FALSE, te.th32ThreadID);
                if (h) {
                    if (SuspendThread(h) != (DWORD)-1) {
                        out[n++] = h;
                    } else {
                        CloseHandle(h);
                    }
                }
            }
        } while (Thread32Next(snap, &te));
    }
    CloseHandle(snap);
    return n;
}

static void ResumeOtherThreads(HANDLE* list, int n) {
    for (int i = 0; i < n; i++) {
        ResumeThread(list[i]);
        CloseHandle(list[i]);
    }
}

// InstallReallocPatchOnce — apply the 13-byte patch to FMallocBinned2::Realloc
// at the first call. Idempotent (returns immediately on subsequent calls).
//
// Called from inside browse_hook_handler (PRE) where the engine thread is
// paused in our code. v12.1 deferred install to here (the engine thread
// itself isn't mid-Realloc), but OTHER threads (render/audio/worker pools)
// were still hot in Realloc — leading to corrupted-instruction-stream
// crashes the moment our 13-byte patch landed. v12.2 wraps the patch in
// SuspendThread on every other thread in the process, then resumes after
// FlushInstructionCache. The Win32 OS's context-switch on resume acts as
// the cross-CPU I-cache invalidation barrier.
static void InstallReallocPatchOnce() {
    if (InterlockedCompareExchange(&g_reallocInstalled, 1, 0) != 0) return;
    if (!g_reallocTrampoline || !g_reallocHookStub) {
        Marker("[5b] Realloc patch SKIPPED — trampoline/stub not built\r\n");
        return;
    }
    static const uint8_t kReallocExpected[kReallocPatchSize] = {
        0x48, 0x83, 0xEC, 0x78,             // sub rsp, 0x78
        0x48, 0x8B, 0xC2,                   // mov rax, rdx
        0x40, 0x53,                         // push rbx
        0x56,                               // push rsi
        0x57,                               // push rdi
        0x41, 0x56                          // push r14
    };
    // One last check that the bytes still match what we expect (page was
    // unpacked when we saw it in the worker, but verify under the deferred
    // timing in case packer touches it post-init).
    uint8_t got[kReallocPatchSize];
    memcpy(got, (const void*)g_reallocAddr, kReallocPatchSize);
    if (memcmp(got, kReallocExpected, kReallocPatchSize) != 0) {
        Markerf("[5b] Realloc prologue mismatch — first byte 0x%02X (want 0x48)\r\n",
                got[0]);
        return;
    }
    memcpy(g_reallocOrig, got, kReallocPatchSize);

    uint8_t rpatch[kReallocPatchSize];
    rpatch[ 0] = 0x48; rpatch[ 1] = 0xB8;
    uint64_t rstub = (uint64_t)g_reallocHookStub;
    memcpy(rpatch + 2, &rstub, 8);
    rpatch[10] = 0xFF; rpatch[11] = 0xE0;
    rpatch[12] = 0x90;

    // v12.3: suspend every other thread before the patch write, AND verify
    // none of them has its RIP currently inside the 13-byte patch range
    // (those would crash on resume because they'd be re-executing now-
    // different bytes). If any RIP is in range, resume everyone, wait
    // briefly, and retry. Up to 20 attempts (~200ms total wait).
    HANDLE susp[256];
    int nSusp = 0;
    bool safe = false;
    for (int attempt = 0; attempt < 20; attempt++) {
        nSusp = SuspendOtherThreads(susp, 256);
        if (!AnyRipInRange(susp, nSusp, g_reallocAddr,
                           g_reallocAddr + kReallocPatchSize)) {
            safe = true;
            Markerf("[5b] safe to patch after %d attempt(s); suspended %d thread(s)\r\n",
                    attempt + 1, nSusp);
            break;
        }
        ResumeOtherThreads(susp, nSusp);
        Sleep(10);
    }
    if (!safe) {
        Markerf("[5b] FAIL: thread always in patch range after 20 attempts; ABORTING\r\n");
        return;
    }

    DWORD oldP = 0;
    if (!VirtualProtect((void*)g_reallocAddr, kReallocPatchSize,
                        PAGE_EXECUTE_READWRITE, &oldP)) {
        ResumeOtherThreads(susp, nSusp);
        Markerf("[5b] FAIL VirtualProtect realloc (err=%lu)\r\n", GetLastError());
        return;
    }
    memcpy((void*)g_reallocAddr, rpatch, kReallocPatchSize);
    DWORD d = 0;
    VirtualProtect((void*)g_reallocAddr, kReallocPatchSize, oldP, &d);
    FlushInstructionCache(GetCurrentProcess(),
                          (void*)g_reallocAddr, kReallocPatchSize);

    ResumeOtherThreads(susp, nSusp);
    Marker("[5b] Realloc HOOK INSTALLED (from PRE, suspended+RIP-checked)\r\n");
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

    // v11: hook stub WRAPS Browse — call PRE, call trampoline (Browse runs
    // and rets back), call POST, ret to caller. Replaces v10's tail-jump.
    g_hookStub = BuildHookStub((void*)&browse_hook_handler,
                               (void*)&browse_hook_post,
                               (void*)g_trampoline);
    if (!g_hookStub) {
        Markerf("[3] FAIL: VirtualAlloc hook stub (err=%lu)\r\n",
                GetLastError());
        return 5;
    }
    Markerf("[3] hook stub @ %p (pre @ %p, post @ %p)\r\n",
            (void*)g_hookStub, (void*)&browse_hook_handler,
            (void*)&browse_hook_post);

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

    // v12: pre-build the Realloc trampoline + hook stub on the worker thread
    // (allocation is cheap and race-free). The actual PATCH on
    // FMallocBinned2::Realloc's entry is deferred to the first time PRE
    // handler fires for a /Game/... browse — at that moment the engine
    // thread is paused inside our hook stub (NOT executing Realloc), so the
    // race window for cross-thread instruction-stream corruption is
    // dramatically smaller than installing from the worker during init.
    g_reallocAddr = g_modBase + kReallocRva;
    Markerf("[5] Realloc target @ 0x%llX (RVA 0x%llX); install DEFERRED until first /Game/ browse\r\n",
            (unsigned long long)g_reallocAddr,
            (unsigned long long)kReallocRva);
    g_reallocTrampoline = BuildReallocTrampoline(g_reallocAddr);
    g_reallocHookStub   = BuildReallocHookStub(g_reallocTrampoline,
                                                (void*)&g_redirect_host[0]);
    if (!g_reallocTrampoline || !g_reallocHookStub) {
        Markerf("[5] FAIL: VirtualAlloc realloc trampoline/stub (err=%lu)\r\n",
                GetLastError());
    } else {
        Markerf("[5] Realloc trampoline @ %p, hook stub @ %p (whitelist=%p) — READY\r\n",
                (void*)g_reallocTrampoline, (void*)g_reallocHookStub,
                (void*)&g_redirect_host[0]);
        // v12.6: dump the actual bytes of trampoline + hook stub so we can
        // verify the encoding matches what we intended. Helps localize
        // whether subtle encoding bugs caused the post-PRE crash.
        {
            char hex[200]; int p = 0;
            const uint8_t* t = (const uint8_t*)g_reallocTrampoline;
            for (int i = 0; i < 32; i++) {
                static const char H[] = "0123456789ABCDEF";
                hex[p++] = H[(t[i] >> 4) & 0xF];
                hex[p++] = H[t[i] & 0xF];
                hex[p++] = ' ';
            }
            hex[p] = 0;
            Markerf("[5] trampoline first 32B: %s\r\n", hex);
        }
        {
            char hex[200]; int p = 0;
            const uint8_t* t = (const uint8_t*)g_reallocHookStub;
            for (int i = 0; i < 32; i++) {
                static const char H[] = "0123456789ABCDEF";
                hex[p++] = H[(t[i] >> 4) & 0xF];
                hex[p++] = H[t[i] & 0xF];
                hex[p++] = ' ';
            }
            hex[p] = 0;
            Markerf("[5] hook stub first 32B:  %s\r\n", hex);
        }
    }

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
