// createthread_probe — hook ntdll!NtCreateThreadEx; log any thread creation whose StartRoutine is
// UNMAPPED (== the session-53 DS crash: a worker thread spun up with garbage entry 0x7FF8F0400001).
// For each such call logs: StartRoutine, Argument, the CALLER (return addr -> module+RVA), and the
// Argument's first qword (if it is a UObject: its vtable -> module+RVA, and ClassPrivate name). That
// names the corrupted object + the code path that threaded its garbage callback.
// NtCreateThreadEx(rcx=PHANDLE, rdx=access, r8=objattr, r9=hProc, [rsp+0x28]=StartRoutine,
//                  [rsp+0x30]=Argument, [rsp+0x38]=flags, ...). Std syscall stub: 4C 8B D1 B8 <imm32>.
// Build:  clang++ -shared -O2 createthread_probe.cpp -o createthread_probe.dll -lkernel32
// Inject: tools/inject/inject.exe watch-now SUPERVIVE-Win64-Shipping.exe <dll>  (early — before the crash)
// Marker: docs/createthread-probe-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstring>

static const char* kMarker = "G:\\git\\Supervive Revival Project\\docs\\createthread-probe-marker.txt";

struct ModRange { uint64_t base, end; char name[64]; };
static ModRange g_mods[320]; static volatile long g_modCount = 0; static uint64_t g_exeBase = 0, g_namePool = 0;
static uint8_t* g_target = nullptr; static uint8_t g_stolen[16]; static int g_stealLen = 0;
typedef void* PFN; static volatile PFN g_tramp = nullptr;

static void W(const char* s, DWORD n) { HANDLE h = CreateFileA(kMarker, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr); if (h == INVALID_HANDLE_VALUE) return; DWORD w = 0; WriteFile(h, s, n, &w, nullptr); CloseHandle(h); }
static void Ws(const char* s) { W(s, (DWORD)strlen(s)); }
static void Hx(char* o, uint64_t v) { const char* d = "0123456789ABCDEF"; for (int i = 15; i >= 0; i--) { o[i] = d[(int)(v & 0xF)]; v >>= 4; } }
static void KV(const char* k, uint64_t v) { char b[96]; int p = 0; while (k[p] && p < 40) { b[p] = k[p]; p++; } b[p++] = '='; b[p++] = '0'; b[p++] = 'x'; Hx(b + p, v); p += 16; b[p++] = '\r'; b[p++] = '\n'; W(b, (DWORD)p); }
static bool SafeR(const void* a, size_t sz) { MEMORY_BASIC_INFORMATION m{}; if (!VirtualQuery(a, &m, sizeof(m))) return false; if (!(m.State & MEM_COMMIT)) return false; if (m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return false; return (uintptr_t)a + sz <= (uintptr_t)m.BaseAddress + m.RegionSize; }
static bool LP(uint64_t v) { return v >= 0x10000 && v < 0x0001000000000000ULL && (v & 7) == 0; }

static void Snapshot() {
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId()); if (s == INVALID_HANDLE_VALUE) return;
    MODULEENTRY32 me; me.dwSize = sizeof(me); int n = 0;
    if (Module32First(s, &me)) { do { if (n >= 320) break; ModRange& r = g_mods[n]; r.base = (uint64_t)me.modBaseAddr; r.end = r.base + me.modBaseSize; int i = 0; for (; i < 63 && me.szModule[i]; i++) r.name[i] = (char)me.szModule[i]; r.name[i] = 0; if (_stricmp(r.name, "SUPERVIVE-Win64-Shipping.exe") == 0) g_exeBase = r.base; n++; } while (Module32Next(s, &me)); }
    CloseHandle(s); InterlockedExchange(&g_modCount, n);
}
static bool InMod(uint64_t a, char* out, int cap) {
    long mc = g_modCount;
    for (long i = 0; i < mc; i++) if (a >= g_mods[i].base && a < g_mods[i].end) { int p = 0; const char* nm = g_mods[i].name; while (nm[p] && p < 48) { out[p] = nm[p]; p++; } out[p++] = '+'; out[p++] = '0'; out[p++] = 'x'; Hx(out + p, a - g_mods[i].base); p += 16; out[p] = 0; return true; }
    int p = 0; const char* u = "<unmapped>"; while (u[p]) { out[p] = u[p]; p++; } out[p] = 0; return false;
}
// FName string from a ComparisonIndex (this build: block=id>>16, off=(id&0xFFFF)<<1; hdr len>>6, wide&1)
static bool FName(uint32_t id, char* out, int cap) {
    if (!g_namePool) return false; uint64_t* blocks = (uint64_t*)g_namePool; uint32_t b = id >> 16, off = (id & 0xFFFF) << 1;
    if (!SafeR(blocks + b, 8)) return false; uint64_t bp = blocks[b]; if (!LP(bp)) return false;
    if (!SafeR((void*)(bp + off), 2)) return false; uint16_t hd = *(uint16_t*)(bp + off); int len = hd >> 6; bool wide = hd & 1;
    if (len <= 0 || len >= cap) return false;
    if (wide) { for (int i = 0; i < len; i++) out[i] = (char)*(uint16_t*)(bp + off + 2 + i * 2); } else { if (!SafeR((void*)(bp + off + 2), len)) return false; for (int i = 0; i < len; i++) out[i] = ((char*)(bp + off + 2))[i]; }
    out[len] = 0; return true;
}

static volatile long g_hits = 0;
// C handler; origRsp = rsp AT NtCreateThreadEx entry ([+0]=caller ret, [+0x28]=StartRoutine, [+0x30]=Argument)
extern "C" void OnCreate(uint64_t* origRsp) {
    if (!SafeR(origRsp, 0x40)) return;
    uint64_t caller = origRsp[0];
    uint64_t start = origRsp[5];   // +0x28
    uint64_t arg = origRsp[6];     // +0x30
    char m[128];
    if (InMod(start, m, sizeof(m))) return;   // normal (mapped) start routine -> ignore
    long h = InterlockedIncrement(&g_hits); if (h > 12) return;
    Snapshot();
    Ws("\r\n=== UNMAPPED THREAD START ===\r\n");
    KV("StartRoutine", start);
    { char r[128]; InMod(start, r, sizeof(r)); Ws("  start_mod="); Ws(r); Ws("\r\n"); }
    KV("Argument", arg);
    { char r[128]; InMod(caller, r, sizeof(r)); Ws("  CALLER="); Ws(r); Ws("\r\n"); }
    if (g_exeBase && caller >= g_exeBase && caller < g_exeBase + 0xC000000) KV("  caller_exeRVA", caller - g_exeBase);
    // Argument as a possible UObject: [arg+0]=vtable, [arg+0x18]=ClassPrivate, class Name @ +0x20
    if (LP(arg) && SafeR((void*)arg, 0x28)) {
        uint64_t vt = *(uint64_t*)arg; char r[128]; InMod(vt, r, sizeof(r)); Ws("  [arg].vtable="); Ws(r); Ws("\r\n");
        uint64_t cls = *(uint64_t*)(arg + 0x18);
        if (LP(cls) && SafeR((void*)(cls + 0x20), 4)) { uint32_t nid = *(uint32_t*)(cls + 0x20); char cn[96]; if (FName(nid, cn, sizeof(cn))) { Ws("  [arg].Class="); Ws(cn); Ws("\r\n"); } }
    }
    Ws("=== end ===\r\n");
}

// ---- hook plumbing ----
static uint8_t* NearAlloc(uintptr_t anchor, size_t sz) { for (uintptr_t off = 0x10000; off < 0x7F000000ull; off += 0x10000) { uintptr_t c[2] = { (anchor + off) & ~0xFFFFull, (anchor > off ? (anchor - off) : 0) & ~0xFFFFull }; for (int i = 0; i < 2; i++) { if (!c[i]) continue; void* p = VirtualAlloc((void*)c[i], sz, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE); if (p) { intptr_t dlt = (intptr_t)p - (intptr_t)anchor; if (dlt > (intptr_t)-0x7F000000 && dlt < (intptr_t)0x7F000000) return (uint8_t*)p; VirtualFree(p, 0, MEM_RELEASE); } } } return nullptr; }
struct Em { uint8_t* w; }; static void EB(Em& e, uint8_t b) { *e.w++ = b; } static void EU32(Em& e, uint32_t v) { memcpy(e.w, &v, 4); e.w += 4; } static void EU64(Em& e, uint64_t v) { memcpy(e.w, &v, 8); e.w += 8; }
static bool SafeWrite(uint8_t* dst, const uint8_t* src, size_t len) {
    DWORD myTid = GetCurrentThreadId(), myPid = GetCurrentProcessId(); HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0); if (snap == INVALID_HANDLE_VALUE) return false;
    HANDLE hs[1024]; int nh = 0; THREADENTRY32 te; te.dwSize = sizeof(te);
    if (Thread32First(snap, &te)) { do { if (te.th32OwnerProcessID == myPid && te.th32ThreadID != myTid && nh < 1024) { HANDLE ht = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID); if (ht) hs[nh++] = ht; } } while (Thread32Next(snap, &te)); } CloseHandle(snap);
    uintptr_t lo = (uintptr_t)dst, hi = (uintptr_t)dst + len; bool ok = false;
    for (int a = 0; a < 400 && !ok; a++) { for (int i = 0; i < nh; i++) SuspendThread(hs[i]); bool unsafe = false; for (int i = 0; i < nh; i++) { CONTEXT c; c.ContextFlags = CONTEXT_CONTROL; if (GetThreadContext(hs[i], &c)) { if (c.Rip > lo && c.Rip < hi) { unsafe = true; break; } } } if (!unsafe) { DWORD op = 0; if (VirtualProtect(dst, len, PAGE_EXECUTE_READWRITE, &op)) { memcpy(dst, src, len); DWORD dd = 0; VirtualProtect(dst, len, op, &dd); FlushInstructionCache(GetCurrentProcess(), dst, len); ok = true; } } if (!ok) { for (int i = 0; i < nh; i++) ResumeThread(hs[i]); Sleep(1); } }
    for (int i = 0; i < nh; i++) { ResumeThread(hs[i]); CloseHandle(hs[i]); } return ok;
}

static DWORD WINAPI Worker(LPVOID) {
    { HANDLE h = CreateFileA(kMarker, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr); if (h != INVALID_HANDLE_VALUE) CloseHandle(h); }
    Ws("[0] createthread_probe start\r\n"); Snapshot();
    // resolve FNamePool base = exe + 0x9D81450 (this build)
    if (g_exeBase) g_namePool = g_exeBase + 0x9D81450;
    HMODULE nt = GetModuleHandleA("ntdll.dll"); if (!nt) { Ws("[x] no ntdll\r\n"); return 1; }
    uint8_t* fn = (uint8_t*)GetProcAddress(nt, "NtCreateThreadEx"); if (!fn) { Ws("[x] no NtCreateThreadEx\r\n"); return 1; }
    g_target = fn; KV("NtCreateThreadEx", (uint64_t)fn);
    // verify std syscall stub: 4C 8B D1 (mov r10,rcx) B8 imm32 (mov eax,imm)
    if (!(fn[0] == 0x4C && fn[1] == 0x8B && fn[2] == 0xD1 && fn[3] == 0xB8)) { Ws("[x] unexpected prologue; not hooking\r\n"); { char b[64]; int p=0; const char* t="prologue="; while(t[p]){b[p]=t[p];p++;} for(int i=0;i<8;i++){b[p++]="0123456789ABCDEF"[fn[i]>>4];b[p++]="0123456789ABCDEF"[fn[i]&0xF];b[p++]=' ';} b[p++]='\r';b[p++]='\n'; W(b,p);} return 1; }
    g_stealLen = 8;  // mov r10,rcx (3) + mov eax,imm32 (5)
    memcpy(g_stolen, fn, g_stealLen);
    // trampoline: stolen bytes + abs jmp to fn+8
    uint8_t* blk = NearAlloc((uintptr_t)fn, 0x200); if (!blk) { Ws("[x] NearAlloc fail\r\n"); return 1; }
    Em t{ blk }; for (int i = 0; i < g_stealLen; i++) EB(t, g_stolen[i]);
    EB(t, 0x48); EB(t, 0xB8); EU64(t, (uint64_t)(fn + g_stealLen)); EB(t, 0xFF); EB(t, 0xE0); // mov rax,fn+8; jmp rax
    g_tramp = (PFN)blk;
    // stub: save volatiles, compute origRsp, call OnCreate, restore, jmp tramp
    uint8_t* stub = blk + 0x40; Em e{ stub };
    // push rcx rdx r8 r9 r10 r11  (6*8=0x30)
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);EB(e,0x41);EB(e,0x52);EB(e,0x41);EB(e,0x53);
    // wait: that's rcx,rdx,r8,r9,r10,r11 -> 51 52 41 50 41 51 41 52 41 53
    EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);               // sub rsp,0x28 (shadow+align)
    // rcx = origRsp = current rsp + 0x28 + 0x30
    EB(e,0x48);EB(e,0x8D);EB(e,0x8C);EB(e,0x24);EU32(e,0x28+0x30); // lea rcx,[rsp+0x58]
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnCreate);EB(e,0xFF);EB(e,0xD0); // mov rax,OnCreate; call rax
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);               // add rsp,0x28
    // pop r11 r10 r9 r8 rdx rcx
    EB(e,0x41);EB(e,0x5B);EB(e,0x41);EB(e,0x5A);EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk);EB(e,0xFF);EB(e,0xE0); // mov rax,tramp; jmp rax
    // install: jmp stub over the 8 stolen bytes (E9 rel32 + 3 nop pad)
    int32_t rel = (int32_t)((intptr_t)stub - ((intptr_t)fn + 5)); uint8_t patch[8] = { 0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24),0x90,0x90,0x90 };
    if (!SafeWrite(fn, patch, 8)) { Ws("[x] SafeWrite fail\r\n"); return 1; }
    Ws("[1] NtCreateThreadEx hooked; watching for unmapped thread starts...\r\n");
    for (;;) { Sleep(3000); Snapshot(); }
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h, DWORD r, LPVOID) { if (r == DLL_PROCESS_ATTACH) { DisableThreadLibraryCalls(h); HANDLE t = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr); if (t) CloseHandle(t); } return TRUE; }
extern "C" __declspec(dllexport) void* start_mod() { return new int(0); }
extern "C" __declspec(dllexport) void uninstall_mod(void* m) { delete static_cast<int*>(m); }
