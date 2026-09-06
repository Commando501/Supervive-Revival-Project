// mainmenu_refresh_test — SESSION 50 Phase-3 VALIDATION (single-shot).
// Goal: prove that calling Comp_MainMenu_PartySlotSubject::Refresh() on the GAME THREAD refreshes the
// main-menu center portrait to the local party member's HeroAssetID — the last missing piece of the
// selected-hunter flow. (Session-50 pickup: the subjects are NOT currently subscribed to
// PartyModel.OnPartyUpdated in our stub, which is why the center never refreshes live; calling their
// Refresh() directly re-runs DetermineCosmeticToShow -> OnCosmeticUpdated -> spawner.SetHero -> UpdateActor.)
//
// Mechanism (all offsets = docs/session-50-pickup-mainmenu-refresh.txt, validated read-only this session):
//   ProcessEvent  @ base+0x12C5A10 (prologue `48 89 5C 24 18` = mov [rsp+0x18],rbx — 5 relocatable bytes).
//   We INLINE-hook PE entry (5-byte E9 jmp -> HookStub) with a callable trampoline (stolen 5B + jmp PE+5).
//   HookStub (runs on WHATEVER thread calls PE) saves volatiles, calls OnPE(), restores, tail-jmps tramp.
//   OnPE(): if !g_pending or g_inHook or not-game-thread -> return; else set g_inHook, ProcessEvent(Refresh)
//           on each live subject via the trampoline (nested PE calls fast-return via g_inHook), clear
//           g_pending, set g_done. => Refresh executes on the GAME THREAD exactly like the game's own call.
//   Worker: resolve subjects + Refresh UFunc (GUObjectArray iterate), patch PE, arm g_pending, wait g_done,
//           UNPATCH (short-lived .text mod << the ~3-5min integrity wall), log. VEH crash logger captures RVA.
//
// UObject layout THIS build: Class@+0x18, Name(FName)@+0x20, Outer@+0x28.
// GUObjectArray.ObjObjects @ base+0x9E38930 (Objects**@+0, NumElements@+0x14; PerChunk 65536, stride 0x18).
// FNamePool @ base+0x9D81450 (Len10). GGameThreadId @ base+0x9D49158.
// PartyMemberModel.HeroAssetID @ +0x78 (type FName@+0x78=Hero 0x1A568, name FName@+0x80) — for logging.
//
// Build:  clang++ -shared -O2 mainmenu_refresh_test.cpp -o mainmenu_refresh_test.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/mainmenu_refresh_test.dll
// Marker: docs/mainmenu-refresh-marker.txt   Crash: docs/mainmenu-refresh-crash.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\mainmenu-refresh-marker.txt";
static const char* kCrashPath  = "G:\\git\\Supervive Revival Project\\docs\\mainmenu-refresh-crash.txt";

constexpr uintptr_t kPeRva        = 0x12C5A10;    // UObject::ProcessEvent
constexpr uintptr_t kObjObjectsRva= 0x9E38930;
constexpr uintptr_t kNamePoolRva  = 0x9D81450;
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr int       PERCHUNK      = 65536;
constexpr int       ITEMSTRIDE    = 0x18;
constexpr uintptr_t CLASS_OFF     = 0x18;
constexpr uintptr_t NAME_OFF      = 0x20;
constexpr uintptr_t OUTER_OFF     = 0x28;
constexpr uintptr_t MEMBER_HEROID = 0x78;
constexpr uint32_t  HERO_TYPE     = 0x1A568;

static const uint8_t kPeProlog[5] = {0x48,0x89,0x5C,0x24,0x18};   // expected: mov [rsp+0x18], rbx

typedef void (*PFN_PE)(void* obj, void* func, void* parms);

static uintptr_t   g_modBase   = 0;
static volatile PFN_PE g_tramp = nullptr;         // callable trampoline = original ProcessEvent
static void*       g_refreshFn = nullptr;         // Refresh UFunction*
static void*       g_subjects[8] = {0};
static int         g_nsubj     = 0;
static volatile long g_pending = 0;
static volatile long g_inHook  = 0;
static volatile long g_done    = 0;
static DWORD       g_gameTid   = 0;
static volatile long  g_peHitsAny = 0;   // EVERY PE entry (any thread) — did the hook fire at all?
static volatile long  g_peHitsGT  = 0;   // PE entries on the game thread
static volatile DWORD g_firstTid  = 0;   // TID of the first PE entry seen

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
static uint32_t NameId(uintptr_t obj){ if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0; return *(uint32_t*)(obj+NAME_OFF); }
static bool NameIs(uintptr_t obj, const char* want){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,want)==0; }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static uintptr_t OuterOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+OUTER_OFF),8))return 0; return *(uintptr_t*)(obj+OUTER_OFF); }

// ─────────── VEH crash logger (from catalog_ready_fix) ───────────
struct ModRange { uint64_t base, end; char name[64]; };
static ModRange g_mods[192]; static volatile long g_modCount=0; static volatile long g_crashSeq=0;
static void SnapshotModules(){
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());
    if(snap==INVALID_HANDLE_VALUE)return; MODULEENTRY32 me; me.dwSize=sizeof(me); int n=0;
    if(Module32First(snap,&me)){ do{ if(n>=192)break; ModRange&r=g_mods[n]; r.base=(uint64_t)me.modBaseAddr; r.end=r.base+me.modBaseSize; int i=0; for(;i<63&&me.szModule[i];i++)r.name[i]=(char)me.szModule[i]; r.name[i]=0; n++; }while(Module32Next(snap,&me)); }
    CloseHandle(snap); InterlockedExchange(&g_modCount,n);
}
static void HxU64(char* o,uint64_t v){const char* d="0123456789ABCDEF";for(int i=15;i>=0;i--){o[i]=d[(int)(v&0xF)];v>>=4;}}
static void CWrite(HANDLE h,const char* s,DWORD n){DWORD w=0;WriteFile(h,s,n,&w,0);}
static void CKV(HANDLE h,const char* k,uint64_t v){char b[96];int p=0;while(k[p]&&p<40){b[p]=k[p];p++;}b[p++]='=';b[p++]='0';b[p++]='x';HxU64(b+p,v);p+=16;b[p++]='\r';b[p++]='\n';CWrite(h,b,(DWORD)p);}
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode;
    bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0x80000003||code==0xC0000374||code==0xC00000FD||code==0xC0000094||code==0xC0000095||code==0xC0000096;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH;
    long seq=InterlockedIncrement(&g_crashSeq); if(seq>64)return EXCEPTION_CONTINUE_SEARCH;
    HANDLE h=CreateFileA(kCrashPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h==INVALID_HANDLE_VALUE)return EXCEPTION_CONTINUE_SEARCH;
    CWrite(h,"=== VEH fatal exception ===\r\n",29); CKV(h,"seq",(uint64_t)seq); CKV(h,"code",code);
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip; CKV(h,"RIP",rip);
    if(g_modBase && rip>g_modBase && rip<g_modBase+0xC000000) CKV(h,"SUPERVIVE_RVA",rip-g_modBase);
    long mc=g_modCount; bool named=false;
    for(long i=0;i<mc;i++){ if(rip>=g_mods[i].base && rip<g_mods[i].end){ CWrite(h,"module=",7); CWrite(h,g_mods[i].name,(DWORD)strlen(g_mods[i].name)); CWrite(h,"\r\n",2); CKV(h,"module_RVA",rip-g_mods[i].base); named=true; break; } }
    if(!named)CWrite(h,"module=UNKNOWN\r\n",16);
    if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2){ CKV(h,"av_op",ep->ExceptionRecord->ExceptionInformation[0]); CKV(h,"av_addr",ep->ExceptionRecord->ExceptionInformation[1]); }
    CKV(h,"Rcx",c->Rcx);CKV(h,"Rdx",c->Rdx);CKV(h,"R8",c->R8);CKV(h,"Rsp",c->Rsp);CKV(h,"Rbp",c->Rbp);CKV(h,"inHook",(uint64_t)g_inHook);CKV(h,"pending",(uint64_t)g_pending);
    CWrite(h,"=== end ===\r\n\r\n",15); FlushFileBuffers(h); CloseHandle(h);
    return EXCEPTION_CONTINUE_SEARCH;
}

// ─────────── the game-thread callback ───────────
extern "C" void OnPE(void* /*obj*/, void* /*func*/, void* /*parms*/){
    InterlockedIncrement(&g_peHitsAny);
    DWORD tid=GetCurrentThreadId();
    if(!g_firstTid) g_firstTid=tid;
    if(tid==g_gameTid) InterlockedIncrement(&g_peHitsGT);
    if(!g_pending) return;
    if(g_inHook)   return;
    if(tid!=g_gameTid) return;                     // only ACT on the game thread (PE is called on others too)
    g_inHook=1;
    for(int i=0;i<g_nsubj;i++){
        if(g_subjects[i] && g_refreshFn && g_tramp) g_tramp(g_subjects[i], g_refreshFn, nullptr);
    }
    g_pending=0;
    g_done=1;
    g_inHook=0;
}

// ─────────── build trampoline + HookStub near PE ───────────
static uint8_t* NearAlloc(uintptr_t anchor, size_t sz){
    for(uintptr_t off=0x10000; off<0x7F000000ull; off+=0x10000){
        uintptr_t cands[2]={ (anchor+off)&~0xFFFFull, (anchor>off?(anchor-off):0)&~0xFFFFull };
        for(int i=0;i<2;i++){ if(!cands[i])continue;
            void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
            if(p){ intptr_t d=(intptr_t)p-(intptr_t)anchor; if(d>(intptr_t)-0x7F000000 && d<(intptr_t)0x7F000000) return (uint8_t*)p; VirtualFree(p,0,MEM_RELEASE); }
        }
    }
    return nullptr;
}
struct Emit{ uint8_t* w; };
static void EB(Emit&e,uint8_t b){*e.w++=b;}
static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;}
static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}

// Returns HookStub address; sets g_tramp (callable original). exec block layout:
//   [0x00] trampoline: <5 stolen bytes> E9 rel32(->PE+5)
//   [0x20] HookStub
static uint8_t* BuildHook(uintptr_t pe, const uint8_t stolen[5]){
    uint8_t* blk=NearAlloc(pe,0x200); if(!blk)return nullptr;
    // trampoline @ blk+0
    Emit t{blk};
    for(int i=0;i<5;i++)EB(t,stolen[i]);
    EB(t,0xE9); int32_t rel=(int32_t)((intptr_t)(pe+5)-((intptr_t)t.w+4)); EU32(t,(uint32_t)rel);
    g_tramp=(PFN_PE)blk;
    // HookStub @ blk+0x20
    uint8_t* stub=blk+0x20; Emit e{stub};
    EB(e,0x51);                              // push rcx
    EB(e,0x52);                              // push rdx
    EB(e,0x41);EB(e,0x50);                   // push r8
    EB(e,0x41);EB(e,0x51);                   // push r9
    EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);          // sub rsp,0x28   (align + shadow)
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnPE);        // mov rax,&OnPE   (rcx/rdx/r8 still = obj/func/parms)
    EB(e,0xFF);EB(e,0xD0);                                // call rax
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);          // add rsp,0x28
    EB(e,0x41);EB(e,0x59);                   // pop r9
    EB(e,0x41);EB(e,0x58);                   // pop r8
    EB(e,0x5A);                              // pop rdx
    EB(e,0x59);                              // pop rcx
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk);          // mov rax, trampoline
    EB(e,0xFF);EB(e,0xE0);                                // jmp rax  (tail-call original)
    return stub;
}

static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// Single pass over GUObjectArray: resolve subjClass, the 4 real subjects, the Refresh UFunc, the live member.
static void ResolveObjects(uintptr_t* outMember){
    uintptr_t oo=g_modBase+kObjObjectsRva;
    if(!SafeReadable((void*)oo,0x18)){Marker("[res] ObjObjects unreadable\r\n");return;}
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000){Marker("[res] bad ObjObjects\r\n");return;}
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    uintptr_t subjClass=0, member=0;
    // pass A: find subjClass (object named the class, whose own class name contains "Class")
    for(int ci=0;ci<numChunks && !subjClass;ci++){
        if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8);
        if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue;
            uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,"Comp_MainMenu_PartySlotSubject_C")){
                uintptr_t cls=ClassOf(obj); char cn[96]="?"; if(cls)GetFNameStr(NameId(cls),cn,sizeof(cn));
                if(strstr(cn,"Class")){ subjClass=obj; break; }
            }
        }
    }
    if(!subjClass){Marker("[res] subjClass NOT FOUND\r\n");return;}
    Markerf("[res] subjClass=0x%llX\r\n",(unsigned long long)subjClass);
    // pass B: subjects (class==subjClass, name==Comp_MainMenu_PartySubject) + Refresh UFunc + live member
    for(int ci=0;ci<numChunks;ci++){
        if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8);
        if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue;
            uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassOf(obj)==subjClass && g_nsubj<8 && NameIs(obj,"Comp_MainMenu_PartySubject")) g_subjects[g_nsubj++]=(void*)obj;
            else if(!g_refreshFn && NameIs(obj,"Refresh") && OuterOf(obj)==subjClass) g_refreshFn=(void*)obj;
            else if(!member){ uintptr_t cls=ClassOf(obj); if(cls){ char cn[96]; if(GetFNameStr(NameId(cls),cn,sizeof(cn))&&strcmp(cn,"PartyMemberModel")==0){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) member=obj; } } }
        }
    }
    *outMember=member;
    Markerf("[res] subjects=%d refreshFn=0x%llX member=0x%llX\r\n",g_nsubj,(unsigned long long)g_refreshFn,(unsigned long long)member);
    for(int i=0;i<g_nsubj;i++)Markerf("   subject[%d]=0x%llX\r\n",i,(unsigned long long)g_subjects[i]);
}

static void LogMemberHero(uintptr_t member,const char* tag){
    if(!member||!SafeReadable((void*)(member+MEMBER_HEROID),16)){Markerf("[%s] member hero: <unreadable>\r\n",tag);return;}
    uint32_t type=*(uint32_t*)(member+MEMBER_HEROID); uint32_t name=*(uint32_t*)(member+MEMBER_HEROID+8);
    char nm[96]="<none>"; if(name)GetFNameStr(name,nm,sizeof(nm));
    Markerf("[%s] member.HeroAssetID = %s (type=0x%X)\r\n",tag,nm,type);
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    { HANDLE ch=CreateFileA(kCrashPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] mainmenu_refresh_test worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);
    SnapshotModules(); AddVectoredExceptionHandler(1,CrashVEH); Marker("[0] crash-VEH installed\r\n");

    g_gameTid=WaitTid(60000); if(!g_gameTid){Marker("[1] FAIL GGameThreadId\r\n");return 2;} Markerf("[1] GGameThreadId=%lu\r\n",g_gameTid);

    uintptr_t member=0; ResolveObjects(&member);
    if(g_nsubj==0||!g_refreshFn){Marker("[2] FAIL: subjects/refreshFn not resolved -> abort (no patch)\r\n");return 3;}
    LogMemberHero(member,"before");

    // verify + steal PE prologue
    uint8_t* pe=(uint8_t*)(g_modBase+kPeRva);
    if(!SafeReadable(pe,5)){Marker("[2] FAIL PE unreadable\r\n");return 4;}
    uint8_t stolen[5]; memcpy(stolen,pe,5);
    if(memcmp(stolen,kPeProlog,5)!=0){Markerf("[2] FAIL PE prologue mismatch: %02X %02X %02X %02X %02X\r\n",stolen[0],stolen[1],stolen[2],stolen[3],stolen[4]);return 5;}

    uint8_t* stub=BuildHook((uintptr_t)pe,stolen);
    if(!stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 6;}
    Markerf("[2] tramp=%p stub=%p — patching PE\r\n",(void*)g_tramp,(void*)stub);

    // patch PE entry: E9 rel32 -> stub
    int32_t rel=(int32_t)((intptr_t)stub-((intptr_t)pe+5)); DWORD op=0;
    if(!VirtualProtect(pe,5,PAGE_EXECUTE_READWRITE,&op)){Marker("[2] FAIL VirtualProtect\r\n");return 7;}
    g_pending=1;                                   // arm BEFORE the jmp is visible so the first game-thread PE acts
    pe[0]=0xE9; pe[1]=(uint8_t)rel; pe[2]=(uint8_t)(rel>>8); pe[3]=(uint8_t)(rel>>16); pe[4]=(uint8_t)(rel>>24);
    DWORD d=0; VirtualProtect(pe,5,op,&d);
    Marker("[3] PE hooked + armed (60s window) — FOCUS the game + move the mouse over the menu to fire a PE...\r\n");

    DWORD dl=GetTickCount()+60000, lastHb=0;
    while(!g_done && GetTickCount()<dl){
        if(GetTickCount()-lastHb>=3000){ Markerf("[hb] peHitsAny=%ld peHitsGT=%ld firstTid=%lu done=%ld\r\n",(long)g_peHitsAny,(long)g_peHitsGT,g_firstTid,(long)g_done); lastHb=GetTickCount(); }
        Sleep(20);
    }

    // UNPATCH (restore original 5 bytes) — keep the .text mod lifetime tiny
    DWORD o2=0; if(VirtualProtect(pe,5,PAGE_EXECUTE_READWRITE,&o2)){ memcpy(pe,stolen,5); DWORD dd=0; VirtualProtect(pe,5,o2,&dd); }
    Markerf("[4] PE unhooked. g_done=%ld peHitsAny=%ld peHitsGT=%ld firstTid=%lu\r\n",(long)g_done,(long)g_peHitsAny,(long)g_peHitsGT,g_firstTid);
    if(g_done){ Sleep(300); LogMemberHero(member,"after"); Marker("[RESULT] Refresh() called on game thread — CHECK the main-menu center portrait now (should show Brall/Ronin).\r\n"); }
    else if(g_peHitsAny==0) Marker("[RESULT] TIMEOUT: ProcessEvent NEVER fired via our hook in 60s — PE entry not on the hot path, or menu fully idle.\r\n");
    else Markerf("[RESULT] TIMEOUT: PE fired %ld times but 0 on game thread (firstTid=%lu vs gameTid=%lu) — thread mismatch.\r\n",(long)g_peHitsAny,g_firstTid,g_gameTid);

    // linger briefly so a late crash still logs via VEH, then exit worker (leave VEH installed).
    Sleep(4000);
    Marker("[done] worker exit\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
