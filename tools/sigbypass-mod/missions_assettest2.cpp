// missions_assettest2 — definitive: chain PrimaryAssetIDFromString(str) -> GetLokiDataAsset(id) for a
// HERO control (guaranteed-resolvable; roster renders) and a MISSION. If hero -> non-null but mission ->
// null, mission asset RESOLUTION is the confirmed blocker (and the call itself works). Uses the verified
// ProcessEvent-on-game-thread primitive. Builds ids from STRINGS (no FName guessing).
//
// LokiAssetManager UFuncs: PrimaryAssetIDFromString([in]FString(16))->[ret]FPrimaryAssetId(16) ;
//   GetLokiDataAsset([in]FPrimaryAssetId(16))->[ret]Object(8).
// Build:  clang++ -shared -O2 missions_assettest2.cpp -o missions_assettest2.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/missions_assettest2.dll
// Marker: docs/missions-assettest2-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath="G:\\git\\Supervive Revival Project\\docs\\missions-assettest2-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0,kPeRva=0x12C5A10,kObjObjectsRva=0x9E38930,kNamePoolRva=0x9D81450,kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536,ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18,NAME_OFF=0x20;
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void*,void*,void*);

static uintptr_t g_modBase=0; static volatile PFN_PE g_tramp=nullptr; static PFN_PE g_pe=nullptr;
static uintptr_t g_mgr=0; static void* g_fromStr=nullptr; static void* g_getAsset=nullptr;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0};
static volatile long g_pending=0,g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static wchar_t g_sHero[64]=L"Hero:Alchemist";
static wchar_t g_sMiss[64]=L"Mission:ArmoryDaily_PlayAGame";
static uint64_t g_p[8]={0};
static uintptr_t g_heroObj=0,g_missObj=0; static uint64_t g_heroId[2]={0},g_missId[2]={0};

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000&&v<0x0001000000000000ULL&&(v&7)==0;}
static bool GetFNameStr(uint32_t id,char* out,int cap){uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva);uint32_t b=id>>16,off=(id&0xFFFF)<<1;if(!SafeReadable(blocks+b,8))return false;uintptr_t bp=blocks[b];if(!LooksLikePtr(bp))return false;if(!SafeReadable((void*)(bp+off),2))return false;uint16_t hdr=*(uint16_t*)(bp+off);int len=hdr>>6;bool wide=(hdr&1)!=0;if(len<=0||len>=cap)return false;if(wide){for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2);}else{if(!SafeReadable((void*)(bp+off+2),len))return false;for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i];}out[len]=0;return true;}
static uint32_t NameId(uintptr_t obj){if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0;return *(uint32_t*)(obj+NAME_OFF);}
static bool NameIs(uintptr_t obj,const char* w){char b[160];if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false;return strcmp(b,w)==0;}
static uintptr_t ClassOf(uintptr_t obj){if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0;return *(uintptr_t*)(obj+CLASS_OFF);}
static bool ClassNameIs(uintptr_t obj,const char* w){uintptr_t c=ClassOf(obj);if(!c)return false;char b[128];if(!GetFNameStr(NameId(c),b,sizeof(b)))return false;return strcmp(b,w)==0;}
static void ClassName(uintptr_t obj,char* out,int cap){uintptr_t c=ClassOf(obj);out[0]=0;if(c)GetFNameStr(NameId(c),out,cap);}

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){DWORD code=ep->ExceptionRecord->ExceptionCode;bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;if(!fatal)return EXCEPTION_CONTINUE_SEARCH;long s=InterlockedIncrement(&g_crashSeq);if(s>8)return EXCEPTION_CONTINUE_SEARCH;uint64_t rip=ep->ContextRecord->Rip;Markerf("[VEH] fatal code=0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);return EXCEPTION_CONTINUE_SEARCH;}

// PrimaryAssetIDFromString(str) -> writes FPrimaryAssetId (16B) into out[0..1]
static void FromStr(wchar_t* s,uint64_t out[2]){
    int len=(int)wcslen(s);
    memset(g_p,0,sizeof(g_p));
    *(void**)((uint8_t*)g_p+0x00)=s; *(int32_t*)((uint8_t*)g_p+0x08)=len+1; *(int32_t*)((uint8_t*)g_p+0x0C)=len+1; // FString @0
    g_pe((void*)g_mgr,g_fromStr,g_p);  // ReturnValue FPrimaryAssetId @ +0x10
    out[0]=g_p[2]; out[1]=g_p[3];
}
static uintptr_t GetAsset(uint64_t id[2]){
    memset(g_p,0,sizeof(g_p));
    g_p[0]=id[0]; g_p[1]=id[1];        // FPrimaryAssetId @0
    g_pe((void*)g_mgr,g_getAsset,g_p); // ReturnValue Object @ +0x10
    return (uintptr_t)g_p[2];
}
extern "C" void OnBP(void*,void*,void*){
    if(!g_pending||g_inHook)return; if(GetCurrentThreadId()!=g_gameTid)return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    FromStr(g_sHero,g_heroId); g_heroObj=GetAsset(g_heroId);
    FromStr(g_sMiss,g_missId); g_missObj=GetAsset(g_missId);
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
    uintptr_t oo=g_modBase+kObjObjectsRva;if(!SafeReadable((void*)oo,0x18))return;uintptr_t objectsPtr=*(uintptr_t*)oo;int32_t numEl=*(int32_t*)(oo+0x14);if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;uintptr_t inst=0,cdo=0;
    for(int ci=0;ci<numChunks;ci++){if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8);if(!LooksLikePtr(chunk))continue;int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;for(int j=0;j<cnt;j++){uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE;if(!SafeReadable((void*)item,8))continue;uintptr_t obj=*(uintptr_t*)item;if(!LooksLikePtr(obj))continue;
        if(ClassNameIs(obj,"LokiAssetManager")){char nm[96];if(GetFNameStr(NameId(obj),nm,sizeof(nm))){if(strncmp(nm,"Default__",9)==0)cdo=obj;else inst=obj;}}}}
    g_mgr=inst?inst:cdo; if(!g_mgr)return; uintptr_t cls=ClassOf(g_mgr);
    uintptr_t f=0;if(SafeReadable((void*)(cls+0x50),8))f=*(uintptr_t*)(cls+0x50);int i=0;
    while(LooksLikePtr(f)&&i<40){if(!g_fromStr&&NameIs(f,"PrimaryAssetIDFromString"))g_fromStr=(void*)f;if(!g_getAsset&&NameIs(f,"GetLokiDataAsset"))g_getAsset=(void*)f;uintptr_t nx=0;if(SafeReadable((void*)(f+0x30),8))nx=*(uintptr_t*)(f+0x30);f=nx;i++;}
}

static DWORD WINAPI Worker(LPVOID){
    {HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch);}
    Marker("[0] missions_assettest2 (hero control vs mission) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;g_pe=(PFN_PE)(g_modBase+kPeRva);AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000);if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000;while(GetTickCount()<dl){Resolve();if(g_mgr&&g_fromStr&&g_getAsset)break;Sleep(500);}
    if(!g_mgr||!g_fromStr||!g_getAsset){Markerf("[2] FAIL resolve mgr=0x%llX fromStr=%p getAsset=%p\r\n",(unsigned long long)g_mgr,g_fromStr,g_getAsset);return 3;}
    Markerf("[2] mgr=0x%llX PrimaryAssetIDFromString=%p GetLokiDataAsset=%p\r\n",(unsigned long long)g_mgr,g_fromStr,g_getAsset);
    g_pi=(uint8_t*)(g_modBase+kPiRva);if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5);g_stub=BuildHook((uintptr_t)g_pi,g_stolen);if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    g_pending=1;g_done=0;if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");return 6;}
    Marker("[3] armed...\r\n");
    DWORD t0=GetTickCount();while(!g_done&&GetTickCount()-t0<8000)Sleep(20);UninstallHook();
    if(!g_done){Markerf("[4] TIMEOUT (hitsGT=%ld)\r\n",(long)g_hitsGT);return 0;}
    char hc[96]="<null>",mc[96]="<null>";
    if(LooksLikePtr(g_heroObj))ClassName(g_heroObj,hc,sizeof(hc));
    if(LooksLikePtr(g_missObj))ClassName(g_missObj,mc,sizeof(mc));
    Markerf("[4] CONTROL Hero:Alchemist  id={0x%llX,0x%llX} -> asset=0x%llX class=%s\r\n",(unsigned long long)g_heroId[0],(unsigned long long)g_heroId[1],(unsigned long long)g_heroObj,hc);
    Markerf("[4] MISSION ArmoryDaily_PlayAGame id={0x%llX,0x%llX} -> asset=0x%llX class=%s\r\n",(unsigned long long)g_missId[0],(unsigned long long)g_missId[1],(unsigned long long)g_missObj,mc);
    if(LooksLikePtr(g_heroObj)&&!LooksLikePtr(g_missObj)) Marker("[4] => CALL WORKS (hero resolves); MISSION does NOT resolve => asset resolution IS the missions blocker.\r\n");
    else if(LooksLikePtr(g_missObj)) Marker("[4] => MISSION RESOLVES! manual model-construction path is viable.\r\n");
    else Marker("[4] => hero control ALSO null -> the call/id path is wrong (inconclusive; GetLokiDataAsset may only return preloaded assets).\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
