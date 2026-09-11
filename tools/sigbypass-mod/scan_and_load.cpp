// scan_and_load — session 46 FIX attempt: scan the AssetManager (so Hero enumerates 25) AND
// then LOAD the 25 hero primary-asset OBJECTS, early, so GetHeroAssetFromPrimaryAssetId resolves
// them (OutputExecs==0) and the ALL HUNTERS grid's Blueprint keeps them instead of dropping all.
//
// Root cause (session 46, read from BP bytecode + native disasm): the grid's BP
// (BPFL_LokiAssets::Get Heroes Asset List Sorted) enumerates Hero ids (GetPrimaryAssetIdList=25
// with the scan) then per id calls native GetHeroAssetFromPrimaryAssetId, which sets OutputExecs=1
// (REJECT) by default and only 0 (KEEP) if the id resolves to a LOADED object. The heroes never
// load, so all 25 are dropped -> empty grid. Fix = load the hero objects before the grid builds.
//
// Mechanism: identical to scan_on_enum (hook GetPrimaryAssetIdList slot 110, first call = scan all
// 30 types on the game thread, then un-hook). ADDED: right after the scan, on the SAME game-thread
// call, (1) call the ORIGINAL GetPrimaryAssetIdList(Hero) to get the 25 FPrimaryAssetIds into our
// own TArray, then (2) call UAssetManager::ChangeBundleStateForPrimaryAssets(ids, {}, {}, false,
// {}, 0) to async-load them. Fired at the FIRST GetPrimaryAssetIdList (initial asset load), well
// before menu-load builds the grid, so the async load has time to complete.
//
// ChangeBundleStateForPrimaryAssets convention (session-46 disasm of +0x34AF2A0):
//   rcx=this, rdx=&TSharedPtr<FStreamableHandle> retval (zeroed at entry), r8=&AssetsToChange
//   (TArray<FPrimaryAssetId>, 16-byte elems), r9=&AddBundles (TArray<FName>), then stack:
//   &RemoveBundles, bRemoveAllBundles(bool), &DelegateToCall(FStreamableDelegate 16B), Priority(i32).
//   => a plain free-function typedef with (self, retval, assets, addB, remB, removeAll, deleg, prio)
//   lands each arg in the right register/stack slot under MSVC x64, no hand stub needed.
//
// Build:  clang++ -shared -O2 scan_and_load.cpp -o scan_and_load.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe scan_and_load.dll 0x3EC57D0 40555356574154415541564157
// Marker: docs/scan-and-load-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\scan-and-load-marker.txt";

constexpr uintptr_t kVtRva        = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva      = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kChangeBundle = 0x34AF2A0;   // ChangeBundleStateForPrimaryAssets (slot 119)
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr uintptr_t kTypeMapOff   = 0x478;
constexpr uintptr_t kInfoBaseOff  = 0x30;
constexpr uintptr_t kInfoPathsOff = 0x70;
constexpr int       SLOT_IDL      = 110;         // GetPrimaryAssetIdList
constexpr uint32_t  kHeroFName    = 0x1A568;
constexpr uintptr_t kNamePoolRva  = 0x9D81450;   // &FNamePool.Blocks[0] (Len10 layout)
constexpr uint32_t  kClientGlobalId = 0x4CA778;  // FName "ClientGlobal" — the hero MENU bundle
                                                 // (verified at runtime below; heroes' bundles are
                                                 //  {ClientGlobal, Game}; ClientGlobal = client display)

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);
// GetPrimaryAssetIdList(this, FPrimaryAssetType(8B), TArray<FPrimaryAssetId>& out, EAssetManagerFilter)
typedef void    (*PFN_GetIdList)(void*, uint64_t, void*, int32_t);
// ChangeBundleStateForPrimaryAssets — see header note for the arg->slot mapping.
typedef void    (*PFN_ChangeBundle)(void* self, void* retval, void* assets, void* addB,
                                    void* remB, bool removeAll, void* deleg, int32_t prio);

struct TArr { void* Data; int32_t Num; int32_t Max; };

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static void*     g_manager = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_scanState = 0;
static volatile bool g_unhooked = false;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLogBuf=64*1024; static char g_log[kLogBuf]; static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLog(const char* s){RingAppend(s,(int)strlen(s));}
static void RingLogf(const char* f,...){char b[256];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

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

// Resolve an ANSI name to its FName id by SEARCHING the FNamePool at runtime. FName ids drift
// between runs (verified S46: ClientGlobal was 0x4CA778 one run, 0x4C9E51 the next), so hardcoding
// is unsafe — we must look it up live. Len10 header: bit0=bIsWide, bits1-5=probehash, bits6-15=Len.
// Blocks[] at base+kNamePoolRva; each block packs entries [2B header][string], 2-byte aligned.
static uint32_t FindFName(const char* target) {
    int tlen = 0; while(target[tlen]) tlen++;
    uintptr_t* blocks = (uintptr_t*)(g_modBase + kNamePoolRva);
    for(uint32_t b=0; b<128; b++){
        if(!SafeReadable(blocks+b, 8)) break;
        uintptr_t bp = blocks[b];
        if(!LooksLikePtr(bp)) continue;
        uint32_t off = 0;
        while(off < 0x1FFF0){
            if(!SafeReadable((void*)(bp+off), 2)) break;
            uint16_t hdr = *(uint16_t*)(bp+off);
            int len = hdr >> 6;
            bool wide = (hdr & 1) != 0;
            if(len == 0) break;                       // end of used region in this block
            int strbytes = wide ? len*2 : len;
            if(!SafeReadable((void*)(bp+off+2), strbytes)) break;
            if(!wide && len == tlen){
                const char* s = (const char*)(bp+off+2);
                bool eq=true; for(int i=0;i<tlen;i++){ if(s[i]!=target[i]){eq=false;break;} }
                if(eq) return (b << 16) | (off >> 1);
            }
            int adv = 2 + strbytes; adv = (adv + 1) & ~1;   // 2-byte align to next entry
            off += (uint32_t)adv;
        }
    }
    return 0;
}

// After the scan: get the 25 Hero ids via the ORIGINAL GetPrimaryAssetIdList, then load their
// ClientGlobal bundle (which pulls in the base LokiHeroAsset object the grid's resolver needs).
static void DoHeroLoad(void* manager) {
    if(!manager || !g_origIdl){RingLog("[load] no manager/origIdl\r\n");return;}
    PFN_GetIdList getIdList = (PFN_GetIdList)g_origIdl;
    TArr heroIds = {nullptr,0,0};
    getIdList(manager, (uint64_t)kHeroFName, &heroIds, 0);   // EAssetManagerFilter::Default = 0
    RingLogf("[load] GetPrimaryAssetIdList(Hero) -> Num=%d (data=%p)\r\n", heroIds.Num, heroIds.Data);
    if(heroIds.Num <= 0 || !heroIds.Data){RingLog("[load] no hero ids; skip load\r\n");return;}

    // Resolve the hero bundle FNames LIVE (ids drift per run). Request BOTH ClientGlobal (client
    // display) and Game (gameplay content) to force the full hero asset load.
    uint32_t cgId = FindFName("ClientGlobal");
    uint32_t gmId = FindFName("Game");
    RingLogf("[load] FindFName -> ClientGlobal=0x%X Game=0x%X\r\n", cgId, gmId);
    if(cgId == 0){ RingLog("[load] FATAL: ClientGlobal not found in pool; aborting load\r\n"); return; }
    uint64_t bundleFNames[2] = { (uint64_t)cgId, (uint64_t)gmId };
    int nBundles = (gmId != 0) ? 2 : 1;
    TArr addBundles = { bundleFNames, nBundles, nBundles };
    TArr emptyRem   = {nullptr,0,0};
    uint8_t retBuf[16] = {0};   // TSharedPtr<FStreamableHandle> out — leaked on purpose (pins the load)
    uint8_t deleg[16]  = {0};   // unbound FStreamableDelegate
    PFN_ChangeBundle chg = (PFN_ChangeBundle)(g_modBase + kChangeBundle);
    RingLogf("[load] ChangeBundleStateForPrimaryAssets(%d Hero ids, add={ClientGlobal}, rem={}, false, {}, 0)\r\n", heroIds.Num);
    chg(manager, retBuf, &heroIds, &addBundles, &emptyRem, false, deleg, 0);
    uintptr_t handle = *(uintptr_t*)retBuf;
    RingLogf("[load] ChangeBundleState returned; handle=0x%llX %s\r\n",
             (unsigned long long)handle, handle ? "(streaming started)" : "(null - no-op/already loaded)");
}

extern "C" void h_idl_pre(uintptr_t rcx, uintptr_t, uintptr_t, uintptr_t) {
    if (InterlockedCompareExchange(&g_scanState,1,0)!=0) return;
    RingLogf("[enum] first GetPrimaryAssetIdList call -> scan+load (mgr=0x%llX)\r\n",(unsigned long long)rcx);
    g_manager=(void*)rcx;
    g_scan=(PFN_Scan)(g_modBase+kScanRva);
    RunScanForAllTypes((void*)rcx);
    DoHeroLoad((void*)rcx);           // <-- the fix: load the hero objects right after the scan
    InterlockedExchange(&g_scanState,2);
    RingLog("[enum] scan+load complete\r\n");
}
static volatile long g_heroLogged = 0;
extern "C" void h_idl_post(uintptr_t, uintptr_t rdx, uintptr_t r8, uintptr_t) {
    if ((uint32_t)(rdx & 0xFFFFFFFF) != kHeroFName) return;
    if (!SafeReadable((void*)(r8+8),4)) return;
    int32_t num = *(int32_t*)(r8+8);
    if (InterlockedExchange(&g_heroLogged,1)==0 || (num>0))
        RingLogf("[enum] GetPrimaryAssetIdList(Hero) returned Num=%d\r\n", num);
}

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

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] scan_and_load worker started\r\n");
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
