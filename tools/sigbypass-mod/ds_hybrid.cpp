// ds_hybrid — SESSION 72: client-side HYBRID match-entry shim for the DEDICATED-SERVER-networked tutorial client.
//
// CONTEXT: the DS route (S70) puts the client in the LIVE tutorial world with a valid replicated LokiGameState —
// but the local player is a SPECTATOR: stock networked APlayerController, no Loki PC, no hero pawn, no drop-in
// (S71: the tutorial drop-in lives in a GAMEMODE component the stub can't run). This shim uses the S55 game-thread
// native-call primitive (hook ProcessInternal @base+0x13454A0, capture a live FFrame, call UFunction thunks
// directly) to drive the local player into a controllable hero — the pieces the DS session provides for free
// (live world + valid GameState) are what the force-open route lacked.
//
// PHASE 1 (this build, kMode=MODE_CENSUS): READ-ONLY census of the DS client — confirm the primitive fires in the
// networked client, find the local PlayerController / GameState / DefaultPawn, resolve the possession UFunctions,
// and locate a spawnable hero class + world context. Scopes Phase 2 (spawn+possess) with zero guessing.
//
// Build:  clang++ -shared -O2 ds_hybrid.cpp -o ds_hybrid.dll -lkernel32
// Inject (into the LIVE DS client): tools/inject/inject.exe mmap <PID> ds_hybrid.dll
// Marker: docs/ds-hybrid-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <math.h>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\ds-hybrid-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, OUTER_OFF=0x28, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t UST_CHILDREN=0x50, UST_SUPER=0x48, FIELD_NEXT_UF=0x30, FIELD_NEXT=0x18, FPROP_OFFSET=0x44, FPROP_FLAGS=0x38;
constexpr uint64_t CPF_OutParm=0x100, CPF_ReturnParm=0x400;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_OUTPARMS=0x80, FF_PROPCHAIN=0x88;
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

// MODE_CENSUS: read-only census. MODE_POSSESS_DP: ClientRestart(PC, DefaultPawn). MODE_SPAWN_HERO (Phase 3, the
// decisive test): spawn a BP_HERO pawn client-side via GameplayStatics deferred-spawn (WorldContext=ProgressionManager,
// hardcoded transform) + possess with the stock PC — does a hero even INITIALIZE + become controllable in the DS session?
enum Mode { MODE_CENSUS=0, MODE_POSSESS_DP=1, MODE_SPAWN_HERO=2, MODE_SPECTATOR_CAM=3, MODE_DEBUGCAM=4, MODE_FREECAM=5 };
static const int kMode = MODE_SPECTATOR_CAM;
// S77 anti-tamper DODGE test (catalog_store_fix pattern): the permanent ProcessInternal .text hook is what the
// code-integrity check catches. catalog_store_fix survives long-term because it leaves NO persistent .text mod
// (self-restores in ~6s + heap pokes only). PORT: run the overlay-hide for a SHORT window then UNINSTALL the hook
// and let the process run clean. kSpectatorHookMs = how long to hold the hook (overlay-hide) before uninstalling.
// kEnableTranslation gates the movement block (input-poll + K2_SetActorLocation) OFF for a clean pure-overlay-hide
// survival test — movement needs continuous game-thread exec (a data/vtable hook, not a .text hook) = phase 2.
// S77 DEFAULT = the durable stable-view dodge (proven): one-shot overlay-hide ~20s then uninstall (survives
// long-term). kEnableTranslation=true adds WASD movement DURING the hook window, but that requires holding the
// .text hook the whole time — and a standing hook is UNRELIABLE (survived 20s overlay-only, but a 30s
// movement window crashed on the integrity check mid-window). Continuous movement needs a NON-.text continuous
// mechanism (data/vtable hook, or transient-per-step) — see the doc's phase-3 note. Leave translation OFF for
// the durable-view default; the pawn+K2_SetActorLocation resolution + DoSpectatorCam movement path are kept.
static const bool     kEnableTranslation = false;
static const unsigned kSpectatorHookMs   = 8000;    // overlay-hide window (shortened from 20s: less standing-hook
                                                    // exposure -> fewer anti-tamper catches; the hide is one-shot so
                                                    // a few seconds suffices, then uninstall)
// S78 refinement #3 — feel: base horizontal/vertical speeds (per step; Sleep(8) => ~90 steps/sec) + a soft Z clamp
// so holding UP no longer rockets the cam into the skybox (which also aggravates the far-away jaggedness, #2).
// SHIFT boosts. Values are generous — the clamp only catches the runaway (S77 reached Z=94500), not legit high views.
// S78 live feedback (S78a): 85/step read as "hyper fast" — cut hard for a controllable fly-cam. Shift boosts
// when you want to cover ground. Step rate is ~40-90/s, so 26/step ~= 1000-2300 u/s (map is ~15000 u wide).
static const double   kMoveSpeed   = 26.0;    // horizontal units/step (was 85 — too fast)
static const double   kMoveSpeedV  = 18.0;    // vertical units/step (was 50)
static const double   kBoostMul    = 4.0;     // hold SHIFT for fast travel
static const double   kZMax        = 22000.0; // soft ceiling (skybox guard)
static const double   kZMin        = -4000.0; // soft floor

static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[640];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>6)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0));
    return EXCEPTION_CONTINUE_SEARCH;
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
static bool ClassName(uintptr_t obj,char* out,int cap){ uintptr_t c=ClassOf(obj); if(!c)return false; return GetFNameStr(NameId(c),out,cap); }
static bool ObjName(uintptr_t obj,char* out,int cap){ return GetFNameStr(NameId(obj),out,cap); }

// Iterate GUObjectArray, invoking cb(obj) for each valid object. cb returns true to stop.
template<class F> static void ForEachObject(F cb){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; if(cb(obj))return; } }
}
// First non-CDO instance whose class name == exact.
static uintptr_t FindInstExactClass(const char* exact){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ char cn[128]; if(!ClassName(o,cn,sizeof(cn)))return false; if(strcmp(cn,exact)!=0)return false; char on[128]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false; out=o; return true; }); return out; }
// First non-CDO instance whose class name CONTAINS sub.
static uintptr_t FindInstClassSub(const char* sub){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ char cn[128]; if(!ClassName(o,cn,sizeof(cn)))return false; if(!strstr(cn,sub))return false; char on[128]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false; out=o; return true; }); return out; }
// First object whose OWN name starts with pre and ends with suf (e.g. "BP_HERO_", "_C") — a UClass.
static uintptr_t FindObjNamePreSuf(const char* pre,const char* suf){ uintptr_t out=0; size_t lp=strlen(pre),ls=strlen(suf); ForEachObject([&](uintptr_t o)->bool{ char on[160]; if(!ObjName(o,on,sizeof(on)))return false; size_t l=strlen(on); if(l<lp+ls)return false; if(strncmp(on,pre,lp)!=0)return false; if(strcmp(on+l-ls,suf)!=0)return false; out=o; return true; }); return out; }
// First object whose OWN name == want exactly.
static uintptr_t FindObjExact(const char* want){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ if(NameIs(o,want)){ out=o; return true; } return false; }); return out; }
// Does cls's SuperStruct chain (@+0x48) contain a class whose name contains `sub`?
static bool SuperChainHas(uintptr_t cls,const char* sub){ int g=0; while(LooksLikePtr(cls)&&g++<16){ char cn[128]; if(GetFNameStr(NameId(cls),cn,sizeof(cn))&&strstr(cn,sub))return true; cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0; } return false; }
// Find a real HERO PAWN class: name "BP_HERO_<X>_C" whose ancestry includes LokiCharacter (excludes projectiles/UI).
static uintptr_t FindHeroPawnClass(){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ char on[160]; if(!ObjName(o,on,sizeof(on)))return false; size_t l=strlen(on); if(l<11)return false; if(strncmp(on,"BP_HERO_",8)!=0)return false; if(strcmp(on+l-2,"_C")!=0)return false; if(strstr(on,"Projectile")||strstr(on,"Cosmetic")||strstr(on,"Ability"))return false; char mc[64]; if(!ClassName(o,mc,sizeof(mc))||!strstr(mc,"BlueprintGeneratedClass"))return false; if(!SuperChainHas(o,"LokiCharacter")&&!SuperChainHas(o,"LokiHeroCharacter"))return false; out=o; return true; }); return out; }

// Resolve a UFunction by name on a class (+ SuperStruct chain @+0x48). Reports thunk (Func@+0xE0) + childProps.
static void ResolveFunc(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child){
    int g=0; while(LooksLikePtr(cls)&&g++<14){
        uintptr_t f=SafeReadable((void*)(cls+UST_CHILDREN),8)?*(uintptr_t*)(cls+UST_CHILDREN):0; int i=0;
        while(LooksLikePtr(f)&&i++<800){ if(NameIs(f,name)){ *fn=(void*)f;
                if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))*thunk=th;}
                if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))*child=cp;} return; }
            f=SafeReadable((void*)(f+FIELD_NEXT_UF),8)?*(uintptr_t*)(f+FIELD_NEXT_UF):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static void ReportFunc(uintptr_t cls,const char* name){ void* fn=0; uintptr_t th=0,cp=0; ResolveFunc(cls,name,&fn,&th,&cp);
    if(fn) Markerf("[FN]   %-26s fn=0x%llX thunk=0x%llX childProps=0x%llX\r\n",name,(unsigned long long)(uintptr_t)fn,(unsigned long long)th,(unsigned long long)cp);
    else   Markerf("[FN]   %-26s NOT FOUND\r\n",name);
}
// Offset_Internal@+0x44 of the named param in a UFunction's ChildProperties chain (Next@+0x18).
static uint32_t ParamOffset(uintptr_t childHead,const char* name){
    uintptr_t f=childHead; int i=0;
    while(LooksLikePtr(f)&&i++<40){ if(NameIs(f,name)){ return SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF; } f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
    return 0xFFFFFFFF;
}
// The S55 game-thread native-call primitive: call a UFunction thunk with a prepared params buffer.
static uint8_t g_pbuf[256]={0}, g_rbuf[64]={0};
// S58/S74 OUT/ref-param marshalling (ported from tutorial_launch): build an FOutParmRec chain for every CPF_OutParm
// param (PropAddr into the Locals buffer) and set FFrame.OutParms@+0x80. Without this the exec thunk walks a null/stale
// OutParms for by-ref/out params (e.g. const FTransform& in BeginDeferredActorSpawnFromClass) and crashes — the exact
// S72 wall #1 that killed the client-side hero spawn.
static uint8_t g_outparms[8*24]={0};
static void BuildOutParms(uintptr_t childProps, uint8_t* locals){
    memset(g_outparms,0,sizeof(g_outparms)); *(uint64_t*)(g_myframe+FF_OUTPARMS)=0;
    uintptr_t f=childProps; int n=0; uint8_t* prev=nullptr; uint8_t* head=nullptr;
    while(LooksLikePtr(f) && n<8){
        uint64_t flags=0; if(SafeReadable((void*)(f+FPROP_FLAGS),8)) flags=*(uint64_t*)(f+FPROP_FLAGS);
        if((flags&CPF_OutParm) && !(flags&CPF_ReturnParm)){
            int32_t off=0; if(SafeReadable((void*)(f+FPROP_OFFSET),4)) off=*(int32_t*)(f+FPROP_OFFSET);
            uint8_t* rec=g_outparms+n*24; *(uintptr_t*)(rec+0)=f; *(uintptr_t*)(rec+8)=(uintptr_t)(locals+off); *(uintptr_t*)(rec+16)=0;
            if(prev) *(uintptr_t*)(prev+16)=(uintptr_t)rec; else head=rec;
            prev=rec; n++;
        }
        uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8)) nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx;
    }
    *(uint64_t*)(g_myframe+FF_OUTPARMS)=(uint64_t)head;
}
static void CallNative(void* func, uintptr_t thunk, uintptr_t childProps, void* context, void* paramsBuf, void* resultBuf){
    memcpy(g_myframe, g_template, sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=func;
    *(void**)(g_myframe+FF_OBJECT)=context;
    *(uint64_t*)(g_myframe+FF_CODE)=0;
    *(void**)(g_myframe+FF_LOCALS)=paramsBuf;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)childProps;
    BuildOutParms(childProps,(uint8_t*)paramsBuf);   // S74: FFrame.OutParms chain for by-ref/out params (fixes the S72 spawn crash)
    ((PFN_THUNK)thunk)(context, g_myframe, resultBuf);
}

// ---- hook plumbing (proven in tutorial_launch.cpp) ----
static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};for(int i=0;i<2;i++){if(!cands[i])continue;void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(p){intptr_t d=(intptr_t)p-(intptr_t)anchor;if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000)return (uint8_t*)p;VirtualFree(p,0,MEM_RELEASE);}}}return nullptr;}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
extern "C" void OnPI(void* ctx, void* frame, void* res);
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
// S77 phase-3 smoothness: FAST hook toggle — only suspend/check the GAME THREAD (ProcessInternal is
// game-thread-dominant), not all ~135 threads. The all-threads SafeWrite took ~seconds/call (400 retries x
// suspend-all), making the per-step transient movement jump every 3-5s. This makes install/uninstall ~us so
// movement is smooth. Small residual risk: an off-thread ProcessInternal in the 5-byte prologue during the write
// (rare) — acceptable for a spectator fly-cam. Used only by the movement loop, not the one-shot overlay-hide.
static HANDLE g_gtHandle=0;
static bool SafeWriteFast(uint8_t* dst,const uint8_t* src,size_t len){
    if(!g_gtHandle) g_gtHandle=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT,FALSE,g_gameTid);
    HANDLE gt=g_gtHandle; uintptr_t lo=(uintptr_t)dst,hi=(uintptr_t)dst+len;
    for(int a=0;a<200;a++){ if(gt)SuspendThread(gt); bool unsafe=false; CONTEXT c; c.ContextFlags=CONTEXT_CONTROL;
        if(gt&&GetThreadContext(gt,&c)&&c.Rip>=lo&&c.Rip<hi) unsafe=true;
        if(!unsafe){ DWORD op=0; if(VirtualProtect(dst,len,PAGE_EXECUTE_READWRITE,&op)){ memcpy(dst,src,len); DWORD d=0; VirtualProtect(dst,len,op,&d); FlushInstructionCache(GetCurrentProcess(),dst,len); if(gt)ResumeThread(gt); return true; } }
        if(gt)ResumeThread(gt); Sleep(0); }
    return false;
}
static bool InstallHookFast(){ if(!g_pi||!g_stub)return false; int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5)); uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)}; return SafeWriteFast(g_pi,p,5); }
static void UninstallHookFast(){ if(g_pi)SafeWriteFast(g_pi,g_stolen,5); }
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// ---- PHASE 1: census ----
static void Census(){
    Marker("[CENSUS] === DS-networked tutorial client census ===\r\n");

    // Local PlayerController: the stub uses stock APlayerController, so the networked PC's class is exactly
    // "PlayerController". Report it + whether any Loki PC exists.
    uintptr_t pc=FindInstExactClass("PlayerController");
    if(pc){ char on[128]="?"; ObjName(pc,on,sizeof(on)); Markerf("[CENSUS] stock PlayerController: obj=0x%llX name=%s\r\n",(unsigned long long)pc,on);
        // resolve possession UFunctions on its class chain
        uintptr_t cls=ClassOf(pc);
        ReportFunc(cls,"Possess"); ReportFunc(cls,"ClientRestart"); ReportFunc(cls,"AcknowledgePossession");
        ReportFunc(cls,"ServerRestartPlayer"); ReportFunc(cls,"ClientSetHUD"); ReportFunc(cls,"SetPawn"); ReportFunc(cls,"OnPossess");
    } else Marker("[CENSUS] no stock PlayerController instance found\r\n");
    uintptr_t lokiPc=FindInstClassSub("LokiPlayerController");
    if(lokiPc){ char cn[128]="?",on[128]="?"; ClassName(lokiPc,cn,sizeof(cn)); ObjName(lokiPc,on,sizeof(on)); Markerf("[CENSUS] LIVE Loki PC present: obj=0x%llX cls=%s name=%s\r\n",(unsigned long long)lokiPc,cn,on); }
    else Marker("[CENSUS] no live LokiPlayerController actor (only the stock networked PC)\r\n");

    // GameState
    uintptr_t gs=FindInstExactClass("LokiGameState");
    if(!gs) gs=FindInstClassSub("LokiGameState");
    if(gs){ char cn[128]="?",on[128]="?"; ClassName(gs,cn,sizeof(cn)); ObjName(gs,on,sizeof(on)); Markerf("[CENSUS] GameState: obj=0x%llX cls=%s name=%s\r\n",(unsigned long long)gs,cn,on); }
    else Marker("[CENSUS] no LokiGameState instance\r\n");

    // The replicated DefaultPawn from the stub
    uintptr_t dp=FindInstExactClass("DefaultPawn");
    if(dp){ char on[128]="?"; ObjName(dp,on,sizeof(on)); Markerf("[CENSUS] DefaultPawn: obj=0x%llX name=%s\r\n",(unsigned long long)dp,on); }
    else Marker("[CENSUS] no DefaultPawn instance\r\n");

    // A spawnable hero class (BP_HERO_<X>_C) — target for Phase 2 spawn.
    uintptr_t heroCls=FindObjNamePreSuf("BP_HERO_","_C");
    if(heroCls){ char on[160]="?"; ObjName(heroCls,on,sizeof(on)); char ccn[128]="?"; ClassName(heroCls,ccn,sizeof(ccn)); Markerf("[CENSUS] hero class: obj=0x%llX name=%s (meta=%s)\r\n",(unsigned long long)heroCls,on,ccn); }
    else Marker("[CENSUS] no BP_HERO_*_C class found\r\n");

    // World context candidates for spawning: a GameInstance / World. Report a ProgressionManager (proven world ctx).
    uintptr_t pm=FindInstClassSub("ProgressionManager");
    if(pm){ char on[128]="?"; ObjName(pm,on,sizeof(on)); Markerf("[CENSUS] ProgressionManager (world ctx): obj=0x%llX name=%s\r\n",(unsigned long long)pm,on); }

    Marker("[CENSUS] === done ===\r\n");
}

// ---- PHASE 2: possess the replicated DefaultPawn client-side ----
// Resolved OFF the game thread (in Worker) to keep the hook's game-thread work minimal (a big object walk inside
// the PI hook stalls the game thread). The primitive CALL itself must run on the game thread (in OnPI).
static uintptr_t g_pc=0, g_dp=0; static void* g_crFn=0; static uintptr_t g_crThunk=0, g_crChild=0; static uint32_t g_crPawnOff=0xFFFFFFFF;
static bool ResolvePossessDP(){
    g_pc=FindInstExactClass("PlayerController");
    g_dp=FindInstExactClass("DefaultPawn");
    if(!g_pc||!g_dp){ Markerf("[POSSESS] resolve FAIL pc=0x%llX dp=0x%llX\r\n",(unsigned long long)g_pc,(unsigned long long)g_dp); return false; }
    ResolveFunc(ClassOf(g_pc),"ClientRestart",&g_crFn,&g_crThunk,&g_crChild);
    if(!g_crFn||!g_crThunk||!g_crChild){ Marker("[POSSESS] ClientRestart resolve FAIL\r\n"); return false; }
    // ClientRestart(APawn* NewPawn) — find the pawn param offset in the params layout.
    g_crPawnOff=ParamOffset(g_crChild,"NewPawn"); if(g_crPawnOff==0xFFFFFFFF) g_crPawnOff=ParamOffset(g_crChild,"P"); if(g_crPawnOff==0xFFFFFFFF) g_crPawnOff=0;
    Markerf("[POSSESS] resolved pc=0x%llX dp=0x%llX crThunk=0x%llX crChild=0x%llX pawnOff=0x%X\r\n",
            (unsigned long long)g_pc,(unsigned long long)g_dp,(unsigned long long)g_crThunk,(unsigned long long)g_crChild,g_crPawnOff);
    return true;
}
static void DoPossessDP(){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_crPawnOff)=(uint64_t)g_dp;         // NewPawn = the replicated DefaultPawn
    Marker("[POSSESS] >>> calling ClientRestart(PC, DefaultPawn)\r\n");
    CallNative(g_crFn,g_crThunk,g_crChild,(void*)g_pc,g_pbuf,g_rbuf);
    Marker("[POSSESS] <<< ClientRestart returned (no crash) — client should now control the DefaultPawn.\r\n");
}

// ---- PHASE 3: spawn a BP_HERO pawn client-side (the decisive viability test) ----
static uintptr_t g_gsCDO=0, g_heroCls=0, g_worldCtx=0, g_pcSpawn=0;
static void* g_beginFn=0; static uintptr_t g_beginThunk=0, g_beginChild=0;
static void* g_finishFn=0; static uintptr_t g_finishThunk=0, g_finishChild=0;
static void* g_possFn=0; static uintptr_t g_possThunk=0, g_possChild=0;
static uint32_t g_oBWorld=0,g_oBClass=8,g_oBXform=0x10,g_oBColl=0x70,g_oBOwner=0x78,g_oBRet=0x88;
static uint32_t g_oFActor=0,g_oFXform=0x10,g_oFRet=0x70,g_oInPawn=0;
static uint32_t g_offParam(uintptr_t child,const char* n,uint32_t dflt){ uint32_t o=ParamOffset(child,n); return o==0xFFFFFFFF?dflt:o; }
// Isolation test: spawn a STOCK ADefaultPawn class (trivial construction) via the SAME BeginDeferred path instead
// of a hero. If this spawns cleanly but the hero crashes, the hero's BP/GAS construction is the crash (dead-end for
// client-side heroes); if this also crashes, the BeginDeferred call mechanism is at fault.
static const bool kSpawnStockIsolation = true;
static bool ResolveSpawnHero(){
    g_heroCls=FindHeroPawnClass();
    if(kSpawnStockIsolation){ uintptr_t dpInst=FindInstExactClass("DefaultPawn"); if(dpInst){ g_heroCls=ClassOf(dpInst); Marker("[SPAWN] ISOLATION: spawning STOCK DefaultPawn class instead of the hero.\r\n"); } }
    g_worldCtx=FindInstClassSub("ProgressionManager"); if(!g_worldCtx) g_worldCtx=FindInstExactClass("LokiGameState");
    g_pcSpawn=FindInstExactClass("PlayerController");
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    if(!g_heroCls||!g_worldCtx||!g_gsCDO){ Markerf("[SPAWN] resolve FAIL hero=0x%llX world=0x%llX gsCDO=0x%llX\r\n",(unsigned long long)g_heroCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO); return false; }
    uintptr_t gc=ClassOf(g_gsCDO);
    ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
    ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
    if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBOwner=g_offParam(g_beginChild,"Owner",0x78); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
    if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    if(g_pcSpawn){ ResolveFunc(ClassOf(g_pcSpawn),"Possess",&g_possFn,&g_possThunk,&g_possChild); if(g_possChild) g_oInPawn=g_offParam(g_possChild,"InPawn",0); }
    char hn[160]="?"; ObjName(g_heroCls,hn,sizeof(hn));
    Markerf("[SPAWN] resolved hero=%s(0x%llX) world=0x%llX gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX possThunk=0x%llX\r\n",
            hn,(unsigned long long)g_heroCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_possThunk);
    Markerf("[SPAWN] Begin params: world@0x%X class@0x%X xform@0x%X coll@0x%X owner@0x%X ret@0x%X | Finish: actor@0x%X xform@0x%X ret@0x%X | Possess InPawn@0x%X\r\n",
            g_oBWorld,g_oBClass,g_oBXform,g_oBColl,g_oBOwner,g_oBRet,g_oFActor,g_oFXform,g_oFRet,g_oInPawn);
    return g_beginThunk&&g_finishThunk;
}
static void DoSpawnHero(){
    // FTransform (UE5 double/LWC): Rotation FQuat@0x0 (W@0x18), Translation FVector@0x20, Scale3D FVector@0x38.
    static uint8_t xf[0x60]={0};
    *(double*)(xf+0x18)=1.0;                                   // rotation W=1 (identity)
    *(double*)(xf+0x20)=0.0; *(double*)(xf+0x28)=0.0; *(double*)(xf+0x30)=500.0;  // translation (0,0,500)
    *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;    // scale (1,1,1)
    // 1. BeginDeferredActorSpawnFromClass(World=ProgressionManager, HeroClass, xform, coll=AlwaysSpawn) -> deferred
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_worldCtx;
    *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)g_heroCls;
    memcpy(g_pbuf+g_oBXform,xf,0x50);
    g_pbuf[g_oBColl]=2;                                        // AdjustIfPossibleButAlwaysSpawn
    Marker("[SPAWN] >>> BeginDeferredActorSpawnFromClass(hero)\r\n");
    CallNative(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf);
    uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!LooksLikePtr(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
    char dcn[96]="-"; if(LooksLikePtr(deferred)&&ClassOf(deferred))GetFNameStr(NameId(ClassOf(deferred)),dcn,sizeof(dcn));
    Markerf("[SPAWN] <<< deferred=0x%llX cls=%s\r\n",(unsigned long long)deferred,dcn);
    if(!LooksLikePtr(deferred)){ Marker("[SPAWN] deferred spawn returned null — hero spawn FAILED.\r\n"); return; }
    // 2. FinishSpawningActor(deferred, xform) -> hero
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
    Marker("[SPAWN] >>> FinishSpawningActor\r\n");
    CallNative(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf);
    uintptr_t hero=(uintptr_t)*(uint64_t*)g_rbuf; if(!LooksLikePtr(hero)) hero=*(uint64_t*)(g_pbuf+g_oFRet); if(!LooksLikePtr(hero)) hero=deferred;
    char hcn[96]="-"; if(LooksLikePtr(hero)&&ClassOf(hero))GetFNameStr(NameId(ClassOf(hero)),hcn,sizeof(hcn));
    Markerf("[SPAWN] <<< HERO SPAWNED actor=0x%llX cls=%s — hero pawn EXISTS client-side!\r\n",(unsigned long long)hero,hcn);
    // 3. Possess with the stock PC (SUPERVIVE gameplay needs a Loki PC, but this tests whether possession + basic
    //    control engage at all).
    if(LooksLikePtr(hero)&&g_possThunk&&g_pcSpawn){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)(g_pbuf+g_oInPawn)=(uint64_t)hero;
        Marker("[SPAWN] >>> Possess(stockPC, hero)\r\n");
        CallNative(g_possFn,g_possThunk,g_possChild,(void*)g_pcSpawn,g_pbuf,g_rbuf);
        Marker("[SPAWN] <<< Possess returned (no crash).\r\n");
    }
}

// ---- Route D (MODE_SPECTATOR_CAM): reveal the live tutorial world for the spectator ----
// The DS client Joins the real LVL_Tutorial with a live LokiGameState (S70) but sits behind the
// "DROP IN... LOADING" overlay as a dead spectator. This mode censuses every UMG UUserWidget, then
// holds any loading-ish widget SetVisibility(Collapsed) on the game thread for ~40s so we can SEE what
// the world/camera actually shows. Read-mostly: the only calls are UWidget::SetVisibility (guarded).
static bool CallGuarded(void* fn, uintptr_t th, uintptr_t ch, void* ctx, void* pb, void* rb){
    __try { CallNative(fn,th,ch,ctx,pb,rb); return false; } __except(EXCEPTION_EXECUTE_HANDLER){ return true; }
}
static void* g_svFn=0; static uintptr_t g_svThunk=0, g_svChild=0; static uint32_t g_svVisOff=0xFFFFFFFF;
static uintptr_t g_loadWidgets[48]={0}; static int g_nLoadW=0; static volatile long g_scHits=0;
// Fly-cam puppet: move the dead-spectator pawn directly (input pipeline is dead in the un-deployed state).
// S76: RootComponent + RelativeLocation offsets are RESOLVED BY REFLECTION (both are UPROPERTYs) — a
// hardcoded 0x1B0 guess crashed the client (it resolved into read-only module memory and a keypress wrote
// there). All writes are HEAP-GUARDED. WASD = move (yaw steered by arrows), Space/Ctrl = up/down.
static uintptr_t g_specPawn=0, g_specRoot=0; static HWND g_hwnd=0; static double g_yaw=0.0;
static uint32_t g_specLocOff=0xFFFFFFFF;
static uintptr_t g_moveComp=0; static uint32_t g_velOff=0xFFFFFFFF;
static bool IsHeapObj(uintptr_t v){ return v>=0x10000000000ull && v<0x00007F0000000000ull && (v&7)==0; }
static uint32_t PropOffsetOnClass(uintptr_t cls,const char* name){
    int g=0; while(LooksLikePtr(cls)&&g++<14){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f)&&i++<1200){ if(NameIs(f,name)){ return SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF; } f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
    return 0xFFFFFFFF;
}
// S77 translation: move the SPECTATOR PAWN itself via K2_SetActorLocation (engine setter -> propagates the
// transform; the native dead-spectator camera targets the pawn, so moving the pawn moves the view). The S77
// velocity puppet went inert (the un-deployed SpectatorPawnMovement integrator doesn't tick), so drive position
// directly. Seed the tracked position from the pawn root's RelativeLocation (reading is fine; only WRITING a raw
// RelativeLocation wouldn't propagate).
static uintptr_t g_spPawn=0, g_spRoot=0;
static void* g_spSlaFn=0; static uintptr_t g_spSlaThunk=0, g_spSlaChild=0; static uint32_t g_spSlaLoc=0xFFFFFFFF, g_spSlaTele=0xFFFFFFFF;
static uint32_t g_spRelLocOff=0xFFFFFFFF; static double g_spX=0,g_spY=0,g_spZ=0,g_spYaw2=0; static bool g_spSeeded=false;
static volatile long g_moveArmed=0, g_moveDone=0;   // S77 phase-2 single-move test
// S78 refinement #1 — mouse-relative steering (S78a: MEMORY-DIFF auto-lock). ControlRotation is NOT a reflected
// UPROPERTY here, and a one-shot rotator scan MISSED the view yaw (it read 0 before the user rotated, so the
// filter dropped it). Instead: snapshot the PC + PlayerCameraManager at resolve, then each ~1s compare every
// 8-byte-aligned DOUBLE (FVector/FRotator are doubles in this LWC build) against the snapshot. The view yaw is
// the offset whose value keeps SWINGING as the user looks around — auto-LOCK it as the steering source (no
// rebuild needed). g_viewRotOff holds the offset of the yaw VALUE (read directly), not the FRotator base.
static uintptr_t g_viewYawObj=0;          // object holding the view yaw (PC or camera mgr)
static uint32_t  g_viewRotOff=0xFFFFFFFF; // byte offset of the yaw DOUBLE within g_viewYawObj
static bool      g_viewYawEnabled=false;  // once true (auto-locked), the heading follows the view yaw (arrows nudge)
static double    g_manualYawOff=0.0;      // arrows nudge this on top of the mouse yaw (fine-tune / fallback)
// one-time reference scan (logged once; not used for steering after the diff approach)
struct RotCand { uintptr_t obj; uint32_t off; char tag[24]; };
static RotCand   g_rotCands[16]; static int g_nRotCands=0;
// diff-discovery state (S78a v2): snapshot SEVERAL candidate objects and diff BOTH float + double, since the
// view yaw wasn't a double in the PC/CameraManager (it's a float, elsewhere, or out of range). Each object gets a
// 0x4000 snapshot; the yaw is whatever value SWINGS widest as the user looks around (float or double).
static const int kMaxDiffObj=6, kDiffLen=0x10000;
struct DiffObj { uintptr_t obj; uint8_t* snap; uint32_t len; char tag[16]; };
static uint8_t   g_snapBuf[kMaxDiffObj][kDiffLen];
static DiffObj   g_dobj[kMaxDiffObj]; static int g_nDobj=0;
enum YawKind { YK_DOUBLE=0, YK_FLOAT=1, YK_QUAT=2 };   // how to read the yaw at g_viewRotOff
struct YawTrack { uintptr_t obj; uint32_t off; int kind; double last, lo, hi; int moves; };
static YawTrack  g_yt[64]; static int g_nYt=0;
static int       g_viewYawKind=YK_DOUBLE;  // the locked yaw's storage kind
// S78a v3 — read the view yaw by CALLING a rotation getter UFunction (robust vs memory-format guessing; the
// rotation isn't a plain FRotator in range in any scanned object, so it's likely a quaternion internally). The
// getter returns a clean FRotator (degrees) on the game thread. Called inside DoStepMove so the heading is fresh.
static void*     g_rotFn=0; static uintptr_t g_rotThunk=0, g_rotChild=0; static uintptr_t g_rotCtx=0;
static uint32_t  g_rotRetOff=0; static const char* g_rotName="?";
static double    g_viewYawLive=0; static volatile long g_viewYawValid=0; static volatile long g_rotLogN=0;
// S78a v4: K2_GetActorLocation (seed the fly position from the pawn's WORLD location so the vtable hook doesn't
// teleport the view to origin) + a dirty flag so the per-frame hook only moves when the user is actually flying.
static void*     g_glaFn=0; static uintptr_t g_glaThunk=0, g_glaChild=0; static uint32_t g_glaRetOff=0;
static volatile long g_moveDirty=0, g_spSeededVt=0;
// S78b — tame the hyper-fast native mouse-look: find float sensitivity fields and continuously re-write them to
// (original * kSensMul) so rotation is controllable. kSensMul is aggressive because the native rate is extreme.
static const float kSensMul=0.06f;
static uintptr_t g_sensObj[12]; static uint32_t g_sensOff[12]; static float g_sensTarget[12]; static int g_nSens=0;
// S78c — camera-rotation take-over: capture raw mouse delta (WM_INPUT, works with the cursor locked) + locate the
// camera POV rotation (in the CameraManager's CameraCachePrivate) so a controlled-speed rotation can override the
// native hyper-fast free-look. Stage 1 = capture + locate + log (no override yet).
static volatile long g_mouseDX=0, g_mouseDY=0, g_mouseEvents=0; static uintptr_t g_camMgr=0;
// S78c take-over: spawn my own ACameraActor as the view target and drive its rotation (+ position). kStage2a uses a
// FIXED rotation to prove the view switches to my camera (mouse should stop rotating it); then mouse-drive it.
// S78c: the camera take-over is DISABLED — the game's camera manager reverts our view-target every frame (cam+0x420
// stays the DefaultPawn no matter how often we re-SetViewTargetWithBlend), so a spawned camera never renders. The
// native free-look rotation is controlled inside the game's dead-spectator camera code (not a settable field, POV
// not findable in memory, view-target un-stealable). Left here (flag off) for a future deeper camera-hook attempt.
// With this false, the shim uses the WORKING path: DefaultPawn view-target + vtable-hook position + native rotation.
static const bool kTakeoverCam=false; static const bool kStage2aFixedRot=true;
static uintptr_t g_myCam=0; static double g_camYaw=0.0, g_camPitch=-12.0; static volatile long g_camSpawnTried=0;
static void* g_sraFn=0; static uintptr_t g_sraThunk=0, g_sraChild=0; static uint32_t g_sraRotOff=0, g_sraTele=0xFFFFFFFF;
static uintptr_t g_toPC=0, g_toCamCls=0;
static void* g_toSvtbFn=0; static uintptr_t g_toSvtbThunk=0, g_toSvtbChild=0; static uint32_t g_toSvtbTgt=0, g_toSvtbBlend=8;
static void* g_toSlaFn=0; static uintptr_t g_toSlaThunk=0, g_toSlaChild=0; static uint32_t g_toSlaLoc=0, g_toSlaTele=0x19;
// per-step input state (set off-thread, consumed on the game thread in DoStepMove) + speed with boost applied
static volatile long g_inFwd=0,g_inBack=0,g_inLeft=0,g_inRight=0,g_inUp=0,g_inDn=0;
static double    g_stepSp=26.0, g_stepSpV=18.0;
static bool IsGameFocused(){ HWND fg=GetForegroundWindow(); DWORD pid=0; if(fg) GetWindowThreadProcessId(fg,&pid); return pid==GetCurrentProcessId(); }
static void ResolveSpectatorCam(){
    static const char* kKeys[]={"Loading","LoadScreen","DropIn","Deploy","MatchLoad","Splash","Intro","Startup","Transition","BlackScreen","Loadout"};
    uintptr_t widgetCls=0; int total=0;
    ForEachObject([&](uintptr_t o)->bool{
        uintptr_t c=ClassOf(o); if(!LooksLikePtr(c))return false;
        if(!SuperChainHas(c,"UserWidget"))return false;
        char on[160]="?",cn[160]="?"; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false;
        GetFNameStr(NameId(c),cn,sizeof(cn)); total++;
        Markerf("[WGT] 0x%llX %s (cls %s)\r\n",(unsigned long long)o,on,cn);
        if(!widgetCls) widgetCls=c;
        for(int k=0;k<(int)(sizeof(kKeys)/sizeof(kKeys[0]));k++){ if(strstr(cn,kKeys[k])||strstr(on,kKeys[k])){ if(g_nLoadW<48) g_loadWidgets[g_nLoadW++]=o; break; } }
        return false;
    });
    if(widgetCls){ ResolveFunc(widgetCls,"SetVisibility",&g_svFn,&g_svThunk,&g_svChild); if(g_svChild) g_svVisOff=ParamOffset(g_svChild,"InVisibility"); }
    uintptr_t cam=FindInstClassSub("CameraManager");
    uintptr_t pc=FindInstClassSub("LokiPlayerController");
    // Drive the dead-spectator's SpectatorPawnMovement Velocity (S75 velocity-puppet pattern): the integrator
    // moves the pawn + updates the cached world transform (a raw RelativeLocation poke wouldn't propagate).
    uintptr_t mc=FindInstClassSub("SpectatorPawnMovement"); if(!mc) mc=FindInstClassSub("PawnMovement");
    g_moveComp=mc; char mcn[128]="?";
    if(IsHeapObj(mc)){ ClassName(mc,mcn,sizeof(mcn)); g_velOff=PropOffsetOnClass(ClassOf(mc),"Velocity"); }
    uintptr_t updComp=0; uint32_t ucOff=(IsHeapObj(mc))?PropOffsetOnClass(ClassOf(mc),"UpdatedComponent"):0xFFFFFFFF;
    if(ucOff!=0xFFFFFFFF && IsHeapObj(mc) && SafeReadable((void*)(mc+ucOff),8)) updComp=*(uintptr_t*)(mc+ucOff);
    // S77 translation: resolve the spectator pawn actor + K2_SetActorLocation on it, seed pos from the root's RelativeLocation.
    // Find the spectator pawn ACTOR (its class name is NOT "Spectator" — only the SpectatorPawnMovement component
    // is). Primary: PC->SpectatorPawn. Fallback: the actor whose RootComponent == the movement comp's
    // UpdatedComponent (g_spRoot).
    g_spPawn=0; g_spRoot=updComp;
    if(IsHeapObj(pc)){ uint32_t spOff=PropOffsetOnClass(ClassOf(pc),"SpectatorPawn");
        if(spOff!=0xFFFFFFFF && SafeReadable((void*)(pc+spOff),8)){ uintptr_t sp=*(uintptr_t*)(pc+spOff); if(IsHeapObj(sp)) g_spPawn=sp; } }
    if(!IsHeapObj(g_spPawn) && IsHeapObj(g_spRoot)){
        ForEachObject([&](uintptr_t o)->bool{ uintptr_t c=ClassOf(o); if(!LooksLikePtr(c)||!SuperChainHas(c,"Pawn"))return false;
            uint32_t rcOff=PropOffsetOnClass(c,"RootComponent"); if(rcOff==0xFFFFFFFF)return false;
            if(SafeReadable((void*)(o+rcOff),8) && *(uintptr_t*)(o+rcOff)==(uintptr_t)g_spRoot){ g_spPawn=o; return true; } return false; });
    }
    char g_spCn[96]="?"; if(IsHeapObj(g_spPawn)) ClassName(g_spPawn,g_spCn,sizeof(g_spCn));
    Markerf("[SPEC] spPawn resolve: pc=0x%llX spPawn=0x%llX class=%s\r\n",(unsigned long long)pc,(unsigned long long)g_spPawn,g_spCn);
    // S77 phase-3 finish: the CAMERA's view target is the DefaultPawn (probe: PlayerCameraManager+0x420), NOT the
    // SpectatorPawn — so moving the SpectatorPawn didn't move the view. RETARGET the move to the view-target pawn.
    { uintptr_t vt=0;
      if(IsHeapObj(cam)&&SafeReadable((void*)(cam+0x420),8)){ uintptr_t t=*(uintptr_t*)(cam+0x420); if(IsHeapObj(t)&&LooksLikePtr(ClassOf(t))&&SuperChainHas(ClassOf(t),"Pawn")) vt=t; }
      if(!IsHeapObj(vt)) vt=FindInstClassSub("DefaultPawn");
      if(IsHeapObj(vt)){ g_spPawn=vt; char vn[96]="?"; ClassName(vt,vn,sizeof(vn));
        // re-seed pos from the new pawn's root RelativeLocation
        uintptr_t rc=0; uint32_t rcOff=PropOffsetOnClass(ClassOf(vt),"RootComponent"); if(rcOff!=0xFFFFFFFF&&SafeReadable((void*)(vt+rcOff),8)) rc=*(uintptr_t*)(vt+rcOff);
        if(IsHeapObj(rc)){ uint32_t ro=PropOffsetOnClass(ClassOf(rc),"RelativeLocation"); if(ro!=0xFFFFFFFF&&SafeReadable((void*)(rc+ro),24)){ double* P=(double*)(rc+ro); g_spX=P[0];g_spY=P[1];g_spZ=P[2]; } }
        Markerf("[SPEC] RETARGET move -> camera view-target 0x%llX (%s) seed=(%.0f,%.0f,%.0f)\r\n",(unsigned long long)vt,vn,g_spX,g_spY,g_spZ); } }
    if(IsHeapObj(g_spPawn)){ ResolveFunc(ClassOf(g_spPawn),"K2_SetActorLocation",&g_spSlaFn,&g_spSlaThunk,&g_spSlaChild);
        if(g_spSlaChild){ g_spSlaLoc=ParamOffset(g_spSlaChild,"NewLocation"); g_spSlaTele=ParamOffset(g_spSlaChild,"bTeleport"); } }
    if(IsHeapObj(g_spRoot)){ g_spRelLocOff=PropOffsetOnClass(ClassOf(g_spRoot),"RelativeLocation");
        if(g_spRelLocOff!=0xFFFFFFFF && SafeReadable((void*)(g_spRoot+g_spRelLocOff),24)){ double* P=(double*)(g_spRoot+g_spRelLocOff); g_spX=P[0];g_spY=P[1];g_spZ=P[2]; g_spSeeded=true; } }
    Markerf("[SPEC] transl: spPawn=0x%llX root=0x%llX slaThunk=0x%llX(loc@0x%X tele@0x%X) relLocOff=0x%X seed=(%.0f,%.0f,%.0f) seeded=%d\r\n",
        (unsigned long long)g_spPawn,(unsigned long long)g_spRoot,(unsigned long long)g_spSlaThunk,g_spSlaLoc,g_spSlaTele,g_spRelLocOff,g_spX,g_spY,g_spZ,g_spSeeded?1:0);
    g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
    double vx=0,vy=0,vz=0; if(IsHeapObj(mc)&&g_velOff!=0xFFFFFFFF&&SafeReadable((void*)(mc+g_velOff),24)){ double* V=(double*)(mc+g_velOff); vx=V[0];vy=V[1];vz=V[2]; }
    Markerf("[SPEC] totalWidgets=%d loadCandidates=%d svThunk=0x%llX(InVisibility@0x%X) cam=0x%llX pc=0x%llX\r\n",
        total,g_nLoadW,(unsigned long long)g_svThunk,g_svVisOff,(unsigned long long)cam,(unsigned long long)pc);
    Markerf("[SPEC] moveComp=0x%llX class=%s velOff=0x%X vel=(%.0f,%.0f,%.0f) updComp=0x%llX hwnd=0x%llX — fly: WASD move, arrows steer, Space/Ctrl up/down\r\n",
        (unsigned long long)mc,mcn,g_velOff,vx,vy,vz,(unsigned long long)updComp,(unsigned long long)(uintptr_t)g_hwnd);
}
static void DoSpectatorCam(){
    long h=InterlockedIncrement(&g_scHits); int hidden=0;
    // 1. keep the "DROP IN... LOADING" (WBP_UI_MatchTransition) overlay hidden
    if(g_svThunk && g_svVisOff!=0xFFFFFFFF){
        for(int i=0;i<g_nLoadW;i++){ uintptr_t w=g_loadWidgets[i]; if(!SafeReadable((void*)w,0x30))continue; uintptr_t wc=ClassOf(w); if(!LooksLikePtr(wc)||!SuperChainHas(wc,"UserWidget"))continue;
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint8_t*)(g_pbuf+g_svVisOff)=1; /* ESlateVisibility::Collapsed */
            if(!CallGuarded(g_svFn,g_svThunk,g_svChild,(void*)w,g_pbuf,g_rbuf)) hidden++;
        }
    } else if(h==1) Marker("[SPEC] SetVisibility unresolved -> overlay not hidden\r\n");
    // 2. fly-cam puppet: poke the spectator root WORLD location each tick from WASD/arrows (the un-deployed
    //    input path is dead, so drive position directly — like the S75 hero velocity puppet). Arrows steer the
    //    movement heading (g_yaw); WASD move in that frame; Space/Ctrl = up/down. View DIRECTION stays fixed for
    //    now (rotating the camera POV needs an offset we RE next) — this gives translate-through-the-world.
    // 2. TRANSLATION (S77): move the spectator pawn via K2_SetActorLocation (WASD, arrows steer, Space/Ctrl up/down).
    //    The native dead-spectator camera targets this pawn, so moving it moves the view. Absolute setter -> track pos.
    bool moved=false;
    if(kEnableTranslation && IsHeapObj(g_spPawn) && g_spSlaThunk && g_spSlaLoc!=0xFFFFFFFF){
        if(IsGameFocused()){
            if(GetAsyncKeyState(VK_LEFT)&0x8000)  g_spYaw2-=2.5;
            if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_spYaw2+=2.5;
            double yr=g_spYaw2*3.14159265358979/180.0, c=cos(yr), s=sin(yr), sp=300.0, dx=0,dy=0,dz=0;
            if(GetAsyncKeyState('W')&0x8000){ dx+=c; dy+=s; }
            if(GetAsyncKeyState('S')&0x8000){ dx-=c; dy-=s; }
            if(GetAsyncKeyState('D')&0x8000){ dx-=s; dy+=c; }
            if(GetAsyncKeyState('A')&0x8000){ dx+=s; dy-=c; }
            if(GetAsyncKeyState(VK_SPACE)&0x8000)   dz+=1;
            if(GetAsyncKeyState(VK_CONTROL)&0x8000) dz-=1;
            if(dx||dy||dz){ g_spX+=dx*sp; g_spY+=dy*sp; g_spZ+=dz*sp; moved=true;
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
                if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
                CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf); }
        }
    }
    if(h==1||h%100==0||moved) Markerf("[SPEC] hit %ld: overlay hidden %d/%d; spPawn=0x%llX pos=(%.0f,%.0f,%.0f) yaw=%.0f moved=%d\r\n",h,hidden,g_nLoadW,(unsigned long long)g_spPawn,g_spX,g_spY,g_spZ,g_spYaw2,moved?1:0);
}

// S77 phase-3 CONTINUOUS movement: one K2_SetActorLocation step to the worker-updated position (g_spX/Y/Z),
// fired via a TRANSIENT hook (install -> one fire -> uninstall) so NO standing .text mod ever exists (the dodge).
// Called ~15x/sec from the worker's off-thread WASD loop; kept minimal (no logging) since it runs hot.
static bool ReadViewYaw(double* out);   // fwd decl (defined after the diff-discovery helpers)
// S78a v3: read the client's view yaw by calling the rotation getter (game thread). FRotator return = Pitch@0,
// Yaw@8, Roll@16 (doubles) in the result buffer (the exec thunk writes to RESULT); params-frame ReturnValue is a
// fallback. Logs the first few reads so the marker confirms it tracks the mouse.
static void DoReadRot(){
    if(!g_rotThunk||!IsHeapObj(g_rotCtx)) return;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(CallGuarded(g_rotFn,g_rotThunk,g_rotChild,(void*)g_rotCtx,g_pbuf,g_rbuf)) return;
    double yawR=*(double*)(g_rbuf+8), yawP=*(double*)(g_pbuf+g_rotRetOff+8);
    double yaw = (yawR!=0.0)?yawR:yawP;
    long n=InterlockedIncrement(&g_rotLogN);
    if(n<=8) Markerf("[yawcall] read #%ld: rbuf(p=%.1f,y=%.1f,r=%.1f) pbuf.yaw=%.1f -> yaw=%.1f\r\n",n,*(double*)g_rbuf,yawR,*(double*)(g_rbuf+16),yawP,yaw);
    g_viewYawLive=yaw; g_viewYawValid=1;
}
// S78a: LEAN move step (S77 architecture, proven reliable) — heading + position are computed OFF-THREAD; this
// runs on the game thread and does ONLY the K2_SetActorLocation to the already-updated pos. No per-step getter
// call (that heavier variant caused the intermittent input stalls), so the transient window stays short.
static volatile long g_fired=0;
static void DoStepMove(){
    g_done=1;   // exactly one fire per transient window
    InterlockedIncrement(&g_fired);
    if(!IsHeapObj(g_spPawn)||!g_spSlaThunk||g_spSlaLoc==0xFFFFFFFF){ g_moveDone=1; return; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
    if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
    CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf);
    g_moveDone=1;
}

// ===== S78 refinement #2: DATA/VTABLE hook — durable per-frame move, no ProcessInternal dependency =====
// The transient-per-step move fires only on a game-thread ProcessInternal (a Blueprint script call), which is
// sparse when the user isn't rotating (native camera ticks don't call PI) -> intermittent input stalls (proven:
// fired=0 while steps climbed). FIX: swap a per-frame-ticked object's vtable POINTER (obj@+0, on the heap -> no
// .text mod, no thread-suspend) to a heap copy whose per-frame slot (CameraManager::UpdateCamera, a NATIVE virtual
// called every frame) is our stub. Our stub runs OnVtableTick every frame on the game thread -> the move applies
// every frame regardless of PI. Pure heap mod; the anti-tamper is a .text integrity check (per S77 RE), which a
// heap vtable/stub doesn't touch.
static const int kVtMax=400;
static volatile long g_vtCounters[kVtMax];
static uintptr_t  g_vtOrig=0, g_vtObj=0; static uintptr_t* g_vtCopy=nullptr; static int g_vtN=0, g_vtSlot=-1;
static volatile long g_vtBusy=0, g_vtTicks=0;
// S78c: resolve the take-over pieces — spawn (GameplayStatics BeginDeferred/FinishSpawning), SetViewTargetWithBlend
// (on the PC), and K2_SetActorLocation/K2_SetActorRotation on the ACameraActor class. (Reuses the DoSpawnHero spawn
// globals g_begin*/g_finish*/g_oB*/g_oF*/g_worldCtx/g_gsCDO, which are declared earlier.)
static void ResolveTakeover(){
    g_toPC=FindInstClassSub("LokiPlayerController");
    g_worldCtx=FindInstClassSub("ProgressionManager"); if(!g_worldCtx) g_worldCtx=FindInstExactClass("LokiGameState");
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    uintptr_t camCDO=FindObjExact("Default__CameraActor"); g_toCamCls=camCDO?ClassOf(camCDO):0;
    if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
        ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
        ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
        if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
        if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    }
    { uintptr_t pcCls=g_toPC?ClassOf(g_toPC):0;
      if(pcCls) ResolveFunc(pcCls,"SetViewTargetWithBlend",&g_toSvtbFn,&g_toSvtbThunk,&g_toSvtbChild);
      if(!g_toSvtbThunk){ uintptr_t pccdo=FindObjExact("Default__PlayerController"); if(pccdo) ResolveFunc(ClassOf(pccdo),"SetViewTargetWithBlend",&g_toSvtbFn,&g_toSvtbThunk,&g_toSvtbChild); }
      if(g_toSvtbChild){ g_toSvtbTgt=g_offParam(g_toSvtbChild,"NewViewTarget",0); g_toSvtbBlend=g_offParam(g_toSvtbChild,"BlendTime",8); } }
    if(g_toCamCls){ ResolveFunc(g_toCamCls,"K2_SetActorLocation",&g_toSlaFn,&g_toSlaThunk,&g_toSlaChild);
        if(g_toSlaChild){ g_toSlaLoc=g_offParam(g_toSlaChild,"NewLocation",0); g_toSlaTele=g_offParam(g_toSlaChild,"bTeleport",0x19); }
        ResolveFunc(g_toCamCls,"K2_SetActorRotation",&g_sraFn,&g_sraThunk,&g_sraChild);
        if(g_sraChild){ g_sraRotOff=g_offParam(g_sraChild,"NewRotation",0); g_sraTele=g_offParam(g_sraChild,"bTeleport",0x18); } }
    Markerf("[TO] pc=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX begin=0x%llX finish=0x%llX svtb=0x%llX(tgt@0x%X) sla=0x%llX(loc@0x%X) sra=0x%llX(rot@0x%X tele@0x%X)\r\n",
        (unsigned long long)g_toPC,(unsigned long long)g_toCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_toSvtbThunk,g_toSvtbTgt,(unsigned long long)g_toSlaThunk,g_toSlaLoc,(unsigned long long)g_sraThunk,g_sraRotOff,g_sraTele);
}
// Spawn my ACameraActor at (g_spX,g_spY,g_spZ) + SetViewTargetWithBlend to it (game thread). Returns true on success.
static bool SpawnMyCamera(){
    if(!g_beginThunk||!g_finishThunk||!IsHeapObj(g_toCamCls)||!IsHeapObj(g_worldCtx)||!IsHeapObj(g_gsCDO)){ Markerf("[TO] spawn resolve incomplete begin=0x%llX finish=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX\r\n",(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_toCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO); return false; }
    static uint8_t xf[0x60]={0}; *(double*)(xf+0x18)=1.0; *(double*)(xf+0x20)=g_spX; *(double*)(xf+0x28)=g_spY; *(double*)(xf+0x30)=g_spZ; *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_worldCtx; *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)g_toCamCls; memcpy(g_pbuf+g_oBXform,xf,0x50); g_pbuf[g_oBColl]=2;
    if(CallGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[TO] BeginDeferred FAULTED\r\n"); return false; }
    uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
    if(!IsHeapObj(deferred)){ Marker("[TO] spawn returned null\r\n"); return false; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
    if(CallGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[TO] FinishSpawning FAULTED\r\n"); return false; }
    uintptr_t cam=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(cam)) cam=*(uint64_t*)(g_pbuf+g_oFRet); if(!IsHeapObj(cam)) cam=deferred; g_myCam=cam;
    if(g_toSvtbThunk && IsHeapObj(g_toPC)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_toSvtbTgt)=(uint64_t)cam; *(float*)(g_pbuf+g_toSvtbBlend)=0.0f;
        bool f=CallGuarded(g_toSvtbFn,g_toSvtbThunk,g_toSvtbChild,(void*)g_toPC,g_pbuf,g_rbuf); Markerf("[TO] spawned cam=0x%llX + SetViewTargetWithBlend%s\r\n",(unsigned long long)cam,f?" [FAULTED]":""); }
    else Markerf("[TO] spawned cam=0x%llX (no SetViewTarget: svtb=0x%llX pc=0x%llX)\r\n",(unsigned long long)cam,(unsigned long long)g_toSvtbThunk,(unsigned long long)g_toPC);
    return IsHeapObj(g_myCam);
}
// Per-frame stub (game thread), runs every frame independent of ProcessInternal:
//   1. seed the fly position from the pawn's WORLD location on the first tick (no origin teleport),
//   2. refresh the real view yaw from the getter (throttled) so the worker's heading is correct,
//   3. apply the move ONLY when the worker marked it dirty (i.e. the user is flying) — not 720x/sec to a stale pos.
extern "C" void OnVtableTick(){
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(g_vtBusy) return; g_vtBusy=1;
    long t=InterlockedIncrement(&g_vtTicks);
    // 1. seed from world location once
    if(!g_spSeededVt){
        if(g_glaThunk && IsHeapObj(g_spPawn)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            if(!CallGuarded(g_glaFn,g_glaThunk,g_glaChild,(void*)g_spPawn,g_pbuf,g_rbuf)){
                double* R=(double*)g_rbuf; double* Rp=(double*)(g_pbuf+g_glaRetOff);
                double wx=(R[0]!=0.0||R[1]!=0.0||R[2]!=0.0)?R[0]:Rp[0], wy=(R[0]!=0.0||R[1]!=0.0||R[2]!=0.0)?R[1]:Rp[1], wz=(R[0]!=0.0||R[1]!=0.0||R[2]!=0.0)?R[2]:Rp[2];
                g_spX=wx; g_spY=wy; g_spZ=wz; Markerf("[vt] seed from world loc = (%.0f,%.0f,%.0f)\r\n",g_spX,g_spY,g_spZ); } }
        g_spSeededVt=1;
    }
    // S78c TAKE-OVER: spawn my own camera as the view target + drive its rotation (mine, slow) + position.
    if(kTakeoverCam){
        if(!g_camSpawnTried){ g_camSpawnTried=1; SpawnMyCamera(); }
        if(IsHeapObj(g_myCam)){
            // S78c: RE-ASSERT the view target every ~4 frames (the game's camera manager likely re-sets its own
            // spectator view target each tick, reverting our one-time SetViewTargetWithBlend).
            if((t&3)==0 && g_toSvtbThunk && IsHeapObj(g_toPC)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                *(uint64_t*)(g_pbuf+g_toSvtbTgt)=(uint64_t)g_myCam; *(float*)(g_pbuf+g_toSvtbBlend)=0.0f;
                CallGuarded(g_toSvtbFn,g_toSvtbThunk,g_toSvtbChild,(void*)g_toPC,g_pbuf,g_rbuf); }
            // rotation: Stage 2a = fixed (prove the view is my camera); else mouse-driven yaw/pitch.
            if(!kStage2aFixedRot){ long mdx=InterlockedExchange(&g_mouseDX,0), mdy=InterlockedExchange(&g_mouseDY,0);
                g_camYaw += mdx*0.04; g_camPitch -= mdy*0.04; if(g_camPitch>85)g_camPitch=85; if(g_camPitch<-85)g_camPitch=-85; }
            if(g_sraThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                double* R=(double*)(g_pbuf+g_sraRotOff); R[0]=g_camPitch; R[1]=g_camYaw; R[2]=0.0;   // FRotator {Pitch,Yaw,Roll}
                if(g_sraTele!=0xFFFFFFFF) g_pbuf[g_sraTele]=1;
                CallGuarded(g_sraFn,g_sraThunk,g_sraChild,(void*)g_myCam,g_pbuf,g_rbuf); }
            if(g_moveDirty && g_toSlaThunk){ g_moveDirty=0; InterlockedIncrement(&g_fired);
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                double* L=(double*)(g_pbuf+g_toSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ; if(g_toSlaTele) g_pbuf[g_toSlaTele]=1;
                CallGuarded(g_toSlaFn,g_toSlaThunk,g_toSlaChild,(void*)g_myCam,g_pbuf,g_rbuf); }
        }
        g_vtBusy=0; return;
    }
    // 2. refresh the view yaw from the getter (throttle: ~every 4th tick)
    if((t&3)==0) DoReadRot();
    // 3. apply the move only when the worker flagged input
    if(g_moveDirty && IsHeapObj(g_spPawn) && g_spSlaThunk && g_spSlaLoc!=0xFFFFFFFF){
        g_moveDirty=0; InterlockedIncrement(&g_fired);
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
        if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
        CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf);
    }
    g_vtBusy=0;
}
// vtable length: count leading code pointers (into the main module) up to cap.
static int VtableLen(uintptr_t vt,int cap){ int n=0; for(;n<cap;n++){ if(!SafeReadable((void*)(vt+n*8),8))break; uintptr_t f=*(uintptr_t*)(vt+n*8); if(f<g_modBase||f>=g_modBase+0xC000000)break; } return n; }
// A tiny per-slot trampoline that increments a counter then jumps to the original: used to find the per-frame slot.
static uintptr_t* BuildSweepVt(uintptr_t origVt,int n){
    uint8_t* blk=(uint8_t*)VirtualAlloc(nullptr,(size_t)n*32+64,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    uintptr_t* vt=(uintptr_t*)VirtualAlloc(nullptr,(size_t)n*8+64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!blk||!vt) return nullptr;
    for(int i=0;i<n;i++){ uint8_t* s=blk+i*32; uintptr_t orig=*(uintptr_t*)(origVt+i*8); Emit e{s};
        EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&g_vtCounters[i]);   // mov rax, &counter[i]
        EB(e,0xF0);EB(e,0x48);EB(e,0xFF);EB(e,0x00);               // lock inc qword [rax]
        EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)orig);              // mov rax, orig[i]
        EB(e,0xFF);EB(e,0xE0);                                     // jmp rax
        vt[i]=(uintptr_t)s; }
    return vt;
}
// Sweep: swap the object's vtable to counting trampolines for ~1.2s, restore, return the highest-count slot.
static int FindPerFrameSlot(uintptr_t obj){
    if(!IsHeapObj(obj)||!SafeReadable((void*)obj,8)) { Marker("[vt] bad obj\r\n"); return -1; }
    uintptr_t origVt=*(uintptr_t*)obj;
    if(origVt<g_modBase||origVt>=g_modBase+0xC000000){ Markerf("[vt] vtable ptr 0x%llX not in module -> abort\r\n",(unsigned long long)origVt); return -1; }
    int n=VtableLen(origVt,kVtMax); if(n<8){ Markerf("[vt] vtable too short n=%d\r\n",n); return -1; }
    for(int i=0;i<kVtMax;i++) g_vtCounters[i]=0;
    uintptr_t* sweepVt=BuildSweepVt(origVt,n); if(!sweepVt){ Marker("[vt] sweep alloc fail\r\n"); return -1; }
    *(uintptr_t*)obj=(uintptr_t)sweepVt;   // swap to counting trampolines (heap write)
    Sleep(1200);
    *(uintptr_t*)obj=origVt;               // restore
    // Log the top-8 slots by count. Pick the highest-count slot in a PER-FRAME range [kLo,kHi] (~1-4 calls/frame
    // over 1.2s at up to 144fps) — avoids hooking a HOT getter (thousands/sec) that would fire the move too often.
    const long kLo=40, kHi=900;
    char tb[400]; int tp=0; int chosen=-1; long chosenC=0;
    for(int rank=0; rank<8; rank++){ int bi=-1; long bc=0;
        for(int i=0;i<n;i++){ long c=g_vtCounters[i]; if(c>bc){ bc=c; bi=i; } }   // highest remaining
        if(bi<0) break;
        int w=_snprintf_s(tb+tp,sizeof(tb)-tp,_TRUNCATE,"[%d]=%ld ",bi,bc); if(w>0) tp+=w;
        if(bc>=kLo && bc<=kHi && bc>chosenC){ chosen=bi; chosenC=bc; }
        g_vtCounters[bi]=-1;   // mark listed so the next rank finds the next-highest
    }
    Markerf("[vt] sweep obj=0x%llX n=%d top: %s -> chosen slot=%d count=%ld\r\n",(unsigned long long)obj,n,tb,chosen,chosenC);
    if(chosen<0){ Marker("[vt] no per-frame slot in range -> abort (fall back to transient)\r\n"); return -1; }
    return chosen;
}
// Build the movement stub for a hooked slot: save arg regs -> call OnVtableTick -> restore -> jmp original[slot]
// (same register-preserving pattern as BuildHook; final jmp is transparent so the original virtual still runs).
static uint8_t* BuildVtStub(uintptr_t origFn){
    uint8_t* stub=(uint8_t*)VirtualAlloc(nullptr,0x80,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE); if(!stub) return nullptr;
    Emit e{stub};
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);   // push rcx,rdx,r8,r9
    EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);                         // sub rsp,0x28 (shadow + align)
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnVtableTick); EB(e,0xFF);EB(e,0xD0);  // mov rax,OnVtableTick; call rax
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);                         // add rsp,0x28
    EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);   // pop r9,r8,rdx,rcx
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)origFn); EB(e,0xFF);EB(e,0xE0); // mov rax,origFn; jmp rax
    return stub;
}
// Install: heap-copy the vtable, replace slot with the stub, swap obj@+0 to the copy (heap write, no .text).
static bool InstallVtableMove(uintptr_t obj,int slot){
    uintptr_t origVt=*(uintptr_t*)obj; int n=VtableLen(origVt,kVtMax); if(slot<0||slot>=n) return false;
    uintptr_t* copy=(uintptr_t*)VirtualAlloc(nullptr,(size_t)n*8+64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE); if(!copy) return false;
    for(int i=0;i<n;i++) copy[i]=*(uintptr_t*)(origVt+i*8);
    uintptr_t origFn=copy[slot]; uint8_t* stub=BuildVtStub(origFn); if(!stub) return false;
    copy[slot]=(uintptr_t)stub;
    g_vtOrig=origVt; g_vtCopy=copy; g_vtObj=obj; g_vtN=n; g_vtSlot=slot;
    *(uintptr_t*)obj=(uintptr_t)copy;   // swap
    Markerf("[vt] INSTALLED per-frame hook: obj=0x%llX slot=%d origFn=0x%llX stub=0x%llX\r\n",(unsigned long long)obj,slot,(unsigned long long)origFn,(unsigned long long)(uintptr_t)stub);
    return true;
}
static void RestoreVtable(){ if(g_vtObj && g_vtOrig && SafeReadable((void*)g_vtObj,8)){ *(uintptr_t*)g_vtObj=g_vtOrig; Marker("[vt] vtable restored\r\n"); } }

// S78c: raw mouse capture. A message-only window + RIDEV_INPUTSINK receives relative mouse deltas even though the
// game (not us) holds focus and the cursor is locked in free-look — GetCursorPos can't see that. Accumulate deltas.
static LRESULT CALLBACK RawWndProc(HWND h,UINT m,WPARAM w,LPARAM l){
    if(m==WM_INPUT){ UINT sz=0; GetRawInputData((HRAWINPUT)l,RID_INPUT,nullptr,&sz,sizeof(RAWINPUTHEADER));
        if(sz && sz<=sizeof(RAWINPUT)+128){ BYTE buf[sizeof(RAWINPUT)+128];
            if(GetRawInputData((HRAWINPUT)l,RID_INPUT,buf,&sz,sizeof(RAWINPUTHEADER))!=(UINT)-1){ RAWINPUT* ri=(RAWINPUT*)buf;
                if(ri->header.dwType==RIM_TYPEMOUSE && !(ri->data.mouse.usFlags&MOUSE_MOVE_ABSOLUTE)){
                    InterlockedAdd(&g_mouseDX,(long)ri->data.mouse.lLastX); InterlockedAdd(&g_mouseDY,(long)ri->data.mouse.lLastY); InterlockedIncrement(&g_mouseEvents); } } }
        return 0; }
    return DefWindowProcA(h,m,w,l);
}
static DWORD WINAPI RawInputThread(LPVOID){
    WNDCLASSA wc; memset(&wc,0,sizeof(wc)); wc.lpfnWndProc=RawWndProc; wc.hInstance=GetModuleHandleA(nullptr); wc.lpszClassName="dshRawIn";
    RegisterClassA(&wc);
    HWND hwnd=CreateWindowExA(0,"dshRawIn","",0,0,0,0,0,HWND_MESSAGE,nullptr,wc.hInstance,nullptr);
    if(!hwnd){ Markerf("[raw] CreateWindow fail err=%lu\r\n",GetLastError()); return 1; }
    RAWINPUTDEVICE rid; memset(&rid,0,sizeof(rid)); rid.usUsagePage=0x01; rid.usUsage=0x02; rid.dwFlags=RIDEV_INPUTSINK; rid.hwndTarget=hwnd;
    if(!RegisterRawInputDevices(&rid,1,sizeof(rid))){ Markerf("[raw] register fail err=%lu\r\n",GetLastError()); return 2; }
    Marker("[raw] raw mouse input registered (INPUTSINK)\r\n");
    MSG msg; while(GetMessage(&msg,nullptr,0,0)>0){ TranslateMessage(&msg); DispatchMessage(&msg); }
    return 0;
}

// S77 phase-3 finish: probe what DRIVES THE VIEW (the camera does NOT follow PC->SpectatorPawn). Logs PC
// pawn-related props + every actor pointer inside the PlayerCameraManager (ViewTarget.Target etc.) with the 3
// doubles after each (candidate POV Location if it's the view-target slot). Pure off-thread reads. From the dump
// we pick the actor to move (or the cam POV-location offset to override) instead of the SpectatorPawn.
static bool IsUObj(uintptr_t v){ if(!IsHeapObj(v)||!SafeReadable((void*)v,8))return false; uintptr_t vt=*(uintptr_t*)v; return vt>=g_modBase && vt<g_modBase+0xC000000; }
static void ProbeCamera(){
    uintptr_t cam=FindInstClassSub("CameraManager"); uintptr_t pc=FindInstClassSub("LokiPlayerController");
    char scn[96]="?"; if(IsHeapObj(g_spPawn)) ClassName(g_spPawn,scn,sizeof(scn));
    Markerf("[probe] cam=0x%llX pc=0x%llX spPawn=0x%llX(%s)\r\n",(unsigned long long)cam,(unsigned long long)pc,(unsigned long long)g_spPawn,scn);
    if(IsHeapObj(pc)){ uintptr_t pcCls=ClassOf(pc);
        const char* props[]={"Pawn","AcknowledgedPawn","SpectatorPawn","PlayerCameraManager"};
        for(int i=0;i<4;i++){ uint32_t o=PropOffsetOnClass(pcCls,props[i]); if(o==0xFFFFFFFF||!SafeReadable((void*)(pc+o),8))continue;
            uintptr_t v=*(uintptr_t*)(pc+o); char cn[96]="?"; if(IsUObj(v))ClassName(v,cn,sizeof(cn));
            Markerf("[probe] PC->%s @0x%X = 0x%llX (%s)\r\n",props[i],o,(unsigned long long)v,cn); } }
    if(IsHeapObj(cam)){ char ccn[96]="?"; ClassName(cam,ccn,sizeof(ccn)); Markerf("[probe] cameraMgr class=%s\r\n",ccn);
        for(uint32_t off=0x28; off<0x800; off+=8){ if(!SafeReadable((void*)(cam+off),8))continue; uintptr_t v=*(uintptr_t*)(cam+off);
            if(!IsUObj(v))continue; uintptr_t c=ClassOf(v); if(!SuperChainHas(c,"Actor"))continue;
            char cn[96]="?"; ClassName(v,cn,sizeof(cn)); char on[96]="?"; ObjName(v,on,sizeof(on));
            double d0=0,d1=0,d2=0; if(SafeReadable((void*)(cam+off+8),24)){ d0=*(double*)(cam+off+8);d1=*(double*)(cam+off+16);d2=*(double*)(cam+off+24); }
            Markerf("[probe] cam+0x%X -> actor 0x%llX %s (%s) next3d=(%.0f,%.0f,%.0f)\r\n",off,(unsigned long long)v,on,cn,d0,d1,d2); } }
}

// S78 refinement #1: does the 24 bytes at p look like an FRotator (3 doubles Pitch/Yaw/Roll)? Tight filter to
// keep the scan's false-positive rate low: finite, pitch in [-90,90], yaw in [-181,361], |roll|<2, not all-zero.
static bool IsRotatorD(uintptr_t p){
    if(!SafeReadable((void*)p,24)) return false;
    double pit=*(double*)p, yaw=*(double*)(p+8), rol=*(double*)(p+16);
    if(!(pit==pit)||!(yaw==yaw)||!(rol==rol)) return false;                 // NaN reject
    if(pit< -90.0001||pit>90.0001) return false;
    if(yaw< -181.0||yaw>361.0) return false;
    if(rol< -2.0||rol>2.0) return false;
    if(pit==0.0&&yaw==0.0&&rol==0.0) return false;                          // all-zero = noise
    return true;
}
static void AddRotCand(uintptr_t obj,uint32_t off,const char* tag){
    if(g_nRotCands>=16) return;
    for(int i=0;i<g_nRotCands;i++) if(g_rotCands[i].obj==obj && (off>g_rotCands[i].off?off-g_rotCands[i].off:g_rotCands[i].off-off)<24) return; // de-dup near hits
    RotCand& r=g_rotCands[g_nRotCands++]; r.obj=obj; r.off=off; strncpy(r.tag,tag,sizeof(r.tag)-1); r.tag[sizeof(r.tag)-1]=0;
}
// Copy up to cap bytes of [base..) into dst, stopping at the first unmapped 8-byte chunk. Returns bytes copied.
static uint32_t SnapRange(uintptr_t base, uint8_t* dst, uint32_t cap){
    if(!IsHeapObj(base)) return 0;
    uint32_t n=0; for(; n+8<=cap; n+=8){ if(!SafeReadable((void*)(base+n),8)) break; memcpy(dst+n,(void*)(base+n),8); } return n;
}
static void AddDiffObj(uintptr_t o,const char* tag){
    if(!IsHeapObj(o)||g_nDobj>=kMaxDiffObj) return;
    for(int i=0;i<g_nDobj;i++) if(g_dobj[i].obj==o) return;   // de-dup (SpectatorPawn/DefaultPawn may coincide)
    DiffObj& d=g_dobj[g_nDobj]; d.obj=o; d.snap=g_snapBuf[g_nDobj]; d.len=SnapRange(o,d.snap,kDiffLen);
    strncpy(d.tag,tag,sizeof(d.tag)-1); d.tag[sizeof(d.tag)-1]=0; g_nDobj++;
}
// Resolve the view-yaw source. Reflection primary (AController::ControlRotation) + a bounded rotator scan of the
// PC and PlayerCameraManager as discovery candidates. Sets g_viewYawObj/off + g_viewYawEnabled if the primary is
// found; always logs every candidate so a live mouse-rotate + the movement heartbeat pins the right offset.
static void ProbeViewYaw(){
    g_nRotCands=0;
    uintptr_t pc=FindInstClassSub("LokiPlayerController");
    uintptr_t cam=FindInstClassSub("CameraManager"); g_camMgr=cam;
    // reflection: known FRotator UPROPERTYs on the controller chain
    if(IsHeapObj(pc)){ uintptr_t cls=ClassOf(pc);
        const char* rp[]={"ControlRotation","BlendedTargetViewRotation","TargetViewRotation"};
        for(int i=0;i<3;i++){ uint32_t o=PropOffsetOnClass(cls,rp[i]); if(o==0xFFFFFFFF)continue;
            char t[24]; _snprintf_s(t,sizeof(t),_TRUNCATE,"PC.%s",rp[i]); AddRotCand(pc,o,t);
            double yw=SafeReadable((void*)(pc+o+8),8)?*(double*)(pc+o+8):0; Markerf("[yaw] refl PC->%s @0x%X yaw=%.1f\r\n",rp[i],o,yw); }
        // primary = ControlRotation if reflected (g_viewRotOff = yaw value = FRotator base + 8, double)
        uint32_t cro=PropOffsetOnClass(cls,"ControlRotation");
        if(cro!=0xFFFFFFFF){ g_viewYawObj=pc; g_viewRotOff=cro+8; g_viewYawEnabled=true; Markerf("[yaw] PRIMARY = PC->ControlRotation.Yaw @0x%X -> mouse steering ON\r\n",cro+8); }
        else Marker("[yaw] ControlRotation NOT reflected -> using memory-diff auto-lock (rotate the mouse to lock steering)\r\n");
    } else Marker("[yaw] no LokiPlayerController -> cannot resolve view yaw\r\n");
    // reference scan (bounded, one-time): rotator-shaped double-triples in the PC / camera manager, logged once.
    if(IsHeapObj(pc))  for(uint32_t o=0x28;o<0x1400 && g_nRotCands<12;o+=8) if(IsRotatorD(pc+o))  AddRotCand(pc,o,"PC.scan");
    if(IsHeapObj(cam)) for(uint32_t o=0x28;o<0x1400 && g_nRotCands<16;o+=8) if(IsRotatorD(cam+o)) AddRotCand(cam,o,"CAM.scan");
    char b[600]; int p=0;
    for(int i=0;i<g_nRotCands && p<540;i++){ RotCand& r=g_rotCands[i]; double yw=SafeReadable((void*)(r.obj+r.off+8),8)?*(double*)(r.obj+r.off+8):0;
        int w=_snprintf_s(b+p,sizeof(b)-p,_TRUNCATE,"%s@0x%X(y=%.1f) ",r.tag,r.off,yw); if(w<0)break; p+=w; }
    Markerf("[yaw] %d ref candidates: %s\r\n",g_nRotCands,b);
    // snapshot several candidate objects for the float+double diff auto-lock
    g_nDobj=0;
    AddDiffObj(pc,"PC");
    AddDiffObj(cam,"CAM");
    AddDiffObj(FindInstExactClass("SpectatorPawn"),"SPAWN");   // the spectator pawn ACTOR (its transform rotates)
    AddDiffObj(FindInstClassSub("DefaultPawn"),"DPAWN");
    AddDiffObj(FindInstClassSub("CameraComponent"),"CAMCOMP");
    AddDiffObj(FindInstClassSub("SpectatorPawnMovement"),"SPMOVE");
    for(int i=0;i<g_nDobj;i++) Markerf("[yawdiff] snap %s=0x%llX len=0x%X\r\n",g_dobj[i].tag,(unsigned long long)g_dobj[i].obj,g_dobj[i].len);
    // S78a: the view yaw is read via the GetCameraRotation GETTER, called on the game thread inside the per-frame
    // vtable hook (OnVtableTick). (An earlier CAM+0x14A0 "pin" was WRONG — that offset is a monotonic TIMER, not the
    // yaw; the getter is the ground truth.) Resolve the getter below.
    // S78a v3: resolve a rotation GETTER to call on the game thread (returns a clean FRotator regardless of storage).
    { void* fn=0; uintptr_t th=0,ch=0;
      struct Cand { uintptr_t ctx; const char* name; };
      Cand cands[]={ {cam,"GetCameraRotation"}, {pc,"GetControlRotation"}, {pc,"GetViewRotation"}, {g_spPawn,"GetViewRotation"} };
      for(int i=0;i<4 && !g_rotThunk;i++){ if(!IsHeapObj(cands[i].ctx))continue; fn=0;th=0;ch=0; ResolveFunc(ClassOf(cands[i].ctx),cands[i].name,&fn,&th,&ch);
          if(th){ g_rotFn=fn; g_rotThunk=th; g_rotChild=ch; g_rotCtx=cands[i].ctx; g_rotName=cands[i].name; } }
      if(g_rotThunk && g_rotChild){ uint32_t ro=ParamOffset(g_rotChild,"ReturnValue"); g_rotRetOff=(ro==0xFFFFFFFF)?0:ro; }
      Markerf("[yawcall] rot getter = %s thunk=0x%llX child=0x%llX retOff=0x%X ctx=0x%llX\r\n",g_rotName,(unsigned long long)g_rotThunk,(unsigned long long)g_rotChild,g_rotRetOff,(unsigned long long)g_rotCtx); }
    // K2_GetActorLocation on the view-target pawn -> seed the fly position from its WORLD location (world coords,
    // matching K2_SetActorLocation) so the vtable hook doesn't yank the view to origin.
    if(IsHeapObj(g_spPawn)){ ResolveFunc(ClassOf(g_spPawn),"K2_GetActorLocation",&g_glaFn,&g_glaThunk,&g_glaChild);
        if(g_glaChild){ uint32_t ro=ParamOffset(g_glaChild,"ReturnValue"); g_glaRetOff=(ro==0xFFFFFFFF)?0:ro; }
        Markerf("[yawcall] K2_GetActorLocation thunk=0x%llX child=0x%llX retOff=0x%X\r\n",(unsigned long long)g_glaThunk,(unsigned long long)g_glaChild,g_glaRetOff); }
}
// S78b (broadened): walk obj's class chain for FLOAT/DOUBLE props whose (lowercased) name has a rotation/camera
// CONTEXT word; log each with its live value. Register the strong RATE-like ones (sensitiv/speed/rate/scale/mult)
// for continuous reduction. Capped log to keep the marker readable.
static volatile long g_sensLogN=0;
static void EnumSensProps(uintptr_t obj,const char* tag){
    if(!IsHeapObj(obj)) return; uintptr_t cls=ClassOf(obj); int g=0;
    static const char* ctx[]={"sens","mouse","look","turn","yaw","pitch","rotat","spin","aim","spectat","freecam","camera"};
    static const char* rate[]={"sensitiv","speed","rate","scale","mult","boost"};   // +boost catches TurningBoost
    while(LooksLikePtr(cls)&&g++<28){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f)&&i++<4000){ char pn[96];
            if(GetFNameStr(NameId(f),pn,sizeof(pn))){ char low[96]; int L=0; for(;pn[L]&&L<95;L++) low[L]=(pn[L]>='A'&&pn[L]<='Z')?pn[L]+32:pn[L]; low[L]=0;
                bool hasCtx=false; for(int k=0;k<(int)(sizeof(ctx)/sizeof(ctx[0]));k++) if(strstr(low,ctx[k])){ hasCtx=true; break; }
                if(hasCtx){ uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                    if(off!=0xFFFFFFFF && off<0x4000 && SafeReadable((void*)(obj+off),8)){ float fv=*(float*)(obj+off); double dv=*(double*)(obj+off);
                        if(InterlockedIncrement(&g_sensLogN)<=80) Markerf("[SENS] %s.%s @0x%X f32=%.4f f64=%.4f\r\n",tag,pn,off,fv,dv);
                        bool hasRate=false; for(int k=0;k<(int)(sizeof(rate)/sizeof(rate[0]));k++) if(strstr(low,rate[k])){ hasRate=true; break; }
                        if(hasRate && g_nSens<12 && fv>0.00001f && fv<100000.0f){ g_sensObj[g_nSens]=obj; g_sensOff[g_nSens]=off; g_sensTarget[g_nSens]=fv*kSensMul; g_nSens++; } } }
            }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static void ProbeSensitivity(){
    g_nSens=0; g_sensLogN=0;
    EnumSensProps(FindInstClassSub("LokiPlayerController"),"PC");
    EnumSensProps(FindInstClassSub("LocalPlayer"),"LocalPlayer");
    EnumSensProps(FindInstClassSub("UserSettings"),"UserSettings");
    EnumSensProps(FindInstClassSub("CameraManager"),"CameraMgr");
    EnumSensProps(FindInstExactClass("SpectatorPawn"),"SpectatorPawn");
    Markerf("[SENS] %d rate fields registered for reduction (x%.3f)\r\n",g_nSens,kSensMul);
}
static void ApplySensReduction(){ for(int i=0;i<g_nSens;i++) if(SafeReadable((void*)(g_sensObj[i]+g_sensOff[i]),4)) *(float*)(g_sensObj[i]+g_sensOff[i])=g_sensTarget[i]; }
// Scan an object's snapshot vs live for 8-aligned doubles that SWUNG into a rotation-like range (the view yaw
// as the user rotates). Tracks each candidate's consecutive "moved-since-last-tick" count; the first to reach
// kLockMoves auto-locks as the steering source. Returns the best moves-count seen this pass.
static const int kLockMoves=3; static const double kLockSpan=25.0;   // deliberate L-R mouse swings span wide + fast
static const char* DiffTag(uintptr_t obj){ for(int i=0;i<g_nDobj;i++) if(g_dobj[i].obj==obj) return g_dobj[i].tag; return "?"; }
static const char* KindName(int k){ return k==YK_QUAT?"quat":(k==YK_FLOAT?"f32":"f64"); }
static double QuatYawDeg(uintptr_t p){   // FQuat {X@0,Y@8,Z@16,W@24} doubles -> yaw (deg)
    double X=*(double*)p, Y=*(double*)(p+8), Z=*(double*)(p+16), W=*(double*)(p+24);
    return atan2(2.0*(W*Z+X*Y), 1.0-2.0*(Y*Y+Z*Z)) * 180.0/3.14159265358979;
}
static YawTrack* FindTrack(uintptr_t obj,uint32_t off,int kind){ for(int i=0;i<g_nYt;i++) if(g_yt[i].obj==obj&&g_yt[i].off==off&&g_yt[i].kind==kind) return &g_yt[i]; if(g_nYt<64){ YawTrack& t=g_yt[g_nYt++]; t.obj=obj; t.off=off; t.kind=kind; t.last=1e9; t.lo=1e9; t.hi=-1e9; t.moves=0; return &t; } return nullptr; }
static void TrackVal(uintptr_t obj,uint32_t off,int kind,double v){ YawTrack* t=FindTrack(obj,off,kind); if(!t)return; if(v<t->lo)t->lo=v; if(v>t->hi)t->hi=v; if(t->last<1e8){ if(fabs(v-t->last)>1.0) t->moves++; else t->moves=0; } t->last=v; }
// Diff one object vs its snapshot for values that swung as the user rotates: a float (4-aligned) or double
// (8-aligned) FRotator-yaw in [-360,360], OR a changed unit QUATERNION (4 doubles in [-1,1], the likely storage
// here — the view rotation wasn't a plain FRotator in range). For a quat we track its EXTRACTED yaw so the lock
// selection (widest span, degrees) treats all three kinds uniformly.
static void ScanDiffObj(DiffObj& d){
    if(!IsHeapObj(d.obj)||d.len<0x28) return;
    for(uint32_t o=0x18; o+8<=d.len; o+=4){
        if((o&7)==0){
            double dn=*(double*)(d.obj+o), dold=*(double*)(d.snap+o);
            if(dn==dn && dn>=-360.0 && dn<=360.0 && fabs(dn-dold)>1.0) TrackVal(d.obj,o,YK_DOUBLE,dn);
            if(o+32<=d.len){ double Y=*(double*)(d.obj+o+8),Z=*(double*)(d.obj+o+16),W=*(double*)(d.obj+o+24);
                if(dn==dn&&Y==Y&&Z==Z&&W==W && fabs(dn)<=1.001&&fabs(Y)<=1.001&&fabs(Z)<=1.001&&fabs(W)<=1.001){
                    double ss=dn*dn+Y*Y+Z*Z+W*W;
                    if(ss>0.9 && ss<1.1){ double dq=fabs(dn-dold)+fabs(Y-*(double*)(d.snap+o+8))+fabs(Z-*(double*)(d.snap+o+16))+fabs(W-*(double*)(d.snap+o+24));
                        if(dq>0.02) TrackVal(d.obj,o,YK_QUAT,QuatYawDeg(d.obj+o)); } } }
        }
        float fn=*(float*)(d.obj+o), fold=*(float*)(d.snap+o);
        if(fn==fn && fn>=-360.0f && fn<=360.0f && fabs((double)fn-(double)fold)>1.0) TrackVal(d.obj,o,YK_FLOAT,(double)fn);
    }
}
// One discovery tick: rescan every candidate object, then auto-lock the WIDEST-swinging value (moves>=kLockMoves
// AND span>=kLockSpan) — deliberate horizontal mouse swings beat a slow-creeping clock/smoother. No-op once locked.
static void DiscoverYaw(){
    if(g_viewYawEnabled) return;
    for(int i=0;i<g_nDobj;i++) ScanDiffObj(g_dobj[i]);
    YawTrack* best=nullptr; double bestSpan=0;
    for(int i=0;i<g_nYt;i++){ double span=g_yt[i].hi-g_yt[i].lo; if(g_yt[i].moves>=kLockMoves && span>=kLockSpan && span>bestSpan){ best=&g_yt[i]; bestSpan=span; } }
    if(best){ g_viewYawObj=best->obj; g_viewRotOff=best->off; g_viewYawKind=best->kind; g_viewYawEnabled=true; g_manualYawOff=0.0;
        Markerf("[yawlock] LOCKED view yaw = %s+0x%X (%s moves=%d span=%.0f val=%.1f) -> MOUSE STEERING ON\r\n",DiffTag(best->obj),best->off,KindName(best->kind),best->moves,bestSpan,best->last); }
}
static bool ReadViewYaw(double* out){
    if(g_viewYawValid){ *out=g_viewYawLive; return true; }
    if(!g_viewYawEnabled||!IsHeapObj(g_viewYawObj)||g_viewRotOff==0xFFFFFFFF) return false;
    if(g_viewYawKind==YK_QUAT){ if(!SafeReadable((void*)(g_viewYawObj+g_viewRotOff),32))return false; double y=QuatYawDeg(g_viewYawObj+g_viewRotOff); if(!(y==y))return false; *out=y; return true; }
    if(g_viewYawKind==YK_FLOAT){ if(!SafeReadable((void*)(g_viewYawObj+g_viewRotOff),4))return false; float v=*(float*)(g_viewYawObj+g_viewRotOff); if(!(v==v))return false; *out=v; return true; }
    if(!SafeReadable((void*)(g_viewYawObj+g_viewRotOff),8)) return false;
    double v=*(double*)(g_viewYawObj+g_viewRotOff); if(!(v==v)) return false; *out=v; return true;
}

// S78 refinement #4: widget-spawn robustness. Instead of a fixed 12s pre-census sleep (a too-early inject got
// 87 widgets and hid 0/3 => overlay stayed up), poll the UserWidget count until it's high/stable. Off-thread.
static int CountUserWidgets(){ int n=0; ForEachObject([&](uintptr_t o)->bool{ uintptr_t c=ClassOf(o); if(!LooksLikePtr(c))return false; if(!SuperChainHas(c,"UserWidget"))return false; char on[96]; if(ObjName(o,on,sizeof(on))&&strncmp(on,"Default__",9)==0)return false; n++; return false; }); return n; }
static int WaitForWidgets(int target,int minMs,int maxMs){
    Sleep(minMs);                                       // widgets need SOME time regardless of inject timing
    DWORD t0=GetTickCount(); int last=-1,stable=0;
    for(;;){ int n=CountUserWidgets();
        if(n>=target){ Markerf("[1b] widgets=%d >= %d after %ums+min -> proceed\r\n",n,target,(unsigned)(GetTickCount()-t0)); return n; }
        if(n==last && n>800){ if(++stable>=3){ Markerf("[1b] widgets=%d stable after %ums+min -> proceed\r\n",n,(unsigned)(GetTickCount()-t0)); return n; } } else stable=0;
        last=n; if(GetTickCount()-t0>=(DWORD)maxMs){ Markerf("[1b] widget wait cap hit, widgets=%d\r\n",n); return n; }
        Sleep(1500); }
}

// ---- Route D (MODE_DEBUGCAM): UE's built-in free-fly debug camera ----
// UCheatManager::EnableDebugCamera spawns an ADebugCameraController that DETACHES from the PlayerController and
// takes over the view with its OWN native free-fly input (WASD/mouse) — bypassing the deploy-gated PC camera +
// the dormant spectator movement. The open question is whether a UCheatManager exists in this shipping build.
static uintptr_t g_dbgCM=0, g_dbgPC=0; static void* g_edcFn=0; static uintptr_t g_edcThunk=0, g_edcChild=0;
static void ResolveDebugCam(){
    uintptr_t pc=FindInstClassSub("LokiPlayerController"); g_dbgPC=pc;
    uintptr_t cm=0; const char* src="none"; uint32_t ccOff=0xFFFFFFFF;
    if(pc){ ccOff=PropOffsetOnClass(ClassOf(pc),"CheatManager"); if(ccOff!=0xFFFFFFFF && SafeReadable((void*)(pc+ccOff),8)){ uintptr_t v=*(uintptr_t*)(pc+ccOff); if(IsHeapObj(v)){ cm=v; src="PC->CheatManager"; } } }
    if(!cm){ ForEachObject([&](uintptr_t o)->bool{ char cn[96]; if(!ClassName(o,cn,sizeof(cn)))return false; if(strcmp(cn,"CheatManager")!=0)return false; char on[96]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false; if(!IsHeapObj(o))return false; cm=o; return true; }); if(cm) src="live UCheatManager instance"; }
    g_dbgCM=cm;
    uintptr_t cmCls = cm?ClassOf(cm):0; if(!cmCls){ uintptr_t cdo=FindObjExact("Default__CheatManager"); if(cdo) cmCls=ClassOf(cdo); }
    if(cmCls) ResolveFunc(cmCls,"EnableDebugCamera",&g_edcFn,&g_edcThunk,&g_edcChild);
    Markerf("[DBG] pc=0x%llX cheatMgrOff=0x%X cheatMgr=0x%llX (%s) enableDbgThunk=0x%llX\r\n",
        (unsigned long long)pc,ccOff,(unsigned long long)cm,src,(unsigned long long)g_edcThunk);
}
static void DoDebugCam(){
    long h=InterlockedIncrement(&g_scHits);
    // keep the "DROP IN... LOADING" overlay hidden so the debug-camera view is visible (widgets from ResolveSpectatorCam)
    if(g_svThunk && g_svVisOff!=0xFFFFFFFF){
        for(int i=0;i<g_nLoadW;i++){ uintptr_t w=g_loadWidgets[i]; if(!SafeReadable((void*)w,0x30))continue; uintptr_t wc=ClassOf(w); if(!LooksLikePtr(wc)||!SuperChainHas(wc,"UserWidget"))continue;
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint8_t*)(g_pbuf+g_svVisOff)=1; CallGuarded(g_svFn,g_svThunk,g_svChild,(void*)w,g_pbuf,g_rbuf); }
    }
    static bool called=false;
    if(!called){ called=true;
        if(!IsHeapObj(g_dbgCM) || !g_edcThunk){ Marker("[DBG] no usable UCheatManager -> cannot EnableDebugCamera (shipping likely nulls it). Pivot to spawn+SetViewTarget.\r\n"); return; }
        Marker("[DBG] >>> EnableDebugCamera(cheatMgr)\r\n");
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        bool f=CallGuarded(g_edcFn,g_edcThunk,g_edcChild,(void*)g_dbgCM,g_pbuf,g_rbuf);
        Markerf("[DBG] <<< EnableDebugCamera returned%s — check screen for the free-fly debug camera (native WASD/mouse look).\r\n",f?" [FAULTED]":"");
    }
}

// ---- Route D (MODE_FREECAM): spawn a plain ACameraActor + retarget the PC's view to it, then puppet its
// position. Owns all its pieces (my camera, BP-callable SetViewTargetWithBlend + K2_SetActorLocation) — bypasses
// the CheatManager, the deploy-gated PC camera, and the dormant spectator movement. Open Q: does re-targeting the
// view to a NON-hero camera dodge the AttachAudioListenerToHero move-crash? Reuses the DoSpawnHero spawn globals.
static uintptr_t g_fcPC=0, g_fcCamCls=0, g_fcCam=0;
static void* g_svtbFn=0; static uintptr_t g_svtbThunk=0, g_svtbChild=0; static uint32_t g_oSvtbTgt=0, g_oSvtbBlend=8;
static void* g_slaFn=0; static uintptr_t g_slaThunk=0, g_slaChild=0; static uint32_t g_oSlaLoc=0, g_oSlaTele=0x19;
static double g_fcX=55, g_fcY=79, g_fcZ=500, g_fcYaw=0; static bool g_fcSpawned=false;
static void ResolveFreeCam(){
    ResolveSpectatorCam();   // populate overlay-hide widgets (+ harmless spectator census)
    g_fcPC=FindInstClassSub("LokiPlayerController");
    g_worldCtx=FindInstClassSub("ProgressionManager"); if(!g_worldCtx) g_worldCtx=FindInstExactClass("LokiGameState");
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    uintptr_t camCDO=FindObjExact("Default__CameraActor"); g_fcCamCls=camCDO?ClassOf(camCDO):0;
    if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
        ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
        ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
        if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
        if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    }
    { uintptr_t pcCls=g_fcPC?ClassOf(g_fcPC):0;
      if(pcCls) ResolveFunc(pcCls,"SetViewTargetWithBlend",&g_svtbFn,&g_svtbThunk,&g_svtbChild);
      if(!g_svtbThunk){ uintptr_t pccdo=FindObjExact("Default__PlayerController"); if(pccdo) ResolveFunc(ClassOf(pccdo),"SetViewTargetWithBlend",&g_svtbFn,&g_svtbThunk,&g_svtbChild); }   // confirmed to live on PlayerController
      if(g_svtbChild){ g_oSvtbTgt=g_offParam(g_svtbChild,"NewViewTarget",0); g_oSvtbBlend=g_offParam(g_svtbChild,"BlendTime",8); } }
    if(g_fcCamCls){ ResolveFunc(g_fcCamCls,"K2_SetActorLocation",&g_slaFn,&g_slaThunk,&g_slaChild);
        if(g_slaChild){ g_oSlaLoc=g_offParam(g_slaChild,"NewLocation",0); g_oSlaTele=g_offParam(g_slaChild,"bTeleport",0x19); } }
    g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
    Markerf("[FC] pc=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX svtbThunk=0x%llX(tgt@0x%X) slaThunk=0x%llX(loc@0x%X)\r\n",
        (unsigned long long)g_fcPC,(unsigned long long)g_fcCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_svtbThunk,g_oSvtbTgt,(unsigned long long)g_slaThunk,g_oSlaLoc);
}
static void DoFreeCam(){
    long h=InterlockedIncrement(&g_scHits);
    if(g_svThunk && g_svVisOff!=0xFFFFFFFF){ for(int i=0;i<g_nLoadW;i++){ uintptr_t w=g_loadWidgets[i]; if(!SafeReadable((void*)w,0x30))continue; uintptr_t wc=ClassOf(w); if(!LooksLikePtr(wc)||!SuperChainHas(wc,"UserWidget"))continue; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint8_t*)(g_pbuf+g_svVisOff)=1; CallGuarded(g_svFn,g_svThunk,g_svChild,(void*)w,g_pbuf,g_rbuf); } }
    if(!g_fcSpawned){ g_fcSpawned=true;
        if(!g_beginThunk||!g_finishThunk||!IsHeapObj(g_fcCamCls)||!IsHeapObj(g_worldCtx)||!IsHeapObj(g_gsCDO)){ Markerf("[FC] resolve incomplete begin=0x%llX finish=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX -> abort\r\n",(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_fcCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO); return; }
        static uint8_t xf[0x60]={0}; *(double*)(xf+0x18)=1.0; *(double*)(xf+0x20)=g_fcX; *(double*)(xf+0x28)=g_fcY; *(double*)(xf+0x30)=g_fcZ; *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_worldCtx; *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)g_fcCamCls; memcpy(g_pbuf+g_oBXform,xf,0x50); g_pbuf[g_oBColl]=2;
        Marker("[FC] >>> spawn CameraActor\r\n");
        if(CallGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[FC] BeginDeferred FAULTED\r\n"); return; }
        uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
        if(!IsHeapObj(deferred)){ Marker("[FC] spawn returned null\r\n"); return; }
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
        if(CallGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[FC] FinishSpawning FAULTED\r\n"); return; }
        uintptr_t cam=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(cam)) cam=*(uint64_t*)(g_pbuf+g_oFRet); if(!IsHeapObj(cam)) cam=deferred; g_fcCam=cam;
        Markerf("[FC] camera spawned 0x%llX -> SetViewTargetWithBlend\r\n",(unsigned long long)cam);
        if(g_svtbThunk && IsHeapObj(g_fcPC)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_oSvtbTgt)=(uint64_t)cam; *(float*)(g_pbuf+g_oSvtbBlend)=0.0f; bool f=CallGuarded(g_svtbFn,g_svtbThunk,g_svtbChild,(void*)g_fcPC,g_pbuf,g_rbuf); Markerf("[FC] SetViewTargetWithBlend returned%s — view should render from the spawned camera now.\r\n",f?" [FAULTED]":""); }
        return;
    }
    if(IsHeapObj(g_fcCam) && g_slaThunk){
        bool focused=(!g_hwnd)||(GetForegroundWindow()==g_hwnd);
        if(focused){
            if(GetAsyncKeyState(VK_LEFT)&0x8000) g_fcYaw-=2.5; if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_fcYaw+=2.5;
            double yr=g_fcYaw*3.14159265358979/180.0, c=cos(yr), s=sin(yr), sp=45.0, dx=0,dy=0,dz=0;
            if(GetAsyncKeyState('W')&0x8000){ dx+=c; dy+=s; } if(GetAsyncKeyState('S')&0x8000){ dx-=c; dy-=s; }
            if(GetAsyncKeyState('D')&0x8000){ dx-=s; dy+=c; } if(GetAsyncKeyState('A')&0x8000){ dx+=s; dy-=c; }
            if(GetAsyncKeyState(VK_SPACE)&0x8000) dz+=1; if(GetAsyncKeyState(VK_CONTROL)&0x8000) dz-=1;
            if(dx||dy||dz){ g_fcX+=dx*sp; g_fcY+=dy*sp; g_fcZ+=dz*sp;
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); double* L=(double*)(g_pbuf+g_oSlaLoc); L[0]=g_fcX;L[1]=g_fcY;L[2]=g_fcZ; g_pbuf[g_oSlaTele]=1;
                CallGuarded(g_slaFn,g_slaThunk,g_slaChild,(void*)g_fcCam,g_pbuf,g_rbuf); }
        }
    }
    if(h==1||h%100==0) Markerf("[FC] hit %ld cam=0x%llX pos=(%.0f,%.0f,%.0f)\r\n",h,(unsigned long long)g_fcCam,g_fcX,g_fcY,g_fcZ);
}

extern "C" void OnPI(void* /*ctx*/, void* frame, void* /*res*/){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));   // capture a live FFrame template (primitive prerequisite)
    long h=InterlockedIncrement(&g_hitsGT);
    if(kMode==MODE_SPECTATOR_CAM){ if(g_moveArmed && !g_moveDone){ DoStepMove(); g_inHook=0; return; } if(h==1) Marker("[HOOK] fired (spectator-cam) — transient overlay-hide\r\n"); DoSpectatorCam(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_DEBUGCAM){ if(h==1) Marker("[HOOK] fired (debug-cam) — hiding overlay + enabling debug camera\r\n"); DoDebugCam(); g_inHook=0; return; }
    if(kMode==MODE_FREECAM){ if(h==1) Marker("[HOOK] fired (free-cam) — spawn camera + retarget view + puppet\r\n"); DoFreeCam(); g_inHook=0; return; }
    Markerf("[HOOK] fired on game thread (hitsGT=%ld) — primitive template captured.\r\n",h);
    if(kMode==MODE_POSSESS_DP) DoPossessDP();
    else if(kMode==MODE_SPAWN_HERO) DoSpawnHero();
    else Census();
    g_done=1; g_inHook=0;
}

static DWORD WINAPI Worker(LPVOID){
    // fresh marker
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    Markerf("[0] ds_hybrid attached. base=0x%llX mode=%d\r\n",(unsigned long long)g_modBase,kMode);
    { HANDLE rt=CreateThread(nullptr,0,RawInputThread,nullptr,0,nullptr); if(rt)CloseHandle(rt); }   // S78c: raw mouse capture
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    Markerf("[1] gameTid=%lu\r\n",g_gameTid);
    // S78 #4: wait for the UMG widgets (incl. the WBP_UI_MatchTransition overlay) to spawn before censusing — a
    // too-early census gets few widgets and misses the overlay (hid 0/3). Poll the count until high/stable
    // (min 6s floor, cap 30s) instead of the old fixed 12s sleep, so inject timing is self-correcting.
    if(kMode==MODE_SPECTATOR_CAM||kMode==MODE_DEBUGCAM||kMode==MODE_FREECAM){ Marker("[1b] polling until UMG widgets have spawned...\r\n"); WaitForWidgets(1500,6000,30000); }
    // Resolve targets OFF the game thread (read-only object walk) so the hook does minimal game-thread work.
    if(kMode==MODE_POSSESS_DP){ if(!ResolvePossessDP()){ Marker("[1] possess resolve failed — aborting\r\n"); return 7; } }
    if(kMode==MODE_SPAWN_HERO){ if(!ResolveSpawnHero()){ Marker("[1] spawn-hero resolve failed — aborting\r\n"); return 8; } }
    if(kMode==MODE_SPECTATOR_CAM){ ResolveSpectatorCam(); ProbeCamera(); ProbeViewYaw(); ProbeSensitivity(); if(kTakeoverCam) ResolveTakeover(); }
    if(kMode==MODE_DEBUGCAM){ ResolveSpectatorCam(); ResolveDebugCam(); }   // spectator resolve populates the overlay-hide widgets
    if(kMode==MODE_FREECAM){ ResolveFreeCam(); }
    g_pi=(uint8_t*)(g_modBase+kPiRva);
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 3;}
    if(kMode==MODE_SPECTATOR_CAM){
        // S78c: TRANSIENT overlay-hide (no standing .text hook — the anti-tamper reliably catches a standing hook,
        // even at 8s; it crashed 3x). Cycle install → one DoSpectatorCam (hides the loading widgets + captures the
        // FFrame template for the primitive) → uninstall, for ~kSpectatorHookMs. Same µs-exposure dodge as movement.
        Marker("[2] transient overlay-hide starting...\r\n");
        DWORD ohT0=GetTickCount();
        while(GetTickCount()-ohT0 < kSpectatorHookMs){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+50; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] overlay-hide done (transient, hitsGT=%ld) — no standing .text hook was ever held.\r\n",(long)g_hitsGT);
    } else {
        if(!InstallHook()){Marker("[2] FAIL InstallHook\r\n");return 4;}
        Marker("[2] hook installed — waiting for a game-thread ProcessInternal...\r\n");
        int waitIters=((kMode==MODE_DEBUGCAM||kMode==MODE_FREECAM)?18000:600);
        for(int i=0;i<waitIters && !g_done;i++) Sleep(20);
        UninstallHook();
        Markerf("[3] hook UNINSTALLED (hitsGT=%ld).\r\n",(long)g_hitsGT);
    }
    // S77 phase-3: CONTINUOUS movement via TRANSIENT-PER-STEP (no standing .text hook — the proven dodge). Poll
    // WASD OFF-THREAD; per step, install the hook -> OnPI does ONE K2_SetActorLocation to the updated pos ->
    // uninstall. The .text patch exists only ~microseconds per step, so the integrity check almost never sees it.
    if(kMode==MODE_SPECTATOR_CAM){
        g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
        // S78 #2: try the DURABLE per-frame VTABLE hook first (removes the ProcessInternal dependency that stalled
        // movement). Sweep the CameraManager's vtable for the per-frame slot, then swap in our stub (heap-only, no
        // .text). If it doesn't take, fall back to the transient-per-step loop.
        bool vtActive=false; uintptr_t vtCam=FindInstClassSub("CameraManager");
        if(IsHeapObj(vtCam)){ int slot=FindPerFrameSlot(vtCam); if(slot>=0) vtActive=InstallVtableMove(vtCam,slot); }
        Markerf("[move] movement loop LIVE via %s (WASD fly; %s; Space/Ctrl up/down; Shift=boost)\r\n",
                vtActive?"VTABLE per-frame hook":"transient-per-step",
                g_viewYawEnabled?"MOUSE steers (arrows nudge)":"arrows steer");
        DWORD t0=GetTickCount(); DWORD lastHb=0, lastDisc=0; long steps=0; int anyKey=0; long instFail=0;
        while(GetTickCount()-t0 < 3600000){   // ~60 min (was 15) so the fly-cam doesn't expire mid-session
            // No focus gate: GetAsyncKeyState reads global hardware key state (works regardless of foreground).
            // Read keys FIRST + unconditionally (so keysSeen reflects detection even before the world-loc seed).
            bool wDn=(GetAsyncKeyState('W')&0x8000)!=0, sDn=(GetAsyncKeyState('S')&0x8000)!=0,
                 aDn=(GetAsyncKeyState('A')&0x8000)!=0, dDn=(GetAsyncKeyState('D')&0x8000)!=0,
                 upDn=(GetAsyncKeyState(VK_SPACE)&0x8000)!=0, dnDn=(GetAsyncKeyState(VK_CONTROL)&0x8000)!=0;
            bool anyDn = wDn||sDn||aDn||dDn||upDn||dnDn; if(anyDn) anyKey++;
            ApplySensReduction();   // S78b: keep mouse-look sensitivity clamped down (re-write each iteration)
            if(GetAsyncKeyState(VK_LEFT)&0x8000)  g_manualYawOff-=3.0;   // arrows nudge on top of the mouse yaw
            if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_manualYawOff+=3.0;
            double vy; double heading = kTakeoverCam ? (g_camYaw + g_manualYawOff)   // take-over: my own controlled yaw
                                                      : ((ReadViewYaw(&vy) ? vy : 0.0) + g_manualYawOff);   // native view yaw
            g_spYaw2 = heading;
            double yr=heading*3.14159265358979/180.0, c=cos(yr), s=sin(yr), dx=0,dy=0,dz=0;
            if(wDn){ dx+=c; dy+=s; }  if(sDn){ dx-=c; dy-=s; }
            if(dDn){ dx-=s; dy+=c; }  if(aDn){ dx+=s; dy-=c; }
            if(upDn) dz+=1; if(dnDn) dz-=1;
            double sp=kMoveSpeed, spV=kMoveSpeedV;
            if(GetAsyncKeyState(VK_SHIFT)&0x8000){ sp*=kBoostMul; spV*=kBoostMul; }   // S78 #3: Shift boost
            // diff auto-lock (quat/FRotator) only if the getter didn't resolve (the getter is the yaw ground truth)
            if(!g_rotThunk && !g_viewYawEnabled && GetTickCount()-lastDisc>=1000){ DiscoverYaw(); lastDisc=GetTickCount(); }
            bool canMove = !vtActive || g_spSeededVt;   // vtable path: wait for the world-loc seed before flying
            if((dx||dy||dz) && canMove){
                g_spX+=dx*sp; g_spY+=dy*sp; g_spZ+=dz*spV;
                if(g_spZ>kZMax) g_spZ=kZMax; if(g_spZ<kZMin) g_spZ=kZMin;
                if(vtActive){ g_moveDirty=1; Sleep(6); }   // per-frame vtable hook applies the pending pos
                else {
                    g_moveDone=0; g_moveArmed=1; g_done=0; g_inHook=0;
                    bool inst=false; for(int r=0;r<4 && !inst;r++){ if(InstallHookFast()){ inst=true; DWORD md=GetTickCount()+60; while(!g_moveDone && GetTickCount()<md) Sleep(0); UninstallHookFast(); steps++; } }
                    if(!inst) instFail++;
                    Sleep(6);
                }
            } else Sleep(anyDn?6:20);
            if(GetTickCount()-lastHb>=5000){
                double vy2=0; bool haveVy=ReadViewYaw(&vy2);
                Markerf("[move] alive via=%s fired=%ld vtTicks=%ld seeded=%ld keysSeen=%d W=%d pos=(%.0f,%.0f,%.0f) yaw=%.0f viewYaw=%s%.0f foc=%d\r\n",
                    vtActive?"vt":"tr",(long)g_fired,(long)g_vtTicks,(long)g_spSeededVt,anyKey,wDn?1:0,g_spX,g_spY,g_spZ,g_spYaw2,haveVy?"":"(unlocked)",vy2,IsGameFocused()?1:0);
                // S78c stage 1: raw mouse capture + POV-rotation discovery. Log accumulated mouse delta (then reset)
                // + the CameraManager CameraCachePrivate doubles (0x14A8..0x14E0) so a live rotate reveals which
                // offset is the POV yaw (it swings). The POV rotation is what we'll override with a slow value.
                long mdx=InterlockedExchange(&g_mouseDX,0), mdy=InterlockedExchange(&g_mouseDY,0), mev=InterlockedExchange(&g_mouseEvents,0);
                Markerf("[raw] events=%ld dx=%ld dy=%ld\r\n",mev,mdx,mdy);
                if(IsHeapObj(g_camMgr) && SafeReadable((void*)(g_camMgr+0x420),8)){ uintptr_t vt=*(uintptr_t*)(g_camMgr+0x420);
                    char vcn[64]="?"; if(IsHeapObj(vt))ClassName(vt,vcn,sizeof(vcn));
                    Markerf("[TO] viewTarget@cam+0x420=0x%llX (%s) myCam=0x%llX %s\r\n",(unsigned long long)vt,vcn,(unsigned long long)g_myCam,(vt==g_myCam)?"<< MINE":"(reverted)"); }
                anyKey=0; lastHb=GetTickCount();
            }
        }
        RestoreVtable();   // put the CameraManager's original vtable pointer back before the worker exits
    }
    Markerf("[3b] done (hitsGT=%ld done=%ld).\r\n",(long)g_hitsGT,(long)g_done);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
