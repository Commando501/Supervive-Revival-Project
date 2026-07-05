// mainmenu_refresh — SESSION 50 Phase-3 DELIVERABLE (continuous).
// Closes the last gap in the selected-hunter flow: when the user picks a hunter, refresh the MAIN-MENU
// center portrait LIVE (like the original). Combines the proven Phase-1/2 MIRROR (shim_watch: active picker
// SelectedHeroAsset -> local party member HeroAssetID) with a per-pick GAME-THREAD ProcessEvent hook that
// calls Comp_MainMenu_PartySlotSubject::Refresh() (re-runs DetermineCosmeticToShow -> OnCosmeticUpdated ->
// spawner.SetHero -> UpdateActor). The subjects are NOT subscribed to PartyModel.OnPartyUpdated in our stub
// (verified S50), which is why the center never refreshed on its own; calling Refresh() directly fixes it.
//
// Per pick: mirror member=pick, then briefly install the PE .text hook (<4s, << the ~3-5min integrity wall);
// the next game-thread ProcessEvent runs OnPE -> Refresh() on all live subjects -> uninstall. Between picks
// PE is UNPATCHED (no overhead, no wall risk). VEH crash logger captures any fault RVA.
//
// Offsets (docs/session-50-pickup-mainmenu-refresh.txt, verified read-only S50):
//   ProcessEvent @ base+0x12C5A10 (prologue 48 89 5C 24 18 = mov [rsp+0x18],rbx; 5 relocatable bytes).
//   GUObjectArray.ObjObjects @ base+0x9E38930 (Objects**@+0, NumElements@+0x14; PerChunk 65536, stride 0x18).
//   FNamePool @ base+0x9D81450 (Len10). GGameThreadId @ base+0x9D49158.
//   UObject: Class@+0x18, Name@+0x20, Outer@+0x28. PartyMemberModel.HeroAssetID @+0x78 (Hero type 0x1A568).
//   WBP_HeroPicker_C.SelectedHeroAsset @+0x10D8. Comp_MainMenu_PartySlotSubject_C::Refresh (Outer==subjClass).
//
// Build:  clang++ -shared -O2 mainmenu_refresh.cpp -o mainmenu_refresh.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/mainmenu_refresh.dll
// Marker: docs/mainmenu-refresh-marker.txt   Crash: docs/mainmenu-refresh-crash.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\mainmenu-refresh-marker.txt";
static const char* kCrashPath  = "G:\\git\\Supervive Revival Project\\docs\\mainmenu-refresh-crash.txt";

constexpr uintptr_t kPeRva        = 0x12C5A10;
constexpr uintptr_t kObjObjectsRva= 0x9E38930;
constexpr uintptr_t kNamePoolRva  = 0x9D81450;
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr int       PERCHUNK      = 65536;
constexpr int       ITEMSTRIDE    = 0x18;
constexpr uintptr_t CLASS_OFF     = 0x18;
constexpr uintptr_t NAME_OFF      = 0x20;
constexpr uintptr_t OUTER_OFF     = 0x28;
constexpr uintptr_t MEMBER_HEROID = 0x78;
constexpr uintptr_t PICKER_SELHERO= 0x10D8;
constexpr uint32_t  HERO_TYPE     = 0x1A568;
static const uint8_t kPeProlog[5] = {0x48,0x89,0x5C,0x24,0x18};

typedef void (*PFN_PE)(void* obj, void* func, void* parms);

static uintptr_t   g_modBase   = 0;
static volatile PFN_PE g_tramp = nullptr;
static void*       g_refreshFn = nullptr;
static uintptr_t   g_subjClass = 0;
static void*       g_subjects[8] = {0};
static int         g_nsubj     = 0;
static uintptr_t   g_member    = 0;
static uint8_t*    g_pe        = nullptr;
static uint8_t     g_stolen[5] = {0};
static volatile long g_pending = 0;
static volatile long g_inHook  = 0;
static volatile long g_done    = 0;
static volatile long g_refreshes = 0;   // total successful game-thread Refresh cycles
static DWORD       g_gameTid   = 0;

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
static bool NameIs(uintptr_t obj,const char* w){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static uintptr_t OuterOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+OUTER_OFF),8))return 0; return *(uintptr_t*)(obj+OUTER_OFF); }
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }
// read PrimaryAssetId(Hero) name id at obj+off; 0 if type!=Hero
static uint32_t ReadHeroPA(uintptr_t obj,uintptr_t off){ if(!SafeReadable((void*)(obj+off),16))return 0; if(*(uint32_t*)(obj+off)!=HERO_TYPE)return 0; return *(uint32_t*)(obj+off+8); }

// ─────────── VEH crash logger ───────────
struct ModRange{uint64_t base,end;char name[64];};
static ModRange g_mods[192]; static volatile long g_modCount=0; static volatile long g_crashSeq=0;
static void SnapshotModules(){HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());if(snap==INVALID_HANDLE_VALUE)return;MODULEENTRY32 me;me.dwSize=sizeof(me);int n=0;if(Module32First(snap,&me)){do{if(n>=192)break;ModRange&r=g_mods[n];r.base=(uint64_t)me.modBaseAddr;r.end=r.base+me.modBaseSize;int i=0;for(;i<63&&me.szModule[i];i++)r.name[i]=(char)me.szModule[i];r.name[i]=0;n++;}while(Module32Next(snap,&me));}CloseHandle(snap);InterlockedExchange(&g_modCount,n);}
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
    CWrite(h,"=== VEH fatal ===\r\n",19); CKV(h,"seq",(uint64_t)seq); CKV(h,"code",code);
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip; CKV(h,"RIP",rip);
    if(g_modBase && rip>g_modBase && rip<g_modBase+0xC000000) CKV(h,"SUPERVIVE_RVA",rip-g_modBase);
    long mc=g_modCount; bool named=false;
    for(long i=0;i<mc;i++){ if(rip>=g_mods[i].base && rip<g_mods[i].end){ CWrite(h,"module=",7); CWrite(h,g_mods[i].name,(DWORD)strlen(g_mods[i].name)); CWrite(h,"\r\n",2); CKV(h,"module_RVA",rip-g_mods[i].base); named=true; break; } }
    if(!named)CWrite(h,"module=UNKNOWN\r\n",16);
    if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2){ CKV(h,"av_op",ep->ExceptionRecord->ExceptionInformation[0]); CKV(h,"av_addr",ep->ExceptionRecord->ExceptionInformation[1]); }
    CKV(h,"Rcx",c->Rcx);CKV(h,"Rdx",c->Rdx);CKV(h,"R8",c->R8);CKV(h,"inHook",(uint64_t)g_inHook);
    CWrite(h,"=== end ===\r\n\r\n",15); FlushFileBuffers(h); CloseHandle(h);
    return EXCEPTION_CONTINUE_SEARCH;
}

// ─────────── game-thread callback ───────────
extern "C" void OnPE(void*,void*,void*){
    if(!g_pending) return;
    if(g_inHook)   return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    g_inHook=1;
    for(int i=0;i<g_nsubj;i++){ if(g_subjects[i]&&g_refreshFn&&g_tramp) g_tramp(g_subjects[i],g_refreshFn,nullptr); }
    g_pending=0; g_done=1; InterlockedIncrement(&g_refreshes);
    g_inHook=0;
}

// ─────────── hook build (once) + install/uninstall (per pick) ───────────
static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){
    for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){
        uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};
        for(int i=0;i<2;i++){ if(!cands[i])continue;
            void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
            if(p){ intptr_t d=(intptr_t)p-(intptr_t)anchor; if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000) return (uint8_t*)p; VirtualFree(p,0,MEM_RELEASE); }
        }
    }
    return nullptr;
}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
static uint8_t* BuildHook(uintptr_t pe,const uint8_t stolen[5]){
    uint8_t* blk=NearAlloc(pe,0x200); if(!blk)return nullptr;
    Emit t{blk}; for(int i=0;i<5;i++)EB(t,stolen[i]); EB(t,0xE9); int32_t rel=(int32_t)((intptr_t)(pe+5)-((intptr_t)t.w+4)); EU32(t,(uint32_t)rel);
    g_tramp=(PFN_PE)blk;
    uint8_t* stub=blk+0x20; Emit e{stub};
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);          // push rcx/rdx/r8/r9
    EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);                                // sub rsp,0x28
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnPE); EB(e,0xFF);EB(e,0xD0);       // mov rax,&OnPE; call rax
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);                                // add rsp,0x28
    EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);          // pop r9/r8/rdx/rcx
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk); EB(e,0xFF);EB(e,0xE0);         // mov rax,tramp; jmp rax
    return stub;
}
static uint8_t* g_stub=nullptr;
static bool InstallHook(){ if(!g_pe||!g_stub)return false; int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pe+5)); DWORD op=0; if(!VirtualProtect(g_pe,5,PAGE_EXECUTE_READWRITE,&op))return false; g_pe[0]=0xE9;g_pe[1]=(uint8_t)rel;g_pe[2]=(uint8_t)(rel>>8);g_pe[3]=(uint8_t)(rel>>16);g_pe[4]=(uint8_t)(rel>>24); DWORD d=0;VirtualProtect(g_pe,5,op,&d); return true; }
static void UninstallHook(){ if(!g_pe)return; DWORD op=0; if(VirtualProtect(g_pe,5,PAGE_EXECUTE_READWRITE,&op)){ memcpy(g_pe,g_stolen,5); DWORD d=0; VirtualProtect(g_pe,5,op,&d); } }

static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// Resolve subjClass + subjects + refreshFn + live member (subjects/class/fn stable; re-callable to refill).
static void ResolveSubjects(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    if(!g_subjClass){
        for(int ci=0;ci<numChunks && !g_subjClass;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
            for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
                if(NameIs(obj,"Comp_MainMenu_PartySlotSubject_C")){ uintptr_t cls=ClassOf(obj); char cn[96]="?"; if(cls)GetFNameStr(NameId(cls),cn,sizeof(cn)); if(strstr(cn,"Class")){ g_subjClass=obj; break; } } } }
    }
    if(!g_subjClass)return;
    g_nsubj=0; g_member=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassOf(obj)==g_subjClass && g_nsubj<8 && NameIs(obj,"Comp_MainMenu_PartySubject")) g_subjects[g_nsubj++]=(void*)obj;
            else if(!g_refreshFn && NameIs(obj,"Refresh") && OuterOf(obj)==g_subjClass) g_refreshFn=(void*)obj;
            else if(!g_member && ClassNameIs(obj,"PartyMemberModel")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) g_member=obj; }
        }
    }
}
// Find WBP_HeroPicker_C instances; return the active one's SelectedHeroAsset name id (0 if none valid).
static uint32_t FindActivePickerHero(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uint32_t best=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassNameIs(obj,"WBP_HeroPicker_C")){ uint32_t nm=ReadHeroPA(obj,PICKER_SELHERO); if(nm){ char s[64]; if(GetFNameStr(nm,s,sizeof(s))&&strcmp(s,"None")!=0){ best=nm; } } } }
    }
    return best;
}
static void WriteMemberHero(uint32_t nameId){ if(!g_member||!SafeReadable((void*)(g_member+MEMBER_HEROID),16))return; *(uint32_t*)(g_member+MEMBER_HEROID)=HERO_TYPE; *(uint32_t*)(g_member+MEMBER_HEROID+4)=0; *(uint32_t*)(g_member+MEMBER_HEROID+8)=nameId; *(uint32_t*)(g_member+MEMBER_HEROID+12)=0; }
static uint32_t ReadMemberHero(){ return g_member?ReadHeroPA(g_member,MEMBER_HEROID):0; }

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    { HANDLE ch=CreateFileA(kCrashPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] mainmenu_refresh (continuous) worker started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);
    SnapshotModules(); AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL GGameThreadId\r\n");return 2;} Markerf("[1] gameTid=%lu\r\n",g_gameTid);

    // wait until the main-menu subjects exist (menu built)
    DWORD dl=GetTickCount()+120000;
    while(GetTickCount()<dl){ ResolveSubjects(); if(g_nsubj>0 && g_refreshFn && g_member) break; Sleep(500); }
    if(g_nsubj==0||!g_refreshFn||!g_member){Markerf("[2] FAIL resolve (subj=%d fn=%p member=0x%llX)\r\n",g_nsubj,g_refreshFn,(unsigned long long)g_member);return 3;}
    Markerf("[2] resolved: subjClass=0x%llX subjects=%d refreshFn=%p member=0x%llX\r\n",(unsigned long long)g_subjClass,g_nsubj,g_refreshFn,(unsigned long long)g_member);

    g_pe=(uint8_t*)(g_modBase+kPeRva);
    if(!SafeReadable(g_pe,5)||memcmp(g_pe,kPeProlog,5)!=0){Markerf("[2] FAIL PE prologue\r\n");return 4;}
    memcpy(g_stolen,g_pe,5);
    g_stub=BuildHook((uintptr_t)g_pe,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Markerf("[3] hook built (tramp=%p stub=%p). MIRROR+REFRESH live. Open HUNTERS and pick a hunter.\r\n",(void*)g_tramp,(void*)g_stub);

    uint32_t desired=0; bool hooked=false; DWORD hookedAt=0, lastResolve=GetTickCount(), lastHb=0; DWORD start=GetTickCount();
    uint32_t lastMemberLogged=0;
    while(GetTickCount()-start < 28800000u){
        if(GetTickCount()-lastResolve>=1500){ lastResolve=GetTickCount(); if(g_nsubj==0||!g_member) ResolveSubjects(); }
        // detect a pick from the active picker
        uint32_t pick=FindActivePickerHero();
        if(pick && pick!=desired){ desired=pick; char s[64]="?"; GetFNameStr(pick,s,sizeof(s)); Markerf("[PICK] Hero:%s -> mirror member + request refresh\r\n",s); }
        // mirror-hold: enforce member = desired
        if(desired){ uint32_t cur=ReadMemberHero(); if(cur!=desired){ WriteMemberHero(desired); if(desired!=lastMemberLogged){ char s[64]="?"; GetFNameStr(desired,s,sizeof(s)); Markerf("[MIRROR] member.HeroAssetID <- Hero:%s\r\n",s); lastMemberLogged=desired; } if(!hooked){ g_pending=1; g_done=0; if(InstallHook()){ hooked=true; hookedAt=GetTickCount(); Marker("[armed] PE hook installed (awaiting game-thread Refresh)\r\n"); } } } }
        // finish a refresh cycle
        if(hooked){ if(g_done){ UninstallHook(); hooked=false; char s[64]="?"; GetFNameStr(ReadMemberHero(),s,sizeof(s)); Markerf("[REFRESH DONE] Refresh() ran on game thread (#%ld). Center should now show Hero:%s.\r\n",(long)g_refreshes,s); }
            else if(GetTickCount()-hookedAt>=4000){ UninstallHook(); hooked=false; g_pending=0; Marker("[refresh timeout] no game-thread PE in 4s; member mirrored, center will refresh on next pick/event.\r\n"); } }
        if(GetTickCount()-lastHb>=15000){ char mh[64]="<none>"; GetFNameStr(ReadMemberHero(),mh,sizeof(mh)); Markerf("[hb] subj=%d member=Hero:%s desired=%u refreshes=%ld hooked=%d\r\n",g_nsubj,mh,desired,(long)g_refreshes,hooked?1:0); lastHb=GetTickCount(); }
        Sleep(60);
    }
    if(hooked)UninstallHook();
    Marker("[done] worker exit\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
