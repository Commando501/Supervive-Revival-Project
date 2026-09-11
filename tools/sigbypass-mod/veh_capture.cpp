// veh_capture — pure read-only VEH crash logger (NO hooks, NO writes). Injected into the
// DS-connected client to name the code that jumps to the corrupted pointer (session-53 crash:
// execute-AV at 0x7FF8F0400001, no module). Logs, BEFORE Sentry's handler: exception code, RIP +
// its module/RVA, AV op/addr, all GP registers, and the STACK RETURN-ADDRESS CHAIN (callers) with
// each resolved to module+RVA — so we see which SUPERVIVE function called through the bad pointer.
// Re-snapshots the module table every 3s (so late-loaded DLLs like d3d12 are covered).
// Build:  clang++ -shared -O2 veh_capture.cpp -o veh_capture.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/veh_capture.dll   (or watch-now early)
// Marker: docs/veh-capture-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstring>

static const char* kMarker = "G:\\git\\Supervive Revival Project\\docs\\veh-capture-marker.txt";

struct ModRange { uint64_t base, end; char name[64]; };
static ModRange g_mods[320];
static volatile long g_modCount = 0;
static volatile long g_seq = 0;
static uint64_t g_exeBase = 0;

static void W(const char* s, DWORD n) { HANDLE h = CreateFileA(kMarker, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr); if (h == INVALID_HANDLE_VALUE) return; DWORD w = 0; WriteFile(h, s, n, &w, nullptr); CloseHandle(h); }
static void Ws(const char* s) { W(s, (DWORD)strlen(s)); }
static void Hx(char* o, uint64_t v) { const char* d = "0123456789ABCDEF"; for (int i = 15; i >= 0; i--) { o[i] = d[(int)(v & 0xF)]; v >>= 4; } }
static void KV(const char* k, uint64_t v) { char b[96]; int p = 0; while (k[p] && p < 40) { b[p] = k[p]; p++; } b[p++] = '='; b[p++] = '0'; b[p++] = 'x'; Hx(b + p, v); p += 16; b[p++] = '\r'; b[p++] = '\n'; W(b, (DWORD)p); }

static bool SafeReadable(const void* a, size_t sz) { MEMORY_BASIC_INFORMATION m{}; if (!VirtualQuery(a, &m, sizeof(m))) return false; if (!(m.State & MEM_COMMIT)) return false; if (m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return false; return (uintptr_t)a + sz <= (uintptr_t)m.BaseAddress + m.RegionSize; }

static void Snapshot() {
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId());
    if (s == INVALID_HANDLE_VALUE) return;
    MODULEENTRY32 me; me.dwSize = sizeof(me); int n = 0;
    if (Module32First(s, &me)) { do { if (n >= 320) break; ModRange& r = g_mods[n]; r.base = (uint64_t)me.modBaseAddr; r.end = r.base + me.modBaseSize; int i = 0; for (; i < 63 && me.szModule[i]; i++) r.name[i] = (char)me.szModule[i]; r.name[i] = 0; if (_stricmp(r.name, "SUPERVIVE-Win64-Shipping.exe") == 0) g_exeBase = r.base; n++; } while (Module32Next(s, &me)); }
    CloseHandle(s); InterlockedExchange(&g_modCount, n);
}
// resolve addr -> "name+0xRVA" into out; returns true if in a module
static bool Resolve(uint64_t addr, char* out, int cap) {
    long mc = g_modCount;
    for (long i = 0; i < mc; i++) {
        if (addr >= g_mods[i].base && addr < g_mods[i].end) {
            int p = 0; const char* nm = g_mods[i].name; while (nm[p] && p < 48) { out[p] = nm[p]; p++; }
            out[p++] = '+'; out[p++] = '0'; out[p++] = 'x'; Hx(out + p, addr - g_mods[i].base); p += 16; out[p] = 0; return true;
        }
    }
    int p = 0; const char* u = "<no-module>"; while (u[p]) { out[p] = u[p]; p++; } out[p] = 0; return false;
}

static LONG CALLBACK VEH(EXCEPTION_POINTERS* ep) {
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    bool fatal = code == 0xC0000005 || code == 0xC0000409 || code == 0xC000001D || code == 0xC0000374 || code == 0xC00000FD || code == 0x80000003;
    if (!fatal) return EXCEPTION_CONTINUE_SEARCH;
    long seq = InterlockedIncrement(&g_seq); if (seq > 8) return EXCEPTION_CONTINUE_SEARCH;
    Snapshot();  // ensure module table is current at crash time
    CONTEXT* c = ep->ContextRecord;
    char line[160];
    Ws("\r\n=== VEH FATAL ===\r\n");
    KV("seq", (uint64_t)seq); KV("code", code);
    uint64_t rip = c->Rip;
    KV("RIP", rip);
    { char r[128]; Resolve(rip, r, sizeof(r)); Ws("RIP_mod="); Ws(r); Ws("\r\n"); }
    if (g_exeBase && rip >= g_exeBase && rip < g_exeBase + 0xC000000) KV("RIP_exeRVA", rip - g_exeBase);
    if (code == 0xC0000005 && ep->ExceptionRecord->NumberParameters >= 2) {
        KV("av_op", ep->ExceptionRecord->ExceptionInformation[0]);   // 0=read 1=write 8=execute
        KV("av_addr", ep->ExceptionRecord->ExceptionInformation[1]);
    }
    KV("RSP", c->Rsp); KV("RBP", c->Rbp);
    KV("RAX", c->Rax); KV("RBX", c->Rbx); KV("RCX", c->Rcx); KV("RDX", c->Rdx);
    KV("RSI", c->Rsi); KV("RDI", c->Rdi); KV("R8", c->R8); KV("R9", c->R9);
    KV("R10", c->R10); KV("R11", c->R11); KV("R12", c->R12); KV("R13", c->R13); KV("R14", c->R14); KV("R15", c->R15);
    // If RCX looks like a UObject (this-ptr) resolve its vtable[0] module — helps ID a corrupted object
    if (SafeReadable((void*)c->Rcx, 8)) { uint64_t vt = *(uint64_t*)c->Rcx; char r[128]; Resolve(vt, r, sizeof(r)); Ws("[RCX].vtable="); Ws(r); Ws("\r\n"); }
    // Walk the stack for the first ~16 return addresses that land in a module = the caller chain.
    Ws("caller chain (stack return addrs):\r\n");
    uint64_t rsp = c->Rsp; int shown = 0;
    for (int off = 0; off < 0x600 && shown < 16; off += 8) {
        uint64_t* pv = (uint64_t*)(rsp + off);
        if (!SafeReadable(pv, 8)) continue;
        uint64_t v = *pv; char r[128];
        if (Resolve(v, r, sizeof(r))) {
            // only report addresses that plausibly point at code (inside a module)
            int p = 0; while (r[p] && r[p] != '+') p++;
            // skip data segs by requiring the RVA looks like .text-ish? keep it simple: report all module hits
            char b[200]; int q = 0; const char* pre = "  [rsp+0x"; while (pre[q - 0] && q < 9) { b[q] = pre[q]; q++; }
            Hx(b + q, (uint64_t)off); q += 16; b[q++] = ']'; b[q++] = ' '; b[q++] = '0'; b[q++] = 'x'; Hx(b + q, v); q += 16; b[q++] = ' ';
            int k = 0; while (r[k] && q < 190) b[q++] = r[k++]; b[q++] = '\r'; b[q++] = '\n'; W(b, (DWORD)q);
            shown++;
        }
    }
    Ws("=== end ===\r\n");
    return EXCEPTION_CONTINUE_SEARCH;  // let Sentry still handle it
}

static DWORD WINAPI Worker(LPVOID) {
    { HANDLE h = CreateFileA(kMarker, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr); if (h != INVALID_HANDLE_VALUE) CloseHandle(h); }
    Ws("[0] veh_capture installed (pure observer)\r\n");
    Snapshot();
    AddVectoredExceptionHandler(1, VEH);  // first-chance, runs before Sentry
    KV("[0] exeBase", g_exeBase);
    KV("[0] modules", (uint64_t)g_modCount);
    // heartbeat: re-snapshot every 3s so late DLLs are captured; prove liveness
    int hb = 0;
    for (;;) { Sleep(3000); Snapshot(); if ((++hb % 10) == 0) { KV("[hb] modules", (uint64_t)g_modCount); } }
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h, DWORD r, LPVOID) { if (r == DLL_PROCESS_ATTACH) { DisableThreadLibraryCalls(h); HANDLE t = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr); if (t) CloseHandle(t); } return TRUE; }
extern "C" __declspec(dllexport) void* start_mod() { return new int(0); }
extern "C" __declspec(dllexport) void uninstall_mod(void* m) { delete static_cast<int*>(m); }
