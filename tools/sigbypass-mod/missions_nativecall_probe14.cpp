// missions_nativecall_probe12 — SESSION 58: RE-TEST the factory now that OUT-param calls work.
// s52 said CreateMissionModelFromFinalProgress "rejects synthetic data / returns null" — but that was the
// OUT-param crash (its array param is CPF_OutParm) / a no-op call; it was never really run. Now, with the
// OutParms@+0x80 fix (probe11) and missions REGISTERED (probe11: 330 ids), feed it a REAL registered mission
// id and see if it builds a model.
// Steps (all via the primitive, OutParms fix applied to every OUT param):
//   1. PrimaryAssetIDFromString("Mission:x") -> Mission type FName; same for MissionPool.
//   2. GetPrimaryAssetIdList(MissionType) [OUT TArray] -> read Data[0] = a real registered mission FPrimaryAssetId.
//      GetPrimaryAssetIdList(MissionPoolType) -> pool[0].
//   3. Build 1 FMissionProgress (0x60): AssetId=mission[0], PoolId=pool[0], valid dates.
//   4. CreateMissionModelFromFinalProgress({&elem,1,1}) [OUT array param] -> MissionsModel*.
//   5. If non-null: GetMissions(model) [return-by-value] -> Num.
// Build:  clang++ -shared -O2 missions_nativecall_probe12.cpp -o missions_nativecall_probe12.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> ...  Marker: docs/missions-nativecall12-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\missions-nativecall14-marker.txt";
// probe14: (1) AsyncLoadPrimaryAssets the N mission DAs (registered!=loaded), poll GetLokiDataAsset until they
// resolve; (2) build a MissionsModel with N DISTINCT-ID missions (map is ID-keyed) across real pools;
// (3) SWAP it into ProgMgr.MissionsModel. Then reopen the modal (computer-use) -> real tiles.
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, PM_MM=0x3B8, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_OUTPARMS=0x80, FF_PROPCHAIN=0x88;
constexpr uintptr_t FLD_NEXT=0x18, FLD_FLAGS=0x38, FLD_OFFSET=0x44;
constexpr uint64_t CPF_OutParm=0x100, CPF_ReturnParm=0x400;
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

struct Fn { void* fn; uintptr_t thunk; uintptr_t child; };
static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_lam=0, g_mm=0, g_pm=0;         // LokiAssetManager singleton, live MissionsModel (knownMM), ProgMgr
static Fn g_pafs{}, g_gpail{}, g_factory{}, g_getMissions{}, g_glda{}, g_load{};
static uint8_t g_loadAssets[8*16]={0};            // TArray data for AsyncLoadPrimaryAssets
static wchar_t g_idbufs[8][6]={ L"M0",L"M1",L"M2",L"M3",L"M4",L"M5",L"M6",L"M7" };  // distinct FMissionProgress.ID
static volatile long g_state=0; static DWORD g_t0=0; static uint64_t g_loadHandle=0; static int g_loadedCheck=0;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};
static uint64_t g_pbuf[16]={0}, g_rbuf[4]={0}; static uint8_t g_outparms[8*24]={0};
constexpr int NMISS=8;
static uint8_t g_elems[NMISS*0x60]={0};
static uint64_t g_missionIds[NMISS][2]={{0}}, g_poolIds[NMISS][2]={{0}}, g_retModel=0, g_glLoaded=0;
static int32_t g_missNum=-1, g_poolNum=-1, g_modelNum=-1; static char g_modelCls[96]={0}, g_poolNames[NMISS][48]={{0}}, g_glCls[64]={0};
static bool g_swapped=false;

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
// gpail(type) -> reads OUT array; returns Num and copies the first K ids (16B FPrimaryAssetId each) into ids[K][2].
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
static void FireLoad(){
    for(int i=0;i<NMISS;i++) memcpy(g_loadAssets+i*16, g_missionIds[i], 16);
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+0)=(uint64_t)g_pm;              // WorldContextObject @0
    *(uint64_t*)((uint8_t*)g_pbuf+8)=(uint64_t)g_loadAssets;     // Assets.Data @8
    *(uint32_t*)((uint8_t*)g_pbuf+16)=NMISS;                     // Assets.Num
    *(uint32_t*)((uint8_t*)g_pbuf+20)=NMISS;                     // Assets.Max
    // OnLoadComplete delegate @24 = 0 (empty). ReturnValue -> r8.
    Call(g_load,(void*)g_lam,g_pbuf,g_rbuf); g_loadHandle=g_rbuf[0];
}
static uint64_t GLDA(uint64_t id0, uint64_t id1){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    g_pbuf[0]=id0; g_pbuf[1]=id1; Call(g_glda,(void*)g_lam,g_pbuf,g_rbuf); return g_rbuf[0];
}
static void BuildAndSwap(){
    memset(g_elems,0,sizeof(g_elems));
    for(int i=0;i<NMISS;i++){
        uint8_t* el=g_elems+i*0x60; int n=(int)wcslen(g_idbufs[i])+1;
        *(uint64_t*)(el+0)=(uint64_t)g_idbufs[i]; *(uint32_t*)(el+8)=(uint32_t)n; *(uint32_t*)(el+12)=(uint32_t)n;  // ID (DISTINCT)
        *(uint64_t*)(el+0x10)=g_missionIds[i][0]; *(uint64_t*)(el+0x18)=g_missionIds[i][1];  // AssetId
        *(uint64_t*)(el+0x20)=g_poolIds[i][0];    *(uint64_t*)(el+0x28)=g_poolIds[i][1];      // PoolId
        *(int64_t*)(el+0x48)=86400000LL; *(int64_t*)(el+0x50)=638000000000000000LL; *(int64_t*)(el+0x58)=638000000000000000LL;
        GetFNameStr((uint32_t)(g_poolIds[i][1]&0xFFFFFFFF), g_poolNames[i], 48);
    }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    ((uint64_t*)g_pbuf)[0]=(uint64_t)g_elems; ((uint32_t*)g_pbuf)[2]=NMISS; ((uint32_t*)g_pbuf)[3]=NMISS;
    Call(g_factory,(void*)g_mm,g_pbuf,g_rbuf); g_retModel=g_rbuf[0];
    if(LooksLikePtr(g_retModel)){
        ClassNameOf(g_retModel,g_modelCls,sizeof(g_modelCls));
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        Call(g_getMissions,(void*)g_retModel,g_pbuf,g_rbuf); g_modelNum=(int32_t)(g_rbuf[1]&0xFFFFFFFF);
        if(g_pm && g_modelNum>0){ *(uint64_t*)(g_pm+PM_MM)=g_retModel; g_swapped=true; }
    }
}
extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));
    if(g_state==0){
        uint32_t missionType=TypeFromPAFS(L"Mission:x"); uint32_t poolType=TypeFromPAFS(L"MissionPool:x");
        g_missNum=QueryIdsK(missionType,g_missionIds,NMISS);
        g_poolNum=QueryIdsK(poolType,g_poolIds,NMISS);
        FireLoad();                                  // async-load the N mission DAs
        g_t0=GetTickCount(); g_state=1;
    } else if(g_state==1){
        uint64_t da=GLDA(g_missionIds[0][0],g_missionIds[0][1]);
        g_loadedCheck = LooksLikePtr((uintptr_t)da)?1:0;
        if(g_loadedCheck || GetTickCount()-g_t0>12000){   // loaded, or give up after 12s
            g_glLoaded=da; if(LooksLikePtr(g_glLoaded)) ClassNameOf(g_glLoaded,g_glCls,sizeof(g_glCls));
            BuildAndSwap();                          // build N distinct-ID missions + swap into ProgMgr
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
}

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] missions_nativecall_probe14 (async-load DAs + build N distinct-ID missions + swap) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ Resolve(); if(g_lam&&g_mm&&g_pm&&g_pafs.thunk&&g_gpail.thunk&&g_factory.thunk&&g_getMissions.thunk&&g_glda.thunk&&g_load.thunk)break; Sleep(500);}
    if(!g_lam||!g_mm||!g_pm||!g_pafs.thunk||!g_gpail.thunk||!g_factory.thunk||!g_getMissions.thunk||!g_glda.thunk||!g_load.thunk){Markerf("[2] FAIL resolve lam=%llX mm=%llX pm=%llX pafs=%llX gpail=%llX fac=%llX gm=%llX glda=%llX load=%llX\r\n",(unsigned long long)g_lam,(unsigned long long)g_mm,(unsigned long long)g_pm,(unsigned long long)g_pafs.thunk,(unsigned long long)g_gpail.thunk,(unsigned long long)g_factory.thunk,(unsigned long long)g_getMissions.thunk,(unsigned long long)g_glda.thunk,(unsigned long long)g_load.thunk);return 3;}
    Markerf("[2] lam=%llX mm=%llX all funcs resolved gameTid=%lu\r\n",(unsigned long long)g_lam,(unsigned long long)g_mm,g_gameTid);
    g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Marker("[3] hook built; async-load DAs -> wait -> build N distinct-ID missions -> swap into ProgMgr.MissionsModel...\r\n");
    if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");return 6;}
    DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<25000) Sleep(20);
    UninstallHook();
    if(g_done){
        Markerf("[4] missions registered=%d, pools=%d. Built %d-mission model=0x%llX class='%s' GetMissions().Num=%d\r\n",g_missNum,g_poolNum,NMISS,(unsigned long long)g_retModel,g_modelCls,g_modelNum);
        char pl[400]={0}; for(int i=0;i<NMISS;i++){ char one[64]; _snprintf_s(one,sizeof(one),_TRUNCATE,"%s%s",i?",":"",g_poolNames[i]); strncat_s(pl,sizeof(pl),one,_TRUNCATE);}
        Markerf("[4] pools used: %s\r\n",pl);
        Markerf("[4] mission[0] DA loaded? GetLokiDataAsset=0x%llX class='%s'\r\n",(unsigned long long)g_glLoaded,g_glCls);
        Markerf("[4] SWAP ProgMgr.MissionsModel -> new model: %s (old knownMM=0x%llX new=0x%llX)\r\n",g_swapped?"DONE":"SKIPPED",(unsigned long long)g_mm,(unsigned long long)g_retModel);
        if(g_swapped && LooksLikePtr(g_glLoaded)) Marker("[4] *** model populated + DA loaded + swapped in => OPEN the Missions modal (computer-use) — tiles should render. ***\r\n");
        else if(g_swapped) Marker("[4] *** model populated + swapped, but mission DA NOT loaded (GetLokiDataAsset null) => tiles may be blank; need AsyncLoadPrimaryAssets first. Open modal to confirm. ***\r\n");
        else Marker("[4] => not swapped (model empty/null).\r\n");
    } else Markerf("[4] TIMEOUT (hitsGT=%ld)\r\n",(long)g_hitsGT);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
