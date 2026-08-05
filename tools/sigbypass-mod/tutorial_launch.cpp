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
// S91 BP-CALL: UStruct tail in this build (stock UE5 order, shifted +0x18 like SuperStruct@0x48/Children@0x50/
// ChildProperties@0x58): PropertiesSize(int32)@0x60, MinAlignment@0x64, Script TArray{Data@0x68,Num@0x70}.
constexpr uintptr_t USTRUCT_PROPSIZE=0x60, USTRUCT_SCRIPT=0x68, USTRUCT_SCRIPTNUM=0x70;
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
enum RunMode { RM_FORCEOPEN=0, RM_SPAWNPOSSESS=1, RM_GOTOPHASE=2, RM_SPAWNPLAYER=3, RM_CHEATSPAWN=4, RM_WAKEMOVE=5, RM_PUPPET=6, RM_TOGGLEREADY=7, RM_TRAINING=8, RM_SPAWNSEQ=9, RM_SPAWNQUEST=10, RM_QUESTPLAY=11, RM_BPCALL=12, RM_OBJDRIVE=13, RM_OBJCOMPLETE=14, RM_FIREOVERLAP=15, RM_DRIVECHAIN=16, RM_CAMERA=17, RM_TOPDOWNCAM=18, RM_MESHCAM=19, RM_DROPIN=20, RM_MAKEMESH=21, RM_PLAY=22 };
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

// ══════════════════════════════════════════════════════════════════════════════════════════════════
// ★★★★ S106d (2026-07-29) — KXFORMFIX: THE SPAWN FTransform WAS **TRUNCATED** *AND* **MIS-OFFSET**.
//   THIS IS A CAUSE-SHAPED FIX, NOT A SYMPTOM GUARD.  It is deliberately its own flag so it can be
//   A/B'd against KVTGUARD (which repairs a symptom) -- see BUILD.md's artifact matrix.
//
// TWO INDEPENDENT DEFECTS, BOTH MEASURED IN THE SOURCE, BOTH DROPPING Scale3D.Z:
//
//   D1  TRUNCATION.  `const uint32_t xfsz=0x50;` in DoSpawnSeq and in SpawnActorCls copied only 0x50
//       bytes of the 0x60-byte FTransform into the spawn params.  Scale3D.Z lives at **0x50**, so the
//       copy stopped EXACTLY at it: every actor SpawnActorCls has ever produced spawned with
//       Scale3D = (x, y, **0**).  The truncation is independent of the caller -- the GAS carrier at
//       L3072 writes Scale3D at the CORRECT 0x40/0x48/0x50 and was truncated anyway.
//       Same defect a third time inside BuildHeroBody: `savedXform[0x50]` + `memcpy(...,0x50)`, so the
//       DEFERRED **FinishAddComponent** -- i.e. component REGISTRATION, which is when the cloth /
//       physics body is built -- re-applied a transform with Scale.Z = 0 and thereby UNDID the S98
//       post-creation `RelativeScale3D = (1,1,1)` fix ~40 lines earlier.  That answers the standing
//       order-of-operations question: yes, the degenerate body is built AFTER the scale fix lands,
//       because registration overwrote it.
//
//   D2  WRONG OFFSETS.  Four call sites still wrote Scale3D at the pre-S98 **0x38/0x40/0x48**:
//       L1442 (DoSpawnSeq), L2411 (**DoTopDownCam -- the VIEW-TARGET CAMERA ITSELF**), L3570 (KSMACTOR),
//       L3588 (KTESTACTOR).  In this build FTransform is the 16-byte-aligned 0x60 layout
//       (Rotation@0x00, Translation@0x20 + 8 pad, **Scale3D@0x40/0x48/0x50** + 8 pad), so those writes
//       put 1.0 into translation PADDING at 0x38, then Scale.X and Scale.Y, and left Scale.Z ZERO.
//       Proof (MEASURED, S98 L3907-3911): xfsz = g_oBColl-g_oBXform = 0x70-0x10 = 0x60, and a first fix
//       writing 0x38/0x40/0x48 produced a LIVE root RelativeScale3D of (1.000,1.000,0.000).
//       The defaults at L106/L107 independently corroborate 0x60 spacing.
//
// CONSEQUENCE (MEASURED by composition): the top-down CameraActor spawned at Scale3D=(1,1,**0**), the
// KTESTACTOR CameraActor at (1,1,0) and the KSMACTOR StaticMeshActor at (3,3,0).  A component attached
// to a root whose scale is (1,1,0) has a NON-UNIFORM world scale whatever its own relative scale is --
// which is exactly what the single `LogChaosCloth` "has a non uniform scale, and has a cloth simulation
// attached" line in 4-of-4 crashing sessions reports (INFERRED: the shipping log does NOT name the
// object, so the line cannot itself identify which body).
//
// WHY THIS IS THE FK-7 SUSPECT AND NOT JUST A RENDER BUG.  The camera crash is a ONE-BYTE store of the
// literal 0x01 at PCM+0x420 (ViewTarget.Target), at a CONSTANT displacement across 4 launches, with
// ZERO collateral corruption, already present at the TOP of DoUpdateCamera in 4/4 -- so the writer is
// NOT in the camera chain, and it computes its address rather than stumbling into it.  Candidate (b),
// "a one-byte heap OVERRUN out of the degenerate cloth/physics bodies", is now FALSIFIED on structural
// grounds: 0x420 is 0x420 bytes INSIDE the PCM's own live allocation (PCM+0x00 holds the
// APlayerCameraManager vtable, PendingViewTarget.Target is a further 0x820 higher at PCM+0xC40), and
// heap blocks do not overlap, so nothing can end at PCM+0x420 and overrun into it.  ⇒ we no longer
// claim the degenerate body writes the byte.  What IS still true, and is why this fix ships anyway:
//   * these are REAL defects that corrupt every actor the shim spawns, including the view target;
//   * the degenerate scale is the only measured antecedent that separates 4/4 crashes from 0/68 others;
//   * a NaN/degenerate scale is the classic source of a WILD indexed write, which is the one overrun
//     variant the structural argument does not kill;
//   * it is a single-variable change and it is free to test.
//   RETRACTED with it: the old note above KVTGUARD that "a repeat [VTG] delta of exactly +0x3F
//   implicates a writer that targets this field; a wandering delta implicates the heap overrun".
//   delta = (live & 0xFF) - 0x01, and the live object's low byte was 0x40 in 3 of 3 observations
//   (including a CLEAN control dump), so +0x3F is ALLOCATOR-FORCED and discriminates nothing.  The line
//   is kept -- it still confirms "same bug, not a new one" -- but not as writer attribution.
//
// -DKXFORMFIX=0 restores the exact pre-S106d behaviour (0x50 copies, Scale3D at 0x38) for the A/B.
#ifndef KXFORMFIX
#define KXFORMFIX 1
#endif
// Byte offset of Scale3D inside this build's FTransform. 0x40 = MEASURED; 0x38 = the historical bug.
static const uint32_t kXfScaleOff = KXFORMFIX ? 0x40 : 0x38;
// Full FTransform size to copy into a spawn param block. MEASURED 0x60 (= g_oBColl - g_oBXform).
static const uint32_t kXfSize     = KXFORMFIX ? 0x60 : 0x50;
// Set g_xform's Scale3D. One helper so a future layout change is ONE edit, not five.
static void XfScale(double x,double y,double z){
    *(double*)(g_xform+kXfScaleOff)      = x;
    *(double*)(g_xform+kXfScaleOff+0x08) = y;
    *(double*)(g_xform+kXfScaleOff+0x10) = z;   // ⚠ 0x50 with the fix on -- the byte D1 used to truncate
}
// The size actually copied. Prefer the RUNTIME-MEASURED param spacing (g_oBColl-g_oBXform, live
// reflection) over any constant; kXfSize is only the fallback when reflection has not filled them in.
// Clamped to sizeof(g_xform) so a surprising layout can never read past the buffer.
static uint32_t XfSize(){
    uint32_t n = (g_oBColl>g_oBXform) ? (g_oBColl-g_oBXform) : kXfSize;
    if(!KXFORMFIX && n>kXfSize) n=kXfSize;          // -DKXFORMFIX=0 must reproduce the OLD truncation
    if(n>sizeof(g_xform)) n=(uint32_t)sizeof(g_xform);
    return n;
}
// ══════════════════════════════════════════════════════════════════════════════════════════════════
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
static bool ResolveTraining(); static void DoTraining();
static bool ResolveSpawnSeq(); static void DoSpawnSeq();   // S90 RM_SPAWNSEQ: spawn the tutorial quest sequencer   // S90 RM_TRAINING: start the tutorial lessons + commit the drop
static bool ResolveSpawnQuest(); static void DoSpawnQuest();   // S91 RM_SPAWNQUEST: spawn the TrainingQuest_Basics_* quest ACTORS
static bool ResolveQuestPlay(); static void DoQuestPlay();     // S91 RM_QUESTPLAY: teleport the hero into the quest's own trigger
static bool ResolveBPCall(); static void DoBPCall();           // S91 RM_BPCALL: BP-function-call primitive + arm the lesson
static bool ResolveObjDrive(); static void DoObjDrive();       // S92 RM_OBJDRIVE: advance the active objective (physical/overlap/ProgressObjective)
static bool ResolveObjComplete(); static void DoObjComplete(); // S93 RM_OBJCOMPLETE: force count->target + fire OnRep/EndTraining
static bool ResolveFireOverlap(); static void DoFireOverlap();  // S93 RM_FIREOVERLAP: fire the overlap beat + ungated completion closer
static bool ResolveDriveChain(); static void DoDriveChain();    // S93 RM_DRIVECHAIN: walk the lesson chain (activate->start->complete per lesson)
static bool ResolveCamera(); static void DoCamera();            // S93 RM_CAMERA: fix the over-zoomed possess camera (enable spring-arm tick)
static bool ResolveTopDownCam(); static void DoTopDownCam();    // S93 RM_TOPDOWNCAM: spawn a top-down CameraActor + re-assert view target
static bool ResolveMeshCam(); static void DoMeshCam();          // S93 RM_MESHCAM: build the hero mesh (ClientInitialComponentSetup) + top-down cam
static bool ResolveDropIn(); static void DoDropIn();            // S93 RM_DROPIN: drive the DropPlane drop-in descent (SpawnPlane->AddPlayerToDropPlane)
static bool ResolveMakeMesh(); static void DoMakeMesh();        // S93 RM_MAKEMESH: recreate a visible hero body from scratch (AddComponentByClass+SetSkeletalMeshAsset)
static bool ResolvePlay(); static void DoPlay();               // S94 RM_PLAY: the VISIBLE + MOVABLE hero (ground-teleport + Ronin mesh + top-down cam + WASD puppet, one shim)

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
// ═══════════════════════════════════════════════════════════════════════════════════════════════════
// ★★★★ S107 (2026-08-03) — FK-24 WATCHPOINT PROBE.  ONE QUESTION: **WHO STORES THE 0x01 BYTE?**
//
// MEASURED (docs/fk7-crash-settled.md §0, four camera dumps):  APlayerCameraManager->ViewTarget.Target
// sits at PCM+0x420.  Its LOW BYTE is replaced by the literal 0x01 while bytes 1..7 stay byte-identical
// to the live object  =>  a ONE-BYTE store of an immediate 1, at a fixed displacement from a LIVE PCM,
// ~0.15 s after the body build, ALREADY WRONG AT THE TOP OF DoUpdateCamera in 4/4  =>  the writer runs
// OUTSIDE the camera chain.  290 of 290 non-pointer PCM offsets are byte-identical across the four
// dumps => surgical, not collateral.  The heap-overrun candidate is dead on structural grounds (0x420
// is 0x420 bytes INSIDE the PCM's own live allocation and heap blocks do not overlap).  A `mov byte
// [reg+0x420],1` instruction scan found 8 sites, none in camera code -- but .text is only 52.29%
// decrypted, so that is NOT a negative result.  Rate: ~1-in-2 to 1-in-3 launches.  A SINGLE QUIET RUN
// PROVES NOTHING.
//
// ⚠⚠ THE RETRACTED TRAP THIS PROBE MUST NOT RE-INTRODUCE.  The previous instrumentation logged
// `delta = live - corrupt` and read `+0x3F` as "a writer aimed at this field".  delta = (live&0xFF)-1,
// and the live low byte is allocator-forced to 0x40 (3/3, incl. a clean control), so +0x3F is
// ARITHMETIC, not evidence -- an instrument artifact built into the instrument meant to settle the
// question.  ⇒ EVERY attribution this probe emits is an **IDENTITY**: thread id, RIP, module+RVA, the
// instruction bytes at RIP-64, the return-address chain, and WHICH REGISTER HELD THE PCM.  The value
// at &Target is used for exactly ONE purpose -- to say WHICH trap was the corrupting one -- and the
// log line labels it as such.  Nothing here reports a property of the written value as attribution.
//
// ───────────────────────────────────────────────────────────────────────────────────────────────────
// TWO MECHANISMS, ONE AT A TIME (they are mutually exclusive on purpose: BOTH surface as
// STATUS_SINGLE_STEP, and running two instruments at once doubles the ways the instrument can be
// wrong -- the exact failure shape this project has hit seven times).
//
//   KWPROBE=1  PRIMARY  -- DR0/DR1 hardware 1-byte WRITE watchpoints, armed on EVERY thread and
//              re-swept every KWPSWEEPMS so threads created later are covered.  Exactly 1 byte of
//              granularity, zero cost when it does not fire, and it does NOT perturb the timing of the
//              race being measured.  ★ Its known risk -- the packer clearing DR7 -- is SELF-ANNOUNCING:
//              every arm reads Dr7 BACK and every sweep re-reads it, so a defeated watchpoint prints
//              VOID instead of a false negative.
//              ★ DR1 at &Target+1 is the HARDWARE DISCRIMINATOR that replaces the retracted +0x3F: a
//              ONE-byte store at offset 0 fires DR0 ONLY; an 8-byte pointer store whose low byte merely
//              happens to be 0x01 fires DR0 **and** DR1.  That is a property of the *instruction*.
//
//   KWPROBE=2  FALLBACK -- PAGE_READONLY write trap on the 4 KB page holding &Target.  Process-wide
//              (VAD-level), so it needs NO per-thread work and covers threads that do not exist yet --
//              strictly better on the thread-coverage problem.  Cost: the page is SHARED (the PCM is
//              not page-aligned, offsets 0x040..0xAE0 measured across 5 dumps) and ViewTarget.POV is on
//              the same page in 5/5 and is written every frame, so this traps on writes that are not
//              ours.  Bounded by the KWPMAXTRAPS / KWPMAXTPS panic valve.
//
//   PAGE_GUARD is REJECTED outright, not merely deprioritised.  SafeReadable (L321) returns false for
//   PAGE_GUARD, so arming it would SILENTLY DISABLE VtGuard -- the instrument would destroy the very
//   correlation evidence it exists to produce.  PAGE_READONLY is accepted by SafeReadable, and
//   SafeWritable is given an explicit exemption for the probe's own page (see its definition) so
//   VtGuard's repair store still lands.  (It traps first, which is correct: it is logged origin=SELF
//   and doubles as a positive control aimed at the exact address in question.)
//
//   NOT DONE, and named so nobody re-proposes it: attaching a real debugger from a second process
//   (DebugActiveProcess + CREATE_THREAD_DEBUG_EVENT) is the textbook fix for thread coverage, but this
//   binary is VMProtect/Themida-packed -- PEB.BeingDebugged / NtGlobalFlag / ProcessDebugPort are all
//   trivially checked and attaching changes exception dispatch, i.e. it changes the experiment.
//
// ───────────────────────────────────────────────────────────────────────────────────────────────────
// WHY DR ARMING CAN ONLY EVER BE A POLL (structural, not a preference): DllMain calls
// DisableThreadLibraryCalls (L5227) AND this DLL is MANUAL-MAPPED (tools/inject mmap), so it is not in
// the loader's module list and DLL_THREAD_ATTACH could never fire even without that call.  There is no
// thread-creation notification available to this shim.  Hence the sweep, and hence `newSinceLast` is
// REPORTED per sweep: if the sweep immediately before the corruption found new threads, coverage was
// not established and the result is VOID, not negative.
//
// PRECEDENT (MEASURED, L538 SafeWrite): CreateToolhelp32Snapshot -> OpenThread -> mass SuspendThread ->
// GetThreadContext -> ResumeThread already runs in THIS process under THIS packer on every launch.  So
// enumeration + suspend + GetThreadContext are proven; only CONTEXT_DEBUG_REGISTERS/SetThreadContext
// is unproven -- which is exactly what the Dr7 readback measures.
//
// HANDLER DISCIPLINE: the VEH does NO CreateFile and NO VirtualQuery.  It fills a lock-free ring
// (plain stores + one InterlockedIncrement) and, for the ONE interesting event, a static full record.
// Logging is done by WpThread.  The single exception is WpLogf, which writes through a marker-file
// handle OPENED AT ARM TIME -- WriteFile on an already-open handle takes no loader/heap lock, so the
// decisive line survives a death that follows it without the CreateFileA deadlock risk.
// ═══════════════════════════════════════════════════════════════════════════════════════════════════
#ifndef KWPROBE
#define KWPROBE 0        // ★ 0 = OFF (default) -> the `play` artifact is byte-unchanged.  1 = DR.  2 = page.
#endif
#if KWPROBE
#ifndef KWPARMAT
#define KWPARMAT 0       // 0 = arm the instant VtResolve() first succeeds (&Target exists; EARLIEST -- and a
                         //     watchpoint costs nothing when it does not fire, so early arming has no price)
                         // 1 = arm at the TOP of DoPlay's one-shot !g_plInit block (before WireAbilitySystem)
                         // 2 = arm at g_plBodyDone (FK-24's original wording).  NOT recommended: L3830 is the
                         //     EXIT of the block whose interior the writer's window sits inside.
#endif
#ifndef KWPHOLDMS
#define KWPHOLDMS 0      // 0 = stay armed for the whole mode hold; >0 = auto-disarm + verdict after N ms
#endif
#ifndef KWPSWEEPMS
#define KWPSWEEPMS 250   // DR only: re-sweep period (arm new tids, RE-READ Dr7 on already-armed ones)
#endif
#ifndef KWPPOLLMS
#define KWPPOLLMS 2      // independent low-byte poller: the V5 void test + it bounds the write to 2 ms. 0=off
#endif
#ifndef KWPSELFTEST
#define KWPSELFTEST 1    // in-session POSITIVE CONTROL: two idempotent stores to &Target from the game thread
#endif
#ifndef KWPSELFWAITMS
// S108: how long WpSelfWatch waits for the positive control to produce a verdict. The old value was a
// hard-coded 8000, which is SHORTER than the one-shot RM_PLAY init block that owns the game thread at
// arming time -- so S107 declared the instrument void before the instrument had had a chance to run.
#define KWPSELFWAITMS 90000
#endif
#ifndef KWPMAXLOG
#define KWPMAXLOG 48     // full log lines for the first N &Target traps; after that, novel RIPs only
#endif
#ifndef KWPMAXTRAPS
#define KWPMAXTRAPS 4000000
#endif
#ifndef KWPMAXTPS
#define KWPMAXTPS 200000
#endif
#ifndef KWPSYNCLOG
#define KWPSYNCLOG 1     // write the corrupting event SYNCHRONOUSLY from the handler (pre-opened handle)
#endif
#ifndef KWPRETSCAN
#define KWPRETSCAN 1     // heuristic return-address scan for the full record (call-shaped predecessor filter)
#endif

#define WP_SINGLE_STEP ((DWORD)0x80000004L)
#define WP_GUARD_PAGE  ((DWORD)0x80000001L)
#define WP_AV          ((DWORD)0xC0000005L)

enum {  // trap-record flags
    WPF_TARGET  = 0x0001,   // the faulting/watched address is inside [&Target, &Target+8)
    WPF_SELF    = 0x0002,   // RIP is inside THIS DLL's mapped image  (tests "our own shim writes it")
    WPF_INMOD   = 0x0004,   // RIP is inside SUPERVIVE-Win64-Shipping.exe
    WPF_CORRUPT = 0x0008,   // post-store value at &Target is the measured corrupt shape (WHICH trap, not WHO)
    WPF_B0      = 0x0010,   // the byte-0 watchpoint fired
    WPF_B1      = 0x0020,   // the byte-1 watchpoint fired => the store was WIDER THAN ONE BYTE
    WPF_DR6ZERO = 0x0040,   // Dr6 read back 0 in the VEH ContextRecord (instrument caveat, see W-notes)
    WPF_PAGEOFF = 0x0080,   // page-mode trap elsewhere on the page (POV etc.) -- census only
    WPF_GAMETID = 0x0100,
    WPF_SELFTEST= 0x0200,   // D9: this trap was raised by a LABELLED selftest store (ground truth)
    WPF_SELFT1B = 0x0400    // ... and it was the 1-BYTE one (expect B0 only); else the 8-byte one (B0|B1)
};

#define WPRING 1024
struct WpRec { uint64_t seq, qpc, rip, addr, before, after; DWORD tid, flags, code, dr6; int full; };
static WpRec  g_wpRing[WPRING];
static volatile LONG g_wpSeq=0;          // total produced (producers)
static long   g_wpCursor=0;              // consumed (WpThread only)

struct WpFull {                          // the ONE record that carries identity, filled synchronously
    uint64_t qpc, rip, addr, before, after;
    uint64_t regs[16];                   // RAX..R15 -- "which register held the PCM" is half the attribution
    uint64_t ret[8]; int nret;
    uint8_t  pre[64], at[16];
    uint64_t dr0, dr1, dr2, dr3, dr6, dr7; DWORD ctxFlags;
    DWORD    tid, flags, code, tick;
    volatile LONG state;                 // 0=empty 1=filling 2=ready 3=drained
};
static WpFull g_wpFull[4];
static volatile LONG g_wpFullN=0;

static uintptr_t g_wpAddr=0, g_wpPage=0, g_wpPCM=0, g_wpPendTgt=0;
static uint32_t  g_wpPageSz=0x1000, g_wpVtOff=0xFFFFFFFF;
static volatile LONG g_wpArmed=0;        // 0 = not armed; 1 = armed (the ONLY gate on the VEH fast path)
static volatile LONG g_wpStorm=0, g_wpStop=0, g_wpArmReq=0, g_wpDisarmReq=0;
static DWORD g_wpOldProt=0;
static volatile LONG g_wpTraps=0, g_wpTrapsTgt=0, g_wpForeign=0, g_wpDr6Zero=0, g_wpDropped=0, g_wpTrapsSelf=0;
static volatile LONG g_wpCorruptTraps=0, g_wpPendSlotFull=0;
// ★ S108 — orphan single-steps swallowed by the terminal fallback in WpHandle (see there). Counted so
// the run reports how often the fallback had to save the process rather than hiding it.
static volatile LONG g_wpOrphanSwallowed=0;
// ── S107 review fixes ──────────────────────────────────────────────────────────────────────────────
// D3: WpDisarm used to clear g_wpArmed BEFORE walking ~140 threads to clear their DR7 (~3-5 ms). A DR
//     hit inside that window was declined by WpHandle and propagated as an UNHANDLED single-step, which
//     kills the process. Reachable mid-session via the `retarget` path (VtGuard's PCM-teardown stand-down
//     is a documented real event, S106c). The disarm now clears the HARDWARE first, and this grace tick
//     lets the handler keep swallowing steps that PROVABLY name our slots for a short window afterwards.
static volatile LONG g_wpGraceUntil=0;    // (LONG)GetTickCount() deadline; 0 = no grace
static volatile LONG g_wpGraceSwallow=0;  // steps swallowed during a grace window (not counted as traps)
// D4: if the VEH ContextRecord does not carry CONTEXT_DEBUG_REGISTERS we cannot read Dr6, so we cannot
//     tell our DR trap from somebody else's single-step. Claiming everything for the whole hold would
//     swallow the packer's own anti-debug stepping. TF is an architectural discriminator that survives
//     the missing Dr6: a DR *data* breakpoint does not set TF, so EFlags.TF set => it is a single-step
//     and NOT our data watchpoint. Both branches are counted and both are reported in the verdict.
static volatile LONG g_wpDr6ZeroClaimed=0, g_wpTfDeclined=0, g_wpDr6ZeroLogged=0;
// D9: WPF_SELFTEST was defined and never set, so a selftest trap was indistinguishable from VtGuard's own
//     repair store. This latch is raised immediately BEFORE each selftest store and consumed by the
//     handler, which labels the trap with GROUND TRUTH -- that is what makes the B0/B1 width discriminator
//     (the replacement for the retracted +0x3F) verifiable in-session instead of merely asserted.
static volatile LONG g_wpSelfStore=0;   // 0 = none, 1 = the 8-byte store, 2 = the 1-byte store
static uintptr_t g_wpSelfLo=0, g_wpSelfHi=0, g_wpModLo=0, g_wpModHi=0;
static HANDLE g_wpLogH=INVALID_HANDLE_VALUE;
static uint64_t g_wpDrBit0=0x1, g_wpDrBit1=0x2, g_wpDr7Val=0x00110005ULL;   // slot pair 0/1 by default
static int  g_wpDrPair=0;                                                    // 0 = DR0/DR1, 1 = DR2/DR3
static uint64_t g_wpPollLast=0;          // last 8 bytes the poller saw at &Target (the handler's "before" source)
static DWORD g_wpBodyTick=0;             // mirror of g_plBodyTick (declared ~2000 lines below); set at the body build
// page mode: every trap must OWN its TF, or the single-step it caused propagates unhandled and kills the
// process.  So a slot is claimed for EVERY page trap, not only the ones on &Target.  32 slots = 32 threads
// faulting at the same instant; the overflow path degrades safely (no TF, page left open for ~1 drain tick).
struct WpPend { volatile LONG tid; uint64_t rip, addr, before; int isTgt, selfTest; };
#define WPPEND 32
static WpPend g_wpPend[WPPEND];
static volatile LONG g_wpInRead=0;       // depth guard: a fault inside our OWN guarded probe read
static volatile LONG g_wpUnprot=0;       // page left unprotected by the overflow path -> WpThread re-arms

static uint64_t WpQpc(){ LARGE_INTEGER li; li.QuadPart=0; QueryPerformanceCounter(&li); return (uint64_t)li.QuadPart; }
// Write through the handle opened at ARM time. No CreateFileA, no allocation -> legal from the VEH.
static void WpLogf(const char* f,...){
    char b[1024]; va_list a; va_start(a,f); int n=_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a); va_end(a);
    if(n<0) n=(int)strlen(b);
    if(g_wpLogH!=INVALID_HANDLE_VALUE){ DWORD w=0; WriteFile(g_wpLogH,b,(DWORD)n,&w,nullptr); }
    else Marker(b);
}
// Reads that must never fault the game: no VirtualQuery (illegal on the trap path), just SEH.
static bool WpRead(const void* p,void* out,size_t n){
    InterlockedIncrement(&g_wpInRead);
    bool ok; __try{ memcpy(out,p,n); ok=true; } __except(EXCEPTION_EXECUTE_HANDLER){ ok=false; }
    InterlockedDecrement(&g_wpInRead); return ok;
}
static uint64_t WpRead8(uintptr_t p){ uint64_t v=0; return WpRead((void*)p,&v,8)?v:0; }
// The corrupt SHAPE, used ONLY to say which trap was the corrupting one (never as attribution):
// low byte == 0x01 AND the pointer is no longer 8-aligned.  Both are consequences of the measured
// one-byte store; neither is offered as evidence about the writer.
static bool WpCorruptShape(uint64_t v){ return (v&0xFF)==0x01 && (v&7)!=0; }

static void WpPush(uint64_t rip,uint64_t addr,uint64_t before,uint64_t after,DWORD tid,DWORD flags,DWORD code,DWORD dr6,int full){
    LONG s=InterlockedIncrement(&g_wpSeq);
    WpRec* r=&g_wpRing[(s-1)&(WPRING-1)];
    r->qpc=WpQpc(); r->rip=rip; r->addr=addr; r->before=before; r->after=after;
    r->tid=tid; r->flags=flags; r->code=code; r->dr6=dr6; r->full=full;
    r->seq=(uint64_t)s;                 // written LAST -> the consumer detects a torn / lapped slot
}
// RIP -> origin.  ★ Classifying against OUR OWN mapped image tests "the shim writes it" for free, and
// nobody has ever tested that.  A RIP in neither range is a packer-hidden private region -- exactly the
// shape strxref cannot reach (.text is 52.29% decrypted), and the reason the full record carries bytes.
static DWORD WpOriginFlags(uint64_t rip){
    DWORD f=0;
    if(g_wpSelfLo && rip>=g_wpSelfLo && rip<g_wpSelfHi) f|=WPF_SELF;
    if(g_wpModLo  && rip>=g_wpModLo  && rip<g_wpModHi ) f|=WPF_INMOD;
    return f;
}
#if KWPRETSCAN
// A filtered SCAN, not an unwind (no DbgHelp: heavy, needs symbols, unsafe in a VEH under this packer).
// Stack bounds come from the trapping thread's own TEB, which is valid because a VEH runs ON that thread.
// A qword is kept only if it points into the game module AND its predecessor bytes look like a call.
static int WpRetScan(uint64_t rsp,uint64_t* out,int cap){
    uint64_t base=__readgsqword(0x08), limit=__readgsqword(0x10);
    if(rsp<limit||rsp>=base) return 0;
    int n=0;
    for(uint64_t p=rsp; p+8<=base && p<rsp+512*8 && n<cap; p+=8){
        uint64_t v=0; if(!WpRead((void*)p,&v,8)) break;
        if(v<g_wpModLo||v>=g_wpModHi) continue;
        uint8_t pb[8]; if(!WpRead((void*)(v-8),pb,8)) continue;
        bool call = (pb[3]==0xE8);                                   // E8 rel32 (5 B): the call ENDS at v
        for(int k=1;k<7&&!call;k++){                                 // FF /2 (2..7 B): indirect call
            if(pb[7-k]!=0xFF) continue;
            uint8_t modrm=pb[8-k]; if(((modrm>>3)&7)==2) call=true; }
        if(call) out[n++]=v;
    }
    return n;
}
#endif
// Fill the ONE record that carries writer IDENTITY. Called only for &Target traps, budgeted.
static int WpCaptureFull(EXCEPTION_POINTERS* ep,uint64_t addr,uint64_t before,uint64_t after,DWORD flags,DWORD tick){
    LONG i=InterlockedIncrement(&g_wpFullN)-1;
    if(i<0||i>=(LONG)(sizeof(g_wpFull)/sizeof(g_wpFull[0]))) return -1;
    WpFull* F=&g_wpFull[i]; CONTEXT* c=ep->ContextRecord;
    F->state=1;
    F->qpc=WpQpc(); F->rip=c->Rip; F->addr=addr; F->before=before; F->after=after;
    F->regs[0]=c->Rax; F->regs[1]=c->Rcx; F->regs[2]=c->Rdx; F->regs[3]=c->Rbx;
    F->regs[4]=c->Rsp; F->regs[5]=c->Rbp; F->regs[6]=c->Rsi; F->regs[7]=c->Rdi;
    F->regs[8]=c->R8;  F->regs[9]=c->R9;  F->regs[10]=c->R10; F->regs[11]=c->R11;
    F->regs[12]=c->R12;F->regs[13]=c->R13;F->regs[14]=c->R14; F->regs[15]=c->R15;
    F->dr0=c->Dr0; F->dr1=c->Dr1; F->dr2=c->Dr2; F->dr3=c->Dr3; F->dr6=c->Dr6; F->dr7=c->Dr7;
    F->ctxFlags=c->ContextFlags; F->tid=GetCurrentThreadId(); F->flags=flags;
    F->code=ep->ExceptionRecord->ExceptionCode; F->tick=tick;
    memset(F->pre,0,sizeof(F->pre)); memset(F->at,0,sizeof(F->at));
    WpRead((void*)(c->Rip-64),F->pre,64);   // >=48 B of prefix is what makes the backward decode converge
    WpRead((void*)c->Rip,F->at,16);
    F->nret=0;
#if KWPRETSCAN
    F->nret=WpRetScan(c->Rsp,F->ret,8);
#endif
    F->state=2;
    return (int)i;
}
static void WpPanicDisarm();   // fwd (defined with the arm code)

// ★ THE VEH FRONT HALF.  Called FIRST from CrashVEH -- ahead of the fatal-crash path, which is left
// EXACTLY as it was.  Returns true (with *out) only when this exception is provably OURS.
static bool WpHandle(EXCEPTION_POINTERS* ep,DWORD code,LONG* out){
    bool armed = InterlockedCompareExchange(&g_wpArmed,0,0)!=0;
    if(!armed){
        // ★ D3 GRACE WINDOW.  WpDisarm now clears the HARDWARE first and the flag last, but a trap can
        // already be in flight when the flag goes down.  Declining it would return an unhandled
        // STATUS_SINGLE_STEP to the OS and kill the process.  Inside the grace window we still swallow
        // traps that PROVABLY name our slots -- but we do NOT record them, because coverage is over.
        LONG gu=InterlockedCompareExchange(&g_wpGraceUntil,0,0);
        if(!gu || (LONG)(GetTickCount()-(DWORD)gu)>=0){
#if KWPROBE==1
            // ★★ S108 TERMINAL FALLBACK — this is what killed S107's run, diagnosed from its own dump.
            // The debug registers live in the THREAD, not in g_wpArmed. Any path that leaves DR7 set on a
            // thread while the flag is down (a partial/failed disarm, a second probe image owning the
            // flag, the packer restoring a context) turns the very next store to &Target into a
            // STATUS_SINGLE_STEP that WpHandle DECLINES -- and an unhandled single-step terminates the
            // process. MEASURED in dump 166396E2: exception 0x80000004, Dr7 == g_wpDr7Val, Dr6 low nibble
            // = B0|B1, RIP one byte past the probe's own `mov [rbx],r14` selftest store, 127/128 threads
            // still armed. The kill was the instrument, and it was read as a game crash.
            // So: if the hardware PROVABLY names our slots AND Dr0 still holds our address, swallow it
            // even with the flag down. We do NOT record it as coverage -- the run is over as a
            // measurement; this only stops the instrument from killing its own host.
            if(code==WP_SINGLE_STEP){
                CONTEXT* cc=ep->ContextRecord;
                if((cc->ContextFlags&CONTEXT_DEBUG_REGISTERS)==CONTEXT_DEBUG_REGISTERS){
                    uint64_t mine0=g_wpDrBit0|g_wpDrBit1;
                    if((cc->Dr6&mine0) && g_wpAddr && cc->Dr0==(DWORD64)g_wpAddr){
                        cc->Dr6 &= ~mine0;
                        InterlockedIncrement(&g_wpOrphanSwallowed);
                        *out=EXCEPTION_CONTINUE_EXECUTION; return true;
                    }
                }
            }
#endif
#if KWPROBE==2
            // ★★ S108b — THE PAGE-MODE HALF OF D-S108-3, which the first fix missed. Page protection is a
            // property of the ADDRESS SPACE, not of g_wpArmed, exactly as debug registers are a property of
            // the thread. If the flag goes down while the page is still PAGE_READONLY, the next write to
            // ANY of the ~4 KB (ViewTarget.POV lives there and is written every frame) faults, WpHandle
            // declines, and the unhandled AV kills the process. MEASURED 2026-08-04: dump FED1F952 is this
            // shim self-killing in page mode. Shipping the DR fallback alone left `_wprobe2*.dll` lethal.
            if(code==0xC0000005 && ep->ExceptionRecord->NumberParameters>=2
               && ep->ExceptionRecord->ExceptionInformation[0]==1){          // 1 = write access
                uintptr_t fa=(uintptr_t)ep->ExceptionRecord->ExceptionInformation[1];
                if(g_wpPage && fa>=g_wpPage && fa<g_wpPage+g_wpPageSz){
                    DWORD old=0;
                    if(VirtualProtect((void*)g_wpPage,g_wpPageSz,g_wpOldProt?g_wpOldProt:PAGE_READWRITE,&old)){
                        InterlockedIncrement(&g_wpOrphanSwallowed);
                        *out=EXCEPTION_CONTINUE_EXECUTION; return true;      // retry the store, now writable
                    }
                }
            }
#endif
            return false;
        }
    }
    CONTEXT* c=ep->ContextRecord; DWORD tid=GetCurrentThreadId();
#if KWPROBE==1
    // ---- DR data breakpoints are TRAPS: the store HAS retired and Rip is the NEXT instruction. -----
    if(code!=WP_SINGLE_STEP) return false;
    // *** Only trust / write Dr* if the kernel actually SUPPLIED them. OR-ing CONTEXT_DEBUG_REGISTERS
    //     into ContextFlags when it is absent makes NtContinue write this CONTEXT's GARBAGE Dr fields
    //     back to the thread -- the instrument would silently DISARM ITSELF and look exactly like
    //     "the packer cleared DR". That is a false-known of precisely the shape this project keeps
    //     hitting, so it is handled explicitly rather than assumed.
    bool dbgOk=((c->ContextFlags&CONTEXT_DEBUG_REGISTERS)==CONTEXT_DEBUG_REGISTERS);
    uint64_t dr6=dbgOk?c->Dr6:0, mine=g_wpDrBit0|g_wpDrBit1;
    if(dr6 && !(dr6&mine)){ InterlockedIncrement(&g_wpForeign); return false; }   // BS-only / another slot: NOT ours
    if(!dr6){
        // ★ D4 -- Dr6 IS UNREADABLE, so "is this trap ours?" has no direct answer.  Claiming EVERY
        // single-step for the whole hold would swallow the packer's own anti-debug stepping.  Bound it
        // with the one discriminator that survives a missing Dr6: a DR *data* breakpoint is a trap and
        // does NOT set EFlags.TF, so TF set here means this is somebody else's single-step -- hand it
        // straight back.  The residue is counted and the verdict reports the run as instrument-suspect.
        // (No I/O here: the loud one-time line is emitted by WpThread off the counter.)
        if(c->EFlags&0x100u){ InterlockedIncrement(&g_wpTfDeclined); InterlockedIncrement(&g_wpForeign); return false; }
        InterlockedIncrement(&g_wpDr6ZeroClaimed);
    }
    if(!armed){                                  // D3: in-flight hit after the hardware was cleared
        if(dbgOk) c->Dr6=0; InterlockedIncrement(&g_wpGraceSwallow);
        *out=EXCEPTION_CONTINUE_EXECUTION; return true;
    }
    DWORD flags=WPF_TARGET|WpOriginFlags(c->Rip);
    if(!dr6){ InterlockedIncrement(&g_wpDr6Zero); flags|=WPF_DR6ZERO; }           // instrument caveat, reported
    { LONG ss=InterlockedExchange(&g_wpSelfStore,0);                              // D9: ground-truth label
      if(ss){ flags|=WPF_SELFTEST; if(ss==2) flags|=WPF_SELFT1B; } }
    if(dr6&g_wpDrBit0) flags|=WPF_B0;
    if(dr6&g_wpDrBit1) flags|=WPF_B1;                 // DR0 alone = 1-BYTE store; DR0|DR1 = wider store
    if(tid==g_gameTid) flags|=WPF_GAMETID;
    uint64_t after=WpRead8(g_wpAddr), before=g_wpPollLast;
    if(WpCorruptShape(after)&&!WpCorruptShape(before)){ flags|=WPF_CORRUPT; InterlockedIncrement(&g_wpCorruptTraps); }
    InterlockedIncrement(&g_wpTraps); InterlockedIncrement(&g_wpTrapsTgt);
    if(flags&WPF_SELF) InterlockedIncrement(&g_wpTrapsSelf);
    int fi=-1;
    if((flags&WPF_CORRUPT)||InterlockedCompareExchange(&g_wpFullN,0,0)<2)
        fi=WpCaptureFull(ep,g_wpAddr,before,after,flags,GetTickCount());
    WpPush(c->Rip,g_wpAddr,before,after,tid,flags,code,(DWORD)dr6,fi);
#if KWPSYNCLOG
    if(flags&WPF_CORRUPT)
        WpLogf("[WP] *** CORRUPTING STORE (sync) tid=%lu rip=0x%llX rva=0x%llX dr6=0x%llX %s before=0x%llX after=0x%llX full#%d ***\r\n",
               (unsigned long)tid,(unsigned long long)c->Rip,
               (unsigned long long)((c->Rip>=g_wpModLo&&c->Rip<g_wpModHi)?c->Rip-g_wpModLo:0),
               (unsigned long long)dr6,(flags&WPF_B1)?"B0+B1(WIDE store)":"B0-only(ONE-BYTE store)",
               (unsigned long long)before,(unsigned long long)after,fi);
#endif
    if(dbgOk) c->Dr6=0;                         // ack. NEVER OR the flag in when it was absent (see above)
    *out=EXCEPTION_CONTINUE_EXECUTION; return true;
#elif KWPROBE==2
    // ---- PAGE_READONLY faults are FAULTS: the store has NOT executed and Rip IS the storing insn. ---
    if(code==WP_AV){
        if(ep->ExceptionRecord->NumberParameters<2) return false;
        uint64_t acc=ep->ExceptionRecord->ExceptionInformation[0];
        uint64_t fa =ep->ExceptionRecord->ExceptionInformation[1];
        if(acc!=1) return false;                                              // reads do not fault under READONLY
        if((fa&~(uint64_t)(g_wpPageSz-1))!=(uint64_t)g_wpPage) return false;  // not our page -> REAL crash path
        if(!armed){   // D3 grace: disarm already restored the page; just let this in-flight store retire
            DWORD tmp=0; VirtualProtect((void*)g_wpPage,g_wpPageSz,g_wpOldProt?g_wpOldProt:PAGE_READWRITE,&tmp);
            InterlockedIncrement(&g_wpGraceSwallow);
            *out=EXCEPTION_CONTINUE_EXECUTION; return true;
        }
        LONG n=InterlockedIncrement(&g_wpTraps);
        bool tgt=(fa>=g_wpAddr&&fa<g_wpAddr+8);
        DWORD flags=WpOriginFlags(c->Rip)|(tgt?WPF_TARGET:WPF_PAGEOFF)|((tid==g_gameTid)?WPF_GAMETID:0);
        if(tgt){ InterlockedIncrement(&g_wpTrapsTgt); if(flags&WPF_SELF) InterlockedIncrement(&g_wpTrapsSelf); }
        // ★ Claim a TF slot for EVERY trap, target or not. TF must be OWNED: an unowned single-step is
        //   returned to the packer and kills the process. (This was a real defect in the first draft.)
        int slot=-1;
        for(int i=0;i<WPPEND;i++) if(InterlockedCompareExchange(&g_wpPend[i].tid,(LONG)tid,0)==0){ slot=i; break; }
        DWORD tmp=0; VirtualProtect((void*)g_wpPage,g_wpPageSz,PAGE_READWRITE,&tmp);   // let the store retire
        if(slot<0){
            // Overflow: degrade SAFELY -- no TF, page left open until WpThread re-arms it (~5 ms). We lose
            // the post-store value for this one trap; we never hang and never hand back a stray step.
            InterlockedIncrement(&g_wpPendSlotFull); InterlockedExchange(&g_wpUnprot,1);
            if(n>KWPMAXTRAPS) WpPanicDisarm();
            *out=EXCEPTION_CONTINUE_EXECUTION; return true;
        }
        g_wpPend[slot].rip=c->Rip; g_wpPend[slot].addr=fa; g_wpPend[slot].isTgt=tgt?1:0;
        // D9: in page mode the fault happens AT the store, so the selftest latch is live right now --
        // consume it here and carry the label through to the TF step that emits the record.
        g_wpPend[slot].selfTest=(int)InterlockedExchange(&g_wpSelfStore,0);
        g_wpPend[slot].before=tgt?WpRead8(g_wpAddr):0;
        c->EFlags|=0x100;                                                              // TF: trap after it
        if(n>KWPMAXTRAPS) WpPanicDisarm();
        *out=EXCEPTION_CONTINUE_EXECUTION; return true;
    }
    if(code==WP_SINGLE_STEP){
        int slot=-1; for(int i=0;i<WPPEND;i++) if(InterlockedCompareExchange(&g_wpPend[i].tid,0,0)==(LONG)tid){ slot=i; break; }
        if(slot<0){ InterlockedIncrement(&g_wpForeign); return false; }   // NOT ours: never touch TF/protection
        c->EFlags&=~0x100u;
        if(!armed){   // D3 grace: we set this TF, so we must clear it -- but never RE-ARM after a disarm
            InterlockedExchange(&g_wpPend[slot].tid,0); InterlockedIncrement(&g_wpGraceSwallow);
            *out=EXCEPTION_CONTINUE_EXECUTION; return true;
        }
        DWORD tmp=0; VirtualProtect((void*)g_wpPage,g_wpPageSz,PAGE_READONLY,&tmp);    // re-arm
        if(g_wpPend[slot].isTgt){
            uint64_t after=WpRead8(g_wpAddr), before=g_wpPend[slot].before;
            DWORD flags=WPF_TARGET|WpOriginFlags(g_wpPend[slot].rip)|((tid==g_gameTid)?WPF_GAMETID:0);
            if(g_wpPend[slot].selfTest){ flags|=WPF_SELFTEST; if(g_wpPend[slot].selfTest==2) flags|=WPF_SELFT1B; }
            if(WpCorruptShape(after)&&!WpCorruptShape(before)){ flags|=WPF_CORRUPT; InterlockedIncrement(&g_wpCorruptTraps); }
            int fi=-1;
            if((flags&WPF_CORRUPT)||InterlockedCompareExchange(&g_wpFullN,0,0)<2){
                uint64_t saveRip=c->Rip; c->Rip=g_wpPend[slot].rip;     // capture bytes AT THE STORE, not after
                fi=WpCaptureFull(ep,g_wpAddr,before,after,flags,GetTickCount()); c->Rip=saveRip; }
            WpPush(g_wpPend[slot].rip,g_wpAddr,before,after,tid,flags,code,0,fi);
#if KWPSYNCLOG
            if(flags&WPF_CORRUPT)
                WpLogf("[WP] *** CORRUPTING STORE (sync) tid=%lu rip=0x%llX rva=0x%llX before=0x%llX after=0x%llX full#%d ***\r\n",
                       (unsigned long)tid,(unsigned long long)g_wpPend[slot].rip,
                       (unsigned long long)((g_wpPend[slot].rip>=g_wpModLo&&g_wpPend[slot].rip<g_wpModHi)?g_wpPend[slot].rip-g_wpModLo:0),
                       (unsigned long long)before,(unsigned long long)after,fi);
#endif
            InterlockedExchange(&g_wpPend[slot].tid,0);
            *out=EXCEPTION_CONTINUE_EXECUTION; return true;
        }
        // TF step with no pending of ours: we still had to clear TF/re-arm above (we set it), but if this
        // is somebody ELSE's single-step we must not swallow it.
        InterlockedIncrement(&g_wpForeign);
        return false;
    }
    return false;
#else
    (void)c; (void)tid; (void)code; (void)out; return false;
#endif
}
#endif  // KWPROBE
// ═══════════════════════════ end FK-24 watchpoint probe (front half) ════════════════════════════════
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode;
#if KWPROBE
    // Probe traps are claimed FIRST and returned with CONTINUE_EXECUTION. Everything the probe does not
    // claim falls through to the fatal path below, which is UNCHANGED.
    { LONG r=EXCEPTION_CONTINUE_SEARCH; if(WpHandle(ep,code,&r)) return r; }
    // A fault inside one of the probe's OWN SEH-guarded reads (WpRead) is caught by its __except; it must
    // not burn the 4-entry g_crashSeq budget or print a misleading [NULL]. Placed AFTER WpHandle so a real
    // page trap is never suppressed by it.
    if(code==0xC0000005 && InterlockedCompareExchange(&g_wpInRead,0,0)) return EXCEPTION_CONTINUE_SEARCH;
#endif
    bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
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
// ★★★ S91 — THE BLUEPRINT-FUNCTION CALL PRIMITIVE (the missing half of the S55 native-call primitive).
// The S55 primitive calls a UFunction's `Func` thunk (@+0xE0) with FFrame.Code = NULL. That is correct for a NATIVE
// thunk, and fatal for a BLUEPRINT function — a BP UFunction's `Func` IS `ProcessInternal`, so Code=NULL makes the
// VM start executing at address 0. Every function on the tutorial-quest chain is bytecode, which is exactly why the
// quests spawn but nothing can start them.
// FIX: do what `UObject::ProcessEvent` itself does — set FFrame.Code to the function's OWN bytecode
// (`UStruct.Script.Data` @+0x68) and FFrame.Locals to a zeroed blob of `UStruct.PropertiesSize` (@+0x60) bytes, then
// call the same `Func` thunk. No new address to guess: this sidesteps the ProcessEvent-RVA question that S80
// falsified. Params are written into the locals blob at each FProperty's Offset_Internal, exactly as for natives.
static uint8_t g_bplocals[0x800]={0};
static bool CallBPGuarded(uintptr_t func, void* context, void* resultBuf){
    if(!LooksLikePtr(func)||!SafeReadable((void*)(func+USTRUCT_SCRIPT),8)) return true;
    uintptr_t script=*(uintptr_t*)(func+USTRUCT_SCRIPT);
    uint32_t  snum  =SafeReadable((void*)(func+USTRUCT_SCRIPTNUM),4)?*(uint32_t*)(func+USTRUCT_SCRIPTNUM):0;
    uint32_t  psize =SafeReadable((void*)(func+USTRUCT_PROPSIZE),4)?*(uint32_t*)(func+USTRUCT_PROPSIZE):0;
    uintptr_t thunk =SafeReadable((void*)(func+UFUNC_FUNC),8)?*(uintptr_t*)(func+UFUNC_FUNC):0;
    uintptr_t child =SafeReadable((void*)(func+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(func+UFUNC_CHILDPROPS):0;
    if(!LooksLikePtr(script)||!snum||!LooksLikePtr(thunk)||psize>sizeof(g_bplocals)){
        Markerf("[BPC] refuse: script=0x%llX num=%u propsSize=%u thunk=0x%llX\r\n",
            (unsigned long long)script,snum,psize,(unsigned long long)thunk); return true; }
    __try{
        memcpy(g_myframe,g_template,sizeof(g_myframe));
        *(void**)(g_myframe+FF_NODE)=(void*)func;
        *(void**)(g_myframe+FF_OBJECT)=context;
        *(uint64_t*)(g_myframe+FF_CODE)=(uint64_t)script;      // ← the whole point: run the function's OWN bytecode
        *(void**)(g_myframe+FF_LOCALS)=g_bplocals;
        *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
        *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)child;
        BuildOutParms(child,g_bplocals);
        ((PFN_THUNK)thunk)(context,g_myframe,resultBuf);
        return false;
    } __except(SehDump(GetExceptionInformation())){ return true; }
}
// Resolve a BP UFunction by name over the class + super chain (BP overrides included — the opposite of
// ResolveFuncNative, which deliberately skips BP_* classes).
static void ResolveFuncSuper(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child);   // fwd
static uintptr_t FindBPFunc(uintptr_t cls,const char* name,uintptr_t* childOut){
    void* fn=nullptr; uintptr_t th=0,ch=0;
    ResolveFuncSuper(cls,name,&fn,&th,&ch);
    if(childOut)*childOut=ch;
    return (uintptr_t)fn;
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
    if(kRunMode==RM_SPAWNSEQ){ DoSpawnSeq(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoSpawnSeq
    if(kRunMode==RM_SPAWNQUEST){ DoSpawnQuest(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoSpawnQuest
    if(kRunMode==RM_QUESTPLAY){ DoQuestPlay(); InterlockedIncrement(&g_called); g_inHook=0; return; }     // g_done set inside DoQuestPlay
    if(kRunMode==RM_BPCALL){ DoBPCall(); InterlockedIncrement(&g_called); g_inHook=0; return; }         // g_done set inside DoBPCall
    if(kRunMode==RM_OBJDRIVE){ DoObjDrive(); InterlockedIncrement(&g_called); g_inHook=0; return; }     // g_done set inside DoObjDrive
    if(kRunMode==RM_OBJCOMPLETE){ DoObjComplete(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoObjComplete
    if(kRunMode==RM_FIREOVERLAP){ DoFireOverlap(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoFireOverlap
    if(kRunMode==RM_DRIVECHAIN){ DoDriveChain(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoDriveChain
    if(kRunMode==RM_CAMERA){ DoCamera(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoCamera
    if(kRunMode==RM_TOPDOWNCAM){ DoTopDownCam(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // holds until worker timeout (no g_done)
    if(kRunMode==RM_MESHCAM){ DoMeshCam(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // holds until worker timeout (no g_done)
    if(kRunMode==RM_DROPIN){ DoDropIn(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoDropIn
    if(kRunMode==RM_MAKEMESH){ DoMakeMesh(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // g_done set inside DoMakeMesh
    if(kRunMode==RM_PLAY){ DoPlay(); InterlockedIncrement(&g_called); g_inHook=0; return; }   // holds until worker timeout (no g_done) — camera + WASD each hit
    if(kRunMode==RM_TRAINING){ DoTraining(); InterlockedIncrement(&g_called); g_inHook=0; return; }       // g_done set inside DoTraining (one step per hit)
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
// ★ S106 — PI-HOOK MUTEX. CLAUDE.md's rule is that every ProcessInternal-hooking shim must serialise its
// 5-byte prologue jmp through the shared named mutex "Local\SuperviveMissionsPIHook" (mainmenu_refresh_pi8,
// missions_fix and loadout_fix all do). tutorial_launch NEVER TOOK IT — measured 2026-07-27: zero
// CreateMutex/SuperviveMissionsPIHook references in this file. If any of those three is injected while a
// tutorial mode holds the hook, the two shims clobber each other's stolen prologue. Every mode goes through
// InstallHook/UninstallHook, so taking it here covers all ~23 of them with one change.
// NOTE the deliberate asymmetry with the menu shims: they hold the lock for ONE game-thread call; tutorial
// modes hold the hook for 20 s..10 min, so this WILL block a menu shim for that long. That is the correct
// behaviour (blocking beats clobbering), but it is why the wait is bounded: if the lock cannot be taken in
// KPIMUTEXMS we log loudly and proceed unlocked, i.e. exactly today's behaviour, never a new hard failure.
#ifndef KPIMUTEX
#define KPIMUTEX 1            // -DKPIMUTEX=0 -> A/B: restore the pre-S106 unsynchronised behaviour
#endif
#ifndef KPIMUTEXMS
#define KPIMUTEXMS 30000
#endif
static HANDLE g_hookMutex=nullptr; static bool g_hookLocked=false;
static void HookLock(){
#if KPIMUTEX
    if(!g_hookMutex) g_hookMutex=CreateMutexA(nullptr,FALSE,"Local\\SuperviveMissionsPIHook");
    if(!g_hookMutex){ Markerf("[PIM] CreateMutex failed (%lu) -> proceeding UNLOCKED\r\n",GetLastError()); return; }
    DWORD w=WaitForSingleObject(g_hookMutex,KPIMUTEXMS);
    if(w==WAIT_OBJECT_0||w==WAIT_ABANDONED){ g_hookLocked=true; Markerf("[PIM] PI hook mutex acquired (%s)\r\n",w==WAIT_ABANDONED?"abandoned":"clean"); }
    else Markerf("[PIM] *** PI hook mutex TIMEOUT after %d ms -> installing UNLOCKED (another PI-hooking shim may clobber us) ***\r\n",(int)KPIMUTEXMS);
#endif
}
static void HookUnlock(){
#if KPIMUTEX
    if(g_hookLocked&&g_hookMutex){ ReleaseMutex(g_hookMutex); g_hookLocked=false; Marker("[PIM] PI hook mutex released\r\n"); }
#endif
}
static bool InstallHook(){ if(!g_pi||!g_stub)return false; HookLock(); int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5)); uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)}; bool ok=SafeWrite(g_pi,p,5); if(!ok) HookUnlock(); return ok; }
static void UninstallHook(){ if(g_pi)SafeWrite(g_pi,g_stolen,5); HookUnlock(); }
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
// ================= S106 — GC ROOT GUARD (the FK-7 worker-thread crash) ==========================
// MEASURED (2026-07-27, from the 86-dump crash corpus under %LOCALAPPDATA%\SUPERVIVE\Saved\Crashes).
// Reproduce every number below with tools/re/crash_corpus.py (survey | cluster | ctx <GUID> | mem):
//
//   Five 2026-07-26 crashes on task-graph worker threads ("Foreground/Background Worker #N") all fault
//   at the SAME instruction, RVA 0x349596D:
//       0x3495960  mov rbx,[r15+rsi*8]      ; FAnimSync::UngroupedActivePlayerArrays[WriteIdx].Data
//       0x3495964  add rbx,r14              ; + i*0x70   (sizeof FAnimTickRecord == 0x70, from `add r14,0x70`)
//       0x3495967  mov rcx,[rbx]            ; FAnimTickRecord.SourceAsset  (UAnimationAsset*)
//       0x349596A  mov rax,[rcx]            ; its VTABLE
//       0x349596D  call [rax+0x2F8]         ; <-- FAULT
//   The containing function 0x3494B40 is UE's FAnimSync::TickAssetPlayerInstances (identified by the
//   literals it touches: "Ticking Group [%s] GroupLeader [%d]", "Invalid position from Leader %d.
//   Trying next leader", "[PreviousMarker %s, NextMarker %s] : %0.2f").
//
//   In every one of the five dumps the SourceAsset object is DESTRUCTED AND FREED:
//     * [obj+0x00] (the vtable) holds a HEAP pointer that chains to further same-size blocks -> the
//       allocator free-list link that FMalloc writes over a freed block's first qword;
//     * [obj+0x20] (NamePrivate) == 0 -> UObjectBase::~UObjectBase() ran (it does LowLevelRename(NAME_None));
//     * [obj+0x18] (ClassPrivate) is still intact and IDENTICAL across independent launches;
//     * [obj+0x30] and [obj+0x38] are two module .rdata vtables (RVA 0x7CA73C0 / 0x7F2F208) — the
//       IInterface_AssetUserData / IInterface_PreviewMeshProvider mixin vtables that sit right after the
//       UObject subobject of a UAnimationAsset.
//   The tick record itself is intact and reads PlayRate=1.0, BlendWeight=1.0, bLooping=1 — i.e. exactly
//   what PlayAnimOn's PlayAnimation(anim, bLooping=true) installs, and there is exactly ONE ungrouped
//   record (Num=1), i.e. the single-node instance.
//   Faulting addresses: EXECUTE at a heap address (0x2549be0ce00 / 0x245775fb200 / 0x1cbe83cd400),
//   EXECUTE at 0, or a read fault — all three are the same event with different free-list residue.
//
//   TIMING (measured from each crash's own Loki.log): the tutorial map finishes loading at T+121..128 s,
//   the game sets gc.TimeBetweenPurgingPendingKillObjects = 61.1, and EVERY crash lands at T+173..201 s
//   — the first garbage collection after the shim builds the hero. Nothing the shim loads is visible to
//   UE's GC: LoadMeshByPath goes through UKismetSystemLibrary::LoadAsset_Blocking, which returns a raw
//   UObject* and holds no reference, and the result lives only in this DLL's plain C globals.
//
// FIX: put every UObject this shim loads (and, optionally, the component + anim instance it drives) into
// UE's GC root set, the same thing UObject::AddToRoot() does — it sets EInternalObjectFlags::RootSet in
// the object's FUObjectItem, which lives in GUObjectArray, NOT in the UObject.
//
// The RootSet bit value is NOT hardcoded blind: GcResolveBit() MEASURES it live (see below) and REFUSES
// to poke anything unless the measurement corroborates the compile-time constant. A wrong bit could set
// Unreachable/Garbage and make things worse, so "refuse and log" is the failure mode, never "guess".
#ifndef KGCROOT
#define KGCROOT 1            // -DKGCROOT=0 -> A/B: build with the guard OFF (reproduces the S106 crash)
#endif
#ifndef KGCROOTCOMP
#define KGCROOTCOMP 1        // also root the body SkeletalMeshComponent + its UAnimSingleNodeInstance
#endif
#ifndef KGCROOTBIT
#define KGCROOTBIT 0x40000000   // EInternalObjectFlags::RootSet == 1<<30 (stable UE4/UE5). Corroborated live.
#endif
#ifndef KGCROOTMAXPCT
#define KGCROOTMAXPCT 33     // S109: max %% of randomly-sampled ordinary objects that may carry KGCROOTBIT
                             // and still have it accepted as RootSet. Ordinary objects CAN be rooted
                             // (GameInstance, subsystems, anything that called AddToRoot), so the old
                             // "none of them may have it" test vetoed the correct bit on 1 contaminated
                             // sample in 64. RootSet is rare among random objects; a generic flag is not.
#endif
#ifndef KGCROOTSTRICT
#define KGCROOTSTRICT 0      // 1 = restore the pre-S109 AND(rooted)&~OR(unrooted) test, for A/B
#endif
static int32_t g_gcBit=0; static bool g_gcRes=false; static int g_gcRooted=0, g_gcFailed=0;
static bool SafeWritable(const void* a,size_t sz){
#if KWPROBE==2
    // ★ S107 FK-24 PROBE EXEMPTION -- LOAD-BEARING, do not delete when reading this function.
    // KWPROBE=2 flips the PCM's page to PAGE_READONLY, which this predicate would otherwise reject.
    // The one caller that matters is VtGuard's repair store (see its "[VTG] slot not writable" branch):
    // without this exemption the probe would SILENTLY DISABLE THE GUARD for its whole armed window --
    // an instrument changing the thing it measures, and the exact reason PAGE_GUARD was rejected.
    // The write is genuinely safe: it faults, WpHandle unprotects, single-steps it, re-protects; the
    // store lands, and it is logged origin=SELF (and doubles as a positive control on &Target).
    if(InterlockedCompareExchange(&g_wpArmed,0,0) && g_wpPage &&
       (uintptr_t)a>=g_wpPage && (uintptr_t)a+sz<=g_wpPage+g_wpPageSz) return true;
#endif
    MEMORY_BASIC_INFORMATION m{}; if(!VirtualQuery(a,&m,sizeof(m)))return false;
    if(!(m.State&MEM_COMMIT))return false; if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;
    const DWORD wr=PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY;
    if(!(m.Protect&wr))return false;
    return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;
}
// obj -> &FUObjectItem (Object@0x00, Flags@0x08, ClusterRootIndex@0x0C, SerialNumber@0x10; stride 0x18).
static uintptr_t GcFindItem(uintptr_t obj){
    if(!LooksLikePtr(obj))return 0;
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,0x10))continue;
            if(*(uintptr_t*)item==obj) return item; } }
    return 0;
}
static bool GcItemFlags(uintptr_t obj,int32_t* out){
    uintptr_t it=GcFindItem(obj); if(!it)return false; *out=*(int32_t*)(it+8); return true;
}
// Derive the RootSet bit from the LIVE array instead of trusting a constant.
//  * ROOTED reference set  = native UClasses. UE allocates every native class with RF_MarkAsRootSet, which
//    StaticAllocateObject converts into EInternalObjectFlags::RootSet, so the bit must be set on all of them.
//  * "UNROOTED" reference set = ordinary live objects (not a UClass, not a "Default__" CDO).
//
// ★ S109 FIX (2026-08-05) — the second reference set was built on a FALSE PREMISE and the whole guard
//   had been silently inert because of it. The old test was
//        cand = AND(rooted) & ~OR(unrooted) & 0xFF000000     // accept iff cand contains KGCROOTBIT
//   and its comment asserted ordinary objects "must not have" RootSet. They can, and routinely do:
//   anything that called AddToRoot -- the GameInstance, engine subsystems, config and manager objects --
//   is an ordinary non-class object that is legitimately in the root set. The filter only excluded
//   Class/Package/Function/Enum/ScriptStruct and Default__ CDOs, so those slipped straight in.
//
//   MEASURED live, 3/3 tutorial sittings (docs/s109-dump-forensics.md sections 22-23):
//        nRooted=5 and=42000000  nUnrooted=64 or=41000004  cand=02000000  expect=40000000
//   AND(rooted) = 0x42000000 CONTAINS 0x40000000: RootSet is set on all five native classes, exactly as
//   the theory says. But OR(unrooted) = 0x41000004 also has bit 30, so `& ~orU` stripped it and the
//   surviving candidate was 0x02000000 = EInternalObjectFlags::Native (1<<25). The guard then refused,
//   nothing was ever rooted, and the run AnimSequence was collected 6.9-10.3 s after body build --
//   which is what killed the locomotion animation.
//   ONE contaminated sample out of 64 was enough to veto the bit. A hard OR has no tolerance at all.
//
//   THE FIX: keep the strong half (the bit must be set on EVERY native class) and replace the brittle
//   half with a FREQUENCY test. RootSet is rare among randomly sampled objects; a generic flag is not.
//   So require freq(bit)/nU <= KGCROOTMAXPCT. That is the property the original was reaching for.
//   The Native bit (1<<25) still survives the AND, which is why the accepted bit is still required to be
//   KGCROOTBIT rather than "whatever survived" -- we never poke a bit we merely inferred.
//   -DKGCROOTSTRICT=1 restores the old AND/~OR behaviour for A/B.
static bool GcResolveBit(){
    if(g_gcRes) return g_gcBit!=0;
    g_gcRes=true;
    static const char* kRooted[]={"Object","Actor","AnimSequence","SkeletalMeshComponent","Package"};
    int32_t andR=(int32_t)0xFFFFFFFF; int nR=0;
    for(int i=0;i<(int)(sizeof(kRooted)/sizeof(kRooted[0]));i++){
        uintptr_t c=FindClassExact(kRooted[i]); if(!c)continue; int32_t f=0; if(!GcItemFlags(c,&f))continue;
        andR&=f; nR++; }
    int32_t orU=0; int nU=0; int nUbit=0;   // S109: nUbit = how many sampled objects carry KGCROOTBIT
    { uintptr_t oo=g_modBase+kObjObjectsRva;
      if(SafeReadable((void*)oo,0x18)){
        uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
        if(LooksLikePtr(objectsPtr)&&numEl>0&&numEl<8000000){ int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
          for(int ci=0;ci<numChunks&&nU<64;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;
            uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue;
            int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
            for(int j=0;j<cnt&&nU<64;j+=997){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE;
              if(!SafeReadable((void*)item,0x10))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
              uintptr_t cls=ClassOf(obj); if(!LooksLikePtr(cls))continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
              if(strstr(cn,"Class")||strstr(cn,"Package")||strstr(cn,"Function")||strstr(cn,"Enum")||strstr(cn,"ScriptStruct"))continue;
              char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
              { int32_t uf=*(int32_t*)(item+8); orU|=uf;
                if(uf&(int32_t)KGCROOTBIT) nUbit++; }              // S109: COUNT it, don't just OR it
              nU++; } } } } }
    int32_t cand = andR & ~orU & (int32_t)0xFF000000;
    int pct = (nU>0) ? (nUbit*100)/nU : 100;
#if KGCROOTSTRICT
    // legacy behaviour, kept for A/B: any single rooted sample vetoes the bit
    bool ok = (nR>=2 && nU>=8 && (cand & (int32_t)KGCROOTBIT));
    const char* how="STRICT(AND&~OR)";
#else
    // S109: the bit must be universal on native classes, and RARE among ordinary objects.
    bool ok = (nR>=2 && nU>=8 && (andR & (int32_t)KGCROOTBIT) && pct<=KGCROOTMAXPCT);
    const char* how="FREQ";
#endif
    g_gcBit = ok ? (int32_t)KGCROOTBIT : 0;
    Markerf("[GC] rootbit[%s]: nRooted=%d and=%08X nUnrooted=%d or=%08X cand=%08X expect=%08X"
            " onNatives=%d bitFreq=%d/%d(%d%%) max=%d%% -> %s\r\n",
            how,nR,(unsigned)andR,nU,(unsigned)orU,(unsigned)cand,(unsigned)KGCROOTBIT,
            (andR&(int32_t)KGCROOTBIT)?1:0,nUbit,nU,pct,(int)KGCROOTMAXPCT,
            g_gcBit?"CORROBORATED (rooting enabled)":"NOT corroborated -> REFUSING to poke flags");
    return g_gcBit!=0;
}
// AddToRoot(obj). Returns true only when the bit reads back set.
static bool GcRoot(uintptr_t obj,const char* tag){
#if !KGCROOT
    (void)obj; (void)tag; return false;
#else
    if(!LooksLikePtr(obj)) return false;
    if(!GcResolveBit()){ Markerf("[GC] %s 0x%llX NOT rooted (bit unresolved)\r\n",tag,(unsigned long long)obj); g_gcFailed++; return false; }
    uintptr_t item=GcFindItem(obj);
    if(!item){ Markerf("[GC] %s 0x%llX has no FUObjectItem -> NOT rooted\r\n",tag,(unsigned long long)obj); g_gcFailed++; return false; }
    char cn[96]="-"; if(LooksLikePtr(ClassOf(obj))) GetFNameStr(NameId(ClassOf(obj)),cn,sizeof(cn));
    int32_t before=*(int32_t*)(item+8);
    if(before & g_gcBit){ Markerf("[GC] %s 0x%llX (%s) already rooted flags=%08X\r\n",tag,(unsigned long long)obj,cn,(unsigned)before); return true; }
    if(!SafeWritable((void*)(item+8),4)){ Markerf("[GC] %s 0x%llX FUObjectItem not writable -> NOT rooted\r\n",tag,(unsigned long long)obj); g_gcFailed++; return false; }
    // Interlocked, not a read-modify-write store: GC's own reachability pass writes Unreachable into this
    // same dword from its worker threads, and a plain RMW here could drop that write. The OR is a single
    // locked instruction, so we can only ever ADD RootSet, never clobber a concurrent flag change.
    InterlockedOr((volatile LONG*)(item+8),(LONG)g_gcBit);
    int32_t after=*(int32_t*)(item+8);
    bool ok=(after & g_gcBit)!=0; if(ok) g_gcRooted++; else g_gcFailed++;
    Markerf("[GC] ROOT %s 0x%llX (%s) item=0x%llX flags %08X -> %08X %s\r\n",
            tag,(unsigned long long)obj,cn,(unsigned long long)item,(unsigned)before,(unsigned)after,ok?"OK":"FAILED");
    return ok;
#endif
}
// Root every live (non-CDO) instance whose class name contains `sub`. Used for the UAnimSingleNodeInstance
// that USkeletalMeshComponent::PlayAnimation creates for us — the shim never holds it, so nothing else can.
static int GcRootAllOfClass(const char* sub,int maxN,const char* tag){
    int n=0;
#if KGCROOT
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks&&n<maxN;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;
        uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue;
        int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt&&n<maxN;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,0x10))continue;
            uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!LooksLikePtr(cls))continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,sub))continue; char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
            if(strncmp(on,"Default__",9)==0)continue;
            if(GcRoot(obj,tag)) n++; } }
#else
    (void)sub; (void)maxN; (void)tag;
#endif
    return n;
}
// Liveness probe for a UObject, derived from the S106 dump analysis. Two independent measured signatures
// of a destructed+freed UObject in this build:
//   (1) [obj+0x00] stops being a module .rdata vtable (the allocator writes its free-list link there);
//   (2) [obj+NAME_OFF] (NamePrivate) becomes 0, because UObjectBase::~UObjectBase does LowLevelRename(NAME_None).
// Both held in 5/5 crash dumps. This does NOT stop the game's own parallel anim tick from touching a dead
// asset — only rooting does that — but it stops the SHIM from calling into one (the S99b "PlayAnimation(idle)
// faulted with RIP=0x0 access=EXEC addr=0x0, RDI=AnimSingleNodeInstance" failure, which is the same event).
static bool GcAlive(uintptr_t obj){
    if(!LooksLikePtr(obj)) return false;
    if(!SafeReadable((void*)obj,NAME_OFF+4)) return false;
    uintptr_t vt=*(uintptr_t*)obj;
    if(vt<g_modBase || (vt-g_modBase)>0x0B000000ULL) return false;   // vtable must live inside the image
    if(*(uint32_t*)(obj+NAME_OFF)==0) return false;                  // NamePrivate == NAME_None -> destructed
    return true;
}
// ================= end S106 GC ROOT GUARD =====================================================

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

// ================= S106b (FK-7, GAME-THREAD ARM) — THE VIEW-TARGET GUARD ========================
//
// WHAT CRASHES.  Four of the 86 crash minidumps under %LOCALAPPDATA%\SUPERVIVE\Saved\Crashes are one
// deterministic GameThread fault, byte-identical across independent launches:
//
//   FEngineLoop::Tick -> UGameEngine::Tick (vt slot 96, base+0x37F8820)
//     -> UWorld::Tick(LEVELTICK_All=2, Delta)            base+0x39C6E70   (E8-called, edx=2)
//       -> APlayerController::UpdateCameraManager        PC  vt +0xF38    (tail-call, leaves no frame)
//         -> APlayerCameraManager::UpdateCamera          PCM vt +0x820 -> base+0x3C59650
//           -> ...DoUpdateCamera                         PCM vt +0x8C0 -> base+0x3C349A0
//             -> ...UpdateViewTarget(ViewTarget@PCM+0x420, Delta)  PCM vt +0x8F0 -> base+0x3C5CFC0
//               -> ...UpdateViewTargetInternal           PCM vt +0x9C0 -> base+0x3C5DBC0
//                 -> OutVT.Target->CalcCamera(Delta, OutVT.POV)   vt +0x700 = AActor::CalcCamera
//                    base+0x3C5DC52: mov rcx,[rbx] / lea r8,[rbx+0x10] / mov rax,[rcx] / call [rax+0x700]
//                    -> ACCESS_VIOLATION reading 0x700, i.e. rax (the target's vptr) == 0.
//
// Every frame above is MEASURED, not inferred: all four camera frames are slots of the very vtable
// (rdata 0x07EC5B88) that the live PCM carries at [rdi], and rbx-rdi == 0x420 in the dumps.
//
// WHAT IS ACTUALLY WRONG — and it is NOT what the record said.  The record called this a
// use-after-free on a garbage-collected CameraActor.  It is not.  In both dumps whose memory window
// covers the target:
//
//   * ViewTarget.Target reads 0x…D01 / 0x…F301 — bit 0 set, so NOT an 8-aligned UObject pointer.
//   * A fully-formed, LIVE UObject sits at exactly Target+0x3F in BOTH dumps, with the SAME vtable
//     (rdata 0x07F96428) and the SAME FName (179548).  That vtable is ACameraActor's: following
//     ACameraActor::GetPrivateStaticClass (base+0x35324A0, it references L"ACameraActor") to
//     InternalConstructor<ACameraActor> (base+0x350F080) gives `lea rax,[rip -> 0x07F96428]`.
//     So the object is the shim's OWN top-down CameraActor (DoTopDownCam), and it is intact.
//   * That object is present in GUObjectArray with FUObjectItem::Flags == 2, which in UE 5.4 is
//     ReachabilityFlag1 — i.e. the GC marked it REACHABLE on its most recent pass.  It was never
//     collected.  (The clean pointer appears in exactly one 8-aligned slot in the dump: that
//     FUObjectItem.  The value Target&~0xFF appears in NO slot, which kills "bit 0 got set".)
//
//   => the ACTOR is alive; the POINTER stored in PCM->ViewTarget.Target has had its LOW BYTE
//      replaced by 0x01 (0x…40 -> 0x…01).  Bytes 1..7 are intact, so the write was ONE byte, not a
//      32/64-bit store.  The rest of the crash follows mechanically and consistently: Cast<ACameraActor>
//      reads [Target+0x18] out of the zero padding, gets null, and fails without faulting, so
//      UpdateViewTarget falls through to UpdateViewTargetInternal; its `if (OutVT.Target)` passes
//      (garbage is non-null); BlueprintUpdateCamera never dereferences the target and returns false;
//      then CalcCamera dispatches through a vptr read out of that same zero padding.
//
// WHO WRITES THE BYTE IS STILL OPEN -- but the search space is now much smaller.  ★ S106d CORRECTIONS
// to the paragraph that used to sit here (two false-knowns; do not re-derive either):
//
//   ⚠ RETRACTED: candidate (b), "a one-byte heap OVERRUN out of the degenerate cloth/physics bodies",
//     is FALSIFIED on structural grounds.  MEASURED in 4/4 camera dumps: 0x420 is 0x420 bytes INSIDE
//     the PlayerCameraManager's OWN live allocation (PCM+0x00 holds the APlayerCameraManager vtable at
//     .rdata RVA 0x7EC5B88; PendingViewTarget.Target is a further 0x820 higher at PCM+0xC40 -- both
//     FTViewTargets located independently via the FMinimalViewInfo default signature FOV 90 / DesiredFOV
//     90 / OrthoWidth 512 at PCM+0x460 and PCM+0xC80).  A one-byte overrun writes one byte past the END
//     of its own block and heap blocks do not overlap, so no allocation can end at PCM+0x420.  The only
//     surviving overrun variant is a WILD indexed write (Buf[i]=1 with a bogus/NaN-derived i) -- and a
//     wild write cannot hit the same byte of the same object in 4 of 4 launches whose heap bases differ
//     (0x23A…, 0x1E6…, 0x2639…, 0x1A56…).
//
//   ⚠ RETRACTED: "a repeat [VTG] delta of exactly +0x3F implicates a writer that targets this field; a
//     wandering delta implicates the heap overrun."  That is a NON-discriminator, and it is the same
//     instrument-artifact shape this project's ★★★ method rule warns about, embedded in this guard's own
//     instrumentation.  delta = (live & 0xFF) - 0x01 whenever byte 0 is replaced by 0x01, and the live
//     object's low byte was 0x40 in 3 of 3 observations (including the CLEAN control dump FF9CF623), so
//     +0x3F is ALLOCATOR-FORCED.  Both candidate writers produce literally the same 8 bytes.  The line
//     is KEPT because it still confirms "this is the same bug, not a new one" -- never as attribution.
//
// WHAT IS NOW MEASURED ABOUT THE WRITE (all 4 camera dumps): the low byte of PCM+0x420 is 0x01, 0x01,
// 0x01, 0x01 while the two neighbouring heap pointers' low bytes vary (PCM+0x390 = 0x70/0x40/0x20/0xC0;
// PCM+0x398 = 0x00/0x00/0x80/0x80).  A cross-dump diff of PCM[0x300..0x480) finds 290 offsets identical
// in 4/4; the ONLY differing bytes are heap-pointer bytes and the POV region.  ⇒ a DETERMINISTIC
// single-byte store of the literal 1 at a FIXED object offset, with zero collateral corruption.  Rules
// out a memset/struct-assign and any 32/64-bit store.  Only candidate (a) survives: a field-aimed 1-byte
// store from code in the undecrypted half of .text (the instruction-shape scan is now exhaustive over
// what IS readable -- 34 byte-width stores at disp32 0x420, 8 with imm8 == 1, none in camera/physics/
// cloth/anim code -- so more offline effort on that encoding is wasted; and the writer may not even use
// disp 0x420, since only the ADDRESS is fixed, not the encoded displacement).
//
// ⚠ ALSO MEASURED: the write is CONDITIONAL, not an inevitable consequence of the body build.  Dump
// FF9CF623 (ANIM family, SecondsSinceStart 195) captures a PCM with a CLEAN ViewTarget.Target
// (0x1CB9A088D40, 8-aligned) whose *(void**)Target resolves to the SAME vtable and SAME FName as the
// object the corrupt pointers resolve to at Target+0x3F -- a third, independent confirmation of the
// view target's identity, and proof that a mesh-build session can reach 195 s uncorrupted.  ⇒ a quiet
// run proves LESS than "the guard worked": it may simply be a run where the writer never fired.
//
// ⚠ The PendingViewTarget arm below is DEAD CODE for this signature: PCM+0xC40 reads 0x0 in all four
// camera dumps.  If only that arm ever fires, that is a NEW phenomenon, not a repair of FK-7.
//
// Reproduce the measurement (all offline, read-only, no game):
//   python tools/crashtri/harvest.py                       # census + family classification, 86 dumps
//   python tools/crashtri/mdctx.py   <dump>                # exception record + full CONTEXT_AMD64
//   python tools/crashtri/deadobj.py <dump> [<dump> ...]   # the target, and UObject headers near it
//   python tools/crashtri/ptrhunt.py <dump> 0x<ptr>        # every 8-aligned slot holding a value
//   python tools/strxref/vtables.py slotof 0x3C5DBC0       # -> slot 312 of APlayerCameraManager
//
// WHY REPAIRING IS LEGITIMATE, NOT A HACK.  UE itself maintains this invariant:
// FTViewTarget::CheckViewTarget(PCOwner) resets Target to the owning PlayerController whenever it is
// not usable.  We do the same thing one frame earlier, from the game thread, with a single aligned
// 8-byte store of a pointer the engine would have accepted anyway.  No .text patch, no new hook.
//
// TIMING (measured, and it is NOT a GC period).  `FlushAsyncLoading(2523)` immediately followed by a
// skeletal-mesh init warning is the last log event in 4 of 4 camera crashes and in 0 of the other 68
// crashes in the corpus.  That is DoPlay's blocking LoadMeshByPath -> body build.  The 173/175/185/194 s
// clock times are just when that step ran; they fit no multiple of any GC period.
//   ★ S106d CORRECTION: the warning is `LogChaosCloth` ONLY.  The other half of that pairing --
//   LogPhysics "Scale3D is (nearly) zero" -- occurs in **0 of 14** log files, as does `LogPhysics` at
//   all; the string exists in the image (.rdata 0x0817DAF0, "Initialising Body : Scale3D is (nearly)
//   zero: %s") but is never emitted.  So there is no evidence of a degenerate PHYSICS body, only cloth,
//   and the count is exactly ONE cloth warning per crashing session (1x in 4/4 crash logs, 0x in 5/5
//   non-crash logs).  Emitter = the 768-byte function at RVA 0x6936E20, warning at +0xDA.  The line's
//   object name is EMPTY in shipping, so it can never tell you WHICH body -- use KTESTACTOR to bisect.
//   ★ Also: the "9 tutorial sessions, only 4 crashed" flakiness was a DENOMINATOR ERROR, not a second
//   failure mode.  All 4 crash logs have FlushAsyncLoading=5 + LogChaosCloth=1 (RM_PLAY); all 5
//   dumpless logs have FlushAsyncLoading=4 + LogChaosCloth=0 and ran a NON-mesh mode (3 recovered from
//   git as RM_SPAWNPOSSESS, terminated by the user 3-9 s before he committed that session's marker; 2
//   died before the T+173 s body build).  The RM_PLAY rate is 4 launches / 4 crashes = 100%.
#ifndef KVTGUARD
#define KVTGUARD 1              // -DKVTGUARD=0 -> A/B: reproduce the un-guarded GameThread crash
#endif
#ifndef KVTOFFFALLBACK
#define KVTOFFFALLBACK 0x420    // MEASURED offset of FTViewTarget ViewTarget on APlayerCameraManager
#endif                          // (rbx-rdi in both 2026-07-26 camera dumps). Reflection wins if it resolves.
static uintptr_t g_vtPCM=0, g_vtGood=0;
static uint32_t  g_vtOff=0xFFFFFFFF, g_vtPendOff=0xFFFFFFFF;
static bool      g_vtRes=false;
static int       g_vtRepairs=0;
static DWORD     g_vtLastOk=0;
// ★ S106d (2026-07-29) — BUG FIX: this counter was a FUNCTION-SCOPED `static int s_tries` inside
// VtResolve. Function-scoped statics live for the process, but the "PlayerCameraManager destroyed ->
// stand down and re-resolve" path in VtGuard resets every OTHER piece of resolve state (g_vtRes,
// g_vtPCM, g_vtOff, ...) and could not reach s_tries. So the 200-hit give-up budget was CUMULATIVE
// across teardowns, not per-resolve: after enough level changes / PC teardowns the running total
// crossed 200 and VtResolve latched `g_vtRes = true` with `g_vtPCM = 0`, which makes
// `VtResolve() -> false` forever. The guard would then be PERMANENTLY DISABLED for the rest of the
// session while still printing nothing -- i.e. an A/B could silently run the "guard on" arm with no
// guard. Promoted to file scope so the stand-down path can zero it, which is the actual fix; the
// bounded budget is still enforced, just per-resolve-attempt as intended.
static int       g_vtTries=0;

#if KWPROBE
// ---- FK-24 probe hooks that live on the GAME THREAD. All three are a handful of stores; none of them
//      arms anything (the arm sweep suspends threads and must never run here -- S81's rule). ---------
static volatile LONG g_wpSelfReq=0, g_wpSelfPhase=0, g_wpSelfDoneTick=0;
// ★ S108 (2026-08-04) — counts entries into VtGuard that REACH the selftest call site (i.e. past
// VtResolve, past the GcAlive stand-down, past SafeReadable). S107's run declared
// "selftest FAIL ... the watchpoint is VOID on the game thread" while printing selfPhase=0 — and
// selfPhase only advances AFTER the idempotent store has executed, so selfPhase=0 means the store
// NEVER RAN. That is a statement about VtGuard's cadence, not about the watchpoint, and the FAIL
// line's own wording asserted the latter. This counter is the discriminator: selfPhase==0 with
// vtHits==0 means VtGuard never got the game thread back after arming (the one-shot RM_PLAY init
// block holds it for >8 s); selfPhase==0 with vtHits>0 means the store was reached but bailed on
// VtValid/SafeReadable. Neither is evidence about the trap. See WpSelfWatch below.
static volatile LONG g_wpVtHits=0;
static volatile LONG g_wpCorruptSeen=0; static DWORD g_wpCorruptTick=0; static uint64_t g_wpCorruptVal=0;
static void WpArmRequest(int at){ if(KWPARMAT==at) InterlockedExchange(&g_wpArmReq,1); }
// Called by VtGuard the instant it sees the measured corruption. This is the CORRELATION gate: every
// verdict below is keyed on whether a trap was recorded near this moment, never on the value's shape.
static void WpNoteCorruption(uint64_t cur){
    g_wpCorruptVal=cur; g_wpCorruptTick=GetTickCount(); InterlockedIncrement(&g_wpCorruptSeen);
}
#endif

// PC -> PlayerCameraManager, and the byte offset of its ViewTarget / PendingViewTarget. Reflection
// first; the measured constant is a logged fallback so a layout change is visible, not silent.
static bool VtResolve(uintptr_t pc){
    if(g_vtRes) return LooksLikePtr(g_vtPCM) && g_vtOff!=0xFFFFFFFF;
    // Do NOT latch on failure: on the first hits the PC / its camera manager may not exist yet.
    // Retry a bounded number of times, then give up loudly rather than scanning forever.
    // g_vtTries is FILE-SCOPE (see its declaration) so the stand-down path in VtGuard can reset it.
    // A function-scoped static here latched the guard off permanently after ~200 cumulative misses
    // across teardowns.
    if(!LooksLikePtr(pc)){ if(++g_vtTries>=200){ g_vtRes=true; Marker("[VTG] no PlayerController after 200 hits -> guard inactive\r\n"); } return false; }
    uint32_t o=PropOffsetSuper(ClassOf(pc),"PlayerCameraManager");
    if(o!=0xFFFFFFFF && SafeReadable((void*)(pc+o),8)) g_vtPCM=*(uintptr_t*)(pc+o);
    if(!LooksLikePtr(g_vtPCM)){ if(++g_vtTries>=200){ g_vtRes=true; Markerf("[VTG] PC->PlayerCameraManager still null after 200 hits (off@0x%X) -> guard inactive\r\n",o); } return false; }
    g_vtRes=true; g_vtTries=0;   // resolved -> the budget for the NEXT resolve starts clean
    uint32_t v=PropOffsetSuper(ClassOf(g_vtPCM),"ViewTarget");
    bool refl=(v!=0xFFFFFFFF); if(!refl) v=KVTOFFFALLBACK;
    g_vtOff=v;
    g_vtPendOff=PropOffsetSuper(ClassOf(g_vtPCM),"PendingViewTarget");
    Markerf("[VTG] pcm=0x%llX ViewTarget@0x%X (%s) PendingViewTarget@0x%X  [crash-dump measurement: 0x420]\r\n",
            (unsigned long long)g_vtPCM,g_vtOff,refl?"reflection":"FALLBACK CONSTANT",g_vtPendOff);
    // S106c: seed the last-good clock at RESOLVE time, not at first-valid-read. It is only ever used for the
    // "after %lu ms good" field of the repair line, and that field is part of the evidence that separates the
    // two candidate writers -- left at 0 it would print ~GetTickCount() (tens of millions of ms) on a repair
    // that happened before any target ever validated, which reads as a plausible number and is not one.
    g_vtLastOk=GetTickCount();
#if KWPROBE
    // KWPARMAT=0 (default): &PCM->ViewTarget.Target now EXISTS, which is the earliest moment the probe
    // can point at it. Only a request flag is set here; WpThread does the arming.
    WpArmRequest(0);
#endif
    return true;
}
// A view target must be an 8-aligned live UObject. The measured corruption (low byte -> 0x01) makes
// it unaligned, so LooksLikePtr alone already rejects it; GcAlive additionally rejects a vtable
// outside the image and a NAME_None (destructed) object, so a genuine UAF is caught too.
static bool VtValid(uintptr_t t){ return LooksLikePtr(t) && GcAlive(t); }

#if KWPROBE
// ★★ THE IN-SESSION POSITIVE CONTROL (KWPSELFTEST).  A watchpoint that never fires is exactly the
// project's dominant error mode -- an instrument's blind spot recorded as a property of the game.  This
// converts "no trap fired" from ambiguous into decisive, in every launch, ~one frame after arming.
//
// TWO idempotent stores through the SAME slot, from the GAME THREAD, in this order:
//   phase 1: an 8-BYTE store of the value already there   -> must fire B0 **and** B1
//   phase 2: a 1-BYTE store of the byte already there     -> must fire B0 **only**
// Phase 2 is not decoration: it validates the DR0/DR1 discriminator that replaces the retracted +0x3F
// against GROUND TRUTH, in-session, on the exact address in question.  Both stores write back the value
// they just read, so neither can perturb the game.  volatile => the compiler cannot elide them.
// LIMITATION, stated so it is not over-read: this proves liveness ON THE GAME THREAD ONLY. For every
// other thread the Dr7 readback is the only evidence, and it is weaker.
static void WpSelfTestTick(uintptr_t* slot){
#if KWPSELFTEST
    if(!InterlockedCompareExchange(&g_wpSelfReq,0,0)) return;
    if(!slot || !InterlockedCompareExchange(&g_wpArmed,0,0)) return;
    LONG ph=InterlockedCompareExchange(&g_wpSelfPhase,0,0);
    if(ph==0){
        uintptr_t v=*(volatile uintptr_t*)slot;
        if(!VtValid(v)) return;                      // never write through a slot that is already bad
        InterlockedExchange(&g_wpSelfStore,1);       // D9: label the trap this store is about to raise
        *(volatile uintptr_t*)slot = v;              // 8-byte idempotent store -> expect B0|B1
        InterlockedExchange(&g_wpSelfStore,0);       // (the #DB is delivered BEFORE this line retires)
        InterlockedExchange(&g_wpSelfPhase,1);
    } else if(ph==1){
        uintptr_t v=*(volatile uintptr_t*)slot;
        if(!VtValid(v)) return;
        volatile uint8_t* b=(volatile uint8_t*)slot;
        InterlockedExchange(&g_wpSelfStore,2);
        *b = *b;                                     // 1-byte idempotent store -> expect B0 only
        InterlockedExchange(&g_wpSelfStore,0);
        InterlockedExchange(&g_wpSelfPhase,2);
        InterlockedExchange(&g_wpSelfDoneTick,(LONG)GetTickCount());
        InterlockedExchange(&g_wpSelfReq,0);
    }
#else
    (void)slot;
#endif
}
#endif

// Runs on the GAME THREAD, once per hook hit, ahead of the camera tick. 3 reads in the common case.
// `preferred` = the actor this mode wants the camera on (the spawned CameraActor); it is only used
// if it is itself valid.
static void VtGuard(uintptr_t pc,uintptr_t preferred){
#if KVTGUARD
    if(!VtResolve(pc)) return;
    // ★ S106c (2026-07-27) — DO NOT REPAIR THROUGH A DEAD CAMERA MANAGER.
    // Gap found while auditing the S106b guard: g_vtPCM is cached once and then written to every hit. If
    // the PlayerCameraManager itself is destroyed (level change, PC teardown, the same UnPossess the S99b
    // possession guard already had to defend against), its heap block can stay COMMITTED while being freed
    // — so SafeReadable/SafeWritable both still pass and the guard would happily store 8 bytes into freed
    // memory. That is strictly worse than the bug being fixed: the original crash is a deterministic AV we
    // can see, whereas a stray write into a recycled allocation is silent corruption.
    // GcAlive is the same two measured death signatures used for the anim assets (vtable must be in-image,
    // NamePrivate != NAME_None). Throttled to 4 Hz because this runs on the game thread on EVERY
    // ProcessInternal hit and GcAlive costs a VirtualQuery; the ViewTarget check itself stays per-hit
    // (see the note below on why it is deliberately NOT throttled).
    { static DWORD s_pcmLast=0; DWORD nw=GetTickCount();
      if(nw-s_pcmLast>=250){ s_pcmLast=nw;
        if(!GcAlive(g_vtPCM)){
            Markerf("[VTG] PlayerCameraManager 0x%llX is no longer a live UObject -> standing down and"
                    " re-resolving (NO write; a repair here would land in freed memory)\r\n",
                    (unsigned long long)g_vtPCM);
            // ★ S106d — g_vtTries MUST be reset here too. Without it the 200-hit give-up budget was
            // cumulative across teardowns and eventually latched the guard off for good (see the
            // g_vtTries declaration). This line is the actual fix; the file-scope promotion enables it.
            g_vtPCM=0; g_vtOff=0xFFFFFFFF; g_vtPendOff=0xFFFFFFFF; g_vtGood=0; g_vtRes=false; g_vtTries=0;
            return; } } }
    // The ViewTarget read+validate below is deliberately EVERY hit, not throttled. The corruption is a
    // single-byte store from an unknown writer, so it can land on any frame, and the whole value of the
    // guard is repairing it before the next APlayerCameraManager tick dispatches through it. Measured
    // cost is ~3 VirtualQuery per hit against the 2-4 full UFunction invocations DoPlay/DoTopDownCam
    // already make per hit — a few percent, which does not buy weakening the one thing this exists to do.
    uintptr_t* slot=(uintptr_t*)(g_vtPCM+g_vtOff);
    if(!SafeReadable(slot,8)) return;
#if KWPROBE
    InterlockedIncrement(&g_wpVtHits);   // S108: measured BEFORE the selftest, so a quiet selftest is attributable
    WpSelfTestTick(slot);   // FK-24 positive control: two idempotent stores, once, right after arming
#endif
    uintptr_t cur=*slot;
    if(VtValid(cur)){ g_vtGood=cur; g_vtLastOk=GetTickCount(); }
    else {
#if KWPROBE
        WpNoteCorruption((uint64_t)cur);   // correlation gate -- see the [WP] correlate: line
#endif
        uintptr_t want = VtValid(preferred)?preferred : (VtValid(g_vtGood)?g_vtGood : (VtValid(pc)?pc:0));
        // Log BEFORE repairing. ★ S106d — READ THIS AS A **SIGNATURE MATCH ONLY, NOT ATTRIBUTION**:
        // `lowbyte=0x01 delta=+0x3F` confirms "this is the SAME bug as the 2026-07-26 dumps", and any
        // other shape (0, a whole-pointer change, a dead-but-aligned pointer) is a DIFFERENT bug that
        // must not be filed under this one. It does NOT identify the writer: delta = (live & 0xFF) - 1,
        // and the live object's low byte is allocator-forced to 0x40 (3 of 3 observations, including a
        // clean control), so +0x3F is arithmetic, not evidence. Both candidate writers print it.
        Markerf("[VTG] *** ViewTarget.Target INVALID: 0x%llX (align=%u lowbyte=0x%02X alive=%d) after %lu ms good"
                " -> repair to 0x%llX (delta=%+lld) [#%d] ***\r\n",
                (unsigned long long)cur,(unsigned)(cur&7),(unsigned)(cur&0xFF),(int)GcAlive(cur),
                (unsigned long)(GetTickCount()-g_vtLastOk),(unsigned long long)want,
                (long long)(want?(long long)want-(long long)cur:0),g_vtRepairs+1);
        if(!want) Marker("[VTG] no valid replacement -> NOT writing (a write would not help)\r\n");
        else if(!SafeWritable(slot,8)) Marker("[VTG] ViewTarget slot not writable -> skipped\r\n");
        else { *slot=want; g_vtRepairs++; g_vtGood=want; g_vtLastOk=GetTickCount(); }
    }
    // PendingViewTarget is walked by the same per-frame chain during a blend. Its SAFE state is NULL
    // (that is exactly what APlayerCameraManager::SetViewTarget writes for an instant cut), so a
    // corrupt pending target is cleared rather than replaced -- strictly the engine's own no-blend state.
    if(g_vtPendOff!=0xFFFFFFFF){
        uintptr_t* p=(uintptr_t*)(g_vtPCM+g_vtPendOff);
        if(SafeReadable(p,8)){ uintptr_t pv=*p;
            if(pv && !VtValid(pv) && SafeWritable(p,8)){
                Markerf("[VTG] *** PendingViewTarget.Target INVALID: 0x%llX (lowbyte=0x%02X) -> cleared to NULL ***\r\n",
                        (unsigned long long)pv,(unsigned)(pv&0xFF));
                *p=0; g_vtRepairs++; } }
    }
#endif
}
// ================= end S106b VIEW-TARGET GUARD =================================================

#if KWPROBE
// ═══════════════════════════════════════════════════════════════════════════════════════════════════
// FK-24 WATCHPOINT PROBE — BACK HALF: arm / sweep / drain / verdict.  Everything here runs on WpThread
// (a dedicated background thread).  The GAME THREAD is never blocked and never sweeps: a sweep suspends
// threads, and S81's rule (a 20 s game-thread block dropped the netdriver) stands.
// ═══════════════════════════════════════════════════════════════════════════════════════════════════
static DWORD g_wpTids[2048]; static int g_wpNTids=0;          // armed set (WpThread only)
static int   g_wpSweepN=0, g_wpLogged=0;
static uint64_t g_wpSeenRva[64]; static int g_wpNSeenRva=0;   // novelty filter for the rate limiter
static DWORD g_wpArmTick=0, g_wpLastCensus=0, g_wpTpsTick=0; static LONG g_wpTpsBase=0;
static bool  g_wpVerdictDone=false, g_wpArmLogged=false;
static int   g_wpVoidThreads=0, g_wpPreexisting=0, g_wpLastNew=0, g_wpNewAtCorrupt=-1;
static bool  g_wpSelfB0B1=false, g_wpSelfB0only=false, g_wpAnySelfTrap=false, g_wpSelfTestTrapped=false;
static DWORD g_wpPollHitTick=0; static uint64_t g_wpPollHitVal=0; static bool g_wpPollHit=false;
static LONG  g_wpPolls=0;   // poll COUNT -> the summary reports the MEASURED period, not the nominal one
static DWORD g_wpLastTrapTick=0; static uint64_t g_wpLastCorruptRva=0; static DWORD g_wpCorruptTrapTick=0;
static int   g_wpCorrelated=0, g_wpFullShown=0;
static const char* kWpRegName[16]={"RAX","RCX","RDX","RBX","RSP","RBP","RSI","RDI",
                                   "R8 ","R9 ","R10","R11","R12","R13","R14","R15"};

static void WpImageRange(uintptr_t base,uintptr_t* lo,uintptr_t* hi){
    *lo=base; *hi=base+0x1000;
    if(!SafeReadable((void*)base,0x40)) return;
    IMAGE_DOS_HEADER* d=(IMAGE_DOS_HEADER*)base;
    if(d->e_magic!=IMAGE_DOS_SIGNATURE) return;
    IMAGE_NT_HEADERS64* nt=(IMAGE_NT_HEADERS64*)(base+(uintptr_t)d->e_lfanew);
    if(!SafeReadable(nt,sizeof(IMAGE_NT_HEADERS64))||nt->Signature!=IMAGE_NT_SIGNATURE) return;
    if(nt->OptionalHeader.SizeOfImage) *hi=base+nt->OptionalHeader.SizeOfImage;   // tight bound, not the 0xC000000 slop
}
static void WpResolveRanges(){
    WpImageRange(g_modBase,&g_wpModLo,&g_wpModHi);
    MEMORY_BASIC_INFORMATION m{};
    if(VirtualQuery((void*)&WpResolveRanges,&m,sizeof(m)) && m.AllocationBase){
        uintptr_t b=(uintptr_t)m.AllocationBase; WpImageRange(b,&g_wpSelfLo,&g_wpSelfHi);
        if(g_wpSelfHi<=g_wpSelfLo+0x1000) g_wpSelfHi=(uintptr_t)m.BaseAddress+m.RegionSize;   // manual-mapped, no headers
    }
}
// Callable FROM THE HANDLER (page mode only). Same D3 discipline: grace open, hardware down, flag last.
static void WpPanicDisarm(){
    InterlockedExchange(&g_wpGraceUntil,(LONG)(GetTickCount()+2000));
#if KWPROBE==2
    DWORD tmp=0; if(g_wpPage) VirtualProtect((void*)g_wpPage,g_wpPageSz,g_wpOldProt?g_wpOldProt:PAGE_READWRITE,&tmp);
#endif
    InterlockedExchange(&g_wpArmed,0); InterlockedExchange(&g_wpStorm,1);
}

// ---------------------------------------------------------------------------------------------------
// DR path: one thread at a time.  SUSPEND DISCIPLINE (non-negotiable): between SuspendThread and
// ResumeThread the ONLY calls are Get/SetThreadContext -- kernel calls that take no user-mode lock in
// this process.  No Marker*, no allocation, no VirtualQuery.  Suspending a thread that holds the heap
// or loader lock and then allocating is the classic self-deadlock.
// ---------------------------------------------------------------------------------------------------
#if KWPROBE==1
struct WpArmRes { int ok, failOpen, failGet, failSet, readbackZero, preexist, busySkipped; };
static void WpArmOne(DWORD tid,WpArmRes* R,uint64_t* preOut){
    HANDLE h=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_SET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,tid);
    if(!h){ R->failOpen++; return; }
    if(SuspendThread(h)==(DWORD)-1){ CloseHandle(h); R->failOpen++; return; }
    alignas(16) CONTEXT ctx; alignas(16) CONTEXT rb;   // an unaligned CONTEXT makes GetThreadContext fail (ERROR_NOACCESS)
    memset(&ctx,0,sizeof(ctx)); memset(&rb,0,sizeof(rb));
    ctx.ContextFlags=CONTEXT_DEBUG_REGISTERS;
    BOOL g=GetThreadContext(h,&ctx), s=FALSE, r=FALSE; bool busy=false;
    uint64_t pre=g?ctx.Dr7:0;
    if(g){
        // ★ D6 -- the slot PAIR is chosen once, from the GAME thread's pre-existing Dr7. Another thread may
        // independently be using that pair. OR-ing our L bits in and overwriting its Dr0/Dr1 would clobber
        // its watchpoints AND merge its R/W+LEN bits with ours into nonsense. Detect it and STEP ASIDE:
        // the resulting coverage hole is real, so it is counted and reported rather than papered over.
        uint64_t curAddr = (g_wpDrPair==0)?ctx.Dr0:ctx.Dr2;
        if((pre&g_wpDr7Val&0xFFULL) && curAddr!=(uint64_t)g_wpAddr) busy=true;
        if(!busy){
            if(g_wpDrPair==0){ ctx.Dr0=g_wpAddr; ctx.Dr1=g_wpAddr+1; }
            else             { ctx.Dr2=g_wpAddr; ctx.Dr3=g_wpAddr+1; }
            ctx.Dr6=0; ctx.Dr7=(DWORD64)(pre|g_wpDr7Val);      // OR: never clobber a pre-existing user's slots
            ctx.ContextFlags=CONTEXT_DEBUG_REGISTERS;          // re-set: Get may have widened it
            s=SetThreadContext(h,&ctx);
        }
    }
    if(!busy){ rb.ContextFlags=CONTEXT_DEBUG_REGISTERS;
        r=GetThreadContext(h,&rb); }                           // ★ READ BACK WHILE STILL SUSPENDED
    uint64_t got0 = (g_wpDrPair==0)?rb.Dr0:rb.Dr2, got7=rb.Dr7;
    ResumeThread(h); CloseHandle(h);
    // ---- only NOW is bookkeeping legal ----
    if(preOut) *preOut=pre;
    if(!g)                                        R->failGet++;
    else if(busy)                                 R->busySkipped++;
    else if(!s)                                   R->failSet++;
    else if(!r||got7==0||got0!=(uint64_t)g_wpAddr) R->readbackZero++;
    else                                          R->ok++;
    if(pre&0xFFULL)                               R->preexist++;
}
static bool WpKnownTid(DWORD t){ for(int i=0;i<g_wpNTids;i++) if(g_wpTids[i]==t) return true; return false; }
static void WpDisarmOne(DWORD tid){
    HANDLE h=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_SET_CONTEXT,FALSE,tid); if(!h) return;
    if(SuspendThread(h)==(DWORD)-1){ CloseHandle(h); return; }
    alignas(16) CONTEXT ctx; memset(&ctx,0,sizeof(ctx)); ctx.ContextFlags=CONTEXT_DEBUG_REGISTERS;
    if(GetThreadContext(h,&ctx)){ ctx.Dr7&=~(DWORD64)g_wpDr7Val; ctx.Dr6=0;
        ctx.ContextFlags=CONTEXT_DEBUG_REGISTERS; SetThreadContext(h,&ctx); }
    ResumeThread(h); CloseHandle(h);
}
static void WpSweep(bool first){
    DWORD myPid=GetCurrentProcessId(), myTid=GetCurrentThreadId();
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);
    if(snap==INVALID_HANDLE_VALUE){ Markerf("[WP] sweep#%d *** CreateToolhelp32Snapshot FAILED (%lu) -- coverage UNKNOWN ***\r\n",g_wpSweepN,GetLastError()); return; }
    static DWORD tids[2048]; int n=0; THREADENTRY32 te; te.dwSize=sizeof(te);
    if(Thread32First(snap,&te)) do{
        if(te.dwSize>=FIELD_OFFSET(THREADENTRY32,th32OwnerProcessID)+sizeof(DWORD) &&
           te.th32OwnerProcessID==myPid && te.th32ThreadID!=myTid && n<2048) tids[n++]=te.th32ThreadID;
    } while(Thread32Next(snap,&te));
    CloseHandle(snap);
    WpArmRes R{}; int nNew=0, nRe=0, nCleared=0;
    for(int i=0;i<n;i++){
        bool known=WpKnownTid(tids[i]);
        uint64_t pre=0; WpArmOne(tids[i],&R,&pre);
        if(!known) nNew++;
        else { nRe++; if((pre&g_wpDr7Val)!=g_wpDr7Val) nCleared++; }   // it WAS armed and is not any more
    }
    // ★ D8 -- REBUILD the armed set from THIS snapshot instead of only appending to it. The old code never
    // evicted dead tids, so over a long session it could saturate the 2048 cap; once saturated every live
    // thread would read as "new" forever, permanently poisoning the newly-armed / W5 coverage signal.
    // Rebuilding is free (we already enumerate every thread each sweep) and dead tids evict themselves.
    { int keep=(n<2048)?n:2048; for(int i=0;i<keep;i++) g_wpTids[i]=tids[i]; g_wpNTids=keep;
      if(n>2048) Markerf("[WP] *** sweep saw %d threads, tracking cap is 2048 -- coverage of the remainder is UNKNOWN ***\r\n",n); }
    g_wpSweepN++; g_wpLastNew=nNew; g_wpVoidThreads=R.readbackZero; g_wpPreexisting=R.preexist;
    if(first||nNew||nCleared||R.readbackZero||R.failGet||R.failSet||R.failOpen||R.busySkipped)
        Markerf("[WP] arm sweep#%d threads=%d armedOK=%d newly-armed=%d re-verified=%d dr7ReadbackZero=%d"
                " failGet=%d failSet=%d openFail=%d preexistingDR=%d busySkipped=%d clearedSinceLast=%d\r\n",
                g_wpSweepN,n,R.ok,nNew,nRe,R.readbackZero,R.failGet,R.failSet,R.failOpen,R.preexist,R.busySkipped,nCleared);
    if(R.busySkipped>0)
        Markerf("[WP] *** %d thread(s) were ALREADY using our DR slot pair for something else -> NOT armed"
                " (we never clobber). Those threads are UNWATCHED: a quiet result is VOID for them. ***\r\n",R.busySkipped);
    if(R.readbackZero>0 && first)
        Markerf("[WP] *** W1 VOID: %d/%d threads read Dr7 back as ZERO -- the DR write did NOT stick on them."
                " A zero readback is VOID, NOT a negative. Escalate to -DKWPROBE=2. ***\r\n",R.readbackZero,n);
    if(nCleared>0)
        Markerf("[WP] *** W2: %d thread(s) had our Dr7 bits CLEARED BY SOMETHING ELSE since the last sweep"
                " (the packer polls DR). Coverage for that window is VOID, not negative. ***\r\n",nCleared);
}
#endif  // KWPROBE==1

// ---------------------------------------------------------------------------------------------------
static bool WpArm(){
    if(!LooksLikePtr(g_vtPCM)||g_vtOff==0xFFFFFFFF) return false;
    SYSTEM_INFO si; GetSystemInfo(&si); if(si.dwPageSize) g_wpPageSz=si.dwPageSize;
    WpResolveRanges();
    g_wpPCM=g_vtPCM; g_wpVtOff=g_vtOff;
    g_wpAddr=g_vtPCM+g_vtOff;                                     // ★ reflection-resolved. NOT hardcoded 0x420.
    g_wpPendTgt=(g_vtPendOff!=0xFFFFFFFF)?(g_vtPCM+g_vtPendOff):0;
    g_wpPage=g_wpAddr&~(uintptr_t)(g_wpPageSz-1);
    g_wpPollLast=WpRead8(g_wpAddr);
    if(g_wpLogH==INVALID_HANDLE_VALUE)                            // pre-open: the handler must never CreateFile
        g_wpLogH=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    MEMORY_BASIC_INFORMATION mb{}; VirtualQuery((void*)g_wpPage,&mb,sizeof(mb));
    Markerf("[WP] cfg mode=%s armAt=%d selftest=%d sweep=%dms poll=%dms hold=%dms synclog=%d\r\n",
            (KWPROBE==1)?"DR0/DR1-hardware":"PAGE_READONLY",(int)KWPARMAT,(int)KWPSELFTEST,
            (int)KWPSWEEPMS,(int)KWPPOLLMS,(int)KWPHOLDMS,(int)KWPSYNCLOG);
    Markerf("[WP] target &VT.Target=0x%llX (pcm=0x%llX +0x%X %s)  &PVT.Target=0x%llX  page=0x%llX"
            " pageOffTarget=0x%03X pageSz=0x%X regionBase=0x%llX regionSz=0x%llX prot=0x%X\r\n",
            (unsigned long long)g_wpAddr,(unsigned long long)g_wpPCM,g_wpVtOff,
            (g_wpVtOff==(uint32_t)KVTOFFFALLBACK)?"FALLBACK-CONSTANT-or-reflection-agrees":"reflection",
            (unsigned long long)g_wpPendTgt,(unsigned long long)g_wpPage,
            (unsigned)(g_wpAddr-g_wpPage),g_wpPageSz,
            (unsigned long long)(uintptr_t)mb.BaseAddress,(unsigned long long)mb.RegionSize,(unsigned)mb.Protect);
    Markerf("[WP] modbase=0x%llX..0x%llX  self(this DLL)=0x%llX..0x%llX  gameTid=%lu wpTid=%lu  initialTarget=0x%llX\r\n",
            (unsigned long long)g_wpModLo,(unsigned long long)g_wpModHi,
            (unsigned long long)g_wpSelfLo,(unsigned long long)g_wpSelfHi,
            (unsigned long)g_gameTid,(unsigned long)GetCurrentThreadId(),(unsigned long long)g_wpPollLast);
#if KWPROBE==1
    // Pick the DR slot pair ONCE, from the game thread's pre-existing Dr7. Non-zero there means the game
    // or the packer is already using debug registers -- log it and step aside rather than clobbering.
    {   uint64_t pre=0;
        if(g_gameTid){ HANDLE h=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT,FALSE,g_gameTid);
            if(h){ if(SuspendThread(h)!=(DWORD)-1){ alignas(16) CONTEXT c0; memset(&c0,0,sizeof(c0));
                    c0.ContextFlags=CONTEXT_DEBUG_REGISTERS; if(GetThreadContext(h,&c0)) pre=c0.Dr7; ResumeThread(h);} CloseHandle(h);} }
        if(pre&0x5ULL){ g_wpDrPair=1; g_wpDr7Val=0x11000050ULL; g_wpDrBit0=0x4; g_wpDrBit1=0x8;
            Markerf("[WP] *** PRE-EXISTING DEBUG REGS on the game thread (Dr7=0x%llX) -> using DR2/DR3 instead of DR0/DR1 ***\r\n",(unsigned long long)pre); }
        else Markerf("[WP] game-thread Dr7 before arming = 0x%llX -> using DR0/DR1 (dr7=0x%llX, R/W=write, LEN=1 byte)\r\n",
                     (unsigned long long)pre,(unsigned long long)g_wpDr7Val);
    }
    InterlockedExchange(&g_wpArmed,1);
    g_wpNTids=0; WpSweep(true);
#elif KWPROBE==2
    // ★ D1 FIX -- ORDER IS LOAD-BEARING.  The pend table and g_wpArmed must be live BEFORE the page goes
    // read-only.  Previously VirtualProtect ran, then a Markerf (CreateFileA+WriteFile+CloseHandle,
    // ~100-200 us), and only then g_wpArmed=1.  WpHandle's first line is `if(!armed) return false`, so any
    // write landing in that window fell through to the fatal path as an unhandled AV.  ViewTarget.POV
    // shares this page in 5/5 dumps and is written every frame, so that window was very likely fatal.
    // Arming the flag early costs nothing: the handler's four-condition page filter rejects everything
    // that is not a WRITE to our page, and the grace/armed logic covers the rest.
    for(int i=0;i<WPPEND;i++){ g_wpPend[i].tid=0; g_wpPend[i].isTgt=0; g_wpPend[i].selfTest=0; }
    InterlockedExchange(&g_wpArmed,1);
    BOOL ok=VirtualProtect((void*)g_wpPage,g_wpPageSz,PAGE_READONLY,&g_wpOldProt);
    MEMORY_BASIC_INFORMATION rb{}; VirtualQuery((void*)g_wpPage,&rb,sizeof(rb));      // ★ MANDATORY READBACK
    // The readback must test COVERAGE, not exact identity.  If the neighbouring page is already
    // PAGE_READONLY the regions coalesce and rb.BaseAddress is BELOW g_wpPage -- the arm is still correct.
    // The old `rb.BaseAddress==g_wpPage` test called that a VOID (and, with the old ordering, left the page
    // read-only with the handler off => a guaranteed crash next frame, misreadable as FK-7).
    bool covered = rb.Protect==PAGE_READONLY &&
                   (uintptr_t)rb.BaseAddress<=g_wpPage &&
                   (uintptr_t)rb.BaseAddress+(uintptr_t)rb.RegionSize>=g_wpPage+g_wpPageSz;
    bool armed = ok && covered;
    if(!armed){
        // ★ D2 FIX -- FAIL SAFE, NOT FAIL DEADLY.  If VirtualProtect succeeded but the readback disagrees,
        // put the protection back before giving up.  Leaving a read-only page behind with the handler
        // disarmed is the single worst thing this probe could do.
        DWORD tmp=0; if(ok) VirtualProtect((void*)g_wpPage,g_wpPageSz,g_wpOldProt?g_wpOldProt:PAGE_READWRITE,&tmp);
        InterlockedExchange(&g_wpArmed,0);
    }
    Markerf("[WP] arm PAGE_READONLY %s: VirtualProtect=%d wasProt=0x%X readback prot=0x%X base=0x%llX size=0x%llX"
            " covered=%d coalesced=%d%s\r\n",
            armed?"OK":"*** V1 VOID -- NEVER ARMED (protection restored) ***",(int)ok,(unsigned)g_wpOldProt,
            (unsigned)rb.Protect,(unsigned long long)(uintptr_t)rb.BaseAddress,(unsigned long long)rb.RegionSize,
            (int)covered,(int)((uintptr_t)rb.BaseAddress!=g_wpPage),
            armed?"":"  <- V1 is TERMINAL for this launch: the page path never ran, so nothing below is a negative");
    if(!armed){ g_wpArmLogged=true; return false; }   // latch: V1 is terminal, retrying would flood the log
#endif
    g_wpArmTick=GetTickCount(); g_wpTpsTick=g_wpArmTick; g_wpTpsBase=0; g_wpArmLogged=true;
#if KWPSELFTEST
    InterlockedExchange(&g_wpSelfPhase,0); InterlockedExchange(&g_wpSelfReq,1);
    Marker("[WP] selftest ARMED: VtGuard will issue an 8-byte then a 1-byte idempotent store to &Target\r\n");
#endif
    return true;
}
// ★ D3 FIX -- HARDWARE FIRST, FLAG LAST, PLUS A GRACE WINDOW.
// The old order cleared g_wpArmed and only then walked ~140 threads clearing their DR7 (3-5 ms).  A DR hit
// inside that window was DECLINED by WpHandle and propagated as an unhandled STATUS_SINGLE_STEP, which
// kills the process.  This is not theoretical: the `retarget` path calls WpDisarm mid-session whenever
// VtGuard stands down on PlayerCameraManager teardown (a documented real event, S106c).
// Now: open a grace window -> clear the hardware -> clear the flag.  During the grace the handler still
// swallows traps that provably name our slots, but does not record them (coverage is over).
static void WpDisarm(const char* why){
    if(!InterlockedCompareExchange(&g_wpArmed,0,0)) return;
    InterlockedExchange(&g_wpGraceUntil,(LONG)(GetTickCount()+2000));
#if KWPROBE==1
    for(int i=0;i<g_wpNTids;i++) WpDisarmOne(g_wpTids[i]);
    InterlockedExchange(&g_wpArmed,0);
    g_wpNTids=0;
#elif KWPROBE==2
    DWORD tmp=0; BOOL ok=VirtualProtect((void*)g_wpPage,g_wpPageSz,g_wpOldProt?g_wpOldProt:PAGE_READWRITE,&tmp);
    InterlockedExchange(&g_wpArmed,0);
    MEMORY_BASIC_INFORMATION rb{}; VirtualQuery((void*)g_wpPage,&rb,sizeof(rb));
    if(!ok||rb.Protect==PAGE_READONLY)
        Markerf("[WP] *** V4: page protection at DISARM reads 0x%X (restore ok=%d) -- coverage for part of the window is UNKNOWN ***\r\n",(unsigned)rb.Protect,(int)ok);
#else
    InterlockedExchange(&g_wpArmed,0);
#endif
    Markerf("[WP] DISARMED (%s) after %lu ms (grace 2000 ms: in-flight traps are swallowed, not recorded)\r\n",
            why,(unsigned long)(GetTickCount()-g_wpArmTick));
}

// ---- drain: ALL formatting happens here, on WpThread, never in the handler ------------------------
// ★ D7 -- SATURATION.  The old version returned true (=> "log this one in full") for every RVA once the
// 64-slot table filled, because it could no longer record what it had already seen.  That turns the rate
// limiter off exactly when it is most needed.  Full => nothing is novel any more, and say so once.
static bool WpNovelRva(uint64_t rva){
    for(int i=0;i<g_wpNSeenRva;i++) if(g_wpSeenRva[i]==rva) return false;
    if(g_wpNSeenRva>=64){
        static bool warned=false;
        if(!warned){ warned=true;
            Markerf("[WP] *** distinct-RVA table FULL (64) -- novelty logging is off from here; the census"
                    " counters stay exact. A CORRUPTING store is still logged in full regardless. ***\r\n"); }
        return false;
    }
    g_wpSeenRva[g_wpNSeenRva++]=rva; return true;
}
static void WpHex(const uint8_t* p,int n,char* out,int cap){
    int o=0; out[0]=0; for(int i=0;i<n&&o+3<cap;i++) o+=_snprintf_s(out+o,cap-o,_TRUNCATE,"%02X ",p[i]);
}
static void WpEmitFull(int idx,uint64_t seq){
    WpFull* F=&g_wpFull[idx];
    uint64_t rva=(F->rip>=g_wpModLo&&F->rip<g_wpModHi)?F->rip-g_wpModLo:0;
    const char* origin=(F->flags&WPF_SELF)?"SELF(this shim)":((F->flags&WPF_INMOD)?"GAME":"OUT-OF-MODULE(packer-hidden or another DLL)");
    // ★ conv= is printed literally because getting it backwards misnames the writer by one instruction.
    const char* conv=(KWPROBE==1)?"RIP-IS-AFTER (DR trap: the store ENDS at rip)":"RIP-IS-AT (page fault: the store STARTS at rip)";
    Markerf("[WP] *** TRAP #%llu tid=%lu%s code=0x%lX dr6=0x%llX %s%s%s conv=%s\r\n",
            (unsigned long long)seq,(unsigned long)F->tid,(F->flags&WPF_GAMETID)?"(GAMETHREAD)":"(WORKER)",
            (unsigned long)F->code,(unsigned long long)F->dr6,
            (F->flags&WPF_B0)?"B0 ":"",(F->flags&WPF_B1)?"B1 ":"",
            (F->flags&WPF_DR6ZERO)?"[dr6=0 UNAVAILABLE-instrument-caveat] ":"",conv);
    Markerf("[WP]   rip=0x%llX rva=0x%llX origin=%s ctxFlags=0x%lX dr7=0x%llX\r\n",
            (unsigned long long)F->rip,(unsigned long long)rva,origin,(unsigned long)F->ctxFlags,(unsigned long long)F->dr7);
    // width discriminator -- a property of the INSTRUCTION, which is what replaces the retracted +0x3F.
    if(KWPROBE==1)
        Markerf("[WP]   width: %s\r\n",((F->flags&WPF_B0)&&(F->flags&WPF_B1))?"B0+B1 => the store was WIDER THAN ONE BYTE (a whole-pointer store)":
                ((F->flags&WPF_B0)?"B0 ONLY => a ONE-BYTE store at offset 0 -- the measured FK-7 shape":"neither byte flagged (see dr6)"));
    Markerf("[WP]   target-before=0x%llX target-now=0x%llX lowbyte=0x%02X aligned=%s%s   pending-now=0x%llX  dt=%lums-after-bodybuild\r\n",
            (unsigned long long)F->before,(unsigned long long)F->after,(unsigned)(F->after&0xFF),
            (F->after&7)?"NO":"yes",(F->flags&WPF_CORRUPT)?"  *** THIS IS THE CORRUPTING STORE (value used ONLY to pick the trap, never as attribution) ***":"",
            (unsigned long long)(g_wpPendTgt?WpRead8(g_wpPendTgt):0),
            (unsigned long)(g_wpBodyTick?(F->tick-g_wpBodyTick):0));
    Markerf("[WP]   RAX=%llX RCX=%llX RDX=%llX RBX=%llX RSP=%llX RBP=%llX RSI=%llX RDI=%llX\r\n",
            (unsigned long long)F->regs[0],(unsigned long long)F->regs[1],(unsigned long long)F->regs[2],(unsigned long long)F->regs[3],
            (unsigned long long)F->regs[4],(unsigned long long)F->regs[5],(unsigned long long)F->regs[6],(unsigned long long)F->regs[7]);
    Markerf("[WP]   R8=%llX R9=%llX R10=%llX R11=%llX R12=%llX R13=%llX R14=%llX R15=%llX\r\n",
            (unsigned long long)F->regs[8],(unsigned long long)F->regs[9],(unsigned long long)F->regs[10],(unsigned long long)F->regs[11],
            (unsigned long long)F->regs[12],(unsigned long long)F->regs[13],(unsigned long long)F->regs[14],(unsigned long long)F->regs[15]);
    // ★ THE OTHER HALF OF ATTRIBUTION: which OBJECT the store was aimed at. delta==0 on some register
    // means the writer HELD A PCM* and wrote a byte into what it believed was its own field; a small
    // negative delta means it was aimed at a DIFFERENT object whose layout puts a byte at PCM+0x420
    // (type confusion), and then the encoded displacement is NOT 0x420. Not recoverable offline.
    { char bm[400]; int o=0; bm[0]=0; int hits=0;
      for(int i=0;i<16;i++){ int64_t d=(int64_t)F->regs[i]-(int64_t)g_wpPCM;
          if(d>-0x40000&&d<0x40000&&o<360){ o+=_snprintf_s(bm+o,sizeof(bm)-o,_TRUNCATE,"%s=pcm%+lld ",kWpRegName[i],(long long)d); hits++; } }
      Markerf("[WP]   base-match(pcm=0x%llX): %s%s\r\n",(unsigned long long)g_wpPCM,hits?bm:"none",
              hits?"  (delta 0 => the store WAS AIMED AT THIS OBJECT)":"  (address was computed/indexed -- reconstruct the index from the reg set)"); }
    { char hx[240]; WpHex(F->pre,64,hx,sizeof(hx)); Markerf("[WP]   bytes@rip-64: %s\r\n",hx); }
    { char hx[64];  WpHex(F->at,16,hx,sizeof(hx));  Markerf("[WP]   bytes@rip:    %s\r\n",hx); }
    if(F->nret){ char rs[220]; int o=0; rs[0]=0;
        for(int i=0;i<F->nret&&o<200;i++) o+=_snprintf_s(rs+o,sizeof(rs)-o,_TRUNCATE,"0x%llX ",(unsigned long long)(F->ret[i]-g_wpModLo));
        Markerf("[WP]   ret-scan(HEURISTIC, call-shaped filter, NOT an unwind): %s\r\n",rs); }
    { char hx[240]; WpHex(F->pre,64,hx,sizeof(hx));
      Markerf("[WP]   -> python tools\\crashtri\\wpattrib.py 0x%llX --conv %s --bytes-at 0x%llX --bytes \"%s\"\r\n",
              (unsigned long long)rva,(KWPROBE==1)?"after":"at",(unsigned long long)(rva?rva-64:0),hx); }
    if(F->flags&WPF_CORRUPT){ g_wpLastCorruptRva=rva; g_wpCorruptTrapTick=F->tick; }
    F->state=3;
}
static void WpDrain(){
    LONG produced=InterlockedCompareExchange(&g_wpSeq,0,0);
    while(g_wpCursor<produced){
        long i=++g_wpCursor; WpRec* r=&g_wpRing[(i-1)&(WPRING-1)];
        if(r->seq!=(uint64_t)i){ InterlockedIncrement(&g_wpDropped); continue; }   // lapped by a storm
        g_wpLastTrapTick=GetTickCount();
        // Liveness proof = ANY trap whose RIP is in this DLL on the game thread (the selftest stores AND
        // VtGuard's own repair store both qualify -- either one proves the watchpoint is live there).
        if(r->flags&WPF_SELF) g_wpAnySelfTrap=true;
        // D9: the WIDTH discriminator is validated only against LABELLED selftest stores -- ground truth.
        if(r->flags&WPF_SELFTEST){ g_wpSelfTestTrapped=true;
            if(r->flags&WPF_SELFT1B) g_wpSelfB0only=((r->flags&WPF_B0)&&!(r->flags&WPF_B1));
            else                     g_wpSelfB0B1  =((r->flags&WPF_B0)&& (r->flags&WPF_B1)); }
        if(r->flags&WPF_PAGEOFF) continue;                                          // census only
        uint64_t rva=(r->rip>=g_wpModLo&&r->rip<g_wpModHi)?r->rip-g_wpModLo:0;
        bool novel=WpNovelRva(rva);
        if((r->flags&WPF_CORRUPT)||g_wpLogged<KWPMAXLOG||novel){
            g_wpLogged++;
            // the full record is bound BY INDEX (recorded by the handler), never matched heuristically
            int fi=r->full;
            if(fi>=0 && fi<(int)(sizeof(g_wpFull)/sizeof(g_wpFull[0])) && g_wpFull[fi].state==2){ WpEmitFull(fi,(uint64_t)i); g_wpFullShown++; }
            else Markerf("[WP] TRAP #%ld tid=%lu%s rip=0x%llX rva=0x%llX %s%s%s before=0x%llX after=0x%llX%s\r\n",
                    i,(unsigned long)r->tid,(r->flags&WPF_GAMETID)?"(GAMETHREAD)":"(WORKER)",
                    (unsigned long long)r->rip,(unsigned long long)rva,
                    (r->flags&WPF_SELF)?"origin=SELF ":((r->flags&WPF_INMOD)?"origin=GAME ":"origin=OUT-OF-MODULE "),
                    (r->flags&WPF_B0)?"B0 ":"",(r->flags&WPF_B1)?"B1 ":"",
                    (unsigned long long)r->before,(unsigned long long)r->after,
                    (r->flags&WPF_CORRUPT)?"  *** CORRUPTING STORE ***":"");
        }
    }
}
// ---- ONE-LINE VERDICT. Rows follow the design's outcome table; every "nothing happened" row says
//      explicitly whether it is a VOID (the instrument did not run) or a MEASUREMENT. ---------------
static void WpVerdict(const char* phase){
    if(g_wpVerdictDone) return; g_wpVerdictDone=true;
    WpDrain();
    bool selftest = (KWPSELFTEST==0) ? true : g_wpAnySelfTrap;
    bool corrupt  = InterlockedCompareExchange(&g_wpCorruptSeen,0,0)>0 || g_wpPollHit;
    LONG traps    = InterlockedCompareExchange(&g_wpTraps,0,0);
    LONG tgt      = InterlockedCompareExchange(&g_wpTrapsTgt,0,0);
    LONG corrTrap = InterlockedCompareExchange(&g_wpCorruptTraps,0,0);
    LONG self     = InterlockedCompareExchange(&g_wpTrapsSelf,0,0);
    LONG nonSelfTgt = tgt-self; if(nonSelfTgt<0) nonSelfTgt=0;   // writes to &Target that were NOT ours
    Markerf("[WP] SUMMARY(%s) traps=%ld trapsAtTarget=%ld self=%ld nonSelfAtTarget=%ld corruptingTraps=%ld"
            " distinctRVAs=%d dropped=%ld foreignExc=%ld dr6zero=%ld dr6zeroClaimed=%ld tfDeclined=%ld"
            " graceSwallowed=%ld sweeps=%d armedTids=%d voidTids=%d newAtLastSweep=%d"
            " selftest=%s(labelled=%d 8B->B0|B1=%d 1B->B0only=%d) pollSaw01=%d vtgInvalid=%ld storm=%ld\r\n",
            phase,(long)traps,(long)tgt,(long)self,(long)nonSelfTgt,(long)corrTrap,g_wpNSeenRva,
            (long)InterlockedCompareExchange(&g_wpDropped,0,0),(long)InterlockedCompareExchange(&g_wpForeign,0,0),
            (long)InterlockedCompareExchange(&g_wpDr6Zero,0,0),(long)InterlockedCompareExchange(&g_wpDr6ZeroClaimed,0,0),
            (long)InterlockedCompareExchange(&g_wpTfDeclined,0,0),(long)InterlockedCompareExchange(&g_wpGraceSwallow,0,0),
            g_wpSweepN,g_wpNTids,g_wpVoidThreads,g_wpLastNew,
            selftest?"PASS":"FAIL",(int)g_wpSelfTestTrapped,(int)g_wpSelfB0B1,(int)g_wpSelfB0only,(int)g_wpPollHit,
            (long)InterlockedCompareExchange(&g_wpCorruptSeen,0,0),(long)InterlockedCompareExchange(&g_wpStorm,0,0));
    // The width discriminator that replaces the retracted +0x3F is only trustworthy if it was checked
    // against ground truth THIS run. Say so either way rather than letting it be assumed.
    if(KWPROBE==1 && g_wpSelfTestTrapped)     // page mode has no B0/B1 by construction -- do not judge it
        Markerf("[WP] width-discriminator: %s (8-byte store -> B0|B1 seen=%d, 1-byte store -> B0-only seen=%d)\r\n",
                (g_wpSelfB0B1&&g_wpSelfB0only)?"VALIDATED against ground truth in-session"
                :"*** NOT VALIDATED -- do NOT read B0/B1 width attribution as measured this run ***",
                (int)g_wpSelfB0B1,(int)g_wpSelfB0only);
    if(InterlockedCompareExchange(&g_wpDr6ZeroClaimed,0,0)>0)
        Markerf("[WP] *** INSTRUMENT SUSPECT: %ld trap(s) arrived with CONTEXT_DEBUG_REGISTERS ABSENT, so Dr6"
                " was unreadable and they were claimed on the EFlags.TF discriminator alone. Width (B0/B1)"
                " attribution is UNAVAILABLE for those. %ld single-step(s) were declined as not ours. ***\r\n",
                (long)InterlockedCompareExchange(&g_wpDr6ZeroClaimed,0,0),(long)InterlockedCompareExchange(&g_wpTfDeclined,0,0));
    if(g_wpPollHit)
        Markerf("[WP] POLL: low byte first read 0x01 at t=+%lums after arm (%lums after body build), value=0x%llX"
                "  -- an INDEPENDENT detector on a different mechanism. It bounds the write to a window"
                " of %lu ms -- that is the MEASURED mean poll period (%ld polls / %lu ms), NOT the nominal"
                " KWPPOLLMS=%d: Sleep granularity is 1..15.6 ms depending on the process timer resolution.\r\n",
                (unsigned long)(g_wpPollHitTick-g_wpArmTick),(unsigned long)(g_wpBodyTick?g_wpPollHitTick-g_wpBodyTick:0),
                (unsigned long long)g_wpPollHitVal,
                (unsigned long)(g_wpPolls?((GetTickCount()-g_wpArmTick)/(DWORD)g_wpPolls):0),
                (long)g_wpPolls,(unsigned long)(GetTickCount()-g_wpArmTick),(int)KWPPOLLMS);
    const char* v; const char* nxt;
    if(!selftest){
        // ★ S108 — split ROW6. `!selftest` only means "no self trap was recorded"; whether that is a dead
        // watchpoint or an unrun control is decided by selfPhase (advanced only after the store retires).
        // Escalating DR->page on the unrun case is wasted, because the page build drives its selftest from
        // the SAME VtGuard call site and would reproduce it exactly.
        if(InterlockedCompareExchange(&g_wpSelfPhase,0,0)==0){
            v="ROW6a UNTESTED-INSTRUMENT: the selftest store NEVER EXECUTED (selfPhase=0), so the watchpoint was never exercised. This is NOT 'void' and NOT a negative -- it is no test at all, and it says nothing about the writer OR about DR viability.";
            nxt="read vtHits on the census lines: 0 => VtGuard never re-entered after arming (raise KWPSELFWAITMS or arm later with -DKWPARMAT=1); >0 => the store bailed on VtValid/SafeReadable. Do NOT switch KWPROBE mode on this row.";
        } else {
            v="ROW6 VOID-INSTRUMENT: the selftest store EXECUTED and fired NO trap => the watchpoint was never live on the game thread. This run says NOTHING about the writer.";
            nxt=(KWPROBE==1)?"read the per-thread dr7ReadbackZero counts; if non-zero the packer defeats DR -> rebuild with -DKWPROBE=2":
                             "check [WP] arm PAGE_READONLY / V1, and that CrashVEH is still registered first";
        }
    } else if(corrTrap>0){
        v="ROW1 ANSWER: a CORRUPTING store was trapped. The writer is named by rip/rva + the instruction bytes + which register held the PCM.";
        nxt="run wpattrib.py on the printed rva (the command line is in the trap record), then re-run once to confirm the RVA REPEATS -- a one-shot RVA is a lead, not a cause";
    // ★ D5 -- THE ROWS ARE GATED ON nonSelfAtTarget, NOT ON `traps`.
    // The old chain gated ROW5 on `traps==0` and ROW7 on `!corrupt && traps==0`. Both were DEAD CODE
    // whenever KWPSELFTEST=1 (the default): the selftest store writes &Target, so a live instrument
    // ALWAYS has traps>0, and `selftest==PASS` implies `traps>0` by construction. The design's ROW2
    // ("only our own store trapped") and ROW5 ("no trap fired") are in fact the SAME observable once
    // the selftest and VtGuard's repair store are both writing that address -- so they are merged
    // here, and the merged row carries ROW5's meaning and ROW5's escalation, not ROW2's weaker one.
    } else if(corrupt && nonSelfTgt==0){
        v="ROW5 VOID-MISSED (subsumes ROW2 SELF-ONLY): the instrument is PROVEN LIVE (selftest passed) yet the corruption happened and NOT ONE non-self store to &Target was trapped. This is a VOID, NOT a negative.";
        nxt=(KWPROBE==1)?"1) if voidTids>0 / busySkipped>0 / a W2 line is present, the DR path is partially defeated -> rebuild with -DKWPROBE=2. 2) else drop -DKWPSWEEPMS to 50 and re-run once. 3) if it repeats with full coverage, the write was not a user-mode CPU store from an armed thread -- read the [WP] POLL line for the 2 ms window it landed in":
                         "the page arm may have been lifted (check V1/V4/V6 above) or the write was not user-mode; the [WP] POLL line still bounds when it happened";
    } else if(corrupt){
        v="ROW4 TRAPS-BUT-UNCORRELATED: non-self stores to &Target WERE trapped, but none carried the 0x40->0x01 transition. The corrupting store itself was missed.";
        nxt="re-read each trap's target-before/target-now; the corrupting one is the trap where target-now's low byte becomes 0x01. If none shows the transition, treat this exactly as ROW5 and escalate the same way.";
    } else if(nonSelfTgt>0){
        v="ROW8 CLEAN-BASELINE: the watchpoint works and &Target was written only by legitimate non-self writers. This launch did NOT reproduce FK-7.";
        nxt="record the legitimate RVAs above as the CONTROL SET (they are what makes a future RVA 'novel'), then RE-LAUNCH. MEASURED base rate 1-in-3..1-in-2 => P(all quiet | 6 launches) ~ 9%. Run >= 6.";
    } else {
        v="ROW7 NO-REPRO: no corruption, and no non-self store to &Target was trapped either. NOT evidence about the writer, the fix, or the probe.";
        nxt="RE-LAUNCH (>=6 launches). Also run the 'novtguard' control once per sitting to establish that THIS build vintage reproduces FK-7 at all -- the four camera dumps predate KXFORMFIX, so that is not yet known.";
    }
    Markerf("[WP] VERDICT: %s\r\n",v);
    Markerf("[WP] NEXT: %s\r\n",nxt);
    if(g_wpNewAtCorrupt>0)
        Markerf("[WP] *** W5 CAVEAT: the sweep immediately before the corruption armed %d NEW thread(s) -- coverage was not"
                " established at that instant, so a quiet result is VOID, not negative. ***\r\n",g_wpNewAtCorrupt);
    if(g_wpLogH!=INVALID_HANDLE_VALUE){ HANDLE h=g_wpLogH; g_wpLogH=INVALID_HANDLE_VALUE; CloseHandle(h); }
}
static void WpShutdown(){ WpDisarm("shutdown"); WpVerdict("final"); InterlockedExchange(&g_wpStop,1); }

static DWORD WINAPI WpThread(LPVOID){
    DWORD lastSweep=0, lastPoll=0;
    for(;;){
        if(InterlockedCompareExchange(&g_wpStop,0,0)) break;
        DWORD now=GetTickCount();
        if(!InterlockedCompareExchange(&g_wpArmed,0,0) && InterlockedCompareExchange(&g_wpArmReq,0,0) && !g_wpArmLogged){
            if(WpArm()){ lastSweep=GetTickCount(); g_wpLastCensus=lastSweep; }
        }
        if(InterlockedCompareExchange(&g_wpArmed,0,0)){
            // ---- retarget: VtGuard's stand-down path zeroes g_vtPCM; on re-resolve the address moves ----
            if(LooksLikePtr(g_vtPCM)&&g_vtOff!=0xFFFFFFFF&&(g_vtPCM+g_vtOff)!=g_wpAddr){
                Markerf("[WP] retarget: &Target moved 0x%llX -> 0x%llX (PCM re-resolved) -- disarming and re-arming\r\n",
                        (unsigned long long)g_wpAddr,(unsigned long long)(g_vtPCM+g_vtOff));
                WpDisarm("retarget"); g_wpArmLogged=false; InterlockedExchange(&g_wpArmReq,1);
            }
#if KWPROBE==1
            else if(now-lastSweep>=(DWORD)KWPSWEEPMS){ lastSweep=now; WpSweep(false); }
#endif
#if KWPROBE==2
            // Re-arm the page if the pending-slot overflow path left it open, or if something else
            // re-protected it. One VirtualQuery per tick; also the V4 detector while still armed.
            if(InterlockedCompareExchange(&g_wpUnprot,0,0)){
                MEMORY_BASIC_INFORMATION q{};
                if(VirtualQuery((void*)g_wpPage,&q,sizeof(q)) && q.Protect!=PAGE_READONLY){
                    DWORD tmp=0; VirtualProtect((void*)g_wpPage,g_wpPageSz,PAGE_READONLY,&tmp); }
                InterlockedExchange(&g_wpUnprot,0);
            }
            // trap-storm panic valve (per-second arm). The total-count arm lives in the handler.
            if(now-g_wpTpsTick>=1000){ LONG t=InterlockedCompareExchange(&g_wpTraps,0,0);
                LONG tps=t-g_wpTpsBase; g_wpTpsBase=t; g_wpTpsTick=now;
                if(tps>KWPMAXTPS){ WpPanicDisarm();
                    Markerf("[WP] *** TRAP STORM %ld/s > %d -> DISARMED (V6: the write window may not have been covered) ***\r\n",(long)tps,(int)KWPMAXTPS); } }
#endif
            if(InterlockedCompareExchange(&g_wpStorm,0,0) && InterlockedCompareExchange(&g_wpArmed,0,0)==0 && !g_wpVerdictDone)
                Marker("[WP] *** V6: disarmed by the panic valve; the remainder of the window is UNCOVERED ***\r\n");
            // ---- the poller: an INDEPENDENT detector on a different mechanism (the V5 void test) ----
#if KWPPOLLMS
            if(now-lastPoll>=(DWORD)KWPPOLLMS){ lastPoll=now; g_wpPolls++;
                uint64_t v=WpRead8(g_wpAddr);
                if(!g_wpPollHit&&WpCorruptShape(v)){ g_wpPollHit=true; g_wpPollHitTick=now; g_wpPollHitVal=v;
                    g_wpNewAtCorrupt=g_wpLastNew;
                    Markerf("[WP] *** POLL saw the corrupt shape at &Target: 0x%llX (t=+%lums after arm, %lums after body build) ***\r\n",
                            (unsigned long long)v,(unsigned long)(now-g_wpArmTick),(unsigned long)(g_wpBodyTick?now-g_wpBodyTick:0)); }
                if(!WpCorruptShape(v)&&v) g_wpPollLast=v;   // the "before" value the handler reports
            }
#endif
            WpDrain();
            // ---- D4: the loud one-time Dr6-unavailable notice. Emitted HERE, not in the handler, so the
            //      handler stays I/O-free. It is a behavioural warning, not a result. ----
            if(InterlockedCompareExchange(&g_wpDr6ZeroClaimed,0,0)>0 && InterlockedExchange(&g_wpDr6ZeroLogged,1)==0)
                Marker("[WP] *** INSTRUMENT CAVEAT: a trap arrived WITHOUT CONTEXT_DEBUG_REGISTERS, so Dr6 is"
                       " unreadable and 'is this ours?' has no direct answer. Such traps are claimed only when"
                       " EFlags.TF is CLEAR (a DR data breakpoint does not set TF), and single-steps with TF set"
                       " are handed back untouched. Width (B0/B1) attribution is UNAVAILABLE for these. ***\r\n");
            // ---- correlation: emitted the moment VtGuard reports the corruption ----
            { LONG cs=InterlockedCompareExchange(&g_wpCorruptSeen,0,0);
              if(cs>g_wpCorrelated){ g_wpCorrelated=cs;
                if(g_wpCorruptTrapTick && (DWORD)(g_wpCorruptTick-g_wpCorruptTrapTick)<2000)
                    Markerf("[WP]   correlate: last CORRUPTING trap rva=0x%llX was %lu ms before this [VTG] INVALID  => ATTRIBUTED\r\n",
                            (unsigned long long)g_wpLastCorruptRva,(unsigned long)(g_wpCorruptTick-g_wpCorruptTrapTick));
                else
                    Markerf("[WP]   correlate: *** NO CORRUPTING TRAP recorded before this [VTG] INVALID (val=0x%llX)"
                            " -- THE PROBE MISSED THE WRITER (VOID, not a negative) ***\r\n",(unsigned long long)g_wpCorruptVal);
                if(g_wpNewAtCorrupt<0) g_wpNewAtCorrupt=g_wpLastNew; } }
            // ★ S108b — the TRIGGER underflowed too, not just the display. `now` is sampled before
            // WpArm(), so g_wpLastCensus (set from a post-arm GetTickCount) is GREATER than `now` on the
            // first ticks and the unsigned compare comes out huge -> DR mode fired a bogus `t=+0s` census
            // immediately. Signed difference handles both that and the 49-day wrap. The first fix clamped
            // only the printed value, which hid the symptom and left the cause -- exactly the half-fix
            // this file keeps warning about.
            if((LONG)(now-g_wpLastCensus)>=30000){ g_wpLastCensus=now;
                // S108: `now` is sampled at the top of the loop, BEFORE WpArm() runs, and the arm sweep
                // takes >1 s over ~128 threads -- so g_wpArmTick lands AFTER `now` and the unsigned
                // subtraction underflowed to the nonsense `t=+4294966s` seen in S107's first census.
                // Clamped. S108 also reports selfPhase and vtHits so a NOT-YET selftest is attributable
                // at every census, not only at the one-shot 8 s deadline.
                Markerf("[WP] census t=+%lus traps=%ld tgt=%ld self=%ld corrupting=%ld distinctRVAs=%d armedTids=%d voidTids=%d selftest=%s selfPhase=%ld vtHits=%ld orphanSwallowed=%ld\r\n",
                        (unsigned long)((now>=g_wpArmTick)?((now-g_wpArmTick)/1000):0),
                        (long)InterlockedCompareExchange(&g_wpTraps,0,0),(long)InterlockedCompareExchange(&g_wpTrapsTgt,0,0),
                        (long)InterlockedCompareExchange(&g_wpTrapsSelf,0,0),(long)InterlockedCompareExchange(&g_wpCorruptTraps,0,0),
                        g_wpNSeenRva,g_wpNTids,g_wpVoidThreads,g_wpAnySelfTrap?"PASS":"NOT-YET",
                        (long)InterlockedCompareExchange(&g_wpSelfPhase,0,0),(long)InterlockedCompareExchange(&g_wpVtHits,0,0),
                        (long)InterlockedCompareExchange(&g_wpOrphanSwallowed,0,0)); }
#if KWPHOLDMS
            if(now-g_wpArmTick>=(DWORD)KWPHOLDMS){ WpDisarm("hold expired"); WpVerdict("hold-expired"); }
#endif
        }
        Sleep(KWPPOLLMS?((KWPPOLLMS<5)?(DWORD)KWPPOLLMS:5):5);
    }
    return 0;
}
// SELFTEST verdict is emitted once, as soon as it is decidable, so a sitting is never spent on a void.
// ★ S108 (2026-08-04) — REWRITTEN, and this is a correction of the instrument, not a tuning knob.
// S107 printed "selftest *** FAIL: no trap 8000 ms after arming (selfPhase=0) -- the watchpoint is
// VOID on the game thread" and the session escalated on it. But selfPhase only advances AFTER the
// idempotent store has RETIRED (WpSelfTestTick), so selfPhase=0 says the store NEVER EXECUTED. "The
// store ran and did not trap" (a real void) and "the store never ran" (no test happened at all) are
// different results with different next actions, and the old wording asserted the first while
// measuring the second -- the project's dominant error mode, inside the positive control built to
// prevent it. The deadline was also too short by construction: arming happens inside the one-shot
// RM_PLAY init block, which holds the game thread well past 8 s (S107: init completed between the
// +8 s FAIL and the +29 s census), so VtGuard could not reach the call site in time.
static DWORD WINAPI WpSelfWatch(LPVOID){
    bool announced8=false;
    for(;;){
        if(InterlockedCompareExchange(&g_wpStop,0,0)) return 0;
        if(InterlockedCompareExchange(&g_wpArmed,0,0)&&g_wpArmTick){
            if(g_wpAnySelfTrap){
                Markerf("[WP] selftest *** PASS: the idempotent store(s) trapped (8B->B0|B1 seen=%d, 1B->B0-only seen=%d)"
                        " -- THE WATCHPOINT IS LIVE ON THE GAME THREAD ***\r\n",(int)g_wpSelfB0B1,(int)g_wpSelfB0only);
                return 0; }
            DWORD el=GetTickCount()-g_wpArmTick;
            LONG  ph=InterlockedCompareExchange(&g_wpSelfPhase,0,0);
            LONG  vh=InterlockedCompareExchange(&g_wpVtHits,0,0);
            LONG  dt=InterlockedCompareExchange(&g_wpSelfDoneTick,0,0);
            // (a) THE ONLY SHAPE THAT LICENSES "VOID": both stores executed, then a drain grace window
            //     (the ring is drained at ~4 Hz) passed with no trap recorded.
            if(ph>=2 && dt && (GetTickCount()-(DWORD)dt)>2000){
                Markerf("[WP] selftest *** FAIL(VOID-WATCHPOINT): both idempotent stores EXECUTED (selfPhase=2,"
                        " vtHits=%ld) and NO trap was recorded 2000 ms later -- the watchpoint is genuinely VOID"
                        " on the game thread. READ NOTHING ELSE IN THIS RUN AS A NEGATIVE. ***\r\n",(long)vh);
                return 0; }
            // (b) NOT the same thing -- this is exactly where S107 printed FAIL.
            if(el>8000 && !announced8){ announced8=true;
                Markerf("[WP] selftest NOT-YET at 8000 ms: selfPhase=%ld vtHits=%ld -- the idempotent store has"
                        " NOT EXECUTED, so this is NOT evidence about the watchpoint (S107 read it as such and"
                        " escalated). VtGuard has not reached the selftest call site since arming. Still watching"
                        " to %d ms.\r\n",(long)ph,(long)vh,(int)KWPSELFWAITMS); }
            if(el>(DWORD)KWPSELFWAITMS){
                if(ph==0)
                    Markerf("[WP] selftest *** INCONCLUSIVE: selfPhase=0 vtHits=%ld after %lu ms -- the positive"
                            " control NEVER RAN, so the watchpoint is UNTESTED: this is neither 'live' nor 'void'."
                            " vtHits=0 => the game thread never re-entered VtGuard; vtHits>0 => the store bailed on"
                            " VtValid/SafeReadable. Do NOT escalate on this line alone. ***\r\n",
                            (long)vh,(unsigned long)el);
                else
                    Markerf("[WP] selftest *** FAIL(VOID-WATCHPOINT): selfPhase=%ld vtHits=%ld, the store executed"
                            " and no trap arrived within %lu ms -- watchpoint VOID on the game thread. READ NOTHING"
                            " ELSE IN THIS RUN AS A NEGATIVE. ***\r\n",(long)ph,(long)vh,(unsigned long)el);
                return 0; }
        }
        Sleep(100);
    }
}
// ═══════════════════════ end FK-24 watchpoint probe (back half) ═════════════════════════════════════
#endif  // KWPROBE

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
// ============ S90 RM_TRAINING — START the tutorial's own lesson system + COMMIT the drop ============
// WHY: S90 proved the FORCE-OPEN route instantiates the WHOLE tutorial machinery (BP_TrainingManager_C, four
// BP_TrainingSkill_* lessons, Comp_GameState_TrainingBase, Comp_PlayerController_BasicTrainingText, the
// TrainingVolume + ResetVolume, and Comp_PlayerController_TutorialObjectives added at runtime by the gamemode BP)
// — but NOTHING ever STARTS a lesson: the only LogLokiTraining line in a whole session is one
// ULokiTrainingManager::ResetAll. A live ufunc_survey of the manager gave us the API; this mode calls it.
// It also commits the DROP: the round parks at EGP_SpawnSelect(4) with the drop UI armed, and S90 proved
// UpdateIsInDropPod/FinishDropPhaseHiding are NOT the descent path (they fire fault-free and change nothing) —
// the DropPlane component is.
//   LokiTrainingManager (native):  SetActive [Static, Parms9 => (Object* Skill, bool)], StartTimers(), ResetAll(),
//                                  IsActiveSkill(q), HasTrainingPrompt(q), GetTrainingPrompt(q)
//   LokiGameModeDropPlaneComponent: AddPlayerToDropPlane(Parms8), SetDropPlane(Parms8) + BP SpawnPlane/GetAutoDropLocation
// Staged ONE step per game-thread hit so a fault localizes to a single native call.
static uintptr_t g_tmMgr=0, g_tmDrop=0, g_tmPC=0;
static uintptr_t g_tmSkills[8]={0}; static int g_tmNSkills=0;
static void*     g_tmSaFn=nullptr;  static uintptr_t g_tmSaThunk=0,  g_tmSaChild=0;   // SetActive
static void*     g_tmStFn=nullptr;  static uintptr_t g_tmStThunk=0,  g_tmStChild=0;   // StartTimers
static void*     g_tmIsFn=nullptr;  static uintptr_t g_tmIsThunk=0,  g_tmIsChild=0;   // IsActiveSkill
static void*     g_tmSpFn=nullptr;  static uintptr_t g_tmSpThunk=0,  g_tmSpChild=0;   // SpawnPlane
static void*     g_tmApFn=nullptr;  static uintptr_t g_tmApThunk=0,  g_tmApChild=0;   // AddPlayerToDropPlane
static void*     g_tmAaFn=nullptr;  static uintptr_t g_tmAaThunk=0,  g_tmAaChild=0;   // AddActiveTrainingAugment
static void*     g_tmCpFn=nullptr;  static uintptr_t g_tmCpThunk=0,  g_tmCpChild=0;   // ChangeSkillPrompt
static void*     g_tmGaFn=nullptr;  static uintptr_t g_tmGaThunk=0,  g_tmGaChild=0;   // GetAutoDropLocation
static void*     g_tmCaFn=nullptr;  static uintptr_t g_tmCaThunk=0,  g_tmCaChild=0;   // ContainsActiveTrainingAugment
static uint32_t  g_oSaWorld=0xFFFFFFFF, g_oSaFlag=0xFFFFFFFF, g_oApPS=0xFFFFFFFF;
static uint32_t  g_oIsSkill=0xFFFFFFFF, g_oIsRet=0xFFFFFFFF, g_oAaArg=0xFFFFFFFF, g_oCaArg=0xFFFFFFFF, g_oCaRet=0xFFFFFFFF;
static uintptr_t g_tmPS=0;          // PC->PlayerState (AddPlayerToDropPlane wants THIS, not the PC)
static int g_tmStep=0;
// ★ S90 iter3 — the REAL lesson lifecycle lives on the SKILL object (native LokiTrainingSkill), not the manager.
// iter2 proved manager-level SetActive/AddActiveTrainingAugment are the wrong level (all fault-free, zero effect;
// "augment" is a different type from "skill"). These are all ZERO-INPUT (Parms1/RetOff0 => a single byte RETURN),
// so the context object IS the skill and the result byte lands at params[0].
static void* g_skTtFn=nullptr;  static uintptr_t g_skTtThunk=0,  g_skTtChild=0;    // TryTestSkill      <- START
static void* g_skPrFn=nullptr;  static uintptr_t g_skPrThunk=0,  g_skPrChild=0;    // TryShowPrompt
static void* g_skMcFn=nullptr;  static uintptr_t g_skMcThunk=0,  g_skMcChild=0;    // MarkTestCompleted <- COMPLETE
static void* g_skCanFn=nullptr; static uintptr_t g_skCanThunk=0, g_skCanChild=0;   // CanTestSkill
static void* g_skShFn=nullptr;  static uintptr_t g_skShThunk=0,  g_skShChild=0;    // ShouldTestSkill
static void* g_skGsFn=nullptr;  static uintptr_t g_skGsThunk=0,  g_skGsChild=0;    // GetSkillState
static const bool kTrainMarkComplete = true;   // also close the loop with MarkTestCompleted
// ★ S90 iter4 — TELEPORT THE HERO INTO THE TRAINING VOLUME.
// iter3 ruled out hero-presence and round-phase as the gate (Can/Should stayed 0 with a possessed hero at Phase 4).
// The four live skills are contextual HINT prompts; the main lesson chain's trigger is the level-placed
// BP_TrainingVolume_Move_V2 (class BP_TrainingVolume_Basics_C) and ZERO basics-quest objects exist yet — consistent
// with the chain being spawned ON PLAYER ENTRY into that volume. So put the hero physically inside it.
static uintptr_t g_tmVol=0, g_tmHero=0;
static void*     g_tmSlFn=nullptr; static uintptr_t g_tmSlThunk=0, g_tmSlChild=0;   // K2_SetActorLocation (on the hero)
static uint32_t  g_oTmSlLoc=0xFFFFFFFF, g_oTmSlSweep=0xFFFFFFFF, g_oTmSlTele=0xFFFFFFFF;
static double    g_volX=0,g_volY=0,g_volZ=0;
static const double kVolZLift = 150.0;   // drop the hero slightly ABOVE the volume centre so it isn't inside geometry
static DWORD g_tmTeleMs=0;               // wall-clock of the teleport (the hook fires many times per frame, so the
                                         // post-teleport check must gate on REAL time, not on step count)
// Read an actor's world location via RootComponent->RelativeLocation (the RM_WAKEMOVE pattern).
static bool ActorLoc(uintptr_t actor,double* out){
    if(!LooksLikePtr(actor)) return false;
    uint32_t rc=PropOffsetSuper(ClassOf(actor),"RootComponent");
    if(rc==0xFFFFFFFF||!SafeReadable((void*)(actor+rc),8)) return false;
    uintptr_t r=*(uintptr_t*)(actor+rc); if(!LooksLikePtr(r)) return false;
    uint32_t lo=PropOffsetSuper(ClassOf(r),"RelativeLocation"); if(lo==0xFFFFFFFF) lo=0x158;
    if(!SafeReadable((void*)(r+lo),24)) return false;
    double* P=(double*)(r+lo); out[0]=P[0]; out[1]=P[1]; out[2]=P[2]; return true;
}
// Call a zero-input skill fn, return its byte result (0xFF on fault / unresolved).
static uint8_t SkillCall(void* fn,uintptr_t thunk,uintptr_t child,uintptr_t skill){
    if(!thunk) return 0xFE;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(CallNativeGuarded(fn,thunk,child,(void*)skill,g_pbuf,g_rbuf)) return 0xFF;
    return *(uint8_t*)g_pbuf;
}

// Print a UFunction's parameter chain (one line per param) so we LEARN the real names instead of guessing them.
static void DumpParams(uintptr_t child,const char* tag){
    uintptr_t f=child; int i=0;
    if(!LooksLikePtr(f)){ Markerf("[TRN] params %s: <none>\r\n",tag); return; }
    while(LooksLikePtr(f)&&i<16){
        char n[96]="?"; GetFNameStr(NameId(f),n,sizeof(n));
        uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
        uint64_t fl=SafeReadable((void*)(f+FPROP_FLAGS),8)?*(uint64_t*)(f+FPROP_FLAGS):0;
        Markerf("[TRN] params %s[%d] %s @0x%X flags=0x%llX\r\n",tag,i,n,off,(unsigned long long)fl);
        uintptr_t nx=0; if(SafeReadable((void*)(f+FIELD_NEXT),8))nx=*(uintptr_t*)(f+FIELD_NEXT); f=nx; i++;
    }
}
// Collect every live BP_TrainingSkill_* instance (the lessons).
static void CollectSkills(){
    g_tmNSkills=0;
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt && g_tmNSkills<8;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,"TrainingSkill"))continue; char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
            if(strncmp(on,"Default__",9)==0)continue;
            g_tmSkills[g_tmNSkills++]=obj; Markerf("[TRN] skill[%d]=0x%llX %s\r\n",g_tmNSkills-1,(unsigned long long)obj,cn); } }
}
static bool ResolveTraining(){
    g_tmMgr =FindInstByClass("TrainingManager",nullptr);
    g_tmDrop=FindInstByClass("DropPlane_Tutorial",nullptr);
    g_tmPC  =FindInstByClass("LokiPlayerController_Dev",nullptr);
    char mcn[96]="-",dcn[96]="-";
    if(g_tmMgr&&ClassOf(g_tmMgr))GetFNameStr(NameId(ClassOf(g_tmMgr)),mcn,sizeof(mcn));
    if(g_tmDrop&&ClassOf(g_tmDrop))GetFNameStr(NameId(ClassOf(g_tmDrop)),dcn,sizeof(dcn));
    Markerf("[TRN] mgr=0x%llX(%s) drop=0x%llX(%s) pc=0x%llX\r\n",(unsigned long long)g_tmMgr,mcn,(unsigned long long)g_tmDrop,dcn,(unsigned long long)g_tmPC);
    CollectSkills();
    if(g_tmMgr){ uintptr_t mc=ClassOf(g_tmMgr);
        ResolveFuncSuper(mc,"SetActive",&g_tmSaFn,&g_tmSaThunk,&g_tmSaChild);
        ResolveFuncSuper(mc,"StartTimers",&g_tmStFn,&g_tmStThunk,&g_tmStChild);
        ResolveFuncSuper(mc,"IsActiveSkill",&g_tmIsFn,&g_tmIsThunk,&g_tmIsChild);
        // S90 iter2: the probe recovered the REAL names — SetActive takes a WORLD CONTEXT, not a skill.
        ResolveFuncSuper(mc,"AddActiveTrainingAugment",&g_tmAaFn,&g_tmAaThunk,&g_tmAaChild);
        ResolveFuncSuper(mc,"ContainsActiveTrainingAugment",&g_tmCaFn,&g_tmCaThunk,&g_tmCaChild);
        ResolveFuncSuper(mc,"ChangeSkillPrompt",&g_tmCpFn,&g_tmCpThunk,&g_tmCpChild);
        if(g_tmSaChild){ DumpParams(g_tmSaChild,"SetActive");
            g_oSaWorld=ParamOffset(g_tmSaChild,"WorldContextObject"); if(g_oSaWorld==0xFFFFFFFF)g_oSaWorld=0;
            g_oSaFlag =ParamOffset(g_tmSaChild,"bActive");            if(g_oSaFlag ==0xFFFFFFFF)g_oSaFlag =8; }
        if(g_tmIsChild){ DumpParams(g_tmIsChild,"IsActiveSkill");
            g_oIsSkill=ParamOffset(g_tmIsChild,"TargetSkill"); if(g_oIsSkill==0xFFFFFFFF)g_oIsSkill=0;
            g_oIsRet  =ParamOffset(g_tmIsChild,"ReturnValue");  if(g_oIsRet==0xFFFFFFFF)g_oIsRet=8; }
        if(g_tmAaChild){ DumpParams(g_tmAaChild,"AddActiveTrainingAugment"); g_oAaArg=0; }   // single Parms8 arg
        if(g_tmCaChild){ DumpParams(g_tmCaChild,"ContainsActiveTrainingAugment"); g_oCaArg=0; g_oCaRet=8; }
        if(g_tmCpChild)  DumpParams(g_tmCpChild,"ChangeSkillPrompt");
    }
    if(g_tmDrop){ uintptr_t dc=ClassOf(g_tmDrop);
        ResolveFuncSuper(dc,"SpawnPlane",&g_tmSpFn,&g_tmSpThunk,&g_tmSpChild);
        ResolveFuncSuper(dc,"AddPlayerToDropPlane",&g_tmApFn,&g_tmApThunk,&g_tmApChild);
        ResolveFuncSuper(dc,"GetAutoDropLocation",&g_tmGaFn,&g_tmGaThunk,&g_tmGaChild);
        if(g_tmGaChild) DumpParams(g_tmGaChild,"GetAutoDropLocation");
        if(g_tmApChild){ DumpParams(g_tmApChild,"AddPlayerToDropPlane");
            g_oApPS=ParamOffset(g_tmApChild,"PlayerState"); if(g_oApPS==0xFFFFFFFF)g_oApPS=0; }
    }
    // iter4: the training VOLUME + the hero, and K2_SetActorLocation to put one inside the other.
    g_tmVol =FindInstByClass("TrainingVolume",nullptr);
    g_tmHero=FindInstByClass("BP_HERO_",nullptr);
    { double v[3]={0,0,0}; if(ActorLoc(g_tmVol,v)){ g_volX=v[0]; g_volY=v[1]; g_volZ=v[2]; }
      double h[3]={0,0,0}; ActorLoc(g_tmHero,h);
      char vn[128]="-"; if(g_tmVol) GetFNameStr(NameId(g_tmVol),vn,sizeof(vn));
      Markerf("[TRN] vol=0x%llX %s loc=(%.0f,%.0f,%.0f) | hero=0x%llX loc=(%.0f,%.0f,%.0f)\r\n",
        (unsigned long long)g_tmVol,vn,g_volX,g_volY,g_volZ,(unsigned long long)g_tmHero,h[0],h[1],h[2]); }
    if(g_tmHero){ ResolveFuncSuper(ClassOf(g_tmHero),"K2_SetActorLocation",&g_tmSlFn,&g_tmSlThunk,&g_tmSlChild);
        if(g_tmSlChild){ g_oTmSlLoc  =ParamOffset(g_tmSlChild,"NewLocation");
                         g_oTmSlSweep=ParamOffset(g_tmSlChild,"bSweep");
                         g_oTmSlTele =ParamOffset(g_tmSlChild,"bTeleport"); }
        Markerf("[TRN] heroSetLoc thunk=0x%llX (loc@0x%X sweep@0x%X tele@0x%X)\r\n",
            (unsigned long long)g_tmSlThunk,g_oTmSlLoc,g_oTmSlSweep,g_oTmSlTele); }
    // iter3: resolve the per-skill lifecycle on the skill's class (ResolveFuncSuper walks up to LokiTrainingSkill).
    if(g_tmNSkills>0){ uintptr_t sc=ClassOf(g_tmSkills[0]);
        ResolveFuncSuper(sc,"TryTestSkill",      &g_skTtFn, &g_skTtThunk, &g_skTtChild);
        ResolveFuncSuper(sc,"TryShowPrompt",     &g_skPrFn, &g_skPrThunk, &g_skPrChild);
        ResolveFuncSuper(sc,"MarkTestCompleted", &g_skMcFn, &g_skMcThunk, &g_skMcChild);
        ResolveFuncSuper(sc,"CanTestSkill",      &g_skCanFn,&g_skCanThunk,&g_skCanChild);
        ResolveFuncSuper(sc,"ShouldTestSkill",   &g_skShFn, &g_skShThunk, &g_skShChild);
        ResolveFuncSuper(sc,"GetSkillState",     &g_skGsFn, &g_skGsThunk, &g_skGsChild);
        Markerf("[TRN] skill-fns TryTest=0x%llX ShowPrompt=0x%llX MarkDone=0x%llX Can=0x%llX Should=0x%llX State=0x%llX\r\n",
            (unsigned long long)g_skTtThunk,(unsigned long long)g_skPrThunk,(unsigned long long)g_skMcThunk,
            (unsigned long long)g_skCanThunk,(unsigned long long)g_skShThunk,(unsigned long long)g_skGsThunk);
    }
    // AddPlayerToDropPlane wants a PLAYERSTATE (probe-confirmed). Fetch PC->PlayerState.
    if(g_tmPC){ uint32_t o=PropOffsetSuper(ClassOf(g_tmPC),"PlayerState");
        if(o!=0xFFFFFFFF && SafeReadable((void*)(g_tmPC+o),8)) g_tmPS=*(uintptr_t*)(g_tmPC+o);
        char psn[96]="-"; if(LooksLikePtr(g_tmPS)&&ClassOf(g_tmPS)) GetFNameStr(NameId(ClassOf(g_tmPS)),psn,sizeof(psn));
        Markerf("[TRN] PC->PlayerState@0x%X = 0x%llX (%s)\r\n",o,(unsigned long long)g_tmPS,psn); }
    Markerf("[TRN] thunks SetActive=0x%llX StartTimers=0x%llX IsActiveSkill=0x%llX SpawnPlane=0x%llX AddPlayer=0x%llX skills=%d\r\n",
        (unsigned long long)g_tmSaThunk,(unsigned long long)g_tmStThunk,(unsigned long long)g_tmIsThunk,
        (unsigned long long)g_tmSpThunk,(unsigned long long)g_tmApThunk,g_tmNSkills);
    return g_tmMgr!=0 && (g_tmSaThunk!=0 || g_tmStThunk!=0);
}
// ★★★ S90 iter7 GATE TRACE — MEASURE, don't infer. Each CanTestSkill gate is a PLAIN NATIVE function (not a
// UFunction), so we can call it DIRECTLY through a raw function pointer and log every intermediate value. Chain:
//   0x338C990(skill) -> world/outer     |  0x56BDF10(that)  -> PlayerState (type-checked vs LokiPlayerState)
//   0x58E3D10(skill) -> bool "disabled" |  0x56BAA00(PS)    -> level (returns 99 when dword[PS+0xE88]==-1)
//   0x58CE1B0(skill) -> CanTestSkill's own implementation
// Every call is SEH-guarded (a '!' suffix in the log marks a fault) so a bad one is captured, not fatal.
typedef uintptr_t (*PFN_1)(uintptr_t);
static bool RawCall1(uintptr_t rva,uintptr_t a,uintptr_t* out){
    PFN_1 f=(PFN_1)(g_modBase+rva);
    __try { *out=f(a); return false; }
    __except(SehDump(GetExceptionInformation())){ *out=0; return true; }
}
static void GateTrace(const char* tag){
    for(int i=0;i<g_tmNSkills;i++){
        uintptr_t sk=g_tmSkills[i], r1=0,r2=0,r3=0,r4=0,r5=0;
        bool f1=false,f2=false,f3=false,f4=false,f5=false;
        f1=RawCall1(0x338C990,sk,&r1);
        if(r1) f2=RawCall1(0x56BDF10,r1,&r2);
        f3=RawCall1(0x58E3D10,sk,&r3);
        if(r2) f4=RawCall1(0x56BAA00,r2,&r4);
        f5=RawCall1(0x58CE1B0,sk,&r5);
        char psn[96]="-"; if(r2&&ClassOf(r2)) GetFNameStr(NameId(ClassOf(r2)),psn,sizeof(psn));
        uint8_t b390=0,b391=0,b393=0,b3F0=0; float v3A8=0.f; int32_t lvlFld=0;
        if(SafeReadable((void*)(sk+0x390),1)) b390=*(uint8_t*)(sk+0x390);
        if(SafeReadable((void*)(sk+0x391),1)) b391=*(uint8_t*)(sk+0x391);
        if(SafeReadable((void*)(sk+0x393),1)) b393=*(uint8_t*)(sk+0x393);
        if(SafeReadable((void*)(sk+0x3F0),1)) b3F0=*(uint8_t*)(sk+0x3F0);
        if(SafeReadable((void*)(sk+0x3A8),4)) v3A8=*(float*)(sk+0x3A8);
        if(r2 && SafeReadable((void*)(r2+0xE88),4)) lvlFld=*(int32_t*)(r2+0xE88);
        Markerf("[GATE:%s] skill[%d] world=0x%llX%s PS=0x%llX(%s)%s disabled=%u%s level=%d%s PS+0xE88=%d CanTest=%u%s"
                " | b390=%u b391=%u b393=%u b3F0=%u f3A8=%.3f\r\n",
            tag,i,(unsigned long long)r1,f1?"!":"",(unsigned long long)r2,psn,f2?"!":"",
            (unsigned)(r3&0xFF),f3?"!":"",(int)(uint32_t)r4,f4?"!":"",lvlFld,(unsigned)(r5&0xFF),f5?"!":"",
            b390,b391,b393,b3F0,v3A8);
    }
}
// GAME THREAD: one step per hit. kTrainDoDrop gates the drop half so the lesson half can be tested alone.
static const bool kTrainDoDrop = true;
static void DoTraining(){
    uint8_t* pb=(uint8_t*)g_pbuf;
    switch(g_tmStep){
    case 0:   // ★ GATE TRACE first (measures which gate fails), then BEFORE state, then teleport
        GateTrace("pre");
        for(int i=0;i<g_tmNSkills;i++)
            Markerf("[TRN] BEFORE skill[%d] State=%u Can=%u Should=%u\r\n",i,
                SkillCall(g_skGsFn,g_skGsThunk,g_skGsChild,g_tmSkills[i]),
                SkillCall(g_skCanFn,g_skCanThunk,g_skCanChild,g_tmSkills[i]),
                SkillCall(g_skShFn,g_skShThunk,g_skShChild,g_tmSkills[i]));
        if(g_tmSlThunk && LooksLikePtr(g_tmHero) && (g_volX||g_volY||g_volZ)){
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            if(g_oTmSlLoc!=0xFFFFFFFF){ double* L=(double*)(pb+g_oTmSlLoc); L[0]=g_volX; L[1]=g_volY; L[2]=g_volZ+kVolZLift; }
            if(g_oTmSlSweep!=0xFFFFFFFF) pb[g_oTmSlSweep]=0;
            if(g_oTmSlTele !=0xFFFFFFFF) pb[g_oTmSlTele ]=1;   // teleport, no sweep
            bool f=CallNativeGuarded(g_tmSlFn,g_tmSlThunk,g_tmSlChild,(void*)g_tmHero,g_pbuf,g_rbuf);
            Markerf("[TRN] *** TELEPORT hero -> volume (%.0f,%.0f,%.0f)%s ***\r\n",g_volX,g_volY,g_volZ+kVolZLift,f?" FAULTED":"");
        } else Markerf("[TRN] TELEPORT SKIPPED (slThunk=0x%llX hero=0x%llX vol=(%.0f,%.0f,%.0f))\r\n",
            (unsigned long long)g_tmSlThunk,(unsigned long long)g_tmHero,g_volX,g_volY,g_volZ);
        g_tmTeleMs=GetTickCount();
        break;
    case 1:   // SETTLE on REAL time (the hook fires many times per frame) so overlap/BeginOverlap + quest spawn can run
        if(GetTickCount()-g_tmTeleMs < 5000) return;   // hold this step; do NOT advance yet
        { double h[3]={0,0,0}; ActorLoc(g_tmHero,h);
          Markerf("[TRN] post-teleport hero loc=(%.0f,%.0f,%.0f)\r\n",h[0],h[1],h[2]); }
        for(int i=0;i<g_tmNSkills;i++)
            Markerf("[TRN] POST-TP skill[%d] State=%u Can=%u Should=%u\r\n",i,
                SkillCall(g_skGsFn,g_skGsThunk,g_skGsChild,g_tmSkills[i]),
                SkillCall(g_skCanFn,g_skCanThunk,g_skCanChild,g_tmSkills[i]),
                SkillCall(g_skShFn,g_skShThunk,g_skShChild,g_tmSkills[i]));
        break;
    case 2:   // now try the lifecycle again, with the hero standing in the volume
        if(g_tmSaThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            *(uint64_t*)(pb+g_oSaWorld)=(uint64_t)(g_tmPC?g_tmPC:g_tmMgr); pb[g_oSaFlag]=1;
            CallNativeGuarded(g_tmSaFn,g_tmSaThunk,g_tmSaChild,(void*)g_tmMgr,g_pbuf,g_rbuf); }
        for(int i=0;i<g_tmNSkills;i++)
            Markerf("[TRN] TryShowPrompt(skill[%d]) -> %u\r\n",i,SkillCall(g_skPrFn,g_skPrThunk,g_skPrChild,g_tmSkills[i]));
        for(int i=0;i<g_tmNSkills;i++)
            Markerf("[TRN] *** TryTestSkill(skill[%d]) -> %u ***\r\n",i,SkillCall(g_skTtFn,g_skTtThunk,g_skTtChild,g_tmSkills[i]));
        break;
    case 3:
        if(g_tmStThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            bool f=CallNativeGuarded(g_tmStFn,g_tmStThunk,g_tmStChild,(void*)g_tmMgr,g_pbuf,g_rbuf);
            Markerf("[TRN] StartTimers()%s\r\n",f?" FAULTED":""); }
        break;
    case 4:   // MID: did TryTestSkill change the state? (a few game-thread ticks have passed since step 2)
        for(int i=0;i<g_tmNSkills;i++)
            Markerf("[TRN] MID skill[%d] State=%u Can=%u Should=%u\r\n",i,
                SkillCall(g_skGsFn,g_skGsThunk,g_skGsChild,g_tmSkills[i]),
                SkillCall(g_skCanFn,g_skCanThunk,g_skCanChild,g_tmSkills[i]),
                SkillCall(g_skShFn,g_skShThunk,g_skShChild,g_tmSkills[i]));
        break;
    case 5:   // close the loop: mark the test completed (the "objective complete" path)
        if(kTrainMarkComplete) for(int i=0;i<g_tmNSkills;i++)
            Markerf("[TRN] MarkTestCompleted(skill[%d]) -> %u\r\n",i,SkillCall(g_skMcFn,g_skMcThunk,g_skMcChild,g_tmSkills[i]));
        break;
    default:
        for(int i=0;i<g_tmNSkills;i++){
            uint8_t act=0xFF;
            if(g_tmIsThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                *(uint64_t*)(pb+g_oIsSkill)=(uint64_t)g_tmSkills[i];
                if(!CallNativeGuarded(g_tmIsFn,g_tmIsThunk,g_tmIsChild,(void*)g_tmMgr,g_pbuf,g_rbuf)) act=pb[g_oIsRet]; }
            Markerf("[TRN] FINAL skill[%d] State=%u IsActiveSkill=%u\r\n",i,
                SkillCall(g_skGsFn,g_skGsThunk,g_skGsChild,g_tmSkills[i]),act);
        }
        GateTrace("post");
        Marker("[TRN] sequence complete\r\n"); g_done=1; break;
    }
    g_tmStep++;
}

// ★★★ S90 iter11 RM_SPAWNSEQ — SPAWN `BP_TutorialTrainingQuestSequencer_C` DIRECTLY.
// WHY: iter9/iter10 established the tutorial's lesson chain is `TrainingQuest_Basics_*` driven by
// `BP_TutorialTrainingQuestSequencer_C` (its ubergraph casts collection items to Training_Quest_Basics_Base and
// reads their AssociatedTrainingVolume). That actor has ZERO live instances — it is level-placed and its
// WorldPartition cell / data-layer never activates on the force-open travel — while its trigger volume
// `BP_TrainingVolume_Move_V2` IS live. Spawning it should run `BP_LokiBeginPlay` -> `ReadyToFire` and populate the
// chain. (The 4 TrainingSkill objects are a PRACTICE-mode system — ValidStates excludes the tutorial — dead end.)
// Uses the S74-proven GameplayStatics deferred-spawn path (Begin -> Finish), the same one that spawns heroes.
static uintptr_t g_seqClass=0, g_seqActor=0; static int g_seqStep=0; static DWORD g_seqMs=0;
static int CountByClassSub(const char* sub,char* firstOut,int cap){
    int n=0; if(firstOut&&cap) firstOut[0]=0;
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[128]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,sub))continue; char on[128]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on));
            if(strncmp(on,"Default__",9)==0)continue;
            if(n==0&&firstOut&&cap) _snprintf_s(firstOut,cap,_TRUNCATE,"%s",cn);
            n++; } }
    return n;
}
static bool ResolveSpawnSeq(){
    g_seqClass=FindClassExact("BP_TutorialTrainingQuestSequencer_C");
    g_gm2  =FindInstByClass("GameMode_Tutorial",nullptr);
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    uintptr_t vol=FindInstByClass("TrainingVolume",nullptr);
    double v[3]={0,0,0}; bool haveV=ActorLoc(vol,v);
    if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO); uint32_t o;
        ResolveFuncOnClass(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
        ResolveFuncOnClass(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
        if(g_beginChild){ o=ParamOffset(g_beginChild,"WorldContextObject");if(o!=0xFFFFFFFF)g_oBWorld=o;
                          o=ParamOffset(g_beginChild,"ActorClass");if(o!=0xFFFFFFFF)g_oBClass=o;
                          o=ParamOffset(g_beginChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oBXform=o;
                          o=ParamOffset(g_beginChild,"CollisionHandlingOverride");if(o!=0xFFFFFFFF)g_oBColl=o;
                          o=ParamOffset(g_beginChild,"Owner");if(o!=0xFFFFFFFF)g_oBOwner=o;
                          o=ParamOffset(g_beginChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oBRet=o; }
        if(g_finishChild){ o=ParamOffset(g_finishChild,"Actor");if(o!=0xFFFFFFFF)g_oFActor=o;
                           o=ParamOffset(g_finishChild,"SpawnTransform");if(o!=0xFFFFFFFF)g_oFXform=o;
                           o=ParamOffset(g_finishChild,"ReturnValue");if(o!=0xFFFFFFFF)g_oFRet=o; }
    }
    // FTransform (LWC doubles): Rotation quat @0x00 (W@0x18), Translation @0x20, Scale3D @0x38.
    memset(g_xform,0,sizeof(g_xform));
    *(double*)(g_xform+0x18)=1.0;                                   // identity quat
    if(haveV){ *(double*)(g_xform+0x20)=v[0]; *(double*)(g_xform+0x28)=v[1]; *(double*)(g_xform+0x30)=v[2]; }
    XfScale(1.0,1.0,1.0);   // S106d: was 0x38/0x40/0x48 -> Scale.Z stayed 0. See KXFORMFIX (L109).
    Markerf("[SEQ] seqClass=0x%llX gm=0x%llX gsCDO=0x%llX begin=0x%llX finish=0x%llX vol=(%.0f,%.0f,%.0f)\r\n",
        (unsigned long long)g_seqClass,(unsigned long long)g_gm2,(unsigned long long)g_gsCDO,
        (unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,v[0],v[1],v[2]);
    { char f1[128],f2[128];
      Markerf("[SEQ] BEFORE: TrainingQuest=%d  Sequencer=%d\r\n",
        CountByClassSub("TrainingQuest",f1,sizeof(f1)),CountByClassSub("QuestSequencer",f2,sizeof(f2))); }
    return g_seqClass && g_beginThunk && g_finishThunk && g_gm2 && g_gsCDO;
}
static void DoSpawnSeq(){
    if(g_seqStep==0){
        const uint32_t xfsz=XfSize();   // S106d: was a hard 0x50, which truncated exactly AT Scale3D.Z.
        memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)(g_gsbuf+g_oBWorld)=(uint64_t)g_gm2;
        *(uint64_t*)(g_gsbuf+g_oBClass)=(uint64_t)g_seqClass;
        memcpy(g_gsbuf+g_oBXform,g_xform,xfsz);
        g_gsbuf[g_oBColl]=2;   // AdjustIfPossibleButAlwaysSpawn
        if(CallNativeGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_gsbuf,g_rbuf)){
            Marker("[SEQ] BeginDeferredActorSpawnFromClass FAULTED\r\n"); g_done=1; return; }
        uintptr_t def=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(def)) def=*(uint64_t*)(g_gsbuf+g_oBRet);
        char dn[96]="-"; if(LooksLikePtr(def)&&ClassOf(def)) GetFNameStr(NameId(ClassOf(def)),dn,sizeof(dn));
        Markerf("[SEQ] deferred=0x%llX cls=%s\r\n",(unsigned long long)def,dn);
        if(!LooksLikePtr(def)){ Marker("[SEQ] Begin returned NULL -> abort\r\n"); g_done=1; return; }
        memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)(g_gsbuf+g_oFActor)=(uint64_t)def;
        memcpy(g_gsbuf+g_oFXform,g_xform,xfsz);
        if(CallNativeGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_gsbuf,g_rbuf)){
            Marker("[SEQ] FinishSpawningActor FAULTED\r\n"); g_done=1; return; }
        uintptr_t act=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(act)) act=*(uint64_t*)(g_gsbuf+g_oFRet);
        if(!LooksLikePtr(act)) act=def;
        g_seqActor=act;
        char an[96]="-"; if(ClassOf(act)) GetFNameStr(NameId(ClassOf(act)),an,sizeof(an));
        Markerf("[SEQ] *** SPAWNED sequencer=0x%llX cls=%s (BeginPlay should now run ReadyToFire) ***\r\n",
            (unsigned long long)act,an);
        g_seqMs=GetTickCount(); g_seqStep++; return;
    }
    if(GetTickCount()-g_seqMs < 8000) return;   // let BeginPlay / ReadyToFire run for 8s of REAL time
    char f1[128],f2[128],f3[128];
    int nq=CountByClassSub("TrainingQuest",f1,sizeof(f1));
    int ns=CountByClassSub("QuestSequencer",f2,sizeof(f2));
    int nv=CountByClassSub("TrainingVolume",f3,sizeof(f3));
    Markerf("[SEQ] AFTER: TrainingQuest=%d (%s)  Sequencer=%d (%s)  TrainingVolume=%d (%s)\r\n",
        nq,nq?f1:"-",ns,ns?f2:"-",nv,nv?f3:"-");
    Marker("[SEQ] done\r\n"); g_done=1;
}

// ★★★ S91 RM_SPAWNQUEST — SPAWN THE `TrainingQuest_Basics_*` ACTORS DIRECTLY.
// WHY (S90 handoff): the tutorial's lesson chain is `TrainingQuest_Basics_*` (Actors, 33 assets under
// .../GameModes/Objectives/Tutorial/Basics/) coordinated by `BP_TutorialTrainingQuestSequencer_C`. S90 proved
// (a) the GameplayStatics deferred-spawn path works for arbitrary level actors — it spawned the sequencer — and
// (b) spawning the SEQUENCER ALONE populates nothing, because its `ReadyToFire` takes a quest CLASS param (it is
// FED, not a spawner) and its ubergraph iterates its own `TrainingQuests` SET (level-populated, empty for us),
// casting each item to `TrainingQuest_Basics_Base_C` and reading that item's `AssociatedTrainingVolume`.
// ⇒ the missing half is the quest ACTORS themselves. `TrainingQuest_Basics_Base_C` IS an Actor (DefaultSceneRoot +
// SCS node), so the same proven path applies.
// DESIGN NOTES:
//  - Classes are DISCOVERED at runtime by substring, not hard-coded: only a LOADED UClass can be spawned, and the
//    bytecode uses both spellings (`TrainingQuest_Basics_Base_C` / a local named `..._AsTraining_Quest_Basics_Base`).
//    Discovery also tells us — for free, in the marker — exactly which quest classes the process has resident.
//  - Bases (`_Base_C`, `_Level_Base_C`, `_UseAbility_Base_C`), CDOs (`Default__`) and SKEL_ stubs are excluded.
//  - Spawn ORDER is the lesson order (WASD -> Jump -> LMB -> ...), one per game-thread hit with a real-time gap so
//    each BeginPlay runs before the next; then the SEQUENCER last (if none is live) so its BeginPlay can collect
//    quests that already exist.
//  - Then: census, dump `AssociatedTrainingVolume` per quest, and — clearly labelled as a SECOND experiment —
//    poke any null one to the live `BP_TrainingVolume_Move_V2` and re-observe. Data write only, no .text patch.
#ifndef KQUESTMAX
#define KQUESTMAX 4          // how many quests to spawn this run (build with -DKQUESTMAX=N; 0 = discovery census only)
#endif
#ifndef KQUESTSEQ
#define KQUESTSEQ 1          // also spawn the sequencer AFTER the quests (0 = quests only)
#endif
#ifndef KQUESTPOKEVOL
#define KQUESTPOKEVOL 1      // phase 2: poke a null AssociatedTrainingVolume to the live volume, then re-observe
#endif
static const int  kQuestMax     = KQUESTMAX;
static const bool kQuestSeq     = KQUESTSEQ!=0;
static const bool kQuestPokeVol = KQUESTPOKEVOL!=0;
// Lesson order (first match wins); anything discovered but unlisted sorts after these, in discovery order.
static const char* kQuestOrder[]={"_WASD","_Jump","_LMB","_Glide","_RMB_Use","_Q_Use","_Dash_Use","_CapturePoint",
                                  "_Ult_Level","_DefeatSingleBot","_DefeatBots","_Ping","_Recall"};
#define QCAP 48
static uintptr_t g_qCls[QCAP]={0}; static char g_qName[QCAP][96]; static int g_qN=0;
static uintptr_t g_qAct[QCAP]={0}; static int g_qStep=0, g_qToSpawn=0, g_qOk=0; static DWORD g_qMs=0;
static uintptr_t g_qVol=0; static uint32_t g_qVolOff=0xFFFFFFFF; static int g_qPoked=0;

// Enumerate LOADED UCLASSES whose own FName contains `sub` (a UClass = its own class name contains "Class",
// the FindClassExact discriminator). Fills g_qCls/g_qName.
static void DiscoverQuestClasses(const char* sub){
    g_qN=0;
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt && g_qN<QCAP;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            char on[128]; if(!GetFNameStr(NameId(obj),on,sizeof(on)))continue;
            if(!strstr(on,sub))continue;
            if(strncmp(on,"Default__",9)==0||strncmp(on,"SKEL_",5)==0||strstr(on,"Sequencer"))continue;
            uintptr_t c=ClassOf(obj); if(!LooksLikePtr(c))continue;
            char cn[96]; if(!GetFNameStr(NameId(c),cn,sizeof(cn))||!strstr(cn,"Class"))continue;   // it IS a UClass
            bool dup=false; for(int k=0;k<g_qN;k++) if(g_qCls[k]==obj){dup=true;break;} if(dup)continue;
            g_qCls[g_qN]=obj; _snprintf_s(g_qName[g_qN],sizeof(g_qName[0]),_TRUNCATE,"%s",on); g_qN++; } }
    // Order: kQuestOrder matches first (in list order), everything else after in discovery order. Bases sort LAST
    // and are never spawned (they are abstract-ish parents; spawning one would add a no-op actor).
    int w=0; const int nOrd=(int)(sizeof(kQuestOrder)/sizeof(kQuestOrder[0]));
    for(int o=0;o<nOrd;o++){ for(int i=w;i<g_qN;i++){ if(strstr(g_qName[i],kQuestOrder[o])){
            uintptr_t tc=g_qCls[i]; char tn[96]; memcpy(tn,g_qName[i],sizeof(tn));
            for(int k=i;k>w;k--){ g_qCls[k]=g_qCls[k-1]; memcpy(g_qName[k],g_qName[k-1],sizeof(tn)); }
            g_qCls[w]=tc; memcpy(g_qName[w],tn,sizeof(tn)); w++; break; } } }
}
static bool IsQuestBase(const char* n){ return strstr(n,"_Base_C")!=nullptr; }

// Factored from DoSpawnSeq: the S74-proven deferred spawn. Returns the actor (0 on failure).
static uintptr_t SpawnActorCls(uintptr_t cls,const char* tag){
    // ★ S106d — was a hard `0x50`, i.e. EVERY actor this function has ever spawned got Scale3D.Z = 0
    // (the copy stopped exactly at the Scale.Z qword @0x50). That includes the top-down CameraActor
    // that becomes PCM->ViewTarget.Target, the KTESTACTOR test body and the KSMACTOR mesh actor.
    const uint32_t xfsz=XfSize();
    { static bool s_once=false; if(!s_once){ s_once=true;
        Markerf("[XF] KXFORMFIX=%d  Scale3D@0x%X  copy=0x%X bytes  (B.xform@0x%X coll@0x%X)  scale=(%.2f,%.2f,%.2f)\r\n",
                (int)KXFORMFIX,kXfScaleOff,xfsz,g_oBXform,g_oBColl,
                *(double*)(g_xform+kXfScaleOff),*(double*)(g_xform+kXfScaleOff+8),*(double*)(g_xform+kXfScaleOff+0x10)); } }
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_gsbuf+g_oBWorld)=(uint64_t)g_gm2;
    *(uint64_t*)(g_gsbuf+g_oBClass)=(uint64_t)cls;
    memcpy(g_gsbuf+g_oBXform,g_xform,xfsz);
    g_gsbuf[g_oBColl]=2;   // AdjustIfPossibleButAlwaysSpawn
    if(CallNativeGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_gsbuf,g_rbuf)){
        Markerf("[QST] %s BeginDeferred FAULTED\r\n",tag); return 0; }
    uintptr_t def=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(def)) def=*(uint64_t*)(g_gsbuf+g_oBRet);
    if(!LooksLikePtr(def)){ Markerf("[QST] %s BeginDeferred -> NULL\r\n",tag); return 0; }
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_gsbuf+g_oFActor)=(uint64_t)def;
    memcpy(g_gsbuf+g_oFXform,g_xform,xfsz);
    if(CallNativeGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_gsbuf,g_rbuf)){
        Markerf("[QST] %s FinishSpawning FAULTED (deferred actor 0x%llX left half-built)\r\n",tag,(unsigned long long)def); return def; }
    // ★ S96: report EXACTLY what FinishSpawningActor returned. If it yields null we silently fall back to the
    //   UNFINISHED deferred actor -> PostActorConstruction/RegisterAllComponents never run -> its primitives never get
    //   a SceneProxy -> nothing it owns can EVER render. That is the leading explanation for the invisible hero.
    uintptr_t retRes=(uintptr_t)g_rbuf[0];
    uintptr_t retPar=(g_oFRet!=0xFFFFFFFF)?*(uint64_t*)(g_gsbuf+g_oFRet):0;
    uintptr_t act=retRes; if(!LooksLikePtr(act)) act=retPar; bool fell=false; if(!LooksLikePtr(act)){ act=def; fell=true; }
    Markerf("[QST] %s FinishSpawning -> res=0x%llX par=0x%llX%s | proxy(root)=%s\r\n",tag,
        (unsigned long long)retRes,(unsigned long long)retPar, fell?"  *** BOTH NULL -> using UNFINISHED deferred actor ***":"",
        [&]{ static char b[24]; uint32_t ro=LooksLikePtr(act)?PropOffsetSuper(ClassOf(act),"RootComponent"):0xFFFFFFFF;
             uintptr_t rc=(ro!=0xFFFFFFFF&&SafeReadable((void*)(act+ro),8))?*(uint64_t*)(act+ro):0;
             uint64_t px=(LooksLikePtr(rc)&&SafeReadable((void*)(rc+0x2B0),8))?*(uint64_t*)(rc+0x2B0):0;
             _snprintf_s(b,sizeof(b),_TRUNCATE,"%s",px?"SET":"null"); return b; }());
    return act;
}
// Dump an object's reflected properties (name @offset = qword, + the class name if it points at a UObject).
static void DumpObjProps(uintptr_t obj,const char* tag,int maxN){
    uintptr_t cls=ClassOf(obj); int g=0,n=0;
    while(LooksLikePtr(cls)&&g++<4&&n<maxN){
        char cn[96]="?"; GetFNameStr(NameId(cls),cn,sizeof(cn));
        uintptr_t f=SafeReadable((void*)(cls+0x58),8)?*(uintptr_t*)(cls+0x58):0; int i=0;
        while(LooksLikePtr(f)&&i<200&&n<maxN){
            char pn[96]="?"; GetFNameStr(NameId(f),pn,sizeof(pn));
            uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
            uint64_t v=0; if(off!=0xFFFFFFFF&&SafeReadable((void*)(obj+off),8)) v=*(uint64_t*)(obj+off);
            char vc[96]="-"; ObjClassName(v,vc,sizeof(vc));
            Markerf("[QST] %s prop %s::%s @0x%X = 0x%llX (%s)\r\n",tag,cn,pn,off,(unsigned long long)v,vc);
            n++; f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; i++;
        }
        cls=SafeReadable((void*)(cls+0x48),8)?*(uintptr_t*)(cls+0x48):0;
    }
}
static void QuestCensus(const char* when){
    char f1[128],f2[128],f3[128];
    int nq=CountByClassSub("Quest_Basics",f1,sizeof(f1));     // ⚠ NOT "TrainingQuest" — that also matches the Sequencer
    int ns=CountByClassSub("QuestSequencer",f2,sizeof(f2));
    int nv=CountByClassSub("TrainingVolume",f3,sizeof(f3));
    Markerf("[QST] CENSUS %s: Quest_Basics=%d (%s)  Sequencer=%d (%s)  TrainingVolume=%d (%s)\r\n",
        when,nq,nq?f1:"-",ns,ns?f2:"-",nv,nv?f3:"-");
}
static bool ResolveSpawnQuest(){
    // Reuse the SEQ resolver for GameMode + GameplayStatics Begin/Finish + the spawn FTransform (already
    // Scale3D=1.0 and placed at the live training volume). Its bool also demands the sequencer class, which we
    // do NOT require, so check our own pieces instead of its return.
    ResolveSpawnSeq();
    g_qVol=FindInstByClass("TrainingVolume",nullptr);
    DiscoverQuestClasses("Quest_Basics");
    Markerf("[QST] discovered %d loaded quest CLASSES (spawn order; bases excluded from spawning):\r\n",g_qN);
    for(int i=0;i<g_qN;i++) Markerf("[QST]   [%02d] %s @0x%llX%s\r\n",i,g_qName[i],(unsigned long long)g_qCls[i],IsQuestBase(g_qName[i])?"   <base, skipped>":"");
    // Pick the spawn set: the first kQuestMax non-base classes, compacted to the front.
    int w=0; for(int i=0;i<g_qN && w<kQuestMax;i++){ if(IsQuestBase(g_qName[i]))continue;
        if(w!=i){ g_qCls[w]=g_qCls[i]; memcpy(g_qName[w],g_qName[i],sizeof(g_qName[0])); } w++; }
    g_qToSpawn=w;
    QuestCensus("BEFORE");
    Markerf("[QST] gm=0x%llX gsCDO=0x%llX begin=0x%llX finish=0x%llX vol=0x%llX toSpawn=%d seqAfter=%d pokeVol=%d\r\n",
        (unsigned long long)g_gm2,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,
        (unsigned long long)g_finishThunk,(unsigned long long)g_qVol,g_qToSpawn,(int)kQuestSeq,(int)kQuestPokeVol);
    if(g_qN==0) Marker("[QST] *** NO TrainingQuest_Basics_* UCLASS IS LOADED — the assets are not resident, so no\r\n"
                       "[QST]     spawn is possible from here. Next step would be an async class load, not a spawn.\r\n");
    return g_beginThunk && g_finishThunk && g_gm2 && g_gsCDO && g_qToSpawn>0;
}
// Staged ONE action per game-thread hit (with a real-time gap) so a fault localizes to a single spawn.
//   steps [0 .. N-1] : spawn quest i          step N : spawn the sequencer (if none live)
//   step N+1         : settle 8s -> census + per-quest AssociatedTrainingVolume
//   step N+2         : (phase 2) poke null volumes -> settle 5s -> census again -> done
static void DoSpawnQuest(){
    if(g_qMs && GetTickCount()-g_qMs < 400) return;   // let each BeginPlay run for real time between actions
    if(g_qStep < g_qToSpawn){
        int i=g_qStep;
        uintptr_t a=SpawnActorCls(g_qCls[i],g_qName[i]); g_qAct[i]=a;
        char an[96]="-"; if(LooksLikePtr(a)&&ClassOf(a)) GetFNameStr(NameId(ClassOf(a)),an,sizeof(an));
        Markerf("[QST] [%d/%d] spawn %s -> 0x%llX cls=%s\r\n",i+1,g_qToSpawn,g_qName[i],(unsigned long long)a,an);
        if(LooksLikePtr(a)) g_qOk++;
        g_qMs=GetTickCount(); g_qStep++; return;
    }
    if(g_qStep == g_qToSpawn){
        g_qStep++; g_qMs=GetTickCount();
        if(kQuestSeq){
            int ns=CountByClassSub("QuestSequencer",nullptr,0);
            if(ns>0){ Markerf("[QST] sequencer already live (%d) -> not spawning another\r\n",ns); }
            else if(g_seqClass){
                uintptr_t s=SpawnActorCls(g_seqClass,"BP_TutorialTrainingQuestSequencer_C");
                Markerf("[QST] sequencer spawned AFTER the quests -> 0x%llX (its BeginPlay can now see them)\r\n",(unsigned long long)s);
            } else Marker("[QST] sequencer class not loaded -> skipped\r\n");
        }
        return;
    }
    if(g_qStep == g_qToSpawn+1){
        if(GetTickCount()-g_qMs < 8000) return;   // 8s of real time for BeginPlay / ReadyToFire / any binding
        QuestCensus("AFTER");
        for(int i=0;i<g_qToSpawn;i++){
            if(!LooksLikePtr(g_qAct[i]))continue;
            uint32_t vo=PropOffsetSuper(ClassOf(g_qAct[i]),"AssociatedTrainingVolume");
            uint64_t v=0; if(vo!=0xFFFFFFFF&&SafeReadable((void*)(g_qAct[i]+vo),8)) v=*(uint64_t*)(g_qAct[i]+vo);
            char vc[96]="-"; ObjClassName(v,vc,sizeof(vc));
            Markerf("[QST] quest[%d] %s @0x%llX AssociatedTrainingVolume@0x%X = 0x%llX (%s)\r\n",
                i,g_qName[i],(unsigned long long)g_qAct[i],vo,(unsigned long long)v,vc);
            if(i==0){ g_qVolOff=vo; DumpObjProps(g_qAct[i],"q0",48); }   // full property picture for the first quest
        }
        g_qStep++; g_qMs=GetTickCount();
        if(!kQuestPokeVol){ Marker("[QST] done (no volume poke)\r\n"); g_done=1; }
        return;
    }
    if(g_qStep == g_qToSpawn+2){
        // ── PHASE 2 (separate, clearly-labelled experiment): if the spawn did NOT bind the quest to a volume,
        //    wire it by hand to the live BP_TrainingVolume_Move_V2 and see whether anything starts.
        for(int i=0;i<g_qToSpawn;i++){
            if(!LooksLikePtr(g_qAct[i])||g_qVolOff==0xFFFFFFFF||!LooksLikePtr(g_qVol))continue;
            if(!SafeReadable((void*)(g_qAct[i]+g_qVolOff),8))continue;
            if(*(uint64_t*)(g_qAct[i]+g_qVolOff))continue;                 // already bound — leave it alone
            *(uint64_t*)(g_qAct[i]+g_qVolOff)=(uint64_t)g_qVol; g_qPoked++;
        }
        Markerf("[QST] PHASE2 poked AssociatedTrainingVolume=0x%llX on %d quest(s); settling 5s...\r\n",(unsigned long long)g_qVol,g_qPoked);
        g_qStep++; g_qMs=GetTickCount(); return;
    }
    if(GetTickCount()-g_qMs < 5000) return;
    QuestCensus("AFTER-POKE");
    Marker("[QST] done\r\n"); g_done=1;
}

// ★★★ S91 RM_QUESTPLAY — PLAY the first lesson: put the possessed hero inside the quest's own trigger.
// WHY: RM_SPAWNQUEST proved the quest actors spawn, survive, and SELF-WIRE — a freshly spawned
// `TrainingQuest_Basics_WASD_C` came up with `TargetTriggerBox` pointing at a LIVE `TriggerBox` and `OBJARROW` at a
// live `BP_GameplayEffectCapsule_Tutorial_OBJ_LOC_C`, i.e. its BeginPlay ran and resolved level actors. It also
// revealed the real inheritance: quest -> `TrainingQuest_Basics_Base_C` -> `BP_TeamAugment_Training_C` ->
// `BP_TeamAugment_C` -> native `TeamAugment`. The WASD lesson's own graph is `OnWASDTriggerOverlap` bound to that
// TriggerBox, so the INTENDED gameplay trigger is a physical overlap — no BP-call hack needed (and the BP path is
// closed anyway: every function on the chain is bytecode, so the direct-thunk primitive cannot dispatch it, and
// S80 falsified our ProcessEvent RVA).
// ⇒ teleport the possessed hero into `TargetTriggerBox` and let the game's own overlap start the lesson.
// Also (build flag) re-spawn a WASD quest FIRST, so this one's BeginPlay runs with a hero already present.
#ifndef KQPSPAWN
#define KQPSPAWN 1        // spawn a fresh WASD quest before playing (its BeginPlay then sees the possessed hero)
#endif
static const bool kQpSpawn = KQPSPAWN!=0;
static uintptr_t g_qpHero=0, g_qpQuest=0, g_qpBox=0, g_qpVol=0;
static void*     g_qpSlFn=nullptr; static uintptr_t g_qpSlThunk=0, g_qpSlChild=0;
static uint32_t  g_oQpLoc=0xFFFFFFFF, g_oQpSweep=0xFFFFFFFF, g_oQpTele=0xFFFFFFFF;
static double    g_qpDst[3]={0,0,0}; static int g_qpStep=0; static DWORD g_qpMs=0; static int g_qpTry=0;
// Sample the augment/quest progress fields (native TeamAugment OnRep_* names give us the property names).
static void QuestState(uintptr_t q,const char* tag){
    if(!LooksLikePtr(q))return;
    static const char* kF[]={"CurrentObjectiveCount","HasMetObjective","HasMetPlacement","IsRemoved",
                             "CurrentMark","TargetActor","AssociatedTrainingVolume","NextQuestPrereqsMet"};
    char line[512]; int o=_snprintf_s(line,sizeof(line),_TRUNCATE,"[QP] %s state:",tag);
    for(int i=0;i<(int)(sizeof(kF)/sizeof(kF[0]));i++){
        uint32_t off=PropOffsetSuper(ClassOf(q),kF[i]); uint64_t v=0;
        if(off!=0xFFFFFFFF&&SafeReadable((void*)(q+off),8)) v=*(uint64_t*)(q+off);
        o+=_snprintf_s(line+o,sizeof(line)-o,_TRUNCATE," %s=%llX",kF[i],(unsigned long long)v);
    }
    Markerf("%s\r\n",line);
}
static bool ResolveQuestPlay(){
    ResolveSpawnSeq();                                   // gm + GameplayStatics + spawn transform
    g_qpHero=FindInstByClass("BP_HERO_",nullptr);
    g_qpVol =FindInstByClass("TrainingVolume",nullptr);
    g_qpQuest=FindInstByClass("Quest_Basics_WASD",nullptr);
    if(!g_qpQuest) g_qpQuest=FindInstByClass("Quest_Basics",nullptr);
    if(g_qpHero){ ResolveFuncSuper(ClassOf(g_qpHero),"K2_SetActorLocation",&g_qpSlFn,&g_qpSlThunk,&g_qpSlChild);
        if(g_qpSlChild){ g_oQpLoc=ParamOffset(g_qpSlChild,"NewLocation");
                         g_oQpSweep=ParamOffset(g_qpSlChild,"bSweep");
                         g_oQpTele=ParamOffset(g_qpSlChild,"bTeleport"); } }
    double h[3]={0,0,0}; ActorLoc(g_qpHero,h);
    char qn[96]="-"; if(g_qpQuest&&ClassOf(g_qpQuest)) GetFNameStr(NameId(ClassOf(g_qpQuest)),qn,sizeof(qn));
    Markerf("[QP] hero=0x%llX loc=(%.0f,%.0f,%.0f) quest=0x%llX(%s) vol=0x%llX setLoc=0x%llX(Loc@0x%X Sweep@0x%X Tele@0x%X)\r\n",
        (unsigned long long)g_qpHero,h[0],h[1],h[2],(unsigned long long)g_qpQuest,qn,
        (unsigned long long)g_qpVol,(unsigned long long)g_qpSlThunk,g_oQpLoc,g_oQpSweep,g_oQpTele);
    if(!g_qpHero) Marker("[QP] *** NO LIVE BP_HERO_* — inject tutorial_launch_sp.dll first ***\r\n");
    return g_qpHero && g_qpSlThunk;
}
// Read the quest's trigger target: TargetTriggerBox's world location, else the TargetLocation FVector, else the volume.
static bool QuestTarget(uintptr_t q,double* out,const char** src){
    if(LooksLikePtr(q)){
        uint32_t bo=PropOffsetSuper(ClassOf(q),"TargetTriggerBox");
        if(bo!=0xFFFFFFFF&&SafeReadable((void*)(q+bo),8)){
            uintptr_t b=*(uintptr_t*)(q+bo);
            if(LooksLikePtr(b)&&ActorLoc(b,out)&&(out[0]||out[1]||out[2])){ g_qpBox=b; *src="TargetTriggerBox"; return true; } }
        uint32_t to=PropOffsetSuper(ClassOf(q),"TargetLocation");
        if(to!=0xFFFFFFFF&&SafeReadable((void*)(q+to),24)){
            double* P=(double*)(q+to);
            if(P[0]||P[1]||P[2]){ out[0]=P[0];out[1]=P[1];out[2]=P[2]; *src="TargetLocation"; return true; } }
    }
    if(LooksLikePtr(g_qpVol)&&ActorLoc(g_qpVol,out)){ *src="TrainingVolume"; return true; }
    return false;
}
static void DoQuestPlay(){
    if(g_qpMs && GetTickCount()-g_qpMs < 400) return;
    switch(g_qpStep){
    case 0:
        if(kQpSpawn && g_beginThunk && g_gm2){
            uintptr_t wc=FindClassExact("TrainingQuest_Basics_WASD_C");
            if(wc){ uintptr_t a=SpawnActorCls(wc,"TrainingQuest_Basics_WASD_C(with hero)");
                    Markerf("[QP] respawned WASD quest WITH the hero present -> 0x%llX\r\n",(unsigned long long)a);
                    if(LooksLikePtr(a)) g_qpQuest=a; }
            else Marker("[QP] WASD class not loaded -> using the existing quest\r\n");
        }
        g_qpStep++; g_qpMs=GetTickCount(); return;
    case 1: {
        if(GetTickCount()-g_qpMs < 3000) return;         // let that BeginPlay resolve its level actors
        const char* src="?";
        if(!QuestTarget(g_qpQuest,g_qpDst,&src)){ Marker("[QP] no target location resolvable -> abort\r\n"); g_done=1; return; }
        char bn[96]="-"; if(LooksLikePtr(g_qpBox)&&ClassOf(g_qpBox)) GetFNameStr(NameId(ClassOf(g_qpBox)),bn,sizeof(bn));
        Markerf("[QP] target from %s (%s) = (%.0f,%.0f,%.0f)\r\n",src,bn,g_qpDst[0],g_qpDst[1],g_qpDst[2]);
        QuestState(g_qpQuest,"PRE");
        g_qpStep++; g_qpMs=GetTickCount(); return; }
    case 2: {
        uint8_t* pb=(uint8_t*)g_pbuf; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(g_oQpLoc!=0xFFFFFFFF){ double* L=(double*)(pb+g_oQpLoc); L[0]=g_qpDst[0]; L[1]=g_qpDst[1]; L[2]=g_qpDst[2]+120.0; }
        if(g_oQpSweep!=0xFFFFFFFF) pb[g_oQpSweep]=0;
        if(g_oQpTele !=0xFFFFFFFF) pb[g_oQpTele ]=1;
        bool f=CallNativeGuarded(g_qpSlFn,g_qpSlThunk,g_qpSlChild,(void*)g_qpHero,g_pbuf,g_rbuf);
        Markerf("[QP] *** TELEPORT hero -> (%.0f,%.0f,%.0f) [try %d]%s ***\r\n",g_qpDst[0],g_qpDst[1],g_qpDst[2]+120.0,g_qpTry,f?" FAULTED":"");
        g_qpStep++; g_qpMs=GetTickCount(); return; }
    case 3: {
        if(GetTickCount()-g_qpMs < 7000) return;         // real time for BeginOverlap + the quest graph
        double h[3]={0,0,0}; ActorLoc(g_qpHero,h);
        Markerf("[QP] post-teleport hero=(%.0f,%.0f,%.0f)\r\n",h[0],h[1],h[2]);
        QuestState(g_qpQuest,"POST");
        // Second attempt: nudge the hero to the TRAINING VOLUME (the other documented trigger) before giving up.
        if(g_qpTry==0 && LooksLikePtr(g_qpVol) && ActorLoc(g_qpVol,g_qpDst)){
            g_qpTry++; Marker("[QP] retry: teleporting to the BP_TrainingVolume instead\r\n");
            g_qpStep=2; g_qpMs=GetTickCount()-400; return; }
        Marker("[QP] done\r\n"); g_done=1; return; }
    }
}

// ★★★ S91 RM_BPCALL — exercise the new BP-call primitive on the tutorial quest, then use it to arm the lesson.
// Staged one call per game-thread hit. Step 1 is deliberately SELF-VERIFYING: `UpdateAssociatedTrainingVolume(vol)`
// writes a field we can read back, so a changed value proves the bytecode really ran (not just "didn't crash").
static uintptr_t g_bcQuest=0, g_bcVol=0, g_bcHero=0; static int g_bcStep=0; static DWORD g_bcMs=0;
static void BCLog(const char* fn,bool faulted,uint64_t r0){
    Markerf("[BPC] %-32s %s ret=0x%llX\r\n",fn,faulted?"FAULTED":"ok     ",(unsigned long long)r0);
}
static uint64_t ReadProp(uintptr_t o,const char* n){
    uint32_t off=PropOffsetSuper(ClassOf(o),n);
    if(off==0xFFFFFFFF||!SafeReadable((void*)(o+off),8))return 0xDEADBEEF;
    return *(uint64_t*)(o+off);
}
static bool ResolveBPCall(){
    ResolveSpawnSeq();
    g_bcQuest=FindInstByClass("Quest_Basics_WASD",nullptr);
    if(!g_bcQuest) g_bcQuest=FindInstByClass("Quest_Basics",nullptr);
    g_bcVol =FindInstByClass("TrainingVolume",nullptr);
    g_bcHero=FindInstByClass("BP_HERO_",nullptr);
    char qn[96]="-"; if(g_bcQuest&&ClassOf(g_bcQuest)) GetFNameStr(NameId(ClassOf(g_bcQuest)),qn,sizeof(qn));
    Markerf("[BPC] quest=0x%llX(%s) vol=0x%llX hero=0x%llX\r\n",
        (unsigned long long)g_bcQuest,qn,(unsigned long long)g_bcVol,(unsigned long long)g_bcHero);
    if(!g_bcQuest){ Marker("[BPC] no live quest — inject tutorial_launch_quest.dll first\r\n"); return false; }
    // Show the primitive's inputs for the first target so a refusal is diagnosable offline.
    uintptr_t ch=0, f=FindBPFunc(ClassOf(g_bcQuest),"UpdateAssociatedTrainingVolume",&ch);
    if(f) Markerf("[BPC] UpdateAssociatedTrainingVolume fn=0x%llX script=0x%llX num=%u propsSize=%u func=0x%llX\r\n",
        (unsigned long long)f,(unsigned long long)*(uintptr_t*)(f+USTRUCT_SCRIPT),
        *(uint32_t*)(f+USTRUCT_SCRIPTNUM),*(uint32_t*)(f+USTRUCT_PROPSIZE),
        (unsigned long long)*(uintptr_t*)(f+UFUNC_FUNC));
    return true;
}
static void DoBPCall(){
    if(g_bcMs && GetTickCount()-g_bcMs < 600) return;
    g_bcMs=GetTickCount();
    uintptr_t cls=ClassOf(g_bcQuest), ch=0, f=0; uint64_t res[4]={0,0,0,0};
    switch(g_bcStep++){
    case 0:   // VALIDATION: a tiny, side-effect-free predicate (14 bytecode entries).
        f=FindBPFunc(cls,"CanPing",&ch);
        if(!f){ Marker("[BPC] CanPing not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res));
        BCLog("CanPing",CallBPGuarded(f,(void*)g_bcQuest,res),res[0]);
        break;
    case 1: { // SELF-VERIFYING: writes AssociatedTrainingVolume — read it back to prove the bytecode executed.
        uint64_t before=ReadProp(g_bcQuest,"AssociatedTrainingVolume");
        f=FindBPFunc(cls,"UpdateAssociatedTrainingVolume",&ch);
        if(!f){ Marker("[BPC] UpdateAssociatedTrainingVolume not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res));
        if(LooksLikePtr(ch)){ uint32_t o=0xFFFFFFFF; uintptr_t p=ch;   // its single param = the volume
            if(SafeReadable((void*)(p+FPROP_OFFSET),4)) o=*(uint32_t*)(p+FPROP_OFFSET);
            char pn[96]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
            if(o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)) *(uint64_t*)(g_bplocals+o)=(uint64_t)g_bcVol;
            Markerf("[BPC] param '%s' @0x%X <- vol 0x%llX\r\n",pn,o,(unsigned long long)g_bcVol); }
        bool fl=CallBPGuarded(f,(void*)g_bcQuest,res);
        uint64_t after=ReadProp(g_bcQuest,"AssociatedTrainingVolume");
        Markerf("[BPC] UpdateAssociatedTrainingVolume %s  AssociatedTrainingVolume 0x%llX -> 0x%llX  %s\r\n",
            fl?"FAULTED":"ok",(unsigned long long)before,(unsigned long long)after,
            (after==(uint64_t)g_bcVol&&g_bcVol)?"*** BP CALL PRIMITIVE WORKS ***":"(unchanged — bytecode did not take effect)");
        break; }
    case 2:   // THE TRIGGER: the quest base's documented entry point; its one FObjectProperty param = the volume.
        f=FindBPFunc(cls,"OnTrainingVolume",&ch);
        if(!f){ Marker("[BPC] OnTrainingVolume not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res));
        if(LooksLikePtr(ch)){ uint32_t o=SafeReadable((void*)(ch+FPROP_OFFSET),4)?*(uint32_t*)(ch+FPROP_OFFSET):0xFFFFFFFF;
            char pn[96]="?"; GetFNameStr(NameId(ch),pn,sizeof(pn));
            if(o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)) *(uint64_t*)(g_bplocals+o)=(uint64_t)g_bcVol;
            Markerf("[BPC] OnTrainingVolume param '%s' @0x%X <- vol 0x%llX\r\n",pn,o,(unsigned long long)g_bcVol); }
        BCLog("OnTrainingVolume",CallBPGuarded(f,(void*)g_bcQuest,res),res[0]);
        break;
    case 3:
        QuestState(g_bcQuest,"POST-OnTrainingVolume");
        QuestCensus("BPC");
        break;
    case 4: {  // ★ THE ARMING CALL: sequencer.ReadyToFire(<quest CLASS>) — the documented "arm the next quest" entry.
               // Never callable before (it is bytecode); the S91 BP primitive makes it reachable.
        uintptr_t seq=FindInstByClass("QuestSequencer",nullptr);
        if(!seq){ Marker("[BPC] no live sequencer\r\n"); break; }
        f=FindBPFunc(ClassOf(seq),"ReadyToFire",&ch);
        if(!f){ Marker("[BPC] ReadyToFire not found\r\n"); break; }
        uintptr_t wc=FindClassExact("TrainingQuest_Basics_WASD_C");
        memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res));
        int filled=0;
        for(uintptr_t p=ch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            char pn[96]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
            uint32_t o =SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0;
            char tn[96]="?"; if(ClassOf(p)) GetFNameStr(NameId(ClassOf(p)),tn,sizeof(tn));
            Markerf("[BPC] ReadyToFire param '%s' type=%s @0x%X flags=0x%llX\r\n",pn,tn,o,(unsigned long long)fl);
            if(!filled && strstr(tn,"ClassProperty") && o!=0xFFFFFFFF && o+8<=sizeof(g_bplocals) && wc){
                *(uint64_t*)(g_bplocals+o)=(uint64_t)wc; filled=1;
                Markerf("[BPC]   -> set to TrainingQuest_Basics_WASD_C 0x%llX\r\n",(unsigned long long)wc); }
        }
        bool fl2=CallBPGuarded(f,(void*)seq,res);
        Markerf("[BPC] ReadyToFire on seq 0x%llX %s ret=0x%llX (classParamFilled=%d)\r\n",
            (unsigned long long)seq,fl2?"FAULTED":"ok",(unsigned long long)res[0],filled);
        for(uintptr_t p=ch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            char pn[96]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            if(o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)) Markerf("[BPC]   out '%s' = 0x%llX\r\n",pn,(unsigned long long)*(uint64_t*)(g_bplocals+o));
        }
        break; }
    case 5:
        QuestState(g_bcQuest,"POST-ReadyToFire");
        QuestCensus("BPC2");
        break;
    case 6: {  // ★★★ THE REAL LESSON-START: Comp_GameState_TrainingBase.GameStateTryStartTraining(NewVolume=vol).
               // Offline bpdump: it sets CurrentTrainingVolume=NewVolume and reads NewVolume.VolumeTag. This is the
               // tutorial's own "start training at this volume" entry (FUNC_BlueprintCallable) — now reachable.
        uintptr_t tb=FindInstByClass("GameState_TrainingBase",nullptr);
        if(!tb){ Marker("[BPC] no live Comp_GameState_TrainingBase\r\n"); break; }
        uint64_t curBefore=ReadProp(tb,"CurrentTrainingVolume"), actBefore=ReadProp(tb,"TrainingActive");
        f=FindBPFunc(ClassOf(tb),"GameStateTryStartTraining",&ch);
        if(!f){ Marker("[BPC] GameStateTryStartTraining not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res));
        // first FObjectProperty param = NewVolume (the training volume). Set it; leave the bools/int at 0.
        for(uintptr_t p=ch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            char pn[96]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0;
            Markerf("[BPC] StartTraining param '%s' @0x%X flags=0x%llX\r\n",pn,o,(unsigned long long)fl);
            if(strstr(pn,"Volume")&&o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)){ *(uint64_t*)(g_bplocals+o)=(uint64_t)g_bcVol;
                Markerf("[BPC]   -> NewVolume = 0x%llX\r\n",(unsigned long long)g_bcVol); }
        }
        bool fl=CallBPGuarded(f,(void*)tb,res);
        uint64_t curAfter=ReadProp(tb,"CurrentTrainingVolume"), actAfter=ReadProp(tb,"TrainingActive");
        Markerf("[BPC] GameStateTryStartTraining %s  CurrentTrainingVolume 0x%llX->0x%llX  TrainingActive 0x%llX->0x%llX\r\n",
            fl?"FAULTED":"ok",(unsigned long long)curBefore,(unsigned long long)curAfter,
            (unsigned long long)actBefore,(unsigned long long)actAfter);
        g_bcMs=GetTickCount()+3400; break; }   // widen the gap before the next step so training can spin up (>600ms floor)
    case 7:
        QuestCensus("BPC-STARTTRAIN");
        { uintptr_t tb=FindInstByClass("GameState_TrainingBase",nullptr);
          if(tb) Markerf("[BPC] TrainingBase now: CurrentTrainingVolume=0x%llX TrainingActive=0x%llX CurrentObjectiveCount=0x%llX\r\n",
              (unsigned long long)ReadProp(tb,"CurrentTrainingVolume"),(unsigned long long)ReadProp(tb,"TrainingActive"),
              (unsigned long long)ReadProp(tb,"CurrentObjectiveCount")); }
        break;
    default:
        Marker("[BPC] done\r\n"); g_done=1; return;
    }
}

// ★★★ S92 RM_OBJDRIVE — advance the ACTIVE WASD objective three ways, watching CurrentObjectiveCount.
// Training is already ACTIVE (S91: GameStateTryStartTraining spawned the on-map arrows). This mode:
//   step0: census — TrainingBase{TrainingActive,CurrentObjectiveCount,CurrentTrainingVolume} + each WASD quest's
//          {CurrentMark(+loc), TargetTriggerBox(+loc), TargetLocation, CurrentObjectiveCount}; pick the active quest.
//   step1: PHYSICAL — teleport the possessed hero onto the active quest's TargetTriggerBox and settle (fire overlap).
//   step2: OVERLAP  — call quest.OnWASDTriggerOverlap(box, hero) via the BP primitive.
//   step3: DIRECT   — call TrainingBase.ProgressObjective(1) via the BP primitive (x3), watching the count.
static uintptr_t g_odTB=0, g_odHero=0, g_odQuest=0, g_odBox=0, g_odVol=0; static int g_odStep=0; static DWORD g_odMs=0;
static void*     g_odSlFn=nullptr; static uintptr_t g_odSlThunk=0, g_odSlChild=0; static uint32_t g_oOdLoc=0xFFFFFFFF,g_oOdSweep=0xFFFFFFFF,g_oOdTele=0xFFFFFFFF;
static uint64_t OdObjCount(){ return g_odTB?ReadProp(g_odTB,"CurrentObjectiveCount"):0; }
static void OdLogState(const char* tag){
    Markerf("[OD] %s TrainingBase: Active=0x%llX ObjCount=0x%llX CurVol=0x%llX\r\n",tag,
        (unsigned long long)ReadProp(g_odTB,"TrainingActive"),(unsigned long long)ReadProp(g_odTB,"CurrentObjectiveCount"),
        (unsigned long long)ReadProp(g_odTB,"CurrentTrainingVolume"));
    if(LooksLikePtr(g_odQuest)){
        uint32_t mo=PropOffsetSuper(ClassOf(g_odQuest),"CurrentMark"), bo=PropOffsetSuper(ClassOf(g_odQuest),"TargetTriggerBox");
        uint64_t mk=(mo!=0xFFFFFFFF&&SafeReadable((void*)(g_odQuest+mo),8))?*(uint64_t*)(g_odQuest+mo):0;
        uint64_t bx=(bo!=0xFFFFFFFF&&SafeReadable((void*)(g_odQuest+bo),8))?*(uint64_t*)(g_odQuest+bo):0;
        double ml[3]={0,0,0},bl[3]={0,0,0}; ActorLoc((uintptr_t)mk,ml); ActorLoc((uintptr_t)bx,bl);
        Markerf("[OD] %s quest 0x%llX: ObjCount=0x%llX CurrentMark=0x%llX(%.0f,%.0f,%.0f) TargetTriggerBox=0x%llX(%.0f,%.0f,%.0f)\r\n",
            tag,(unsigned long long)g_odQuest,(unsigned long long)ReadProp(g_odQuest,"CurrentObjectiveCount"),
            (unsigned long long)mk,ml[0],ml[1],ml[2],(unsigned long long)bx,bl[0],bl[1],bl[2]);
    }
}
static bool ResolveObjDrive(){
    g_odTB  =FindInstByClass("GameState_TrainingBase",nullptr);
    g_odHero=FindInstByClass("BP_HERO_",nullptr);
    g_odVol =FindInstByClass("TrainingVolume",nullptr);
    // pick the WASD quest that has a live CurrentMark or TargetTriggerBox (the active one).
    uintptr_t oo=g_modBase+kObjObjectsRva; if(SafeReadable((void*)oo,0x18)){
        uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
        if(LooksLikePtr(objectsPtr)&&numEl>0&&numEl<8000000){ int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
            for(int ci=0;ci<numChunks&&!g_odQuest;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
                for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
                    uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
                    if(!strstr(cn,"Quest_Basics_WASD"))continue; char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue;
                    uint32_t bo=PropOffsetSuper(cls,"TargetTriggerBox"); uint64_t bx=(bo!=0xFFFFFFFF&&SafeReadable((void*)(obj+bo),8))?*(uint64_t*)(obj+bo):0;
                    if(LooksLikePtr(bx)){ g_odQuest=obj; g_odBox=bx; break; }
                    if(!g_odQuest) g_odQuest=obj; } } } }
    if(g_odHero){ ResolveFuncSuper(ClassOf(g_odHero),"K2_SetActorLocation",&g_odSlFn,&g_odSlThunk,&g_odSlChild);
        if(g_odSlChild){ g_oOdLoc=ParamOffset(g_odSlChild,"NewLocation"); g_oOdSweep=ParamOffset(g_odSlChild,"bSweep"); g_oOdTele=ParamOffset(g_odSlChild,"bTeleport"); } }
    Markerf("[OD] TB=0x%llX hero=0x%llX quest=0x%llX box=0x%llX vol=0x%llX setLoc=0x%llX\r\n",
        (unsigned long long)g_odTB,(unsigned long long)g_odHero,(unsigned long long)g_odQuest,
        (unsigned long long)g_odBox,(unsigned long long)g_odVol,(unsigned long long)g_odSlThunk);
    return g_odTB && g_odQuest;
}
static void DoObjDrive(){
    if(g_odMs && GetTickCount()-g_odMs < 600) return; g_odMs=GetTickCount();
    uintptr_t ch=0,f=0; uint64_t res[4]={0,0,0,0};
    switch(g_odStep++){
    case 0: OdLogState("INITIAL"); break;
    case 1: { // PHYSICAL: teleport hero onto the trigger box (or the active mark), then let overlap run.
        double dst[3]={0,0,0}; const char* src="none";
        if(LooksLikePtr(g_odBox)&&ActorLoc(g_odBox,dst)&&(dst[0]||dst[1]||dst[2])) src="box";
        else if(LooksLikePtr(g_odVol)&&ActorLoc(g_odVol,dst)) src="vol";
        if(g_odSlThunk&&LooksLikePtr(g_odHero)&&src[0]!='n'){
            uint8_t* pb=(uint8_t*)g_pbuf; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            if(g_oOdLoc!=0xFFFFFFFF){ double* L=(double*)(pb+g_oOdLoc); L[0]=dst[0];L[1]=dst[1];L[2]=dst[2]+90.0; }
            if(g_oOdTele!=0xFFFFFFFF) pb[g_oOdTele]=1;
            bool fl=CallNativeGuarded(g_odSlFn,g_odSlThunk,g_odSlChild,(void*)g_odHero,g_pbuf,g_rbuf);
            Markerf("[OD] PHYSICAL teleport hero -> %s (%.0f,%.0f,%.0f)%s\r\n",src,dst[0],dst[1],dst[2]+90.0,fl?" FAULTED":"");
        } else Marker("[OD] PHYSICAL skipped (no box/hero/setLoc)\r\n");
        g_odMs=GetTickCount()+2600; break; }   // widen gap so overlap can fire
    case 2: OdLogState("POST-PHYSICAL"); break;
    case 3: { // OVERLAP: call quest.OnWASDTriggerOverlap(OverlappedActor=box, OtherActor=hero) via the BP primitive.
        f=FindBPFunc(ClassOf(g_odQuest),"OnWASDTriggerOverlap",&ch);
        if(!f){ Marker("[OD] OnWASDTriggerOverlap not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        int k=0; for(uintptr_t p=ch;LooksLikePtr(p)&&k<2;p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            uint64_t fp=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0; if(!(fp&0x80))continue;   // CPF_Parm
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            char pn[64]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
            uint64_t v=(k==0)?(uint64_t)(g_odBox?g_odBox:g_odVol):(uint64_t)g_odHero;
            if(o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)) *(uint64_t*)(g_bplocals+o)=v;
            Markerf("[OD] OnWASDTriggerOverlap param[%d] '%s'@0x%X <- 0x%llX\r\n",k,pn,o,(unsigned long long)v); k++; }
        bool fl=CallBPGuarded(f,(void*)g_odQuest,res);
        Markerf("[OD] OnWASDTriggerOverlap %s\r\n",fl?"FAULTED":"ok"); g_odMs=GetTickCount()+1600; break; }
    case 4: OdLogState("POST-OVERLAP"); break;
    case 5: case 6: case 7: { // DIRECT: ProgressObjective(1) on the TrainingBase component.
        f=FindBPFunc(ClassOf(g_odTB),"ProgressObjective",&ch);
        if(!f){ Marker("[OD] ProgressObjective not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        uint32_t o=LooksLikePtr(ch)&&SafeReadable((void*)(ch+FPROP_OFFSET),4)?*(uint32_t*)(ch+FPROP_OFFSET):0;
        if(o+4<=sizeof(g_bplocals)) *(int32_t*)(g_bplocals+o)=1;   // ProgressAmount = 1
        uint64_t before=OdObjCount();
        bool fl=CallBPGuarded(f,(void*)g_odTB,res);
        Markerf("[OD] ProgressObjective(1) %s  ObjCount 0x%llX -> 0x%llX\r\n",fl?"FAULTED":"ok",
            (unsigned long long)before,(unsigned long long)OdObjCount());
        g_odMs=GetTickCount()+900; break; }
    case 8: OdLogState("POST-PROGRESS"); break;
    case 9: {  // NATIVE augment path on the active quest: IncrementObjectiveCount (TeamAugment native thunk).
        void* nf=nullptr; uintptr_t nth=0,nch=0;
        ResolveFuncNative(ClassOf(g_odQuest),"IncrementObjectiveCount",&nf,&nth,&nch);
        if(nth){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            uint64_t before=ReadProp(g_odQuest,"CurrentObjectiveCount");
            bool fl=CallNativeGuarded(nf,nth,nch,(void*)g_odQuest,g_pbuf,g_rbuf);
            Markerf("[OD] native IncrementObjectiveCount %s  quest.ObjCount 0x%llX->0x%llX  TB.ObjCount->0x%llX\r\n",
                fl?"FAULTED":"ok",(unsigned long long)before,(unsigned long long)ReadProp(g_odQuest,"CurrentObjectiveCount"),
                (unsigned long long)OdObjCount());
        } else Marker("[OD] IncrementObjectiveCount thunk not found\r\n");
        g_odMs=GetTickCount()+800; break; }
    case 10: {  // THE COMPLETION EVENT: quest.OnObjectiveComplete (BP, FUNC_BlueprintAuthorityOnly; force-open IS authority).
        f=FindBPFunc(ClassOf(g_odQuest),"OnObjectiveComplete",&ch);
        if(!f){ Marker("[OD] OnObjectiveComplete not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        bool fl=CallBPGuarded(f,(void*)g_odQuest,res);
        Markerf("[OD] quest.OnObjectiveComplete %s (authority completion path)\r\n",fl?"FAULTED":"ok");
        g_odMs=GetTickCount()+2600; break; }
    case 11: OdLogState("POST-COMPLETE"); QuestCensus("OBJDRIVE"); break;
    default: Marker("[OD] done\r\n"); g_done=1; return;
    }
}

// ★★★ S93 RM_OBJCOMPLETE — force the training component's objective to its target + fire the completion OnRep.
// The bytecode chain (read this session): Comp.ProgressObjective -> ExecuteUbergraph(768) -> [ServerOnly gate] ->
// CurrentObjectiveCount += ProgressAmount -> OnRep_CurrentObjectiveCount -> [ServerOnly gate] ->
// if CurrentObjectiveCount >= ObjectiveTarget -> EndTraining(). This mode bypasses the increment (pokes the count to
// the target directly) then invokes OnRep so the completion runs — testing (a) whether my BP primitive runs gated
// functions, (b) whether ServerOnly passes on force-open (authority), (c) whether EndTraining visibly completes the lesson.
static uintptr_t g_ocTB=0; static int g_ocStep=0; static DWORD g_ocMs=0;
static void OcLog(const char* tag){
    uint32_t fvo=PropOffsetSuper(ClassOf(g_ocTB),"FinishedVolumes"); uint32_t fvn=0;
    if(fvo!=0xFFFFFFFF&&SafeReadable((void*)(g_ocTB+fvo+8),4)) fvn=*(uint32_t*)(g_ocTB+fvo+8);
    Markerf("[OC] %s TrainingActive=0x%llX CurObjCount=0x%llX ObjectiveTarget=0x%llX TrainingSuccessful=0x%llX AllTrainingCompleted=0x%llX FinishedVolumes.Num=%u\r\n",
        tag,(unsigned long long)ReadProp(g_ocTB,"TrainingActive"),(unsigned long long)ReadProp(g_ocTB,"CurrentObjectiveCount"),
        (unsigned long long)ReadProp(g_ocTB,"ObjectiveTarget"),(unsigned long long)ReadProp(g_ocTB,"TrainingSuccessful"),
        (unsigned long long)ReadProp(g_ocTB,"AllTrainingCompleted"),fvn);
}
static bool ResolveObjComplete(){
    // pick the LIVE active TrainingBase (TrainingActive==1), not a GEN_VARIABLE archetype.
    uintptr_t oo=g_modBase+kObjObjectsRva; if(SafeReadable((void*)oo,0x18)){
        uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
        if(LooksLikePtr(objectsPtr)&&numEl>0&&numEl<8000000){ int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
            for(int ci=0;ci<numChunks&&!g_ocTB;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
                for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
                    uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
                    if(strcmp(cn,"Comp_GameState_TrainingBase_C")!=0)continue;
                    uint32_t o=PropOffsetSuper(cls,"TrainingActive"); if(o!=0xFFFFFFFF&&SafeReadable((void*)(obj+o),1)&&*(uint8_t*)(obj+o)==1){ g_ocTB=obj; break; } } } } }
    if(!g_ocTB) g_ocTB=FindInstByClass("GameState_TrainingBase",nullptr);
    Markerf("[OC] TrainingBase=0x%llX\r\n",(unsigned long long)g_ocTB);
    return g_ocTB!=0;
}
static void DoObjComplete(){
    if(g_ocMs && GetTickCount()-g_ocMs < 700) return; g_ocMs=GetTickCount();
    uintptr_t ch=0,f=0; uint64_t res[4]={0,0,0,0};
    switch(g_ocStep++){
    case 0: OcLog("INITIAL"); break;
    case 1: {  // POKE CurrentObjectiveCount = ObjectiveTarget (direct RPM write; bypass the increment gate).
        uint32_t co=PropOffsetSuper(ClassOf(g_ocTB),"CurrentObjectiveCount");
        uint32_t to=PropOffsetSuper(ClassOf(g_ocTB),"ObjectiveTarget");
        if(co!=0xFFFFFFFF&&to!=0xFFFFFFFF&&SafeReadable((void*)(g_ocTB+to),4)){
            int32_t tgt=*(int32_t*)(g_ocTB+to); if(tgt<1)tgt=1;
            SafeWrite((uint8_t*)(g_ocTB+co),(uint8_t*)&tgt,4);
            Markerf("[OC] poked CurrentObjectiveCount@0x%X = %d (=ObjectiveTarget)\r\n",co,tgt);
        } else Marker("[OC] could not resolve count/target offsets\r\n");
        OcLog("POST-POKE"); break; }
    case 2: {  // fire OnRep_CurrentObjectiveCount -> should hit GreaterEqual(count,target) -> EndTraining().
        f=FindBPFunc(ClassOf(g_ocTB),"OnRep_CurrentObjectiveCount",&ch);
        if(!f){ Marker("[OC] OnRep_CurrentObjectiveCount not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        bool fl=CallBPGuarded(f,(void*)g_ocTB,res);
        Markerf("[OC] OnRep_CurrentObjectiveCount %s\r\n",fl?"FAULTED":"ok");
        g_ocMs=GetTickCount()+2600; break; }
    case 3: OcLog("POST-ONREP"); break;
    case 4: {  // fallback: call EndTraining() directly.
        f=FindBPFunc(ClassOf(g_ocTB),"EndTraining",&ch);
        if(!f){ Marker("[OC] EndTraining not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        bool fl=CallBPGuarded(f,(void*)g_ocTB,res);
        Markerf("[OC] EndTraining %s (direct)\r\n",fl?"FAULTED":"ok");
        g_ocMs=GetTickCount()+2600; break; }
    case 5: OcLog("FINAL"); QuestCensus("OBJCOMPLETE");
        Markerf("[OC] TrainingBase now marks the volume finished? FinishedVolumes checked above; OnTrainingFinish should have fired if EndTraining ran\r\n");
        break;
    default: Marker("[OC] done\r\n"); g_done=1; return;
    }
}

// ★★★ S93 RM_FIREOVERLAP — the "through gameplay" completion, then a guaranteed ungated closer.
// From the verification workflow + live reads: the WASD overlap bind is EMPTY (box.OnActorBeginOverlap Num=0 — the
// quest's authority ClientServerSplit bind branch never ran for our force-open quest), the TargetTriggerBox is huge
// (extent ~5190x2898x768) and the hero is ALREADY inside it, so a physical begin-overlap can't fire. So:
//   (A) fire the quest's OWN OnWASDTriggerOverlap(box, hero) on the ACTIVE quest (OBJARROW!=0) via the BP primitive —
//       the "objective reached" gameplay beat (class filter passes for the LokiHeroCharacter -> IncrementObjectiveCount
//       -> OnObjectiveComplete -> GameEvent_Tutorial_QuestComplete).
//   (B) GUARANTEED CLOSER (authority-independent, param-free, all UNGATED per the EndTraining/OnRep_TrainingActive
//       bytecode): RPM-set the component's TrainingSuccessful=1, TrainingActive=0, CurrentObjectiveCount=1, then
//       BP-call the param-free OnRep_TrainingActive() -> CallTrainingCompletions -> broadcasts OnTrainingFinish
//       (BOUND -> chain-advance) + LokiGameState.OnTrainingComplete, and FinishedVolumes.AddUnique(volume tag).
static uintptr_t g_foQuest=0, g_foBox=0, g_foHero=0, g_foTB=0, g_foVolFO=0; static int g_foStep=0; static DWORD g_foMs=0;
static void FoLogTB(const char* tag){
    if(!g_foTB)return;
    Markerf("[FO] %s TB: TrainingActive=0x%llX CurObjCount=0x%llX ObjectiveTarget=0x%llX TrainingSuccessful=0x%llX\r\n",tag,
        (unsigned long long)ReadProp(g_foTB,"TrainingActive"),(unsigned long long)ReadProp(g_foTB,"CurrentObjectiveCount"),
        (unsigned long long)ReadProp(g_foTB,"ObjectiveTarget"),(unsigned long long)ReadProp(g_foTB,"TrainingSuccessful"));
    if(g_foQuest) Markerf("[FO] %s quest.CurrentObjectiveCount=0x%llX AugmentObjectiveCount=0x%llX\r\n",tag,
        (unsigned long long)ReadProp(g_foQuest,"CurrentObjectiveCount"),(unsigned long long)ReadProp(g_foQuest,"AugmentObjectiveCount"));
}
static bool ResolveFireOverlap(){
    // active WASD quest = the one whose OBJARROW is set (the on-screen marker) — the tutorial's live objective.
    uintptr_t oo=g_modBase+kObjObjectsRva; if(SafeReadable((void*)oo,0x18)){
        uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
        if(LooksLikePtr(objectsPtr)&&numEl>0&&numEl<8000000){ int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
            for(int ci=0;ci<numChunks&&!g_foQuest;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
                for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
                    uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
                    if(strcmp(cn,"TrainingQuest_Basics_WASD_C")!=0)continue;
                    uint32_t ao=PropOffsetSuper(cls,"OBJARROW"); if(ao!=0xFFFFFFFF&&SafeReadable((void*)(obj+ao),8)&&*(uint64_t*)(obj+ao)){ g_foQuest=obj; break; } } } } }
    if(!g_foQuest) g_foQuest=FindInstByClass("Quest_Basics_WASD",nullptr);
    if(g_foQuest){ uint32_t bo=PropOffsetSuper(ClassOf(g_foQuest),"TargetTriggerBox"); if(bo!=0xFFFFFFFF&&SafeReadable((void*)(g_foQuest+bo),8)) g_foBox=*(uint64_t*)(g_foQuest+bo); }
    g_foHero=FindInstByClass("BP_HERO_",nullptr);
    // the LIVE training component = the one whose CurrentTrainingVolume is set (survives an EndTraining); prefer
    // TrainingActive==1 but accept CurrentTrainingVolume!=0 so we can re-start it if a prior EndTraining cleared active.
    uintptr_t fallback=0;
    { uintptr_t oo2=g_modBase+kObjObjectsRva; uintptr_t objectsPtr=*(uintptr_t*)oo2; int32_t numEl=*(int32_t*)(oo2+0x14); int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
      for(int ci=0;ci<numChunks&&!g_foTB;ci++){ uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue; if(strcmp(cn,"Comp_GameState_TrainingBase_C")!=0)continue;
            char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strstr(on,"GEN_VARIABLE")||strstr(on,"Race"))continue;
            uint32_t ta=PropOffsetSuper(cls,"TrainingActive"); uint32_t cv=PropOffsetSuper(cls,"CurrentTrainingVolume");
            uint8_t active=(ta!=0xFFFFFFFF&&SafeReadable((void*)(obj+ta),1))?*(uint8_t*)(obj+ta):0;
            uint64_t vol=(cv!=0xFFFFFFFF&&SafeReadable((void*)(obj+cv),8))?*(uint64_t*)(obj+cv):0;
            if(active==1){ g_foTB=obj; break; } if(vol&&!fallback) fallback=obj; } } }
    if(!g_foTB) g_foTB=fallback;
    if(g_foTB && !g_foBox){ uint32_t cv=PropOffsetSuper(ClassOf(g_foTB),"CurrentTrainingVolume"); if(cv!=0xFFFFFFFF&&SafeReadable((void*)(g_foTB+cv),8)) g_foVolFO=*(uint64_t*)(g_foTB+cv); }
    if(g_foTB){ uint32_t cv=PropOffsetSuper(ClassOf(g_foTB),"CurrentTrainingVolume"); if(cv!=0xFFFFFFFF&&SafeReadable((void*)(g_foTB+cv),8)) g_foVolFO=*(uint64_t*)(g_foTB+cv); }
    Markerf("[FO] quest=0x%llX box=0x%llX hero=0x%llX TB=0x%llX vol=0x%llX\r\n",(unsigned long long)g_foQuest,(unsigned long long)g_foBox,(unsigned long long)g_foHero,(unsigned long long)g_foTB,(unsigned long long)g_foVolFO);
    return g_foQuest && g_foTB;
}
static void DoFireOverlap(){
    if(g_foMs && GetTickCount()-g_foMs < 700) return; g_foMs=GetTickCount();
    uintptr_t ch=0,f=0; uint64_t res[4]={0,0,0,0};
    switch(g_foStep++){
    case 0: {  // RE-ARM: if a prior EndTraining cleared TrainingActive, restart the WASD lesson so the arrows respawn.
        FoLogTB("INITIAL");
        if(ReadProp(g_foTB,"TrainingActive")==0 && LooksLikePtr(g_foVolFO)){
            f=FindBPFunc(ClassOf(g_foTB),"GameStateTryStartTraining",&ch);
            if(f){ memset(g_bplocals,0,sizeof(g_bplocals));
                for(uintptr_t p=ch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
                    char pn[64]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
                    uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
                    if(strstr(pn,"Volume")&&o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)){ *(uint64_t*)(g_bplocals+o)=(uint64_t)g_foVolFO; break; } }
                bool fl=CallBPGuarded(f,(void*)g_foTB,res);
                Markerf("[FO] re-armed via GameStateTryStartTraining(vol) %s\r\n",fl?"FAULTED":"ok");
            } else Marker("[FO] GameStateTryStartTraining not found (skip re-arm)\r\n");
        }
        g_foMs=GetTickCount()+2600; break; }
    case 1: FoLogTB("POST-REARM"); break;
    case 2: {  // (A) GAMEPLAY BEAT: fire the ACTIVE quest's OnWASDTriggerOverlap(OverlappedActor=box, OtherActor=hero).
        f=FindBPFunc(ClassOf(g_foQuest),"OnWASDTriggerOverlap",&ch);
        if(!f){ Marker("[FO] OnWASDTriggerOverlap not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals)); int k=0;
        for(uintptr_t p=ch;LooksLikePtr(p)&&k<2;p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            uint64_t fp=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0; if(!(fp&0x80))continue;
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            uint64_t v=(k==0)?(uint64_t)g_foBox:(uint64_t)g_foHero;
            if(o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)) *(uint64_t*)(g_bplocals+o)=v; k++; }
        bool fl=CallBPGuarded(f,(void*)g_foQuest,res);
        Markerf("[FO] OnWASDTriggerOverlap(box,hero) on active quest %s\r\n",fl?"FAULTED":"ok");
        g_foMs=GetTickCount()+2600; break; }
    case 3: FoLogTB("POST-OVERLAP-BEAT"); break;
    case 4: {  // (B) GUARANTEED CLOSER — RPM-set the component fields (ungated tail), then param-free OnRep_TrainingActive.
        uint32_t co=PropOffsetSuper(ClassOf(g_foTB),"CurrentObjectiveCount");
        uint32_t ta=PropOffsetSuper(ClassOf(g_foTB),"TrainingActive");
        uint32_t ts=PropOffsetSuper(ClassOf(g_foTB),"TrainingSuccessful");
        int32_t one=1; uint8_t t1=1,t0=0;
        if(ts!=0xFFFFFFFF) SafeWrite((uint8_t*)(g_foTB+ts),&t1,1);   // TrainingSuccessful = true  (so FinishedVolumes.AddUnique runs)
        if(co!=0xFFFFFFFF) SafeWrite((uint8_t*)(g_foTB+co),(uint8_t*)&one,4); // CurrentObjectiveCount = 1 (UI)
        if(ta!=0xFFFFFFFF) SafeWrite((uint8_t*)(g_foTB+ta),&t0,1);   // TrainingActive = false (OnRep jumps to the ended block)
        Markerf("[FO] pre-set TrainingSuccessful@0x%X=1 CurObjCount@0x%X=1 TrainingActive@0x%X=0\r\n",ts,co,ta);
        f=FindBPFunc(ClassOf(g_foTB),"OnRep_TrainingActive",&ch);
        if(!f){ Marker("[FO] OnRep_TrainingActive not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        bool fl=CallBPGuarded(f,(void*)g_foTB,res);
        Markerf("[FO] OnRep_TrainingActive() (ungated closer) %s\r\n",fl?"FAULTED":"ok");
        g_foMs=GetTickCount()+2600; break; }
    case 5: {
        FoLogTB("FINAL");
        uint32_t fvo=PropOffsetSuper(ClassOf(g_foTB),"FinishedVolumes"); uint32_t fvn=0;
        if(fvo!=0xFFFFFFFF&&SafeReadable((void*)(g_foTB+fvo+8),4)) fvn=*(uint32_t*)(g_foTB+fvo+8);
        Markerf("[FO] FinishedVolumes.Num=%u (>=1 => the WASD volume is marked finished; OnTrainingFinish should have advanced the chain)\r\n",fvn);
        QuestCensus("FIREOVERLAP");
        break; }
    default: Marker("[FO] done\r\n"); g_done=1; return;
    }
}

// ★★★ S93 RM_DRIVECHAIN — walk the tutorial lesson CHAIN: for each quest (following NextQuestInChain), activate it,
// GameStateTryStartTraining(volume), then complete via the ungated closer. On force-open there is ONE loaded volume
// (Move_V2), so each "next volume" reuses it; the lesson identity is carried by the active quest (OnTrainingVolume
// sets its OBJARROW marker). Completing a volume adds its tag to FinishedVolumes (which would block a re-start), so we
// clear FinishedVolumes before each GameStateTryStartTraining. Staged; heavily fault-guarded (the game is precious).
#ifndef KCHAINMAX
#define KCHAINMAX 3
#endif
static const int kChainMax=KCHAINMAX;
static uintptr_t g_dcTB=0, g_dcVol=0, g_dcQuest=0, g_dcHero=0; static int g_dcPhase=0, g_dcLesson=0; static DWORD g_dcMs=0;
static uintptr_t NextQuestClass(uintptr_t q){
    uint32_t no=PropOffsetSuper(ClassOf(q),"NextQuestInChain"); if(no==0xFFFFFFFF)return 0;
    if(!SafeReadable((void*)(q+no),16))return 0; uintptr_t data=*(uint64_t*)(q+no); uint32_t num=*(uint32_t*)(q+no+8);
    if(num==0||!LooksLikePtr(data)||!SafeReadable((void*)data,8))return 0;
    uintptr_t elem=*(uint64_t*)data; return LooksLikePtr(elem)?elem:0;   // element is the next quest UCLASS
}
static uintptr_t LiveInstOfClass(uintptr_t cls,uintptr_t exclude){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14); if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj)||obj==exclude)continue;
            if(ClassOf(obj)!=cls)continue; char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strncmp(on,"Default__",9)==0)continue; return obj; } }
    return 0;
}
static void DcClearFinished(){ uint32_t fvo=PropOffsetSuper(ClassOf(g_dcTB),"FinishedVolumes"); if(fvo!=0xFFFFFFFF){ uint32_t z=0; SafeWrite((uint8_t*)(g_dcTB+fvo+8),(uint8_t*)&z,4); } }
static void DcCallOneObjParam(uintptr_t obj,const char* fn,uintptr_t param){
    uintptr_t ch=0; uint64_t res[4]={0,0,0,0}; void* pf=nullptr; uintptr_t th=0,c2=0; ResolveFuncSuper(ClassOf(obj),fn,&pf,&th,&c2);
    if(!pf){ Markerf("[DC] %s not found\r\n",fn); return; }
    memset(g_bplocals,0,sizeof(g_bplocals));
    for(uintptr_t p=c2;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
        uint64_t fp=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0; if(!(fp&0x80))continue;
        uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
        if(o!=0xFFFFFFFF&&o+8<=sizeof(g_bplocals)) *(uint64_t*)(g_bplocals+o)=(uint64_t)param; break; }
    bool fl=CallBPGuarded((uintptr_t)pf,(void*)obj,res); Markerf("[DC] %s %s\r\n",fn,fl?"FAULTED":"ok");
}
static void DcComplete(){
    uintptr_t ch=0; uint64_t res[4]={0,0,0,0};
    uint32_t co=PropOffsetSuper(ClassOf(g_dcTB),"CurrentObjectiveCount"), ta=PropOffsetSuper(ClassOf(g_dcTB),"TrainingActive"), ts=PropOffsetSuper(ClassOf(g_dcTB),"TrainingSuccessful");
    int32_t one=1; uint8_t t1=1,t0=0;
    if(ts!=0xFFFFFFFF) SafeWrite((uint8_t*)(g_dcTB+ts),&t1,1);
    if(co!=0xFFFFFFFF) SafeWrite((uint8_t*)(g_dcTB+co),(uint8_t*)&one,4);
    if(ta!=0xFFFFFFFF) SafeWrite((uint8_t*)(g_dcTB+ta),&t0,1);
    uintptr_t f=FindBPFunc(ClassOf(g_dcTB),"OnRep_TrainingActive",&ch);
    if(f){ memset(g_bplocals,0,sizeof(g_bplocals)); bool fl=CallBPGuarded(f,(void*)g_dcTB,res); Markerf("[DC] closer OnRep_TrainingActive %s\r\n",fl?"FAULTED":"ok"); }
}
static bool ResolveDriveChain(){
    ResolveSpawnSeq();   // set up g_gm2 / g_gsCDO / g_begin*/g_finish* + spawn xform so SpawnActorCls works in the chain-advance
    // component (live, by CurrentTrainingVolume!=0), its volume, hero, and the FIRST quest of the chain (WASD).
    uintptr_t oo=g_modBase+kObjObjectsRva; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14); int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; uintptr_t fb=0;
    for(int ci=0;ci<numChunks&&!g_dcTB;ci++){ uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue; if(strcmp(cn,"Comp_GameState_TrainingBase_C")!=0)continue; char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strstr(on,"GEN_VARIABLE")||strstr(on,"Race"))continue; uint32_t cv=PropOffsetSuper(cls,"CurrentTrainingVolume"); uint64_t v=(cv!=0xFFFFFFFF&&SafeReadable((void*)(obj+cv),8))?*(uint64_t*)(obj+cv):0; if(v){ g_dcTB=obj; g_dcVol=v; break; } if(!fb)fb=obj; } }
    if(!g_dcTB)g_dcTB=fb;
    if(g_dcTB&&!g_dcVol){ uint32_t cv=PropOffsetSuper(ClassOf(g_dcTB),"CurrentTrainingVolume"); if(cv!=0xFFFFFFFF&&SafeReadable((void*)(g_dcTB+cv),8)) g_dcVol=*(uint64_t*)(g_dcTB+cv); }
    if(!g_dcVol) g_dcVol=FindInstByClass("TrainingVolume",nullptr);
    g_dcHero=FindInstByClass("BP_HERO_",nullptr);
    // start the chain at the NEXT quest after WASD (the user asked for the NEXT volume): follow WASD.NextQuestInChain.
    uintptr_t wasd=FindInstByClass("Quest_Basics_WASD",nullptr);
    uintptr_t nextcls = wasd?NextQuestClass(wasd):0;
    if(nextcls){ g_dcQuest=LiveInstOfClass(nextcls,wasd); if(!g_dcQuest){ g_gm2=FindInstByClass("GameMode_Tutorial",nullptr); g_gsCDO=FindObjExact("Default__GameplayStatics"); if(!g_seqClass){} ResolveSpawnSeq(); g_dcQuest=SpawnActorCls(nextcls,"next-quest"); } }
    if(!g_dcQuest) g_dcQuest=wasd;   // fall back to re-driving WASD
    char qn[96]="-"; if(g_dcQuest&&ClassOf(g_dcQuest))GetFNameStr(NameId(ClassOf(g_dcQuest)),qn,sizeof(qn));
    Markerf("[DC] TB=0x%llX vol=0x%llX hero=0x%llX firstNextQuest=0x%llX(%s) chainMax=%d\r\n",(unsigned long long)g_dcTB,(unsigned long long)g_dcVol,(unsigned long long)g_dcHero,(unsigned long long)g_dcQuest,qn,kChainMax);
    return g_dcTB && g_dcVol && g_dcQuest;
}
static void DoDriveChain(){
    if(g_dcMs && GetTickCount()-g_dcMs < 700) return; g_dcMs=GetTickCount();
    switch(g_dcPhase){
    case 0: {  // activate the lesson quest (OnTrainingVolume sets its marker) + clear FinishedVolumes.
        char qn[96]="-"; if(ClassOf(g_dcQuest))GetFNameStr(NameId(ClassOf(g_dcQuest)),qn,sizeof(qn));
        Markerf("[DC] ===== LESSON %d/%d: quest=0x%llX %s =====\r\n",g_dcLesson+1,kChainMax,(unsigned long long)g_dcQuest,qn);
        DcClearFinished();
        DcCallOneObjParam(g_dcQuest,"OnTrainingVolume",g_dcVol);
        Markerf("[DC] activated: OBJARROW=0x%llX AssociatedVol=0x%llX\r\n",(unsigned long long)ReadProp(g_dcQuest,"OBJARROW"),(unsigned long long)ReadProp(g_dcQuest,"AssociatedTrainingVolume"));
        g_dcPhase=1; g_dcMs=GetTickCount()+2200; break; }
    case 1: {  // GameStateTryStartTraining(vol) — start the lesson (arrows/objective come up).
        DcCallOneObjParam(g_dcTB,"GameStateTryStartTraining",g_dcVol);
        Markerf("[DC] started: TrainingActive=0x%llX CurObjCount=0x%llX\r\n",(unsigned long long)ReadProp(g_dcTB,"TrainingActive"),(unsigned long long)ReadProp(g_dcTB,"CurrentObjectiveCount"));
        g_dcPhase=2; g_dcMs=GetTickCount()+2600; break; }
    case 2: {  // complete via the ungated closer.
        DcComplete();
        uint32_t fvo=PropOffsetSuper(ClassOf(g_dcTB),"FinishedVolumes"); uint32_t fvn=0; if(fvo!=0xFFFFFFFF&&SafeReadable((void*)(g_dcTB+fvo+8),4)) fvn=*(uint32_t*)(g_dcTB+fvo+8);
        Markerf("[DC] completed: TrainingSuccessful=0x%llX TrainingActive=0x%llX FinishedVolumes.Num=%u\r\n",(unsigned long long)ReadProp(g_dcTB,"TrainingSuccessful"),(unsigned long long)ReadProp(g_dcTB,"TrainingActive"),fvn);
        g_dcPhase=3; g_dcMs=GetTickCount()+1500; break; }
    case 3: {  // advance to the next quest in the chain.
        g_dcLesson++;
        if(g_dcLesson>=kChainMax){ Markerf("[DC] reached chainMax=%d -> done\r\n",kChainMax); g_done=1; return; }
        uintptr_t nextcls=NextQuestClass(g_dcQuest);
        if(!nextcls){ Marker("[DC] no NextQuestInChain -> chain end\r\n"); g_done=1; return; }
        char ncn[96]="-"; GetFNameStr(NameId(nextcls),ncn,sizeof(ncn));
        uintptr_t inst=LiveInstOfClass(nextcls,g_dcQuest);
        if(!inst && g_beginThunk && g_gm2 && g_gsCDO){ Markerf("[DC] no live %s -> spawning\r\n",ncn); inst=SpawnActorCls(nextcls,"chain-next"); }
        if(!LooksLikePtr(inst)){ Markerf("[DC] no instance for next quest %s (spawn globals begin=0x%llX) -> stop\r\n",ncn,(unsigned long long)g_beginThunk); g_done=1; return; }
        g_dcQuest=inst; g_dcPhase=0; g_dcMs=GetTickCount()+1200; break; }
    }
}

// ★★★ S93 RM_CAMERA — fix the over-zoomed possess camera. The live camera POV.Location == the hero's location exactly
// (camera sits AT the hero, pitch ~-66°) while the hero's LokiCharacterSpringArmComponent wants TargetArmLength=3020 —
// i.e. the spring arm is NOT pulling the camera back, almost certainly because the possessed hero's camera/spring-arm
// components aren't TICKING (the same deploy-gate that froze the CMC in S75). This enables their ticks + re-activates
// them, then re-samples the camera POV to see whether it pulls back to a top-down distance.
static uintptr_t g_cmPC=0, g_cmHero=0, g_cmComp=0, g_cmArm=0; static int g_cmStep=0; static DWORD g_cmMs=0;
static void CamPOV(const char* tag){
    uint32_t pmo=PropOffsetSuper(ClassOf(g_cmPC),"PlayerCameraManager");
    uintptr_t pm=(pmo!=0xFFFFFFFF&&SafeReadable((void*)(g_cmPC+pmo),8))?*(uint64_t*)(g_cmPC+pmo):0;
    if(!LooksLikePtr(pm)){ Markerf("[CM] %s no cam manager\r\n",tag); return; }
    uint32_t cco=PropOffsetSuper(ClassOf(pm),"CameraCachePrivate");
    if(cco==0xFFFFFFFF||!SafeReadable((void*)(pm+cco+0x10),48)){ Markerf("[CM] %s no POV (cco=0x%X)\r\n",tag,cco); return; }
    double* L=(double*)(pm+cco+0x10); double* R=(double*)(pm+cco+0x28);
    double hl[3]={0,0,0}; ActorLoc(g_cmHero,hl);
    double dx=L[0]-hl[0],dy=L[1]-hl[1],dz=L[2]-hl[2];
    Markerf("[CM] %s POV.Loc=(%.0f,%.0f,%.0f) rot(P,Y)=(%.0f,%.0f) hero=(%.0f,%.0f,%.0f) camDistFromHero=%.0f\r\n",
        tag,L[0],L[1],L[2],R[0],R[1],hl[0],hl[1],hl[2],(double)__builtin_sqrt(dx*dx+dy*dy+dz*dz));
}
static void CamCallBools(uintptr_t obj,const char* fn,uint8_t b0,uint8_t b1){
    if(!LooksLikePtr(obj))return; void* pf=nullptr; uintptr_t th=0,ch=0; ResolveFuncNative(ClassOf(obj),fn,&pf,&th,&ch);
    if(!th){ Markerf("[CM] %s not found\r\n",fn); return; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    int i=0; for(uintptr_t p=ch;LooksLikePtr(p)&&i<2;p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
        uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0; if(!(fl&0x80))continue;
        uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
        if(o!=0xFFFFFFFF) ((uint8_t*)g_pbuf)[o]=(i==0)?b0:b1; i++; }
    bool f=CallNativeGuarded(pf,th,ch,(void*)obj,g_pbuf,g_rbuf); Markerf("[CM] %s(%d,%d) %s\r\n",fn,b0,b1,f?"FAULTED":"ok");
}
static bool ResolveCamera(){
    g_cmPC=FindInstByClass("LokiPlayerController_Dev",nullptr);
    g_cmHero=FindInstByClass("BP_HERO_",nullptr);
    if(g_cmHero){ uint32_t co=PropOffsetSuper(ClassOf(g_cmHero),"Camera"); if(co!=0xFFFFFFFF&&SafeReadable((void*)(g_cmHero+co),8)) g_cmComp=*(uint64_t*)(g_cmHero+co);
        if(g_cmComp){ uint32_t ao=PropOffsetSuper(ClassOf(g_cmComp),"AttachParent"); if(ao!=0xFFFFFFFF&&SafeReadable((void*)(g_cmComp+ao),8)) g_cmArm=*(uint64_t*)(g_cmComp+ao); } }
    char an[96]="-"; if(g_cmArm&&ClassOf(g_cmArm))GetFNameStr(NameId(ClassOf(g_cmArm)),an,sizeof(an));
    Markerf("[CM] pc=0x%llX hero=0x%llX camComp=0x%llX arm=0x%llX(%s)\r\n",(unsigned long long)g_cmPC,(unsigned long long)g_cmHero,(unsigned long long)g_cmComp,(unsigned long long)g_cmArm,an);
    return g_cmPC&&g_cmHero&&g_cmArm;
}
static void DoCamera(){
    if(g_cmMs && GetTickCount()-g_cmMs < 700) return; g_cmMs=GetTickCount();
    switch(g_cmStep++){
    case 0: CamPOV("BEFORE"); break;
    case 1:
        CamCallBools(g_cmArm,"SetComponentTickEnabled",1,0);
        CamCallBools(g_cmArm,"Activate",1,0);
        CamCallBools(g_cmComp,"SetComponentTickEnabled",1,0);
        CamCallBools(g_cmComp,"Activate",1,0);
        CamCallBools(g_cmHero,"SetActorTickEnabled",1,0);
        g_cmMs=GetTickCount()+2500; break;
    case 2: CamPOV("AFTER-TICKENABLE"); break;
    default: Marker("[CM] done\r\n"); g_done=1; return;
    }
}

// ★★★ S93 RM_TOPDOWNCAM — the camera TAKEOVER. Tick-enable didn't help (the camera manager computes POV = hero loc
// directly, ignoring the spring arm), so spawn our OWN CameraActor, position it above/behind the hero at SUPERVIVE's
// own framing (pitch -66°, ~3020 back = offset (0,+1229,+2760)) and RE-ASSERT it as the PC view target every few hits
// (the manager reverts a one-time SetViewTargetWithBlend each frame — proven in ds_hybrid S78). Holds ~120s so the
// top-down view can be seen/screenshotted; the possess camera reverts when the shim releases.
static uintptr_t g_tcPC=0,g_tcHero=0,g_tcCam=0,g_tcCamCls=0; static bool g_tcSpawned=false; static volatile long g_tcHit=0;
static void* g_tcSlFn=nullptr; static uintptr_t g_tcSlThunk=0,g_tcSlChild=0; static uint32_t g_tcSlLoc=0xFFFFFFFF,g_tcSlTele=0xFFFFFFFF;
static void* g_tcSrFn=nullptr; static uintptr_t g_tcSrThunk=0,g_tcSrChild=0; static uint32_t g_tcSrRot=0xFFFFFFFF,g_tcSrTele=0xFFFFFFFF;
static void* g_tcSvtFn=nullptr; static uintptr_t g_tcSvtThunk=0,g_tcSvtChild=0; static uint32_t g_tcSvtTgt=0xFFFFFFFF;
#ifndef KCAMUP
#define KCAMUP 2760.0
#endif
#ifndef KCAMBACK
#define KCAMBACK 1229.0
#endif
#ifndef KCAMPITCH
#define KCAMPITCH -66.0
#endif
static bool ResolveTopDownCam(){
    ResolveSpawnSeq();   // g_gm2/g_gsCDO/g_begin*/g_finish* + spawn xform
    g_tcPC=FindInstByClass("LokiPlayerController_Dev",nullptr);
    g_tcHero=FindInstByClass("BP_HERO_",nullptr);
    g_tcCamCls=FindClassExact("CameraActor");
    if(g_tcPC){ ResolveFuncNative(ClassOf(g_tcPC),"SetViewTargetWithBlend",&g_tcSvtFn,&g_tcSvtThunk,&g_tcSvtChild);
        if(g_tcSvtChild){ uint32_t o=ParamOffset(g_tcSvtChild,"NewViewTarget"); if(o!=0xFFFFFFFF)g_tcSvtTgt=o; } }
    Markerf("[TC] pc=0x%llX hero=0x%llX camCls=0x%llX svtThunk=0x%llX(tgt@0x%X) gm=0x%llX begin=0x%llX\r\n",
        (unsigned long long)g_tcPC,(unsigned long long)g_tcHero,(unsigned long long)g_tcCamCls,(unsigned long long)g_tcSvtThunk,g_tcSvtTgt,(unsigned long long)g_gm2,(unsigned long long)g_beginThunk);
    return g_tcPC&&g_tcHero&&g_tcCamCls&&g_tcSvtThunk&&g_beginThunk&&g_gm2&&g_gsCDO;
}
static void DoTopDownCam(){
    long t=InterlockedIncrement(&g_tcHit);
    // ★ S106b FK-7 (game-thread arm). FIRST thing every hit, and BEFORE the early-out below: the
    // deterministic 173-201 s GameThread crash is APlayerCameraManager ticking a corrupt
    // ViewTarget.Target (low byte overwritten with 0x01 -- see the VtGuard block for the full
    // measurement). Placed ahead of the ActorLoc early-out on purpose: if the hero read fails we
    // still must not leave a corrupt pointer for UWorld::Tick to dispatch through.
    // RM_PLAY and RM_MESHCAM both funnel through here, so this one call covers all three camera modes.
    VtGuard(g_tcPC?g_tcPC:g_wmPC,g_tcCam);
    double hl[3]={0,0,0}; if(!ActorLoc(g_tcHero,hl)) return;
    if(!g_tcSpawned){
        memset(g_xform,0,sizeof(g_xform)); *(double*)(g_xform+0x18)=1.0;
        *(double*)(g_xform+0x20)=hl[0]; *(double*)(g_xform+0x28)=hl[1]+KCAMBACK; *(double*)(g_xform+0x30)=hl[2]+KCAMUP;
        // ★★ S106d — THIS IS THE VIEW-TARGET CAMERA. The old 0x38/0x40/0x48 write left Scale3D.Z = 0, so
        // the actor whose pointer FK-7 corrupts was itself spawned degenerate (1,1,0). See KXFORMFIX (L109).
        XfScale(1.0,1.0,1.0);
        g_tcCam=SpawnActorCls(g_tcCamCls,"topdown-cam");
        if(!LooksLikePtr(g_tcCam)){ Marker("[TC] camera spawn FAILED -> abort\r\n"); g_done=1; return; }
        ResolveFuncSuper(ClassOf(g_tcCam),"K2_SetActorLocation",&g_tcSlFn,&g_tcSlThunk,&g_tcSlChild);
        if(g_tcSlChild){ uint32_t o=ParamOffset(g_tcSlChild,"NewLocation"); if(o!=0xFFFFFFFF)g_tcSlLoc=o; o=ParamOffset(g_tcSlChild,"bTeleport"); if(o!=0xFFFFFFFF)g_tcSlTele=o; }
        ResolveFuncSuper(ClassOf(g_tcCam),"K2_SetActorRotation",&g_tcSrFn,&g_tcSrThunk,&g_tcSrChild);
        if(g_tcSrChild){ uint32_t o=ParamOffset(g_tcSrChild,"NewRotation"); if(o!=0xFFFFFFFF)g_tcSrRot=o; o=ParamOffset(g_tcSrChild,"bTeleportPhysics"); if(o!=0xFFFFFFFF)g_tcSrTele=o; }
        Markerf("[TC] *** spawned CameraActor=0x%llX at (%.0f,%.0f,%.0f) setLoc@0x%X setRot@0x%X ***\r\n",(unsigned long long)g_tcCam,hl[0],hl[1]+KCAMBACK,hl[2]+KCAMUP,g_tcSlLoc,g_tcSrRot);
        g_tcSpawned=true;
    }
    // follow: reposition + orient the camera top-down over the hero each hit.
    if(g_tcSlThunk && g_tcSlLoc!=0xFFFFFFFF){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        double* L=(double*)((uint8_t*)g_pbuf+g_tcSlLoc); L[0]=hl[0]; L[1]=hl[1]+KCAMBACK; L[2]=hl[2]+KCAMUP;
        if(g_tcSlTele!=0xFFFFFFFF) ((uint8_t*)g_pbuf)[g_tcSlTele]=1;
        CallNativeGuarded(g_tcSlFn,g_tcSlThunk,g_tcSlChild,(void*)g_tcCam,g_pbuf,g_rbuf); }
    if(g_tcSrThunk && g_tcSrRot!=0xFFFFFFFF){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        double* R=(double*)((uint8_t*)g_pbuf+g_tcSrRot); R[0]=KCAMPITCH; R[1]=-90.0; R[2]=0.0;   // Pitch,Yaw,Roll
        if(g_tcSrTele!=0xFFFFFFFF) ((uint8_t*)g_pbuf)[g_tcSrTele]=1;
        CallNativeGuarded(g_tcSrFn,g_tcSrThunk,g_tcSrChild,(void*)g_tcCam,g_pbuf,g_rbuf); }
    // re-assert the view target (the manager reverts it each frame); every 3rd hit is enough.
    if((t%3)==0 && g_tcSvtThunk && g_tcSvtTgt!=0xFFFFFFFF){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)((uint8_t*)g_pbuf+g_tcSvtTgt)=(uint64_t)g_tcCam;
        CallNativeGuarded(g_tcSvtFn,g_tcSvtThunk,g_tcSvtChild,(void*)g_tcPC,g_pbuf,g_rbuf); }
}

// ★★★ S93 RM_MESHCAM — build the possessed hero's VISUAL MESH (which force-open skipped) then hold the top-down cam.
// The hero has Mesh=0 + CosmeticsController=0: SUPERVIVE builds the whole hero body via its cosmetics controller,
// created in `ClientInitialComponentSetup` (a BP fn the force-open client-join skipped). The ORIGINAL spawn shim used
// native calls (RefreshCosmetics/OnRep) and got controller=0 — but it could NOT call the BP-bytecode setup fns. The
// S91 BP-call primitive can, so drive the real client setup, then hold the top-down camera so the result is visible.
static bool g_mcMeshTried=false;
static void McBuildMesh(){
    uintptr_t hero=g_tcHero, ch=0, f=0; uint64_t res[4]={0,0,0,0};
    Markerf("[MC] BEFORE Mesh=0x%llX CosmeticsController=0x%llX\r\n",(unsigned long long)ReadProp(hero,"Mesh"),(unsigned long long)ReadProp(hero,"CosmeticsController"));
    // 1. ClientInitialComponentSetup (BP) — the client-side component/cosmetics setup force-open never ran.
    f=FindBPFunc(ClassOf(hero),"ClientInitialComponentSetup",&ch);
    if(f){ memset(g_bplocals,0,sizeof(g_bplocals)); bool fl=CallBPGuarded(f,(void*)hero,res); Markerf("[MC] ClientInitialComponentSetup %s\r\n",fl?"FAULTED":"ok"); }
    else Marker("[MC] ClientInitialComponentSetup not found\r\n");
    // 2. GetBaseCosmeticsController (BP) — creates/returns the controller that builds the mesh.
    f=FindBPFunc(ClassOf(hero),"GetBaseCosmeticsController",&ch);
    if(f){ memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res)); bool fl=CallBPGuarded(f,(void*)hero,res); Markerf("[MC] GetBaseCosmeticsController %s ret=0x%llX\r\n",fl?"FAULTED":"ok",(unsigned long long)res[0]); }
    // 3. RefreshCosmetics (native).
    { void* nf=nullptr; uintptr_t th=0,nc=0; ResolveFuncNative(ClassOf(hero),"RefreshCosmetics",&nf,&th,&nc); if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); bool fl=CallNativeGuarded(nf,th,nc,(void*)hero,g_pbuf,g_rbuf); Markerf("[MC] RefreshCosmetics(native) %s\r\n",fl?"FAULTED":"ok"); } }
    // 4. BP_PostSetupCosmetics (BP).
    f=FindBPFunc(ClassOf(hero),"BP_PostSetupCosmetics",&ch);
    if(f){ memset(g_bplocals,0,sizeof(g_bplocals)); memset(res,0,sizeof(res)); bool fl=CallBPGuarded(f,(void*)hero,res); Markerf("[MC] BP_PostSetupCosmetics %s\r\n",fl?"FAULTED":"ok"); }
    Markerf("[MC] AFTER Mesh=0x%llX CosmeticsController=0x%llX (cosmetics load is async — the model may appear over a few seconds)\r\n",(unsigned long long)ReadProp(hero,"Mesh"),(unsigned long long)ReadProp(hero,"CosmeticsController"));
}
// ★★★ S93 RM_DROPIN — drive the REAL drop-in descent so the game's own OnLanded deploy cascade activates the hero
// (cosmetics mesh + movement). The S79 piecemeal deploy fns "changed nothing"; the untried lever is the DropPlane
// orchestration: Comp_GameMode_DropPlane_Tutorial.SpawnPlane (BP event — reads level-tagged path markers) ->
// AddPlayerToDropPlane (native) -> the tutorial auto-drops (GetAutoDropLocation) -> descent -> OnLanded. Empirical.
static uintptr_t g_diComp=0, g_diPC=0, g_diHero=0; static int g_diStep=0; static DWORD g_diMs=0;
static int CountByClassSubDI(const char* sub){ char f[8]; return CountByClassSub(sub,f,0); }
static bool ResolveDropIn(){
    // the live DropPlane component (non-archetype)
    uintptr_t oo=g_modBase+kObjObjectsRva; uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14); int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks&&!g_diComp;ci++){ uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue; if(strcmp(cn,"Comp_GameMode_DropPlane_Tutorial_C")!=0)continue; char on[96]; on[0]=0; GetFNameStr(NameId(obj),on,sizeof(on)); if(strstr(on,"GEN_VARIABLE"))continue; g_diComp=obj; break; } }
    g_diPC=FindInstByClass("LokiPlayerController_Dev",nullptr);
    g_diHero=FindInstByClass("BP_HERO_",nullptr);
    char cn[96]="-"; if(g_diComp&&ClassOf(g_diComp))GetFNameStr(NameId(ClassOf(g_diComp)),cn,sizeof(cn));
    Markerf("[DI] dropPlaneComp=0x%llX(%s) pc=0x%llX hero=0x%llX\r\n",(unsigned long long)g_diComp,cn,(unsigned long long)g_diPC,(unsigned long long)g_diHero);
    return g_diComp!=0;
}
static void DoDropIn(){
    if(g_diMs && GetTickCount()-g_diMs < 800) return; g_diMs=GetTickCount();
    uintptr_t ch=0,f=0; uint64_t res[4]={0,0,0,0};
    switch(g_diStep++){
    case 0:
        Markerf("[DI] BEFORE: BP_DropPlane actors=%d hero.Mesh=0x%llX hero.CosmeticsController=0x%llX IsHeroPredropHidden=0x%llX\r\n",
            CountByClassSubDI("DropPlane_C"),(unsigned long long)ReadProp(g_diHero,"Mesh"),(unsigned long long)ReadProp(g_diHero,"CosmeticsController"),(unsigned long long)ReadProp(g_diHero,"IsHeroPredropHidden"));
        break;
    case 1: {  // SpawnPlane (BP event) on the DropPlane component.
        f=FindBPFunc(ClassOf(g_diComp),"SpawnPlane",&ch);
        if(!f){ Marker("[DI] SpawnPlane not found\r\n"); break; }
        memset(g_bplocals,0,sizeof(g_bplocals));
        bool fl=CallBPGuarded(f,(void*)g_diComp,res);
        Markerf("[DI] SpawnPlane %s\r\n",fl?"FAULTED":"ok");
        g_diMs=GetTickCount()+3000; break; }
    case 2:
        Markerf("[DI] AFTER SpawnPlane: BP_DropPlane actors=%d  Plane*=%d\r\n",CountByClassSubDI("DropPlane_C"),CountByClassSubDI("BP_DropPlane"));
        break;
    case 3: {  // AddPlayerToDropPlane (native) — put the PC on the plane.
        void* nf=nullptr; uintptr_t th=0,nc=0; ResolveFuncNative(ClassOf(g_diComp),"AddPlayerToDropPlane",&nf,&th,&nc);
        if(!th){ Marker("[DI] AddPlayerToDropPlane not found\r\n"); break; }
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        // its first object param = the player (PC or PlayerState); try the PC.
        if(LooksLikePtr(nc)){ uint32_t o=SafeReadable((void*)(nc+FPROP_OFFSET),4)?*(uint32_t*)(nc+FPROP_OFFSET):0xFFFFFFFF; if(o!=0xFFFFFFFF) *(uint64_t*)((uint8_t*)g_pbuf+o)=(uint64_t)g_diPC; }
        bool fl=CallNativeGuarded(nf,th,nc,(void*)g_diComp,g_pbuf,g_rbuf);
        Markerf("[DI] AddPlayerToDropPlane(PC) %s\r\n",fl?"FAULTED":"ok");
        g_diMs=GetTickCount()+3000; break; }
    case 4: {  // GetAutoDropLocation (BP) — the tutorial auto-picks the drop spot.
        f=FindBPFunc(ClassOf(g_diComp),"GetAutoDropLocation",&ch);
        if(f){ memset(g_bplocals,0,sizeof(g_bplocals)); bool fl=CallBPGuarded(f,(void*)g_diComp,res); Markerf("[DI] GetAutoDropLocation %s\r\n",fl?"FAULTED":"ok"); }
        else Marker("[DI] GetAutoDropLocation not found\r\n");
        g_diMs=GetTickCount()+4000; break; }
    case 5:
        Markerf("[DI] AFTER: BP_DropPlane=%d hero.Mesh=0x%llX hero.CosmeticsController=0x%llX IsHeroPredropHidden=0x%llX skeletals=%d\r\n",
            CountByClassSubDI("DropPlane_C"),(unsigned long long)ReadProp(g_diHero,"Mesh"),(unsigned long long)ReadProp(g_diHero,"CosmeticsController"),(unsigned long long)ReadProp(g_diHero,"IsHeroPredropHidden"),CountByClassSubDI("SkeletalMeshComponent"));
        break;
    default: Marker("[DI] done\r\n"); g_done=1; return;
    }
}
// ★★★ S93 RM_MAKEMESH — recreate a VISIBLE hero body FROM SCRATCH (not the game's cosmetics controller).
// The game's cosmetics system won't build the mesh outside the real deploy — but we don't need it: create our OWN
// SkeletalMeshComponent on the hero (AddComponentByClass, BPCallable) + assign a loaded hero skeletal mesh
// (SetSkeletalMeshAsset). First test uses an already-loaded body mesh (SK_KaijuCaster_Default) to prove visibility;
// refine to Ronin's own mesh (async-load) once the approach shows a body.
static uintptr_t g_mkHero=0, g_mkSkelCls=0, g_mkMesh=0, g_mkComp=0; static int g_mkStep=0; static DWORD g_mkMs=0;
static int CountHeroSkelComps(uintptr_t hero){
    int n=0; uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14); if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t outer=SafeReadable((void*)(obj+0x28),8)?*(uintptr_t*)(obj+0x28):0; if(outer!=hero)continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(strstr(cn,"SkeletalMesh"))n++; } }
    return n;
}
static bool ResolveMakeMesh(){
    g_mkHero=FindInstByClass("BP_HERO_",nullptr);
    g_mkSkelCls=FindClassExact("SkeletalMeshComponent");
    g_mkMesh=FindObjExact("SK_KaijuCaster_Default"); if(!g_mkMesh) g_mkMesh=FindObjExact("SK_Base_Wisp"); if(!g_mkMesh) g_mkMesh=FindObjExact("SK_HeroPlatform_Default");
    char mn[96]="-"; if(g_mkMesh) GetFNameStr(NameId(g_mkMesh),mn,sizeof(mn));
    Markerf("[MK] hero=0x%llX skelCls=0x%llX mesh=0x%llX(%s)\r\n",(unsigned long long)g_mkHero,(unsigned long long)g_mkSkelCls,(unsigned long long)g_mkMesh,mn);
    return g_mkHero && g_mkSkelCls && g_mkMesh;
}
static void DoMakeMesh(){
    if(g_mkMs && GetTickCount()-g_mkMs < 800) return; g_mkMs=GetTickCount();
    uintptr_t ch=0,f=0; uint64_t res[4]={0,0,0,0};
    switch(g_mkStep++){
    case 0: Markerf("[MK] BEFORE: hero SkeletalMeshComponents(direct)=%d\r\n",CountHeroSkelComps(g_mkHero)); break;
    case 1: {  // AddComponentByClass (NATIVE — S55 direct-thunk primitive): SkeletalMeshComponent, bManualAttachment=false, identity xform, bDeferredFinish=false.
        void* acfn=nullptr; uintptr_t acth=0,acch=0; ResolveFuncSuper(ClassOf(g_mkHero),"AddComponentByClass",&acfn,&acth,&acch);
        if(!acth){ Marker("[MK] AddComponentByClass thunk not found\r\n"); break; }
        memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); uint32_t retOff=0xFFFFFFFF;
        for(uintptr_t p=acch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            char pn[64]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF; if(o==0xFFFFFFFF||o+0x50>sizeof(g_gsbuf))continue;
            uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0;
            if(strcmp(pn,"Class")==0) *(uint64_t*)(g_gsbuf+o)=(uint64_t)g_mkSkelCls;
            else if(strcmp(pn,"RelativeTransform")==0){ double* T=(double*)(g_gsbuf+o); T[3]=1.0; T[7]=1.0; T[8]=1.0; T[9]=1.0; }   // quatW@0x18, Scale3D@0x38/0x40/0x48
            else if(fl&0x400) retOff=o;   // CPF_ReturnParm
        }
        bool flt=CallNativeGuarded(acfn,acth,acch,(void*)g_mkHero,g_gsbuf,g_rbuf);
        g_mkComp=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(g_mkComp)&&retOff!=0xFFFFFFFF) g_mkComp=*(uint64_t*)(g_gsbuf+retOff);
        char ccn[96]="-"; if(LooksLikePtr(g_mkComp)&&ClassOf(g_mkComp)) GetFNameStr(NameId(ClassOf(g_mkComp)),ccn,sizeof(ccn));
        Markerf("[MK] AddComponentByClass %s -> comp=0x%llX(%s)\r\n",flt?"FAULTED":"ok",(unsigned long long)g_mkComp,ccn);
        g_mkMs=GetTickCount()+1800; break; }
    case 2: {  // SetSkeletalMeshAsset(NewMesh) on the created component (NATIVE).
        if(!LooksLikePtr(g_mkComp)){ Marker("[MK] no component -> abort\r\n"); g_done=1; return; }
        void* smfn=nullptr; uintptr_t smth=0,smch=0; ResolveFuncSuper(ClassOf(g_mkComp),"SetSkeletalMeshAsset",&smfn,&smth,&smch);
        if(!smth){ Marker("[MK] SetSkeletalMeshAsset thunk not found\r\n"); break; }
        memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        for(uintptr_t p=smch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0; if(!(fl&0x80))continue;
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            if(o!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+o)=(uint64_t)g_mkMesh; break; }
        bool flt=CallNativeGuarded(smfn,smth,smch,(void*)g_mkComp,g_gsbuf,g_rbuf);
        Markerf("[MK] SetSkeletalMeshAsset(mesh) %s\r\n",flt?"FAULTED":"ok");
        // ANIM-SAFE: stop the component ticking + pause anims so it renders a STATIC reference pose (no anim-thread
        // eval against a mismatched skeleton -> avoids the S93 anim crash). A body that doesn't animate is fine for
        // the first visible test.
        { void* tf=nullptr; uintptr_t tt=0,tc=0; ResolveFuncSuper(ClassOf(g_mkComp),"SetComponentTickEnabled",&tf,&tt,&tc);
          if(tt){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=0; CallNativeGuarded(tf,tt,tc,(void*)g_mkComp,g_pbuf,g_rbuf); Marker("[MK] SetComponentTickEnabled(false)\r\n"); } }
        { void* pf=nullptr; uintptr_t pt=0,pc=0; ResolveFuncSuper(ClassOf(g_mkComp),"PauseAnims",&pf,&pt,&pc);
          if(pt){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=1; CallNativeGuarded(pf,pt,pc,(void*)g_mkComp,g_pbuf,g_rbuf); Marker("[MK] PauseAnims(true)\r\n"); } }
        // visibility on
        { void* vf=nullptr; uintptr_t vt=0,vc=0; ResolveFuncSuper(ClassOf(g_mkComp),"SetVisibility",&vf,&vt,&vc);
          if(vt){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=1; CallNativeGuarded(vf,vt,vc,(void*)g_mkComp,g_pbuf,g_rbuf); Marker("[MK] SetVisibility(true)\r\n"); } }
        g_mkMs=GetTickCount()+2500; break; }
    case 3: {
        uint32_t so=PropOffsetSuper(ClassOf(g_mkComp),"SkeletalMeshAsset"); uint64_t sm=(so!=0xFFFFFFFF&&SafeReadable((void*)(g_mkComp+so),8))?*(uint64_t*)(g_mkComp+so):0;
        Markerf("[MK] AFTER: hero SkeletalMeshComponents=%d comp=0x%llX comp.SkeletalMeshAsset@0x%X=0x%llX\r\n",CountHeroSkelComps(g_mkHero),(unsigned long long)g_mkComp,so,(unsigned long long)sm);
        Marker("[MK] *** if a body appeared at the hero, the from-scratch mesh works (T-pose expected — no AnimBP) ***\r\n");
        break; }
    default: Marker("[MK] done\r\n"); g_done=1; return;
    }
}
static bool ResolveMeshCam(){ return ResolveTopDownCam(); }   // same resolve (hero/PC/camera + spawn infra)
static void DoMeshCam(){
    if(!g_mcMeshTried){ g_mcMeshTried=true; McBuildMesh(); }
    DoTopDownCam();   // spawn + hold the top-down camera so the (hopefully now-visible) hero can be seen
}

// ★★★ S94 RM_PLAY — the VISIBLE + MOVABLE hero, in ONE PI-hooking shim (so no PI-hook contention with a separate
// camera/puppet shim). On the possessed force-open hero it: (1) teleports to walkable ground (no [SP] sky-lift),
// (2) builds a from-scratch SkeletalMeshComponent assigned RONIN's own body mesh (anim/tick OFF = static reference
// pose, no anim-thread crash), (3) holds a top-down CameraActor following the hero (reuses DoTopDownCam), (4) drives
// WASD -> CMC velocity every hit (reuses DoPuppet's velocity path). Inject gft_ready_fix FIRST (quiets the
// mantle/FudgeMantling toggle spam that crashed S75 movement). Holds until the worker timeout (playable + screenshottable).
static bool g_plInit=false; static uintptr_t g_plMesh=0, g_plComp=0, g_plSkelCls=0; static char g_plMeshName[96]="-";
// S94 iter4: async-load Ronin's REAL mesh. The resident placeholder meshes (KaijuCaster etc.) are header-only (no
// GPU/skeleton render data) so they never render (and ticking them crashes). AsyncLoadPrimaryAssets(Ronin bundle)
// streams SK_Ronin_Default WITH render data; poll for it, then build the body with it.
static uintptr_t g_plLam=0, g_plWorld=0; static bool g_plBodyDone=false; static int g_plPoll=0; static bool g_plLoadFired=false; static uintptr_t g_plBpCls=0;
// S99b: body-build timestamp (drives the screenshot + self-walk schedule), which screenshot pair has fired, and a
// one-shot log latch for the walk.
static DWORD g_plBodyTick=0; static int g_plShot=0; static bool g_plAwLogged=false; static bool g_plLostPawn=false;
static bool g_plCheatDone=false;
// Find a live instance whose class name contains `sub`, SKIPPING `except` — used to locate the cheat-spawned hero
// as distinct from the one we spawned ourselves.
static uintptr_t FindInstByClassExcept(const char* sub, uintptr_t except){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){
        if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;
        uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue;
        int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){
            uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue;
            uintptr_t o=*(uintptr_t*)item; if(!LooksLikePtr(o)||o==except)continue;
            uintptr_t cls=ClassOf(o); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,sub))continue;
            char on[96]; if(GetFNameStr(NameId(o),on,sizeof(on)) && strncmp(on,"Default__",9)==0) continue;   // skip CDOs
            return o;
        }
    }
    return 0;
}
#define PRIM_SCENEPROXY_OFF 0x2B0   // S95: UPrimitiveComponent::SceneProxy for this build (found by prim_diff.py)
static uint64_t ProxyOf(uintptr_t comp){ return (LooksLikePtr(comp)&&SafeReadable((void*)(comp+PRIM_SCENEPROXY_OFF),8))?*(uint64_t*)(comp+PRIM_SCENEPROXY_OFF):0; }
// Report the SceneProxy of every primitive component on `actor` — the one number that says whether it can render.
static void ProxyReport(uintptr_t actor,const char* tag){
    if(!LooksLikePtr(actor)){ Markerf("[PROXY] %s: actor null\r\n",tag); return; }
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK; int n=0,live=0;
    for(int ci=0;ci<numChunks;ci++){
        if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;
        uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue;
        int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){
            uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue;
            uintptr_t o=*(uintptr_t*)item; if(!LooksLikePtr(o))continue;
            if((SafeReadable((void*)(o+0x28),8)?*(uintptr_t*)(o+0x28):0)!=actor) continue;
            uintptr_t cls=ClassOf(o); if(!cls)continue; char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,"Mesh")&&!strstr(cn,"Decal")&&!strstr(cn,"Capsule")) continue;   // primitives only
            uint64_t px=ProxyOf(o); n++; if(px)live++;
            Markerf("[PROXY] %s  %-44s proxy=%s\r\n",tag,cn,px?"SET":"null");
        }
    }
    Markerf("[PROXY] %s: %d primitives, %d WITH a proxy %s\r\n",tag,n,live,live?"*** RENDERABLE ***":"(none renderable)");
}
static void* g_plPafsFn=nullptr; static uintptr_t g_plPafsThunk=0, g_plPafsChild=0;
static void* g_plAlpaFn=nullptr; static uintptr_t g_plAlpaThunk=0, g_plAlpaChild=0;
// S94 iter5 (route 1): blocking load of Ronin's ACTUAL mesh by soft path (SK_Ronin_Default_LOD1 in Modeling/Default,
// a HARD ref inside BP_Ronin_DefaultSKMeshComponent_C — the bundle load never pulled it). KismetSystemLibrary.
// MakeSoftObjectPath(FString) -> FSoftObjectPath, then LoadAsset_Blocking(TSoftObjectPtr) -> UObject* (synchronous,
// loads render data). No async poll needed.
static uintptr_t g_plKsl=0;
static void* g_plMspFn=nullptr; static uintptr_t g_plMspThunk=0, g_plMspChild=0; static uint32_t g_oMspPath=0xFFFFFFFF, g_oMspRet=0xFFFFFFFF;
static void* g_plLabFn=nullptr; static uintptr_t g_plLabThunk=0, g_plLabChild=0; static uint32_t g_oLabAsset=0xFFFFFFFF, g_oLabRet=0xFFFFFFFF;
#ifndef KMESHPATH
#define KMESHPATH L"/Game/Loki/Characters/Heroes/Ronin/Modeling/Default/SK_Ronin_Default_LOD1.SK_Ronin_Default_LOD1"
#endif
// S94 route 2: build the GAME'S OWN configured mesh-component BP (mesh+materials+registration wired the game way, which
// the bare SkeletalMeshComponent lacked -> no render). Load its class + AddComponentByClass(that class), DEFERRED so we
// can switch off its AnimBP (SingleNode) + cloth before it registers (those crashed the bare path).
#ifndef KUSEBPCOMP
#define KUSEBPCOMP 1         // 1 = route 2 (BP component); 0 = route 1 (bare SkeletalMeshComponent + SetSkeletalMeshAsset).
#endif
// ══════════════════════════════════════════════════════════════════════════════════════════════════
// ★★★★ S106d (2026-07-29) — **DEFAULT FLIPPED 1 -> 0.  READ THIS BEFORE TURNING IT BACK ON.**
//
// KTESTACTOR is a LEFTOVER S94 DIAGNOSTIC ("hero-hidden vs mesh discriminator") that has been ON by
// default ever since, and it builds a **SECOND SKELETAL-MESH BODY** on a standalone CameraActor beside
// the hero -- inside the SAME single post-build game-thread hook hit as everything else, in the
// +0.15 s window where FK-7's one-byte write lands.  It is a prime FK-7 antecedent, on three counts:
//
//   1. MEASURED: its actor is spawned by SpawnActorCls, which until S106d truncated the FTransform at
//      0x50 and dropped Scale3D.Z -- and its own scale write used the pre-S98 0x38/0x40/0x48 offsets.
//      So the test actor's ROOT scale was (1,1,**0**).
//   2. STRONG_INFERENCE: a component attached to a root whose scale is (1,1,0) has a NON-UNIFORM world
//      scale whatever its own relative scale is (and UE's GetSafeScaleReciprocal maps 0 -> 0, so
//      SetWorldScale3D(1,1,1) cannot recover Z through such a parent).  That is exactly the condition
//      `LogChaosCloth` reports.
//   3. MEASURED: there is exactly **ONE** LogChaosCloth non-uniform-scale line per crashing session
//      (1x in each of 4 crash logs, 0x in each of 5 non-crash logs) -- i.e. ONE non-uniform body.  The
//      hero's own body cannot be it: the hero is the GAME's pawn (root scale (1,1,1)) and BuildHeroBody
//      forces its component's RelativeScale3D to (1,1,1).  ⇒ the one body is this actor's.
//      ⚠ INFERRED, not proven: the shipping log line has an EMPTY object name, so it cannot name the
//      body itself.  The one-bit live test is `grep -c LogChaosCloth Loki.log` with KTESTACTOR=0.
//
// ⚠ RETRACTED antecedent, do not re-derive it: `LogPhysics "Scale3D is (nearly) zero"` appears in
//    **0 of 14** log files (the string exists at .rdata 0x0817DAF0 but is never emitted).  Only CLOTH
//    is ever reported.  The old "LogChaosCloth **/ LogPhysics Scale3D**" pairing was half false-known.
//
// This is a DIAGNOSTIC, not a fix: nothing in the playable-tutorial route needs it, and its question
// ("is the hero hidden, or is the mesh unable to draw?") was answered in S94/S95/S96.  Turning it off
// removes a whole extra skeletal body from the crash window at zero cost to the route.
// Build `-DKTESTACTOR=1` to restore it (variant `play-testactor`) -- that is the A/B partner.
#ifndef KTESTACTOR
#define KTESTACTOR 0         // S106d: WAS 1. Leftover S94 diagnostic; builds a 2nd, degenerate skeletal body.
#endif
#ifndef KFOWRADIUS
#define KFOWRADIUS 20000     // hero's FogOfWarRadius (vision source) — wide so the FOW mask reveals the area.
#endif
#ifndef KFOWKILL
#define KFOWKILL 1           // route B: 0=off, 1=untick+hide the FOW actors, 2=also K2_DestroyActor them.
#endif
#ifndef KFOWATTR
#define KFOWATTR 0           // route A (GAS vision attrs) — proven dead (hero has no attribute set); off = one less full object scan.
#endif
#ifndef KCHEATSPAWN
#define KCHEATSPAWN 1        // ★ S96: spawn through the GAME'S OWN path (LokiPlayerCheats). Our GameplayStatics deferred
                             // spawn yields actors whose components never get a SceneProxy (never render-registered);
                             // the game's own RPC should produce a properly registered, RENDERABLE actor.
                             // 1 = ServerCheatSpawnActor(hero class) beside the hero, 2 = also ServerCheatChangeHero.
#endif
#ifndef KSMACTOR
#define KSMACTOR 1           // spawn a real StaticMeshActor + set the mesh on its ENGINE-built root (spawn-vs-component test).
#endif
#ifndef KSTATICTEST
// ★★ S108b (2026-08-04) — DEFAULT FLIPPED 1 -> 0.  This is the S95 spawn-vs-component DISCRIMINATOR:
// build a plain StaticMeshComponent from a mesh borrowed off a level component that IS visibly
// rendering, so that "our copy doesn't draw" separates a broken component-creation path from a
// skeletal-only problem.  It answered that question long ago and is now pure cost.
//
// WHY IT MUST BE OFF BY DEFAULT (MEASURED, docs/s108b-ksmactor-bisect.md):
//   The block at :4960 calls BuildHeroBody(hero, StaticMeshComponent, ...) at :4970, and
//   BuildHeroBody unconditionally drives PlayAnimation -- on a component that has no animation.
//   That faults 0xC0000005 every run.  The fault is SEH-caught, so it does not kill the process; what
//   it does is worse and quieter:
//       [ANIM] PlayAnimation(...) FAULTED -> anim swapping DISABLED for the rest of the session
//   ⇒ THE HERO'S WALK/RUN ANIMATION WAS DEAD FOR THE WHOLE SESSION, every session, because of a
//     leftover diagnostic.  With KSTATICTEST=0 the marker instead cycles
//     `PlayAnimation(run, loop) ok` / `PlayAnimation(idle, loop) ok` and locomotion animates
//     (MEASURED in both bisect arms; confirmed visually by the user).
//   The faulting object names itself in the register dump: `[NULL] cls RBX=StaticMeshComponent`.
//   KSMACTOR is EXONERATED -- the nostatictest arm ran its [SMA] block to completion with 0 faults.
//
// Same precedent, same reason as KTESTACTOR (S106, :4020): an S9x diagnostic left switched on that
// quietly damaged every later run.  Rebuild with -DKSTATICTEST=1 (variant `play-statictest`) to get
// the discriminator back.
#define KSTATICTEST 0
#endif
#ifndef KTESTDX
#define KTESTDX 500          // X offset of that test actor from the hero.
#endif
#ifndef KBPCOMPPATH
#define KBPCOMPPATH L"/Game/Loki/Characters/Heroes/Ronin/Cosmetics/Default/BP_Ronin_DefaultSKMeshComponent.BP_Ronin_DefaultSKMeshComponent_C"
#endif
static void* g_plFacFn=nullptr; static uintptr_t g_plFacThunk=0, g_plFacChild=0; static uint32_t g_oFacComp=0xFFFFFFFF, g_oFacManual=0xFFFFFFFF, g_oFacXform=0xFFFFFFFF;
// ★★★ S94 iter11 — THE FOG-OF-WAR REGISTRATION. SUPERVIVE renders character primitives through its LokiFogOfWar
// system (plugin /Script/FogOfWar): a primitive that was never registered is culled from the FOW scene view, so it
// NEVER draws — which is exactly what we saw (ground-decal ring + world render; hero AND standalone bodies do not,
// with a healthy 8-material mesh at the right place, visible, registered). Signatures via ufunc_params.py (both
// Native|Static|BlueprintCallable on LokiFogOfWarStatics; call with its CDO as context):
//   Bool RegisterFogOfWarPrimitive(PrimitiveComponent Component@0x0) -> Bool@0x8
//   Bool IsFogOfWarVisibleToLocal(Actor Target@0x0)                  -> Bool@0x8
static uintptr_t g_plFowCDO=0;
static void* g_plFowRegFn=nullptr; static uintptr_t g_plFowRegThunk=0, g_plFowRegChild=0; static uint32_t g_oFowComp=0xFFFFFFFF, g_oFowRet=0xFFFFFFFF;
static void* g_plFowVisFn=nullptr; static uintptr_t g_plFowVisThunk=0, g_plFowVisChild=0; static uint32_t g_oFowTgt=0xFFFFFFFF, g_oFowVisRet=0xFFFFFFFF;
// Resolve a UFunction by GLOBAL name (the FOW statics do NOT live on LokiFogOfWarStatics — a class-scoped lookup
// returns thunk=0). Finds the UFunction object, takes its thunk (Func@+0xE0) + params (ChildProperties@+0x58), and
// derives a call context from its OWNING class's CDO (Outer@+0x28 -> "Default__<ClassName>").
static bool ResolveFuncGlobal(const char* name, void** fn, uintptr_t* thunk, uintptr_t* child, uintptr_t* ctxCDO){
    *fn=nullptr; *thunk=0; *child=0;
    uintptr_t f=FindObjExact(name); if(!LooksLikePtr(f)) return false;
    char kcn[64]="?"; if(ClassOf(f)) GetFNameStr(NameId(ClassOf(f)),kcn,sizeof(kcn));
    if(!strstr(kcn,"Function")){ Markerf("[FOW] '%s' found but class=%s (not a Function)\r\n",name,kcn); return false; }
    *fn=(void*)f;
    *thunk = SafeReadable((void*)(f+0xE0),8)?*(uintptr_t*)(f+0xE0):0;
    *child = SafeReadable((void*)(f+0x58),8)?*(uintptr_t*)(f+0x58):0;
    uintptr_t owner = SafeReadable((void*)(f+0x28),8)?*(uintptr_t*)(f+0x28):0;   // Outer = the owning UClass
    char on[96]="?"; if(LooksLikePtr(owner)) GetFNameStr(NameId(owner),on,sizeof(on));
    if(ctxCDO && LooksLikePtr(owner)){ char dn[128]; _snprintf_s(dn,sizeof(dn),_TRUNCATE,"Default__%s",on); uintptr_t c=FindObjExact(dn); if(LooksLikePtr(c)) *ctxCDO=c; }
    Markerf("[FOW] resolved '%s' fn=0x%llX thunk=0x%llX owner=%s cdo=0x%llX\r\n",name,(unsigned long long)f,(unsigned long long)*thunk,on,(unsigned long long)(ctxCDO?*ctxCDO:0));
    return *thunk!=0;
}
// Call a param-free UFunction on obj, auto-picking the NATIVE (Script.Num==0 -> direct thunk) vs BLUEPRINT
// (FFrame.Code = Script.Data) primitive — using the wrong one FAULTS.
static void CallNoArgAuto(uintptr_t obj,const char* fname,const char* tag){
    if(!LooksLikePtr(obj)) return;
    void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(obj),fname,&f,&th,&ch);
    if(!th){ Markerf("[FOW] %s: %s NOT FOUND\r\n",tag,fname); return; }
    uint32_t sn = SafeReadable((void*)((uintptr_t)f+0x70),4) ? *(uint32_t*)((uintptr_t)f+0x70) : 0;   // UStruct Script.Num
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    bool flt = (sn==0) ? CallNativeGuarded(f,th,ch,(void*)obj,g_pbuf,g_rbuf)
                       : CallBPGuarded((uintptr_t)f,(void*)obj,g_rbuf);
    Markerf("[FOW] %s: %s (%s) %s\r\n",tag,fname,(sn==0)?"native":"BP",flt?"FAULTED":"ok");
}
// ★ ROUTE B/A HYBRID — make the hero its own FOG-OF-WAR VISION SOURCE. IsFogOfWarVisibleToLocal(hero)==FALSE is the
// render gate; force-open has no team/vision so the FOW mask stays dark and character primitives are culled. The
// replicated FogOfWarRadius/FogOfWarAngle properties (with OnRep_ handlers) ARE the vision source — set them wide and
// fire the OnReps so the FOW system reveals around the hero.
// FogOfWarRadius/Angle are NOT plain floats on the hero — usmap schema.txt shows they are **GAS attributes on
// LokiAttributeSet** (UClass:AttributeSet, 125 props), i.e. FGameplayAttributeData { vtable@0x0, float BaseValue@0x8,
// float CurrentValue@0xC }. Find the attribute set owned by the hero (GAS parents it to the owner actor / its ASC).
static uintptr_t g_plAttrSet=0;
static uintptr_t FindAttrSetFor(uintptr_t hero){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return 0;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return 0;
    int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){
        if(!SafeReadable((void*)(objectsPtr+ci*8),8))break;
        uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue;
        int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){
            uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue;
            uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue;
            uintptr_t cls=ClassOf(obj); if(!cls)continue;
            char cn[96]; if(!GetFNameStr(NameId(cls),cn,sizeof(cn)))continue;
            if(!strstr(cn,"AttributeSet"))continue;
            uintptr_t o=SafeReadable((void*)(obj+0x28),8)?*(uintptr_t*)(obj+0x28):0; int d=0;   // Outer chain -> hero?
            while(LooksLikePtr(o)&&d<3){ if(o==hero) return obj; o=SafeReadable((void*)(o+0x28),8)?*(uintptr_t*)(o+0x28):0; d++; }
        }
    }
    return 0;
}
static void FowPokeAttr(uintptr_t as,const char* name,float v){
    uint32_t off=PropOffsetSuper(ClassOf(as),name);
    if(off==0xFFFFFFFF||!SafeReadable((void*)(as+off),0x10)){ Markerf("[FOW] attr %s NOT FOUND (off=0x%X)\r\n",name,off); return; }
    float ob=*(float*)(as+off+0x8), oc=*(float*)(as+off+0xC);   // FGameplayAttributeData Base@0x8 Current@0xC
    *(float*)(as+off+0x8)=v; *(float*)(as+off+0xC)=v;
    Markerf("[FOW] attr %s@0x%X base %.1f->%.0f cur %.1f->%.0f\r\n",name,off,ob,v,oc,v);
}
// ★ ROUTE B — DISABLE FOG OF WAR. The FOW mask is rendered by the live `FogOfWarSceneView` actor (one instance in
// the tutorial's PersistentLevel) and primitives are gathered by `FogOfWarPrimitiveCollector`. With no vision source
// the mask stays dark and every character primitive is culled. Neutralise the renderer: stop its tick, hide it, and
// (KFOWKILL=2) destroy it outright — if the FOW pass stops masking, characters should draw unmasked.
static void FowDisable(){
    const char* names[2]={"FogOfWarSceneView","FogOfWarPrimitiveCollector"};
    for(int i=0;i<2;i++){
        uintptr_t a=FindInstByClass(names[i],nullptr);
        if(!LooksLikePtr(a)){ Markerf("[FOW] disable: %s instance NOT FOUND\r\n",names[i]); continue; }
        Markerf("[FOW] disable: %s inst=0x%llX\r\n",names[i],(unsigned long long)a);
        { void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(a),"SetActorTickEnabled",&f,&th,&ch);
          if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); uint32_t o=ParamOffset(ch,"bEnabled"); if(o!=0xFFFFFFFF)((uint8_t*)g_pbuf)[o]=0; memset(g_rbuf,0,sizeof(g_rbuf));
            bool fl=CallNativeGuarded(f,th,ch,(void*)a,g_pbuf,g_rbuf); Markerf("[FOW]   SetActorTickEnabled(false)%s\r\n",fl?" FAULTED":""); } }
        { void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(a),"SetActorHiddenInGame",&f,&th,&ch);
          if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); uint32_t o=ParamOffset(ch,"bNewHidden"); if(o!=0xFFFFFFFF)((uint8_t*)g_pbuf)[o]=1; memset(g_rbuf,0,sizeof(g_rbuf));
            bool fl=CallNativeGuarded(f,th,ch,(void*)a,g_pbuf,g_rbuf); Markerf("[FOW]   SetActorHiddenInGame(true)%s\r\n",fl?" FAULTED":""); } }
        if(KFOWKILL>=2){ void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(a),"K2_DestroyActor",&f,&th,&ch);
          if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            bool fl=CallNativeGuarded(f,th,ch,(void*)a,g_pbuf,g_rbuf); Markerf("[FOW]   K2_DestroyActor%s\r\n",fl?" FAULTED":""); } }
    }
}
static void FowMakeVisionSource(uintptr_t hero){
    if(!LooksLikePtr(g_plAttrSet)){
        g_plAttrSet=FindAttrSetFor(hero);
        char cn[96]="-"; if(LooksLikePtr(g_plAttrSet)&&ClassOf(g_plAttrSet)) GetFNameStr(NameId(ClassOf(g_plAttrSet)),cn,sizeof(cn));
        Markerf("[FOW] hero attributeSet=0x%llX (%s)\r\n",(unsigned long long)g_plAttrSet,cn);
    }
    if(!LooksLikePtr(g_plAttrSet)) return;
    FowPokeAttr(g_plAttrSet,"FogOfWarRadius",(float)KFOWRADIUS);
    FowPokeAttr(g_plAttrSet,"FogOfWarAngle",360.0f);
}
static void FowRegister(uintptr_t comp,const char* tag){
    if(!g_plFowRegThunk||!LooksLikePtr(g_plFowCDO)||!LooksLikePtr(comp)){
        Markerf("[FOW] %s register SKIPPED (thunk=0x%llX cdo=0x%llX comp=0x%llX)\r\n",tag,(unsigned long long)g_plFowRegThunk,(unsigned long long)g_plFowCDO,(unsigned long long)comp); return; }
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(g_oFowComp!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oFowComp)=(uint64_t)comp;
    bool f=CallNativeGuarded(g_plFowRegFn,g_plFowRegThunk,g_plFowRegChild,(void*)g_plFowCDO,g_gsbuf,g_rbuf);
    uint8_t r=(g_oFowRet!=0xFFFFFFFF)?g_gsbuf[g_oFowRet]:((uint8_t*)g_rbuf)[0];
    Markerf("[FOW] RegisterFogOfWarPrimitive(%s) %s -> ret=%d\r\n",tag,f?"FAULTED":"ok",(int)r);
}
#ifndef KLOADRONIN
#define KLOADRONIN 1         // 1 = async-load Ronin's real mesh; 0 = only use a resident placeholder (won't render).
#endif
#ifndef KLOADWAITMS
#define KLOADWAITMS 15000    // how long to poll for the streamed mesh before falling back to a resident placeholder.
#endif
#ifndef KFIREBUNDLE
#define KFIREBUNDLE 0        // also fire the async cosmetics-bundle load (redundant with the blocking mesh load; off = stabler render).
#endif
#ifndef KGROUNDX
#define KGROUNDX (-65.0)     // S75 CapturePoint (-65,-1770,353) is confirmed-solid tutorial ground
#endif
#ifndef KGROUNDY
#define KGROUNDY (-1770.0)
#endif
#ifndef KGROUNDZ
#define KGROUNDZ (393.0)     // +40 above the surface so gravity settles the hero onto it
#endif
#ifndef KNOMESH
#define KNOMESH 0            // -DKNOMESH=1 -> skip the body build (isolate camera+movement)
#endif
#ifndef KNOMOVE
#define KNOMOVE 0            // -DKNOMOVE=1 -> skip the WASD puppet (isolate the visible standing body)
#endif
#ifndef KNOTELE
#define KNOTELE 0            // -DKNOTELE=1 -> skip the ground teleport (keep the hero where [SP] left it)
#endif
#ifndef KBODYZ
#define KBODYZ 0.0           // RelativeLocation Z of the body component (tune ~-88 to drop feet to the capsule base)
#endif
#ifndef KPLAYANIM
#define KPLAYANIM 1          // play a looping AnimSequence on the body (SingleNode). Fixes T-pose + sword-through-torso.
#endif
#ifndef KANIMNAME
#define KANIMNAME "A_Ronin_Cosmetic_HeroSelect_Breathe"
#endif
#ifndef KANIMPATH
// Ronin's hero-select idle/breathe loop — a self-contained standing idle that needs no gameplay state.
#define KANIMPATH L"/Game/Loki/Characters/Heroes/Ronin/Animation/Cosmetics/A_Ronin_Cosmetic_HeroSelect_Breathe.A_Ronin_Cosmetic_HeroSelect_Breathe"
#endif
#ifndef KMESHTICK
#define KMESHTICK 1          // tick the body component ON (needed to update pose/render state); with SingleNode anim it's crash-safe. 0 = tick off.
#endif
// ★★★ S99b — RUN ANIMATION. Real locomotion blending lives in the AnimBP, and the AnimBP collapses the pose to
// nothing in force-open (S99, user-confirmed: body VANISHES). So swap whole AnimSequences off the CMC's velocity
// instead: |V| over KRUNSPEED -> the run loop, at rest -> the idle loop. Crude vs a BlendSpace, but it animates
// movement without ever instantiating ABP_LokiHero_GenericRoot_EventDriven_C.
// ★★★★ S101 — drive LokiPlayerState's own ability-system wiring chain (ServerSetHeroClass -> OnRep_HeroClass ->
// TryUpdateAbilitySystem) and report LokiCharacter::IsAbilitySystemInitialized before/after. See WireAbilitySystem.
#ifndef KGASCARRIER
#define KGASCARRIER 1        // S103: spawn LokiPlayerState_HeroAffiliated + ASC + attribute sets, then install it on the PlayerState
#endif
#ifndef KGASROLE
#define KGASROLE 1           // S101 iter2: if the PlayerState is not ROLE_Authority, force it and retry the keystone
#endif
#ifndef KWIREGAS
#define KWIREGAS 1
#endif
#ifndef KRUNANIM
#define KRUNANIM 1
#endif
#ifndef KRUNANIMNAME
#define KRUNANIMNAME "A_Ronin_Movement_OutOfCombat_N"
#endif
#ifndef KRUNANIMPATH
#define KRUNANIMPATH L"/Game/Loki/Characters/Heroes/Ronin/Animation/Movement/A_Ronin_Movement_OutOfCombat_N.A_Ronin_Movement_OutOfCombat_N"
#endif
#ifndef KRUNSPEED
#define KRUNSPEED 40.0       // |CMC velocity XY| above this = moving -> run loop; below = idle loop.
#endif
// ★★★ S99b — SELF-SCREENSHOT. S99's animation fix went UNVERIFIED because the session died before anyone could
// look at the screen, and this route has no way to grab the desktop. Fix: make the GAME write its own screenshot
// via its console (the same ExecuteConsoleCommand primitive that force-opens the map), so every run leaves a
// verifiable PNG in Saved/Screenshots/WindowsClient/ with no human at the machine.
#ifndef KSHOT
#define KSHOT 1
#endif
#ifndef KSHOTMS
// Deliberately SHORT. These sessions die unpredictably (S99b lost one ~1s after the body was built), so the
// picture has to be taken almost immediately rather than after a comfortable settling delay.
#define KSHOTMS 3000         // ms after the body is built -> screenshot #1 (the IDLE pose)
#endif
// The shim cannot press W, so it drives the velocity itself for a window to exercise the run animation and
// capture it. 0 disables (leaves movement entirely to the player).
#ifndef KAUTOWALKATMS
#define KAUTOWALKATMS 20000  // ms after body build when the self-driven walk starts (AFTER the three idle shots)
#endif
#ifndef KAUTOWALKMS
#define KAUTOWALKMS 5000     // how long the self-driven walk lasts
#endif
#ifndef KANIMMODE
#define KANIMMODE 1          // SetAnimationMode: 1=AnimationSingleNode (ref pose, NO hero AnimBP -> no S93 crash), 0=AnimBlueprint (crashes), -1=don't set.
#endif
#ifndef KFLYMODE
#define KFLYMODE 5           // MOVE_Flying(5): bypasses the Walking-mode ground-mantle chain that spams "FudgeMantling
                             // toggles not ready" + crashed movement on cell-streaming (S75/S81). Hero hovers at the
                             // teleport Z; velocity XY still drives it. -DKFLYMODE=1 = Walking (mantle spam), 0 = leave as-is.
#endif
// Build a visible body on `hero` from scratch: AddComponentByClass(SkeletalMeshComponent, auto-attach) +
// SetSkeletalMeshAsset(mesh); tick+anim OFF (static ref pose), visibility ON. Returns the component (0 on fail).
// AddComponentByClass + SetSkeletalMeshAsset are NATIVE -> CallNativeGuarded (the BP-call primitive FAULTS on them).
static uintptr_t LoadMeshByPath(const wchar_t* path);   // fwd (defined below) — BuildHeroBody uses it for the anim asset

// ★ S99b — the two per-hit primitives the animation work needs, each resolved ONCE and cached. Everything in
// DoPlay's per-hit path runs on the game thread inside the PI hook, so a full re-resolve per frame (which does
// 188k-object scans) is not affordable; these keep the hot path to a single native call.
static uintptr_t g_plIdleAnim=0, g_plRunAnim=0, g_plCurAnim=0;   // the two AnimSequences + which one is playing
static void*     g_plPaFn=nullptr; static uintptr_t g_plPaThunk=0, g_plPaChild=0; static bool g_plPaRes=false;
static uint32_t  g_oPaAnim=0, g_oPaLoop=8;
static bool      g_plAnimDead=false;      // latched after the first PlayAnimation fault — see PlayAnimOn
static DWORD     g_plLastSwap=0;          // rate limiter for the idle<->run swap
// PlayAnimation(anim, bLooping=true) — sets SingleNode mode, assigns the asset and plays, in one native call.
static bool PlayAnimOn(uintptr_t comp, uintptr_t anim, const char* tag){
    if(!LooksLikePtr(comp)||!LooksLikePtr(anim)) return false;
    if(!g_plPaRes){ g_plPaRes=true;
        ResolveFuncSuper(ClassOf(comp),"PlayAnimation",&g_plPaFn,&g_plPaThunk,&g_plPaChild);
        if(g_plPaChild){ uint32_t a=ParamOffset(g_plPaChild,"NewAnimToPlay"); if(a!=0xFFFFFFFF) g_oPaAnim=a;
                         uint32_t l=ParamOffset(g_plPaChild,"bLooping");      if(l!=0xFFFFFFFF) g_oPaLoop=l; }
        if(!g_plPaThunk) Marker("[ANIM] PlayAnimation thunk not found\r\n"); }
    if(!g_plPaThunk || g_plAnimDead) return false;
    // ★ S106 (FK-7) — refuse to drive a destructed component/asset. MEASURED signature of the S99b
    // "PlayAnimation(idle) FAULTED, RIP=0x0 access=EXEC addr=0x0, RDI=AnimSingleNodeInstance" event and of
    // the five worker-thread crashes: NamePrivate cleared to 0 + vtable replaced by an allocator free-list
    // link. Latch off rather than call a virtual through a dead object.
    if(!GcAlive(comp) || !GcAlive(anim)){
        g_plAnimDead=true;
        Markerf("[GCW] %s: DEAD UObject before PlayAnimation (comp=0x%llX alive=%d anim=0x%llX alive=%d)"
                " -> anim swapping DISABLED. The asset was garbage-collected: check the [GC] lines above.\r\n",
                tag,(unsigned long long)comp,(int)GcAlive(comp),(unsigned long long)anim,(int)GcAlive(anim));
        return false; }
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_gsbuf+g_oPaAnim)=(uint64_t)anim; g_gsbuf[g_oPaLoop]=1;
    bool f=CallNativeGuarded(g_plPaFn,g_plPaThunk,g_plPaChild,(void*)comp,g_gsbuf,g_rbuf);
    // ★ S99b — ALWAYS record the request, success or not, and LATCH OFF on the first fault.
    // Without this the swap retries the same failing call every single frame: S99b watched PlayAnimation(idle)
    // fault four times in a row with `RIP=0x0 access=EXEC addr=0x0` (a call through a null function pointer,
    // RDI=AnimSingleNodeInstance) until one escaped the SEH guard and killed the process. Re-driving the
    // single-node instance from inside the PI hook is not safe once the component is being torn down or is
    // mid parallel-evaluation, so one fault = stop swapping for good and keep whatever pose is on the skeleton.
    g_plCurAnim=anim;
    if(f){ g_plAnimDead=true;
        Markerf("[ANIM] PlayAnimation(%s, loop) FAULTED -> anim swapping DISABLED for the rest of the session\r\n",tag); }
    else Markerf("[ANIM] PlayAnimation(%s, loop) ok\r\n",tag);
    return !f;
}
// ================= S110 — GIVE THE ASSET A REAL REFERENCE (the actual fix for the run anim) ======
// WHY THIS EXISTS, and why it is NOT another rooting attempt. docs/s110-item-watch-gc-mechanism.md:
// the poked RootSet bit is MEASURED INERT in this build. Phase-locked experiment, only the injection
// phase varied, three armed windows: the bit was set and readback-verified 0.15 s / 2.9 s / **33.1 s**
// before the next GC pass, and the asset was destroyed at that pass every time -- in the last run it
// sat through six clean 5 s heartbeats and then died 708 ms after the reachability flip. The engine
// zeroes bit 30 with the rest of the flag word on free. Poking harder cannot work.
//
// What DOES keep an object alive here is being REACHED by the traversal. Same run, same pass, six
// objects all carrying bit 30: the four the traversal reached were re-marked and survived; the two it
// did not (the run anim and an orphaned AnimSingleNodeInstance) were destroyed within 3 s. The run
// anim is referenced by nothing but g_plRunAnim -- a plain C global in this DLL, which UE cannot see.
//
// So put it somewhere UE CAN see: USkeletalMeshComponent::AnimationData.AnimToPlay, an object-typed
// UPROPERTY on the component. Three reasons that slot and not another:
//   * the component is REACHABLE and measured to survive every pass (it is owned by the hero actor);
//   * the component is OURS -- the shim created it via AddComponentByClass -- so nothing else reads it;
//   * AnimationData is unused by us: the swap drives PlayAnimation() explicitly, which writes the
//     single-node instance's CurrentAsset, never this. It is a free object slot on a live object.
// PlayAnimation's own CurrentAsset is why the IDLE anim already survives and the run anim does not:
// it holds exactly one asset, and the run anim is not it until the walk starts ~20 s too late.
//
// Both offsets are resolved BY NAME and the write is verified by readback. Nothing here assumes a
// layout: if either lookup fails, or the slot does not already look like an empty/valid object
// pointer, it REFUSES and says so rather than writing 8 bytes over playback state.
#ifndef KANIMREF
#define KANIMREF 1           // -DKANIMREF=0 -> A/B control: no reference held, reproduces the collection
#endif
static void AnimRefHold(uintptr_t comp, uintptr_t anim, const char* tag){
#if !KANIMREF
    (void)comp; (void)anim; Markerf("[REF] %s: KANIMREF=0, not referencing (control arm)\r\n",tag);
#else
    if(!LooksLikePtr(comp)||!LooksLikePtr(anim)){ Markerf("[REF] %s: bad comp/anim -> skipped\r\n",tag); return; }
    uint32_t so=PropOffsetSuper(ClassOf(comp),"AnimationData");
    if(so==0xFFFFFFFF){ Markerf("[REF] %s: no AnimationData property on the component -> NOT referenced\r\n",tag); return; }
    // AnimToPlay's offset INSIDE FSingleAnimationPlayData, resolved from the UScriptStruct itself
    // (a UScriptStruct is a UStruct, so the same ChildProperties walk works). Never assume "first member".
    static uint32_t io=0xFFFFFFFF; static bool ioTried=false;
    if(!ioTried){ ioTried=true;
        uintptr_t ss=FindObjExact("SingleAnimationPlayData");
        if(ss) io=PropOffsetSuper(ss,"AnimToPlay");
        Markerf("[REF] SingleAnimationPlayData=0x%llX AnimToPlay@0x%X\r\n",(unsigned long long)ss,io); }
    if(io==0xFFFFFFFF){ Markerf("[REF] %s: AnimToPlay offset unresolved -> NOT referenced\r\n",tag); return; }
    uintptr_t slot=comp+so+io;
    if(!SafeWritable((void*)slot,8)){ Markerf("[REF] %s: slot 0x%llX not writable -> NOT referenced\r\n",tag,(unsigned long long)slot); return; }
    uintptr_t before=*(uintptr_t*)slot;
    if(before!=0 && !LooksLikePtr(before)){
        Markerf("[REF] %s: slot holds 0x%llX (not null, not a pointer) -> REFUSING to write\r\n",tag,(unsigned long long)before); return; }
    *(uintptr_t*)slot=anim;
    uintptr_t after=*(uintptr_t*)slot;
    Markerf("[REF] %s: AnimationData.AnimToPlay @comp+0x%X (struct 0x%X + 0x%X) %llX -> %llX %s\r\n",
            tag,so+io,so,io,(unsigned long long)before,(unsigned long long)after,after==anim?"OK":"FAILED");
#endif
}
// ================= end S110 reference hold =====================================================
// Run a console command on the game thread (KismetSystemLibrary::ExecuteConsoleCommand — the same primitive that
// force-opens the map). Used for the self-screenshot; the WorldContextObject is the live PlayerController.
static void*     g_plCcFn=nullptr; static uintptr_t g_plCcThunk=0, g_plCcChild=0, g_plCcCDO=0; static bool g_plCcRes=false;
static uint32_t  g_oCcWCO=0xFFFFFFFF, g_oCcCmd=0xFFFFFFFF, g_oCcSP=0xFFFFFFFF;
static void RunConsole(const wchar_t* cmd, const char* tag){
    if(!g_plCcRes){ g_plCcRes=true;
        ResolveFuncGlobal("ExecuteConsoleCommand",&g_plCcFn,&g_plCcThunk,&g_plCcChild,&g_plCcCDO);
        if(g_plCcChild){ g_oCcWCO=ParamOffset(g_plCcChild,"WorldContextObject");
                         g_oCcCmd=ParamOffset(g_plCcChild,"Command");
                         g_oCcSP =ParamOffset(g_plCcChild,"SpecificPlayer"); } }
    if(!g_plCcThunk||!LooksLikePtr(g_plCcCDO)||g_oCcCmd==0xFFFFFFFF){
        Markerf("[SHOT] %s: ExecuteConsoleCommand unresolved (thunk=0x%llX cdo=0x%llX cmd@0x%X)\r\n",
                tag,(unsigned long long)g_plCcThunk,(unsigned long long)g_plCcCDO,g_oCcCmd); return; }
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(g_oCcWCO!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oCcWCO)=(uint64_t)(g_wmPC?g_wmPC:g_worldCtx);
    SetFStringAt((uint8_t*)g_gsbuf,g_oCcCmd,cmd);   // the literal is static storage, so the FString view stays valid
    if(g_oCcSP!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oCcSP)=0;
    bool f=CallNativeGuarded(g_plCcFn,g_plCcThunk,g_plCcChild,(void*)g_plCcCDO,g_gsbuf,g_rbuf);
    Markerf("[SHOT] %s: console '%ls' %s\r\n",tag,cmd,f?"FAULTED":"ok");
}

// ★★★★ S101 — DRIVE THE GAME'S OWN ABILITY-SYSTEM WIRING CHAIN.
//
// S100 measured that the force-open hero has NO ability system: AbilitySystemComponentStorage /
// AttributeSetStorage / AttributeSetHealthStorage are all NULL, and no LokiPlayerState_HeroAffiliated carrier
// exists. S100b then found we do NOT have to build any of that by hand — `LokiPlayerState` owns the lifecycle and
// exposes it natively:
//     void TryUpdateAbilitySystem()            [Native, PARAMETERLESS]
//     void ServerSetHeroClass(Class NewClass)  [Native, BPCallable]
//     void OnRep_HeroClass()                   [Native, Event, parameterless]
// and `LokiCharacter::IsAbilitySystemInitialized() -> Bool` reports success in one bit.
//
// Staged one call per step with a read of the witness bit before and after, so a fault or a no-op localises to a
// single call instead of "the chain didn't work".
static bool ReadAbilityInitBit(uintptr_t hero, const char* when){
    void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(hero),"IsAbilitySystemInitialized",&f,&th,&ch);
    if(!th){ Markerf("[GAS] %s: IsAbilitySystemInitialized NOT FOUND\r\n",when); return false; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    uint32_t ro=ParamOffset(ch,"ReturnValue");
    bool flt=CallNativeGuarded(f,th,ch,(void*)hero,g_pbuf,g_rbuf);
    // A native bool return can land either in the params frame at ReturnValue or in the result buffer; read both.
    int viaParm = (ro!=0xFFFFFFFF) ? ((uint8_t*)g_pbuf)[ro] : -1;
    int viaRes  = ((uint8_t*)g_rbuf)[0];
    Markerf("[GAS] %s IsAbilitySystemInitialized -> parm@0x%X=%d res=%d%s\r\n",when,ro,viaParm,viaRes,flt?" FAULTED":"");
    return (viaParm==1)||(viaRes==1);
}
static void ReportGasState(uintptr_t hero, const char* when){
    static const char* kFields[3]={"AbilitySystemComponentStorage","AttributeSetStorage","AttributeSetHealthStorage"};
    for(int i=0;i<3;i++){
        uint32_t o=PropOffsetSuper(ClassOf(hero),kFields[i]);
        uintptr_t v=(o!=0xFFFFFFFF&&SafeReadable((void*)(hero+o),8))?*(uintptr_t*)(hero+o):0;
        char cn[96]="-"; if(LooksLikePtr(v)&&ClassOf(v)) GetFNameStr(NameId(ClassOf(v)),cn,sizeof(cn));
        Markerf("[GAS] %s %-30s @0x%X = 0x%llX (%s)\r\n",when,kFields[i],o,(unsigned long long)v,LooksLikePtr(v)?cn:"NULL");
    }
}
// Generic AddComponentByClass(actor, cls) -> component. Non-deferred, identity transform.
static uintptr_t AddCompByClass(uintptr_t actor, uintptr_t cls, const char* tag){
    void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(actor),"AddComponentByClass",&f,&th,&ch);
    if(!th){ Markerf("[GAS] %s: AddComponentByClass NOT FOUND\r\n",tag); return 0; }
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    uint32_t retOff=0xFFFFFFFF;
    for(uintptr_t p=ch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
        char pn[64]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
        uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
        if(o==0xFFFFFFFF||o+0x50>sizeof(g_gsbuf)) continue;
        uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0;
        if(strcmp(pn,"Class")==0) *(uint64_t*)(g_gsbuf+o)=(uint64_t)cls;
        else if(strcmp(pn,"RelativeTransform")==0){ double* T=(double*)(g_gsbuf+o); T[3]=1.0; T[8]=1.0; T[9]=1.0; T[10]=1.0; }  // Scale3D@0x40/48/50 (S98)
        else if(strcmp(pn,"bDeferredFinish")==0) *(uint8_t*)(g_gsbuf+o)=0;
        else if(fl&0x400) retOff=o;
    }
    bool flt=CallNativeGuarded(f,th,ch,(void*)actor,g_gsbuf,g_rbuf);
    uintptr_t comp=(uintptr_t)g_rbuf[0];
    if(!LooksLikePtr(comp)&&retOff!=0xFFFFFFFF) comp=*(uint64_t*)(g_gsbuf+retOff);
    char cn[96]="-"; if(LooksLikePtr(comp)&&ClassOf(comp)) GetFNameStr(NameId(ClassOf(comp)),cn,sizeof(cn));
    Markerf("[GAS] %s AddComponentByClass %s -> 0x%llX (%s)\r\n",tag,flt?"FAULTED":"ok",(unsigned long long)comp,LooksLikePtr(comp)?cn:"NULL");
    return comp;
}
// ★★★★ S103 — BUILD THE MISSING CARRIER.
// S102b decoded the gate completely: IAbilitySystemInterface::GetAbilitySystemComponent() reads
// PlayerState->HeroAffiliatedObject (+0x4F8) and returns carrier->AbilitySystemComponent (+0x3E8);
// HeroAffiliatedObject is NULL in force-open, so TryUpdateAbilitySystem bails ~8 instructions in.
// TryUpdate is update-not-create, so nothing on the PlayerState will ever bootstrap GAS — the carrier has to
// exist first. This builds it with primitives already proven on this route:
//   spawn LokiPlayerState_HeroAffiliated -> AddComponentByClass(LokiAbilitySystemComponent)
//   -> K2_InitStats(<AttributeSet class>, null) x2  (UAttributeSet is a UObject, NOT a component, so it cannot be
//      added with AddComponentByClass; InitStats is the game's own "create + register the attribute subobject" API)
//   -> write PlayerState.HeroAffiliatedObject (a REFLECTED ObjectProperty, so a direct write is legitimate)
static uintptr_t EnsureHeroAffiliatedCarrier(uintptr_t ps){
    uint32_t hoOff=PropOffsetSuper(ClassOf(ps),"HeroAffiliatedObject");
    uintptr_t cur=(hoOff!=0xFFFFFFFF&&SafeReadable((void*)(ps+hoOff),8))?*(uintptr_t*)(ps+hoOff):0;
    Markerf("[GAS] HeroAffiliatedObject@0x%X = 0x%llX\r\n",hoOff,(unsigned long long)cur);
    if(LooksLikePtr(cur)) return cur;
    if(hoOff==0xFFFFFFFF){ Marker("[GAS] HeroAffiliatedObject property NOT FOUND -> abort carrier build\r\n"); return 0; }

    uintptr_t cls=FindClassExact("LokiPlayerState_HeroAffiliated");
    Markerf("[GAS] carrier class = 0x%llX\r\n",(unsigned long long)cls);
    if(!LooksLikePtr(cls)) return 0;
    // identity transform with Scale3D=1 at 0x40/0x48/0x50 (S98 offset fact)
    memset(g_xform,0,sizeof(g_xform));
    *(double*)(g_xform+0x18)=1.0;                                   // quat W
    *(double*)(g_xform+0x40)=1.0; *(double*)(g_xform+0x48)=1.0; *(double*)(g_xform+0x50)=1.0;
    uintptr_t carrier=SpawnActorCls(cls,"LokiPlayerState_HeroAffiliated");
    if(!LooksLikePtr(carrier)){ Marker("[GAS] carrier spawn FAILED\r\n"); return 0; }

    // Did the carrier's own constructor create the ASC (the way the level actors' do)?
    uint32_t ascOff=PropOffsetSuper(ClassOf(carrier),"AbilitySystemComponent");
    uintptr_t asc=(ascOff!=0xFFFFFFFF&&SafeReadable((void*)(carrier+ascOff),8))?*(uintptr_t*)(carrier+ascOff):0;
    Markerf("[GAS] carrier=0x%llX AbilitySystemComponent@0x%X = 0x%llX (%s)\r\n",
            (unsigned long long)carrier,ascOff,(unsigned long long)asc,LooksLikePtr(asc)?"constructor built it":"NULL -> we add one");
    if(!LooksLikePtr(asc)){
        uintptr_t ascCls=FindClassExact("LokiAbilitySystemComponent");
        if(LooksLikePtr(ascCls)) asc=AddCompByClass(carrier,ascCls,"ASC");
        if(LooksLikePtr(asc)&&ascOff!=0xFFFFFFFF&&SafeReadable((void*)(carrier+ascOff),8)){
            *(uintptr_t*)(carrier+ascOff)=asc; Marker("[GAS] wrote carrier.AbilitySystemComponent\r\n"); }
    }
    // Attribute sets: InitStats(<AttributeSet class>, DataTable=null) creates + registers the subobject.
    if(LooksLikePtr(asc)){
        static const char* kSets[2]={"LokiAttributeSet","LokiAttributeSetHealth"};
        static const char* kProp[2]={"AttributeSet","AttributeSetHealth"};
        void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(asc),"K2_InitStats",&f,&th,&ch);
        if(th){ for(int i=0;i<2;i++){
                uintptr_t sc=FindClassExact(kSets[i]); if(!LooksLikePtr(sc)){ Markerf("[GAS] %s class not found\r\n",kSets[i]); continue; }
                memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                uint32_t oa=ParamOffset(ch,"Attributes"); if(oa==0xFFFFFFFF)oa=0;
                uint32_t od=ParamOffset(ch,"DataTable");  if(od==0xFFFFFFFF)od=8;
                *(uint64_t*)(g_gsbuf+oa)=(uint64_t)sc; *(uint64_t*)(g_gsbuf+od)=0;
                bool flt=CallNativeGuarded(f,th,ch,(void*)asc,g_gsbuf,g_rbuf);
                Markerf("[GAS] K2_InitStats(%s, null) %s\r\n",kSets[i],flt?"FAULTED":"ok");
                // mirror onto the carrier's own property if InitStats left it unset
                uint32_t po=PropOffsetSuper(ClassOf(carrier),kProp[i]);
                uintptr_t pv=(po!=0xFFFFFFFF&&SafeReadable((void*)(carrier+po),8))?*(uintptr_t*)(carrier+po):0;
                Markerf("[GAS] carrier.%s@0x%X = 0x%llX\r\n",kProp[i],po,(unsigned long long)pv);
            } }
        else Marker("[GAS] K2_InitStats NOT FOUND on the ASC\r\n");
    }
    *(uintptr_t*)(ps+hoOff)=carrier;
    Markerf("[GAS] *** PlayerState.HeroAffiliatedObject@0x%X = 0x%llX (carrier installed) ***\r\n",hoOff,(unsigned long long)carrier);
    return carrier;
}

static void WireAbilitySystem(uintptr_t hero, uintptr_t pc){
    Marker("[GAS] ===== S101: driving LokiPlayerState's own ability-system wiring chain =====\r\n");
    uint32_t psOff=PropOffsetSuper(ClassOf(pc),"PlayerState");
    uintptr_t ps=(psOff!=0xFFFFFFFF&&SafeReadable((void*)(pc+psOff),8))?*(uintptr_t*)(pc+psOff):0;
    char psn[96]="-"; if(LooksLikePtr(ps)&&ClassOf(ps)) GetFNameStr(NameId(ClassOf(ps)),psn,sizeof(psn));
    Markerf("[GAS] PlayerState @0x%X = 0x%llX (%s)\r\n",psOff,(unsigned long long)ps,psn);
    if(!LooksLikePtr(ps)){ Marker("[GAS] no PlayerState -> abort (the carrier is owned BY the PlayerState)\r\n"); return; }

    ReportGasState(hero,"BEFORE");
    bool before=ReadAbilityInitBit(hero,"BEFORE");
    // ★ S103 — the carrier must exist BEFORE the chain; TryUpdateAbilitySystem only updates, never creates.
    if(KGASCARRIER) EnsureHeroAffiliatedCarrier(ps);

    // STEP 1 — HeroClass. Prefer the native setter; fall back to writing the property, which is what the S90
    // spawn path already does (PlayerState.HeroClass is a UClass* field the spawn reads).
    uintptr_t heroCls=FindClassExact(kCheatHeroClassName);
    Markerf("[GAS] step1 heroClass(%s)=0x%llX\r\n",kCheatHeroClassName,(unsigned long long)heroCls);
    if(LooksLikePtr(heroCls)){
        void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(ps),"ServerSetHeroClass",&f,&th,&ch);
        if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            uint32_t o=ParamOffset(ch,"NewClass"); if(o==0xFFFFFFFF)o=0;
            *(uint64_t*)((uint8_t*)g_pbuf+o)=(uint64_t)heroCls;
            bool flt=CallNativeGuarded(f,th,ch,(void*)ps,g_pbuf,g_rbuf);
            Markerf("[GAS] step1 ServerSetHeroClass(NewClass@0x%X) %s\r\n",o,flt?"FAULTED":"ok");
        } else Marker("[GAS] step1 ServerSetHeroClass NOT FOUND\r\n");
        uint32_t hco=PropOffsetSuper(ClassOf(ps),"HeroClass");
        if(hco!=0xFFFFFFFF&&SafeReadable((void*)(ps+hco),8)){
            uintptr_t cur=*(uintptr_t*)(ps+hco);
            if(!LooksLikePtr(cur)){ *(uintptr_t*)(ps+hco)=heroCls; Markerf("[GAS] step1 HeroClass@0x%X was NULL -> poked\r\n",hco); }
            else Markerf("[GAS] step1 HeroClass@0x%X = 0x%llX (already set)\r\n",hco,(unsigned long long)cur);
        }
    }
    // ★ S101 iter2 — NET ROLE. iter1's decisive clue: ServerSetHeroClass returned "ok" yet HeroClass stayed NULL
    //   (we had to poke it). That is what a Server RPC does when the actor is NOT authority — it routes the call
    //   instead of running the body. TryUpdateAbilitySystem is the server's job, so an authority check is the
    //   prime suspect for why it ran fault-free and did nothing. Report both roles, then (KGASROLE) force
    //   ROLE_Authority=3 and retry the keystone.
    uint32_t roOff=PropOffsetSuper(ClassOf(ps),"Role"), rrOff=PropOffsetSuper(ClassOf(ps),"RemoteRole");
    int roVal=(roOff!=0xFFFFFFFF&&SafeReadable((void*)(ps+roOff),1))?*(uint8_t*)(ps+roOff):-1;
    int rrVal=(rrOff!=0xFFFFFFFF&&SafeReadable((void*)(ps+rrOff),1))?*(uint8_t*)(ps+rrOff):-1;
    Markerf("[GAS] PlayerState Role@0x%X=%d RemoteRole@0x%X=%d  (3=ROLE_Authority)%s\r\n",
            roOff,roVal,rrOff,rrVal, (roVal==3)?"":"   <== NOT AUTHORITY");
    { uint32_t hro=PropOffsetSuper(ClassOf(hero),"Role");
      int hrv=(hro!=0xFFFFFFFF&&SafeReadable((void*)(hero+hro),1))?*(uint8_t*)(hero+hro):-1;
      Markerf("[GAS] hero Role@0x%X=%d\r\n",hro,hrv); }
    // Does the PlayerState resolve a HeroAsset? The carrier build may need the ASSET (a primary data asset), not
    // just the class — HeroClass and HeroAsset are different things on this PlayerState.
    { void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(ps),"GetHeroAsset",&f,&th,&ch);
      if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        uint32_t ro=ParamOffset(ch,"ReturnValue");
        bool flt=CallNativeGuarded(f,th,ch,(void*)ps,g_pbuf,g_rbuf);
        uintptr_t ha=(uintptr_t)g_rbuf[0];
        if(!LooksLikePtr(ha)&&ro!=0xFFFFFFFF) ha=*(uint64_t*)((uint8_t*)g_pbuf+ro);
        char hn[96]="-"; if(LooksLikePtr(ha)&&ClassOf(ha)) GetFNameStr(NameId(ClassOf(ha)),hn,sizeof(hn));
        Markerf("[GAS] GetHeroAsset -> 0x%llX (%s)%s\r\n",(unsigned long long)ha,LooksLikePtr(ha)?hn:"NULL",flt?" FAULTED":"");
      } else Marker("[GAS] GetHeroAsset NOT FOUND\r\n"); }

    // STEP 2 — OnRep_HeroClass (parameterless native event; normally fired by replication).
    CallNoArgAuto(ps,"OnRep_HeroClass","GAS step2");
    // STEP 3 — the keystone: build/refresh the ability system + its HeroAffiliated carrier.
    CallNoArgAuto(ps,"TryUpdateAbilitySystem","GAS step3");
    // STEP 3b — if the PlayerState was not authority, make it so and retry. Single variable: only the role byte
    //   changes between the two TryUpdateAbilitySystem calls, so a difference is attributable to it alone.
    if(KGASROLE && roVal!=3 && roOff!=0xFFFFFFFF && SafeReadable((void*)(ps+roOff),1)){
        *(uint8_t*)(ps+roOff)=3;
        Markerf("[GAS] step3b Role %d -> 3 (ROLE_Authority); re-running SetHeroClass + the keystone\r\n",roVal);
        // With authority in place the Server RPC should execute its body rather than route — which is also a
        // second, independent test of the "not authority" diagnosis: HeroClass sticking on its own confirms it.
        if(LooksLikePtr(heroCls)){
            void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(ps),"ServerSetHeroClass",&f,&th,&ch);
            if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                uint32_t o=ParamOffset(ch,"NewClass"); if(o==0xFFFFFFFF)o=0;
                *(uint64_t*)((uint8_t*)g_pbuf+o)=(uint64_t)heroCls;
                bool flt=CallNativeGuarded(f,th,ch,(void*)ps,g_pbuf,g_rbuf);
                Markerf("[GAS] step3b ServerSetHeroClass %s\r\n",flt?"FAULTED":"ok"); }
        }
        CallNoArgAuto(ps,"OnRep_HeroClass","GAS step3b-onrep");
        CallNoArgAuto(ps,"TryUpdateAbilitySystem","GAS step3b");
    }

    ReportGasState(hero,"AFTER ");
    bool after=ReadAbilityInitBit(hero,"AFTER ");
    // The accessor is the second witness: a non-null ASC means the carrier really was created and cached.
    { void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(hero),"GetLokiAbilitySystem_BP",&f,&th,&ch);
      if(th){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        uint32_t ro=ParamOffset(ch,"ReturnValue");
        bool flt=CallNativeGuarded(f,th,ch,(void*)hero,g_pbuf,g_rbuf);
        uintptr_t asc=(uintptr_t)g_rbuf[0];
        if(!LooksLikePtr(asc)&&ro!=0xFFFFFFFF) asc=*(uint64_t*)((uint8_t*)g_pbuf+ro);
        char an[96]="-"; if(LooksLikePtr(asc)&&ClassOf(asc)) GetFNameStr(NameId(ClassOf(asc)),an,sizeof(an));
        Markerf("[GAS] GetLokiAbilitySystem_BP -> 0x%llX (%s)%s\r\n",(unsigned long long)asc,LooksLikePtr(asc)?an:"NULL",flt?" FAULTED":"");
      } else Marker("[GAS] GetLokiAbilitySystem_BP NOT FOUND\r\n"); }
    Markerf("[GAS] ===== RESULT: initialised %d -> %d  %s =====\r\n",(int)before,(int)after,
            (after&&!before)?"*** THE CHAIN WORKED ***":(after?"(was already set)":"*** STILL NOT INITIALISED ***"));
}

static uintptr_t BuildHeroBody(uintptr_t hero, uintptr_t skelCls, uintptr_t mesh, bool deferred){
    void* acfn=nullptr; uintptr_t acth=0,acch=0; ResolveFuncSuper(ClassOf(hero),"AddComponentByClass",&acfn,&acth,&acch);
    if(!acth){ Marker("[PL] AddComponentByClass thunk not found\r\n"); return 0; }
    // ★ S106d — savedXform WAS `[0x50]`, i.e. the third instance of the D1 truncation (see KXFORMFIX,
    // L109). RelativeTransform is 0x60 and Scale3D.Z sits at 0x50, so the save/restore pair dropped it
    // and the DEFERRED FinishAddComponent below re-applied Scale.Z = 0 at REGISTRATION -- undoing the
    // S98 `RelativeScale3D = (1,1,1)` fix ~55 lines down, at exactly the moment the cloth/physics body
    // is built. kXfSavedSz is 0x60 with the fix on, 0x50 with -DKXFORMFIX=0 (reproduces the old bug).
    static const uint32_t kXfSavedSz = KXFORMFIX ? 0x60 : 0x50;
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); uint32_t retOff=0xFFFFFFFF; uint8_t savedXform[0x60]={0}; uint32_t xoff=0xFFFFFFFF;
    for(uintptr_t p=acch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
        char pn[64]="?"; GetFNameStr(NameId(p),pn,sizeof(pn));
        // S106d: bound is kXfSavedSz (0x60), matching the memcpy below -- at 0x50 a high-offset
        // RelativeTransform would have passed the check and then overrun g_gsbuf by up to 0x10 bytes.
        uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF; if(o==0xFFFFFFFF||o+kXfSavedSz>sizeof(g_gsbuf))continue;
        uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0;
        if(strcmp(pn,"Class")==0) *(uint64_t*)(g_gsbuf+o)=(uint64_t)skelCls;
        // FTransform (0x60, 16-byte aligned): quatW@0x18=T[3]; Translation@0x20/28/30=T[4..6] (+pad T[7]);
        // ⚠ Scale3D@0x40/0x48/0x50 = T[8],T[9],T[10] — NOT T[7..9]. The old T[7..9] wrote translation-pad, Scale.X,
        // Scale.Y and left Scale.Z = 0, flattening the component to zero height (invisible). Proven live.
        else if(strcmp(pn,"RelativeTransform")==0){ double* T=(double*)(g_gsbuf+o); T[3]=1.0; T[6]=KBODYZ; T[8]=1.0; T[9]=1.0; T[10]=1.0; xoff=o; }
        else if(strcmp(pn,"bDeferredFinish")==0){ *(uint8_t*)(g_gsbuf+o)=deferred?1:0; }
        else if(fl&0x400) retOff=o;   // CPF_ReturnParm
    }
    if(xoff!=0xFFFFFFFF) memcpy(savedXform, g_gsbuf+xoff, kXfSavedSz);   // keep the identity xform for FinishAddComponent
    bool flt=CallNativeGuarded(acfn,acth,acch,(void*)hero,g_gsbuf,g_rbuf);
    uintptr_t comp=(uintptr_t)g_rbuf[0]; if(!LooksLikePtr(comp)&&retOff!=0xFFFFFFFF) comp=*(uint64_t*)(g_gsbuf+retOff);
    char ccn[96]="-"; if(LooksLikePtr(comp)&&ClassOf(comp)) GetFNameStr(NameId(ClassOf(comp)),ccn,sizeof(ccn));
    Markerf("[PL] AddComponentByClass %s -> comp=0x%llX(%s)\r\n",flt?"FAULTED":"ok",(unsigned long long)comp,ccn);
    if(!LooksLikePtr(comp)) return 0;
    // ★★★ S98 — FORCE THE COMPONENT'S SCALE TO 1 AFTER CREATION. Passing Scale3D inside the RelativeTransform param
    // is fragile (FTransform here is the ALIGNED 0x60 layout: Rotation@0x00, Translation@0x20+pad, Scale3D@0x40+pad,
    // so Scale.Z sits at 0x50 and kept landing outside what the call actually consumed). Live proof: the component
    // read RelativeScale3D = (1.000,1.000,0.000) — FLAT, i.e. invisible from every angle — while the game's own hero
    // capsule read (1,1,1). Writing the field directly (and via SetWorldScale3D when available) is offset-exact.
    { uint32_t so=PropOffsetSuper(ClassOf(comp),"RelativeScale3D");
      if(so!=0xFFFFFFFF && SafeReadable((void*)(comp+so),24)){
          double* S=(double*)(comp+so); double h0=S[0],h1=S[1],h2=S[2];
          S[0]=1.0; S[1]=1.0; S[2]=1.0;
          Markerf("[PL] comp RelativeScale3D@0x%X was (%.3f,%.3f,%.3f) -> (1,1,1)%s\r\n",so,h0,h1,h2,
                  (h0==0.0||h1==0.0||h2==0.0)?"  *** FLAT/ZERO SCALE FIXED ***":"");
      } else Marker("[PL] RelativeScale3D prop NOT FOUND on component\r\n"); }
    // push it through the engine so the transform actually propagates to the render/physics state
    { void* sf=nullptr; uintptr_t st=0,sc=0; ResolveFuncSuper(ClassOf(comp),"SetWorldScale3D",&sf,&st,&sc);
      if(st){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
          uint32_t o=ParamOffset(sc,"NewScale"); if(o==0xFFFFFFFF)o=0;
          double* S=(double*)(g_gsbuf+o); S[0]=1.0; S[1]=1.0; S[2]=1.0;
          bool f=CallNativeGuarded(sf,st,sc,(void*)comp,g_gsbuf,g_rbuf);
          Markerf("[PL] SetWorldScale3D(1,1,1) %s\r\n",f?"FAULTED":"ok"); } }
    if(mesh){ void* smfn=nullptr; uintptr_t smth=0,smch=0; ResolveFuncSuper(ClassOf(comp),"SetSkeletalMeshAsset",&smfn,&smth,&smch);
      if(smth){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        for(uintptr_t p=smch;LooksLikePtr(p);p=SafeReadable((void*)(p+FIELD_NEXT),8)?*(uintptr_t*)(p+FIELD_NEXT):0){
            uint64_t fl=SafeReadable((void*)(p+FPROP_FLAGS),8)?*(uint64_t*)(p+FPROP_FLAGS):0; if(!(fl&0x80))continue;   // CPF_Parm
            uint32_t o=SafeReadable((void*)(p+FPROP_OFFSET),4)?*(uint32_t*)(p+FPROP_OFFSET):0xFFFFFFFF;
            if(o!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+o)=(uint64_t)mesh; break; }
        bool f=CallNativeGuarded(smfn,smth,smch,(void*)comp,g_gsbuf,g_rbuf); Markerf("[PL] SetSkeletalMeshAsset %s\r\n",f?"FAULTED":"ok"); }
      else Marker("[PL] SetSkeletalMeshAsset thunk not found\r\n"); }
    // Disable CLOTH: Ronin's mesh carries ClothingSimulationFactoryNv; cloth sim in the force-open context (no proper
    // physics/deploy world) is a prime render-crash suspect. Null the factory + OR the bDisableClothSimulation bit.
    { uint32_t cf=PropOffsetSuper(ClassOf(comp),"ClothingSimulationFactory"); if(cf!=0xFFFFFFFF&&SafeReadable((void*)(comp+cf),8)){ *(uint64_t*)(comp+cf)=0; Markerf("[PL] ClothingSimulationFactory@0x%X=null\r\n",cf); } }
    // ⚠ S94 iter10 BUG (fixed): bDisableClothSimulation / bOwnerNoSee / bOnlyOwnerSee are BITFIELD bools — several
    // share ONE byte (all three resolved to bytes holding other flags, e.g. bOwnerNoSee@0x2A4 read 152). Writing the
    // whole byte (=0, or |=1) CLOBBERS the neighbouring render flags. Don't poke them raw; nulling the cloth factory
    // (a real pointer field) is enough, and the game's own BP component already has sane visibility flags.
    // RENDER the ref pose without an AnimBP: S93 rendered NOTHING with tick OFF (the component never updates its
    // pose/render state). Fix = SetAnimationMode(AnimationSingleNode=1) so NO hero AnimBP is instantiated (that
    // mismatched-skeleton AnimBP eval is what crashed S93), THEN enable tick so the component evaluates the empty
    // single-node = ref pose and submits render state each frame. Visible last.
    if(KANIMMODE>=0){ void* af=nullptr; uintptr_t at=0,ac=0; ResolveFuncSuper(ClassOf(comp),"SetAnimationMode",&af,&at,&ac);
      if(at){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=(uint8_t)KANIMMODE; CallNativeGuarded(af,at,ac,(void*)comp,g_pbuf,g_rbuf); Markerf("[PL] SetAnimationMode(%d)\r\n",(int)KANIMMODE); }
      else Marker("[PL] SetAnimationMode thunk not found\r\n"); }
    { void* vf=nullptr; uintptr_t vt=0,vc=0; ResolveFuncSuper(ClassOf(comp),"SetVisibility",&vf,&vt,&vc);
      if(vt){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=1; CallNativeGuarded(vf,vt,vc,(void*)comp,g_pbuf,g_rbuf); } }
    { void* tf=nullptr; uintptr_t tt=0,tc=0; ResolveFuncSuper(ClassOf(comp),"SetComponentTickEnabled",&tf,&tt,&tc);
      if(tt){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=(uint8_t)(KMESHTICK?1:0); CallNativeGuarded(tf,tt,tc,(void*)comp,g_pbuf,g_rbuf); } }
    // DEFERRED finish (route 2): now that AnimBP is off (SingleNode) + cloth off, register the component so it renders.
    if(deferred){
        if(g_plFacThunk && g_oFacComp!=0xFFFFFFFF){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            *(uint64_t*)(g_gsbuf+g_oFacComp)=(uint64_t)comp;
            if(g_oFacManual!=0xFFFFFFFF) g_gsbuf[g_oFacManual]=0;
            // ★ S106d — 0x60, not 0x50: at 0x50 this call re-applied Scale.Z = 0 AT REGISTRATION and
            // silently undid the S98 RelativeScale3D fix above. Log the scale actually being sent so a
            // marker file proves which value registration saw.
            if(g_oFacXform!=0xFFFFFFFF && g_oFacXform+kXfSavedSz<=sizeof(g_gsbuf)){
                memcpy(g_gsbuf+g_oFacXform, savedXform, kXfSavedSz);
                double* FS=(double*)(savedXform+kXfScaleOff);
                Markerf("[XF] FinishAddComponent RelativeTransform@0x%X copy=0x%X Scale3D=(%.3f,%.3f,%.3f)%s\r\n",
                        g_oFacXform,kXfSavedSz,FS[0],FS[1],FS[2],
                        (FS[0]==0.0||FS[1]==0.0||FS[2]==0.0)?"  *** DEGENERATE (would build a non-uniform body) ***":""); }
            bool ff=CallNativeGuarded(g_plFacFn,g_plFacThunk,g_plFacChild,(void*)hero,g_gsbuf,g_rbuf);
            Markerf("[PL] FinishAddComponent %s\r\n",ff?"FAULTED":"ok"); }
        else Markerf("[PL] FinishAddComponent thunk MISSING (comp left unregistered) fac=0x%llX comp@0x%X\r\n",(unsigned long long)g_plFacThunk,g_oFacComp);
    }
    // ★★★ S99 — PLAY A REAL ANIMATION (fixes BOTH the T-pose AND the sword-through-the-torso).
    // The sword is NOT a separate component: SK_Ronin_Default_LOD1's own skeleton carries sword_01..04_m_jnt /
    // hand_weapon01_l|r_jnt / spine03_weaponAttach01_m_jnt (see SK_Ronin_Default_LOD1.uasset.names.txt). In BIND pose
    // those bones sit at rest = the blade passes through the body. Any real pose puts the sword in the hand, so there
    // is nothing to socket-attach. Enabling the component's own AnimBP (ABP_LokiHero_GenericRoot_EventDriven_C) makes
    // the body VANISH — it is "EventDriven" and, with no GAS/character state in force-open, evaluates to a degenerate
    // pose. So: stay in SingleNode and drive an AnimSequence ourselves. PlayAnimation(anim, loop) sets SingleNode mode,
    // assigns the asset and plays, all in one native call.
    if(KPLAYANIM){
        uintptr_t anim=LoadMeshByPath(KANIMPATH);
        char an[96]="-"; if(LooksLikePtr(anim)&&ClassOf(anim)) GetFNameStr(NameId(ClassOf(anim)),an,sizeof(an));
        Markerf("[PL] anim asset=0x%llX (%s)\r\n",(unsigned long long)anim,an);
        if(LooksLikePtr(anim)){
            g_plIdleAnim=anim;                     // S99b: remembered so the run<->idle swap can come back to it
            PlayAnimOn(comp,anim,KANIMNAME);       // <- fixes T-pose AND sword placement (same bug: bind pose)
            // ★ S106 (FK-7) — PlayAnimation creates a UAnimSingleNodeInstance we never hold, and the body
            // component is likewise only referenced from this DLL's globals. Rooting the component keeps its
            // whole Outer/owner chain reachable too, which is the point: the measured crash is the FIRST GC
            // after this code runs. Costs a permanent leak of a handful of objects for the session.
            if(KGCROOTCOMP){
                GcRoot(comp,"body-component");
                int nInst=GcRootAllOfClass("AnimSingleNodeInstance",4,"anim-instance");
                Markerf("[GC] anim-instance rooted x%d (rooted=%d failed=%d)\r\n",nInst,g_gcRooted,g_gcFailed); }
        } else Marker("[PL] anim load FAILED -> body stays in T-pose\r\n");
    }
    // ★ REGISTER WITH FOG OF WAR — the render gate: unregistered character primitives are culled from the FOW scene
    //   view and never draw (S94 iter11 root cause). Must happen AFTER the component is registered/finished.
    FowRegister(comp,"body");
    Markerf("[PL] body built (animMode=%d tick=%d visible deferred=%d)\r\n",(int)KANIMMODE,(int)KMESHTICK,(int)deferred);
    return comp;
}
// Fire AsyncLoadPrimaryAssets for candidate Ronin primary assets so SK_Ronin_Default streams in WITH render data.
// Param layout (LokiAssetManager.AsyncLoadPrimaryAssets, per missions_fix/ds_hybrid): WorldContextObject@0,
// AssetsToLoad{Data@8,Num@16,Max@20}. The param chain is DumpParams'd in ResolvePlay so we can correct it if wrong.
static void FireRoninLoad(){
    if(!g_plLam || !g_plPafsThunk || !g_plAlpaThunk){ Marker("[PL] async-load infra missing -> skip (fallback to resident placeholder)\r\n"); return; }
    static const wchar_t* kCand[]={ L"HeroCosmeticsBundle:RoninDefault", L"Hero:Ronin", L"LokiHero:Ronin",
        L"Character:Ronin", L"HeroCosmetic:RoninDefault", L"CharacterCosmetic:RoninDefault", L"Cosmetic:RoninDefault" };
    static uint8_t ids[8*16]={0}; int n=0;
    for(unsigned c=0;c<sizeof(kCand)/sizeof(kCand[0]) && n<8;c++){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); SetFStringAt((uint8_t*)g_pbuf,0,kCand[c]);
        if(CallNativeGuarded(g_plPafsFn,g_plPafsThunk,g_plPafsChild,(void*)g_plLam,g_pbuf,g_rbuf)){ Markerf("[PL] paid '%ls' FAULTED\r\n",kCand[c]); continue; }
        uint64_t t=*(uint64_t*)g_rbuf, nm=*(uint64_t*)((uint8_t*)g_rbuf+8);
        if((uint32_t)t==0){ Markerf("[PL] paid '%ls' -> type 0 (unresolved)\r\n",kCand[c]); continue; }
        memcpy(ids+n*16, g_rbuf, 16); n++;
        Markerf("[PL] paid '%ls' -> {0x%llX,0x%llX}\r\n",kCand[c],(unsigned long long)t,(unsigned long long)nm);
    }
    if(n==0){ Marker("[PL] NO Ronin primary-asset id resolved -> async-load skipped\r\n"); return; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+0)=(uint64_t)g_plWorld;   // WorldContextObject
    *(uint64_t*)((uint8_t*)g_pbuf+8)=(uint64_t)ids;         // AssetsToLoad.Data
    *(uint32_t*)((uint8_t*)g_pbuf+16)=(uint32_t)n;          // .Num
    *(uint32_t*)((uint8_t*)g_pbuf+20)=(uint32_t)n;          // .Max
    bool f=CallNativeGuarded(g_plAlpaFn,g_plAlpaThunk,g_plAlpaChild,(void*)g_plLam,g_pbuf,g_rbuf);
    Markerf("[PL] AsyncLoadPrimaryAssets(%d Ronin ids) %s handle=0x%llX\r\n",n,f?"FAULTED":"fired",(unsigned long long)*(uint64_t*)g_rbuf);
    g_plLoadFired=true;
}
// Blocking load of a UObject by soft path: MakeSoftObjectPath(path) -> FSoftObjectPath, then LoadAsset_Blocking it.
// Returns the loaded object (0 on fail). Synchronous — loads render data before returning.
static uintptr_t LoadMeshByPath(const wchar_t* path){
    if(!g_plKsl || !g_plMspThunk || !g_plLabThunk){ Markerf("[PL] load-by-path infra missing (ksl=0x%llX msp=0x%llX lab=0x%llX)\r\n",(unsigned long long)g_plKsl,(unsigned long long)g_plMspThunk,(unsigned long long)g_plLabThunk); return 0; }
    uint8_t soft[0x40]={0}, res[0x40]={0};
    // 1. MakeSoftObjectPath(path) -> FSoftObjectPath. Native struct returns land in the RESULT buffer (soft), not the
    //    params ReturnValue offset (that was the S94-iter5 bug: read g_gsbuf+0x10 -> empty).
    memset(g_gsbuf,0,sizeof(g_gsbuf));
    if(g_oMspPath!=0xFFFFFFFF) SetFStringAt((uint8_t*)g_gsbuf,g_oMspPath,path);
    bool f1=CallNativeGuarded(g_plMspFn,g_plMspThunk,g_plMspChild,(void*)g_plKsl,g_gsbuf,soft);
    // if the result buffer stayed empty, fall back to the params ReturnValue offset.
    if(*(uint64_t*)soft==0 && g_oMspRet!=0xFFFFFFFF && g_oMspRet+0x20<=sizeof(g_gsbuf)) memcpy(soft, g_gsbuf+g_oMspRet, 0x20);
    Markerf("[PL] MakeSoftObjectPath %s (pkgFName=0x%llX assetFName=0x%llX)\r\n",f1?"FAULTED":"ok",(unsigned long long)*(uint64_t*)soft,(unsigned long long)*(uint64_t*)(soft+8));
    // 2. LoadAsset_Blocking(softptr) -> UObject*. TSoftObjectPtr (0x28) = FWeakObjectPtr WeakPtr@0x0 (8, MUST be zero
    //    so LoadSynchronous resolves from the path, not a stale cache) + FSoftObjectPath ObjectID@0x8 (0x20). The
    //    S94-iter6 bug: wrote the path at +0x0, clobbering WeakPtr -> "cached null" -> LoadAsset returned null.
    memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(res,0,sizeof(res));
    if(g_oLabAsset!=0xFFFFFFFF && g_oLabAsset+0x28<=sizeof(g_gsbuf)) memcpy(g_gsbuf+g_oLabAsset+0x8, soft, 0x20);
    bool f2=CallNativeGuarded(g_plLabFn,g_plLabThunk,g_plLabChild,(void*)g_plKsl,g_gsbuf,res);
    uintptr_t obj=(uintptr_t)*(uint64_t*)res; if(!LooksLikePtr(obj)&&g_oLabRet!=0xFFFFFFFF) obj=*(uint64_t*)(g_gsbuf+g_oLabRet);
    char cn[96]="-"; if(LooksLikePtr(obj)&&ClassOf(obj)) GetFNameStr(NameId(ClassOf(obj)),cn,sizeof(cn));
    Markerf("[PL] LoadAsset_Blocking %s -> 0x%llX (%s)\r\n",f2?"FAULTED":"ok",(unsigned long long)obj,cn);
    // ★ S106 (FK-7) — LoadAsset_Blocking returns a RAW UObject* and holds no reference; the result lives
    // only in this DLL's C globals, which UE's GC cannot see. Measured consequence: the asset is collected
    // at the first purge after the tutorial map loads (~T+180 s) and the parallel animation tick then
    // dereferences it on a worker thread. Root it here, at the single choke point every load goes through.
    if(LooksLikePtr(obj)) GcRoot(obj,"loaded-asset");
    return LooksLikePtr(obj)?obj:0;
}
static bool ResolvePlay(){
    g_gameHwnd=FindWindowA(nullptr,"SUPERVIVE");
    Markerf("[PL] gameHwnd=0x%llX (0 => focus check disabled)\r\n",(unsigned long long)(uintptr_t)g_gameHwnd);
    if(!ResolveWakeMove()){ Marker("[PL] ResolveWakeMove failed (no possessed hero — spawn+possess first) -> abort\r\n"); return false; }
    // Mesh: prefer Ronin's own body (SK_Ronin_Default); report residency of every candidate. Skins bind to Ronin's
    // skeleton; the SK_KaijuCaster/Base fallbacks are wrong-skeleton (still render a static pose but not Ronin's).
    // SPEED: each FindObjExact is a FULL ~188k-object scan on the game thread. The 7-candidate placeholder sweep cost
    // ~7 scans and is dead weight now that LoadMeshByPath loads the real mesh — only do it if that route is disabled.
    // (Time-to-body was ~215s, and force-open sessions die ~230-260s, leaving no window to see/screenshot the body.)
    if(!KLOADRONIN){
        const char* cand[]={"SK_KaijuCaster_Default","SK_Base_Wisp","SK_HeroPlatform_Default"};
        for(int i=0;i<3;i++){ uintptr_t m=FindObjExact(cand[i]); bool use=(m&&!g_plMesh);
            Markerf("[PL] mesh cand %s = 0x%llX%s\r\n",cand[i],(unsigned long long)m,use?"  <== USING":"");
            if(use){ g_plMesh=m; _snprintf_s(g_plMeshName,sizeof(g_plMeshName),_TRUNCATE,"%s",cand[i]); } }
    }
    g_plSkelCls=FindClassExact("SkeletalMeshComponent");
    ResolveTopDownCam();       // g_gm2/g_gsCDO/g_begin*/g_finish* (SpawnActorCls infra) + g_tcCamCls/g_tcSvtThunk
    g_tcHero=g_wmHero;         // the camera follows the POSSESSED pawn (authoritative), not a name scan
    // async-load infra (stream Ronin's real mesh with render data): LokiAssetManager.PrimaryAssetIDFromString + AsyncLoadPrimaryAssets.
    g_plLam=FindInstByClass("LokiAssetManager",nullptr);
    g_plWorld=FindInstByClass("ProgressionManager",nullptr); if(!g_plWorld) g_plWorld=FindInstByClass("LokiGameState",nullptr); if(!g_plWorld) g_plWorld=g_wmPC;
    if(g_plLam){ ResolveFuncNative(ClassOf(g_plLam),"PrimaryAssetIDFromString",&g_plPafsFn,&g_plPafsThunk,&g_plPafsChild);
        ResolveFuncNative(ClassOf(g_plLam),"AsyncLoadPrimaryAssets",&g_plAlpaFn,&g_plAlpaThunk,&g_plAlpaChild);
        if(g_plAlpaChild) DumpParams(g_plAlpaChild,"AsyncLoadPrimaryAssets"); }
    Markerf("[PL] loadInfra lam=0x%llX world=0x%llX pafs=0x%llX alpa=0x%llX\r\n",(unsigned long long)g_plLam,(unsigned long long)g_plWorld,(unsigned long long)g_plPafsThunk,(unsigned long long)g_plAlpaThunk);
    // route 1: KismetSystemLibrary.MakeSoftObjectPath + LoadAsset_Blocking (blocking load of the real Ronin mesh).
    { uintptr_t kslCDO=FindObjExact("Default__KismetSystemLibrary"); g_plKsl = kslCDO?ClassOf(kslCDO):0;
      if(g_plKsl){ ResolveFuncNative(g_plKsl,"MakeSoftObjectPath",&g_plMspFn,&g_plMspThunk,&g_plMspChild);
        if(g_plMspChild){ g_oMspPath=ParamOffset(g_plMspChild,"PathString"); g_oMspRet=ParamOffset(g_plMspChild,"ReturnValue"); DumpParams(g_plMspChild,"MakeSoftObjectPath"); }
        ResolveFuncNative(g_plKsl,"LoadAsset_Blocking",&g_plLabFn,&g_plLabThunk,&g_plLabChild);
        if(!g_plLabThunk) ResolveFuncNative(g_plKsl,"LoadAssetBlocking",&g_plLabFn,&g_plLabThunk,&g_plLabChild);
        if(g_plLabChild){ g_oLabAsset=ParamOffset(g_plLabChild,"Asset"); g_oLabRet=ParamOffset(g_plLabChild,"ReturnValue"); DumpParams(g_plLabChild,"LoadAsset_Blocking"); } }
      Markerf("[PL] route1 ksl=0x%llX msp=0x%llX(path@0x%X ret@0x%X) lab=0x%llX(asset@0x%X ret@0x%X)\r\n",
        (unsigned long long)g_plKsl,(unsigned long long)g_plMspThunk,g_oMspPath,g_oMspRet,(unsigned long long)g_plLabThunk,g_oLabAsset,g_oLabRet); }
    // ★ FOG-OF-WAR statics (the render gate for character primitives in this game).
    { g_plFowCDO=FindObjExact("Default__LokiFogOfWarStatics");   // fallback context (statics usually ignore `this`)
      uintptr_t regCdo=0, visCdo=0;
      ResolveFuncGlobal("RegisterFogOfWarPrimitive",&g_plFowRegFn,&g_plFowRegThunk,&g_plFowRegChild,&regCdo);
      if(g_plFowRegChild){ g_oFowComp=ParamOffset(g_plFowRegChild,"Component"); g_oFowRet=ParamOffset(g_plFowRegChild,"ReturnValue"); }
      ResolveFuncGlobal("IsFogOfWarVisibleToLocal",&g_plFowVisFn,&g_plFowVisThunk,&g_plFowVisChild,&visCdo);
      if(g_plFowVisChild){ g_oFowTgt=ParamOffset(g_plFowVisChild,"Target"); g_oFowVisRet=ParamOffset(g_plFowVisChild,"ReturnValue"); }
      if(LooksLikePtr(regCdo)) g_plFowCDO=regCdo; else if(LooksLikePtr(visCdo)) g_plFowCDO=visCdo;
      if(!LooksLikePtr(g_plFowCDO)) g_plFowCDO=g_wmPC;   // last resort: any live UObject as context for a static
      Markerf("[FOW] cdo=0x%llX reg=0x%llX(comp@0x%X ret@0x%X) vis=0x%llX(tgt@0x%X ret@0x%X)\r\n",
        (unsigned long long)g_plFowCDO,(unsigned long long)g_plFowRegThunk,g_oFowComp,g_oFowRet,(unsigned long long)g_plFowVisThunk,g_oFowTgt,g_oFowVisRet); }
    // ★ S96 — the GAME'S OWN spawn path. Everything WE spawn has SceneProxy==NULL (never render-registered), while
    //   game-spawned actors render fine. LokiPlayerCheats is the game's own spawn machinery (S74 cheat enum).
    if(KCHEATSPAWN){
        g_cheatCDO=FindObjExact("Default__LokiPlayerCheats");
        uintptr_t cc = LooksLikePtr(g_cheatCDO) ? ClassOf(g_cheatCDO) : 0;
        if(cc){
            ResolveFuncNative(cc,"GetLocalLokiPlayerCheatsBP",&g_glcFn,&g_glcThunk,&g_glcChild);
            if(g_glcChild){ g_oGlcWCO=ParamOffset(g_glcChild,"WorldContextObject"); g_oGlcRet=ParamOffset(g_glcChild,"ReturnValue"); }
            ResolveFuncNative(cc,"ServerCheatSpawnActor",&g_scsaFn,&g_scsaThunk,&g_scsaChild);
            if(g_scsaChild){ g_oScsaClass=ParamOffset(g_scsaChild,"ClassToSpawn"); g_oScsaLoc=ParamOffset(g_scsaChild,"Location"); DumpParams(g_scsaChild,"ServerCheatSpawnActor"); }
            ResolveFuncNative(cc,"ServerCheatChangeHero",&g_schFn,&g_schThunk,&g_schChild);
            if(g_schChild){ g_oSchClass=ParamOffset(g_schChild,"HeroClass"); DumpParams(g_schChild,"ServerCheatChangeHero"); }
        }
        Markerf("[CHEAT] cdo=0x%llX cls=0x%llX getLocal=0x%llX(wco@0x%X ret@0x%X) spawnActor=0x%llX(cls@0x%X loc@0x%X) changeHero=0x%llX(cls@0x%X)\r\n",
            (unsigned long long)g_cheatCDO,(unsigned long long)cc,(unsigned long long)g_glcThunk,g_oGlcWCO,g_oGlcRet,
            (unsigned long long)g_scsaThunk,g_oScsaClass,g_oScsaLoc,(unsigned long long)g_schThunk,g_oSchClass);
    }
    // route 2: FinishAddComponent (register a DEFERRED component) on the hero (AActor).
    ResolveFuncSuper(ClassOf(g_wmHero),"FinishAddComponent",&g_plFacFn,&g_plFacThunk,&g_plFacChild);
    if(g_plFacChild){ g_oFacComp=ParamOffset(g_plFacChild,"Component"); g_oFacManual=ParamOffset(g_plFacChild,"bManualAttachment"); g_oFacXform=ParamOffset(g_plFacChild,"RelativeTransform"); DumpParams(g_plFacChild,"FinishAddComponent"); }
    Markerf("[PL] route2 finishAddComp=0x%llX(comp@0x%X manual@0x%X xform@0x%X)\r\n",(unsigned long long)g_plFacThunk,g_oFacComp,g_oFacManual,g_oFacXform);
    Markerf("[PL] hero=0x%llX CMC=0x%llX mesh=0x%llX(%s) skelCls=0x%llX camCls=0x%llX pc=0x%llX gm=0x%llX gsCDO=0x%llX begin=0x%llX\r\n",
        (unsigned long long)g_wmHero,(unsigned long long)g_wmCMC,(unsigned long long)g_plMesh,g_plMeshName,(unsigned long long)g_plSkelCls,
        (unsigned long long)g_tcCamCls,(unsigned long long)g_tcPC,(unsigned long long)g_gm2,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk);
    bool camOk = g_tcCamCls && g_tcSvtThunk && g_gm2 && g_gsCDO && g_beginThunk;
    if(!camOk) Marker("[PL] WARN: camera infra incomplete — will still teleport/build/move, but no camera takeover\r\n");
    return LooksLikePtr(g_wmHero) && LooksLikePtr(g_wmCMC);
}
static void DoPlay(){
    // ★★ S106c (2026-07-27) — FK-7 GAME-THREAD ARM: the view-target guard must run BEFORE every one of
    // DoPlay's early-outs, so it is called here rather than relying on the DoTopDownCam call site alone.
    //
    // MEASURED GAP in the S106b placement (found by reading the control flow, not by a live run): the only
    // VtGuard call site was the top of DoTopDownCam, which DoPlay reaches at its very BOTTOM (the
    // `DoTopDownCam()` line below the visibility/diagnostic block). But ~60 lines ABOVE that, the S99b
    // possession guard latches `g_plLostPawn` and `return`s — and `if(g_plLostPawn) return;` on the next
    // line makes that stand-down PERMANENT for the rest of the session. So the moment the tutorial
    // unpossessed the hero, the guard silently stopped running for every subsequent hit while the shim
    // still held the PI hook for the remainder of its 600 s hold.
    //
    // That is precisely the wrong time to disarm it: an unpossess is an actor teardown, i.e. the state
    // where PCM->ViewTarget.Target is most likely to be left pointing at something that is going away.
    // The S99b log ("UNPOSSESSED ... standing down") and the 173-201 s camera crash band overlap, so the
    // two could co-occur in a single session and the guard would not have been armed for it.
    //
    // Standing down from CALLING NATIVES on a dead hero (what S99b fixed) and standing down from
    // VALIDATING A POINTER THE ENGINE IS ABOUT TO DEREFERENCE are different decisions: the first protects
    // the game from the shim, the second protects the game from itself, and only the first should be
    // gated on possession. VtGuard makes no native calls — it is reads plus one aligned 8-byte store — so
    // it is safe on the stand-down path. g_wmPC is the authoritative controller here (ResolvePlay requires
    // it via ResolveWakeMove); g_tcPC is the same object resolved by name and is kept as the fallback.
    // The DoTopDownCam call site is intentionally LEFT IN PLACE: it is what covers RM_TOPDOWNCAM and
    // RM_MESHCAM, which never enter DoPlay. Double-calling within one RM_PLAY hit is harmless (the second
    // call sees an already-valid pointer and returns after its reads).
    VtGuard(g_wmPC?g_wmPC:g_tcPC, g_tcCam);
    if(!g_plInit){
        g_plInit=true;
#if KWPROBE
        // FK-24 arm site KWPARMAT=1: the TOP of the one-shot block. MEASURED: this whole block runs inside
        // ONE ProcessInternal hit and ends at g_plBodyDone; the writer's window is its INTERIOR (the blocking
        // FlushAsyncLoading + body build), so arming at its exit (KWPARMAT=2) arms too late.
        WpArmRequest(1);
#endif
        // ★★★★ S101 — run the ability-system wiring FIRST. It is three cheap native calls, whereas the body build
        //   below does blocking asset loads and object scans; these sessions die unpredictably, so the measurement
        //   we came for must not sit behind the slow part.
        if(KWIREGAS) WireAbilitySystem(g_wmHero,g_wmPC);
        // 1. ground: teleport to a known-walkable spot (no [SP] sky-lift), gravity ON so it settles onto the surface.
        if(!KNOTELE && g_slThunk && g_oSlLoc!=0xFFFFFFFF){
            memset(g_slbuf,0,sizeof(g_slbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            double* NL=(double*)(g_slbuf+g_oSlLoc); NL[0]=KGROUNDX; NL[1]=KGROUNDY; NL[2]=KGROUNDZ;
            if(g_oSlSweep!=0xFFFFFFFF) g_slbuf[g_oSlSweep]=0; if(g_oSlTele!=0xFFFFFFFF) g_slbuf[g_oSlTele]=1;
            bool f=CallNativeGuarded(g_slFn,g_slThunk,g_slChild,(void*)g_wmHero,g_slbuf,g_rbuf);
            Markerf("[PL] teleport hero -> ground (%.0f,%.0f,%.0f)%s\r\n",(double)KGROUNDX,(double)KGROUNDY,(double)KGROUNDZ,f?" FAULTED":"");
        }
        if(g_wmGravOff!=0xFFFFFFFF&&SafeReadable((void*)(g_wmCMC+g_wmGravOff),4)) *(float*)(g_wmCMC+g_wmGravOff)=1.0f;
        if(g_rimThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallNativeGuarded(g_rimFn,g_rimThunk,g_rimChild,(void*)g_wmPC,g_pbuf,g_rbuf); }
        // MOVE_Flying (S81): bypass the ground-mantle chain that crashed movement on cell-streaming. Set on the CMC.
        if(KFLYMODE && g_smmThunk && g_oSmmMode!=0xFFFFFFFF){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            ((uint8_t*)g_pbuf)[g_oSmmMode]=(uint8_t)KFLYMODE; if(g_oSmmCustom!=0xFFFFFFFF)((uint8_t*)g_pbuf)[g_oSmmCustom]=0;
            bool f=CallNativeGuarded(g_smmFn,g_smmThunk,g_smmChild,(void*)g_wmCMC,g_pbuf,g_rbuf); Markerf("[PL] SetMovementMode(%d)%s\r\n",(int)KFLYMODE,f?" FAULTED":""); }
        g_puppetInit=true;   // suppress DoPuppet's own init (gravity+rim already done here)
        // ★ UNHIDE the hero: SUPERVIVE spawns heroes HIDDEN until deploy; a hidden ACTOR hides ALL its child
        //   components (incl. our from-scratch mesh) -> nothing renders no matter how the component is set up.
        { void* hf=nullptr; uintptr_t ht=0,hc=0; ResolveFuncSuper(ClassOf(g_wmHero),"SetActorHiddenInGame",&hf,&ht,&hc);
          if(ht){ uint32_t o=ParamOffset(hc,"bNewHidden"); memset(g_pbuf,0,sizeof(g_pbuf)); if(o!=0xFFFFFFFF)((uint8_t*)g_pbuf)[o]=0; memset(g_rbuf,0,sizeof(g_rbuf));
            bool f=CallNativeGuarded(hf,ht,hc,(void*)g_wmHero,g_pbuf,g_rbuf); Markerf("[PL] SetActorHiddenInGame(hero,false)%s\r\n",f?" FAULTED":""); }
          else Marker("[PL] SetActorHiddenInGame thunk not found\r\n"); }
        // ★ FOG OF WAR — the render gate (S94 iter12 root cause): IsFogOfWarVisibleToLocal(hero)==FALSE, so every
        //   character primitive is culled. Make the hero a vision source BEFORE building the body.
        if(KFOWATTR) FowMakeVisionSource(g_wmHero);   // route A: DEAD (hero has no GAS attribute set) + costs a full object scan
        if(KFOWKILL) FowDisable();   // route B: neutralise the FOW renderer so nothing is mask-culled
        // 2. build the body with Ronin's REAL mesh. FireRoninLoad first (bundle deps/materials), then the BLOCKING
        //    load-by-path of SK_Ronin_Default_LOD1 (synchronous -> render data ready), then build. Fallback = placeholder.
        if(!KNOMESH){
            if(KFIREBUNDLE) FireRoninLoad();   // async bundle load — redundant once the blocking load works.
            if(KUSEBPCOMP){   // route 2: the game's own configured BP mesh-component (mesh+materials+registration wired the game way).
                uintptr_t bpCls = LoadMeshByPath(KBPCOMPPATH); g_plBpCls = bpCls;   // keep the CLASS (FindObjExact by that
                // name later returns the hero's component INSTANCE — it's named after its class — which broke the test actor).
                char bcn[96]="-"; if(LooksLikePtr(bpCls)&&ClassOf(bpCls)) GetFNameStr(NameId(ClassOf(bpCls)),bcn,sizeof(bcn));
                Markerf("[PL] route2 BP-comp class = 0x%llX (%s)\r\n",(unsigned long long)bpCls,bcn);
                if(LooksLikePtr(bpCls)) g_plComp = BuildHeroBody(g_wmHero, bpCls, 0, true);   // deferred; BP CDO provides the mesh
                else Marker("[PL] route2 class load FAILED -> route 1 fallback\r\n");
            }
            if(!LooksLikePtr(g_plComp)){   // route 1: bare SkeletalMeshComponent + the real mesh loaded by path.
                uintptr_t m = KLOADRONIN ? LoadMeshByPath(KMESHPATH) : 0;
                if(!m){ m = FindObjExact("SK_Ronin_Default_LOD1"); if(m) Marker("[PL] SK_Ronin_Default_LOD1 already resident\r\n"); }
                if(!m && g_plMesh){ m = g_plMesh; Markerf("[PL] falling back to resident placeholder %s (may not render)\r\n",g_plMeshName); }
                if(m && g_plSkelCls) g_plComp = BuildHeroBody(g_wmHero, g_plSkelCls, m, false);
                else Markerf("[PL] no mesh -> body skipped (skelCls=0x%llX)\r\n",(unsigned long long)g_plSkelCls);
            }
        }
        // ★ DISCRIMINATOR (KTESTACTOR): put the SAME Ronin body on a STANDALONE actor beside the hero. The hero is at
        //   the right place with the mesh assigned and still doesn't draw, so either the HERO ACTOR is hidden
        //   (SUPERVIVE hides heroes until deploy) or the MESH itself can't draw. A CameraActor (known-good spawn, has
        //   a root) carries the body ~500 units away: body appears there but not on the hero => the HERO is the
        //   blocker; neither appears => the MESH/materials are.
        // ★★★ S96 — SPAWN VIA THE GAME'S OWN CHEAT RPC and immediately report the new actor's SceneProxy. A non-null
        //     proxy here is THE fix: it means game-spawned actors register with the render scene while ours don't.
        if(KCHEATSPAWN && g_glcThunk && LooksLikePtr(g_cheatCDO)){
            uintptr_t cheatObj=0;
            memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            if(g_oGlcWCO!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oGlcWCO)=(uint64_t)g_wmPC;
            if(!CallNativeGuarded(g_glcFn,g_glcThunk,g_glcChild,(void*)g_cheatCDO,g_gsbuf,g_rbuf)){
                cheatObj=(uintptr_t)g_rbuf[0];
                if(!LooksLikePtr(cheatObj)&&g_oGlcRet!=0xFFFFFFFF) cheatObj=*(uint64_t*)(g_gsbuf+g_oGlcRet);
            }
            char con[96]="-"; if(LooksLikePtr(cheatObj)&&ClassOf(cheatObj)) GetFNameStr(NameId(ClassOf(cheatObj)),con,sizeof(con));
            Markerf("[CHEAT] localCheatObj=0x%llX(%s)\r\n",(unsigned long long)cheatObj,con);
            if(LooksLikePtr(cheatObj) && g_scsaThunk){
                uintptr_t spawnCls=FindClassExact("BP_HERO_Ronin_C");   // a class whose CDO already carries a body
                double hl[3]={0,0,0}; ActorLoc(g_wmHero,hl);
                char cbuf[8]; int before=CountByClassSub("BP_HERO_",cbuf,0);
                memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                if(g_oScsaClass!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oScsaClass)=(uint64_t)spawnCls;
                if(g_oScsaLoc!=0xFFFFFFFF){ double* L=(double*)(g_gsbuf+g_oScsaLoc); L[0]=hl[0]-400.0; L[1]=hl[1]; L[2]=hl[2]; }
                bool f=CallNativeGuarded(g_scsaFn,g_scsaThunk,g_scsaChild,(void*)cheatObj,g_gsbuf,g_rbuf);
                Markerf("[CHEAT] ServerCheatSpawnActor(BP_HERO_Ronin_C @ %.0f,%.0f,%.0f) %s  [BP_HERO_ count before=%d]\r\n",
                    hl[0]-400.0,hl[1],hl[2],f?"FAULTED":"ok",before);
                g_plCheatDone=true;
            }
            if(KCHEATSPAWN>=2 && LooksLikePtr(cheatObj) && g_schThunk){
                uintptr_t hc=FindClassExact("BP_HERO_Ronin_C");
                memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                if(g_oSchClass!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oSchClass)=(uint64_t)hc;
                bool f=CallNativeGuarded(g_schFn,g_schThunk,g_schChild,(void*)cheatObj,g_gsbuf,g_rbuf);
                Markerf("[CHEAT] ServerCheatChangeHero(BP_HERO_Ronin_C) %s\r\n",f?"FAULTED":"ok");
            }
        }
        // ★ S95 SPAWN-vs-COMPONENT discriminator: spawn a real **StaticMeshActor** (NOT a CameraActor — those are
        //   hidden in game by default, which invalidated the earlier "standalone" control) and set the mesh on the
        //   component the ENGINE built as part of that actor. Renders => our spawn path is fine and the HERO actor is
        //   the thing that isn't render-registered. Doesn't render => nothing we spawn can ever render.
        if(KSMACTOR && g_gm2 && g_gsCDO && g_beginThunk){
            uintptr_t smaCls=FindClassExact("StaticMeshActor");
            uintptr_t lvlSMC=FindInstByClass("StaticMeshComponent","UAID"); if(!LooksLikePtr(lvlSMC)) lvlSMC=FindInstByClass("StaticMeshComponent",nullptr);
            uintptr_t sm=0; if(LooksLikePtr(lvlSMC)){ uint32_t o=PropOffsetSuper(ClassOf(lvlSMC),"StaticMesh"); if(o!=0xFFFFFFFF&&SafeReadable((void*)(lvlSMC+o),8)) sm=*(uint64_t*)(lvlSMC+o); }
            double hl[3]={0,0,0}; ActorLoc(g_wmHero,hl);
            memset(g_xform,0,sizeof(g_xform)); *(double*)(g_xform+0x18)=1.0;
            *(double*)(g_xform+0x20)=hl[0]+400.0; *(double*)(g_xform+0x28)=hl[1]; *(double*)(g_xform+0x30)=hl[2];
            XfScale(3.0,3.0,3.0);   // 3x = unmissable. S106d: was 0x38/0x40/0x48 -> spawned (3,3,0), i.e. FLAT.
            uintptr_t sma = LooksLikePtr(smaCls) ? SpawnActorCls(smaCls,"sma-test") : 0;
            uintptr_t root=0; if(LooksLikePtr(sma)){ uint32_t ro=PropOffsetSuper(ClassOf(sma),"RootComponent"); if(ro!=0xFFFFFFFF&&SafeReadable((void*)(sma+ro),8)) root=*(uint64_t*)(sma+ro); }
            char rn[96]="-"; if(LooksLikePtr(root)&&ClassOf(root)) GetFNameStr(NameId(ClassOf(root)),rn,sizeof(rn));
            Markerf("[SMA] cls=0x%llX actor=0x%llX root=0x%llX(%s) mesh=0x%llX\r\n",(unsigned long long)smaCls,(unsigned long long)sma,(unsigned long long)root,rn,(unsigned long long)sm);
            if(LooksLikePtr(root)&&LooksLikePtr(sm)){
                void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(root),"SetStaticMesh",&f,&th,&ch);
                if(th){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                    uint32_t o=ParamOffset(ch,"NewMesh"); if(o==0xFFFFFFFF)o=0; *(uint64_t*)(g_gsbuf+o)=(uint64_t)sm;
                    bool fl=CallNativeGuarded(f,th,ch,(void*)root,g_gsbuf,g_rbuf);
                    Markerf("[SMA] SetStaticMesh on the ENGINE-built root %s  (look for a big sphere beside the hero)\r\n",fl?"FAULTED":"ok"); }
                else Marker("[SMA] SetStaticMesh thunk not found\r\n");
            }
        }
        if(KTESTACTOR && g_tcCamCls && g_gm2 && g_gsCDO && g_beginThunk){
            double hl[3]={0,0,0}; ActorLoc(g_wmHero,hl);
            memset(g_xform,0,sizeof(g_xform)); *(double*)(g_xform+0x18)=1.0;
            *(double*)(g_xform+0x20)=hl[0]+KTESTDX; *(double*)(g_xform+0x28)=hl[1]; *(double*)(g_xform+0x30)=hl[2];
            XfScale(1.0,1.0,1.0);   // S106d: was 0x38/0x40/0x48 -> this test actor spawned at (1,1,0).
            uintptr_t ta=SpawnActorCls(g_tcCamCls,"test-body-actor");
            Markerf("[PL] TEST actor=0x%llX at (%.0f,%.0f,%.0f)\r\n",(unsigned long long)ta,hl[0]+(double)KTESTDX,hl[1],hl[2]);
            if(LooksLikePtr(ta)){
                uintptr_t tcls = KUSEBPCOMP ? g_plBpCls : 0;   // the loaded CLASS (not FindObjExact — that returns the instance)
                uintptr_t tmesh = 0; if(!tcls){ tcls=g_plSkelCls; tmesh=FindObjExact("SK_Ronin_Default_LOD1"); }
                uintptr_t tc = (tcls) ? BuildHeroBody(ta, tcls, tmesh, KUSEBPCOMP?true:false) : 0;
                Markerf("[PL] TEST body comp=0x%llX (cls=0x%llX mesh=0x%llX)\r\n",(unsigned long long)tc,(unsigned long long)tcls,(unsigned long long)tmesh);
            }
        }
        // ★ STATIC-MESH DISCRIMINATOR — borrow a mesh from a level StaticMeshComponent that is VISIBLY rendering right
        //   now, and put it on a StaticMeshComponent WE create (on the hero, so it's centre-frame). Same asset, same
        //   world, same frame: if the level's copy draws and ours doesn't, the fault is our component-creation path
        //   (no render proxy), not the mesh/skeletal pipeline.
        if(KSTATICTEST){
            uintptr_t lvlSMC=FindInstByClass("StaticMeshComponent","UAID");   // a level static-mesh component
            if(!LooksLikePtr(lvlSMC)) lvlSMC=FindInstByClass("StaticMeshComponent",nullptr);
            uintptr_t sm=0; uint32_t smo=0xFFFFFFFF;
            if(LooksLikePtr(lvlSMC)){ smo=PropOffsetSuper(ClassOf(lvlSMC),"StaticMesh");
                if(smo!=0xFFFFFFFF&&SafeReadable((void*)(lvlSMC+smo),8)) sm=*(uint64_t*)(lvlSMC+smo); }
            char smn[96]="-"; if(LooksLikePtr(sm)) GetFNameStr(NameId(sm),smn,sizeof(smn));
            Markerf("[SMT] level SMC=0x%llX StaticMesh@0x%X=0x%llX(%s)\r\n",(unsigned long long)lvlSMC,smo,(unsigned long long)sm,smn);
            uintptr_t smCls=FindClassExact("StaticMeshComponent");
            if(LooksLikePtr(sm)&&LooksLikePtr(smCls)){
                uintptr_t c=BuildHeroBody(g_wmHero,smCls,0,false);   // bare StaticMeshComponent on the hero
                if(LooksLikePtr(c)){
                    void* f=nullptr; uintptr_t th=0,ch=0; ResolveFuncSuper(ClassOf(c),"SetStaticMesh",&f,&th,&ch);
                    if(th){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                        uint32_t o=ParamOffset(ch,"NewMesh"); if(o==0xFFFFFFFF)o=0;
                        *(uint64_t*)(g_gsbuf+o)=(uint64_t)sm;
                        bool fl=CallNativeGuarded(f,th,ch,(void*)c,g_gsbuf,g_rbuf);
                        Markerf("[SMT] our StaticMeshComponent=0x%llX SetStaticMesh(%s) %s\r\n",(unsigned long long)c,smn,fl?"FAULTED":"ok");
                    } else Marker("[SMT] SetStaticMesh thunk not found\r\n");
                }
            } else Markerf("[SMT] SKIPPED (sm=0x%llX cls=0x%llX)\r\n",(unsigned long long)sm,(unsigned long long)smCls);
        }
        // ★ S99b — load the RUN loop now (blocking, same LoadMeshByPath path as the idle) so the per-hit swap
        //   never has to touch the loader on the game thread.
        if(KRUNANIM && LooksLikePtr(g_plComp)){
            g_plRunAnim=LoadMeshByPath(KRUNANIMPATH);
            char rn[96]="-"; if(LooksLikePtr(g_plRunAnim)&&ClassOf(g_plRunAnim)) GetFNameStr(NameId(ClassOf(g_plRunAnim)),rn,sizeof(rn));
            Markerf("[ANIM] run anim %s = 0x%llX (%s)%s\r\n",KRUNANIMNAME,(unsigned long long)g_plRunAnim,rn,
                    LooksLikePtr(g_plRunAnim)?"":"  <- LOAD FAILED, idle only");
            // ★ S110 — the run anim is the ONE asset nothing references (the idle survives because
            // PlayAnimation put it in the single-node instance's CurrentAsset). Park it in the
            // component's unused AnimationData.AnimToPlay so the GC traversal reaches it. Rooting it
            // is measured inert; see AnimRefHold's comment block.
            AnimRefHold(g_plComp,g_plRunAnim,"run-anim");
        }
        g_plBodyDone=true; g_plBodyTick=GetTickCount();
#if KWPROBE
        g_wpBodyTick=g_plBodyTick;   // probe-owned mirror (the probe code is compiled ~2000 lines above this)
        WpArmRequest(2);             // FK-24 arm site KWPARMAT=2 (the sketch's original; NOT the default)
#endif
        Markerf("[PL] *** init complete: body=%s; camera + WASD active ***\r\n", g_plComp?"BUILT":"none");
    }
    // ★★★ S99b — POSSESSION GUARD. The tutorial's own logic can UnPossess (and then destroy) the hero mid-hold.
    // Every per-hit call below takes g_wmHero / g_plComp as a raw pointer, so once that happens they are calling
    // natives on freed memory: S99b saw exactly that — a repeating 0xC0000005 reading 0xFFFF'FFFF'FFFF'FFFF with
    // `UnPossess` live in the fault context, one hit after the camera spawned, and eventually one fault escaped
    // the SEH guard and killed the process. LooksLikePtr cannot detect a freed object, but PC->Pawn can: if the
    // controller no longer possesses our hero, stand down permanently instead of poking a corpse.
    if(g_plBodyDone && LooksLikePtr(g_wmPC)){
        static uint32_t pawnOff=0xFFFFFFFF;
        if(pawnOff==0xFFFFFFFF){ pawnOff=PropOffsetSuper(ClassOf(g_wmPC),"Pawn"); if(pawnOff==0xFFFFFFFF) pawnOff=0x3F8; }
        uintptr_t cur=SafeReadable((void*)(g_wmPC+pawnOff),8)?*(uintptr_t*)(g_wmPC+pawnOff):0;
        if(cur!=g_wmHero){
            if(!g_plLostPawn){ g_plLostPawn=true;
                Markerf("[PL] *** UNPOSSESSED (PC->Pawn 0x%llX != hero 0x%llX) — standing down: no further native calls on the dead hero ***\r\n",
                        (unsigned long long)cur,(unsigned long long)g_wmHero); }
            return;
        }
    }
    if(g_plLostPawn) return;

    // ★ S94 iter10 — RE-ASSERT visibility EVERY hit + log the decisive coordinates.
    // WHY re-assert: SUPERVIVE hides heroes until deploy, and this build re-applies such state every frame (the same
    // pattern that makes the camera manager revert SetViewTargetWithBlend — proven S78/S93). A ONE-TIME unhide at init
    // would be silently undone, so the body would never render no matter how the component is built. Cheap per hit.
    if(g_plBodyDone && LooksLikePtr(g_wmHero)){
        static void* uhF=nullptr; static uintptr_t uhT=0,uhC=0; static uint32_t uhO=0xFFFFFFFF; static bool uhR=false;
        if(!uhR){ uhR=true; ResolveFuncSuper(ClassOf(g_wmHero),"SetActorHiddenInGame",&uhF,&uhT,&uhC); if(uhC) uhO=ParamOffset(uhC,"bNewHidden"); }
        if(uhT){ memset(g_pbuf,0,sizeof(g_pbuf)); if(uhO!=0xFFFFFFFF)((uint8_t*)g_pbuf)[uhO]=0; memset(g_rbuf,0,sizeof(g_rbuf)); CallNativeGuarded(uhF,uhT,uhC,(void*)g_wmHero,g_pbuf,g_rbuf); }
        if(LooksLikePtr(g_plComp)){
            static void* vF=nullptr; static uintptr_t vT=0,vC=0; static bool vR=false;
            if(!vR){ vR=true; ResolveFuncSuper(ClassOf(g_plComp),"SetVisibility",&vF,&vT,&vC); }
            if(vT){ memset(g_pbuf,0,sizeof(g_pbuf)); ((uint8_t*)g_pbuf)[0]=1; memset(g_rbuf,0,sizeof(g_rbuf)); CallNativeGuarded(vF,vT,vC,(void*)g_plComp,g_pbuf,g_rbuf); }
        }
        // DIAGNOSTIC every ~3s — the measurement that distinguishes occluded / mis-placed / off-camera / re-hidden:
        // hero world loc + its live bHidden byte, the component's WORLD loc (K2_GetComponentLocation) + its assigned
        // mesh ptr, and the camera's world loc. All read AFTER the game has had frames to revert things.
        static DWORD dlast=0; DWORD dnow=GetTickCount();
        if(dnow-dlast>=3000){ dlast=dnow;
            double hl[3]={0,0,0}; ActorLoc(g_wmHero,hl);
            double cl[3]={0,0,0}; if(LooksLikePtr(g_tcCam)) ActorLoc(g_tcCam,cl);
            uint32_t hb=PropOffsetSuper(ClassOf(g_wmHero),"bHidden"); int hbv=(hb!=0xFFFFFFFF&&SafeReadable((void*)(g_wmHero+hb),1))?*(uint8_t*)(g_wmHero+hb):-1;
            double wl[3]={0,0,0}; uint64_t skm=0; int cvis=-1;
            if(LooksLikePtr(g_plComp)){
                static void* gF=nullptr; static uintptr_t gT=0,gC=0; static bool gR=false;
                if(!gR){ gR=true; ResolveFuncSuper(ClassOf(g_plComp),"K2_GetComponentLocation",&gF,&gT,&gC); }
                if(gT){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallNativeGuarded(gF,gT,gC,(void*)g_plComp,g_pbuf,g_rbuf)){ double* R=(double*)g_rbuf; wl[0]=R[0]; wl[1]=R[1]; wl[2]=R[2]; } }
                uint32_t so=PropOffsetSuper(ClassOf(g_plComp),"SkeletalMeshAsset"); if(so==0xFFFFFFFF) so=PropOffsetSuper(ClassOf(g_plComp),"SkeletalMesh");
                if(so!=0xFFFFFFFF&&SafeReadable((void*)(g_plComp+so),8)) skm=*(uint64_t*)(g_plComp+so);
                uint32_t vo=PropOffsetSuper(ClassOf(g_plComp),"bVisible"); if(vo!=0xFFFFFFFF&&SafeReadable((void*)(g_plComp+vo),1)) cvis=*(uint8_t*)(g_plComp+vo);
            }
            int fowVis=-1;   // is the hero considered visible by the fog-of-war system? (the render gate)
            if(g_plFowVisThunk && LooksLikePtr(g_plFowCDO)){ memset(g_gsbuf,0,sizeof(g_gsbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                if(g_oFowTgt!=0xFFFFFFFF) *(uint64_t*)(g_gsbuf+g_oFowTgt)=(uint64_t)g_wmHero;
                if(!CallNativeGuarded(g_plFowVisFn,g_plFowVisThunk,g_plFowVisChild,(void*)g_plFowCDO,g_gsbuf,g_rbuf))
                    fowVis=(g_oFowVisRet!=0xFFFFFFFF)?g_gsbuf[g_oFowVisRet]:((uint8_t*)g_rbuf)[0]; }
            // ★ S98: the hero's LIVE root scale — the zero-scale bug's fingerprint. (0,0,0) here = invisible by geometry.
            { uint32_t rc=PropOffsetSuper(ClassOf(g_wmHero),"RootComponent");
              uintptr_t root=(rc!=0xFFFFFFFF&&SafeReadable((void*)(g_wmHero+rc),8))?*(uint64_t*)(g_wmHero+rc):0;
              uint32_t so=LooksLikePtr(root)?PropOffsetSuper(ClassOf(root),"RelativeScale3D"):0xFFFFFFFF;
              if(so!=0xFFFFFFFF&&SafeReadable((void*)(root+so),24)){ double* S=(double*)(root+so);
                  Markerf("[DIAG] hero root RelativeScale3D=(%.3f,%.3f,%.3f)%s\r\n",S[0],S[1],S[2],
                          (S[0]==0.0||S[1]==0.0||S[2]==0.0)?"  *** ZERO SCALE = INVISIBLE ***":"  (ok)"); } }
            Markerf("[DIAG] hero=(%.0f,%.0f,%.0f) bHidden=%d fowVisible=%d | comp=0x%llX world=(%.0f,%.0f,%.0f) mesh=0x%llX bVisible=%d | cam=(%.0f,%.0f,%.0f)\r\n",
                hl[0],hl[1],hl[2],hbv,fowVis,(unsigned long long)g_plComp,wl[0],wl[1],wl[2],(unsigned long long)skm,cvis,cl[0],cl[1],cl[2]);
            FowRegister(g_plComp,"re-assert");   // re-register in case the FOW collector drops unowned primitives
            if(KFOWATTR && fowVis==0) FowMakeVisionSource(g_wmHero);   // (route A dead; off by default)
            // ★ S96 verdict: once (a few seconds after the cheat spawn) report proxies for OUR hero vs any OTHER
            //   BP_HERO_ in the world (the cheat-spawned one). "SET" on the cheat one = the game's spawn path is the fix.
            if(g_plCheatDone){ static int rep=0;
                if(rep<2){ rep++;
                    ProxyReport(g_wmHero,"our-hero");
                    uintptr_t other=FindInstByClassExcept("BP_HERO_",g_wmHero);
                    if(LooksLikePtr(other)) ProxyReport(other,"cheat-hero");
                    else Marker("[PROXY] cheat-hero: no second BP_HERO_ found (spawn produced nothing)\r\n");
                } }
        }
    }
    DoTopDownCam();                  // spawn (once) + follow the top-down camera over the hero each hit
    if(!KNOMOVE) DoPuppet();         // WASD -> CMC velocity (g_puppetInit preset so it only drives, doesn't re-init)

    // ★★★ S99b — RUN ANIMATION + SELF-SCREENSHOT. Deliberately AFTER DoPuppet: DoPuppet zeroes velocity XY when no
    // key is held, so the self-driven walk must be written after it or it is erased on the same hit, and the
    // idle/run decision must read the FINAL velocity for this frame.
    if(g_plBodyDone && LooksLikePtr(g_plComp) && LooksLikePtr(g_wmCMC)){
        DWORD el = GetTickCount() - g_plBodyTick;
        // (1) SELF-DRIVEN WALK. The shim cannot press W, so to exercise (and photograph) the run animation with
        //     nobody at the keyboard it drives the velocity itself for one window. Outside that window the player
        //     is in full control via DoPuppet.
        if(KAUTOWALKMS>0 && el>=(DWORD)KAUTOWALKATMS && el<(DWORD)(KAUTOWALKATMS+KAUTOWALKMS)
           && SafeReadable((void*)(g_wmCMC+0xE8),16)){
            double yaw=kPupYawDeg*3.14159265358979/180.0;
            double* V=(double*)(g_wmCMC+0xE8);
            V[0]=__builtin_cos(yaw)*kPupSpeed; V[1]=__builtin_sin(yaw)*kPupSpeed;   // "W" in the camera's frame
            if(SafeReadable((void*)(g_wmCMC+0x328),24)){ double* A=(double*)(g_wmCMC+0x328); A[0]=V[0]*4.0; A[1]=V[1]*4.0; A[2]=0.0; }
            if(!g_plAwLogged){ g_plAwLogged=true; Marker("[ANIM] self-driven walk START (so the run anim can be captured with no human at the keyboard)\r\n"); }
        }
        // ★ S106 (FK-7) GC WATCHDOG — poll the two anim assets + the component once a second and SAY SO the
        // instant one dies. This is the instrument that turns "the session died at ~T+180 s, nobody knows why"
        // into a dated marker line naming the object. It cannot save the process (the game's own parallel anim
        // tick dereferences the dead asset every frame, on a worker thread this shim does not control) — the
        // rooting above is what prevents the death. Keep both: rooting is the fix, this is the proof.
        if(KGCROOT){
            static DWORD s_gcwLast=0; DWORD nw=GetTickCount();
            if(nw-s_gcwLast>=1000){ s_gcwLast=nw;
                if(LooksLikePtr(g_plIdleAnim)&&!GcAlive(g_plIdleAnim)){ Markerf("[GCW] *** IDLE ANIM 0x%llX WAS GARBAGE-COLLECTED (t=%lums after body build) ***\r\n",(unsigned long long)g_plIdleAnim,(unsigned long)(nw-g_plBodyTick)); g_plIdleAnim=0; g_plAnimDead=true; }
                if(LooksLikePtr(g_plRunAnim) &&!GcAlive(g_plRunAnim)){  Markerf("[GCW] *** RUN ANIM 0x%llX WAS GARBAGE-COLLECTED (t=%lums after body build) ***\r\n",(unsigned long long)g_plRunAnim,(unsigned long)(nw-g_plBodyTick)); g_plRunAnim=0;  g_plAnimDead=true; }
                if(LooksLikePtr(g_plComp)    &&!GcAlive(g_plComp)){     Markerf("[GCW] *** BODY COMPONENT 0x%llX WAS GARBAGE-COLLECTED (t=%lums after body build) ***\r\n",(unsigned long long)g_plComp,(unsigned long)(nw-g_plBodyTick)); g_plAnimDead=true; } } }
        // (2) IDLE <-> RUN swap off the live velocity. One native call, and only when the state actually flips.
        if(KRUNANIM && !g_plAnimDead && LooksLikePtr(g_plRunAnim) && LooksLikePtr(g_plIdleAnim)
           && SafeReadable((void*)(g_wmCMC+0xE8),16)){
            double* V=(double*)(g_wmCMC+0xE8);
            double sp=__builtin_sqrt(V[0]*V[0]+V[1]*V[1]);
            uintptr_t want=(sp>(double)KRUNSPEED)?g_plRunAnim:g_plIdleAnim;
            DWORD now=GetTickCount();
            if(want!=g_plCurAnim && now-g_plLastSwap>=400){   // rate-limited: never re-drive the instance every frame
                g_plLastSwap=now; PlayAnimOn(g_plComp,want,(want==g_plRunAnim)?"run":"idle"); }
        }
        // (3) THE GAME PHOTOGRAPHS ITSELF -> Saved/Screenshots/WindowsClient/. This is what makes the work
        //     verifiable without access to the desktop. Several shots on a schedule, because the top-down camera
        //     needs a few seconds to become the view target (the +3s shot in S99b caught the pre-blend view).
        //     ★ Each shot logs the hero AND camera world positions, so a hero missing from the picture can be
        //       told apart as "outside the frame" vs "in frame but not drawn" — S99b could not distinguish them.
        if(KSHOT){
            static const DWORD kAt[4]={ (DWORD)KSHOTMS, (DWORD)KSHOTMS+5000, (DWORD)KSHOTMS+11000,
                                        (DWORD)KAUTOWALKATMS+(DWORD)KAUTOWALKMS/2 };
            static const char* kTag[4]={ "idle1","idle2","idle3","run" };
            if(g_plShot<4 && el>=kAt[g_plShot]){
                int i=g_plShot++;
                double hl[3]={0,0,0}, cl[3]={0,0,0};
                ActorLoc(g_wmHero,hl); if(LooksLikePtr(g_tcCam)) ActorLoc(g_tcCam,cl);
                Markerf("[SHOT] %s @%.1fs hero=(%.0f,%.0f,%.0f) cam=(%.0f,%.0f,%.0f) anim=%s\r\n",
                        kTag[i],el/1000.0,hl[0],hl[1],hl[2],cl[0],cl[1],cl[2],
                        (g_plCurAnim==g_plRunAnim)?"run":"idle");
                RunConsole(L"HighResShot 1",kTag[i]);
            }
        }
    }
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
    // S90 FIX: was FindObjExact — but a SPAWNED hero instance is ALSO named "BP_HERO_Ronin_C", so in any session
    // where a hero already exists this grabbed the ACTOR and wrote it into PlayerState.HeroClass (a UClass* field).
    // FindClassExact is what ResolveSpawnPossess already uses for exactly this reason.
    g_heroClass=FindClassExact("BP_HERO_Ronin_C");   // the hero UCLASS; SpawnPlayer reads PlayerState.HeroClass
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
        uint32_t xfsz=XfSize();   // S106d: was an inline copy with a WRONG 0x50 fallback (see KXFORMFIX, L109)
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
        // ★★★ S98 THE BUG — SCALE3D WAS NEVER SET, SO THE HERO SPAWNED AT SCALE (0,0,0).
        // g_xform is memset to 0; the GetActorTransform fill is skipped live (xfThunk resolves to 0) and its zero-check
        // only scans bytes 0..0x38 anyway; both location fixes below write ONLY Translation(@0x20/28/30) and quat
        // W(@0x18). Scale3D(@0x38/0x40/0x48) therefore stayed 0 => a ZERO-SCALE actor: correct world position, working
        // possession, working CMC velocity puppet, camera follows it, bHiddenInGame=0, every render pointer populated —
        // and NOTHING DRAWN, at ground level or at Z=2200, with any mesh, because it is scaled to a point. That is the
        // entire "invisible hero" mystery. Every sibling spawn path already does this (L1062 "scale 1 (NOT 0)", L2024,
        // L2778); DoSpawnPossess — the path that spawns the hero we possess — never got the back-port.
        // ⚠ SCALE3D IS AT 0x40/0x48/0x50, **NOT** 0x38/0x40/0x48. FTransform in this build is the 16-byte-ALIGNED
        // 0x60 layout — Rotation@0x00 (0x20), Translation@0x20 (0x18 used + 8 PAD), Scale3D@0x40 (0x18 used + 8 pad).
        // Proof: xfsz = g_oBColl-g_oBXform = 0x70-0x10 = 0x60, and a first fix writing 0x38/0x40/0x48 produced a LIVE
        // root RelativeScale3D of (1.000,1.000,0.000) — i.e. it hit translation-pad, Scale.X, Scale.Y and left
        // Scale.Z ZERO. A mesh flattened to zero height is invisible from every angle.
        // ⚠ The same wrong offsets are used by the other spawn paths (L1062/L2024/L2778) and by BuildHeroBody.
        { double* S=(double*)(g_xform+0x40); double h0=S[0],h1=S[1],h2=S[2];
          if(S[0]==0.0) S[0]=1.0; if(S[1]==0.0) S[1]=1.0; if(S[2]==0.0) S[2]=1.0;
          Markerf("[GS] Scale3D@0x40 was (%.3f,%.3f,%.3f) -> now (%.1f,%.1f,%.1f) %s\r\n",h0,h1,h2,S[0],S[1],S[2],
                  (h0==0.0||h1==0.0||h2==0.0)?"*** ZERO-SCALE BUG FIXED ***":"(already non-zero)"); }
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
        // ★★★ S101 iter3 — run the ability-system wiring HERE, in the sp shim, rather than in play.
        //   Three consecutive iter2 attempts died inside play's ResolvePlay (its many full 188k-object scans are
        //   the most crash-prone part of the whole route) BEFORE reaching DoPlay, so the measurement never ran —
        //   while sp reported "[SP] done" cleanly every single time. sp already holds the possessed hero and the
        //   PC, which is everything WireAbilitySystem needs, so putting it here removes the flakiest dependency
        //   from the experiment.
        if(KWIREGAS && LooksLikePtr(g_spawnedPawn) && LooksLikePtr(g_pc2)) WireAbilitySystem(g_spawnedPawn,g_pc2);
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
#if KWPROBE
    // FK-24 probe threads. They only POLL until an arm request arrives (see KWPARMAT), so starting them
    // here is free; they must exist before VtResolve can fire the request. Neither ever runs on the game
    // thread, and the sweep's SuspendThread work is confined to WpThread.
    Markerf("[WP] FK-24 watchpoint probe COMPILED IN (KWPROBE=%d) -- see the [WP] cfg line for the full config\r\n",(int)KWPROBE);
    { HANDLE t1=CreateThread(nullptr,0,WpThread,nullptr,0,nullptr); if(t1)CloseHandle(t1);
      HANDLE t2=CreateThread(nullptr,0,WpSelfWatch,nullptr,0,nullptr); if(t2)CloseHandle(t2); }
#endif
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
    if(kRunMode==RM_SPAWNSEQ){
        Marker("[SEQ] spawn-sequencer mode: spawn BP_TutorialTrainingQuestSequencer_C so BeginPlay/ReadyToFire populates the quest chain\r\n");
        if(!ResolveSpawnSeq()){ Marker("[SEQ] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[SEQ] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[SEQ] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[SEQ] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<25000) Sleep(20);
        UninstallHook();
        Markerf("[SEQ] done (step=%d called=%ld hitsGT=%ld)\r\n",g_seqStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_SPAWNQUEST){
        Marker("[QST] spawn-quest mode: spawn the TrainingQuest_Basics_* ACTORS directly (S91) so the lesson chain exists\r\n");
        if(!ResolveSpawnQuest()){ Marker("[QST] resolve failed -> abort (see the discovery list above)\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[QST] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[QST] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[QST] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<45000) Sleep(20);   // N spawns x 400ms + 8s + 5s settles
        UninstallHook();
        Markerf("[QST] done (step=%d spawned=%d/%d poked=%d called=%ld hitsGT=%ld)\r\n",
            g_qStep,g_qOk,g_qToSpawn,g_qPoked,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_QUESTPLAY){
        Marker("[QP] quest-play mode: teleport the possessed hero into the WASD quest's own TargetTriggerBox (S91)\r\n");
        if(!ResolveQuestPlay()){ Marker("[QP] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[QP] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[QP] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[QP] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<45000) Sleep(20);
        UninstallHook();
        Markerf("[QP] done (step=%d try=%d called=%ld hitsGT=%ld)\r\n",g_qpStep,g_qpTry,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_BPCALL){
        Marker("[BPC] bp-call mode: run BLUEPRINT bytecode via FFrame.Code = UFunction.Script (S91 primitive)\r\n");
        if(!ResolveBPCall()){ Marker("[BPC] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[BPC] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[BPC] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[BPC] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<30000) Sleep(20);
        UninstallHook();
        Markerf("[BPC] done (step=%d called=%ld hitsGT=%ld)\r\n",g_bcStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_OBJDRIVE){
        Marker("[OD] obj-drive mode: advance the active WASD objective (physical teleport / OnWASDTriggerOverlap / ProgressObjective) (S92)\r\n");
        if(!ResolveObjDrive()){ Marker("[OD] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[OD] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[OD] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[OD] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<30000) Sleep(20);
        UninstallHook();
        Markerf("[OD] done (step=%d called=%ld hitsGT=%ld)\r\n",g_odStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_OBJCOMPLETE){
        Marker("[OC] obj-complete mode: force CurrentObjectiveCount->ObjectiveTarget + fire OnRep_CurrentObjectiveCount / EndTraining (S93)\r\n");
        if(!ResolveObjComplete()){ Marker("[OC] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[OC] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[OC] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[OC] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<30000) Sleep(20);
        UninstallHook();
        Markerf("[OC] done (step=%d called=%ld hitsGT=%ld)\r\n",g_ocStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_FIREOVERLAP){
        Marker("[FO] fire-overlap mode: gameplay OnWASDTriggerOverlap beat + ungated OnRep_TrainingActive completion closer (S93)\r\n");
        if(!ResolveFireOverlap()){ Marker("[FO] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[FO] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[FO] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[FO] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<30000) Sleep(20);
        UninstallHook();
        Markerf("[FO] done (step=%d called=%ld hitsGT=%ld)\r\n",g_foStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_DRIVECHAIN){
        Marker("[DC] drive-chain mode: walk the lesson chain (per lesson: activate quest -> GameStateTryStartTraining -> ungated closer) (S93)\r\n");
        if(!ResolveDriveChain()){ Marker("[DC] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[DC] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[DC] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[DC] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<60000) Sleep(20);
        UninstallHook();
        Markerf("[DC] done (lesson=%d phase=%d called=%ld hitsGT=%ld)\r\n",g_dcLesson,g_dcPhase,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_CAMERA){
        Marker("[CM] camera mode: enable the possessed hero's spring-arm/camera/actor ticks so the camera pulls back to top-down (S93)\r\n");
        if(!ResolveCamera()){ Marker("[CM] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[CM] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[CM] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[CM] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<20000) Sleep(20);
        UninstallHook();
        Markerf("[CM] done (step=%d called=%ld hitsGT=%ld)\r\n",g_cmStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_TOPDOWNCAM){
        Marker("[TC] top-down-cam mode: spawn a CameraActor + re-assert it as the view target (holds ~120s to view/screenshot) (S93)\r\n");
        if(!ResolveTopDownCam()){ Marker("[TC] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[TC] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[TC] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[TC] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<120000) Sleep(20);   // hold the cam ~120s
        UninstallHook();
        Markerf("[TC] done (spawned=%d hits=%ld called=%ld hitsGT=%ld)\r\n",(int)g_tcSpawned,(long)g_tcHit,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_MESHCAM){
        Marker("[MC] mesh+cam mode: build the hero's cosmetics mesh (ClientInitialComponentSetup via BP primitive) + hold top-down cam (S93)\r\n");
        if(!ResolveMeshCam()){ Marker("[MC] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[MC] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[MC] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[MC] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<120000) Sleep(20);
        UninstallHook();
        Markerf("[MC] done (meshTried=%d camSpawned=%d hits=%ld)\r\n",(int)g_mcMeshTried,(int)g_tcSpawned,(long)g_tcHit);
        return 0;
    }
    if(kRunMode==RM_DROPIN){
        Marker("[DI] drop-in mode: drive the DropPlane descent (SpawnPlane -> AddPlayerToDropPlane -> GetAutoDropLocation) so OnLanded activates the hero (S93)\r\n");
        if(!ResolveDropIn()){ Marker("[DI] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[DI] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[DI] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[DI] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<40000) Sleep(20);
        UninstallHook();
        Markerf("[DI] done (step=%d called=%ld hitsGT=%ld)\r\n",g_diStep,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_MAKEMESH){
        Marker("[MK] make-mesh mode: create a SkeletalMeshComponent on the hero + assign a body mesh (recreate visible hero from scratch) (S93)\r\n");
        if(!ResolveMakeMesh()){ Marker("[MK] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[MK] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[MK] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[MK] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<30000) Sleep(20);
        UninstallHook();
        Markerf("[MK] done (step=%d comp=0x%llX called=%ld)\r\n",g_mkStep,(unsigned long long)g_mkComp,(long)g_called);
        return 0;
    }
    if(kRunMode==RM_PLAY){
        Marker("[PL] play mode (S94): ground-teleport + build Ronin body from scratch + top-down cam + WASD puppet, in one shim (inject gft_ready_fix first)\r\n");
        if(!ResolvePlay()){ Marker("[PL] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[PL] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[PL] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[PL] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<600000) Sleep(20);   // ~10 min of playable hold, then release
        UninstallHook();
#if KWPROBE
        WpShutdown();   // disarm every thread / restore the page, drain the ring, print the one-line VERDICT
#endif
        if(SafeReadable((void*)(g_wmCMC+0xE8),16)){ double* V=(double*)(g_wmCMC+0xE8); V[0]=0.0; V[1]=0.0; }   // stop on exit
        Markerf("[PL] done (init=%d comp=0x%llX camSpawned=%d hits=%ld called=%ld hitsGT=%ld)\r\n",(int)g_plInit,(unsigned long long)g_plComp,(int)g_tcSpawned,(long)g_tcHit,(long)g_called,(long)g_hitsGT);
        return 0;
    }
    if(kRunMode==RM_TRAINING){
        Marker("[TRN] training mode: SetActive each BP_TrainingSkill_* on the LokiTrainingManager + StartTimers, then SpawnPlane + AddPlayerToDropPlane\r\n");
        if(!ResolveTraining()){ Marker("[TRN] resolve failed -> abort\r\n"); return 0; }
        g_pi=(uint8_t*)(g_modBase+kPiRva); if(!SafeReadable(g_pi,5)||memcmp(g_pi,kPiProlog,5)!=0){Marker("[TRN] FAIL PI prologue\r\n");return 4;}
        memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[TRN] FAIL BuildHook\r\n");return 5;}
        if(!InstallHook()){Marker("[TRN] FAIL InstallHook\r\n");return 6;}
        DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<20000) Sleep(20);   // 6 staged steps, one per game-thread hit
        UninstallHook();
        Markerf("[TRN] done (steps=%d called=%ld hitsGT=%ld)\r\n",g_tmStep,(long)g_called,(long)g_hitsGT);
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
