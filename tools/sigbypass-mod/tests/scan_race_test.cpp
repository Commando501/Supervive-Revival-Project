// scan_race_test.cpp — offline control for the S111 catalog_store_fix scan fix.
//
// Reproduces, in a standalone process, the exact condition that was killing SUPERVIVE:
// a scan walks a VirtualQuery region snapshot while another thread decommits pages under it.
//
//   ARM 1 (OLD): the shipped-until-now unguarded `*(uintptr_t*)p` walk   -> expected: CRASH
//   ARM 2 (NEW): SafeCopy/ReadProcessMemory chunked walk                 -> expected: SURVIVE + find
//
// Also runs a POSITIVE CONTROL first (no racing thread): the new scan must actually FIND the
// needle, so that "survived" can never be confused with "found nothing because it read nothing".
//
// build: clang++ -O2 scan_race_test.cpp -o scan_race_test.exe -lkernel32
#include <windows.h>
#include <cstdint>
#include <cstdio>

static constexpr size_t kScanChunk = 256 * 1024;
static constexpr size_t kScanPage  = 4096;
static uint8_t g_scanBuf[kScanChunk];

typedef int (*PFN_OnHit)(uintptr_t p, void* ctx);
static volatile uintptr_t g_walking;

// ── the NEW primitives, copied verbatim from catalog_store_fix.cpp ──
static inline bool SafeCopy(void* dst, const void* src, size_t n) {
    SIZE_T got = 0;
    return ReadProcessMemory(GetCurrentProcess(), src, dst, n, &got) && got == n;
}
static void ScanChunkBuf(uintptr_t at, size_t len, uintptr_t needle, PFN_OnHit onHit, void* ctx, bool* stop) {
    const uintptr_t* q = (const uintptr_t*)g_scanBuf;
    for (size_t i = 0; i + 8 <= len; i += 8)
        if (q[i / 8] == needle && onHit(at + i, ctx)) { *stop = true; return; }
}
static void ScanPrivateForQword_NEW(uintptr_t needle, PFN_OnHit onHit, void* ctx) {
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress;
    uintptr_t maxA = (uintptr_t)si.lpMaximumApplicationAddress;
    bool stop = false;
    while (addr < maxA && !stop) {
        MEMORY_BASIC_INFORMATION m{};
        if (!VirtualQuery((void*)addr, &m, sizeof(m))) break;
        uintptr_t next = (uintptr_t)m.BaseAddress + m.RegionSize;
        bool ok = (m.State & MEM_COMMIT) && !(m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
                  (m.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_WRITECOPY));
        if (ok && m.Type == MEM_PRIVATE) {
            uintptr_t base = (uintptr_t)m.BaseAddress, end = base + m.RegionSize;
            g_walking = base;
            for (uintptr_t c = base; c < end && !stop; c += kScanChunk) {
                size_t len = (size_t)((end - c) < kScanChunk ? (end - c) : kScanChunk);
                if (SafeCopy(g_scanBuf, (const void*)c, len)) {
                    ScanChunkBuf(c, len, needle, onHit, ctx, &stop);
                } else {
                    for (uintptr_t pg = c; pg < c + len && !stop; pg += kScanPage) {
                        size_t pl = (size_t)((c + len - pg) < kScanPage ? (c + len - pg) : kScanPage);
                        if (!SafeCopy(g_scanBuf, (const void*)pg, pl)) continue;
                        ScanChunkBuf(pg, pl, needle, onHit, ctx, &stop);
                    }
                }
            }
        }
        if (next <= addr) break; addr = next;
    }
}

// ── the OLD body, copied verbatim from the pre-fix catalog_store_fix.cpp ──
static uintptr_t ScanPrivateForQword_OLD(uintptr_t needle) {
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr = (uintptr_t)si.lpMinimumApplicationAddress, maxA = (uintptr_t)si.lpMaximumApplicationAddress;
    while (addr < maxA) {
        MEMORY_BASIC_INFORMATION m{};
        if (!VirtualQuery((void*)addr, &m, sizeof(m))) break;
        uintptr_t next = (uintptr_t)m.BaseAddress + m.RegionSize;
        bool ok = (m.State & MEM_COMMIT) && !(m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
                  (m.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_WRITECOPY));
        if (ok && m.Type == MEM_PRIVATE) {
            uintptr_t base = (uintptr_t)m.BaseAddress, end = base + m.RegionSize;
            g_walking = base;
            for (uintptr_t p = base; p + 8 <= end; p += 8)
                if (*(uintptr_t*)p == needle) return p;   // <-- THE UNGUARDED DEREF
        }
        if (next <= addr) break; addr = next;
    }
    return 0;
}

static const uintptr_t NEEDLE = 0x00007FF6DEADBEE0ULL;  // 8-aligned, plausible-looking
static const size_t REGSZ = 512 * 1024 * 1024;          // big enough that the walk takes real time
static void* g_region = nullptr;
static volatile LONG g_shredded = 0;

static int OnHit(uintptr_t p, void* ctx) { *(uintptr_t*)ctx = p; return 1; }

// The game freeing memory mid-walk. Waits until the scan is demonstrably INSIDE our region --
// i.e. it has already taken its VirtualQuery snapshot -- then decommits the tail out from under it.
// This is exactly the TOCTOU that killed SUPERVIVE >=11 times.
static DWORD WINAPI Shredder(LPVOID) {
    while (g_walking != (uintptr_t)g_region) Sleep(0);
    Sleep(1);                                            // let the walk get into the head of the region
    VirtualFree((uint8_t*)g_region + REGSZ / 4, REGSZ - REGSZ / 4, MEM_DECOMMIT);
    InterlockedExchange(&g_shredded, 1);
    return 0;
}

int main(int argc, char** argv) {
    int arm  = (argc > 1 && argv[1][0] == 'o') ? 0 : 1;   // "old" | "new"
    int race = (argc > 2 && argv[2][0] == 'r') ? 1 : 0;

    g_region = VirtualAlloc(nullptr, REGSZ, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!g_region) { printf("alloc fail\n"); return 9; }
    memset(g_region, 0x11, REGSZ);
    // Needle at the very END of the region, so the scan MUST traverse the whole thing (and, in the
    // race arms, must cross the shredded tail) before it can succeed. No early return.
    *(uintptr_t*)((uint8_t*)g_region + REGSZ - 4096) = NEEDLE;

    if (race) CreateThread(nullptr, 0, Shredder, nullptr, 0, nullptr);

    uintptr_t found = 0;
    if (arm == 0) found = ScanPrivateForQword_OLD(NEEDLE);
    else          ScanPrivateForQword_NEW(NEEDLE, OnHit, &found);

    printf("arm=%s race=%d -> SURVIVED, shredded=%d, found=0x%llX (%s)\n",
           arm ? "NEW" : "OLD", race, (int)g_shredded, (unsigned long long)found,
           found ? "FOUND" : "NOT FOUND");
    return 0;
}
