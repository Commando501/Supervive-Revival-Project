// battlepass_adopt_fix — S82: FORCE-GATE the battlepass "current published progression tracks" adoption.
//
// The client's SDK converter drops every track we serve on GET /storefront/battlepass/progressiontracks,
// so BattlepassInfoManager never adopts (the version-gated OnSuccess handler is skipped) and the whole
// PASSES system (season + account passes) stays empty while the endpoint tight-loops. RE'd fully (S82):
//   - OnSuccess handler = RVA 0x57C8130, __fastcall(rcx=BattlepassInfoManager, rdx=&aggregate).
//     It: cancels the retry timer, checks `[rdx+0x10](Version) > [BPIM+0x50](adopted)`, and IF so deep-copies
//     the aggregate's TArray into BPIM+0x40, sets BPIM+0x50=Version, Broadcasts the +0x30 delegate
//     OnUpdatedCurrentPublishedProgressionTracks (=> ViewManager builds season/account view-models).
//   - The aggregate is a `LokiPublishedProgressionTracks` { +0x00 TArray<LokiPublishedProgressionTrack>, +0x10 int64 Version }.
//   - Element `LokiPublishedProgressionTrack` (0x120): +0x00 ProgressionTrackID FString | +0x10 Details
//     (LokiBattlepassProgressionTrack 0x98: +0x00 InternalId FString ...) | +0xA8 IsRetired | +0xA9 IsAccountPass |
//     +0xAA IsReferralPass | +0xAB IsSeasonalPass | +0xB0 PurchaseDetails (0x70).
//   - SetCurrentPublishedProgressionTracks (UFunction) is a compiled-out ret-0 no-op, so we call OnSuccess directly.
// This shim: get on the game thread (ProcessInternal hook, base+0x13454A0), find the live BattlepassInfoManager,
// build a 1-element aggregate (HuntersJourney account pass, Version=1), call OnSuccess(BPIM,&agg), then read
// BPIM+0x48 (Num) / +0x50 (adopted) to confirm adoption fired. The deep-copy takes our FStrings by value, so the
// static source buffers are only read.
// Build:  clang++ -shared -O2 battlepass_adopt_fix.cpp -o battlepass_adopt_fix.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> ...   Marker: docs/battlepass-adopt-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\battlepass-adopt-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr uintptr_t kOnSuccessRva=0x57C8130;         // BattlepassInfoManager progressiontracks OnSuccess handler
constexpr uintptr_t kPopulateRva=0x57DF4B0;          // BattlepassViewModel populate: fills Levels@+0xC8 from ProgressionTrackAsset@+0xE8
constexpr uintptr_t kCheckAcctRva=0x5794480;         // BattlepassViewManager::CheckAccountPassChanges — the REAL caller of the populate
constexpr uintptr_t kGet1Rva=0x562BC70, kGet2Rva=0x562BED0;   // published-pass resolution getters (see typedefs)
constexpr uintptr_t kPaidToStrRva=0x12F4230;                  // FPrimaryAssetId::ToString
constexpr int kGetPaidVtblSlot=0x1D0/8;                       // GetPrimaryAssetId vtable slot (byte off 0x1D0)
// S83: arm the gate-satisfy + CheckAccountPassChanges force-call (set false to fall back to the S82 adopt+bind-only shim).
constexpr bool kArmCheckAccount=true;
// S83 SEASONAL — TESTED LIVE, WORKS AT THE DATA LAYER, BUT BUYS NOTHING VISIBLE. Default OFF.
// Setting this adopts a SECOND published track with IsSeasonalPass=1, and the VM builder DOES fill
// SeasonalPassViewModel (verified live: BattlepassViewManager+0x1A8 0x0 -> a real
// BP_BattlepassViewModel_C, BPIM tracks.Num 1->2, BattlepassViewModels 2->3, account VM untouched
// at Levels=86). BUT: (a) the VM is EMPTY and structurally must be — the non-account path uses the
// pure field copier 0x57B9C00 which zeroes Levels (+57B9C86) and never calls the level Init
// 0x57BB560, so no packed asset would help; and (b) **NO SEASONAL TAB APPEARS IN THE UI** — the tab
// strip still shows only HUNTER'S JOURNEY / YOUR REFERRALS, so tab visibility is NOT gated on
// SeasonalPassViewModel being non-null. It is driven by something else, still unidentified.
// => Left OFF: an empty, invisible VM is dead weight and (per the RE) a latent risk if any widget
// ever iterates its Levels unguarded. Flip to true to reproduce the experiment.
constexpr bool kArmSeasonal=false;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20;
constexpr uintptr_t BPIM_TRACKS=0x40, BPIM_NUM=0x48, BPIM_ADOPTED=0x50, BPIM_TARGET=0x58; // BattlepassInfoManager members
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_ONSUCCESS)(void* bpim, void* agg);
typedef void* (*PFN_POPULATE)(void* vm, void* progArr, void* progStruct);
typedef void (*PFN_CHECKACCT)(void* vmgr);   // __fastcall(rcx=BattlepassViewManager); builds the populate's args itself
// S83 diagnostic: the published-pass resolution chain CheckAccountPassChanges runs AFTER its two gates.
// Disasm @0x579454B: mov rcx,rsi; call 0x562BC70; test rax,rax; je bail
//                    lea rdx,[rsp+0x20]; mov rcx,rax; call 0x562BED0; mov rbx,[rsp+0x20]; test rbx,rbx; je bail
// Both are null-checked getters (safe to call). If either yields null we know exactly where it gives up.
typedef void* (*PFN_GET1)(void* vmgr);
typedef void* (*PFN_GET2)(void* x, void* outSlot);
// The VM lookup key. Disasm @0x5794631..0x5794652:
//   mov rax,[rcx]; lea rdx,[rsp+0x48]; call [rax+0x1D0]   -> P->GetPrimaryAssetId(&outPaid)
//   mov rcx,rax;  lea rdx,[rsp+0x38]; call 0x12F4230      -> FPrimaryAssetId::ToString(&outFStr)
//   mov rdx,rax;  mov rcx,rsi;        call 0x57AB180      -> FindVM(ViewManager, K); je skip-populate
// So the populate only runs for a VM stored under K. Our shim-built VM was keyed by the track's
// ProgressionTrackID ("HuntersJourney"), while K is P's PrimaryAssetId string ("<Type>:HuntersJourney").
// A TMap find HASHES the key, so patching the stored string in place would NOT match — instead we
// resolve K at runtime and re-adopt with ProgressionTrackID=K so the game INSERTS the VM under K.
typedef void* (*PFN_GETPAID)(void* obj, void* outPaid);   // virtual, vtable byte-offset 0x1D0 (index 58)
typedef void* (*PFN_PAIDTOSTR)(void* paid, void* outFStr);

constexpr uintptr_t VMGR_ACCOUNTVM=0x198, VM_LEVELS=0xC8, VM_PTA=0xE8;  // BattlepassViewManager.AccountPassViewModel; VM.Levels/ProgressionTrackAsset
constexpr uintptr_t VMGR_PM=0x1C8;                                     // BattlepassViewManager.ProgressionManager
constexpr uintptr_t PM_ACCTTRACK=0x90, TRACK_TIER=0xEC, PM_ACCTFLAG=0x208;  // account track struct / CurrentTierIndex / present-flag
constexpr uintptr_t VM_LEVELSTODISPLAY=0x70;                           // int32; working mastery VM = 8, our account VM = 0
static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_bpim=0, g_vmgr=0, g_asset=0;   // BattlepassInfoManager, BattlepassViewManager, Default__HuntersJourney_C
static uintptr_t g_acctVM=0, g_ptaBefore=0, g_ptaAfter=0;
static PFN_ONSUCCESS g_onSuccess=nullptr;
static PFN_POPULATE g_populate=nullptr;
static PFN_CHECKACCT g_checkAcct=nullptr;
static int32_t g_levelsBefore=-1, g_levelsAfter=-1;
static uintptr_t g_pm=0; static int32_t g_tierBefore=-99, g_tierAfter=-99, g_ltdBefore=-99; static uint8_t g_flagA=0xFF; static bool g_calledCheck=false;
static PFN_GET1 g_get1=nullptr; static PFN_GET2 g_get2=nullptr; static PFN_PAIDTOSTR g_paidToStr=nullptr;
static uintptr_t g_chainX=0, g_chainS=0, g_publishedPass=0;  // 0x562BC70 result, 0x562BED0 out (=P, the pass class)
static wchar_t g_keyw[160]={0}; static bool g_gotKey=false;  // K = P's PrimaryAssetId string == the VM map key
constexpr uintptr_t VMGR_SEASONALVM=0x1A8;                   // BattlepassViewManager.SeasonalPassViewModel
static uintptr_t g_seasonBefore=0, g_seasonAfter=0; static int32_t g_seasonLevels=-1, g_seasonLTD=-1;
static uint8_t g_progArr[0x18]={0};     // empty TArray {Data=0,Num=0,Max=0} (no per-tier progress rows)
static uint8_t g_progStruct[0x18]={0};  // zeroed progress {tier=0,xp=0,cleared=0}
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static int32_t g_preNum=-1,g_postNum=-1,g_preAdopt=-1,g_postAdopt=-1,g_target=-1; static bool g_called=false;

// --- the aggregate + elements (game-thread read by OnSuccess; static, only read via deep-copy) ---
static wchar_t g_idw[]  = L"HuntersJourney";
static wchar_t g_intw[] = L"HuntersJourney";
// Seasonal track identity. The builder looks the VM up by track+0x00 (ProgressionTrackID) and SKIPS
// any track whose ID is already a key in BattlepassViewModels (+57CA963 cmp eax,-1 / jne skip) — that
// is exactly what protects the hard-won account VM — so this MUST be a string not already in the map.
static wchar_t g_seasonIdw[]  = L"Season:supervive-season-1";
static wchar_t g_seasonIntw[] = L"SuperviveSeason1";
#pragma pack(push,1)
static uint8_t g_elems[2][0x120]={};  // LokiPublishedProgressionTrack[]: [0]=account, [1]=seasonal
static uint8_t g_agg[0x18]={0};       // LokiPublishedProgressionTracks { TArray, int64 Version }
#pragma pack(pop)

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static bool LooksLikePtr(uintptr_t v){return v>=0x10000 && v<0x0001000000000000ULL && (v&0x7)==0;}
static bool GetFNameStr(uint32_t id,char* out,int cap){
    uintptr_t* blocks=(uintptr_t*)(g_modBase+kNamePoolRva); uint32_t b=id>>16,off=(id&0xFFFF)<<1;
    if(!SafeReadable(blocks+b,8))return false; uintptr_t bp=blocks[b]; if(!LooksLikePtr(bp))return false;
    if(!SafeReadable((void*)(bp+off),2))return false; uint16_t hdr=*(uint16_t*)(bp+off); int len=hdr>>6; bool wide=(hdr&1)!=0;
    if(len<=0||len>=cap)return false;
    if(wide){for(int i=0;i<len;i++)out[i]=(char)*(uint16_t*)(bp+off+2+i*2);} else {if(!SafeReadable((void*)(bp+off+2),len))return false;for(int i=0;i<len;i++)out[i]=((char*)(bp+off+2))[i];}
    out[len]=0;return true;
}
static uint32_t NameId(uintptr_t obj){ if(!SafeReadable((void*)(obj+NAME_OFF),4))return 0; return *(uint32_t*)(obj+NAME_OFF); }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static bool NameStartsDefault(uintptr_t obj){ char nm[96]; if(!GetFNameStr(NameId(obj),nm,sizeof(nm)))return true; return strncmp(nm,"Default__",9)==0; }

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>8)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);
    return EXCEPTION_CONTINUE_SEARCH;
}
static void SetFString(uint8_t* p, wchar_t* s){ int n=(int)wcslen(s)+1; *(uint64_t*)(p+0)=(uint64_t)s; *(uint32_t*)(p+8)=(uint32_t)n; *(uint32_t*)(p+12)=(uint32_t)n; }

// Resolve K = P->GetPrimaryAssetId().ToString() — the key the VM must be stored under for
// CheckAccountPassChanges' FindVM (0x57AB180) to hit and reach the populate. Game thread only.
static void ResolveKey(){
    if(g_gotKey || !g_get1 || !g_get2 || !g_paidToStr) return;
    g_chainX=(uintptr_t)g_get1((void*)g_vmgr);
    if(!LooksLikePtr(g_chainX)) return;
    uintptr_t slot=0; g_get2((void*)g_chainX,(void*)&slot); g_chainS=slot;   // P (the pass class)
    if(!LooksLikePtr(g_chainS)||!SafeReadable((void*)g_chainS,8)) return;
    uintptr_t vt=*(uintptr_t*)g_chainS;
    if(!LooksLikePtr(vt)||!SafeReadable((void*)(vt+kGetPaidVtblSlot*8),8)) return;
    PFN_GETPAID getPaid=(PFN_GETPAID)*(uintptr_t*)(vt+kGetPaidVtblSlot*8);
    uint8_t paid[16]={0}; getPaid((void*)g_chainS,paid);          // FPrimaryAssetId {FName Type, FName Name}
    uint8_t fs[16]={0};  g_paidToStr((void*)paid,(void*)fs);      // FString {wchar* Data, int32 Num, int32 Max}
    uintptr_t p=*(uintptr_t*)fs; int32_t n=*(int32_t*)(fs+8);
    if(!LooksLikePtr(p)||n<=1||n>150||!SafeReadable((void*)p,(size_t)n*2)) return;
    for(int i=0;i<n && i<159;i++) g_keyw[i]=*(wchar_t*)(p+i*2);
    g_keyw[(n<159?n:159)]=0; g_gotKey=true;
}

// SEASONAL (S83): the account and seasonal view models are built by the SAME builder (true entry
// 0x57CA670 — note 0x57CAB50 from earlier notes is MID-INSTRUCTION), which iterates the adopted
// tracks at BattlepassInfoManager+0x40 (stride 0x120) and switches on the per-track flag bytes:
//     +57CACF5 cmp byte ptr [r15+0xAB],0 ; +57CACFD je skip      <- bIsSeasonalPass
//     +57CADF2 mov qword ptr [r13+0x1a8], rax                    <- SeasonalPassViewModel
// Slots proven by live UClass reflection: Account=+0x198, Referral=+0x1A0, Seasonal=+0x1A8
// (so track+0xAA=bIsReferralPass, track+0xAB=bIsSeasonalPass). The builder reads the INFO manager,
// NOT the ProgressionManager — zero refs to PM+0x388/0x210/0x2FC in its 688-instruction body — so
// the account-progress lever cannot build this; it needs its own adopted track. We are the writer of
// BattlepassInfoManager+0x40 (OnSuccess deep-copies this aggregate), so we hand it a FRESH 2-element
// array rather than appending — the live Num=1,Max=1 is an exact-fit allocation with no slack.
//
// EXPECTATION, so nobody misreads the result: the seasonal VM will be BUILT BUT EMPTY. The non-account
// path uses the pure field copier 0x57B9C00, which explicitly ZEROES the Levels count
// (+57B9C86 mov dword[r15+8],r14d with r15=VM+0xC8, r14d=0) and never calls the level Init 0x57BB560.
// A seasonal ladder is therefore structurally impossible through this path, with or without a packed
// asset (and no packed LokiDataAsset_Season exists in this build anyway). Live negative control: the
// game-built VM at 'HuntersJourney' has LevelsToDisplay=0 / Levels=0 — that is this copier's output.
// RISK ACCEPTED: a non-null-but-empty SeasonalPassViewModel could regress the currently-rendering
// passes page if the widget iterates Levels unguarded. Set kArmSeasonal=false to revert to 1 track.
static void BuildAggregate(){
    memset(g_elems,0,sizeof(g_elems)); memset(g_agg,0,sizeof(g_agg));
    // [0] ACCOUNT — ProgressionTrackID doubles as the VM's map key, so use K when we resolved it.
    SetFString(g_elems[0]+0x00, g_gotKey?g_keyw:g_idw);
    SetFString(g_elems[0]+0x10, g_intw);  // Details.InternalId (Details @ elem+0x10)
    g_elems[0][0xA9]=1;                    // IsAccountPass = true
    // everything else (Details.Season/Start/End/TierPurchaseDetails/RewardTracks[]/ExperienceRequiredPerLevel[],
    // Is{Retired,Referral,Seasonal}, PurchaseDetails{RewardTrackToItemInfo map, TierItemInfo}) stays zeroed = empty.
    // NB the zero season WINDOW is safe: the builder's date check soft-fails OPEN on an empty window
    // (+57CADA0 je 0x57CADC1 fires before the hard compare at +57CADB7).
    int nTracks=1;
    if(kArmSeasonal){
        // [1] SEASONAL — same shape, different flag byte and a map key not already present.
        SetFString(g_elems[1]+0x00, g_seasonIdw);
        SetFString(g_elems[1]+0x10, g_seasonIntw);
        g_elems[1][0xAB]=1;                // IsSeasonalPass = true
        nTracks=2;
    }
    *(uint64_t*)(g_agg+0x00)=(uint64_t)g_elems; // ProgressionTracks.Data
    *(uint32_t*)(g_agg+0x08)=(uint32_t)nTracks; // .Num
    *(uint32_t*)(g_agg+0x0C)=(uint32_t)nTracks; // .Max
    // Version must EXCEED the currently-adopted value or OnSuccess's `jle` skips the adopt+broadcast.
    // BUMP THIS on every re-inject into an already-adopted process (the marker prints the adopted value).
    *(int64_t*) (g_agg+0x10)=104;              // Version high (> current adopted) so re-adopt + rebuild fires
}

extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    if(!g_bpim || !g_onSuccess){ return; }
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    // snapshot pre-state
    if(SafeReadable((void*)(g_bpim+BPIM_NUM),4))     g_preNum=*(int32_t*)(g_bpim+BPIM_NUM);
    if(SafeReadable((void*)(g_bpim+BPIM_ADOPTED),4))  g_preAdopt=*(int32_t*)(g_bpim+BPIM_ADOPTED);
    if(SafeReadable((void*)(g_bpim+BPIM_TARGET),4))   g_target=*(int32_t*)(g_bpim+BPIM_TARGET);
    ResolveKey();      // must precede BuildAggregate: K becomes the track's ProgressionTrackID == VM map key
    BuildAggregate();
    if(g_vmgr && SafeReadable((void*)(g_vmgr+VMGR_SEASONALVM),8)) g_seasonBefore=*(uintptr_t*)(g_vmgr+VMGR_SEASONALVM);
    g_called=true;
    g_onSuccess((void*)g_bpim, (void*)g_agg);   // *** force-adopt on the game thread => broadcast builds the account VM ***
    if(SafeReadable((void*)(g_bpim+BPIM_NUM),4))     g_postNum=*(int32_t*)(g_bpim+BPIM_NUM);
    if(SafeReadable((void*)(g_bpim+BPIM_ADOPTED),4))  g_postAdopt=*(int32_t*)(g_bpim+BPIM_ADOPTED);
    if(g_vmgr && SafeReadable((void*)(g_vmgr+VMGR_SEASONALVM),8)){
        g_seasonAfter=*(uintptr_t*)(g_vmgr+VMGR_SEASONALVM);
        if(LooksLikePtr(g_seasonAfter)){
            if(SafeReadable((void*)(g_seasonAfter+VM_LEVELS+8),4))        g_seasonLevels=*(int32_t*)(g_seasonAfter+VM_LEVELS+8);
            if(SafeReadable((void*)(g_seasonAfter+VM_LEVELSTODISPLAY),4)) g_seasonLTD   =*(int32_t*)(g_seasonAfter+VM_LEVELSTODISPLAY);
        }
    }
    // *** bind the packed HuntersJourney_C asset into the built account VM so its tiers can render ***
    if(g_vmgr && g_asset && SafeReadable((void*)(g_vmgr+VMGR_ACCOUNTVM),8)){
        g_acctVM=*(uintptr_t*)(g_vmgr+VMGR_ACCOUNTVM);
        if(LooksLikePtr(g_acctVM) && SafeReadable((void*)(g_acctVM+VM_PTA),8)){
            g_ptaBefore=*(uintptr_t*)(g_acctVM+VM_PTA);
            *(uintptr_t*)(g_acctVM+VM_PTA)=g_asset;              // ProgressionTrackAsset = Default__HuntersJourney_C
            g_ptaAfter=*(uintptr_t*)(g_acctVM+VM_PTA);
            // S82 p12 (DEAD END, kept as a warning): calling the populate 0x57DF4B0 DIRECTLY with
            // rdx={0,0,0} and a zeroed r8 CRASHED the game thread. Live RPM later showed why: Levels is a
            // TArray<UObject*> of per-tier BP_BattlepassLevelViewModel_<Kind>_C objects that the populate
            // CONSTRUCTS — it needs far more real context than fabricated args can supply. Never re-arm this.
            //
            // S83 (this path): don't fabricate args — satisfy the REAL caller's gates and let the GAME build
            // them. CheckAccountPassChanges (0x5794480, rcx=ViewManager) is the populate's real caller. It is
            // gated on:
            //   Gate A: byte[PM+0x208] != 0      (account track present; normally set by the /progression lever)
            //   Gate B: dword[PM+0x90+0xEC] != -1 (CurrentTierIndex; the account track is default-init'd to -1)
            // LIVE-MEASURED on a running game: Gate A = 1 (passes) but Gate B = -1 (FAILS) => the populate is
            // never reached => Levels stays empty => the PASSES tier grid renders blank. No backend field
            // feeds +0xEC (proven over a fresh-login test with distinctive values), so we set it here.
            if(kArmCheckAccount && g_checkAcct && g_ptaAfter==g_asset && SafeReadable((void*)(g_vmgr+VMGR_PM),8)){
                g_pm=*(uintptr_t*)(g_vmgr+VMGR_PM);
                if(LooksLikePtr(g_pm) && SafeReadable((void*)(g_pm+PM_ACCTFLAG),1)
                                      && SafeReadable((void*)(g_pm+PM_ACCTTRACK+TRACK_TIER),4)){
                    g_flagA=*(uint8_t*)(g_pm+PM_ACCTFLAG);
                    if(g_flagA==0) *(uint8_t*)(g_pm+PM_ACCTFLAG)=1;              // gate A
                    g_tierBefore=*(int32_t*)(g_pm+PM_ACCTTRACK+TRACK_TIER);
                    if(g_tierBefore<0) *(int32_t*)(g_pm+PM_ACCTTRACK+TRACK_TIER)=0;  // gate B: -1 sentinel -> tier 0
                    g_tierAfter=*(int32_t*)(g_pm+PM_ACCTTRACK+TRACK_TIER);
                    if(SafeReadable((void*)(g_acctVM+VM_LEVELS+8),4))        g_levelsBefore=*(int32_t*)(g_acctVM+VM_LEVELS+8);
                    if(SafeReadable((void*)(g_acctVM+VM_LEVELSTODISPLAY),4)) g_ltdBefore  =*(int32_t*)(g_acctVM+VM_LEVELSTODISPLAY);
                    g_calledCheck=true;   // (ResolveKey already walked the published-pass chain above)
                    g_checkAcct((void*)g_vmgr);   // *** the game builds the populate's args from its own state ***
                    if(SafeReadable((void*)(g_acctVM+VM_LEVELS+8),4))        g_levelsAfter =*(int32_t*)(g_acctVM+VM_LEVELS+8);
                }
            }
        }
    }
    g_done=1; g_inHook=0;
}

static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};for(int i=0;i<2;i++){if(!cands[i])continue;void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(p){intptr_t d=(intptr_t)p-(intptr_t)anchor;if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000)return (uint8_t*)p;VirtualFree(p,0,MEM_RELEASE);}}}return nullptr;}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
static uint8_t* BuildHook(uintptr_t fn,const uint8_t stolen[5]){
    uint8_t* blk=NearAlloc(fn,0x200); if(!blk)return nullptr;
    Emit t{blk}; for(int i=0;i<5;i++)EB(t,stolen[i]); EB(t,0xE9); int32_t rel=(int32_t)((intptr_t)(fn+5)-((intptr_t)t.w+4)); EU32(t,(uint32_t)rel); g_tramp=(PFN_PE)blk;
    uint8_t* stub=blk+0x20; Emit e{stub};
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51); EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnPI); EB(e,0xFF);EB(e,0xD0);
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28); EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk); EB(e,0xFF);EB(e,0xE0);
    return stub;
}
static bool SafeWrite(uint8_t* dst,const uint8_t* src,size_t len){
    DWORD myTid=GetCurrentThreadId(),myPid=GetCurrentProcessId(); HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0); if(snap==INVALID_HANDLE_VALUE)return false;
    HANDLE hs[1024]; int nh=0; THREADENTRY32 te; te.dwSize=sizeof(te);
    if(Thread32First(snap,&te)){do{if(te.th32OwnerProcessID==myPid&&te.th32ThreadID!=myTid&&nh<1024){HANDLE ht=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,te.th32ThreadID);if(ht)hs[nh++]=ht;}}while(Thread32Next(snap,&te));} CloseHandle(snap);
    uintptr_t lo=(uintptr_t)dst,hi=(uintptr_t)dst+len; bool ok=false;
    for(int a=0;a<400&&!ok;a++){ for(int i=0;i<nh;i++)SuspendThread(hs[i]); bool unsafe=false;
        for(int i=0;i<nh;i++){CONTEXT c;c.ContextFlags=CONTEXT_CONTROL;if(GetThreadContext(hs[i],&c)){if(c.Rip>=lo&&c.Rip<hi){unsafe=true;break;}}}
        if(!unsafe){DWORD op=0;if(VirtualProtect(dst,len,PAGE_EXECUTE_READWRITE,&op)){memcpy(dst,src,len);DWORD d=0;VirtualProtect(dst,len,op,&d);FlushInstructionCache(GetCurrentProcess(),dst,len);ok=true;}}
        if(!ok){for(int i=0;i<nh;i++)ResumeThread(hs[i]);Sleep(1);} }
    for(int i=0;i<nh;i++){ResumeThread(hs[i]);CloseHandle(hs[i]);} return ok;
}
static bool InstallHook(){ if(!g_pi||!g_stub)return false; int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5)); uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)}; return SafeWrite(g_pi,p,5); }
static void UninstallHook(){ if(g_pi)SafeWrite(g_pi,g_stolen,5); }
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

static bool ObjNameIs(uintptr_t obj,const char* w){ char b[96]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
// One GUObjectArray pass: BattlepassInfoManager (g_bpim), BattlepassViewManager (g_vmgr),
// packed HuntersJourney track CDO (g_asset = Default__HuntersJourney_C).
static void FindObjects(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!g_bpim  && ClassNameIs(obj,"BattlepassInfoManager")  && !NameStartsDefault(obj)) g_bpim=obj;
            else if(!g_vmgr  && ClassNameIs(obj,"BattlepassViewManager")  && !NameStartsDefault(obj)) g_vmgr=obj;
            else if(!g_asset && ObjNameIs(obj,"Default__HuntersJourney_C")) g_asset=obj;
        } }
}

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] battlepass_adopt_fix (force OnSuccess adoption of HuntersJourney account pass) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_onSuccess=(PFN_ONSUCCESS)(g_modBase+kOnSuccessRva);
    g_populate =(PFN_POPULATE)(g_modBase+kPopulateRva);
    g_checkAcct=(PFN_CHECKACCT)(g_modBase+kCheckAcctRva);
    g_get1=(PFN_GET1)(g_modBase+kGet1Rva); g_get2=(PFN_GET2)(g_modBase+kGet2Rva); g_paidToStr=(PFN_PAIDTOSTR)(g_modBase+kPaidToStrRva);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ FindObjects(); if(g_bpim&&g_vmgr&&g_asset)break; Sleep(500);}
    if(!g_bpim){Marker("[2] FAIL find BattlepassInfoManager\r\n");return 3;}
    Markerf("[2b] vmgr=0x%llX asset(HuntersJourney_C)=0x%llX\r\n",(unsigned long long)g_vmgr,(unsigned long long)g_asset);
    int32_t num0=-1,adopt0=-1,tgt0=-1;
    if(SafeReadable((void*)(g_bpim+BPIM_NUM),4))num0=*(int32_t*)(g_bpim+BPIM_NUM);
    if(SafeReadable((void*)(g_bpim+BPIM_ADOPTED),4))adopt0=*(int32_t*)(g_bpim+BPIM_ADOPTED);
    if(SafeReadable((void*)(g_bpim+BPIM_TARGET),4))tgt0=*(int32_t*)(g_bpim+BPIM_TARGET);
    Markerf("[2] BPIM=0x%llX  pre: Num=%d adopted=%d target=%d  OnSuccess=0x%llX\r\n",(unsigned long long)g_bpim,num0,adopt0,tgt0,(unsigned long long)g_onSuccess);
    g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Marker("[3] hook built; installing to catch the game thread and force adoption...\r\n");
    if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");return 6;}
    DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<10000) Sleep(20);
    UninstallHook();
    if(g_done){
        Markerf("[4] called=%d  pre(Num=%d adopted=%d target=%d) -> post(Num=%d adopted=%d)\r\n",g_called,g_preNum,g_preAdopt,g_target,g_postNum,g_postAdopt);
        Markerf("[4] account VM=0x%llX  ProgressionTrackAsset +0xE8: before=0x%llX -> after=0x%llX (bound=%s to HuntersJourney_C 0x%llX)\r\n",
                (unsigned long long)g_acctVM,(unsigned long long)g_ptaBefore,(unsigned long long)g_ptaAfter,
                (g_ptaAfter==g_asset&&g_asset)?"YES":"NO",(unsigned long long)g_asset);
        Markerf("[5] gates: PM=0x%llX flagA(+0x208)=%u  tier(+0x90+0xEC): before=%d -> after=%d  LevelsToDisplay(+0x70)=%d  calledCheckAccountPassChanges=%d\r\n",
                (unsigned long long)g_pm,(unsigned)g_flagA,g_tierBefore,g_tierAfter,g_ltdBefore,(int)g_calledCheck);
        { char kn[192]="(unresolved)"; if(g_gotKey){ int i=0; for(;g_keyw[i]&&i<190;i++) kn[i]=(char)g_keyw[i]; kn[i]=0; }
          char sn[96]="(null)"; if(LooksLikePtr(g_chainS)&&!GetFNameStr(NameId(g_chainS),sn,sizeof(sn))) sn[0]=0;
          Markerf("[5] published-pass chain: X(assetloader)=0x%llX  P(pass class)=0x%llX name='%s'\r\n",
                  (unsigned long long)g_chainX,(unsigned long long)g_chainS,sn);
          Markerf("[5] VM lookup key K = P->GetPrimaryAssetId().ToString() = '%s'   (track ProgressionTrackID set to this)\r\n",kn); }
        Markerf("[5] Levels via CheckAccountPassChanges: before=%d -> after=%d %s\r\n",g_levelsBefore,g_levelsAfter,(g_levelsAfter>0)?"*** TIER GRID BUILT ***":"(still empty)");
        Markerf("[6] SEASONAL (kArmSeasonal=%d): SeasonalPassViewModel@+0x1A8 before=0x%llX -> after=0x%llX  Levels=%d LevelsToDisplay=%d  %s\r\n",
                (int)kArmSeasonal,(unsigned long long)g_seasonBefore,(unsigned long long)g_seasonAfter,g_seasonLevels,g_seasonLTD,
                (!g_seasonBefore&&g_seasonAfter)?"*** SEASONAL VM BUILT (empty ladder is EXPECTED — copier zeroes Levels) ***":"(unchanged)");
        if(g_postNum>0 && g_ptaAfter==g_asset && g_asset && g_levelsAfter>0) Marker("[4] *** ADOPTED + account VM + asset bound + Levels tier grid POPULATED. Passes account tab is data-ready. ***\r\n");
        else if(g_postNum>0 && g_ptaAfter==g_asset && g_asset) Marker("[4] *** ADOPTED + account VM built + HuntersJourney_C bound (Levels not built — open PASSES; widget may populate on display). ***\r\n");
        else if(g_postNum>0) Marker("[4] *** ADOPTED + VM built, but asset bind incomplete (vmgr/asset/acctVM missing). ***\r\n");
        else Marker("[4] adoption did NOT populate (Num still 0).\r\n");
    } else Markerf("[4] TIMEOUT (hitsGT=%ld, bpim=0x%llX)\r\n",(long)g_hitsGT,(unsigned long long)g_bpim);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
