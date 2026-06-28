// scan_shim.dll — native shim that triggers UAssetManager::ScanPrimaryAssetTypesFromConfig
// ON THE GAME (MAIN) THREAD via thread-hijack.
//
// WHY: SUPERVIVE's custom LokiAssetManager registers primary assets ONLY from the
// content-service manifest's named maps and never runs UE's config-driven directory scan,
// so baked primary assets (Mission, MissionPool, Hero, StoreOffer...) never register —
// leaving the Missions modal / hunters grid / store empty. The data IS in the cooked
// AssetRegistry; the scan just never fires. This shim calls that scan once.
//
// A first version called the scan from the injected thread → it crashed (exit 0xDEAD):
// the function asserts check(IsInGameThread()) / uses game-thread-local state. So we run it
// on the process's MAIN thread (UE's game thread) by hijacking: suspend it, point it at the
// scan with a fresh stack that returns into a spin-stub, wait, then restore its full context.
//
// Stable module RVAs (only ASLR base moves), recovered by read-only RE (tools/usmapdump):
//   LokiAssetManager vtable                            = base + 0x888CB78
//   UAssetManager::ScanPrimaryAssetTypesFromConfig     = base + 0x34D0807  (void __fastcall(this))
//
// No C++ exceptions (packer breaks C++ EH in manually-mapped code). Manual-map:
//   inject mmap "SUPERVIVE-Win64-Shipping.exe" scan_shim.dll
// Build:
//   clang++ -shared -O2 scan_shim.cpp -o scan_shim.dll -lkernel32 -luser32
// Marker (proof): tools/inject/shim/scan_shim_result.txt

#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <cstdint>

static const char* kMarker =
    "G:\\git\\Supervive Revival Project\\tools\\inject\\shim\\scan_shim_result.txt";

static const uintptr_t kVtableRVA = 0x888CB78;
static const uintptr_t kScanRVA   = 0x34D0807;

typedef void(__fastcall* ScanFn)(void* thisptr);

static volatile LONG g_done = 0;

// Spin-stub: the hijacked game thread "returns" here after scan(). It flags completion and
// spins; the shim then suspends it and restores its original context.
static void StubReturn()
{
    g_done = 1;
    for (;;) { YieldProcessor(); }
}

static int hex64(char* dst, uintptr_t v)
{
    static const char* H = "0123456789ABCDEF";
    dst[0] = '0'; dst[1] = 'x';
    for (int i = 0; i < 16; ++i)
        dst[2 + i] = H[(v >> ((15 - i) * 4)) & 0xF];
    return 18;
}

// Appends a line "<tag> a=<hex> b=<hex> c=<hex>\r\n" to the marker (append mode).
static void Log(const char* tag, uintptr_t a, uintptr_t b, uintptr_t c)
{
    HANDLE h = CreateFileA(kMarker, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    SetFilePointer(h, 0, nullptr, FILE_END);
    char buf[256];
    int n = 0;
    for (const char* p = tag; *p; ++p) buf[n++] = *p;
    buf[n++] = ' '; buf[n++] = 'a'; buf[n++] = '='; n += hex64(buf + n, a);
    buf[n++] = ' '; buf[n++] = 'b'; buf[n++] = '='; n += hex64(buf + n, b);
    buf[n++] = ' '; buf[n++] = 'c'; buf[n++] = '='; n += hex64(buf + n, c);
    buf[n++] = '\r'; buf[n++] = '\n';
    DWORD w = 0;
    WriteFile(h, buf, (DWORD)n, &w, nullptr);
    CloseHandle(h);
}

static bool ReadableProt(DWORD p)
{
    if (p & (PAGE_GUARD | PAGE_NOACCESS)) return false;
    return (p & (PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                 PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)) != 0;
}

// FindSingleton: locate the live LokiAssetManager (skip the CDO).
static uintptr_t FindSingleton(uintptr_t vtable)
{
    uintptr_t cdoClass = 0, singleton = 0;
    SYSTEM_INFO si; GetSystemInfo(&si);
    for (int pass = 0; pass < 2 && (pass == 0 || cdoClass); ++pass)
    {
        uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
        uintptr_t maxA = (uintptr_t)si.lpMaximumApplicationAddress;
        while (addr < maxA)
        {
            MEMORY_BASIC_INFORMATION mbi;
            if (VirtualQuery((LPCVOID)addr, &mbi, sizeof(mbi)) == 0) break;
            uintptr_t rbase = (uintptr_t)mbi.BaseAddress;
            uintptr_t rsize = (uintptr_t)mbi.RegionSize;
            uintptr_t next = rbase + rsize;
            if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE && ReadableProt(mbi.Protect))
            {
                uintptr_t* p = (uintptr_t*)rbase;
                uintptr_t count = rsize / sizeof(uintptr_t);
                for (uintptr_t i = 0; i + 4 < count; ++i)
                {
                    if (p[i] != vtable) continue;
                    uintptr_t obj = rbase + i * sizeof(uintptr_t);
                    uint32_t flags = *(uint32_t*)(obj + 0x0C);
                    uintptr_t cls = *(uintptr_t*)(obj + 0x18);
                    if (pass == 0) { if (flags & 0x10) cdoClass = cls; }
                    else { if (!(flags & 0x10) && cls == cdoClass) { singleton = obj; break; } }
                }
            }
            if (next <= addr) break;
            addr = next;
            if (singleton) break;
        }
    }
    return singleton;
}

// FindMainThread: UE runs the game loop on the process's initial thread = the earliest
// created thread, AND that thread's TID matches GGameThreadId. Confirmed by RE
// (tools/usmapdump findgametid: top hit RVA 0x9D49158 holds the ord=0 thread TID).
// Returns its TID (excluding our own thread), or 0.
static DWORD FindMainThread()
{
    DWORD myPid = GetCurrentProcessId();
    DWORD myTid = GetCurrentThreadId();
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;
    THREADENTRY32 te; te.dwSize = sizeof(te);
    DWORD best = 0;
    ULONGLONG bestCreate = ~0ull;
    if (Thread32First(snap, &te))
    {
        do {
            if (te.th32OwnerProcessID != myPid) continue;
            if (te.th32ThreadID == myTid) continue;
            HANDLE th = OpenThread(THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID);
            if (!th) continue;
            FILETIME c, e, k, u;
            if (GetThreadTimes(th, &c, &e, &k, &u))
            {
                ULONGLONG ct = ((ULONGLONG)c.dwHighDateTime << 32) | c.dwLowDateTime;
                if (ct < bestCreate) { bestCreate = ct; best = te.th32ThreadID; }
            }
            CloseHandle(th);
        } while (Thread32Next(snap, &te));
    }
    CloseHandle(snap);
    return best;
}

// VerifyGameThread reads GGameThreadId from its module slot (RVA 0x9D49158, recovered
// by tools/usmapdump findgametid: the uint32 module-data slot most-referenced by
// code that compares to a thread id; currently holds the ord=0 thread TID). Returns
// the value at that slot or 0 if invalid.
static const uintptr_t kGGameThreadIdRVA = 0x9D49158;
static DWORD GetGGameThreadId(uintptr_t base)
{
    return *(volatile DWORD*)(base + kGGameThreadIdRVA);
}

// ThreadBasicInformation layout (NT internal). Just need TebBaseAddress.
struct THREAD_BASIC_INFORMATION_LITE
{
    long      ExitStatus;
    void*     TebBaseAddress;
    uintptr_t ClientId_UniqueProcess;
    uintptr_t ClientId_UniqueThread;
    uintptr_t AffinityMask;
    long      Priority;
    long      BasePriority;
};

typedef long (NTAPI *PFN_NtQueryInformationThread)(
    HANDLE, int, void*, unsigned long, unsigned long*);

static void* GetThreadTeb(HANDLE th)
{
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) return nullptr;
    auto pNt = (PFN_NtQueryInformationThread)GetProcAddress(ntdll, "NtQueryInformationThread");
    if (!pNt) return nullptr;
    THREAD_BASIC_INFORMATION_LITE tbi = {};
    unsigned long ret = 0;
    if (pNt(th, /*ThreadBasicInformation*/0, &tbi, sizeof(tbi), &ret) != 0) return nullptr;
    return tbi.TebBaseAddress;
}

// DoScan strategy v3: call scan ON OUR OWN INJECTED THREAD, but temporarily IMPERSONATE
// the game thread by patching the GGameThreadId global to OUR TID for the duration of
// the call. This avoids:
//   - hijacking a suspended thread in an unknown state (could hold locks → deadlock)
//   - TEB/stack-bounds gymnastics (we run on a normal Win32 thread with a real stack)
// Any check(IsInGameThread()) inside scan() compares GetCurrentThreadId() to the patched
// global and passes. After scan returns we restore the original GGameThreadId.
//
// Risk: any OTHER thread (renderer, async loader) that calls IsInGameThread during the
// scan would see the wrong value. Mitigation: scan runs in milliseconds in a quiet menu
// state, and the global is restored under a memory fence.
static void DoScan()
{
    uintptr_t base = (uintptr_t)GetModuleHandleW(nullptr);
    uintptr_t vtable = base + kVtableRVA;
    ScanFn scan = (ScanFn)(base + kScanRVA);

    uintptr_t singleton = FindSingleton(vtable);
    if (!singleton) { Log("FAIL-no-singleton", base, vtable, 0); return; }

    // Diagnostic: confirm the singleton state we're about to call into.
    //   [+0]    : vtable (must == base + 0x888CB78)
    //   [+0x0C] : ObjectFlags (must NOT have 0x10 RF_ClassDefaultObject)
    //   [+0x18] : ClassPrivate (UClass*)
    //   [+0x4d0]: cached AssetRegistry pointer (scan reads it; if 0 it calls into FModuleManager)
    uintptr_t vt0    = *(uintptr_t*)(singleton + 0x00);
    uint32_t  flags  = *(uint32_t*)(singleton + 0x0C);
    uintptr_t cls    = *(uintptr_t*)(singleton + 0x18);
    uintptr_t arCache = *(uintptr_t*)(singleton + 0x4d0);
    Log("S-vt-flags-cls", vt0, (uintptr_t)flags, cls);
    Log("S-arCache+0x4d0", arCache, base, vtable);
    // If AssetRegistry IS cached, also peek [arCache+0x60]/[arCache+0x68]: array start/count.
    if (arCache) {
        uintptr_t arr   = *(uintptr_t*)(arCache + 0x60);
        int32_t   count = *(int32_t*)(arCache + 0x68);
        Log("S-ar.arr-count", arr, (uintptr_t)(uint32_t)count, 0);
        uintptr_t arr70   = *(uintptr_t*)(arCache + 0x70);
        int32_t   count78 = *(int32_t*)(arCache + 0x78);
        Log("S-ar.arr70-78", arr70, (uintptr_t)(uint32_t)count78, 0);
    }
    // Read the vtable slot at offset 0x508 — that's the `call [vtbl+0x508]` in the empty
    // path at scan rva 0x34D0A19. If that fn ptr is corrupted, that's our AV.
    {
        uintptr_t fn508 = *(uintptr_t*)(vt0 + 0x508);
        Log("S-vt[0x508]", fn508, vt0, vt0 + 0x508);
    }

    DWORD origGGameTid = GetGGameThreadId(base);
    DWORD myTid = GetCurrentThreadId();
    DWORD enumTid = FindMainThread();
    // Record context (helpful if anything goes wrong): a=origGGameTid, b=enum-ord0, c=ours.
    Log("CTX", (uintptr_t)origGGameTid, (uintptr_t)enumTid, (uintptr_t)myTid);

    // Patch GGameThreadId to our TID so the primary IsInGameThread() check passes.
    // Confirmed by experiment: WITHOUT this patch, scan __fastfails immediately (the
    // primary IsInGameThread check fires). The slot lives in module .data (may be RO).
    volatile DWORD* slot = (volatile DWORD*)(base + kGGameThreadIdRVA);
    DWORD oldProt = 0;
    if (!VirtualProtect((LPVOID)slot, sizeof(DWORD), PAGE_READWRITE, &oldProt)) {
        Log("FAIL-vprotect", base, singleton, (uintptr_t)slot);
        return;
    }
    *slot = myTid;
    MemoryBarrier();

    Log("IMPERSONATE", base, singleton, (uintptr_t)myTid);

    int nPatched = 0; uintptr_t patchedSlots[1] = {0};

    // STRATEGY: schedule the scan to run on the GAME THREAD via QueueUserAPC. APCs run
    // safely when the target thread enters an alertable wait — exactly the safe execution
    // context we need. UE's game thread regularly enters WaitForSingleObjectEx and
    // SleepEx (alertable). This avoids hijacking (unsafe in arbitrary state) and avoids
    // running scan on our own thread (which traps on thread-affinity / TLS / cookie).
    // Setup: open the game thread, queue an APC that calls scan(this), wait for it
    // to complete (the APC sets a done flag), then return.
    DWORD ggameTid = origGGameTid;
    HANDLE gameTh = OpenThread(THREAD_SET_CONTEXT, FALSE, ggameTid);
    if (!gameTh) {
        Log("FAIL-openGameTh", base, singleton, (uintptr_t)ggameTid);
        // restore patch
        MemoryBarrier(); *slot = origGGameTid;
        DWORD rp; VirtualProtect((LPVOID)slot, sizeof(DWORD), oldProt, &rp);
        return;
    }
    Log("APC-OPEN-GT", (uintptr_t)gameTh, (uintptr_t)ggameTid, 0);

    // We need a small APC stub that calls scan((void*)singleton) — APCs receive the user
    // data in RCX (1st arg). We can pass (uintptr_t)singleton as that arg directly and
    // use scan itself as the APC routine — but scan takes (void* this), and Windows passes
    // (ULONG_PTR data) — same calling convention on x64. So:
    //   QueueUserAPC((PAPCFUNC)scan, gameTh, (ULONG_PTR)singleton);
    // The game thread, on its next alertable wait, will call scan(singleton).
    DWORD r = QueueUserAPC((PAPCFUNC)scan, gameTh, (ULONG_PTR)singleton);
    Log("APC-QUEUED", (uintptr_t)r, (uintptr_t)scan, (uintptr_t)singleton);
    CloseHandle(gameTh);

    // Wait longer (game thread enters alertable waits relatively rarely; UI tick and
    // Vivox/IO can take several seconds). Poll the AssetRegistry's primary-asset count
    // every 500ms — if scan succeeds, [arCache+0x60] (config types array start) goes
    // non-zero and [arCache+0x68] (count) > 0. That's our hard signal that the scan ran.
    int waitedMs = 0;
    while (waitedMs < 30000) {
        Sleep(500); waitedMs += 500;
        uintptr_t arr60 = *(uintptr_t*)(arCache + 0x60);
        int32_t cnt68 = *(int32_t*)(arCache + 0x68);
        if (arr60 != 0 || cnt68 != 0) {
            Log("APC-FIRED-arr-cnt", arr60, (uintptr_t)(uint32_t)cnt68, (uintptr_t)waitedMs);
            break;
        }
    }
    Log("APC-WAIT-DONE", (uintptr_t)waitedMs, 0, 0);

    // Restore GGameThreadId and return; the APC may or may not have run yet.
    MemoryBarrier();
    *slot = origGGameTid;
    {
        DWORD rp2; VirtualProtect((LPVOID)slot, sizeof(DWORD), oldProt, &rp2);
    }
    Log("APC-DONE-RESTORED", 0, 0, 0);
    return;

    // (legacy path kept below for reference / fallback experiments)
    DWORD ec = 0;
    uintptr_t exAddr = 0, exRip = 0, exRsp = 0, exRax = 0, exRcx = 0;
    Log("PRE-CALL", (uintptr_t)scan, (uintptr_t)singleton, 0);
    __try {
        scan((void*)singleton);
        Log("POST-CALL-RETURNED", 0, 0, 0);
    } __except (
        ec = GetExceptionCode(),
        exAddr = (uintptr_t)((EXCEPTION_POINTERS*)_exception_info())->ExceptionRecord->ExceptionAddress,
        exRip = (uintptr_t)((EXCEPTION_POINTERS*)_exception_info())->ContextRecord->Rip,
        exRsp = (uintptr_t)((EXCEPTION_POINTERS*)_exception_info())->ContextRecord->Rsp,
        exRax = (uintptr_t)((EXCEPTION_POINTERS*)_exception_info())->ContextRecord->Rax,
        exRcx = (uintptr_t)((EXCEPTION_POINTERS*)_exception_info())->ContextRecord->Rcx,
        EXCEPTION_EXECUTE_HANDLER) {
        // Restore GGameThreadId on the failure path too.
        MemoryBarrier();
        *slot = origGGameTid;
        DWORD rp; VirtualProtect((LPVOID)slot, sizeof(DWORD), oldProt, &rp);
        Log("SEH-CAUGHT code", (uintptr_t)ec, exAddr, exAddr - base);
        Log("SEH-RIP", exRip, exRip - base, 0);
        Log("SEH-RAX-RCX", exRax, exRcx, exRsp);
        // Read the bytes at the faulting instruction (RIP) so we can decode it externally.
        // 0xC0000005 with exAddr != RIP means an indirect call/jmp; the JUMP TARGET is exAddr
        // and the instruction LIVES at RIP. We log a few qwords from each side of RIP.
        if (exRip) {
            __try {
                uintptr_t q0 = *(uintptr_t*)exRip;
                uintptr_t q1 = *(uintptr_t*)(exRip - 8);
                Log("SEH-RIP-q[0,-8]", q0, q1, 0);
            } __except(EXCEPTION_EXECUTE_HANDLER) {}
        }
        return;
    }

    // Restore the real GGameThreadId immediately after.
    MemoryBarrier();
    *slot = origGGameTid;
    DWORD restoreProt;
    VirtualProtect((LPVOID)slot, sizeof(DWORD), oldProt, &restoreProt);

    Log("DONE-scan-returned", base, singleton, (uintptr_t)origGGameTid);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(hModule);
        DoScan();
    }
    return TRUE;
}
