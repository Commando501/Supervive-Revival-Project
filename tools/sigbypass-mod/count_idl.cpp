// count_idl — DE-RISK probe (session 46): does the ALL HUNTERS grid RE-QUERY the hero
// list every time you open the HUNTERS screen, or is it built once at menu-load and cached?
//
// The grid's Blueprint (BPFL_LokiAssets::Get Heroes Asset List Sorted) calls native
// GetHeroCharacterList, which calls UAssetManager::GetPrimaryAssetIdList(Hero) exactly once
// per list build. So: hook GetPrimaryAssetIdList (LokiAssetManager vtable slot 110) via a
// vtable-slot swap (clean, no .text patch) and LOG every Hero call with a timestamp +
// running counter. Do NOT scan (the target already ran its scan, enum=25) and do NOT unhook
// (we want to keep counting across navigations).
//
// Test procedure: inject into the running (scanned) client, then in the game:
//   HUNTERS -> (back) -> some other tab -> HUNTERS -> ...
// and read docs/count-idl-marker.txt. If the Hero counter INCREMENTS each time HUNTERS is
// opened, the grid re-queries per navigation => a post-hoc asset LOAD + re-open will populate
// it (no relaunch needed). If it stays flat after the first build, the list is cached at
// menu-load => the load must happen EARLY (before menu-load), i.e. relaunch + early inject.
//
// Offsets (this build; base moves with ASLR, RVAs stable):
//   LokiAssetManager vtable = RVA +0x888CB78 ; slot 110 = GetPrimaryAssetIdList
//   GGameThreadId slot      = RVA +0x9D49158 ; Hero FName id 0x1A568
//
// Build:  clang++ -shared -O2 count_idl.cpp -o count_idl.dll -lkernel32
// Inject: tools/inject mmap SUPERVIVE-Win64-Shipping.exe count_idl.dll   (into running proc)
// Marker: docs/count-idl-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\count-idl-marker.txt";

constexpr uintptr_t kVtRva       = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kGGameTidRva = 0x9D49158;
constexpr int       SLOT_IDL     = 110;         // GetPrimaryAssetIdList
constexpr uint32_t  kHeroFName   = 0x1A568;

static uintptr_t g_modBase = 0;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_heroCount = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLogBuf=64*1024; static char g_log[kLogBuf]; static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLogf(const char* f,...){char b[256];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}

// PRE handler: no-op (the target already scanned; we only want to COUNT).
extern "C" void h_idl_pre(uintptr_t, uintptr_t, uintptr_t, uintptr_t) {}
// POST handler: on each Hero call, bump the counter + log time + returned Num.
extern "C" void h_idl_post(uintptr_t /*rcx*/, uintptr_t rdx, uintptr_t r8, uintptr_t /*r9*/) {
    if ((uint32_t)(rdx & 0xFFFFFFFF) != kHeroFName) return;
    int32_t num = SafeReadable((void*)(r8+8),4) ? *(int32_t*)(r8+8) : -1;
    long n = InterlockedIncrement(&g_heroCount);
    RingLogf("[idl] Hero call #%ld  t=%lu ms  returned Num=%d\r\n", n, GetTickCount(), num);
}

// WRAP stub: pre -> original -> post -> ret (rcx/rdx/r8/r9 saved+reloaded around each call).
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
    *w++=0x48;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x40;             // mov [rsp+0x40],rax
    reload();
    *w++=0x48;*w++=0xB8; uint64_t sf=(uint64_t)post; memcpy(w,&sf,8); w+=8; *w++=0xFF;*w++=0xD0; // call post
    *w++=0x48;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x40;             // mov rax,[rsp+0x40]
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x48;                       // add rsp,0x48
    *w++=0xC3;                                                     // ret
    return p;
}

static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] count_idl worker started\r\n");
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
    Markerf("[3] GetPrimaryAssetIdList hooked (orig=0x%llX stub=%p) — NAVIGATE HUNTERS now\r\n",
            (unsigned long long)g_origIdl,(void*)g_stubIdl);

    // IMPORTANT: a left-in-place hook (even a vtable-slot swap) trips this build's periodic
    // code-integrity check ~3-5 min in and crashes the client (session-43 finding). So
    // self-UNHOOK after a bounded window — long enough to do a few HUNTERS navigations, short
    // enough to stay well under the integrity deadline. (Session 46: forgetting this crashed
    // the client mid-test.)
    const DWORD kUnhookAfterMs = 90000;
    DWORD installedAt=GetTickCount(); bool unhooked=false;
    LONG64 flushed=0; DWORD hb=GetTickCount();
    while(true){
        Sleep(150);
        if(!unhooked && GetTickCount()-installedAt>=kUnhookAfterMs){
            DWORD o=0; if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}
            unhooked=true; Marker("[unhook] slot 110 restored (integrity-safe); counting stopped\r\n");
        }
        LONG64 head=g_head; if(head>(LONG64)sizeof(g_log))head=(LONG64)sizeof(g_log);
        if(head>flushed){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_log+flushed,(DWORD)(head-flushed),&w,nullptr);CloseHandle(f);flushed=head;}}
        if(GetTickCount()-hb>=5000){Markerf("[hb] heroCount=%ld unhooked=%d\r\n",g_heroCount,unhooked?1:0);hb=GetTickCount();}
    }
}

BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
