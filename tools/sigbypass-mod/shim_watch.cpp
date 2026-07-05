// shim_watch — Phase 1 of the selection-watcher shim (READ-ONLY, no writes, no hooks, no native calls).
// Validates in-process: iterate GUObjectArray by class, find the live PartyMemberModel + all WBP_HeroPicker
// instances, and poll each picker's SelectedHeroAsset — logging which picker tracks the user's click and how
// it relates to the party member's HeroAssetID. This confirms the object-finding + input signal + which
// picker is "active" before Phase 2 adds the member write and Phase 3 the game-thread refresh.
//
// Offset map (docs/session-49-click-center-offline-model.txt, LIVE SESSION 4):
//   GUObjectArray.ObjObjects @ base+0x9E38930 : Objects(FUObjectItem**)@+0, NumElements(int32)@+0x14.
//     PerChunk 65536, FUObjectItem stride 0x18 (Object ptr @ item+0).
//   UObject THIS build: Class@+0x18, Name(FName)@+0x20 ; FNamePool @ base+0x9D81450 (Len10 layout).
//   PartyMemberModel.HeroAssetID @ +0x78 (type FName@+0x78=Hero 0x1A568, name FName@+0x80).
//   WBP_HeroPicker_C.SelectedHeroAsset @ +0x10D8 (type@+0x10D8, name@+0x10E0).
//
// Build:  clang++ -shared -O2 shim_watch.cpp -o shim_watch.dll -lkernel32
// Inject: tools/inject mmap <PID> shim_watch.dll   (into the running client)
// Marker: docs/shim-watch-marker.txt
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\shim-watch-marker.txt";

constexpr uintptr_t kObjObjectsRva = 0x9E38930;   // FChunkedFixedUObjectArray
constexpr uintptr_t kNamePoolRva   = 0x9D81450;
constexpr int       PERCHUNK       = 65536;
constexpr int       ITEMSTRIDE     = 0x18;
constexpr uintptr_t CLASS_OFF      = 0x18;
constexpr uintptr_t NAME_OFF       = 0x20;
constexpr uintptr_t MEMBER_HEROID  = 0x78;        // PrimaryAssetId (type@+0x78, name@+0x80)
constexpr uintptr_t PICKER_SELHERO = 0x10D8;      // PrimaryAssetId (type@+0x10D8, name@+0x10E0)
constexpr uint32_t  HERO_TYPE      = 0x1A568;

static uintptr_t g_base = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

// FName -> string (Len10 layout, from pick_probe). id: block=id>>16, off=(id&0xFFFF)<<1.
static bool GetFNameStr(uint32_t id, char* out, int cap){
    uintptr_t* blocks=(uintptr_t*)(g_base+kNamePoolRva);
    uint32_t b=id>>16, off=(id&0xFFFF)<<1;
    if(!SafeReadable(blocks+b,8)) return false;
    uintptr_t bp=blocks[b]; if(!LooksLikePtr(bp)) return false;
    if(!SafeReadable((void*)(bp+off),2)) return false;
    uint16_t hdr=*(uint16_t*)(bp+off); int len=hdr>>6; bool wide=(hdr&1)!=0;
    if(len<=0||len>=cap) return false;
    if(wide){ if(!SafeReadable((void*)(bp+off+2),len*2))return false; for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2); }
    else    { if(!SafeReadable((void*)(bp+off+2),len))  return false; for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i]; }
    out[len]=0; return true;
}
static bool ClassNameIs(uintptr_t obj, const char* want){
    if(!SafeReadable((void*)(obj+CLASS_OFF),8)) return false;
    uintptr_t cls=*(uintptr_t*)(obj+CLASS_OFF); if(!LooksLikePtr(cls)) return false;
    if(!SafeReadable((void*)(cls+NAME_OFF),4)) return false;
    char nm[128]; if(!GetFNameStr(*(uint32_t*)(cls+NAME_OFF),nm,sizeof(nm))) return false;
    return strcmp(nm,want)==0;
}
static const char* ObjName(uintptr_t obj, char* buf, int cap){
    if(SafeReadable((void*)(obj+NAME_OFF),4) && GetFNameStr(*(uint32_t*)(obj+NAME_OFF),buf,cap)) return buf;
    buf[0]='?'; buf[1]=0; return buf;
}

// Iterate GUObjectArray; collect up to `cap` objects whose class name == want. Returns count.
static int FindByClass(const char* want, uintptr_t* out, int cap){
    uintptr_t oo=g_base+kObjObjectsRva;
    if(!SafeReadable((void*)oo,0x18)) return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>4000000) return 0;
    int n=0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0; ci<numChunks && n<cap; ci++){
        if(!SafeReadable((void*)(objectsPtr+ci*8),8)) break;
        uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk)) continue;
        int cnt = (ci==numChunks-1) ? (numEl-ci*PERCHUNK) : PERCHUNK;
        for(int j=0;j<cnt && n<cap;j++){
            uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE;
            if(!SafeReadable((void*)item,8)) continue;
            uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj)) continue;
            if(ClassNameIs(obj,want)) out[n++]=obj;
        }
    }
    return n;
}
// read a PrimaryAssetId {typeFName, nameFName} at obj+off; return name FName id (0 if type!=Hero/unreadable)
static uint32_t ReadHeroPA(uintptr_t obj, uintptr_t off){
    if(!SafeReadable((void*)(obj+off),16)) return 0;
    uint32_t type=*(uint32_t*)(obj+off);
    if(type!=HERO_TYPE) return 0;
    return *(uint32_t*)(obj+off+8);
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] shim_watch worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_base=(uintptr_t)hExe;
    Markerf("[0] base=0x%llX\r\n",(unsigned long long)g_base);

    // sanity: resolve a known FName (Hero) to confirm the pool layout in-process
    { char nm[64]; if(GetFNameStr(HERO_TYPE,nm,sizeof(nm))) Markerf("[0] FName(0x1A568)=\"%s\"\r\n",nm); else Marker("[0] FName resolve FAILED\r\n"); }

    uintptr_t pickers[16]; uintptr_t members[8];
    uint32_t lastSel[16]={0}; bool init=false;
    DWORD lastFind=0, lastHb=0, start=GetTickCount();
    while(GetTickCount()-start < 600000){   // run 10 min
        // (re)discover objects every 2s (widgets get rebuilt on nav -> instances change)
        if(GetTickCount()-lastFind>=2000 || !init){
            lastFind=GetTickCount();
            int np=FindByClass("WBP_HeroPicker_C",pickers,16);
            int nm=FindByClass("PartyMemberModel",members,8);
            // member: pick the non-CDO (Name != "Default__...") — log its hero
            uintptr_t liveMember=0; for(int i=0;i<nm;i++){ char b[96]; ObjName(members[i],b,sizeof(b)); if(strncmp(b,"Default__",9)!=0){ liveMember=members[i]; } }
            uint32_t memHero = liveMember? ReadHeroPA(liveMember,MEMBER_HEROID):0;
            char mh[64]="<none>"; if(memHero) GetFNameStr(memHero,mh,sizeof(mh));
            if(!init){
                Markerf("[find] pickers=%d members=%d liveMember=0x%llX HeroAssetID=Hero:%s\r\n",np,nm,(unsigned long long)liveMember,mh);
                for(int i=0;i<np && i<16;i++){
                    char nmb[96]; ObjName(pickers[i],nmb,sizeof(nmb));
                    uint32_t s=ReadHeroPA(pickers[i],PICKER_SELHERO); char sb[64]="None"; if(s)GetFNameStr(s,sb,sizeof(sb));
                    Markerf("   picker[%d]=0x%llX Name=%s SelectedHeroAsset=Hero:%s\r\n",i,(unsigned long long)pickers[i],nmb,sb);
                    lastSel[i]=s;
                }
                init=true;
            } else {
                // detect SelectedHeroAsset changes on any picker
                for(int i=0;i<np && i<16;i++){
                    uint32_t s=ReadHeroPA(pickers[i],PICKER_SELHERO);
                    if(s!=lastSel[i]){
                        char sb[64]="None"; if(s)GetFNameStr(s,sb,sizeof(sb));
                        char nmb[96]; ObjName(pickers[i],nmb,sizeof(nmb));
                        Markerf("[CHANGE] picker[%d]=0x%llX %s SelectedHeroAsset -> Hero:%s  (member=Hero:%s)\r\n",
                            i,(unsigned long long)pickers[i],nmb,sb,mh);
                        lastSel[i]=s;
                    }
                }
            }
        }
        if(GetTickCount()-lastHb>=10000){Marker("[hb] watching...\r\n");lastHb=GetTickCount();}
        Sleep(120);
    }
    Marker("[done] shim_watch exit\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
