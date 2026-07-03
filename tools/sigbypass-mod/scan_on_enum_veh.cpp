// scan_on_enum — populate the AssetManager catalog DEMAND-DRIVEN, exactly when the menu
// first enumerates it, so the ALL HUNTERS grid (and store/cosmetics/missions) render.
//
// Session-43 trace (trace_hooks.dll) proved the grid enumerates heroes via
// UAssetManager::GetPrimaryAssetIdList(Hero) — called 209x at menu-load — and in the
// stock game that returns 0 because LokiAssetManager never fills the per-type AssetMap.
// Populating at Browse time was TIMING-fragile (the enumeration ran before the scan).
//
// Fix: hook GetPrimaryAssetIdList (LokiAssetManager vtable slot 110) via a vtable-slot
// swap. On the FIRST call (any type), run ScanPathsForPrimaryAssets for all 30 types —
// rcx IS the manager, so nothing to find — THEN tail-jump to the original, which now
// iterates the populated map and returns the real list. The scan therefore always
// precedes the enumeration's read, by construction. Un-hook after the one-shot scan so
// the vtable is pristine for any integrity check (session-43: a left-in-place patch
// crashes the game ~3-5 min in).
//
// Offsets (this build; module base moves with ASLR, RVAs stable):
//   LokiAssetManager vtable       = RVA +0x888CB78 ; slot 110 = GetPrimaryAssetIdList
//   UAssetManager::ScanPathsForPrimaryAssets = RVA +0x34CF9F0
//   GGameThreadId slot            = RVA +0x9D49158
//   manager+0x478 = AssetTypeMap (stride 0x20: key FName@0, FPrimaryAssetTypeData*@8)
//   FPrimaryAssetTypeData: Type FName@0, BaseClass UClass*@0x30, scan-paths TArray@0x70
//
// This is the scan_on_enum FIX + a read-only VEH crash logger (Session 45, Path-1):
// it both TRIGGERS the hero roster resolve+load AND captures the faulting RIP/module/
// RVA of the resulting hero-content-load crash before Sentry's crashpad kills the
// process, so we can tell whether that crash is the S40/41 D3D12/RHI family or not.
//
// Build:  clang++ -shared -O2 scan_on_enum_veh.cpp -o scan_on_enum_veh.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe scan_on_enum_veh.dll 0x3EC57D0 <prologuehex>
// Markers: docs/scan-on-enum-marker.txt (scan/enum) + docs/veh-crash-marker.txt (crash)

#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\scan-on-enum-marker.txt";

constexpr uintptr_t kVtRva       = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva     = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kGGameTidRva = 0x9D49158;
constexpr uintptr_t kTypeMapOff  = 0x478;
constexpr uintptr_t kInfoBaseOff = 0x30;
constexpr uintptr_t kInfoPathsOff= 0x70;
constexpr int       SLOT_IDL     = 110;         // GetPrimaryAssetIdList
constexpr uint32_t  kHeroFName   = 0x1A568;

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static void*     g_manager = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_scanState = 0;   // 0=not started, 1=scanning, 2=done
static volatile bool g_unhooked = false;

// ── logging: worker uses Marker (file); the hook uses the ring buffer ──
static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLogBuf=64*1024; static char g_log[kLogBuf]; static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLog(const char* s){RingAppend(s,(int)strlen(s));}
static void RingLogf(const char* f,...){char b[256];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

// ─────────────────────────── VEH crash logger (Path-1) ───────────────────────────
// Record the faulting RIP / RVA-in-main-exe / module / registers / stack band before
// Sentry's crashpad tears the process down, so we can tell whether the hero-content-
// load crash is the S40/41 D3D12/RHI family (RIP in the SUPERVIVE +0x29xxxxx band, or
// inside D3D12Core.dll) or something else (streaming/asset/GC). This is READ-ONLY and
// returns EXCEPTION_CONTINUE_SEARCH — it is NOT a C++-EH payload (the packer's VEH eats
// those). To avoid taking the loader lock inside the handler, the module table is
// snapshotted on the worker thread (SnapshotModules) and the VEH only reads it.
static const char* kCrashPath =
    "G:\\git\\Supervive Revival Project\\docs\\veh-crash-marker.txt";
static volatile long g_crashSeq = 0;

struct ModRange { uint64_t base, end; char name[64]; };
static ModRange g_mods[192];
static volatile long g_modCount = 0;

static void SnapshotModules() {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32, GetCurrentProcessId());
    if (snap == INVALID_HANDLE_VALUE) return;
    MODULEENTRY32 me; me.dwSize = sizeof(me);
    int n = 0;
    if (Module32First(snap, &me)) {
        do {
            if (n >= 192) break;
            ModRange& r = g_mods[n];
            r.base = (uint64_t)me.modBaseAddr; r.end = r.base + me.modBaseSize;
            int i = 0; for (; i < 63 && me.szModule[i]; i++) r.name[i] = (char)me.szModule[i];
            r.name[i] = 0; n++;
        } while (Module32Next(snap, &me));
    }
    CloseHandle(snap);
    InterlockedExchange(&g_modCount, n);
}

static void HxU64(char* o, uint64_t v){ const char* d="0123456789ABCDEF";
    for(int i=15;i>=0;i--){ o[i]=d[(int)(v&0xF)]; v>>=4; } }
static void CWrite(HANDLE h,const char* s,DWORD n){ DWORD w=0; WriteFile(h,s,n,&w,0); }
static void CKV(HANDLE h,const char* k,uint64_t v){
    char b[96]; int p=0; while(k[p] && p<40){ b[p]=k[p]; p++; }
    b[p++]='='; b[p++]='0'; b[p++]='x'; HxU64(b+p,v); p+=16; b[p++]='\r'; b[p++]='\n';
    CWrite(h,b,(DWORD)p); }

static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    bool fatal = code==0xC0000005 || code==0xC0000409 || code==0xC000001D ||
                 code==0x80000003 || code==0xC0000374 || code==0xC00000FD ||
                 code==0xC0000094 || code==0xC0000095 || code==0xC0000096;
    if(!fatal) return EXCEPTION_CONTINUE_SEARCH;
    long seq = InterlockedIncrement(&g_crashSeq);
    if(seq>64) return EXCEPTION_CONTINUE_SEARCH;                 // cap runaway
    HANDLE h=CreateFileA(kCrashPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,
                         nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE) return EXCEPTION_CONTINUE_SEARCH;
    CWrite(h,"=== VEH fatal exception ===\r\n",29);
    CKV(h,"seq",(uint64_t)seq); CKV(h,"code",code);
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip; CKV(h,"RIP",rip);
    // decisive datum: is the crash inside the SUPERVIVE binary, and at what RVA?
    if(g_modBase && rip>g_modBase && rip<g_modBase+0xC000000)
        CKV(h,"SUPERVIVE_RVA",rip-g_modBase);
    // module identity via the pre-snapshotted table (no loader API in the VEH)
    long mc=g_modCount; bool named=false;
    for(long i=0;i<mc;i++){ if(rip>=g_mods[i].base && rip<g_mods[i].end){
        CWrite(h,"module=",7); CWrite(h,g_mods[i].name,(DWORD)strlen(g_mods[i].name));
        CWrite(h,"\r\n",2); CKV(h,"module_RVA",rip-g_mods[i].base); named=true; break; } }
    if(!named) CWrite(h,"module=UNKNOWN\r\n",16);
    if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2){
        CKV(h,"av_op",ep->ExceptionRecord->ExceptionInformation[0]);   // 0=rd 1=wr 8=exec
        CKV(h,"av_addr",ep->ExceptionRecord->ExceptionInformation[1]); }
    CKV(h,"Rax",c->Rax); CKV(h,"Rbx",c->Rbx); CKV(h,"Rcx",c->Rcx); CKV(h,"Rdx",c->Rdx);
    CKV(h,"Rsi",c->Rsi); CKV(h,"Rdi",c->Rdi); CKV(h,"R8",c->R8); CKV(h,"R9",c->R9);
    CKV(h,"R10",c->R10); CKV(h,"R11",c->R11); CKV(h,"Rsp",c->Rsp); CKV(h,"Rbp",c->Rbp);
    // stack-band scan: return-addr-looking values inside the main exe -> which code band
    uint64_t base=g_modBase, top=g_modBase+0xC000000; uint64_t* sp=(uint64_t*)c->Rsp;
    int found=0;
    for(int i=0;i<800 && found<32;i++){
        if(!SafeReadable(sp+i,8)) break;
        uint64_t v=sp[i];
        if(base && v>base && v<top){ CKV(h,"stkRVA",v-base); found++; }
    }
    CWrite(h,"=== end ===\r\n\r\n",15);
    FlushFileBuffers(h); CloseHandle(h);
    return EXCEPTION_CONTINUE_SEARCH;   // let UE/Sentry handle it too
}

// Run ScanPathsForPrimaryAssets for every type in the manager's AssetTypeMap.
static void RunScanForAllTypes(void* manager) {
    const uint8_t* mgr=(const uint8_t*)manager;
    if(!SafeReadable(mgr+kTypeMapOff,16)){RingLog("[scan] typemap unreadable\r\n");return;}
    uintptr_t data=*(const uintptr_t*)(mgr+kTypeMapOff);
    uint32_t num=*(const uint32_t*)(mgr+kTypeMapOff+8), mx=*(const uint32_t*)(mgr+kTypeMapOff+12);
    RingLogf("[scan] AssetTypeMap num=%u max=%u\r\n",num,mx);
    if(!LooksLikePtr(data)||mx==0||mx>4096){RingLog("[scan] bad typemap\r\n");return;}
    int called=0,heroAdded=-1;
    for(uint32_t i=0;i<mx;i++){
        const uint8_t* e=(const uint8_t*)data+(uintptr_t)i*0x20;
        if(!SafeReadable(e,0x10))continue;
        uint64_t key=*(const uint64_t*)(e); uintptr_t td=*(const uintptr_t*)(e+8);
        if(key==0||!LooksLikePtr(td)||!SafeReadable((void*)td,0x80))continue;
        uint64_t type=*(const uint64_t*)td; uintptr_t base=*(const uintptr_t*)(td+kInfoBaseOff);
        void* paths=(void*)(td+kInfoPathsOff);
        if(type!=key||!LooksLikePtr(base)||!SafeReadable((void*)base,8))continue;
        int32_t added=g_scan(manager,type,paths,(void*)base,true,false,true);
        called++;
        if((uint32_t)(type&0xFFFFFFFF)==kHeroFName)heroAdded=added;
    }
    RingLogf("[scan] DONE: %d types scanned (Hero added=%d)\r\n",called,heroAdded);
}

// PRE handler (rcx=this, rdx=type, r8=&OutList, r9=filter). On the first call, run the
// scan once (rcx is the manager) so the original enumeration below reads a populated map.
extern "C" void h_idl_pre(uintptr_t rcx, uintptr_t /*rdx*/, uintptr_t, uintptr_t) {
    if (InterlockedCompareExchange(&g_scanState,1,0)!=0) return;   // already scanning/done
    RingLogf("[enum] first GetPrimaryAssetIdList call -> populating catalog (mgr=0x%llX)\r\n",
             (unsigned long long)rcx);
    g_manager=(void*)rcx;
    g_scan=(PFN_Scan)(g_modBase+kScanRva);
    RunScanForAllTypes((void*)rcx);
    InterlockedExchange(&g_scanState,2);
    RingLog("[enum] scan complete\r\n");
}
// POST handler: after the original ran, log what it returned for Hero (out TArray @r8, Num@+8).
static volatile long g_heroLogged = 0;
extern "C" void h_idl_post(uintptr_t /*rcx*/, uintptr_t rdx, uintptr_t r8, uintptr_t /*r9*/) {
    if ((uint32_t)(rdx & 0xFFFFFFFF) != kHeroFName) return;
    if (!SafeReadable((void*)(r8+8),4)) return;
    int32_t num = *(int32_t*)(r8+8);
    if (InterlockedExchange(&g_heroLogged,1)==0 || (num>0))
        RingLogf("[enum] GetPrimaryAssetIdList(Hero) returned Num=%d\r\n", num);
}

// WRAP stub: pre(scan) -> call original -> post(log Hero return) -> ret. The GetIdList
// function itself is unpatched (we swapped the vtable slot), so we call g_origIdl directly.
static uint8_t* BuildStub(void* pre, void* post, uintptr_t orig){
    uint8_t* p=(uint8_t*)VirtualAlloc(nullptr,0x100,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!p)return nullptr; uint8_t* w=p;
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x48;                       // sub rsp,0x48
    *w++=0x48;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x20;             // mov [rsp+0x20],rcx
    *w++=0x48;*w++=0x89;*w++=0x54;*w++=0x24;*w++=0x28;             // mov [rsp+0x28],rdx
    *w++=0x4C;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x30;             // mov [rsp+0x30],r8
    *w++=0x4C;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x38;             // mov [rsp+0x38],r9
    auto reload=[&](){ *w++=0x48;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x20; // mov rcx,[rsp+0x20]
        *w++=0x48;*w++=0x8B;*w++=0x54;*w++=0x24;*w++=0x28;               // mov rdx,[rsp+0x28]
        *w++=0x4C;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x30;               // mov r8,[rsp+0x30]
        *w++=0x4C;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x38; };            // mov r9,[rsp+0x38]
    *w++=0x48;*w++=0xB8; uint64_t pf=(uint64_t)pre; memcpy(w,&pf,8); w+=8; *w++=0xFF;*w++=0xD0;  // call pre
    reload();
    *w++=0x48;*w++=0xB8; uint64_t of=(uint64_t)orig; memcpy(w,&of,8); w+=8; *w++=0xFF;*w++=0xD0; // call original
    *w++=0x48;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x40;             // mov [rsp+0x40],rax (save ret)
    reload();
    *w++=0x48;*w++=0xB8; uint64_t sf=(uint64_t)post; memcpy(w,&sf,8); w+=8; *w++=0xFF;*w++=0xD0; // call post
    *w++=0x48;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x40;             // mov rax,[rsp+0x40] (restore ret)
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x48;                       // add rsp,0x48
    *w++=0xC3;                                                     // ret
    return p;
}

static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] scan_on_enum worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX vtable=0x%llX\r\n",(unsigned long long)g_modBase,(unsigned long long)(g_modBase+kVtRva));
    // Path-1: install the read-only crash VEH (first handler) + seed the module table.
    SnapshotModules();
    AddVectoredExceptionHandler(1, CrashVEH);
    Markerf("[veh] crash logger installed (modules=%ld) -> docs\\veh-crash-marker.txt\r\n",g_modCount);
    if(!WaitTid(g_modBase,60000)){Marker("[1] FAIL GGameThreadId\r\n");return 2;}

    uintptr_t* pslot=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)SLOT_IDL*8);
    DWORD dl=GetTickCount()+30000; bool ready=false;
    while(GetTickCount()<dl){if(SafeReadable(pslot,8)){uintptr_t v=*pslot;if(v>g_modBase&&v<g_modBase+0xC000000){ready=true;break;}}Sleep(5);}
    if(!ready){Marker("[2] FAIL slot 110 not ready\r\n");return 3;}
    g_origIdl=*pslot;
    g_stubIdl=BuildStub((void*)&h_idl_pre,(void*)&h_idl_post,g_origIdl);
    if(!g_stubIdl){Marker("[3] FAIL build stub\r\n");return 4;}
    DWORD op=0; if(!VirtualProtect(pslot,8,PAGE_READWRITE,&op)){Marker("[3] FAIL VP\r\n");return 5;}
    *pslot=(uintptr_t)g_stubIdl; DWORD d=0; VirtualProtect(pslot,8,op,&d);
    Markerf("[3] GetPrimaryAssetIdList hooked (orig=0x%llX stub=%p)\r\n",(unsigned long long)g_origIdl,(void*)g_stubIdl);

    LONG64 flushed=0; DWORD hb=GetTickCount();
    while(true){
        Sleep(150);
        // un-hook shortly after the one-shot scan finished
        if(!g_unhooked && g_scanState==2){
            static DWORD doneAt=0; if(doneAt==0)doneAt=GetTickCount();
            else if(GetTickCount()-doneAt>=1500){
                DWORD o=0; if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}
                g_unhooked=true; Marker("[unhook] slot 110 restored\r\n");
            }
        }
        LONG64 head=g_head; if(head>(LONG64)sizeof(g_log))head=(LONG64)sizeof(g_log);
        if(head>flushed){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_log+flushed,(DWORD)(head-flushed),&w,nullptr);CloseHandle(f);flushed=head;}}
        if(GetTickCount()-hb>=5000){SnapshotModules();Markerf("[hb] scanState=%ld unhooked=%d modules=%ld\r\n",g_scanState,g_unhooked?1:0,g_modCount);hb=GetTickCount();}
    }
}

BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
