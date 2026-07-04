// catalog_ready_fix — session 47 FIX test. Root cause (docs/session-47-tile-widget-FOUND.txt): the ALL
// HUNTERS grid (WBP_HeroPicker) only runs LoadCharacters if IsCatalogDataReady() is true; that native impl
// (+0x57BB700, rcx=CatalogManager) returns true only when ALL of [CatMgr+0x350..0x354] are nonzero, but the
// live 5th flag [+0x354]==0 on the dead/stub backend => IsCatalogDataReady==false => the grid binds
// OnCatalogDataReady and waits forever => AllHunters never built => empty grid. Heroes themselves resolve
// fine (proven) and aren't hidden. So: (1) scan the AssetManager so Hero enumerates 25 (else GetHeroCharacterList
// returns 0), and (2) force IsCatalogDataReady true BEFORE the grid Constructs by holding [CatMgr+0x354]=1.
//
// (1) = the proven scan_on_enum: hook GetPrimaryAssetIdList slot 110, first call scans all 30 types.
// (2) = find the live CatalogManager (scan committed memory for its vtable abs = base+0x8831758; pick the
//       instance whose +0x60 catalog map Num is populated, NOT the empty CDO) and, in a tight loop through
//       menu-load, write [+0x350..0x354]=1. When WBP_HeroPicker Constructs it sees IsCatalogDataReady==true
//       and calls LoadCharacters directly (no waiting on the never-firing delegate) -> AllHunters fills.
//
// Build:  clang++ -shared -O2 catalog_ready_fix.cpp -o catalog_ready_fix.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe catalog_ready_fix.dll 0x3EC57D0 40555356574154415541564157
// Marker: docs/catalog-ready-fix-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\catalog-ready-fix-marker.txt";

constexpr uintptr_t kVtRva        = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva      = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr uintptr_t kTypeMapOff   = 0x478;
constexpr uintptr_t kInfoBaseOff  = 0x30;
constexpr uintptr_t kInfoPathsOff = 0x70;
constexpr int       SLOT_IDL      = 110;
constexpr uint32_t  kHeroFName    = 0x1A568;
constexpr uintptr_t kCatMgrVtRva  = 0x8831758;   // CatalogManager vtable
constexpr uintptr_t kMapOff       = 0x60;        // CatalogManager catalog map (Data@+0x60, Num@+0x68)
constexpr uintptr_t kReadyOff     = 0x350;       // IsCatalogDataReady flags [+0x350..+0x354]
constexpr uintptr_t kJzRva        = 0x57BB722;   // the `jz false` after the [+0x354] check in IsCatalogDataReady
                                                 // impl; NOP it (74 0C -> 90 90) so the never-set 5th flag is
                                                 // ignored => IsCatalogDataReady returns true once the 4 REAL
                                                 // flags [0x350-0x353] are set (== when the catalog is loaded),
                                                 // so the game's post-load readiness check BROADCASTS
                                                 // OnCatalogDataReady and the waiting grid runs LoadCharacters.

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);
struct TArr { void* Data; int32_t Num; int32_t Max; };

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_scanState = 0;
static volatile bool g_unhooked = false;
static volatile uintptr_t g_catMgr = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

static void RunScanForAllTypes(void* manager){
    const uint8_t* mgr=(const uint8_t*)manager;
    if(!SafeReadable(mgr+kTypeMapOff,16)){Marker("[scan] typemap unreadable\r\n");return;}
    uintptr_t data=*(const uintptr_t*)(mgr+kTypeMapOff);
    uint32_t mx=*(const uint32_t*)(mgr+kTypeMapOff+12);
    if(!LooksLikePtr(data)||mx==0||mx>4096){Marker("[scan] bad typemap\r\n");return;}
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
    Markerf("[scan] DONE: %d types scanned (Hero added=%d)\r\n",called,heroAdded);
}

extern "C" void h_idl_pre(uintptr_t rcx, uintptr_t, uintptr_t, uintptr_t){
    if(InterlockedCompareExchange(&g_scanState,1,0)!=0) return;
    Markerf("[enum] first GetPrimaryAssetIdList -> scan (mgr=0x%llX)\r\n",(unsigned long long)rcx);
    g_scan=(PFN_Scan)(g_modBase+kScanRva);
    RunScanForAllTypes((void*)rcx);
    InterlockedExchange(&g_scanState,2);
}
extern "C" void h_idl_post(uintptr_t, uintptr_t, uintptr_t, uintptr_t){}

static uint8_t* BuildStub(void* pre, void* post, uintptr_t orig){
    uint8_t* p=(uint8_t*)VirtualAlloc(nullptr,0x100,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!p)return nullptr; uint8_t* w=p;
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x48;
    *w++=0x48;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x20;
    *w++=0x48;*w++=0x89;*w++=0x54;*w++=0x24;*w++=0x28;
    *w++=0x4C;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x30;
    *w++=0x4C;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x38;
    auto reload=[&](){ *w++=0x48;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x20;
        *w++=0x48;*w++=0x8B;*w++=0x54;*w++=0x24;*w++=0x28;
        *w++=0x4C;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x30;
        *w++=0x4C;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x38; };
    *w++=0x48;*w++=0xB8; uint64_t pf=(uint64_t)pre; memcpy(w,&pf,8); w+=8; *w++=0xFF;*w++=0xD0;
    reload();
    *w++=0x48;*w++=0xB8; uint64_t of=(uint64_t)orig; memcpy(w,&of,8); w+=8; *w++=0xFF;*w++=0xD0;
    *w++=0x48;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x40;
    reload();
    *w++=0x48;*w++=0xB8; uint64_t sf=(uint64_t)post; memcpy(w,&sf,8); w+=8; *w++=0xFF;*w++=0xD0;
    *w++=0x48;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x40;
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x48;
    *w++=0xC3;
    return p;
}
static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// Scan committed RW memory for a CatalogManager instance (vtable==target) whose +0x60 catalog map is
// populated (Num in a plausible range). Returns the instance address or 0.
static uintptr_t FindCatalogManager(uintptr_t vtabAbs){
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr=(uintptr_t)si.lpMinimumApplicationAddress;
    uintptr_t maxA=(uintptr_t)si.lpMaximumApplicationAddress;
    while(addr<maxA){
        MEMORY_BASIC_INFORMATION m{};
        if(!VirtualQuery((void*)addr,&m,sizeof(m))) break;
        uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;
        bool ok = (m.State&MEM_COMMIT) && !(m.Protect&(PAGE_NOACCESS|PAGE_GUARD)) &&
                  (m.Protect&(PAGE_READWRITE|PAGE_EXECUTE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_WRITECOPY));
        if(ok && m.Type==MEM_PRIVATE){
            uintptr_t base=(uintptr_t)m.BaseAddress; uintptr_t end=base+m.RegionSize;
            for(uintptr_t p=base; p+8<=end; p+=8){
                if(*(uintptr_t*)p==vtabAbs){
                    // candidate instance at p; check +0x60 map Num
                    if(SafeReadable((void*)(p+kMapOff),16)){
                        uintptr_t mdata=*(uintptr_t*)(p+kMapOff);
                        int32_t mnum=*(int32_t*)(p+kMapOff+8);
                        if(LooksLikePtr(mdata) && mnum>=50 && mnum<=5000) return p;
                    }
                }
            }
        }
        if(next<=addr) break; addr=next;
    }
    return 0;
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] catalog_ready_fix worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);
    if(!WaitTid(g_modBase,60000)){Marker("[1] FAIL GGameThreadId\r\n");return 2;}
    uintptr_t* pslot=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)SLOT_IDL*8);
    DWORD dl=GetTickCount()+30000; bool ready=false;
    while(GetTickCount()<dl){if(SafeReadable(pslot,8)){uintptr_t v=*pslot;if(v>g_modBase&&v<g_modBase+0xC000000){ready=true;break;}}Sleep(5);}
    if(!ready){Marker("[2] FAIL slot 110\r\n");return 3;}
    g_origIdl=*pslot;
    g_stubIdl=BuildStub((void*)&h_idl_pre,(void*)&h_idl_post,g_origIdl);
    DWORD op=0; VirtualProtect(pslot,8,PAGE_READWRITE,&op); *pslot=(uintptr_t)g_stubIdl; DWORD d=0; VirtualProtect(pslot,8,op,&d);
    Marker("[3] GetPrimaryAssetIdList hooked (scan armed)\r\n");

    uintptr_t vtabAbs=g_modBase+kCatMgrVtRva;
    DWORD start=GetTickCount(); DWORD lastScan=0; DWORD lastHb=0; uint64_t pokes=0; bool jzPatched=false;
    while(GetTickCount()-start < 180000){
        // NOP the `jz false` after the [+0x354] check as soon as the impl page decrypts (74 0C -> 90 90),
        // so IsCatalogDataReady ignores the never-set 5th flag and returns true once the 4 real flags are set.
        if(!jzPatched){
            uint8_t* jz=(uint8_t*)(g_modBase+kJzRva);
            if(SafeReadable(jz,2) && jz[0]==0x74 && jz[1]==0x0C){
                DWORD o=0; if(VirtualProtect(jz,2,PAGE_EXECUTE_READWRITE,&o)){ jz[0]=0x90; jz[1]=0x90; DWORD dd=0; VirtualProtect(jz,2,o,&dd); jzPatched=true; Marker("[patch] IsCatalogDataReady jz NOP'd (ignores +0x354)\r\n"); }
            }
        }
        // find the CatalogManager (once) as soon as its catalog map is populated
        if(!g_catMgr && GetTickCount()-lastScan>=300){
            lastScan=GetTickCount();
            uintptr_t cm=FindCatalogManager(vtabAbs);
            if(cm){ g_catMgr=cm; int32_t mnum=*(int32_t*)(cm+kMapOff+8);
                Markerf("[cm] CatalogManager @0x%llX (map Num=%d)\r\n",(unsigned long long)cm,mnum); }
        }
        // hold IsCatalogDataReady flags set so the grid Construct sees ready==true
        if(g_catMgr && SafeReadable((void*)(g_catMgr+kReadyOff),8)){
            uint8_t* f=(uint8_t*)(g_catMgr+kReadyOff);
            for(int i=0;i<5;i++) if(f[i]==0){ f[i]=1; pokes++; }
        }
        // un-hook slot 110 once the scan has run (keep it long enough to catch the menu-load enum)
        if(!g_unhooked && g_scanState==2 && GetTickCount()-start>=8000){
            DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}g_unhooked=true;Marker("[unhook] slot 110 restored\r\n");
        }
        if(GetTickCount()-lastHb>=5000){Markerf("[hb] scanState=%ld catMgr=0x%llX pokes=%llu unhook=%d\r\n",g_scanState,(unsigned long long)g_catMgr,(unsigned long long)pokes,g_unhooked?1:0);lastHb=GetTickCount();}
        Sleep(15);
    }
    // final: leave flags set; ensure slot restored
    if(!g_unhooked){DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}}
    Markerf("[done] catMgr=0x%llX total pokes=%llu\r\n",(unsigned long long)g_catMgr,(unsigned long long)pokes);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
