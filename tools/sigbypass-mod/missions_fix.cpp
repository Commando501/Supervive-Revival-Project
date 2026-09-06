// missions_fix — SESSION 59, OPTION 2 (2d: DURABLE menu-load shim). Same fetch/build/swap as probe18,
// packaged to auto-run on launch (no manual injection) and to keep progress fresh mid-session:
//   1. Wait for ProgMgr / MissionsModel + the native funcs to resolve (menu load).
//   2. Fetch per-objective progress from ags (GET http://127.0.0.1:8080/revival/missions/progress),
//      build the GetUniqueObjectiveName-keyed model with each ObjectiveProgress[i].Progress set from it,
//      and swap it into ProgMgr.MissionsModel. Reopen the modal -> bars reflect ags progress.
//   3. Then POLL ags every ~30s; only when the fetched progress CHANGES (e.g. a match posted /add) does
//      it re-hook + rebuild + re-swap, so progress "fills as you play" without a relaunch (reopen the
//      modal to see it). Idle = cheap HTTP polls, no thread-suspends.
// DEPLOY: injected by configs/inject-secondaries.ps1 (spawned by launch-redirect.ps1; part of the DEFAULT
// secondary set), AFTER the primary catalog_store_fix settles. Coexists with the other ProcessInternal
// hookers (pi8, loadout_fix) via the shared "Local\SuperviveMissionsPIHook" mutex — each installs its
// 5-byte PI jmp only TRANSIENTLY (install -> apply -> uninstall) under the lock, so they never race on the
// thread-suspend install. (The old inject-missions.ps1 "-Missions" mode that skipped pi8 is retired.) Build:
//   clang++ -shared -O2 missions_fix.cpp -o missions_fix.dll -lkernel32 -lwininet
// Marker: docs/missions-fix-marker.txt.
// (Original probe17/18 header follows.)
// missions_nativecall_probe17 — SESSION 59, OPTION 1: make the progress bars show "0 / real-max"
// (not the design-time placeholder "10/20"). Root cause (RE'd s59): the per-objective bar widget
// (WBP_UI_MissionObjectiveProgress) binds ObjectiveModel via
//     name = LokiAssetStatics::GetUniqueObjectiveName(widget.Objective /*LokiMissionObjectiveData*/)
//     ObjectiveModel = MissionModel.Objectives.Find(name)   [FName-keyed map]
// then OnObjectiveModelSet -> UpdateProgress -> text = ObjectiveModel.CurrentProgress / Objective.TotalProgress,
// bar.Percent = current/total. The DA's TotalProgress (real max) is ALREADY bound (widget.Objective = DA struct),
// but our factory model keyed the Objectives map by ObjectiveProgress[i].ObjectiveName = None (probe16), so
// Map_Find fails -> ObjectiveModel stays null -> UpdateProgress never runs -> the DESIGN-TIME placeholder
// (Percent=0.5, text "10/20") remains. FIX: build each FMissionProgress with one FMissionObjectiveProgress
// per DA objective, ObjectiveName = GetUniqueObjectiveName(that DA objective) [called natively via the s55
// primitive], Progress = 0. Then the bind path succeeds -> UpdateProgress -> "0 / real-max". Durable: the
// game's own BP does the work each time the modal opens.
//
// Pipeline (all native, via the Avenue-A primitive): enumerate(330) + name-prefix pool map + AsyncLoadPrimaryAssets
// + per-mission read DA.Objectives(@+0x88, LokiMissionObjectiveData[48]) -> GetUniqueObjectiveName +TotalProgress(@+0x10)
// -> CreateMissionModelFromFinalProgress -> swap ProgMgr.MissionsModel(@+0x3B8).
// Build:  clang++ -shared -O2 missions_nativecall_probe17.cpp -o missions_nativecall_probe17.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> ...  Marker: docs/missions-nativecall17-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <wininet.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <cstdlib>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\missions-fix-marker.txt";
static const char* kProgressUrl = "http://127.0.0.1:8080/revival/missions/progress";
constexpr DWORD kPollMs = 30000;   // re-fetch cadence; only re-applies when progress changed
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, PM_MM=0x3B8, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_OUTPARMS=0x80, FF_PROPCHAIN=0x88;
constexpr uintptr_t FLD_NEXT=0x18, FLD_FLAGS=0x38, FLD_OFFSET=0x44;
constexpr uint64_t CPF_OutParm=0x100, CPF_ReturnParm=0x400;
constexpr uintptr_t DA_OBJECTIVES=0x88;   // LokiDataAsset_Mission.Objectives (TArray<LokiMissionObjectiveData>)
constexpr uintptr_t DA_INTERNALNAME=0x40; // LokiDataAsset_Base.InternalName (FName) — the mission's unique name
constexpr uintptr_t LMOD_SIZE=0x30;       // sizeof LokiMissionObjectiveData
constexpr uintptr_t LMOD_TOTAL=0x10;      // LokiMissionObjectiveData.TotalProgress (float)
constexpr int MAXOBJ=6;                   // max objectives per mission we mirror
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

struct Fn { void* fn; uintptr_t thunk; uintptr_t child; };
static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_lam=0, g_mm=0, g_pm=0;
static Fn g_pafs{}, g_gpail{}, g_factory{}, g_getMissions{}, g_glda{}, g_load{}, g_guon{};
constexpr int NMAX=360, NPOOL=32;
static uint8_t g_loadAssets[NMAX*16]={0};
static wchar_t g_idbufs[NMAX][8]={{0}};
static volatile long g_state=0; static DWORD g_t0=0; static uint64_t g_loadHandle=0; static int g_loadedCheck=0;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};
static uint64_t g_pbuf[16]={0}, g_rbuf[4]={0}; static uint8_t g_outparms[8*24]={0};
static uint8_t g_elems[NMAX*0x60]={0};
static uint8_t g_objprog[NMAX*MAXOBJ*0x38]={0};   // FMissionObjectiveProgress[NMAX][MAXOBJ]
static int g_objCount[NMAX]={0};                  // objectives mirrored per mission
static uint8_t g_daStruct[0x30]={0};              // scratch: one LokiMissionObjectiveData copy for the GUON call
static uint64_t g_missionIds[NMAX][2]={{0}}, g_poolIds[NPOOL][2]={{0}}, g_missPool[NMAX][2]={{0}}, g_retModel=0, g_glLoaded=0;
static char g_missNames[NMAX][48]={{0}}, g_poolNames[NPOOL][48]={{0}};
static int32_t g_missNum=0, g_poolNum=0, g_modelNum=-1, g_nBuilt=0; static char g_modelCls[96]={0}, g_glCls[64]={0};
static bool g_swapped=false;
// verification capture for the first few missions
static char g_vKeyName[8][64]={{0}}; static float g_vTotal[8]={0}; static int g_vObjN[8]={0}; static char g_vMiss[8][48]={{0}};
static float g_vProg[8]={0};   // applied progress for the first few (Option 2 verification)
// fetched per-objective progress (from ags GET /revival/missions/progress)
constexpr int PROGMAX=512;
constexpr int KEYW=128;   // key width — composite keys are "<mission>/<objective>"
static char g_progName[PROGMAX][KEYW]={{0}}; static float g_progVal[PROGMAX]={0}; static int g_progNum=0;
static int g_fetchOk=0; static int g_appliedNonZero=0;
// snapshot of the last-APPLIED progress, for order-independent change detection between polls.
static char g_lastName[PROGMAX][KEYW]={{0}}; static float g_lastVal[PROGMAX]={0}; static int g_lastNum=-1;
static volatile long g_applyCount=0;
// mission->objective manifest JSON, built in BuildAndSwap (game thread), POSTed from Worker (off thread)
// so match results can fan out to per-mission composite keys. Registered once per session.
static char g_manifest[262144]={0}; static volatile long g_manifestLen=0; static int g_manifestPosted=0; static int g_manifestEntries=0;
#ifdef MISSIONS_XP_DRAFT
// XP-draft state: the DA internal name per mission (so the manifest can be re-serialized after the factory)
// and the per-mission XP reward read from the OUTPUT model. Gated: the default build doesn't compile these.
static char g_missInternal[NMAX][64]={{0}};
static float g_missXP[NMAX]={0};
#endif
// Shared ProcessInternal-hook lock: mainmenu_refresh_pi8.dll ALSO hooks ProcessInternal, and two hooks race
// on the thread-suspending SafeWrite. Both shims serialize their (one-time g_stolen capture + every
// install->use->uninstall) span on this named mutex so only one owns the PI prologue at a time. Under the
// lock the prologue is always the ORIGINAL (the other shim installs only while it holds the lock).
static HANDLE g_hookMutex=nullptr;
static void HookLock(){ if(g_hookMutex) WaitForSingleObject(g_hookMutex,30000); }
static void HookUnlock(){ if(g_hookMutex) ReleaseMutex(g_hookMutex); }

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}
static bool GetFNameStr(uint32_t id,char* out,int cap){
    uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva); uint32_t b=id>>16,off=(id&0xFFFF)<<1;
    if(!SafeReadable(blocks+b,8))return false; uintptr_t bp=blocks[b]; if(!LooksLikePtr(bp))return false;
    if(!SafeReadable((void*)(bp+off),2))return false; uint16_t hdr=*(uint16_t*)(bp+off); int len=hdr>>6; bool wide=(hdr&1)!=0;
    if(len<=0||len>=cap)return false;
    if(wide){for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2);} else {if(!SafeReadable((void*)(bp+off+2),len))return false;for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i];}
    out[len]=0;return true;
}
static uint32_t NameId(uintptr_t obj){ if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0; return *(uint32_t*)(obj+NAME_OFF); }
static bool NameIs(uintptr_t obj,const char* w){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static void ClassNameOf(uintptr_t obj,char* out,int cap){ out[0]=0; uintptr_t c=ClassOf(obj); if(c)GetFNameStr(NameId(c),out,cap); }

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>8)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);
    return EXCEPTION_CONTINUE_SEARCH;
}
static void BuildOutParms(uintptr_t childProps, uint8_t* locals){
    memset(g_outparms,0,sizeof(g_outparms)); *(uint64_t*)(g_myframe+FF_OUTPARMS)=0;
    uintptr_t f=childProps; int n=0; uint8_t* prev=nullptr; uint8_t* head=nullptr;
    while(LooksLikePtr(f) && n<8){
        uint64_t flags=0; if(SafeReadable((void*)(f+FLD_FLAGS),8)) flags=*(uint64_t*)(f+FLD_FLAGS);
        if((flags&CPF_OutParm) && !(flags&CPF_ReturnParm)){
            int32_t off=0; if(SafeReadable((void*)(f+FLD_OFFSET),4)) off=*(int32_t*)(f+FLD_OFFSET);
            uint8_t* rec=g_outparms+n*24; *(uintptr_t*)(rec+0)=f; *(uintptr_t*)(rec+8)=(uintptr_t)(locals+off); *(uintptr_t*)(rec+16)=0;
            if(prev) *(uintptr_t*)(prev+16)=(uintptr_t)rec; else head=rec; prev=rec; n++;
        }
        uintptr_t nx=0; if(SafeReadable((void*)(f+FLD_NEXT),8)) nx=*(uintptr_t*)(f+FLD_NEXT); f=nx;
    }
    *(uint64_t*)(g_myframe+FF_OUTPARMS)=(uint64_t)head;
}
static void Call(Fn& F, void* context, void* paramsBuf, void* resultBuf){
    memcpy(g_myframe, g_template, sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=F.fn; *(void**)(g_myframe+FF_OBJECT)=context;
    *(uint64_t*)(g_myframe+FF_CODE)=0; *(void**)(g_myframe+FF_LOCALS)=paramsBuf;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)F.child;
    BuildOutParms(F.child,(uint8_t*)paramsBuf);
    ((PFN_THUNK)F.thunk)(context, g_myframe, resultBuf);
}
static void SetFString(uint64_t* pbuf, const wchar_t* s){ int n=(int)wcslen(s)+1; ((uint64_t*)pbuf)[0]=(uint64_t)s; ((uint32_t*)pbuf)[2]=(uint32_t)n; ((uint32_t*)pbuf)[3]=(uint32_t)n; }
static uint32_t TypeFromPAFS(const wchar_t* idstr){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); SetFString(g_pbuf,idstr);
    Call(g_pafs,(void*)g_lam,g_pbuf,g_rbuf); return (uint32_t)(g_rbuf[0]&0xFFFFFFFF);
}
static int32_t QueryIdsK(uint32_t typeNameId, uint64_t ids[][2], int K){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    ((uint32_t*)g_pbuf)[0]=typeNameId; ((uint32_t*)g_pbuf)[1]=0;
    Call(g_gpail,(void*)g_lam,g_pbuf,g_rbuf);
    int32_t num=*(int32_t*)(((uint8_t*)g_pbuf)+16); uint64_t data=((uint64_t*)g_pbuf)[1];
    for(int i=0;i<K;i++){ ids[i][0]=0; ids[i][1]=0; }
    if(num>0 && LooksLikePtr((uintptr_t)data)){
        int lim = num<K?num:K;
        for(int i=0;i<lim;i++){ if(SafeReadable((void*)(data+i*16),16)){ ids[i][0]=*(uint64_t*)(data+i*16); ids[i][1]=*(uint64_t*)(data+i*16+8); } }
    }
    return num;
}
static bool startsWith(const char* s,const char* p){ return strncmp(s,p,strlen(p))==0; }
static int FindPoolSub(const char* sub){ for(int j=0;j<g_poolNum;j++){ if(strstr(g_poolNames[j],sub)) return j; } return -1; }
static void EnumerateAndMap(){
    uint32_t missionType=TypeFromPAFS(L"Mission:x"); uint32_t poolType=TypeFromPAFS(L"MissionPool:x");
    static uint64_t mtmp[NMAX][2], ptmp[NPOOL][2];
    g_missNum=QueryIdsK(missionType,mtmp,NMAX); if(g_missNum>NMAX)g_missNum=NMAX;
    g_poolNum=QueryIdsK(poolType,ptmp,NPOOL);   if(g_poolNum>NPOOL)g_poolNum=NPOOL;
    for(int j=0;j<g_poolNum;j++){ g_poolIds[j][0]=ptmp[j][0]; g_poolIds[j][1]=ptmp[j][1]; GetFNameStr((uint32_t)(ptmp[j][1]&0xFFFFFFFF),g_poolNames[j],48); }
    for(int i=0;i<g_missNum;i++){ g_missionIds[i][0]=mtmp[i][0]; g_missionIds[i][1]=mtmp[i][1]; GetFNameStr((uint32_t)(mtmp[i][1]&0xFFFFFFFF),g_missNames[i],48); }
    for(int i=0;i<g_missNum;i++){
        const char* n=g_missNames[i]; int pj=-1;
        if(startsWith(n,"Tournament")) pj=FindPoolSub("Tournament");
        else if(startsWith(n,"ArmoryDaily")) { pj=FindPoolSub("DailyChallenge"); if(pj<0)pj=FindPoolSub("Daily"); }
        else if(startsWith(n,"ArmoryOnboarding")||startsWith(n,"Armory")) pj=FindPoolSub("ArmoryOnboarding");
        else if(startsWith(n,"NewOnboarding")||startsWith(n,"Onboarding")) pj=FindPoolSub("Onboarding");
        else if(startsWith(n,"TimedSurvive")||startsWith(n,"CompleteAll")) pj=FindPoolSub("Tutorial");
        else pj=FindPoolSub("Hunter");
        if(pj<0) pj=0;
        g_missPool[i][0]=g_poolIds[pj][0]; g_missPool[i][1]=g_poolIds[pj][1];
    }
}
static void FireLoad(){
    for(int i=0;i<g_missNum;i++) memcpy(g_loadAssets+i*16, g_missionIds[i], 16);
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+0)=(uint64_t)g_pm;
    *(uint64_t*)((uint8_t*)g_pbuf+8)=(uint64_t)g_loadAssets;
    *(uint32_t*)((uint8_t*)g_pbuf+16)=(uint32_t)g_missNum;
    *(uint32_t*)((uint8_t*)g_pbuf+20)=(uint32_t)g_missNum;
    Call(g_load,(void*)g_lam,g_pbuf,g_rbuf); g_loadHandle=g_rbuf[0];
}
static uint64_t GLDA(uint64_t id0, uint64_t id1){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    g_pbuf[0]=id0; g_pbuf[1]=id1; Call(g_glda,(void*)g_lam,g_pbuf,g_rbuf); return g_rbuf[0];
}
// GetUniqueObjectiveName(LokiMissionObjectiveData Objective) -> FName. Objective(48B) is a const-ref OutParm
// (BuildOutParms provides Locals+0); return FName in r8. Returns the 8-byte FName packed in a u64.
static uint64_t GetUniqueObjName(const uint8_t* daStruct48){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    memcpy(g_pbuf, daStruct48, 0x30);          // Objective struct @ Locals+0 (48 bytes)
    Call(g_guon,(void*)g_lam,g_pbuf,g_rbuf);
    uint64_t nm=g_rbuf[0];
    if((uint32_t)nm==0){ uint64_t alt=*(uint64_t*)((uint8_t*)g_pbuf+0x30); if((uint32_t)alt) nm=alt; }  // fallback: ReturnValue @Locals+48
    return nm;
}
// ---- Option 2: fetch per-objective progress from ags, then look it up by unique name ----
// Minimal JSON scan of {"objectives":{"<name>":<num>,...}} — no dependencies. Runs OFF the game
// thread (in Worker), so blocking WinINet I/O never stalls the game.
static void ParseProgress(const char* json){
    g_progNum=0; const char* p=strstr(json,"\"objectives\""); if(!p) return; p=strchr(p,'{'); if(!p) return; p++;
    while(*p && g_progNum<PROGMAX){
        while(*p && *p!='"' && *p!='}') p++;
        if(*p=='}'||!*p) break;
        p++; const char* ks=p; while(*p && *p!='"') p++; if(!*p) break; int kl=(int)(p-ks); if(kl>KEYW-1)kl=KEYW-1;
        memcpy(g_progName[g_progNum],ks,kl); g_progName[g_progNum][kl]=0; p++;
        while(*p && *p!=':') p++; if(!*p) break; p++; while(*p==' ') p++;
        g_progVal[g_progNum]=(float)atof(p);
        while(*p && *p!=',' && *p!='}') p++;
        g_progNum++;
        if(*p==',') p++; else break;
    }
}
static void FetchProgress(){
    HINTERNET hi=InternetOpenA("supervive-missions-shim",INTERNET_OPEN_TYPE_DIRECT,nullptr,nullptr,0); if(!hi) return;
    HINTERNET hu=InternetOpenUrlA(hi,kProgressUrl,nullptr,0,INTERNET_FLAG_RELOAD|INTERNET_FLAG_NO_CACHE_WRITE|INTERNET_FLAG_PRAGMA_NOCACHE,0);
    if(hu){ static char buf[65536]; DWORD total=0,got=0;
        while(total<sizeof(buf)-1 && InternetReadFile(hu,buf+total,(DWORD)(sizeof(buf)-1-total),&got) && got){ total+=got; }
        buf[total]=0; if(total>0){ ParseProgress(buf); g_fetchOk=1; }
        InternetCloseHandle(hu);
    }
    InternetCloseHandle(hi);
}
// POST the mission->objective manifest (built game-side in BuildAndSwap) so ags can fan match-result
// deltas out to per-mission composite keys. Off the game thread; once per session.
static void PostManifest(){
    if(g_manifestPosted || g_manifestLen<=0) return;
    HINTERNET hi=InternetOpenA("supervive-missions-shim",INTERNET_OPEN_TYPE_DIRECT,nullptr,nullptr,0); if(!hi) return;
    HINTERNET hc=InternetConnectA(hi,"127.0.0.1",8080,nullptr,nullptr,INTERNET_SERVICE_HTTP,0,0);
    if(hc){
        const char* accept[]={"application/json",nullptr};
        HINTERNET hr=HttpOpenRequestA(hc,"POST","/revival/missions/manifest",nullptr,nullptr,accept,INTERNET_FLAG_RELOAD|INTERNET_FLAG_NO_CACHE_WRITE,0);
        if(hr){
            const char* hdr="Content-Type: application/json\r\n";
            if(HttpSendRequestA(hr,hdr,(DWORD)strlen(hdr),(void*)g_manifest,(DWORD)g_manifestLen)) g_manifestPosted=1;
            InternetCloseHandle(hr);
        }
        InternetCloseHandle(hc);
    }
    InternetCloseHandle(hi);
}
static float LookupProgress(const char* name){
    for(int i=0;i<g_progNum;i++) if(strcmp(g_progName[i],name)==0) return g_progVal[i];
    return 0.0f;
}
// Has the freshly-fetched progress changed vs. the last applied snapshot? (order-independent)
static bool ProgressChanged(){
    if(g_lastNum!=g_progNum) return true;
    for(int i=0;i<g_progNum;i++){
        bool found=false;
        for(int j=0;j<g_lastNum;j++){ if(strcmp(g_progName[i],g_lastName[j])==0){ if(g_lastVal[j]!=g_progVal[i]) return true; found=true; break; } }
        if(!found) return true;
    }
    return false;
}
static void SnapshotProgress(){
    g_lastNum=g_progNum;
    for(int i=0;i<g_progNum;i++){ memcpy(g_lastName[i],g_progName[i],KEYW); g_lastVal[i]=g_progVal[i]; }
}
// AppendManifest adds one {"mission","objective","max"[,"pool"]} entry to g_manifest (built game-side,
// POSTed off thread). mission/objective/pool are plain asset identifiers (no JSON escaping needed).
//
// pool (2026-07-10): the mission's pool NAME, so ags can group/rotate by pool server-side
// (POST /revival/missions/rotate {"pool":...}, GET /revival/missions/{status,coverage}). Optional — the
// server's ManifestEntry.Pool is omitempty, so an empty pool is simply absent.
// xp: the mission's total XP reward. Optional (omitted when <=0); server's ManifestEntry.XP is omitempty and
// feeds GET /revival/missions/status "xpEarned". Only the MISSIONS_XP_DRAFT build fills it (post-factory read,
// see RebuildManifestWithXP); the DEFAULT build always passes 0.0f, so pool-only output is unchanged. The
// value comes from MissionModel.XPReward@+0x60 on the OUTPUT model (an RE'd offset — NOT a guess), correlated
// to each input mission by MissionAssetId; see FillXPFromModel. Gated because rebuilding the manifest is a
// change to the working pool path that can't be runtime-validated headless.
static void AppendManifest(const char* mission, const char* obj, float mx, const char* pool, float xp){
    long len=g_manifestLen; if(len > (long)sizeof(g_manifest)-448) return;
    char poolField[80]={0};
    if(pool && pool[0]) _snprintf_s(poolField,sizeof(poolField),_TRUNCATE,",\"pool\":\"%s\"",pool);
    char xpField[48]={0};
    if(xp>0.0f) _snprintf_s(xpField,sizeof(xpField),_TRUNCATE,",\"xp\":%d",(int)xp);
    char tmp[448]; int n=_snprintf_s(tmp,sizeof(tmp),_TRUNCATE,"%s{\"mission\":\"%s\",\"objective\":\"%s\",\"max\":%d%s%s}",
        g_manifestEntries?",":"", mission, obj, (int)mx, poolField, xpField);
    if(n>0){ memcpy(g_manifest+len, tmp, n); g_manifestLen=len+n; g_manifestEntries++; }
}
// Build ObjectiveProgress[] for mission i from its loaded DA; returns objective count. Also records the
// per-mission composite manifest entries and looks up fetched progress by the composite key.
static int BuildObjectivesForMission(int i){
    uint64_t da=GLDA(g_missionIds[i][0],g_missionIds[i][1]);
    if(!LooksLikePtr((uintptr_t)da)) return 0;
    char internal[64]={0}; if(SafeReadable((void*)(da+DA_INTERNALNAME),4)) GetFNameStr(*(uint32_t*)(da+DA_INTERNALNAME),internal,64);
    if(!internal[0]) return 0;                            // no mission name -> can't form a composite key
    // Pool name for this mission (from the pool PrimaryAssetId assigned in EnumerateAndMap) -> manifest,
    // so ags can group/rotate by pool. Empty if unresolved (AppendManifest then omits the field).
    char poolName[48]={0}; GetFNameStr((uint32_t)(g_missPool[i][1]&0xFFFFFFFF),poolName,48);
#ifdef MISSIONS_XP_DRAFT
    if(i>=0 && i<NMAX) strncpy_s(g_missInternal[i],sizeof(g_missInternal[i]),internal,_TRUNCATE);  // for RebuildManifestWithXP
#endif
    if(!SafeReadable((void*)(da+DA_OBJECTIVES),16)) return 0;
    uint64_t odata=*(uint64_t*)(da+DA_OBJECTIVES); int32_t onum=*(int32_t*)(da+DA_OBJECTIVES+8);
    if(onum<=0 || !LooksLikePtr((uintptr_t)odata)) return 0;
    if(onum>MAXOBJ) onum=MAXOBJ;
    int made=0;
    for(int j=0;j<onum;j++){
        uintptr_t objAddr=(uintptr_t)odata + (uintptr_t)j*LMOD_SIZE;
        if(!SafeReadable((void*)objAddr,LMOD_SIZE)) continue;
        memcpy(g_daStruct, (void*)objAddr, LMOD_SIZE);
        uint64_t key=GetUniqueObjName(g_daStruct);
        float total=*(float*)(g_daStruct+LMOD_TOTAL);
        char objName[64]={0}; GetFNameStr((uint32_t)(key&0xFFFFFFFF),objName,64);
        char composite[KEYW]={0}; _snprintf_s(composite,sizeof(composite),_TRUNCATE,"%s/%s",internal,objName);  // "<mission>/<objective>"
        AppendManifest(internal, objName, total, poolName, 0.0f);   // xp=0 (default build); MISSIONS_XP_DRAFT rebuilds w/ xp post-factory
        float prog=LookupProgress(composite);            // per-mission progress from ags (else 0)
        if(prog>total) prog=total;                       // clamp so the bar never overfills
        if(prog>0.0f) InterlockedIncrement((volatile long*)&g_appliedNonZero);
        uint8_t* op=g_objprog + (i*MAXOBJ+made)*0x38; memset(op,0,0x38);
        *(uint64_t*)(op+0x00)=key;      // ObjectiveName (FName, 8B)
        *(float*)(op+0x08)=prog;        // Progress (fetched, per-mission)
        *(float*)(op+0x0C)=total;       // MaxProgress (informational; bar reads DA anyway)
        *(float*)(op+0x30)=0.0f;        // StartingProgress
        if(i<8 && made==0) g_vProg[i]=prog;
        made++;
    }
    return made;
}
#ifdef MISSIONS_XP_DRAFT
// FillXPFromModel reads XPReward off each OUTPUT MissionModel (from the array GetMissions() returned) and
// correlates it back to an input mission by MissionAssetId (a unique key), filling g_missXP[i]. Fully
// SafeReadable-guarded: any bad read leaves that mission's XP at 0 (the field is then omitted server-side),
// so a wrong offset degrades to "no xp", never a crash or a misassigned value.
//   MissionModel.MissionAssetId @ +0x40 (FPrimaryAssetId, 16B); MissionModel.XPReward @ +0x60 (float)  [RE'd s58/s59]
static void FillXPFromModel(uint64_t arrData, int num){
    for(int i=0;i<g_missNum && i<NMAX;i++) g_missXP[i]=0.0f;
    if(!LooksLikePtr((uintptr_t)arrData) || num<=0) return;
    for(int k=0;k<num;k++){
        if(!SafeReadable((void*)(arrData+(uint64_t)k*8),8)) continue;
        uint64_t mm=*(uint64_t*)(arrData+(uint64_t)k*8);            // TArray<UMissionModel*> element
        if(!LooksLikePtr((uintptr_t)mm)) continue;
        if(!SafeReadable((void*)(mm+0x40),16) || !SafeReadable((void*)(mm+0x60),4)) continue;
        uint64_t a0=*(uint64_t*)(mm+0x40), a1=*(uint64_t*)(mm+0x48); // MissionAssetId (FPrimaryAssetId)
        float xp=*(float*)(mm+0x60);                                // XPReward
        if(xp<=0.0f) continue;
        for(int i=0;i<g_missNum && i<NMAX;i++){
            if(g_missionIds[i][0]==a0 && g_missionIds[i][1]==a1){ g_missXP[i]=xp; break; }  // match by AssetId -> input i
        }
    }
}
// RebuildManifestWithXP re-serializes g_manifest from stored per-mission data, now including xp. Mirrors the
// inline build in BuildObjectivesForMission (same objective names + maxes + pool) but adds each mission's XP.
// Objective names/maxes come from the already-built FMissionObjectiveProgress rows (g_objprog[i][j]: FName key
// @0x00, MaxProgress @0x0C), so no DA is re-read.
static void RebuildManifestWithXP(){
    const char* head="{\"entries\":["; long hl=(long)strlen(head); memcpy(g_manifest,head,hl); g_manifestLen=hl; g_manifestEntries=0;
    for(int i=0;i<g_missNum && i<NMAX;i++){
        if(!g_missInternal[i][0]) continue;
        char poolName[48]={0}; GetFNameStr((uint32_t)(g_missPool[i][1]&0xFFFFFFFF),poolName,48);
        for(int j=0;j<g_objCount[i] && j<MAXOBJ;j++){
            uint8_t* op=g_objprog+(i*MAXOBJ+j)*0x38;
            uint32_t kid=*(uint32_t*)op; float total=*(float*)(op+0x0C);
            char objName[64]={0}; GetFNameStr(kid,objName,64);
            if(!objName[0]) continue;
            AppendManifest(g_missInternal[i], objName, total, poolName, g_missXP[i]);
        }
    }
    long l=g_manifestLen; if(l < (long)sizeof(g_manifest)-4){ g_manifest[l++]=']'; g_manifest[l++]='}'; g_manifest[l]=0; g_manifestLen=l; }
}
#endif
static void BuildAndSwap(){
    memset(g_elems,0,sizeof(g_elems)); memset(g_objprog,0,sizeof(g_objprog));
    // (re)build the manifest JSON header; entries are appended per objective in BuildObjectivesForMission.
    { const char* head="{\"entries\":["; long hl=(long)strlen(head); memcpy(g_manifest,head,hl); g_manifestLen=hl; g_manifestEntries=0; }
    for(int i=0;i<g_missNum;i++){
        int on=BuildObjectivesForMission(i); g_objCount[i]=on;
        _snwprintf_s(g_idbufs[i],8,_TRUNCATE,L"m%d",i); int n=(int)wcslen(g_idbufs[i])+1;
        uint8_t* el=g_elems+i*0x60;
        *(uint64_t*)(el+0)=(uint64_t)g_idbufs[i]; *(uint32_t*)(el+8)=(uint32_t)n; *(uint32_t*)(el+12)=(uint32_t)n;  // ID (DISTINCT)
        *(uint64_t*)(el+0x10)=g_missionIds[i][0]; *(uint64_t*)(el+0x18)=g_missionIds[i][1];  // AssetId
        *(uint64_t*)(el+0x20)=g_missPool[i][0];   *(uint64_t*)(el+0x28)=g_missPool[i][1];     // PoolId
        if(on>0){ *(uint64_t*)(el+0x38)=(uint64_t)(g_objprog+i*MAXOBJ*0x38); *(uint32_t*)(el+0x40)=(uint32_t)on; *(uint32_t*)(el+0x44)=(uint32_t)on; } // ObjectiveProgress
        *(int64_t*)(el+0x48)=86400000LL; *(int64_t*)(el+0x50)=638000000000000000LL; *(int64_t*)(el+0x58)=638000000000000000LL;
        if(i<8){ // capture verification for the first few
            strncpy_s(g_vMiss[i],sizeof(g_vMiss[i]),g_missNames[i],_TRUNCATE); g_vObjN[i]=on;
            if(on>0){ uint8_t* op=g_objprog+i*MAXOBJ*0x38; uint32_t kid=*(uint32_t*)op; GetFNameStr(kid,g_vKeyName[i],64); g_vTotal[i]=*(float*)(op+0x0C); }
        }
    }
    { long l=g_manifestLen; if(l < (long)sizeof(g_manifest)-4){ g_manifest[l++]=']'; g_manifest[l++]='}'; g_manifest[l]=0; g_manifestLen=l; } }  // close entries array
    g_nBuilt=g_missNum;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    ((uint64_t*)g_pbuf)[0]=(uint64_t)g_elems; ((uint32_t*)g_pbuf)[2]=(uint32_t)g_missNum; ((uint32_t*)g_pbuf)[3]=(uint32_t)g_missNum;
    Call(g_factory,(void*)g_mm,g_pbuf,g_rbuf); g_retModel=g_rbuf[0];
    if(LooksLikePtr(g_retModel)){
        ClassNameOf(g_retModel,g_modelCls,sizeof(g_modelCls));
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        Call(g_getMissions,(void*)g_retModel,g_pbuf,g_rbuf); g_modelNum=(int32_t)(g_rbuf[1]&0xFFFFFFFF);
        if(g_pm && g_modelNum>0){ *(uint64_t*)(g_pm+PM_MM)=g_retModel; g_swapped=true; }
#ifdef MISSIONS_XP_DRAFT
        // Enrich the manifest with per-mission XP before Worker POSTs it. g_rbuf[0] is still the GetMissions()
        // array data (untouched since the call above). Defensive: FillXPFromModel no-ops on any bad read.
        if(g_swapped){ FillXPFromModel(g_rbuf[0], g_modelNum); RebuildManifestWithXP(); }
#endif
    }
}
extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));
    if(g_state==0){
        EnumerateAndMap();
        FireLoad();
        g_t0=GetTickCount(); g_state=1;
    } else if(g_state==1){
        // Wait until MOST DAs have loaded (registered != loaded), not just mission[0], so we never swap a
        // DEGRADED model (missions with no objectives). Sample a spread of missions; proceed at >=90% loaded,
        // or after 35s if we at least got a majority. If loading badly stalled (<50% at timeout), SKIP the
        // swap entirely (leave the game's own empty model) rather than push a malformed one.
        int sample = g_missNum<60?g_missNum:60; int loaded=0;
        for(int k=0;k<sample;k++){ int mi=(g_missNum>0)?(k*g_missNum/sample):0; if(LooksLikePtr((uintptr_t)GLDA(g_missionIds[mi][0],g_missionIds[mi][1]))) loaded++; }
        g_loadedCheck=loaded;
        bool enough = (sample>0 && loaded>=sample*9/10);
        bool timeout = GetTickCount()-g_t0>35000;
        if(enough || timeout){
            uint64_t da=GLDA(g_missionIds[0][0],g_missionIds[0][1]);
            g_glLoaded=da; if(LooksLikePtr(g_glLoaded)) ClassNameOf(g_glLoaded,g_glCls,sizeof(g_glCls));
            if(enough || (timeout && sample>0 && loaded>=sample/2)) BuildAndSwap();   // only swap a well-formed model
            g_state=2; g_done=1;
        }
    }
    g_inHook=0;
}

static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};for(int i=0;i<2;i++){if(!cands[i])continue;void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(p){intptr_t d=(intptr_t)p-(intptr_t)anchor;if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000)return (uint8_t*)p;VirtualFree(p,0,MEM_RELEASE);}}}return nullptr;}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
static uint8_t* BuildHook(uintptr_t fn,const uint8_t stolen[5]){
    uint8_t* blk=NearAlloc(fn,0x200); if(!blk)return nullptr;
    Emit t{blk}; for(int i=0;i<5;i++)EB(t,stolen[i]); EB(t,0xE9); int32_t rel=(int32_t)((intptr_t)(fn+5)-((intptr_t)t.w+4)); EU32(t,(uint32_t)rel); g_tramp=(PFN_PE)blk;
    uint8_t* stub=blk+0x20; Emit e{stub};
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51); EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnPI); EB(e,0xFF);EB(e,0xD0);
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28); EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk); EB(e,0xFF);EB(e,0xE0);
    return stub;
}
static bool SafeWrite(uint8_t* dst,const uint8_t* src,size_t len){
    DWORD myTid=GetCurrentThreadId(),myPid=GetCurrentProcessId(); HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0); if(snap==INVALID_HANDLE_VALUE)return false;
    HANDLE hs[1024]; int nh=0; THREADENTRY32 te; te.dwSize=sizeof(te);
    if(Thread32First(snap,&te)){do{if(te.th32OwnerProcessID==myPid&&te.th32ThreadID!=myTid&&nh<1024){HANDLE ht=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,te.th32ThreadID);if(ht)hs[nh++]=ht;}}while(Thread32Next(snap,&te));} CloseHandle(snap);
    uintptr_t lo=(uintptr_t)dst,hi=(uintptr_t)dst+len; bool ok=false;
    for(int a=0;a<400&&!ok;a++){ for(int i=0;i<nh;i++)SuspendThread(hs[i]); bool unsafe=false;
        for(int i=0;i<nh;i++){CONTEXT c;c.ContextFlags=CONTEXT_CONTROL;if(GetThreadContext(hs[i],&c)){if(c.Rip>=lo&&c.Rip<hi){unsafe=true;break;}}}
        if(!unsafe){DWORD op=0;if(VirtualProtect(dst,len,PAGE_EXECUTE_READWRITE,&op)){memcpy(dst,src,len);DWORD d=0;VirtualProtect(dst,len,op,&d);FlushInstructionCache(GetCurrentProcess(),dst,len);ok=true;}}
        if(!ok){for(int i=0;i<nh;i++)ResumeThread(hs[i]);Sleep(1);} }
    for(int i=0;i<nh;i++){ResumeThread(hs[i]);CloseHandle(hs[i]);} return ok;
}
static bool InstallHook(){ if(!g_pi||!g_stub)return false; int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5)); uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)}; return SafeWrite(g_pi,p,5); }
static void UninstallHook(){ if(g_pi)SafeWrite(g_pi,g_stolen,5); }
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}
static void ResolveFn(uintptr_t cls,const char* fname,Fn* F){
    uintptr_t f=0; if(SafeReadable((void*)(cls+0x50),8)) f=*(uintptr_t*)(cls+0x50); int i=0;
    while(LooksLikePtr(f)&&i<800){ if(NameIs(f,fname)){ F->fn=(void*)f; if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))F->thunk=th;} if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))F->child=cp;} return; } uintptr_t nx=0; if(SafeReadable((void*)(f+0x30),8))nx=*(uintptr_t*)(f+0x30); f=nx; i++; }
}
static uintptr_t FindClass(const char* clsname){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,clsname)){ char cn[64]; uintptr_t c=ClassOf(obj); if(c&&GetFNameStr(NameId(c),cn,sizeof(cn))&&strstr(cn,"Class")) return obj; } } }
    return 0;
}
static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t ksl=0,lam=0,pm=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!ksl && NameIs(obj,"KismetSystemLibrary")){ char cn[64]="?"; uintptr_t c=ClassOf(obj); if(c)GetFNameStr(NameId(c),cn,sizeof(cn)); if(strstr(cn,"Class")) ksl=obj; }
            if(!lam && ClassNameIs(obj,"LokiAssetManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) lam=obj; }
            if(!pm && ClassNameIs(obj,"ProgressionManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) pm=obj; } } }
    if(!ksl||!lam||!pm)return; g_lam=lam; g_pm=pm;
    if(SafeReadable((void*)(pm+PM_MM),8)){ uintptr_t mm=*(uintptr_t*)(pm+PM_MM); if(LooksLikePtr(mm)) g_mm=mm; }
    if(!g_mm)return;
    uintptr_t lamCls=ClassOf(lam), mmCls=ClassOf(g_mm);
    if(lamCls){ ResolveFn(lamCls,"PrimaryAssetIDFromString",&g_pafs); ResolveFn(lamCls,"GetLokiDataAsset",&g_glda); ResolveFn(lamCls,"AsyncLoadPrimaryAssets",&g_load); }
    ResolveFn(ksl,"GetPrimaryAssetIdList",&g_gpail);
    if(mmCls){ ResolveFn(mmCls,"CreateMissionModelFromFinalProgress",&g_factory); ResolveFn(mmCls,"GetMissions",&g_getMissions); }
    if(!g_guon.thunk){ uintptr_t las=FindClass("LokiAssetStatics"); if(las) ResolveFn(las,"GetUniqueObjectiveName",&g_guon); }  // FindClass returns the CLASS itself; do NOT ClassOf() it
}

// ApplyOnce: one fetch-driven rebuild+swap on the game thread. Re-arms the pipeline (g_state/g_done),
// installs the PI hook, waits for the hook to complete the swap, then unhooks. Requires funcs+model
// resolved and g_stub built. Returns whether the swap landed.
static bool ApplyOnce(DWORD budgetMs){
    g_state=0; g_done=0; g_appliedNonZero=0; g_swapped=false; g_t0=0;
    HookLock();                                          // serialize vs pi8's PI hook
    if(!InstallHook()){ HookUnlock(); return false; }
    DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<budgetMs) Sleep(20);
    UninstallHook();
    HookUnlock();
    return g_swapped;
}

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] missions_fix (Option 2 durable: ags-fetched progress on launch + poll-on-change) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_hookMutex=CreateMutexA(nullptr,FALSE,"Local\\SuperviveMissionsPIHook");   // shared with mainmenu_refresh_pi8
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ Resolve(); if(g_lam&&g_mm&&g_pm&&g_pafs.thunk&&g_gpail.thunk&&g_factory.thunk&&g_getMissions.thunk&&g_glda.thunk&&g_load.thunk&&g_guon.thunk)break; Sleep(500);}
    if(!g_lam||!g_mm||!g_pm||!g_pafs.thunk||!g_gpail.thunk||!g_factory.thunk||!g_getMissions.thunk||!g_glda.thunk||!g_load.thunk||!g_guon.thunk){Markerf("[2] FAIL resolve lam=%llX mm=%llX pm=%llX pafs=%llX gpail=%llX fac=%llX gm=%llX glda=%llX load=%llX guon=%llX\r\n",(unsigned long long)g_lam,(unsigned long long)g_mm,(unsigned long long)g_pm,(unsigned long long)g_pafs.thunk,(unsigned long long)g_gpail.thunk,(unsigned long long)g_factory.thunk,(unsigned long long)g_getMissions.thunk,(unsigned long long)g_glda.thunk,(unsigned long long)g_load.thunk,(unsigned long long)g_guon.thunk);return 3;}
    Markerf("[2] lam=%llX mm=%llX guon-thunk=%llX all funcs resolved gameTid=%lu\r\n",(unsigned long long)g_lam,(unsigned long long)g_mm,(unsigned long long)g_guon.thunk,g_gameTid);
    g_pi=(uint8_t*)(g_modBase+kPiRva);
    HookLock();   // capture the ORIGINAL prologue + build the trampoline while pi8 is guaranteed unhooked
    if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){HookUnlock();Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen);
    HookUnlock();
    if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    // ---- initial apply on menu load ----
    FetchProgress();
    Markerf("[3] fetched ags progress: ok=%d entries=%d (%s) -> build keyed model w/ progress -> swap...\r\n",g_fetchOk,g_progNum,kProgressUrl);
    bool ok=ApplyOnce(40000);
    if(ok){
        SnapshotProgress(); InterlockedIncrement(&g_applyCount);
        PostManifest();   // register mission->objective structure so match results fan out per-mission
        Markerf("[4] apply#%ld: missions=%d pools=%d model=0x%llX Num=%d fetchOk=%d entries=%d appliedNonZero=%d\r\n",
            (long)g_applyCount,g_missNum,g_poolNum,(unsigned long long)g_retModel,g_modelNum,g_fetchOk,g_progNum,g_appliedNonZero);
        Markerf("[4] manifest: %d entries POSTed=%d (per-mission composite keys)\r\n",g_manifestEntries,g_manifestPosted);
        for(int i=0;i<8 && i<g_missNum;i++) Markerf("[4]   m%d '%s': key0='%s' prog0=%.1f total0=%.1f\r\n",i,g_vMiss[i],g_vKeyName[i],g_vProg[i],g_vTotal[i]);
        Marker("[4] *** swapped w/ fetched progress. Reopen the Missions modal to see it. Now polling ags for changes... ***\r\n");
    } else { Markerf("[4] initial apply FAILED (hitsGT=%ld state=%ld) — will keep polling\r\n",(long)g_hitsGT,(long)g_state); }

    // ---- durable poll loop: re-apply only when ags progress changes (e.g. a match posted /add) ----
    for(;;){
        Sleep(kPollMs);
        if(!GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe")) break;   // process gone
        FetchProgress();
        if(!ProgressChanged()) continue;
        bool rok=ApplyOnce(40000);
        if(rok){ SnapshotProgress(); InterlockedIncrement(&g_applyCount);
            Markerf("[poll] apply#%ld: progress changed -> re-swapped (entries=%d appliedNonZero=%d). Reopen modal to refresh.\r\n",(long)g_applyCount,g_progNum,g_appliedNonZero); }
        else Markerf("[poll] progress changed but re-apply failed (state=%ld)\r\n",(long)g_state);
    }
    Marker("[done] worker exit (game closed)\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
