// missions_nativecall_probe9 — SESSION 57: mission-DA RESOLUTION re-test via the WORKING primitive.
// s52 concluded mission DAs "don't resolve as primary assets" — but that test used the NO-OP
// ProcessEvent-from-hook primitive (the calls never ran). Re-test with Avenue A (direct thunk + params):
//   CONTROL: PrimaryAssetIDFromString("Hero:Alchemist") -> GetLokiDataAsset(id) -> should be a non-null Hero DA.
//   TEST:    PrimaryAssetIDFromString("Mission:ArmoryDaily_PlayAGame") -> GetLokiDataAsset(id) -> ?
// If the control resolves (proves the primitive + asset-manager path work) and the mission does NOT, missions
// genuinely need registration. If BOTH resolve, s52's negative was purely the no-op and missions load by path.
//
// Both natives are LokiAssetManager members (Context=the LokiAssetManager singleton), param[0]@Locals+0:
//   PrimaryAssetIDFromString(AssetIDString:FString@0) -> FPrimaryAssetId (16B struct, written to r8/Result).
//   GetLokiDataAsset(PrimaryAssetId:struct@0)         -> LokiDataAsset_Base* (written to r8/Result).
// FPrimaryAssetId = {FName Type@+0, FName Name@+8}. Param recipe: Code=NULL, Locals=paramsBuf,
// PropertyChainForCompiledIn@+0x88 = Function.ChildProperties(*(UFunc+0x58)).
// Build:  clang++ -shared -O2 missions_nativecall_probe9.cpp -o missions_nativecall_probe9.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> ...  Marker: docs/missions-nativecall9-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\missions-nativecall9-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_PROPCHAIN=0x88;
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_lam=0;                          // LokiAssetManager singleton instance
static void* g_pafs=nullptr; static uintptr_t g_pafsThunk=0, g_pafsChild=0;   // PrimaryAssetIDFromString
static void* g_glda=nullptr; static uintptr_t g_gldaThunk=0, g_gldaChild=0;   // GetLokiDataAsset
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};
static uint64_t g_pbuf[16]={0}, g_rbuf[4]={0};
// results
static uint64_t g_heroId[2]={0}, g_missionId[2]={0}, g_heroDA=0, g_missionDA=0;
static char g_heroDACls[96]={0}, g_missionDACls[96]={0};

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
static void FNameStr(uint32_t id,char* out,int cap){ if(!GetFNameStr(id,out,cap)){ _snprintf_s(out,cap,_TRUNCATE,"#%u",id);} }

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>8)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);
    return EXCEPTION_CONTINUE_SEARCH;
}

// Generic: call a native UFunction with a prepared params buffer (param[0]@Locals+0). Result -> resultBuf.
static void CallNative(void* func, uintptr_t thunk, uintptr_t childProps, void* context, void* paramsBuf, void* resultBuf){
    memcpy(g_myframe, g_template, sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=func;
    *(void**)(g_myframe+FF_OBJECT)=context;
    *(uint64_t*)(g_myframe+FF_CODE)=0;
    *(void**)(g_myframe+FF_LOCALS)=paramsBuf;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)childProps;
    ((PFN_THUNK)thunk)(context, g_myframe, resultBuf);
}
// Set an FString {Data,Num,Max} into pbuf[0..] from a wide literal (Num includes null terminator).
static void SetFString(uint64_t* pbuf, const wchar_t* s){
    int n=(int)wcslen(s)+1;
    ((uint64_t*)pbuf)[0]=(uint64_t)s;
    ((uint32_t*)pbuf)[2]=(uint32_t)n;
    ((uint32_t*)pbuf)[3]=(uint32_t)n;
}
static const wchar_t* kHero    = L"Hero:Alchemist";
static const wchar_t* kMission = L"Mission:ArmoryDaily_PlayAGame";

extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));
    // 1) PrimaryAssetIDFromString("Hero:Alchemist") -> g_heroId (16B FPrimaryAssetId in g_rbuf[0..1])
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); SetFString(g_pbuf,kHero);
    CallNative(g_pafs,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf); g_heroId[0]=g_rbuf[0]; g_heroId[1]=g_rbuf[1];
    // 2) GetLokiDataAsset(heroId) -> g_heroDA
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); g_pbuf[0]=g_heroId[0]; g_pbuf[1]=g_heroId[1];
    CallNative(g_glda,g_gldaThunk,g_gldaChild,(void*)g_lam,g_pbuf,g_rbuf); g_heroDA=g_rbuf[0];
    if(LooksLikePtr(g_heroDA)) ClassNameOf(g_heroDA,g_heroDACls,sizeof(g_heroDACls));
    // 3) PrimaryAssetIDFromString("Mission:ArmoryDaily_PlayAGame") -> g_missionId
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); SetFString(g_pbuf,kMission);
    CallNative(g_pafs,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf); g_missionId[0]=g_rbuf[0]; g_missionId[1]=g_rbuf[1];
    // 4) GetLokiDataAsset(missionId) -> g_missionDA
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); g_pbuf[0]=g_missionId[0]; g_pbuf[1]=g_missionId[1];
    CallNative(g_glda,g_gldaThunk,g_gldaChild,(void*)g_lam,g_pbuf,g_rbuf); g_missionDA=g_rbuf[0];
    if(LooksLikePtr(g_missionDA)) ClassNameOf(g_missionDA,g_missionDACls,sizeof(g_missionDACls));
    g_done=1; g_inHook=0;
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

static void ResolveFuncOnClass(uintptr_t cls,const char* fname,void** func,uintptr_t* thunk,uintptr_t* child){
    uintptr_t f=0; if(SafeReadable((void*)(cls+0x50),8)) f=*(uintptr_t*)(cls+0x50); int i=0;
    while(LooksLikePtr(f)&&i<400){ if(NameIs(f,fname)){ *func=(void*)f; if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))*thunk=th;} if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))*child=cp;} return; } uintptr_t nx=0; if(SafeReadable((void*)(f+0x30),8))nx=*(uintptr_t*)(f+0x30); f=nx; i++; }
}
static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t lam=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!lam && ClassNameIs(obj,"LokiAssetManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) lam=obj; } } }
    if(!lam)return; g_lam=lam;
    uintptr_t cls=ClassOf(lam); if(!cls)return;
    ResolveFuncOnClass(cls,"PrimaryAssetIDFromString",&g_pafs,&g_pafsThunk,&g_pafsChild);
    ResolveFuncOnClass(cls,"GetLokiDataAsset",&g_glda,&g_gldaThunk,&g_gldaChild);
}

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] missions_nativecall_probe9 (mission-DA resolution re-test: PrimaryAssetIDFromString + GetLokiDataAsset) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ Resolve(); if(g_lam&&g_pafsThunk&&g_pafsChild&&g_gldaThunk&&g_gldaChild)break; Sleep(500);}
    if(!g_lam||!g_pafsThunk||!g_gldaThunk){Markerf("[2] FAIL resolve lam=0x%llX pafs=0x%llX glda=0x%llX\r\n",(unsigned long long)g_lam,(unsigned long long)g_pafsThunk,(unsigned long long)g_gldaThunk);return 3;}
    Markerf("[2] LokiAssetManager=0x%llX pafsThunk=0x%llX gldaThunk=0x%llX gameTid=%lu\r\n",(unsigned long long)g_lam,(unsigned long long)g_pafsThunk,(unsigned long long)g_gldaThunk,g_gameTid);
    g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Marker("[3] hook built; chaining PrimaryAssetIDFromString + GetLokiDataAsset (Hero control + Mission test)...\r\n");
    if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");return 6;}
    DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
    UninstallHook();
    if(g_done){
        char ht[64],hn[64],mt[64],mn[64];
        FNameStr((uint32_t)(g_heroId[0]&0xFFFFFFFF),ht,sizeof(ht)); FNameStr((uint32_t)(g_heroId[1]&0xFFFFFFFF),hn,sizeof(hn));
        FNameStr((uint32_t)(g_missionId[0]&0xFFFFFFFF),mt,sizeof(mt)); FNameStr((uint32_t)(g_missionId[1]&0xFFFFFFFF),mn,sizeof(mn));
        Markerf("[4] CONTROL Hero: id={Type=%s Name=%s} raw={0x%llX,0x%llX} DA=0x%llX class='%s'\r\n",ht,hn,(unsigned long long)g_heroId[0],(unsigned long long)g_heroId[1],(unsigned long long)g_heroDA,g_heroDACls);
        Markerf("[4] TEST   Mission: id={Type=%s Name=%s} raw={0x%llX,0x%llX} DA=0x%llX class='%s'\r\n",mt,mn,(unsigned long long)g_missionId[0],(unsigned long long)g_missionId[1],(unsigned long long)g_missionDA,g_missionDACls);
        if(LooksLikePtr(g_heroDA)&&LooksLikePtr(g_missionDA)) Marker("[4] *** BOTH resolve => the primitive loads mission DAs by id. s52's negative was the no-op. Missions are RESOLVABLE. ***\r\n");
        else if(LooksLikePtr(g_heroDA)) Marker("[4] => CONTROL resolves but MISSION does NOT => missions genuinely need registration/scan. (primitive+asset path proven by the control.)\r\n");
        else Marker("[4] => even the CONTROL is null: primitive/asset-path issue OR id parse failed — inspect raw ids.\r\n");
    } else Markerf("[4] TIMEOUT no game-thread PI in 8s (hitsGT=%ld)\r\n",(long)g_hitsGT);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
