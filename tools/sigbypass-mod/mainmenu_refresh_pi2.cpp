// mainmenu_refresh_pi2 — SESSION 50 Phase-3, EXPERIMENT: drive the SPAWNER directly.
// subject.Refresh() ran but never reached SetHero (spawner TargetAssetID unchanged). This variant, on a pick,
// mirrors member=pick then calls **spawner.OnPartyUpdated** (no-param BP event) on each live
// BP_MainMenuSpawner_MainMenu_PartySlot_C via the ProcessInternal->ProcessEvent game-thread capability, and
// SELF-VERIFIES by reading each spawner's TargetAssetID @+0x3F8 (HeroCosmeticsBundle name) before/after. If a
// spawner's TargetAssetID changes to the picked hero's bundle, OnPartyUpdated drives SetHero -> switch the shim
// trigger to it. (Only ONE ProcessInternal-hooking shim may run per client — relaunch clean with just this one.)
//
// Offsets: ProcessInternal @base+0x13454A0 (hook), ProcessEvent @base+0x12C5A10 (call). UObject Class@+0x18,
// Name@+0x20, Outer@+0x28. PartyMemberModel.HeroAssetID@+0x78 (Hero 0x1A568). WBP_HeroPicker.SelectedHeroAsset
// @+0x10D8. BP_MainMenuSpawner_MainMenu_PartySlot_C.TargetAssetID PrimaryAssetId @+0x3F8 (name @+0x400).
// GUObjectArray@base+0x9E38930, FNamePool@base+0x9D81450, GGameThreadId@base+0x9D49158.
// Build:  clang++ -shared -O2 mainmenu_refresh_pi2.cpp -o mainmenu_refresh_pi2.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/mainmenu_refresh_pi2.dll
// Marker: docs/mainmenu-refresh-pi2-marker.txt   Crash: docs/mainmenu-refresh-pi2-crash.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\mainmenu-refresh-pi2-marker.txt";
static const char* kCrashPath  = "G:\\git\\Supervive Revival Project\\docs\\mainmenu-refresh-pi2-crash.txt";

constexpr uintptr_t kPiRva        = 0x13454A0;
constexpr uintptr_t kPeRva        = 0x12C5A10;
constexpr uintptr_t kObjObjectsRva= 0x9E38930;
constexpr uintptr_t kNamePoolRva  = 0x9D81450;
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr int       PERCHUNK      = 65536;
constexpr int       ITEMSTRIDE    = 0x18;
constexpr uintptr_t CLASS_OFF     = 0x18;
constexpr uintptr_t NAME_OFF      = 0x20;
constexpr uintptr_t OUTER_OFF     = 0x28;
constexpr uintptr_t MEMBER_HEROID = 0x78;
constexpr uintptr_t PICKER_SELHERO= 0x10D8;
constexpr uintptr_t SPAWNER_TARGET= 0x3F8;         // TargetAssetID PrimaryAssetId (name @ +0x400)
constexpr uint32_t  HERO_TYPE     = 0x1A568;
static const uint8_t kPiProlog[5] = {0x48,0x89,0x5C,0x24,0x08};

typedef void (*PFN_PE)(void* obj, void* func, void* parms);

static uintptr_t   g_modBase   = 0;
static volatile PFN_PE g_tramp = nullptr;
static PFN_PE      g_processEvent = nullptr;
static void*       g_onPartyUpd = nullptr;         // spawner OnPartyUpdated UFunction
static uintptr_t   g_spawnClass = 0;
static void*       g_spawners[8] = {0};
static int         g_nspawn    = 0;
static uintptr_t   g_member    = 0;
static uint8_t*    g_pi        = nullptr;
static uint8_t     g_stolen[5] = {0};
static volatile long g_pending = 0;
static volatile long g_inHook  = 0;
static volatile long g_done    = 0;
static volatile long g_calls   = 0;
static volatile long g_hitsGT  = 0;
static DWORD       g_gameTid   = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}
static bool GetFNameStr(uint32_t id,char* out,int cap){
    uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva); uint32_t b=id>>16,off=(id&0xFFFF)<<1;
    if(!SafeReadable(blocks+b,8))return false; uintptr_t bp=blocks[b]; if(!LooksLikePtr(bp))return false;
    if(!SafeReadable((void*)(bp+off),2))return false; uint16_t hdr=*(uint16_t*)(bp+off); int len=hdr>>6; bool wide=(hdr&1)!=0;
    if(len<=0||len>=cap)return false;
    if(wide){for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2);}
    else    {if(!SafeReadable((void*)(bp+off+2),len))return false;for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i];}
    out[len]=0;return true;
}
static uint32_t NameId(uintptr_t obj){ if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0; return *(uint32_t*)(obj+NAME_OFF); }
static bool NameIs(uintptr_t obj,const char* w){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static uintptr_t OuterOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+OUTER_OFF),8))return 0; return *(uintptr_t*)(obj+OUTER_OFF); }
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static uint32_t ReadHeroPA(uintptr_t obj,uintptr_t off){ if(!SafeReadable((void*)(obj+off),16))return 0; if(*(uint32_t*)(obj+off)!=HERO_TYPE)return 0; return *(uint32_t*)(obj+off+8); }
// spawner TargetAssetID cosmetic name (FName id @ +0x3F8+8), 0 if none
static uint32_t SpawnerCosmetic(uintptr_t sp){ if(!SafeReadable((void*)(sp+SPAWNER_TARGET),16))return 0; return *(uint32_t*)(sp+SPAWNER_TARGET+8); }

// ─────────── VEH ───────────
struct ModRange{uint64_t base,end;char name[64];};
static ModRange g_mods[192]; static volatile long g_modCount=0; static volatile long g_crashSeq=0;
static void SnapshotModules(){HANDLE s=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());if(s==INVALID_HANDLE_VALUE)return;MODULEENTRY32 me;me.dwSize=sizeof(me);int n=0;if(Module32First(s,&me)){do{if(n>=192)break;ModRange&r=g_mods[n];r.base=(uint64_t)me.modBaseAddr;r.end=r.base+me.modBaseSize;int i=0;for(;i<63&&me.szModule[i];i++)r.name[i]=(char)me.szModule[i];r.name[i]=0;n++;}while(Module32Next(s,&me));}CloseHandle(s);InterlockedExchange(&g_modCount,n);}
static void HxU64(char* o,uint64_t v){const char* d="0123456789ABCDEF";for(int i=15;i>=0;i--){o[i]=d[(int)(v&0xF)];v>>=4;}}
static void CWrite(HANDLE h,const char* s,DWORD n){DWORD w=0;WriteFile(h,s,n,&w,0);}
static void CKV(HANDLE h,const char* k,uint64_t v){char b[96];int p=0;while(k[p]&&p<40){b[p]=k[p];p++;}b[p++]='=';b[p++]='0';b[p++]='x';HxU64(b+p,v);p+=16;b[p++]='\r';b[p++]='\n';CWrite(h,b,(DWORD)p);}
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode;
    bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0x80000003||code==0xC0000374||code==0xC00000FD||code==0xC0000094||code==0xC0000095||code==0xC0000096;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH;
    long seq=InterlockedIncrement(&g_crashSeq); if(seq>64)return EXCEPTION_CONTINUE_SEARCH;
    HANDLE h=CreateFileA(kCrashPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h==INVALID_HANDLE_VALUE)return EXCEPTION_CONTINUE_SEARCH;
    CWrite(h,"=== VEH fatal ===\r\n",19); CKV(h,"seq",(uint64_t)seq); CKV(h,"code",code);
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip; CKV(h,"RIP",rip);
    if(g_modBase && rip>g_modBase && rip<g_modBase+0xC000000) CKV(h,"SUPERVIVE_RVA",rip-g_modBase);
    long mc=g_modCount; bool named=false;
    for(long i=0;i<mc;i++){ if(rip>=g_mods[i].base && rip<g_mods[i].end){ CWrite(h,"module=",7); CWrite(h,g_mods[i].name,(DWORD)strlen(g_mods[i].name)); CWrite(h,"\r\n",2); CKV(h,"module_RVA",rip-g_mods[i].base); named=true; break; } }
    if(!named)CWrite(h,"module=UNKNOWN\r\n",16);
    if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2){ CKV(h,"av_op",ep->ExceptionRecord->ExceptionInformation[0]); CKV(h,"av_addr",ep->ExceptionRecord->ExceptionInformation[1]); }
    CKV(h,"Rcx",c->Rcx);CKV(h,"Rdx",c->Rdx);CKV(h,"R8",c->R8);CKV(h,"inHook",(uint64_t)g_inHook);
    CWrite(h,"=== end ===\r\n\r\n",15); FlushFileBuffers(h); CloseHandle(h);
    return EXCEPTION_CONTINUE_SEARCH;
}

extern "C" void OnBP(void*,void*,void*){
    DWORD tid=GetCurrentThreadId();
    if(!g_pending) return;
    if(g_inHook)   return;
    if(tid!=g_gameTid) return;
    InterlockedIncrement(&g_hitsGT);
    g_inHook=1;
    for(int i=0;i<g_nspawn;i++){ if(g_spawners[i]&&g_onPartyUpd&&g_processEvent) g_processEvent(g_spawners[i],g_onPartyUpd,nullptr); }
    g_pending=0; g_done=1; InterlockedIncrement(&g_calls);
    g_inHook=0;
}

static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){
    for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){ uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};
        for(int i=0;i<2;i++){ if(!cands[i])continue; void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
            if(p){ intptr_t d=(intptr_t)p-(intptr_t)anchor; if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000) return (uint8_t*)p; VirtualFree(p,0,MEM_RELEASE); } } }
    return nullptr;
}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
static uint8_t* BuildHook(uintptr_t fn,const uint8_t stolen[5]){
    uint8_t* blk=NearAlloc(fn,0x200); if(!blk)return nullptr;
    Emit t{blk}; for(int i=0;i<5;i++)EB(t,stolen[i]); EB(t,0xE9); int32_t rel=(int32_t)((intptr_t)(fn+5)-((intptr_t)t.w+4)); EU32(t,(uint32_t)rel);
    g_tramp=(PFN_PE)blk;
    uint8_t* stub=blk+0x20; Emit e{stub};
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);
    EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnBP); EB(e,0xFF);EB(e,0xD0);
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);
    EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk); EB(e,0xFF);EB(e,0xE0);
    return stub;
}
static uint8_t* g_stub=nullptr;
// SAFE inline patch of a HOT function entry: suspend all other threads, ensure none is executing INSIDE the
// [dst, dst+len) bytes (retry if so), then write + FlushInstructionCache, then resume. Removes the race where a
// non-atomic 5-byte write over ProcessInternal (called thousands/sec) corrupts an in-flight execution.
static bool SafeWrite(uint8_t* dst, const uint8_t* src, size_t len){
    DWORD myTid=GetCurrentThreadId(), myPid=GetCurrentProcessId();
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0); if(snap==INVALID_HANDLE_VALUE)return false;
    HANDLE hs[1024]; int nh=0; THREADENTRY32 te; te.dwSize=sizeof(te);
    if(Thread32First(snap,&te)){ do{ if(te.dwSize>=FIELD_OFFSET(THREADENTRY32,th32OwnerProcessID)+sizeof(DWORD)
        && te.th32OwnerProcessID==myPid && te.th32ThreadID!=myTid && nh<1024){
        HANDLE ht=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,te.th32ThreadID);
        if(ht) hs[nh++]=ht; } }while(Thread32Next(snap,&te)); }
    CloseHandle(snap);
    uintptr_t lo=(uintptr_t)dst, hi=(uintptr_t)dst+len; bool ok=false;
    for(int attempt=0; attempt<400 && !ok; attempt++){
        for(int i=0;i<nh;i++) SuspendThread(hs[i]);
        bool unsafe=false;
        for(int i=0;i<nh;i++){ CONTEXT c; c.ContextFlags=CONTEXT_CONTROL; if(GetThreadContext(hs[i],&c)){ if(c.Rip>lo && c.Rip<hi){ unsafe=true; break; } } }
        if(!unsafe){ DWORD op=0; if(VirtualProtect(dst,len,PAGE_EXECUTE_READWRITE,&op)){ memcpy(dst,src,len); DWORD d=0; VirtualProtect(dst,len,op,&d); FlushInstructionCache(GetCurrentProcess(),dst,len); ok=true; } }
        if(!ok){ for(int i=0;i<nh;i++) ResumeThread(hs[i]); Sleep(1); }
    }
    for(int i=0;i<nh;i++){ ResumeThread(hs[i]); CloseHandle(hs[i]); }   // resume once (net) + close
    return ok;
}
static bool InstallHook(){ if(!g_pi||!g_stub)return false; int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5)); uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)}; return SafeWrite(g_pi,p,5); }
static void UninstallHook(){ if(!g_pi)return; SafeWrite(g_pi,g_stolen,5); }
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    if(!g_spawnClass){ for(int ci=0;ci<numChunks && !g_spawnClass;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,"BP_MainMenuSpawner_MainMenu_PartySlot_C")){ uintptr_t cls=ClassOf(obj); char cn[96]="?"; if(cls)GetFNameStr(NameId(cls),cn,sizeof(cn)); if(strstr(cn,"Class")){ g_spawnClass=obj; break; } } } } }
    if(!g_spawnClass)return; g_nspawn=0; g_member=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassOf(obj)==g_spawnClass && g_nspawn<8 && NameIs(obj,"BP_MainMenuSpawner_MainMenu_PartySlot_C")) g_spawners[g_nspawn++]=(void*)obj;
            else if(!g_onPartyUpd && NameIs(obj,"OnPartyUpdated") && OuterOf(obj)==g_spawnClass) g_onPartyUpd=(void*)obj;
            else if(!g_member && ClassNameIs(obj,"PartyMemberModel")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) g_member=obj; } } }
}
static uint32_t FindActivePickerHero(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uint32_t best=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassNameIs(obj,"WBP_HeroPicker_C")){ uint32_t nm=ReadHeroPA(obj,PICKER_SELHERO); if(nm){ char s[64]; if(GetFNameStr(nm,s,sizeof(s))&&strcmp(s,"None")!=0) best=nm; } } } }
    return best;
}
static void WriteMemberHero(uint32_t nameId){ if(!g_member||!SafeReadable((void*)(g_member+MEMBER_HEROID),16))return; *(uint32_t*)(g_member+MEMBER_HEROID)=HERO_TYPE; *(uint32_t*)(g_member+MEMBER_HEROID+4)=0; *(uint32_t*)(g_member+MEMBER_HEROID+8)=nameId; *(uint32_t*)(g_member+MEMBER_HEROID+12)=0; }
static uint32_t ReadMemberHero(){ return g_member?ReadHeroPA(g_member,MEMBER_HEROID):0; }
static void LogSpawners(const char* tag){ for(int i=0;i<g_nspawn;i++){ uint32_t c=SpawnerCosmetic((uintptr_t)g_spawners[i]); char s[64]="<none>"; if(c)GetFNameStr(c,s,sizeof(s)); Markerf("   [%s] spawner[%d]=0x%llX TargetAssetID=%s\r\n",tag,i,(unsigned long long)g_spawners[i],s); } }

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    { HANDLE ch=CreateFileA(kCrashPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] mainmenu_refresh_pi2 (spawner.OnPartyUpdated experiment) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; g_processEvent=(PFN_PE)(g_modBase+kPeRva);
    SnapshotModules(); AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;} Markerf("[1] gameTid=%lu\r\n",g_gameTid);
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ Resolve(); if(g_nspawn>0&&g_onPartyUpd&&g_member)break; Sleep(500);}
    if(g_nspawn==0||!g_onPartyUpd||!g_member){Markerf("[2] FAIL resolve spawners=%d onPartyUpd=%p member=0x%llX\r\n",g_nspawn,g_onPartyUpd,(unsigned long long)g_member);return 3;}
    Markerf("[2] resolved spawners=%d onPartyUpd=%p member=0x%llX\r\n",g_nspawn,g_onPartyUpd,(unsigned long long)g_member);
    LogSpawners("init");
    g_pi=(uint8_t*)(g_modBase+kPiRva);
    if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Markerf("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Marker("[3] hook built. Open HUNTERS + click a hunter.\r\n");

    uint32_t desired=0; bool hooked=false; DWORD hookedAt=0,lastResolve=GetTickCount(),lastHb=0,start=GetTickCount(); uint32_t lastLogged=0;
    while(GetTickCount()-start<28800000u){
        if(GetTickCount()-lastResolve>=1500){ lastResolve=GetTickCount(); if(g_nspawn==0||!g_member)Resolve(); }
        uint32_t pick=FindActivePickerHero();
        if(pick&&pick!=desired){ desired=pick; char s[64]="?"; GetFNameStr(pick,s,sizeof(s)); Markerf("[PICK] Hero:%s\r\n",s); }
        if(desired){ uint32_t cur=ReadMemberHero(); if(cur!=desired){ WriteMemberHero(desired); if(desired!=lastLogged){ char s[64]="?"; GetFNameStr(desired,s,sizeof(s)); Markerf("[MIRROR] member <- Hero:%s\r\n",s); LogSpawners("before"); lastLogged=desired; }
            if(!hooked){ g_pending=1; g_done=0; if(InstallHook()){ hooked=true; hookedAt=GetTickCount(); Marker("[armed] calling spawner.OnPartyUpdated on next game-thread BP...\r\n"); } } } }
        if(hooked){ if(g_done){ UninstallHook(); hooked=false; Markerf("[CALLED] spawner.OnPartyUpdated x%d ran on game thread (#%ld). Spawner TargetAssetID AFTER:\r\n",g_nspawn,(long)g_calls); LogSpawners("after"); }
            else if(GetTickCount()-hookedAt>=6000){ UninstallHook(); hooked=false; g_pending=0; Markerf("[timeout] no game-thread PI in 6s (hitsGT=%ld)\r\n",(long)g_hitsGT); } }
        if(GetTickCount()-lastHb>=10000){ char mh[64]="<none>"; GetFNameStr(ReadMemberHero(),mh,sizeof(mh)); Markerf("[hb] member=Hero:%s desired=%u calls=%ld hitsGT=%ld hooked=%d\r\n",mh,desired,(long)g_calls,(long)g_hitsGT,hooked?1:0); lastHb=GetTickCount(); }
        Sleep(60);
    }
    if(hooked)UninstallHook(); Marker("[done] worker exit\r\n"); return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
