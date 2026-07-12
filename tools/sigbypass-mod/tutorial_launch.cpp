// tutorial_launch — SESSION 60 (force-launch route). The menu's native TryStartSoloMode bails
// (region gates only the FIND MATCH path; tutorial uses solo-start which no-ops against our stub).
// The tutorial map is LOCAL, so we bypass the menu entirely: call
//   UKismetSystemLibrary::ExecuteConsoleCommand(WorldContext, "open LVL_Tutorial", nullptr)
// via the proven S55/S56 game-thread native-call primitive (hook ProcessInternal, capture a live
// FFrame, call the UFunction thunk directly). "open <map>" routes through UEngine::HandleOpenCommand
// -> Browse -> a local client travel to the tutorial map (the exact thing TryStartSoloMode should do).
//
// Primitive recipe (probe9): myframe = captured template; Node=UFunction, Object=Context, Code=NULL,
// Locals=paramsBuf, clear +0x30/+0x38/+0x40 (MostRecentProperty*), PropertyChainForCompiledIn@+0x88 =
// Function.ChildProperties (*(UFunc+0x58)); thunk(Context,&frame,&result). Params placed at each
// param FProperty's Offset_Internal@+0x44 within paramsBuf.
// Build:  clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tutorial_launch.dll   Marker: docs/tutorial-launch-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\tutorial-launch-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_PROPCHAIN=0x88;
constexpr uintptr_t FIELD_NEXT=0x18, FPROP_OFFSET=0x44;   // FField.Next, FProperty.Offset_Internal
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

// The console command to force the local tutorial travel. "open <mapname>" is the client-travel command.
//
// S61 finding (static): LVL_Tutorial's WorldSettings.DefaultGameMode is BP_LokiGameMode_Tutorial (the FULL
// machinery mode); the map has NO PlayerStart on purpose (hero drops in via Comp_GameMode_DropPlane_Tutorial).
// BP_GameMode_BasicTraining is a STOCK GameModeBase stub (zero CDO overrides -> stock GameState/PC/DefaultPawn),
// which is why ?game=BasicTraining loads but shows a spectator at origin + "IsBattleRoyaleBP failed to find game
// state". So the only route to a PLAYABLE tutorial is BP_LokiGameMode_Tutorial, gated by native
// ALokiGameMode::Login (packer-blocked from static disasm; not overridden in BP).
//
// To make the next live session's Login-satisfy sweep fast, the command is now read from an external file at
// inject time (edit the file + reinject, no rebuild). If the file is absent/empty, we fall back to the
// KNOWN-GOOD BasicTraining render (loads + shows the island, never crashes) so a bare inject is always safe.
//   File: docs/tutorial-launch-cmd.txt  (first non-comment line; '#'/'//' and blank lines ignored; UTF-8/ASCII)
static const char* kCmdFilePath = "G:\\git\\Supervive Revival Project\\docs\\tutorial-launch-cmd.txt";
// S62: default is now the FULL tutorial mode so the custom-Login trampoline (match-mode vtable slot 285)
// actually fires — BasicTraining is a stock GameModeBase and never dispatches through the match vtables.
// (The external cmd-file read has been flaky; the compiled default removes that dependency for this test.)
static const wchar_t* kDefaultCommand =
    L"open LVL_Tutorial?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.BP_LokiGameMode_Tutorial_C";  // S64: ?listen tested + ruled out (failed to Listen, reverted identically) — reverted to plain full mode
static wchar_t g_cmd[1024];   // resolved at startup by LoadCommand(); points OnPI's Command FString.

// ---- S61 native Login-approve (transient, self-restoring vtable DE-OVERRIDE) ----
// The tutorial force-open crashes in native ALokiGameMode::Login. Slot 176 (the ONLY GameMode override in the
// first 190 vtable slots) turned out NOT to be the Login dispatch (patching it, verified held, had zero effect).
// A 300-slot vtdump diff shows ALokiGameMode overrides SEVERAL virtuals: slots 176,236,259,283,285,288,294. Any
// could be Login. DECISIVE TEST: de-override ALL of them to their stock AGameModeBase values at once — if the
// "ALokiGameMode::Login failed to Login" crash disappears, Login is one of these (then bisect); if it persists,
// the reject is not a GameMode virtual (likely AGameSession::ApproveLogin). .rdata patch trips the ~3-5min
// integrity check if PERSISTENT (a live 10-vtable patch hard-crashed at menu in ~30s), so do it TRANSIENTLY:
// patch right before force-open, hold through the travel login (~a few s), restore. RVAs stable for this build
// (base 0x7FF6B54F0000); verify with usmapdump if the game updates.
constexpr uintptr_t kStockGmbVtRva = 0x806EDD8;   // stock AGameModeBase CDO vtable (source of de-override values)
static const uintptr_t kMatchVtRvas[] = {         // match-mode CDO vtables (instances share the native parent's)
    0x8A94C48,  // ALokiTutorialGameMode
    0x8A52A98,  // ALokiRoundGameMode
    0x8951FA0,  // ALokiGameMode
    0x88B7CB0,  // ALokiBattleRoyaleGameMode
    0x8936948,  // ALokiDropInGameMode
};
static const int kOverrideSlots[] = {285};  // BISECT: testing which override slot is Login (candidates 236,283,285,288,294)
static uintptr_t g_savedVt[5][7];                 // [match vtable][slot] originals for restore
// PatchLoginVtables(bool) is defined below, after g_modBase / Marker / SafeReadable are declared.
static void PatchLoginVtables(bool toStock);

static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_worldCtx=0;                 // WorldContextObject (a live ProgressionManager)
static uintptr_t g_kslCDO=0;                    // Default__KismetSystemLibrary (call context)
static void* g_ecc=nullptr; static uintptr_t g_eccThunk=0, g_eccChild=0;   // ExecuteConsoleCommand
static uint32_t g_offWCO=0xFFFFFFFF, g_offCmd=0xFFFFFFFF, g_offSP=0xFFFFFFFF;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0,g_called=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};
static uint64_t g_pbuf[16]={0}, g_rbuf[4]={0};

// ---- S68 spawn+possess mode (LEAD B / OPTION 2) ----
enum RunMode { RM_FORCEOPEN=0, RM_SPAWNPOSSESS=1 };
static const int kRunMode = RM_SPAWNPOSSESS;   // RM_FORCEOPEN = force-open tutorial; RM_SPAWNPOSSESS = spawn+possess in the running tutorial
static uintptr_t g_gm2=0, g_pc2=0, g_startSpot=0, g_spawnedPawn=0, g_heroClass=0;
constexpr uint32_t GM_DEFPAWN_OFF=0x3F0;   // AGameModeBase::DefaultPawnClass
// S68 GameplayStatics deferred-spawn (bypass GetDefaultPawnClass): explicit hero-class spawn + possess.
static const bool kUseGameplayStatics = true;
static uintptr_t g_gsCDO=0;
static void* g_beginFn=nullptr; static uintptr_t g_beginThunk=0, g_beginChild=0;
static void* g_finishFn=nullptr; static uintptr_t g_finishThunk=0, g_finishChild=0;
static void* g_xfFn=nullptr; static uintptr_t g_xfThunk=0, g_xfChild=0;
static uint32_t g_oBWorld=0,g_oBClass=8,g_oBXform=0x10,g_oBColl=0x70,g_oBOwner=0x78,g_oBRet=0x88;
static uint32_t g_oFActor=0,g_oFXform=0x10,g_oFRet=0x70; static uint32_t g_oXfRet=0;
static uint8_t g_xform[0x60]={0}; static uint8_t g_gsbuf[0x100]={0};
static void* g_spawnFn=nullptr; static uintptr_t g_spawnThunk=0, g_spawnChild=0;
static void* g_possessFn=nullptr; static uintptr_t g_possessThunk=0, g_possessChild=0;
static uint32_t g_offSpawnNP=0, g_offSpawnSS=8, g_offSpawnRet=0x10, g_offInPawn=0;
static volatile long g_spStep=0;   // progress: 1=spawn called, 2=pawn got, 3=possess called
static void DoSpawnPossess();

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
// De-override (toStock=true) or restore (false) all of ALokiGameMode's overridden virtuals across the match-mode
// vtables, copying the stock AGameModeBase vtable's value at each slot. Saves originals for a clean restore.
static void PatchLoginVtables(bool toStock){
    uintptr_t* gmb=(uintptr_t*)(g_modBase+kStockGmbVtRva);
    const int NV=(int)(sizeof(kMatchVtRvas)/sizeof(kMatchVtRvas[0]));
    const int NS=(int)(sizeof(kOverrideSlots)/sizeof(kOverrideSlots[0]));
    int n=0;
    for(int v=0; v<NV; v++){
        uintptr_t vt=g_modBase+kMatchVtRvas[v];
        for(int s=0; s<NS; s++){
            int slot=kOverrideSlots[s];
            uintptr_t* tgt=(uintptr_t*)(vt+(uintptr_t)slot*8);
            if(!SafeReadable(tgt,8)||!SafeReadable(gmb+slot,8)) continue;
            DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op)) continue;
            if(toStock){ g_savedVt[v][s]=*tgt; *tgt=gmb[slot]; }        // point slot at stock AGameModeBase impl
            else if(g_savedVt[v][s]){ *tgt=g_savedVt[v][s]; }           // restore the Loki override
            DWORD d=0; VirtualProtect(tgt,8,op,&d); n++;
        }
    }
    Markerf("[VT] %s %d slot-writes across %d match vtables x %d override slots (de-override to stock GameModeBase)\r\n",
            toStock?"PATCH":"restore", n, NV, NS);
}
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

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>8)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);
    return EXCEPTION_CONTINUE_SEARCH;
}

// Call a native UFunction with a prepared params buffer. Result -> resultBuf.
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
// Set an FString {Data,Num,Max} at pbuf+byteOff (Num includes null terminator).
static void SetFStringAt(uint8_t* pbuf, uint32_t byteOff, const wchar_t* s){
    int n=(int)wcslen(s)+1;
    *(uint64_t*)(pbuf+byteOff)=(uint64_t)s;
    *(uint32_t*)(pbuf+byteOff+8)=(uint32_t)n;
    *(uint32_t*)(pbuf+byteOff+12)=(uint32_t)n;
}

extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));
    if(kRunMode==RM_SPAWNPOSSESS){ DoSpawnPossess(); InterlockedIncrement(&g_called); g_done=1; g_inHook=0; return; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    uint8_t* pb=(uint8_t*)g_pbuf;
    if(g_offWCO!=0xFFFFFFFF) *(uint64_t*)(pb+g_offWCO)=(uint64_t)g_worldCtx;   // WorldContextObject
    if(g_offCmd!=0xFFFFFFFF) SetFStringAt(pb,g_offCmd,g_cmd);                   // Command FString
    if(g_offSP !=0xFFFFFFFF) *(uint64_t*)(pb+g_offSP)=0;                       // SpecificPlayer = null
    CallNative(g_ecc,g_eccThunk,g_eccChild,(void*)g_kslCDO,g_pbuf,g_rbuf);
    InterlockedIncrement(&g_called);
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

// Resolve g_cmd: read the first non-comment/non-blank line of kCmdFilePath; fall back to kDefaultCommand.
// Returns true if the file supplied the command, false if we fell back to the compiled default.
static bool LoadCommand(){
    wcscpy_s(g_cmd,_countof(g_cmd),kDefaultCommand);
    // S62: retry the open — a transient share/lock (editor/AV touching the file at inject time) made a
    // fresh inject fall back to the compiled default (BasicTraining) instead of the full tutorial mode.
    HANDLE h=INVALID_HANDLE_VALUE;
    for(int i=0;i<20 && h==INVALID_HANDLE_VALUE;i++){
        h=CreateFileA(kCmdFilePath,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(h==INVALID_HANDLE_VALUE) Sleep(50);
    }
    if(h==INVALID_HANDLE_VALUE){ Markerf("[0] LoadCommand: open failed (GetLastError=%lu) -> default fallback\r\n",GetLastError()); return false; }
    char buf[4096]; DWORD rd=0; bool got=ReadFile(h,buf,sizeof(buf)-1,&rd,nullptr)!=0; CloseHandle(h);
    if(!got||rd==0){ Markerf("[0] LoadCommand: read failed/empty (got=%d rd=%lu) -> default fallback\r\n",got?1:0,rd); return false; }
    buf[rd]=0;
    // Walk lines; take the first that isn't blank / '#' / '//'.
    for(char* p=buf; *p; ){
        char* eol=p; while(*eol && *eol!='\r' && *eol!='\n') eol++; char saved=*eol; *eol=0;
        char* s=p; while(*s==' '||*s=='\t') s++;                       // ltrim
        char* e=s+strlen(s); while(e>s&&(e[-1]==' '||e[-1]=='\t')) *--e=0; // rtrim
        bool comment = s[0]=='#' || (s[0]=='/'&&s[1]=='/');
        if(*s && !comment){
            wchar_t w[1024]; int n=MultiByteToWideChar(CP_UTF8,0,s,-1,w,_countof(w));
            if(n>0){ wcscpy_s(g_cmd,_countof(g_cmd),w); return true; }
            return false;
        }
        *eol=saved; p=eol; while(*p=='\r'||*p=='\n') p++;
    }
    return false;
}

static void ResolveFuncOnClass(uintptr_t cls,const char* fname,void** func,uintptr_t* thunk,uintptr_t* child){
    uintptr_t f=0; if(SafeReadable((void*)(cls+0x50),8)) f=*(uintptr_t*)(cls+0x50); int i=0;
    while(LooksLikePtr(f)&&i<600){ if(NameIs(f,fname)){ *func=(void*)f; if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))*thunk=th;} if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))*child=cp;} return; } uintptr_t nx=0; if(SafeReadable((void*)(f+0x30),8))nx=*(uintptr_t*)(f+0x30); f=nx; i++; }
}
// Walk a UFunction's param FField chain (head=childProps, Next@+0x18), return Offset_Internal@+0x44 of the named param.
static uint32_t ParamOffset(uintptr_t childHead,const char* name){
    uintptr_t f=childHead; int i=0;
    while(LooksLikePtr(f)&&i<40){ if(NameIs(f,name)){ if(SafeReadable((void*)(f+FPROP_OFFSET),4)) return *(uint32_t*)(f+FPROP_OFFSET); return 0xFFFFFFFF; } uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8))nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx; i++; }
    return 0xFFFFFFFF;
}

// ---- S68 spawn+possess helpers ----
// Find the first non-Default (live) instance whose class name contains `sub` (and object name contains `nameMust`).
static uintptr_t FindInstByClass(const char* sub, const char* nameMust){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,sub))continue; char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
            if(strncmp(on,"Default__",9)==0)continue; if(nameMust&&!strstr(on,nameMust))continue;
            return obj; } }
    return 0;
}
// Find the first object whose OWN FName == want (e.g. a UClass "BP_HERO_Ronin_C").
static uintptr_t FindObjExact(const char* want){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,want))return obj; } }
    return 0;
}
// Resolve a UFunction by name walking cls + its SuperStruct chain (@+0x48).
static void ResolveFuncSuper(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child){
    int g=0; while(LooksLikePtr(cls)&&g++<12){ ResolveFuncOnClass(cls,name,fn,thunk,child); if(*fn)return; cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0; }
}
// Resolve a UFunction on the first NATIVE ancestor (class name not "BP_*") — the native thunk, NOT a BP-bytecode
// override. The primitive calls with FFrame.Code=NULL, which crashes a BP-VM Func but is correct for a native thunk.
static void ResolveFuncNative(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child){
    int g=0; while(LooksLikePtr(cls)&&g++<12){
        char cn[128]; if(GetFNameStr(NameId(cls),cn,sizeof(cn)) && strncmp(cn,"BP_",3)!=0){ ResolveFuncOnClass(cls,name,fn,thunk,child); if(*fn)return; }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
}
static bool ResolveSpawnPossess(){
    g_gm2=FindInstByClass("GameMode_Tutorial",nullptr);
    g_pc2=FindInstByClass("LokiPlayerController_Dev",nullptr);
    g_startSpot=FindInstByClass("LokiPlayerStart","UAID");
    if(!g_startSpot) g_startSpot=FindInstByClass("CapturePoint_Tutorial","UAID");
    if(!g_startSpot) g_startSpot=FindInstByClass("LokiRespawnBeacon_Tutorial","UAID");
    g_heroClass=FindObjExact("BP_HERO_Ronin_C");   // the hero UClass to force as DefaultPawnClass
    Markerf("[SP] gm=0x%llX pc=0x%llX startSpot=0x%llX heroClass=0x%llX\r\n",(unsigned long long)g_gm2,(unsigned long long)g_pc2,(unsigned long long)g_startSpot,(unsigned long long)g_heroClass);
    if(!g_gm2||!g_pc2||!g_startSpot)return false;
    ResolveFuncNative(ClassOf(g_gm2),"SpawnDefaultPawnFor",&g_spawnFn,&g_spawnThunk,&g_spawnChild);   // NATIVE thunk, not the BP override
    if(g_spawnChild){ uint32_t o; o=ParamOffset(g_spawnChild,"NewPlayer"); if(o!=0xFFFFFFFF)g_offSpawnNP=o; o=ParamOffset(g_spawnChild,"StartSpot"); if(o!=0xFFFFFFFF)g_offSpawnSS=o; o=ParamOffset(g_spawnChild,"ReturnValue"); if(o!=0xFFFFFFFF)g_offSpawnRet=o; }
    ResolveFuncNative(ClassOf(g_pc2),"Possess",&g_possessFn,&g_possessThunk,&g_possessChild);
    if(g_possessChild){ uint32_t o=ParamOffset(g_possessChild,"InPawn"); if(o!=0xFFFFFFFF)g_offInPawn=o; }
    if(kUseGameplayStatics){
        g_gsCDO=FindObjExact("Default__GameplayStatics");
        if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
            ResolveFuncOnClass(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
            ResolveFuncOnClass(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
            uint32_t o;
            if(g_beginChild){ o=ParamOffset(g_beginChild,"WorldContextObject");if(o!=0xFFFFFFFF)g_oBWorld=o; o=ParamOffset(g_beginChild,"ActorClass");if(o!=0xFFFFFFFF)g_oBClass=o; o=ParamOffset(g_beginChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oBXform=o; o=ParamOffset(g_beginChild,"CollisionHandlingOverride");if(o!=0xFFFFFFFF)g_oBColl=o; o=ParamOffset(g_beginChild,"Owner");if(o!=0xFFFFFFFF)g_oBOwner=o; o=ParamOffset(g_beginChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oBRet=o; }
            if(g_finishChild){ o=ParamOffset(g_finishChild,"Actor");if(o!=0xFFFFFFFF)g_oFActor=o; o=ParamOffset(g_finishChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oFXform=o; o=ParamOffset(g_finishChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oFRet=o; }
        }
        ResolveFuncSuper(ClassOf(g_startSpot),"GetActorTransform",&g_xfFn,&g_xfThunk,&g_xfChild);
        if(g_xfChild){ uint32_t o=ParamOffset(g_xfChild,"ReturnValue"); if(o!=0xFFFFFFFF)g_oXfRet=o; }
        Markerf("[GS] gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX xfThunk=0x%llX\r\n",(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_xfThunk);
        Markerf("[GS] B[world@%X class@%X xform@%X coll@%X owner@%X ret@%X] F[actor@%X xform@%X ret@%X] xfRet@%X\r\n",g_oBWorld,g_oBClass,g_oBXform,g_oBColl,g_oBOwner,g_oBRet,g_oFActor,g_oFXform,g_oFRet,g_oXfRet);
    }
    Markerf("[SP] spawnThunk=0x%llX(NP@0x%X SS@0x%X ret@0x%X) possessThunk=0x%llX(InPawn@0x%X)\r\n",
        (unsigned long long)g_spawnThunk,g_offSpawnNP,g_offSpawnSS,g_offSpawnRet,(unsigned long long)g_possessThunk,g_offInPawn);
    return g_spawnThunk&&g_possessThunk;
}
static const bool kDoPossess = true;   // S68: spawn (native) + possess; step markers localize any crash.
// Runs on the GAME THREAD (from OnPI): SpawnDefaultPawnFor(PC, StartSpot) -> pawn, then (optionally) PC.Possess(pawn).
// Markers flush per call so a crash pinpoints which native call died.
static void DoSpawnPossess(){
    if(kUseGameplayStatics && g_beginThunk && g_finishThunk){
        uint32_t xfsz=(g_oBColl>g_oBXform)?(g_oBColl-g_oBXform):0x50; if(xfsz>sizeof(g_xform))xfsz=sizeof(g_xform);
        // 1. GetActorTransform(startSpot) -> g_xform (struct return via RESULT; fall back to the params ReturnValue)
        memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_xform,0,sizeof(g_xform));
        if(g_xfThunk){ CallNative(g_xfFn,g_xfThunk,g_xfChild,(void*)g_startSpot,g_gsbuf,g_xform);
            bool zero=true; for(uint32_t i=0;i<0x38;i++) if(g_xform[i]){zero=false;break;}
            if(zero && g_oXfRet!=0xFFFFFFFF && g_oXfRet+xfsz<=sizeof(g_gsbuf)) memcpy(g_xform,g_gsbuf+g_oXfRet,xfsz); }
        double* t=(double*)(g_xform+0x20); Markerf("[GS] xform T=(%.1f,%.1f,%.1f)\r\n",t[0],t[1],t[2]);
        // 2. BeginDeferredActorSpawnFromClass(gm, heroClass, xform, AdjustButAlwaysSpawn) -> deferred actor
        memset(g_gsbuf,0,sizeof(g_gsbuf));
        *(uint64_t*)(g_gsbuf+g_oBWorld)=(uint64_t)g_gm2;
        *(uint64_t*)(g_gsbuf+g_oBClass)=(uint64_t)g_heroClass;
        memcpy(g_gsbuf+g_oBXform,g_xform,xfsz);
        g_gsbuf[g_oBColl]=2;   // ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn
        memset(g_rbuf,0,sizeof(g_rbuf));
        CallNative(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_gsbuf,g_rbuf);
        uintptr_t deferred=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(deferred)) deferred=*(uint64_t*)(g_gsbuf+g_oBRet);
        g_spStep=2; char dcn[96]="-"; if(LooksLikePtr(deferred)&&ClassOf(deferred))GetFNameStr(NameId(ClassOf(deferred)),dcn,sizeof(dcn));
        Markerf("[GS] deferred=0x%llX cls=%s\r\n",(unsigned long long)deferred,dcn);
        // 3. FinishSpawningActor(deferred, xform) -> spawned actor
        uintptr_t actor=0;
        if(LooksLikePtr(deferred)){
            memset(g_gsbuf,0,sizeof(g_gsbuf)); *(uint64_t*)(g_gsbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_gsbuf+g_oFXform,g_xform,xfsz);
            memset(g_rbuf,0,sizeof(g_rbuf));
            CallNative(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_gsbuf,g_rbuf);
            actor=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(actor)) actor=*(uint64_t*)(g_gsbuf+g_oFRet); if(!LooksLikePtr(actor)) actor=deferred;
        }
        g_spawnedPawn=actor; g_spStep=3;
        char acn[96]="-"; if(LooksLikePtr(actor)&&ClassOf(actor))GetFNameStr(NameId(ClassOf(actor)),acn,sizeof(acn));
        Markerf("[GS] spawned actor=0x%llX cls=%s\r\n",(unsigned long long)actor,acn);
        // 4. Possess(pc, actor)
        if(kDoPossess && LooksLikePtr(actor) && g_possessThunk){
            memset(g_gsbuf,0,sizeof(g_gsbuf)); *(uint64_t*)(g_gsbuf+g_offInPawn)=(uint64_t)actor; memset(g_rbuf,0,sizeof(g_rbuf));
            CallNative(g_possessFn,g_possessThunk,g_possessChild,(void*)g_pc2,g_gsbuf,g_rbuf);
            g_spStep=4; Marker("[GS] possess called\r\n");
        }
        return;
    }
    // Force the gamemode's DefaultPawnClass to the hero, so GetDefaultPawnClassForController (which returned null
    // due to no hero-select context) falls back to a real hero pawn instead of nothing.
    if(g_heroClass && SafeReadable((void*)(g_gm2+GM_DEFPAWN_OFF),8)){
        uintptr_t old=*(uintptr_t*)(g_gm2+GM_DEFPAWN_OFF); char ocn[96]="-"; if(LooksLikePtr(old)) GetFNameStr(NameId(old),ocn,sizeof(ocn));
        *(uintptr_t*)(g_gm2+GM_DEFPAWN_OFF)=g_heroClass;
        Markerf("[SP] poked DefaultPawnClass@0x%X: %s -> BP_HERO_Ronin_C\r\n",GM_DEFPAWN_OFF,ocn);
    }
    g_spStep=1; Marker("[SP] >>> calling SpawnDefaultPawnFor\r\n");
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    uint8_t* pb=(uint8_t*)g_pbuf;
    *(uint64_t*)(pb+g_offSpawnNP)=(uint64_t)g_pc2;
    *(uint64_t*)(pb+g_offSpawnSS)=(uint64_t)g_startSpot;
    CallNative(g_spawnFn,g_spawnThunk,g_spawnChild,(void*)g_gm2,g_pbuf,g_rbuf);
    uintptr_t pawn=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(pawn)) pawn=*(uint64_t*)(pb+g_offSpawnRet);
    g_spawnedPawn=pawn; g_spStep=2;
    char pcn[96]="-"; if(LooksLikePtr(pawn)&&ClassOf(pawn)) GetFNameStr(NameId(ClassOf(pawn)),pcn,sizeof(pcn));
    Markerf("[SP] <<< SpawnDefaultPawnFor returned pawn=0x%llX cls=%s\r\n",(unsigned long long)pawn,pcn);
    if(kDoPossess && LooksLikePtr(pawn)){
        Marker("[SP] >>> calling Possess\r\n");
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)((uint8_t*)g_pbuf+g_offInPawn)=(uint64_t)pawn;
        CallNative(g_possessFn,g_possessThunk,g_possessChild,(void*)g_pc2,g_pbuf,g_rbuf);
        g_spStep=3; Marker("[SP] <<< Possess returned\r\n");
    }
}

static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t progMgr=0, kslCDO=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!progMgr && ClassNameIs(obj,"ProgressionManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) progMgr=obj; }
            if(!kslCDO && NameIs(obj,"Default__KismetSystemLibrary")) kslCDO=obj;
            if(progMgr&&kslCDO)break;
        } if(progMgr&&kslCDO)break; }
    if(progMgr) g_worldCtx=progMgr;
    if(kslCDO){ g_kslCDO=kslCDO; uintptr_t cls=ClassOf(kslCDO); if(cls){ ResolveFuncOnClass(cls,"ExecuteConsoleCommand",&g_ecc,&g_eccThunk,&g_eccChild);
        if(g_eccChild){ g_offWCO=ParamOffset(g_eccChild,"WorldContextObject"); g_offCmd=ParamOffset(g_eccChild,"Command"); g_offSP=ParamOffset(g_eccChild,"SpecificPlayer"); } } }
}

// Walk the live object array during travel: find the tutorial GameMode INSTANCE + dump its config classes
// (GameMode member offsets from gm_config.py: GameStateClass@+0x3D0, PlayerControllerClass@+0x3D8,
// PlayerStateClass@+0x3E0), and count live PlayerController/PlayerState instances. Tells us why the PC ends up
// without a PlayerState.
static void DumpTutorialState(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; int nPC=0,nPS=0,nGM=0; uintptr_t gmInst=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
            if(strstr(cn,"PlayerController")) nPC++;
            if(strstr(cn,"PlayerState")) nPS++;
            if(strstr(cn,"GameMode_Tutorial")){ nGM++; if(!gmInst) gmInst=obj; }
        }
    }
    char psN[96]="-",gsN[96]="-",pcN[96]="-";
    if(gmInst){
        uintptr_t gs=SafeReadable((void*)(gmInst+0x3D0),8)?*(uintptr_t*)(gmInst+0x3D0):0;
        uintptr_t pc=SafeReadable((void*)(gmInst+0x3D8),8)?*(uintptr_t*)(gmInst+0x3D8):0;
        uintptr_t ps=SafeReadable((void*)(gmInst+0x3E0),8)?*(uintptr_t*)(gmInst+0x3E0):0;
        if(ps)GetFNameStr(NameId(ps),psN,sizeof(psN)); else strcpy(psN,"NULL");
        if(gs)GetFNameStr(NameId(gs),gsN,sizeof(gsN)); else strcpy(gsN,"NULL");
        if(pc)GetFNameStr(NameId(pc),pcN,sizeof(pcN)); else strcpy(pcN,"NULL");
    }
    Markerf("[DIAG%d] gmInst=0x%llX(n=%d) PSClass=%s GSClass=%s PCClass=%s livePC=%d livePS=%d\r\n",
        tag,(unsigned long long)gmInst,nGM,psN,gsN,pcN,nPC,nPS);
}

// S64/S65 DETERMINATION PROBE: find the live CoreGameManager (persists from the menu) and dump its match/model/
// session/server props + their live object pointers. The revert is a RAW Browse-to-lobby = the front-end FLOW
// MANAGER browsing home; if CoreGameManager's match model is NULL during the tutorial, the flow manager has no
// valid match -> PATH 1 (populate the model via the primitive) is the fix, and this dumps the field OFFSET needed
// to do it. Also dumps the match model's bIsValid/MatchState if non-null.
static void DumpCoreGameState(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t cgm=0; char cgmCls[96]="-";
    for(int ci=0;ci<numChunks && !cgm;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"CoreGameManager")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0){ cgm=obj; strncpy(cgmCls,cn,sizeof(cgmCls)-1); break; } }
        }
    }
    if(!cgm){ Markerf("[CGM%d] no live CoreGameManager instance\r\n",tag); return; }
    Markerf("[CGM%d] inst=0x%llX cls=%s\r\n",tag,(unsigned long long)cgm,cgmCls);
    uintptr_t mm=0;
    uintptr_t cls=ClassOf(cgm); int guard=0;
    while(LooksLikePtr(cls) && guard++<12){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f) && i++<500){
            char pn[96];
            if(GetFNameStr(NameId(f),pn,sizeof(pn)) && (strstr(pn,"Match")||strstr(pn,"Model")||strstr(pn,"Server")||strstr(pn,"Session")||strstr(pn,"Platform"))){
                uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                uintptr_t val=(off!=0xFFFFFFFF&&SafeReadable((void*)(cgm+off),8))?*(uintptr_t*)(cgm+off):0;
                char vcls[96]="null"; if(LooksLikePtr(val)&&ClassOf(val)) GetFNameStr(NameId(ClassOf(val)),vcls,sizeof(vcls));
                Markerf("[CGM%d]   %s @0x%X = 0x%llX (%s)\r\n",tag,pn,off,(unsigned long long)val,vcls);
                if(strcmp(pn,"CoreGameMatchModel")==0) mm=val;
            }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;   // UStruct::SuperStruct
    }
    // Dump the match model's own state props (bIsValid / MatchState / TeamSize / MatchInfo etc.) to see if the
    // flow manager considers the match INVALID -> the likely revert trigger (PATH 1 = force valid + InProgress).
    if(LooksLikePtr(mm)){
        uintptr_t mcls=ClassOf(mm); int g2=0;
        while(LooksLikePtr(mcls) && g2++<12){
            uintptr_t f=SafeReadable((void*)(mcls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(mcls+UFUNC_CHILDPROPS):0; int i=0;
            while(LooksLikePtr(f) && i++<500){
                char pn[96];
                if(GetFNameStr(NameId(f),pn,sizeof(pn)) && (strstr(pn,"Valid")||strstr(pn,"State")||strstr(pn,"Team")||strstr(pn,"Match")||strstr(pn,"Info")||strstr(pn,"Self"))){
                    uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                    uint32_t v4=(off!=0xFFFFFFFF&&SafeReadable((void*)(mm+off),4))?*(uint32_t*)(mm+off):0;
                    uintptr_t pv=(off!=0xFFFFFFFF&&SafeReadable((void*)(mm+off),8))?*(uintptr_t*)(mm+off):0;
                    char vcls[64]="-"; if(LooksLikePtr(pv)&&ClassOf(pv)) GetFNameStr(NameId(ClassOf(pv)),vcls,sizeof(vcls));
                    Markerf("[MM%d]   %s @0x%X u32=%u ptr=0x%llX(%s)\r\n",tag,pn,off,v4,(unsigned long long)pv,vcls);
                }
                f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0;
            }
            mcls=SafeReadable((void*)(mcls+0x48),8)?*(uintptr_t*)(mcls+0x48):0;
        }
    }
}

// S65 PATH-1 EXPERIMENT: the CoreGameMatchModel exists but bIsValid=0 / MatchState=0 during the force-open
// tutorial (no valid match) -> the front-end flow manager browses home. Continuously poke bIsValid=1 +
// MatchState=5 (InProgress) on CoreGameManager.CoreGameMatchModel across the tutorial to test whether keeping
// the model "valid + in-progress" stops the revert. Offsets from the S65 DumpCoreGameState dump.
constexpr uint32_t CGM_MM_OFF=0x6E0;      // CoreGameManager.CoreGameMatchModel
constexpr uint32_t MM_VALID_OFF=0x30;     // CoreGameMatchModel.bIsValid (bool)
constexpr uint32_t MM_STATE_OFF=0x48;     // CoreGameMatchModel.MatchState (enum: InProgress=5)
// S65: poking bIsValid (with or without MatchState=InProgress) crashes tutorial init ~2s after world-up (the
// init takes the "valid match" branch and derefs the INCOMPLETE model / null MatchInfo). So the durable default
// is FALSE (diagnostic sampling only, no crash-inducing poke). PATH 1 requires building a COMPLETE valid model.
static const bool kPokeMatchModel = false;
// S65 PATH-1: dump CoreGameManager/CoreGameMatchModel FUNCTIONS + model state at the MENU, then SKIP force-open
// (game stays alive) — to find a native setter/factory that populates the model consistently (missions-style),
// instead of hand-writing the 19-field MatchInfo. Set false for a normal force-open run.
static const bool kInvestigateOnly = false;   // S68: run the spawn+possess branch (kRunMode)
static uintptr_t g_cgm = 0;
static uintptr_t FindCoreGameManager(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"CoreGameManager")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0) return obj; } } }
    return 0;
}
static void DumpClassFuncs(int tag, const char* label, uintptr_t cls);   // fwd decl (defined below)
// S68: find live (non-CDO) placed actors usable as a SpawnDefaultPawnFor StartSpot (a valid map location).
static void DumpStartSpots(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; int shown=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"CapturePoint")||strstr(cn,"RespawnBeacon")||strstr(cn,"PlayerStart")||strstr(cn,"LandingPad")||strstr(cn,"DropPod")||strstr(cn,"SpawnPoint")||strstr(cn,"StartSpot")||strstr(cn,"DropPlane")){
                char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
                if(shown++<24) Markerf("[SPOT%d] 0x%llX cls=%s name=%s\r\n",tag,(unsigned long long)obj,cn,on);
            } } }
    Markerf("[SPOT%d] total live startspot-ish actors=%d\r\n",tag,shown);
}
static void DumpParams(int tag, const char* label, uintptr_t cls, const char* fname);   // fwd decl (S67)
// S66: find the ULokiGameFeatureToggles subsystem + dump its props (a bReady/bInitialized flag + a toggle
// container) and functions, so we can make it "ready". Prefer a live instance; fall back to the CDO.
static void DumpFeatureToggles(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    uintptr_t ft=0, ftDef=0; char ftCls[96]="-";
    for(int ci=0;ci<numChunks && !ft;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"FeatureToggles")&&!strstr(cn,"ActivationMethod")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
                if(strncmp(on,"Default__",9)==0){ if(!ftDef){ftDef=obj; strncpy(ftCls,cn,sizeof(ftCls)-1);} } else { ft=obj; strncpy(ftCls,cn,sizeof(ftCls)-1); break; } } } }
    uintptr_t use = ft?ft:ftDef;
    if(!use){ Markerf("[FT%d] no LokiGameFeatureToggles object found\r\n",tag); return; }
    Markerf("[FT%d] %s=0x%llX cls=%s\r\n",tag, ft?"inst":"CDO", (unsigned long long)use, ftCls);
    uintptr_t cls=ClassOf(use); int guard=0, shown=0;
    while(LooksLikePtr(cls) && guard++<10){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f) && i++<400 && shown<50){
            char pn[96]; if(GetFNameStr(NameId(f),pn,sizeof(pn))){
                uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                uint32_t v4=(off!=0xFFFFFFFF&&SafeReadable((void*)(use+off),4))?*(uint32_t*)(use+off):0;
                uintptr_t pv=(off!=0xFFFFFFFF&&SafeReadable((void*)(use+off),8))?*(uintptr_t*)(use+off):0;
                Markerf("[FT%d]   %s @0x%X u32=%u ptr=0x%llX\r\n",tag,pn,off,v4,(unsigned long long)pv); shown++;
            }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
    DumpClassFuncs(tag,"FeatureToggles",ClassOf(use));
}

// S66: find the live tutorial gamemode instance and dump its (and its ALokiRoundGameMode/ALokiGameMode supers')
// UFunctions — looking for a phase-advance / drop-in / deploy / start trigger callable via the PI primitive.
static void DumpGameModeFuncs(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t gm=0;
    for(int ci=0;ci<numChunks && !gm;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"GameMode_Tutorial")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0){ gm=obj; break; } } } }
    if(!gm){ Markerf("[GMFN%d] no live tutorial gamemode instance\r\n",tag); return; }
    Markerf("[GMFN%d] gm=0x%llX\r\n",tag,(unsigned long long)gm);
    DumpClassFuncs(tag,"TutorialGameMode",ClassOf(gm));
    DumpParams(tag,"GM",ClassOf(gm),"SpawnDefaultPawnFor");
    DumpParams(tag,"GM",ClassOf(gm),"SpawnDefaultPawnAtTransform");
    DumpParams(tag,"GM",ClassOf(gm),"K2_OnRestartPlayer");
}

// S67: find the live local PlayerController + dump its UFunctions (looking for Possess / spawn / deploy entry
// points) and the params of the key spawn/possess functions, to build the LEAD-B native spawn+possess call.
static void DumpParams(int tag, const char* label, uintptr_t cls, const char* fname){
    // walk cls (+supers) Children for the named UFunction, then dump its param FFields (name@+0x20, offset@+0x44).
    int g=0;
    while(LooksLikePtr(cls) && g++<10){
        uintptr_t f=SafeReadable((void*)(cls+0x50),8)?*(uintptr_t*)(cls+0x50):0; int i=0;
        while(LooksLikePtr(f) && i++<1000){
            if(NameIs(f,fname)){
                Markerf("[PARM%d] %s::%s params:\r\n",tag,label,fname);
                uintptr_t p=SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(f+UFUNC_CHILDPROPS):0; int k=0;
                while(LooksLikePtr(p) && k++<20){
                    char pn[96]; if(GetFNameStr(NameId(p),pn,sizeof(pn))){
                        uint32_t off=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
                        Markerf("[PARM%d]   %s @0x%X\r\n",tag,pn,off);
                    }
                    p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0;
                }
                return;
            }
            f=SafeReadable((void*)(f+0x30),8)?*(uintptr_t*)(f+0x30):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
    Markerf("[PARM%d] %s::%s NOT FOUND\r\n",tag,label,fname);
}
static void DumpPCFuncs(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t pc=0;
    for(int ci=0;ci<numChunks && !pc;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"LokiPlayerController_Dev")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0){ pc=obj; break; } } } }
    if(!pc){ Markerf("[PCFN%d] no live BP_LokiPlayerController_Dev instance\r\n",tag); return; }
    Markerf("[PCFN%d] pc=0x%llX\r\n",tag,(unsigned long long)pc);
    // SuperStruct-offset diagnostic: which of +0x40/+0x48 points at the parent UClass (ALokiPlayerController)?
    { uintptr_t c=ClassOf(pc); for(uint32_t so=0x38; so<=0x50; so+=8){ uintptr_t sup=SafeReadable((void*)(c+so),8)?*(uintptr_t*)(c+so):0; char sn[96]="?"; if(LooksLikePtr(sup)&&SafeReadable((void*)(sup+NAME_OFF),4)) GetFNameStr(NameId(sup),sn,sizeof(sn)); Markerf("[SUP%d] cls+0x%X=0x%llX (%s)\r\n",tag,so,(unsigned long long)sup,sn); } }
    DumpClassFuncs(tag,"LokiPC",ClassOf(pc));
    DumpParams(tag,"LokiPC",ClassOf(pc),"Possess");
    DumpParams(tag,"LokiPC",ClassOf(pc),"K2_Possess");
}

// Census of live (non-CDO) pawn/hero/drop actors — tells us whether a controllable hero dropped in.
static void DumpPawns(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    int shown=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            // A LokiCharacterMovementComponent's Outer IS the owning hero pawn — dump the Outer's class+name
            // (that's the pawn class to possess). Also dump its Outer's Outer (world/level) for context.
            if(strstr(cn,"LokiCharacterMovementComponent")){
                char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
                uintptr_t owner=SafeReadable((void*)(obj+0x28),8)?*(uintptr_t*)(obj+0x28):0;   // UObject::Outer
                if(!LooksLikePtr(owner))continue;
                char ocn[128]="?", oon[128]="?"; if(ClassOf(owner)) GetFNameStr(NameId(ClassOf(owner)),ocn,sizeof(ocn)); GetFNameStr(NameId(owner),oon,sizeof(oon));
                if(strncmp(oon,"Default__",9)==0)continue;   // skip CDO subobjects — LIVE instances only
                if(shown++<20) Markerf("[PAWN%d] LIVE pawn=0x%llX cls=%s name=%s\r\n",tag,(unsigned long long)owner,ocn,oon);
            }
        }
    }
    Markerf("[PAWN%d] total hero/champion/drop/lokichar live actors=%d\r\n",tag,shown);
}

// Dump a class's UFunctions (Children @ UStruct+0x50, Next @ UField+0x30) + supers, filtered to names likely to
// be a match-model setter/factory. Finds the native entry point to populate CoreGameMatchModel consistently.
static void DumpClassFuncs(int tag, const char* label, uintptr_t cls){
    if(!LooksLikePtr(cls)){ Markerf("[FUNC%d] %s: bad class\r\n",tag,label); return; }
    char cnm[96]="?"; GetFNameStr(NameId(cls),cnm,sizeof(cnm));
    Markerf("[FUNC%d] %s cls=%s:\r\n",tag,label,cnm);
    int guard=0;
    while(LooksLikePtr(cls) && guard++<8){
        char scn[96]="?"; GetFNameStr(NameId(cls),scn,sizeof(scn));
        uintptr_t f=SafeReadable((void*)(cls+0x50),8)?*(uintptr_t*)(cls+0x50):0; int i=0;
        while(LooksLikePtr(f) && i++<1000){
            char fn[96];
            if(GetFNameStr(NameId(f),fn,sizeof(fn)) && (strstr(fn,"Match")||strstr(fn,"Update")||strstr(fn,"Valid")||strstr(fn,"Info")||strstr(fn,"Start")||strstr(fn,"Create")||strstr(fn,"Set")||strstr(fn,"Handle")||strstr(fn,"Enter")||strstr(fn,"Refresh")||strstr(fn,"State")||strstr(fn,"Ready")||strstr(fn,"Init")||strstr(fn,"Phase")||strstr(fn,"Drop")||strstr(fn,"Deploy")||strstr(fn,"Round")||strstr(fn,"Advance")||strstr(fn,"Begin")||strstr(fn,"Spawn")||strstr(fn,"Possess")||strstr(fn,"Player")||strstr(fn,"Warmup")||strstr(fn,"Countdown")))
                Markerf("[FUNC%d]   %s::%s\r\n",tag,scn,fn);
            f=SafeReadable((void*)(f+0x30),8)?*(uintptr_t*)(f+0x30):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;   // UStruct::SuperStruct
    }
}

// Tight loop poking the match model valid+InProgress for ~13s (covers the ~7s-after-force-open revert window).
static void PokeMatchModelLoop(){
    if(!g_cgm) g_cgm=FindCoreGameManager();
    if(!g_cgm){ Marker("[POKE] no CoreGameManager\r\n"); return; }
    Markerf("[POKE] cgm=0x%llX poking mm+0x%X=1 mm+0x%X=5 ~13s\r\n",(unsigned long long)g_cgm,MM_VALID_OFF,MM_STATE_OFF);
    DWORD t0=GetTickCount(); long n=0; uintptr_t lastMM=0;
    while(GetTickCount()-t0<13000){
        uintptr_t mm=SafeReadable((void*)(g_cgm+CGM_MM_OFF),8)?*(uintptr_t*)(g_cgm+CGM_MM_OFF):0;
        if(LooksLikePtr(mm)){
            if(mm!=lastMM){ Markerf("[POKE] mm=0x%llX (t+%lums)\r\n",(unsigned long long)mm,GetTickCount()-t0); lastMM=mm; }
            if(SafeReadable((void*)(mm+MM_VALID_OFF),1)) *(volatile uint8_t*)(mm+MM_VALID_OFF)=1;
            // S65: MatchState=5 (InProgress) poke crashed init (~2.4s post world-up, before "ready") — forcing
            // InProgress with a null MatchInfo is inconsistent. Test bIsValid-only (MatchState left at 0).
            // if(SafeReadable((void*)(mm+MM_STATE_OFF),1)) *(volatile uint8_t*)(mm+MM_STATE_OFF)=5;
        }
        n++; Sleep(3);
    }
    Markerf("[POKE] done %ld iters\r\n",n);
}

// ============================ S62 INSTRUMENTED CUSTOM-LOGIN (STEP 0) ============================
// Instead of de-overriding GameMode vtable slot 285 to *plain* stock AGameModeBase::Login (which returns a
// PC whose PlayerState is null -> SpawnPlayActor fatal "PlayerState is null"), point slot 285 at CustomLogin:
// it calls stock Login (gmb[285]) with the same 7 args, LOGS the PC + PlayerState state AT LOGIN-RETURN (no
// 350ms/14ms sampling race), then returns the PC. This captures the exact null-cause so the synthesis step (poke
// PlayerStateClass / bWantsPlayerState, or SpawnActor+assign) can be added minimally next.
static volatile void* g_stockLogin = nullptr;    // gmb[285] = stock AGameModeBase::Login (resolved at install)
static volatile long g_loginCalls = 0;

// Offset of a named FProperty on a class, walking ChildProperties@+0x58 then the SuperStruct@+0x40 chain.
static uint32_t PropOffset(uintptr_t cls, const char* name){
    int guard=0;
    while(LooksLikePtr(cls) && guard++<12){
        uintptr_t f = SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8) ? *(uintptr_t*)(cls+UFUNC_CHILDPROPS) : 0;
        int i=0;
        while(LooksLikePtr(f) && i++<500){
            if(NameIs(f,name)) return SafeReadable((void*)(f+FPROP_OFFSET),4) ? *(uint32_t*)(f+FPROP_OFFSET) : 0xFFFFFFFF;
            f = SafeReadable((void*)(f+FIELD_NEXT),8) ? *(uintptr_t*)(f+FIELD_NEXT) : 0;
        }
        cls = SafeReadable((void*)(cls+0x48),8) ? *(uintptr_t*)(cls+0x48) : 0;   // UStruct::SuperStruct (@+0x48 this build)
    }
    return 0xFFFFFFFF;
}

// C handler invoked by CustomLogin after stock Login returns. gm = GameMode(this), pc = returned PC.
extern "C" void LogLoginResult(void* gm_, void* pc_, void* err_){
    uintptr_t gm=(uintptr_t)gm_, pc=(uintptr_t)pc_;
    long n = InterlockedIncrement(&g_loginCalls);
    char gmN[96]="?", pcN[96]="?", psClsN[96]="?", curPsN[64]="-";
    uintptr_t psCls = (gm && SafeReadable((void*)(gm+0x3E0),8)) ? *(uintptr_t*)(gm+0x3E0) : 0;
    if(gm && ClassOf(gm)) GetFNameStr(NameId(ClassOf(gm)), gmN, sizeof(gmN));
    if(pc && ClassOf(pc)) GetFNameStr(NameId(ClassOf(pc)), pcN, sizeof(pcN));
    if(psCls) GetFNameStr(NameId(psCls), psClsN, sizeof(psClsN)); else strcpy(psClsN,"NULL");
    // PlayerControllerClass (@GM+0x3D8): the class whose InitPlayerState we must de-override to stock.
    char pcClsN[96]="?"; uintptr_t pcCls = (gm && SafeReadable((void*)(gm+0x3D8),8)) ? *(uintptr_t*)(gm+0x3D8) : 0;
    if(pcCls) GetFNameStr(NameId(pcCls), pcClsN, sizeof(pcClsN)); else strcpy(pcClsN,"NULL");
    uintptr_t psPtr=0; uint32_t psOff=0xFFFFFFFF;
    if(pc){ psOff = PropOffset(ClassOf(pc),"PlayerState"); if(psOff!=0xFFFFFFFF && SafeReadable((void*)(pc+psOff),8)) psPtr=*(uintptr_t*)(pc+psOff); }
    if(psPtr && ClassOf(psPtr)) GetFNameStr(NameId(ClassOf(psPtr)), curPsN, sizeof(curPsN)); else strcpy(curPsN, psPtr?"?":"NULL");
    // arg7 = ErrorMessage FString {Data@0, Num@8}: stock Login writes WHY it returned null here.
    char errS[128]="-";
    if(err_ && SafeReadable(err_,16)){
        uintptr_t d=*(uintptr_t*)err_; uint32_t num=*(uint32_t*)((uint8_t*)err_+8);
        if(num<=1) strcpy(errS,"(empty=approved)");
        else if(d && num<120 && SafeReadable((void*)d,num*2)){ for(uint32_t i=0;i<num-1&&i<127;i++) errS[i]=(char)*(uint16_t*)(d+i*2); errS[(num-1)<127?(num-1):127]=0; }
    }
    Markerf("[LOGIN%ld] gm=%s PCClass=%s pc=0x%llX(%s) PSClass=%s PS(off=0x%X)=0x%llX(%s) err='%s'\r\n",
        n, gmN, pcClsN, (unsigned long long)pc, pcN, psClsN, psOff, (unsigned long long)psPtr, curPsN, errS);
}

// ============================ S63 PLAYERSTATE FIX (STEP 1) ============================
// S62 root cause: stock AGameModeBase::Login SPAWNS the PC fine but BP_LokiPlayerController_Dev_C has a NULL
// PlayerState (the Loki PC defers PlayerState creation to network replication; a standalone force-open has no
// server) -> stock Login's InitNewPlayer returns "PlayerState is null" -> Login returns null -> fatal.
// FIX STRATEGY (both done in PrepareLogin, called from CustomLogin *before* stock Login runs):
//   (instrument) Diff the Loki PC C++ vtable vs stock APlayerController's, .text-guarded, and flag the slot(s)
//     whose STOCK function references GameMode+0x3E0 (PlayerStateClass) = the InitPlayerState candidate(s).
//     The class loads only during travel, so this MUST run in-shim at Login-time (not offline).
//   (fix, kFixMode) FIX_A2_STOCKPC: poke GM+0x3D8 (PlayerControllerClass) -> stock APlayerController so
//     SpawnPlayerController makes a fully-stock PC whose stock InitPlayerState creates the PlayerState in
//     standalone. Near-certain to clear the gate, low crash risk, keeps the game ALIVE to observe downstream
//     (but a stock PC loses Loki input/camera/possession -> diagnostic, not the final fix).
//   (fix, kFixMode) FIX_TARGETED_INITPS: de-override the InitPlayerState slot(s) in the Loki PC vtable to stock
//     -> the Loki PC creates its own BP_LokiPlayerState locally, keeping full Loki PC behavior (the real fix).
// All patches are TRANSIENT: restored right after stock Login returns (integrity check covers .rdata vtables).
constexpr uintptr_t kTextLoRva=0x1000, kTextHiRva=0x7649000;                 // .text range (above = .rdata/data)
constexpr uintptr_t GM_GSCLASS_OFF=0x3D0, GM_PCCLASS_OFF=0x3D8, GM_PSCLASS_OFF=0x3E0;  // AGameModeBase config members
enum FixMode { FIX_NONE=0, FIX_A2_STOCKPC=1, FIX_TARGETED_INITPS=2 };
static const int kFixMode = FIX_TARGETED_INITPS;   // S63: A2 cleared login (parked at WaitingForClientsReady w/ stock PC);
                                                   // now keep the Loki PC via InitPlayerState de-override (slots 260/273)

static uintptr_t g_lokiPCVt=0;                        // Loki PC C++ vtable base (for restore)
static int g_pcPatchSlots[8]={0}; static uintptr_t g_pcPatchOrig[8]={0}; static int g_nPcPatch=0;
static uintptr_t g_savedPCClass=0; static bool g_pokedPCClass=false;

// Find the first object whose FName == want (matches CDOs by their "Default__<Class>" FName).
static uintptr_t FindObjByName(const char* want){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; if(NameIs(obj,want))return obj; } }
    return 0;
}
// Scan up to cap bytes at fn for the 4-byte little-endian value needle (e.g. a disp32 like 0x3E0).
static bool ScanDisp(uintptr_t fn,uint32_t needle,int cap){
    if(!fn)return false;
    for(int i=0;i+4<=cap;i++){ if(!SafeReadable((void*)(fn+i),4))break; uint32_t v; memcpy(&v,(void*)(fn+i),4); if(v==needle)return true; }
    return false;
}

// Runs INSIDE CustomLogin, before stock Login. gm = GameMode(this). Dumps the PC vtable diff + applies the fix.
static void PrepareLogin(uintptr_t gm){
    g_nPcPatch=0; g_pokedPCClass=false; g_lokiPCVt=0;
    if(!gm){ Marker("[PREP] gm=0\r\n"); return; }
    uintptr_t lokiCDO=FindObjByName("Default__BP_LokiPlayerController_Dev_C");
    uintptr_t stockCDO=FindObjByName("Default__PlayerController");
    uintptr_t lokiVt =(lokiCDO && SafeReadable((void*)lokiCDO,8))?*(uintptr_t*)lokiCDO:0;
    uintptr_t stockVt=(stockCDO&& SafeReadable((void*)stockCDO,8))?*(uintptr_t*)stockCDO:0;
    uintptr_t stockPCClass=stockCDO?ClassOf(stockCDO):0;
    Markerf("[PREP] lokiCDO=0x%llX(vt rva 0x%llX) stockCDO=0x%llX(vt rva 0x%llX) stockPCClass=0x%llX\r\n",
        (unsigned long long)lokiCDO,(unsigned long long)(lokiVt?lokiVt-g_modBase:0),
        (unsigned long long)stockCDO,(unsigned long long)(stockVt?stockVt-g_modBase:0),(unsigned long long)stockPCClass);
    int psSlots[8]; int nps=0,nOverride=0;
    if(lokiVt && stockVt){
        uintptr_t tLo=g_modBase+kTextLoRva, tHi=g_modBase+kTextHiRva; int endRun=0;
        for(int s=0;s<380 && endRun<8;s++){
            if(!SafeReadable((void*)(stockVt+s*8),8)||!SafeReadable((void*)(lokiVt+s*8),8)){endRun++;continue;}
            uintptr_t sv=*(uintptr_t*)(stockVt+s*8), lv=*(uintptr_t*)(lokiVt+s*8);
            if(sv<tLo||sv>=tHi){endRun++;continue;} endRun=0;
            if(sv==lv)continue; nOverride++;
            if(ScanDisp(sv,(uint32_t)GM_PSCLASS_OFF,400)){    // stock fn references GM+0x3E0 => InitPlayerState-like
                if(nps<8){ psSlots[nps]=s; Markerf("[DIFF] PS-cand slot %d stockRva=0x%llX lokiRva=0x%llX\r\n",
                    s,(unsigned long long)(sv-g_modBase),(unsigned long long)(lv-g_modBase)); }
                nps++;
            }
        }
    }
    Markerf("[DIFF] overrideCount=%d psCandidates=%d fixMode=%d\r\n",nOverride,nps,kFixMode);
    g_lokiPCVt=lokiVt;
    if(kFixMode==FIX_TARGETED_INITPS && lokiVt && stockVt && nps>=1 && nps<=4){
        for(int k=0;k<nps;k++){ int s=psSlots[k]; uintptr_t* tgt=(uintptr_t*)(lokiVt+(uintptr_t)s*8);
            uintptr_t sval=*(uintptr_t*)(stockVt+(uintptr_t)s*8); DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op))continue;
            g_pcPatchSlots[g_nPcPatch]=s; g_pcPatchOrig[g_nPcPatch]=*tgt; g_nPcPatch++; *tgt=sval; DWORD d=0; VirtualProtect(tgt,8,op,&d); }
        Markerf("[FIX] targeted: de-overrode %d PC vtable slot(s) -> stock InitPlayerState\r\n",g_nPcPatch);
    } else {
        // FIX_A2_STOCKPC (also the fallback when targeted can't identify the slot).
        uintptr_t* tgt=(uintptr_t*)(gm+GM_PCCLASS_OFF);
        if(stockPCClass && SafeReadable(tgt,8)){ DWORD op=0; if(VirtualProtect(tgt,8,PAGE_READWRITE,&op)){
            g_savedPCClass=*tgt; *tgt=stockPCClass; g_pokedPCClass=true; DWORD d=0; VirtualProtect(tgt,8,op,&d);
            Markerf("[FIX] A2: GM+0x3D8 PlayerControllerClass -> stock APlayerController 0x%llX (was 0x%llX)\r\n",
                (unsigned long long)stockPCClass,(unsigned long long)g_savedPCClass); } }
        else Marker("[FIX] A2 FAILED: no stockPCClass or GM+0x3D8 unreadable\r\n");
    }
}
// Restore all Login-time patches right after stock Login returns.
static void RestoreLoginPatches(uintptr_t gm){
    for(int k=0;k<g_nPcPatch;k++){ uintptr_t* tgt=(uintptr_t*)(g_lokiPCVt+(uintptr_t)g_pcPatchSlots[k]*8);
        DWORD op=0; if(VirtualProtect(tgt,8,PAGE_READWRITE,&op)){ *tgt=g_pcPatchOrig[k]; DWORD d=0; VirtualProtect(tgt,8,op,&d); } }
    g_nPcPatch=0;
    if(g_pokedPCClass && gm){ uintptr_t* tgt=(uintptr_t*)(gm+GM_PCCLASS_OFF);
        DWORD op=0; if(VirtualProtect(tgt,8,PAGE_READWRITE,&op)){ *tgt=g_savedPCClass; DWORD d=0; VirtualProtect(tgt,8,op,&d); } g_pokedPCClass=false; }
}

// GameMode vtable slot 285 (Login). Plain C++ fn — the Win64 ABI matches the vtable call site (rcx=this(GM),
// rdx=NewPlayer, r8=InRemoteRole, r9=&Portal, [rsp+0x28]=&Options, [rsp+0x30]=&UniqueId, [rsp+0x38]=&ErrorMessage).
typedef void* (*PFN_LOGIN)(void*,void*,uint64_t,void*,void*,void*,void*);
extern "C" void* CustomLogin(void* gm,void* np,uint64_t rr,void* portal,void* options,void* uid,void* err){
    PrepareLogin((uintptr_t)gm);
    void* pc = g_stockLogin ? ((PFN_LOGIN)g_stockLogin)(gm,np,rr,portal,options,uid,err) : nullptr;
    LogLoginResult(gm,pc,err);
    RestoreLoginPatches((uintptr_t)gm);
    return pc;
}

static uintptr_t g_savedLoginVt[5];   // slot-285 originals per match vtable, for restore
// Install (or restore) CustomLogin into slot 285 of the match-mode vtables. Transient: install before the
// force-open, restore after (integrity check covers .rdata vtables). Records stock Login = gmb[285] for the tramp.
static void InstallCustomLogin(bool install){
    uintptr_t* gmb=(uintptr_t*)(g_modBase+kStockGmbVtRva);
    const int NV=(int)(sizeof(kMatchVtRvas)/sizeof(kMatchVtRvas[0])); const int slot=285;
    if(install && SafeReadable(gmb+slot,8)) g_stockLogin=(void*)gmb[slot];
    int n=0;
    for(int v=0; v<NV; v++){
        uintptr_t* tgt=(uintptr_t*)(g_modBase+kMatchVtRvas[v]+(uintptr_t)slot*8);
        if(!SafeReadable(tgt,8)) continue;
        DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op)) continue;
        if(install){ g_savedLoginVt[v]=*tgt; *tgt=(uintptr_t)&CustomLogin; }
        else if(g_savedLoginVt[v]){ *tgt=g_savedLoginVt[v]; }
        DWORD d=0; VirtualProtect(tgt,8,op,&d); n++;
    }
    Markerf("[VT] custom-login %s: %d vtables slot285, stockLogin=0x%llX tramp=0x%llX\r\n",
        install?"INSTALL":"restore", n, (unsigned long long)(uintptr_t)g_stockLogin, (unsigned long long)(uintptr_t)&CustomLogin);
}

// S62: [LOGIN1] proved stock Login returns a NULL PC (PlayerStateClass was valid) => the reject is
// ALokiGameSession::ApproveLogin. De-override ALokiGameSession's virtual overrides to stock AGameSession so
// ApproveLogin approves -> stock Login spawns a real PC + PlayerState. vtdiff_gamesession.py: ALokiGameSession
// vtable rva 0x898D628 vs stock AGameSession rva 0x80854F8; overrides at slots {0(dtor),298,299,301,313,314}.
// De-override the AGameSession-region ones {298,299,313,314} (301 is a non-GS-region virtual; 0 is the dtor).
// RVAs stable (base 0x7FF6B54F0000). Transient like the GameMode de-override.
constexpr uintptr_t kLokiGSVtRva = 0x898D628, kStockGSVtRva = 0x80854F8;
static const int kGSSlots[] = {298,299,313,314};
static uintptr_t g_savedGSVt[8];
static void InstallGameSessionDeoverride(bool install){
    uintptr_t* loki=(uintptr_t*)(g_modBase+kLokiGSVtRva);
    uintptr_t* stock=(uintptr_t*)(g_modBase+kStockGSVtRva);
    const int NS=(int)(sizeof(kGSSlots)/sizeof(kGSSlots[0])); int n=0;
    for(int s=0; s<NS; s++){
        int slot=kGSSlots[s]; uintptr_t* tgt=loki+slot;
        if(!SafeReadable(tgt,8)||!SafeReadable(stock+slot,8)) continue;
        DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op)) continue;
        if(install){ g_savedGSVt[s]=*tgt; *tgt=stock[slot]; }
        else if(g_savedGSVt[s]){ *tgt=g_savedGSVt[s]; }
        DWORD d=0; VirtualProtect(tgt,8,op,&d); n++;
    }
    Markerf("[VT] gamesession de-override %s: %d slots {298,299,313,314}\r\n", install?"INSTALL":"restore", n);
}
// ================================================================================================

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] tutorial_launch (force-open LVL_Tutorial via ExecuteConsoleCommand) started\r\n");
    bool fromFile=LoadCommand();
    Markerf("[0] command %s: '%ls'\r\n", fromFile?"from tutorial-launch-cmd.txt":"(default fallback)", g_cmd);
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    if(kInvestigateOnly){
        Marker("[INV] investigate-only: dumping CoreGameManager/CoreGameMatchModel state + functions at the menu\r\n");
        DumpTutorialState(0); DumpPawns(0); DumpStartSpots(0);
        Marker("[INV] done; NOT force-opening (game stays at menu)\r\n"); return 0;
    }
    if(kRunMode==RM_SPAWNPOSSESS){
        Marker("[SP] spawn+possess mode (inject into the RUNNING tutorial)\r\n");
        if(!ResolveSpawnPossess()){ Marker("[SP] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[SP] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[SP] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[SP] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
        UninstallHook();
        char pcn[96]="-"; if(LooksLikePtr(g_spawnedPawn)&&ClassOf(g_spawnedPawn)) GetFNameStr(NameId(ClassOf(g_spawnedPawn)),pcn,sizeof(pcn));
        Markerf("[SP] done step=%ld spawnedPawn=0x%llX cls=%s (called=%ld hitsGT=%ld)\r\n",
            (long)g_spStep,(unsigned long long)g_spawnedPawn,pcn,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ Resolve(); if(g_worldCtx&&g_eccThunk&&g_eccChild&&g_offCmd!=0xFFFFFFFF)break; Sleep(500);}
    if(!g_worldCtx||!g_eccThunk||g_offCmd==0xFFFFFFFF){Markerf("[2] FAIL resolve worldCtx=0x%llX kslCDO=0x%llX eccThunk=0x%llX child=0x%llX offWCO=0x%X offCmd=0x%X offSP=0x%X\r\n",(unsigned long long)g_worldCtx,(unsigned long long)g_kslCDO,(unsigned long long)g_eccThunk,(unsigned long long)g_eccChild,g_offWCO,g_offCmd,g_offSP);return 3;}
    Markerf("[2] worldCtx=0x%llX kslCDO=0x%llX eccThunk=0x%llX(rva 0x%llX) child=0x%llX offWCO=0x%X offCmd=0x%X offSP=0x%X gameTid=%lu cmd='%ls'\r\n",(unsigned long long)g_worldCtx,(unsigned long long)g_kslCDO,(unsigned long long)g_eccThunk,(unsigned long long)(g_eccThunk-g_modBase),(unsigned long long)g_eccChild,g_offWCO,g_offCmd,g_offSP,g_gameTid,g_cmd);
    g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Marker("[3] hook built; issuing ExecuteConsoleCommand('open LVL_Tutorial') on the game thread...\r\n");
    if(kPokeMatchModel){ g_cgm=FindCoreGameManager(); Markerf("[3] pre-cached CoreGameManager=0x%llX\r\n",(unsigned long long)g_cgm); }
    InstallCustomLogin(true);   // S62: slot-285 -> CustomLogin (calls stock Login + logs the PlayerState at Login-return)
    // (GameSession de-override removed — the vtdiff read past the vtable end; instrument ErrorMessage instead.)
    if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");InstallCustomLogin(false);return 6;}
    DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
    UninstallHook();
    if(g_done){
        Markerf("[4] CALLED (called=%ld hitsGT=%ld) — de-override held; %s across travel...\r\n",(long)g_called,(long)g_hitsGT, kPokeMatchModel?"POKING match model valid":"sampling tutorial state");
        if(kPokeMatchModel){
            DumpCoreGameState(0);       // pre-poke state
            PokeMatchModelLoop();       // keep bIsValid=1 + MatchState=InProgress across the revert window
            DumpCoreGameState(9);       // post state
        } else {
            // KEEP CustomLogin (slot-285) installed until the tutorial Login actually fires. The "open" console
            // command is DEFERRED — Login runs ~7s later (after LoadMap). Restoring too early => the strict
            // native Login runs => "ALokiGameMode::Login failed to Login" fatal. Poll g_loginCalls (set by
            // CustomLogin/LogLoginResult), max 16s, then a grace. No object-walk here (avoid init contention);
            // survey the running tutorial via a separate census inject.
            DWORD hs=GetTickCount(); while(g_loginCalls==0 && GetTickCount()-hs<16000) Sleep(50);
            Sleep(1500);
        }
    } else {
        Markerf("[4] TIMEOUT no game-thread PI in 8s (hitsGT=%ld)\r\n",(long)g_hitsGT);
    }
    InstallCustomLogin(false);  // restore slot-285 so the ~3-5min code-integrity check sees the vtables clean
    Marker("[5] done (vtable restored)\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
