// tutorial_launch — SESSION 60 (force-launch route). The menu's native TryStartSoloMode bails
// (region gates only the FIND MATCH path; tutorial uses solo-start which no-ops against our stub).
// The tutorial map is LOCAL, so we bypass the menu entirely: call
//   UKismetSystemLibrary::ExecuteConsoleCommand(WorldContext, "open LVL_Tutorial", nullptr)
// via the proven S55/S56 game-thread native-call primitive (hook ProcessInternal, capture a live
// FFrame, call the UFunction thunk directly). "open <map>" routes through UEngine::HandleOpenCommand
// -> Browse -> a local client travel to the tutorial map (the exact thing TryStartSoloMode should do).
//
// Primitive recipe (probe9): myframe = captured template; Node=UFunction, Object=Context, Code=NULL,
// Locals=paramsBuf, clear +0x30/+0x38/+0x40 (MostRecentProperty*), PropertyChainForCompiledIn@+0x88 =
// Function.ChildProperties (*(UFunc+0x58)); thunk(Context,&frame,&result). Params placed at each
// param FProperty's Offset_Internal@+0x44 within paramsBuf.
// Build:  clang++ -shared -O2 tutorial_launch.cpp -o tutorial_launch.dll -lkernel32
// Inject: tools/inject/inject.exe mmap <PID> tutorial_launch.dll   Marker: docs/tutorial-launch-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\tutorial-launch-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_OUTPARMS=0x80, FF_PROPCHAIN=0x88;
constexpr uintptr_t FIELD_NEXT=0x18, FPROP_OFFSET=0x44, FPROP_FLAGS=0x38;   // FField.Next, FProperty.Offset_Internal, FProperty.FlagsPrivate
constexpr uint64_t CPF_OutParm=0x100, CPF_ReturnParm=0x400;
static const uint8_t kPiProlog[5]={0x48,0x89,0x5C,0x24,0x08};
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

// The console command to force the local tutorial travel. "open <mapname>" is the client-travel command.
//
// S61 finding (static): LVL_Tutorial's WorldSettings.DefaultGameMode is BP_LokiGameMode_Tutorial (the FULL
// machinery mode); the map has NO PlayerStart on purpose (hero drops in via Comp_GameMode_DropPlane_Tutorial).
// BP_GameMode_BasicTraining is a STOCK GameModeBase stub (zero CDO overrides -> stock GameState/PC/DefaultPawn),
// which is why ?game=BasicTraining loads but shows a spectator at origin + "IsBattleRoyaleBP failed to find game
// state". So the only route to a PLAYABLE tutorial is BP_LokiGameMode_Tutorial, gated by native
// ALokiGameMode::Login (packer-blocked from static disasm; not overridden in BP).
//
// To make the next live session's Login-satisfy sweep fast, the command is now read from an external file at
// inject time (edit the file + reinject, no rebuild). If the file is absent/empty, we fall back to the
// KNOWN-GOOD BasicTraining render (loads + shows the island, never crashes) so a bare inject is always safe.
//   File: docs/tutorial-launch-cmd.txt  (first non-comment line; '#'/'//' and blank lines ignored; UTF-8/ASCII)
static const char* kCmdFilePath = "G:\\git\\Supervive Revival Project\\docs\\tutorial-launch-cmd.txt";
// S62: default is now the FULL tutorial mode so the custom-Login trampoline (match-mode vtable slot 285)
// actually fires — BasicTraining is a stock GameModeBase and never dispatches through the match vtables.
// (The external cmd-file read has been flaky; the compiled default removes that dependency for this test.)
static const wchar_t* kDefaultCommand =
    L"open LVL_Tutorial?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.BP_LokiGameMode_Tutorial_C";  // S64: ?listen tested + ruled out (failed to Listen, reverted identically) — reverted to plain full mode
static wchar_t g_cmd[1024];   // resolved at startup by LoadCommand(); points OnPI's Command FString.

// ---- S61 native Login-approve (transient, self-restoring vtable DE-OVERRIDE) ----
// The tutorial force-open crashes in native ALokiGameMode::Login. Slot 176 (the ONLY GameMode override in the
// first 190 vtable slots) turned out NOT to be the Login dispatch (patching it, verified held, had zero effect).
// A 300-slot vtdump diff shows ALokiGameMode overrides SEVERAL virtuals: slots 176,236,259,283,285,288,294. Any
// could be Login. DECISIVE TEST: de-override ALL of them to their stock AGameModeBase values at once — if the
// "ALokiGameMode::Login failed to Login" crash disappears, Login is one of these (then bisect); if it persists,
// the reject is not a GameMode virtual (likely AGameSession::ApproveLogin). .rdata patch trips the ~3-5min
// integrity check if PERSISTENT (a live 10-vtable patch hard-crashed at menu in ~30s), so do it TRANSIENTLY:
// patch right before force-open, hold through the travel login (~a few s), restore. RVAs stable for this build
// (base 0x7FF6B54F0000); verify with usmapdump if the game updates.
constexpr uintptr_t kStockGmbVtRva = 0x806EDD8;   // stock AGameModeBase CDO vtable (source of de-override values)
static const uintptr_t kMatchVtRvas[] = {         // match-mode CDO vtables (instances share the native parent's)
    0x8A94C48,  // ALokiTutorialGameMode
    0x8A52A98,  // ALokiRoundGameMode
    0x8951FA0,  // ALokiGameMode
    0x88B7CB0,  // ALokiBattleRoyaleGameMode
    0x8936948,  // ALokiDropInGameMode
};
static const int kOverrideSlots[] = {285};  // BISECT: testing which override slot is Login (candidates 236,283,285,288,294)
static uintptr_t g_savedVt[5][7];                 // [match vtable][slot] originals for restore
// PatchLoginVtables(bool) is defined below, after g_modBase / Marker / SafeReadable are declared.
static void PatchLoginVtables(bool toStock);

static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uintptr_t g_worldCtx=0;                 // WorldContextObject (a live ProgressionManager)
static uintptr_t g_kslCDO=0;                    // Default__KismetSystemLibrary (call context)
static void* g_ecc=nullptr; static uintptr_t g_eccThunk=0, g_eccChild=0;   // ExecuteConsoleCommand
static uint32_t g_offWCO=0xFFFFFFFF, g_offCmd=0xFFFFFFFF, g_offSP=0xFFFFFFFF;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0,g_called=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};
static uint64_t g_pbuf[16]={0}, g_rbuf[4]={0};
static uint64_t g_spbuf[32]={0};   // S74 B2 exp3: larger param buffer for SpawnPlayer (96-byte FTransform OUT)

// ---- S68 spawn+possess mode (LEAD B / OPTION 2) ----
enum RunMode { RM_FORCEOPEN=0, RM_SPAWNPOSSESS=1, RM_GOTOPHASE=2, RM_SPAWNPLAYER=3, RM_CHEATSPAWN=4, RM_WAKEMOVE=5, RM_PUPPET=6, RM_TOGGLEREADY=7 };
#ifndef KRUNMODE
#define KRUNMODE RM_CHEATSPAWN
#endif
static const int kRunMode = KRUNMODE;   // override at build with -DKRUNMODE=RM_FORCEOPEN etc. RM_FORCEOPEN=force-open; RM_SPAWNPOSSESS=spawn+possess; RM_GOTOPHASE=advance round; RM_SPAWNPLAYER=real hero spawn+possess; RM_CHEATSPAWN=call the game's own LokiPlayerCheats spawn RPC (S74 Path B)
static uintptr_t g_gm2=0, g_pc2=0, g_startSpot=0, g_spawnedPawn=0, g_heroClass=0;
constexpr uint32_t GM_DEFPAWN_OFF=0x3F0;   // AGameModeBase::DefaultPawnClass
// S68 GameplayStatics deferred-spawn (bypass GetDefaultPawnClass): explicit hero-class spawn + possess.
static const bool kUseGameplayStatics = true;
static uintptr_t g_gsCDO=0;
static void* g_beginFn=nullptr; static uintptr_t g_beginThunk=0, g_beginChild=0;
static void* g_finishFn=nullptr; static uintptr_t g_finishThunk=0, g_finishChild=0;
static void* g_xfFn=nullptr; static uintptr_t g_xfThunk=0, g_xfChild=0;
static uint32_t g_oBWorld=0,g_oBClass=8,g_oBXform=0x10,g_oBColl=0x70,g_oBOwner=0x78,g_oBRet=0x88;
static uint32_t g_oFActor=0,g_oFXform=0x10,g_oFRet=0x70; static uint32_t g_oXfRet=0;
static uint8_t g_xform[0x60]={0}; static uint8_t g_gsbuf[0x100]={0};
static void* g_spawnFn=nullptr; static uintptr_t g_spawnThunk=0, g_spawnChild=0;
static void* g_possessFn=nullptr; static uintptr_t g_possessThunk=0, g_possessChild=0;
static uint32_t g_offSpawnNP=0, g_offSpawnSS=8, g_offSpawnRet=0x10, g_offInPawn=0;
// K2_SetActorLocation(NewLocation, bSweep, FHitResult& OUT, bTeleport) — SWEEP the spawned hero DOWN onto the ground
// (collision-continuous, never tunnels; snaps to the terrain surface regardless of spawn height).
static void* g_slFn=nullptr; static uintptr_t g_slThunk=0, g_slChild=0; static uint32_t g_oSlLoc=0xFFFFFFFF,g_oSlSweep=0xFFFFFFFF,g_oSlTele=0xFFFFFFFF;
static uint8_t g_slbuf[0x140]={0};
// GetPlayerViewPoint(OUT Location, OUT Rotation) — the camera's actual view point. Spawn HERE (not the arbitrary start
// spot): where the camera looks is definitionally STREAMED (rendering) so it has real landscape collision to land on.
static void* g_vpFn=nullptr; static uintptr_t g_vpThunk=0, g_vpChild=0; static uint32_t g_oVpLoc=0xFFFFFFFF,g_oVpRot=0xFFFFFFFF;
// COSMETICS: the hero's visual SkeletalMesh is attached by the cosmetics system (needs a CosmeticsAssetID + a refresh).
static void* g_ccFn=nullptr; static uintptr_t g_ccThunk=0, g_ccChild=0;   // GetCosmeticsController
static void* g_gcaFn=nullptr; static uintptr_t g_gcaThunk=0, g_gcaChild=0; // GetCosmeticsAssetID -> FPrimaryAssetId
static void* g_rcFn=nullptr; static uintptr_t g_rcThunk=0, g_rcChild=0;   // RefreshCosmetics
static void* g_drlFn=nullptr; static uintptr_t g_drlThunk=0, g_drlChild=0; // GetDefaultRecommendedLoadoutFromClass
static void* g_oncFn=nullptr; static uintptr_t g_oncThunk=0, g_oncChild=0; // OnRep_CosmeticsAssetID (drives BP_PostSetupCosmetics)
static void* g_svtFn=nullptr; static uintptr_t g_svtThunk=0, g_svtChild=0; static uint32_t g_oSvtTarget=0xFFFFFFFF; // SetViewTargetWithBlend(NewViewTarget,...) -> point the camera at the hero (off the Z=0 under-map spectator view)
// CosmeticsAssetId = FPrimaryAssetId{ FPrimaryAssetType(FName), FName Name }. FName = {ComparisonIndex, Number=0}.
// FNameEntryIds from usmapdump nameid: HeroCosmeticsBundle=0x1A572, RoninDefault=0xA12AB (the default Ronin skin bundle).
constexpr uint32_t kFN_HeroCosmeticsBundle=0x1A572, kFN_RoninDefault=0xA12AB;
static volatile long g_spStep=0;   // progress: 1=spawn called, 2=pawn got, 3=possess called
static void DoSpawnPossess();
// ---- S74 B2: GoToPhase (force the round past EGP_BeginInit) ----
static uintptr_t g_gmPhase=0; static void* g_gpFn=nullptr; static uintptr_t g_gpThunk=0, g_gpChild=0; static uint32_t g_offNextPhase=0;
// S74 B2 exp2: skip SpawnSelect(4)+SpawnReveal(5) — they null-deref on the missing deploy state — and jump
// straight to Lineup(6) then Combat(7). Change this list to sweep phase paths. (exp1 was {2,3,4,5,6,7}.)
static const int kPhaseList[]={2,3,4};   // Step0: stop at SpawnSelect(4) to capture the deploy null-deref via CrashVEH
static int g_phaseIdx=0;
static DWORD g_lastPhaseMs=0;
static void DoGoToPhase();
// ---- S74 B2 exp3: SpawnPlayer (real hero-spawn) + Possess ----
static void* g_spwFn=nullptr; static uintptr_t g_spwThunk=0, g_spwChild=0;
static uint32_t g_oSpwPS=0xFFFFFFFF,g_oSpwXf=0xFFFFFFFF,g_oSpwSS=0xFFFFFFFF,g_oSpwEnsure=0xFFFFFFFF,g_oSpwRet=0xFFFFFFFF;
static uintptr_t g_localPS=0; static uint32_t g_psHeroOff=0xFFFFFFFF;   // PlayerState.HeroClass offset — SpawnPlayer reads which hero to spawn from here
static void DoSpawnPlayer();
// ---- S74 Path B: CHEAT-OBJECT spawn — call the game's OWN LokiPlayerCheats RPC directly ----
// The shipping build keeps its whole cheat surface intact (only the console-ENABLE knobs were stripped, S3).
// LokiPlayerCheats has purpose-built spawn RPCs: ServerCheatChangeHero(Class), ServerCheatSpawnActor(Class,Vector),
// CheatChangeHero(FString). Calling a Server* function's native thunk DIRECTLY (the S55 primitive) runs its
// _Implementation body in-process — the exec thunk calls _Implementation, NOT the RPC-routing stub — so with the
// force-open tutorial's local authority it executes the real server-side hero-spawn. A game-native path that S68's
// 4 hand-rolled spawn methods never tried. Enumerated live S74: docs/session-74-cheat-enum-dump.txt.
// Like RM_SPAWNPLAYER/POSSESS this assumes the force-open tutorial is ALREADY running (the cheat obj + PC exist
// only in the live match); inject this build INTO the running tutorial.
enum CheatTarget { CT_SERVERCHANGEHERO=0, CT_CHANGEHERONAME=1, CT_AUTHCHANGECHAR=2, CT_SPAWNACTOR=3, CT_SWITCHPLAYING=4 };
#ifndef KCHEATTARGET
#define KCHEATTARGET CT_SPAWNACTOR
#endif
static const int kCheatTarget = KCHEATTARGET;            // -DKCHEATTARGET=... CT_SERVERCHANGEHERO/CT_CHANGEHERONAME need the LokiPlayerCheats obj (absent in force-open, GetLocal returns null); CT_AUTHCHANGECHAR=AuthCheatChangeCharacter(Class) on the PC (fires clean but no-ops on the round gate); CT_SPAWNACTOR=spawn the LokiPlayerCheats obj ourselves (GameplayStatics), wire it to the PC, then ServerCheatSpawnActor(HeroClass,loc) on it
#ifndef KCHEATRESOLVEONLY
#define KCHEATRESOLVEONLY true
#endif
static const bool kCheatResolveOnly = KCHEATRESOLVEONLY;  // -DKCHEATRESOLVEONLY=false to actually fire. true = resolve+log then STOP (safe at menu; no game-thread call).
static const char* kCheatHeroClassName = "BP_HERO_Ronin_C";  // hero UClass fed to ServerCheatChangeHero (matches RM_SPAWNPOSSESS)
static const wchar_t* kCheatHeroName = L"Ronin";              // hero name string fed to CheatChangeHero
static uintptr_t g_cheatObj=0, g_cheatCDO=0, g_cheatHeroClass=0, g_csWorldCtx=0;
static void* g_glcFn=nullptr; static uintptr_t g_glcThunk=0, g_glcChild=0; static uint32_t g_oGlcWCO=0xFFFFFFFF, g_oGlcRet=0xFFFFFFFF;  // GetLocalLokiPlayerCheatsBP(WorldContext)->obj
static void* g_schFn=nullptr; static uintptr_t g_schThunk=0, g_schChild=0; static uint32_t g_oSchClass=0xFFFFFFFF;   // ServerCheatChangeHero(HeroClass)
static void* g_cchFn=nullptr; static uintptr_t g_cchThunk=0, g_cchChild=0; static uint32_t g_oCchName=0xFFFFFFFF;    // CheatChangeHero(HeroName)
static void* g_accFn=nullptr; static uintptr_t g_accThunk=0, g_accChild=0; static uint32_t g_oAccClass=0xFFFFFFFF; static uintptr_t g_cheatPC=0;  // AuthCheatChangeCharacter(Class) on the live PC — no cheat obj needed
// CT_SPAWNACTOR: spawn a LokiPlayerCheats actor ourselves (reuses the g_gm2/g_startSpot/g_gsCDO/g_begin*/g_finish*/g_xf* GameplayStatics globals), wire to PC, then call ServerCheatSpawnActor on it.
static void* g_scsaFn=nullptr; static uintptr_t g_scsaThunk=0, g_scsaChild=0; static uint32_t g_oScsaClass=0xFFFFFFFF, g_oScsaLoc=0xFFFFFFFF;  // ServerCheatSpawnActor(ClassToSpawn, Location)
static uintptr_t g_cheatObjClass=0; static uint32_t g_pcCheatOff=0xFFFFFFFF;  // cheat-obj class to spawn; PC's LokiPlayerCheats member offset
static void* g_locFn=nullptr; static uintptr_t g_locThunk=0, g_locChild=0;   // K2_GetActorLocation(startSpot) -> FVector (real spawn loc; origin is the void)
// CT_SWITCHPLAYING (S74 RE): SwitchToPlayingState() transitions the PC state machine spectator->playing (state idx 0x140,
// UNGATED — vs SwitchToSpectatorState which gates on PC+0x160==3). FinishDropPhaseHiding sets PC+0xF28=1 (drop reveal).
static void* g_spsFn=nullptr; static uintptr_t g_spsThunk=0, g_spsChild=0;    // SwitchToPlayingState()
static void* g_fdphFn=nullptr; static uintptr_t g_fdphThunk=0, g_fdphChild=0; // FinishDropPhaseHiding()
static void* g_isSpecFn=nullptr; static uintptr_t g_isSpecThunk=0, g_isSpecChild=0; // IsSpectating() -> bool (authoritative spectator check: [PC+0x3F0]==spectatingState)
constexpr uint32_t PC_STATEBYTE_OFF=0x160, PC_DROPFLAG_OFF=0xF28, PC_STATEOBJ_OFF=0x3F0;
static void* g_ehcFn=nullptr; static uintptr_t g_ehcThunk=0, g_ehcChild=0; static uint32_t g_oEhcEnabled=0xFFFFFFFF;  // EnableHotkeyCheats(double Enabled) — ServerCheatSpawnActor may gate on this
static void* g_ahceFn=nullptr; static uintptr_t g_ahceThunk=0, g_ahceChild=0;  // AreHotkeyCheatsEnabled() -> bool (verify the flag took)
static void ResolveCheatSpawn(); static void DoCheatSpawn();
// ---- S75: RM_WAKEMOVE — try to WAKE the frozen movement sim on the possessed hero. Diagnosis (S75): the CMC
// never ticks (Velocity=0, gravity has no effect) round-wide, so no client flag moves it. This mode reuses the
// primitive to call SetActive(true)+SetComponentTickEnabled(true)+SetActorTickEnabled(true)+SetMovementMode(Falling)
// on PC->Pawn's CMC (plus GravityScale=1.0), then SAMPLES Velocity/MovementMode for ~3s. If the hero starts
// falling (|Vel| ramps up), the sim woke -> WASD would then work; if it stays 0, PerformMovement is deploy-gated
// and the kick doesn't reach it. Autonomously verifiable via the marker (no WASD keypress needed).
static uintptr_t g_wmPC=0, g_wmHero=0, g_wmCMC=0;
static uint32_t g_wmGravOff=0xFFFFFFFF, g_wmVelOff=0xFFFFFFFF, g_wmModeOff=0xFFFFFFFF;
static void* g_saFn=nullptr; static uintptr_t g_saThunk=0, g_saChild=0; static uint32_t g_oSaActive=0xFFFFFFFF,g_oSaReset=0xFFFFFFFF;   // SetActive(bNewActive,bReset)
static void* g_scteFn=nullptr; static uintptr_t g_scteThunk=0, g_scteChild=0; static uint32_t g_oScteEn=0xFFFFFFFF;   // SetComponentTickEnabled(bEnabled)
static void* g_smmFn=nullptr; static uintptr_t g_smmThunk=0, g_smmChild=0; static uint32_t g_oSmmMode=0xFFFFFFFF,g_oSmmCustom=0xFFFFFFFF;   // SetMovementMode(NewMovementMode,NewCustomMode)
static void* g_satFn=nullptr; static uintptr_t g_satThunk=0, g_satChild=0; static uint32_t g_oSatEn=0xFFFFFFFF;   // SetActorTickEnabled(bEnabled) on the hero
static void* g_rimFn=nullptr; static uintptr_t g_rimThunk=0, g_rimChild=0;   // ResetIgnoreMoveInput() on the PC — clears the IgnoreMoveInput counter so AddMovementInput stops no-op'ing (WASD input reaches the pawn)
static void* g_amiFn=nullptr; static uintptr_t g_amiThunk=0, g_amiChild=0; static uint32_t g_oAmiDir=0xFFFFFFFF,g_oAmiScale=0xFFFFFFFF,g_oAmiForce=0xFFFFFFFF;   // AddMovementInput(WorldDirection,ScaleValue,bForce) — FORCE-MOVE test
static int g_wmSample=0; static DWORD g_wmLastMs=0;
static uintptr_t g_wmRoot=0;   // hero root capsule (=CMC.UpdatedComponent@+0xD0); RelativeLocation@+0x158 = world pos
#ifndef KWAKEZ
#define KWAKEZ 500.0
#endif
#ifndef KWAKEX
#define KWAKEX (-999999.0)
#endif
#ifndef KWAKEY
#define KWAKEY (-999999.0)
#endif
static const double kWakeZ = KWAKEZ;   // absolute Z to teleport the hero to before waking; build -DKWAKEZ=<n> to iterate
static const double kWakeX = KWAKEX, kWakeY = KWAKEY;   // -999999 sentinel = keep the hero's current X/Y; else teleport to this XY (e.g. a spawn point)
// ---- S75 RM_PUPPET: WASD movement puppet. The stock input->acceleration path is dead in the un-deployed force-open
// (forced AddMovementInput produced ZERO accel/velocity), but poking the CMC velocity moves the hero WITH collision.
// So each game-thread hit we read WASD key state and write CMC.Velocity.XY (+0xE8) = keydir * speed. Camera-relative
// mapping is a compile-time yaw offset (calibrate with -DKPUPYAW=<deg>). Runs until the hook window expires.
#ifndef KPUPSPEED
#define KPUPSPEED 600.0
#endif
#ifndef KPUPYAW
#define KPUPYAW 0.0
#endif
static const double kPupSpeed = KPUPSPEED, kPupYawDeg = KPUPYAW;
static bool g_puppetInit=false; static HWND g_gameHwnd=nullptr;
static void DoPuppet();
static bool ResolveWakeMove(); static void DoWakeMove();

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[512];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
// De-override (toStock=true) or restore (false) all of ALokiGameMode's overridden virtuals across the match-mode
// vtables, copying the stock AGameModeBase vtable's value at each slot. Saves originals for a clean restore.
static void PatchLoginVtables(bool toStock){
    uintptr_t* gmb=(uintptr_t*)(g_modBase+kStockGmbVtRva);
    const int NV=(int)(sizeof(kMatchVtRvas)/sizeof(kMatchVtRvas[0]));
    const int NS=(int)(sizeof(kOverrideSlots)/sizeof(kOverrideSlots[0]));
    int n=0;
    for(int v=0; v<NV; v++){
        uintptr_t vt=g_modBase+kMatchVtRvas[v];
        for(int s=0; s<NS; s++){
            int slot=kOverrideSlots[s];
            uintptr_t* tgt=(uintptr_t*)(vt+(uintptr_t)slot*8);
            if(!SafeReadable(tgt,8)||!SafeReadable(gmb+slot,8)) continue;
            DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op)) continue;
            if(toStock){ g_savedVt[v][s]=*tgt; *tgt=gmb[slot]; }        // point slot at stock AGameModeBase impl
            else if(g_savedVt[v][s]){ *tgt=g_savedVt[v][s]; }           // restore the Loki override
            DWORD d=0; VirtualProtect(tgt,8,op,&d); n++;
        }
    }
    Markerf("[VT] %s %d slot-writes across %d match vtables x %d override slots (de-override to stock GameModeBase)\r\n",
            toStock?"PATCH":"restore", n, NV, NS);
}
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
static bool ClassNameIs(uintptr_t obj,const char* w){ uintptr_t c=ClassOf(obj); if(!c)return false; char b[128]; if(!GetFNameStr(NameId(c),b,sizeof(b)))return false; return strcmp(b,w)==0; }

static volatile long g_crashSeq=0;
static void CallNative(void* func, uintptr_t thunk, uintptr_t childProps, void* context, void* paramsBuf, void* resultBuf);   // fwd (defined below)
// If v is a UObject, write its CLASS name (else "-"); used to NAME the null-deref context registers.
static void ObjClassName(uint64_t v,char* out,int cap){
    out[0]='-'; out[1]=0;
    if(!LooksLikePtr(v))return;
    uintptr_t cls=ClassOf((uintptr_t)v);
    if(LooksLikePtr(cls)){ char cn[96]; if(GetFNameStr(NameId(cls),cn,sizeof(cn))){ int n=(int)strlen(cn); if(n>0&&n<cap){ memcpy(out,cn,n+1); return; } } }
    // maybe v is itself a UClass/UObject with a name
    char on[96]; if(GetFNameStr(NameId((uintptr_t)v),on,sizeof(on))){ int n=(int)strlen(on); if(n>0&&n<cap-1){ out[0]='?'; memcpy(out+1,on,n+1); } }
}
// S74 Path A Step 0: on the null-deref, dump RIP+rva, the faulting/accessed address, all GP regs, the
// class name of each pointer-register (names the object whose member is null), and the instruction bytes
// at RIP and RIP-24 (to see WHERE the null pointer was loaded from = base object + member offset).
static void DumpCrashCtx(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode;
    CONTEXT* c=ep->ContextRecord; uint64_t rip=c->Rip;
    uint64_t rva=(rip>g_modBase&&rip<g_modBase+0xC000000)?rip-g_modBase:0;
    uint64_t accType=ep->ExceptionRecord->NumberParameters>=2?ep->ExceptionRecord->ExceptionInformation[0]:0;
    uint64_t accAddr=ep->ExceptionRecord->NumberParameters>=2?ep->ExceptionRecord->ExceptionInformation[1]:0;
    Markerf("[NULL] fatal 0x%lX RIP=0x%llX rva=0x%llX access=%s addr=0x%llX inHook=%ld\r\n",
        code,(unsigned long long)rip,(unsigned long long)rva, accType==1?"WRITE":(accType==8?"EXEC":"READ"),(unsigned long long)accAddr,(long)g_inHook);
    Markerf("[NULL] RAX=%llX RBX=%llX RCX=%llX RDX=%llX RSI=%llX RDI=%llX RBP=%llX RSP=%llX\r\n",
        (unsigned long long)c->Rax,(unsigned long long)c->Rbx,(unsigned long long)c->Rcx,(unsigned long long)c->Rdx,(unsigned long long)c->Rsi,(unsigned long long)c->Rdi,(unsigned long long)c->Rbp,(unsigned long long)c->Rsp);
    Markerf("[NULL] R8=%llX R9=%llX R10=%llX R11=%llX R12=%llX R13=%llX R14=%llX R15=%llX\r\n",
        (unsigned long long)c->R8,(unsigned long long)c->R9,(unsigned long long)c->R10,(unsigned long long)c->R11,(unsigned long long)c->R12,(unsigned long long)c->R13,(unsigned long long)c->R14,(unsigned long long)c->R15);
    char ca[96],cb[96],cc[96],cd[96],csi[96],cdi[96],c8[96],c9[96];
    ObjClassName(c->Rax,ca,sizeof(ca)); ObjClassName(c->Rbx,cb,sizeof(cb)); ObjClassName(c->Rcx,cc,sizeof(cc)); ObjClassName(c->Rdx,cd,sizeof(cd));
    ObjClassName(c->Rsi,csi,sizeof(csi)); ObjClassName(c->Rdi,cdi,sizeof(cdi)); ObjClassName(c->R8,c8,sizeof(c8)); ObjClassName(c->R9,c9,sizeof(c9));
    Markerf("[NULL] cls RAX=%s RBX=%s RCX=%s RDX=%s RSI=%s RDI=%s R8=%s R9=%s\r\n",ca,cb,cc,cd,csi,cdi,c8,c9);
    if(SafeReadable((void*)rip,24)){ uint8_t* p=(uint8_t*)rip; char hx[80]; int o=0; for(int i=0;i<24&&o<74;i++)o+=_snprintf_s(hx+o,sizeof(hx)-o,_TRUNCATE,"%02X ",p[i]); Markerf("[NULL] code@RIP:    %s\r\n",hx); }
    if(SafeReadable((void*)(rip-24),24)){ uint8_t* p=(uint8_t*)(rip-24); char hx[80]; int o=0; for(int i=0;i<24&&o<74;i++)o+=_snprintf_s(hx+o,sizeof(hx)-o,_TRUNCATE,"%02X ",p[i]); Markerf("[NULL] code@RIP-24: %s\r\n",hx); }
}
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>4)return EXCEPTION_CONTINUE_SEARCH;
    Markerf("[NULL] (via VEH)\r\n"); DumpCrashCtx(ep);
    return EXCEPTION_CONTINUE_SEARCH;
}
// SEH filter: reliably catches the AV at the exact CallNative site (VEH ordering is unreliable under the packer).
// EXCEPTION_EXECUTE_HANDLER = handle it (game thread corrupt after, but we have the null data).
static int SehDump(EXCEPTION_POINTERS* ep){ long s=InterlockedIncrement(&g_crashSeq); if(s<=4){ Markerf("[NULL] (via SEH)\r\n"); DumpCrashCtx(ep); } return EXCEPTION_EXECUTE_HANDLER; }
// Call a native UFunction under SEH so an AV inside it is captured (not just crashed). Returns true if it faulted.
static bool CallNativeGuarded(void* func, uintptr_t thunk, uintptr_t childProps, void* context, void* paramsBuf, void* resultBuf){
    __try { CallNative(func,thunk,childProps,context,paramsBuf,resultBuf); return false; }
    __except(SehDump(GetExceptionInformation())){ return true; }
}

// S58 OUT/ref-param marshalling (ported from missions_fix.cpp): for each param flagged CPF_OutParm (and not the
// return value), build an FOutParmRec{Property@+0, PropAddr@+8, NextOutParm@+0x10} whose PropAddr points into the
// Locals(params) buffer, chain them, and set FFrame.OutParms@+0x80 to the head. The exec thunk walks this chain for
// by-ref/out params (e.g. const FTransform& SpawnTransform in BeginDeferredActorSpawnFromClass) — without it the
// walk derefs a null/stale OutParms and crashes at ProcessInternal+0xB58.
static uint8_t g_outparms[8*24]={0};
static void BuildOutParms(uintptr_t childProps, uint8_t* locals){
    memset(g_outparms,0,sizeof(g_outparms)); *(uint64_t*)(g_myframe+FF_OUTPARMS)=0;
    uintptr_t f=childProps; int n=0; uint8_t* prev=nullptr; uint8_t* head=nullptr;
    while(LooksLikePtr(f) && n<8){
        uint64_t flags=0; if(SafeReadable((void*)(f+FPROP_FLAGS),8)) flags=*(uint64_t*)(f+FPROP_FLAGS);
        if((flags&CPF_OutParm) && !(flags&CPF_ReturnParm)){
            int32_t off=0; if(SafeReadable((void*)(f+FPROP_OFFSET),4)) off=*(int32_t*)(f+FPROP_OFFSET);
            uint8_t* rec=g_outparms+n*24; *(uintptr_t*)(rec+0)=f; *(uintptr_t*)(rec+8)=(uintptr_t)(locals+off); *(uintptr_t*)(rec+16)=0;
            if(prev) *(uintptr_t*)(prev+16)=(uintptr_t)rec; else head=rec;
            prev=rec; n++;
        }
        uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8)) nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx;
    }
    *(uint64_t*)(g_myframe+FF_OUTPARMS)=(uint64_t)head;
}
// Call a native UFunction with a prepared params buffer. Result -> resultBuf.
static void CallNative(void* func, uintptr_t thunk, uintptr_t childProps, void* context, void* paramsBuf, void* resultBuf){
    memcpy(g_myframe, g_template, sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=func;
    *(void**)(g_myframe+FF_OBJECT)=context;
    *(uint64_t*)(g_myframe+FF_CODE)=0;
    *(void**)(g_myframe+FF_LOCALS)=paramsBuf;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)childProps;
    BuildOutParms(childProps,(uint8_t*)paramsBuf);   // S58: FFrame.OutParms chain for by-ref/out params
    ((PFN_THUNK)thunk)(context, g_myframe, resultBuf);
}
// Set an FString {Data,Num,Max} at pbuf+byteOff (Num includes null terminator).
static void SetFStringAt(uint8_t* pbuf, uint32_t byteOff, const wchar_t* s){
    int n=(int)wcslen(s)+1;
    *(uint64_t*)(pbuf+byteOff)=(uint64_t)s;
    *(uint32_t*)(pbuf+byteOff+8)=(uint32_t)n;
    *(uint32_t*)(pbuf+byteOff+12)=(uint32_t)n;
}

extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));
    if(kRunMode==RM_GOTOPHASE){ DoGoToPhase(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoGoToPhase when phases exhausted
    if(kRunMode==RM_WAKEMOVE){ DoWakeMove(); InterlockedIncrement(&g_called); g_inHook=0; return; }       // g_done set inside DoWakeMove after sampling
    if(kRunMode==RM_PUPPET){ DoPuppet(); InterlockedIncrement(&g_called); g_inHook=0; return; }             // runs every hit; g_done set by the Worker timeout
    if(kRunMode==RM_SPAWNPLAYER){ DoSpawnPlayer(); InterlockedIncrement(&g_called); g_done=1; g_inHook=0; return; }
    if(kRunMode==RM_SPAWNPOSSESS){ DoSpawnPossess(); InterlockedIncrement(&g_called); g_done=1; g_inHook=0; return; }
    if(kRunMode==RM_CHEATSPAWN){ DoCheatSpawn(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoCheatSpawn
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    uint8_t* pb=(uint8_t*)g_pbuf;
    if(g_offWCO!=0xFFFFFFFF) *(uint64_t*)(pb+g_offWCO)=(uint64_t)g_worldCtx;   // WorldContextObject
    if(g_offCmd!=0xFFFFFFFF) SetFStringAt(pb,g_offCmd,g_cmd);                   // Command FString
    if(g_offSP !=0xFFFFFFFF) *(uint64_t*)(pb+g_offSP)=0;                       // SpecificPlayer = null
    CallNative(g_ecc,g_eccThunk,g_eccChild,(void*)g_kslCDO,g_pbuf,g_rbuf);
    InterlockedIncrement(&g_called);
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
// ---- S75 RM_TOGGLEREADY: detour ULokiGameFeatureToggles::Get (checked variant that logs "not ready") and set the
// per-object readiness bit byte[D+0xB3] bit6 (0x40) so Get takes the ready path. D = [ [obj->vfn188()->0x7FF6BAB80AC0]
// +0x5A0 ]. Data-only write (persists after unhook, no .text patch left => dodges the code-integrity check).
static uint8_t* g_getStub=nullptr; static uint8_t g_getStolen[7]={0}; static uintptr_t g_getAddr=0;
static volatile long g_inOnGet=0, g_getHits=0, g_dSeenN=0, g_getWork=0; static uintptr_t g_dSeen[64]={0};
constexpr uintptr_t kGetRva=0x55DB6DE, kStoreGetterRva=0x5690AC0;   // checked Get 0x7FF6BAACB6DE, storeGetter 0x7FF6BAB80AC0
// Runs on whatever thread calls Get (rcx=the queried object). RECORD-ONLY diagnostic: no game-function calls (those
// hard-crash under the packer if any object faults) — just dedupe-record the object pointers. Resolve D + set bit6
// OFFLINE (after unhook) where SEH actually works. Tests whether the hook MECHANICS are safe.
extern "C" void OnGet(void* obj){
    InterlockedIncrement(&g_getHits);
    if(!LooksLikePtr((uintptr_t)obj)) return;
    long n=g_dSeenN; if(n>=64) return;
    for(long i=0;i<n;i++) if(g_dSeen[i]==(uintptr_t)obj) return;   // dedupe
    if(InterlockedCompareExchange(&g_dSeenN,n+1,n)==n) g_dSeen[n]=(uintptr_t)obj;
}
// Same trampoline shape as BuildHook but 7 stolen bytes + calls OnGet(rcx).
static uint8_t* BuildGetHook(uintptr_t fn,const uint8_t stolen[7]){
    uint8_t* blk=NearAlloc(fn,0x200); if(!blk)return nullptr;
    Emit t{blk}; for(int i=0;i<7;i++)EB(t,stolen[i]); EB(t,0xE9); int32_t rel=(int32_t)((intptr_t)(fn+7)-((intptr_t)t.w+4)); EU32(t,(uint32_t)rel);
    uint8_t* stub=blk+0x20; Emit e{stub};
    // Get is entered via indirect tail-jump (0 direct callers, prologue writes [rsp+8]) => entry rsp alignment is
    // UNKNOWN. Force-align to 16 before the call using rbp (nonvolatile, preserved across OnGet). rcx (=object) is
    // untouched through the saves so it is still the arg at the call.
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);EB(e,0x55);            // push rcx,rdx,r8,r9,rbp
    EB(e,0x48);EB(e,0x89);EB(e,0xE5); EB(e,0x48);EB(e,0x83);EB(e,0xE4);EB(e,0xF0); EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x20);  // mov rbp,rsp; and rsp,-16; sub rsp,0x20
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnGet); EB(e,0xFF);EB(e,0xD0);                    // mov rax,OnGet; call rax
    EB(e,0x48);EB(e,0x89);EB(e,0xEC); EB(e,0x5D);                                             // mov rsp,rbp; pop rbp
    EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);                        // pop r9,r8,rdx,rcx
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)blk); EB(e,0xFF);EB(e,0xE0);                       // mov rax,blk; jmp rax
    return stub;
}
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// Resolve g_cmd: read the first non-comment/non-blank line of kCmdFilePath; fall back to kDefaultCommand.
// Returns true if the file supplied the command, false if we fell back to the compiled default.
static bool LoadCommand(){
    wcscpy_s(g_cmd,_countof(g_cmd),kDefaultCommand);
    // S62: retry the open — a transient share/lock (editor/AV touching the file at inject time) made a
    // fresh inject fall back to the compiled default (BasicTraining) instead of the full tutorial mode.
    HANDLE h=INVALID_HANDLE_VALUE;
    for(int i=0;i<20 && h==INVALID_HANDLE_VALUE;i++){
        h=CreateFileA(kCmdFilePath,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(h==INVALID_HANDLE_VALUE) Sleep(50);
    }
    if(h==INVALID_HANDLE_VALUE){ Markerf("[0] LoadCommand: open failed (GetLastError=%lu) -> default fallback\r\n",GetLastError()); return false; }
    char buf[4096]; DWORD rd=0; bool got=ReadFile(h,buf,sizeof(buf)-1,&rd,nullptr)!=0; CloseHandle(h);
    if(!got||rd==0){ Markerf("[0] LoadCommand: read failed/empty (got=%d rd=%lu) -> default fallback\r\n",got?1:0,rd); return false; }
    buf[rd]=0;
    // Walk lines; take the first that isn't blank / '#' / '//'.
    for(char* p=buf; *p; ){
        char* eol=p; while(*eol && *eol!='\r' && *eol!='\n') eol++; char saved=*eol; *eol=0;
        char* s=p; while(*s==' '||*s=='\t') s++;                       // ltrim
        char* e=s+strlen(s); while(e>s&&(e[-1]==' '||e[-1]=='\t')) *--e=0; // rtrim
        bool comment = s[0]=='#' || (s[0]=='/'&&s[1]=='/');
        if(*s && !comment){
            wchar_t w[1024]; int n=MultiByteToWideChar(CP_UTF8,0,s,-1,w,_countof(w));
            if(n>0){ wcscpy_s(g_cmd,_countof(g_cmd),w); return true; }
            return false;
        }
        *eol=saved; p=eol; while(*p=='\r'||*p=='\n') p++;
    }
    return false;
}

static void ResolveFuncOnClass(uintptr_t cls,const char* fname,void** func,uintptr_t* thunk,uintptr_t* child){
    uintptr_t f=0; if(SafeReadable((void*)(cls+0x50),8)) f=*(uintptr_t*)(cls+0x50); int i=0;
    while(LooksLikePtr(f)&&i<600){ if(NameIs(f,fname)){ *func=(void*)f; if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))*thunk=th;} if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))*child=cp;} return; } uintptr_t nx=0; if(SafeReadable((void*)(f+0x30),8))nx=*(uintptr_t*)(f+0x30); f=nx; i++; }
}
// Walk a UFunction's param FField chain (head=childProps, Next@+0x18), return Offset_Internal@+0x44 of the named param.
static uint32_t ParamOffset(uintptr_t childHead,const char* name){
    uintptr_t f=childHead; int i=0;
    while(LooksLikePtr(f)&&i<40){ if(NameIs(f,name)){ if(SafeReadable((void*)(f+FPROP_OFFSET),4)) return *(uint32_t*)(f+FPROP_OFFSET); return 0xFFFFFFFF; } uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8))nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx; i++; }
    return 0xFFFFFFFF;
}

// ---- S68 spawn+possess helpers ----
// Find the first non-Default (live) instance whose class name contains `sub` (and object name contains `nameMust`).
static uintptr_t FindInstByClass(const char* sub, const char* nameMust){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,sub))continue; char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
            if(strncmp(on,"Default__",9)==0)continue; if(nameMust&&!strstr(on,nameMust))continue;
            return obj; } }
    return 0;
}
// Find the first object whose OWN FName == want (e.g. a UClass "BP_HERO_Ronin_C").
static uintptr_t FindObjExact(const char* want){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,want))return obj; } }
    return 0;
}
// Like FindObjExact but only returns an object that IS a class (own class name contains "Class", e.g.
// BlueprintGeneratedClass) — disambiguates the UClass "BP_HERO_Ronin_C" from spawned hero INSTANCES named the same.
static uintptr_t FindClassExact(const char* want){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(NameIs(obj,want)){ uintptr_t c=ClassOf(obj); if(LooksLikePtr(c)){ char cn[96]; if(GetFNameStr(NameId(c),cn,sizeof(cn)) && strstr(cn,"Class")) return obj; } } } }
    return 0;
}
// Resolve a UFunction by name walking cls + its SuperStruct chain (@+0x48).
static void ResolveFuncSuper(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child){
    int g=0; while(LooksLikePtr(cls)&&g++<12){ ResolveFuncOnClass(cls,name,fn,thunk,child); if(*fn)return; cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0; }
}
// Resolve a UFunction on the first NATIVE ancestor (class name not "BP_*") — the native thunk, NOT a BP-bytecode
// override. The primitive calls with FFrame.Code=NULL, which crashes a BP-VM Func but is correct for a native thunk.
static void ResolveFuncNative(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child){
    int g=0; while(LooksLikePtr(cls)&&g++<12){
        char cn[128]; if(GetFNameStr(NameId(cls),cn,sizeof(cn)) && strncmp(cn,"BP_",3)!=0){ ResolveFuncOnClass(cls,name,fn,thunk,child); if(*fn)return; }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
}
// ---- S74 B2: resolve + call GoToPhase to advance the round ----
static bool ResolveGoToPhase(){
    g_gmPhase=FindInstByClass("GameMode_Tutorial",nullptr);
    if(!g_gmPhase){ Marker("[GP] no live GameMode_Tutorial instance (force-open first)\r\n"); return false; }
    ResolveFuncNative(ClassOf(g_gmPhase),"GoToPhase",&g_gpFn,&g_gpThunk,&g_gpChild);   // native LokiRoundGameMode thunk
    if(g_gpChild){ uint32_t o=ParamOffset(g_gpChild,"NextPhase"); if(o!=0xFFFFFFFF)g_offNextPhase=o; }
    Markerf("[GP] gm=0x%llX goToPhaseThunk=0x%llX child=0x%llX NextPhase@0x%X\r\n",
        (unsigned long long)g_gmPhase,(unsigned long long)g_gpThunk,(unsigned long long)g_gpChild,g_offNextPhase);
    return g_gpThunk!=0;
}
// Runs on the GAME THREAD (from OnPI). Advances the round ONE phase per ~450ms so each phase processes
// (spawn-select/deploy/drop) on the game thread between calls. Steps EGP_Pre(2) -> EGP_Combat(7).
static void DoGoToPhase(){
    DWORD now=GetTickCount();
    if(g_lastPhaseMs && now-g_lastPhaseMs<450) return;
    g_lastPhaseMs=now;
    if(g_phaseIdx>=(int)(sizeof(kPhaseList)/sizeof(kPhaseList[0]))){ g_done=1; return; }
    int ph=kPhaseList[g_phaseIdx++];
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    ((uint8_t*)g_pbuf)[g_offNextPhase]=(uint8_t)ph;   // NextPhase (ERoundPhase, 1 byte)
    Markerf("[GP] calling GoToPhase(%d)...\r\n",ph);   // BEFORE the call, so a crash marker localizes it
    bool faulted=CallNativeGuarded(g_gpFn,g_gpThunk,g_gpChild,(void*)g_gmPhase,g_pbuf,g_rbuf);
    Markerf("[GP] GoToPhase(%d) returned%s\r\n",ph,faulted?" [FAULTED — null captured, halting sweep]":"");
    if(faulted){ g_done=1; return; }
}
// Walk cls + super chain, each class's ChildProperties(@+0x58 via FField.Next@+0x18), for a named property's Offset_Internal(@+0x44).
static uint32_t PropOffsetSuper(uintptr_t cls,const char* name){
    int g=0; while(LooksLikePtr(cls)&&g++<12){
        uintptr_t f=SafeReadable((void*)(cls+0x58),8)?*(uintptr_t*)(cls+0x58):0; int i=0;
        while(LooksLikePtr(f)&&i<300){ if(NameIs(f,name)){ if(SafeReadable((void*)(f+FPROP_OFFSET),4)) return *(uint32_t*)(f+FPROP_OFFSET); } uintptr_t nx=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; f=nx; i++; }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
    return 0xFFFFFFFF;
}
// S75: resolve the possessed hero's CMC + the wake-kick UFunctions.
static bool ResolveWakeMove(){
    g_wmPC=FindInstByClass("LokiPlayerController_Dev",nullptr);
    if(!g_wmPC){ Marker("[WM] no live LokiPlayerController_Dev -> abort (force-open+possess first)\r\n"); return false; }
    uint32_t pawnOff=PropOffsetSuper(ClassOf(g_wmPC),"Pawn"); if(pawnOff==0xFFFFFFFF) pawnOff=0x3F8;
    if(SafeReadable((void*)(g_wmPC+pawnOff),8)) g_wmHero=*(uintptr_t*)(g_wmPC+pawnOff);
    if(!LooksLikePtr(g_wmHero)){ Markerf("[WM] PC->Pawn null (pawnOff@0x%X) -> abort (no possessed hero)\r\n",pawnOff); return false; }
    uint32_t cmcOff=PropOffsetSuper(ClassOf(g_wmHero),"CharacterMovement"); if(cmcOff==0xFFFFFFFF) cmcOff=0x458;
    if(SafeReadable((void*)(g_wmHero+cmcOff),8)) g_wmCMC=*(uintptr_t*)(g_wmHero+cmcOff);
    if(!LooksLikePtr(g_wmCMC)){ Markerf("[WM] hero->CharacterMovement null (cmcOff@0x%X) -> abort\r\n",cmcOff); return false; }
    uintptr_t cmcCls=ClassOf(g_wmCMC), heroCls=ClassOf(g_wmHero);
    g_wmGravOff=PropOffsetSuper(cmcCls,"GravityScale");
    g_wmVelOff=PropOffsetSuper(cmcCls,"Velocity");
    g_wmModeOff=PropOffsetSuper(cmcCls,"MovementMode");
    ResolveFuncSuper(cmcCls,"SetActive",&g_saFn,&g_saThunk,&g_saChild);
    if(g_saChild){ g_oSaActive=ParamOffset(g_saChild,"bNewActive"); g_oSaReset=ParamOffset(g_saChild,"bReset"); }
    ResolveFuncSuper(cmcCls,"SetComponentTickEnabled",&g_scteFn,&g_scteThunk,&g_scteChild);
    if(g_scteChild){ g_oScteEn=ParamOffset(g_scteChild,"bEnabled"); }
    ResolveFuncSuper(cmcCls,"SetMovementMode",&g_smmFn,&g_smmThunk,&g_smmChild);
    if(g_smmChild){ g_oSmmMode=ParamOffset(g_smmChild,"NewMovementMode"); g_oSmmCustom=ParamOffset(g_smmChild,"NewCustomMode"); }
    ResolveFuncSuper(heroCls,"SetActorTickEnabled",&g_satFn,&g_satThunk,&g_satChild);
    if(g_satChild){ g_oSatEn=ParamOffset(g_satChild,"bEnabled"); }
    ResolveFuncSuper(heroCls,"K2_SetActorLocation",&g_slFn,&g_slThunk,&g_slChild);   // teleport the hero above ground before waking
    if(g_slChild){ g_oSlLoc=ParamOffset(g_slChild,"NewLocation"); g_oSlSweep=ParamOffset(g_slChild,"bSweep"); g_oSlTele=ParamOffset(g_slChild,"bTeleport"); }
    ResolveFuncSuper(ClassOf(g_wmPC),"ResetIgnoreMoveInput",&g_rimFn,&g_rimThunk,&g_rimChild);   // clear the PC's IgnoreMoveInput counter
    ResolveFuncSuper(heroCls,"AddMovementInput",&g_amiFn,&g_amiThunk,&g_amiChild);   // force-move test
    if(g_amiChild){ g_oAmiDir=ParamOffset(g_amiChild,"WorldDirection"); g_oAmiScale=ParamOffset(g_amiChild,"ScaleValue"); g_oAmiForce=ParamOffset(g_amiChild,"bForce"); }
    if(SafeReadable((void*)(g_wmCMC+0xD0),8)) g_wmRoot=*(uintptr_t*)(g_wmCMC+0xD0);   // UpdatedComponent = root capsule
    char hcn[96]="-"; if(ClassOf(g_wmHero)) GetFNameStr(NameId(ClassOf(g_wmHero)),hcn,sizeof(hcn));
    Markerf("[WM] PC=0x%llX hero=0x%llX(%s) CMC=0x%llX grav@0x%X vel@0x%X mode@0x%X\r\n",
        (unsigned long long)g_wmPC,(unsigned long long)g_wmHero,hcn,(unsigned long long)g_wmCMC,g_wmGravOff,g_wmVelOff,g_wmModeOff);
    Markerf("[WM] thunks SetActive=0x%llX(act@0x%X rst@0x%X) SetTickEn=0x%llX(en@0x%X) SetMoveMode=0x%llX(mode@0x%X cust@0x%X) SetActorTick=0x%llX(en@0x%X)\r\n",
        (unsigned long long)g_saThunk,g_oSaActive,g_oSaReset,(unsigned long long)g_scteThunk,g_oScteEn,(unsigned long long)g_smmThunk,g_oSmmMode,g_oSmmCustom,(unsigned long long)g_satThunk,g_oSatEn);
    Markerf("[WM] root=0x%llX SetActorLocation=0x%llX(loc@0x%X sweep@0x%X tele@0x%X) wakeZ=%.0f\r\n",
        (unsigned long long)g_wmRoot,(unsigned long long)g_slThunk,g_oSlLoc,g_oSlSweep,g_oSlTele,kWakeZ);
    return LooksLikePtr(g_wmCMC);
}
static void WmSampleLine(const char* tag){
    double vx=0,vy=0,vz=0; uint32_t mode=0xFF; float grav=-1;
    if(g_wmVelOff!=0xFFFFFFFF&&SafeReadable((void*)(g_wmCMC+g_wmVelOff),24)){ vx=*(double*)(g_wmCMC+g_wmVelOff); vy=*(double*)(g_wmCMC+g_wmVelOff+8); vz=*(double*)(g_wmCMC+g_wmVelOff+16); }
    if(g_wmModeOff!=0xFFFFFFFF&&SafeReadable((void*)(g_wmCMC+g_wmModeOff),1)) mode=*(uint8_t*)(g_wmCMC+g_wmModeOff);
    if(g_wmGravOff!=0xFFFFFFFF&&SafeReadable((void*)(g_wmCMC+g_wmGravOff),4)) grav=*(float*)(g_wmCMC+g_wmGravOff);
    double px=0,py=0,pz=0;
    if(LooksLikePtr(g_wmRoot)&&SafeReadable((void*)(g_wmRoot+0x158),24)){ px=*(double*)(g_wmRoot+0x158); py=*(double*)(g_wmRoot+0x158+8); pz=*(double*)(g_wmRoot+0x158+16); }
    double v2=vx*vx+vy*vy+vz*vz, mag=(v2>0)?__builtin_sqrt(v2):0.0;
    Markerf("[WM] %s: pos=(%.0f,%.0f,%.1f) mode=%u grav=%.2f vel=(%.1f,%.1f,%.1f) |v|=%.1f\r\n",tag,px,py,pz,mode,grav,vx,vy,vz,mag);
}
// Runs on the GAME THREAD (from OnPI). First hit = do the kick; subsequent hits (every ~400ms) sample Velocity/mode.
static void DoWakeMove(){
    DWORD now=GetTickCount();
    if(g_wmSample==0){
        WmSampleLine("BEFORE");
        // TELEPORT above ground FIRST: the hero was UNDER the map (Z~0.5, ground~18), so movement/collision is stuck in
        // geometry. Place it at kWakeZ (well above) via K2_SetActorLocation (teleport, no sweep), keeping X/Y.
        if(g_slThunk && LooksLikePtr(g_wmRoot) && SafeReadable((void*)(g_wmRoot+0x158),24)){
            double px=*(double*)(g_wmRoot+0x158), py=*(double*)(g_wmRoot+0x158+8);
            double tx=(kWakeX>-999998.0)?kWakeX:px, ty=(kWakeY>-999998.0)?kWakeY:py;   // keep X/Y unless overridden
            memset(g_slbuf,0,sizeof(g_slbuf));
            if(g_oSlLoc!=0xFFFFFFFF){ double* NL=(double*)(g_slbuf+g_oSlLoc); NL[0]=tx; NL[1]=ty; NL[2]=kWakeZ; }
            if(g_oSlSweep!=0xFFFFFFFF) g_slbuf[g_oSlSweep]=0; if(g_oSlTele!=0xFFFFFFFF) g_slbuf[g_oSlTele]=1;
            bool f=CallNativeGuarded(g_slFn,g_slThunk,g_slChild,(void*)g_wmHero,g_slbuf,g_rbuf);
            Markerf("[WM] teleport -> (%.0f,%.0f,%.0f)%s\r\n",tx,ty,kWakeZ,f?" FAULTED":"");
        }
        if(g_wmGravOff!=0xFFFFFFFF&&SafeReadable((void*)(g_wmCMC+g_wmGravOff),4)){ *(float*)(g_wmCMC+g_wmGravOff)=1.0f; Marker("[WM] GravityScale=1.0 set\r\n"); }
        uint8_t* pb=(uint8_t*)g_pbuf;
        if(g_saThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(g_oSaActive!=0xFFFFFFFF)pb[g_oSaActive]=1; if(g_oSaReset!=0xFFFFFFFF)pb[g_oSaReset]=0; bool f=CallNativeGuarded(g_saFn,g_saThunk,g_saChild,(void*)g_wmCMC,g_pbuf,g_rbuf); Markerf("[WM] SetActive(true)%s\r\n",f?" FAULTED":""); }
        if(g_scteThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(g_oScteEn!=0xFFFFFFFF)pb[g_oScteEn]=1; bool f=CallNativeGuarded(g_scteFn,g_scteThunk,g_scteChild,(void*)g_wmCMC,g_pbuf,g_rbuf); Markerf("[WM] SetComponentTickEnabled(true)%s\r\n",f?" FAULTED":""); }
        if(g_satThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(g_oSatEn!=0xFFFFFFFF)pb[g_oSatEn]=1; bool f=CallNativeGuarded(g_satFn,g_satThunk,g_satChild,(void*)g_wmHero,g_pbuf,g_rbuf); Markerf("[WM] SetActorTickEnabled(true)%s\r\n",f?" FAULTED":""); }
        if(g_smmThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(g_oSmmMode!=0xFFFFFFFF)pb[g_oSmmMode]=3; if(g_oSmmCustom!=0xFFFFFFFF)pb[g_oSmmCustom]=0; bool f=CallNativeGuarded(g_smmFn,g_smmThunk,g_smmChild,(void*)g_wmCMC,g_pbuf,g_rbuf); Markerf("[WM] SetMovementMode(Falling=3)%s\r\n",f?" FAULTED":""); }
        // Clear the PC's IgnoreMoveInput counter: AddMovementInput no-ops (ControlInputVector stays 0) while it's >0.
        // input_watch proved WASD produces ZERO ControlInputVector while jump works => movement input is being ignored.
        if(g_rimThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); bool f=CallNativeGuarded(g_rimFn,g_rimThunk,g_rimChild,(void*)g_wmPC,g_pbuf,g_rbuf); Markerf("[WM] ResetIgnoreMoveInput(PC)%s\r\n",f?" FAULTED":""); }
        g_wmLastMs=now; g_wmSample=1; return;
    }
    // FORCE-MOVE TEST: every game-thread hit, (a) AddMovementInput(+X,bForce) AND (b) directly poke the CMC's
    // Acceleration(+0x328) and Velocity(+0xE8) to +X. If the hero's X drifts, the CMC integrates horizontal motion
    // => a WASD puppet (write velocity per frame from key state) is viable; if X stays put, movement is gated deeper.
    if(g_amiThunk){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); uint8_t* pb=(uint8_t*)g_pbuf;
        if(g_oAmiDir!=0xFFFFFFFF){ double* D=(double*)(pb+g_oAmiDir); D[0]=1.0; D[1]=0.0; D[2]=0.0; }
        if(g_oAmiScale!=0xFFFFFFFF) *(float*)(pb+g_oAmiScale)=1.0f;
        if(g_oAmiForce!=0xFFFFFFFF) pb[g_oAmiForce]=1;
        CallNativeGuarded(g_amiFn,g_amiThunk,g_amiChild,(void*)g_wmHero,g_pbuf,g_rbuf);
    }
    if(SafeReadable((void*)(g_wmCMC+0x328),24)){ double* A=(double*)(g_wmCMC+0x328); A[0]=2000.0; A[1]=0.0; A[2]=0.0; }   // Acceleration = +X
    if(SafeReadable((void*)(g_wmCMC+0xE8),24)){ double* V=(double*)(g_wmCMC+0xE8); V[0]=600.0; V[1]=0.0; }                 // Velocity.XY = +X (keep Z)
    if(now-g_wmLastMs<400) return;
    g_wmLastMs=now;
    char tag[24]; _snprintf_s(tag,sizeof(tag),_TRUNCATE,"sample %d",g_wmSample);
    WmSampleLine(tag);
    g_wmSample++;
    if(g_wmSample>12){ g_done=1; }
}
// S75 RM_PUPPET: runs on the GAME THREAD every hit. Reads WASD, writes CMC.Velocity.XY (keeps Z for gravity/jump).
static void DoPuppet(){
    if(!g_puppetInit){
        if(g_wmGravOff!=0xFFFFFFFF&&SafeReadable((void*)(g_wmCMC+g_wmGravOff),4)) *(float*)(g_wmCMC+g_wmGravOff)=1.0f;
        if(g_rimThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallNativeGuarded(g_rimFn,g_rimThunk,g_rimChild,(void*)g_wmPC,g_pbuf,g_rbuf); }
        g_puppetInit=true; Markerf("[PUP] puppet ACTIVE: WASD -> CMC velocity (speed=%.0f yaw=%.0f) hero=0x%llX CMC=0x%llX\r\n",kPupSpeed,kPupYawDeg,(unsigned long long)g_wmHero,(unsigned long long)g_wmCMC);
    }
    if(!SafeReadable((void*)(g_wmCMC+0xE8),16)) return;
    double* V=(double*)(g_wmCMC+0xE8);
    // Only drive while the game window is focused (avoids moving when typing elsewhere); if HWND unknown, always drive.
    if(g_gameHwnd && GetForegroundWindow()!=g_gameHwnd){ V[0]=0.0; V[1]=0.0; return; }
    bool w=(GetAsyncKeyState('W')&0x8000)!=0, a=(GetAsyncKeyState('A')&0x8000)!=0, s=(GetAsyncKeyState('S')&0x8000)!=0, d=(GetAsyncKeyState('D')&0x8000)!=0;
    double ax=(w?1.0:0.0)-(s?1.0:0.0);   // forward/back axis (W/S)
    double ay=(d?1.0:0.0)-(a?1.0:0.0);   // right/left axis (D/A)
    double yaw=kPupYawDeg*3.14159265358979/180.0, c=__builtin_cos(yaw), sn=__builtin_sin(yaw);
    double dx=ax*c - ay*sn, dy=ax*sn + ay*c;   // rotate the WASD frame by the (camera) yaw offset
    double m=__builtin_sqrt(dx*dx+dy*dy), vx=0.0, vy=0.0;
    if(m>0.0001){ vx=dx/m*kPupSpeed; vy=dy/m*kPupSpeed; }
    V[0]=vx; V[1]=vy;   // keep V[2] (Z) so gravity + jump still work
    if(SafeReadable((void*)(g_wmCMC+0x328),24)){ double* A=(double*)(g_wmCMC+0x328); A[0]=vx*4.0; A[1]=vy*4.0; A[2]=0.0; }   // Acceleration -> facing/anim
}
// S74 B2 exp3: resolve the REAL hero spawn — LokiGameMode::SpawnPlayer(PlayerState, Transform& OUT, StartSpot, bEnsure) -> LokiCharacter*.
static bool ResolveSpawnPlayer(){
    g_gm2=FindInstByClass("GameMode_Tutorial",nullptr);
    g_pc2=FindInstByClass("LokiPlayerController_Dev",nullptr);
    g_startSpot=FindInstByClass("LokiPlayerStart","UAID");
    if(!g_startSpot) g_startSpot=FindInstByClass("CapturePoint_Tutorial","UAID");
    if(!g_startSpot) g_startSpot=FindInstByClass("LokiRespawnBeacon_Tutorial","UAID");
    if(!g_gm2||!g_pc2){ Marker("[SPW] missing gm/pc -> abort\r\n"); return false; }
    uint32_t psOff=PropOffsetSuper(ClassOf(g_pc2),"PlayerState");
    if(psOff!=0xFFFFFFFF && SafeReadable((void*)(g_pc2+psOff),8)) g_localPS=*(uintptr_t*)(g_pc2+psOff);
    char psn[96]="-"; if(LooksLikePtr(g_localPS)&&ClassOf(g_localPS)) GetFNameStr(NameId(ClassOf(g_localPS)),psn,sizeof(psn));
    g_heroClass=FindObjExact("BP_HERO_Ronin_C");   // the hero to spawn; SpawnPlayer reads PlayerState.HeroClass
    if(LooksLikePtr(g_localPS)) g_psHeroOff=PropOffsetSuper(ClassOf(g_localPS),"HeroClass");
    ResolveFuncNative(ClassOf(g_gm2),"SpawnPlayer",&g_spwFn,&g_spwThunk,&g_spwChild);
    if(g_spwChild){ g_oSpwPS=ParamOffset(g_spwChild,"PlayerState"); g_oSpwXf=ParamOffset(g_spwChild,"SpawnTransform"); g_oSpwSS=ParamOffset(g_spwChild,"StartSpot"); g_oSpwEnsure=ParamOffset(g_spwChild,"bEnsurePositionIsValid"); g_oSpwRet=ParamOffset(g_spwChild,"ReturnValue"); }
    ResolveFuncNative(ClassOf(g_pc2),"Possess",&g_possessFn,&g_possessThunk,&g_possessChild);
    if(g_possessChild){ uint32_t o=ParamOffset(g_possessChild,"InPawn"); if(o!=0xFFFFFFFF)g_offInPawn=o; }
    Markerf("[SPW] gm=0x%llX pc=0x%llX localPS=0x%llX(%s,psOff@0x%X) startSpot=0x%llX spawnThunk=0x%llX possessThunk=0x%llX\r\n",
        (unsigned long long)g_gm2,(unsigned long long)g_pc2,(unsigned long long)g_localPS,psn,psOff,(unsigned long long)g_startSpot,(unsigned long long)g_spwThunk,(unsigned long long)g_possessThunk);
    Markerf("[SPW] offs PS@0x%X Xf@0x%X SS@0x%X Ensure@0x%X Ret@0x%X InPawn@0x%X | heroClass=0x%llX psHeroOff@0x%X\r\n",g_oSpwPS,g_oSpwXf,g_oSpwSS,g_oSpwEnsure,g_oSpwRet,g_offInPawn,(unsigned long long)g_heroClass,g_psHeroOff);
    return g_spwThunk!=0 && LooksLikePtr(g_localPS);
}
// Runs on the GAME THREAD (from OnPI): SpawnPlayer(localPS, xform_out, startSpot, bEnsure=true) -> hero, then Possess.
static void DoSpawnPlayer(){
    uint8_t* pb=(uint8_t*)g_spbuf; memset(g_spbuf,0,sizeof(g_spbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(g_oSpwPS!=0xFFFFFFFF) *(uint64_t*)(pb+g_oSpwPS)=(uint64_t)g_localPS;
    if(g_oSpwSS!=0xFFFFFFFF) *(uint64_t*)(pb+g_oSpwSS)=(uint64_t)g_startSpot;
    if(g_oSpwEnsure!=0xFFFFFFFF) pb[g_oSpwEnsure]=1;
    // Seed the hero selection: SpawnPlayer reads PlayerState.HeroClass to know which hero to spawn (round never
    // reached hero-select, so it's null -> SpawnPlayer returns null). Force it to Ronin.
    if(g_psHeroOff!=0xFFFFFFFF && LooksLikePtr(g_heroClass) && LooksLikePtr(g_localPS) && SafeReadable((void*)(g_localPS+g_psHeroOff),8)){
        uintptr_t old=*(uintptr_t*)(g_localPS+g_psHeroOff); char ocn[96]="-"; if(LooksLikePtr(old)) GetFNameStr(NameId(old),ocn,sizeof(ocn));
        *(uintptr_t*)(g_localPS+g_psHeroOff)=g_heroClass;
        Markerf("[SPW] set PlayerState.HeroClass@0x%X: %s -> BP_HERO_Ronin_C\r\n",g_psHeroOff,ocn);
    }
    Marker("[SPW] calling SpawnPlayer...\r\n");
    if(CallNativeGuarded(g_spwFn,g_spwThunk,g_spwChild,(void*)g_gm2,g_spbuf,g_rbuf)){ Marker("[SPW] SpawnPlayer FAULTED (null captured)\r\n"); g_done=1; return; }
    uintptr_t hero=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(hero)&&g_oSpwRet!=0xFFFFFFFF) hero=*(uint64_t*)(pb+g_oSpwRet);
    char hcn[96]="-"; if(LooksLikePtr(hero)&&ClassOf(hero)) GetFNameStr(NameId(ClassOf(hero)),hcn,sizeof(hcn));
    Markerf("[SPW] SpawnPlayer -> hero=0x%llX cls=%s\r\n",(unsigned long long)hero,hcn);
    g_spawnedPawn=hero;
    if(LooksLikePtr(hero) && g_possessThunk){
        uint8_t* qb=(uint8_t*)g_pbuf; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_offInPawn!=0xFFFFFFFF) *(uint64_t*)(qb+g_offInPawn)=(uint64_t)hero;
        CallNative(g_possessFn,g_possessThunk,g_possessChild,(void*)g_pc2,g_pbuf,g_rbuf);
        Marker("[SPW] Possess(PC,hero) called\r\n");
    }
    g_done=1;
}
static bool ResolveSpawnPossess(){
    g_gm2=FindInstByClass("GameMode_Tutorial",nullptr);
    g_pc2=FindInstByClass("LokiPlayerController_Dev",nullptr);
    g_startSpot=FindInstByClass("LokiPlayerStart","UAID");
    if(!g_startSpot) g_startSpot=FindInstByClass("CapturePoint_Tutorial","UAID");
    if(!g_startSpot) g_startSpot=FindInstByClass("LokiRespawnBeacon_Tutorial","UAID");
    g_heroClass=FindClassExact("BP_HERO_Ronin_C");   // the hero UCLASS (not a spawned instance of the same name)
    Markerf("[SP] gm=0x%llX pc=0x%llX startSpot=0x%llX heroClass=0x%llX\r\n",(unsigned long long)g_gm2,(unsigned long long)g_pc2,(unsigned long long)g_startSpot,(unsigned long long)g_heroClass);
    if(!g_gm2||!g_pc2||!g_startSpot)return false;
    ResolveFuncNative(ClassOf(g_gm2),"SpawnDefaultPawnFor",&g_spawnFn,&g_spawnThunk,&g_spawnChild);   // NATIVE thunk, not the BP override
    if(g_spawnChild){ uint32_t o; o=ParamOffset(g_spawnChild,"NewPlayer"); if(o!=0xFFFFFFFF)g_offSpawnNP=o; o=ParamOffset(g_spawnChild,"StartSpot"); if(o!=0xFFFFFFFF)g_offSpawnSS=o; o=ParamOffset(g_spawnChild,"ReturnValue"); if(o!=0xFFFFFFFF)g_offSpawnRet=o; }
    ResolveFuncNative(ClassOf(g_pc2),"Possess",&g_possessFn,&g_possessThunk,&g_possessChild);
    if(g_possessChild){ uint32_t o=ParamOffset(g_possessChild,"InPawn"); if(o!=0xFFFFFFFF)g_offInPawn=o; }
    if(kUseGameplayStatics){
        g_gsCDO=FindObjExact("Default__GameplayStatics");
        if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
            ResolveFuncOnClass(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
            ResolveFuncOnClass(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
            uint32_t o;
            if(g_beginChild){ o=ParamOffset(g_beginChild,"WorldContextObject");if(o!=0xFFFFFFFF)g_oBWorld=o; o=ParamOffset(g_beginChild,"ActorClass");if(o!=0xFFFFFFFF)g_oBClass=o; o=ParamOffset(g_beginChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oBXform=o; o=ParamOffset(g_beginChild,"CollisionHandlingOverride");if(o!=0xFFFFFFFF)g_oBColl=o; o=ParamOffset(g_beginChild,"Owner");if(o!=0xFFFFFFFF)g_oBOwner=o; o=ParamOffset(g_beginChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oBRet=o; }
            if(g_finishChild){ o=ParamOffset(g_finishChild,"Actor");if(o!=0xFFFFFFFF)g_oFActor=o; o=ParamOffset(g_finishChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oFXform=o; o=ParamOffset(g_finishChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oFRet=o; }
        }
        ResolveFuncSuper(ClassOf(g_startSpot),"GetActorTransform",&g_xfFn,&g_xfThunk,&g_xfChild);
        if(g_xfChild){ uint32_t o=ParamOffset(g_xfChild,"ReturnValue"); if(o!=0xFFFFFFFF)g_oXfRet=o; }
        ResolveFuncSuper(ClassOf(g_startSpot),"K2_GetActorLocation",&g_locFn,&g_locThunk,&g_locChild);   // real spawn loc (GetActorTransform often unresolved -> origin/void)
        if(LooksLikePtr(g_heroClass)){ ResolveFuncSuper(g_heroClass,"K2_SetActorLocation",&g_slFn,&g_slThunk,&g_slChild);   // sweep-to-ground (on the hero, inherits AActor)
            if(g_slChild){ g_oSlLoc=ParamOffset(g_slChild,"NewLocation"); g_oSlSweep=ParamOffset(g_slChild,"bSweep"); g_oSlTele=ParamOffset(g_slChild,"bTeleport"); } }
        if(LooksLikePtr(g_pc2)){ ResolveFuncSuper(ClassOf(g_pc2),"GetPlayerViewPoint",&g_vpFn,&g_vpThunk,&g_vpChild);   // camera view point = streamed ground
            if(g_vpChild){ g_oVpLoc=ParamOffset(g_vpChild,"Location"); g_oVpRot=ParamOffset(g_vpChild,"Rotation"); }
            ResolveFuncSuper(ClassOf(g_pc2),"SetViewTargetWithBlend",&g_svtFn,&g_svtThunk,&g_svtChild); if(g_svtChild) g_oSvtTarget=ParamOffset(g_svtChild,"NewViewTarget"); }
        if(LooksLikePtr(g_heroClass)){ ResolveFuncNative(g_heroClass,"GetCosmeticsController",&g_ccFn,&g_ccThunk,&g_ccChild);
            ResolveFuncNative(g_heroClass,"GetCosmeticsAssetID",&g_gcaFn,&g_gcaThunk,&g_gcaChild);
            ResolveFuncNative(g_heroClass,"RefreshCosmetics",&g_rcFn,&g_rcThunk,&g_rcChild);
            ResolveFuncNative(g_heroClass,"OnRep_CosmeticsAssetID",&g_oncFn,&g_oncThunk,&g_oncChild);
            ResolveFuncNative(g_heroClass,"GetDefaultRecommendedLoadoutFromClass",&g_drlFn,&g_drlThunk,&g_drlChild);
            Markerf("[COS] resolve: getController=0x%llX getAssetID=0x%llX refresh=0x%llX defLoadout=0x%llX\r\n",(unsigned long long)g_ccThunk,(unsigned long long)g_gcaThunk,(unsigned long long)g_rcThunk,(unsigned long long)g_drlThunk); }
        Markerf("[GS] gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX xfThunk=0x%llX\r\n",(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_xfThunk);
        Markerf("[GS] B[world@%X class@%X xform@%X coll@%X owner@%X ret@%X] F[actor@%X xform@%X ret@%X] xfRet@%X\r\n",g_oBWorld,g_oBClass,g_oBXform,g_oBColl,g_oBOwner,g_oBRet,g_oFActor,g_oFXform,g_oFRet,g_oXfRet);
    }
    Markerf("[SP] spawnThunk=0x%llX(NP@0x%X SS@0x%X ret@0x%X) possessThunk=0x%llX(InPawn@0x%X)\r\n",
        (unsigned long long)g_spawnThunk,g_offSpawnNP,g_offSpawnSS,g_offSpawnRet,(unsigned long long)g_possessThunk,g_offInPawn);
    return g_spawnThunk&&g_possessThunk;
}
static const bool kDoPossess = true;   // S68: spawn (native) + possess; step markers localize any crash.
// Runs on the GAME THREAD (from OnPI): SpawnDefaultPawnFor(PC, StartSpot) -> pawn, then (optionally) PC.Possess(pawn).
// Markers flush per call so a crash pinpoints which native call died.
static void DoSpawnPossess(){
    if(kUseGameplayStatics && g_beginThunk && g_finishThunk){
        uint32_t xfsz=(g_oBColl>g_oBXform)?(g_oBColl-g_oBXform):0x50; if(xfsz>sizeof(g_xform))xfsz=sizeof(g_xform);
        // 1. GetActorTransform(startSpot) -> g_xform (struct return via RESULT; fall back to the params ReturnValue)
        memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_xform,0,sizeof(g_xform));
        if(g_xfThunk){ CallNative(g_xfFn,g_xfThunk,g_xfChild,(void*)g_startSpot,g_gsbuf,g_xform);
            bool zero=true; for(uint32_t i=0;i<0x38;i++) if(g_xform[i]){zero=false;break;}
            if(zero && g_oXfRet!=0xFFFFFFFF && g_oXfRet+xfsz<=sizeof(g_gsbuf)) memcpy(g_xform,g_gsbuf+g_oXfRet,xfsz); }
        // LOCATION FIX (S74): the start spot's landscape COLLISION isn't streamed (spectator isn't a streaming source
        // there) -> the hero falls through the visible grass onto a lower base collision UNDER the map. Spawn where the
        // CAMERA is actually looking instead (that area IS streamed/rendering -> has real collision). Then sweep down.
        bool haveLoc=false;
        if(g_vpThunk && LooksLikePtr(g_pc2) && g_oVpLoc!=0xFFFFFFFF){
            memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            CallNative(g_vpFn,g_vpThunk,g_vpChild,(void*)g_pc2,g_gsbuf,g_rbuf);
            double* V=(double*)(g_gsbuf+g_oVpLoc);
            if(V[0]||V[1]||V[2]){ *(double*)(g_xform+0x20)=V[0]; *(double*)(g_xform+0x28)=V[1]; *(double*)(g_xform+0x30)=V[2]+200.0; *(double*)(g_xform+0x18)=1.0; haveLoc=true;
                Markerf("[GS] camera viewpoint=(%.0f,%.0f,%.0f) -> spawn there + sweep down (streamed ground)\r\n",V[0],V[1],V[2]); }
        }
        if(!haveLoc && g_locThunk && LooksLikePtr(g_startSpot)){   // fallback: start spot (+5000, sweep down)
            memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            CallNative(g_locFn,g_locThunk,g_locChild,(void*)g_startSpot,g_gsbuf,g_rbuf);
            double* L=(double*)g_rbuf;
            if(L[0]||L[1]||L[2]){
                *(double*)(g_xform+0x20)=L[0]; *(double*)(g_xform+0x28)=L[1]; *(double*)(g_xform+0x30)=L[2]+5000.0;
                if(!*(double*)(g_xform+0x00)&&!*(double*)(g_xform+0x08)&&!*(double*)(g_xform+0x10)&&!*(double*)(g_xform+0x18)) *(double*)(g_xform+0x18)=1.0;
            }
        }
        double* t=(double*)(g_xform+0x20); Markerf("[GS] xform T=(%.1f,%.1f,%.1f)\r\n",t[0],t[1],t[2]);
        // 2. BeginDeferredActorSpawnFromClass(gm, heroClass, xform, AdjustButAlwaysSpawn) -> deferred actor
        memset(g_gsbuf,0,sizeof(g_gsbuf));
        *(uint64_t*)(g_gsbuf+g_oBWorld)=(uint64_t)g_gm2;
        *(uint64_t*)(g_gsbuf+g_oBClass)=(uint64_t)g_heroClass;
        memcpy(g_gsbuf+g_oBXform,g_xform,xfsz);
        g_gsbuf[g_oBColl]=2;   // ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn
        memset(g_rbuf,0,sizeof(g_rbuf));
        CallNative(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_gsbuf,g_rbuf);
        uintptr_t deferred=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(deferred)) deferred=*(uint64_t*)(g_gsbuf+g_oBRet);
        g_spStep=2; char dcn[96]="-"; if(LooksLikePtr(deferred)&&ClassOf(deferred))GetFNameStr(NameId(ClassOf(deferred)),dcn,sizeof(dcn));
        Markerf("[GS] deferred=0x%llX cls=%s\r\n",(unsigned long long)deferred,dcn);
        // 3. FinishSpawningActor(deferred, xform) -> spawned actor
        uintptr_t actor=0;
        if(LooksLikePtr(deferred)){
            memset(g_gsbuf,0,sizeof(g_gsbuf)); *(uint64_t*)(g_gsbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_gsbuf+g_oFXform,g_xform,xfsz);
            memset(g_rbuf,0,sizeof(g_rbuf));
            CallNative(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_gsbuf,g_rbuf);
            actor=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(actor)) actor=*(uint64_t*)(g_gsbuf+g_oFRet); if(!LooksLikePtr(actor)) actor=deferred;
        }
        g_spawnedPawn=actor; g_spStep=3;
        char acn[96]="-"; if(LooksLikePtr(actor)&&ClassOf(actor))GetFNameStr(NameId(ClassOf(actor)),acn,sizeof(acn));
        Markerf("[GS] spawned actor=0x%llX cls=%s\r\n",(unsigned long long)actor,acn);
        // MESH DIAGNOSTIC (user: ring visible but NO character model): is the hero's SkeletalMesh assigned + visible?
        if(LooksLikePtr(actor)){
            uint32_t meshOff=PropOffsetSuper(ClassOf(actor),"Mesh");
            if(meshOff!=0xFFFFFFFF && SafeReadable((void*)(actor+meshOff),8)){
                uintptr_t mc=*(uintptr_t*)(actor+meshOff); char mcn[96]="-"; if(LooksLikePtr(mc)&&ClassOf(mc))GetFNameStr(NameId(ClassOf(mc)),mcn,sizeof(mcn));
                uintptr_t skm=0; uint32_t skmOff=0xFFFFFFFF;
                if(LooksLikePtr(mc)){ skmOff=PropOffsetSuper(ClassOf(mc),"SkeletalMeshAsset"); if(skmOff==0xFFFFFFFF)skmOff=PropOffsetSuper(ClassOf(mc),"SkeletalMesh");
                    if(skmOff!=0xFFFFFFFF&&SafeReadable((void*)(mc+skmOff),8))skm=*(uintptr_t*)(mc+skmOff); }
                char skn[96]="-"; if(LooksLikePtr(skm))GetFNameStr(NameId(skm),skn,sizeof(skn));
                Markerf("[MESH] Mesh@0x%X comp=0x%llX(%s) SkeletalMesh@0x%X=0x%llX(%s)\r\n",meshOff,(unsigned long long)mc,mcn,skmOff,(unsigned long long)skm,skn);
            } else Markerf("[MESH] no 'Mesh' property found on hero (meshOff=0x%X)\r\n",meshOff);
        }
        // SWEEP DOWN onto the ground: K2_SetActorLocation((X,Y, spawnZ-8000), bSweep=1, bTeleport=1). A swept move is
        // collision-continuous so it stops ON the terrain surface instead of falling/tunneling through it.
        if(g_slThunk && LooksLikePtr(actor) && g_oSlLoc!=0xFFFFFFFF){
            double* xt=(double*)(g_xform+0x20);   // spawn XYZ
            memset(g_slbuf,0,sizeof(g_slbuf)); memset(g_gsbuf,0,sizeof(g_gsbuf));
            double* NL=(double*)(g_slbuf+g_oSlLoc); NL[0]=xt[0]; NL[1]=xt[1]; NL[2]=xt[2]-8000.0;   // sweep straight down
            if(g_oSlSweep!=0xFFFFFFFF) g_slbuf[g_oSlSweep]=1;   // bSweep=true
            if(g_oSlTele!=0xFFFFFFFF) g_slbuf[g_oSlTele]=1;     // bTeleport=true
            CallNative(g_slFn,g_slThunk,g_slChild,(void*)actor,g_slbuf,g_gsbuf);
            // DIAGNOSTIC: read the hero's ACTUAL location after the sweep. If Z ~= the sweep target (-8000 below),
            // NOTHING stopped it => no collision streamed here (World Partition) or over a void. If Z is sensible,
            // it landed (start spot just below surface). bBlockingHit is the return bool (g_gsbuf[0]).
            uint8_t hitG=g_gsbuf[0]&1;
            if(g_locThunk){ memset(g_slbuf,0,sizeof(g_slbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallNative(g_locFn,g_locThunk,g_locChild,(void*)actor,g_slbuf,g_rbuf);
                double* HL=(double*)g_rbuf; Markerf("[GS] swept: bBlockingHit=%d hero NOW at (%.0f,%.0f,%.0f) [spawned Z=%.0f, sweep target Z=%.0f]\r\n",hitG,HL[0],HL[1],HL[2],xt[2],xt[2]-8000.0); }
        }
        // 4. Possess(pc, actor)
        if(kDoPossess && LooksLikePtr(actor) && g_possessThunk){
            memset(g_gsbuf,0,sizeof(g_gsbuf)); *(uint64_t*)(g_gsbuf+g_offInPawn)=(uint64_t)actor; memset(g_rbuf,0,sizeof(g_rbuf));
            CallNative(g_possessFn,g_possessThunk,g_possessChild,(void*)g_pc2,g_gsbuf,g_rbuf);
            g_spStep=4; Marker("[GS] possess called\r\n");
        }
        // COSMETICS: the hero's visual mesh is attached by the cosmetics system. Investigate state + try to trigger it.
        if(LooksLikePtr(actor)){
            // 1. GetCosmeticsController -> the component that manages the visual mesh
            uintptr_t cc=0; if(g_ccThunk){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallNativeGuarded(g_ccFn,g_ccThunk,g_ccChild,(void*)actor,g_gsbuf,g_rbuf)) cc=(uintptr_t)g_rbuf[0]; }
            char ccn[96]="-"; if(LooksLikePtr(cc)&&ClassOf(cc))GetFNameStr(NameId(ClassOf(cc)),ccn,sizeof(ccn));
            // 2. GetCosmeticsAssetID -> FPrimaryAssetId{Type FName, Name FName} (is a cosmetic set?)
            uint64_t caid[2]={0,0}; if(g_gcaThunk){ memset(g_gsbuf,0,sizeof(g_gsbuf)); uint8_t rb[32]={0}; if(!CallNativeGuarded(g_gcaFn,g_gcaThunk,g_gcaChild,(void*)actor,g_gsbuf,rb)){ caid[0]=*(uint64_t*)rb; caid[1]=*(uint64_t*)(rb+8); } }
            char ctype[96]="-",cname[96]="-"; GetFNameStr((uint32_t)caid[0],ctype,sizeof(ctype)); GetFNameStr((uint32_t)caid[1],cname,sizeof(cname));
            Markerf("[COS] controller=0x%llX(%s) CosmeticsAssetID Type=%s Name=%s (raw %llX,%llX)\r\n",(unsigned long long)cc,ccn,ctype,cname,(unsigned long long)caid[0],(unsigned long long)caid[1]);
            // 3. ★ INJECT: write CosmeticsAssetID = {HeroCosmeticsBundle, RoninDefault} onto the hero's replicated member,
            //    then fire OnRep_CosmeticsAssetID -> BP_PostSetupCosmetics builds the controller + async-loads/attaches the mesh.
            uint32_t caOff=PropOffsetSuper(ClassOf(actor),"CosmeticsAssetID");
            if(caOff!=0xFFFFFFFF && SafeReadable((void*)(actor+caOff),16)){
                uint32_t* pai=(uint32_t*)(actor+caOff);
                pai[0]=kFN_HeroCosmeticsBundle; pai[1]=0; pai[2]=kFN_RoninDefault; pai[3]=0;   // {Type FName, Name FName}
                Markerf("[COS] SET CosmeticsAssetID@0x%X = HeroCosmeticsBundle:RoninDefault\r\n",caOff);
                if(g_oncThunk){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); bool f=CallNativeGuarded(g_oncFn,g_oncThunk,g_oncChild,(void*)actor,g_gsbuf,g_rbuf); Markerf("[COS] OnRep_CosmeticsAssetID called%s\r\n",f?" [FAULTED]":""); }
            } else Markerf("[COS] no CosmeticsAssetID property (off=0x%X) -> can't set\r\n",caOff);
            // 4. RefreshCosmetics + re-read the state (controller/mesh attach may be ASYNC — the model appears over frames)
            if(g_rcThunk){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); bool f=CallNativeGuarded(g_rcFn,g_rcThunk,g_rcChild,(void*)actor,g_gsbuf,g_rbuf); Markerf("[COS] RefreshCosmetics called%s\r\n",f?" [FAULTED]":""); }
            uintptr_t cc2=0; if(g_ccThunk){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallNativeGuarded(g_ccFn,g_ccThunk,g_ccChild,(void*)actor,g_gsbuf,g_rbuf)) cc2=(uintptr_t)g_rbuf[0]; }
            uint32_t mo=PropOffsetSuper(ClassOf(actor),"Mesh"); uintptr_t mc=(mo!=0xFFFFFFFF&&SafeReadable((void*)(actor+mo),8))?*(uintptr_t*)(actor+mo):0;
            Markerf("[COS] after inject: controller=0x%llX base Mesh=0x%llX\r\n",(unsigned long long)cc2,(unsigned long long)mc);
        }
        // CAMERA: point the PC's camera at the hero (off the Z=0 under-map spectator view) so we can actually SEE it.
        if(g_svtThunk && LooksLikePtr(g_pc2) && LooksLikePtr(actor) && g_oSvtTarget!=0xFFFFFFFF){
            memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            *(uint64_t*)(g_gsbuf+g_oSvtTarget)=(uint64_t)actor;   // NewViewTarget = hero; BlendTime=0 (rest of params zero)
            bool f=CallNativeGuarded(g_svtFn,g_svtThunk,g_svtChild,(void*)g_pc2,g_gsbuf,g_rbuf);
            Markerf("[CAM] SetViewTargetWithBlend(hero) called%s\r\n",f?" [FAULTED]":"");
        }
        // LIFT-TO-SEE: the camera follows the hero vertically (jump reveals the map), but sits below the surface. Kill
        // the hero's gravity + teleport it WAY up so the camera rises above the terrain and the model becomes visible.
        if(LooksLikePtr(actor)){
            uint32_t cmOff=PropOffsetSuper(ClassOf(actor),"CharacterMovement");
            if(cmOff!=0xFFFFFFFF && SafeReadable((void*)(actor+cmOff),8)){ uintptr_t cmc=*(uintptr_t*)(actor+cmOff);
                if(LooksLikePtr(cmc)){ uint32_t gsOff=PropOffsetSuper(ClassOf(cmc),"GravityScale"); if(gsOff!=0xFFFFFFFF&&SafeReadable((void*)(cmc+gsOff),4)){ *(float*)(cmc+gsOff)=0.0f; Markerf("[LIFT] gravity OFF (CMC=0x%llX GravityScale@0x%X)\r\n",(unsigned long long)cmc,gsOff); } } }
            uint64_t hl[4]={0}; if(g_locThunk){ memset(g_gsbuf,0,sizeof(g_gsbuf)); CallNative(g_locFn,g_locThunk,g_locChild,(void*)actor,g_gsbuf,hl); }
            double* HL=(double*)hl;
            if((HL[0]||HL[1]||HL[2]) && g_slThunk && g_oSlLoc!=0xFFFFFFFF){
                memset(g_slbuf,0,sizeof(g_slbuf)); memset(g_gsbuf,0,sizeof(g_gsbuf));
                double* NL=(double*)(g_slbuf+g_oSlLoc); NL[0]=HL[0]; NL[1]=HL[1]; NL[2]=HL[2]+1800.0;   // lift 1800 up
                if(g_oSlSweep!=0xFFFFFFFF) g_slbuf[g_oSlSweep]=0; if(g_oSlTele!=0xFFFFFFFF) g_slbuf[g_oSlTele]=1;   // teleport, no sweep
                CallNativeGuarded(g_slFn,g_slThunk,g_slChild,(void*)actor,g_slbuf,g_gsbuf);
                Markerf("[LIFT] hero lifted (%.0f,%.0f,%.0f) -> Z+1800=%.0f\r\n",HL[0],HL[1],HL[2],HL[2]+1800.0);
            }
        }
        return;
    }
    // Force the gamemode's DefaultPawnClass to the hero, so GetDefaultPawnClassForController (which returned null
    // due to no hero-select context) falls back to a real hero pawn instead of nothing.
    if(g_heroClass && SafeReadable((void*)(g_gm2+GM_DEFPAWN_OFF),8)){
        uintptr_t old=*(uintptr_t*)(g_gm2+GM_DEFPAWN_OFF); char ocn[96]="-"; if(LooksLikePtr(old)) GetFNameStr(NameId(old),ocn,sizeof(ocn));
        *(uintptr_t*)(g_gm2+GM_DEFPAWN_OFF)=g_heroClass;
        Markerf("[SP] poked DefaultPawnClass@0x%X: %s -> BP_HERO_Ronin_C\r\n",GM_DEFPAWN_OFF,ocn);
    }
    g_spStep=1; Marker("[SP] >>> calling SpawnDefaultPawnFor\r\n");
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    uint8_t* pb=(uint8_t*)g_pbuf;
    *(uint64_t*)(pb+g_offSpawnNP)=(uint64_t)g_pc2;
    *(uint64_t*)(pb+g_offSpawnSS)=(uint64_t)g_startSpot;
    CallNative(g_spawnFn,g_spawnThunk,g_spawnChild,(void*)g_gm2,g_pbuf,g_rbuf);
    uintptr_t pawn=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(pawn)) pawn=*(uint64_t*)(pb+g_offSpawnRet);
    g_spawnedPawn=pawn; g_spStep=2;
    char pcn[96]="-"; if(LooksLikePtr(pawn)&&ClassOf(pawn)) GetFNameStr(NameId(ClassOf(pawn)),pcn,sizeof(pcn));
    Markerf("[SP] <<< SpawnDefaultPawnFor returned pawn=0x%llX cls=%s\r\n",(unsigned long long)pawn,pcn);
    if(kDoPossess && LooksLikePtr(pawn)){
        Marker("[SP] >>> calling Possess\r\n");
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)((uint8_t*)g_pbuf+g_offInPawn)=(uint64_t)pawn;
        CallNative(g_possessFn,g_possessThunk,g_possessChild,(void*)g_pc2,g_pbuf,g_rbuf);
        g_spStep=3; Marker("[SP] <<< Possess returned\r\n");
    }
}

// ---- S74 Path B: resolve the cheat object accessor + target RPC thunks (off-thread, before hooking) ----
// Thunks are CLASS-level: resolve them off the native LokiPlayerCheats CDO's class (works even though the live
// object is a BP subclass Comp_PlayerController_Cheats_C). The live `this` comes from GetLocalLokiPlayerCheatsBP
// at call time — more robust than a class-name instance scan (the BP subclass name doesn't contain "LokiPlayerCheats").
static void ResolveCheatSpawn(){
    g_cheatCDO=FindObjExact("Default__LokiPlayerCheats");
    uintptr_t cheatCls = g_cheatCDO ? ClassOf(g_cheatCDO) : 0;
    if(!LooksLikePtr(cheatCls)){ Marker("[CS] no Default__LokiPlayerCheats CDO/class (is the tutorial running?) -> abort\r\n"); return; }
    // GetLocalLokiPlayerCheatsBP (Static): context=CDO, param WorldContextObject -> ReturnValue (the local cheat obj).
    ResolveFuncNative(cheatCls,"GetLocalLokiPlayerCheatsBP",&g_glcFn,&g_glcThunk,&g_glcChild);
    if(g_glcChild){ g_oGlcWCO=ParamOffset(g_glcChild,"WorldContextObject"); g_oGlcRet=ParamOffset(g_glcChild,"ReturnValue"); }
    // ServerCheatChangeHero(Class HeroClass) — the purpose-built hero spawn/swap RPC.
    ResolveFuncNative(cheatCls,"ServerCheatChangeHero",&g_schFn,&g_schThunk,&g_schChild);
    if(g_schChild){ g_oSchClass=ParamOffset(g_schChild,"HeroClass"); }
    // CheatChangeHero(FString HeroName) — Exec alt target (name-based).
    ResolveFuncNative(cheatCls,"CheatChangeHero",&g_cchFn,&g_cchThunk,&g_cchChild);
    if(g_cchChild){ g_oCchName=ParamOffset(g_cchChild,"HeroName"); }
    g_cheatHeroClass=FindObjExact(kCheatHeroClassName);
    // WorldContext for the static accessor: prefer the live local PC (valid GetWorld + owning player), else progMgr.
    uintptr_t pc=FindInstByClass("LokiPlayerController_Dev",nullptr); if(!pc)pc=FindInstByClass("LokiPlayerController",nullptr);
    g_csWorldCtx = pc ? pc : g_worldCtx; g_cheatPC = pc;
    // AuthCheatChangeCharacter(Class CharacterClass) — a cheat method ON the PC (no LokiPlayerCheats obj needed).
    if(pc){ ResolveFuncNative(ClassOf(pc),"AuthCheatChangeCharacter",&g_accFn,&g_accThunk,&g_accChild); if(g_accChild) g_oAccClass=ParamOffset(g_accChild,"CharacterClass"); }
    if(pc){ ResolveFuncNative(ClassOf(pc),"SwitchToPlayingState",&g_spsFn,&g_spsThunk,&g_spsChild); ResolveFuncNative(ClassOf(pc),"FinishDropPhaseHiding",&g_fdphFn,&g_fdphThunk,&g_fdphChild); ResolveFuncNative(ClassOf(pc),"IsSpectating",&g_isSpecFn,&g_isSpecThunk,&g_isSpecChild);
        Markerf("[CS] switchPlayingThunk=0x%llX finishDropThunk=0x%llX pcStateByte@0x%X=%d\r\n",(unsigned long long)g_spsThunk,(unsigned long long)g_fdphThunk,PC_STATEBYTE_OFF, (pc&&SafeReadable((void*)(pc+PC_STATEBYTE_OFF),1))?*(uint8_t*)(pc+PC_STATEBYTE_OFF):-1); }
    if(kCheatTarget==CT_SPAWNACTOR){
        ResolveFuncNative(cheatCls,"ServerCheatSpawnActor",&g_scsaFn,&g_scsaThunk,&g_scsaChild);
        if(g_scsaChild){ g_oScsaClass=ParamOffset(g_scsaChild,"ClassToSpawn"); g_oScsaLoc=ParamOffset(g_scsaChild,"Location"); }
        g_gm2=FindInstByClass("GameMode_Tutorial",nullptr);
        g_startSpot=FindInstByClass("LokiPlayerStart","UAID"); if(!g_startSpot)g_startSpot=FindInstByClass("CapturePoint_Tutorial","UAID"); if(!g_startSpot)g_startSpot=FindInstByClass("LokiRespawnBeacon_Tutorial","UAID");
        g_cheatObjClass=cheatCls;  // native LokiPlayerCheats (an Actor) — Comp_PlayerController_Cheats_C is a COMPONENT, not spawnable via SpawnActor
        g_gsCDO=FindObjExact("Default__GameplayStatics");
        if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
            ResolveFuncOnClass(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
            ResolveFuncOnClass(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
            uint32_t o;
            if(g_beginChild){ o=ParamOffset(g_beginChild,"WorldContextObject");if(o!=0xFFFFFFFF)g_oBWorld=o; o=ParamOffset(g_beginChild,"ActorClass");if(o!=0xFFFFFFFF)g_oBClass=o; o=ParamOffset(g_beginChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oBXform=o; o=ParamOffset(g_beginChild,"CollisionHandlingOverride");if(o!=0xFFFFFFFF)g_oBColl=o; o=ParamOffset(g_beginChild,"Owner");if(o!=0xFFFFFFFF)g_oBOwner=o; o=ParamOffset(g_beginChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oBRet=o; }
            if(g_finishChild){ o=ParamOffset(g_finishChild,"Actor");if(o!=0xFFFFFFFF)g_oFActor=o; o=ParamOffset(g_finishChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oFXform=o; o=ParamOffset(g_finishChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oFRet=o; }
        }
        if(g_startSpot){ ResolveFuncSuper(ClassOf(g_startSpot),"K2_GetActorLocation",&g_locFn,&g_locThunk,&g_locChild); }
        ResolveFuncNative(cheatCls,"EnableHotkeyCheats",&g_ehcFn,&g_ehcThunk,&g_ehcChild); if(g_ehcChild) g_oEhcEnabled=ParamOffset(g_ehcChild,"Enabled");
        ResolveFuncNative(cheatCls,"AreHotkeyCheatsEnabled",&g_ahceFn,&g_ahceThunk,&g_ahceChild);
        if(pc) g_pcCheatOff=PropOffsetSuper(ClassOf(pc),"LokiPlayerCheats");
        Markerf("[CS] SPAWNACTOR: scsaThunk=0x%llX(class@0x%X loc@0x%X) cheatObjClass=0x%llX gm=0x%llX startSpot=0x%llX beginThunk=0x%llX finishThunk=0x%llX locThunk=0x%llX pcCheatOff=0x%X\r\n",
            (unsigned long long)g_scsaThunk,g_oScsaClass,g_oScsaLoc,(unsigned long long)g_cheatObjClass,(unsigned long long)g_gm2,(unsigned long long)g_startSpot,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_locThunk,g_pcCheatOff);
    }
    Markerf("[CS] cheatCDO=0x%llX cls=0x%llX getLocalThunk=0x%llX(WCO@0x%X ret@0x%X) schThunk=0x%llX(HeroClass@0x%X) cchThunk=0x%llX(HeroName@0x%X)\r\n",
        (unsigned long long)g_cheatCDO,(unsigned long long)cheatCls,(unsigned long long)g_glcThunk,g_oGlcWCO,g_oGlcRet,(unsigned long long)g_schThunk,g_oSchClass,(unsigned long long)g_cchThunk,g_oCchName);
    Markerf("[CS] heroClass(%s)=0x%llX worldCtx=0x%llX (pc=0x%llX) authChangeCharThunk=0x%llX(CharacterClass@0x%X)\r\n",kCheatHeroClassName,(unsigned long long)g_cheatHeroClass,(unsigned long long)g_csWorldCtx,(unsigned long long)pc,(unsigned long long)g_accThunk,g_oAccClass);
}
// Runs on the GAME THREAD (from OnPI): get the local cheat obj via GetLocalLokiPlayerCheatsBP, then fire the target cheat.
static void DoCheatSpawn(){
    // CT_AUTHCHANGECHAR: call AuthCheatChangeCharacter(HeroClass) directly on the live PC — no cheat obj needed.
    if(kCheatTarget==CT_AUTHCHANGECHAR){
        if(!g_accThunk||!LooksLikePtr(g_cheatPC)||!LooksLikePtr(g_cheatHeroClass)){ Markerf("[CS] AuthChangeChar missing accThunk=0x%llX pc=0x%llX heroClass=0x%llX -> abort\r\n",(unsigned long long)g_accThunk,(unsigned long long)g_cheatPC,(unsigned long long)g_cheatHeroClass); g_done=1; return; }
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_oAccClass!=0xFFFFFFFF) *(uint64_t*)((uint8_t*)g_pbuf+g_oAccClass)=(uint64_t)g_cheatHeroClass;
        Markerf("[CS] calling AuthCheatChangeCharacter(%s) on PC 0x%llX...\r\n",kCheatHeroClassName,(unsigned long long)g_cheatPC);
        bool f=CallNativeGuarded(g_accFn,g_accThunk,g_accChild,(void*)g_cheatPC,g_pbuf,g_rbuf);
        Markerf("[CS] AuthCheatChangeCharacter returned%s\r\n",f?" [FAULTED — null captured]":"");
        g_done=1; return;
    }
    // CT_SWITCHPLAYING (S74 RE): drive the PC state machine spectator->playing via SwitchToPlayingState() + set the
    // drop-reveal flag. The decisive test: does forcing the playing state engage hero control (or need a hero pawn first)?
    if(kCheatTarget==CT_SWITCHPLAYING){
        if(!g_spsThunk||!LooksLikePtr(g_cheatPC)){ Markerf("[CS] SWITCHPLAYING missing spsThunk=0x%llX pc=0x%llX -> abort\r\n",(unsigned long long)g_spsThunk,(unsigned long long)g_cheatPC); g_done=1; return; }
        auto readSpec=[&]()->int{ if(!g_isSpecThunk)return -1; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallNativeGuarded(g_isSpecFn,g_isSpecThunk,g_isSpecChild,(void*)g_cheatPC,g_pbuf,g_rbuf))return -2; return (int)(g_rbuf[0]&0xFF); };
        uint64_t so0=SafeReadable((void*)(g_cheatPC+PC_STATEOBJ_OFF),8)?*(uint64_t*)(g_cheatPC+PC_STATEOBJ_OFF):0;
        Markerf("[CS] BEFORE: IsSpectating=%d stateByte@0x160=%d stateObj@0x3F0=0x%llX; calling SwitchToPlayingState()...\r\n",readSpec(),SafeReadable((void*)(g_cheatPC+PC_STATEBYTE_OFF),1)?*(uint8_t*)(g_cheatPC+PC_STATEBYTE_OFF):-1,(unsigned long long)so0);
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        bool f=CallNativeGuarded(g_spsFn,g_spsThunk,g_spsChild,(void*)g_cheatPC,g_pbuf,g_rbuf);
        uint64_t so1=SafeReadable((void*)(g_cheatPC+PC_STATEOBJ_OFF),8)?*(uint64_t*)(g_cheatPC+PC_STATEOBJ_OFF):0;
        Markerf("[CS] SwitchToPlayingState returned%s; AFTER: IsSpectating=%d stateByte@0x160=%d stateObj@0x3F0=0x%llX\r\n",f?" [FAULTED]":"",readSpec(),SafeReadable((void*)(g_cheatPC+PC_STATEBYTE_OFF),1)?*(uint8_t*)(g_cheatPC+PC_STATEBYTE_OFF):-1,(unsigned long long)so1);
        // set the drop-reveal flag (FinishDropPhaseHiding = PC+0xF28=1) so the drop-hide doesn't keep the view hidden
        if(g_fdphThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallNativeGuarded(g_fdphFn,g_fdphThunk,g_fdphChild,(void*)g_cheatPC,g_pbuf,g_rbuf); Markerf("[CS] FinishDropPhaseHiding called; PC+0xF28=%d\r\n",SafeReadable((void*)(g_cheatPC+PC_DROPFLAG_OFF),1)?*(uint8_t*)(g_cheatPC+PC_DROPFLAG_OFF):-1); }
        g_done=1; return;
    }
    // CT_SPAWNACTOR: spawn a LokiPlayerCheats actor ourselves, wire it to the PC, then ServerCheatSpawnActor on it.
    if(kCheatTarget==CT_SPAWNACTOR){
        if(!g_beginThunk||!g_finishThunk||!LooksLikePtr(g_cheatObjClass)||!g_scsaThunk){ Markerf("[CS] SPAWNACTOR missing beginThunk=0x%llX finishThunk=0x%llX cheatObjClass=0x%llX scsaThunk=0x%llX -> abort\r\n",(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_cheatObjClass,(unsigned long long)g_scsaThunk); g_done=1; return; }
        uintptr_t wctx = LooksLikePtr(g_gm2) ? g_gm2 : g_cheatPC;
        uint32_t xfsz=(g_oBColl>g_oBXform)?(g_oBColl-g_oBXform):0x60; if(xfsz>sizeof(g_xform))xfsz=sizeof(g_xform);
        // 1. spawn transform: identity rotation (quat W=1 @ +0x18) + real translation from K2_GetActorLocation(startSpot).
        //    Origin (0,0,0) is the void -> hero spawn gets rejected/falls out; use the start spot's world location.
        memset(g_xform,0,sizeof(g_xform)); *(double*)(g_xform+0x18)=1.0;
        if(g_locThunk && LooksLikePtr(g_startSpot)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallNative(g_locFn,g_locThunk,g_locChild,(void*)g_startSpot,g_pbuf,g_rbuf);
            double* L=(double*)g_rbuf; *(double*)(g_xform+0x20)=L[0]; *(double*)(g_xform+0x28)=L[1]; *(double*)(g_xform+0x30)=L[2]; }
        double* t=(double*)(g_xform+0x20); Markerf("[CS] spawnLoc=(%.0f,%.0f,%.0f)\r\n",t[0],t[1],t[2]);
        // 2. BeginDeferredActorSpawnFromClass(wctx, cheatObjClass, xform, AlwaysSpawn, Owner=PC) -> deferred cheat obj
        memset(g_gsbuf,0,sizeof(g_gsbuf));
        *(uint64_t*)(g_gsbuf+g_oBWorld)=(uint64_t)wctx;
        *(uint64_t*)(g_gsbuf+g_oBClass)=(uint64_t)g_cheatObjClass;
        memcpy(g_gsbuf+g_oBXform,g_xform,xfsz);
        g_gsbuf[g_oBColl]=2;   // AdjustIfPossibleButAlwaysSpawn
        if(g_oBOwner!=0xFFFFFFFF && LooksLikePtr(g_cheatPC)) *(uint64_t*)(g_gsbuf+g_oBOwner)=(uint64_t)g_cheatPC;
        memset(g_rbuf,0,sizeof(g_rbuf));
        Marker("[CS] spawning cheat object (BeginDeferred)...\r\n");
        if(CallNativeGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_gsbuf,g_rbuf)){ Marker("[CS] BeginDeferred FAULTED\r\n"); g_done=1; return; }
        uintptr_t deferred=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(deferred)) deferred=*(uint64_t*)(g_gsbuf+g_oBRet);
        char dcn[96]="-"; if(LooksLikePtr(deferred)&&ClassOf(deferred))GetFNameStr(NameId(ClassOf(deferred)),dcn,sizeof(dcn));
        Markerf("[CS] deferred cheatObj=0x%llX cls=%s\r\n",(unsigned long long)deferred,dcn);
        if(!LooksLikePtr(deferred)){ g_done=1; return; }
        // 3. FinishSpawningActor(deferred, xform) -> cheat obj (runs BeginPlay/init)
        memset(g_gsbuf,0,sizeof(g_gsbuf)); *(uint64_t*)(g_gsbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_gsbuf+g_oFXform,g_xform,xfsz); memset(g_rbuf,0,sizeof(g_rbuf));
        Marker("[CS] FinishSpawningActor(cheatObj)...\r\n");
        if(CallNativeGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_gsbuf,g_rbuf)){ Marker("[CS] FinishSpawning FAULTED\r\n"); g_done=1; return; }
        uintptr_t cheatObj=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(cheatObj)) cheatObj=*(uint64_t*)(g_gsbuf+g_oFRet); if(!LooksLikePtr(cheatObj)) cheatObj=deferred;
        g_cheatObj=cheatObj; Markerf("[CS] spawned cheatObj=0x%llX\r\n",(unsigned long long)cheatObj);
        // 4. wire the spawned obj into the PC's LokiPlayerCheats member (so GetPlayerCheats resolves it)
        if(g_pcCheatOff!=0xFFFFFFFF && LooksLikePtr(g_cheatPC) && SafeReadable((void*)(g_cheatPC+g_pcCheatOff),8)){ *(uint64_t*)(g_cheatPC+g_pcCheatOff)=(uint64_t)cheatObj; Markerf("[CS] wired PC(0x%llX)->LokiPlayerCheats@0x%X = cheatObj\r\n",(unsigned long long)g_cheatPC,g_pcCheatOff); }
        // 4b. EnableHotkeyCheats(1) on the object — ServerCheatSpawnActor likely gates on a cheat-enabled flag.
        if(g_ehcThunk){
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            if(g_oEhcEnabled!=0xFFFFFFFF) *(double*)((uint8_t*)g_pbuf+g_oEhcEnabled)=1.0;
            Marker("[CS] EnableHotkeyCheats(1)...\r\n");
            bool ef=CallNativeGuarded(g_ehcFn,g_ehcThunk,g_ehcChild,(void*)cheatObj,g_pbuf,g_rbuf);
            Markerf("[CS] EnableHotkeyCheats returned%s\r\n",ef?" [FAULTED]":"");
        }
        if(g_ahceThunk){
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            CallNativeGuarded(g_ahceFn,g_ahceThunk,g_ahceChild,(void*)cheatObj,g_pbuf,g_rbuf);
            Markerf("[CS] AreHotkeyCheatsEnabled -> %llu\r\n",(unsigned long long)(g_rbuf[0]&0xFF));
        }
        // 5. ServerCheatSpawnActor(cheatObj, {HeroClass, location})
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_oScsaClass!=0xFFFFFFFF) *(uint64_t*)((uint8_t*)g_pbuf+g_oScsaClass)=(uint64_t)g_cheatHeroClass;
        if(g_oScsaLoc!=0xFFFFFFFF){ double* L=(double*)((uint8_t*)g_pbuf+g_oScsaLoc); L[0]=t[0]; L[1]=t[1]; L[2]=t[2]; }
        Markerf("[CS] calling ServerCheatSpawnActor(%s, loc=(%.0f,%.0f,%.0f)) on cheatObj 0x%llX...\r\n",kCheatHeroClassName,t[0],t[1],t[2],(unsigned long long)cheatObj);
        bool f=CallNativeGuarded(g_scsaFn,g_scsaThunk,g_scsaChild,(void*)cheatObj,g_pbuf,g_rbuf);
        Markerf("[CS] ServerCheatSpawnActor returned%s\r\n",f?" [FAULTED — null captured]":"");
        g_done=1; return;
    }
    // 1. Resolve the live cheat object (this-pointer for the RPC).
    if(!LooksLikePtr(g_cheatObj) && g_glcThunk){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_oGlcWCO!=0xFFFFFFFF) *(uint64_t*)((uint8_t*)g_pbuf+g_oGlcWCO)=(uint64_t)g_csWorldCtx;
        Marker("[CS] calling GetLocalLokiPlayerCheatsBP...\r\n");
        if(CallNativeGuarded(g_glcFn,g_glcThunk,g_glcChild,(void*)g_cheatCDO,g_pbuf,g_rbuf)){ Marker("[CS] GetLocal FAULTED (null captured)\r\n"); g_done=1; return; }
        uintptr_t obj=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(obj)&&g_oGlcRet!=0xFFFFFFFF) obj=*(uint64_t*)((uint8_t*)g_pbuf+g_oGlcRet);
        g_cheatObj=obj;
        char cn[96]="-"; if(LooksLikePtr(g_cheatObj)&&ClassOf(g_cheatObj)) GetFNameStr(NameId(ClassOf(g_cheatObj)),cn,sizeof(cn));
        Markerf("[CS] GetLocal -> cheatObj=0x%llX cls=%s\r\n",(unsigned long long)g_cheatObj,cn);
    }
    if(!LooksLikePtr(g_cheatObj)){ Marker("[CS] no cheat object -> abort\r\n"); g_done=1; return; }
    // 2. Fire the selected cheat on the cheat object.
    if(kCheatTarget==CT_SERVERCHANGEHERO){
        if(!g_schThunk||!LooksLikePtr(g_cheatHeroClass)){ Markerf("[CS] missing schThunk=0x%llX heroClass=0x%llX -> abort\r\n",(unsigned long long)g_schThunk,(unsigned long long)g_cheatHeroClass); g_done=1; return; }
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_oSchClass!=0xFFFFFFFF) *(uint64_t*)((uint8_t*)g_pbuf+g_oSchClass)=(uint64_t)g_cheatHeroClass;
        Markerf("[CS] calling ServerCheatChangeHero(%s)...\r\n",kCheatHeroClassName);
        bool f=CallNativeGuarded(g_schFn,g_schThunk,g_schChild,(void*)g_cheatObj,g_pbuf,g_rbuf);
        Markerf("[CS] ServerCheatChangeHero returned%s\r\n",f?" [FAULTED — null captured]":"");
    } else if(kCheatTarget==CT_CHANGEHERONAME){
        if(!g_cchThunk){ Marker("[CS] missing CheatChangeHero thunk -> abort\r\n"); g_done=1; return; }
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_oCchName!=0xFFFFFFFF) SetFStringAt((uint8_t*)g_pbuf,g_oCchName,kCheatHeroName);
        Markerf("[CS] calling CheatChangeHero('%ls')...\r\n",kCheatHeroName);
        bool f=CallNativeGuarded(g_cchFn,g_cchThunk,g_cchChild,(void*)g_cheatObj,g_pbuf,g_rbuf);
        Markerf("[CS] CheatChangeHero returned%s\r\n",f?" [FAULTED — null captured]":"");
    }
    g_done=1;
}

static void Resolve(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t progMgr=0, kslCDO=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            if(!progMgr && ClassNameIs(obj,"ProgressionManager")){ char nm[96]; if(GetFNameStr(NameId(obj),nm,sizeof(nm))&&strncmp(nm,"Default__",9)!=0) progMgr=obj; }
            if(!kslCDO && NameIs(obj,"Default__KismetSystemLibrary")) kslCDO=obj;
            if(progMgr&&kslCDO)break;
        } if(progMgr&&kslCDO)break; }
    if(progMgr) g_worldCtx=progMgr;
    if(kslCDO){ g_kslCDO=kslCDO; uintptr_t cls=ClassOf(kslCDO); if(cls){ ResolveFuncOnClass(cls,"ExecuteConsoleCommand",&g_ecc,&g_eccThunk,&g_eccChild);
        if(g_eccChild){ g_offWCO=ParamOffset(g_eccChild,"WorldContextObject"); g_offCmd=ParamOffset(g_eccChild,"Command"); g_offSP=ParamOffset(g_eccChild,"SpecificPlayer"); } } }
}

// Walk the live object array during travel: find the tutorial GameMode INSTANCE + dump its config classes
// (GameMode member offsets from gm_config.py: GameStateClass@+0x3D0, PlayerControllerClass@+0x3D8,
// PlayerStateClass@+0x3E0), and count live PlayerController/PlayerState instances. Tells us why the PC ends up
// without a PlayerState.
static void DumpTutorialState(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; int nPC=0,nPS=0,nGM=0; uintptr_t gmInst=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
            if(strstr(cn,"PlayerController")) nPC++;
            if(strstr(cn,"PlayerState")) nPS++;
            if(strstr(cn,"GameMode_Tutorial")){ nGM++; if(!gmInst) gmInst=obj; }
        }
    }
    char psN[96]="-",gsN[96]="-",pcN[96]="-";
    if(gmInst){
        uintptr_t gs=SafeReadable((void*)(gmInst+0x3D0),8)?*(uintptr_t*)(gmInst+0x3D0):0;
        uintptr_t pc=SafeReadable((void*)(gmInst+0x3D8),8)?*(uintptr_t*)(gmInst+0x3D8):0;
        uintptr_t ps=SafeReadable((void*)(gmInst+0x3E0),8)?*(uintptr_t*)(gmInst+0x3E0):0;
        if(ps)GetFNameStr(NameId(ps),psN,sizeof(psN)); else strcpy(psN,"NULL");
        if(gs)GetFNameStr(NameId(gs),gsN,sizeof(gsN)); else strcpy(gsN,"NULL");
        if(pc)GetFNameStr(NameId(pc),pcN,sizeof(pcN)); else strcpy(pcN,"NULL");
    }
    Markerf("[DIAG%d] gmInst=0x%llX(n=%d) PSClass=%s GSClass=%s PCClass=%s livePC=%d livePS=%d\r\n",
        tag,(unsigned long long)gmInst,nGM,psN,gsN,pcN,nPC,nPS);
}

// S64/S65 DETERMINATION PROBE: find the live CoreGameManager (persists from the menu) and dump its match/model/
// session/server props + their live object pointers. The revert is a RAW Browse-to-lobby = the front-end FLOW
// MANAGER browsing home; if CoreGameManager's match model is NULL during the tutorial, the flow manager has no
// valid match -> PATH 1 (populate the model via the primitive) is the fix, and this dumps the field OFFSET needed
// to do it. Also dumps the match model's bIsValid/MatchState if non-null.
static void DumpCoreGameState(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t cgm=0; char cgmCls[96]="-";
    for(int ci=0;ci<numChunks && !cgm;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"CoreGameManager")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0){ cgm=obj; strncpy(cgmCls,cn,sizeof(cgmCls)-1); break; } }
        }
    }
    if(!cgm){ Markerf("[CGM%d] no live CoreGameManager instance\r\n",tag); return; }
    Markerf("[CGM%d] inst=0x%llX cls=%s\r\n",tag,(unsigned long long)cgm,cgmCls);
    uintptr_t mm=0;
    uintptr_t cls=ClassOf(cgm); int guard=0;
    while(LooksLikePtr(cls) && guard++<12){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f) && i++<500){
            char pn[96];
            if(GetFNameStr(NameId(f),pn,sizeof(pn)) && (strstr(pn,"Match")||strstr(pn,"Model")||strstr(pn,"Server")||strstr(pn,"Session")||strstr(pn,"Platform"))){
                uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                uintptr_t val=(off!=0xFFFFFFFF&&SafeReadable((void*)(cgm+off),8))?*(uintptr_t*)(cgm+off):0;
                char vcls[96]="null"; if(LooksLikePtr(val)&&ClassOf(val)) GetFNameStr(NameId(ClassOf(val)),vcls,sizeof(vcls));
                Markerf("[CGM%d]   %s @0x%X = 0x%llX (%s)\r\n",tag,pn,off,(unsigned long long)val,vcls);
                if(strcmp(pn,"CoreGameMatchModel")==0) mm=val;
            }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;   // UStruct::SuperStruct
    }
    // Dump the match model's own state props (bIsValid / MatchState / TeamSize / MatchInfo etc.) to see if the
    // flow manager considers the match INVALID -> the likely revert trigger (PATH 1 = force valid + InProgress).
    if(LooksLikePtr(mm)){
        uintptr_t mcls=ClassOf(mm); int g2=0;
        while(LooksLikePtr(mcls) && g2++<12){
            uintptr_t f=SafeReadable((void*)(mcls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(mcls+UFUNC_CHILDPROPS):0; int i=0;
            while(LooksLikePtr(f) && i++<500){
                char pn[96];
                if(GetFNameStr(NameId(f),pn,sizeof(pn)) && (strstr(pn,"Valid")||strstr(pn,"State")||strstr(pn,"Team")||strstr(pn,"Match")||strstr(pn,"Info")||strstr(pn,"Self"))){
                    uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                    uint32_t v4=(off!=0xFFFFFFFF&&SafeReadable((void*)(mm+off),4))?*(uint32_t*)(mm+off):0;
                    uintptr_t pv=(off!=0xFFFFFFFF&&SafeReadable((void*)(mm+off),8))?*(uintptr_t*)(mm+off):0;
                    char vcls[64]="-"; if(LooksLikePtr(pv)&&ClassOf(pv)) GetFNameStr(NameId(ClassOf(pv)),vcls,sizeof(vcls));
                    Markerf("[MM%d]   %s @0x%X u32=%u ptr=0x%llX(%s)\r\n",tag,pn,off,v4,(unsigned long long)pv,vcls);
                }
                f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0;
            }
            mcls=SafeReadable((void*)(mcls+0x48),8)?*(uintptr_t*)(mcls+0x48):0;
        }
    }
}

// S65 PATH-1 EXPERIMENT: the CoreGameMatchModel exists but bIsValid=0 / MatchState=0 during the force-open
// tutorial (no valid match) -> the front-end flow manager browses home. Continuously poke bIsValid=1 +
// MatchState=5 (InProgress) on CoreGameManager.CoreGameMatchModel across the tutorial to test whether keeping
// the model "valid + in-progress" stops the revert. Offsets from the S65 DumpCoreGameState dump.
constexpr uint32_t CGM_MM_OFF=0x6E0;      // CoreGameManager.CoreGameMatchModel
constexpr uint32_t MM_VALID_OFF=0x30;     // CoreGameMatchModel.bIsValid (bool)
constexpr uint32_t MM_STATE_OFF=0x48;     // CoreGameMatchModel.MatchState (enum: InProgress=5)
// S65: poking bIsValid (with or without MatchState=InProgress) crashes tutorial init ~2s after world-up (the
// init takes the "valid match" branch and derefs the INCOMPLETE model / null MatchInfo). So the durable default
// is FALSE (diagnostic sampling only, no crash-inducing poke). PATH 1 requires building a COMPLETE valid model.
static const bool kPokeMatchModel = false;
// S65 PATH-1: dump CoreGameManager/CoreGameMatchModel FUNCTIONS + model state at the MENU, then SKIP force-open
// (game stays alive) — to find a native setter/factory that populates the model consistently (missions-style),
// instead of hand-writing the 19-field MatchInfo. Set false for a normal force-open run.
static const bool kInvestigateOnly = false;   // S68: run the spawn+possess branch (kRunMode)
static uintptr_t g_cgm = 0;
static uintptr_t FindCoreGameManager(){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"CoreGameManager")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0) return obj; } } }
    return 0;
}
static void DumpClassFuncs(int tag, const char* label, uintptr_t cls);   // fwd decl (defined below)
// S68: find live (non-CDO) placed actors usable as a SpawnDefaultPawnFor StartSpot (a valid map location).
static void DumpStartSpots(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; int shown=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"CapturePoint")||strstr(cn,"RespawnBeacon")||strstr(cn,"PlayerStart")||strstr(cn,"LandingPad")||strstr(cn,"DropPod")||strstr(cn,"SpawnPoint")||strstr(cn,"StartSpot")||strstr(cn,"DropPlane")){
                char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
                if(shown++<24) Markerf("[SPOT%d] 0x%llX cls=%s name=%s\r\n",tag,(unsigned long long)obj,cn,on);
            } } }
    Markerf("[SPOT%d] total live startspot-ish actors=%d\r\n",tag,shown);
}
static void DumpParams(int tag, const char* label, uintptr_t cls, const char* fname);   // fwd decl (S67)
// S66: find the ULokiGameFeatureToggles subsystem + dump its props (a bReady/bInitialized flag + a toggle
// container) and functions, so we can make it "ready". Prefer a live instance; fall back to the CDO.
static void DumpFeatureToggles(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    uintptr_t ft=0, ftDef=0; char ftCls[96]="-";
    for(int ci=0;ci<numChunks && !ft;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"FeatureToggles")&&!strstr(cn,"ActivationMethod")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
                if(strncmp(on,"Default__",9)==0){ if(!ftDef){ftDef=obj; strncpy(ftCls,cn,sizeof(ftCls)-1);} } else { ft=obj; strncpy(ftCls,cn,sizeof(ftCls)-1); break; } } } }
    uintptr_t use = ft?ft:ftDef;
    if(!use){ Markerf("[FT%d] no LokiGameFeatureToggles object found\r\n",tag); return; }
    Markerf("[FT%d] %s=0x%llX cls=%s\r\n",tag, ft?"inst":"CDO", (unsigned long long)use, ftCls);
    uintptr_t cls=ClassOf(use); int guard=0, shown=0;
    while(LooksLikePtr(cls) && guard++<10){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f) && i++<400 && shown<50){
            char pn[96]; if(GetFNameStr(NameId(f),pn,sizeof(pn))){
                uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                uint32_t v4=(off!=0xFFFFFFFF&&SafeReadable((void*)(use+off),4))?*(uint32_t*)(use+off):0;
                uintptr_t pv=(off!=0xFFFFFFFF&&SafeReadable((void*)(use+off),8))?*(uintptr_t*)(use+off):0;
                Markerf("[FT%d]   %s @0x%X u32=%u ptr=0x%llX\r\n",tag,pn,off,v4,(unsigned long long)pv); shown++;
            }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
    DumpClassFuncs(tag,"FeatureToggles",ClassOf(use));
}

// S66: find the live tutorial gamemode instance and dump its (and its ALokiRoundGameMode/ALokiGameMode supers')
// UFunctions — looking for a phase-advance / drop-in / deploy / start trigger callable via the PI primitive.
static void DumpGameModeFuncs(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t gm=0;
    for(int ci=0;ci<numChunks && !gm;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"GameMode_Tutorial")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0){ gm=obj; break; } } } }
    if(!gm){ Markerf("[GMFN%d] no live tutorial gamemode instance\r\n",tag); return; }
    Markerf("[GMFN%d] gm=0x%llX\r\n",tag,(unsigned long long)gm);
    DumpClassFuncs(tag,"TutorialGameMode",ClassOf(gm));
    DumpParams(tag,"GM",ClassOf(gm),"SpawnDefaultPawnFor");
    DumpParams(tag,"GM",ClassOf(gm),"SpawnDefaultPawnAtTransform");
    DumpParams(tag,"GM",ClassOf(gm),"K2_OnRestartPlayer");
}

// S67: find the live local PlayerController + dump its UFunctions (looking for Possess / spawn / deploy entry
// points) and the params of the key spawn/possess functions, to build the LEAD-B native spawn+possess call.
static void DumpParams(int tag, const char* label, uintptr_t cls, const char* fname){
    // walk cls (+supers) Children for the named UFunction, then dump its param FFields (name@+0x20, offset@+0x44).
    int g=0;
    while(LooksLikePtr(cls) && g++<10){
        uintptr_t f=SafeReadable((void*)(cls+0x50),8)?*(uintptr_t*)(cls+0x50):0; int i=0;
        while(LooksLikePtr(f) && i++<1000){
            if(NameIs(f,fname)){
                Markerf("[PARM%d] %s::%s params:\r\n",tag,label,fname);
                uintptr_t p=SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(f+UFUNC_CHILDPROPS):0; int k=0;
                while(LooksLikePtr(p) && k++<20){
                    char pn[96]; if(GetFNameStr(NameId(p),pn,sizeof(pn))){
                        uint32_t off=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
                        Markerf("[PARM%d]   %s @0x%X\r\n",tag,pn,off);
                    }
                    p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0;
                }
                return;
            }
            f=SafeReadable((void*)(f+0x30),8)?*(uintptr_t*)(f+0x30):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
    Markerf("[PARM%d] %s::%s NOT FOUND\r\n",tag,label,fname);
}
static void DumpPCFuncs(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t pc=0;
    for(int ci=0;ci<numChunks && !pc;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"LokiPlayerController_Dev")){ char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)!=0){ pc=obj; break; } } } }
    if(!pc){ Markerf("[PCFN%d] no live BP_LokiPlayerController_Dev instance\r\n",tag); return; }
    Markerf("[PCFN%d] pc=0x%llX\r\n",tag,(unsigned long long)pc);
    // SuperStruct-offset diagnostic: which of +0x40/+0x48 points at the parent UClass (ALokiPlayerController)?
    { uintptr_t c=ClassOf(pc); for(uint32_t so=0x38; so<=0x50; so+=8){ uintptr_t sup=SafeReadable((void*)(c+so),8)?*(uintptr_t*)(c+so):0; char sn[96]="?"; if(LooksLikePtr(sup)&&SafeReadable((void*)(sup+NAME_OFF),4)) GetFNameStr(NameId(sup),sn,sizeof(sn)); Markerf("[SUP%d] cls+0x%X=0x%llX (%s)\r\n",tag,so,(unsigned long long)sup,sn); } }
    DumpClassFuncs(tag,"LokiPC",ClassOf(pc));
    DumpParams(tag,"LokiPC",ClassOf(pc),"Possess");
    DumpParams(tag,"LokiPC",ClassOf(pc),"K2_Possess");
}

// Census of live (non-CDO) pawn/hero/drop actors — tells us whether a controllable hero dropped in.
static void DumpPawns(int tag){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    int shown=0;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            // A LokiCharacterMovementComponent's Outer IS the owning hero pawn — dump the Outer's class+name
            // (that's the pawn class to possess). Also dump its Outer's Outer (world/level) for context.
            if(strstr(cn,"LokiCharacterMovementComponent")){
                char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
                uintptr_t owner=SafeReadable((void*)(obj+0x28),8)?*(uintptr_t*)(obj+0x28):0;   // UObject::Outer
                if(!LooksLikePtr(owner))continue;
                char ocn[128]="?", oon[128]="?"; if(ClassOf(owner)) GetFNameStr(NameId(ClassOf(owner)),ocn,sizeof(ocn)); GetFNameStr(NameId(owner),oon,sizeof(oon));
                if(strncmp(oon,"Default__",9)==0)continue;   // skip CDO subobjects — LIVE instances only
                if(shown++<20) Markerf("[PAWN%d] LIVE pawn=0x%llX cls=%s name=%s\r\n",tag,(unsigned long long)owner,ocn,oon);
            }
        }
    }
    Markerf("[PAWN%d] total hero/champion/drop/lokichar live actors=%d\r\n",tag,shown);
}

// Dump a class's UFunctions (Children @ UStruct+0x50, Next @ UField+0x30) + supers, filtered to names likely to
// be a match-model setter/factory. Finds the native entry point to populate CoreGameMatchModel consistently.
static void DumpClassFuncs(int tag, const char* label, uintptr_t cls){
    if(!LooksLikePtr(cls)){ Markerf("[FUNC%d] %s: bad class\r\n",tag,label); return; }
    char cnm[96]="?"; GetFNameStr(NameId(cls),cnm,sizeof(cnm));
    Markerf("[FUNC%d] %s cls=%s:\r\n",tag,label,cnm);
    int guard=0;
    while(LooksLikePtr(cls) && guard++<8){
        char scn[96]="?"; GetFNameStr(NameId(cls),scn,sizeof(scn));
        uintptr_t f=SafeReadable((void*)(cls+0x50),8)?*(uintptr_t*)(cls+0x50):0; int i=0;
        while(LooksLikePtr(f) && i++<1000){
            char fn[96];
            if(GetFNameStr(NameId(f),fn,sizeof(fn)) && (strstr(fn,"Match")||strstr(fn,"Update")||strstr(fn,"Valid")||strstr(fn,"Info")||strstr(fn,"Start")||strstr(fn,"Create")||strstr(fn,"Set")||strstr(fn,"Handle")||strstr(fn,"Enter")||strstr(fn,"Refresh")||strstr(fn,"State")||strstr(fn,"Ready")||strstr(fn,"Init")||strstr(fn,"Phase")||strstr(fn,"Drop")||strstr(fn,"Deploy")||strstr(fn,"Round")||strstr(fn,"Advance")||strstr(fn,"Begin")||strstr(fn,"Spawn")||strstr(fn,"Possess")||strstr(fn,"Player")||strstr(fn,"Warmup")||strstr(fn,"Countdown")))
                Markerf("[FUNC%d]   %s::%s\r\n",tag,scn,fn);
            f=SafeReadable((void*)(f+0x30),8)?*(uintptr_t*)(f+0x30):0;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;   // UStruct::SuperStruct
    }
}

// Tight loop poking the match model valid+InProgress for ~13s (covers the ~7s-after-force-open revert window).
static void PokeMatchModelLoop(){
    if(!g_cgm) g_cgm=FindCoreGameManager();
    if(!g_cgm){ Marker("[POKE] no CoreGameManager\r\n"); return; }
    Markerf("[POKE] cgm=0x%llX poking mm+0x%X=1 mm+0x%X=5 ~13s\r\n",(unsigned long long)g_cgm,MM_VALID_OFF,MM_STATE_OFF);
    DWORD t0=GetTickCount(); long n=0; uintptr_t lastMM=0;
    while(GetTickCount()-t0<13000){
        uintptr_t mm=SafeReadable((void*)(g_cgm+CGM_MM_OFF),8)?*(uintptr_t*)(g_cgm+CGM_MM_OFF):0;
        if(LooksLikePtr(mm)){
            if(mm!=lastMM){ Markerf("[POKE] mm=0x%llX (t+%lums)\r\n",(unsigned long long)mm,GetTickCount()-t0); lastMM=mm; }
            if(SafeReadable((void*)(mm+MM_VALID_OFF),1)) *(volatile uint8_t*)(mm+MM_VALID_OFF)=1;
            // S65: MatchState=5 (InProgress) poke crashed init (~2.4s post world-up, before "ready") — forcing
            // InProgress with a null MatchInfo is inconsistent. Test bIsValid-only (MatchState left at 0).
            // if(SafeReadable((void*)(mm+MM_STATE_OFF),1)) *(volatile uint8_t*)(mm+MM_STATE_OFF)=5;
        }
        n++; Sleep(3);
    }
    Markerf("[POKE] done %ld iters\r\n",n);
}

// ============================ S62 INSTRUMENTED CUSTOM-LOGIN (STEP 0) ============================
// Instead of de-overriding GameMode vtable slot 285 to *plain* stock AGameModeBase::Login (which returns a
// PC whose PlayerState is null -> SpawnPlayActor fatal "PlayerState is null"), point slot 285 at CustomLogin:
// it calls stock Login (gmb[285]) with the same 7 args, LOGS the PC + PlayerState state AT LOGIN-RETURN (no
// 350ms/14ms sampling race), then returns the PC. This captures the exact null-cause so the synthesis step (poke
// PlayerStateClass / bWantsPlayerState, or SpawnActor+assign) can be added minimally next.
static volatile void* g_stockLogin = nullptr;    // gmb[285] = stock AGameModeBase::Login (resolved at install)
static volatile long g_loginCalls = 0;

// Offset of a named FProperty on a class, walking ChildProperties@+0x58 then the SuperStruct@+0x40 chain.
static uint32_t PropOffset(uintptr_t cls, const char* name){
    int guard=0;
    while(LooksLikePtr(cls) && guard++<12){
        uintptr_t f = SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8) ? *(uintptr_t*)(cls+UFUNC_CHILDPROPS) : 0;
        int i=0;
        while(LooksLikePtr(f) && i++<500){
            if(NameIs(f,name)) return SafeReadable((void*)(f+FPROP_OFFSET),4) ? *(uint32_t*)(f+FPROP_OFFSET) : 0xFFFFFFFF;
            f = SafeReadable((void*)(f+FIELD_NEXT),8) ? *(uintptr_t*)(f+FIELD_NEXT) : 0;
        }
        cls = SafeReadable((void*)(cls+0x48),8) ? *(uintptr_t*)(cls+0x48) : 0;   // UStruct::SuperStruct (@+0x48 this build)
    }
    return 0xFFFFFFFF;
}

// C handler invoked by CustomLogin after stock Login returns. gm = GameMode(this), pc = returned PC.
extern "C" void LogLoginResult(void* gm_, void* pc_, void* err_){
    uintptr_t gm=(uintptr_t)gm_, pc=(uintptr_t)pc_;
    long n = InterlockedIncrement(&g_loginCalls);
    char gmN[96]="?", pcN[96]="?", psClsN[96]="?", curPsN[64]="-";
    uintptr_t psCls = (gm && SafeReadable((void*)(gm+0x3E0),8)) ? *(uintptr_t*)(gm+0x3E0) : 0;
    if(gm && ClassOf(gm)) GetFNameStr(NameId(ClassOf(gm)), gmN, sizeof(gmN));
    if(pc && ClassOf(pc)) GetFNameStr(NameId(ClassOf(pc)), pcN, sizeof(pcN));
    if(psCls) GetFNameStr(NameId(psCls), psClsN, sizeof(psClsN)); else strcpy(psClsN,"NULL");
    // PlayerControllerClass (@GM+0x3D8): the class whose InitPlayerState we must de-override to stock.
    char pcClsN[96]="?"; uintptr_t pcCls = (gm && SafeReadable((void*)(gm+0x3D8),8)) ? *(uintptr_t*)(gm+0x3D8) : 0;
    if(pcCls) GetFNameStr(NameId(pcCls), pcClsN, sizeof(pcClsN)); else strcpy(pcClsN,"NULL");
    uintptr_t psPtr=0; uint32_t psOff=0xFFFFFFFF;
    if(pc){ psOff = PropOffset(ClassOf(pc),"PlayerState"); if(psOff!=0xFFFFFFFF && SafeReadable((void*)(pc+psOff),8)) psPtr=*(uintptr_t*)(pc+psOff); }
    if(psPtr && ClassOf(psPtr)) GetFNameStr(NameId(ClassOf(psPtr)), curPsN, sizeof(curPsN)); else strcpy(curPsN, psPtr?"?":"NULL");
    // arg7 = ErrorMessage FString {Data@0, Num@8}: stock Login writes WHY it returned null here.
    char errS[128]="-";
    if(err_ && SafeReadable(err_,16)){
        uintptr_t d=*(uintptr_t*)err_; uint32_t num=*(uint32_t*)((uint8_t*)err_+8);
        if(num<=1) strcpy(errS,"(empty=approved)");
        else if(d && num<120 && SafeReadable((void*)d,num*2)){ for(uint32_t i=0;i<num-1&&i<127;i++) errS[i]=(char)*(uint16_t*)(d+i*2); errS[(num-1)<127?(num-1):127]=0; }
    }
    Markerf("[LOGIN%ld] gm=%s PCClass=%s pc=0x%llX(%s) PSClass=%s PS(off=0x%X)=0x%llX(%s) err='%s'\r\n",
        n, gmN, pcClsN, (unsigned long long)pc, pcN, psClsN, psOff, (unsigned long long)psPtr, curPsN, errS);
}

// ============================ S63 PLAYERSTATE FIX (STEP 1) ============================
// S62 root cause: stock AGameModeBase::Login SPAWNS the PC fine but BP_LokiPlayerController_Dev_C has a NULL
// PlayerState (the Loki PC defers PlayerState creation to network replication; a standalone force-open has no
// server) -> stock Login's InitNewPlayer returns "PlayerState is null" -> Login returns null -> fatal.
// FIX STRATEGY (both done in PrepareLogin, called from CustomLogin *before* stock Login runs):
//   (instrument) Diff the Loki PC C++ vtable vs stock APlayerController's, .text-guarded, and flag the slot(s)
//     whose STOCK function references GameMode+0x3E0 (PlayerStateClass) = the InitPlayerState candidate(s).
//     The class loads only during travel, so this MUST run in-shim at Login-time (not offline).
//   (fix, kFixMode) FIX_A2_STOCKPC: poke GM+0x3D8 (PlayerControllerClass) -> stock APlayerController so
//     SpawnPlayerController makes a fully-stock PC whose stock InitPlayerState creates the PlayerState in
//     standalone. Near-certain to clear the gate, low crash risk, keeps the game ALIVE to observe downstream
//     (but a stock PC loses Loki input/camera/possession -> diagnostic, not the final fix).
//   (fix, kFixMode) FIX_TARGETED_INITPS: de-override the InitPlayerState slot(s) in the Loki PC vtable to stock
//     -> the Loki PC creates its own BP_LokiPlayerState locally, keeping full Loki PC behavior (the real fix).
// All patches are TRANSIENT: restored right after stock Login returns (integrity check covers .rdata vtables).
constexpr uintptr_t kTextLoRva=0x1000, kTextHiRva=0x7649000;                 // .text range (above = .rdata/data)
constexpr uintptr_t GM_GSCLASS_OFF=0x3D0, GM_PCCLASS_OFF=0x3D8, GM_PSCLASS_OFF=0x3E0;  // AGameModeBase config members
enum FixMode { FIX_NONE=0, FIX_A2_STOCKPC=1, FIX_TARGETED_INITPS=2 };
static const int kFixMode = FIX_TARGETED_INITPS;   // S63: A2 cleared login (parked at WaitingForClientsReady w/ stock PC);
                                                   // now keep the Loki PC via InitPlayerState de-override (slots 260/273)

static uintptr_t g_lokiPCVt=0;                        // Loki PC C++ vtable base (for restore)
static int g_pcPatchSlots[8]={0}; static uintptr_t g_pcPatchOrig[8]={0}; static int g_nPcPatch=0;
static uintptr_t g_savedPCClass=0; static bool g_pokedPCClass=false;

// Find the first object whose FName == want (matches CDOs by their "Default__<Class>" FName).
static uintptr_t FindObjByName(const char* want){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; if(NameIs(obj,want))return obj; } }
    return 0;
}
// Scan up to cap bytes at fn for the 4-byte little-endian value needle (e.g. a disp32 like 0x3E0).
static bool ScanDisp(uintptr_t fn,uint32_t needle,int cap){
    if(!fn)return false;
    for(int i=0;i+4<=cap;i++){ if(!SafeReadable((void*)(fn+i),4))break; uint32_t v; memcpy(&v,(void*)(fn+i),4); if(v==needle)return true; }
    return false;
}

// Runs INSIDE CustomLogin, before stock Login. gm = GameMode(this). Dumps the PC vtable diff + applies the fix.
static void PrepareLogin(uintptr_t gm){
    g_nPcPatch=0; g_pokedPCClass=false; g_lokiPCVt=0;
    if(!gm){ Marker("[PREP] gm=0\r\n"); return; }
    uintptr_t lokiCDO=FindObjByName("Default__BP_LokiPlayerController_Dev_C");
    uintptr_t stockCDO=FindObjByName("Default__PlayerController");
    uintptr_t lokiVt =(lokiCDO && SafeReadable((void*)lokiCDO,8))?*(uintptr_t*)lokiCDO:0;
    uintptr_t stockVt=(stockCDO&& SafeReadable((void*)stockCDO,8))?*(uintptr_t*)stockCDO:0;
    uintptr_t stockPCClass=stockCDO?ClassOf(stockCDO):0;
    Markerf("[PREP] lokiCDO=0x%llX(vt rva 0x%llX) stockCDO=0x%llX(vt rva 0x%llX) stockPCClass=0x%llX\r\n",
        (unsigned long long)lokiCDO,(unsigned long long)(lokiVt?lokiVt-g_modBase:0),
        (unsigned long long)stockCDO,(unsigned long long)(stockVt?stockVt-g_modBase:0),(unsigned long long)stockPCClass);
    int psSlots[8]; int nps=0,nOverride=0;
    if(lokiVt && stockVt){
        uintptr_t tLo=g_modBase+kTextLoRva, tHi=g_modBase+kTextHiRva; int endRun=0;
        for(int s=0;s<380 && endRun<8;s++){
            if(!SafeReadable((void*)(stockVt+s*8),8)||!SafeReadable((void*)(lokiVt+s*8),8)){endRun++;continue;}
            uintptr_t sv=*(uintptr_t*)(stockVt+s*8), lv=*(uintptr_t*)(lokiVt+s*8);
            if(sv<tLo||sv>=tHi){endRun++;continue;} endRun=0;
            if(sv==lv)continue; nOverride++;
            if(ScanDisp(sv,(uint32_t)GM_PSCLASS_OFF,400)){    // stock fn references GM+0x3E0 => InitPlayerState-like
                if(nps<8){ psSlots[nps]=s; Markerf("[DIFF] PS-cand slot %d stockRva=0x%llX lokiRva=0x%llX\r\n",
                    s,(unsigned long long)(sv-g_modBase),(unsigned long long)(lv-g_modBase)); }
                nps++;
            }
        }
    }
    Markerf("[DIFF] overrideCount=%d psCandidates=%d fixMode=%d\r\n",nOverride,nps,kFixMode);
    g_lokiPCVt=lokiVt;
    if(kFixMode==FIX_TARGETED_INITPS && lokiVt && stockVt && nps>=1 && nps<=4){
        for(int k=0;k<nps;k++){ int s=psSlots[k]; uintptr_t* tgt=(uintptr_t*)(lokiVt+(uintptr_t)s*8);
            uintptr_t sval=*(uintptr_t*)(stockVt+(uintptr_t)s*8); DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op))continue;
            g_pcPatchSlots[g_nPcPatch]=s; g_pcPatchOrig[g_nPcPatch]=*tgt; g_nPcPatch++; *tgt=sval; DWORD d=0; VirtualProtect(tgt,8,op,&d); }
        Markerf("[FIX] targeted: de-overrode %d PC vtable slot(s) -> stock InitPlayerState\r\n",g_nPcPatch);
    } else {
        // FIX_A2_STOCKPC (also the fallback when targeted can't identify the slot).
        uintptr_t* tgt=(uintptr_t*)(gm+GM_PCCLASS_OFF);
        if(stockPCClass && SafeReadable(tgt,8)){ DWORD op=0; if(VirtualProtect(tgt,8,PAGE_READWRITE,&op)){
            g_savedPCClass=*tgt; *tgt=stockPCClass; g_pokedPCClass=true; DWORD d=0; VirtualProtect(tgt,8,op,&d);
            Markerf("[FIX] A2: GM+0x3D8 PlayerControllerClass -> stock APlayerController 0x%llX (was 0x%llX)\r\n",
                (unsigned long long)stockPCClass,(unsigned long long)g_savedPCClass); } }
        else Marker("[FIX] A2 FAILED: no stockPCClass or GM+0x3D8 unreadable\r\n");
    }
}
// Restore all Login-time patches right after stock Login returns.
static void RestoreLoginPatches(uintptr_t gm){
    for(int k=0;k<g_nPcPatch;k++){ uintptr_t* tgt=(uintptr_t*)(g_lokiPCVt+(uintptr_t)g_pcPatchSlots[k]*8);
        DWORD op=0; if(VirtualProtect(tgt,8,PAGE_READWRITE,&op)){ *tgt=g_pcPatchOrig[k]; DWORD d=0; VirtualProtect(tgt,8,op,&d); } }
    g_nPcPatch=0;
    if(g_pokedPCClass && gm){ uintptr_t* tgt=(uintptr_t*)(gm+GM_PCCLASS_OFF);
        DWORD op=0; if(VirtualProtect(tgt,8,PAGE_READWRITE,&op)){ *tgt=g_savedPCClass; DWORD d=0; VirtualProtect(tgt,8,op,&d); } g_pokedPCClass=false; }
}

// GameMode vtable slot 285 (Login). Plain C++ fn — the Win64 ABI matches the vtable call site (rcx=this(GM),
// rdx=NewPlayer, r8=InRemoteRole, r9=&Portal, [rsp+0x28]=&Options, [rsp+0x30]=&UniqueId, [rsp+0x38]=&ErrorMessage).
typedef void* (*PFN_LOGIN)(void*,void*,uint64_t,void*,void*,void*,void*);
extern "C" void* CustomLogin(void* gm,void* np,uint64_t rr,void* portal,void* options,void* uid,void* err){
    PrepareLogin((uintptr_t)gm);
    void* pc = g_stockLogin ? ((PFN_LOGIN)g_stockLogin)(gm,np,rr,portal,options,uid,err) : nullptr;
    LogLoginResult(gm,pc,err);
    RestoreLoginPatches((uintptr_t)gm);
    return pc;
}

static uintptr_t g_savedLoginVt[5];   // slot-285 originals per match vtable, for restore
// Install (or restore) CustomLogin into slot 285 of the match-mode vtables. Transient: install before the
// force-open, restore after (integrity check covers .rdata vtables). Records stock Login = gmb[285] for the tramp.
static void InstallCustomLogin(bool install){
    uintptr_t* gmb=(uintptr_t*)(g_modBase+kStockGmbVtRva);
    const int NV=(int)(sizeof(kMatchVtRvas)/sizeof(kMatchVtRvas[0])); const int slot=285;
    if(install && SafeReadable(gmb+slot,8)) g_stockLogin=(void*)gmb[slot];
    int n=0;
    for(int v=0; v<NV; v++){
        uintptr_t* tgt=(uintptr_t*)(g_modBase+kMatchVtRvas[v]+(uintptr_t)slot*8);
        if(!SafeReadable(tgt,8)) continue;
        DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op)) continue;
        if(install){ g_savedLoginVt[v]=*tgt; *tgt=(uintptr_t)&CustomLogin; }
        else if(g_savedLoginVt[v]){ *tgt=g_savedLoginVt[v]; }
        DWORD d=0; VirtualProtect(tgt,8,op,&d); n++;
    }
    Markerf("[VT] custom-login %s: %d vtables slot285, stockLogin=0x%llX tramp=0x%llX\r\n",
        install?"INSTALL":"restore", n, (unsigned long long)(uintptr_t)g_stockLogin, (unsigned long long)(uintptr_t)&CustomLogin);
}

// S62: [LOGIN1] proved stock Login returns a NULL PC (PlayerStateClass was valid) => the reject is
// ALokiGameSession::ApproveLogin. De-override ALokiGameSession's virtual overrides to stock AGameSession so
// ApproveLogin approves -> stock Login spawns a real PC + PlayerState. vtdiff_gamesession.py: ALokiGameSession
// vtable rva 0x898D628 vs stock AGameSession rva 0x80854F8; overrides at slots {0(dtor),298,299,301,313,314}.
// De-override the AGameSession-region ones {298,299,313,314} (301 is a non-GS-region virtual; 0 is the dtor).
// RVAs stable (base 0x7FF6B54F0000). Transient like the GameMode de-override.
constexpr uintptr_t kLokiGSVtRva = 0x898D628, kStockGSVtRva = 0x80854F8;
static const int kGSSlots[] = {298,299,313,314};
static uintptr_t g_savedGSVt[8];
static void InstallGameSessionDeoverride(bool install){
    uintptr_t* loki=(uintptr_t*)(g_modBase+kLokiGSVtRva);
    uintptr_t* stock=(uintptr_t*)(g_modBase+kStockGSVtRva);
    const int NS=(int)(sizeof(kGSSlots)/sizeof(kGSSlots[0])); int n=0;
    for(int s=0; s<NS; s++){
        int slot=kGSSlots[s]; uintptr_t* tgt=loki+slot;
        if(!SafeReadable(tgt,8)||!SafeReadable(stock+slot,8)) continue;
        DWORD op=0; if(!VirtualProtect(tgt,8,PAGE_READWRITE,&op)) continue;
        if(install){ g_savedGSVt[s]=*tgt; *tgt=stock[slot]; }
        else if(g_savedGSVt[s]){ *tgt=g_savedGSVt[s]; }
        DWORD d=0; VirtualProtect(tgt,8,op,&d); n++;
    }
    Markerf("[VT] gamesession de-override %s: %d slots {298,299,313,314}\r\n", install?"INSTALL":"restore", n);
}
// ================================================================================================

static DWORD WINAPI Worker(LPVOID){
    { HANDLE ch=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(ch!=INVALID_HANDLE_VALUE)CloseHandle(ch); }
    Marker("[0] tutorial_launch (force-open LVL_Tutorial via ExecuteConsoleCommand) started\r\n");
    bool fromFile=LoadCommand();
    Markerf("[0] command %s: '%ls'\r\n", fromFile?"from tutorial-launch-cmd.txt":"(default fallback)", g_cmd);
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    if(kInvestigateOnly){
        Marker("[INV] investigate-only: dumping CoreGameManager/CoreGameMatchModel state + functions at the menu\r\n");
        DumpTutorialState(0); DumpPawns(0); DumpStartSpots(0);
        Marker("[INV] done; NOT force-opening (game stays at menu)\r\n"); return 0;
    }
    if(kRunMode==RM_SPAWNPLAYER){
        Marker("[SPW] spawn-player mode: SpawnPlayer(localPS)->hero + Possess in the RUNNING tutorial\r\n");
        if(!ResolveSpawnPlayer()){ Marker("[SPW] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[SPW] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[SPW] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[SPW] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
        UninstallHook();
        char pcn[96]="-"; if(LooksLikePtr(g_spawnedPawn)&&ClassOf(g_spawnedPawn)) GetFNameStr(NameId(ClassOf(g_spawnedPawn)),pcn,sizeof(pcn));
        Markerf("[SPW] done hero=0x%llX cls=%s (called=%ld hitsGT=%ld)\r\n",(unsigned long long)g_spawnedPawn,pcn,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_CHEATSPAWN){
        Marker("[CS] cheat-spawn mode: call the game's own LokiPlayerCheats RPC directly (in-process, local authority)\r\n");
        Resolve();   // populate g_worldCtx (a live ProgressionManager) as WorldContext fallback for GetLocal
        ResolveCheatSpawn();
        if(kCheatResolveOnly){ Markerf("[CS] resolve-only: schThunk=0x%llX cchThunk=0x%llX accThunk=0x%llX scsaThunk=0x%llX glcThunk=0x%llX heroClass=0x%llX — NOT firing (set kCheatResolveOnly=false + inject into a running tutorial)\r\n",(unsigned long long)g_schThunk,(unsigned long long)g_cchThunk,(unsigned long long)g_accThunk,(unsigned long long)g_scsaThunk,(unsigned long long)g_glcThunk,(unsigned long long)g_cheatHeroClass); return 0; }
        if(!g_schThunk && !g_cchThunk && !g_accThunk && !g_scsaThunk && !g_spsThunk){ Marker("[CS] resolve failed (no target thunk) -> abort\r\n"); return 0; }
        if(!g_glcThunk){ Marker("[CS] WARN: GetLocalLokiPlayerCheatsBP unresolved; DoCheatSpawn will abort unless g_cheatObj is preset\r\n"); }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[CS] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[CS] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[CS] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
        UninstallHook();
        char cn[96]="-"; if(LooksLikePtr(g_cheatObj)&&ClassOf(g_cheatObj)) GetFNameStr(NameId(ClassOf(g_cheatObj)),cn,sizeof(cn));
        Markerf("[CS] done cheatObj=0x%llX cls=%s (called=%ld hitsGT=%ld)\r\n",(unsigned long long)g_cheatObj,cn,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_GOTOPHASE){
        Marker("[GP] go-to-phase mode: advance the round EGP_BeginInit -> Combat in the RUNNING tutorial\r\n");
        if(!ResolveGoToPhase()){ Marker("[GP] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[GP] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[GP] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[GP] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<15000) Sleep(20);   // ~7 phases x 450ms + processing
        UninstallHook();
        Markerf("[GP] done (phasesCalled=%d called=%ld hitsGT=%ld)\r\n",g_phaseIdx,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_WAKEMOVE){
        Marker("[WM] wake-move mode: kick the possessed hero's frozen CMC (activate+tick+mode+gravity) then sample velocity\r\n");
        if(!ResolveWakeMove()){ Marker("[WM] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[WM] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[WM] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[WM] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<12000) Sleep(20);   // teleport + 1 kick + ~12 samples x 400ms
        UninstallHook();
        Markerf("[WM] done (samples=%d called=%ld hitsGT=%ld)\r\n",g_wmSample,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_PUPPET){
        Marker("[PUP] puppet mode: read WASD each game-thread hit -> write the possessed hero's CMC velocity\r\n");
        g_gameHwnd=FindWindowA(nullptr,"SUPERVIVE");
        Markerf("[PUP] gameHwnd=0x%llX (0 => focus check disabled, always drives)\r\n",(unsigned long long)(uintptr_t)g_gameHwnd);
        if(!ResolveWakeMove()){ Marker("[PUP] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[PUP] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[PUP] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[PUP] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<600000) Sleep(20);   // ~10 min of play, then release
        UninstallHook();
        if(SafeReadable((void*)(g_wmCMC+0xE8),16)){ double* V=(double*)(g_wmCMC+0xE8); V[0]=0.0; V[1]=0.0; }   // stop on exit
        Markerf("[PUP] done (called=%ld hitsGT=%ld)\r\n",(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_TOGGLEREADY){
        Marker("[TR] toggle-ready mode: hook ULokiGameFeatureToggles::Get, set readiness bit6 on each queried object's D\r\n");
        g_getAddr=g_modBase+kGetRva;
        static const uint8_t kGetProlog[7]={0x41,0x54,0x48,0x89,0x5C,0x24,0x08};   // push r12; mov [rsp+8],rbx
        if(!SafeReadable((void*)g_getAddr,7)||memcmp((void*)g_getAddr,kGetProlog,7)!=0){ Markerf("[TR] FAIL Get prologue mismatch @0x%llX\r\n",(unsigned long long)g_getAddr); return 4; }
        memcpy(g_getStolen,(void*)g_getAddr,7);
        g_getStub=BuildGetHook(g_getAddr,g_getStolen);
        if(!g_getStub){ Marker("[TR] FAIL BuildGetHook\r\n"); return 5; }
        int32_t rel=(int32_t)((intptr_t)g_getStub-((intptr_t)g_getAddr+5));
        uint8_t patch[7]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24),0x90,0x90};
        if(!SafeWrite((uint8_t*)g_getAddr,patch,7)){ Marker("[TR] FAIL install\r\n"); return 6; }
        Markerf("[TR] hook installed Get=0x%llX stub=0x%llX storeGetter=0x%llX; collecting ~3s...\r\n",(unsigned long long)g_getAddr,(unsigned long long)(uintptr_t)g_getStub,(unsigned long long)(g_modBase+kStoreGetterRva));
        Sleep(3000);
        SafeWrite((uint8_t*)g_getAddr,g_getStolen,7);   // uninstall (bit6 stays set — data)
        Markerf("[TR] hook removed. getHits=%ld uniqueD-set=%ld\r\n",(long)g_getHits,(long)g_dSeenN);
        for(long i=0;i<g_dSeenN && i<64;i++) Markerf("[TR]   D[%ld]=0x%llX (bit6 set)\r\n",i,(unsigned long long)g_dSeen[i]);
        return 0;
    }
    if(kRunMode==RM_SPAWNPOSSESS){
        Marker("[SP] spawn+possess mode (inject into the RUNNING tutorial)\r\n");
        if(!ResolveSpawnPossess()){ Marker("[SP] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[SP] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[SP] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[SP] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
        UninstallHook();
        char pcn[96]="-"; if(LooksLikePtr(g_spawnedPawn)&&ClassOf(g_spawnedPawn)) GetFNameStr(NameId(ClassOf(g_spawnedPawn)),pcn,sizeof(pcn));
        Markerf("[SP] done step=%ld spawnedPawn=0x%llX cls=%s (called=%ld hitsGT=%ld)\r\n",
            (long)g_spStep,(unsigned long long)g_spawnedPawn,pcn,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    DWORD dl=GetTickCount()+120000; while(GetTickCount()<dl){ Resolve(); if(g_worldCtx&&g_eccThunk&&g_eccChild&&g_offCmd!=0xFFFFFFFF)break; Sleep(500);}
    if(!g_worldCtx||!g_eccThunk||g_offCmd==0xFFFFFFFF){Markerf("[2] FAIL resolve worldCtx=0x%llX kslCDO=0x%llX eccThunk=0x%llX child=0x%llX offWCO=0x%X offCmd=0x%X offSP=0x%X\r\n",(unsigned long long)g_worldCtx,(unsigned long long)g_kslCDO,(unsigned long long)g_eccThunk,(unsigned long long)g_eccChild,g_offWCO,g_offCmd,g_offSP);return 3;}
    Markerf("[2] worldCtx=0x%llX kslCDO=0x%llX eccThunk=0x%llX(rva 0x%llX) child=0x%llX offWCO=0x%X offCmd=0x%X offSP=0x%X gameTid=%lu cmd='%ls'\r\n",(unsigned long long)g_worldCtx,(unsigned long long)g_kslCDO,(unsigned long long)g_eccThunk,(unsigned long long)(g_eccThunk-g_modBase),(unsigned long long)g_eccChild,g_offWCO,g_offCmd,g_offSP,g_gameTid,g_cmd);
    g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[2] FAIL PI prologue\r\n");return 4;}
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 5;}
    Marker("[3] hook built; issuing ExecuteConsoleCommand('open LVL_Tutorial') on the game thread...\r\n");
    if(kPokeMatchModel){ g_cgm=FindCoreGameManager(); Markerf("[3] pre-cached CoreGameManager=0x%llX\r\n",(unsigned long long)g_cgm); }
    InstallCustomLogin(true);   // S62: slot-285 -> CustomLogin (calls stock Login + logs the PlayerState at Login-return)
    // (GameSession de-override removed — the vtdiff read past the vtable end; instrument ErrorMessage instead.)
    if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n");InstallCustomLogin(false);return 6;}
    DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
    UninstallHook();
    if(g_done){
        Markerf("[4] CALLED (called=%ld hitsGT=%ld) — de-override held; %s across travel...\r\n",(long)g_called,(long)g_hitsGT, kPokeMatchModel?"POKING match model valid":"sampling tutorial state");
        if(kPokeMatchModel){
            DumpCoreGameState(0);       // pre-poke state
            PokeMatchModelLoop();       // keep bIsValid=1 + MatchState=InProgress across the revert window
            DumpCoreGameState(9);       // post state
        } else {
            // KEEP CustomLogin (slot-285) installed until the tutorial Login actually fires. The "open" console
            // command is DEFERRED — Login runs ~7s later (after LoadMap). Restoring too early => the strict
            // native Login runs => "ALokiGameMode::Login failed to Login" fatal. Poll g_loginCalls (set by
            // CustomLogin/LogLoginResult), max 16s, then a grace. No object-walk here (avoid init contention);
            // survey the running tutorial via a separate census inject.
            DWORD hs=GetTickCount(); while(g_loginCalls==0 && GetTickCount()-hs<16000) Sleep(50);
            Sleep(1500);
        }
    } else {
        Markerf("[4] TIMEOUT no game-thread PI in 8s (hitsGT=%ld)\r\n",(long)g_hitsGT);
    }
    InstallCustomLogin(false);  // restore slot-285 so the ~3-5min code-integrity check sees the vtables clean
    Marker("[5] done (vtable restored)\r\n");
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
extern "C" __declspec(dllexport) void* start_mod(){return new int(0);}
extern "C" __declspec(dllexport) void uninstall_mod(void* m){delete static_cast<int*>(m);}
