// gft_ready_fix — S89: flip the client's GAME-FEATURE-TOGGLE READINESS on the dedicated-server tutorial route,
// automatically, on launch. Durable version of the S89 RPM poke (tools/re/poke_toggles.py).
//
// WHY / WHAT (S89, disassembly-proven):
//   The client spams "ULokiGameFeatureToggles::Get ... called when feature toggles were not ready" until its
//   toggles are READY. On the DS route the real server never delivers them (the S88 property-array wall; the
//   S89 RPC delivers a clean block but can't POPULATE the array). The readiness GATE is NOT the array size —
//   `LokiGameplayStatics::GetFeatureTogglesReady` disassembles (its native thunk IS readable) to:
//       World = WorldContext->GetWorld();  obj = getObj(World);  sac = *(obj + 0x5A0);  return bit6(*(sac+0xB3));
//   and `GameState + 0x5A0` is verified live to be the GameState's LokiServerAuthConfig component. So readiness
//   is exactly **bit 6 of byte [LokiServerAuthConfig + 0xB3]** (an unreflected bool). Setting it makes
//   GetFeatureTogglesReady() return true. (Confirmed live: bit 0->1 flips it; client stays stable.)
//
// This shim polls GUObjectArray for every LokiServerAuthConfig and sets that bit, re-applying every ~2s so it
// stays set for the whole session (the DS server never sets/clears it). Bit-only by default (no allocation, no
// crash surface). Build with -DFILL_VALUES to ALSO fill GameFeatureToggles@+0x130 with 151 trues so value
// getters (GetGameFeatureToggleValue) return real values — off by default (a non-UE buffer would crash if the
// game ever frees/reallocs the array, and the DS spectator never queries values anyway).
//
// Build:  clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS gft_ready_fix.cpp -o gft_ready_fix.dll -lkernel32
// Inject: tools\inject\inject.exe watch-now SUPERVIVE-Win64-Shipping.exe gft_ready_fix.dll   (or launch-redirect -Hook)
// Marker: docs/gft-ready-marker.txt
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\gft-ready-marker.txt";
constexpr uintptr_t kObjObjectsRva = 0x9E38930, kNamePoolRva = 0x9D81450;
constexpr int PERCHUNK = 65536, ITEMSTRIDE = 0x18;
constexpr uintptr_t CLASS_OFF = 0x18, NAME_OFF = 0x20;
constexpr uintptr_t SAC_READY_BYTE = 0xB3;      // GetFeatureTogglesReady returns bit 6 of this byte
constexpr uint8_t   READY_BIT      = 0x40;      // bit 6
constexpr uintptr_t SAC_TOGGLES    = 0x130;     // GameFeatureToggles TArray<bool> (values; -DFILL_VALUES only)
constexpr int       TOGGLE_COUNT   = 151;       // ELokiGameFeatureToggle count

static uintptr_t g_modBase = 0;

static void Marker(const char* m){ HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h==INVALID_HANDLE_VALUE)return; DWORD w=0; WriteFile(h,m,(DWORD)strlen(m),&w,nullptr); CloseHandle(h); }
static void Markerf(const char* f,...){ char b[512]; va_list a; va_start(a,f); _vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a); va_end(a); Marker(b); }
static bool SafeReadable(const void* a,size_t sz){ MEMORY_BASIC_INFORMATION m{}; if(!VirtualQuery(a,&m,sizeof(m)))return false; if(!(m.State&MEM_COMMIT))return false; if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false; return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize; }
static bool SafeWritable(const void* a,size_t sz){ MEMORY_BASIC_INFORMATION m{}; if(!VirtualQuery(a,&m,sizeof(m)))return false; if(!(m.State&MEM_COMMIT))return false; DWORD w=m.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY); if(!w||(m.Protect&(PAGE_NOACCESS|PAGE_GUARD)))return false; return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize; }
static bool LooksLikePtr(uintptr_t v){ return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0; }
static bool GetFNameStr(uint32_t id,char* out,int cap){
    uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva); uint32_t b=id>>16,off=(id&0xFFFF)<<1;
    if(!SafeReadable(blocks+b,8))return false; uintptr_t bp=blocks[b]; if(!LooksLikePtr(bp))return false;
    if(!SafeReadable((void*)(bp+off),2))return false; uint16_t hdr=*(uint16_t*)(bp+off); int len=hdr>>6; bool wide=(hdr&1)!=0;
    if(len<=0||len>=cap)return false;
    if(wide){ for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2); } else { if(!SafeReadable((void*)(bp+off+2),len))return false; for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i]; }
    out[len]=0; return true;
}
static uint32_t NameId(uintptr_t obj){ if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0; return *(uint32_t*)(obj+NAME_OFF); }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static bool ClassName(uintptr_t obj,char* out,int cap){ uintptr_t c=ClassOf(obj); if(!c)return false; return GetFNameStr(NameId(c),out,cap); }
static bool ObjName(uintptr_t obj,char* out,int cap){ return GetFNameStr(NameId(obj),out,cap); }
template<class F> static void ForEachObject(F cb){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; if(cb(obj))return; } }
}

#ifdef FILL_VALUES
static uint8_t g_valbuf[TOGGLE_COUNT];
#endif

static DWORD WINAPI Worker(LPVOID){
    g_modBase=(uintptr_t)GetModuleHandleW(nullptr);
    Markerf("[gft-ready] injected; base=0x%llX — polling for LokiServerAuthConfig (readiness = bit6 of +0x%llX)\r\n",
            (unsigned long long)g_modBase,(unsigned long long)SAC_READY_BYTE);
#ifdef FILL_VALUES
    memset(g_valbuf,1,sizeof(g_valbuf));
    Marker("[gft-ready] FILL_VALUES on — will also fill GameFeatureToggles with 151 trues\r\n");
#endif
    int lastCount=-1;
    for(int iter=0; iter<12000; iter++){        // ~ session-long (2s cadence)
        int found=0, newlySet=0;
        ForEachObject([&](uintptr_t o)->bool{
            char cn[128]; if(!ClassName(o,cn,sizeof(cn)))return false;
            if(strcmp(cn,"LokiServerAuthConfig")!=0)return false;
            found++;
            uint8_t* rb=(uint8_t*)(o+SAC_READY_BYTE);
            if(SafeWritable(rb,1)){ if(!(*rb & READY_BIT)) newlySet++; *rb |= READY_BIT; }
#ifdef FILL_VALUES
            struct FArr{ void* Data; int32_t Num; int32_t Max; }* arr=(FArr*)(o+SAC_TOGGLES);
            if(SafeWritable(arr,16) && arr->Num<TOGGLE_COUNT){ arr->Data=g_valbuf; arr->Num=TOGGLE_COUNT; arr->Max=TOGGLE_COUNT; }
#endif
            return false;   // keep visiting (poke every instance, incl. the CDO — harmless)
        });
        if(found!=lastCount || newlySet>0){
            Markerf("[gft-ready] instances=%d, readiness bit set (newly=%d) — GetFeatureTogglesReady now TRUE\r\n",found,newlySet);
            lastCount=found;
        }
        Sleep(2000);
    }
    Marker("[gft-ready] worker loop ended\r\n");
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID){
    if(reason==DLL_PROCESS_ATTACH){ DisableThreadLibraryCalls(h); CreateThread(nullptr,0,Worker,nullptr,0,nullptr); }
    return TRUE;
}
