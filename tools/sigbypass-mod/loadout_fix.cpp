// loadout_fix — SESSION (2026-07-08): CUSTOMIZATION persistence via the s55 native-call primitive.
//
// Problem (docs/session-53-customization-persistence.md): equips (hunter skins, gliders, chromas) are
// saved server-side and apply live on click, but on page re-entry / relaunch the customization page
// reverts to the DEFAULT. Root cause: the client fetches the loadout once at login via
// GET /personalization/players/{id} and hands it to UPersonalizationManager::RefreshCurrentLoadoutOperation,
// but that op does NOT populate the in-memory loadout from OUR response (unknown shape; the dead server's
// real response was never captured). Even the clean glider array field fails => whole-loadout parse drop.
//
// FIX (client-side, chosen by the user): replay the saved equips by calling the game's OWN native setters
// on the game thread, so the game itself builds the loadout containers + fires OnUpdated (exactly like a
// real click). Reuses the Avenue-A native-call primitive proven in missions_nativecall_probe17/18:
// hook ProcessInternal @base+0x13454A0, capture a live FFrame template, then call each native UFunction's
// thunk (@UFunction+0xE0) with a hand-built FFrame from the game thread.
//
// Targets (native UPersonalizationManager methods; resolved by name off the instance's class):
//   SetHeroCosmeticsBundlePreference(const FPrimaryAssetId& Hero, const FPrimaryAssetId& Bundle)   [skins]
//   SetSlotCosmetic(FName Slot, const FPrimaryAssetId& Asset)                                       [gliders/wisps/…]
//   SetLuxeSkinChromaPreference(const FPrimaryAssetId& Luxe, const FPrimaryAssetId& Chroma)         [chromas]
// String->FPrimaryAssetId via LokiAssetManager::PrimaryAssetIDFromString(const FString&) -> FPrimaryAssetId
// (16B in the result buffer). That ALSO yields any FName: PrimaryAssetIDFromString("x:Glider").name = FName("Glider").
//
// Data source: GET http://127.0.0.1:8080/revival/loadout (served by ags interactive.loadout.go), a flat
//   {"heroCosmeticsBundles":{"Hero:X":"HeroCosmeticsBundle:Y",...},"slotCosmetics":{"Glider":"SlotCosmetics:Z",...},"luxeChromas":{...}}
//
// Build:  clang++ -shared -O2 loadout_fix.cpp -o loadout_fix.dll -lkernel32 -lwininet
// Inject: tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/loadout_fix.dll
// Marker: docs/loadout-fix-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <wininet.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <cstdlib>

static const char* kMarkerPath  = "G:\\git\\Supervive Revival Project\\docs\\loadout-fix-marker.txt";
static const char* kLoadoutUrl  = "http://127.0.0.1:8080/revival/loadout";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
// GetDefaultCosmeticsBundleIdForHeroId (resolved 2026-07-09 via usmapdump). This is the SHARED
// fallback the SKIN tab + party slot use for a hero's DEFAULT bundle when the party-member cosmetic
// is empty (which it always is — the client ignores the /party echo). Redirecting it per-hero to the
// SAVED skin makes both surfaces show the saved skin persistently, poll-proof.
//   exec thunk @RVA 0x52B3400 (FFrame sig: reads the hero FPrimaryAssetId param, calls the impl,
//     movups the 16-byte result into the FFrame Result)
//   native impl @RVA 0x55899C0 (C ABI: FPrimaryAssetId* fn(out /*rcx*/, hero /*rdx*/))
// We hook via the UFunction.Func POINTER SWAP (heap), NOT an inline .text patch: a persistent .text
// patch on the impl tripped the game's ~3-5min .text integrity check (crash, 2026-07-09). UE5.4
// execCallMathFunction reads UFunction->Func (@+0xE0) at call time, so swapping that heap field
// redirects every call with zero .text modification (invisible to a code checksum).
constexpr uintptr_t kGdcbThunkRva=0x52B3400;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, OUTER_OFF=0x28, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58, USTRUCT_CHILDREN=0x50, UFUNC_SCRIPT=0x68;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_OUTPARMS=0x80, FF_PROPCHAIN=0x88;
constexpr uintptr_t FLD_NEXT=0x18, FLD_FLAGS=0x38, FLD_OFFSET=0x44, FIELD_NEXT=0x30;
constexpr uint64_t CPF_OutParm=0x100, CPF_ReturnParm=0x400;
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

struct Fn { void* fn; uintptr_t thunk; uintptr_t child; };
static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_lam=0, g_pm=0, g_party=0;       // LokiAssetManager, PersonalizationManager, PartyManager instances
static Fn g_pafs{}, g_setBundle{}, g_setSlot{}, g_setChroma{}, g_getBundle{}, g_tryPick{};
static Fn g_getHeroAsset{};                        // native GetHeroAssetFromPrimaryAssetId(PAID) -> ULokiHeroAsset*
// GAP 1 re-render: Comp_MainMenu_PartySlotSubject.Refresh() (BP fn) re-runs DetermineCosmeticToShow so the
// main-menu center hunter re-reads the patched fallback cosmetic. Resolved + invoked via pi8's InvokeBP.
static uintptr_t g_subjClass=0; static void* g_subjects[8]={0}; static int g_nsubj=0; static void* g_refreshFn=nullptr;
static uint64_t g_bplocals[24]={0}; static volatile long g_refreshDone=0, g_refreshCalls=0;
static volatile long g_centerDirty=0;   // set when a skin changed at runtime -> re-arm a live main-menu Refresh
static volatile long g_dirtyTick=0;     // GetTickCount() when the change was detected (latency instrumentation)
// CUSTOMIZATION OVERVIEW pedestal re-render: WBP_UI_Loadout_CustomizationScreen_C.PreviewCurrentSkin() (BP fn)
// re-previews the current skin on the customization pedestal (separate actor from the main-menu subject).
static uintptr_t g_custClass=0; static void* g_custScreens[8]={0}; static int g_nCust=0; static void* g_previewSkinFn=nullptr;
static void* g_previewAssetFn=nullptr; static int g_custParamsDumped=0;   // PreviewAsset(<asset>) — the per-slot hover-preview
static volatile long g_custResolvedTick=0;   // when the customization screens were (re)found = a NAV just happened
// LEVER #B (2026-07-10 part 7): the render checks member.CosmeticsAssetID FIRST (before the CDO fallback).
// Keeping it = the current hero's saved/selected skin makes EVERY surface follow the selection instead of
// fighting it (the CDO patch is a fixed value that reverts new picks). We only BACKFILL when the field is
// empty (the ~1s /party poll wipes it) — while the client holds a live pick we leave it, so the pick shows.
static uintptr_t g_member=0, g_memberClass=0, g_memberCosmeticOff=0;   // PartyMemberModel + CosmeticsAssetID offset
static volatile long g_memberWrites=0, g_memberClears=0; static int g_memberDumped=0;
constexpr uintptr_t MEMBER_HEROID=0x78;   // member.HeroAssetID FPrimaryAssetId (pi8-confirmed): type@+0x78 name@+0x80
// Per-hero cache of the last valid HeroCosmeticsBundle PAID observed on the member (= the client's live pick).
// Seeded from /revival/loadout on load; updated live from the client's picks. Restored after the ~1s poll wipe
// so the render FOLLOWS picks (changeability) and NEVER shows a cross-hero bundle (Brall previewed while a
// RocketJumper bundle lingered). Cross-hero mismatches are actively CLEARED.
struct McCache { char code[64]; uint64_t paid[2]; };
static McCache g_mc[128]; static int g_mcN=0;   // 128 == LMAX (defined later); per-hero pick cache
static int McFind(const char* code){ for(int i=0;i<g_mcN;i++) if(_stricmp(g_mc[i].code,code)==0) return i; return -1; }
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static volatile long g_applyDone=0,g_cdoDone=0,g_trypicked=0;   // PI-hook state machine: apply -> (off-thread CDO patch) -> TryPick
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};
static uint64_t g_pbuf[16]={0}, g_rbuf[4]={0}; static uint8_t g_outparms[8*24]={0};

// Parsed loadout feed (from ags GET /revival/loadout).
constexpr int LMAX=128;
struct Pair { wchar_t k[96]; wchar_t v[96]; };
static Pair g_bundles[LMAX]; static int g_nBundles=0;   // (Hero:X, HeroCosmeticsBundle:Y)
static Pair g_slots[LMAX];   static int g_nSlots=0;     // (SlotName,  SlotCosmetics:Z)
static Pair g_chromas[LMAX]; static int g_nChromas=0;   // (LuxeId,    ChromaId)
static int g_applied=0, g_fetchOk=0;
static wchar_t g_selectedHero[96]={0};                  // "Hero:<name>" — current party hero (from /revival/loadout)

// ---- GetDefaultCosmeticsBundleIdForHeroId redirect (the persistent skin fix, via Func-swap) ----
// Precomputed in ApplyLoadout (game thread, PAIDFromString available): for each saved bundle, the
// hero CODENAME ("Alchemist", from the "Hero:X" key) + the saved bundle's full 16-byte FPrimaryAssetId.
// The replacement thunk calls the ORIGINAL exec thunk to get the game's DEFAULT bundle, then matches
// the default's name prefix to a saved hero and overwrites the result with the saved bundle — no
// FFrame param parsing, no .text patch.
static char     g_gdcbCode[LMAX][128];  // hero codename ("Alchemist")
static uint64_t g_gdcbBundle[LMAX][2];  // live FPrimaryAssetId (16B): {typeFName, nameFName} — what MyGdcbThunk writes
static wchar_t  g_gdcbWantV[LMAX][96];   // desired bundle string per hero (from the latest /revival/loadout poll)
static wchar_t  g_gdcbHaveV[LMAX][96];   // the string g_gdcbBundle was last converted from (change detection)
static int      g_gdcbN=0;
static uintptr_t g_gdcbFunc=0;          // the UFunction object (Func ptr @ +0xE0)
static PFN_THUNK g_origExecThunk=nullptr; // original exec thunk (base+kGdcbThunkRva)
static volatile long g_gdcbInstalled=0, g_gdcbHits=0, g_gdcbDirty=0, g_gdcbConverting=0;
// Hero-asset DefaultCosmeticsBundle patch (fixes the 3D RENDER, which reads
// LokiHeroAsset.DefaultCosmeticsBundle as the fallback when the member cosmetic is empty).
static uintptr_t g_dcbOff=0;            // DefaultCosmeticsBundle field offset in LokiHeroAsset (found once)
static int g_dcbPatched=0;
static volatile long g_gdcbRepatch=0;  // request the bg thread to (re)patch hero DefaultCosmeticsBundle
// Cache of the per-hero DefaultCosmeticsBundle CDO field addresses (from the off-thread scan) so a live
// skin change can repatch the CDO INSTANTLY (single 16B write, any thread) instead of waiting for the slow
// ~500k-object rescan — this is what makes the MAIN-MENU center update snappily on a change.
struct CdoEntry { char code[64]; uintptr_t obj; uintptr_t off; };
static CdoEntry g_cdoCache[16]; static int g_cdoCacheN=0;

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
static bool NameIs(uintptr_t obj,const char* w){ char b[160]; if(!GetFNameStr(NameId(obj),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static uintptr_t ClassOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+CLASS_OFF),8))return 0; return *(uintptr_t*)(obj+CLASS_OFF); }
static uintptr_t OuterOf(uintptr_t obj){ if(!SafeReadable((void*)(obj+OUTER_OFF),8))return 0; return *(uintptr_t*)(obj+OUTER_OFF); }
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }
static bool ClassNameHas(uintptr_t obj,const char* sub){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strstr(b,sub)!=nullptr; }
static bool StrIContains(const char* hay,const char* needle){ size_t nl=strlen(needle); if(!nl)return false; for(const char* p=hay;*p;p++){ if(_strnicmp(p,needle,nl)==0) return true; } return false; }

static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>8)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX inHook=%ld\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0),(long)g_inHook);
    return EXCEPTION_CONTINUE_SEARCH;
}

// ---- native-call primitive (Avenue A; identical to missions_nativecall_probe18) ----
static void BuildOutParms(uintptr_t childProps, uint8_t* locals){
    memset(g_outparms,0,sizeof(g_outparms)); *(uint64_t*)(g_myframe+FF_OUTPARMS)=0;
    uintptr_t f=childProps; int n=0; uint8_t* prev=nullptr; uint8_t* head=nullptr;
    while(LooksLikePtr(f) && n<8){
        uint64_t flags=0; if(SafeReadable((void*)(f+FLD_FLAGS),8)) flags=*(uint64_t*)(f+FLD_FLAGS);
        if((flags&CPF_OutParm) && !(flags&CPF_ReturnParm)){
            int32_t off=0; if(SafeReadable((void*)(f+FLD_OFFSET),4)) off=*(int32_t*)(f+FLD_OFFSET);
            uint8_t* rec=g_outparms+n*24; *(uintptr_t*)(rec+0)=f; *(uintptr_t*)(rec+8)=(uintptr_t)(locals+off); *(uintptr_t*)(rec+16)=0;
            if(prev) *(uintptr_t*)(prev+16)=(uintptr_t)rec; else head=rec; prev=rec; n++;
        }
        uintptr_t nx=0; if(SafeReadable((void*)(f+FLD_NEXT),8)) nx=*(uintptr_t*)(f+FLD_NEXT); f=nx;
    }
    *(uint64_t*)(g_myframe+FF_OUTPARMS)=(uint64_t)head;
}
static void Call(Fn& F, void* context, void* paramsBuf, void* resultBuf){
    memcpy(g_myframe, g_template, sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=F.fn; *(void**)(g_myframe+FF_OBJECT)=context;
    *(uint64_t*)(g_myframe+FF_CODE)=0; *(void**)(g_myframe+FF_LOCALS)=paramsBuf;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)F.child;
    BuildOutParms(F.child,(uint8_t*)paramsBuf);
    ((PFN_THUNK)F.thunk)(context, g_myframe, resultBuf);
}
static void SetFString(uint64_t* pbuf, const wchar_t* s){ int n=(int)wcslen(s)+1; ((uint64_t*)pbuf)[0]=(uint64_t)s; ((uint32_t*)pbuf)[2]=(uint32_t)n; ((uint32_t*)pbuf)[3]=(uint32_t)n; }

// Ordered input-param offsets (excludes the ReturnValue), so struct/FName args land where the thunk reads them.
static int ParamOffsets(Fn& F, int* offs, int maxn){
    int n=0; uintptr_t f=F.child;
    while(LooksLikePtr(f) && n<maxn){
        uint64_t flags=0; if(SafeReadable((void*)(f+FLD_FLAGS),8)) flags=*(uint64_t*)(f+FLD_FLAGS);
        if(!(flags&CPF_ReturnParm)){ int32_t off=0; if(SafeReadable((void*)(f+FLD_OFFSET),4)) off=*(int32_t*)(f+FLD_OFFSET); offs[n++]=off; }
        uintptr_t nx=0; if(SafeReadable((void*)(f+FLD_NEXT),8)) nx=*(uintptr_t*)(f+FLD_NEXT); f=nx;
    }
    return n;
}
// str -> FPrimaryAssetId (type FName @ret[0], name FName @ret[1]); returns false if type is None.
static bool PAIDFromString(const wchar_t* s, uint64_t out[2]){
    if(!g_pafs.thunk||!g_lam) return false;
    static wchar_t sbuf[128]; wcsncpy_s(sbuf,128,s,_TRUNCATE);
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); SetFString(g_pbuf,sbuf);
    Call(g_pafs,(void*)g_lam,g_pbuf,g_rbuf);
    out[0]=g_rbuf[0]; out[1]=g_rbuf[1];
    return (uint32_t)(out[0]&0xFFFFFFFF)!=0;
}
// FName(name) via a throwaway "Slot:<name>" PrimaryAssetId; returns the packed 8B FName of the name part.
static uint64_t FNameFromString(const wchar_t* name){
    wchar_t tmp[128]; _snwprintf_s(tmp,128,_TRUNCATE,L"Slot:%s",name); uint64_t pa[2]={0,0};
    if(!PAIDFromString(tmp,pa)) return 0; return pa[1];
}

// Call a native fn(PAID a, PAID b) on `ctx`: SetHeroCosmeticsBundlePreference / SetLuxeSkinChromaPreference
// (ctx=PersonalizationManager) or TryPickMyHeroAndCosmetics (ctx=PartyManager).
static bool CallSet2PAID(Fn& F, void* ctx, const uint64_t a[2], const uint64_t b[2]){
    if(!F.thunk||!ctx) return false;
    int offs[6]; int n=ParamOffsets(F,offs,6); if(n<2) return false;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+offs[0])=a[0]; *(uint64_t*)((uint8_t*)g_pbuf+offs[0]+8)=a[1];
    *(uint64_t*)((uint8_t*)g_pbuf+offs[1])=b[0]; *(uint64_t*)((uint8_t*)g_pbuf+offs[1]+8)=b[1];
    Call(F,ctx,g_pbuf,g_rbuf); return true;
}
// SetSlotCosmetic(FName Slot, FPrimaryAssetId Asset)
static bool CallSetSlot(uint64_t slotFName, const uint64_t asset[2]){
    if(!g_setSlot.thunk||!g_pm) return false;
    int offs[6]; int n=ParamOffsets(g_setSlot,offs,6); if(n<2) return false;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+offs[0])=slotFName;
    *(uint64_t*)((uint8_t*)g_pbuf+offs[1])=asset[0]; *(uint64_t*)((uint8_t*)g_pbuf+offs[1]+8)=asset[1];
    Call(g_setSlot,(void*)g_pm,g_pbuf,g_rbuf); return true;
}

// Walk a class + superclasses for the FProperty named `name`; return its Offset_Internal (0 if absent).
// ChildProperties (FField* head) is at +0x58 for any UStruct in this build (same as a UFunction's params
// that ResolveFn walks); FField.Next @ +0x18, FProperty.Offset_Internal @ +0x44, FField.Name @ +0x20.
static uintptr_t FindPropOffset(uintptr_t cls, const char* name){
    for(int d=0; d<10 && cls; d++){
        uintptr_t f=0; if(SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)) f=*(uintptr_t*)(cls+UFUNC_CHILDPROPS);
        int i=0;
        while(LooksLikePtr(f) && i<600){
            if(NameIs(f,name)){ if(SafeReadable((void*)(f+FLD_OFFSET),4)) return (uintptr_t)(uint32_t)*(int32_t*)(f+FLD_OFFSET); return 0; }
            uintptr_t nx=0; if(SafeReadable((void*)(f+FLD_NEXT),8)) nx=*(uintptr_t*)(f+FLD_NEXT); f=nx; i++;
        }
        uintptr_t sup=0; if(SafeReadable((void*)(cls+0x40),8)) sup=*(uintptr_t*)(cls+0x40); cls=sup;
    }
    return 0;
}
// Patch every LOADED hero asset's DefaultCosmeticsBundle (FPrimaryAssetId @ g_dcbOff) to the saved skin.
// This is the RENDER fix: Comp_MainMenu_PartySlotSubject.DetermineCosmeticToShow ->
// BPFL_Cosmetics.ResolveCosmeticsBundleForHero falls back to this field when the party-member cosmetic is
// empty (always), so the main-menu hunter + customization pedestal render whatever it holds. Self-verifying:
// only writes when the current value reads as a "HeroCosmeticsBundle:<Codename>Default*" PAID matching a
// saved hero (so a wrong offset/object can't corrupt memory). Heap write => no .text integrity risk. The
// render refreshes on the next navigation (DetermineCosmeticToShow re-runs). Runs on the game thread.
// Is `cls` (or a superclass) equal to `target`? (class-identity via SuperStruct @ +0x40)
static bool IsSubclassOf(uintptr_t cls, uintptr_t target){
    for(int d=0; d<12 && cls; d++){ if(cls==target) return true; if(!SafeReadable((void*)(cls+0x40),8)) return false; cls=*(uintptr_t*)(cls+0x40); }
    return false;
}
static void PatchHeroDefaultBundles(){
    if(g_gdcbN==0) return;
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    // Pass 1: find the LokiHeroAsset CLASS object (a UClass whose own name is "LokiHeroAsset") + the field offset.
    static uintptr_t s_heroCls=0;
    if(!s_heroCls){
        int heroClassCandidates=0;
        for(int ci=0;ci<numChunks && !s_heroCls;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
            for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
                if(NameIs(obj,"LokiHeroAsset")){ uintptr_t off=FindPropOffset(obj,"DefaultCosmeticsBundle"); heroClassCandidates++; if(off){ s_heroCls=obj; g_dcbOff=off; break; } } } }
        Markerf("[render] LokiHeroAsset class %s (candidates=%d) dcbOff=0x%llX\r\n", s_heroCls?"FOUND":"NOT FOUND", heroClassCandidates, (unsigned long long)g_dcbOff);
        if(!s_heroCls || !g_dcbOff) return;
    }
    // Pass 2: DATA scan — find hero assets by a "HeroCosmeticsBundle:<Codename>Default*" PAID at offset
    // g_dcbOff, regardless of class (the real per-hero assets aren't direct LokiHeroAsset instances; they
    // may be BP subclass instances/CDOs). The type-FName check + codename prefix make false positives
    // near-impossible, and we only ever write a valid saved-bundle PAID.
    int matched=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            // CHEAP filter first: the field at g_dcbOff must be a "HeroCosmeticsBundle" PAID (skips the vast
            // majority of objects without a GetFNameStr on their class name).
            uintptr_t fld=obj+g_dcbOff; if(!SafeReadable((void*)fld,16)) continue;
            uint32_t typeId=*(uint32_t*)fld, nameId=*(uint32_t*)(fld+8);
            if(!typeId||!nameId) continue;
            char tn[96]; if(!GetFNameStr(typeId,tn,sizeof(tn)) || strcmp(tn,"HeroCosmeticsBundle")!=0) continue;
            char vn[96]; if(!GetFNameStr(nameId,vn,sizeof(vn))) continue;
            // Then restrict to hero-asset objects (class name contains "HeroAsset") so an unrelated object
            // that merely holds a HeroCosmeticsBundle PAID at this offset (e.g. "OverlaySlot") is never touched.
            uintptr_t cls=ClassOf(obj); if(!cls) continue;
            char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)) || strstr(cn,"HeroAsset")==nullptr) continue;
            // Match by the hero-asset's STABLE object name ("Default__BP_HeroAsset_<Codename>_C") containing the
            // saved hero codename — NOT the field VALUE (which changes to a skin after the first patch, so the old
            // "<Codename>Default*" value-prefix match couldn't find an already-patched CDO to UPDATE for a live
            // skin change). vn (current value) is still logged for the before->after.
            char oName[96]="?"; GetFNameStr(NameId(obj),oName,96);
            for(int i=0;i<g_gdcbN;i++){ size_t cl=strlen(g_gdcbCode[i]);
                if(cl>0 && (g_gdcbBundle[i][0]&0xFFFFFFFF) && StrIContains(oName,g_gdcbCode[i])){
                    matched++;
                    // Cache this hero-asset CDO field addr for instant live repatch (dedup by obj).
                    { bool have=false; for(int c=0;c<g_cdoCacheN;c++) if(g_cdoCache[c].obj==obj){have=true;break;}
                      if(!have && g_cdoCacheN<16){ strncpy_s(g_cdoCache[g_cdoCacheN].code,64,g_gdcbCode[i],_TRUNCATE); g_cdoCache[g_cdoCacheN].obj=obj; g_cdoCache[g_cdoCacheN].off=g_dcbOff; g_cdoCacheN++; } }
                    if(*(uint64_t*)fld!=g_gdcbBundle[i][0] || *(uint64_t*)(fld+8)!=g_gdcbBundle[i][1]){
                        DWORD op=0; if(VirtualProtect((void*)fld,16,PAGE_READWRITE,&op)){ *(uint64_t*)fld=g_gdcbBundle[i][0]; *(uint64_t*)(fld+8)=g_gdcbBundle[i][1]; DWORD d=0; VirtualProtect((void*)fld,16,op,&d);
                            g_dcbPatched++; char nb[96]="?"; GetFNameStr((uint32_t)(g_gdcbBundle[i][1]&0xFFFFFFFF),nb,96); Markerf("[render] patched '%s' DefaultCosmeticsBundle: %s -> %s\r\n",oName,vn,nb); }
                    }
                    break;
                }
            }
        } }
    Markerf("[render] data-scan matched %d hero-asset field(s)\r\n",matched);
}
// Instantly repatch the cached CDO for one hero (single 16B write, no rescan). Validates the field is still
// a HeroCosmeticsBundle PAID before writing (guards against an unloaded/reused CDO). Any thread.
static bool FastRepatchCDO(const char* code, const uint64_t paid[2]){
    for(int c=0;c<g_cdoCacheN;c++){ if(_stricmp(g_cdoCache[c].code,code)!=0) continue;
        uintptr_t obj=g_cdoCache[c].obj; if(!SafeReadable((void*)obj,0x30)) return false;
        // STRICT stale-pointer guard: the cached object must STILL be this hero's CDO (its object name
        // "Default__BP_HeroAsset_<Codename>_C" contains the codename). Prevents ever writing into a
        // reused/unloaded object that coincidentally has a HeroCosmeticsBundle field at this offset.
        char on[96]; if(!GetFNameStr(NameId(obj),on,sizeof(on)) || !StrIContains(on,code)) return false;
        uintptr_t fld=obj+g_cdoCache[c].off; if(!SafeReadable((void*)fld,16)) return false;
        uint32_t t=*(uint32_t*)fld; char tn[96]; if(!t||!GetFNameStr(t,tn,sizeof(tn))||strcmp(tn,"HeroCosmeticsBundle")!=0) return false;
        DWORD op=0; if(!VirtualProtect((void*)fld,16,PAGE_READWRITE,&op)) return false;
        *(uint64_t*)fld=paid[0]; *(uint64_t*)(fld+8)=paid[1]; DWORD d=0; VirtualProtect((void*)fld,16,op,&d); return true;
    }
    return false;
}

// LEVER #A (2026-07-09 part 6): patch the EXACT hero-asset object the RENDER reads, not just the CDO.
// The render fallback is BPFL_Cosmetics."Resolve Cosmetics Bundle For Hero" ->
// GetHeroAssetFromPrimaryAssetId(member.HeroAssetID).DefaultCosmeticsBundle. The CDO scan
// (PatchHeroDefaultBundles) patches Default__BP_HeroAsset_<Hero>_C, but part 5 suspected the render
// reads a DIFFERENT object. GetHeroAssetFromPrimaryAssetId is NATIVE (confirmed: ANSI name in the exe
// .rdata, sibling of PrimaryAssetIDFromString on the LokiAssetManager family), so we CALL it via the
// primitive to get the precise object pointer the render dereferences, LOG what it is + its current
// DefaultCosmeticsBundle, then patch THAT object's field. Diagnostic + fix in one. Game thread only.
static uintptr_t CallGetHeroAsset(const uint64_t hero[2]){
    if(!g_getHeroAsset.thunk) return 0;
    int offs[6]; int n=ParamOffsets(g_getHeroAsset,offs,6); if(n<1) return 0;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+offs[0])=hero[0]; *(uint64_t*)((uint8_t*)g_pbuf+offs[0]+8)=hero[1];
    void* ctx = g_lam ? (void*)g_lam : nullptr;
    Call(g_getHeroAsset, ctx, g_pbuf, g_rbuf);
    return (uintptr_t)g_rbuf[0];   // ObjectProperty ReturnValue lands in the result buffer
}
static int g_renderAPatched=0;
static void PatchRenderHeroAssets(){
    for(int i=0;i<g_nBundles;i++){
        uint64_t hero[2], bun[2];
        if(!PAIDFromString(g_bundles[i].k,hero)) continue;
        if(!PAIDFromString(g_bundles[i].v,bun))  continue;
        uintptr_t obj=CallGetHeroAsset(hero);
        if(!obj || !LooksLikePtr(obj) || !SafeReadable((void*)obj,0x30)){ Markerf("[renderA] GetHeroAsset(%ls) -> NULL/bad 0x%llX\r\n",g_bundles[i].k,(unsigned long long)obj); continue; }
        char on[96]="?",cn[128]="?"; GetFNameStr(NameId(obj),on,96); uintptr_t cls=ClassOf(obj); if(cls)GetFNameStr(NameId(cls),cn,128);
        // Compute the field offset from THIS object's class chain (self-contained; no global scan / g_dcbOff dep).
        uintptr_t off = cls ? FindPropOffset(cls,"DefaultCosmeticsBundle") : 0;
        if(!off){ Markerf("[renderA] GetHeroAsset(%ls) -> obj=0x%llX '%s' class '%s' but no DefaultCosmeticsBundle prop\r\n",g_bundles[i].k,(unsigned long long)obj,on,cn); continue; }
        uintptr_t fld=obj+off; char cur[96]="?"; uint32_t ctype=0;
        if(SafeReadable((void*)fld,16)){ ctype=*(uint32_t*)fld; uint32_t nm=*(uint32_t*)(fld+8); if(nm)GetFNameStr(nm,cur,96); }
        Markerf("[renderA] GetHeroAsset(%ls) -> obj=0x%llX '%s' class '%s' dcb@0x%llX cur='%s'%s\r\n",
                g_bundles[i].k,(unsigned long long)obj,on,cn,(unsigned long long)off,cur,(off==0x68?"":" (OFF DIFFERS FROM 0x68!)"));
        // Safety: only overwrite when the field currently reads as a HeroCosmeticsBundle PAID (or is empty),
        // so a wrong object/offset can't corrupt unrelated memory.
        char tn[96]="?"; if(ctype)GetFNameStr(ctype,tn,96);
        if(ctype && strcmp(tn,"HeroCosmeticsBundle")!=0){ Markerf("[renderA]   SKIP write (field type '%s' != HeroCosmeticsBundle)\r\n",tn); continue; }
        DWORD op=0; if(VirtualProtect((void*)fld,16,PAGE_READWRITE,&op)){ *(uint64_t*)fld=bun[0]; *(uint64_t*)(fld+8)=bun[1]; DWORD d=0; VirtualProtect((void*)fld,16,op,&d);
            g_renderAPatched++; char nb[96]="?"; GetFNameStr((uint32_t)(bun[1]&0xFFFFFFFF),nb,96); Markerf("[renderA]   patched -> %s\r\n",nb); }
    }
    Markerf("[renderA] render-object patch: %d field(s) set (obj from GetHeroAssetFromPrimaryAssetId)\r\n",g_renderAPatched);
}

// ---- GAP 1: main-menu center re-render via Comp_MainMenu_PartySlotSubject.Refresh() (BP fn) ----
// pi8's proven Option-B primitive: invoke a parameterless BP UFunction on the game thread by building an
// FFrame from the captured template (Node=UFunc, Object=this, Code=UFunc.Script.Data@+0x68, Locals=buf)
// and calling the ORIGINAL ProcessInternal via the trampoline (bypasses ProcessEvent's re-entrancy guard).
static void InvokeBP(void* obj, void* ufunc){
    if(!obj||!ufunc||!g_tramp) return;
    memset(g_bplocals,0,sizeof(g_bplocals)); uint64_t res[4]={0};
    uint8_t frame[0x180]; memcpy(frame, g_template, sizeof(frame));
    *(void**)(frame+FF_NODE)=ufunc;                                    // Node
    *(void**)(frame+FF_OBJECT)=obj;                                    // Object (this)
    *(uint64_t*)(frame+FF_CODE)=*(uint64_t*)((uint8_t*)ufunc+UFUNC_SCRIPT);  // Code = Script.Data (BP bytecode)
    *(void**)(frame+FF_LOCALS)=(void*)g_bplocals;                      // Locals
    *(uint64_t*)(frame+FF_MRP)=0; *(uint64_t*)(frame+FF_MRPA)=0;
    ((PFN_PE)g_tramp)(obj, frame, res);
}
// Same as InvokeBP but with a CALLER-PROVIDED Locals buffer (for BP fns that take input params — the params
// occupy the first bytes of Locals at their FProperty Offset_Internal). `locals` must be sized for ALL the
// function's locals (params + temporaries) since the BP VM writes temporaries into it during execution.
static void InvokeBPLocals(void* obj, void* ufunc, void* locals){
    if(!obj||!ufunc||!g_tramp) return;
    uint64_t res[4]={0};
    uint8_t frame[0x180]; memcpy(frame, g_template, sizeof(frame));
    *(void**)(frame+FF_NODE)=ufunc; *(void**)(frame+FF_OBJECT)=obj;
    *(uint64_t*)(frame+FF_CODE)=*(uint64_t*)((uint8_t*)ufunc+UFUNC_SCRIPT);
    *(void**)(frame+FF_LOCALS)=locals;
    *(uint64_t*)(frame+FF_MRP)=0; *(uint64_t*)(frame+FF_MRPA)=0;
    ((PFN_PE)g_tramp)(obj, frame, res);
}
// Two-pass scan (like pi8): find the Comp_MainMenu_PartySlotSubject_C class, its live instances, and the
// Refresh UFunction (name "Refresh", Outer==class). Called from the Worker (off game thread — reads only).
static void ResolveSubjects(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    if(!g_subjClass){ for(int ci=0;ci<numChunks && !g_subjClass;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,"Comp_MainMenu_PartySlotSubject_C")){ uintptr_t cls=ClassOf(obj); char cn[96]; if(cls&&GetFNameStr(NameId(cls),cn,sizeof(cn))&&strstr(cn,"Class")){ g_subjClass=obj; break; } } } } }
    if(!g_subjClass)return; g_nsubj=0; g_refreshFn=nullptr;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassOf(obj)==g_subjClass && g_nsubj<8 && NameIs(obj,"Comp_MainMenu_PartySubject")) g_subjects[g_nsubj++]=(void*)obj;
            else if(!g_refreshFn && NameIs(obj,"Refresh") && OuterOf(obj)==g_subjClass) g_refreshFn=(void*)obj; } }
}
// Fire Refresh on every live party-slot subject (game thread). Re-runs DetermineCosmeticToShow so the
// main-menu center hunter re-reads the patched fallback cosmetic -> SetHero -> renders the saved skin.
static void RefreshSubjects(){
    if(!g_refreshFn) return; int fired=0;
    for(int i=0;i<g_nsubj;i++){ uintptr_t su=(uintptr_t)g_subjects[i]; if(su && SafeReadable((void*)su,0x30) && ClassOf(su)==g_subjClass){ InvokeBP((void*)su,g_refreshFn); fired++; } }
    if(fired) Markerf("[renderR] Refresh fired on %d subject(s) (call #%ld) -> main-menu center re-render\r\n",fired,(long)g_refreshCalls);
}
// Our cached subject[0] is no longer a live subject-class object => the menu rebuilt the party slot on nav
// (e.g. returning from customization) and we must re-Resolve to find the fresh subjects.
static bool SubjStale(){ if(g_nsubj==0)return true; uintptr_t s0=(uintptr_t)g_subjects[0]; return !SafeReadable((void*)s0,0x30)||ClassOf(s0)!=g_subjClass; }
// Same staleness check for the cached customization screens — lets us SKIP the (slow, 2-4s) full object-array
// re-scan while the user stays in customization clicking skins (the screens don't change), so a refresh is fast.
static bool CustStale(){ if(g_nCust==0||!g_custClass)return true; uintptr_t s0=(uintptr_t)g_custScreens[0]; return !SafeReadable((void*)s0,0x30)||ClassOf(s0)!=g_custClass; }

static void ResolveFn(uintptr_t cls,const char* fname,Fn* F);   // fwd
// Resolve the live WBP_UI_Loadout_CustomizationScreen_C instance(s) + PreviewCurrentSkin fn. These exist only
// while the CUSTOMIZATION screen is open, so re-resolve each time (cheap-ish). Off the game thread (reads).
static void ResolveCustomization(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    if(!g_custClass){ for(int ci=0;ci<numChunks && !g_custClass;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,"WBP_UI_Loadout_CustomizationScreen_C")){ uintptr_t cls=ClassOf(obj); char cn[96]; if(cls&&GetFNameStr(NameId(cls),cn,sizeof(cn))&&strstr(cn,"Class")){ g_custClass=obj; break; } } } } }
    if(!g_custClass) return; g_nCust=0;
    // Resolve the functions by walking the class's own function list (reliable; the object-array name-scan
    // missed PreviewAsset). ResolveFn sets F.fn = the UFunction + F.child = its ChildProperties (params).
    Fn skinF{}, assetF{}; ResolveFn(g_custClass,"PreviewCurrentSkin",&skinF); ResolveFn(g_custClass,"PreviewAsset",&assetF);
    g_previewSkinFn=skinF.fn; g_previewAssetFn=assetF.fn;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(ClassOf(obj)==g_custClass && g_nCust<8){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) g_custScreens[g_nCust++]=(void*)obj; } } }
    if(g_nCust>0) g_custResolvedTick=GetTickCount();   // freshly (re)found = a NAV just happened -> the game's own nav-refresh will fire, so RefreshCustomization skips its PreviewAsset briefly (avoids the double-refresh)
    // One-time: dump the parameter shapes so the call can be built precisely (always log a summary line).
    if(!g_custParamsDumped){ g_custParamsDumped=1;
        Markerf("[param] resolved skinFn=%p assetFn=%p childSkin=0x%llX childAsset=0x%llX\r\n",g_previewSkinFn,g_previewAssetFn,(unsigned long long)skinF.child,(unsigned long long)assetF.child);
        uintptr_t children[2]={assetF.child,skinF.child}; const char* lbl[2]={"PreviewAsset","PreviewCurrentSkin"};
        for(int k=0;k<2;k++){ uintptr_t f=children[k];
            int pi=0; while(LooksLikePtr(f)&&pi<16){ char pn[96]="?"; GetFNameStr(NameId(f),pn,96);
                int32_t off=SafeReadable((void*)(f+FLD_OFFSET),4)?*(int32_t*)(f+FLD_OFFSET):-1; uint64_t flags=SafeReadable((void*)(f+FLD_FLAGS),8)?*(uint64_t*)(f+FLD_FLAGS):0;
                char tc[96]="?"; uintptr_t fcls=0; if(SafeReadable((void*)(f+0x8),8)) fcls=*(uintptr_t*)(f+0x8); if(fcls&&SafeReadable((void*)fcls,4)){ GetFNameStr(*(uint32_t*)fcls,tc,96); }
                Markerf("[param] %s: '%s' off=0x%X flags=0x%llX type=%s\r\n",lbl[k],pn,off,(unsigned long long)flags,tc);
                uintptr_t nx=0; if(SafeReadable((void*)(f+FLD_NEXT),8))nx=*(uintptr_t*)(f+FLD_NEXT); f=nx; pi++; } }
    }
}
// Re-preview the current hero's skin on the CUSTOMIZATION/OVERVIEW pedestal by calling
// PreviewAsset(FPrimaryAssetId Asset @0x0, bool 2D @0x10) — the per-slot preview the hover uses, passing the
// skin bundle EXPLICITLY (PreviewCurrentSkin read GetCurrentHeroAssets.CurrentCosmeticAsset, which is empty).
// Game thread only (InvokeBPLocals + PAIDFromString). No-op if the customization screen isn't open.
static void RefreshCustomization(){
    if(g_nCust==0 || !g_previewAssetFn || !g_selectedHero[0]) return;
    char sh[160]; WideCharToMultiByte(CP_UTF8,0,g_selectedHero,-1,sh,160,nullptr,nullptr); const char* code=strchr(sh,':'); code=code?code+1:sh;
    int idx=-1; for(int i=0;i<g_gdcbN;i++){ if(_stricmp(g_gdcbCode[i],code)==0){ idx=i; break; } }
    if(idx<0) return;
    // Convert the CURRENT desired skin string fresh (game thread) so it tracks the latest pick even if the
    // GDCB re-convert chain hasn't run; fall back to the cached PAID.
    uint64_t skinPAID[2]={0,0};
    if(g_gdcbWantV[idx][0] && PAIDFromString(g_gdcbWantV[idx],skinPAID) && (skinPAID[0]&0xFFFFFFFF)){}
    else { skinPAID[0]=g_gdcbBundle[idx][0]; skinPAID[1]=g_gdcbBundle[idx][1]; }
    if(!(skinPAID[0]&0xFFFFFFFF)) return;
    // Keep the Func-swap (checkmark) cache + the render CDO in sync INSTANTLY so the main-menu center Refresh
    // (which runs right after, reading the CDO) shows the new skin without waiting for the slow GDCB rescan.
    g_gdcbBundle[idx][0]=skinPAID[0]; g_gdcbBundle[idx][1]=skinPAID[1]; wcscpy_s(g_gdcbHaveV[idx],96,g_gdcbWantV[idx]);
    FastRepatchCDO(code, skinPAID);
    int fired=0;
    for(int i=0;i<g_nCust;i++){ uintptr_t s=(uintptr_t)g_custScreens[i]; if(!(s && SafeReadable((void*)s,0x30) && ClassOf(s)==g_custClass)) continue;
        uint8_t locals[0x100]; memset(locals,0,sizeof(locals));
        *(uint64_t*)(locals+0x0)=skinPAID[0]; *(uint64_t*)(locals+0x8)=skinPAID[1]; locals[0x10]=0;   // Asset=skin PAID, 2D=false
        InvokeBPLocals((void*)s,g_previewAssetFn,locals); fired++;
    }
    if(fired){ char nb[96]="?"; GetFNameStr((uint32_t)(skinPAID[1]&0xFFFFFFFF),nb,96); Markerf("[custR] PreviewAsset(%s) fired on %d customization screen(s)\r\n",nb,fired); }
}

// DIAGNOSTIC: log each distinct "*Subject*/*Preview*/*Pedestal*"-class actor (once) + whether its class has a
// Refresh fn, so the CUSTOMIZATION/OVERVIEW preview actor (separate from the main-menu subject) can be
// identified while the user navigates. Deduped by class -> new classes are logged as they load.
static void ResolveFn(uintptr_t cls,const char* fname,Fn* F);   // fwd (defined in the Resolve section)
static uintptr_t g_dumpSeen[256]; static int g_dumpSeenN=0;
static void DumpSubjectClasses(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls) continue;
            char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn))) continue;
            if(!(strstr(cn,"Subject")||strstr(cn,"Preview")||strstr(cn,"Pedestal")||strstr(cn,"Loadout")||strstr(cn,"Style")||strstr(cn,"Customiz")||strstr(cn,"Pod")||strstr(cn,"Diorama"))) continue;
            if(strstr(cn,"Niagara")||strstr(cn,"UVLayout")||strstr(cn,"PolyEdit")||strstr(cn,"MeshOp")||strstr(cn,"Groom")||strstr(cn,"MovieGraph")) continue;   // editor noise
            bool dup=false; for(int i=0;i<g_dumpSeenN;i++) if(g_dumpSeen[i]==cls){dup=true;break;} if(dup) continue;
            if(g_dumpSeenN<256) g_dumpSeen[g_dumpSeenN++]=cls;
            // Walk the class's own functions, collect ones whose name hints at a re-render (refresh/update/
            // sethero/preview/cosmetic) — the customization pedestal's update method to call on a skin change.
            char fns[360]=""; int fc=0;
            uintptr_t f=0; if(SafeReadable((void*)(cls+USTRUCT_CHILDREN),8)) f=*(uintptr_t*)(cls+USTRUCT_CHILDREN);
            for(int gi=0; LooksLikePtr(f)&&gi<400; gi++){ char fn[96]; if(GetFNameStr(NameId(f),fn,sizeof(fn))){ if((strstr(fn,"efresh")||strstr(fn,"pdate")||strstr(fn,"etHero")||strstr(fn,"review")||strstr(fn,"osmetic")||strstr(fn,"ebuild")) && fc<7){ strncat(fns,fn,70); strncat(fns," ",2); fc++; } } uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8))nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx; }
            char on[96]="?"; GetFNameStr(NameId(obj),on,96);
            Markerf("[subj] '%s' fns=[%s]\r\n",cn,fns);
        } }
}

// Re-pick the current hero with its saved skin via the native TryPickMyHeroAndCosmetics. This is the
// RE-RENDER TRIGGER: it sets the party member's cosmetic (firing OnCosmeticUpdated) so the main-menu
// hunter + customization pedestal re-render to the saved skin — the CDO DefaultCosmeticsBundle patch
// then holds it after the ~1s /party poll wipes the member. Uses the current hero (selectedHero from
// /revival/loadout) so it never switches the hero. Game thread only (fires BP delegates). Returns true
// if it fired.
static bool TryPickSavedSkin(){
    if(!g_tryPick.thunk || !g_party || !g_selectedHero[0]) return false;
    uint64_t heroPA[2]; if(!PAIDFromString(g_selectedHero,heroPA)) return false;
    // find the saved skin for the selected hero (match codename after "Hero:").
    char sh[160]; WideCharToMultiByte(CP_UTF8,0,g_selectedHero,-1,sh,160,nullptr,nullptr);
    const char* code=strchr(sh,':'); code=code?code+1:sh;
    for(int i=0;i<g_gdcbN;i++){
        if((g_gdcbBundle[i][0]&0xFFFFFFFF) && _stricmp(code,g_gdcbCode[i])==0){
            CallSet2PAID(g_tryPick,(void*)g_party,heroPA,g_gdcbBundle[i]);
            char nb[96]="?"; GetFNameStr((uint32_t)(g_gdcbBundle[i][1]&0xFFFFFFFF),nb,96);
            Markerf("[render] TryPick(%s, %s) -> re-render trigger fired\r\n",code,nb);
            return true;
        }
    }
    return false;
}

// Apply every saved equip. Runs on the game thread (from the PI hook).
static void ApplyLoadout(){
    uint64_t firstHero[2]={0,0}, firstBun[2]={0,0}; bool haveFirst=false;
    for(int i=0;i<g_nBundles;i++){ uint64_t hero[2],bun[2];
        if(PAIDFromString(g_bundles[i].k,hero) && PAIDFromString(g_bundles[i].v,bun)){
            if(CallSet2PAID(g_setBundle,(void*)g_pm,hero,bun)){ g_applied++; char h[96]="?",b[96]="?"; GetFNameStr((uint32_t)(hero[1]&0xFFFFFFFF),h,96); GetFNameStr((uint32_t)(bun[1]&0xFFFFFFFF),b,96); Markerf("[apply] bundle %s -> %s\r\n",h,b); }
            // Record the per-hero redirect for the GetDefaultCosmeticsBundleIdForHeroId Func-swap:
            // the hero CODENAME (strip "Hero:") + the saved bundle's full 16-byte PAID. The default
            // bundle the game returns for a hero is "<Codename>Default*", so the thunk matches by
            // codename prefix.
            if(g_gdcbN<LMAX){ char kb[160]; WideCharToMultiByte(CP_UTF8,0,g_bundles[i].k,-1,kb,160,nullptr,nullptr);
                const char* code=strchr(kb,':'); code=code?code+1:kb; strncpy_s(g_gdcbCode[g_gdcbN],128,code,_TRUNCATE);
                g_gdcbBundle[g_gdcbN][0]=bun[0]; g_gdcbBundle[g_gdcbN][1]=bun[1];
                wcsncpy_s(g_gdcbWantV[g_gdcbN],96,g_bundles[i].v,_TRUNCATE); wcsncpy_s(g_gdcbHaveV[g_gdcbN],96,g_bundles[i].v,_TRUNCATE);
                g_gdcbN++; }
            if(!haveFirst){ firstHero[0]=hero[0];firstHero[1]=hero[1]; firstBun[0]=bun[0];firstBun[1]=bun[1]; haveFirst=true; } } }
    for(int i=0;i<g_nSlots;i++){ uint64_t slot=FNameFromString(g_slots[i].k); uint64_t asset[2];
        if(slot && PAIDFromString(g_slots[i].v,asset)){
            if(CallSetSlot(slot,asset)){ g_applied++; char a[96]="?"; GetFNameStr((uint32_t)(asset[1]&0xFFFFFFFF),a,96); Markerf("[apply] slot %ls -> %s\r\n",g_slots[i].k,a); } } }
    for(int i=0;i<g_nChromas;i++){ uint64_t luxe[2],chr[2];
        if(PAIDFromString(g_chromas[i].k,luxe) && PAIDFromString(g_chromas[i].v,chr)){
            if(CallSet2PAID(g_setChroma,(void*)g_pm,luxe,chr)){ g_applied++; Markerf("[apply] chroma %ls -> %ls\r\n",g_chromas[i].k,g_chromas[i].v); } } }
    // NOTE (2026-07-09 CORRECTION): the SKIN display is NOT fixed anywhere yet. The backend attempt
    // (ags buildSoloParty serving the member CosmeticsAssetID) is CONCLUSIVELY INERT and was REVERTED:
    // the client rebuilds PartyModel.GetSelf() from the /party poll each ~1s and reads only HeroAssetID,
    // never CosmeticsAssetID, so Loki.log shows the party slot loading GetDefaultCosmeticsBundleIdForHeroId
    // (= AlchemistDefault_STR / "Strawberry Bomb") no matter what we echo. The customization SKIN tab +
    // the party-slot preview BOTH read that same default fallback (WBP_UI_Loadout_StyleScreen "Get Current
    // Party Assets" -> else-branch), which is exactly why the SKIN tab always reverts to the default.
    // The remaining client-side path is to redirect GetDefaultCosmeticsBundleIdForHeroId(hero) to the saved
    // skin per hero (a single native fn both the SKIN tab and the party slot fall back to). We keep only
    // SetHeroCosmeticsBundlePreference above (harmless preference) + the slot cosmetics (which the slot tabs
    // read from SlotCosmeticsEntries). firstHero/firstBun retained for diagnostics; TryPick intentionally
    // NOT called (it force-switched the selected hero and was clobbered by the poll).
    (void)haveFirst; (void)firstHero; (void)firstBun;
    // PROBE (skin diagnosis): after setting the preference, read it back with the game's own getter.
    // GetHeroCosmeticsBundlePreference(const FPrimaryAssetId& Hero, FPrimaryAssetId& OutPreference).
    // If OutPreference == the bundle we set -> the setter DID populate the local map (display reads
    // elsewhere / key form). If empty/None -> the setter is server-only (need a local equip path).
    if(g_getBundle.thunk && g_nBundles>0){
        uint64_t hero[2];
        if(PAIDFromString(g_bundles[0].k,hero)){
            int offs[6]; int n=ParamOffsets(g_getBundle,offs,6);
            if(n>=2){
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                *(uint64_t*)((uint8_t*)g_pbuf+offs[0])=hero[0]; *(uint64_t*)((uint8_t*)g_pbuf+offs[0]+8)=hero[1];
                Call(g_getBundle,(void*)g_pm,g_pbuf,g_rbuf);
                uint32_t outName=*(uint32_t*)((uint8_t*)g_pbuf+offs[1]+8);   // OutPreference.name
                uint32_t retName=(uint32_t)(g_rbuf[1]&0xFFFFFFFF);           // in case it returns by value
                char o[96]="<none>",rr[96]="<none>"; if(outName)GetFNameStr(outName,o,96); if(retName)GetFNameStr(retName,rr,96);
                Markerf("[probe] GetHeroCosmeticsBundlePreference(%ls) out='%s' ret='%s' (nparams=%d off0=%d off1=%d)\r\n",g_bundles[0].k,o,rr,n,offs[0],offs[1]);
            }
        }
    }
    // LEVER #A: patch the EXACT object the render dereferences (from the native resolver). Game thread.
    if(g_getHeroAsset.thunk) PatchRenderHeroAssets();
    else Marker("[renderA] GetHeroAssetFromPrimaryAssetId UFunction NOT resolved -> render-object patch skipped\r\n");
}

// PI-hook state machine (game thread). Fire 1: capture the FFrame + ApplyLoadout (compute PAIDs), then
// signal the Worker to run the off-thread CDO patch. Later fires: once the CDO patch is done, call
// TryPick to fire the re-render (member now valid -> main-menu/pedestal show the saved skin; the patched
// CDO holds it after the ~1s poll wipe). Ordering the CDO patch BEFORE TryPick avoids the poll-wipe race.
static DWORD g_lastRefreshTick=0;
extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));
    if(!g_applyDone){ ApplyLoadout(); g_applyDone=1; }
    else if(g_cdoDone){
        // GAP 1: after the fallback CDO is patched, re-render the main-menu center by firing
        // Comp_MainMenu_PartySlotSubject.Refresh() a few times over ~1s (tick-gated so we don't
        // spam every PI call). Refresh re-runs DetermineCosmeticToShow -> reads the patched cosmetic
        // -> SetHero -> the 3D model swaps to the saved skin. (TryPick was ineffective + risked setting
        // the member cosmetic to a default, so it's replaced by the proven pi8 Refresh mechanism.)
        DWORD now=GetTickCount();
        if(now-g_lastRefreshTick>=60){ g_lastRefreshTick=now;
            // Only refresh a surface that is LIVE + SETTLED — never fire BP calls into a surface that is
            // mid-rebuild during navigation (that's what raced the hunter-pick / stalled). RefreshCustomization
            // (CDO repatch + PreviewAsset) only when a customization screen is open + only ONCE; RefreshSubjects
            // (main-menu) only when the main-menu subjects are live.
            if(g_refreshCalls==0 && g_nCust>0) RefreshCustomization();
            if(!SubjStale()) RefreshSubjects();
            InterlockedIncrement(&g_refreshCalls);
        }
        if(g_refreshCalls>=2){ g_trypicked=1; g_done=1; }
    }
    g_inHook=0;
}

// ---- hook plumbing (identical to probe18) ----
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

// ---- GetDefaultCosmeticsBundleIdForHeroId replacement thunk (Func-swap target) ----
// Exec-thunk signature. Runs on the game thread during a party-slot / SKIN-tab refresh. Calls the
// ORIGINAL exec thunk first (which reads the hero param and writes the game's DEFAULT bundle to the
// FFrame Result), then post-processes: the default bundle is named "<Codename>Default*", so read its
// name FName, prefix-match a saved hero codename, and overwrite Result with the saved bundle PAID.
// No FFrame param parsing and no VM re-entry — pure data massage of the already-written Result.
extern "C" void MyGdcbThunk(void* Context, void* Frame, void* Result){
    g_origExecThunk(Context, Frame, Result);   // Result <- default bundle FPrimaryAssetId (16B)
    // Lazy table refresh (changeability): the background poller sets g_gdcbDirty when the saved skin
    // for a hero changed in /revival/loadout. Re-convert those entries HERE — we're on the game thread
    // (this is a Func-swap target invoked by the VM), so PAIDFromString is valid. Guarded so we convert
    // only on an actual change and never re-enter the conversion.
    if(g_gdcbDirty && !InterlockedCompareExchange(&g_gdcbConverting,1,0)){
        for(int i=0;i<g_gdcbN;i++){
            if(wcscmp(g_gdcbWantV[i],g_gdcbHaveV[i])!=0){
                wchar_t want[96]; wcsncpy_s(want,96,g_gdcbWantV[i],_TRUNCATE);   // snapshot (poller may rewrite)
                uint64_t pa[2];
                if(PAIDFromString(want,pa)){ g_gdcbBundle[i][0]=pa[0]; g_gdcbBundle[i][1]=pa[1]; wcscpy_s(g_gdcbHaveV[i],96,want); }
            }
        }
        g_gdcbRepatch=1;   // request the bg thread to re-apply the render fix for the changed skin (off game thread)
        g_gdcbDirty=0; g_gdcbConverting=0;
    }
    if(g_gdcbN>0 && Result && SafeReadable(Result,16)){
        uint32_t bundleName=*(uint32_t*)((uint8_t*)Result+8);   // default bundle's PrimaryAssetName FName
        char bn[160];
        if(bundleName && GetFNameStr(bundleName,bn,sizeof(bn))){
            for(int i=0;i<g_gdcbN;i++){
                size_t cl=strlen(g_gdcbCode[i]);
                // "<Codename>Default..." — match codename then require the next char to start "Default"
                // (disambiguates codenames that prefix each other, e.g. Fire vs Firefox).
                // require a converted (non-empty) saved PAID so a not-yet-converted new entry never
                // writes an empty bundle (type FName in [0] is non-zero for a valid PAID).
                if(cl>0 && (g_gdcbBundle[i][0]&0xFFFFFFFF) && _strnicmp(bn,g_gdcbCode[i],cl)==0 && (bn[cl]=='D'||bn[cl]=='d')){
                    ((uint64_t*)Result)[0]=g_gdcbBundle[i][0];
                    ((uint64_t*)Result)[1]=g_gdcbBundle[i][1];
                    InterlockedIncrement(&g_gdcbHits);
                    break;
                }
            }
        }
    }
}
// Redirect via a UFunction.Func POINTER SWAP (heap write, no .text patch). Finds the UFunction whose
// Func @+0xE0 == the known exec thunk (base+kGdcbThunkRva), saves it as the original, and atomically
// overwrites Func with &MyGdcbThunk. An 8-byte aligned pointer write is atomic on x64, so the VM
// never sees a torn value and no thread-suspend is needed. Left installed (poll-proof fallback).
static bool InstallGdcbFuncSwap(){
    if(g_gdcbInstalled || g_gdcbN==0 || !g_gdcbFunc) return false;
    uintptr_t fp=g_gdcbFunc+UFUNC_FUNC;                       // &UFunction.Func
    if(!SafeReadable((void*)fp,8)) { Marker("[gdcb] FAIL Func unreadable\r\n"); return false; }
    uintptr_t cur=*(uintptr_t*)fp;
    uintptr_t want=g_modBase+kGdcbThunkRva;
    if(cur!=want){ Markerf("[gdcb] FAIL Func mismatch cur=0x%llX want=0x%llX\r\n",(unsigned long long)cur,(unsigned long long)want); return false; }
    g_origExecThunk=(PFN_THUNK)cur;
    DWORD op=0; if(!VirtualProtect((void*)fp,8,PAGE_READWRITE,&op)) { Marker("[gdcb] FAIL VirtualProtect\r\n"); return false; }
    *(volatile uintptr_t*)fp=(uintptr_t)&MyGdcbThunk;         // atomic aligned 8-byte write
    DWORD d=0; VirtualProtect((void*)fp,8,op,&d);
    g_gdcbInstalled=1; return true;
}
// Shared ProcessInternal-hook lock — serialize install/use/uninstall (and the one-time g_stolen capture)
// with the other PI-hookers (mainmenu_refresh_pi8 / missions_fix) so the thread-suspending SafeWrite never
// races. Same name they use; no-op if we're the only PI-hooker. pi8 HOLDS this lock while its hook is
// installed, so when we acquire it pi8's hook is uninstalled => the live prologue is the ORIGINAL.
static HANDLE g_hookMutex=nullptr;
static void HookLock(){ if(g_hookMutex) WaitForSingleObject(g_hookMutex,30000); }
static void HookUnlock(){ if(g_hookMutex) ReleaseMutex(g_hookMutex); }
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}
static void ResolveFn(uintptr_t cls,const char* fname,Fn* F){
    uintptr_t f=0; if(SafeReadable((void*)(cls+USTRUCT_CHILDREN),8)) f=*(uintptr_t*)(cls+USTRUCT_CHILDREN); int i=0;
    while(LooksLikePtr(f)&&i<800){ if(NameIs(f,fname)){ F->fn=(void*)f; if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))F->thunk=th;} if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))F->child=cp;} return; } uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8))nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx; i++; }
}
// Resolve a UFunction by walking the class AND its superclasses (setters may live on a base manager).
static void ResolveFnChain(uintptr_t cls,const char* fname,Fn* F){
    for(int d=0; d<8 && cls && !F->thunk; d++){ ResolveFn(cls,fname,F); if(F->thunk) return; uintptr_t sup=0; if(SafeReadable((void*)(cls+0x40),8)) sup=*(uintptr_t*)(cls+0x40); cls=sup; }
}
static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t lam=0,pm=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!lam && ClassNameIs(obj,"LokiAssetManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) lam=obj; }
            if(!pm && ClassNameIs(obj,"PersonalizationManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) pm=obj; }
            // PartyManager instance (native): owns TryPickMyHeroAndCosmetics, which sets the party
            // member's hero+cosmetic — the source the customization/preview cosmetic display reads
            // (sessions 48/50). Class name is "*PartyManager"; require TryPick to resolve to confirm.
            if(!g_party && ClassNameHas(obj,"PartyManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0){ Fn t{}; ResolveFnChain(ClassOf(obj),"TryPickMyHeroAndCosmetics",&t); if(t.thunk){ g_party=obj; g_tryPick=t; } } }
            // PartyMemberModel (GetSelf) — the render's PRIMARY cosmetic source (member.CosmeticsAssetID).
            if(!g_member && ClassNameIs(obj,"PartyMemberModel")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0){ g_member=obj; g_memberClass=ClassOf(obj); } }
            // The GetDefaultCosmeticsBundleIdForHeroId UFunction: the unique object whose Func @+0xE0
            // equals the known exec thunk (base+kGdcbThunkRva). Matching by Func ptr avoids a name walk.
            if(!g_gdcbFunc && SafeReadable((void*)(obj+UFUNC_FUNC),8) && *(uintptr_t*)(obj+UFUNC_FUNC)==g_modBase+kGdcbThunkRva && NameIs(obj,"GetDefaultCosmeticsBundleIdForHeroId")) g_gdcbFunc=obj;
            // GetHeroAssetFromPrimaryAssetId UFunction (native; the render fallback resolver). Prefer the
            // object whose Func @+0xE0 points into the module .text (the native exec thunk, not a BP stub).
            if(!g_getHeroAsset.thunk && SafeReadable((void*)(obj+UFUNC_FUNC),8) && NameIs(obj,"GetHeroAssetFromPrimaryAssetId")){
                uintptr_t th=*(uintptr_t*)(obj+UFUNC_FUNC);
                if(th>=g_modBase && th<g_modBase+0xC000000){ g_getHeroAsset.fn=(void*)obj; g_getHeroAsset.thunk=th; if(SafeReadable((void*)(obj+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(obj+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))g_getHeroAsset.child=cp;} }
            } } }
    if(!lam||!pm)return; g_lam=lam; g_pm=pm;
    uintptr_t lamCls=ClassOf(lam), pmCls=ClassOf(pm);
    if(lamCls){ ResolveFnChain(lamCls,"PrimaryAssetIDFromString",&g_pafs); if(!g_getHeroAsset.thunk) ResolveFnChain(lamCls,"GetHeroAssetFromPrimaryAssetId",&g_getHeroAsset); }
    if(pmCls){ ResolveFnChain(pmCls,"SetHeroCosmeticsBundlePreference",&g_setBundle); ResolveFnChain(pmCls,"SetSlotCosmetic",&g_setSlot); ResolveFnChain(pmCls,"SetLuxeSkinChromaPreference",&g_setChroma); ResolveFnChain(pmCls,"GetHeroCosmeticsBundlePreference",&g_getBundle); }
    // Resolve member.CosmeticsAssetID offset from reflection (usmap-independent). Dump the member class
    // property layout ONCE so the exact field name/offset is verifiable in the marker.
    if(g_memberClass && !g_memberCosmeticOff){
        const char* cands[]={"CosmeticsAssetID","CosmeticsAssetId","CosmeticsBundleId","CosmeticsBundleID","CosmeticId"};
        for(int i=0;i<5;i++){ uintptr_t o=FindPropOffset(g_memberClass,cands[i]); if(o){ g_memberCosmeticOff=o; break; } }
        if(!g_memberDumped){ g_memberDumped=1;
            Markerf("[member] class=0x%llX cosmeticOff=0x%llX heroOff=0x%llX — props:\r\n",(unsigned long long)g_memberClass,(unsigned long long)g_memberCosmeticOff,(unsigned long long)MEMBER_HEROID);
            uintptr_t cls=g_memberClass; for(int d=0; d<6 && cls; d++){ uintptr_t f=0; if(SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)) f=*(uintptr_t*)(cls+UFUNC_CHILDPROPS); int i=0;
                while(LooksLikePtr(f) && i<200){ char pn[96]="?"; GetFNameStr(NameId(f),pn,96); int32_t off=SafeReadable((void*)(f+FLD_OFFSET),4)?*(int32_t*)(f+FLD_OFFSET):-1; Markerf("[member]   +0x%X %s\r\n",off,pn);
                    uintptr_t nx=0; if(SafeReadable((void*)(f+FLD_NEXT),8)) nx=*(uintptr_t*)(f+FLD_NEXT); f=nx; i++; }
                uintptr_t sup=0; if(SafeReadable((void*)(cls+0x40),8)) sup=*(uintptr_t*)(cls+0x40); cls=sup; }
        }
    }
}

// ---- /revival/loadout fetch + parse (off the game thread) ----
static void Utf8ToW(const char* s,int len,wchar_t* out,int cap){ int n=MultiByteToWideChar(CP_UTF8,0,s,len,out,cap-1); if(n<0)n=0; out[n]=0; }
// Parse the string-map under "objName" into pairs[]; returns count.
static int ParseMap(const char* json,const char* objName,Pair* pairs,int cap){
    char pat[64]; _snprintf_s(pat,sizeof(pat),_TRUNCATE,"\"%s\"",objName);
    const char* p=strstr(json,pat); if(!p) return 0; p=strchr(p,'{'); if(!p) return 0; p++;
    int n=0;
    while(*p && n<cap){
        while(*p && *p!='"' && *p!='}') p++;
        if(*p=='}'||!*p) break;
        p++; const char* ks=p; while(*p && *p!='"') p++; if(!*p) break; int kl=(int)(p-ks); p++;
        while(*p && *p!=':') p++; if(!*p) break; p++; while(*p==' '||*p=='\t') p++;
        if(*p!='"') { while(*p && *p!=',' && *p!='}') p++; if(*p==',') { p++; } continue; }
        p++; const char* vs=p; while(*p && *p!='"') p++; if(!*p) break; int vl=(int)(p-vs); p++;
        Utf8ToW(ks,kl,pairs[n].k,96); Utf8ToW(vs,vl,pairs[n].v,96); n++;
        while(*p && *p!=',' && *p!='}') p++;
        if(*p==',') p++; else break;
    }
    return n;
}
// HTTP GET /revival/loadout into buf (cap). Returns bytes read (0 on failure).
static int HttpGetLoadout(char* buf, int cap){
    HINTERNET hi=InternetOpenA("supervive-loadout-shim",INTERNET_OPEN_TYPE_DIRECT,nullptr,nullptr,0); if(!hi) return 0;
    int total=0;
    HINTERNET hu=InternetOpenUrlA(hi,kLoadoutUrl,nullptr,0,INTERNET_FLAG_RELOAD|INTERNET_FLAG_NO_CACHE_WRITE|INTERNET_FLAG_PRAGMA_NOCACHE,0);
    if(hu){ DWORD got=0; while(total<cap-1 && InternetReadFile(hu,buf+total,(DWORD)(cap-1-total),&got) && got){ total+=got; } InternetCloseHandle(hu); }
    InternetCloseHandle(hi); buf[total<cap?total:cap-1]=0; return total;
}
// Extract a top-level JSON string value ("key":"value") into out (wide). Returns true if found.
static bool ParseStr(const char* json,const char* key,wchar_t* out,int cap){
    char pat[64]; _snprintf_s(pat,sizeof(pat),_TRUNCATE,"\"%s\"",key);
    const char* p=strstr(json,pat); if(!p) return false; p+=strlen(pat);
    while(*p && *p!=':') p++; if(!*p) return false; p++; while(*p==' '||*p=='\t') p++;
    if(*p!='"') return false; p++; const char* vs=p; while(*p && *p!='"') p++; if(!*p) return false;
    Utf8ToW(vs,(int)(p-vs),out,cap); return true;
}
static void FetchLoadout(){
    static char buf[65536];
    if(HttpGetLoadout(buf,sizeof(buf))>0){ g_nBundles=ParseMap(buf,"heroCosmeticsBundles",g_bundles,LMAX); g_nSlots=ParseMap(buf,"slotCosmetics",g_slots,LMAX); g_nChromas=ParseMap(buf,"luxeChromas",g_chromas,LMAX); if(!ParseStr(buf,"selectedHero",g_selectedHero,96)) g_selectedHero[0]=0; g_fetchOk=1; }
}

// Re-poll /revival/loadout and update the GDCB redirect's desired-string table (g_gdcbWantV). When a
// hero's saved skin changed (or a new hero was customized), set g_gdcbDirty so MyGdcbThunk re-converts
// on the game thread. This is what makes SKIN picks CHANGEABLE (not locked to the install-time skin):
// a click's member PUT records the new skin into /revival/loadout in ms, we pick it up within a poll,
// and the redirect flips before the ~1s party-poll wipes the member and falls back to us.
static void RefreshGdcb(){
    if(!g_gdcbInstalled) return;
    static char buf[65536]; if(HttpGetLoadout(buf,sizeof(buf))<=0) return;
    Pair pairs[LMAX]; int n=ParseMap(buf,"heroCosmeticsBundles",pairs,LMAX);
    bool changed=false;
    for(int i=0;i<n;i++){
        char kb[160]; WideCharToMultiByte(CP_UTF8,0,pairs[i].k,-1,kb,160,nullptr,nullptr);
        const char* code=strchr(kb,':'); code=code?code+1:kb;
        int slot=-1; for(int j=0;j<g_gdcbN;j++){ if(_stricmp(g_gdcbCode[j],code)==0){ slot=j; break; } }
        if(slot<0 && g_gdcbN<LMAX){ slot=g_gdcbN++; strncpy_s(g_gdcbCode[slot],128,code,_TRUNCATE); g_gdcbHaveV[slot][0]=0; g_gdcbBundle[slot][0]=g_gdcbBundle[slot][1]=0; }
        if(slot>=0 && wcscmp(g_gdcbWantV[slot],pairs[i].v)!=0){ wcsncpy_s(g_gdcbWantV[slot],96,pairs[i].v,_TRUNCATE); changed=true; }
    }
    if(changed){ g_gdcbDirty=1; g_centerDirty=1; g_dirtyTick=GetTickCount(); }   // g_gdcbDirty -> MyGdcbThunk re-convert (CDO); g_centerDirty -> ReArmRefresh (OVERVIEW PreviewAsset converts fresh, not gated on the GDCB call)
}
// Live changeability of the MAIN-MENU CENTER on an in-place skin change: re-arm the one-shot PI hook so
// OnPI fires RefreshSubjects again (re-runs DetermineCosmeticToShow -> reads the freshly re-patched CDO ->
// SetHero). Only fires when the main-menu subjects are live (i.e. the user is back on the main menu — the
// customization nav rebuilds the slot). Under the shared PI-hook mutex so it never clobbers pi8. Retries
// via g_centerDirty until the subjects are live. (pi8 already covers hero-switch + leaving-HUNTERS.)
static void ReArmRefresh(){
    DWORD t0=GetTickCount();
    // Re-scan a surface ONLY when its cache is stale (i.e. on navigation) — NOT on every skin click. This
    // was the 2-4s cost. Also skip the main-menu subject scan while in customization (subjects don't exist
    // there, so SubjStale would force a fruitless full scan every time).
    if(CustStale()) ResolveCustomization();
    if(g_nCust==0 && SubjStale()) ResolveSubjects();
    DWORD tResolve=GetTickCount();
    bool mmLive   = g_refreshFn && g_nsubj>0 && !SubjStale();
    bool custLive = g_previewSkinFn && g_nCust>0;
    if(!mmLive && !custLive) return;   // neither surface live yet -> keep g_centerDirty set, retry next tick
    g_refreshCalls=0; g_lastRefreshTick=0; g_done=0;        // g_applyDone/g_cdoDone stay 1 -> OnPI goes straight to Refresh
    HookLock();
    DWORD tLock=GetTickCount();
    bool ok=InstallHook();
    DWORD tInstall=GetTickCount();
    if(ok){ DWORD t=GetTickCount(); while(!g_done && GetTickCount()-t<1500) Sleep(10); UninstallHook(); }
    DWORD tDone=GetTickCount();
    HookUnlock();
    Markerf("[8b] latency=%lums [resolve=%lu lockwait=%lu install=%lu refreshwait=%lu] mm=%d cust=%d calls=%ld\r\n",
            (unsigned long)(g_dirtyTick?tDone-g_dirtyTick:0),(unsigned long)(tResolve-t0),(unsigned long)(tLock-tResolve),(unsigned long)(tInstall-tLock),(unsigned long)(tDone-tInstall),mmLive,custLive,(long)g_refreshCalls);
    g_centerDirty=0;
}
// LEVER #B (cache-and-restore): the render reads member.CosmeticsAssetID FIRST (before the CDO fallback).
// A HeroCosmeticsBundle PAID encodes BOTH hero + skin, so it MUST match the member's current hero or the
// render shows the wrong hunter (the Brall-shows-RocketJumper bug). So we:
//   * observe the member cosmetic; if it's a valid bundle whose name matches the current hero, CACHE those
//     exact 16 bytes (the client's live pick) — no conversion, no lag;
//   * if it's a bundle that does NOT match the current hero (stale cross-hero), CLEAR it (empty -> the game
//     renders that hero's default) so a previewed hunter never wears another's skin;
//   * if it's empty (the ~1s poll wiped it), RESTORE this hero's cached pick so the render follows the
//     selection instead of reverting.
// Seeded from /revival/loadout on load (SeedMemberCache) so the saved skin shows on load. Any-thread 16B
// write (pi8 writes the adjacent HeroAssetID from its worker — established safe). 100ms to beat the poll.
static DWORD WINAPI MemberWriterThread(LPVOID){
    for(;;){ Sleep(100);
        if(!g_member || !g_memberCosmeticOff) continue;
        if(!SafeReadable((void*)g_member,0x30)) continue;
        uintptr_t hf=g_member+MEMBER_HEROID; if(!SafeReadable((void*)hf,16)) continue;
        uint32_t hname=*(uint32_t*)(hf+8); if(!hname) continue;
        char hcode[96]; if(!GetFNameStr(hname,hcode,sizeof(hcode))) continue;
        size_t hl=strlen(hcode); if(hl==0) continue;
        uintptr_t cf=g_member+g_memberCosmeticOff; if(!SafeReadable((void*)cf,16)) continue;
        uint32_t ctype=*(uint32_t*)cf, cname=*(uint32_t*)(cf+8); char tn[96]="", bn[96]="";
        bool valid = ctype && GetFNameStr(ctype,tn,sizeof(tn)) && strcmp(tn,"HeroCosmeticsBundle")==0 && cname && GetFNameStr(cname,bn,sizeof(bn));
        if(valid){
            bool heroMatch = _strnicmp(bn,hcode,hl)==0;   // bundle "RocketJumperKnockOut" starts with hero "RocketJumper"
            if(heroMatch){ int i=McFind(hcode); if(i<0 && g_mcN<LMAX){ i=g_mcN++; strncpy_s(g_mc[i].code,64,hcode,_TRUNCATE); } if(i>=0){ g_mc[i].paid[0]=*(uint64_t*)cf; g_mc[i].paid[1]=*(uint64_t*)(cf+8); } }
            else { *(uint64_t*)cf=0; *(uint64_t*)(cf+8)=0; InterlockedIncrement(&g_memberClears); }   // stale cross-hero -> clear
        } else {
            int i=McFind(hcode);
            if(i>=0 && (g_mc[i].paid[0]&0xFFFFFFFF)){ *(uint64_t*)cf=g_mc[i].paid[0]; *(uint64_t*)(cf+8)=g_mc[i].paid[1]; InterlockedIncrement(&g_memberWrites); }
            // else: no cached pick for this hero -> leave empty -> the game renders the hero's default.
        }
    }
    return 0;
}
// Seed the per-hero cache from the saved bundles converted during ApplyLoadout (g_gdcbCode + g_gdcbBundle),
// so the saved skin shows on load before the user picks anything.
static void SeedMemberCache(){
    for(int i=0;i<g_gdcbN && g_mcN<LMAX;i++){ if(!(g_gdcbBundle[i][0]&0xFFFFFFFF)) continue; if(McFind(g_gdcbCode[i])>=0) continue;
        int j=g_mcN++; strncpy_s(g_mc[j].code,64,g_gdcbCode[i],_TRUNCATE); g_mc[j].paid[0]=g_gdcbBundle[i][0]; g_mc[j].paid[1]=g_gdcbBundle[i][1]; }
    Markerf("[9b] member cache seeded with %d hero(es) from saved loadout.\r\n",g_mcN);
}
static DWORD WINAPI RefreshThread(LPVOID){ int tick=0; for(;;){ Sleep(300); RefreshGdcb();
    // CDO repatch is now INSTANT via FastRepatchCDO (in RefreshCustomization, game thread) — the old per-change
    // full ~500k rescan here was the 2-4s bottleneck, so it's removed (the initial load scan populated the cache).
    if(InterlockedCompareExchange(&g_gdcbRepatch,0,1)==1) g_centerDirty=1;
    // DEBOUNCE (settle ~250ms) + COOLDOWN (>=1200ms since the last re-arm). Re-arming the ProcessInternal
    // hook (thread-suspending install/uninstall) too often crashes the game, so we throttle it: rapid clicking
    // just makes the render catch up to the FINAL pick at most once/1.2s instead of churning the hook per click.
    static DWORD s_lastRearm=0;
    if(g_centerDirty && (GetTickCount()-(DWORD)g_dirtyTick)>=250 && (GetTickCount()-s_lastRearm)>=1200){ s_lastRearm=GetTickCount(); ReArmRefresh(); }
    (void)tick;
} return 0; }

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] loadout_fix (replay saved equips via native setters) started\r\n");
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_hookMutex=CreateMutexA(nullptr,FALSE,"Local\\SuperviveMissionsPIHook");   // shared with pi8/missions_fix
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    DWORD dl=GetTickCount()+120000; DWORD coreAt=0;
    while(GetTickCount()<dl){ Resolve();
        bool core = g_lam&&g_pm&&g_pafs.thunk&&g_setBundle.thunk;
        if(core && !coreAt) coreAt=GetTickCount();
        if(core && (g_tryPick.thunk || (coreAt && GetTickCount()-coreAt>8000))) break;   // grace for PartyManager/TryPick
        Sleep(500);
    }
    if(!g_lam||!g_pm||!g_pafs.thunk||!g_setBundle.thunk){Markerf("[2] FAIL resolve lam=%llX pm=%llX pafs=%llX setBundle=%llX setSlot=%llX setChroma=%llX\r\n",(unsigned long long)g_lam,(unsigned long long)g_pm,(unsigned long long)g_pafs.thunk,(unsigned long long)g_setBundle.thunk,(unsigned long long)g_setSlot.thunk,(unsigned long long)g_setChroma.thunk);return 3;}
    Markerf("[2] lam=%llX pm=%llX pafs=%llX setBundle=%llX setSlot=%llX setChroma=%llX party=0x%llX tryPick=%llX getHeroAsset=%llX gameTid=%lu\r\n",(unsigned long long)g_lam,(unsigned long long)g_pm,(unsigned long long)g_pafs.thunk,(unsigned long long)g_setBundle.thunk,(unsigned long long)g_setSlot.thunk,(unsigned long long)g_setChroma.thunk,(unsigned long long)g_party,(unsigned long long)g_tryPick.thunk,(unsigned long long)g_getHeroAsset.thunk,g_gameTid);
    g_pi=(uint8_t*)(g_modBase+kPiRva);
    // Capture the ORIGINAL prologue + build the trampoline under the shared lock (pi8 holds it while its
    // hook is installed, so under the lock the prologue is guaranteed original — not pi8's JMP).
    HookLock();
    bool okProlog = SafeReadable(g_pi,5) && memcmp(g_pi,kPiProlog,5)==0;
    if(okProlog){ memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); }
    HookUnlock();
    if(!okProlog){Marker("[2] FAIL PI prologue (another PI-hooker installed?)\r\n");return 4;}
    if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    // Resolve the main-menu party-slot subjects + Refresh UFunction (GAP 1 re-render). Retry briefly —
    // the subjects are created at menu load, which may be after core resolve. Off the game thread (reads only).
    for(int r=0; r<20 && !((g_nsubj>0 && g_refreshFn) && (g_member && g_memberCosmeticOff)); r++){ ResolveSubjects(); Resolve(); if((g_nsubj>0 && g_refreshFn) && (g_member && g_memberCosmeticOff)) break; Sleep(250); }
    Markerf("[2b] subjects=%d refreshFn=%p subjClass=0x%llX member=0x%llX cosmeticOff=0x%llX\r\n",g_nsubj,g_refreshFn,(unsigned long long)g_subjClass,(unsigned long long)g_member,(unsigned long long)g_memberCosmeticOff);
    FetchLoadout();
    Markerf("[3] fetched loadout: ok=%d bundles=%d slots=%d chromas=%d (%s)\r\n",g_fetchOk,g_nBundles,g_nSlots,g_nChromas,kLoadoutUrl);
    for(int i=0;i<g_nBundles;i++) Markerf("[3]   bundle: %ls -> %ls\r\n",g_bundles[i].k,g_bundles[i].v);
    for(int i=0;i<g_nSlots;i++)   Markerf("[3]   slot:   %ls -> %ls\r\n",g_slots[i].k,g_slots[i].v);
    if(g_nBundles==0 && g_nSlots==0 && g_nChromas==0){ Marker("[3] nothing saved to apply; exiting.\r\n"); return 0; }
    // Give the login loadout-refresh time to land FIRST so our setters win (else the empty refresh overwrites us).
    Sleep(4000);
    // One-shot under the shared lock (pi8 can't install/uninstall while we hold it). The PI hook is a
    // small state machine: OnPI fire 1 does ApplyLoadout (game thread), then we run the CDO patch HERE
    // (Worker thread, off the game thread) and signal g_cdoDone, then a later OnPI fire does TryPick (the
    // re-render trigger) — ordered so the CDO fallback is patched before the poll wipe can revert it.
    HookLock();
    if(!InstallHook()){HookUnlock();Marker("[3] FAIL InstallHook\r\n");return 6;}
    DWORD t0=GetTickCount(); while(!g_applyDone && GetTickCount()-t0<40000) Sleep(20);
    if(g_applyDone){
        PatchHeroDefaultBundles();   // off-thread CDO patch (render fallback) BEFORE the Refresh re-render
        Markerf("[7] render patch: %d hero DefaultCosmeticsBundle field(s) set.\r\n",g_dcbPatched);
        g_cdoDone=1;                 // lets subsequent OnPI fires run RefreshSubjects (main-menu re-render)
        t0=GetTickCount(); while(!g_done && GetTickCount()-t0<15000) Sleep(20);
    }
    UninstallHook();
    HookUnlock();
    if(g_done) Markerf("[4] *** applied %d equip(s) + %ld main-menu Refresh call(s) fired. Skins render on the hunter. ***\r\n",g_applied,(long)g_refreshCalls);
    else       Markerf("[4] partial (applyDone=%ld cdoDone=%ld refreshCalls=%ld hitsGT=%ld).\r\n",(long)g_applyDone,(long)g_cdoDone,(long)g_refreshCalls,(long)g_hitsGT);
    // ---- Persistent SKIN fix: swap the GetDefaultCosmeticsBundleIdForHeroId UFunction.Func ----
    // Populated in ApplyLoadout (game thread). This is a HEAP pointer write (no .text patch), so it
    // dodges the ~3-5min .text integrity check that crashed the earlier inline detour. Left installed:
    // it's the poll-proof fallback the SKIN tab + party slot read, so every future refresh renders the
    // saved skin. No thread-suspend needed (8-byte aligned atomic write) but take the lock for tidiness.
    if(g_gdcbN>0){
        HookLock();
        bool gi=InstallGdcbFuncSwap();
        HookUnlock();
        if(gi){ Markerf("[5] *** GDCB skin-redirect INSTALLED (Func-swap, heap) for %d hero(es): UFunc=0x%llX thunk 0x%llX->MyThunk. ***\r\n",g_gdcbN,(unsigned long long)g_gdcbFunc,(unsigned long long)(uintptr_t)g_origExecThunk);
                for(int i=0;i<g_gdcbN;i++) Markerf("[5]   redirect: %s -> nameFName=0x%llX\r\n",g_gdcbCode[i],(unsigned long long)g_gdcbBundle[i][1]);
                // Start the ~1s poller so SKIN picks are CHANGEABLE (not locked to the install-time skin).
                HANDLE rt=CreateThread(nullptr,0,RefreshThread,nullptr,0,nullptr); if(rt){ CloseHandle(rt); Marker("[6] redirect refresh poller started (1s) — SKIN picks now changeable.\r\n"); }
                // LEVER #B (cache-and-restore): keep member.CosmeticsAssetID = this hero's cached pick so the
                // render follows picks (no CDO fight) and never shows a cross-hero bundle.
                // *** DISABLED BY DEFAULT (2026-07-10 part 9) *** — deployed with the aggressive 100ms member
                // writer/clear, the user saw hunters show LOCKED + skin picks not committing. Root cause is the
                // client-side CanUse/ownership catalog activation being flaky this session (backend serves all
                // 977+25 owned; catalog_pick_fix hit an ntdll injection race on rapid relaunch), NOT proven to be
                // this writer — but until it can be isolated on a STABLE launch, default OFF so the shim is the
                // proven render-only build (Refresh + CDO + Func-swap = saved skin renders on all surfaces,
                // multi-hunter, persist, hunters NOT locked). Set MEMBER_WRITER_ENABLED=1 to re-test lever #B.
                #define MEMBER_WRITER_ENABLED 0
                Markerf("[9] member cosmetic write: g_member=0x%llX cosmeticOff=0x%llX %s\r\n",(unsigned long long)g_member,(unsigned long long)g_memberCosmeticOff,(MEMBER_WRITER_ENABLED && g_member&&g_memberCosmeticOff)?"-> writer ON":"-> DISABLED (default off; see part 9)");
                if(MEMBER_WRITER_ENABLED && g_member && g_memberCosmeticOff){ SeedMemberCache(); HANDLE mw=CreateThread(nullptr,0,MemberWriterThread,nullptr,0,nullptr); if(mw) CloseHandle(mw); } }
        else    Markerf("[5] GDCB skin-redirect FAILED (gdcbN=%d func=0x%llX).\r\n",g_gdcbN,(unsigned long long)g_gdcbFunc);
    } else {
        Marker("[5] no saved hero skins -> GDCB redirect skipped.\r\n");
    }
    // Keep the DLL resident so MyGdcbThunk (the swapped Func target) stays valid (do NOT return-unload).
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
