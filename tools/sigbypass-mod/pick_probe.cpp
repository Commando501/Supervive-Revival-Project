// pick_probe — trace UPartyManager::TryPickMyHeroAndCosmetics to see why an owned-hero click
// never sets the party member's hero (center stays "?"). Injected into the RUNNING client via
// `inject mmap <pid>` (its pick page is already decrypted, so no relaunch / menu-load crash).
//
// Chain (RE'd live): exec thunk +0x54B5380 -> impl +0x58467E0 -> action +0x5846BE0.
// Impl +0x58467E0:  r13=this(PartyManager), r15=&HeroAssetId(FPrimaryAssetId), then
//   +0x5846808  call 0x7ff6882c0730         ; members getter -> [rsp+0x40]=data, [rsp+0x48]=count
//   +0x584680D  mov rbx, [rsp+0x40]          ; <-- CP1 patch site (5 bytes: 48 8B 5C 24 40)
//   +0x5846812  movsxd rax, [rsp+0x48]       ; jmp-back target
//   ... loop members ... cmp rbx,rbp; jz +0x58468F7 (empty) ...
//
// CP1 captures {this=r13, id.Type=[r15], id.Name=[r15+8], membersData=[rsp+0x40], membersCount=[rsp+0x48]}.
// If membersCount==0 -> the client party-members array is EMPTY at pick time => the pick can't set any
// member's hero => that's the bail (fix: give the client valid party members). If >0 -> members exist and
// the drop is deeper (send/member-set gated) => add a later capture point.
//
// Build:  clang++ -shared -O2 pick_probe.cpp -o pick_probe.dll -lkernel32
// Inject: tools/inject mmap <PID> pick_probe.dll
// Marker: docs/pick-probe-marker.txt

#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\pick-probe-marker.txt";

constexpr uintptr_t kPickSiteRva = 0x584680D;   // mov rbx,[rsp+0x40]  (CP1, 5 bytes overwrite)
constexpr uintptr_t kPickContRva = 0x5846812;   // jmp-back target
constexpr uintptr_t kNamePoolRva = 0x9D81450;   // &FNamePool.Blocks[0] (Len10 layout)

struct Rec { uint64_t thisPtr, idType, idName, membData, membCount; };  // 40 bytes; stride 0x30
constexpr int MAXREC = 256;
static Rec           g_recs[MAXREC];
static volatile LONG g_recN = 0;

static uintptr_t g_modBase = 0;
static uint8_t*  g_stub    = nullptr;
static uint8_t   g_orig[5] = {0};
static volatile bool g_patched = false;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

static bool GetFNameStr(uint32_t id, char* out, int cap){
    uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva);
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

static uint8_t* NearAlloc(uintptr_t anchor, size_t sz){
    for(uintptr_t off=0x10000; off<0x7F000000ull; off+=0x10000){
        uintptr_t cands[2]={ (anchor+off)&~0xFFFFull, (anchor>off ? (anchor-off) : 0)&~0xFFFFull };
        for(int i=0;i<2;i++){
            if(!cands[i]) continue;
            void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
            if(p){ intptr_t d=(intptr_t)p-(intptr_t)anchor; if(d>(intptr_t)-0x7F000000 && d<(intptr_t)0x7F000000) return (uint8_t*)p; VirtualFree(p,0,MEM_RELEASE); }
        }
    }
    return nullptr;
}

struct Emit { uint8_t* w; };
static void EB(Emit& e, uint8_t b){ *e.w++=b; }
static void EU32(Emit& e, uint32_t v){ memcpy(e.w,&v,4); e.w+=4; }
static void EU64(Emit& e, uint64_t v){ memcpy(e.w,&v,8); e.w+=8; }

// Build CP1 stub. Jumped-to from +0x584680D (rsp unchanged). Saves scratch (rax/rcx/rdx/r10/r11) to the
// stack, records the pick args, restores, replicates `mov rbx,[rsp+0x40]`, then jmp +0x5846812.
static uint8_t* BuildStub(){
    uint8_t* p=NearAlloc(g_modBase+kPickSiteRva,0x200); if(!p)return nullptr;
    Emit e{p};
    EB(e,0x50); EB(e,0x51); EB(e,0x52);                    // push rax; push rcx; push rdx
    EB(e,0x41);EB(e,0x52); EB(e,0x41);EB(e,0x53);          // push r10; push r11    (rsp now +0x28)
    // idx = lock xadd g_recN
    EB(e,0x49);EB(e,0xBA); EU64(e,(uint64_t)&g_recN);      // mov r10, &g_recN
    EB(e,0xB9); EU32(e,1);                                  // mov ecx, 1
    EB(e,0xF0);EB(e,0x41);EB(e,0x0F);EB(e,0xC1);EB(e,0x0A);// lock xadd [r10], ecx   (ecx = old idx)
    EB(e,0x81);EB(e,0xF9); EU32(e,(uint32_t)MAXREC);       // cmp ecx, MAXREC
    EB(e,0x73); uint8_t* jae=e.w; EB(e,0x00);              // jae .skip
    uint8_t* afterJae=e.w;
    EB(e,0x48);EB(e,0x63);EB(e,0xC9);                      // movsxd rcx, ecx
    EB(e,0x48);EB(e,0x6B);EB(e,0xC9);EB(e,0x30);           // imul rcx, rcx, 0x30
    EB(e,0x49);EB(e,0xBA); EU64(e,(uint64_t)&g_recs[0]);   // mov r10, &g_recs
    EB(e,0x49);EB(e,0x01);EB(e,0xCA);                      // add r10, rcx    (rec ptr)
    EB(e,0x4D);EB(e,0x89);EB(e,0x2A);                      // mov [r10], r13          this
    EB(e,0x49);EB(e,0x8B);EB(e,0x07);                      // mov rax, [r15]          id.Type
    EB(e,0x49);EB(e,0x89);EB(e,0x42);EB(e,0x08);           // mov [r10+8], rax
    EB(e,0x49);EB(e,0x8B);EB(e,0x47);EB(e,0x08);           // mov rax, [r15+8]        id.Name
    EB(e,0x49);EB(e,0x89);EB(e,0x42);EB(e,0x10);           // mov [r10+16], rax
    EB(e,0x48);EB(e,0x8B);EB(e,0x44);EB(e,0x24);EB(e,0x68);// mov rax, [rsp+0x68]     membersData ([rsp+0x40]+0x28)
    EB(e,0x49);EB(e,0x89);EB(e,0x42);EB(e,0x18);           // mov [r10+24], rax
    EB(e,0x48);EB(e,0x8B);EB(e,0x44);EB(e,0x24);EB(e,0x70);// mov rax, [rsp+0x70]     membersCount ([rsp+0x48]+0x28)
    EB(e,0x49);EB(e,0x89);EB(e,0x42);EB(e,0x20);           // mov [r10+32], rax
    // .skip:
    *jae=(uint8_t)((intptr_t)e.w-(intptr_t)afterJae);
    EB(e,0x41);EB(e,0x5B); EB(e,0x41);EB(e,0x5A);          // pop r11; pop r10
    EB(e,0x5A); EB(e,0x59); EB(e,0x58);                    // pop rdx; pop rcx; pop rax
    EB(e,0x48);EB(e,0x8B);EB(e,0x5C);EB(e,0x24);EB(e,0x40);// mov rbx, [rsp+0x40]     (replicate)
    EB(e,0xE9);                                            // jmp rel32 -> +0x5846812
    int32_t rel=(int32_t)((intptr_t)(g_modBase+kPickContRva)-((intptr_t)e.w+4)); EU32(e,(uint32_t)rel);
    return p;
}

static void DumpRecords(){
    LONG n=g_recN; if(n>MAXREC)n=MAXREC;
    Markerf("[RESULT] TryPickMyHeroAndCosmetics hits (owned-hero clicks) = %ld\r\n",(long)g_recN);
    for(int i=0;i<n && i<40;i++){
        uint32_t tId=(uint32_t)(g_recs[i].idType&0xFFFFFFFF);
        uint32_t nId=(uint32_t)(g_recs[i].idName&0xFFFFFFFF);
        char tn[128]="?", nn[128]="?"; GetFNameStr(tId,tn,sizeof(tn)); GetFNameStr(nId,nn,sizeof(nn));
        Markerf("  [%d] this=0x%llX hero=%s:%s membersData=0x%llX **membersCount=%d**\r\n",
            i,(unsigned long long)g_recs[i].thisPtr,tn,nn,
            (unsigned long long)g_recs[i].membData,(int)(g_recs[i].membCount&0xFFFFFFFF));
    }
    Markerf("[RESULT] membersCount==0 => empty client party-members at pick time (the bail); >0 => members exist, drop is deeper.\r\n");
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    Marker("[0] pick_probe worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);

    uint8_t* site=(uint8_t*)(g_modBase+kPickSiteRva);
    // wait (should be immediate — page decrypted) for the expected bytes: 48 8B 5C 24 40
    DWORD dl=GetTickCount()+20000; bool ok=false;
    while(GetTickCount()<dl){
        if(SafeReadable(site,5) && site[0]==0x48&&site[1]==0x8B&&site[2]==0x5C&&site[3]==0x24&&site[4]==0x40){ok=true;break;}
        Sleep(50);
    }
    if(!ok){Markerf("[1] FAIL pick site not decrypted/expected: %02X %02X %02X %02X %02X\r\n",site[0],site[1],site[2],site[3],site[4]);return 2;}

    g_stub=BuildStub();
    if(!g_stub){Marker("[1] FAIL BuildStub (NearAlloc)\r\n");return 3;}
    int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)site+5));
    DWORD op=0;
    if(VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&op)){
        memcpy(g_orig,site,5);
        site[0]=0xE9; site[1]=(uint8_t)rel; site[2]=(uint8_t)(rel>>8); site[3]=(uint8_t)(rel>>16); site[4]=(uint8_t)(rel>>24);
        DWORD d=0; VirtualProtect(site,5,op,&d);
        g_patched=true;
        Markerf("[2] CP1 patched +0x584680D -> stub %p. CLICK OWNED HEROES NOW.\r\n",(void*)g_stub);
    } else { Marker("[1] FAIL VirtualProtect\r\n"); return 4; }

    DWORD patchedAt=GetTickCount(); DWORD hb=GetTickCount(); LONG lastN=0; DWORD settledAt=0; bool dumped=false;
    while(true){
        Sleep(200);
        LONG n=g_recN;
        if(n!=lastN){ lastN=n; settledAt=GetTickCount(); }
        // dump+unpatch once we have hits that settled 2s, or 45s timeout (well under the ~3-5min
        // code-integrity wall — the leave-installed 120s previously tripped it and the client exited).
        bool settled=(n>0 && settledAt && GetTickCount()-settledAt>=2000);
        bool timeout=(GetTickCount()-patchedAt>=45000);
        if(!dumped && (settled||timeout)){
            Markerf("[dump] hits=%ld (settled=%d timeout=%d)\r\n",g_recN,settled?1:0,timeout?1:0);
            DumpRecords();
            if(g_patched){DWORD o=0;if(VirtualProtect(site,5,PAGE_EXECUTE_READWRITE,&o)){memcpy(site,g_orig,5);DWORD dd=0;VirtualProtect(site,5,o,&dd);}Marker("[unpatch] CP1 restored (no persistent .text mod)\r\n");}
            dumped=true;
        }
        if(GetTickCount()-hb>=5000){Markerf("[hb] patched=%d hits=%ld dumped=%d\r\n",g_patched?1:0,g_recN,dumped?1:0);hb=GetTickCount();}
        if(dumped) break;
    }
    Marker("[done] pick_probe worker exit\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
