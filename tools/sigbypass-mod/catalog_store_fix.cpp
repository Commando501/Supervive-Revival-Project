// catalog_ready_fix — session 47 FIX test. Root cause (docs/session-47-tile-widget-FOUND.txt): the ALL
// HUNTERS grid (WBP_HeroPicker) only runs LoadCharacters if IsCatalogDataReady() is true; that native impl
// (+0x57BB700, rcx=CatalogManager) returns true only when ALL of [CatMgr+0x350..0x354] are nonzero, but the
// live 5th flag [+0x354]==0 on the dead/stub backend => IsCatalogDataReady==false => the grid binds
// OnCatalogDataReady and waits forever => AllHunters never built => empty grid. Heroes themselves resolve
// fine (proven) and aren't hidden. So: (1) scan the AssetManager so Hero enumerates 25 (else GetHeroCharacterList
// returns 0), and (2) force IsCatalogDataReady true BEFORE the grid Constructs by holding [CatMgr+0x354]=1.
//
// (1) = the proven scan_on_enum: hook GetPrimaryAssetIdList slot 110, first call scans all 30 types.
// (2) = find the live CatalogManager (scan committed memory for its vtable abs = base+0x8831758; pick the
//       instance whose +0x60 catalog map Num is populated, NOT the empty CDO) and, in a tight loop through
//       menu-load, write [+0x350..0x354]=1. When WBP_HeroPicker Constructs it sees IsCatalogDataReady==true
//       and calls LoadCharacters directly (no waiting on the never-firing delegate) -> AllHunters fills.
//
// Build:  clang++ -shared -O2 catalog_ready_fix.cpp -o catalog_ready_fix.dll -lkernel32
// Inject: tools/inject watch SUPERVIVE-Win64-Shipping.exe catalog_ready_fix.dll 0x3EC57D0 40555356574154415541564157
// Marker: docs/catalog-ready-fix-marker.txt
//
// ═══════════════════════════════════════════════════════════════════════════════════════════════
// 2026-08-05 (S111) — THIS SHIM WAS KILLING THE GAME. FIXED. NOT YET LIVE-VERIFIED.
//
// WHAT: the memory scans dereferenced `*(uintptr_t*)p` with NO guard, walking a whole-region
//   VirtualQuery snapshot that goes stale the instant the game frees anything. FindCatalogManagers_first
//   is polled by the Worker EVERY 400 ms until the catalog loads, so it sweeps all committed private
//   memory continuously through the phase where UE frees the most — the worst possible exposure.
//
// HOW IT WAS FOUND: not by reading this file. Crash-dump forensics over the 114-record corpus
//   (docs/fk8-crash-timing-mined.md §3.1) isolated a fault family at RIP & 0xFFFF == 0x205d and
//   matched a 40-byte code window from the minidump against THIS DLL's .text at RVA 0x205d, with
//   Rax == SUPERVIVE+0x8831758 (kCatMgrVtRva) and R14 == kernel32!VirtualQuery at exception time.
//   >=11 recorded process deaths, typically 15-45 s in on menu routes. Those deaths were being
//   attributed to injection spacing (CLAUDE.md's -InjectGapSeconds hazard table) and to FK-7.
//
// WHAT WAS TRIED / REJECTED:
//   * __try/__except (SEH) — REJECTED, and it is the trap here: the packer installs a VECTORED
//     handler, which runs BEFORE any SEH frame handler, so the process can die before __except is
//     consulted. (C++ EH is already forbidden project-wide for the adjacent reason.)
//   * re-VirtualQuery per 4 KB page — REJECTED: narrows the window, never closes it. Still a race,
//     and costs a syscall per page (more than the shipped fix costs per 256 KB).
//   * WriteProcessMemory for PokeAllPurchasable's writes — REJECTED as out of scope: 2 syscalls x
//     up to `num` entries x every 500 ms, on a path that has NEVER appeared in the crash corpus.
//
// WHAT WORKED: ReadProcessMemory on self. NtReadVirtualMemory probes in KERNEL mode and reports
//   STATUS_PARTIAL_COPY by return value — it cannot raise a user-mode exception in the caller, so
//   there is no race left to lose. See the SafeCopy / ScanPrivateForQword block below.
//
// EVIDENCE IT WORKS (offline, tools/sigbypass-mod/tests/scan_race_test.cpp — verbatim copies of both
//   bodies, a thread decommitting pages mid-walk, coordinated so the scan is provably inside the
//   region first):  OLD arm segfaults 3/3 (exit 139).  NEW arm survives 3/3 and still finds the
//   needle in the no-race control.  Cost ~1.2x, background thread.
//   ⚠ The FIRST version of that harness let the OLD arm survive — the scan short-circuited before
//     reaching the shredded pages. A quiet negative control is VOID, not a pass; it was rebuilt.
//
// ⚠ NOT LIVE-VERIFIED. Zero game runs of this build exist. The baseline to beat is 11 deaths at
//   RVA 0x205d. Marker now stamps `build=<date> <time> scan=SAFECOPY-S111` so a run can be
//   attributed to this build from the marker alone (ignorance-map gap F3).
// ⚠ catalog_ready_fix.cpp (2 sites) and catalog_purchasable_fix.cpp (1 site) STILL CARRY THE
//   DEFECT. Neither is in the default injection set; both are banner-warned. Port before injecting.
// ═══════════════════════════════════════════════════════════════════════════════════════════════

#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath =
    "G:\\git\\Supervive Revival Project\\docs\\catalog-store-fix-marker.txt";
static const char* kCrashPath =
    "G:\\git\\Supervive Revival Project\\docs\\catalog-store-fix-crash.txt";

constexpr uintptr_t kVtRva        = 0x888CB78;   // LokiAssetManager vtable
constexpr uintptr_t kScanRva      = 0x34CF9F0;   // ScanPathsForPrimaryAssets
constexpr uintptr_t kGGameTidRva  = 0x9D49158;
constexpr uintptr_t kTypeMapOff   = 0x478;
constexpr uintptr_t kInfoBaseOff  = 0x30;
constexpr uintptr_t kInfoPathsOff = 0x70;
constexpr int       SLOT_IDL      = 110;
constexpr uint32_t  kHeroFName    = 0x1A568;
constexpr uintptr_t kCatMgrVtRva  = 0x8831758;   // CatalogManager vtable
constexpr uintptr_t kMapOff       = 0x60;        // CatalogManager catalog map (Data@+0x60, Num@+0x68)
// CatalogEntry byte-flag offsets (from disasm of the native getter exec thunks). Store/cosmetic
// entries come back CanUse=0/IsPurchasable=0 (no offering cost from the dead backend) so the
// generic browse tile WBP_UI_Storefront_ListItem collapses. Poke them to make the tiles RENDER
// (price still blank — offering cost is a separate fix). BUNDLES/SKINS/ACCESSORIES.
constexpr uintptr_t kOffCanUse    = 0xD0;
constexpr uintptr_t kOffReason    = 0xD1;   // ELokiCatalogCannotUseReason
constexpr uintptr_t kOffDisabled  = 0xD2;
constexpr uintptr_t kOffHidden    = 0xD3;
constexpr uintptr_t kOffPurch     = 0x118;
constexpr uintptr_t kReadyOff     = 0x350;       // IsCatalogDataReady flags [+0x350..+0x354]
constexpr uintptr_t kJzRva        = 0x57BB722;   // the `jz false` after the [+0x354] check in IsCatalogDataReady
                                                 // impl; NOP it (74 0C -> 90 90) so the never-set 5th flag is
                                                 // ignored => IsCatalogDataReady returns true once the 4 REAL
                                                 // flags [0x350-0x353] are set (== when the catalog is loaded),
                                                 // so the game's post-load readiness check BROADCASTS
                                                 // OnCatalogDataReady and the waiting grid runs LoadCharacters.

typedef int32_t (*PFN_Scan)(void*, uint64_t, void*, void*, bool, bool, bool);
struct TArr { void* Data; int32_t Num; int32_t Max; };

static uintptr_t g_modBase = 0;
static PFN_Scan  g_scan    = nullptr;
static uintptr_t g_origIdl = 0;
static uint8_t*  g_stubIdl = nullptr;
static volatile long g_scanState = 0;
static volatile bool g_unhooked = false;
static volatile uintptr_t g_catMgr = 0;

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}

static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}

// ─────────────── 2026-08-05 (S111): FAULT-FREE MEMORY ACCESS ───────────────
// WHY THIS EXISTS. Crash-dump forensics over the 114-record corpus
// (docs/fk8-crash-timing-mined.md §3.1) attributed a whole crash family to THIS DLL: fault
// RIP & 0xFFFF == 0x205d, a READ fault (ExceptionInformation[0]==0), identified to the byte by
// matching a 40-byte code window out of the minidump against this DLL's .text at RVA 0x205d, with
// Rax == SUPERVIVE+0x8831758 (kCatMgrVtRva) and R14 == kernel32!VirtualQuery at exception time.
// It is FindCatalogManagers_first. At least 11 process deaths, typically 15-45 s in on menu routes.
//
// THE DEFECT (both scan loops had it, identically):
//     for(uintptr_t p=base; p+8<=end; p+=8)
//         if(*(uintptr_t*)p==vtabAbs && SafeReadable((void*)(p+kMapOff),16)){ ... }
//                ^^^^^^^^^^^^^^^^ dereferenced with NO guard whatsoever.
// SafeReadable was consulted only AFTER the vtable compare, and it validates p+kMapOff, not p.
// VirtualQuery snapshots an ENTIRE region up front; the loop then walks that stale snapshot while
// the game is actively freeing memory (the caller polls this every 400 ms through asset load, so
// the exposure is enormous). Any page decommitted mid-walk = instant AV.
//
// WHY NOT SEH. __try/__except would look like the obvious fix and is a TRAP here: the packer
// installs a VECTORED exception handler, which by definition runs BEFORE any SEH frame handler,
// so the process can die before __except is ever consulted. CLAUDE.md already forbids C++ EH in
// injected payloads for the adjacent reason. Neither mechanism is used below.
//
// WHY THIS WORKS. ReadProcessMemory -> NtReadVirtualMemory PROBES IN KERNEL MODE and reports
// STATUS_PARTIAL_COPY by return value; it never raises a user-mode exception in the calling
// thread, whatever the game does to the page underneath us. There is no race left to lose: we do
// not validate-then-read, we simply cannot fault. GetCurrentProcess() is a constant pseudo-handle
// (-1), not a syscall, so this costs one kernel transition per CHUNK -- not per read.
static inline bool SafeCopy(void* dst,const void* src,size_t n){
    SIZE_T got=0;
    return ReadProcessMemory(GetCurrentProcess(),src,dst,n,&got) && got==n;
}
static inline bool SafeReadQ(uintptr_t a,uintptr_t* out){ return SafeCopy(out,(const void*)a,sizeof(*out)); }
static inline bool SafeReadD(uintptr_t a,int32_t*   out){ return SafeCopy(out,(const void*)a,sizeof(*out)); }

// Scan every committed private region for an 8-byte-aligned qword == `needle`, without ever
// dereferencing game memory. Copies through SafeCopy into a small reused buffer that stays hot in
// L2 (so the added cost over the old in-place scan is the cache-resident store side, not a second
// pass over RAM), then scans the copy. onHit returns 1 to accept and stop, 0 to keep going.
// Pages that vanish mid-scan are SKIPPED, never faulted on: a failed chunk read degrades to
// per-page reads and only the pages that are actually gone are dropped. We deliberately do not
// rely on ReadProcessMemory's partial-copy prefix semantics.
// MEASURED cost of safety (standalone control harness, tools/sigbypass-mod/tests/scan_race_test.cpp,
// 512 MB region, avg of 3, whole-address-space sweep incl. process startup):
//     old unguarded 275 ms | 16 KB 391 | 64 KB 356 | 256 KB 338 | 1 MB 329
// 256 KB is the knee -- past it the gain is ~3 % for 4x the .bss. Net overhead ~1.2x, paid on a
// background thread, in exchange for a fault class that killed the process >=11 times.
// NOT changed: the Worker's 400 ms poll cadence. Backing it off would cut this cost further and was
// deliberately NOT done -- detection time gates catLoadedAt, and the jz self-restore fires
// catLoadedAt+6000, so a later detection means a LONGER .text patch uptime and a closer approach to
// the code-integrity check. That trade needs a live run, not an assumption.
// ⚠⚠ KNOSCAN — ARM-C CONTROL BUILD ONLY. DEFAULT 0. NEVER SHIP THIS ON. ⚠⚠
// Disables the memory scan ENTIRELY (neither the old unguarded walk nor the new SafeCopy one).
// It exists to answer ONE question, left open by the 60-launch A/B
// (docs/s111-scanfix-ab-campaign.md §1): protector deaths ran 11/30 with the fix vs 5/30 without
// (p=0.072), and ReadProcessMemory is a memory-scanning API inside an anti-tamper-protected
// process. If arm C (no scan at all) still shows ~11/30 protector deaths, RPM is EXONERATED and
// the effect is competing risks. If arm C drops to ~5/30, RPM is implicated.
// ⚠ With the scan off the shim CANNOT find the CatalogManager, so: no [cm] line, no purchasable
//   poke, and the jz self-restore never fires (it is gated on catLoadedAt) — meaning the .text
//   patch stays for the life of the run. Harmless at the 60 s hold used for the A/B (the
//   code-integrity kill is minutes away) but it is a REAL difference from arms A and B; do not run
//   this arm long. This build is a CONTROL, not a candidate.
// ⚠ CLAUDE.md: "Don't leave an S9x diagnostic switched on and then reason about the game." That has
//   already cost this project two sessions (KTESTACTOR, KSTATICTEST). Default is 0; the only way to
//   get it is the registered `noscan` variant, which writes a DIFFERENTLY NAMED dll.
#ifndef KNOSCAN
#define KNOSCAN 0
#endif

// ⚠⚠ ARM E1/E2/E3 BISECT SWITCHES — ALL DEFAULT 0. NEVER SHIP ANY OF THESE ON. ⚠⚠
// Arm E (docs/s111-arme-shim-activity.md) proved the protector kill is provoked by this shim's own
// worker activity: one INERT mapped DLL survived 11/11 at a 320 s hold, this one died 7/8 at the
// identical hold and image count (p = 0.00016). Arm E still leaves FIVE behaviours running, so these
// three switches remove one variable each. Whichever restores arm D's 0 % is the trigger.
//   KNOVEH   skip SnapshotModules + AddVectoredExceptionHandler — a VEH, installed into a process
//            whose protector itself dispatches through VEH
//   KNOSLOT  skip BuildStub (an EXECUTABLE private allocation) + the slot-110 vtable write
//   KNOJZ    skip the .text jz-NOP — the only write into module image memory
// Each is reachable only through its registered build.ps1 variant, which emits a DIFFERENTLY NAMED
// dll. Run them at 320 s holds: at 60 s the arms do not separate (arm E is only ~12 % by 60 s).
#ifndef KNOVEH
#define KNOVEH 0
#endif
#ifndef KNOSLOT
#define KNOSLOT 0
#endif
// ★★ KNOJZ NOW DEFAULTS TO 1 — THE .text PATCH IS OFF IN THE SHIPPED BUILD (2026-08-06, S111).
// The jz-NOP was MEASURED to be the trigger for the protector kill that has been costing ~30 % of
// all launches: one-variable bisect, patch standing 11/12 vs no patch 0/5, p = 0.00097
// (docs/s111-bisect-jz-is-the-trigger.md). Dropping it is safe because the shim ALREADY sets the
// same condition as DATA — the `[+0x354]=1` poke on the live CatalogManager, in the worker loop.
// VERIFIED FUNCTIONALLY 2026-08-06: with jz=0 the ALL HUNTERS grid renders the full roster
// (screenshot-confirmed by the user), marker showing scan=SAFECOPY-S111 veh=1 slot=1 jz=0,
// `[cm] live CatalogManager (map Num=1339)`, lastPurch=1339, and the run cleared a 320 s hold.
// ⚠ S47 (docs/session-47-tile-widget-FOUND.txt:385) warns the poke does NOT repopulate a grid that
//   has ALREADY Constructed and is waiting on the delegate. That is consistent: the shim pokes
//   continuously from catalog-load onward, so the flag is set well before the user opens HUNTERS
//   and the grid takes the direct LoadCharacters path on Construct. If a future change delays the
//   scan past first navigation, this could regress — keep the poke early and continuous.
// Roll back with -DKNOJZ=0 (variant `jzpatch`) if the roster ever fails to populate.
#ifndef KNOJZ
#define KNOJZ 1
#endif

typedef int (*PFN_OnHit)(uintptr_t p,void* ctx);
static constexpr size_t kScanChunk = 256*1024;
static constexpr size_t kScanPage  = 4096;
static uint8_t g_scanBuf[kScanChunk];   // worker thread only; scans are single-threaded

static void ScanChunkBuf(uintptr_t at,size_t len,uintptr_t needle,PFN_OnHit onHit,void* ctx,bool* stop){
    const uintptr_t* q=(const uintptr_t*)g_scanBuf;
    for(size_t i=0;i+8<=len;i+=8){
        if(q[i/8]==needle && onHit(at+i,ctx)){ *stop=true; return; }
    }
}

static void ScanPrivateForQword(uintptr_t needle,PFN_OnHit onHit,void* ctx){
#if KNOSCAN
    (void)needle; (void)onHit; (void)ctx;
    return;                 // ARM-C CONTROL: no memory scan of any kind is performed.
#else
    SYSTEM_INFO si; GetSystemInfo(&si);
    uintptr_t addr=(uintptr_t)si.lpMinimumApplicationAddress;
    uintptr_t maxA=(uintptr_t)si.lpMaximumApplicationAddress;
    bool stop=false;
    while(addr<maxA && !stop){
        MEMORY_BASIC_INFORMATION m{};
        if(!VirtualQuery((void*)addr,&m,sizeof(m))) break;
        uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;
        bool ok=(m.State&MEM_COMMIT)&&!(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))&&
                (m.Protect&(PAGE_READWRITE|PAGE_EXECUTE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_WRITECOPY));
        if(ok && m.Type==MEM_PRIVATE){
            uintptr_t base=(uintptr_t)m.BaseAddress, end=base+m.RegionSize;
            for(uintptr_t c=base; c<end && !stop; c+=kScanChunk){
                size_t len=(size_t)((end-c)<kScanChunk?(end-c):kScanChunk);
                if(SafeCopy(g_scanBuf,(const void*)c,len)){
                    ScanChunkBuf(c,len,needle,onHit,ctx,&stop);
                }else{
                    // the region went away under us (or partly). Retry page-by-page and keep
                    // whatever is still there. THIS IS THE PATH THAT USED TO BE AN AV.
                    for(uintptr_t pg=c; pg<c+len && !stop; pg+=kScanPage){
                        size_t pl=(size_t)((c+len-pg)<kScanPage?(c+len-pg):kScanPage);
                        if(!SafeCopy(g_scanBuf,(const void*)pg,pl)) continue;
                        ScanChunkBuf(pg,pl,needle,onHit,ctx,&stop);
                    }
                }
            }
        }
        if(next<=addr) break; addr=next;
    }
#endif  // KNOSCAN
}

// ─────────── read-only VEH crash logger (adapted from scan_on_enum_veh) ───────────
// Capture the faulting RIP / SUPERVIVE RVA / module / registers / stack band into
// docs/catalog-ready-fix-crash.txt before Sentry kills the process, to pin WHERE opening the
// catalog-ready gate crashes (D3D12/RHI render wall vs a content-load path). CONTINUE_SEARCH only.
struct ModRange { uint64_t base, end; char name[64]; };
static ModRange g_mods[192];
static volatile long g_modCount = 0;
static volatile long g_crashSeq = 0;
static void SnapshotModules(){
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());
    if(snap==INVALID_HANDLE_VALUE)return; MODULEENTRY32 me; me.dwSize=sizeof(me); int n=0;
    if(Module32First(snap,&me)){ do{ if(n>=192)break; ModRange&r=g_mods[n];
        r.base=(uint64_t)me.modBaseAddr; r.end=r.base+me.modBaseSize;
        int i=0; for(;i<63&&me.szModule[i];i++)r.name[i]=(char)me.szModule[i]; r.name[i]=0; n++;
    }while(Module32Next(snap,&me)); }
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
    CWrite(h,"=== VEH fatal exception ===\r\n",29);
    CKV(h,"seq",(uint64_t)seq); CKV(h,"code",code);
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip; CKV(h,"RIP",rip);
    if(g_modBase && rip>g_modBase && rip<g_modBase+0xC000000) CKV(h,"SUPERVIVE_RVA",rip-g_modBase);
    long mc=g_modCount; bool named=false;
    for(long i=0;i<mc;i++){ if(rip>=g_mods[i].base && rip<g_mods[i].end){ CWrite(h,"module=",7); CWrite(h,g_mods[i].name,(DWORD)strlen(g_mods[i].name)); CWrite(h,"\r\n",2); CKV(h,"module_RVA",rip-g_mods[i].base); named=true; break; } }
    if(!named)CWrite(h,"module=UNKNOWN\r\n",16);
    if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2){ CKV(h,"av_op",ep->ExceptionRecord->ExceptionInformation[0]); CKV(h,"av_addr",ep->ExceptionRecord->ExceptionInformation[1]); }
    CKV(h,"Rax",c->Rax);CKV(h,"Rbx",c->Rbx);CKV(h,"Rcx",c->Rcx);CKV(h,"Rdx",c->Rdx);CKV(h,"Rsi",c->Rsi);CKV(h,"Rdi",c->Rdi);CKV(h,"R8",c->R8);CKV(h,"R9",c->R9);CKV(h,"R10",c->R10);CKV(h,"R11",c->R11);CKV(h,"Rsp",c->Rsp);CKV(h,"Rbp",c->Rbp);
    uint64_t base=g_modBase, top=g_modBase+0xC000000; uint64_t* sp=(uint64_t*)c->Rsp; int found=0;
    for(int i=0;i<800 && found<40;i++){ if(!SafeReadable(sp+i,8))break; uint64_t v=sp[i]; if(base && v>base && v<top){ CKV(h,"stkRVA",v-base); found++; } }
    CWrite(h,"=== end ===\r\n\r\n",15); FlushFileBuffers(h); CloseHandle(h);
    return EXCEPTION_CONTINUE_SEARCH;
}

static void RunScanForAllTypes(void* manager){
    const uint8_t* mgr=(const uint8_t*)manager;
    if(!SafeReadable(mgr+kTypeMapOff,16)){Marker("[scan] typemap unreadable\r\n");return;}
    uintptr_t data=*(const uintptr_t*)(mgr+kTypeMapOff);
    uint32_t mx=*(const uint32_t*)(mgr+kTypeMapOff+12);
    if(!LooksLikePtr(data)||mx==0||mx>4096){Marker("[scan] bad typemap\r\n");return;}
    int called=0,heroAdded=-1;
    for(uint32_t i=0;i<mx;i++){
        const uint8_t* e=(const uint8_t*)data+(uintptr_t)i*0x20;
        if(!SafeReadable(e,0x10))continue;
        uint64_t key=*(const uint64_t*)(e); uintptr_t td=*(const uintptr_t*)(e+8);
        if(key==0||!LooksLikePtr(td)||!SafeReadable((void*)td,0x80))continue;
        uint64_t type=*(const uint64_t*)td; uintptr_t base=*(const uintptr_t*)(td+kInfoBaseOff);
        void* paths=(void*)(td+kInfoPathsOff);
        if(type!=key||!LooksLikePtr(base)||!SafeReadable((void*)base,8))continue;
        int32_t added=g_scan(manager,type,paths,(void*)base,true,false,true);
        called++;
        if((uint32_t)(type&0xFFFFFFFF)==kHeroFName)heroAdded=added;
    }
    Markerf("[scan] DONE: %d types scanned (Hero added=%d)\r\n",called,heroAdded);
}

extern "C" void h_idl_pre(uintptr_t rcx, uintptr_t, uintptr_t, uintptr_t){
    if(InterlockedCompareExchange(&g_scanState,1,0)!=0) return;
    Markerf("[enum] first GetPrimaryAssetIdList -> scan (mgr=0x%llX)\r\n",(unsigned long long)rcx);
    g_scan=(PFN_Scan)(g_modBase+kScanRva);
    RunScanForAllTypes((void*)rcx);
    InterlockedExchange(&g_scanState,2);
}
extern "C" void h_idl_post(uintptr_t, uintptr_t, uintptr_t, uintptr_t){}

static uint8_t* BuildStub(void* pre, void* post, uintptr_t orig){
    uint8_t* p=(uint8_t*)VirtualAlloc(nullptr,0x100,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!p)return nullptr; uint8_t* w=p;
    *w++=0x48;*w++=0x83;*w++=0xEC;*w++=0x48;
    *w++=0x48;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x20;
    *w++=0x48;*w++=0x89;*w++=0x54;*w++=0x24;*w++=0x28;
    *w++=0x4C;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x30;
    *w++=0x4C;*w++=0x89;*w++=0x4C;*w++=0x24;*w++=0x38;
    auto reload=[&](){ *w++=0x48;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x20;
        *w++=0x48;*w++=0x8B;*w++=0x54;*w++=0x24;*w++=0x28;
        *w++=0x4C;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x30;
        *w++=0x4C;*w++=0x8B;*w++=0x4C;*w++=0x24;*w++=0x38; };
    *w++=0x48;*w++=0xB8; uint64_t pf=(uint64_t)pre; memcpy(w,&pf,8); w+=8; *w++=0xFF;*w++=0xD0;
    reload();
    *w++=0x48;*w++=0xB8; uint64_t of=(uint64_t)orig; memcpy(w,&of,8); w+=8; *w++=0xFF;*w++=0xD0;
    *w++=0x48;*w++=0x89;*w++=0x44;*w++=0x24;*w++=0x40;
    reload();
    *w++=0x48;*w++=0xB8; uint64_t sf=(uint64_t)post; memcpy(w,&sf,8); w+=8; *w++=0xFF;*w++=0xD0;
    *w++=0x48;*w++=0x8B;*w++=0x44;*w++=0x24;*w++=0x40;
    *w++=0x48;*w++=0x83;*w++=0xC4;*w++=0x48;
    *w++=0xC3;
    return p;
}
static DWORD WaitTid(uintptr_t mb,DWORD to){uint32_t*s=(uint32_t*)(mb+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// Scan committed private memory for ALL CatalogManager instances (vtable==target) — including the CDO
// and the live subsystem instance BEFORE its catalog map fills. We want them EARLY (before the catalog
// finishes loading) so we can pre-set the 5th ready-flag [+0x354]=1; then when the game finishes the 4
// real categories and checks readiness, all 5 are set and it BROADCASTS OnCatalogDataReady naturally
// (no .text patch => no code-integrity crash). Fills `out[]` (cap N), returns count.
// 2026-08-05 (S111): rewritten onto ScanPrivateForQword. Was an unguarded `*(uintptr_t*)p` walk
// over a stale VirtualQuery snapshot -- same defect as FindCatalogManagers_first, which the crash
// corpus caught in the act. Behaviour on success is unchanged: same vtable match, same
// +kReadyOff readability requirement, same dedup, same cap.
struct FcmCtx { uintptr_t* out; int cap; int n; };
static int OnHitCollect(uintptr_t p,void* v){
    FcmCtx* c=(FcmCtx*)v;
    uintptr_t probe;
    if(!SafeReadQ(p+kReadyOff,&probe)) return 0;     // was SafeReadable(); now the read itself is safe
    for(int i=0;i<c->n;i++) if(c->out[i]==p) return 0;
    c->out[c->n++]=p;
    return c->n>=c->cap ? 1 : 0;
}
static int FindCatalogManagers(uintptr_t vtabAbs, uintptr_t* out, int cap){
    FcmCtx c{out,cap,0};
    if(cap<=0) return 0;
    ScanPrivateForQword(vtabAbs,OnHitCollect,&c);
    return c.n;
}

// Find the ONE live CatalogManager (vtable match whose +0x60 catalog map is populated). Returns 0 until
// the catalog has loaded. Used only to detect "catalog loaded" for restore timing (find-once, then stop).
// ★ 2026-08-05 (S111): THIS IS THE FUNCTION THAT WAS KILLING THE GAME (fault at .text RVA 0x205d,
// >=11 recorded process deaths). The old body dereferenced `*(uintptr_t*)p` completely unguarded,
// walking a stale whole-region VirtualQuery snapshot, and the Worker polls it EVERY 400 ms until
// the catalog loads -- i.e. continuously, through exactly the phase where the game frees the most
// memory. Rewritten onto ScanPrivateForQword; the accept predicate is byte-for-byte the same
// (vtable match, +0x60 map Data looks like a pointer, 50 <= Num <= 5000), only the reads changed.
struct FcmFirstCtx { uintptr_t hit; };
static int OnHitFirstLive(uintptr_t p,void* v){
    uintptr_t md; int32_t mn;
    if(!SafeReadQ(p+kMapOff,&md))      return 0;     // both were SafeReadable()-then-deref (a TOCTOU
    if(!SafeReadD(p+kMapOff+8,&mn))    return 0;     // in its own right); now they cannot fault
    if(!LooksLikePtr(md) || mn<50 || mn>5000) return 0;
    ((FcmFirstCtx*)v)->hit=p;
    return 1;                                        // accept & stop -- same first-match semantics
}
static uintptr_t FindCatalogManagers_first(uintptr_t vtabAbs){
    FcmFirstCtx c{0};
    ScanPrivateForQword(vtabAbs,OnHitFirstLive,&c);
    return c.hit;
}

// A live UObject: its first qword (vtable) points into the module image.
static bool LooksLikeObject(uintptr_t p,uintptr_t modBase){ if(!LooksLikePtr(p)) return false; uintptr_t vt; if(!SafeReadQ(p,&vt)) return false; return vt>=modBase && vt<modBase+0xC000000; }

// Iterate the CatalogManager Catalog TMap sparse array; poke each CatalogEntry's status flags
// so the browse tiles render (CanUse=1, CannotUseReason=0, IsDisabled=0, IsHidden=0,
// IsPurchasable=1). Returns count poked. Pure DATA writes (no .text touch).
static int PokeAllPurchasable(uintptr_t catMgr,uintptr_t modBase){
    uintptr_t data; int32_t num;
    // 2026-08-05 (S111): reads moved off SafeReadable()-then-deref onto SafeRead*. Same predicates.
    if(!SafeReadQ(catMgr+kMapOff,&data))   return 0;
    if(!SafeReadD(catMgr+kMapOff+8,&num))  return 0;
    if(!LooksLikePtr(data)||num<=0||num>20000) return 0;
    int poked=0; int cap=num*3+256;
    for(int i=0;i<cap && poked<num;i++){
        uintptr_t elem=data+(uintptr_t)i*0x20;
        uintptr_t entry;
        if(!SafeReadQ(elem+0x10,&entry)) continue;
        if(!LooksLikeObject(entry,modBase)) continue;
        uint8_t probe;
        // Proves the flag page is present RIGHT NOW; LooksLikeObject already proved the entry's
        // vtable points into the image, i.e. it is a live UObject and not recycled memory.
        if(!SafeCopy(&probe,(const void*)(entry+kOffPurch),1)) continue;
        // ⚠ RESIDUAL, DELIBERATE, SCOPED: these five stay DIRECT writes. Converting them to
        // WriteProcessMemory would make them fault-free too, but at 2 syscalls x up to `num`
        // entries x every 500 ms that is a real cost on a path that has NEVER appeared in the
        // crash corpus -- the measured family is the SCAN (.text RVA 0x205d), not the poke. The
        // window here is nanoseconds (probe-then-write on the same page) versus the scan's
        // milliseconds-to-seconds walk of a stale region snapshot. Revisit only if a fault ever
        // lands in this function's RVA range. See docs/fk8-crash-timing-mined.md §3.1.
        uint8_t* e=(uint8_t*)entry;
        e[kOffCanUse]=1; e[kOffReason]=0; e[kOffDisabled]=0; e[kOffHidden]=0; e[kOffPurch]=1;
        poked++;
    }
    return poked;
}

static DWORD WINAPI Worker(LPVOID){
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    // Build stamp: ignorance-map gap F3 is "nothing distinguishes 'the target ran and did nothing'
    // from 'we never reached the target'; no shim stamps a source SHA or build time into its
    // marker." Stamping it makes the S111 scan fix verifiable from the marker alone.
    Markerf("[0] catalog_store_fix worker started (ready-gate + purchasable poke) "
            "build=%s %s scan=%s veh=%d slot=%d jz=%d\r\n",__DATE__,__TIME__,
            KNOSCAN ? "DISABLED-ARMC-CONTROL" : "SAFECOPY-S111",
            KNOVEH ? 0 : 1, KNOSLOT ? 0 : 1, KNOJZ ? 0 : 1);
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe");
    if(!hExe){Marker("[0] FAIL GetModuleHandle\r\n");return 1;}
    g_modBase=(uintptr_t)hExe;
    Markerf("[0] modBase=0x%llX\r\n",(unsigned long long)g_modBase);
    { HANDLE ch=CreateFileA(kCrashPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
#if !KNOVEH
    SnapshotModules();
    AddVectoredExceptionHandler(1,CrashVEH);
    Marker("[0] crash-VEH installed\r\n");
#else
    Marker("[0] KNOVEH: SnapshotModules + crash-VEH SKIPPED (arm E1 control)\r\n");
#endif
    if(!WaitTid(g_modBase,60000)){Marker("[1] FAIL GGameThreadId\r\n");return 2;}
    uintptr_t* pslot=(uintptr_t*)(g_modBase+kVtRva+(uintptr_t)SLOT_IDL*8);
#if !KNOSLOT
    DWORD dl=GetTickCount()+30000; bool ready=false;
    while(GetTickCount()<dl){if(SafeReadable(pslot,8)){uintptr_t v=*pslot;if(v>g_modBase&&v<g_modBase+0xC000000){ready=true;break;}}Sleep(5);}
    if(!ready){Marker("[2] FAIL slot 110\r\n");return 3;}
    g_origIdl=*pslot;
    g_stubIdl=BuildStub((void*)&h_idl_pre,(void*)&h_idl_post,g_origIdl);
    DWORD op=0; VirtualProtect(pslot,8,PAGE_READWRITE,&op); *pslot=(uintptr_t)g_stubIdl; DWORD d=0; VirtualProtect(pslot,8,op,&d);
    Marker("[3] GetPrimaryAssetIdList hooked (scan armed)\r\n");
#else
    // No stub is allocated and the vtable is never written, so there is nothing to restore later.
    // g_unhooked=true keeps both unhook paths from touching pslot.
    g_unhooked=true;
    Marker("[3] KNOSLOT: BuildStub + slot-110 vtable hook SKIPPED (arm E2 control)\r\n");
#endif

    uintptr_t vtabAbs=g_modBase+kCatMgrVtRva;
    DWORD start=GetTickCount(); DWORD lastScan=0; DWORD lastHb=0; uint64_t pokes=0;
    bool jzPatched=false; uint8_t origJz[2]={0}; bool jzRestored=false; DWORD catLoadedAt=0;
    // PROVEN jz-patch (grid builds) + SELF-RESTORE: NOP the `jz` after the [+0x354] check so IsCatalogDataReady
    // ignores the never-set 5th flag and returns true once the 4 real flags set -> the game broadcasts
    // OnCatalogDataReady -> the grid builds. Then, shortly after the catalog has loaded + broadcast fired,
    // RESTORE the jz (74 0C) so the persistent .text mod is gone before the ~3-5min code-integrity check.
    uint64_t purchPokes=0; int lastPurch=0; DWORD lastPurchTick=0;
    // Extended to ~30 min: the ready-gate work (jz NOP + restore + unhook) still happens in the
    // first few seconds (guarded by flags); the loop then keeps re-poking the CatalogEntry
    // purchasable/canuse flags so the browse tiles render whenever the user opens the store.
    while(GetTickCount()-start < 1800000){
#if !KNOJZ
        if(!jzPatched){
            uint8_t* jz=(uint8_t*)(g_modBase+kJzRva);
            if(SafeReadable(jz,2) && jz[0]==0x74 && jz[1]==0x0C){
                DWORD o=0; if(VirtualProtect(jz,2,PAGE_EXECUTE_READWRITE,&o)){ origJz[0]=jz[0]; origJz[1]=jz[1]; jz[0]=0x90; jz[1]=0x90; DWORD dd=0; VirtualProtect(jz,2,o,&dd); jzPatched=true; Marker("[patch] jz NOP'd (IsCatalogDataReady ignores +0x354)\r\n"); }
            }
        }
#endif  // KNOJZ — arm E3 control: no .text write of any kind
        // find the live CatalogManager once (map populated = catalog loaded => broadcast has fired w/ the patch)
        if(!g_catMgr && GetTickCount()-lastScan>=400){
            lastScan=GetTickCount();
            uintptr_t cm=FindCatalogManagers_first(vtabAbs);
            if(cm){ g_catMgr=cm; catLoadedAt=GetTickCount(); int32_t mnum=-1; SafeReadD(cm+kMapOff+8,&mnum);
                Markerf("[cm] live CatalogManager @0x%llX (map Num=%d) — catalog loaded\r\n",(unsigned long long)cm,mnum); }
        }
        // belt-and-suspenders data poke of [+0x354]=1 on the live instance (harmless; helps if the game re-checks)
        if(g_catMgr){
            uint8_t rf[8];
            if(SafeCopy(rf,(const void*)(g_catMgr+kReadyOff),8) && rf[4]==0){
                ((uint8_t*)(g_catMgr+kReadyOff))[4]=1; pokes++; } }
        // NEW: poke every CatalogEntry purchasable/canuse so the browse tiles render (throttled).
        if(g_catMgr && GetTickCount()-lastPurchTick>=500){ lastPurchTick=GetTickCount(); lastPurch=PokeAllPurchasable(g_catMgr,g_modBase); purchPokes++; }
        // ~6s after the catalog loaded (grid has built), RESTORE the jz so no persistent .text mod remains.
        if(jzPatched && !jzRestored && catLoadedAt && GetTickCount()-catLoadedAt>=6000){
            uint8_t* jz=(uint8_t*)(g_modBase+kJzRva); DWORD o=0;
            if(VirtualProtect(jz,2,PAGE_EXECUTE_READWRITE,&o)){ jz[0]=origJz[0]; jz[1]=origJz[1]; DWORD dd=0; VirtualProtect(jz,2,o,&dd); jzRestored=true; Marker("[restore] jz restored (no persistent .text mod)\r\n"); }
        }
        if(!g_unhooked && g_scanState==2 && GetTickCount()-start>=8000){
            DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}g_unhooked=true;Marker("[unhook] slot 110 restored\r\n");
        }
        if(GetTickCount()-lastHb>=5000){Markerf("[hb] catMgr=0x%llX jz=%d/%d unhook=%d purchIters=%llu lastPurch=%d\r\n",(unsigned long long)g_catMgr,jzPatched?1:0,jzRestored?1:0,g_unhooked?1:0,(unsigned long long)purchPokes,lastPurch);lastHb=GetTickCount();}
        Sleep(15);
    }
    if(!g_unhooked){DWORD o=0;if(VirtualProtect(pslot,8,PAGE_READWRITE,&o)){*pslot=g_origIdl;DWORD dd=0;VirtualProtect(pslot,8,o,&dd);}}
    Markerf("[done] catMgr=0x%llX pokes=%llu jzRestored=%d\r\n",(unsigned long long)g_catMgr,(unsigned long long)pokes,jzRestored?1:0);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
