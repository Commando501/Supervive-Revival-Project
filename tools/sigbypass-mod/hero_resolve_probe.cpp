// hero_resolve_probe (v2, SAFE keep-set capture) — session 47 decisive diagnostic.
// v1 tried an entry-detour WRAPPER (call the resolver as a black box, read RAX after). It CRASHED the
// game at menu-load 2/2, while the identical scan-only control survived => the resolver's frame is
// non-standard and cannot be black-box-wrapped. v2 instead uses a probe_r14-style INTRA-FUNCTION jmp
// patch at the resolver's single keep-set (no return interception), which is safe.
//
// GetHeroAssetFromPrimaryAssetId (entry +0x562E9F6) resolves a hero PrimaryAssetId. Both the main
// TMap-hit path (+0x562EAD5 jz +0x562EB02) and the cookie path converge to:
//   +0x562EB1A  mov rdi,[rax]          ; rdi = *(entry+0x10) = the resolved object (returned in RAX)
//   +0x562EB22  [rdi+0xc] bit30 flag check
//   +0x562EB2E  mov byte[r15],0        ; KEEP  (r15 = OutputExecs ptr, set 0)
//   +0x562EB32  jmp +0x562EB5D         ; -> epilogue (mov rax,rdi ; ret)
// At +0x562EB2E: r15=OutputExecs ptr, rdi=the object being returned, r14=id ptr (set +0x562EA15).
//
// Technique: at menu-load (h_idl_post on the Hero GetPrimaryAssetIdList call, when GetHeroCharacterList
// has decrypted the +0x562EB page), overwrite the 5 bytes at +0x562EB2E ("41 C6 07 00 EB" = the keep-set
// mov + the first byte of the jmp) with `jmp keepStub` (NearAlloc'd within +-2GB). keepStub replicates
// `mov byte[r15],0`, records {id.Type, id.Name, object=rdi}, then `jmp +0x562EB5D`. No CALL/return frame,
// so the resolver's odd frame is never an issue. Worker dumps each KEPT hero's id + returned object +
// the object's UClass FName ([obj+0x18]->[cls+0x20]), then un-patches (5 bytes) + un-hooks (<10s, safe).
//
// DECISIVE READ:
//   * many keeps whose object class = BP_LokiHeroAsset_C / BP_HeroAsset_* => resolver returns loadable
//     hero assets that DynamicCast<BP_LokiHeroAsset_C> would accept => grid failure is DOWNSTREAM
//     (all-or-nothing count gate / IsCatalogDataReady / timing).
//   * keeps whose object class is NOT a hero asset (e.g. a CatalogEntry/descriptor) => the grid's
//     DynamicCast<BP_LokiHeroAsset_C> FAILS => that is the drop.
//   * zero keeps => every hero id is REJECTED (OutputExecs stays 1) => resolution fails (== S44/S45).
//
// Build:  clang++ -shared -O2 hero_resolve_probe.cpp -o hero_resolve_probe.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe hero_resolve_probe.dll 0x3EC57D0 40555356574154415541564157
// Marker: docs/hero-resolve-probe-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\hero-resolve-probe-marker.txt";

constexpr uintptr_t kVtRva        = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva      = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr uintptr_t kTypeMapOff   = 0x478;
constexpr uintptr_t kInfoBaseOff  = 0x30;
constexpr uintptr_t kInfoPathsOff = 0x70;
constexpr int       SLOT_IDL      = 110;
constexpr uint32_t  kHeroFName    = 0x1A568;
constexpr uintptr_t kNamePoolRva  = 0x9D81450;   // &FNamePool.Blocks[0] (Len10 layout)
constexpr uintptr_t kKeepSetRva   = 0x562EB2E;   // mov byte[r15],0  (KEEP)  — patch site (5 bytes overwrite)
constexpr uintptr_t kKeepRetRva   = 0x562EB5D;   // jmp target after keep (the epilogue)
constexpr uintptr_t kClassOff     = 0x18;        // UObject->Class (this build's non-standard layout)
constexpr uintptr_t kNameOff      = 0x20;        // UObject->Name / UClass->Name

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);
struct TArr { void* Data; int32_t Num; int32_t Max; };

struct Rec { uint64_t idType; uint64_t idName; uint64_t obj; uint64_t pad; };
constexpr int MAXREC = 512;
static Rec           g_recs[MAXREC];
static volatile LONG g_recN = 0;

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_scanState = 0;
static volatile bool g_unhooked = false;
static uint8_t*  g_keepRegion = nullptr;         // NearAlloc'd keepStub
static uint8_t   g_origKeep[5] = {0};            // saved 5 bytes at +0x562EB2E
static volatile bool g_patched = false;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLogBuf=64*1024; static char g_log[kLogBuf]; static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLog(const char* s){RingAppend(s,(int)strlen(s));}
static void RingLogf(const char* f,...){char b[256];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

static bool GetFNameStr(uint32_t id, char* out, int cap){
    uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva);
    uint32_t b=id>>16, off=(id&0xFFFF)<<1;
    if(!SafeReadable(blocks+b,8)) return false;
    uintptr_t bp=blocks[b]; if(!LooksLikePtr(bp)) return false;
    if(!SafeReadable((void*)(bp+off),2)) return false;
    uint16_t hdr=*(uint16_t*)(bp+off); int len=hdr>>6; bool wide=(hdr&1)!=0;
    if(len<=0||len>=cap) return false;
    if(wide){ if(!SafeReadable((void*)(bp+off+2),len*2))return false; for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2); }
    else    { if(!SafeReadable((void*)(bp+off+2),len))  return false; for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i]; }
    out[len]=0; return true;
}

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

struct Emit { uint8_t* w; };
static void EB(Emit& e, uint8_t b){ *e.w++=b; }
static void EU32(Emit& e, uint32_t v){ memcpy(e.w,&v,4); e.w+=4; }
static void EU64(Emit& e, uint64_t v){ memcpy(e.w,&v,8); e.w+=8; }

// Build the keepStub. On entry (jumped-to from +0x562EB2E): r15=OutputExecs ptr, rdi=object, r14=id ptr.
// Preserve rdi (the epilogue does `mov rax,rdi`) and r14/r15/rsi/rbx (epilogue reloads from stack, but
// rdi is used live). Only use rax/rcx/rdx/r10/r11 (scratch) + flags. Replicate the keep, record, jmp back.
static uint8_t* BuildKeepStub(uintptr_t keepRetAbs){
    uint8_t* p=NearAlloc(g_modBase+kKeepSetRva,0x100); if(!p)return nullptr;
    Emit e{p};
    EB(e,0x41);EB(e,0xC6);EB(e,0x07);EB(e,0x00);          // mov byte [r15], 0   (replicate the KEEP)
    // atomic idx = g_recN++
    EB(e,0x49);EB(e,0xBA); EU64(e,(uint64_t)&g_recN);     // mov r10, &g_recN
    EB(e,0xB9); EU32(e,1);                                 // mov ecx, 1
    EB(e,0xF0);EB(e,0x41);EB(e,0x0F);EB(e,0xC1);EB(e,0x0A);// lock xadd [r10], ecx   (ecx = old idx)
    EB(e,0x81);EB(e,0xF9); EU32(e,(uint32_t)MAXREC);       // cmp ecx, MAXREC
    EB(e,0x73); uint8_t* jae=e.w; EB(e,0x00);              // jae .skip  (rel8, backpatched)
    uint8_t* afterJae=e.w;
    EB(e,0x48);EB(e,0x63);EB(e,0xC9);                      // movsxd rcx, ecx
    EB(e,0x48);EB(e,0xC1);EB(e,0xE1);EB(e,0x05);           // shl rcx, 5   (*32)
    EB(e,0x49);EB(e,0xBA); EU64(e,(uint64_t)&g_recs[0]);   // mov r10, &g_recs
    EB(e,0x49);EB(e,0x01);EB(e,0xCA);                      // add r10, rcx   (rec ptr)
    EB(e,0x49);EB(e,0x8B);EB(e,0x06);                      // mov rax, [r14]      id.Type
    EB(e,0x49);EB(e,0x89);EB(e,0x02);                      // mov [r10], rax
    EB(e,0x49);EB(e,0x8B);EB(e,0x46);EB(e,0x08);           // mov rax, [r14+8]    id.Name
    EB(e,0x49);EB(e,0x89);EB(e,0x42);EB(e,0x08);           // mov [r10+8], rax
    EB(e,0x49);EB(e,0x89);EB(e,0x7A);EB(e,0x10);           // mov [r10+16], rdi   object
    // .skip:
    *jae=(uint8_t)((intptr_t)e.w-(intptr_t)afterJae);
    EB(e,0xE9);                                            // jmp rel32 -> +0x562EB5D
    int32_t rel=(int32_t)((intptr_t)keepRetAbs-((intptr_t)e.w+4)); EU32(e,(uint32_t)rel);
    return p;
}

extern "C" void h_idl_pre(uintptr_t rcx, uintptr_t, uintptr_t, uintptr_t){
    if(InterlockedCompareExchange(&g_scanState,1,0)!=0) return;
    RingLogf("[enum] first GetPrimaryAssetIdList -> scan (mgr=0x%llX)\r\n",(unsigned long long)rcx);
    g_scan=(PFN_Scan)(g_modBase+kScanRva);
    RunScanForAllTypes((void*)rcx);
    InterlockedExchange(&g_scanState,2);
}
static volatile long g_keepPatched = 0;
extern "C" void h_idl_post(uintptr_t, uintptr_t rdx, uintptr_t, uintptr_t){
    if((uint32_t)(rdx&0xFFFFFFFF)!=kHeroFName) return;
    if(InterlockedCompareExchange(&g_keepPatched,1,0)!=0) return;
    uint8_t* site=(uint8_t*)(g_modBase+kKeepSetRva);
    // expect the decrypted keep-set: 41 C6 07 00 EB (mov byte[r15],0 ; jmp rel8)
    if(!SafeReadable(site,5) || site[0]!=0x41 || site[1]!=0xC6 || site[2]!=0x07 || site[3]!=0x00 || site[4]!=0xEB){
        RingLog("[patch] Hero call but keep-set +0x562EB2E not decrypted/expected\r\n"); InterlockedExchange(&g_keepPatched,0); return; }
    g_keepRegion=BuildKeepStub(g_modBase+kKeepRetRva);
    if(!g_keepRegion){ RingLog("[patch] BuildKeepStub failed\r\n"); return; }
    int32_t rel=(int32_t)((intptr_t)g_keepRegion-((intptr_t)site+5));
    DWORD op=0;
    if(VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&op)){
        memcpy(g_origKeep,site,5);
        site[0]=0xE9; site[1]=(uint8_t)rel; site[2]=(uint8_t)(rel>>8); site[3]=(uint8_t)(rel>>16); site[4]=(uint8_t)(rel>>24);
        DWORD d=0; VirtualProtect(site,5,op,&d);
        g_patched=true;
        RingLogf("[patch] keep-set +0x562EB2E patched -> keepStub %p\r\n",(void*)g_keepRegion);
    } else RingLog("[patch] VirtualProtect failed\r\n");
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

static void DumpRecords(){
    LONG n=g_recN; if(n>MAXREC)n=MAXREC;
    RingLogf("[RESULT] keep-set hits (heroes the resolver KEEPS w/ OutputExecs=0) = %ld\r\n",(long)g_recN);
    RingLog("[RESULT] each kept hero's RETURNED object + its UClass name (does it cast to BP_LokiHeroAsset_C?):\r\n");
    // tally distinct id.Name + class
    int shown=0;
    for(int i=0;i<n && shown<60;i++){
        uint32_t tId=(uint32_t)(g_recs[i].idType&0xFFFFFFFF);
        uint32_t nId=(uint32_t)(g_recs[i].idName&0xFFFFFFFF);
        uint64_t obj=g_recs[i].obj;
        char tname[128]="?", nname[128]="?", cname[160]="?";
        GetFNameStr(tId,tname,sizeof(tname)); GetFNameStr(nId,nname,sizeof(nname));
        uint64_t cls=0;
        if(obj && SafeReadable((void*)(obj+kClassOff),8)){
            cls=*(uintptr_t*)(obj+kClassOff);
            if(LooksLikePtr(cls)&&SafeReadable((void*)(cls+kNameOff),4)){ GetFNameStr(*(uint32_t*)(cls+kNameOff),cname,sizeof(cname)); }
        }
        RingLogf("  [%d] id=%s:%s obj=0x%llX class=%s\r\n",i,tname,nname,(unsigned long long)obj,cname);
        shown++;
    }
    RingLogf("[RESULT] shown %d of %ld keeps. If class=BP_LokiHeroAsset_C/BP_HeroAsset_* => cast OK (grid fails downstream); if not a hero asset => cast fails; if 0 keeps => all rejected (load fails).\r\n",shown,(long)g_recN);
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] hero_resolve_probe v2 (keep-set capture) worker started\r\n");
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

    LONG64 flushed=0; DWORD hb=GetTickCount(); DWORD hb0=GetTickCount(); bool dumped=false; DWORD patchedAt=0; LONG lastN=0; DWORD settledAt=0;
    while(true){
        Sleep(150);
        if(g_patched && !dumped){
            if(patchedAt==0) patchedAt=GetTickCount();
            LONG n=g_recN;
            if(n!=lastN){ lastN=n; settledAt=GetTickCount(); }
            bool settled = (n>0 && settledAt && GetTickCount()-settledAt>=2000);
            bool timeout = (GetTickCount()-patchedAt>=140000);  // hold patch <=140s (under integrity wall)
            if(settled || timeout){
                RingLogf("[dump] keeps=%ld (settled=%d timeout=%d)\r\n",g_recN,settled?1:0,timeout?1:0);
                DumpRecords();
                if(g_patched){uint8_t* site=(uint8_t*)(g_modBase+kKeepSetRva);DWORD o=0;if(VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&o)){memcpy(site,g_origKeep,5);DWORD dd=0;VirtualProtect(site,5,o,&dd);}Marker("[unpatch] keep-set restored\r\n");}
                dumped=true;
            }
        }
        if(!g_unhooked && (dumped || GetTickCount()-hb0>=150000)){
            DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}g_unhooked=true;Marker("[unhook] slot 110 restored\r\n");
        }
        LONG64 head=g_head; if(head>(LONG64)sizeof(g_log))head=(LONG64)sizeof(g_log);
        if(head>flushed){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_log+flushed,(DWORD)(head-flushed),&w,nullptr);CloseHandle(f);flushed=head;}}
        if(GetTickCount()-hb>=5000){Markerf("[hb] scanState=%ld patched=%d keeps=%ld dumped=%d\r\n",g_scanState,g_patched?1:0,g_recN,dumped?1:0);hb=GetTickCount();}
    }
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
