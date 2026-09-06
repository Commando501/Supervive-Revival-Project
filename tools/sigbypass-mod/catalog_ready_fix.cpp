// ⚠⚠ 2026-08-05 (S111) — DO NOT INJECT THIS WITHOUT PORTING THE SCAN FIX FIRST. ⚠⚠
// This file still carries the unguarded-scan defect that was killing the game from
// catalog_store_fix.dll: `if(*(uintptr_t*)p==vtabAbs && SafeReadable(...))` dereferences p with no
// guard at all, walking a stale whole-region VirtualQuery snapshot (2 sites here). Crash-dump
// forensics attributed >=11 process deaths to the identical code in catalog_store_fix
// (docs/fk8-crash-timing-mined.md §3.1). It is NOT in the default injection set, which is the only
// reason it has not been killing runs too. The fix + an offline control that reproduces the crash
// are in catalog_store_fix.cpp (ScanPrivateForQword / SafeCopy) and tools/sigbypass-mod/tests/.
//
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
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\catalog-ready-fix-marker.txt";
static const char* kCrashPath =
    "G:\\git\\Supervive Revival Project\\docs\\catalog-ready-fix-crash.txt";

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

// ─────────── read-only VEH crash logger (adapted from scan_on_enum_veh) ───────────
// Capture the faulting RIP / SUPERVIVE RVA / module / registers / stack band into
// docs/catalog-ready-fix-crash.txt before Sentry kills the process, to pin WHERE opening the
// catalog-ready gate crashes (D3D12/RHI render wall vs a content-load path). CONTINUE_SEARCH only.
struct ModRange { uint64_t base, end; char name[64]; };
static ModRange g_mods[192];
static volatile long g_modCount = 0;
static volatile long g_crashSeq = 0;
static void SnapshotModules(){
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());
    if(snap==INVALID_HANDLE_VALUE)return; MODULEENTRY32 me; me.dwSize=sizeof(me); int n=0;
    if(Module32First(snap,&me)){ do{ if(n>=192)break; ModRange&r=g_mods[n];
        r.base=(uint64_t)me.modBaseAddr; r.end=r.base+me.modBaseSize;
        int i=0; for(;i<63&&me.szModule[i];i++)r.name[i]=(char)me.szModule[i]; r.name[i]=0; n++;
    }while(Module32Next(snap,&me)); }
    CloseHandle(snap); InterlockedExchange(&g_modCount,n);
}
static void HxU64(char* o,uint64_t v){const char* d="0123456789ABCDEF";for(int i=15;i>=0;i--){o[i]=d[(int)(v&0xF)];v>>=4;}}
static void CWrite(HANDLE h,const char* s,DWORD n){DWORD w=0;WriteFile(h,s,n,&w,0);}
static void CKV(HANDLE h,const char* k,uint64_t v){char b[96];int p=0;while(k[p]&&p<40){b[p]=k[p];p++;}b[p++]='=';b[p++]='0';b[p++]='x';HxU64(b+p,v);p+=16;b[p++]='\r';b[p++]='\n';CWrite(h,b,(DWORD)p);}
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode;
    bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0x80000003||code==0xC0000374||code==0xC00000FD||code==0xC0000094||code==0xC0000095||code==0xC0000096;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH;
    long seq=InterlockedIncrement(&g_crashSeq); if(seq>64)return EXCEPTION_CONTINUE_SEARCH;
    HANDLE h=CreateFileA(kCrashPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE)return EXCEPTION_CONTINUE_SEARCH;
    CWrite(h,"=== VEH fatal exception ===\r\n",29);
    CKV(h,"seq",(uint64_t)seq); CKV(h,"code",code);
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip; CKV(h,"RIP",rip);
    if(g_modBase && rip>g_modBase && rip<g_modBase+0xC000000) CKV(h,"SUPERVIVE_RVA",rip-g_modBase);
    long mc=g_modCount; bool named=false;
    for(long i=0;i<mc;i++){ if(rip>=g_mods[i].base && rip<g_mods[i].end){ CWrite(h,"module=",7); CWrite(h,g_mods[i].name,(DWORD)strlen(g_mods[i].name)); CWrite(h,"\r\n",2); CKV(h,"module_RVA",rip-g_mods[i].base); named=true; break; } }
    if(!named)CWrite(h,"module=UNKNOWN\r\n",16);
    if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2){ CKV(h,"av_op",ep->ExceptionRecord->ExceptionInformation[0]); CKV(h,"av_addr",ep->ExceptionRecord->ExceptionInformation[1]); }
    CKV(h,"Rax",c->Rax);CKV(h,"Rbx",c->Rbx);CKV(h,"Rcx",c->Rcx);CKV(h,"Rdx",c->Rdx);CKV(h,"Rsi",c->Rsi);CKV(h,"Rdi",c->Rdi);CKV(h,"R8",c->R8);CKV(h,"R9",c->R9);CKV(h,"R10",c->R10);CKV(h,"R11",c->R11);CKV(h,"Rsp",c->Rsp);CKV(h,"Rbp",c->Rbp);
    uint64_t base=g_modBase, top=g_modBase+0xC000000; uint64_t* sp=(uint64_t*)c->Rsp; int found=0;
    for(int i=0;i<800 && found<40;i++){ if(!SafeReadable(sp+i,8))break; uint64_t v=sp[i]; if(base && v>base && v<top){ CKV(h,"stkRVA",v-base); found++; } }
    CWrite(h,"=== end ===\r\n\r\n",15); FlushFileBuffers(h); CloseHandle(h);
    return EXCEPTION_CONTINUE_SEARCH;
}

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

// Scan committed private memory for ALL CatalogManager instances (vtable==target) — including the CDO
// and the live subsystem instance BEFORE its catalog map fills. We want them EARLY (before the catalog
// finishes loading) so we can pre-set the 5th ready-flag [+0x354]=1; then when the game finishes the 4
// real categories and checks readiness, all 5 are set and it BROADCASTS OnCatalogDataReady naturally
// (no .text patch => no code-integrity crash). Fills `out[]` (cap N), returns count.
static int FindCatalogManagers(uintptr_t vtabAbs, uintptr_t* out, int cap){
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr=(uintptr_t)si.lpMinimumApplicationAddress;
    uintptr_t maxA=(uintptr_t)si.lpMaximumApplicationAddress; int n=0;
    while(addr<maxA && n<cap){
        MEMORY_BASIC_INFORMATION m{};
        if(!VirtualQuery((void*)addr,&m,sizeof(m))) break;
        uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;
        bool ok = (m.State&MEM_COMMIT) && !(m.Protect&(PAGE_NOACCESS|PAGE_GUARD)) &&
                  (m.Protect&(PAGE_READWRITE|PAGE_EXECUTE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_WRITECOPY));
        if(ok && m.Type==MEM_PRIVATE){
            uintptr_t base=(uintptr_t)m.BaseAddress; uintptr_t end=base+m.RegionSize;
            for(uintptr_t p=base; p+8<=end && n<cap; p+=8){
                if(*(uintptr_t*)p==vtabAbs && SafeReadable((void*)(p+kReadyOff),8)){
                    bool dup=false; for(int i=0;i<n;i++) if(out[i]==p){dup=true;break;}
                    if(!dup) out[n++]=p;
                }
            }
        }
        if(next<=addr) break; addr=next;
    }
    return n;
}

// Find the ONE live CatalogManager (vtable match whose +0x60 catalog map is populated). Returns 0 until
// the catalog has loaded. Used only to detect "catalog loaded" for restore timing (find-once, then stop).
static uintptr_t FindCatalogManagers_first(uintptr_t vtabAbs){
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

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] catalog_ready_fix worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);
    { HANDLE ch=CreateFileA(kCrashPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    SnapshotModules();
    AddVectoredExceptionHandler(1,CrashVEH);
    Marker("[0] crash-VEH installed\r\n");
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
    DWORD start=GetTickCount(); DWORD lastScan=0; DWORD lastHb=0; uint64_t pokes=0;
    bool jzPatched=false; uint8_t origJz[2]={0}; bool jzRestored=false; DWORD catLoadedAt=0;
    // PROVEN jz-patch (grid builds) + SELF-RESTORE: NOP the `jz` after the [+0x354] check so IsCatalogDataReady
    // ignores the never-set 5th flag and returns true once the 4 real flags set -> the game broadcasts
    // OnCatalogDataReady -> the grid builds. Then, shortly after the catalog has loaded + broadcast fired,
    // RESTORE the jz (74 0C) so the persistent .text mod is gone before the ~3-5min code-integrity check.
    while(GetTickCount()-start < 240000){
        if(!jzPatched){
            uint8_t* jz=(uint8_t*)(g_modBase+kJzRva);
            if(SafeReadable(jz,2) && jz[0]==0x74 && jz[1]==0x0C){
                DWORD o=0; if(VirtualProtect(jz,2,PAGE_EXECUTE_READWRITE,&o)){ origJz[0]=jz[0]; origJz[1]=jz[1]; jz[0]=0x90; jz[1]=0x90; DWORD dd=0; VirtualProtect(jz,2,o,&dd); jzPatched=true; Marker("[patch] jz NOP'd (IsCatalogDataReady ignores +0x354)\r\n"); }
            }
        }
        // find the live CatalogManager once (map populated = catalog loaded => broadcast has fired w/ the patch)
        if(!g_catMgr && GetTickCount()-lastScan>=400){
            lastScan=GetTickCount();
            uintptr_t cm=FindCatalogManagers_first(vtabAbs);
            if(cm){ g_catMgr=cm; catLoadedAt=GetTickCount(); int32_t mnum=*(int32_t*)(cm+kMapOff+8);
                Markerf("[cm] live CatalogManager @0x%llX (map Num=%d) — catalog loaded\r\n",(unsigned long long)cm,mnum); }
        }
        // belt-and-suspenders data poke of [+0x354]=1 on the live instance (harmless; helps if the game re-checks)
        if(g_catMgr && SafeReadable((void*)(g_catMgr+kReadyOff),8)){
            uint8_t* f=(uint8_t*)(g_catMgr+kReadyOff); if(f[4]==0){ f[4]=1; pokes++; } }
        // ~6s after the catalog loaded (grid has built), RESTORE the jz so no persistent .text mod remains.
        if(jzPatched && !jzRestored && catLoadedAt && GetTickCount()-catLoadedAt>=6000){
            uint8_t* jz=(uint8_t*)(g_modBase+kJzRva); DWORD o=0;
            if(VirtualProtect(jz,2,PAGE_EXECUTE_READWRITE,&o)){ jz[0]=origJz[0]; jz[1]=origJz[1]; DWORD dd=0; VirtualProtect(jz,2,o,&dd); jzRestored=true; Marker("[restore] jz restored (no persistent .text mod)\r\n"); }
        }
        if(!g_unhooked && g_scanState==2 && GetTickCount()-start>=8000){
            DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}g_unhooked=true;Marker("[unhook] slot 110 restored\r\n");
        }
        if(GetTickCount()-lastHb>=5000){Markerf("[hb] scanState=%ld catMgr=0x%llX pokes=%llu jz=%d/%d unhook=%d\r\n",g_scanState,(unsigned long long)g_catMgr,(unsigned long long)pokes,jzPatched?1:0,jzRestored?1:0,g_unhooked?1:0);lastHb=GetTickCount();}
        Sleep(15);
    }
    if(!g_unhooked){DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}}
    Markerf("[done] catMgr=0x%llX pokes=%llu jzRestored=%d\r\n",(unsigned long long)g_catMgr,(unsigned long long)pokes,jzRestored?1:0);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
