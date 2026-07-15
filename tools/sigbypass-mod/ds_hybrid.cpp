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
static const unsigned kSpectatorHookMs   = 20000;   // ~20s overlay-hide window (proven to survive + stick), then uninstall

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
static void DoStepMove(){
    g_done=1;   // exactly one fire per transient window
    if(!IsHeapObj(g_spPawn)||!g_spSlaThunk||g_spSlaLoc==0xFFFFFFFF){ g_moveDone=1; return; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
    if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
    CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf);
    g_moveDone=1;
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
    if(kMode==MODE_SPECTATOR_CAM){ if(g_moveArmed && !g_moveDone){ DoStepMove(); g_inHook=0; return; } if(h==1) Marker("[HOOK] fired (spectator-cam) — holding loading overlay hidden\r\n"); DoSpectatorCam(); g_inHook=0; return; }
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
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    Markerf("[1] gameTid=%lu\r\n",g_gameTid);
    // S77: wait for the UMG widgets (incl. the WBP_UI_MatchTransition overlay) to fully spawn before censusing —
    // a too-early census gets few widgets and misses the overlay (hid 0/3). ~12s covers a cached fast boot.
    if(kMode==MODE_SPECTATOR_CAM||kMode==MODE_DEBUGCAM||kMode==MODE_FREECAM){ Marker("[1b] waiting 12s for UMG widgets to spawn...\r\n"); Sleep(12000); }
    // Resolve targets OFF the game thread (read-only object walk) so the hook does minimal game-thread work.
    if(kMode==MODE_POSSESS_DP){ if(!ResolvePossessDP()){ Marker("[1] possess resolve failed — aborting\r\n"); return 7; } }
    if(kMode==MODE_SPAWN_HERO){ if(!ResolveSpawnHero()){ Marker("[1] spawn-hero resolve failed — aborting\r\n"); return 8; } }
    if(kMode==MODE_SPECTATOR_CAM){ ResolveSpectatorCam(); }
    if(kMode==MODE_DEBUGCAM){ ResolveSpectatorCam(); ResolveDebugCam(); }   // spectator resolve populates the overlay-hide widgets
    if(kMode==MODE_FREECAM){ ResolveFreeCam(); }
    g_pi=(uint8_t*)(g_modBase+kPiRva);
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 3;}
    if(!InstallHook()){Marker("[2] FAIL InstallHook\r\n");return 4;}
    Marker("[2] hook installed — waiting for a game-thread ProcessInternal...\r\n");
    // S77 dodge: SPECTATOR_CAM holds the hook only ~kSpectatorHookMs (overlay-hide window) then UNINSTALLS it, so
    // no persistent .text mod remains for the code-integrity check to catch (the catalog_store_fix one-shot pattern).
    int waitIters=(kMode==MODE_SPECTATOR_CAM)?(int)(kSpectatorHookMs/20):((kMode==MODE_DEBUGCAM||kMode==MODE_FREECAM)?18000:600);
    for(int i=0;i<waitIters && !g_done;i++) Sleep(20);
    UninstallHook();
    Markerf("[3] hook UNINSTALLED after ~%ums (hitsGT=%ld) — no persistent .text mod now; observing survival.\r\n",kSpectatorHookMs,(long)g_hitsGT);
    // S77 phase-3: CONTINUOUS movement via TRANSIENT-PER-STEP (no standing .text hook — the proven dodge). Poll
    // WASD OFF-THREAD; per step, install the hook -> OnPI does ONE K2_SetActorLocation to the updated pos ->
    // uninstall. The .text patch exists only ~microseconds per step, so the integrity check almost never sees it.
    if(kMode==MODE_SPECTATOR_CAM){
        g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
        Marker("[move] transient-per-step movement loop LIVE (WASD fly; arrows steer; Space/Ctrl up/down)\r\n");
        DWORD t0=GetTickCount(); DWORD lastHb=0; long steps=0; int anyKey=0;
        while(GetTickCount()-t0 < 900000){
            double dx=0,dy=0,dz=0;
            // No focus gate: GetAsyncKeyState reads global hardware key state (works regardless of foreground).
            if(GetAsyncKeyState(VK_LEFT)&0x8000)  g_spYaw2-=3.0;
            if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_spYaw2+=3.0;
            double yr=g_spYaw2*3.14159265358979/180.0, c=cos(yr), s=sin(yr);
            if(GetAsyncKeyState('W')&0x8000){ dx+=c; dy+=s; }
            if(GetAsyncKeyState('S')&0x8000){ dx-=c; dy-=s; }
            if(GetAsyncKeyState('D')&0x8000){ dx-=s; dy+=c; }
            if(GetAsyncKeyState('A')&0x8000){ dx+=s; dy-=c; }
            if(GetAsyncKeyState(VK_SPACE)&0x8000)   dz+=1;
            if(GetAsyncKeyState(VK_CONTROL)&0x8000) dz-=1;
            if(dx||dy||dz){
                anyKey++;
                const double sp=400.0; g_spX+=dx*sp; g_spY+=dy*sp; g_spZ+=dz*sp;
                g_moveDone=0; g_moveArmed=1; g_done=0; g_inHook=0;
                if(InstallHook()){ DWORD md=GetTickCount()+400; while(!g_moveDone && GetTickCount()<md) Sleep(1); UninstallHook(); steps++; }
                Sleep(12);
            } else Sleep(20);
            if(GetTickCount()-lastHb>=5000){ Markerf("[move] alive steps=%ld keysSeen=%d pos=(%.0f,%.0f,%.0f) yaw=%.0f foc=%d\r\n",steps,anyKey,g_spX,g_spY,g_spZ,g_spYaw2,IsGameFocused()?1:0); anyKey=0; lastHb=GetTickCount(); }
        }
    }
    Markerf("[3b] done (hitsGT=%ld done=%ld).\r\n",(long)g_hitsGT,(long)g_done);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
