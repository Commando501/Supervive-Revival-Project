// probe_r14 — capture the runtime pointer + contents of the per-hero map the ALL HUNTERS
// grid actually consults. Session 45 read the grid filter from code: after
// GetPrimaryAssetIdList(Hero)=25, caller 1 (+0x562EBF7) loops and, per hero id, calls a
// per-hero lookup (+0x57AB3C0, at call site +0x562EC85) into a widget/singleton object r14;
// if the lookup returns null the hero is dropped. r14 = Singleton(+0x565E1C0)->[0x1f0]->[0x190];
// the per-hero TMap is at r14+0x60. We could not identify r14's class statically (weak-ptr held),
// and we don't know if the map is EMPTY (populate it) or WRONG-KEYED (re-key). This DLL captures
// r14 live + dumps the map.
//
// Mechanism:
//   1. Scan (as scan_on_enum) so GetPrimaryAssetIdList(Hero) returns 25 -> caller 1's loop runs.
//   2. Hook GetPrimaryAssetIdList (slot 110) with a retaddr-capturing stub. In the handler:
//        - first call: run the scan (rcx = manager).
//        - if retaddr == caller-1 (+0x562EBFE): JIT-patch caller-1's `call +0x57AB3C0` site
//          (+0x562EC85, an E8 rel32; decrypted because caller 1 is executing) to redirect to a
//          near-allocated log-stub.
//   3. log-stub: rcx = r14. Save regs, call logger(r14) [dumps r14, [r14] vtable, the +0x60 map],
//      restore, tail-jump the REAL lookup (absolute) so caller 1 behaves normally.
//   4. Un-patch the call site + un-hook slot 110 after capture / ~28s (integrity check ~3-5min).
//
// Build:  clang++ -shared -O2 probe_r14.cpp -o probe_r14.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe probe_r14.dll 0x3EC57D0 <prologuehex>
// Marker: docs/probe-r14-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

typedef unsigned long long ull;
static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\probe-r14-marker.txt";

constexpr uintptr_t kVtRva       = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva     = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kGGameTidRva = 0x9D49158;
constexpr uintptr_t kNamePoolRva = 0x9D81450;
constexpr uintptr_t kTypeMapOff  = 0x478;
constexpr uintptr_t kInfoBaseOff = 0x30;
constexpr uintptr_t kInfoPathsOff= 0x70;
constexpr int       SLOT_IDL     = 110;
constexpr uint32_t  kHeroFName   = 0x1A568;
constexpr uintptr_t RET1_RVA     = 0x562EBFE;   // caller-1 GetPrimaryAssetIdList return addr
constexpr uintptr_t CALLSITE_RVA = 0x562EC85;   // caller-1 `call +0x57AB3C0` (E8 rel32)
constexpr uintptr_t LOOKUP_RVA   = 0x57AB3C0;   // the real per-hero lookup fn
static const uint8_t kCallsiteBytes[5] = {0xE8,0x36,0xC7,0x17,0x00};

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static uint8_t*  g_logStub = nullptr;
static volatile long g_scanState = 0;
static volatile long g_patched   = 0;
static volatile long g_capCount  = 0;
static volatile bool g_cleaned   = false;
static uint8_t   g_origRel[4];

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLogBuf=128*1024; static char g_log[kLogBuf]; static volatile LONG64 g_head=0;
static void RingAppend(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_head,(LONG64)n);if(p+n>(LONG64)sizeof(g_log))return;for(int i=0;i<n;i++)g_log[p+i]=s[i];}
static void RingLog(const char* s){RingAppend(s,(int)strlen(s));}
static void RingLogf(const char* f,...){char b[400];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RingAppend(b,(int)strlen(b));}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}
static void ResolveFName(uint32_t idx,char* out,int outsz){out[0]=0;uint32_t block=idx>>16,off=(idx&0xFFFF)<<1;if(block>=128){snprintf(out,outsz,"<blk%u>",block);return;}uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva);if(!SafeReadable(blocks+block,8)){snprintf(out,outsz,"<blkptr>");return;}uintptr_t base=blocks[block];if(!base||!SafeReadable((void*)(base+off),2)){snprintf(out,outsz,"<hdr>");return;}uint16_t hdr=*(uint16_t*)(base+off);int len=hdr>>6;if(len<=0||len>250){snprintf(out,outsz,"<len%d>",len);return;}if(!SafeReadable((void*)(base+off+2),len)){snprintf(out,outsz,"<str>");return;}const char* s=(const char*)(base+off+2);int n=len<outsz-1?len:outsz-1;for(int i=0;i<n;i++)out[i]=s[i];out[n]=0;}

// scan all types (populate enumeration) — from scan_on_enum
static void RunScanForAllTypes(void* manager){const uint8_t* mgr=(const uint8_t*)manager;if(!SafeReadable(mgr+kTypeMapOff,16)){RingLog("[scan] typemap unreadable\r\n");return;}uintptr_t data=*(const uintptr_t*)(mgr+kTypeMapOff);uint32_t mx=*(const uint32_t*)(mgr+kTypeMapOff+12);if(!LooksLikePtr(data)||mx==0||mx>4096){RingLog("[scan] bad typemap\r\n");return;}int called=0,heroAdded=-1;for(uint32_t i=0;i<mx;i++){const uint8_t* e=(const uint8_t*)data+(uintptr_t)i*0x20;if(!SafeReadable(e,0x10))continue;uint64_t key=*(const uint64_t*)(e);uintptr_t td=*(const uintptr_t*)(e+8);if(key==0||!LooksLikePtr(td)||!SafeReadable((void*)td,0x80))continue;uint64_t type=*(const uint64_t*)td;uintptr_t base=*(const uintptr_t*)(td+kInfoBaseOff);void* paths=(void*)(td+kInfoPathsOff);if(type!=key||!LooksLikePtr(base)||!SafeReadable((void*)base,8))continue;int32_t added=g_scan(manager,type,paths,(void*)base,true,false,true);called++;if((uint32_t)(type&0xFFFFFFFF)==kHeroFName)heroAdded=added;}RingLogf("[scan] DONE %d types (Hero added=%d)\r\n",called,heroAdded);}

// ── the log-stub's C logger: dump r14, its vtable, the +0x60 map ──
extern "C" void logger(void* r14p){
    long n=InterlockedIncrement(&g_capCount);
    if(n>6) return;
    uintptr_t r14=(uintptr_t)r14p;
    RingLogf("\r\n[cap#%ld] r14=0x%llX\r\n",n,(ull)r14);
    if(!SafeReadable((void*)r14,8)){RingLog("  r14 unreadable\r\n");return;}
    uintptr_t v0=*(uintptr_t*)r14;
    if(v0>g_modBase && v0<g_modBase+0xC000000) RingLogf("  [r14+0]=0x%llX (vtable? rva +0x%llX)\r\n",(ull)v0,(ull)(v0-g_modBase));
    else RingLogf("  [r14+0]=0x%llX (not a module ptr)\r\n",(ull)v0);
    RingLog("  raw r14+0x50..0xB0: ");
    for(uintptr_t i=0x50;i<0xB0;i+=8){ if(SafeReadable((void*)(r14+i),8)) RingLogf("%016llX ",(ull)*(uintptr_t*)(r14+i)); else {RingLog("?? ");break;} }
    RingLog("\r\n");
    uintptr_t data=SafeReadable((void*)(r14+0x60),8)?*(uintptr_t*)(r14+0x60):0;
    int32_t num =SafeReadable((void*)(r14+0x68),4)?*(int32_t*)(r14+0x68):-1;
    RingLogf("  map@r14+0x60: Data=0x%llX Num=%d\r\n",(ull)data,num);
    if(LooksLikePtr(data) && num>0 && num<=8192){
        int show=num<12?num:12;
        for(int i=0;i<show;i++){
            uintptr_t e=data+(uintptr_t)i*0x20;
            if(!SafeReadable((void*)e,16)) break;
            uint32_t t=*(uint32_t*)e, nm=*(uint32_t*)(e+8);
            char tn[96],nn[96]; ResolveFName(t,tn,sizeof(tn)); ResolveFName(nm,nn,sizeof(nn));
            RingLogf("    [%d] key %s : %s\r\n",i,tn,nn);
        }
    }
}

// ── near allocation so the patched E8 rel32 can reach the log-stub ──
static uint8_t* AllocNear(uintptr_t nearAddr){
    for(uintptr_t off=0x02000000; off<0x40000000; off+=0x02000000){
        void* p=VirtualAlloc((void*)((nearAddr+off)&~(uintptr_t)0xFFFF),0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE); if(p)return(uint8_t*)p;
        void* q=VirtualAlloc((void*)((nearAddr-off)&~(uintptr_t)0xFFFF),0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE); if(q)return(uint8_t*)q;
    }
    return (uint8_t*)VirtualAlloc(nullptr,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
}
static uint8_t* BuildLogStub(){
    uintptr_t cs=g_modBase+CALLSITE_RVA;
    uint8_t* p=AllocNear(cs); if(!p)return nullptr;
    intptr_t d=(intptr_t)p-(intptr_t)(cs+5);
    if(d>0x7ff00000||d<-(intptr_t)0x7ff00000){ Markerf("[logstub] OUT OF REACH d=0x%llX\r\n",(ull)d); return nullptr; }
    uint8_t* w=p;
    *w++=0x51;*w++=0x52;*w++=0x41;*w++=0x50;*w++=0x41;*w++=0x51;*w++=0x41;*w++=0x52;*w++=0x41;*w++=0x53; // push rcx,rdx,r8,r9,r10,r11
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x28;                       // sub rsp,0x28
    *w++=0x48;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x50;             // mov rcx,[rsp+0x50] (r14)
    *w++=0x48;*w++=0xB8; uint64_t lf=(uint64_t)&logger; memcpy(w,&lf,8); w+=8; *w++=0xFF;*w++=0xD0; // mov rax,logger; call rax
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x28;                       // add rsp,0x28
    *w++=0x41;*w++=0x5B;*w++=0x41;*w++=0x5A;*w++=0x41;*w++=0x59;*w++=0x41;*w++=0x58;*w++=0x5A;*w++=0x59; // pop r11,r10,r9,r8,rdx,rcx
    uint64_t lookup=(uint64_t)(g_modBase+LOOKUP_RVA);
    *w++=0x48;*w++=0xB8; memcpy(w,&lookup,8); w+=8; *w++=0xFF;*w++=0xE0; // mov rax,lookup; jmp rax
    return p;
}

static void PatchCallSite(){
    if(InterlockedCompareExchange(&g_patched,1,0)!=0) return;
    uintptr_t cs=g_modBase+CALLSITE_RVA;
    if(!SafeReadable((void*)cs,5)||memcmp((void*)cs,kCallsiteBytes,5)!=0){ Marker("[patch] callsite not decrypted/mismatch\r\n"); g_patched=0; return; }
    if(!g_logStub){ g_logStub=BuildLogStub(); if(!g_logStub){ Marker("[patch] logstub build FAIL\r\n"); g_patched=0; return; } }
    int32_t newrel=(int32_t)((intptr_t)g_logStub-(intptr_t)(cs+5));
    memcpy(g_origRel,(void*)(cs+1),4);
    DWORD op; if(!VirtualProtect((void*)(cs+1),4,PAGE_EXECUTE_READWRITE,&op)){ Marker("[patch] VP FAIL\r\n"); g_patched=0; return; }
    memcpy((void*)(cs+1),&newrel,4);
    DWORD dd; VirtualProtect((void*)(cs+1),4,op,&dd);
    FlushInstructionCache(GetCurrentProcess(),(void*)cs,5);
    Markerf("[patch] callsite patched -> logstub=%p (newrel=0x%X)\r\n",(void*)g_logStub,(unsigned)newrel);
}
static void UnpatchCallSite(){
    if(!g_patched||!g_logStub) return;
    uintptr_t cs=g_modBase+CALLSITE_RVA;
    DWORD op; if(VirtualProtect((void*)(cs+1),4,PAGE_EXECUTE_READWRITE,&op)){ memcpy((void*)(cs+1),g_origRel,4); DWORD dd; VirtualProtect((void*)(cs+1),4,op,&dd); FlushInstructionCache(GetCurrentProcess(),(void*)cs,5); }
}

// ── slot-110 handler (rcx,rdx,r8,r9,retaddr): scan on first call + JIT-patch on caller-1 ──
extern "C" void h_idl(uintptr_t rcx, uintptr_t /*rdx*/, uintptr_t, uintptr_t, uintptr_t ret){
    if(InterlockedCompareExchange(&g_scanState,1,0)==0){
        g_scan=(PFN_Scan)(g_modBase+kScanRva);
        RunScanForAllTypes((void*)rcx);
        InterlockedExchange(&g_scanState,2);
    }
    if(ret==g_modBase+RET1_RVA && g_patched==0) PatchCallSite();
}

// retaddr-capturing stub (from trace_caller): handler(rcx,rdx,r8,r9,[rsp+0x20]=ret) then jmp orig
static uint8_t* BuildIdlStub(void* handler, uintptr_t orig){
    uint8_t* p=(uint8_t*)VirtualAlloc(nullptr,0x80,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!p)return nullptr; uint8_t* w=p;
    *w++=0x51;*w++=0x52;*w++=0x41;*w++=0x50;*w++=0x41;*w++=0x51;       // push rcx,rdx,r8,r9
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x38;                           // sub rsp,0x38
    *w++=0x48;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x58;                 // mov rax,[rsp+0x58] (retaddr)
    *w++=0x48;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x20;                 // mov [rsp+0x20],rax
    *w++=0x48;*w++=0xB8; uint64_t hf=(uint64_t)handler; memcpy(w,&hf,8); w+=8; *w++=0xFF;*w++=0xD0; // call handler
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x38;                           // add rsp,0x38
    *w++=0x41;*w++=0x59;*w++=0x41;*w++=0x58;*w++=0x5A;*w++=0x59;       // pop r9,r8,rdx,rcx
    *w++=0x48;*w++=0xB8; uint64_t of=(uint64_t)orig; memcpy(w,&of,8); w+=8; *w++=0xFF;*w++=0xE0; // jmp orig
    return p;
}

static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] probe_r14 worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX\r\n",(ull)g_modBase);
    if(!WaitTid(g_modBase,60000)){Marker("[1] FAIL GGameThreadId\r\n");return 2;}
    uintptr_t* pslot=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)SLOT_IDL*8);
    DWORD dl=GetTickCount()+30000; bool ready=false;
    while(GetTickCount()<dl){if(SafeReadable(pslot,8)){uintptr_t v=*pslot;if(v>g_modBase&&v<g_modBase+0xC000000){ready=true;break;}}Sleep(5);}
    if(!ready){Marker("[2] FAIL slot110 not ready\r\n");return 3;}
    g_origIdl=*pslot;
    g_stubIdl=BuildIdlStub((void*)&h_idl,g_origIdl);
    if(!g_stubIdl){Marker("[3] FAIL build stub\r\n");return 4;}
    DWORD op=0; if(!VirtualProtect(pslot,8,PAGE_READWRITE,&op)){Marker("[3] FAIL VP\r\n");return 5;}
    *pslot=(uintptr_t)g_stubIdl; DWORD d=0; VirtualProtect(pslot,8,op,&d);
    Markerf("[3] slot110 hooked (orig=0x%llX)\r\n",(ull)g_origIdl);
    LONG64 flushed=0; DWORD start=GetTickCount(); DWORD hb=start;
    while(true){
        Sleep(120);
        if(!g_cleaned && (g_capCount>=6 || GetTickCount()-start>=28000)){
            UnpatchCallSite();
            DWORD o=0; if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}
            g_cleaned=true; Marker("\r\n[cleanup] call site un-patched + slot110 un-hooked\r\n");
        }
        LONG64 head=g_head; if(head>(LONG64)sizeof(g_log))head=(LONG64)sizeof(g_log);
        if(head>flushed){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_log+flushed,(DWORD)(head-flushed),&w,nullptr);CloseHandle(f);flushed=head;}}
        if(GetTickCount()-hb>=4000){Markerf("[hb] scan=%ld patched=%ld caps=%ld cleaned=%d\r\n",g_scanState,g_patched,g_capCount,g_cleaned?1:0);hb=GetTickCount();}
    }
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
