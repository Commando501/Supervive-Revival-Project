// trace_hooks — vtable-hook UAssetManager query virtuals to see EXACTLY what the ALL
// HUNTERS grid asks the AssetManager for at menu-load. Session 43 proved the per-type
// Hero AssetMap is populated correctly (25 heroes under PascalCase names) yet the grid
// stays empty — so the grid must request something my scan doesn't satisfy. This traces
// the requests. Shipping build strips Verbose UE_LOG, so we hook instead.
//
// Targets (LokiAssetManager vtable @ RVA +0x888CB78; slots counted from AssetManager.h
// with ScanPathsForPrimaryAssets = slot 88, validated by AddDynamicAsset=slot 94):
//   slot 101  GetPrimaryAssetObject(const FPrimaryAssetId&)            [Hero-filtered]
//   slot 110  GetPrimaryAssetIdList(FPrimaryAssetType, TArray<...>&)   [does grid enumerate?]
//   slot 119  ChangeBundleStateForPrimaryAssets(const TArray<FPrimaryAssetId>&, ...)
//
// Mechanism: swap each vtable slot to a logging stub that records the request (FNames
// resolved via the FNamePool at RVA +0x9D81450), then tail-jumps to the original. No
// prologue patching. Un-hook (restore slots) after the menu-load window.
//
// Build:  clang++ -shared -O2 trace_hooks.cpp -o trace_hooks.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe trace_hooks.dll 0x3EC57D0 <prologuehex>
//   (any early inject works; we gate on the vtable slot being readable). Marker below.

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\trace-hooks-marker.txt";

constexpr uintptr_t kVtRva       = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kGGameTidRva = 0x9D49158;
constexpr uintptr_t kNamePoolRva = 0x9D81450;   // &FNamePool.Blocks[0]
constexpr uint32_t  kHeroFName   = 0x1A568;

constexpr int SLOT_OBJ = 101;  // GetPrimaryAssetObject
constexpr int SLOT_IDL = 110;  // GetPrimaryAssetIdList
constexpr int SLOT_CBS = 119;  // ChangeBundleStateForPrimaryAssets

static uintptr_t g_modBase = 0;
static uintptr_t g_origObj = 0, g_origIdl = 0, g_origCbs = 0;
static uint8_t*  g_stubObj = nullptr;
static uint8_t*  g_stubIdl = nullptr;
static uint8_t*  g_stubCbs = nullptr;
static volatile bool g_unhooked = false;

// ── marker (worker thread) + ring log (hook threads) ──────────────────
static void Marker(const char* m) {
    HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,
                         nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE)return; DWORD w=0; WriteFile(h,m,(DWORD)strlen(m),&w,nullptr); CloseHandle(h);
}
static void Markerf(const char* fmt,...){char b[512];va_list a;va_start(a,fmt);_vsnprintf_s(b,sizeof(b),_TRUNCATE,fmt,a);va_end(a);Marker(b);}

constexpr size_t kLogBuf=256*1024;
static char g_log[kLogBuf];
static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLog(const char* s){RingAppend(s,(int)strlen(s));}
static void RingLogf(const char* fmt,...){char b[512];va_list a;va_start(a,fmt);_vsnprintf_s(b,sizeof(b),_TRUNCATE,fmt,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}

// ── FNamePool resolver: FName ComparisonIndex -> string (narrow, Len10 header) ──
static void ResolveFName(uint32_t idx, char* out, int outsz) {
    out[0]=0;
    uint32_t block = idx >> 16, off = (idx & 0xFFFF) << 1;
    if (block >= 128) { snprintf(out,outsz,"<blk%u>",block); return; }
    uintptr_t* blocks = (uintptr_t*)(g_modBase + kNamePoolRva);
    if (!SafeReadable(blocks+block,8)) { snprintf(out,outsz,"<blkptr>"); return; }
    uintptr_t base = blocks[block];
    if (!base || !SafeReadable((void*)(base+off),2)) { snprintf(out,outsz,"<hdr>"); return; }
    uint16_t hdr = *(uint16_t*)(base+off);
    int len = hdr >> 6;                       // Len10 layout: length = header>>6
    if (len<=0 || len>250) { snprintf(out,outsz,"<len%d>",len); return; }
    if (!SafeReadable((void*)(base+off+2),len)) { snprintf(out,outsz,"<str>"); return; }
    const char* s=(const char*)(base+off+2);
    int n = len<outsz-1?len:outsz-1; for(int i=0;i<n;i++)out[i]=s[i]; out[n]=0;
}

// ── C handlers (called by the asm stubs; args = original rcx,rdx,r8,r9) ──
extern "C" void h_obj(uintptr_t /*rcx*/, uintptr_t rdx, uintptr_t, uintptr_t) {
    // GetPrimaryAssetObject(const FPrimaryAssetId& @rdx). Log only Hero-type requests.
    if (!SafeReadable((void*)rdx,16)) return;
    uint32_t type=*(uint32_t*)rdx, name=*(uint32_t*)(rdx+8);
    if (type!=kHeroFName) return;
    char tn[128],nn[128]; ResolveFName(type,tn,sizeof(tn)); ResolveFName(name,nn,sizeof(nn));
    RingLogf("[GetObject] %s:%s\r\n",tn,nn);
}
extern "C" void h_idl(uintptr_t /*rcx*/, uintptr_t rdx, uintptr_t, uintptr_t) {
    // GetPrimaryAssetIdList(FPrimaryAssetType @rdx by value; low32=index). Log the type.
    uint32_t type=(uint32_t)(rdx & 0xFFFFFFFF);
    char tn[128]; ResolveFName(type,tn,sizeof(tn));
    RingLogf("[GetIdList] type=%s (0x%X)\r\n",tn,type);
}
extern "C" void h_cbs(uintptr_t /*rcx*/, uintptr_t rdx, uintptr_t, uintptr_t) {
    // ChangeBundleStateForPrimaryAssets(const TArray<FPrimaryAssetId>& @rdx, ...).
    if (!SafeReadable((void*)rdx,16)) { RingLog("[CBS] arr unreadable\r\n"); return; }
    uintptr_t data=*(uintptr_t*)rdx; int32_t num=*(int32_t*)(rdx+8);
    RingLogf("[CBS] AssetsToChange num=%d\r\n",num);
    if (num<0||num>4096||!SafeReadable((void*)data,(size_t)num*16)) return;
    for (int i=0;i<num;i++){
        uint32_t type=*(uint32_t*)(data+i*16), name=*(uint32_t*)(data+i*16+8);
        char tn[128],nn[128]; ResolveFName(type,tn,sizeof(tn)); ResolveFName(name,nn,sizeof(nn));
        RingLogf("[CBS]   [%d] %s:%s\r\n",i,tn,nn);
    }
}

// ── build a tail-jump logging stub: save rcx/rdx/r8/r9, call handler, restore, jmp orig ──
static uint8_t* BuildStub(void* handler, uintptr_t orig) {
    uint8_t* p=(uint8_t*)VirtualAlloc(nullptr,0x80,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!p)return nullptr; uint8_t* w=p;
    *w++=0x51;                               // push rcx
    *w++=0x52;                               // push rdx
    *w++=0x41;*w++=0x50;                     // push r8
    *w++=0x41;*w++=0x51;                     // push r9
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x28; // sub rsp,0x28  (shadow+align)
    *w++=0x48;*w++=0xB8; uint64_t hf=(uint64_t)handler; memcpy(w,&hf,8); w+=8; // mov rax,handler
    *w++=0xFF;*w++=0xD0;                      // call rax
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x28; // add rsp,0x28
    *w++=0x41;*w++=0x59;                     // pop r9
    *w++=0x41;*w++=0x58;                     // pop r8
    *w++=0x5A;                               // pop rdx
    *w++=0x59;                               // pop rcx
    *w++=0x48;*w++=0xB8; uint64_t of=(uint64_t)orig; memcpy(w,&of,8); w+=8; // mov rax,orig
    *w++=0xFF;*w++=0xE0;                      // jmp rax
    return p;
}

static bool SwapSlot(int slot, void* newval, uintptr_t* savedOrig) {
    uintptr_t* pslot=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)slot*8);
    if(!SafeReadable(pslot,8))return false;
    *savedOrig=*pslot;
    DWORD op=0; if(!VirtualProtect(pslot,8,PAGE_READWRITE,&op))return false;
    *pslot=(uintptr_t)newval;
    DWORD d=0; VirtualProtect(pslot,8,op,&d);
    return true;
}
static void RestoreSlot(int slot, uintptr_t orig){
    uintptr_t* pslot=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)slot*8);
    DWORD op=0; if(VirtualProtect(pslot,8,PAGE_READWRITE,&op)){*pslot=orig;DWORD d=0;VirtualProtect(pslot,8,op,&d);}
}

static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] trace_hooks worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX vtable=0x%llX\r\n",(unsigned long long)g_modBase,(unsigned long long)(g_modBase+kVtRva));
    if(!WaitTid(g_modBase,60000)){Marker("[1] FAIL GGameThreadId\r\n");return 2;}

    // wait for the vtable slots to be readable + hold plausible .text pointers
    uintptr_t* pcbs=(uintptr_t*)(g_modBase+kVtRva+SLOT_CBS*8);
    DWORD dl=GetTickCount()+30000; bool ready=false;
    while(GetTickCount()<dl){ if(SafeReadable(pcbs,8)){ uintptr_t v=*pcbs; if(v>g_modBase && v<g_modBase+0xC000000){ready=true;break;} } Sleep(5); }
    if(!ready){Marker("[2] FAIL vtable slot not ready\r\n");return 3;}

    g_stubObj=BuildStub((void*)&h_obj,0); // orig filled after read
    // build stubs after reading originals so the tail-jump targets are correct
    uintptr_t oObj=*(uintptr_t*)(g_modBase+kVtRva+SLOT_OBJ*8);
    uintptr_t oIdl=*(uintptr_t*)(g_modBase+kVtRva+SLOT_IDL*8);
    uintptr_t oCbs=*(uintptr_t*)(g_modBase+kVtRva+SLOT_CBS*8);
    g_stubObj=BuildStub((void*)&h_obj,oObj);
    g_stubIdl=BuildStub((void*)&h_idl,oIdl);
    g_stubCbs=BuildStub((void*)&h_cbs,oCbs);
    Markerf("[2] origs: Obj=0x%llX Idl=0x%llX Cbs=0x%llX\r\n",(unsigned long long)oObj,(unsigned long long)oIdl,(unsigned long long)oCbs);
    if(!g_stubObj||!g_stubIdl||!g_stubCbs){Marker("[3] FAIL build stubs\r\n");return 4;}

    bool a=SwapSlot(SLOT_OBJ,g_stubObj,&g_origObj);
    bool b=SwapSlot(SLOT_IDL,g_stubIdl,&g_origIdl);
    bool c=SwapSlot(SLOT_CBS,g_stubCbs,&g_origCbs);
    Markerf("[3] hooks installed: Obj=%d Idl=%d Cbs=%d\r\n",a,b,c);

    // flush loop; un-hook after 90s (well past menu-load, before the integrity crash)
    LONG64 flushed=0; DWORD start=GetTickCount(); DWORD hb=start;
    while(true){
        Sleep(150);
        if(!g_unhooked && GetTickCount()-start>=90000){
            RestoreSlot(SLOT_OBJ,g_origObj);RestoreSlot(SLOT_IDL,g_origIdl);RestoreSlot(SLOT_CBS,g_origCbs);
            g_unhooked=true; Marker("[unhook] vtable slots restored\r\n");
        }
        LONG64 head=g_head; if(head>(LONG64)sizeof(g_log))head=(LONG64)sizeof(g_log);
        if(head>flushed){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_log+flushed,(DWORD)(head-flushed),&w,nullptr);CloseHandle(f);flushed=head;}}
        if(GetTickCount()-hb>=5000){Markerf("[hb] head=%lld unhooked=%d\r\n",(long long)g_head,g_unhooked?1:0);hb=GetTickCount();}
    }
}

BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
