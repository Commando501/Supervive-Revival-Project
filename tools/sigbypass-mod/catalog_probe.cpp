// catalog_probe — session 46 attempt #2 diagnostic: capture the map that
// GetHeroAssetFromPrimaryAssetId actually searches (rsi = *(Singleton+0x210)) and dump it, to
// decide WHY heroes are rejected: is the hero id NOT in that map (map-miss), or is it present but
// its CatalogEntry has the [entry+0xc] bit30 flag set (entry-flag)?
//
// The resolver GetHeroAssetFromPrimaryAssetId (+0x562E9F6) computes rsi at +0x562EA51:
//   call +0x149D770   ; = `mov rax,[rcx+0x210]; ret`  -> rax = rsi (the CatalogManager sub-object)
//   mov rsi, rax                                        (+0x562EA56)
// then searches rsi's embedded TMap (Data@rsi+0x30, Num@rsi+0x38, stride 0x20: key FPrimaryAssetId@0,
// value CatalogEntry*@+0x10). We JIT-patch the E8 rel32 at +0x562EA51 to a capture stub that calls the
// real +0x149D770, records rax(=rsi) once, and returns it — same technique as S45's probe_r14 (the
// .text region is packer-decrypted by scan time, so the patch persists through the menu-load grid
// build). The worker then dumps rsi + its map (Num + first entries' key.Name FName id + value +
// [value+0xc]) to docs/catalog-probe-marker.txt, and UN-patches + UN-hooks (integrity-safe).
//
// Build:  clang++ -shared -O2 catalog_probe.cpp -o catalog_probe.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe catalog_probe.dll 0x3EC57D0 40555356574154415541564157
// Marker: docs/catalog-probe-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\catalog-probe-marker.txt";

constexpr uintptr_t kVtRva        = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva      = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr uintptr_t kTypeMapOff   = 0x478;
constexpr uintptr_t kInfoBaseOff  = 0x30;
constexpr uintptr_t kInfoPathsOff = 0x70;
constexpr int       SLOT_IDL      = 110;
constexpr uint32_t  kHeroFName    = 0x1A568;
constexpr uintptr_t kCallSiteRva  = 0x562EA51;   // the `call +0x149D770` (E8 rel32) inside the resolver
constexpr uintptr_t kGetterRva    = 0x149D770;   // mov rax,[rcx+0x210]; ret  -> returns rsi

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);
struct TArr { void* Data; int32_t Num; int32_t Max; };

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_scanState = 0;
static volatile bool g_unhooked = false;
static volatile uintptr_t g_rsi = 0;             // captured by the JIT stub
static uint8_t*  g_capStub = nullptr;
static uint8_t   g_origCall[5] = {0};            // saved E8 rel32 bytes
static volatile bool g_patched = false;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLogBuf=64*1024; static char g_log[kLogBuf]; static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLog(const char* s){RingAppend(s,(int)strlen(s));}
static void RingLogf(const char* f,...){char b[256];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

static void RunScanForAllTypes(void* manager){
    const uint8_t* mgr=(const uint8_t*)manager;
    if(!SafeReadable(mgr+kTypeMapOff,16)){RingLog("[scan] typemap unreadable\r\n");return;}
    uintptr_t data=*(const uintptr_t*)(mgr+kTypeMapOff);
    uint32_t mx=*(const uint32_t*)(mgr+kTypeMapOff+12);
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

// Allocate executable memory WITHIN +-2GB of `near` so a `call rel32` from the patched site can
// reach it (plain VirtualAlloc lands ~29GB away -> the E8 rel32 wraps -> jump to garbage -> crash;
// this was the bug that crashed the client 3x). Scan pages outward from `near`.
static uint8_t* NearAlloc(uintptr_t anchor, size_t sz){
    for(uintptr_t off=0x10000; off<0x7F000000ull; off+=0x10000){
        uintptr_t cands[2]={ (anchor+off)&~0xFFFFull, (anchor>off ? (anchor-off) : 0)&~0xFFFFull };
        for(int i=0;i<2;i++){
            if(!cands[i]) continue;
            void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
            if(p){ intptr_t d=(intptr_t)p-(intptr_t)anchor; if(d>(intptr_t)-0x7F000000 && d<(intptr_t)0x7F000000) return (uint8_t*)p; VirtualFree(p,0,MEM_RELEASE); }
        }
    }
    return nullptr;
}

// Build the capture stub: rcx = the Singleton (arg to the getter). Call the real getter, record its
// result (rax = rsi) once, return rax. Clobbers only r10/flags (caller only consumes rax next).
static uint8_t* BuildCaptureStub(uintptr_t getterAbs, volatile uintptr_t* rsiSlot){
    uint8_t* p=NearAlloc(g_modBase+kCallSiteRva,0x80);   // within +-2GB of the patched call site
    if(!p)return nullptr; uint8_t* w=p;
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x28;                         // sub rsp,0x28
    *w++=0x48;*w++=0xB8; uint64_t g=(uint64_t)getterAbs; memcpy(w,&g,8); w+=8;  // mov rax, getter
    *w++=0xFF;*w++=0xD0;                                             // call rax  -> rax=rsi (rcx passed thru)
    *w++=0x49;*w++=0xBA; uint64_t s=(uint64_t)rsiSlot; memcpy(w,&s,8); w+=8;     // mov r10, &g_rsi
    *w++=0x49;*w++=0x83;*w++=0x3A;*w++=0x00;                         // cmp qword [r10],0
    *w++=0x75;*w++=0x03;                                             // jnz +3 (skip store)
    *w++=0x49;*w++=0x89;*w++=0x02;                                   // mov [r10], rax
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x28;                         // add rsp,0x28
    *w++=0xC3;                                                       // ret
    return p;
}

extern "C" void h_idl_pre(uintptr_t rcx, uintptr_t, uintptr_t, uintptr_t){
    if(InterlockedCompareExchange(&g_scanState,1,0)!=0) return;
    RingLogf("[enum] first GetPrimaryAssetIdList -> scan (mgr=0x%llX)\r\n",(unsigned long long)rcx);
    g_scan=(PFN_Scan)(g_modBase+kScanRva);
    RunScanForAllTypes((void*)rcx);
    InterlockedExchange(&g_scanState,2);
}
// At MENU-LOAD, GetPrimaryAssetIdList(Hero) is called by GetHeroCharacterList, which runs on the SAME
// +0x562E page as the resolver — so the page is packer-decrypted right now, and this fires BEFORE the
// per-hero GetHeroAssetFromPrimaryAssetId calls. Patch the resolver's +0x562EA51 call site here.
static volatile long g_resolverPatched = 0;
extern "C" void h_idl_post(uintptr_t, uintptr_t rdx, uintptr_t, uintptr_t){
    if((uint32_t)(rdx&0xFFFFFFFF)!=kHeroFName) return;
    if(InterlockedCompareExchange(&g_resolverPatched,1,0)!=0) return;   // once
    uint8_t* site=(uint8_t*)(g_modBase+kCallSiteRva);
    if(!SafeReadable(site,5) || site[0]!=0xE8){ RingLog("[patch] Hero call but +0x562EA51 still not E8\r\n"); InterlockedExchange(&g_resolverPatched,0); return; }
    g_capStub=BuildCaptureStub(g_modBase+kGetterRva,&g_rsi);
    if(!g_capStub) return;
    int32_t newRel=(int32_t)((intptr_t)g_capStub-((intptr_t)site+5));
    DWORD op=0;
    if(VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&op)){
        memcpy(g_origCall,site,5);
        site[1]=(uint8_t)newRel; site[2]=(uint8_t)(newRel>>8); site[3]=(uint8_t)(newRel>>16); site[4]=(uint8_t)(newRel>>24);
        DWORD d=0; VirtualProtect(site,5,op,&d);
        g_patched=true;
        RingLogf("[patch] resolver +0x562EA51 patched at Hero call -> capStub %p\r\n",(void*)g_capStub);
    }
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

// Dump the rsi map: Num, then walk the sparse array (stride 0x20; key.Name @+8, value @+0x10, and the
// entry's [value+0xc] flag). Also print rsi's own flags [rsi+0xc].
static void DumpRsiMap(){
    uintptr_t rsi=g_rsi;
    if(!SafeReadable((void*)rsi,0x80)){RingLogf("[dump] rsi=0x%llX unreadable\r\n",(unsigned long long)rsi);return;}
    uint32_t rsiFlags=*(uint32_t*)(rsi+0xc);
    uintptr_t data=*(uintptr_t*)(rsi+0x30);
    int32_t num=*(int32_t*)(rsi+0x38);
    RingLogf("[dump] rsi=0x%llX [rsi+0xc]flags=0x%X map{Data=0x%llX Num=%d}\r\n",
             (unsigned long long)rsi,rsiFlags,(unsigned long long)data,num);
    if(!LooksLikePtr(data)||num<=0||num>20000){RingLog("[dump] map empty or bad -> heroes NOT in this map (map-miss reject)\r\n");return;}
    int shown=0;
    for(int32_t i=0;i<num+64 && shown<12;i++){
        const uint8_t* e=(const uint8_t*)data+(uintptr_t)i*0x20;
        if(!SafeReadable(e,0x18))break;
        uint32_t keyType=*(const uint32_t*)(e+0);     // FPrimaryAssetType FName index
        uint32_t keyName=*(const uint32_t*)(e+8);     // PrimaryAssetName FName index
        uintptr_t val=*(const uintptr_t*)(e+0x10);
        if(keyType==0 && keyName==0) continue;         // free slot
        uint32_t vflag=(LooksLikePtr(val)&&SafeReadable((void*)(val+0xc),4))?*(uint32_t*)(val+0xc):0xDEAD;
        RingLogf("[dump]  [%d] key.Type=0x%X key.Name=0x%X val=0x%llX [val+0xc]=0x%X\r\n",
                 i,keyType,keyName,(unsigned long long)val,vflag);
        shown++;
    }
    RingLogf("[dump] shown %d entries (Hero FName type id=0x%X)\r\n",shown,kHeroFName);
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] catalog_probe worker started\r\n");
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
    Marker("[3] GetPrimaryAssetIdList hooked\r\n");

    LONG64 flushed=0; DWORD hb=GetTickCount(); DWORD hb0=GetTickCount(); bool dumped=false; DWORD rsiAt=0;
    while(true){
        Sleep(150);
        // once rsi captured, wait a beat then dump + un-patch + un-hook
        if(g_rsi && !dumped){
            if(rsiAt==0) rsiAt=GetTickCount();
            else if(GetTickCount()-rsiAt>=800){
                DumpRsiMap();
                // un-patch the resolver call site
                if(g_patched){uint8_t* site=(uint8_t*)(g_modBase+kCallSiteRva);DWORD o=0;if(VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&o)){memcpy(site,g_origCall,5);DWORD dd=0;VirtualProtect(site,5,o,&dd);}Marker("[unpatch] resolver call site restored\r\n");}
                dumped=true;
            }
        }
        // Keep the vtable hook until the resolver patch has fired at menu-load (h_idl_post patches on
        // the Hero call). Un-hook once dumped, OR as a safety after 150s (well under the integrity wall).
        if(!g_unhooked && (dumped || GetTickCount()-hb0>=150000)){
            DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}g_unhooked=true;Marker("[unhook] slot 110 restored\r\n");
        }
        LONG64 head=g_head; if(head>(LONG64)sizeof(g_log))head=(LONG64)sizeof(g_log);
        if(head>flushed){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_log+flushed,(DWORD)(head-flushed),&w,nullptr);CloseHandle(f);flushed=head;}}
        if(GetTickCount()-hb>=5000){Markerf("[hb] scanState=%ld rsi=0x%llX dumped=%d\r\n",g_scanState,(unsigned long long)g_rsi,dumped?1:0);hb=GetTickCount();}
    }
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
