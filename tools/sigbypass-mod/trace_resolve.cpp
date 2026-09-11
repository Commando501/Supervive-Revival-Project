// trace_resolve — with the catalog populated (demand-driven scan on GetPrimaryAssetIdList),
// trace how the ALL HUNTERS grid RESOLVES its 25 hero IDs into renderable data. Session 43
// proved enumeration is fixed (GetPrimaryAssetIdList(Hero)=25) yet the grid renders 0 tiles,
// so the failure is in the id -> asset-data/object resolution. This hooks those getters and
// logs, per Hero request, what they return (data/object/null).
//
// LokiAssetManager vtable @ RVA +0x888CB78; slots (ScanPaths=88, AddDynamicAsset=94 verified):
//   slot 99  GetPrimaryAssetData(const FPrimaryAssetId& @rdx, FAssetData& @r8) -> bool
//   slot 100 GetPrimaryAssetDataList(FPrimaryAssetType @rdx, TArray<FAssetData>& @r8) -> bool
//   slot 101 GetPrimaryAssetObject(const FPrimaryAssetId& @rdx) -> UObject*
//   slot 110 GetPrimaryAssetIdList  (populate catalog on first call)
//
// Build:  clang++ -shared -O2 trace_resolve.cpp -o trace_resolve.dll -lkernel32
// Marker: docs/trace-resolve-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath="G:\\git\\Supervive Revival Project\\docs\\trace-resolve-marker.txt";
constexpr uintptr_t kVtRva=0x888CB78, kScanRva=0x34CF9F0, kGGameTidRva=0x9D49158, kNamePoolRva=0x9D81450;
constexpr uintptr_t kTypeMapOff=0x478, kInfoBaseOff=0x30, kInfoPathsOff=0x70;
constexpr uint32_t  kHeroFName=0x1A568;
constexpr int SLOT_DATA=99, SLOT_DLIST=100, SLOT_OBJ=101, SLOT_IDL=110;

typedef int32_t (*PFN_Scan)(void*,uint64_t,void*,void*,bool,bool,bool);
static uintptr_t g_modBase=0; static PFN_Scan g_scan=nullptr;
static uintptr_t g_oData=0,g_oDlist=0,g_oObj=0,g_oIdl=0;
static volatile long g_scanState=0; static volatile bool g_unhooked=false;
static int SLOTS[2]={SLOT_DLIST,SLOT_IDL};        // only the per-type getters are hooked
static uintptr_t* g_saved[2]={&g_oDlist,&g_oIdl};

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
constexpr size_t kLB=256*1024; static char g_lg[kLB]; static volatile LONG64 g_hd=0;
static void RA(const char* s,int n){LONG64 p=InterlockedExchangeAdd64(&g_hd,(LONG64)n);if(p+n>(LONG64)sizeof(g_lg))return;for(int i=0;i<n;i++)g_lg[p+i]=s[i];}
static void RL(const char* s){RA(s,(int)strlen(s));}
static void RLf(const char* f,...){char b[300];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);RA(b,(int)strlen(b));}
static bool SR(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LLP(uintptr_t v){return v>=0x10000&&v<0x0001000000000000ULL&&(v&7)==0;}
static void RFN(uint32_t idx,char* out,int outsz){out[0]=0;uint32_t blk=idx>>16,off=(idx&0xFFFF)<<1;if(blk>=128){snprintf(out,outsz,"<blk%u>",blk);return;}uintptr_t*B=(uintptr_t*)(g_modBase+kNamePoolRva);if(!SR(B+blk,8)){snprintf(out,outsz,"<bp>");return;}uintptr_t base=B[blk];if(!base||!SR((void*)(base+off),2)){snprintf(out,outsz,"<h>");return;}uint16_t h=*(uint16_t*)(base+off);int len=h>>6;if(len<=0||len>250){snprintf(out,outsz,"<l%d>",len);return;}if(!SR((void*)(base+off+2),len)){snprintf(out,outsz,"<s>");return;}const char* s=(const char*)(base+off+2);int n=len<outsz-1?len:outsz-1;for(int i=0;i<n;i++)out[i]=s[i];out[n]=0;}

static void RunScan(void* mgr){const uint8_t* m=(const uint8_t*)mgr;if(!SR(m+kTypeMapOff,16)){RL("[scan] typemap unreadable\r\n");return;}
    uintptr_t data=*(const uintptr_t*)(m+kTypeMapOff);uint32_t mx=*(const uint32_t*)(m+kTypeMapOff+12);
    if(!LLP(data)||mx==0||mx>4096){RL("[scan] bad typemap\r\n");return;}int called=0,ha=-1;
    for(uint32_t i=0;i<mx;i++){const uint8_t* e=(const uint8_t*)data+(uintptr_t)i*0x20;if(!SR(e,0x10))continue;
        uint64_t key=*(const uint64_t*)e;uintptr_t td=*(const uintptr_t*)(e+8);if(key==0||!LLP(td)||!SR((void*)td,0x80))continue;
        uint64_t type=*(const uint64_t*)td;uintptr_t base=*(const uintptr_t*)(td+kInfoBaseOff);void* paths=(void*)(td+kInfoPathsOff);
        if(type!=key||!LLP(base)||!SR((void*)base,8))continue;int32_t added=g_scan(mgr,type,paths,(void*)base,true,false,true);called++;if((uint32_t)(type&0xFFFFFFFF)==kHeroFName)ha=added;}
    RLf("[scan] DONE %d types (Hero=%d)\r\n",called,ha);}

// ── handlers ──
extern "C" void pre_scan(uintptr_t rcx,uintptr_t,uintptr_t,uintptr_t){
    if(InterlockedCompareExchange(&g_scanState,1,0)!=0)return;
    RLf("[scan] first GetIdList -> populate (mgr=0x%llX)\r\n",(unsigned long long)rcx);
    g_scan=(PFN_Scan)(g_modBase+kScanRva);RunScan((void*)rcx);InterlockedExchange(&g_scanState,2);RL("[scan] complete\r\n");}
extern "C" void pre_noop(uintptr_t,uintptr_t,uintptr_t,uintptr_t){}
// post(ret, rdx, r8): id-taking (rdx=&FPrimaryAssetId), Hero-filtered
extern "C" void post_data(uintptr_t ret,uintptr_t rdx,uintptr_t){
    if(!SR((void*)rdx,16))return;uint32_t t=*(uint32_t*)rdx,n=*(uint32_t*)(rdx+8);if(t!=kHeroFName)return;
    char nn[96];RFN(n,nn,sizeof(nn));RLf("[GetData] Hero:%s -> ret=%d\r\n",nn,(int)(ret&0xFF));}
extern "C" void post_obj(uintptr_t ret,uintptr_t rdx,uintptr_t){
    if(!SR((void*)rdx,16))return;uint32_t t=*(uint32_t*)rdx,n=*(uint32_t*)(rdx+8);if(t!=kHeroFName)return;
    char nn[96];RFN(n,nn,sizeof(nn));RLf("[GetObject] Hero:%s -> obj=0x%llX\r\n",nn,(unsigned long long)ret);}
// post(ret, rdx=FName type by value, r8=&out TArray): type-taking
extern "C" void post_dlist(uintptr_t ret,uintptr_t rdx,uintptr_t r8){
    if((uint32_t)(rdx&0xFFFFFFFF)!=kHeroFName)return;int num=SR((void*)(r8+8),4)?*(int32_t*)(r8+8):-1;
    char tn[64];RFN((uint32_t)(rdx&0xFFFFFFFF),tn,sizeof(tn));RLf("[GetDataList] %s -> ret=%d outNum=%d\r\n",tn,(int)(ret&0xFF),num);}
extern "C" void post_idl(uintptr_t ret,uintptr_t rdx,uintptr_t r8){
    if((uint32_t)(rdx&0xFFFFFFFF)!=kHeroFName)return;int num=SR((void*)(r8+8),4)?*(int32_t*)(r8+8):-1;
    static volatile long once=0; if(InterlockedExchange(&once,1)==0||num>0)RLf("[GetIdList] Hero -> outNum=%d\r\n",num);(void)ret;}

// ── wrap stub: pre -> call orig -> post(ret,rdx,r8) -> ret ──
static uint8_t* Wrap(void* pre,void* post,uintptr_t orig){
    uint8_t* p=(uint8_t*)VirtualAlloc(nullptr,0x120,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(!p)return nullptr;uint8_t* w=p;
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x48;
    *w++=0x48;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x20;
    *w++=0x48;*w++=0x89;*w++=0x54;*w++=0x24;*w++=0x28;
    *w++=0x4C;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x30;
    *w++=0x4C;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x38;
    auto rel=[&](){*w++=0x48;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x20;*w++=0x48;*w++=0x8B;*w++=0x54;*w++=0x24;*w++=0x28;*w++=0x4C;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x30;*w++=0x4C;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x38;};
    rel();*w++=0x48;*w++=0xB8;uint64_t pf=(uint64_t)pre;memcpy(w,&pf,8);w+=8;*w++=0xFF;*w++=0xD0;    // call pre
    rel();*w++=0x48;*w++=0xB8;uint64_t of=(uint64_t)orig;memcpy(w,&of,8);w+=8;*w++=0xFF;*w++=0xD0;   // call orig
    *w++=0x48;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x40;                                                // mov [rsp+0x40],rax
    *w++=0x48;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x40;    // mov rcx,[rsp+0x40] (ret)
    *w++=0x48;*w++=0x8B;*w++=0x54;*w++=0x24;*w++=0x28;    // mov rdx,[rsp+0x28]
    *w++=0x4C;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x30;    // mov r8,[rsp+0x30]
    *w++=0x48;*w++=0xB8;uint64_t sf=(uint64_t)post;memcpy(w,&sf,8);w+=8;*w++=0xFF;*w++=0xD0;          // call post
    *w++=0x48;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x40;    // mov rax,[rsp+0x40]
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x48;*w++=0xC3;    // add rsp,0x48 ; ret
    return p;
}
static bool Swap(int slot,void* nv,uintptr_t* sv){uintptr_t* ps=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)slot*8);if(!SR(ps,8))return false;*sv=*ps;DWORD o=0;if(!VirtualProtect(ps,8,PAGE_READWRITE,&o))return false;*ps=(uintptr_t)nv;DWORD d=0;VirtualProtect(ps,8,o,&d);return true;}
static void Restore(int slot,uintptr_t v){uintptr_t* ps=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)slot*8);DWORD o=0;if(VirtualProtect(ps,8,PAGE_READWRITE,&o)){*ps=v;DWORD d=0;VirtualProtect(ps,8,o,&d);}}
static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SR(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] trace_resolve started\r\n");
    HMODULE e=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");if(!e){Marker("[0] FAIL mod\r\n");return 1;}
    g_modBase=(uintptr_t)e;Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);
    if(!WaitTid(g_modBase,60000)){Marker("[1] FAIL tid\r\n");return 2;}
    uintptr_t* pi=(uintptr_t*)(g_modBase+kVtRva+SLOT_IDL*8);DWORD dl=GetTickCount()+30000;bool rdy=false;
    while(GetTickCount()<dl){if(SR(pi,8)){uintptr_t v=*pi;if(v>g_modBase&&v<g_modBase+0xC000000){rdy=true;break;}}Sleep(5);}
    if(!rdy){Marker("[2] FAIL slot\r\n");return 3;}
    // read originals, build wraps, swap. ONLY the per-type getters (100 DataList, 110
    // IdList) — the per-OBJECT getters (99 GetData, 101 GetObject) are called millions of
    // times and hooking them stalls/crashes the game thread.
    uintptr_t oDlist=*(uintptr_t*)(g_modBase+kVtRva+SLOT_DLIST*8);
    uintptr_t oIdl=*(uintptr_t*)(g_modBase+kVtRva+SLOT_IDL*8);
    uint8_t* wDlist=Wrap((void*)&pre_noop,(void*)&post_dlist,oDlist);
    uint8_t* wIdl=Wrap((void*)&pre_scan,(void*)&post_idl,oIdl);
    Swap(SLOT_DLIST,wDlist,&g_oDlist);Swap(SLOT_IDL,wIdl,&g_oIdl);
    Marker("[3] hooks installed (100 DataList, 110 IdList)\r\n");
    LONG64 fl=0;DWORD hb=GetTickCount(),st=GetTickCount();
    while(true){Sleep(150);
        if(!g_unhooked && GetTickCount()-st>=90000){for(int i=0;i<2;i++)Restore(SLOTS[i],*g_saved[i]);g_unhooked=true;Marker("[unhook] restored\r\n");}
        LONG64 hd=g_hd;if(hd>(LONG64)sizeof(g_lg))hd=(LONG64)sizeof(g_lg);
        if(hd>fl){HANDLE f=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(f!=INVALID_HANDLE_VALUE){DWORD w=0;WriteFile(f,g_lg+fl,(DWORD)(hd-fl),&w,nullptr);CloseHandle(f);fl=hd;}}
        if(GetTickCount()-hb>=5000){Markerf("[hb] scanState=%ld unhooked=%d\r\n",g_scanState,g_unhooked?1:0);hb=GetTickCount();}}
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
