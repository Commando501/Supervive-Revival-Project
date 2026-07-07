// missions_populate2 — SESSION 52 Phase-2b EXPERIMENT: call CreateMissionModelFromFinalProgress
// with one constructed MissionProgress, then check GetMissions().Num — does the factory INSERT into
// the MissionsModel.Missions map, or only build a model? Log-only (no broadcast, no manual insert).
// Uses the VERIFIED primitive: ProcessInternal hook -> ProcessEvent(native MissionsModel method).
//
// MissionProgress (size 0x60): ID(FString)@0x00 AssetId(FPrimaryAssetId)@0x10 PoolId@0x20
//   Complete@0x30 Failed@0x31 ObjectiveProgress(TArray)@0x38 MillisUntilExpiry(i64)@0x48
//   Expiry(FDateTime i64)@0x50 GrantedAt@0x58.  FPrimaryAssetId = {FName Type(8), FName Name(8)}.
// FNames (this exe): Mission=0x000162B8, ArmoryDaily_PlayAGame=0x003FB29E, MissionPool=0x00016F06.
// Factory params (ProcessEvent flat buffer): [0..15]=TArray<MissionProgress>{ptr,num,max}, [16..23]=ReturnValue(UMissionModel*).
// Build:  clang++ -shared -O2 missions_populate2.cpp -o missions_populate2.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/missions_populate2.dll
// Marker: docs/missions-populate2-marker.txt   (ONE ProcessInternal-hooking shim per client!)
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath="G:\\git\\Supervive Revival Project\\docs\\missions-populate2-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0,kPeRva=0x12C5A10,kObjObjectsRva=0x9E38930,kNamePoolRva=0x9D81450,kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536,ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18,NAME_OFF=0x20,OUTER_OFF=0x28,PM_MM=0x3B8;
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void*,void*,void*);

static uintptr_t g_modBase=0; static volatile PFN_PE g_tramp=nullptr; static PFN_PE g_processEvent=nullptr;
static uintptr_t g_mm=0; static void* g_getMissions=nullptr; static void* g_factory=nullptr;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0};
static volatile long g_pending=0,g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
// constructed inputs (static so they live in committed DLL memory the game can read)
static wchar_t g_idbuf[64]=L"ArmoryDaily_PlayAGame";
static uint8_t g_mp[0x60]={0};                 // one MissionProgress
static uint64_t g_arr[2]={0,0};                // TArray header: [0]=Data, [1]= (Num<<0 | Max<<32)
static uint64_t g_facParams[4]={0};            // [0..1]=TArray(16B), [2]=ReturnValue, [3]=pad
static uint64_t g_getParams[2]={0};            // TArray<...> return
static uintptr_t g_retModel=0; static int32_t g_numBefore=-1,g_numAfter=-1;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000&&v<0x0001000000000000ULL&&(v&7)==0;}
static bool GetFNameStr(uint32_t id,char* out,int cap){uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva);uint32_t b=id>>16,off=(id&0xFFFF)<<1;if(!SafeReadable(blocks+b,8))return false;uintptr_t bp=blocks[b];if(!LooksLikePtr(bp))return false;if(!SafeReadable((void*)(bp+off),2))return false;uint16_t hdr=*(uint16_t*)(bp+off);int len=hdr>>6;bool wide=(hdr&1)!=0;if(len<=0||len>=cap)return false;if(wide){for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2);}else{if(!SafeReadable((void*)(bp+off+2),len))return false;for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i];}out[len]=0;return true;}
static uint32_t NameId(uintptr_t obj){if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0;return *(uint32_t*)(obj+NAME_OFF);}
static bool NameIs(uintptr_t obj,const char* w){char b[160];if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false;return strcmp(b,w)==0;}
static uintptr_t ClassOf(uintptr_t obj){if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0;return *(uintptr_t*)(obj+CLASS_OFF);}
static bool ClassNameIs(uintptr_t obj,const char* w){uintptr_t c=ClassOf(obj);if(!c)return false;char b[128];if(!GetFNameStr(NameId(c),b,sizeof(b)))return false;return strcmp(b,w)==0;}

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){DWORD code=ep->ExceptionRecord->ExceptionCode;bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;if(!fatal)return EXCEPTION_CONTINUE_SEARCH;long s=InterlockedIncrement(&g_crashSeq);if(s>8)return EXCEPTION_CONTINUE_SEARCH;uint64_t rip=ep->ContextRecord->Rip;Markerf("[VEH] fatal code=0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);return EXCEPTION_CONTINUE_SEARCH;}

static void BuildMissionProgress(){
    memset(g_mp,0,sizeof(g_mp));
    // ID FString @0x00 = {Data=g_idbuf, Num=len+1, Max=len+1}
    int len=(int)wcslen(g_idbuf);
    *(void**)(g_mp+0x00)=g_idbuf; *(int32_t*)(g_mp+0x08)=len+1; *(int32_t*)(g_mp+0x0C)=len+1;
    // AssetId @0x10 = {Type FName(Mission,0), Name FName(ArmoryDaily_PlayAGame,0)}
    *(uint32_t*)(g_mp+0x10)=0x000162B8; *(uint32_t*)(g_mp+0x14)=0; *(uint32_t*)(g_mp+0x18)=0x003FB29E; *(uint32_t*)(g_mp+0x1C)=0;
    // PoolId @0x20 = {MissionPool, 0}  (Name left 0/None — not needed for the insert test)
    *(uint32_t*)(g_mp+0x20)=0x00016F06; *(uint32_t*)(g_mp+0x24)=0; *(uint32_t*)(g_mp+0x28)=0; *(uint32_t*)(g_mp+0x2C)=0;
    // Complete=0 @0x30, Failed=0 @0x31, ObjectiveProgress empty TArray @0x38 (already 0)
    // MillisUntilExpiry @0x48, Expiry @0x50, GrantedAt @0x58 = a valid FDateTime tick (~year 2025)
    *(int64_t*)(g_mp+0x48)=7LL*24*3600*1000;
    *(int64_t*)(g_mp+0x50)=(int64_t)638750000000000000ULL;   // Expiry
    *(int64_t*)(g_mp+0x58)=(int64_t)638740000000000000ULL;   // GrantedAt
    // TArray<MissionProgress> {Data=g_mp, Num=1, Max=1}
    g_arr[0]=(uint64_t)(uintptr_t)g_mp; g_arr[1]=((uint64_t)1)|((uint64_t)1<<32);
}

extern "C" void OnBP(void*,void*,void*){
    if(!g_pending||g_inHook)return; if(GetCurrentThreadId()!=g_gameTid)return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    // 0) GetMissions before
    memset(g_getParams,0,sizeof(g_getParams)); g_processEvent((void*)g_mm,g_getMissions,g_getParams);
    g_numBefore=(int32_t)(g_getParams[1]&0xFFFFFFFF);
    // 1) factory: params [0..1]=TArray, [2]=ReturnValue
    memset(g_facParams,0,sizeof(g_facParams)); g_facParams[0]=g_arr[0]; g_facParams[1]=g_arr[1];
    g_processEvent((void*)g_mm,g_factory,g_facParams);
    g_retModel=(uintptr_t)g_facParams[2];
    // 2) GetMissions after
    memset(g_getParams,0,sizeof(g_getParams)); g_processEvent((void*)g_mm,g_getMissions,g_getParams);
    g_numAfter=(int32_t)(g_getParams[1]&0xFFFFFFFF);
    g_pending=0; g_done=1; g_inHook=0;
}

static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};for(int i=0;i<2;i++){if(!cands[i])continue;void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(p){intptr_t d=(intptr_t)p-(intptr_t)anchor;if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000)return (uint8_t*)p;VirtualFree(p,0,MEM_RELEASE);}}}return nullptr;}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
static uint8_t* BuildHook(uintptr_t fn,const uint8_t stolen[5]){uint8_t* blk=NearAlloc(fn,0x200);if(!blk)return nullptr;Emit t{blk};for(int i=0;i<5;i++)EB(t,stolen[i]);EB(t,0xE9);int32_t rel=(int32_t)((intptr_t)(fn+5)-((intptr_t)t.w+4));EU32(t,(uint32_t)rel);g_tramp=(PFN_PE)blk;uint8_t* stub=blk+0x20;Emit e{stub};EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnBP);EB(e,0xFF);EB(e,0xD0);EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk);EB(e,0xFF);EB(e,0xE0);return stub;}
static uint8_t* g_stub=nullptr;
static bool SafeWrite(uint8_t* dst,const uint8_t* src,size_t len){DWORD myTid=GetCurrentThreadId(),myPid=GetCurrentProcessId();HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);if(snap==INVALID_HANDLE_VALUE)return false;HANDLE hs[1024];int nh=0;THREADENTRY32 te;te.dwSize=sizeof(te);if(Thread32First(snap,&te)){do{if(te.th32OwnerProcessID==myPid&&te.th32ThreadID!=myTid&&nh<1024){HANDLE ht=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,te.th32ThreadID);if(ht)hs[nh++]=ht;}}while(Thread32Next(snap,&te));}CloseHandle(snap);uintptr_t lo=(uintptr_t)dst,hi=(uintptr_t)dst+len;bool ok=false;for(int a=0;a<400&&!ok;a++){for(int i=0;i<nh;i++)SuspendThread(hs[i]);bool unsafe=false;for(int i=0;i<nh;i++){CONTEXT c;c.ContextFlags=CONTEXT_CONTROL;if(GetThreadContext(hs[i],&c)){if(c.Rip>lo&&c.Rip<hi){unsafe=true;break;}}}if(!unsafe){DWORD op=0;if(VirtualProtect(dst,len,PAGE_EXECUTE_READWRITE,&op)){memcpy(dst,src,len);DWORD d=0;VirtualProtect(dst,len,op,&d);FlushInstructionCache(GetCurrentProcess(),dst,len);ok=true;}}if(!ok){for(int i=0;i<nh;i++)ResumeThread(hs[i]);Sleep(1);}}for(int i=0;i<nh;i++){ResumeThread(hs[i]);CloseHandle(hs[i]);}return ok;}
static bool InstallHook(){if(!g_pi||!g_stub)return false;int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5));uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)};return SafeWrite(g_pi,p,5);}
static void UninstallHook(){if(g_pi)SafeWrite(g_pi,g_stolen,5);}
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva;if(!SafeReadable((void*)oo,0x18))return;uintptr_t objectsPtr=*(uintptr_t*)oo;int32_t numEl=*(int32_t*)(oo+0x14);if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;uintptr_t progMgr=0,mmClass=0;
    for(int ci=0;ci<numChunks;ci++){if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8);if(!LooksLikePtr(chunk))continue;int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;for(int j=0;j<cnt;j++){uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE;if(!SafeReadable((void*)item,8))continue;uintptr_t obj=*(uintptr_t*)item;if(!LooksLikePtr(obj))continue;if(!progMgr&&ClassNameIs(obj,"ProgressionManager")){char nm[96];if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0)progMgr=obj;}}}
    if(!progMgr)return;if(SafeReadable((void*)(progMgr+PM_MM),8)){uintptr_t mm=*(uintptr_t*)(progMgr+PM_MM);if(LooksLikePtr(mm)){g_mm=mm;mmClass=ClassOf(mm);}}if(!mmClass)return;
    uintptr_t f=0;if(SafeReadable((void*)(mmClass+0x50),8))f=*(uintptr_t*)(mmClass+0x50);int i=0;
    while(LooksLikePtr(f)&&i<40){if(!g_getMissions&&NameIs(f,"GetMissions"))g_getMissions=(void*)f;if(!g_factory&&NameIs(f,"CreateMissionModelFromFinalProgress"))g_factory=(void*)f;uintptr_t nx=0;if(SafeReadable((void*)(f+0x30),8))nx=*(uintptr_t*)(f+0x30);f=nx;i++;}
}

static DWORD WINAPI Worker(LPVOID){
    {HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch);}
    Marker("[0] missions_populate2 (factory insert test) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;g_processEvent=(PFN_PE)(g_modBase+kPeRva);AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000);if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000;while(GetTickCount()<dl){Resolve();if(g_mm&&g_getMissions&&g_factory)break;Sleep(500);}
    if(!g_mm||!g_getMissions||!g_factory){Markerf("[2] FAIL resolve mm=0x%llX get=%p factory=%p\r\n",(unsigned long long)g_mm,g_getMissions,g_factory);return 3;}
    Markerf("[2] mm=0x%llX GetMissions=%p factory=%p\r\n",(unsigned long long)g_mm,g_getMissions,g_factory);
    BuildMissionProgress();
    Markerf("[2] MissionProgress built: ID='ArmoryDaily_PlayAGame' AssetId=Mission:ArmoryDaily_PlayAGame arr={Data=0x%llX Num=1}\r\n",(unsigned long long)g_arr[0]);
    g_pi=(uint8_t*)(g_modBase+kPiRva);if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5);g_stub=BuildHook((uintptr_t)g_pi,g_stolen);if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    g_pending=1;g_done=0;if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");return 6;}
    Marker("[3] armed factory call...\r\n");
    DWORD t0=GetTickCount();while(!g_done&&GetTickCount()-t0<8000)Sleep(20);UninstallHook();
    if(!g_done){Markerf("[4] TIMEOUT (hitsGT=%ld)\r\n",(long)g_hitsGT);return 0;}
    char mcls[96]="<null>";int haveModel=0;
    if(LooksLikePtr(g_retModel)){haveModel=1;uintptr_t c=ClassOf(g_retModel);if(c)GetFNameStr(NameId(c),mcls,sizeof(mcls));}
    Markerf("[4] factory returned model=0x%llX class=%s\r\n",(unsigned long long)g_retModel,mcls);
    Markerf("[4] GetMissions().Num  before=%d  after=%d  => factory %s the map\r\n",g_numBefore,g_numAfter,(g_numAfter>g_numBefore)?"INSERTS INTO":"does NOT insert into");
    if(haveModel){
        // read the returned model's ID (Str@+? ) — MissionModel.ID is first field after UObject header. Log a few qwords.
        uint8_t hb[0x60]; if(SafeReadable((void*)g_retModel,0x60)){memcpy(hb,(void*)g_retModel,0x60);Markerf("[4] model[+0x28..0x38]=%02X%02X%02X%02X.. (inspect ID/MissionAssetId offsets)\r\n",hb[0x28],hb[0x29],hb[0x2A],hb[0x2B]);}
    }
    Marker("[4] DONE.\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
