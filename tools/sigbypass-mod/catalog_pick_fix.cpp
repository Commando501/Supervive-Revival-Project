// catalog_pick_fix — SESSION 51: self-deriving IsPreviewable/IsUseable Script-bytecode patcher.
//
// PROBLEM: the store fix marks every hunter OWNED, so an owned-hunter click routes into the
// native TryPickMyHeroAndCosmetics path (needs a party-service round-trip our stub can't do)
// instead of the PREVIEW path — so the selection never commits (blue focus, never purple) and
// the center never updates. Session 50's WORKING pick config forced the tile's IsPreviewable=true
// and IsUseable=false via Script-bytecode patches, routing owned clicks into the preview path;
// mainmenu_refresh_pi8.dll then mirrors + refreshes the pick. Those patches were applied by hand
// with script_patch.py against per-launch UFunc addresses. This shim SELF-DERIVES the tile UFuncs
// at runtime and applies the patches — no manual per-launch step — so it can auto-inject at launch.
//
// The patches (Script bytecode, heap — no .text integrity wall; from the session-50 offline dump):
//   IsPreviewable tile UFunc: pokebyte Script[257] 0x28(EX_False)->0x27(EX_True) + jump0 247
//                             (Script[0..4] = 06 F7 00 00 00 = EX_Jump 247)  => returns TRUE
//   IsUseable     tile UFunc: jump0 109  (Script[0..4] = 06 6D 00 00 00 = EX_Jump 109) => FALSE
// Bytecode is baked in the asset (SAME across launches for this build); only the heap UFunc
// ADDRESSES differ per launch, which is what we self-derive. UFunction.Script.Data @ UFunc+0x68,
// Num @ +0x70 (confirmed in mainmenu_refresh_pi8.cpp: InvokeBP reads Code=Script.Data @ +0x68).
//
// Identify the tile UFunc among all "IsPreviewable" functions by CONTENT signature: Script Num>257
// AND Script[257]==0x28. Its Outer (owning UClass) also holds the matching "IsUseable". There may be
// two HeroPickerSelectable tile classes — patch every matching pair.
//
// Build:  clang++ -shared -O2 catalog_pick_fix.cpp -o catalog_pick_fix.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/catalog_pick_fix.dll  (or watch-now at launch)
// Marker: docs/catalog-pick-fix-marker.txt   Crash: docs/catalog-pick-fix-crash.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\catalog-pick-fix-marker.txt";
static const char* kCrashPath  = "G:\\git\\Supervive Revival Project\\docs\\catalog-pick-fix-crash.txt";

constexpr uintptr_t kObjObjectsRva = 0x9E38930;   // GUObjectArray.ObjObjects (FChunkedFixedUObjectArray)
constexpr uintptr_t kNamePoolRva   = 0x9D81450;   // FNamePool
constexpr int       PERCHUNK       = 65536;
constexpr int       ITEMSTRIDE     = 0x18;
constexpr uintptr_t NUMELEM_OFF    = 0x14;         // NumElements(int32) @ ObjObjects+0x14
constexpr uintptr_t CLASS_OFF      = 0x18;
constexpr uintptr_t NAME_OFF       = 0x20;
constexpr uintptr_t OUTER_OFF      = 0x28;
constexpr uintptr_t SCRIPT_DATA    = 0x68;         // UFunction.Script.Data
constexpr uintptr_t SCRIPT_NUM     = 0x70;         // UFunction.Script.Num
// Patch constants (session-50 offline dump for this build).
constexpr int   PREV_POKE_OFF  = 257;  constexpr uint8_t PREV_POKE_FROM=0x28, PREV_POKE_TO=0x27;
constexpr int   PREV_JMP_TGT   = 247;
constexpr int   USE_JMP_TGT    = 109;

static uintptr_t g_modBase = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool Writable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;DWORD w=PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY;if(!(m.Protect&w))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
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
static uintptr_t OuterOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+OUTER_OFF),8))return 0; return *(uintptr_t*)(obj+OUTER_OFF); }
static bool NameIs(uintptr_t obj,const char* w){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static uintptr_t ObjAt(uint32_t idx){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,8))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; if(!LooksLikePtr(objectsPtr))return 0;
    if(!SafeReadable((void*)(objectsPtr+(idx/PERCHUNK)*8),8))return 0;
    uintptr_t chunk=*(uintptr_t*)(objectsPtr+(idx/PERCHUNK)*8); if(!LooksLikePtr(chunk))return 0;
    uintptr_t item=chunk+(uintptr_t)(idx%PERCHUNK)*ITEMSTRIDE; if(!SafeReadable((void*)item,8))return 0;
    return *(uintptr_t*)item;
}
static int NumElements(){ uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)(oo+NUMELEM_OFF),4))return 0; int n=*(int*)(oo+NUMELEM_OFF); return (n>0&&n<8000000)?n:0; }

// Read a UFunction's Script {Data,Num}; return false if it doesn't look like bytecode.
static bool ScriptOf(uintptr_t ufunc,uintptr_t& dataOut,uint32_t& numOut){
    if(!SafeReadable((void*)(ufunc+SCRIPT_DATA),8)||!SafeReadable((void*)(ufunc+SCRIPT_NUM),4))return false;
    uintptr_t d=*(uintptr_t*)(ufunc+SCRIPT_DATA); uint32_t n=*(uint32_t*)(ufunc+SCRIPT_NUM);
    if(!LooksLikePtr(d)||n<8||n>65536||!SafeReadable((void*)d,n))return false;
    dataOut=d; numOut=n; return true;
}
static bool WriteBytes(uintptr_t addr,const uint8_t* src,size_t n){
    if(!Writable((void*)addr,n)){ DWORD old; if(!VirtualProtect((void*)addr,n,PAGE_EXECUTE_READWRITE,&old))return false; memcpy((void*)addr,src,n); DWORD t; VirtualProtect((void*)addr,n,old,&t); FlushInstructionCache(GetCurrentProcess(),(void*)addr,n); return true; }
    memcpy((void*)addr,src,n); return true;
}

// ─── VEH crash logger ───
static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode;
    bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374||code==0xC00000FD;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH;
    long seq=InterlockedIncrement(&g_crashSeq); if(seq>32)return EXCEPTION_CONTINUE_SEARCH;
    Markerf("[VEH] fatal code=0x%08X rip=0x%llX rva=0x%llX\r\n",code,(unsigned long long)ep->ContextRecord->Rip,
        g_modBase?(unsigned long long)(ep->ContextRecord->Rip-g_modBase):0ull);
    return EXCEPTION_CONTINUE_SEARCH;
}

static bool PatchPreviewable(uintptr_t ufunc){
    uintptr_t d; uint32_t n; if(!ScriptOf(ufunc,d,n))return false;
    if(n<=(uint32_t)PREV_POKE_OFF)return false;
    uint8_t at257=*(uint8_t*)(d+PREV_POKE_OFF); uint8_t at0=*(uint8_t*)d;
    if(at0==0x06){ Markerf("  IsPreviewable @0x%llX already patched (Script[0]=06)\r\n",(unsigned long long)ufunc); return true; }
    if(at257!=PREV_POKE_FROM)return false;             // not the tile IsPreviewable signature
    uint8_t poke=PREV_POKE_TO; uint8_t jmp[5]={0x06,(uint8_t)(PREV_JMP_TGT&0xFF),(uint8_t)((PREV_JMP_TGT>>8)&0xFF),0,0};
    bool ok1=WriteBytes(d+PREV_POKE_OFF,&poke,1); bool ok2=WriteBytes(d,jmp,5);
    Markerf("  PATCH IsPreviewable @0x%llX Script=0x%llX Num=%u : poke[257]28->27 ok=%d + jump0 247 ok=%d\r\n",
        (unsigned long long)ufunc,(unsigned long long)d,n,ok1,ok2);
    return ok1&&ok2;
}
static bool PatchUseable(uintptr_t ufunc){
    uintptr_t d; uint32_t n; if(!ScriptOf(ufunc,d,n))return false;
    if(n<=(uint32_t)USE_JMP_TGT)return false;
    if(*(uint8_t*)d==0x06){ Markerf("  IsUseable @0x%llX already patched\r\n",(unsigned long long)ufunc); return true; }
    uint8_t jmp[5]={0x06,(uint8_t)(USE_JMP_TGT&0xFF),(uint8_t)((USE_JMP_TGT>>8)&0xFF),0,0};
    bool ok=WriteBytes(d,jmp,5);
    Markerf("  PATCH IsUseable @0x%llX Script=0x%llX Num=%u : jump0 109 ok=%d\r\n",(unsigned long long)ufunc,(unsigned long long)d,n,ok);
    return ok;
}

// Scan GUObjectArray: find every tile IsPreviewable (by signature) + its same-Outer IsUseable; patch both.
static int ApplyTilePatches(){
    int total=NumElements(); if(total<=0)return 0;
    // Pass 1: collect tile IsPreviewable UFuncs (signature) and ALL IsUseable UFuncs (addr+outer).
    uintptr_t prevFns[8]={0}, prevOuter[8]={0}; int nprev=0;
    uintptr_t useFns[64]={0}, useOuter[64]={0}; int nuse=0;
    for(int i=0;i<total;i++){
        uintptr_t o=ObjAt((uint32_t)i); if(!LooksLikePtr(o))continue;
        char nm[64]; uint32_t id=NameId(o); if(!id)continue; if(!GetFNameStr(id,nm,sizeof(nm)))continue;
        if(nm[0]!='I'||nm[1]!='s')continue;             // cheap prefilter: Is*
        if(strcmp(nm,"IsPreviewable")==0){
            uintptr_t d; uint32_t n; if(ScriptOf(o,d,n) && n>(uint32_t)PREV_POKE_OFF){
                uint8_t b=*(uint8_t*)(d+PREV_POKE_OFF);
                if((b==PREV_POKE_FROM||*(uint8_t*)d==0x06) && nprev<8){ prevFns[nprev]=o; prevOuter[nprev]=OuterOf(o); nprev++; }
            }
        } else if(strcmp(nm,"IsUseable")==0){
            if(nuse<64){ useFns[nuse]=o; useOuter[nuse]=OuterOf(o); nuse++; }
        }
    }
    if(nprev==0){ return 0; }                            // tile class not loaded yet
    int patched=0;
    for(int p=0;p<nprev;p++){
        Markerf("[tile] IsPreviewable @0x%llX outer=0x%llX\r\n",(unsigned long long)prevFns[p],(unsigned long long)prevOuter[p]);
        bool okP=PatchPreviewable(prevFns[p]);
        bool okU=false;
        for(int u=0;u<nuse;u++){ if(useOuter[u]==prevOuter[p]){ okU=PatchUseable(useFns[u]); break; } }
        if(okP&&okU)patched++;
        else Markerf("  (pair incomplete: prevOK=%d useOK=%d — IsUseable in same outer %s)\r\n",okP,okU,okU?"found":"NOT found");
    }
    return patched;
}

static DWORD WINAPI Worker(LPVOID){
    AddVectoredExceptionHandler(1,CrashVEH);
    g_modBase=(uintptr_t)GetModuleHandleW(nullptr);
    Markerf("[0] catalog_pick_fix started; modBase=0x%llX NumElements=%d\r\n",(unsigned long long)g_modBase,NumElements());
    int tries=0; bool done=false;
    while(tries<600){                                    // retry until HUNTERS tile class is loaded (~5min budget)
        int p=ApplyTilePatches();
        if(p>0){ Markerf("[done] patched %d tile pair(s) — owned clicks now route to the preview path\r\n",p); done=true; break; }
        tries++; Sleep(500);
    }
    if(!done)Marker("[warn] tile UFuncs not found within budget (open HUNTERS to load them, or relaunch)\r\n");
    // Re-verify/re-apply every 3s (covers a tile-class reload on re-nav); idempotent.
    while(true){ Sleep(3000); ApplyTilePatches(); }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID){
    if(reason==DLL_PROCESS_ATTACH){ DisableThreadLibraryCalls(h); CreateThread(nullptr,0,Worker,nullptr,0,nullptr); }
    return TRUE;
}
