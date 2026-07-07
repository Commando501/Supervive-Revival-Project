// missions_populate — SESSION 52, Route A for the MISSIONS page. PHASE 1 = READ-ONLY HARNESS.
// ---------------------------------------------------------------------------------------------
// Goal (eventual): populate the live UMissionsModel's Missions/Pools TMaps + broadcast OnUpdated
// so the empty Missions modal renders tiles. See docs/session-52-missions-page-decompiled.txt.
//
// PHASE 1 (THIS FILE): pure read-only validation — NO hook, NO writes, zero crash risk. It:
//   1. Resolves the live ProgressionManager instance (class "ProgressionManager", not the CDO).
//   2. Reads ProgressionManager+0x3B8 -> MissionsModel, then that model's 3 TMaps at
//      +0x30/+0x80/+0xD0 and logs their element counts (expected 0/0/0 at menu).
//   3. Locates the mission UFunctions the write phase will call, by scanning GUObjectArray for
//      UFunction objects named CreateMissionModelFromFinalProgress / GetMissions / GetMissionModel
//      / GetActiveMissionModel / OnPSMissionsUpdated, logging their addr + Outer class.
//   4. Confirms the 16 DA_MissionPool CDOs are present (pool classes resolve).
// The marker file records everything; use it to confirm the harness before writing Phase 2.
//
// Offsets (this build; UObject Class@+0x18 Name@+0x20 Outer@+0x28; per-launch base resolved live):
//   GUObjectArray@base+0x9E38930, FNamePool@base+0x9D81450.
//   ProgressionManager.MissionsModel @ +0x3B8 (verified live S52).
//   UMissionsModel maps: Missions@+0x30, Pools@+0x80, CompletionCounts@+0xD0 (0x50 stride,
//     FScriptSet; element count = TSparseArray.ArrayNum at map+0x08).
// Build:  clang++ -shared -O2 missions_populate.cpp -o missions_populate.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/missions_populate.dll
// Marker: docs/missions-populate-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\missions-populate-marker.txt";

constexpr uintptr_t kObjObjectsRva = 0x9E38930;
constexpr uintptr_t kNamePoolRva   = 0x9D81450;
constexpr int       PERCHUNK       = 65536;
constexpr int       ITEMSTRIDE     = 0x18;
constexpr uintptr_t CLASS_OFF      = 0x18;
constexpr uintptr_t NAME_OFF       = 0x20;
constexpr uintptr_t OUTER_OFF      = 0x28;
constexpr uintptr_t PM_MISSIONSMODEL = 0x3B8;                 // ProgressionManager.MissionsModel
constexpr uintptr_t MM_MAP_MISSIONS  = 0x30;                  // UMissionsModel.Missions  (TMap)
constexpr uintptr_t MM_MAP_POOLS     = 0x80;                  // UMissionsModel.Pools     (TMap)
constexpr uintptr_t MM_MAP_COMPCOUNT = 0xD0;                  // UMissionsModel.CompletionCounts
constexpr uintptr_t SET_ARRAYNUM_OFF = 0x08;                  // TScriptArray.ArrayNum inside FScriptSet

static uintptr_t g_modBase = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
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
static bool NameIs(uintptr_t obj,const char* w){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static bool NameStr(uintptr_t obj,char* out,int cap){ return GetFNameStr(NameId(obj),out,cap); }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static uintptr_t OuterOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+OUTER_OFF),8))return 0; return *(uintptr_t*)(obj+OUTER_OFF); }
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }

// FScriptSet element count = TSparseArray.Data(TScriptArray).ArrayNum at set+0x08.
static int32_t MapNum(uintptr_t obj,uintptr_t off){ uintptr_t s=obj+off; if(!SafeReadable((void*)(s+SET_ARRAYNUM_OFF),4))return -1; return *(int32_t*)(s+SET_ARRAYNUM_OFF); }

static const char* kWantFns[5]={"CreateMissionModelFromFinalProgress","GetMissions","GetMissionModel","GetActiveMissionModel","OnPSMissionsUpdated"};

static DWORD WINAPI Worker(LPVOID){
    { HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h!=INVALID_HANDLE_VALUE)CloseHandle(h); }
    Marker("[0] missions_populate PHASE 1 (read-only harness) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; Markerf("[0] base=0x%llX\r\n",(unsigned long long)g_modBase);

    // Give the menu time to fully load the ProgressionManager + MissionsModel.
    uintptr_t oo=g_modBase+kObjObjectsRva;
    uintptr_t progMgr=0, missModel=0; int poolCdos=0, fnFound=0;
    DWORD dl=GetTickCount()+120000;
    while(GetTickCount()<dl){
        if(!SafeReadable((void*)oo,0x18)){Sleep(500);continue;}
        uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
        if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000){Sleep(500);continue;}
        int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
        progMgr=0; poolCdos=0;
        for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
            for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
                // live ProgressionManager (skip the CDO Default__ProgressionManager)
                if(!progMgr && ClassNameIs(obj,"ProgressionManager")){ char nm[96]; if(NameStr(obj,nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) progMgr=obj; }
                // count loaded MissionPool CDOs
                if(ClassNameIs(obj,"Class")){ /* skip UClass objects for pool count */ }
                char cn[96]; uintptr_t cls=ClassOf(obj);
                if(cls && GetFNameStr(NameId(cls),cn,sizeof(cn)) && strstr(cn,"MissionPool") && strstr(cn,"_C")) poolCdos++;
            }
        }
        if(progMgr) break;
        Sleep(500);
    }
    if(!progMgr){ Marker("[1] FAIL: no live ProgressionManager resolved in 120s\r\n"); return 2; }
    Markerf("[1] ProgressionManager=0x%llX  loaded MissionPool CDOs=%d\r\n",(unsigned long long)progMgr,poolCdos);

    if(SafeReadable((void*)(progMgr+PM_MISSIONSMODEL),8)) missModel=*(uintptr_t*)(progMgr+PM_MISSIONSMODEL);
    if(!LooksLikePtr(missModel)){ Markerf("[2] FAIL: MissionsModel ptr @+0x3B8 invalid (0x%llX)\r\n",(unsigned long long)missModel); return 3; }
    char mmcls[96]="?"; { uintptr_t c=ClassOf(missModel); if(c)GetFNameStr(NameId(c),mmcls,sizeof(mmcls)); }
    uintptr_t outer=OuterOf(missModel);
    Markerf("[2] MissionsModel=0x%llX class=%s outer=0x%llX (outer==ProgMgr:%d)\r\n",
            (unsigned long long)missModel,mmcls,(unsigned long long)outer,outer==progMgr?1:0);
    Markerf("[2] map counts: Missions(+0x30)=%d  Pools(+0x80)=%d  CompletionCounts(+0xD0)=%d\r\n",
            MapNum(missModel,MM_MAP_MISSIONS),MapNum(missModel,MM_MAP_POOLS),MapNum(missModel,MM_MAP_COMPCOUNT));

    // Locate the mission UFunctions the write phase will call.
    { uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14); int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
      for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!ClassNameIs(obj,"Function"))continue;
            char fn[128]; if(!NameStr(obj,fn,sizeof(fn)))continue;
            for(int w=0;w<5;w++){ if(strcmp(fn,kWantFns[w])==0){ uintptr_t ou=OuterOf(obj); char oc[96]="?"; if(ou)GetFNameStr(NameId(ou),oc,sizeof(oc));
                Markerf("[3] UFunction %-36s @0x%llX  Outer=%s\r\n",fn,(unsigned long long)obj,oc); fnFound++; break; } }
        }
      }
    }
    Markerf("[4] DONE. functions found=%d. Harness ready for Phase 2 (populate).\r\n",fnFound);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
