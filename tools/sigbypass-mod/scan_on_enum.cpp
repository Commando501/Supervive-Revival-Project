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
// Build:  clang++ -shared -O2 scan_on_enum.cpp -o scan_on_enum.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe scan_on_enum.dll 0x3EC57D0 <prologuehex>
// Marker: docs/scan-on-enum-marker.txt

#include <windows.h>
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
        if(GetTickCount()-hb>=5000){Markerf("[hb] scanState=%ld unhooked=%d\r\n",g_scanState,g_unhooked?1:0);hb=GetTickCount();}
    }
}

BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
