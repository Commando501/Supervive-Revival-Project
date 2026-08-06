// ⚠⚠ 2026-08-05 (S111) — DO NOT INJECT THIS WITHOUT PORTING THE SCAN FIX FIRST. ⚠⚠
// Still carries the unguarded-scan defect (1 site) that crash-dump forensics attributed to >=11
// process deaths in catalog_store_fix.dll: `*(uintptr_t*)p` dereferenced with no guard while
// walking a stale VirtualQuery region snapshot. See docs/fk8-crash-timing-mined.md §3.1; the fix
// and its offline control are in catalog_store_fix.cpp and tools/sigbypass-mod/tests/.
//
// catalog_purchasable_fix — POKE TEST for the store browse tabs (BUNDLES/SKINS/ACCESSORIES).
//
// Root cause (RE'd 2026-07-05, docs + memory supervive-store-status): those tabs use the
// generic tile WBP_UI_Storefront_ListItem, whose visibility is gated on the CatalogEntry
// status (CanUse / IsPurchasable / IsHidden / IsDisabled). Store-offer & cosmetic entries
// come back CanUse=0 / IsPurchasable=0 (no offering cost from the dead backend) => the
// tiles collapse (0-height sections, no "No Results"). The offering COST (price) is a
// separate/bigger fix; this shim only tests whether flipping the status flags makes the
// tiles RENDER.
//
// CatalogEntry byte-flag offsets (from disasm of the native getter exec thunks; the
// getters do `movzx eax, byte ptr [rcx+off]`):
//   +0xD0 CanUse   +0xD1 CannotUseReason   +0xD2 IsDisabled   +0xD3 IsHidden
//   +0xD4 IsFree   +0xD5 IsOwned           +0xD6 IsDefault    +0xD7 IsPremiumBenefit
//   +0x118 IsPurchasable
//
// This shim finds the live CatalogManager (vtable == base+0x8831758, catalog map @+0x60
// populated), then loops: for every CatalogEntry in the map set CanUse=1, CannotUseReason=0,
// IsDisabled=0, IsHidden=0, IsPurchasable=1. Pure DATA pokes (no .text patch => no code-
// integrity wall). Loops so the values are set when the store builds its tiles (and re-set
// if the game reprocesses the storefront). Read-only VEH crash logger included.
//
// Build:  clang++ -shared -O2 catalog_purchasable_fix.cpp -o catalog_purchasable_fix.dll -lkernel32
// Inject: tools/inject/inject.exe watch-now SUPERVIVE-Win64-Shipping.exe catalog_purchasable_fix.dll
// Marker: docs/catalog-purchasable-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\catalog-purchasable-marker.txt";

constexpr uintptr_t kCatMgrVtRva = 0x8831758;   // CatalogManager vtable
constexpr uintptr_t kMapOff      = 0x60;         // Catalog map (Data@+0x60, Num@+0x68)
constexpr uintptr_t kOffCanUse   = 0xD0;
constexpr uintptr_t kOffReason   = 0xD1;
constexpr uintptr_t kOffDisabled = 0xD2;
constexpr uintptr_t kOffHidden   = 0xD3;
constexpr uintptr_t kOffFree     = 0xD4;
constexpr uintptr_t kOffOwned    = 0xD5;
constexpr uintptr_t kOffPurch    = 0x118;

static uintptr_t g_modBase = 0, g_modEnd = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}
// A live UObject: its first qword (vtable) points into the module image.
static bool LooksLikeObject(uintptr_t p){ if(!LooksLikePtr(p)||!SafeReadable((void*)p,8)) return false; uintptr_t vt=*(uintptr_t*)p; return vt>=g_modBase && vt<g_modEnd; }

// Scan committed private memory for the live CatalogManager (vtable match, populated map).
static uintptr_t FindCatalogManager(uintptr_t vtabAbs){
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr=(uintptr_t)si.lpMinimumApplicationAddress, maxA=(uintptr_t)si.lpMaximumApplicationAddress;
    while(addr<maxA){
        MEMORY_BASIC_INFORMATION m{}; if(!VirtualQuery((void*)addr,&m,sizeof(m))) break;
        uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;
        bool ok=(m.State&MEM_COMMIT)&&!(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))&&(m.Protect&(PAGE_READWRITE|PAGE_EXECUTE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_WRITECOPY));
        if(ok && m.Type==MEM_PRIVATE){
            uintptr_t base=(uintptr_t)m.BaseAddress, end=base+m.RegionSize;
            for(uintptr_t p=base; p+8<=end; p+=8){
                if(*(uintptr_t*)p==vtabAbs && SafeReadable((void*)(p+kMapOff),16)){
                    uintptr_t md=*(uintptr_t*)(p+kMapOff); int32_t mn=*(int32_t*)(p+kMapOff+8);
                    if(LooksLikePtr(md)&&mn>=50&&mn<=5000) return p;
                }
            }
        }
        if(next<=addr) break; addr=next;
    }
    return 0;
}

// Iterate the Catalog TMap sparse array; poke each valid CatalogEntry. Returns count poked.
static int PokeAll(uintptr_t catMgr){
    if(!SafeReadable((void*)(catMgr+kMapOff),16)) return 0;
    uintptr_t data=*(uintptr_t*)(catMgr+kMapOff); int32_t num=*(int32_t*)(catMgr+kMapOff+8);
    if(!LooksLikePtr(data)||num<=0||num>20000) return 0;
    int poked=0; int scanned=0; int cap=num*3+256;
    for(int i=0;i<cap && poked<num;i++){
        uintptr_t elem=data+(uintptr_t)i*0x20;
        if(!SafeReadable((void*)(elem+0x10),8)) continue;
        uintptr_t entry=*(uintptr_t*)(elem+0x10);
        if(!LooksLikeObject(entry)) continue;   // skip empty/free sparse slots
        if(!SafeReadable((void*)(entry+kOffPurch),1)) continue;
        uint8_t* e=(uint8_t*)entry;
        e[kOffCanUse]=1; e[kOffReason]=0; e[kOffDisabled]=0; e[kOffHidden]=0;
        e[kOffFree]=1; e[kOffOwned]=1; e[kOffPurch]=1;
        poked++;
        (void)scanned;
    }
    return poked;
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] catalog_purchasable_fix worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; g_modEnd=g_modBase+0xC000000;
    uintptr_t vtabAbs=g_modBase+kCatMgrVtRva;
    Markerf("[0] modBase=0x%llX vtabAbs=0x%llX\r\n",(unsigned long long)g_modBase,(unsigned long long)vtabAbs);

    uintptr_t catMgr=0; DWORD start=GetTickCount(); DWORD lastHb=0; uint64_t iters=0; int lastPoked=0;
    // Run ~30 min so the pokes are in place whenever the user opens the store, and re-set
    // if the game reprocesses the storefront.
    while(GetTickCount()-start < 1800000){
        if(!catMgr){
            catMgr=FindCatalogManager(vtabAbs);
            if(catMgr) Markerf("[cm] CatalogManager @0x%llX (mapNum=%d)\r\n",(unsigned long long)catMgr,*(int32_t*)(catMgr+kMapOff+8));
        }
        if(catMgr){ lastPoked=PokeAll(catMgr); iters++; }
        if(GetTickCount()-lastHb>=5000){ Markerf("[hb] catMgr=0x%llX iters=%llu lastPoked=%d\r\n",(unsigned long long)catMgr,(unsigned long long)iters,lastPoked); lastHb=GetTickCount(); }
        Sleep(300);
    }
    Markerf("[done] iters=%llu lastPoked=%d\r\n",(unsigned long long)iters,lastPoked);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
