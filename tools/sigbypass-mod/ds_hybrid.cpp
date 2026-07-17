// ds_hybrid — SESSION 72: client-side HYBRID match-entry shim for the DEDICATED-SERVER-networked tutorial client.
//
// CONTEXT: the DS route (S70) puts the client in the LIVE tutorial world with a valid replicated LokiGameState —
// but the local player is a SPECTATOR: stock networked APlayerController, no Loki PC, no hero pawn, no drop-in
// (S71: the tutorial drop-in lives in a GAMEMODE component the stub can't run). This shim uses the S55 game-thread
// native-call primitive (hook ProcessInternal @base+0x13454A0, capture a live FFrame, call UFunction thunks
// directly) to drive the local player into a controllable hero — the pieces the DS session provides for free
// (live world + valid GameState) are what the force-open route lacked.
//
// PHASE 1 (this build, kMode=MODE_CENSUS): READ-ONLY census of the DS client — confirm the primitive fires in the
// networked client, find the local PlayerController / GameState / DefaultPawn, resolve the possession UFunctions,
// and locate a spawnable hero class + world context. Scopes Phase 2 (spawn+possess) with zero guessing.
//
// Build:  clang++ -shared -O2 ds_hybrid.cpp -o ds_hybrid.dll -lkernel32
// Inject (into the LIVE DS client): tools/inject/inject.exe mmap <PID> ds_hybrid.dll
// Marker: docs/ds-hybrid-marker.txt
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <cwchar>
#include <math.h>

static const char* kMarkerPath = "G:\\git\\Supervive Revival Project\\docs\\ds-hybrid-marker.txt";
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930, kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
constexpr int PERCHUNK=65536, ITEMSTRIDE=0x18;
constexpr uintptr_t CLASS_OFF=0x18, NAME_OFF=0x20, OUTER_OFF=0x28, UFUNC_FUNC=0xE0, UFUNC_CHILDPROPS=0x58;
constexpr uintptr_t UST_CHILDREN=0x50, UST_SUPER=0x48, FIELD_NEXT_UF=0x30, FIELD_NEXT=0x18, FPROP_OFFSET=0x44, FPROP_FLAGS=0x38;
// UStruct tail + UFunction bytecode (S80, live-verified on the UFUNCDUMP of BP_LokiHeroCharacter_C fns):
// PropertiesSize(int32)@+0x60, MinAlignment(int32)@+0x64, Script TArray@+0x68 {Data@+0x68, Num@+0x70, Max@+0x74}.
// Matches stock UE5.4 UStruct given SuperStruct@+0x48/Children@+0x50/ChildProperties@+0x58, and tools/re/find_func.py's
// long-standing "Script.Num@+0x70" convention. Needed to run BP bytecode (see MODE_BPCALL).
constexpr uintptr_t UST_PROPSIZE=0x60, UFUNC_SCRIPT=0x68, UFUNC_SCRIPTNUM=0x70;
constexpr uint64_t CPF_OutParm=0x100, CPF_ReturnParm=0x400;
constexpr uintptr_t FF_NODE=0x10, FF_OBJECT=0x18, FF_CODE=0x20, FF_LOCALS=0x28, FF_MRP=0x30, FF_MRPA=0x38, FF_MRPC=0x40, FF_OUTPARMS=0x80, FF_PROPCHAIN=0x88;
// S80: FFrame::FlowStack — REQUIRED for BP bytecode (ubergraphs are full of EX_PushExecutionFlow/EX_PopExecutionFlow).
// UE5 FFrame: ... MostRecentPropertyContainer@0x40, FlowStack@0x48, PreviousFrame@0x78, OutParms@0x80, PropChain@0x88,
// CurrentNativeFunction@0x90. FlowStack = TArray<CodeSkipSizeType, TInlineAllocator<8>> = {Inline[8*4=32]@+0x00,
// Secondary@+0x20, Num@+0x28, Max@+0x2C} = 0x30 bytes. Cross-check: 0x48+0x30 = 0x78/0x80/0x88 EXACTLY matches this
// project's long-established FF_OUTPARMS/FF_PROPCHAIN — the layout is confirmed by arithmetic, not guessed.
// A BP call MUST start with an EMPTY FlowStack: the graph's bail paths (EX_PopExecutionFlow) rely on "empty == return".
// Inheriting the captured template's stale stack makes them pop a GARBAGE offset and execute random bytecode.
constexpr uintptr_t FF_FLOWSTACK=0x48, FF_FLOW_SECONDARY=0x68, FF_FLOW_NUM=0x70, FF_FLOW_MAX=0x74,
                    FF_PREVFRAME=0x78, FF_CURNATIVEFN=0x90;
typedef void (*PFN_PE)(void* obj, void* func, void* parms);
typedef void (*PFN_THUNK)(void* Context, void* Frame, void* Result);

// MODE_CENSUS: read-only census. MODE_POSSESS_DP: ClientRestart(PC, DefaultPawn). MODE_SPAWN_HERO (Phase 3, the
// decisive test): spawn a BP_HERO pawn client-side via GameplayStatics deferred-spawn (WorldContext=ProgressionManager,
// hardcoded transform) + possess with the stock PC — does a hero even INITIALIZE + become controllable in the DS session?
// MODE_SPAWN_P2 (S79 moonshot Phase 2): spawn a LOCAL BP_LokiPlayerController_Dev_C + a BP_HERO_Assault_C (both
// classes proven RESIDENT by the Phase-1 load census) via the proven deferred-spawn path, then census the BP_Dev PC's
// drop-in machinery (DropPlaneComponentSetup/UpdateIsInDropPod/FinishDropPhaseHiding). NO swap/possess (Phase 3/4).
// Build:  clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_SPAWN_P2 ds_hybrid.cpp -o ds_hybrid_spawnp2.dll -lkernel32 -luser32
// MODE_SWAP_CENSUS (S79 moonshot Phase 3a): PURE READ-ONLY discovery of the controller-swap surface — the two engine
// offsets Phase 3 needs (ULocalPlayer->PlayerController + APlayerController->Player, neither a reflected UPROPERTY),
// found by pointer-equality scan against the live LocalPlayer + native PC. No hook, no spawn, no write => fully anti-
// tamper-safe.  Build: clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_SWAP_CENSUS ds_hybrid.cpp -o ds_hybrid_swapcensus.dll -lkernel32 -luser32
// MODE_SWAP (S79 moonshot Phase 3, MINIMAL): spawn a fresh BP_Dev PC (Phase-2-proven), then on the game thread repoint
// the local player's controller to it (L->PlayerController@+0x38 = devPC ; devPC->Player@+0x458 = L ; old PC->Player = 0),
// then MONITOR off-thread whether the game keeps the swap (control relinquished) or reverts/crashes (the fighting-session
// wall). Build: clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_SWAP ds_hybrid.cpp -o ds_hybrid_swap.dll -lkernel32 -luser32
// MODE_POSSESS (S79 moonshot Phase 4): on the ALREADY-swapped-in BP_Dev PC (L->PlayerController from Phase 3), spawn a
// BP_HERO_Assault_C, Possess it (C++ Possess via the exec thunk — locally-spawned actors have local authority), then
// drive the drop-in flags (FinishDropPhaseHiding -> PC+0xF28=1, UpdateIsInDropPod(false), DropPlaneComponentSetup) to
// try to flip spectator -> control. Requires the Phase-3 swap to be in place (persisted in the process).
// Build: clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_POSSESS ds_hybrid.cpp -o ds_hybrid_possess.dll -lkernel32 -luser32
// MODE_DEPLOY (S79 moonshot Phase 4b): on the possessed hero (L->PC->Pawn), try to make it VISIBLE + CONTROLLABLE —
// log hero+camera locations, SetActorHiddenInGame(false), EnableInput(PC), and RECON the hero's deploy/visibility
// UFunctions for the next step. Benign engine setters (low crash risk).
// Build: clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_DEPLOY ds_hybrid.cpp -o ds_hybrid_deploy.dll -lkernel32 -luser32
// MODE_UNHIDE (S79 moonshot Phase 4c): reveal the possessed hero — SetPredropHidden(false) (the SUPERVIVE pre-drop mesh
// gate found by Phase-4b recon) + SetViewTargetWithBlend(hero) so the camera follows it. Monitor the view target.
// Build: clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_UNHIDE ds_hybrid.cpp -o ds_hybrid_unhide.dll -lkernel32 -luser32
// MODE_NPOSSESS (S79 moonshot Phase 4d): the render/input pipeline follows the NATIVE PC (S73 LokiPlayerController), not
// our swapped-in BP_Dev PC. So: restore L->PlayerController = native PC, hand the native PC the hero (Possess, with a raw
// pawn<->controller wire fallback since the networked proxy PC may be authority-gated), SetPredropHidden(false), and point
// the native PC's camera at the hero. If the pipeline follows the native PC, we SEE + control the hero.
// Build: clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_NPOSSESS ds_hybrid.cpp -o ds_hybrid_npossess.dll -lkernel32 -luser32
// MODE_CAMFIX (S79 moonshot Phase 4e): the camera follows the hero but clips at its root (no framing). Census the hero's
// actual components (spring-arm / camera component that drive its top-down view) and pull the camera back (TargetArmLength).
// Pure off-thread read + one benign float write (no hook). Build: -DKMODE=MODE_CAMFIX -o ds_hybrid_camfix.dll
// MODE_DEPLOYRECON (S79 Phase 4f): the camera/input/HUD are deploy-gated custom systems. Read-only list of the deploy
// entry-point UFunctions on the hero + native PC classes (Deploy/Land/Restart/SetupPlayerInput/...). -DKMODE=MODE_DEPLOYRECON
// MODE_CRESTART (S79 Phase 4g): we raw-wired PC->Pawn = hero, bypassing the client-side possession setup. Run the setup we
// skipped — OnRep_Pawn (C++ pawn-change handler: camera+input for the new pawn) + ClientRestart(hero) + ClientSetHUD — to
// wire camera framing + input + HUD. -DKMODE=MODE_CRESTART
// MODE_CAMFRAME (S79 Phase 4h, visual capstone): offset the hero's CameraComponent up+back via
// K2_SetRelativeLocationAndRotation, re-applied repeatedly to hold vs a per-frame reset, so the camera stops clipping at
// the hero's root and frames the hunter top-down. -DKMODE=MODE_CAMFRAME
// MODE_STATERECON (S79→S80 deploy reconstruction): read-only enumeration of the hero's living-state / deploy control
// surface — native functions + properties gating mesh visibility (UpdateComponentVisibilityForLivingState reads a living
// state; a raw hero has none so its mesh stays hidden). Find the state field + setter. -DKMODE=MODE_STATERECON
// MODE_LIVINGSTATE (deploy reconstruction step 1): read the hero's LivingState, set it Alive + clear pre-drop, and fire
// the native visibility handlers (OnRep_LivingState / OnNewLivingState / OnCharacterVisibilityUpdated) to reveal the mesh.
// kAliveVal is the ELokiLivingState value for Alive (guess 1; iterate from the logged current value). -DKMODE=MODE_LIVINGSTATE
enum Mode { MODE_CENSUS=0, MODE_POSSESS_DP=1, MODE_SPAWN_HERO=2, MODE_SPECTATOR_CAM=3, MODE_DEBUGCAM=4, MODE_FREECAM=5, MODE_LOAD_CENSUS=6, MODE_SPAWN_P2=7, MODE_SWAP_CENSUS=8, MODE_SWAP=9, MODE_POSSESS=10, MODE_DEPLOY=11, MODE_UNHIDE=12, MODE_NPOSSESS=13, MODE_CAMFIX=14, MODE_DEPLOYRECON=15, MODE_CRESTART=16, MODE_CAMFRAME=17, MODE_STATERECON=18, MODE_LIVINGSTATE=19 };
#ifndef KALIVEVAL
#define KALIVEVAL 1
#endif
// MODE_MESHDIAG (deploy reconstruction step 2): read-only — find the hero's skeletal mesh component(s) and report whether
// a mesh asset is assigned + visibility, to tell "hidden but present" from "no mesh (cosmetics not loaded)". -DKMODE=MODE_MESHDIAG
constexpr int MODE_MESHDIAG=20;
// MODE_MESHMGRRECON (deploy step 3): read-only — dump LokiMeshManagerComponent's functions (+ hero cosmetics/setup fns),
// marked [N]ative/[BP], to find a native mesh-create before resorting to crash-prone BP ProcessEvent. -DKMODE=MODE_MESHMGRRECON
constexpr int MODE_MESHMGRRECON=21;
// MODE_COSMETICS (deploy step 4): call the native LokiHeroCharacter::RefreshCosmetics (+OnRep_CosmeticsAssetID) to BUILD
// the character mesh a raw hero never created, re-assert Alive+visibility, then re-count skeletal meshes. -DKMODE=MODE_COSMETICS
constexpr int MODE_COSMETICS=22;
// MODE_COSMENUM (deploy step 5): enumerate cosmetics PrimaryAssetTypes via GetPrimaryAssetIdList (Phase-1 primitive) and
// log the IDs + resolved names, flagging Assault/Default — to find the character CosmeticsAssetID to assign. -DKMODE=MODE_COSMENUM
constexpr int MODE_COSMENUM=23;
// MODE_SETCOSMETIC (deploy step 6): build FPrimaryAssetId "HeroCosmeticsBundle:AssaultDefault", async-load it, write it to
// the hero's CosmeticsAssetID field, and call RefreshCosmetics (re-fired as the async load lands) to build the character
// mesh. kSkin overridable. -DKMODE=MODE_SETCOSMETIC  [-DKSKIN='L"HeroCosmeticsBundle:AssaultDefault"']
constexpr int MODE_SETCOSMETIC=24;
#ifndef KSKIN
#define KSKIN L"HeroCosmeticsBundle:AssaultDefault"
#endif
// MODE_BPDEPLOY (deploy step 7): use ProcessEvent to call the BP deploy-setup fns (ClientInitialComponentSetup /
// BP_PostSetupCosmetics) that create the cosmetics CONTROLLER, then RefreshCosmetics builds the mesh. -DKMODE=MODE_BPDEPLOY
constexpr int MODE_BPDEPLOY=25;
// ProcessEvent (base+0x12C5A10, S54-validated) runs a BP UFunction's bytecode. The direct-thunk primitive can't call
// BP-folded fns (their Func == ProcessInternal); ProcessEvent is the correct path. Runs on the game thread (in OnPI).
constexpr uintptr_t kProcEventRva=0x12C5A10;
// MODE_CONTEXT (deploy step 8): the BP deploy fns fault because the hero has no PlayerState. Give it the native PC's
// replicated PlayerState (+ LocalPlayerState), wire it (OnRep_PlayerState), then retry the BP setup. -DKMODE=MODE_CONTEXT
constexpr int MODE_CONTEXT=26;
// MODE_DEPLOYEVT (deploy step 9): with PlayerState set, call the game's own deploy ORCHESTRATOR BP events (ReceiveRestarted /
// OnLocalPlayer_CharacterSpawned / RefreshLocalControl / TryLocalControlSetup) that run the init in order. -DKMODE=MODE_DEPLOYEVT
constexpr int MODE_DEPLOYEVT=27;
// MODE_VTDUMP (tool validation): dump the hero/PC/GameState vtables + find the slot matching my ProcessEvent RVA
// (base+0x12C5A10) to confirm it's actually ProcessEvent — a wrong RVA would make every BP call fault. -DKMODE=MODE_VTDUMP
constexpr int MODE_VTDUMP=28;
// MODE_BPTEST (tool validation 2): call a BP getter (GetBaseCosmeticsController) via ProcessEvent + read its return; if it
// == the known controller, ProcessEvent BP-calls WORK (so the deploy faults are real context). -DKMODE=MODE_BPTEST
constexpr int MODE_BPTEST=29;
// MODE_BPTEST2 (tool validation 3): raw-remove the PI hook, THEN call the BP getter via ProcessEvent — if it now returns
// the controller, the earlier faults were PI-hook re-entrancy, not the functions → the deploy path REOPENS. -DKMODE=MODE_BPTEST2
constexpr int MODE_BPTEST2=30;
// MODE_BPTEST3 (tool validation 4): call a NATIVE member fn (GetCosmeticsController) via ProcessEvent + compare to its
// direct-thunk return — isolates a ProcessEvent MECHANISM bug from BP-bytecode/context faults. -DKMODE=MODE_BPTEST3
constexpr int MODE_BPTEST3=31;
// MODE_UFUNCDUMP (BP-invoker prep): dump a BP UFunction's fields to find UStruct::PropertiesSize + UFunction::Script offsets
// (needed to build a proper FFrame for a direct ProcessInternal call). -DKMODE=MODE_UFUNCDUMP
constexpr int MODE_UFUNCDUMP=32;
// MODE_BPCALL (S80): call BP-folded UFunctions CORRECTLY. TWO independent tool bugs faked the "deploy context wall"
// that S79 called definitive — neither is a wall, and the BP deploy fns were NEVER ACTUALLY EXECUTED:
//  (1) ★ CallNative sets FFrame.Code=0. Harmless for a native thunk (it ignores Code), but a BP fn's Func IS
//      ProcessInternal, which executes bytecode from *Stack.Code => Code=0 is a NULL DEREF. Every "BP fn faulted"
//      result was this. FIX (one line): Code = UFunction->Script.GetData() @+0x68, Locals = a zeroed
//      PropertiesSize(@+0x60) buffer. Func is ALREADY ProcessInternal, so no new call target is needed.
//  (2) kProcEventRva (base+0x12C5A10) is NOT ProcessEvent — S80 live disasm: its prologue saves only rcx->rdi and
//      rdx->r14 and NEVER touches r8, so it's a 2-arg fn that ignores the Parms buffer entirely (it guards recursion
//      on `this` via a TLS list and tail-calls vtable slot 58). The S54 "slot 56 = ProcessEvent" id is wrong, which
//      is why routing BP calls through it faulted even for a NATIVE member (MODE_BPTEST3) and looked "neutered".
// Corollary from the live UFunction survey: `ReceiveRestarted` (Pawn) is an EMPTY BlueprintImplementableEvent stub
// (Script=0, PropertiesSize=0) that BP_LokiHeroCharacter_C never overrides — calling it is a no-op BY DESIGN, not a
// context fault. The real deploy fns DO carry bytecode on BP_LokiHeroCharacter_C: ClientInitialComponentSetup
// (Script=88), GetBaseCosmeticsController (121), BP_PostSetupCosmetics / TryLocalControlSetup / RefreshLocalControl (18).
// Validation is self-checking: GetBaseCosmeticsController's bytecode calls the NATIVE GetCosmeticsController and stores
// it in local CallFunc_GetCosmeticsController_ReturnValue @+0x8, so locals[0x8] MUST equal the direct-thunk controller.
// The deploy chain only runs if that gate passes (a deploy result on a broken invoker would be meaningless). -DKMODE=MODE_BPCALL
constexpr int MODE_BPCALL=33;
// MODE_DEVSWAP (S80): the ONE untested variable. S79 4g drove ClientRestart on the NATIVE `LokiPlayerController` — which
// S80q proved owns **ZERO** input events (all 45 `InpActEvt_*_K2Node_InputActionEvent` live on
// BP_LokiPlayerController_C(39) + _Code_C(6), which `BP_LokiPlayerController_Dev_C` INHERITS). So 4g's "fires clean, no
// effect" was ClientRestart on a PC with nothing to restart. This swaps the LocalPlayer to the EXISTING S79-spawned
// BP_Dev PC and drives ClientRestart THERE. `ClientRestart` is a real reflected UFunction (native+0x3C5F990, ParmsSize=8,
// APawn* NewPawn) => the direct-thunk primitive calls it; no `SetPlayer` RE needed (4 vtable candidates refuted, S80s/u).
// APlayerController::ClientRestart_Implementation -> AcknowledgePossession -> SetPawn -> Pawn->PawnClientRestart() ->
// SetupPlayerInputComponent + EnableInput, i.e. the input half. Camera may still be absent (no PlayerCameraManager on a
// GameplayStatics-spawned PC — that's what SetPlayer's SpawnPlayerCameraManager would have done), so read BOTH.
// Swap offsets are S79-3a proven + S80s re-confirmed: LocalPlayer->PlayerController @+0x38, PC->Player @+0x458.
constexpr int MODE_DEVSWAP=34;
// MODE_MOVETEST (S80): THE decisive split. S80's devswap gave camera + a PC owning the 45 InpActEvt_* ACTION events, but
// the user's screen check says NO WASD. My error: those 137 `inputaction` hits are all DISCRETE ACTIONS (Sprint/Ping/
// Use/ToggleMap) — none is movement. In UE legacy input WASD is an AXIS. The real movement surface (find_func needles
// inpaxisevt/moveforward/moveright) is only 4 fns: **LokiPlayerController::MoveForward / ::MoveRight (NATIVE)** and
// DefaultPawn's pair. Native UFunctions ⇒ the direct-thunk primitive calls them with NO key binding / input system /
// SetPlayer needed. This calls MoveForward(pc, 1.0) on the live L->PlayerController and watches the hero's location.
//   hero MOVES  => the movement path is intact; the ONLY gap is key -> axis binding.
//   hero STILL  => movement is gated deeper (CharacterMovementComponent state / authority / deploy machinery),
//                  and the diagnostics below (MovementMode, bIsOnGround, velocity, Controller/Pawn wiring) say which.
// Read-mostly: the only writes are the MoveForward/MoveRight calls themselves (the game's own movement entry points).
constexpr int MODE_MOVETEST=35;
static const unsigned kMoveMode = 5;   // EMovementMode for MODE_MOVETEST: 1=MOVE_Walking 3=MOVE_Falling 5=MOVE_Flying
// S79 moonshot Phase 1 (force-load hero assets + re-census) builds with `-DKMODE=MODE_LOAD_CENSUS`; the shipped
// spectator-cam build stays MODE_SPECTATOR_CAM. Compile-time override so neither build clobbers the other.
#ifndef KMODE
#define KMODE MODE_SPECTATOR_CAM
#endif
static const int kMode = KMODE;
// S77 anti-tamper DODGE test (catalog_store_fix pattern): the permanent ProcessInternal .text hook is what the
// code-integrity check catches. catalog_store_fix survives long-term because it leaves NO persistent .text mod
// (self-restores in ~6s + heap pokes only). PORT: run the overlay-hide for a SHORT window then UNINSTALL the hook
// and let the process run clean. kSpectatorHookMs = how long to hold the hook (overlay-hide) before uninstalling.
// kEnableTranslation gates the movement block (input-poll + K2_SetActorLocation) OFF for a clean pure-overlay-hide
// survival test — movement needs continuous game-thread exec (a data/vtable hook, not a .text hook) = phase 2.
// S77 DEFAULT = the durable stable-view dodge (proven): one-shot overlay-hide ~20s then uninstall (survives
// long-term). kEnableTranslation=true adds WASD movement DURING the hook window, but that requires holding the
// .text hook the whole time — and a standing hook is UNRELIABLE (survived 20s overlay-only, but a 30s
// movement window crashed on the integrity check mid-window). Continuous movement needs a NON-.text continuous
// mechanism (data/vtable hook, or transient-per-step) — see the doc's phase-3 note. Leave translation OFF for
// the durable-view default; the pawn+K2_SetActorLocation resolution + DoSpectatorCam movement path are kept.
static const bool     kEnableTranslation = false;
static const unsigned kSpectatorHookMs   = 8000;    // overlay-hide window (shortened from 20s: less standing-hook
                                                    // exposure -> fewer anti-tamper catches; the hide is one-shot so
                                                    // a few seconds suffices, then uninstall)
// S78 refinement #3 — feel: base horizontal/vertical speeds (per step; Sleep(8) => ~90 steps/sec) + a soft Z clamp
// so holding UP no longer rockets the cam into the skybox (which also aggravates the far-away jaggedness, #2).
// SHIFT boosts. Values are generous — the clamp only catches the runaway (S77 reached Z=94500), not legit high views.
// S78 live feedback (S78a): 85/step read as "hyper fast" — cut hard for a controllable fly-cam. Shift boosts
// when you want to cover ground. Step rate is ~40-90/s, so 26/step ~= 1000-2300 u/s (map is ~15000 u wide).
static const double   kMoveSpeed   = 26.0;    // horizontal units/step (was 85 — too fast)
static const double   kMoveSpeedV  = 18.0;    // vertical units/step (was 50)
static const double   kBoostMul    = 4.0;     // hold SHIFT for fast travel
static const double   kZMax        = 22000.0; // soft ceiling (skybox guard)
static const double   kZMin        = -4000.0; // soft floor

static uintptr_t g_modBase=0;
static volatile PFN_PE g_tramp=nullptr;
static uint8_t* g_pi=nullptr; static uint8_t g_stolen[5]={0}; static uint8_t* g_stub=nullptr;
static volatile long g_inHook=0,g_done=0,g_hitsGT=0; static DWORD g_gameTid=0;
static uint8_t g_template[0x180]={0}, g_myframe[0x180]={0};

static void Marker(const char* m){HANDLE h=CreateFileA(kMarkerPath,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return;DWORD w=0;WriteFile(h,m,(DWORD)strlen(m),&w,nullptr);CloseHandle(h);}
static void Markerf(const char* f,...){char b[640];va_list a;va_start(a,f);_vsnprintf_s(b,sizeof(b),_TRUNCATE,f,a);va_end(a);Marker(b);}
static bool SafeReadable(const void* a,size_t sz){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(a,&m,sizeof(m)))return false;if(!(m.State&MEM_COMMIT))return false;if(m.Protect&(PAGE_NOACCESS|PAGE_GUARD))return false;return (uintptr_t)a+sz<=(uintptr_t)m.BaseAddress+m.RegionSize;}
static volatile long g_crashSeq=0;
static LONG CALLBACK CrashVEH(EXCEPTION_POINTERS* ep){
    DWORD code=ep->ExceptionRecord->ExceptionCode; bool fatal=code==0xC0000005||code==0xC0000409||code==0xC000001D||code==0xC0000374;
    if(!fatal)return EXCEPTION_CONTINUE_SEARCH; long s=InterlockedIncrement(&g_crashSeq); if(s>6)return EXCEPTION_CONTINUE_SEARCH;
    uint64_t rip=ep->ContextRecord->Rip; Markerf("[VEH] fatal 0x%lX RIP=0x%llX rva=0x%llX\r\n",code,(unsigned long long)rip,(unsigned long long)(rip>g_modBase&&rip<g_modBase+0xC000000?rip-g_modBase:0));
    return EXCEPTION_CONTINUE_SEARCH;
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
static bool ClassName(uintptr_t obj,char* out,int cap){ uintptr_t c=ClassOf(obj); if(!c)return false; return GetFNameStr(NameId(c),out,cap); }
static bool ObjName(uintptr_t obj,char* out,int cap){ return GetFNameStr(NameId(obj),out,cap); }

// Iterate GUObjectArray, invoking cb(obj) for each valid object. cb returns true to stop.
template<class F> static void ForEachObject(F cb){
    uintptr_t oo=g_modBase+kObjObjectsRva; if(!SafeReadable((void*)oo,0x18))return;
    uintptr_t objectsPtr=*(uintptr_t*)oo; int32_t numEl=*(int32_t*)(oo+0x14);
    if(!LooksLikePtr(objectsPtr)||numEl<=0||numEl>8000000)return; int numChunks=(numEl+PERCHUNK-1)/PERCHUNK;
    for(int ci=0;ci<numChunks;ci++){ if(!SafeReadable((void*)(objectsPtr+ci*8),8))break; uintptr_t chunk=*(uintptr_t*)(objectsPtr+ci*8); if(!LooksLikePtr(chunk))continue; int cnt=(ci==numChunks-1)?(numEl-ci*PERCHUNK):PERCHUNK;
        for(int j=0;j<cnt;j++){ uintptr_t item=chunk+(uintptr_t)j*ITEMSTRIDE; if(!SafeReadable((void*)item,8))continue; uintptr_t obj=*(uintptr_t*)item; if(!LooksLikePtr(obj))continue; if(cb(obj))return; } }
}
// First non-CDO instance whose class name == exact.
static uintptr_t FindInstExactClass(const char* exact){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ char cn[128]; if(!ClassName(o,cn,sizeof(cn)))return false; if(strcmp(cn,exact)!=0)return false; char on[128]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false; out=o; return true; }); return out; }
// First non-CDO instance whose class name CONTAINS sub.
static uintptr_t FindInstClassSub(const char* sub){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ char cn[128]; if(!ClassName(o,cn,sizeof(cn)))return false; if(!strstr(cn,sub))return false; char on[128]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false; out=o; return true; }); return out; }
// First object whose OWN name starts with pre and ends with suf (e.g. "BP_HERO_", "_C") — a UClass.
static uintptr_t FindObjNamePreSuf(const char* pre,const char* suf){ uintptr_t out=0; size_t lp=strlen(pre),ls=strlen(suf); ForEachObject([&](uintptr_t o)->bool{ char on[160]; if(!ObjName(o,on,sizeof(on)))return false; size_t l=strlen(on); if(l<lp+ls)return false; if(strncmp(on,pre,lp)!=0)return false; if(strcmp(on+l-ls,suf)!=0)return false; out=o; return true; }); return out; }
// First object whose OWN name == want exactly.
static uintptr_t FindObjExact(const char* want){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ if(NameIs(o,want)){ out=o; return true; } return false; }); return out; }
// Does cls's SuperStruct chain (@+0x48) contain a class whose name contains `sub`?
static bool SuperChainHas(uintptr_t cls,const char* sub){ int g=0; while(LooksLikePtr(cls)&&g++<16){ char cn[128]; if(GetFNameStr(NameId(cls),cn,sizeof(cn))&&strstr(cn,sub))return true; cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0; } return false; }
// Find a real HERO PAWN class: name "BP_HERO_<X>_C" whose ancestry includes LokiCharacter (excludes projectiles/UI).
static uintptr_t FindHeroPawnClass(){ uintptr_t out=0; ForEachObject([&](uintptr_t o)->bool{ char on[160]; if(!ObjName(o,on,sizeof(on)))return false; size_t l=strlen(on); if(l<11)return false; if(strncmp(on,"BP_HERO_",8)!=0)return false; if(strcmp(on+l-2,"_C")!=0)return false; if(strstr(on,"Projectile")||strstr(on,"Cosmetic")||strstr(on,"Ability"))return false; char mc[64]; if(!ClassName(o,mc,sizeof(mc))||!strstr(mc,"BlueprintGeneratedClass"))return false; if(!SuperChainHas(o,"LokiCharacter")&&!SuperChainHas(o,"LokiHeroCharacter"))return false; out=o; return true; }); return out; }

// Resolve a UFunction by name on a class (+ SuperStruct chain @+0x48). Reports thunk (Func@+0xE0) + childProps.
static void ResolveFunc(uintptr_t cls,const char* name,void** fn,uintptr_t* thunk,uintptr_t* child){
    int g=0; while(LooksLikePtr(cls)&&g++<14){
        uintptr_t f=SafeReadable((void*)(cls+UST_CHILDREN),8)?*(uintptr_t*)(cls+UST_CHILDREN):0; int i=0;
        while(LooksLikePtr(f)&&i++<800){ if(NameIs(f,name)){ *fn=(void*)f;
                if(SafeReadable((void*)(f+UFUNC_FUNC),8)){uintptr_t th=*(uintptr_t*)(f+UFUNC_FUNC); if(LooksLikePtr(th))*thunk=th;}
                if(SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)){uintptr_t cp=*(uintptr_t*)(f+UFUNC_CHILDPROPS); if(LooksLikePtr(cp))*child=cp;} return; }
            f=SafeReadable((void*)(f+FIELD_NEXT_UF),8)?*(uintptr_t*)(f+FIELD_NEXT_UF):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static void ReportFunc(uintptr_t cls,const char* name){ void* fn=0; uintptr_t th=0,cp=0; ResolveFunc(cls,name,&fn,&th,&cp);
    if(fn) Markerf("[FN]   %-26s fn=0x%llX thunk=0x%llX childProps=0x%llX\r\n",name,(unsigned long long)(uintptr_t)fn,(unsigned long long)th,(unsigned long long)cp);
    else   Markerf("[FN]   %-26s NOT FOUND\r\n",name);
}
// Offset_Internal@+0x44 of the named param in a UFunction's ChildProperties chain (Next@+0x18).
static uint32_t ParamOffset(uintptr_t childHead,const char* name){
    uintptr_t f=childHead; int i=0;
    while(LooksLikePtr(f)&&i++<40){ if(NameIs(f,name)){ return SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF; } f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
    return 0xFFFFFFFF;
}
// The S55 game-thread native-call primitive: call a UFunction thunk with a prepared params buffer.
static uint8_t g_pbuf[256]={0}, g_rbuf[64]={0};
// S58/S74 OUT/ref-param marshalling (ported from tutorial_launch): build an FOutParmRec chain for every CPF_OutParm
// param (PropAddr into the Locals buffer) and set FFrame.OutParms@+0x80. Without this the exec thunk walks a null/stale
// OutParms for by-ref/out params (e.g. const FTransform& in BeginDeferredActorSpawnFromClass) and crashes — the exact
// S72 wall #1 that killed the client-side hero spawn.
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
static void CallNative(void* func, uintptr_t thunk, uintptr_t childProps, void* context, void* paramsBuf, void* resultBuf){
    memcpy(g_myframe, g_template, sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=func;
    *(void**)(g_myframe+FF_OBJECT)=context;
    *(uint64_t*)(g_myframe+FF_CODE)=0;
    *(void**)(g_myframe+FF_LOCALS)=paramsBuf;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)childProps;
    BuildOutParms(childProps,(uint8_t*)paramsBuf);   // S74: FFrame.OutParms chain for by-ref/out params (fixes the S72 spawn crash)
    ((PFN_THUNK)thunk)(context, g_myframe, resultBuf);
}

// ---- hook plumbing (proven in tutorial_launch.cpp) ----
static uint8_t* NearAlloc(uintptr_t anchor,size_t sz){for(uintptr_t off=0x10000;off<0x7F000000ull;off+=0x10000){uintptr_t cands[2]={(anchor+off)&~0xFFFFull,(anchor>off?(anchor-off):0)&~0xFFFFull};for(int i=0;i<2;i++){if(!cands[i])continue;void* p=VirtualAlloc((void*)cands[i],sz,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(p){intptr_t d=(intptr_t)p-(intptr_t)anchor;if(d>(intptr_t)-0x7F000000&&d<(intptr_t)0x7F000000)return (uint8_t*)p;VirtualFree(p,0,MEM_RELEASE);}}}return nullptr;}
struct Emit{uint8_t* w;}; static void EB(Emit&e,uint8_t b){*e.w++=b;} static void EU32(Emit&e,uint32_t v){memcpy(e.w,&v,4);e.w+=4;} static void EU64(Emit&e,uint64_t v){memcpy(e.w,&v,8);e.w+=8;}
extern "C" void OnPI(void* ctx, void* frame, void* res);
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
// S77 phase-3 smoothness: FAST hook toggle — only suspend/check the GAME THREAD (ProcessInternal is
// game-thread-dominant), not all ~135 threads. The all-threads SafeWrite took ~seconds/call (400 retries x
// suspend-all), making the per-step transient movement jump every 3-5s. This makes install/uninstall ~us so
// movement is smooth. Small residual risk: an off-thread ProcessInternal in the 5-byte prologue during the write
// (rare) — acceptable for a spectator fly-cam. Used only by the movement loop, not the one-shot overlay-hide.
static HANDLE g_gtHandle=0;
static bool SafeWriteFast(uint8_t* dst,const uint8_t* src,size_t len){
    if(!g_gtHandle) g_gtHandle=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT,FALSE,g_gameTid);
    HANDLE gt=g_gtHandle; uintptr_t lo=(uintptr_t)dst,hi=(uintptr_t)dst+len;
    for(int a=0;a<200;a++){ if(gt)SuspendThread(gt); bool unsafe=false; CONTEXT c; c.ContextFlags=CONTEXT_CONTROL;
        if(gt&&GetThreadContext(gt,&c)&&c.Rip>=lo&&c.Rip<hi) unsafe=true;
        if(!unsafe){ DWORD op=0; if(VirtualProtect(dst,len,PAGE_EXECUTE_READWRITE,&op)){ memcpy(dst,src,len); DWORD d=0; VirtualProtect(dst,len,op,&d); FlushInstructionCache(GetCurrentProcess(),dst,len); if(gt)ResumeThread(gt); return true; } }
        if(gt)ResumeThread(gt); Sleep(0); }
    return false;
}
static bool InstallHookFast(){ if(!g_pi||!g_stub)return false; int32_t rel=(int32_t)((intptr_t)g_stub-((intptr_t)g_pi+5)); uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)}; return SafeWriteFast(g_pi,p,5); }
static void UninstallHookFast(){ if(g_pi)SafeWriteFast(g_pi,g_stolen,5); }
static DWORD WaitTid(DWORD to){uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);DWORD dl=GetTickCount()+to;while(GetTickCount()<dl){if(SafeReadable(s,4)){uint32_t v=0;memcpy(&v,s,4);if(v)return v;}Sleep(20);}return 0;}

// ---- PHASE 1: census ----
static void Census(){
    Marker("[CENSUS] === DS-networked tutorial client census ===\r\n");

    // Local PlayerController: the stub uses stock APlayerController, so the networked PC's class is exactly
    // "PlayerController". Report it + whether any Loki PC exists.
    uintptr_t pc=FindInstExactClass("PlayerController");
    if(pc){ char on[128]="?"; ObjName(pc,on,sizeof(on)); Markerf("[CENSUS] stock PlayerController: obj=0x%llX name=%s\r\n",(unsigned long long)pc,on);
        // resolve possession UFunctions on its class chain
        uintptr_t cls=ClassOf(pc);
        ReportFunc(cls,"Possess"); ReportFunc(cls,"ClientRestart"); ReportFunc(cls,"AcknowledgePossession");
        ReportFunc(cls,"ServerRestartPlayer"); ReportFunc(cls,"ClientSetHUD"); ReportFunc(cls,"SetPawn"); ReportFunc(cls,"OnPossess");
    } else Marker("[CENSUS] no stock PlayerController instance found\r\n");
    uintptr_t lokiPc=FindInstClassSub("LokiPlayerController");
    if(lokiPc){ char cn[128]="?",on[128]="?"; ClassName(lokiPc,cn,sizeof(cn)); ObjName(lokiPc,on,sizeof(on)); Markerf("[CENSUS] LIVE Loki PC present: obj=0x%llX cls=%s name=%s\r\n",(unsigned long long)lokiPc,cn,on); }
    else Marker("[CENSUS] no live LokiPlayerController actor (only the stock networked PC)\r\n");

    // GameState
    uintptr_t gs=FindInstExactClass("LokiGameState");
    if(!gs) gs=FindInstClassSub("LokiGameState");
    if(gs){ char cn[128]="?",on[128]="?"; ClassName(gs,cn,sizeof(cn)); ObjName(gs,on,sizeof(on)); Markerf("[CENSUS] GameState: obj=0x%llX cls=%s name=%s\r\n",(unsigned long long)gs,cn,on); }
    else Marker("[CENSUS] no LokiGameState instance\r\n");

    // The replicated DefaultPawn from the stub
    uintptr_t dp=FindInstExactClass("DefaultPawn");
    if(dp){ char on[128]="?"; ObjName(dp,on,sizeof(on)); Markerf("[CENSUS] DefaultPawn: obj=0x%llX name=%s\r\n",(unsigned long long)dp,on); }
    else Marker("[CENSUS] no DefaultPawn instance\r\n");

    // A spawnable hero class (BP_HERO_<X>_C) — target for Phase 2 spawn.
    uintptr_t heroCls=FindObjNamePreSuf("BP_HERO_","_C");
    if(heroCls){ char on[160]="?"; ObjName(heroCls,on,sizeof(on)); char ccn[128]="?"; ClassName(heroCls,ccn,sizeof(ccn)); Markerf("[CENSUS] hero class: obj=0x%llX name=%s (meta=%s)\r\n",(unsigned long long)heroCls,on,ccn); }
    else Marker("[CENSUS] no BP_HERO_*_C class found\r\n");

    // World context candidates for spawning: a GameInstance / World. Report a ProgressionManager (proven world ctx).
    uintptr_t pm=FindInstClassSub("ProgressionManager");
    if(pm){ char on[128]="?"; ObjName(pm,on,sizeof(on)); Markerf("[CENSUS] ProgressionManager (world ctx): obj=0x%llX name=%s\r\n",(unsigned long long)pm,on); }

    Marker("[CENSUS] === done ===\r\n");
}

// ---- PHASE 2: possess the replicated DefaultPawn client-side ----
// Resolved OFF the game thread (in Worker) to keep the hook's game-thread work minimal (a big object walk inside
// the PI hook stalls the game thread). The primitive CALL itself must run on the game thread (in OnPI).
static uintptr_t g_pc=0, g_dp=0; static void* g_crFn=0; static uintptr_t g_crThunk=0, g_crChild=0; static uint32_t g_crPawnOff=0xFFFFFFFF;
static bool ResolvePossessDP(){
    g_pc=FindInstExactClass("PlayerController");
    g_dp=FindInstExactClass("DefaultPawn");
    if(!g_pc||!g_dp){ Markerf("[POSSESS] resolve FAIL pc=0x%llX dp=0x%llX\r\n",(unsigned long long)g_pc,(unsigned long long)g_dp); return false; }
    ResolveFunc(ClassOf(g_pc),"ClientRestart",&g_crFn,&g_crThunk,&g_crChild);
    if(!g_crFn||!g_crThunk||!g_crChild){ Marker("[POSSESS] ClientRestart resolve FAIL\r\n"); return false; }
    // ClientRestart(APawn* NewPawn) — find the pawn param offset in the params layout.
    g_crPawnOff=ParamOffset(g_crChild,"NewPawn"); if(g_crPawnOff==0xFFFFFFFF) g_crPawnOff=ParamOffset(g_crChild,"P"); if(g_crPawnOff==0xFFFFFFFF) g_crPawnOff=0;
    Markerf("[POSSESS] resolved pc=0x%llX dp=0x%llX crThunk=0x%llX crChild=0x%llX pawnOff=0x%X\r\n",
            (unsigned long long)g_pc,(unsigned long long)g_dp,(unsigned long long)g_crThunk,(unsigned long long)g_crChild,g_crPawnOff);
    return true;
}
static void DoPossessDP(){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_crPawnOff)=(uint64_t)g_dp;         // NewPawn = the replicated DefaultPawn
    Marker("[POSSESS] >>> calling ClientRestart(PC, DefaultPawn)\r\n");
    CallNative(g_crFn,g_crThunk,g_crChild,(void*)g_pc,g_pbuf,g_rbuf);
    Marker("[POSSESS] <<< ClientRestart returned (no crash) — client should now control the DefaultPawn.\r\n");
}

// ---- PHASE 3: spawn a BP_HERO pawn client-side (the decisive viability test) ----
static uintptr_t g_gsCDO=0, g_heroCls=0, g_worldCtx=0, g_pcSpawn=0;
static void* g_beginFn=0; static uintptr_t g_beginThunk=0, g_beginChild=0;
static void* g_finishFn=0; static uintptr_t g_finishThunk=0, g_finishChild=0;
static void* g_possFn=0; static uintptr_t g_possThunk=0, g_possChild=0;
static uint32_t g_oBWorld=0,g_oBClass=8,g_oBXform=0x10,g_oBColl=0x70,g_oBOwner=0x78,g_oBRet=0x88;
static uint32_t g_oFActor=0,g_oFXform=0x10,g_oFRet=0x70,g_oInPawn=0;
static uint32_t g_offParam(uintptr_t child,const char* n,uint32_t dflt){ uint32_t o=ParamOffset(child,n); return o==0xFFFFFFFF?dflt:o; }
// Isolation test: spawn a STOCK ADefaultPawn class (trivial construction) via the SAME BeginDeferred path instead
// of a hero. If this spawns cleanly but the hero crashes, the hero's BP/GAS construction is the crash (dead-end for
// client-side heroes); if this also crashes, the BeginDeferred call mechanism is at fault.
static const bool kSpawnStockIsolation = true;
static bool ResolveSpawnHero(){
    g_heroCls=FindHeroPawnClass();
    if(kSpawnStockIsolation){ uintptr_t dpInst=FindInstExactClass("DefaultPawn"); if(dpInst){ g_heroCls=ClassOf(dpInst); Marker("[SPAWN] ISOLATION: spawning STOCK DefaultPawn class instead of the hero.\r\n"); } }
    g_worldCtx=FindInstClassSub("ProgressionManager"); if(!g_worldCtx) g_worldCtx=FindInstExactClass("LokiGameState");
    g_pcSpawn=FindInstExactClass("PlayerController");
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    if(!g_heroCls||!g_worldCtx||!g_gsCDO){ Markerf("[SPAWN] resolve FAIL hero=0x%llX world=0x%llX gsCDO=0x%llX\r\n",(unsigned long long)g_heroCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO); return false; }
    uintptr_t gc=ClassOf(g_gsCDO);
    ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
    ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
    if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBOwner=g_offParam(g_beginChild,"Owner",0x78); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
    if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    if(g_pcSpawn){ ResolveFunc(ClassOf(g_pcSpawn),"Possess",&g_possFn,&g_possThunk,&g_possChild); if(g_possChild) g_oInPawn=g_offParam(g_possChild,"InPawn",0); }
    char hn[160]="?"; ObjName(g_heroCls,hn,sizeof(hn));
    Markerf("[SPAWN] resolved hero=%s(0x%llX) world=0x%llX gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX possThunk=0x%llX\r\n",
            hn,(unsigned long long)g_heroCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_possThunk);
    Markerf("[SPAWN] Begin params: world@0x%X class@0x%X xform@0x%X coll@0x%X owner@0x%X ret@0x%X | Finish: actor@0x%X xform@0x%X ret@0x%X | Possess InPawn@0x%X\r\n",
            g_oBWorld,g_oBClass,g_oBXform,g_oBColl,g_oBOwner,g_oBRet,g_oFActor,g_oFXform,g_oFRet,g_oInPawn);
    return g_beginThunk&&g_finishThunk;
}
static void DoSpawnHero(){
    // FTransform (UE5 double/LWC): Rotation FQuat@0x0 (W@0x18), Translation FVector@0x20, Scale3D FVector@0x38.
    static uint8_t xf[0x60]={0};
    *(double*)(xf+0x18)=1.0;                                   // rotation W=1 (identity)
    *(double*)(xf+0x20)=0.0; *(double*)(xf+0x28)=0.0; *(double*)(xf+0x30)=500.0;  // translation (0,0,500)
    *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;    // scale (1,1,1)
    // 1. BeginDeferredActorSpawnFromClass(World=ProgressionManager, HeroClass, xform, coll=AlwaysSpawn) -> deferred
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_worldCtx;
    *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)g_heroCls;
    memcpy(g_pbuf+g_oBXform,xf,0x50);
    g_pbuf[g_oBColl]=2;                                        // AdjustIfPossibleButAlwaysSpawn
    Marker("[SPAWN] >>> BeginDeferredActorSpawnFromClass(hero)\r\n");
    CallNative(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf);
    uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!LooksLikePtr(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
    char dcn[96]="-"; if(LooksLikePtr(deferred)&&ClassOf(deferred))GetFNameStr(NameId(ClassOf(deferred)),dcn,sizeof(dcn));
    Markerf("[SPAWN] <<< deferred=0x%llX cls=%s\r\n",(unsigned long long)deferred,dcn);
    if(!LooksLikePtr(deferred)){ Marker("[SPAWN] deferred spawn returned null — hero spawn FAILED.\r\n"); return; }
    // 2. FinishSpawningActor(deferred, xform) -> hero
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
    Marker("[SPAWN] >>> FinishSpawningActor\r\n");
    CallNative(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf);
    uintptr_t hero=(uintptr_t)*(uint64_t*)g_rbuf; if(!LooksLikePtr(hero)) hero=*(uint64_t*)(g_pbuf+g_oFRet); if(!LooksLikePtr(hero)) hero=deferred;
    char hcn[96]="-"; if(LooksLikePtr(hero)&&ClassOf(hero))GetFNameStr(NameId(ClassOf(hero)),hcn,sizeof(hcn));
    Markerf("[SPAWN] <<< HERO SPAWNED actor=0x%llX cls=%s — hero pawn EXISTS client-side!\r\n",(unsigned long long)hero,hcn);
    // 3. Possess with the stock PC (SUPERVIVE gameplay needs a Loki PC, but this tests whether possession + basic
    //    control engage at all).
    if(LooksLikePtr(hero)&&g_possThunk&&g_pcSpawn){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)(g_pbuf+g_oInPawn)=(uint64_t)hero;
        Marker("[SPAWN] >>> Possess(stockPC, hero)\r\n");
        CallNative(g_possFn,g_possThunk,g_possChild,(void*)g_pcSpawn,g_pbuf,g_rbuf);
        Marker("[SPAWN] <<< Possess returned (no crash).\r\n");
    }
}

// Forward decls (both are defined later in the Route D / spectator section).
static bool CallGuarded(void* fn, uintptr_t th, uintptr_t ch, void* ctx, void* pb, void* rb);
static uint32_t PropOffsetOnClass(uintptr_t cls,const char* name);

// ---- PHASE 2 (S79 moonshot): spawn a local BP_Dev PC + a hero, census the drop-in machinery (NO swap) ----
// The DS client's local networked PC is the NATIVE LokiPlayerController (S73 by-path mirror). It LACKS the
// BP_LokiPlayerController_Dev_C drop-in fns (DropPlaneComponentSetup / UpdateIsInDropPod / FinishDropPhaseHiding@PC+0xF28,
// S74) and the GameEventRouterComponent that clears the loading overlay (S77). Phase 1 (S79) proved BOTH the BP_Dev PC
// class AND BP_HERO_Assault_C are RESIDENT in this session's memory. Phase 2 spawns a LOCAL instance of each via the
// proven deferred-spawn path (BuildOutParms fixed the const-FTransform& struct-param ABI, S78 spawned an ACameraActor
// clean) and confirms the spawned BP_Dev PC exposes the drop-in fns — the gate for Phase 3 (swap-in) + Phase 4 (possess).
// KILL-CRITERIA: if the BP_Dev PC (or hero) can't be constructed client-side (BP/GAS/component construction crash, à la
// the S72 hero spawn), Phase 2's gate FAILS -> bank. NO swap/possess is performed here.
static uintptr_t g_p2World=0, g_p2DevCls=0, g_p2HeroCls=0, g_p2NativePc=0, g_p2Dp=0;
static void* g_p2GlaFn=0; static uintptr_t g_p2GlaThunk=0, g_p2GlaChild=0;
static double g_p2X=0.0, g_p2Y=0.0, g_p2Z=1000.0;
static bool ResolveSpawnP2(){
    g_p2DevCls  = FindObjExact("BP_LokiPlayerController_Dev_C"); if(!g_p2DevCls)  g_p2DevCls = FindObjNamePreSuf("BP_LokiPlayerController_Dev","_C");
    g_p2HeroCls = FindObjExact("BP_HERO_Assault_C");            if(!g_p2HeroCls) g_p2HeroCls= FindHeroPawnClass();
    g_p2World   = FindInstClassSub("ProgressionManager");        if(!g_p2World)   g_p2World  = FindInstClassSub("LokiGameState");
    g_p2NativePc= FindInstExactClass("LokiPlayerController");    if(!g_p2NativePc)g_p2NativePc=FindInstClassSub("LokiPlayerController");
    g_gsCDO     = FindObjExact("Default__GameplayStatics");
    if(!g_p2DevCls||!g_p2HeroCls||!g_p2World||!g_gsCDO){
        Markerf("[P2] resolve FAIL devCls=0x%llX heroCls=0x%llX world=0x%llX gsCDO=0x%llX\r\n",
                (unsigned long long)g_p2DevCls,(unsigned long long)g_p2HeroCls,(unsigned long long)g_p2World,(unsigned long long)g_gsCDO);
        return false;
    }
    uintptr_t gc=ClassOf(g_gsCDO);
    ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
    ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
    if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBOwner=g_offParam(g_beginChild,"Owner",0x78); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
    if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    // read a valid in-world spawn location from the DefaultPawn (K2_GetActorLocation on the Actor chain).
    if(g_p2NativePc){ uint32_t pawnOff=PropOffsetOnClass(ClassOf(g_p2NativePc),"Pawn");
        uintptr_t dp=(pawnOff!=0xFFFFFFFF && SafeReadable((void*)(g_p2NativePc+pawnOff),8))?*(uintptr_t*)(g_p2NativePc+pawnOff):0;
        if(LooksLikePtr(dp)){ g_p2Dp=dp; ResolveFunc(ClassOf(dp),"K2_GetActorLocation",&g_p2GlaFn,&g_p2GlaThunk,&g_p2GlaChild); } }
    char dn[160]="?",hn[160]="?"; ObjName(g_p2DevCls,dn,sizeof(dn)); ObjName(g_p2HeroCls,hn,sizeof(hn));
    Markerf("[P2] resolved devPc=%s(0x%llX) hero=%s(0x%llX) world=0x%llX gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX glaThunk=0x%llX dp=0x%llX\r\n",
            dn,(unsigned long long)g_p2DevCls,hn,(unsigned long long)g_p2HeroCls,(unsigned long long)g_p2World,(unsigned long long)g_gsCDO,
            (unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_p2GlaThunk,(unsigned long long)g_p2Dp);
    return g_beginThunk && g_finishThunk;
}
// Generic deferred spawn of `cls` at (x,y,z). Returns the constructed actor (or 0 on null/catchable fault). Both calls
// are CallGuarded so a catchable exception is caught + logged (the VEH logs an uncatchable __fastfail RIP separately).
static uintptr_t P2SpawnActor(uintptr_t cls, double x, double y, double z){
    static uint8_t xf[0x60]; memset(xf,0,sizeof(xf));
    *(double*)(xf+0x18)=1.0;                                                       // quat W=1 (identity rot)
    *(double*)(xf+0x20)=x; *(double*)(xf+0x28)=y; *(double*)(xf+0x30)=z;           // translation
    *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;     // scale (1,1,1)
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_p2World;
    *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)cls;
    memcpy(g_pbuf+g_oBXform,xf,0x50);
    g_pbuf[g_oBColl]=2;                                                            // AdjustIfPossibleButAlwaysSpawn
    if(CallGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[P2] BeginDeferredActorSpawnFromClass FAULTED\r\n"); return 0; }
    uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!LooksLikePtr(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
    if(!LooksLikePtr(deferred)){ Marker("[P2] BeginDeferred returned null\r\n"); return 0; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
    if(CallGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[P2] FinishSpawningActor FAULTED\r\n"); return deferred; }
    uintptr_t actor=(uintptr_t)*(uint64_t*)g_rbuf; if(!LooksLikePtr(actor)) actor=*(uint64_t*)(g_pbuf+g_oFRet); if(!LooksLikePtr(actor)) actor=deferred;
    return actor;
}
static void DoSpawnP2(){
    Marker("[P2] === Phase 2: spawn BP_Dev PC + hero (NO swap/possess) ===\r\n");
    // Prefer a real in-world spawn point (the DefaultPawn's location) over the void origin.
    if(g_p2GlaThunk && g_p2Dp){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(!CallGuarded(g_p2GlaFn,g_p2GlaThunk,g_p2GlaChild,(void*)g_p2Dp,g_pbuf,g_rbuf)){
            double x=*(double*)(g_rbuf+0), y=*(double*)(g_rbuf+8), z=*(double*)(g_rbuf+16);
            if(x!=0.0||y!=0.0||z!=0.0){ g_p2X=x; g_p2Y=y; g_p2Z=z; }
        }
    }
    Markerf("[P2] spawn location = (%.0f,%.0f,%.0f)\r\n",g_p2X,g_p2Y,g_p2Z);
    // 1. Spawn the BP_Dev PC first (wall #2 class; the crash-gate). Marker is flushed per line, so even an uncatchable
    //    hero-spawn crash below still leaves this PC result on disk.
    char n[160]="?"; ObjName(g_p2DevCls,n,sizeof(n));
    Markerf("[P2] >>> spawning BP_Dev PC class '%s'\r\n",n);
    uintptr_t devPc=P2SpawnActor(g_p2DevCls, g_p2X, g_p2Y, g_p2Z);
    if(!LooksLikePtr(devPc)){ Marker("[P2] BP_Dev PC spawn FAILED (null/fault) — Phase-2 gate FAILED; bank.\r\n"); Marker("[P2] === Phase 2 done (gate failed). ===\r\n"); return; }
    { char cn[128]="-"; ClassName(devPc,cn,sizeof(cn)); Markerf("[P2] <<< BP_Dev PC SPAWNED obj=0x%llX cls=%s — construction SURVIVED!\r\n",(unsigned long long)devPc,cn);
      uintptr_t dc=ClassOf(devPc);
      Marker("[P2] BP_Dev PC drop-in / control fns (present => Phase 3/4 have a real target):\r\n");
      ReportFunc(dc,"DropPlaneComponentSetup"); ReportFunc(dc,"UpdateIsInDropPod"); ReportFunc(dc,"FinishDropPhaseHiding");
      ReportFunc(dc,"TryGetLocalLokiController"); ReportFunc(dc,"ClientRestart"); ReportFunc(dc,"Possess"); }
    // 2. Spawn the hero (only after the PC survived). Nudge Z up so it doesn't co-locate with the PC.
    ObjName(g_p2HeroCls,n,sizeof(n)); Markerf("[P2] >>> spawning hero class '%s'\r\n",n);
    uintptr_t hero=P2SpawnActor(g_p2HeroCls, g_p2X, g_p2Y, g_p2Z+120.0);
    if(LooksLikePtr(hero)){ char cn[128]="-"; ClassName(hero,cn,sizeof(cn)); Markerf("[P2] <<< HERO SPAWNED obj=0x%llX cls=%s — hero construction SURVIVED!\r\n",(unsigned long long)hero,cn);
        uintptr_t hc=ClassOf(hero); ReportFunc(hc,"GetAbilitySystemComponent"); ReportFunc(hc,"BeginPlay"); }
    else Marker("[P2] hero spawn FAILED (null/fault).\r\n");
    Marker("[P2] === Phase 2 done. NO swap/possess performed (that is Phase 3/4). ===\r\n");
}

// ---- PHASE 3a (S79 moonshot): read-only census of the controller-SWAP surface (no hook, no spawn, no write) ----
// Phase 3 makes a spawned BP_Dev PC the LOCAL active controller. That needs two engine offsets that are NOT reflected
// UPROPERTYs (PropOffsetOnClass can't find them): ULocalPlayer->PlayerController and APlayerController->Player. Find
// them by POINTER-EQUALITY scan against the CURRENT local player + native PC (robust, no disasm needed). Everything
// here is off-thread read-only RPM — no .text hook is ever installed, so the anti-tamper has nothing to catch.
static void ScanForPtr(uintptr_t obj, uintptr_t want, uint32_t span, const char* tag){
    int hits=0;
    for(uint32_t o=0;o<span && hits<8;o+=8){ if(!SafeReadable((void*)(obj+o),8)) continue; if(*(uintptr_t*)(obj+o)==want){ Markerf("[SWAP]   %s @ +0x%X\r\n",tag,o); hits++; } }
    if(!hits) Markerf("[SWAP]   %s NOT FOUND in [0,0x%X)\r\n",tag,span);
}
static void DoSwapCensus(){
    Marker("[SWAP] === Phase 3a: controller-swap surface census (read-only) ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    uintptr_t P=FindInstExactClass("LokiPlayerController"); if(!P) P=FindInstClassSub("LokiPlayerController");
    uintptr_t GI=FindInstClassSub("GameInstance");
    char lcn[128]="-",pcn[128]="-",gcn[128]="-",lon[160]="-",pon[160]="-";
    if(L){ClassName(L,lcn,sizeof(lcn));ObjName(L,lon,sizeof(lon));} if(P){ClassName(P,pcn,sizeof(pcn));ObjName(P,pon,sizeof(pon));} if(GI)ClassName(GI,gcn,sizeof(gcn));
    Markerf("[SWAP] LocalPlayer=0x%llX(%s '%s') localPC=0x%llX(%s '%s') GameInstance=0x%llX(%s)\r\n",
            (unsigned long long)L,lcn,lon,(unsigned long long)P,pcn,pon,(unsigned long long)GI,gcn);
    if(!L||!P){ Marker("[SWAP] missing LocalPlayer or PC — cannot census swap surface. ===\r\n"); return; }
    Marker("[SWAP] ULocalPlayer->PlayerController (scan LocalPlayer for a qword == localPC):\r\n");
    ScanForPtr(L,P,0x800,"LocalPlayer->PlayerController");
    Marker("[SWAP] APlayerController->Player (scan localPC for a qword == LocalPlayer):\r\n");
    ScanForPtr(P,L,0x1000,"PC->Player");
    if(GI){ Marker("[SWAP] GameInstance refs to localPC (informational — LocalPlayers array / cached PC):\r\n"); ScanForPtr(GI,P,0x600,"GameInstance->? localPC"); ScanForPtr(GI,L,0x600,"GameInstance->? LocalPlayer"); }
    Marker("[SWAP] === Phase 3a done. (Phase 3 WRITE = point those offsets at the spawned BP_Dev PC + refire SpectatorStateChanged.) ===\r\n");
}

// ---- PHASE 3 (S79 moonshot, MINIMAL): controller swap + revert/crash monitor ----
// Reuses the Phase-2 spawn machinery (ResolveSpawnP2 + P2SpawnActor) to spawn a fresh BP_Dev PC, then repoints the
// local player's controller to it. The two-pointer swap is done ON THE GAME THREAD inside the PI hook (a BP-call
// boundary — the safest point to repoint a live controller). Offsets are RE-VERIFIED by pointer equality this launch
// (Phase-3a found L->PC@+0x38, PC->Player@+0x458) before trusting them. The monitor is read-only off-thread.
static uintptr_t g_swL=0, g_swOldPc=0, g_swDevPc=0; static uint32_t g_swLpcOff=0x38, g_swPcPlayerOff=0x458;
static bool ResolveSwap(){
    if(!ResolveSpawnP2()) return false;                 // resolves devCls/heroCls/world/spawn-thunks/dp + K2_GetActorLocation
    g_swL = FindInstExactClass("LocalPlayer"); if(!g_swL) g_swL=FindInstClassSub("LocalPlayer");
    g_swOldPc = g_p2NativePc ? g_p2NativePc : FindInstClassSub("LokiPlayerController");
    if(!g_swL||!g_swOldPc){ Markerf("[SW] resolve FAIL L=0x%llX oldPc=0x%llX\r\n",(unsigned long long)g_swL,(unsigned long long)g_swOldPc); return false; }
    // Verify/re-scan the two swap offsets by pointer equality (don't blindly trust the hardcoded 0x38/0x458).
    if(!(SafeReadable((void*)(g_swL+g_swLpcOff),8) && *(uintptr_t*)(g_swL+g_swLpcOff)==g_swOldPc)){
        g_swLpcOff=0xFFFFFFFF; for(uint32_t o=0;o<0x800;o+=8){ if(SafeReadable((void*)(g_swL+o),8) && *(uintptr_t*)(g_swL+o)==g_swOldPc){ g_swLpcOff=o; break; } } }
    if(!(SafeReadable((void*)(g_swOldPc+g_swPcPlayerOff),8) && *(uintptr_t*)(g_swOldPc+g_swPcPlayerOff)==g_swL)){
        g_swPcPlayerOff=0xFFFFFFFF; for(uint32_t o=0;o<0x1000;o+=8){ if(SafeReadable((void*)(g_swOldPc+o),8) && *(uintptr_t*)(g_swOldPc+o)==g_swL){ g_swPcPlayerOff=o; break; } } }
    Markerf("[SW] resolved L=0x%llX oldPc=0x%llX devCls=0x%llX lpcOff=0x%X pcPlayerOff=0x%X\r\n",
            (unsigned long long)g_swL,(unsigned long long)g_swOldPc,(unsigned long long)g_p2DevCls,g_swLpcOff,g_swPcPlayerOff);
    return g_swLpcOff!=0xFFFFFFFF && g_swPcPlayerOff!=0xFFFFFFFF && g_beginThunk && g_finishThunk;
}
static void DoSwap(){
    Marker("[SW] === Phase 3: minimal controller swap ===\r\n");
    // spawn point from the DefaultPawn (reuse the Phase-2 K2_GetActorLocation resolution)
    if(g_p2GlaThunk && g_p2Dp){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(!CallGuarded(g_p2GlaFn,g_p2GlaThunk,g_p2GlaChild,(void*)g_p2Dp,g_pbuf,g_rbuf)){
            double x=*(double*)(g_rbuf+0),y=*(double*)(g_rbuf+8),z=*(double*)(g_rbuf+16); if(x||y||z){ g_p2X=x; g_p2Y=y; g_p2Z=z; } } }
    Markerf("[SW] spawn loc=(%.0f,%.0f,%.0f)\r\n",g_p2X,g_p2Y,g_p2Z);
    uintptr_t devPc=P2SpawnActor(g_p2DevCls, g_p2X, g_p2Y, g_p2Z);
    if(!LooksLikePtr(devPc)){ Marker("[SW] BP_Dev PC spawn FAILED — aborting swap (no write).\r\n"); g_swDevPc=0; return; }
    { char cn[128]="-"; ClassName(devPc,cn,sizeof(cn)); Markerf("[SW] BP_Dev PC spawned=0x%llX(%s)\r\n",(unsigned long long)devPc,cn); }
    g_swDevPc=devPc;
    // THE SWAP (game thread, at the PI boundary):
    uintptr_t beforeLpc = SafeReadable((void*)(g_swL+g_swLpcOff),8)?*(uintptr_t*)(g_swL+g_swLpcOff):0;
    *(uintptr_t*)(g_swL+g_swLpcOff)=(uintptr_t)devPc;                    // LocalPlayer->PlayerController = devPC
    *(uintptr_t*)(devPc+g_swPcPlayerOff)=(uintptr_t)g_swL;               // devPC->Player = LocalPlayer
    if(SafeReadable((void*)(g_swOldPc+g_swPcPlayerOff),8)) *(uintptr_t*)(g_swOldPc+g_swPcPlayerOff)=0;  // old PC->Player = null
    Markerf("[SW] SWAPPED: L+0x%X: 0x%llX -> 0x%llX ; devPC+0x%X = L ; oldPC+0x%X = 0\r\n",
            g_swLpcOff,(unsigned long long)beforeLpc,(unsigned long long)devPc,g_swPcPlayerOff,g_swPcPlayerOff);
    Marker("[SW] swap applied on game thread — worker monitors for revert/crash.\r\n");
}

// ---- PHASE 4 (S79 moonshot): possess a hero on the swapped-in BP_Dev PC + drive drop-in ----
static uintptr_t g_poPc=0, g_poHero=0; static uint32_t g_poPawnOff=0x3F8;
static void* g_poPossFn=0; static uintptr_t g_poPossThunk=0,g_poPossChild=0; static uint32_t g_poInPawn=0;
static void* g_poFdphFn=0; static uintptr_t g_poFdphThunk=0,g_poFdphChild=0;
static void* g_poUidpFn=0; static uintptr_t g_poUidpThunk=0,g_poUidpChild=0; static uint32_t g_poUidpArg=0;
static void* g_poDpcsFn=0; static uintptr_t g_poDpcsThunk=0,g_poDpcsChild=0;
static bool ResolvePossess(){
    if(!ResolveSpawnP2()) return false;                 // heroCls / world / spawn-thunks / dp / K2_GetActorLocation
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    if(!L){ Marker("[PO] no LocalPlayer\r\n"); return false; }
    g_poPc = SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0;   // the swapped-in PC (Phase 3 persisted)
    if(!LooksLikePtr(g_poPc)){ Marker("[PO] L->PlayerController null\r\n"); return false; }
    char pcn[128]="-"; ClassName(g_poPc,pcn,sizeof(pcn));
    bool isDev = strstr(pcn,"Dev")!=nullptr;
    Markerf("[PO] local PC = 0x%llX (%s) %s\r\n",(unsigned long long)g_poPc,pcn, isDev?"[swapped-in BP_Dev]":"[NOT BP_Dev — run the swap first?]");
    uintptr_t pcCls=ClassOf(g_poPc);
    ResolveFunc(pcCls,"Possess",&g_poPossFn,&g_poPossThunk,&g_poPossChild); if(g_poPossChild) g_poInPawn=g_offParam(g_poPossChild,"InPawn",0);
    ResolveFunc(pcCls,"FinishDropPhaseHiding",&g_poFdphFn,&g_poFdphThunk,&g_poFdphChild);
    ResolveFunc(pcCls,"UpdateIsInDropPod",&g_poUidpFn,&g_poUidpThunk,&g_poUidpChild); g_poUidpArg=0;
    ResolveFunc(pcCls,"DropPlaneComponentSetup",&g_poDpcsFn,&g_poDpcsThunk,&g_poDpcsChild);
    uint32_t po=PropOffsetOnClass(pcCls,"Pawn"); if(po!=0xFFFFFFFF) g_poPawnOff=po;
    Markerf("[PO] resolved possThunk=0x%llX fdph=0x%llX uidp=0x%llX dpcs=0x%llX pawnOff=0x%X heroCls=0x%llX\r\n",
            (unsigned long long)g_poPossThunk,(unsigned long long)g_poFdphThunk,(unsigned long long)g_poUidpThunk,(unsigned long long)g_poDpcsThunk,g_poPawnOff,(unsigned long long)g_p2HeroCls);
    return g_poPossThunk && g_p2HeroCls;
}
static void DoPossess(){
    Marker("[PO] === Phase 4: possess hero on swapped-in PC + drive drop-in ===\r\n");
    uintptr_t curPawn=SafeReadable((void*)(g_poPc+g_poPawnOff),8)?*(uintptr_t*)(g_poPc+g_poPawnOff):0;
    char cpn[96]="-"; if(LooksLikePtr(curPawn))ClassName(curPawn,cpn,sizeof(cpn));
    Markerf("[PO] PC->Pawn before = 0x%llX(%s)\r\n",(unsigned long long)curPawn,cpn);
    if(g_p2GlaThunk && g_p2Dp){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(!CallGuarded(g_p2GlaFn,g_p2GlaThunk,g_p2GlaChild,(void*)g_p2Dp,g_pbuf,g_rbuf)){ double x=*(double*)(g_rbuf+0),y=*(double*)(g_rbuf+8),z=*(double*)(g_rbuf+16); if(x||y||z){g_p2X=x;g_p2Y=y;g_p2Z=z;} } }
    Markerf("[PO] spawning hero at (%.0f,%.0f,%.0f)...\r\n",g_p2X,g_p2Y,g_p2Z);
    uintptr_t hero=P2SpawnActor(g_p2HeroCls,g_p2X,g_p2Y,g_p2Z);
    if(!LooksLikePtr(hero)){ Marker("[PO] hero spawn FAILED — abort.\r\n"); return; }
    g_poHero=hero; { char hcn[96]="-"; ClassName(hero,hcn,sizeof(hcn)); Markerf("[PO] hero spawned=0x%llX(%s)\r\n",(unsigned long long)hero,hcn); }
    // Possess (C++ Possess via the exec thunk; locally-spawned PC+hero have local authority so OnPossess runs).
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_poInPawn)=(uint64_t)hero;
    Marker("[PO] >>> Possess(PC, hero)\r\n");
    if(CallGuarded(g_poPossFn,g_poPossThunk,g_poPossChild,(void*)g_poPc,g_pbuf,g_rbuf)) Marker("[PO] Possess FAULTED\r\n"); else Marker("[PO] <<< Possess returned\r\n");
    // Drive the drop-in flags (S74: FinishDropPhaseHiding sets PC+0xF28=1, no server check).
    if(g_poFdphThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_poFdphFn,g_poFdphThunk,g_poFdphChild,(void*)g_poPc,g_pbuf,g_rbuf)) Marker("[PO] FinishDropPhaseHiding FAULTED\r\n"); else Marker("[PO] FinishDropPhaseHiding done (PC+0xF28=1)\r\n"); }
    if(g_poUidpThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); g_pbuf[g_poUidpArg]=0; if(CallGuarded(g_poUidpFn,g_poUidpThunk,g_poUidpChild,(void*)g_poPc,g_pbuf,g_rbuf)) Marker("[PO] UpdateIsInDropPod FAULTED\r\n"); else Marker("[PO] UpdateIsInDropPod(false) done\r\n"); }
    if(g_poDpcsThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_poDpcsFn,g_poDpcsThunk,g_poDpcsChild,(void*)g_poPc,g_pbuf,g_rbuf)) Marker("[PO] DropPlaneComponentSetup FAULTED\r\n"); else Marker("[PO] DropPlaneComponentSetup done\r\n"); }
    uintptr_t nowPawn=SafeReadable((void*)(g_poPc+g_poPawnOff),8)?*(uintptr_t*)(g_poPc+g_poPawnOff):0;
    char npn[96]="-"; if(LooksLikePtr(nowPawn))ClassName(nowPawn,npn,sizeof(npn));
    Markerf("[PO] PC->Pawn after = 0x%llX(%s) %s\r\n",(unsigned long long)nowPawn,npn, nowPawn==hero?"<< HERO POSSESSED":"(not the hero)");
    Marker("[PO] === Phase 4 done. ===\r\n");
}

// ---- PHASE 4b (S79 moonshot): make the possessed hero visible + controllable (+ deploy-func recon) ----
static uintptr_t g_depHero=0, g_depPc=0, g_depCam=0;
static void* g_depHideFn=0; static uintptr_t g_depHideThunk=0,g_depHideChild=0; static uint32_t g_depHideArg=0;
static void* g_depEIFn=0;   static uintptr_t g_depEIThunk=0,  g_depEIChild=0;   static uint32_t g_depEIArg=0;
// Log every UFunction on cls's chain whose name contains any keyword — recon for the deploy pipeline.
static void ListFuncsMatching(uintptr_t cls, const char* const* keys, int nkeys){
    int g=0; while(LooksLikePtr(cls)&&g++<10){
        char ccn[96]="?"; GetFNameStr(NameId(cls),ccn,sizeof(ccn));
        uintptr_t f=SafeReadable((void*)(cls+UST_CHILDREN),8)?*(uintptr_t*)(cls+UST_CHILDREN):0; int i=0;
        while(LooksLikePtr(f)&&i++<1200){ char fn[128];
            if(GetFNameStr(NameId(f),fn,sizeof(fn))){ for(int k=0;k<nkeys;k++){ if(strstr(fn,keys[k])){ uintptr_t th=SafeReadable((void*)(f+UFUNC_FUNC),8)?*(uintptr_t*)(f+UFUNC_FUNC):0; Markerf("[DEP]   %s::%s thunk=0x%llX\r\n",ccn,fn,(unsigned long long)th); break; } } }
            f=SafeReadable((void*)(f+FIELD_NEXT_UF),8)?*(uintptr_t*)(f+FIELD_NEXT_UF):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static bool ResolveDeploy(){
    if(!ResolveSpawnP2()) return false;                 // for g_p2Gla (K2_GetActorLocation)
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    if(!L){ Marker("[DEP] no LocalPlayer\r\n"); return false; }
    g_depPc = SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0;
    if(!LooksLikePtr(g_depPc)){ Marker("[DEP] L->PlayerController null\r\n"); return false; }
    uint32_t po=PropOffsetOnClass(ClassOf(g_depPc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    g_depHero = SafeReadable((void*)(g_depPc+pawnOff),8)?*(uintptr_t*)(g_depPc+pawnOff):0;
    if(!LooksLikePtr(g_depHero)){ Marker("[DEP] PC->Pawn null — run possess first.\r\n"); return false; }
    char hcn[96]="-"; ClassName(g_depHero,hcn,sizeof(hcn));
    Markerf("[DEP] hero=0x%llX(%s) pc=0x%llX pawnOff=0x%X\r\n",(unsigned long long)g_depHero,hcn,(unsigned long long)g_depPc,pawnOff);
    uintptr_t hc=ClassOf(g_depHero);
    ResolveFunc(hc,"SetActorHiddenInGame",&g_depHideFn,&g_depHideThunk,&g_depHideChild); if(g_depHideChild) g_depHideArg=g_offParam(g_depHideChild,"bNewHidden",0);
    ResolveFunc(hc,"EnableInput",&g_depEIFn,&g_depEIThunk,&g_depEIChild);                 if(g_depEIChild)   g_depEIArg=g_offParam(g_depEIChild,"PlayerController",0);
    g_depCam=FindInstClassSub("PlayerCameraManager");
    Marker("[DEP] hero deploy/visibility/drop-ish UFunctions (recon):\r\n");
    static const char* keys[]={"Deploy","DropPod","DropPlane","Reveal","Hidden","Visib","Reset","Respawn","Landed","Land"};
    ListFuncsMatching(hc,keys,10);
    Markerf("[DEP] resolved hideThunk=0x%llX eiThunk=0x%llX camMgr=0x%llX\r\n",(unsigned long long)g_depHideThunk,(unsigned long long)g_depEIThunk,(unsigned long long)g_depCam);
    return true;
}
static void DoDeploy(){
    Marker("[DEP] === Phase 4b: make hero visible + bind input ===\r\n");
    if(g_p2GlaThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(!CallGuarded(g_p2GlaFn,g_p2GlaThunk,g_p2GlaChild,(void*)g_depHero,g_pbuf,g_rbuf)) Markerf("[DEP] hero loc=(%.0f,%.0f,%.0f)\r\n",*(double*)(g_rbuf),*(double*)(g_rbuf+8),*(double*)(g_rbuf+16)); }
    if(g_p2GlaThunk && LooksLikePtr(g_depCam)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(!CallGuarded(g_p2GlaFn,g_p2GlaThunk,g_p2GlaChild,(void*)g_depCam,g_pbuf,g_rbuf)) Markerf("[DEP] camMgr loc=(%.0f,%.0f,%.0f)\r\n",*(double*)(g_rbuf),*(double*)(g_rbuf+8),*(double*)(g_rbuf+16)); }
    if(g_depHideThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); g_pbuf[g_depHideArg]=0;
        if(CallGuarded(g_depHideFn,g_depHideThunk,g_depHideChild,(void*)g_depHero,g_pbuf,g_rbuf)) Marker("[DEP] SetActorHiddenInGame FAULTED\r\n"); else Marker("[DEP] SetActorHiddenInGame(false) done\r\n"); }
    if(g_depEIThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_depEIArg)=(uint64_t)g_depPc;
        if(CallGuarded(g_depEIFn,g_depEIThunk,g_depEIChild,(void*)g_depHero,g_pbuf,g_rbuf)) Marker("[DEP] EnableInput FAULTED\r\n"); else Marker("[DEP] EnableInput(PC) done\r\n"); }
    Marker("[DEP] === Phase 4b done. ===\r\n");
}

// ---- PHASE 4c (S79 moonshot): reveal the possessed hero (SetPredropHidden) + point the camera at it ----
static uintptr_t g_uhHero=0, g_uhPc=0, g_uhCam=0;
static void* g_uhSphFn=0; static uintptr_t g_uhSphThunk=0,g_uhSphChild=0; static uint32_t g_uhSphArg=0;
static void* g_uhVtFn=0;  static uintptr_t g_uhVtThunk=0, g_uhVtChild=0;  static uint32_t g_uhVtTgt=0;
static bool ResolveUnhide(){
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer"); if(!L){ Marker("[UH] no LocalPlayer\r\n"); return false; }
    g_uhPc=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0; if(!LooksLikePtr(g_uhPc)){ Marker("[UH] L->PC null\r\n"); return false; }
    uint32_t po=PropOffsetOnClass(ClassOf(g_uhPc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    g_uhHero=SafeReadable((void*)(g_uhPc+pawnOff),8)?*(uintptr_t*)(g_uhPc+pawnOff):0; if(!LooksLikePtr(g_uhHero)){ Marker("[UH] PC->Pawn null\r\n"); return false; }
    char hcn[96]="-"; ClassName(g_uhHero,hcn,sizeof(hcn)); Markerf("[UH] hero=0x%llX(%s) pc=0x%llX\r\n",(unsigned long long)g_uhHero,hcn,(unsigned long long)g_uhPc);
    ResolveFunc(ClassOf(g_uhHero),"SetPredropHidden",&g_uhSphFn,&g_uhSphThunk,&g_uhSphChild); g_uhSphArg=0;   // first param (bool bHidden)
    ResolveFunc(ClassOf(g_uhPc),"SetViewTargetWithBlend",&g_uhVtFn,&g_uhVtThunk,&g_uhVtChild); if(g_uhVtChild) g_uhVtTgt=g_offParam(g_uhVtChild,"NewViewTarget",0);
    g_uhCam=FindInstClassSub("CameraManager");
    Markerf("[UH] sphThunk=0x%llX vtThunk=0x%llX vtTgtOff=0x%X camMgr=0x%llX\r\n",(unsigned long long)g_uhSphThunk,(unsigned long long)g_uhVtThunk,g_uhVtTgt,(unsigned long long)g_uhCam);
    return g_uhSphThunk!=0 || g_uhVtThunk!=0;
}
static void DoUnhide(){
    Marker("[UH] === Phase 4c: reveal hero + point camera ===\r\n");
    if(g_uhSphThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); g_pbuf[g_uhSphArg]=0;   // false = not pre-drop-hidden
        if(CallGuarded(g_uhSphFn,g_uhSphThunk,g_uhSphChild,(void*)g_uhHero,g_pbuf,g_rbuf)) Marker("[UH] SetPredropHidden FAULTED\r\n"); else Marker("[UH] SetPredropHidden(false) done\r\n"); }
    if(g_uhVtThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_uhVtTgt)=(uint64_t)g_uhHero;   // BlendTime etc = 0
        if(CallGuarded(g_uhVtFn,g_uhVtThunk,g_uhVtChild,(void*)g_uhPc,g_pbuf,g_rbuf)) Marker("[UH] SetViewTargetWithBlend FAULTED\r\n"); else Marker("[UH] SetViewTargetWithBlend(hero) done\r\n"); }
    Marker("[UH] === Phase 4c done. ===\r\n");
}

// ---- PHASE 4d (S79 moonshot): make the NATIVE PC (the render/input-following one) own the hero ----
static uintptr_t g_npNative=0, g_npDev=0, g_npL=0, g_npHero=0, g_npCam=0; static uint32_t g_npPawnOff=0x3F8, g_npCtrlOff=0xFFFFFFFF;
static void* g_npPossFn=0; static uintptr_t g_npPossThunk=0,g_npPossChild=0; static uint32_t g_npInPawn=0;
static void* g_npVtFn=0;   static uintptr_t g_npVtThunk=0,  g_npVtChild=0;   static uint32_t g_npVtTgt=0;
static void* g_npSphFn=0;  static uintptr_t g_npSphThunk=0, g_npSphChild=0;
static bool ResolveNPossess(){
    if(!ResolveSpawnP2()) return false;                       // spawn machinery + K2_GetActorLocation (fallback hero)
    g_npL=FindInstExactClass("LocalPlayer"); if(!g_npL) g_npL=FindInstClassSub("LocalPlayer");
    g_npNative=FindInstExactClass("LokiPlayerController");     // native networked PC (exact class, NOT the BP_Dev subclass)
    g_npDev=FindInstClassSub("BP_LokiPlayerController_Dev");   // our swapped-in BP_Dev PC instance (holds the hero)
    if(!g_npL||!g_npNative){ Markerf("[NP] resolve FAIL L=0x%llX native=0x%llX\r\n",(unsigned long long)g_npL,(unsigned long long)g_npNative); return false; }
    g_npPawnOff=PropOffsetOnClass(ClassOf(g_npNative),"Pawn"); if(g_npPawnOff==0xFFFFFFFF) g_npPawnOff=0x3F8;
    if(g_npDev){ g_npHero=SafeReadable((void*)(g_npDev+g_npPawnOff),8)?*(uintptr_t*)(g_npDev+g_npPawnOff):0; }
    ResolveFunc(ClassOf(g_npNative),"Possess",&g_npPossFn,&g_npPossThunk,&g_npPossChild); if(g_npPossChild) g_npInPawn=g_offParam(g_npPossChild,"InPawn",0);
    ResolveFunc(ClassOf(g_npNative),"SetViewTargetWithBlend",&g_npVtFn,&g_npVtThunk,&g_npVtChild); if(g_npVtChild) g_npVtTgt=g_offParam(g_npVtChild,"NewViewTarget",0);
    if(LooksLikePtr(g_npHero)){ ResolveFunc(ClassOf(g_npHero),"SetPredropHidden",&g_npSphFn,&g_npSphThunk,&g_npSphChild); g_npCtrlOff=PropOffsetOnClass(ClassOf(g_npHero),"Controller"); }
    g_npCam=FindInstClassSub("CameraManager");
    Markerf("[NP] native=0x%llX dev=0x%llX hero=0x%llX pawnOff=0x%X ctrlOff=0x%X possThunk=0x%llX vtThunk=0x%llX camMgr=0x%llX\r\n",
            (unsigned long long)g_npNative,(unsigned long long)g_npDev,(unsigned long long)g_npHero,g_npPawnOff,g_npCtrlOff,(unsigned long long)g_npPossThunk,(unsigned long long)g_npVtThunk,(unsigned long long)g_npCam);
    return g_npNative && (LooksLikePtr(g_npHero) || g_beginThunk);
}
static void DoNPossess(){
    Marker("[NP] === Phase 4d: native-PC possess the hero ===\r\n");
    uintptr_t hero=g_npHero;
    if(!LooksLikePtr(hero) && g_beginThunk){                   // fallback: spawn a fresh hero if BP_Dev PC had none
        if(g_p2GlaThunk && g_p2Dp){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(g_p2GlaFn,g_p2GlaThunk,g_p2GlaChild,(void*)g_p2Dp,g_pbuf,g_rbuf)){ double x=*(double*)(g_rbuf),y=*(double*)(g_rbuf+8),z=*(double*)(g_rbuf+16); if(x||y||z){g_p2X=x;g_p2Y=y;g_p2Z=z;} } }
        hero=P2SpawnActor(g_p2HeroCls,g_p2X,g_p2Y,g_p2Z);
        if(LooksLikePtr(hero)){ ResolveFunc(ClassOf(hero),"SetPredropHidden",&g_npSphFn,&g_npSphThunk,&g_npSphChild); g_npCtrlOff=PropOffsetOnClass(ClassOf(hero),"Controller"); }
    }
    if(!LooksLikePtr(hero)){ Marker("[NP] no hero — abort.\r\n"); return; }
    g_npHero=hero; { char hcn[96]="-"; ClassName(hero,hcn,sizeof(hcn)); Markerf("[NP] hero=0x%llX(%s)\r\n",(unsigned long long)hero,hcn); }
    // 1. Restore the local-player association to the NATIVE PC (undo the Phase-3 swap).
    if(SafeReadable((void*)(g_npL+0x38),8))     *(uintptr_t*)(g_npL+0x38)=(uintptr_t)g_npNative;
    if(SafeReadable((void*)(g_npNative+0x458),8))*(uintptr_t*)(g_npNative+0x458)=(uintptr_t)g_npL;
    Marker("[NP] restored L->PlayerController = native PC\r\n");
    // 2. Possess the hero on the native PC (may no-op on the networked proxy — checked next).
    if(g_npPossThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_npInPawn)=(uint64_t)hero;
        if(CallGuarded(g_npPossFn,g_npPossThunk,g_npPossChild,(void*)g_npNative,g_pbuf,g_rbuf)) Marker("[NP] Possess FAULTED\r\n"); else Marker("[NP] Possess(native,hero) returned\r\n"); }
    // 3. If Possess didn't set the pawn (authority-gated), raw-wire pawn<->controller + clear the BP_Dev PC's pawn.
    uintptr_t nowPawn=SafeReadable((void*)(g_npNative+g_npPawnOff),8)?*(uintptr_t*)(g_npNative+g_npPawnOff):0;
    if(nowPawn!=hero){ Marker("[NP] Possess left Pawn unchanged — raw-wiring pawn<->controller\r\n");
        if(SafeReadable((void*)(g_npNative+g_npPawnOff),8)) *(uintptr_t*)(g_npNative+g_npPawnOff)=(uintptr_t)hero;
        if(g_npCtrlOff!=0xFFFFFFFF && SafeReadable((void*)(hero+g_npCtrlOff),8)) *(uintptr_t*)(hero+g_npCtrlOff)=(uintptr_t)g_npNative;
        if(g_npDev){ uint32_t dp=PropOffsetOnClass(ClassOf(g_npDev),"Pawn"); if(dp!=0xFFFFFFFF && SafeReadable((void*)(g_npDev+dp),8)) *(uintptr_t*)(g_npDev+dp)=0; }
    }
    // 4. Un-hide the hero mesh.
    if(g_npSphThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); g_pbuf[0]=0;
        if(CallGuarded(g_npSphFn,g_npSphThunk,g_npSphChild,(void*)hero,g_pbuf,g_rbuf)) Marker("[NP] SetPredropHidden FAULTED\r\n"); else Marker("[NP] SetPredropHidden(false) done\r\n"); }
    // 5. Point the native PC's camera at the hero.
    if(g_npVtThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_npVtTgt)=(uint64_t)hero;
        if(CallGuarded(g_npVtFn,g_npVtThunk,g_npVtChild,(void*)g_npNative,g_pbuf,g_rbuf)) Marker("[NP] SetViewTargetWithBlend FAULTED\r\n"); else Marker("[NP] SetViewTargetWithBlend(hero) done\r\n"); }
    uintptr_t fp=SafeReadable((void*)(g_npNative+g_npPawnOff),8)?*(uintptr_t*)(g_npNative+g_npPawnOff):0; char fpn[96]="-"; if(LooksLikePtr(fp))ClassName(fp,fpn,sizeof(fpn));
    Markerf("[NP] native PC->Pawn now = 0x%llX(%s) %s\r\n",(unsigned long long)fp,fpn, fp==hero?"<< HERO":"(not hero)");
    Marker("[NP] === Phase 4d done. ===\r\n");
}

// ---- PHASE 4e (S79 moonshot): camera-rig recon + pull-back (pure off-thread, no hook) ----
static void DoCamFix(){
    Marker("[CF] === Phase 4e: camera-rig recon + pull-back ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer"); if(!L){ Marker("[CF] no LocalPlayer ===\r\n"); return; }
    uintptr_t pc=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0; if(!LooksLikePtr(pc)){ Marker("[CF] L->PC null ===\r\n"); return; }
    uint32_t po=PropOffsetOnClass(ClassOf(pc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero=SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0; if(!LooksLikePtr(hero)){ Marker("[CF] PC->Pawn null ===\r\n"); return; }
    char hcn[96]="-",pcn[96]="-"; ClassName(hero,hcn,sizeof(hcn)); ClassName(pc,pcn,sizeof(pcn));
    uintptr_t cam=FindInstClassSub("CameraManager"); char ccn[96]="-"; if(cam) ClassName(cam,ccn,sizeof(ccn));
    Markerf("[CF] hero=0x%llX(%s) pc=0x%llX(%s) camMgr=0x%llX(%s)\r\n",(unsigned long long)hero,hcn,(unsigned long long)pc,pcn,(unsigned long long)cam,ccn);
    Marker("[CF] hero direct components (Outer==hero):\r\n");
    uintptr_t spring=0, camComp=0; int n=0;
    ForEachObject([&](uintptr_t o)->bool{
        uintptr_t outer=SafeReadable((void*)(o+OUTER_OFF),8)?*(uintptr_t*)(o+OUTER_OFF):0; if(outer!=hero) return false;
        char cn[96]="?",on[96]="?"; ClassName(o,cn,sizeof(cn)); ObjName(o,on,sizeof(on));
        Markerf("[CF]   0x%llX cls=%s name=%s\r\n",(unsigned long long)o,cn,on);
        if(!spring && (strstr(cn,"SpringArm")||strstr(cn,"Boom"))) spring=o;
        if(!camComp && strstr(cn,"CameraComponent")) camComp=o;
        return (++n>=48);
    });
    Markerf("[CF] spring=0x%llX camComp=0x%llX (found %d direct comps)\r\n",(unsigned long long)spring,(unsigned long long)camComp,n);
    if(spring){ uint32_t armOff=PropOffsetOnClass(ClassOf(spring),"TargetArmLength");
        if(armOff!=0xFFFFFFFF && SafeReadable((void*)(spring+armOff),4)){ float cur=*(float*)(spring+armOff);
            Markerf("[CF] spring TargetArmLength @+0x%X = %.1f -> setting 2500\r\n",armOff,cur);
            *(float*)(spring+armOff)=2500.0f; }
        else Marker("[CF] TargetArmLength offset not resolved on spring-arm\r\n");
    } else Marker("[CF] no spring-arm found on hero — camera likely driven by a custom LokiPlayerCameraManager (needs a different lever)\r\n");
    Marker("[CF] === Phase 4e done — check the screen (view pulls back only if the spring-arm drives it). ===\r\n");
}

// ---- PHASE 4f (S79 moonshot): recon the deploy entry-point functions (read-only, no hook) ----
static void DoDeployRecon(){
    Marker("[DR] === Phase 4f: deploy entry-point recon (hero + PC) ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)? (SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0) : 0;
    if(!LooksLikePtr(pc)) pc=FindInstExactClass("LokiPlayerController");
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)? (SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0) : 0;
    static const char* keys[]={"Deploy","DropPlane","DropPod","Landed","OnLand","Restart","SetupPlayerInput","InitInput",
        "InitializeInput","BindInput","MappingContext","ExitPod","FinishDrop","BeginDeploy","StartDeploy","OnRep_Pawn",
        "PawnClientRestart","ClientSetHUD","AddHUD","CreateHUD","SetInputMode"};
    const int NK=21;
    if(LooksLikePtr(hero)){ char hcn[96]="-"; ClassName(hero,hcn,sizeof(hcn)); Markerf("[DR] --- HERO (%s) matching fns ---\r\n",hcn); ListFuncsMatching(ClassOf(hero),keys,NK); }
    else Marker("[DR] no hero\r\n");
    if(LooksLikePtr(pc)){ char pcn[96]="-"; ClassName(pc,pcn,sizeof(pcn)); Markerf("[DR] --- PC (%s) matching fns ---\r\n",pcn); ListFuncsMatching(ClassOf(pc),keys,NK); }
    else Marker("[DR] no PC\r\n");
    Marker("[DR] === Phase 4f done ===\r\n");
}

// ---- PHASE 4g (S79 moonshot): run the client-side possession setup we bypassed (OnRep_Pawn + ClientRestart) ----
static uintptr_t g_crPc=0, g_crHero=0, g_crCam=0;
static void* g_crOrpFn=0; static uintptr_t g_crOrpThunk=0,g_crOrpChild=0;
static void* g_crCrFn=0;  static uintptr_t g_crCrThunk=0, g_crCrChild=0; static uint32_t g_crNewPawn=0;
static bool ResolveCRestart(){
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer"); if(!L){ Marker("[CR] no LocalPlayer\r\n"); return false; }
    g_crPc=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0; if(!LooksLikePtr(g_crPc)){ Marker("[CR] L->PC null\r\n"); return false; }
    uint32_t po=PropOffsetOnClass(ClassOf(g_crPc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    g_crHero=SafeReadable((void*)(g_crPc+pawnOff),8)?*(uintptr_t*)(g_crPc+pawnOff):0; if(!LooksLikePtr(g_crHero)){ Marker("[CR] PC->Pawn null\r\n"); return false; }
    ResolveFunc(ClassOf(g_crPc),"OnRep_Pawn",&g_crOrpFn,&g_crOrpThunk,&g_crOrpChild);
    ResolveFunc(ClassOf(g_crPc),"ClientRestart",&g_crCrFn,&g_crCrThunk,&g_crCrChild); if(g_crCrChild) g_crNewPawn=g_offParam(g_crCrChild,"NewPawn",0);
    g_crCam=FindInstClassSub("CameraManager");
    char pcn[96]="-",hcn[96]="-"; ClassName(g_crPc,pcn,sizeof(pcn)); ClassName(g_crHero,hcn,sizeof(hcn));
    Markerf("[CR] pc=0x%llX(%s) hero=0x%llX(%s) orpThunk=0x%llX crThunk=0x%llX newPawnOff=0x%X camMgr=0x%llX\r\n",
            (unsigned long long)g_crPc,pcn,(unsigned long long)g_crHero,hcn,(unsigned long long)g_crOrpThunk,(unsigned long long)g_crCrThunk,g_crNewPawn,(unsigned long long)g_crCam);
    return g_crOrpThunk || g_crCrThunk;
}
static void DoCRestart(){
    Marker("[CR] === Phase 4g: client-side possession setup (OnRep_Pawn + ClientRestart) ===\r\n");
    if(g_crOrpThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        if(CallGuarded(g_crOrpFn,g_crOrpThunk,g_crOrpChild,(void*)g_crPc,g_pbuf,g_rbuf)) Marker("[CR] OnRep_Pawn FAULTED\r\n"); else Marker("[CR] OnRep_Pawn done\r\n"); }
    if(g_crCrThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_crNewPawn)=(uint64_t)g_crHero;
        if(CallGuarded(g_crCrFn,g_crCrThunk,g_crCrChild,(void*)g_crPc,g_pbuf,g_rbuf)) Marker("[CR] ClientRestart FAULTED\r\n"); else Marker("[CR] ClientRestart(hero) done\r\n"); }
    Marker("[CR] === Phase 4g done. ===\r\n");
}

// ---- PHASE 4h (S79 moonshot, visual capstone): pull the hero's CameraComponent up+back so the hunter is framed ----
static uintptr_t g_cfrHero=0, g_cfrComp=0;
static void* g_cfrFn=0; static uintptr_t g_cfrThunk=0,g_cfrChild=0;                 // K2_SetWorldLocationAndRotation (camera component)
static void* g_cfrGlaFn=0; static uintptr_t g_cfrGlaThunk=0,g_cfrGlaChild=0;        // K2_GetActorLocation (hero)
static uint32_t g_cfrLoc=0, g_cfrRot=0x18, g_cfrTele=0xFFFFFFFF; static volatile long g_cfrReps=0;
static bool ResolveCamFrame(){
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer"); if(!L){ Marker("[FR] no LocalPlayer\r\n"); return false; }
    uintptr_t pc=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0; if(!LooksLikePtr(pc)){ Marker("[FR] L->PC null\r\n"); return false; }
    uint32_t po=PropOffsetOnClass(ClassOf(pc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    g_cfrHero=SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0; if(!LooksLikePtr(g_cfrHero)){ Marker("[FR] PC->Pawn null\r\n"); return false; }
    ForEachObject([&](uintptr_t o)->bool{ uintptr_t outer=SafeReadable((void*)(o+OUTER_OFF),8)?*(uintptr_t*)(o+OUTER_OFF):0; if(outer!=g_cfrHero)return false; char cn[96]; if(ClassName(o,cn,sizeof(cn))&&strstr(cn,"CameraComponent")){ g_cfrComp=o; return true; } return false; });
    if(!g_cfrComp){ Marker("[FR] no CameraComponent on hero\r\n"); return false; }
    ResolveFunc(ClassOf(g_cfrComp),"K2_SetWorldLocationAndRotation",&g_cfrFn,&g_cfrThunk,&g_cfrChild);
    if(g_cfrChild){ g_cfrLoc=g_offParam(g_cfrChild,"NewLocation",0); g_cfrRot=g_offParam(g_cfrChild,"NewRotation",0x18); g_cfrTele=g_offParam(g_cfrChild,"bTeleport",0xFFFFFFFF); }
    ResolveFunc(ClassOf(g_cfrHero),"K2_GetActorLocation",&g_cfrGlaFn,&g_cfrGlaThunk,&g_cfrGlaChild);
    Markerf("[FR] hero=0x%llX camComp=0x%llX swlrThunk=0x%llX glaThunk=0x%llX loc@0x%X rot@0x%X tele@0x%X\r\n",
            (unsigned long long)g_cfrHero,(unsigned long long)g_cfrComp,(unsigned long long)g_cfrThunk,(unsigned long long)g_cfrGlaThunk,g_cfrLoc,g_cfrRot,g_cfrTele);
    return g_cfrThunk!=0 && g_cfrGlaThunk!=0;
}
static void DoCamFrame(){
    static uint8_t frbuf[0x240];
    // read the hero's WORLD location
    memset(frbuf,0,sizeof(frbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    double hx=0,hy=0,hz=0;
    if(!CallGuarded(g_cfrGlaFn,g_cfrGlaThunk,g_cfrGlaChild,(void*)g_cfrHero,frbuf,g_rbuf)){ hx=*(double*)(g_rbuf+0); hy=*(double*)(g_rbuf+8); hz=*(double*)(g_rbuf+16); }
    // put the camera in WORLD space directly above the hero, looking straight down.
    memset(frbuf,0,sizeof(frbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(double*)(frbuf+g_cfrLoc+0)=hx-60.0; *(double*)(frbuf+g_cfrLoc+8)=hy; *(double*)(frbuf+g_cfrLoc+16)=hz+3500.0;    // ~3500 above (authentic SUPERVIVE range), ~centered
    *(double*)(frbuf+g_cfrRot+0)=-89.0;   *(double*)(frbuf+g_cfrRot+8)=0.0; *(double*)(frbuf+g_cfrRot+16)=0.0;          // world pitch -89 (straight down)
    if(g_cfrTele!=0xFFFFFFFF && g_cfrTele<0x240) frbuf[g_cfrTele]=1;                                                    // bTeleport=true
    bool fault=CallGuarded(g_cfrFn,g_cfrThunk,g_cfrChild,(void*)g_cfrComp,frbuf,g_rbuf);
    if(InterlockedIncrement(&g_cfrReps)==1) Markerf(fault?"[FR] SetWorldLocationAndRotation FAULTED\r\n":"[FR] camera -> world (%.0f,%.0f,%.0f) pitch -89 (hero at %.0f,%.0f,%.0f); re-applying to hold\r\n",hx-60.0,hy,hz+3500.0,hx,hy,hz);
}

// ---- DEPLOY RECONSTRUCTION (S79→S80): find the hero living-state control (read-only, no hook) ----
// List every property on cls's chain whose name contains any keyword (name @ Offset_Internal +0x44).
static void ListPropsMatching(uintptr_t cls, const char* const* keys, int nkeys){
    int g=0; while(LooksLikePtr(cls)&&g++<12){
        char ccn[96]="?"; GetFNameStr(NameId(cls),ccn,sizeof(ccn));
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f)&&i++<1500){ char pn[128];
            if(GetFNameStr(NameId(f),pn,sizeof(pn))){ for(int k=0;k<nkeys;k++){ if(strstr(pn,keys[k])){ uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF; Markerf("[SR]   prop %s::%s @+0x%X\r\n",ccn,pn,off); break; } } }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static void DoStateRecon(){
    Marker("[SR] === deploy/living-state recon on the hero ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)? (SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0) : 0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)? (SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0) : 0;
    if(!LooksLikePtr(hero)){ Marker("[SR] no hero — abort\r\n"); return; }
    char hcn[96]="-"; ClassName(hero,hcn,sizeof(hcn));
    Markerf("[SR] hero=0x%llX(%s)  [BP-folded thunk = 0x%llX; anything else = natively callable]\r\n",
            (unsigned long long)hero,hcn,(unsigned long long)(g_modBase+kPiRva));
    static const char* fkeys[]={"LivingState","LifeState","Living","Alive","Dead","Deploy","Landed","Drop","Pod","Revive",
        "Respawn","Reveal","SetState","OnRep_","Visib","MeshVis","Hidden","Predrop","Ragdoll","Init","Setup"};
    Marker("[SR] --- matching functions (name / thunk) ---\r\n"); ListFuncsMatching(ClassOf(hero),fkeys,21);
    static const char* pkeys[]={"State","Living","Alive","Dead","Hidden","Predrop","Drop","Deploy","Life","Revive","bIs"};
    Marker("[SR] --- matching properties (name @ offset) ---\r\n"); ListPropsMatching(ClassOf(hero),pkeys,11);
    Marker("[SR] === done ===\r\n");
}

// ---- DEPLOY RECONSTRUCTION step 1 (MODE_LIVINGSTATE): set LivingState=Alive + fire visibility handlers ----
static uintptr_t g_lsHero=0;
static void* g_lsGetFn=0;   static uintptr_t g_lsGetThunk=0,g_lsGetChild=0;      // GetLivingState -> byte
static void* g_lsOrpFn=0;   static uintptr_t g_lsOrpThunk=0,g_lsOrpChild=0;      // OnRep_LivingState
static void* g_lsNewFn=0;   static uintptr_t g_lsNewThunk=0,g_lsNewChild=0;      // OnNewLivingState
static void* g_lsVisFn=0;   static uintptr_t g_lsVisThunk=0,g_lsVisChild=0;      // OnCharacterVisibilityUpdated
constexpr uintptr_t LS_LIVINGSTATE=0x1090, LS_PREDROP=0x1BE8, LS_ONGROUND=0x1B20, LS_MIDAIR=0x1B21, LS_VISSTATE=0xD38;
static bool ResolveLivingState(){
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer"); if(!L){ Marker("[LS] no LocalPlayer\r\n"); return false; }
    uintptr_t pc=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0; if(!LooksLikePtr(pc)){ Marker("[LS] L->PC null\r\n"); return false; }
    uint32_t po=PropOffsetOnClass(ClassOf(pc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    g_lsHero=SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0; if(!LooksLikePtr(g_lsHero)){ Marker("[LS] PC->Pawn null\r\n"); return false; }
    uintptr_t hc=ClassOf(g_lsHero);
    ResolveFunc(hc,"GetLivingState",&g_lsGetFn,&g_lsGetThunk,&g_lsGetChild);
    ResolveFunc(hc,"OnRep_LivingState",&g_lsOrpFn,&g_lsOrpThunk,&g_lsOrpChild);
    ResolveFunc(hc,"OnNewLivingState",&g_lsNewFn,&g_lsNewThunk,&g_lsNewChild);
    ResolveFunc(hc,"OnCharacterVisibilityUpdated",&g_lsVisFn,&g_lsVisThunk,&g_lsVisChild);
    char hcn[96]="-"; ClassName(g_lsHero,hcn,sizeof(hcn));
    Markerf("[LS] hero=0x%llX(%s) getThunk=0x%llX orpThunk=0x%llX newThunk=0x%llX visThunk=0x%llX aliveVal=%d\r\n",
            (unsigned long long)g_lsHero,hcn,(unsigned long long)g_lsGetThunk,(unsigned long long)g_lsOrpThunk,(unsigned long long)g_lsNewThunk,(unsigned long long)g_lsVisThunk,(int)KALIVEVAL);
    return true;
}
static uint8_t LsRead(uintptr_t off){ return SafeReadable((void*)(g_lsHero+off),1)?*(uint8_t*)(g_lsHero+off):0xFF; }
static void DoLivingState(){
    Marker("[LS] === deploy step 1: LivingState -> Alive + reveal ===\r\n");
    // READ current
    uint8_t getVal=0xFF; if(g_lsGetThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(g_lsGetFn,g_lsGetThunk,g_lsGetChild,(void*)g_lsHero,g_pbuf,g_rbuf)) getVal=g_rbuf[0]; }
    Markerf("[LS] BEFORE: GetLivingState=%d rawLivingState@0x1090=%d predrop@0x1BE8=%d onGround@0x1B20=%d visState@0xD38=%d\r\n",
            getVal,LsRead(LS_LIVINGSTATE),LsRead(LS_PREDROP),LsRead(LS_ONGROUND),LsRead(LS_VISSTATE));
    // WRITE: Alive, not pre-drop-hidden, on ground
    if(SafeReadable((void*)(g_lsHero+LS_LIVINGSTATE),1)) *(uint8_t*)(g_lsHero+LS_LIVINGSTATE)=(uint8_t)KALIVEVAL;
    if(SafeReadable((void*)(g_lsHero+LS_PREDROP),1))     *(uint8_t*)(g_lsHero+LS_PREDROP)=0;
    if(SafeReadable((void*)(g_lsHero+LS_ONGROUND),1))    *(uint8_t*)(g_lsHero+LS_ONGROUND)=1;
    if(SafeReadable((void*)(g_lsHero+LS_MIDAIR),1))      *(uint8_t*)(g_lsHero+LS_MIDAIR)=0;
    Marker("[LS] wrote LivingState=Alive, predrop=0, onGround=1\r\n");
    // FIRE the client-side apply handlers (native)
    if(g_lsOrpThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_lsOrpFn,g_lsOrpThunk,g_lsOrpChild,(void*)g_lsHero,g_pbuf,g_rbuf)) Marker("[LS] OnRep_LivingState FAULTED\r\n"); else Marker("[LS] OnRep_LivingState done\r\n"); }
    if(g_lsNewThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_lsNewFn,g_lsNewThunk,g_lsNewChild,(void*)g_lsHero,g_pbuf,g_rbuf)) Marker("[LS] OnNewLivingState FAULTED\r\n"); else Marker("[LS] OnNewLivingState done\r\n"); }
    if(g_lsVisThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_lsVisFn,g_lsVisThunk,g_lsVisChild,(void*)g_lsHero,g_pbuf,g_rbuf)) Marker("[LS] OnCharacterVisibilityUpdated FAULTED\r\n"); else Marker("[LS] OnCharacterVisibilityUpdated done\r\n"); }
    uint8_t getVal2=0xFF; if(g_lsGetThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(g_lsGetFn,g_lsGetThunk,g_lsGetChild,(void*)g_lsHero,g_pbuf,g_rbuf)) getVal2=g_rbuf[0]; }
    Markerf("[LS] AFTER: GetLivingState=%d rawLivingState@0x1090=%d predrop@0x1BE8=%d\r\n",getVal2,LsRead(LS_LIVINGSTATE),LsRead(LS_PREDROP));
    Marker("[LS] === done — check the screen for a visible hero. ===\r\n");
}

// ---- DEPLOY RECONSTRUCTION step 2 (MODE_MESHDIAG): is the hero's skeletal mesh present-but-hidden, or unassigned? ----
static bool OuterChainReaches(uintptr_t o, uintptr_t target){ int g=0; while(LooksLikePtr(o)&&g++<6){ uintptr_t outer=SafeReadable((void*)(o+OUTER_OFF),8)?*(uintptr_t*)(o+OUTER_OFF):0; if(outer==target)return true; o=outer; } return false; }
static void DoMeshDiag(){
    Marker("[MD] === mesh diagnostic on the hero ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)? (SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0) : 0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)? (SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0) : 0;
    if(!LooksLikePtr(hero)){ Marker("[MD] no hero — abort\r\n"); return; }
    char hcn[96]="-"; ClassName(hero,hcn,sizeof(hcn)); Markerf("[MD] hero=0x%llX(%s)\r\n",(unsigned long long)hero,hcn);
    int n=0;
    ForEachObject([&](uintptr_t o)->bool{
        char cn[96]; if(!ClassName(o,cn,sizeof(cn))) return false;
        if(!strstr(cn,"SkeletalMeshComponent") && !strstr(cn,"SkinnedMeshComponent") && !strstr(cn,"StaticMeshComponent")) return false;
        if(!OuterChainReaches(o,hero)) return false;
        char on[96]="?"; ObjName(o,on,sizeof(on));
        uint32_t visOff=PropOffsetOnClass(ClassOf(o),"bVisible"); uint32_t hidOff=PropOffsetOnClass(ClassOf(o),"bHiddenInGame");
        uint32_t smOff=PropOffsetOnClass(ClassOf(o),"SkeletalMeshAsset"); if(smOff==0xFFFFFFFF) smOff=PropOffsetOnClass(ClassOf(o),"SkeletalMesh"); if(smOff==0xFFFFFFFF) smOff=PropOffsetOnClass(ClassOf(o),"StaticMesh");
        uint8_t vis=(visOff!=0xFFFFFFFF&&SafeReadable((void*)(o+visOff),1))?*(uint8_t*)(o+visOff):0xFF;
        uint8_t hid=(hidOff!=0xFFFFFFFF&&SafeReadable((void*)(o+hidOff),1))?*(uint8_t*)(o+hidOff):0xFF;
        uintptr_t sm=(smOff!=0xFFFFFFFF&&SafeReadable((void*)(o+smOff),8))?*(uintptr_t*)(o+smOff):0;
        char smn[96]="<none>"; if(LooksLikePtr(sm)) ObjName(sm,smn,sizeof(smn));
        Markerf("[MD]   %s '%s' bVisible=%d bHiddenInGame=%d meshOff@0x%X mesh=%s\r\n",cn,on,vis,hid,smOff,smn);
        return (++n>=16);
    });
    Markerf("[MD] (%d mesh comps under the hero)\r\n",n);
    ForEachObject([&](uintptr_t o)->bool{ uintptr_t outer=SafeReadable((void*)(o+OUTER_OFF),8)?*(uintptr_t*)(o+OUTER_OFF):0; if(outer!=hero)return false; char cn[96]; if(ClassName(o,cn,sizeof(cn))&&strstr(cn,"MeshManager")){ Markerf("[MD] LokiMeshManagerComponent=0x%llX\r\n",(unsigned long long)o); return true;} return false;});
    Marker("[MD] === done ===\r\n");
}

// ---- DEPLOY RECONSTRUCTION step 3 (MODE_MESHMGRRECON): find a native mesh-create on LokiMeshManagerComponent ----
static void ListAllFuncs(uintptr_t cls, int maxDepth){
    uintptr_t piThunk=g_modBase+kPiRva; int g=0;
    while(LooksLikePtr(cls)&&g++<maxDepth){
        char ccn[96]="?"; GetFNameStr(NameId(cls),ccn,sizeof(ccn));
        uintptr_t f=SafeReadable((void*)(cls+UST_CHILDREN),8)?*(uintptr_t*)(cls+UST_CHILDREN):0; int i=0;
        while(LooksLikePtr(f)&&i++<400){ char fn[128];
            if(GetFNameStr(NameId(f),fn,sizeof(fn))){ uintptr_t th=SafeReadable((void*)(f+UFUNC_FUNC),8)?*(uintptr_t*)(f+UFUNC_FUNC):0; Markerf("[MM]   %s::%s [%s] thunk=0x%llX\r\n",ccn,fn,(th==piThunk?"BP":"N"),(unsigned long long)th); }
            f=SafeReadable((void*)(f+FIELD_NEXT_UF),8)?*(uintptr_t*)(f+FIELD_NEXT_UF):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static void DoMeshMgrRecon(){
    Marker("[MM] === mesh-manager recon ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)? (SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0) : 0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)? (SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0) : 0;
    if(!LooksLikePtr(hero)){ Marker("[MM] no hero — abort\r\n"); return; }
    uintptr_t mm=0; ForEachObject([&](uintptr_t o)->bool{ if((SafeReadable((void*)(o+OUTER_OFF),8)?*(uintptr_t*)(o+OUTER_OFF):0)!=hero)return false; char cn[96]; if(ClassName(o,cn,sizeof(cn))&&strstr(cn,"MeshManager")){mm=o;return true;} return false;});
    if(mm){ Markerf("[MM] LokiMeshManagerComponent=0x%llX  [BP thunk=0x%llX]  its functions:\r\n",(unsigned long long)mm,(unsigned long long)(g_modBase+kPiRva)); ListAllFuncs(ClassOf(mm),2); }
    else Marker("[MM] no mesh manager found\r\n");
    Marker("[MM] --- hero cosmetics/mesh/setup fns ---\r\n");
    static const char* keys[]={"Cosmetic","Mesh","Skin","Character","Setup","Refresh","Rebuild","Attach","Create","Body","Skeletal","Skel"};
    ListFuncsMatching(ClassOf(hero),keys,12);
    Marker("[MM] === done ===\r\n");
}

// ---- DEPLOY RECONSTRUCTION step 4 (MODE_COSMETICS): build the character mesh via native RefreshCosmetics ----
static uintptr_t g_cmHero=0;
static void* g_cmRefFn=0; static uintptr_t g_cmRefThunk=0,g_cmRefChild=0;    // RefreshCosmetics
static void* g_cmOrpFn=0; static uintptr_t g_cmOrpThunk=0,g_cmOrpChild=0;    // OnRep_CosmeticsAssetID
static void* g_cmGetFn=0; static uintptr_t g_cmGetThunk=0,g_cmGetChild=0;    // GetCosmeticsAssetID
static void* g_cmVisFn=0; static uintptr_t g_cmVisThunk=0,g_cmVisChild=0;    // OnCharacterVisibilityUpdated
static bool ResolveCosmetics(){
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer"); if(!L){ Marker("[CM] no LocalPlayer\r\n"); return false; }
    uintptr_t pc=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0; if(!LooksLikePtr(pc)){ Marker("[CM] L->PC null\r\n"); return false; }
    uint32_t po=PropOffsetOnClass(ClassOf(pc),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    g_cmHero=SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0; if(!LooksLikePtr(g_cmHero)){ Marker("[CM] PC->Pawn null\r\n"); return false; }
    uintptr_t hc=ClassOf(g_cmHero);
    ResolveFunc(hc,"RefreshCosmetics",&g_cmRefFn,&g_cmRefThunk,&g_cmRefChild);
    ResolveFunc(hc,"OnRep_CosmeticsAssetID",&g_cmOrpFn,&g_cmOrpThunk,&g_cmOrpChild);
    ResolveFunc(hc,"GetCosmeticsAssetID",&g_cmGetFn,&g_cmGetThunk,&g_cmGetChild);
    ResolveFunc(hc,"OnCharacterVisibilityUpdated",&g_cmVisFn,&g_cmVisThunk,&g_cmVisChild);
    Markerf("[CM] hero=0x%llX refreshThunk=0x%llX orpThunk=0x%llX getThunk=0x%llX visThunk=0x%llX\r\n",
            (unsigned long long)g_cmHero,(unsigned long long)g_cmRefThunk,(unsigned long long)g_cmOrpThunk,(unsigned long long)g_cmGetThunk,(unsigned long long)g_cmVisThunk);
    return g_cmRefThunk!=0;
}
// ★★★ S80c WARNING — THIS COUNTER IS BROKEN AND ITS 0 INVENTED AN ENTIRE FAKE WALL. DO NOT TRUST IT; DO NOT USE IT
// TO CONCLUDE "no mesh". It greps class names for "SkeletalMeshComponent"/"SkinnedMeshComponent", but this build's hero
// mesh component class is `BP_Assault_DefaultSKMeshComponent_C` — "SKMeshComponent" does NOT contain "SkeletalMesh
// Component", so the filter MISSES it and returns 0 for a component that exists, has SK_Assault_Default_LOD1 assigned,
// has bVisible=true/bHiddenInGame=false/bRecentlyRendered=true, and is ON SCREEN (the user saw it at S79 Phase 4d).
// Its bogus 0 is the sole basis of S79's "MESHDIAG: no character SkeletalMeshComponent", the whole cosmetics chase
// (MESHMGRRECON/COSMETICS/COSMENUM/SETCOSMETIC), "RefreshCosmetics built nothing", "the cosmetics controller is
// missing", and the S79 "DEFINITIVE deploy-context wall". All of it collapsed when the mesh was read DIRECTLY.
// ⇒ To check the character mesh, read `ACharacter::Mesh` by reflection (PropOffsetOnClass(hc,"Mesh"), @+0x450 this
// build) and its SkeletalMesh — the way DoBPCall now does. Kept only so the older modes still compile.
static int CountHeroSkeletals(){ int n=0; ForEachObject([&](uintptr_t o)->bool{ char cn[96]; if(!ClassName(o,cn,sizeof(cn)))return false; if(!strstr(cn,"SkeletalMeshComponent")&&!strstr(cn,"SkinnedMeshComponent")&&!strstr(cn,"MeshComponent"))return false; if(!OuterChainReaches(o,g_cmHero))return false; char on[96]="?"; ObjName(o,on,sizeof(on)); Markerf("[CM]   mesh comp: %s '%s'\r\n",cn,on); return (++n>=12); }); return n; }
static void DoCosmetics(){
    Marker("[CM] === deploy step 4: RefreshCosmetics (build character mesh) ===\r\n");
    Markerf("[CM] skeletal meshes BEFORE: %d\r\n",CountHeroSkeletals());
    if(g_cmGetThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(g_cmGetFn,g_cmGetThunk,g_cmGetChild,(void*)g_cmHero,g_pbuf,g_rbuf)) Markerf("[CM] CosmeticsAssetID = 0x%llX 0x%llX\r\n",(unsigned long long)*(uint64_t*)(g_rbuf),(unsigned long long)*(uint64_t*)(g_rbuf+8)); }
    if(g_cmRefThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_cmRefFn,g_cmRefThunk,g_cmRefChild,(void*)g_cmHero,g_pbuf,g_rbuf)) Marker("[CM] RefreshCosmetics FAULTED\r\n"); else Marker("[CM] RefreshCosmetics done\r\n"); }
    if(g_cmOrpThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_cmOrpFn,g_cmOrpThunk,g_cmOrpChild,(void*)g_cmHero,g_pbuf,g_rbuf)) Marker("[CM] OnRep_CosmeticsAssetID FAULTED\r\n"); else Marker("[CM] OnRep_CosmeticsAssetID done\r\n"); }
    // re-assert Alive + visibility
    if(SafeReadable((void*)(g_cmHero+0x1090),1)) *(uint8_t*)(g_cmHero+0x1090)=1;
    if(SafeReadable((void*)(g_cmHero+0x1BE8),1)) *(uint8_t*)(g_cmHero+0x1BE8)=0;
    if(g_cmVisThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_cmVisFn,g_cmVisThunk,g_cmVisChild,(void*)g_cmHero,g_pbuf,g_rbuf)) Marker("[CM] OnCharacterVisibilityUpdated FAULTED\r\n"); else Marker("[CM] OnCharacterVisibilityUpdated done\r\n"); }
    Markerf("[CM] skeletal meshes AFTER: %d\r\n",CountHeroSkeletals());
    Marker("[CM] === done — check the screen. ===\r\n");
}

// ---- TOOL VALIDATION (MODE_VTDUMP): confirm the ProcessEvent RVA against the live vtable (read-only) ----
static void VtDumpOne(const char* nm, uintptr_t o, uintptr_t targetRva){
    if(!LooksLikePtr(o)) { Markerf("[VT] %s: null\r\n",nm); return; }
    uintptr_t vt=SafeReadable((void*)o,8)?*(uintptr_t*)o:0; if(!LooksLikePtr(vt)){ Markerf("[VT] %s: bad vtable\r\n",nm); return; }
    Markerf("[VT] %s obj=0x%llX vtable rva=0x%llX\r\n",nm,(unsigned long long)o,(unsigned long long)(vt-g_modBase));
    int found=-1;
    for(int i=0;i<160;i++){ if(!SafeReadable((void*)(vt+i*8),8))break; uintptr_t f=*(uintptr_t*)(vt+i*8); if(f<=g_modBase||f>=g_modBase+0xC000000)continue; if((f-g_modBase)==targetRva){ found=i; Markerf("[VT]   %s slot %d = ProcessEvent RVA 0x%llX  <<< MATCH\r\n",nm,i,(unsigned long long)targetRva); } }
    if(found<0) Markerf("[VT]   %s: ProcessEvent RVA 0x%llX NOT in first 160 vtable slots (RVA may be WRONG)\r\n",nm,(unsigned long long)targetRva);
}
static void DoVtDump(){
    Marker("[VT] === ProcessEvent RVA validation ===\r\n");
    uintptr_t targetRva=kProcEventRva;
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L)L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)?(SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0):0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)?(SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0):0;
    uintptr_t gs=FindInstClassSub("LokiGameState");
    VtDumpOne("hero",hero,targetRva);
    VtDumpOne("PC",pc,targetRva);
    VtDumpOne("GameState",gs,targetRva);
    // Also: dump hero vtable slots 60-75 (ProcessEvent is ~slot 66-68 in UE5.4) as RVAs so I can eyeball the real one.
    if(LooksLikePtr(hero)){ uintptr_t vt=*(uintptr_t*)hero; Marker("[VT] hero vtable slots 60..75:\r\n");
        for(int i=60;i<76;i++){ if(!SafeReadable((void*)(vt+i*8),8))break; uintptr_t f=*(uintptr_t*)(vt+i*8); uintptr_t rva=(f>g_modBase&&f<g_modBase+0xC000000)?f-g_modBase:0; Markerf("[VT]   slot %d rva=0x%llX\r\n",i,(unsigned long long)rva); } }
    Marker("[VT] === done ===\r\n");
}

// ---- Route D (MODE_SPECTATOR_CAM): reveal the live tutorial world for the spectator ----
// The DS client Joins the real LVL_Tutorial with a live LokiGameState (S70) but sits behind the
// "DROP IN... LOADING" overlay as a dead spectator. This mode censuses every UMG UUserWidget, then
// holds any loading-ish widget SetVisibility(Collapsed) on the game thread for ~40s so we can SEE what
// the world/camera actually shows. Read-mostly: the only calls are UWidget::SetVisibility (guarded).
static bool CallGuarded(void* fn, uintptr_t th, uintptr_t ch, void* ctx, void* pb, void* rb){
    __try { CallNative(fn,th,ch,ctx,pb,rb); return false; } __except(EXCEPTION_EXECUTE_HANDLER){ return true; }
}
static void* g_svFn=0; static uintptr_t g_svThunk=0, g_svChild=0; static uint32_t g_svVisOff=0xFFFFFFFF;
static uintptr_t g_loadWidgets[48]={0}; static int g_nLoadW=0; static volatile long g_scHits=0;
// Fly-cam puppet: move the dead-spectator pawn directly (input pipeline is dead in the un-deployed state).
// S76: RootComponent + RelativeLocation offsets are RESOLVED BY REFLECTION (both are UPROPERTYs) — a
// hardcoded 0x1B0 guess crashed the client (it resolved into read-only module memory and a keypress wrote
// there). All writes are HEAP-GUARDED. WASD = move (yaw steered by arrows), Space/Ctrl = up/down.
static uintptr_t g_specPawn=0, g_specRoot=0; static HWND g_hwnd=0; static double g_yaw=0.0;
static uint32_t g_specLocOff=0xFFFFFFFF;
static uintptr_t g_moveComp=0; static uint32_t g_velOff=0xFFFFFFFF;
static bool IsHeapObj(uintptr_t v){ return v>=0x10000000000ull && v<0x00007F0000000000ull && (v&7)==0; }
static uint32_t PropOffsetOnClass(uintptr_t cls,const char* name){
    int g=0; while(LooksLikePtr(cls)&&g++<14){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f)&&i++<1200){ if(NameIs(f,name)){ return SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF; } f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
    return 0xFFFFFFFF;
}
// S77 translation: move the SPECTATOR PAWN itself via K2_SetActorLocation (engine setter -> propagates the
// transform; the native dead-spectator camera targets the pawn, so moving the pawn moves the view). The S77
// velocity puppet went inert (the un-deployed SpectatorPawnMovement integrator doesn't tick), so drive position
// directly. Seed the tracked position from the pawn root's RelativeLocation (reading is fine; only WRITING a raw
// RelativeLocation wouldn't propagate).
static uintptr_t g_spPawn=0, g_spRoot=0;
static void* g_spSlaFn=0; static uintptr_t g_spSlaThunk=0, g_spSlaChild=0; static uint32_t g_spSlaLoc=0xFFFFFFFF, g_spSlaTele=0xFFFFFFFF;
static uint32_t g_spRelLocOff=0xFFFFFFFF; static double g_spX=0,g_spY=0,g_spZ=0,g_spYaw2=0; static bool g_spSeeded=false;
static volatile long g_moveArmed=0, g_moveDone=0;   // S77 phase-2 single-move test
// S78 refinement #1 — mouse-relative steering (S78a: MEMORY-DIFF auto-lock). ControlRotation is NOT a reflected
// UPROPERTY here, and a one-shot rotator scan MISSED the view yaw (it read 0 before the user rotated, so the
// filter dropped it). Instead: snapshot the PC + PlayerCameraManager at resolve, then each ~1s compare every
// 8-byte-aligned DOUBLE (FVector/FRotator are doubles in this LWC build) against the snapshot. The view yaw is
// the offset whose value keeps SWINGING as the user looks around — auto-LOCK it as the steering source (no
// rebuild needed). g_viewRotOff holds the offset of the yaw VALUE (read directly), not the FRotator base.
static uintptr_t g_viewYawObj=0;          // object holding the view yaw (PC or camera mgr)
static uint32_t  g_viewRotOff=0xFFFFFFFF; // byte offset of the yaw DOUBLE within g_viewYawObj
static bool      g_viewYawEnabled=false;  // once true (auto-locked), the heading follows the view yaw (arrows nudge)
static double    g_manualYawOff=0.0;      // arrows nudge this on top of the mouse yaw (fine-tune / fallback)
// one-time reference scan (logged once; not used for steering after the diff approach)
struct RotCand { uintptr_t obj; uint32_t off; char tag[24]; };
static RotCand   g_rotCands[16]; static int g_nRotCands=0;
// diff-discovery state (S78a v2): snapshot SEVERAL candidate objects and diff BOTH float + double, since the
// view yaw wasn't a double in the PC/CameraManager (it's a float, elsewhere, or out of range). Each object gets a
// 0x4000 snapshot; the yaw is whatever value SWINGS widest as the user looks around (float or double).
static const int kMaxDiffObj=6, kDiffLen=0x10000;
struct DiffObj { uintptr_t obj; uint8_t* snap; uint32_t len; char tag[16]; };
static uint8_t   g_snapBuf[kMaxDiffObj][kDiffLen];
static DiffObj   g_dobj[kMaxDiffObj]; static int g_nDobj=0;
enum YawKind { YK_DOUBLE=0, YK_FLOAT=1, YK_QUAT=2 };   // how to read the yaw at g_viewRotOff
struct YawTrack { uintptr_t obj; uint32_t off; int kind; double last, lo, hi; int moves; };
static YawTrack  g_yt[64]; static int g_nYt=0;
static int       g_viewYawKind=YK_DOUBLE;  // the locked yaw's storage kind
// S78a v3 — read the view yaw by CALLING a rotation getter UFunction (robust vs memory-format guessing; the
// rotation isn't a plain FRotator in range in any scanned object, so it's likely a quaternion internally). The
// getter returns a clean FRotator (degrees) on the game thread. Called inside DoStepMove so the heading is fresh.
static void*     g_rotFn=0; static uintptr_t g_rotThunk=0, g_rotChild=0; static uintptr_t g_rotCtx=0;
static uint32_t  g_rotRetOff=0; static const char* g_rotName="?";
static double    g_viewYawLive=0; static volatile long g_viewYawValid=0; static volatile long g_rotLogN=0;
// S78a v4: K2_GetActorLocation (seed the fly position from the pawn's WORLD location so the vtable hook doesn't
// teleport the view to origin) + a dirty flag so the per-frame hook only moves when the user is actually flying.
static void*     g_glaFn=0; static uintptr_t g_glaThunk=0, g_glaChild=0; static uint32_t g_glaRetOff=0;
static volatile long g_moveDirty=0, g_spSeededVt=0;
// S78b — tame the hyper-fast native mouse-look: find float sensitivity fields and continuously re-write them to
// (original * kSensMul) so rotation is controllable. kSensMul is aggressive because the native rate is extreme.
static const float kSensMul=0.06f;
static uintptr_t g_sensObj[12]; static uint32_t g_sensOff[12]; static float g_sensTarget[12]; static int g_nSens=0;
// S78c — camera-rotation take-over: capture raw mouse delta (WM_INPUT, works with the cursor locked) + locate the
// camera POV rotation (in the CameraManager's CameraCachePrivate) so a controlled-speed rotation can override the
// native hyper-fast free-look. Stage 1 = capture + locate + log (no override yet).
static volatile long g_mouseDX=0, g_mouseDY=0, g_mouseEvents=0; static uintptr_t g_camMgr=0;
// S78c take-over: spawn my own ACameraActor as the view target and drive its rotation (+ position). kStage2a uses a
// FIXED rotation to prove the view switches to my camera (mouse should stop rotating it); then mouse-drive it.
// S78c: the camera take-over is DISABLED — the game's camera manager reverts our view-target every frame (cam+0x420
// stays the DefaultPawn no matter how often we re-SetViewTargetWithBlend), so a spawned camera never renders. The
// native free-look rotation is controlled inside the game's dead-spectator camera code (not a settable field, POV
// not findable in memory, view-target un-stealable). Left here (flag off) for a future deeper camera-hook attempt.
// With this false, the shim uses the WORKING path: DefaultPawn view-target + vtable-hook position + native rotation.
static const bool kTakeoverCam=false; static const bool kStage2aFixedRot=true;
static uintptr_t g_myCam=0; static double g_camYaw=0.0, g_camPitch=-12.0; static volatile long g_camSpawnTried=0;
static void* g_sraFn=0; static uintptr_t g_sraThunk=0, g_sraChild=0; static uint32_t g_sraRotOff=0, g_sraTele=0xFFFFFFFF;
static uintptr_t g_toPC=0, g_toCamCls=0;
static void* g_toSvtbFn=0; static uintptr_t g_toSvtbThunk=0, g_toSvtbChild=0; static uint32_t g_toSvtbTgt=0, g_toSvtbBlend=8;
static void* g_toSlaFn=0; static uintptr_t g_toSlaThunk=0, g_toSlaChild=0; static uint32_t g_toSlaLoc=0, g_toSlaTele=0x19;
// per-step input state (set off-thread, consumed on the game thread in DoStepMove) + speed with boost applied
static volatile long g_inFwd=0,g_inBack=0,g_inLeft=0,g_inRight=0,g_inUp=0,g_inDn=0;
static double    g_stepSp=26.0, g_stepSpV=18.0;
static bool IsGameFocused(){ HWND fg=GetForegroundWindow(); DWORD pid=0; if(fg) GetWindowThreadProcessId(fg,&pid); return pid==GetCurrentProcessId(); }
static void ResolveSpectatorCam(){
    static const char* kKeys[]={"Loading","LoadScreen","DropIn","Deploy","MatchLoad","Splash","Intro","Startup","Transition","BlackScreen","Loadout"};
    uintptr_t widgetCls=0; int total=0;
    ForEachObject([&](uintptr_t o)->bool{
        uintptr_t c=ClassOf(o); if(!LooksLikePtr(c))return false;
        if(!SuperChainHas(c,"UserWidget"))return false;
        char on[160]="?",cn[160]="?"; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false;
        GetFNameStr(NameId(c),cn,sizeof(cn)); total++;
        Markerf("[WGT] 0x%llX %s (cls %s)\r\n",(unsigned long long)o,on,cn);
        if(!widgetCls) widgetCls=c;
        for(int k=0;k<(int)(sizeof(kKeys)/sizeof(kKeys[0]));k++){ if(strstr(cn,kKeys[k])||strstr(on,kKeys[k])){ if(g_nLoadW<48) g_loadWidgets[g_nLoadW++]=o; break; } }
        return false;
    });
    if(widgetCls){ ResolveFunc(widgetCls,"SetVisibility",&g_svFn,&g_svThunk,&g_svChild); if(g_svChild) g_svVisOff=ParamOffset(g_svChild,"InVisibility"); }
    uintptr_t cam=FindInstClassSub("CameraManager");
    uintptr_t pc=FindInstClassSub("LokiPlayerController");
    // Drive the dead-spectator's SpectatorPawnMovement Velocity (S75 velocity-puppet pattern): the integrator
    // moves the pawn + updates the cached world transform (a raw RelativeLocation poke wouldn't propagate).
    uintptr_t mc=FindInstClassSub("SpectatorPawnMovement"); if(!mc) mc=FindInstClassSub("PawnMovement");
    g_moveComp=mc; char mcn[128]="?";
    if(IsHeapObj(mc)){ ClassName(mc,mcn,sizeof(mcn)); g_velOff=PropOffsetOnClass(ClassOf(mc),"Velocity"); }
    uintptr_t updComp=0; uint32_t ucOff=(IsHeapObj(mc))?PropOffsetOnClass(ClassOf(mc),"UpdatedComponent"):0xFFFFFFFF;
    if(ucOff!=0xFFFFFFFF && IsHeapObj(mc) && SafeReadable((void*)(mc+ucOff),8)) updComp=*(uintptr_t*)(mc+ucOff);
    // S77 translation: resolve the spectator pawn actor + K2_SetActorLocation on it, seed pos from the root's RelativeLocation.
    // Find the spectator pawn ACTOR (its class name is NOT "Spectator" — only the SpectatorPawnMovement component
    // is). Primary: PC->SpectatorPawn. Fallback: the actor whose RootComponent == the movement comp's
    // UpdatedComponent (g_spRoot).
    g_spPawn=0; g_spRoot=updComp;
    if(IsHeapObj(pc)){ uint32_t spOff=PropOffsetOnClass(ClassOf(pc),"SpectatorPawn");
        if(spOff!=0xFFFFFFFF && SafeReadable((void*)(pc+spOff),8)){ uintptr_t sp=*(uintptr_t*)(pc+spOff); if(IsHeapObj(sp)) g_spPawn=sp; } }
    if(!IsHeapObj(g_spPawn) && IsHeapObj(g_spRoot)){
        ForEachObject([&](uintptr_t o)->bool{ uintptr_t c=ClassOf(o); if(!LooksLikePtr(c)||!SuperChainHas(c,"Pawn"))return false;
            uint32_t rcOff=PropOffsetOnClass(c,"RootComponent"); if(rcOff==0xFFFFFFFF)return false;
            if(SafeReadable((void*)(o+rcOff),8) && *(uintptr_t*)(o+rcOff)==(uintptr_t)g_spRoot){ g_spPawn=o; return true; } return false; });
    }
    char g_spCn[96]="?"; if(IsHeapObj(g_spPawn)) ClassName(g_spPawn,g_spCn,sizeof(g_spCn));
    Markerf("[SPEC] spPawn resolve: pc=0x%llX spPawn=0x%llX class=%s\r\n",(unsigned long long)pc,(unsigned long long)g_spPawn,g_spCn);
    // S77 phase-3 finish: the CAMERA's view target is the DefaultPawn (probe: PlayerCameraManager+0x420), NOT the
    // SpectatorPawn — so moving the SpectatorPawn didn't move the view. RETARGET the move to the view-target pawn.
    { uintptr_t vt=0;
      if(IsHeapObj(cam)&&SafeReadable((void*)(cam+0x420),8)){ uintptr_t t=*(uintptr_t*)(cam+0x420); if(IsHeapObj(t)&&LooksLikePtr(ClassOf(t))&&SuperChainHas(ClassOf(t),"Pawn")) vt=t; }
      if(!IsHeapObj(vt)) vt=FindInstClassSub("DefaultPawn");
      if(IsHeapObj(vt)){ g_spPawn=vt; char vn[96]="?"; ClassName(vt,vn,sizeof(vn));
        // re-seed pos from the new pawn's root RelativeLocation
        uintptr_t rc=0; uint32_t rcOff=PropOffsetOnClass(ClassOf(vt),"RootComponent"); if(rcOff!=0xFFFFFFFF&&SafeReadable((void*)(vt+rcOff),8)) rc=*(uintptr_t*)(vt+rcOff);
        if(IsHeapObj(rc)){ uint32_t ro=PropOffsetOnClass(ClassOf(rc),"RelativeLocation"); if(ro!=0xFFFFFFFF&&SafeReadable((void*)(rc+ro),24)){ double* P=(double*)(rc+ro); g_spX=P[0];g_spY=P[1];g_spZ=P[2]; } }
        Markerf("[SPEC] RETARGET move -> camera view-target 0x%llX (%s) seed=(%.0f,%.0f,%.0f)\r\n",(unsigned long long)vt,vn,g_spX,g_spY,g_spZ); } }
    if(IsHeapObj(g_spPawn)){ ResolveFunc(ClassOf(g_spPawn),"K2_SetActorLocation",&g_spSlaFn,&g_spSlaThunk,&g_spSlaChild);
        if(g_spSlaChild){ g_spSlaLoc=ParamOffset(g_spSlaChild,"NewLocation"); g_spSlaTele=ParamOffset(g_spSlaChild,"bTeleport"); } }
    if(IsHeapObj(g_spRoot)){ g_spRelLocOff=PropOffsetOnClass(ClassOf(g_spRoot),"RelativeLocation");
        if(g_spRelLocOff!=0xFFFFFFFF && SafeReadable((void*)(g_spRoot+g_spRelLocOff),24)){ double* P=(double*)(g_spRoot+g_spRelLocOff); g_spX=P[0];g_spY=P[1];g_spZ=P[2]; g_spSeeded=true; } }
    Markerf("[SPEC] transl: spPawn=0x%llX root=0x%llX slaThunk=0x%llX(loc@0x%X tele@0x%X) relLocOff=0x%X seed=(%.0f,%.0f,%.0f) seeded=%d\r\n",
        (unsigned long long)g_spPawn,(unsigned long long)g_spRoot,(unsigned long long)g_spSlaThunk,g_spSlaLoc,g_spSlaTele,g_spRelLocOff,g_spX,g_spY,g_spZ,g_spSeeded?1:0);
    g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
    double vx=0,vy=0,vz=0; if(IsHeapObj(mc)&&g_velOff!=0xFFFFFFFF&&SafeReadable((void*)(mc+g_velOff),24)){ double* V=(double*)(mc+g_velOff); vx=V[0];vy=V[1];vz=V[2]; }
    Markerf("[SPEC] totalWidgets=%d loadCandidates=%d svThunk=0x%llX(InVisibility@0x%X) cam=0x%llX pc=0x%llX\r\n",
        total,g_nLoadW,(unsigned long long)g_svThunk,g_svVisOff,(unsigned long long)cam,(unsigned long long)pc);
    Markerf("[SPEC] moveComp=0x%llX class=%s velOff=0x%X vel=(%.0f,%.0f,%.0f) updComp=0x%llX hwnd=0x%llX — fly: WASD move, arrows steer, Space/Ctrl up/down\r\n",
        (unsigned long long)mc,mcn,g_velOff,vx,vy,vz,(unsigned long long)updComp,(unsigned long long)(uintptr_t)g_hwnd);
}
static void DoSpectatorCam(){
    long h=InterlockedIncrement(&g_scHits); int hidden=0;
    // 1. keep the "DROP IN... LOADING" (WBP_UI_MatchTransition) overlay hidden
    if(g_svThunk && g_svVisOff!=0xFFFFFFFF){
        for(int i=0;i<g_nLoadW;i++){ uintptr_t w=g_loadWidgets[i]; if(!SafeReadable((void*)w,0x30))continue; uintptr_t wc=ClassOf(w); if(!LooksLikePtr(wc)||!SuperChainHas(wc,"UserWidget"))continue;
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint8_t*)(g_pbuf+g_svVisOff)=1; /* ESlateVisibility::Collapsed */
            if(!CallGuarded(g_svFn,g_svThunk,g_svChild,(void*)w,g_pbuf,g_rbuf)) hidden++;
        }
    } else if(h==1) Marker("[SPEC] SetVisibility unresolved -> overlay not hidden\r\n");
    // 2. fly-cam puppet: poke the spectator root WORLD location each tick from WASD/arrows (the un-deployed
    //    input path is dead, so drive position directly — like the S75 hero velocity puppet). Arrows steer the
    //    movement heading (g_yaw); WASD move in that frame; Space/Ctrl = up/down. View DIRECTION stays fixed for
    //    now (rotating the camera POV needs an offset we RE next) — this gives translate-through-the-world.
    // 2. TRANSLATION (S77): move the spectator pawn via K2_SetActorLocation (WASD, arrows steer, Space/Ctrl up/down).
    //    The native dead-spectator camera targets this pawn, so moving it moves the view. Absolute setter -> track pos.
    bool moved=false;
    if(kEnableTranslation && IsHeapObj(g_spPawn) && g_spSlaThunk && g_spSlaLoc!=0xFFFFFFFF){
        if(IsGameFocused()){
            if(GetAsyncKeyState(VK_LEFT)&0x8000)  g_spYaw2-=2.5;
            if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_spYaw2+=2.5;
            double yr=g_spYaw2*3.14159265358979/180.0, c=cos(yr), s=sin(yr), sp=300.0, dx=0,dy=0,dz=0;
            if(GetAsyncKeyState('W')&0x8000){ dx+=c; dy+=s; }
            if(GetAsyncKeyState('S')&0x8000){ dx-=c; dy-=s; }
            if(GetAsyncKeyState('D')&0x8000){ dx-=s; dy+=c; }
            if(GetAsyncKeyState('A')&0x8000){ dx+=s; dy-=c; }
            if(GetAsyncKeyState(VK_SPACE)&0x8000)   dz+=1;
            if(GetAsyncKeyState(VK_CONTROL)&0x8000) dz-=1;
            if(dx||dy||dz){ g_spX+=dx*sp; g_spY+=dy*sp; g_spZ+=dz*sp; moved=true;
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
                if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
                CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf); }
        }
    }
    if(h==1||h%100==0||moved) Markerf("[SPEC] hit %ld: overlay hidden %d/%d; spPawn=0x%llX pos=(%.0f,%.0f,%.0f) yaw=%.0f moved=%d\r\n",h,hidden,g_nLoadW,(unsigned long long)g_spPawn,g_spX,g_spY,g_spZ,g_spYaw2,moved?1:0);
}

// S77 phase-3 CONTINUOUS movement: one K2_SetActorLocation step to the worker-updated position (g_spX/Y/Z),
// fired via a TRANSIENT hook (install -> one fire -> uninstall) so NO standing .text mod ever exists (the dodge).
// Called ~15x/sec from the worker's off-thread WASD loop; kept minimal (no logging) since it runs hot.
static bool ReadViewYaw(double* out);   // fwd decl (defined after the diff-discovery helpers)
// S78a v3: read the client's view yaw by calling the rotation getter (game thread). FRotator return = Pitch@0,
// Yaw@8, Roll@16 (doubles) in the result buffer (the exec thunk writes to RESULT); params-frame ReturnValue is a
// fallback. Logs the first few reads so the marker confirms it tracks the mouse.
static void DoReadRot(){
    if(!g_rotThunk||!IsHeapObj(g_rotCtx)) return;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(CallGuarded(g_rotFn,g_rotThunk,g_rotChild,(void*)g_rotCtx,g_pbuf,g_rbuf)) return;
    double yawR=*(double*)(g_rbuf+8), yawP=*(double*)(g_pbuf+g_rotRetOff+8);
    double yaw = (yawR!=0.0)?yawR:yawP;
    long n=InterlockedIncrement(&g_rotLogN);
    if(n<=8) Markerf("[yawcall] read #%ld: rbuf(p=%.1f,y=%.1f,r=%.1f) pbuf.yaw=%.1f -> yaw=%.1f\r\n",n,*(double*)g_rbuf,yawR,*(double*)(g_rbuf+16),yawP,yaw);
    g_viewYawLive=yaw; g_viewYawValid=1;
}
// S78a: LEAN move step (S77 architecture, proven reliable) — heading + position are computed OFF-THREAD; this
// runs on the game thread and does ONLY the K2_SetActorLocation to the already-updated pos. No per-step getter
// call (that heavier variant caused the intermittent input stalls), so the transient window stays short.
static volatile long g_fired=0;
static void DoStepMove(){
    g_done=1;   // exactly one fire per transient window
    InterlockedIncrement(&g_fired);
    if(!IsHeapObj(g_spPawn)||!g_spSlaThunk||g_spSlaLoc==0xFFFFFFFF){ g_moveDone=1; return; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
    if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
    CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf);
    g_moveDone=1;
}

// ===== S78 refinement #2: DATA/VTABLE hook — durable per-frame move, no ProcessInternal dependency =====
// The transient-per-step move fires only on a game-thread ProcessInternal (a Blueprint script call), which is
// sparse when the user isn't rotating (native camera ticks don't call PI) -> intermittent input stalls (proven:
// fired=0 while steps climbed). FIX: swap a per-frame-ticked object's vtable POINTER (obj@+0, on the heap -> no
// .text mod, no thread-suspend) to a heap copy whose per-frame slot (CameraManager::UpdateCamera, a NATIVE virtual
// called every frame) is our stub. Our stub runs OnVtableTick every frame on the game thread -> the move applies
// every frame regardless of PI. Pure heap mod; the anti-tamper is a .text integrity check (per S77 RE), which a
// heap vtable/stub doesn't touch.
static const int kVtMax=400;
static volatile long g_vtCounters[kVtMax];
static uintptr_t  g_vtOrig=0, g_vtObj=0; static uintptr_t* g_vtCopy=nullptr; static int g_vtN=0, g_vtSlot=-1;
static volatile long g_vtBusy=0, g_vtTicks=0;
// S78c: resolve the take-over pieces — spawn (GameplayStatics BeginDeferred/FinishSpawning), SetViewTargetWithBlend
// (on the PC), and K2_SetActorLocation/K2_SetActorRotation on the ACameraActor class. (Reuses the DoSpawnHero spawn
// globals g_begin*/g_finish*/g_oB*/g_oF*/g_worldCtx/g_gsCDO, which are declared earlier.)
static void ResolveTakeover(){
    g_toPC=FindInstClassSub("LokiPlayerController");
    g_worldCtx=FindInstClassSub("ProgressionManager"); if(!g_worldCtx) g_worldCtx=FindInstExactClass("LokiGameState");
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    uintptr_t camCDO=FindObjExact("Default__CameraActor"); g_toCamCls=camCDO?ClassOf(camCDO):0;
    if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
        ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
        ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
        if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
        if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    }
    { uintptr_t pcCls=g_toPC?ClassOf(g_toPC):0;
      if(pcCls) ResolveFunc(pcCls,"SetViewTargetWithBlend",&g_toSvtbFn,&g_toSvtbThunk,&g_toSvtbChild);
      if(!g_toSvtbThunk){ uintptr_t pccdo=FindObjExact("Default__PlayerController"); if(pccdo) ResolveFunc(ClassOf(pccdo),"SetViewTargetWithBlend",&g_toSvtbFn,&g_toSvtbThunk,&g_toSvtbChild); }
      if(g_toSvtbChild){ g_toSvtbTgt=g_offParam(g_toSvtbChild,"NewViewTarget",0); g_toSvtbBlend=g_offParam(g_toSvtbChild,"BlendTime",8); } }
    if(g_toCamCls){ ResolveFunc(g_toCamCls,"K2_SetActorLocation",&g_toSlaFn,&g_toSlaThunk,&g_toSlaChild);
        if(g_toSlaChild){ g_toSlaLoc=g_offParam(g_toSlaChild,"NewLocation",0); g_toSlaTele=g_offParam(g_toSlaChild,"bTeleport",0x19); }
        ResolveFunc(g_toCamCls,"K2_SetActorRotation",&g_sraFn,&g_sraThunk,&g_sraChild);
        if(g_sraChild){ g_sraRotOff=g_offParam(g_sraChild,"NewRotation",0); g_sraTele=g_offParam(g_sraChild,"bTeleport",0x18); } }
    Markerf("[TO] pc=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX begin=0x%llX finish=0x%llX svtb=0x%llX(tgt@0x%X) sla=0x%llX(loc@0x%X) sra=0x%llX(rot@0x%X tele@0x%X)\r\n",
        (unsigned long long)g_toPC,(unsigned long long)g_toCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_toSvtbThunk,g_toSvtbTgt,(unsigned long long)g_toSlaThunk,g_toSlaLoc,(unsigned long long)g_sraThunk,g_sraRotOff,g_sraTele);
}
// Spawn my ACameraActor at (g_spX,g_spY,g_spZ) + SetViewTargetWithBlend to it (game thread). Returns true on success.
static bool SpawnMyCamera(){
    if(!g_beginThunk||!g_finishThunk||!IsHeapObj(g_toCamCls)||!IsHeapObj(g_worldCtx)||!IsHeapObj(g_gsCDO)){ Markerf("[TO] spawn resolve incomplete begin=0x%llX finish=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX\r\n",(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_toCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO); return false; }
    static uint8_t xf[0x60]={0}; *(double*)(xf+0x18)=1.0; *(double*)(xf+0x20)=g_spX; *(double*)(xf+0x28)=g_spY; *(double*)(xf+0x30)=g_spZ; *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_worldCtx; *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)g_toCamCls; memcpy(g_pbuf+g_oBXform,xf,0x50); g_pbuf[g_oBColl]=2;
    if(CallGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[TO] BeginDeferred FAULTED\r\n"); return false; }
    uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
    if(!IsHeapObj(deferred)){ Marker("[TO] spawn returned null\r\n"); return false; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
    if(CallGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[TO] FinishSpawning FAULTED\r\n"); return false; }
    uintptr_t cam=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(cam)) cam=*(uint64_t*)(g_pbuf+g_oFRet); if(!IsHeapObj(cam)) cam=deferred; g_myCam=cam;
    if(g_toSvtbThunk && IsHeapObj(g_toPC)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_toSvtbTgt)=(uint64_t)cam; *(float*)(g_pbuf+g_toSvtbBlend)=0.0f;
        bool f=CallGuarded(g_toSvtbFn,g_toSvtbThunk,g_toSvtbChild,(void*)g_toPC,g_pbuf,g_rbuf); Markerf("[TO] spawned cam=0x%llX + SetViewTargetWithBlend%s\r\n",(unsigned long long)cam,f?" [FAULTED]":""); }
    else Markerf("[TO] spawned cam=0x%llX (no SetViewTarget: svtb=0x%llX pc=0x%llX)\r\n",(unsigned long long)cam,(unsigned long long)g_toSvtbThunk,(unsigned long long)g_toPC);
    return IsHeapObj(g_myCam);
}
// Per-frame stub (game thread), runs every frame independent of ProcessInternal:
//   1. seed the fly position from the pawn's WORLD location on the first tick (no origin teleport),
//   2. refresh the real view yaw from the getter (throttled) so the worker's heading is correct,
//   3. apply the move ONLY when the worker marked it dirty (i.e. the user is flying) — not 720x/sec to a stale pos.
extern "C" void OnVtableTick(){
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(g_vtBusy) return; g_vtBusy=1;
    long t=InterlockedIncrement(&g_vtTicks);
    // 1. seed from world location once
    if(!g_spSeededVt){
        if(g_glaThunk && IsHeapObj(g_spPawn)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            if(!CallGuarded(g_glaFn,g_glaThunk,g_glaChild,(void*)g_spPawn,g_pbuf,g_rbuf)){
                double* R=(double*)g_rbuf; double* Rp=(double*)(g_pbuf+g_glaRetOff);
                double wx=(R[0]!=0.0||R[1]!=0.0||R[2]!=0.0)?R[0]:Rp[0], wy=(R[0]!=0.0||R[1]!=0.0||R[2]!=0.0)?R[1]:Rp[1], wz=(R[0]!=0.0||R[1]!=0.0||R[2]!=0.0)?R[2]:Rp[2];
                g_spX=wx; g_spY=wy; g_spZ=wz; Markerf("[vt] seed from world loc = (%.0f,%.0f,%.0f)\r\n",g_spX,g_spY,g_spZ); } }
        g_spSeededVt=1;
    }
    // S78c TAKE-OVER: spawn my own camera as the view target + drive its rotation (mine, slow) + position.
    if(kTakeoverCam){
        if(!g_camSpawnTried){ g_camSpawnTried=1; SpawnMyCamera(); }
        if(IsHeapObj(g_myCam)){
            // S78c: RE-ASSERT the view target every ~4 frames (the game's camera manager likely re-sets its own
            // spectator view target each tick, reverting our one-time SetViewTargetWithBlend).
            if((t&3)==0 && g_toSvtbThunk && IsHeapObj(g_toPC)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                *(uint64_t*)(g_pbuf+g_toSvtbTgt)=(uint64_t)g_myCam; *(float*)(g_pbuf+g_toSvtbBlend)=0.0f;
                CallGuarded(g_toSvtbFn,g_toSvtbThunk,g_toSvtbChild,(void*)g_toPC,g_pbuf,g_rbuf); }
            // rotation: Stage 2a = fixed (prove the view is my camera); else mouse-driven yaw/pitch.
            if(!kStage2aFixedRot){ long mdx=InterlockedExchange(&g_mouseDX,0), mdy=InterlockedExchange(&g_mouseDY,0);
                g_camYaw += mdx*0.04; g_camPitch -= mdy*0.04; if(g_camPitch>85)g_camPitch=85; if(g_camPitch<-85)g_camPitch=-85; }
            if(g_sraThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                double* R=(double*)(g_pbuf+g_sraRotOff); R[0]=g_camPitch; R[1]=g_camYaw; R[2]=0.0;   // FRotator {Pitch,Yaw,Roll}
                if(g_sraTele!=0xFFFFFFFF) g_pbuf[g_sraTele]=1;
                CallGuarded(g_sraFn,g_sraThunk,g_sraChild,(void*)g_myCam,g_pbuf,g_rbuf); }
            if(g_moveDirty && g_toSlaThunk){ g_moveDirty=0; InterlockedIncrement(&g_fired);
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                double* L=(double*)(g_pbuf+g_toSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ; if(g_toSlaTele) g_pbuf[g_toSlaTele]=1;
                CallGuarded(g_toSlaFn,g_toSlaThunk,g_toSlaChild,(void*)g_myCam,g_pbuf,g_rbuf); }
        }
        g_vtBusy=0; return;
    }
    // 2. refresh the view yaw from the getter (throttle: ~every 4th tick)
    if((t&3)==0) DoReadRot();
    // 3. apply the move only when the worker flagged input
    if(g_moveDirty && IsHeapObj(g_spPawn) && g_spSlaThunk && g_spSlaLoc!=0xFFFFFFFF){
        g_moveDirty=0; InterlockedIncrement(&g_fired);
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        double* L=(double*)(g_pbuf+g_spSlaLoc); L[0]=g_spX;L[1]=g_spY;L[2]=g_spZ;
        if(g_spSlaTele!=0xFFFFFFFF) g_pbuf[g_spSlaTele]=1;
        CallGuarded(g_spSlaFn,g_spSlaThunk,g_spSlaChild,(void*)g_spPawn,g_pbuf,g_rbuf);
    }
    g_vtBusy=0;
}
// vtable length: count leading code pointers (into the main module) up to cap.
static int VtableLen(uintptr_t vt,int cap){ int n=0; for(;n<cap;n++){ if(!SafeReadable((void*)(vt+n*8),8))break; uintptr_t f=*(uintptr_t*)(vt+n*8); if(f<g_modBase||f>=g_modBase+0xC000000)break; } return n; }
// A tiny per-slot trampoline that increments a counter then jumps to the original: used to find the per-frame slot.
static uintptr_t* BuildSweepVt(uintptr_t origVt,int n){
    uint8_t* blk=(uint8_t*)VirtualAlloc(nullptr,(size_t)n*32+64,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    uintptr_t* vt=(uintptr_t*)VirtualAlloc(nullptr,(size_t)n*8+64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!blk||!vt) return nullptr;
    for(int i=0;i<n;i++){ uint8_t* s=blk+i*32; uintptr_t orig=*(uintptr_t*)(origVt+i*8); Emit e{s};
        EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&g_vtCounters[i]);   // mov rax, &counter[i]
        EB(e,0xF0);EB(e,0x48);EB(e,0xFF);EB(e,0x00);               // lock inc qword [rax]
        EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)orig);              // mov rax, orig[i]
        EB(e,0xFF);EB(e,0xE0);                                     // jmp rax
        vt[i]=(uintptr_t)s; }
    return vt;
}
// Sweep: swap the object's vtable to counting trampolines for ~1.2s, restore, return the highest-count slot.
static int FindPerFrameSlot(uintptr_t obj){
    if(!IsHeapObj(obj)||!SafeReadable((void*)obj,8)) { Marker("[vt] bad obj\r\n"); return -1; }
    uintptr_t origVt=*(uintptr_t*)obj;
    if(origVt<g_modBase||origVt>=g_modBase+0xC000000){ Markerf("[vt] vtable ptr 0x%llX not in module -> abort\r\n",(unsigned long long)origVt); return -1; }
    int n=VtableLen(origVt,kVtMax); if(n<8){ Markerf("[vt] vtable too short n=%d\r\n",n); return -1; }
    for(int i=0;i<kVtMax;i++) g_vtCounters[i]=0;
    uintptr_t* sweepVt=BuildSweepVt(origVt,n); if(!sweepVt){ Marker("[vt] sweep alloc fail\r\n"); return -1; }
    *(uintptr_t*)obj=(uintptr_t)sweepVt;   // swap to counting trampolines (heap write)
    Sleep(1200);
    *(uintptr_t*)obj=origVt;               // restore
    // Log the top-8 slots by count. Pick the highest-count slot in a PER-FRAME range [kLo,kHi] (~1-4 calls/frame
    // over 1.2s at up to 144fps) — avoids hooking a HOT getter (thousands/sec) that would fire the move too often.
    const long kLo=40, kHi=900;
    char tb[400]; int tp=0; int chosen=-1; long chosenC=0;
    for(int rank=0; rank<8; rank++){ int bi=-1; long bc=0;
        for(int i=0;i<n;i++){ long c=g_vtCounters[i]; if(c>bc){ bc=c; bi=i; } }   // highest remaining
        if(bi<0) break;
        int w=_snprintf_s(tb+tp,sizeof(tb)-tp,_TRUNCATE,"[%d]=%ld ",bi,bc); if(w>0) tp+=w;
        if(bc>=kLo && bc<=kHi && bc>chosenC){ chosen=bi; chosenC=bc; }
        g_vtCounters[bi]=-1;   // mark listed so the next rank finds the next-highest
    }
    Markerf("[vt] sweep obj=0x%llX n=%d top: %s -> chosen slot=%d count=%ld\r\n",(unsigned long long)obj,n,tb,chosen,chosenC);
    if(chosen<0){ Marker("[vt] no per-frame slot in range -> abort (fall back to transient)\r\n"); return -1; }
    return chosen;
}
// Build the movement stub for a hooked slot: save arg regs -> call OnVtableTick -> restore -> jmp original[slot]
// (same register-preserving pattern as BuildHook; final jmp is transparent so the original virtual still runs).
static uint8_t* BuildVtStub(uintptr_t origFn){
    uint8_t* stub=(uint8_t*)VirtualAlloc(nullptr,0x80,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE); if(!stub) return nullptr;
    Emit e{stub};
    EB(e,0x51);EB(e,0x52);EB(e,0x41);EB(e,0x50);EB(e,0x41);EB(e,0x51);   // push rcx,rdx,r8,r9
    EB(e,0x48);EB(e,0x83);EB(e,0xEC);EB(e,0x28);                         // sub rsp,0x28 (shadow + align)
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)&OnVtableTick); EB(e,0xFF);EB(e,0xD0);  // mov rax,OnVtableTick; call rax
    EB(e,0x48);EB(e,0x83);EB(e,0xC4);EB(e,0x28);                         // add rsp,0x28
    EB(e,0x41);EB(e,0x59);EB(e,0x41);EB(e,0x58);EB(e,0x5A);EB(e,0x59);   // pop r9,r8,rdx,rcx
    EB(e,0x48);EB(e,0xB8);EU64(e,(uint64_t)origFn); EB(e,0xFF);EB(e,0xE0); // mov rax,origFn; jmp rax
    return stub;
}
// Install: heap-copy the vtable, replace slot with the stub, swap obj@+0 to the copy (heap write, no .text).
static bool InstallVtableMove(uintptr_t obj,int slot){
    uintptr_t origVt=*(uintptr_t*)obj; int n=VtableLen(origVt,kVtMax); if(slot<0||slot>=n) return false;
    uintptr_t* copy=(uintptr_t*)VirtualAlloc(nullptr,(size_t)n*8+64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE); if(!copy) return false;
    for(int i=0;i<n;i++) copy[i]=*(uintptr_t*)(origVt+i*8);
    uintptr_t origFn=copy[slot]; uint8_t* stub=BuildVtStub(origFn); if(!stub) return false;
    copy[slot]=(uintptr_t)stub;
    g_vtOrig=origVt; g_vtCopy=copy; g_vtObj=obj; g_vtN=n; g_vtSlot=slot;
    *(uintptr_t*)obj=(uintptr_t)copy;   // swap
    Markerf("[vt] INSTALLED per-frame hook: obj=0x%llX slot=%d origFn=0x%llX stub=0x%llX\r\n",(unsigned long long)obj,slot,(unsigned long long)origFn,(unsigned long long)(uintptr_t)stub);
    return true;
}
static void RestoreVtable(){ if(g_vtObj && g_vtOrig && SafeReadable((void*)g_vtObj,8)){ *(uintptr_t*)g_vtObj=g_vtOrig; Marker("[vt] vtable restored\r\n"); } }

// S78c: raw mouse capture. A message-only window + RIDEV_INPUTSINK receives relative mouse deltas even though the
// game (not us) holds focus and the cursor is locked in free-look — GetCursorPos can't see that. Accumulate deltas.
static LRESULT CALLBACK RawWndProc(HWND h,UINT m,WPARAM w,LPARAM l){
    if(m==WM_INPUT){ UINT sz=0; GetRawInputData((HRAWINPUT)l,RID_INPUT,nullptr,&sz,sizeof(RAWINPUTHEADER));
        if(sz && sz<=sizeof(RAWINPUT)+128){ BYTE buf[sizeof(RAWINPUT)+128];
            if(GetRawInputData((HRAWINPUT)l,RID_INPUT,buf,&sz,sizeof(RAWINPUTHEADER))!=(UINT)-1){ RAWINPUT* ri=(RAWINPUT*)buf;
                if(ri->header.dwType==RIM_TYPEMOUSE && !(ri->data.mouse.usFlags&MOUSE_MOVE_ABSOLUTE)){
                    InterlockedAdd(&g_mouseDX,(long)ri->data.mouse.lLastX); InterlockedAdd(&g_mouseDY,(long)ri->data.mouse.lLastY); InterlockedIncrement(&g_mouseEvents); } } }
        return 0; }
    return DefWindowProcA(h,m,w,l);
}
static DWORD WINAPI RawInputThread(LPVOID){
    WNDCLASSA wc; memset(&wc,0,sizeof(wc)); wc.lpfnWndProc=RawWndProc; wc.hInstance=GetModuleHandleA(nullptr); wc.lpszClassName="dshRawIn";
    RegisterClassA(&wc);
    HWND hwnd=CreateWindowExA(0,"dshRawIn","",0,0,0,0,0,HWND_MESSAGE,nullptr,wc.hInstance,nullptr);
    if(!hwnd){ Markerf("[raw] CreateWindow fail err=%lu\r\n",GetLastError()); return 1; }
    RAWINPUTDEVICE rid; memset(&rid,0,sizeof(rid)); rid.usUsagePage=0x01; rid.usUsage=0x02; rid.dwFlags=RIDEV_INPUTSINK; rid.hwndTarget=hwnd;
    if(!RegisterRawInputDevices(&rid,1,sizeof(rid))){ Markerf("[raw] register fail err=%lu\r\n",GetLastError()); return 2; }
    Marker("[raw] raw mouse input registered (INPUTSINK)\r\n");
    MSG msg; while(GetMessage(&msg,nullptr,0,0)>0){ TranslateMessage(&msg); DispatchMessage(&msg); }
    return 0;
}

// S77 phase-3 finish: probe what DRIVES THE VIEW (the camera does NOT follow PC->SpectatorPawn). Logs PC
// pawn-related props + every actor pointer inside the PlayerCameraManager (ViewTarget.Target etc.) with the 3
// doubles after each (candidate POV Location if it's the view-target slot). Pure off-thread reads. From the dump
// we pick the actor to move (or the cam POV-location offset to override) instead of the SpectatorPawn.
static bool IsUObj(uintptr_t v){ if(!IsHeapObj(v)||!SafeReadable((void*)v,8))return false; uintptr_t vt=*(uintptr_t*)v; return vt>=g_modBase && vt<g_modBase+0xC000000; }
static void ProbeCamera(){
    uintptr_t cam=FindInstClassSub("CameraManager"); uintptr_t pc=FindInstClassSub("LokiPlayerController");
    char scn[96]="?"; if(IsHeapObj(g_spPawn)) ClassName(g_spPawn,scn,sizeof(scn));
    Markerf("[probe] cam=0x%llX pc=0x%llX spPawn=0x%llX(%s)\r\n",(unsigned long long)cam,(unsigned long long)pc,(unsigned long long)g_spPawn,scn);
    if(IsHeapObj(pc)){ uintptr_t pcCls=ClassOf(pc);
        const char* props[]={"Pawn","AcknowledgedPawn","SpectatorPawn","PlayerCameraManager"};
        for(int i=0;i<4;i++){ uint32_t o=PropOffsetOnClass(pcCls,props[i]); if(o==0xFFFFFFFF||!SafeReadable((void*)(pc+o),8))continue;
            uintptr_t v=*(uintptr_t*)(pc+o); char cn[96]="?"; if(IsUObj(v))ClassName(v,cn,sizeof(cn));
            Markerf("[probe] PC->%s @0x%X = 0x%llX (%s)\r\n",props[i],o,(unsigned long long)v,cn); } }
    if(IsHeapObj(cam)){ char ccn[96]="?"; ClassName(cam,ccn,sizeof(ccn)); Markerf("[probe] cameraMgr class=%s\r\n",ccn);
        for(uint32_t off=0x28; off<0x800; off+=8){ if(!SafeReadable((void*)(cam+off),8))continue; uintptr_t v=*(uintptr_t*)(cam+off);
            if(!IsUObj(v))continue; uintptr_t c=ClassOf(v); if(!SuperChainHas(c,"Actor"))continue;
            char cn[96]="?"; ClassName(v,cn,sizeof(cn)); char on[96]="?"; ObjName(v,on,sizeof(on));
            double d0=0,d1=0,d2=0; if(SafeReadable((void*)(cam+off+8),24)){ d0=*(double*)(cam+off+8);d1=*(double*)(cam+off+16);d2=*(double*)(cam+off+24); }
            Markerf("[probe] cam+0x%X -> actor 0x%llX %s (%s) next3d=(%.0f,%.0f,%.0f)\r\n",off,(unsigned long long)v,on,cn,d0,d1,d2); } }
}

// S78 refinement #1: does the 24 bytes at p look like an FRotator (3 doubles Pitch/Yaw/Roll)? Tight filter to
// keep the scan's false-positive rate low: finite, pitch in [-90,90], yaw in [-181,361], |roll|<2, not all-zero.
static bool IsRotatorD(uintptr_t p){
    if(!SafeReadable((void*)p,24)) return false;
    double pit=*(double*)p, yaw=*(double*)(p+8), rol=*(double*)(p+16);
    if(!(pit==pit)||!(yaw==yaw)||!(rol==rol)) return false;                 // NaN reject
    if(pit< -90.0001||pit>90.0001) return false;
    if(yaw< -181.0||yaw>361.0) return false;
    if(rol< -2.0||rol>2.0) return false;
    if(pit==0.0&&yaw==0.0&&rol==0.0) return false;                          // all-zero = noise
    return true;
}
static void AddRotCand(uintptr_t obj,uint32_t off,const char* tag){
    if(g_nRotCands>=16) return;
    for(int i=0;i<g_nRotCands;i++) if(g_rotCands[i].obj==obj && (off>g_rotCands[i].off?off-g_rotCands[i].off:g_rotCands[i].off-off)<24) return; // de-dup near hits
    RotCand& r=g_rotCands[g_nRotCands++]; r.obj=obj; r.off=off; strncpy(r.tag,tag,sizeof(r.tag)-1); r.tag[sizeof(r.tag)-1]=0;
}
// Copy up to cap bytes of [base..) into dst, stopping at the first unmapped 8-byte chunk. Returns bytes copied.
static uint32_t SnapRange(uintptr_t base, uint8_t* dst, uint32_t cap){
    if(!IsHeapObj(base)) return 0;
    uint32_t n=0; for(; n+8<=cap; n+=8){ if(!SafeReadable((void*)(base+n),8)) break; memcpy(dst+n,(void*)(base+n),8); } return n;
}
static void AddDiffObj(uintptr_t o,const char* tag){
    if(!IsHeapObj(o)||g_nDobj>=kMaxDiffObj) return;
    for(int i=0;i<g_nDobj;i++) if(g_dobj[i].obj==o) return;   // de-dup (SpectatorPawn/DefaultPawn may coincide)
    DiffObj& d=g_dobj[g_nDobj]; d.obj=o; d.snap=g_snapBuf[g_nDobj]; d.len=SnapRange(o,d.snap,kDiffLen);
    strncpy(d.tag,tag,sizeof(d.tag)-1); d.tag[sizeof(d.tag)-1]=0; g_nDobj++;
}
// Resolve the view-yaw source. Reflection primary (AController::ControlRotation) + a bounded rotator scan of the
// PC and PlayerCameraManager as discovery candidates. Sets g_viewYawObj/off + g_viewYawEnabled if the primary is
// found; always logs every candidate so a live mouse-rotate + the movement heartbeat pins the right offset.
static void ProbeViewYaw(){
    g_nRotCands=0;
    uintptr_t pc=FindInstClassSub("LokiPlayerController");
    uintptr_t cam=FindInstClassSub("CameraManager"); g_camMgr=cam;
    // reflection: known FRotator UPROPERTYs on the controller chain
    if(IsHeapObj(pc)){ uintptr_t cls=ClassOf(pc);
        const char* rp[]={"ControlRotation","BlendedTargetViewRotation","TargetViewRotation"};
        for(int i=0;i<3;i++){ uint32_t o=PropOffsetOnClass(cls,rp[i]); if(o==0xFFFFFFFF)continue;
            char t[24]; _snprintf_s(t,sizeof(t),_TRUNCATE,"PC.%s",rp[i]); AddRotCand(pc,o,t);
            double yw=SafeReadable((void*)(pc+o+8),8)?*(double*)(pc+o+8):0; Markerf("[yaw] refl PC->%s @0x%X yaw=%.1f\r\n",rp[i],o,yw); }
        // primary = ControlRotation if reflected (g_viewRotOff = yaw value = FRotator base + 8, double)
        uint32_t cro=PropOffsetOnClass(cls,"ControlRotation");
        if(cro!=0xFFFFFFFF){ g_viewYawObj=pc; g_viewRotOff=cro+8; g_viewYawEnabled=true; Markerf("[yaw] PRIMARY = PC->ControlRotation.Yaw @0x%X -> mouse steering ON\r\n",cro+8); }
        else Marker("[yaw] ControlRotation NOT reflected -> using memory-diff auto-lock (rotate the mouse to lock steering)\r\n");
    } else Marker("[yaw] no LokiPlayerController -> cannot resolve view yaw\r\n");
    // reference scan (bounded, one-time): rotator-shaped double-triples in the PC / camera manager, logged once.
    if(IsHeapObj(pc))  for(uint32_t o=0x28;o<0x1400 && g_nRotCands<12;o+=8) if(IsRotatorD(pc+o))  AddRotCand(pc,o,"PC.scan");
    if(IsHeapObj(cam)) for(uint32_t o=0x28;o<0x1400 && g_nRotCands<16;o+=8) if(IsRotatorD(cam+o)) AddRotCand(cam,o,"CAM.scan");
    char b[600]; int p=0;
    for(int i=0;i<g_nRotCands && p<540;i++){ RotCand& r=g_rotCands[i]; double yw=SafeReadable((void*)(r.obj+r.off+8),8)?*(double*)(r.obj+r.off+8):0;
        int w=_snprintf_s(b+p,sizeof(b)-p,_TRUNCATE,"%s@0x%X(y=%.1f) ",r.tag,r.off,yw); if(w<0)break; p+=w; }
    Markerf("[yaw] %d ref candidates: %s\r\n",g_nRotCands,b);
    // snapshot several candidate objects for the float+double diff auto-lock
    g_nDobj=0;
    AddDiffObj(pc,"PC");
    AddDiffObj(cam,"CAM");
    AddDiffObj(FindInstExactClass("SpectatorPawn"),"SPAWN");   // the spectator pawn ACTOR (its transform rotates)
    AddDiffObj(FindInstClassSub("DefaultPawn"),"DPAWN");
    AddDiffObj(FindInstClassSub("CameraComponent"),"CAMCOMP");
    AddDiffObj(FindInstClassSub("SpectatorPawnMovement"),"SPMOVE");
    for(int i=0;i<g_nDobj;i++) Markerf("[yawdiff] snap %s=0x%llX len=0x%X\r\n",g_dobj[i].tag,(unsigned long long)g_dobj[i].obj,g_dobj[i].len);
    // S78a: the view yaw is read via the GetCameraRotation GETTER, called on the game thread inside the per-frame
    // vtable hook (OnVtableTick). (An earlier CAM+0x14A0 "pin" was WRONG — that offset is a monotonic TIMER, not the
    // yaw; the getter is the ground truth.) Resolve the getter below.
    // S78a v3: resolve a rotation GETTER to call on the game thread (returns a clean FRotator regardless of storage).
    { void* fn=0; uintptr_t th=0,ch=0;
      struct Cand { uintptr_t ctx; const char* name; };
      Cand cands[]={ {cam,"GetCameraRotation"}, {pc,"GetControlRotation"}, {pc,"GetViewRotation"}, {g_spPawn,"GetViewRotation"} };
      for(int i=0;i<4 && !g_rotThunk;i++){ if(!IsHeapObj(cands[i].ctx))continue; fn=0;th=0;ch=0; ResolveFunc(ClassOf(cands[i].ctx),cands[i].name,&fn,&th,&ch);
          if(th){ g_rotFn=fn; g_rotThunk=th; g_rotChild=ch; g_rotCtx=cands[i].ctx; g_rotName=cands[i].name; } }
      if(g_rotThunk && g_rotChild){ uint32_t ro=ParamOffset(g_rotChild,"ReturnValue"); g_rotRetOff=(ro==0xFFFFFFFF)?0:ro; }
      Markerf("[yawcall] rot getter = %s thunk=0x%llX child=0x%llX retOff=0x%X ctx=0x%llX\r\n",g_rotName,(unsigned long long)g_rotThunk,(unsigned long long)g_rotChild,g_rotRetOff,(unsigned long long)g_rotCtx); }
    // K2_GetActorLocation on the view-target pawn -> seed the fly position from its WORLD location (world coords,
    // matching K2_SetActorLocation) so the vtable hook doesn't yank the view to origin.
    if(IsHeapObj(g_spPawn)){ ResolveFunc(ClassOf(g_spPawn),"K2_GetActorLocation",&g_glaFn,&g_glaThunk,&g_glaChild);
        if(g_glaChild){ uint32_t ro=ParamOffset(g_glaChild,"ReturnValue"); g_glaRetOff=(ro==0xFFFFFFFF)?0:ro; }
        Markerf("[yawcall] K2_GetActorLocation thunk=0x%llX child=0x%llX retOff=0x%X\r\n",(unsigned long long)g_glaThunk,(unsigned long long)g_glaChild,g_glaRetOff); }
}
// S78b (broadened): walk obj's class chain for FLOAT/DOUBLE props whose (lowercased) name has a rotation/camera
// CONTEXT word; log each with its live value. Register the strong RATE-like ones (sensitiv/speed/rate/scale/mult)
// for continuous reduction. Capped log to keep the marker readable.
static volatile long g_sensLogN=0;
static void EnumSensProps(uintptr_t obj,const char* tag){
    if(!IsHeapObj(obj)) return; uintptr_t cls=ClassOf(obj); int g=0;
    static const char* ctx[]={"sens","mouse","look","turn","yaw","pitch","rotat","spin","aim","spectat","freecam","camera"};
    static const char* rate[]={"sensitiv","speed","rate","scale","mult","boost"};   // +boost catches TurningBoost
    while(LooksLikePtr(cls)&&g++<28){
        uintptr_t f=SafeReadable((void*)(cls+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(cls+UFUNC_CHILDPROPS):0; int i=0;
        while(LooksLikePtr(f)&&i++<4000){ char pn[96];
            if(GetFNameStr(NameId(f),pn,sizeof(pn))){ char low[96]; int L=0; for(;pn[L]&&L<95;L++) low[L]=(pn[L]>='A'&&pn[L]<='Z')?pn[L]+32:pn[L]; low[L]=0;
                bool hasCtx=false; for(int k=0;k<(int)(sizeof(ctx)/sizeof(ctx[0]));k++) if(strstr(low,ctx[k])){ hasCtx=true; break; }
                if(hasCtx){ uint32_t off=SafeReadable((void*)(f+FPROP_OFFSET),4)?*(uint32_t*)(f+FPROP_OFFSET):0xFFFFFFFF;
                    if(off!=0xFFFFFFFF && off<0x4000 && SafeReadable((void*)(obj+off),8)){ float fv=*(float*)(obj+off); double dv=*(double*)(obj+off);
                        if(InterlockedIncrement(&g_sensLogN)<=80) Markerf("[SENS] %s.%s @0x%X f32=%.4f f64=%.4f\r\n",tag,pn,off,fv,dv);
                        bool hasRate=false; for(int k=0;k<(int)(sizeof(rate)/sizeof(rate[0]));k++) if(strstr(low,rate[k])){ hasRate=true; break; }
                        if(hasRate && g_nSens<12 && fv>0.00001f && fv<100000.0f){ g_sensObj[g_nSens]=obj; g_sensOff[g_nSens]=off; g_sensTarget[g_nSens]=fv*kSensMul; g_nSens++; } } }
            }
            f=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; }
        cls=SafeReadable((void*)(cls+UST_SUPER),8)?*(uintptr_t*)(cls+UST_SUPER):0;
    }
}
static void ProbeSensitivity(){
    g_nSens=0; g_sensLogN=0;
    EnumSensProps(FindInstClassSub("LokiPlayerController"),"PC");
    EnumSensProps(FindInstClassSub("LocalPlayer"),"LocalPlayer");
    EnumSensProps(FindInstClassSub("UserSettings"),"UserSettings");
    EnumSensProps(FindInstClassSub("CameraManager"),"CameraMgr");
    EnumSensProps(FindInstExactClass("SpectatorPawn"),"SpectatorPawn");
    Markerf("[SENS] %d rate fields registered for reduction (x%.3f)\r\n",g_nSens,kSensMul);
}
static void ApplySensReduction(){ for(int i=0;i<g_nSens;i++) if(SafeReadable((void*)(g_sensObj[i]+g_sensOff[i]),4)) *(float*)(g_sensObj[i]+g_sensOff[i])=g_sensTarget[i]; }
// Scan an object's snapshot vs live for 8-aligned doubles that SWUNG into a rotation-like range (the view yaw
// as the user rotates). Tracks each candidate's consecutive "moved-since-last-tick" count; the first to reach
// kLockMoves auto-locks as the steering source. Returns the best moves-count seen this pass.
static const int kLockMoves=3; static const double kLockSpan=25.0;   // deliberate L-R mouse swings span wide + fast
static const char* DiffTag(uintptr_t obj){ for(int i=0;i<g_nDobj;i++) if(g_dobj[i].obj==obj) return g_dobj[i].tag; return "?"; }
static const char* KindName(int k){ return k==YK_QUAT?"quat":(k==YK_FLOAT?"f32":"f64"); }
static double QuatYawDeg(uintptr_t p){   // FQuat {X@0,Y@8,Z@16,W@24} doubles -> yaw (deg)
    double X=*(double*)p, Y=*(double*)(p+8), Z=*(double*)(p+16), W=*(double*)(p+24);
    return atan2(2.0*(W*Z+X*Y), 1.0-2.0*(Y*Y+Z*Z)) * 180.0/3.14159265358979;
}
static YawTrack* FindTrack(uintptr_t obj,uint32_t off,int kind){ for(int i=0;i<g_nYt;i++) if(g_yt[i].obj==obj&&g_yt[i].off==off&&g_yt[i].kind==kind) return &g_yt[i]; if(g_nYt<64){ YawTrack& t=g_yt[g_nYt++]; t.obj=obj; t.off=off; t.kind=kind; t.last=1e9; t.lo=1e9; t.hi=-1e9; t.moves=0; return &t; } return nullptr; }
static void TrackVal(uintptr_t obj,uint32_t off,int kind,double v){ YawTrack* t=FindTrack(obj,off,kind); if(!t)return; if(v<t->lo)t->lo=v; if(v>t->hi)t->hi=v; if(t->last<1e8){ if(fabs(v-t->last)>1.0) t->moves++; else t->moves=0; } t->last=v; }
// Diff one object vs its snapshot for values that swung as the user rotates: a float (4-aligned) or double
// (8-aligned) FRotator-yaw in [-360,360], OR a changed unit QUATERNION (4 doubles in [-1,1], the likely storage
// here — the view rotation wasn't a plain FRotator in range). For a quat we track its EXTRACTED yaw so the lock
// selection (widest span, degrees) treats all three kinds uniformly.
static void ScanDiffObj(DiffObj& d){
    if(!IsHeapObj(d.obj)||d.len<0x28) return;
    for(uint32_t o=0x18; o+8<=d.len; o+=4){
        if((o&7)==0){
            double dn=*(double*)(d.obj+o), dold=*(double*)(d.snap+o);
            if(dn==dn && dn>=-360.0 && dn<=360.0 && fabs(dn-dold)>1.0) TrackVal(d.obj,o,YK_DOUBLE,dn);
            if(o+32<=d.len){ double Y=*(double*)(d.obj+o+8),Z=*(double*)(d.obj+o+16),W=*(double*)(d.obj+o+24);
                if(dn==dn&&Y==Y&&Z==Z&&W==W && fabs(dn)<=1.001&&fabs(Y)<=1.001&&fabs(Z)<=1.001&&fabs(W)<=1.001){
                    double ss=dn*dn+Y*Y+Z*Z+W*W;
                    if(ss>0.9 && ss<1.1){ double dq=fabs(dn-dold)+fabs(Y-*(double*)(d.snap+o+8))+fabs(Z-*(double*)(d.snap+o+16))+fabs(W-*(double*)(d.snap+o+24));
                        if(dq>0.02) TrackVal(d.obj,o,YK_QUAT,QuatYawDeg(d.obj+o)); } } }
        }
        float fn=*(float*)(d.obj+o), fold=*(float*)(d.snap+o);
        if(fn==fn && fn>=-360.0f && fn<=360.0f && fabs((double)fn-(double)fold)>1.0) TrackVal(d.obj,o,YK_FLOAT,(double)fn);
    }
}
// One discovery tick: rescan every candidate object, then auto-lock the WIDEST-swinging value (moves>=kLockMoves
// AND span>=kLockSpan) — deliberate horizontal mouse swings beat a slow-creeping clock/smoother. No-op once locked.
static void DiscoverYaw(){
    if(g_viewYawEnabled) return;
    for(int i=0;i<g_nDobj;i++) ScanDiffObj(g_dobj[i]);
    YawTrack* best=nullptr; double bestSpan=0;
    for(int i=0;i<g_nYt;i++){ double span=g_yt[i].hi-g_yt[i].lo; if(g_yt[i].moves>=kLockMoves && span>=kLockSpan && span>bestSpan){ best=&g_yt[i]; bestSpan=span; } }
    if(best){ g_viewYawObj=best->obj; g_viewRotOff=best->off; g_viewYawKind=best->kind; g_viewYawEnabled=true; g_manualYawOff=0.0;
        Markerf("[yawlock] LOCKED view yaw = %s+0x%X (%s moves=%d span=%.0f val=%.1f) -> MOUSE STEERING ON\r\n",DiffTag(best->obj),best->off,KindName(best->kind),best->moves,bestSpan,best->last); }
}
static bool ReadViewYaw(double* out){
    if(g_viewYawValid){ *out=g_viewYawLive; return true; }
    if(!g_viewYawEnabled||!IsHeapObj(g_viewYawObj)||g_viewRotOff==0xFFFFFFFF) return false;
    if(g_viewYawKind==YK_QUAT){ if(!SafeReadable((void*)(g_viewYawObj+g_viewRotOff),32))return false; double y=QuatYawDeg(g_viewYawObj+g_viewRotOff); if(!(y==y))return false; *out=y; return true; }
    if(g_viewYawKind==YK_FLOAT){ if(!SafeReadable((void*)(g_viewYawObj+g_viewRotOff),4))return false; float v=*(float*)(g_viewYawObj+g_viewRotOff); if(!(v==v))return false; *out=v; return true; }
    if(!SafeReadable((void*)(g_viewYawObj+g_viewRotOff),8)) return false;
    double v=*(double*)(g_viewYawObj+g_viewRotOff); if(!(v==v)) return false; *out=v; return true;
}

// S78 refinement #4: widget-spawn robustness. Instead of a fixed 12s pre-census sleep (a too-early inject got
// 87 widgets and hid 0/3 => overlay stayed up), poll the UserWidget count until it's high/stable. Off-thread.
static int CountUserWidgets(){ int n=0; ForEachObject([&](uintptr_t o)->bool{ uintptr_t c=ClassOf(o); if(!LooksLikePtr(c))return false; if(!SuperChainHas(c,"UserWidget"))return false; char on[96]; if(ObjName(o,on,sizeof(on))&&strncmp(on,"Default__",9)==0)return false; n++; return false; }); return n; }
static int WaitForWidgets(int target,int minMs,int maxMs){
    Sleep(minMs);                                       // widgets need SOME time regardless of inject timing
    DWORD t0=GetTickCount(); int last=-1,stable=0;
    for(;;){ int n=CountUserWidgets();
        if(n>=target){ Markerf("[1b] widgets=%d >= %d after %ums+min -> proceed\r\n",n,target,(unsigned)(GetTickCount()-t0)); return n; }
        if(n==last && n>800){ if(++stable>=3){ Markerf("[1b] widgets=%d stable after %ums+min -> proceed\r\n",n,(unsigned)(GetTickCount()-t0)); return n; } } else stable=0;
        last=n; if(GetTickCount()-t0>=(DWORD)maxMs){ Markerf("[1b] widget wait cap hit, widgets=%d\r\n",n); return n; }
        Sleep(1500); }
}

// ---- Route D (MODE_DEBUGCAM): UE's built-in free-fly debug camera ----
// UCheatManager::EnableDebugCamera spawns an ADebugCameraController that DETACHES from the PlayerController and
// takes over the view with its OWN native free-fly input (WASD/mouse) — bypassing the deploy-gated PC camera +
// the dormant spectator movement. The open question is whether a UCheatManager exists in this shipping build.
static uintptr_t g_dbgCM=0, g_dbgPC=0; static void* g_edcFn=0; static uintptr_t g_edcThunk=0, g_edcChild=0;
static void ResolveDebugCam(){
    uintptr_t pc=FindInstClassSub("LokiPlayerController"); g_dbgPC=pc;
    uintptr_t cm=0; const char* src="none"; uint32_t ccOff=0xFFFFFFFF;
    if(pc){ ccOff=PropOffsetOnClass(ClassOf(pc),"CheatManager"); if(ccOff!=0xFFFFFFFF && SafeReadable((void*)(pc+ccOff),8)){ uintptr_t v=*(uintptr_t*)(pc+ccOff); if(IsHeapObj(v)){ cm=v; src="PC->CheatManager"; } } }
    if(!cm){ ForEachObject([&](uintptr_t o)->bool{ char cn[96]; if(!ClassName(o,cn,sizeof(cn)))return false; if(strcmp(cn,"CheatManager")!=0)return false; char on[96]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0)return false; if(!IsHeapObj(o))return false; cm=o; return true; }); if(cm) src="live UCheatManager instance"; }
    g_dbgCM=cm;
    uintptr_t cmCls = cm?ClassOf(cm):0; if(!cmCls){ uintptr_t cdo=FindObjExact("Default__CheatManager"); if(cdo) cmCls=ClassOf(cdo); }
    if(cmCls) ResolveFunc(cmCls,"EnableDebugCamera",&g_edcFn,&g_edcThunk,&g_edcChild);
    Markerf("[DBG] pc=0x%llX cheatMgrOff=0x%X cheatMgr=0x%llX (%s) enableDbgThunk=0x%llX\r\n",
        (unsigned long long)pc,ccOff,(unsigned long long)cm,src,(unsigned long long)g_edcThunk);
}
static void DoDebugCam(){
    long h=InterlockedIncrement(&g_scHits);
    // keep the "DROP IN... LOADING" overlay hidden so the debug-camera view is visible (widgets from ResolveSpectatorCam)
    if(g_svThunk && g_svVisOff!=0xFFFFFFFF){
        for(int i=0;i<g_nLoadW;i++){ uintptr_t w=g_loadWidgets[i]; if(!SafeReadable((void*)w,0x30))continue; uintptr_t wc=ClassOf(w); if(!LooksLikePtr(wc)||!SuperChainHas(wc,"UserWidget"))continue;
            memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint8_t*)(g_pbuf+g_svVisOff)=1; CallGuarded(g_svFn,g_svThunk,g_svChild,(void*)w,g_pbuf,g_rbuf); }
    }
    static bool called=false;
    if(!called){ called=true;
        if(!IsHeapObj(g_dbgCM) || !g_edcThunk){ Marker("[DBG] no usable UCheatManager -> cannot EnableDebugCamera (shipping likely nulls it). Pivot to spawn+SetViewTarget.\r\n"); return; }
        Marker("[DBG] >>> EnableDebugCamera(cheatMgr)\r\n");
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        bool f=CallGuarded(g_edcFn,g_edcThunk,g_edcChild,(void*)g_dbgCM,g_pbuf,g_rbuf);
        Markerf("[DBG] <<< EnableDebugCamera returned%s — check screen for the free-fly debug camera (native WASD/mouse look).\r\n",f?" [FAULTED]":"");
    }
}

// ---- Route D (MODE_FREECAM): spawn a plain ACameraActor + retarget the PC's view to it, then puppet its
// position. Owns all its pieces (my camera, BP-callable SetViewTargetWithBlend + K2_SetActorLocation) — bypasses
// the CheatManager, the deploy-gated PC camera, and the dormant spectator movement. Open Q: does re-targeting the
// view to a NON-hero camera dodge the AttachAudioListenerToHero move-crash? Reuses the DoSpawnHero spawn globals.
static uintptr_t g_fcPC=0, g_fcCamCls=0, g_fcCam=0;
static void* g_svtbFn=0; static uintptr_t g_svtbThunk=0, g_svtbChild=0; static uint32_t g_oSvtbTgt=0, g_oSvtbBlend=8;
static void* g_slaFn=0; static uintptr_t g_slaThunk=0, g_slaChild=0; static uint32_t g_oSlaLoc=0, g_oSlaTele=0x19;
static double g_fcX=55, g_fcY=79, g_fcZ=500, g_fcYaw=0; static bool g_fcSpawned=false;
static void ResolveFreeCam(){
    ResolveSpectatorCam();   // populate overlay-hide widgets (+ harmless spectator census)
    g_fcPC=FindInstClassSub("LokiPlayerController");
    g_worldCtx=FindInstClassSub("ProgressionManager"); if(!g_worldCtx) g_worldCtx=FindInstExactClass("LokiGameState");
    g_gsCDO=FindObjExact("Default__GameplayStatics");
    uintptr_t camCDO=FindObjExact("Default__CameraActor"); g_fcCamCls=camCDO?ClassOf(camCDO):0;
    if(g_gsCDO){ uintptr_t gc=ClassOf(g_gsCDO);
        ResolveFunc(gc,"BeginDeferredActorSpawnFromClass",&g_beginFn,&g_beginThunk,&g_beginChild);
        ResolveFunc(gc,"FinishSpawningActor",&g_finishFn,&g_finishThunk,&g_finishChild);
        if(g_beginChild){ g_oBWorld=g_offParam(g_beginChild,"WorldContextObject",0); g_oBClass=g_offParam(g_beginChild,"ActorClass",8); g_oBXform=g_offParam(g_beginChild,"SpawnTransform",0x10); g_oBColl=g_offParam(g_beginChild,"CollisionHandlingOverride",0x70); g_oBRet=g_offParam(g_beginChild,"ReturnValue",0x88); }
        if(g_finishChild){ g_oFActor=g_offParam(g_finishChild,"Actor",0); g_oFXform=g_offParam(g_finishChild,"SpawnTransform",0x10); g_oFRet=g_offParam(g_finishChild,"ReturnValue",0x70); }
    }
    { uintptr_t pcCls=g_fcPC?ClassOf(g_fcPC):0;
      if(pcCls) ResolveFunc(pcCls,"SetViewTargetWithBlend",&g_svtbFn,&g_svtbThunk,&g_svtbChild);
      if(!g_svtbThunk){ uintptr_t pccdo=FindObjExact("Default__PlayerController"); if(pccdo) ResolveFunc(ClassOf(pccdo),"SetViewTargetWithBlend",&g_svtbFn,&g_svtbThunk,&g_svtbChild); }   // confirmed to live on PlayerController
      if(g_svtbChild){ g_oSvtbTgt=g_offParam(g_svtbChild,"NewViewTarget",0); g_oSvtbBlend=g_offParam(g_svtbChild,"BlendTime",8); } }
    if(g_fcCamCls){ ResolveFunc(g_fcCamCls,"K2_SetActorLocation",&g_slaFn,&g_slaThunk,&g_slaChild);
        if(g_slaChild){ g_oSlaLoc=g_offParam(g_slaChild,"NewLocation",0); g_oSlaTele=g_offParam(g_slaChild,"bTeleport",0x19); } }
    g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
    Markerf("[FC] pc=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX beginThunk=0x%llX finishThunk=0x%llX svtbThunk=0x%llX(tgt@0x%X) slaThunk=0x%llX(loc@0x%X)\r\n",
        (unsigned long long)g_fcPC,(unsigned long long)g_fcCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO,(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_svtbThunk,g_oSvtbTgt,(unsigned long long)g_slaThunk,g_oSlaLoc);
}
static void DoFreeCam(){
    long h=InterlockedIncrement(&g_scHits);
    if(g_svThunk && g_svVisOff!=0xFFFFFFFF){ for(int i=0;i<g_nLoadW;i++){ uintptr_t w=g_loadWidgets[i]; if(!SafeReadable((void*)w,0x30))continue; uintptr_t wc=ClassOf(w); if(!LooksLikePtr(wc)||!SuperChainHas(wc,"UserWidget"))continue; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint8_t*)(g_pbuf+g_svVisOff)=1; CallGuarded(g_svFn,g_svThunk,g_svChild,(void*)w,g_pbuf,g_rbuf); } }
    if(!g_fcSpawned){ g_fcSpawned=true;
        if(!g_beginThunk||!g_finishThunk||!IsHeapObj(g_fcCamCls)||!IsHeapObj(g_worldCtx)||!IsHeapObj(g_gsCDO)){ Markerf("[FC] resolve incomplete begin=0x%llX finish=0x%llX camCls=0x%llX world=0x%llX gsCDO=0x%llX -> abort\r\n",(unsigned long long)g_beginThunk,(unsigned long long)g_finishThunk,(unsigned long long)g_fcCamCls,(unsigned long long)g_worldCtx,(unsigned long long)g_gsCDO); return; }
        static uint8_t xf[0x60]={0}; *(double*)(xf+0x18)=1.0; *(double*)(xf+0x20)=g_fcX; *(double*)(xf+0x28)=g_fcY; *(double*)(xf+0x30)=g_fcZ; *(double*)(xf+0x38)=1.0; *(double*)(xf+0x40)=1.0; *(double*)(xf+0x48)=1.0;
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        *(uint64_t*)(g_pbuf+g_oBWorld)=(uint64_t)g_worldCtx; *(uint64_t*)(g_pbuf+g_oBClass)=(uint64_t)g_fcCamCls; memcpy(g_pbuf+g_oBXform,xf,0x50); g_pbuf[g_oBColl]=2;
        Marker("[FC] >>> spawn CameraActor\r\n");
        if(CallGuarded(g_beginFn,g_beginThunk,g_beginChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[FC] BeginDeferred FAULTED\r\n"); return; }
        uintptr_t deferred=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(deferred)) deferred=*(uint64_t*)(g_pbuf+g_oBRet);
        if(!IsHeapObj(deferred)){ Marker("[FC] spawn returned null\r\n"); return; }
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_oFActor)=(uint64_t)deferred; memcpy(g_pbuf+g_oFXform,xf,0x50);
        if(CallGuarded(g_finishFn,g_finishThunk,g_finishChild,(void*)g_gsCDO,g_pbuf,g_rbuf)){ Marker("[FC] FinishSpawning FAULTED\r\n"); return; }
        uintptr_t cam=(uintptr_t)*(uint64_t*)g_rbuf; if(!IsHeapObj(cam)) cam=*(uint64_t*)(g_pbuf+g_oFRet); if(!IsHeapObj(cam)) cam=deferred; g_fcCam=cam;
        Markerf("[FC] camera spawned 0x%llX -> SetViewTargetWithBlend\r\n",(unsigned long long)cam);
        if(g_svtbThunk && IsHeapObj(g_fcPC)){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+g_oSvtbTgt)=(uint64_t)cam; *(float*)(g_pbuf+g_oSvtbBlend)=0.0f; bool f=CallGuarded(g_svtbFn,g_svtbThunk,g_svtbChild,(void*)g_fcPC,g_pbuf,g_rbuf); Markerf("[FC] SetViewTargetWithBlend returned%s — view should render from the spawned camera now.\r\n",f?" [FAULTED]":""); }
        return;
    }
    if(IsHeapObj(g_fcCam) && g_slaThunk){
        bool focused=(!g_hwnd)||(GetForegroundWindow()==g_hwnd);
        if(focused){
            if(GetAsyncKeyState(VK_LEFT)&0x8000) g_fcYaw-=2.5; if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_fcYaw+=2.5;
            double yr=g_fcYaw*3.14159265358979/180.0, c=cos(yr), s=sin(yr), sp=45.0, dx=0,dy=0,dz=0;
            if(GetAsyncKeyState('W')&0x8000){ dx+=c; dy+=s; } if(GetAsyncKeyState('S')&0x8000){ dx-=c; dy-=s; }
            if(GetAsyncKeyState('D')&0x8000){ dx-=s; dy+=c; } if(GetAsyncKeyState('A')&0x8000){ dx+=s; dy-=c; }
            if(GetAsyncKeyState(VK_SPACE)&0x8000) dz+=1; if(GetAsyncKeyState(VK_CONTROL)&0x8000) dz-=1;
            if(dx||dy||dz){ g_fcX+=dx*sp; g_fcY+=dy*sp; g_fcZ+=dz*sp;
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); double* L=(double*)(g_pbuf+g_oSlaLoc); L[0]=g_fcX;L[1]=g_fcY;L[2]=g_fcZ; g_pbuf[g_oSlaTele]=1;
                CallGuarded(g_slaFn,g_slaThunk,g_slaChild,(void*)g_fcCam,g_pbuf,g_rbuf); }
        }
    }
    if(h==1||h%100==0) Markerf("[FC] hit %ld cam=0x%llX pos=(%.0f,%.0f,%.0f)\r\n",h,(unsigned long long)g_fcCam,g_fcX,g_fcY,g_fcZ);
}

// ---- PHASE 1 (S79 MOONSHOT): force-load hero assets, then re-census ----
// The decisive first gate: does the client's asset system work in the DS spectator process? S76 found
// BP_HERO_*_C = 0x0 (unloaded) — but the CLIENT (unlike the stub) has every hero cooked into its OWN paks
// (it's the exe that plays real matches). If a hero primary asset can be pulled into memory IN-PROCESS, the
// client-side spawn path is unlocked; if not, the whole moonshot dies cheaply (bank the S70/S78 spectator).
// Reuses the PROVEN missions load primitive: PrimaryAssetIDFromString -> GetPrimaryAssetIdList ->
// AsyncLoadPrimaryAssets on the LokiAssetManager (missions_fix.cpp). The hero PrimaryAssetType is DISCOVERED
// (try a candidate list, keep whichever returns ids) — no blind single-string guess, and the log records every
// candidate tried so the next iteration can extend the list. All native calls are SEH-guarded (CallGuarded).
static uintptr_t g_lam=0, g_ksl=0, g_lcWorld=0;
static void* g_pafsFn=0;   static uintptr_t g_pafsThunk=0,  g_pafsChild=0;
static void* g_gpailFn=0;  static uintptr_t g_gpailThunk=0, g_gpailChild=0;
static void* g_lcLoadFn=0; static uintptr_t g_lcLoadThunk=0,g_lcLoadChild=0;
static const int LC_NMAX=64;
static uint64_t g_lcIds[LC_NMAX][2]; static int g_lcNum=0; static uint64_t g_lcHandle=0;
static char g_lcHeroType[48]="?"; static volatile long g_lcFired=0;

static bool ResolveLoadCensus(){
    g_lam = FindInstClassSub("LokiAssetManager");
    uintptr_t kslCDO = FindObjExact("Default__KismetSystemLibrary"); g_ksl = kslCDO?ClassOf(kslCDO):0;
    g_lcWorld = FindInstClassSub("ProgressionManager"); if(!g_lcWorld) g_lcWorld = FindInstClassSub("LokiGameState");
    if(!g_lam || !g_ksl || !g_lcWorld){ Markerf("[LOAD] resolve FAIL lam=0x%llX ksl=0x%llX world=0x%llX\r\n",(unsigned long long)g_lam,(unsigned long long)g_ksl,(unsigned long long)g_lcWorld); return false; }
    uintptr_t lamCls=ClassOf(g_lam);
    ResolveFunc(lamCls,"PrimaryAssetIDFromString",&g_pafsFn,&g_pafsThunk,&g_pafsChild);
    ResolveFunc(lamCls,"AsyncLoadPrimaryAssets",&g_lcLoadFn,&g_lcLoadThunk,&g_lcLoadChild);
    ResolveFunc(g_ksl,"GetPrimaryAssetIdList",&g_gpailFn,&g_gpailThunk,&g_gpailChild);
    Markerf("[LOAD] resolved lam=0x%llX world=0x%llX pafsThunk=0x%llX gpailThunk=0x%llX loadThunk=0x%llX\r\n",
            (unsigned long long)g_lam,(unsigned long long)g_lcWorld,(unsigned long long)g_pafsThunk,(unsigned long long)g_gpailThunk,(unsigned long long)g_lcLoadThunk);
    return g_pafsThunk && g_gpailThunk && g_lcLoadThunk;
}
// FString param: {ptr(8), num(4), max(4)} = 16B at pbuf.
static void LcSetFStr(void* pbuf, const wchar_t* s){ int n=(int)wcslen(s)+1; ((uint64_t*)pbuf)[0]=(uint64_t)s; ((uint32_t*)pbuf)[2]=(uint32_t)n; ((uint32_t*)pbuf)[3]=(uint32_t)n; }
// PrimaryAssetIDFromString("<Type>:x") -> FPrimaryAssetId in rbuf; low32 = the type FName id (0 = parse produced no type).
static uint32_t LcTypeId(const wchar_t* idstr){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); LcSetFStr(g_pbuf,idstr);
    if(CallGuarded(g_pafsFn,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf)) return 0;
    return (uint32_t)(*(uint64_t*)g_rbuf & 0xFFFFFFFF);
}
// GetPrimaryAssetIdList(FPrimaryAssetType{typeId,0}) -> TArray<FPrimaryAssetId> (written back into the params buffer:
// data ptr @+8, num @+16 — the missions QueryIdsK layout). Returns count, fills ids.
static int LcQueryIds(uint32_t typeId, uint64_t ids[][2], int K){
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    ((uint32_t*)g_pbuf)[0]=typeId; ((uint32_t*)g_pbuf)[1]=0;
    if(CallGuarded(g_gpailFn,g_gpailThunk,g_gpailChild,(void*)g_lam,g_pbuf,g_rbuf)) return -1;
    int num=*(int32_t*)((uint8_t*)g_pbuf+16); uint64_t data=((uint64_t*)g_pbuf)[1];
    for(int i=0;i<K;i++){ ids[i][0]=0; ids[i][1]=0; }
    if(num>0 && LooksLikePtr((uintptr_t)data)){ int lim=num<K?num:K; for(int i=0;i<lim;i++){ if(SafeReadable((void*)(data+i*16),16)){ ids[i][0]=*(uint64_t*)(data+i*16); ids[i][1]=*(uint64_t*)(data+i*16+8); } } }
    return num;
}
static void LcFireLoad(){
    static uint8_t loadBuf[LC_NMAX*16];
    for(int i=0;i<g_lcNum;i++){ *(uint64_t*)(loadBuf+i*16)=g_lcIds[i][0]; *(uint64_t*)(loadBuf+i*16+8)=g_lcIds[i][1]; }
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    *(uint64_t*)((uint8_t*)g_pbuf+0)=(uint64_t)g_lcWorld;   // WorldContextObject
    *(uint64_t*)((uint8_t*)g_pbuf+8)=(uint64_t)loadBuf;     // AssetsToLoad.Data
    *(uint32_t*)((uint8_t*)g_pbuf+16)=(uint32_t)g_lcNum;    // .Num
    *(uint32_t*)((uint8_t*)g_pbuf+20)=(uint32_t)g_lcNum;    // .Max
    if(CallGuarded(g_lcLoadFn,g_lcLoadThunk,g_lcLoadChild,(void*)g_lam,g_pbuf,g_rbuf)){ Marker("[LOAD] AsyncLoadPrimaryAssets FAULTED\r\n"); return; }
    g_lcHandle=*(uint64_t*)g_rbuf;
}
// Deploy step 5: enumerate cosmetics PrimaryAssetTypes + log ids with resolved names (find the Assault character cosmetic).
static void DoCosmEnum(){
    static const wchar_t* kCand[] = { L"Cosmetic:x", L"HeroCosmetic:x", L"CharacterCosmetic:x", L"LokiHeroCosmetic:x",
        L"LokiCosmetic:x", L"Skin:x", L"HeroSkin:x", L"CharacterSkin:x", L"BaseCosmetic:x", L"CosmeticSet:x",
        L"LokiCharacterCosmetic:x", L"HeroBody:x", L"Body:x", L"Character:x", L"CharacterBody:x" };
    static uint64_t ids[LC_NMAX][2];
    for(unsigned c=0;c<sizeof(kCand)/sizeof(kCand[0]);c++){
        uint32_t tid=LcTypeId(kCand[c]);
        int num = tid ? LcQueryIds(tid,ids,LC_NMAX) : 0;
        Markerf("[CE] type '%ls' -> tid=0x%X ids=%d\r\n",kCand[c],tid,num);
        if(num>0){ int lim=num<24?num:24;
            for(int i=0;i<lim;i++){ uint32_t nameId=(uint32_t)(ids[i][1]&0xFFFFFFFF); char nm[128]="?"; GetFNameStr(nameId,nm,sizeof(nm));
                Markerf("[CE]     id[%d] type=0x%llX name=0x%llX '%s'%s\r\n",i,(unsigned long long)ids[i][0],(unsigned long long)ids[i][1],nm,
                        (strstr(nm,"Assault")?" <<ASSAULT":(strstr(nm,"Default")?" <<DEFAULT":""))); }
        }
    }
    Marker("[CE] === cosmetics enum done ===\r\n");
}
// Deploy step 6: assign a real CosmeticsAssetID + RefreshCosmetics to build the character mesh (uses g_cm* from ResolveCosmetics).
static volatile long g_scReps=0; static uint8_t g_scPaid[16]={0};
static void DoSetCosmetic(){
    long rep=InterlockedIncrement(&g_scReps);
    if(rep==1){
        Marker("[SC] === set CosmeticsAssetID + RefreshCosmetics (build character mesh) ===\r\n");
        if(g_pafsThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); LcSetFStr(g_pbuf,KSKIN);
            if(!CallGuarded(g_pafsFn,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf)) memcpy(g_scPaid,g_rbuf,16); }
        Markerf("[SC] skin PrimaryAssetId = 0x%llX 0x%llX\r\n",(unsigned long long)*(uint64_t*)g_scPaid,(unsigned long long)*(uint64_t*)(g_scPaid+8));
        if(*(uint64_t*)g_scPaid==0){ Marker("[SC] PrimaryAssetIDFromString gave 0 — skin type not resolvable; abort\r\n"); return; }
        if(g_lcLoadThunk){ static uint8_t lb[16]; memcpy(lb,g_scPaid,16); memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
            *(uint64_t*)(g_pbuf+0)=(uint64_t)g_lcWorld; *(uint64_t*)(g_pbuf+8)=(uint64_t)lb; *(uint32_t*)(g_pbuf+16)=1; *(uint32_t*)(g_pbuf+20)=1;
            CallGuarded(g_lcLoadFn,g_lcLoadThunk,g_lcLoadChild,(void*)g_lam,g_pbuf,g_rbuf); Marker("[SC] AsyncLoadPrimaryAssets(skin) fired\r\n"); }
        uint32_t caOff=PropOffsetOnClass(ClassOf(g_cmHero),"CosmeticsAssetID");
        uint32_t ovOff=PropOffsetOnClass(ClassOf(g_cmHero),"OverrideCosmeticsAssetID");
        if(caOff!=0xFFFFFFFF && SafeReadable((void*)(g_cmHero+caOff),16)){ memcpy((void*)(g_cmHero+caOff),g_scPaid,16); Markerf("[SC] wrote CosmeticsAssetID @+0x%X\r\n",caOff); } else Marker("[SC] CosmeticsAssetID offset NOT FOUND\r\n");
        if(ovOff!=0xFFFFFFFF && SafeReadable((void*)(g_cmHero+ovOff),16)){ memcpy((void*)(g_cmHero+ovOff),g_scPaid,16); Markerf("[SC] wrote OverrideCosmeticsAssetID @+0x%X\r\n",ovOff); }
    }
    if(*(uint64_t*)g_scPaid==0) return;
    // every rep: rebuild + keep Alive/visible (RefreshCosmetics rebuilds once the async asset is resident)
    if(g_cmRefThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_cmRefFn,g_cmRefThunk,g_cmRefChild,(void*)g_cmHero,g_pbuf,g_rbuf)){ if(rep==1)Marker("[SC] RefreshCosmetics FAULTED\r\n"); } else if(rep==1) Marker("[SC] RefreshCosmetics done\r\n"); }
    if(g_cmOrpThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmOrpFn,g_cmOrpThunk,g_cmOrpChild,(void*)g_cmHero,g_pbuf,g_rbuf); }
    if(SafeReadable((void*)(g_cmHero+0x1090),1)) *(uint8_t*)(g_cmHero+0x1090)=1;
    if(SafeReadable((void*)(g_cmHero+0x1BE8),1)) *(uint8_t*)(g_cmHero+0x1BE8)=0;
    if(g_cmVisThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmVisFn,g_cmVisThunk,g_cmVisChild,(void*)g_cmHero,g_pbuf,g_rbuf); }
    if(rep==1||rep==8||rep==16) Markerf("[SC] rep %ld: skeletal meshes under hero = %d\r\n",rep,CountHeroSkeletals());
}
// Call a BLUEPRINT UFunction via ProcessEvent (guarded). ufunc = the UFunction* (ResolveFunc's *fn), NOT the thunk.
static bool CallGuardedBP(uintptr_t obj, void* ufunc){
    if(!ufunc || !LooksLikePtr(obj)) return true;
    static uint8_t peb[512];
    __try { memset(peb,0,sizeof(peb)); ((PFN_PE)(g_modBase+kProcEventRva))((void*)obj, ufunc, peb); return false; }
    __except(EXCEPTION_EXECUTE_HANDLER){ return true; }
}
// Variant taking a caller-owned params buffer (so the return value can be read back).
static bool CallGuardedBPP(uintptr_t obj, void* ufunc, void* params){
    if(!ufunc || !LooksLikePtr(obj)) return true;
    __try { ((PFN_PE)(g_modBase+kProcEventRva))((void*)obj, ufunc, params); return false; }
    __except(EXCEPTION_EXECUTE_HANDLER){ return true; }
}
static void DoBPTest(){
    Marker("[BT] === ProcessEvent BP-call validation (getter returns) ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L)L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)?(SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0):0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)?(SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0):0;
    if(!LooksLikePtr(hero)){ Marker("[BT] no hero\r\n"); return; }
    uintptr_t hc=ClassOf(hero);
    // known-good: native GetCosmeticsController
    void* nfn=0; uintptr_t nth=0,nch=0; ResolveFunc(hc,"GetCosmeticsController",&nfn,&nth,&nch);
    uintptr_t ctrlNative=0; if(nth){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(nfn,nth,nch,(void*)hero,g_pbuf,g_rbuf)) ctrlNative=*(uintptr_t*)g_rbuf; }
    Markerf("[BT] native GetCosmeticsController = 0x%llX\r\n",(unsigned long long)ctrlNative);
    // TEST: BP GetBaseCosmeticsController via ProcessEvent, read the return
    const char* cands[]={"GetBaseCosmeticsController","GetHeroCharacter","GetLocalLokiCharacterBP"};
    for(int c=0;c<3;c++){
        void* fn=0; uintptr_t th=0,ch=0; ResolveFunc(hc,cands[c],&fn,&th,&ch);
        if(!fn){ Markerf("[BT] %s NOT FOUND\r\n",cands[c]); continue; }
        uint32_t retOff = ch? ParamOffset(ch,"ReturnValue"):0xFFFFFFFF; if(retOff==0xFFFFFFFF) retOff=0;
        bool isBP = (th==g_modBase+kPiRva);
        static uint8_t pb[256]; memset(pb,0,sizeof(pb));
        bool fault = CallGuardedBPP(hero, fn, pb);
        uintptr_t ret = *(uintptr_t*)(pb+ (retOff<248?retOff:0));
        Markerf("[BT] %s [%s] fault=%d retOff=0x%X ret=0x%llX%s\r\n",cands[c],isBP?"BP":"N",fault,retOff,(unsigned long long)ret,(ret==ctrlNative&&ret?"  == controller (WORKS!)":""));
    }
    Marker("[BT] === done ===\r\n");
}
// Raw-restore ProcessInternal's stolen bytes WITHOUT the thread-suspend dance (safe from inside OnPI: we're already past
// the 5-byte prologue, and the stub's trampoline has its own copy to complete the in-flight call).
static void RawUnhook(){ if(!g_pi)return; DWORD op=0; if(VirtualProtect(g_pi,5,PAGE_EXECUTE_READWRITE,&op)){ memcpy(g_pi,g_stolen,5); DWORD d=0; VirtualProtect(g_pi,5,op,&d); FlushInstructionCache(GetCurrentProcess(),g_pi,5); } }
static void DoBPTest2(){
    Marker("[B2] === ProcessEvent BP test with the PI hook REMOVED (re-entrancy test) ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L)L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)?(SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0):0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)?(SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0):0;
    if(!LooksLikePtr(hero)){ Marker("[B2] no hero\r\n"); return; }
    uintptr_t hc=ClassOf(hero);
    // known-good controller via direct-thunk native (uses the captured template; no hook needed)
    void* nfn=0; uintptr_t nth=0,nch=0; ResolveFunc(hc,"GetCosmeticsController",&nfn,&nth,&nch);
    uintptr_t ctrlNative=0; if(nth){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(nfn,nth,nch,(void*)hero,g_pbuf,g_rbuf)) ctrlNative=*(uintptr_t*)g_rbuf; }
    // ★ remove the PI hook so ProcessEvent -> ProcessInternal doesn't re-enter it
    RawUnhook(); Marker("[B2] PI hook raw-removed; calling ProcessEvent now\r\n");
    void* fn=0; uintptr_t th=0,ch=0; ResolveFunc(hc,"GetBaseCosmeticsController",&fn,&th,&ch);
    uint32_t retOff = ch? ParamOffset(ch,"ReturnValue"):0xFFFFFFFF; if(retOff==0xFFFFFFFF) retOff=0;
    static uint8_t pb[256]; memset(pb,0,sizeof(pb));
    bool fault = CallGuardedBPP(hero, fn, pb);
    uintptr_t ret = *(uintptr_t*)(pb+(retOff<248?retOff:0));
    Markerf("[B2] GetBaseCosmeticsController(BP, hook-removed) fault=%d ret=0x%llX (native ctrl=0x%llX)%s\r\n",
            fault,(unsigned long long)ret,(unsigned long long)ctrlNative,(ret==ctrlNative&&ret?"  <<< WORKS! ProcessEvent was the false wall":""));
    Marker("[B2] === done ===\r\n");
}
static void DoBPTest3(){
    Marker("[B3] === ProcessEvent on a NATIVE member fn (GetCosmeticsController) ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L)L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)?(SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0):0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)?(SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0):0;
    if(!LooksLikePtr(hero)){ Marker("[B3] no hero\r\n"); return; }
    uintptr_t hc=ClassOf(hero);
    void* nfn=0; uintptr_t nth=0,nch=0; ResolveFunc(hc,"GetCosmeticsController",&nfn,&nth,&nch);
    if(!nth){ Marker("[B3] GetCosmeticsController not resolved\r\n"); return; }
    uintptr_t viaThunk=0; { memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(!CallGuarded(nfn,nth,nch,(void*)hero,g_pbuf,g_rbuf)) viaThunk=*(uintptr_t*)g_rbuf; }
    uint32_t retOff = nch? ParamOffset(nch,"ReturnValue"):0xFFFFFFFF; if(retOff==0xFFFFFFFF) retOff=0;
    static uint8_t pb[256]; memset(pb,0,sizeof(pb));
    bool fault = CallGuardedBPP(hero, nfn, pb);
    uintptr_t viaPE = *(uintptr_t*)(pb+(retOff<248?retOff:0));
    Markerf("[B3] direct-thunk=0x%llX | ProcessEvent fault=%d ret=0x%llX  %s\r\n",
            (unsigned long long)viaThunk,fault,(unsigned long long)viaPE,
            (viaPE==viaThunk&&viaPE)?"<<< ProcessEvent WORKS on native (BP faults are bytecode/context)":"<<< ProcessEvent BROKEN even on native (mechanism bug)");
    Marker("[B3] === done ===\r\n");
}
// ===== S80: the BP-call primitive (see the MODE_BPCALL note for the two bugs this retires) =====
// Runs a BP-folded UFunction's bytecode by handing ProcessInternal the FFrame it actually needs. The ONLY material
// difference from CallNative is FF_CODE: native thunks ignore it, the BP VM dereferences it.
// argsIn is copied to the head of the locals (a UFunction's params occupy [0, ParmsSize) of its frame).
// CALLER MUST RawUnhook() first — thunk == ProcessInternal == our hooked address, so an installed hook re-enters OnPI.
static uint8_t g_bplocals[1024];
static bool CallBP(uintptr_t obj, void* ufunc, const void* argsIn, int argsLen){
    if(!ufunc || !LooksLikePtr(obj)) return true;
    uintptr_t f=(uintptr_t)ufunc;
    uintptr_t script=SafeReadable((void*)(f+UFUNC_SCRIPT),8)?*(uintptr_t*)(f+UFUNC_SCRIPT):0;
    uint32_t  snum  =SafeReadable((void*)(f+UFUNC_SCRIPTNUM),4)?*(uint32_t*)(f+UFUNC_SCRIPTNUM):0;
    uint32_t  psz   =SafeReadable((void*)(f+UST_PROPSIZE),4)?*(uint32_t*)(f+UST_PROPSIZE):0;
    uintptr_t thunk =SafeReadable((void*)(f+UFUNC_FUNC),8)?*(uintptr_t*)(f+UFUNC_FUNC):0;
    uintptr_t child =SafeReadable((void*)(f+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(f+UFUNC_CHILDPROPS):0;
    if(!LooksLikePtr(script)||!snum||!LooksLikePtr(thunk)) return true;  // empty stub (e.g. Pawn::ReceiveRestarted)
    if(psz>sizeof(g_bplocals)) return true;
    memset(g_bplocals,0,sizeof(g_bplocals));
    if(argsIn && argsLen>0 && argsLen<=(int)sizeof(g_bplocals)) memcpy(g_bplocals,argsIn,argsLen);
    memcpy(g_myframe,g_template,sizeof(g_myframe));
    *(void**)(g_myframe+FF_NODE)=ufunc;
    *(void**)(g_myframe+FF_OBJECT)=(void*)obj;
    *(uint64_t*)(g_myframe+FF_CODE)=(uint64_t)script;      // ★ THE FIX — CallNative hardcodes 0 here
    *(void**)(g_myframe+FF_LOCALS)=g_bplocals;
    *(uint64_t*)(g_myframe+FF_MRP)=0; *(uint64_t*)(g_myframe+FF_MRPA)=0; *(uint64_t*)(g_myframe+FF_MRPC)=0;
    *(uint64_t*)(g_myframe+FF_PROPCHAIN)=(uint64_t)child;
    // ★ Reset the inherited FlowStack to EMPTY-inline. Without this the ubergraph's bail paths (EX_PopExecutionFlow)
    // pop a stale offset from the captured template's frame and jump into arbitrary bytecode. Num=0 + Max=8 (inline
    // capacity) + Secondary=null is a clean empty TArray<uint32,TInlineAllocator<8>>.
    memset(g_myframe+FF_FLOWSTACK,0,0x30);
    *(uint32_t*)(g_myframe+FF_FLOW_MAX)=8;
    *(uint64_t*)(g_myframe+FF_PREVFRAME)=0;      // we are a root call, not nested under the captured frame
    *(uint64_t*)(g_myframe+FF_CURNATIVEFN)=0;
    BuildOutParms(child,g_bplocals);
    static uint8_t rb[64];
    __try { memset(rb,0,sizeof(rb)); ((PFN_THUNK)thunk)((void*)obj,g_myframe,rb); return false; }
    __except(EXCEPTION_EXECUTE_HANDLER){ return true; }
}
static void DoBPCall(){
    Marker("[BC] === S80 BP invoker (FFrame.Code=Script.GetData) — validate, then deploy ===\r\n");
    if(!ResolveCosmetics()){ Marker("[BC] resolve failed\r\n"); return; }
    uintptr_t hero=g_cmHero, hc=ClassOf(hero); char cn[96]="?"; ClassName(hero,cn,sizeof(cn));
    Markerf("[BC] hero=0x%llX class=%s\r\n",(unsigned long long)hero,cn);
    // Ground truth for the gate: the NATIVE GetCosmeticsController via the (working) direct-thunk primitive.
    void* nfn=0; uintptr_t nth=0,nch=0; ResolveFunc(hc,"GetCosmeticsController",&nfn,&nth,&nch);
    uintptr_t ctrl=0;
    if(nth){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
             if(!CallGuarded(nfn,nth,nch,(void*)hero,g_pbuf,g_rbuf)) ctrl=*(uintptr_t*)g_rbuf; }
    Markerf("[BC] ground truth: native GetCosmeticsController = 0x%llX\r\n",(unsigned long long)ctrl);
    RawUnhook(); Marker("[BC] PI hook raw-removed (ProcessInternal must not re-enter OnPI)\r\n");
    // ---- GATE: a BP fn whose own bytecode calls that same native getter into locals@+0x8 ----
    bool ok=false;
    { void* vfn=0; uintptr_t vth=0,vch=0; ResolveFunc(hc,"GetBaseCosmeticsController",&vfn,&vth,&vch);
      if(!vfn) Marker("[BC] GetBaseCosmeticsController NOT FOUND\r\n");
      else { bool fault=CallBP(hero,vfn,nullptr,0);
             uintptr_t outp=*(uintptr_t*)(g_bplocals+0x0), cf=*(uintptr_t*)(g_bplocals+0x8);
             ok = (!fault && ctrl && cf==ctrl);
             Markerf("[BC] GetBaseCosmeticsController: fault=%d out@+0x0=0x%llX CallFunc@+0x8=0x%llX  %s\r\n",
                     fault,(unsigned long long)outp,(unsigned long long)cf,
                     ok?"<<<<<< BP BYTECODE EXECUTED — INVOKER WORKS":"<<<<<< still not executing"); } }
    if(!ok){ Marker("[BC] GATE FAILED — skipping deploy (a deploy result on a broken invoker proves nothing)\r\n"); return; }
    // ---- THE DEPLOY SETUP — first time these BP fns have ever actually RUN ----
    Markerf("[BC] hero LivingState=%u HeroPredropHidden=%u | gate note: TryLocalControlSetup's ubergraph bails on\r\n"
            "[BC]   PopExecutionFlowIfNot IsLocallyControlled() -- hero->Controller must be the local PC\r\n",
            SafeReadable((void*)(hero+0x1090),1)?*(uint8_t*)(hero+0x1090):0,
            SafeReadable((void*)(hero+0x1BE8),1)?*(uint8_t*)(hero+0x1BE8):0);
    const char* chain[]={"ClientInitialComponentSetup","BP_PostSetupCosmetics","TryLocalControlSetup","RefreshLocalControl"};
    for(int i=0;i<4;i++){
        void* fn=0; uintptr_t th=0,ch=0; ResolveFunc(hc,chain[i],&fn,&th,&ch);
        if(!fn){ Markerf("[BC] %-28s NOT FOUND\r\n",chain[i]); continue; }
        uint32_t sn=SafeReadable((void*)((uintptr_t)fn+UFUNC_SCRIPTNUM),4)?*(uint32_t*)((uintptr_t)fn+UFUNC_SCRIPTNUM):0;
        bool fault=CallBP(hero,fn,nullptr,0);
        Markerf("[BC] %-28s script=%-4u fault=%d  %s\r\n",chain[i],sn,fault,(!fault&&sn)?"RAN":(sn?"FAULTED":"empty stub - skipped"));
    }
    // ★ S80c: report the mesh HONESTLY via ACharacter::Mesh, not CountHeroSkeletals(). That counter greps class names
    // for "SkeletalMeshComponent" and MISSES this build's `BP_Assault_DefaultSKMeshComponent_C` ("SKMesh" != "Skeletal
    // Mesh") — it reported 0 for a component that exists, has SK_Assault_Default_LOD1 assigned, and is on screen. Its
    // bogus 0 is what invented the entire S79 "mesh wall" + cosmetics chase.
    { uint32_t mo=PropOffsetOnClass(hc,"Mesh");
      uintptr_t mesh=(mo!=0xFFFFFFFF && SafeReadable((void*)(hero+mo),8))?*(uintptr_t*)(hero+mo):0;
      char mcn[96]="?"; if(LooksLikePtr(mesh)) ClassName(mesh,mcn,sizeof(mcn));
      uintptr_t skm=0; if(LooksLikePtr(mesh)){ uint32_t so=PropOffsetOnClass(ClassOf(mesh),"SkeletalMesh");
          if(so!=0xFFFFFFFF && SafeReadable((void*)(mesh+so),8)) skm=*(uintptr_t*)(mesh+so); }
      char skn[96]="<none>"; if(LooksLikePtr(skm)) ObjName(skm,skn,sizeof(skn));
      Markerf("[BC] hero->Mesh @+0x%X = 0x%llX [%s] SkeletalMesh='%s'\r\n",mo,(unsigned long long)mesh,mcn,skn); }
    Marker("[BC] === done ===\r\n");
}
// ===== S80 MODE_DEVSWAP: swap to the BP_Dev PC (which OWNS the input events) + ClientRestart there =====
static volatile long g_dsReps=0; static uintptr_t g_dsL=0,g_dsDev=0,g_dsOld=0,g_dsHero=0,g_dsCamMgr=0;
static void* g_dsCrFn=0; static uintptr_t g_dsCrThunk=0,g_dsCrCh=0;
static void DoDevSwap(){
    long rep=InterlockedIncrement(&g_dsReps);
    if(rep==1){
        Marker("[DS] === S80 devswap: LocalPlayer -> BP_Dev PC (owns the 45 input events) + ClientRestart ===\r\n");
        g_dsL=FindInstExactClass("LocalPlayer"); if(!g_dsL) g_dsL=FindInstClassSub("LocalPlayer");
        if(!LooksLikePtr(g_dsL)){ Marker("[DS] no LocalPlayer — abort\r\n"); g_done=1; return; }
        g_dsOld=SafeReadable((void*)(g_dsL+0x38),8)?*(uintptr_t*)(g_dsL+0x38):0;
        g_dsDev=FindInstExactClass("BP_LokiPlayerController_Dev_C");
        if(!LooksLikePtr(g_dsDev)){ Marker("[DS] no live BP_Dev PC — abort\r\n"); g_done=1; return; }
        // hero = the pawn the native PC currently drives (S79 4d raw-wired it)
        uint32_t po=PropOffsetOnClass(ClassOf(g_dsOld),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
        g_dsHero=SafeReadable((void*)(g_dsOld+pawnOff),8)?*(uintptr_t*)(g_dsOld+pawnOff):0;
        char oc[96]="?",dc[96]="?",hc2[96]="?";
        ClassName(g_dsOld,oc,sizeof(oc)); ClassName(g_dsDev,dc,sizeof(dc)); if(LooksLikePtr(g_dsHero))ClassName(g_dsHero,hc2,sizeof(hc2));
        Markerf("[DS] L=0x%llX oldPC=0x%llX [%s]  devPC=0x%llX [%s]  hero=0x%llX [%s]\r\n",
                (unsigned long long)g_dsL,(unsigned long long)g_dsOld,oc,(unsigned long long)g_dsDev,dc,(unsigned long long)g_dsHero,hc2);
        // ClientRestart on the DEV PC's class (native UFunction, ParmsSize=8 -> APawn* NewPawn)
        ResolveFunc(ClassOf(g_dsDev),"ClientRestart",&g_dsCrFn,&g_dsCrThunk,&g_dsCrCh);
        Markerf("[DS] ClientRestart on devPC class: fn=0x%llX thunk=0x%llX child=0x%llX\r\n",
                (unsigned long long)(uintptr_t)g_dsCrFn,(unsigned long long)g_dsCrThunk,(unsigned long long)g_dsCrCh);
        g_dsCamMgr=FindInstClassSub("PlayerCameraManager");
        // ---- THE SWAP (S79 Phase-3 proven: held 10s, no revert) ----
        if(SafeReadable((void*)(g_dsL+0x38),8))    *(uintptr_t*)(g_dsL+0x38)=g_dsDev;
        if(SafeReadable((void*)(g_dsDev+0x458),8)) *(uintptr_t*)(g_dsDev+0x458)=g_dsL;
        // ★★★ DO **NOT** null the native PC's Player (+0x458). LIVE-PROVEN FATAL (S80, Loki.log):
        // the NATIVE PC owns the NetConnection and UE resolves an RPC's owning connection THROUGH the
        // PC<->Player link. Zeroing it made the next `ServerEcho` heartbeat fail with
        // "UNetDriver::ProcessRemoteFunction: No owning connection for actor LokiPlayerController_..."
        // -> GameNetDriver shut down -> "LogTravelManager: starting client travel ... LVL_Login" -> the
        // whole 23-hour DS session (hero + BP_Dev PCs + swap) was destroyed. S79 Phase 3 got away with it
        // only because 4d reverted within 10s, before the heartbeat tripped.
        // Leave oldPC->Player pointing at the LocalPlayer: both PCs referencing it is inconsistent but
        // SURVIVABLE, and it is what keeps the net connection alive.
        Marker("[DS] swapped L->PlayerController = devPC (oldPC->Player deliberately LEFT INTACT — nulling it kills the NetConnection)\r\n");
        // ---- give the dev PC the hero, then ClientRestart THERE (the untested variable) ----
        if(LooksLikePtr(g_dsHero)){
            uint32_t dpo=PropOffsetOnClass(ClassOf(g_dsDev),"Pawn"); uint32_t dPawnOff=(dpo!=0xFFFFFFFF)?dpo:0x3F8;
            if(SafeReadable((void*)(g_dsDev+dPawnOff),8)) *(uintptr_t*)(g_dsDev+dPawnOff)=g_dsHero;
            uint32_t co=PropOffsetOnClass(ClassOf(g_dsHero),"Controller"); uint32_t ctlOff=(co!=0xFFFFFFFF)?co:0x400;
            if(SafeReadable((void*)(g_dsHero+ctlOff),8)) *(uintptr_t*)(g_dsHero+ctlOff)=g_dsDev;
            Markerf("[DS] wired devPC->Pawn=hero (@+0x%X) and hero->Controller=devPC (@+0x%X)\r\n",dPawnOff,ctlOff);
            if(g_dsCrThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                *(uintptr_t*)g_pbuf=g_dsHero;                     // APawn* NewPawn
                bool f=CallGuarded(g_dsCrFn,g_dsCrThunk,g_dsCrCh,(void*)g_dsDev,g_pbuf,g_rbuf);
                Markerf("[DS] ★ ClientRestart(devPC, hero) fault=%d %s\r\n",f,f?"":"<<< RAN on a PC that OWNS the input events"); }
        }
        // did the dev PC get a PlayerCameraManager? (SetPlayer would normally spawn one)
        uint32_t cmo=PropOffsetOnClass(ClassOf(g_dsDev),"PlayerCameraManager");
        uintptr_t devCam=(cmo!=0xFFFFFFFF&&SafeReadable((void*)(g_dsDev+cmo),8))?*(uintptr_t*)(g_dsDev+cmo):0;
        uint32_t ico=PropOffsetOnClass(ClassOf(g_dsDev),"InputComponent");
        uintptr_t devIC=(ico!=0xFFFFFFFF&&SafeReadable((void*)(g_dsDev+ico),8))?*(uintptr_t*)(g_dsDev+ico):0;
        Markerf("[DS] devPC->PlayerCameraManager @+0x%X = 0x%llX | devPC->InputComponent @+0x%X = 0x%llX\r\n",
                cmo,(unsigned long long)devCam,ico,(unsigned long long)devIC);
        return;
    }
    // monitor: does the swap hold, and does the RENDERING camera follow?
    uintptr_t cur=SafeReadable((void*)(g_dsL+0x38),8)?*(uintptr_t*)(g_dsL+0x38):0;
    uintptr_t vt=(LooksLikePtr(g_dsCamMgr)&&SafeReadable((void*)(g_dsCamMgr+0x420),8))?*(uintptr_t*)(g_dsCamMgr+0x420):0;
    if(rep%4==0) Markerf("[DS] t+%ld: L->PC=%s  camMgr viewTarget=0x%llX %s\r\n",rep,
        cur==g_dsDev?"devPC (HOLDING)":(cur==g_dsOld?"REVERTED to native":"other"),
        (unsigned long long)vt, vt==g_dsHero?"== HERO":"");
    if(rep>=20){ Marker("[DS] === done ===\r\n"); g_done=1; }
}
// ===== S80 MODE_MOVETEST: call the game's own native movement entry points and watch the hero =====
static volatile long g_mtReps=0;
static uintptr_t g_mtPC=0,g_mtHero=0,g_mtCMC=0;
static void* g_mtFwdFn=0; static uintptr_t g_mtFwdThunk=0,g_mtFwdCh=0;
static void* g_mtRgtFn=0; static uintptr_t g_mtRgtThunk=0,g_mtRgtCh=0;
static void* g_mtLocFn=0; static uintptr_t g_mtLocThunk=0,g_mtLocCh=0;
static void* g_mtAmiFn=0; static uintptr_t g_mtAmiThunk=0,g_mtAmiCh=0;   // APawn::AddMovementInput — the REAL entry
static void* g_mtSmFn=0; static uintptr_t g_mtSmThunk=0,g_mtSmCh=0;      // CMC::SetMovementMode (re-asserted per tick)
static double g_mtX0=0,g_mtY0=0,g_mtZ0=0;
static bool MtLoc(double* x,double* y,double* z){
    if(!g_mtLocThunk) return false;
    memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
    if(CallGuarded(g_mtLocFn,g_mtLocThunk,g_mtLocCh,(void*)g_mtHero,g_pbuf,g_rbuf)) return false;
    *x=*(double*)(g_rbuf+0); *y=*(double*)(g_rbuf+8); *z=*(double*)(g_rbuf+16); return true;
}
static void DoMoveTest(){
    long rep=InterlockedIncrement(&g_mtReps);
    if(rep==1){
        Marker("[MT] === S80 movetest: call NATIVE MoveForward/MoveRight, watch the hero ===\r\n");
        uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L) L=FindInstClassSub("LocalPlayer");
        if(!LooksLikePtr(L)){ Marker("[MT] no LocalPlayer\r\n"); g_done=1; return; }
        g_mtPC=SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0;
        if(!LooksLikePtr(g_mtPC)){ Marker("[MT] L->PC null\r\n"); g_done=1; return; }
        uint32_t po=PropOffsetOnClass(ClassOf(g_mtPC),"Pawn"); uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
        g_mtHero=SafeReadable((void*)(g_mtPC+pawnOff),8)?*(uintptr_t*)(g_mtPC+pawnOff):0;
        char pc[96]="?",hc[96]="?"; ClassName(g_mtPC,pc,sizeof(pc)); if(LooksLikePtr(g_mtHero))ClassName(g_mtHero,hc,sizeof(hc));
        Markerf("[MT] L->PC=0x%llX [%s]  current Pawn=0x%llX [%s]\r\n",(unsigned long long)g_mtPC,pc,(unsigned long long)g_mtHero,hc);
        // ★ If the PC is driving a DefaultPawn (the dead-spectator state), hand it a REAL hero instead.
        // NB we wire the hero onto the NATIVE PC and NEVER touch oldPC->Player — nulling Player killed the
        // NetConnection and re-travelled the client (S80, see the MODE_DEVSWAP comment). No swap => no disconnect.
        if(!LooksLikePtr(g_mtHero) || strstr(hc,"DefaultPawn")){
            uintptr_t real=FindInstExactClass("BP_HERO_Assault_C");
            if(!LooksLikePtr(real)){ Marker("[MT] no live BP_HERO_Assault_C to test with — run MODE_SPAWN_P2 first\r\n"); g_done=1; return; }
            uint32_t co2=PropOffsetOnClass(ClassOf(real),"Controller"); uint32_t ctlOff=(co2!=0xFFFFFFFF)?co2:0x400;
            if(SafeReadable((void*)(g_mtPC+pawnOff),8)) *(uintptr_t*)(g_mtPC+pawnOff)=real;   // nativePC->Pawn = hero
            if(SafeReadable((void*)(real+ctlOff),8))    *(uintptr_t*)(real+ctlOff)=g_mtPC;    // hero->Controller = nativePC
            if(SafeReadable((void*)(real+0x1090),1))    *(uint8_t*)(real+0x1090)=1;           // LivingState = Alive
            if(SafeReadable((void*)(real+0x1BE8),1))    *(uint8_t*)(real+0x1BE8)=0;           // clear pre-drop hide
            g_mtHero=real;
            Markerf("[MT] ★ wired NATIVE PC -> hero 0x%llX (Pawn@+0x%X, Controller@+0x%X), LivingState=Alive; Player link untouched\r\n",
                    (unsigned long long)real,pawnOff,ctlOff);
        }
        if(!LooksLikePtr(g_mtHero)){ Marker("[MT] no pawn — nothing to move\r\n"); g_done=1; return; }
        ResolveFunc(ClassOf(g_mtPC),"MoveForward",&g_mtFwdFn,&g_mtFwdThunk,&g_mtFwdCh);
        ResolveFunc(ClassOf(g_mtPC),"MoveRight",  &g_mtRgtFn,&g_mtRgtThunk,&g_mtRgtCh);
        ResolveFunc(ClassOf(g_mtHero),"K2_GetActorLocation",&g_mtLocFn,&g_mtLocThunk,&g_mtLocCh);
        ResolveFunc(ClassOf(g_mtHero),"AddMovementInput",&g_mtAmiFn,&g_mtAmiThunk,&g_mtAmiCh);
        Markerf("[MT] AddMovementInput thunk=0x%llX child=0x%llX\r\n",(unsigned long long)g_mtAmiThunk,(unsigned long long)g_mtAmiCh);
        Markerf("[MT] MoveForward thunk=0x%llX child=0x%llX | MoveRight thunk=0x%llX | GetLoc thunk=0x%llX\r\n",
                (unsigned long long)g_mtFwdThunk,(unsigned long long)g_mtFwdCh,(unsigned long long)g_mtRgtThunk,(unsigned long long)g_mtLocThunk);
        if(g_mtFwdCh){ uint32_t vo=ParamOffset(g_mtFwdCh,"Val"); Markerf("[MT] MoveForward param 'Val' offset=0x%X\r\n",vo); }
        // --- diagnostics: the wiring + movement state that decide the outcome's meaning ---
        uint32_t co=PropOffsetOnClass(ClassOf(g_mtHero),"Controller");
        uintptr_t ctl=(co!=0xFFFFFFFF&&SafeReadable((void*)(g_mtHero+co),8))?*(uintptr_t*)(g_mtHero+co):0;
        uint32_t cmo=PropOffsetOnClass(ClassOf(g_mtHero),"CharacterMovement");
        g_mtCMC=(cmo!=0xFFFFFFFF&&SafeReadable((void*)(g_mtHero+cmo),8))?*(uintptr_t*)(g_mtHero+cmo):0;
        char cmn[96]="-"; if(LooksLikePtr(g_mtCMC)) ClassName(g_mtCMC,cmn,sizeof(cmn));
        Markerf("[MT] hero->Controller=0x%llX (%s the live PC) | CharacterMovement=0x%llX [%s]\r\n",
                (unsigned long long)ctl, ctl==g_mtPC?"==":"!=", (unsigned long long)g_mtCMC,cmn);
        if(LooksLikePtr(g_mtCMC)){
            uint32_t mmo=PropOffsetOnClass(ClassOf(g_mtCMC),"MovementMode");
            uint32_t vo2=PropOffsetOnClass(ClassOf(g_mtCMC),"Velocity");
            uint8_t mm=(mmo!=0xFFFFFFFF&&SafeReadable((void*)(g_mtCMC+mmo),1))?*(uint8_t*)(g_mtCMC+mmo):255;
            double vx=0,vy=0,vz=0;
            if(vo2!=0xFFFFFFFF&&SafeReadable((void*)(g_mtCMC+vo2),24)){ vx=*(double*)(g_mtCMC+vo2); vy=*(double*)(g_mtCMC+vo2+8); vz=*(double*)(g_mtCMC+vo2+16); }
            Markerf("[MT] CMC MovementMode@+0x%X = %u (0=None 1=Walking 2=NavWalking 3=Falling 4=Swimming 5=Flying 6=Custom) | Velocity=(%.1f,%.1f,%.1f)\r\n",mmo,mm,vx,vy,vz);
        }
        uint8_t ls=SafeReadable((void*)(g_mtHero+0x1090),1)?*(uint8_t*)(g_mtHero+0x1090):255;
        Markerf("[MT] hero LivingState=%u (1=Alive)\r\n",ls);
        // ★★★ THE GATE (S80, live-proven): a GameplayStatics-spawned hero has CMC MovementMode = 0 (MOVE_None) =>
        // AddMovementInput is DISCARDED, Velocity stays 0, and MoveForward runs clean but moves nothing. Drive the
        // CMC's own native UFUNCTION SetMovementMode(EMovementMode NewMovementMode, uint8 NewCustomMode) to
        // MOVE_Walking(1) first. (kMoveMode overridable: 1=Walking 3=Falling 5=Flying.)
        if(LooksLikePtr(g_mtCMC)){
            void* smFn=0; uintptr_t smTh=0,smCh=0;
            ResolveFunc(ClassOf(g_mtCMC),"SetMovementMode",&smFn,&smTh,&smCh);
            g_mtSmFn=smFn; g_mtSmThunk=smTh; g_mtSmCh=smCh;   // persist: the tick re-asserts the mode
            Markerf("[MT] SetMovementMode thunk=0x%llX child=0x%llX\r\n",(unsigned long long)smTh,(unsigned long long)smCh);
            if(smTh){
                uint32_t mo=smCh?ParamOffset(smCh,"NewMovementMode"):0xFFFFFFFF;
                uint32_t co3=smCh?ParamOffset(smCh,"NewCustomMode"):0xFFFFFFFF;
                memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                g_pbuf[(mo!=0xFFFFFFFF&&mo<200)?mo:0]=(uint8_t)kMoveMode;      // EMovementMode: 1 = MOVE_Walking
                if(co3!=0xFFFFFFFF&&co3<200) g_pbuf[co3]=0;
                bool sf=CallGuarded(smFn,smTh,smCh,(void*)g_mtCMC,g_pbuf,g_rbuf);
                uint32_t mmo=PropOffsetOnClass(ClassOf(g_mtCMC),"MovementMode");
                uint8_t mm=(mmo!=0xFFFFFFFF&&SafeReadable((void*)(g_mtCMC+mmo),1))?*(uint8_t*)(g_mtCMC+mmo):255;
                Markerf("[MT] ★ SetMovementMode(%u) fault=%d (params: mode@0x%X custom@0x%X) -> MovementMode is now %u %s\r\n",
                        kMoveMode,sf,mo,co3,mm, mm==kMoveMode?"<<< MODE SET":"<<< mode did NOT stick");
            }
        }
        // ★★★ THE SUSPECT: CalcVelocity does `Velocity += Acceleration*dt; Velocity.GetClampedToMaxSize(GetMaxSpeed())`.
        // Accel is a full (50000,0,0) yet Velocity stays 0 => the clamp is the only thing that can be zeroing it.
        // GetMaxSpeed() is VIRTUAL and LokiCharacterMovementComponent likely overrides it to return a GAS
        // attribute-driven speed — a hero with an uninitialised ASC would get 0 (base MaxWalkSpeed=180/MaxFlySpeed=600
        // are non-zero, so the base props are NOT the zero). Call it and read the real value.
        if(LooksLikePtr(g_mtCMC)){
            void* gsFn=0; uintptr_t gsTh=0,gsCh=0;
            ResolveFunc(ClassOf(g_mtCMC),"GetMaxSpeed",&gsFn,&gsTh,&gsCh);
            if(gsTh){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                bool gf=CallGuarded(gsFn,gsTh,gsCh,(void*)g_mtCMC,g_pbuf,g_rbuf);
                float ms=*(float*)g_rbuf;
                Markerf("[MT] ★★★ GetMaxSpeed() fault=%d -> %g   %s\r\n",gf,ms,
                        (ms<0.001f)?"<<<<<< ZERO — CalcVelocity clamps Velocity to 0. THIS IS THE GATE.":"(non-zero — the clamp is NOT the gate)"); }
            void* gaFn=0; uintptr_t gaTh=0,gaCh=0;
            ResolveFunc(ClassOf(g_mtCMC),"GetMaxAcceleration",&gaFn,&gaTh,&gaCh);
            if(gaTh){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
                CallGuarded(gaFn,gaTh,gaCh,(void*)g_mtCMC,g_pbuf,g_rbuf);
                Markerf("[MT] GetMaxAcceleration() -> %g\r\n",*(float*)g_rbuf); }
        }
        if(MtLoc(&g_mtX0,&g_mtY0,&g_mtZ0)) Markerf("[MT] hero loc BEFORE = (%.1f, %.1f, %.1f)\r\n",g_mtX0,g_mtY0,g_mtZ0);
        else Marker("[MT] K2_GetActorLocation FAULTED\r\n");
        if(!g_mtFwdThunk){ Marker("[MT] MoveForward NOT RESOLVED on this PC — abort\r\n"); g_done=1; return; }
        return;
    }
    // ★★★ Each tick: drive APawn::AddMovementInput ON THE HERO — the REAL movement entry.
    // NOT PlayerController::MoveForward: S80 disasm proved LokiPlayerController::MoveForward is the
    // SPECTATOR/free-cam path — at base+0x569A1B1 it does `cmp [this+0x3F8],0 / jne <epilogue>`, i.e. it
    // RETURNS IMMEDIATELY when the PC HAS a pawn (a possessed pawn is expected to move itself), and its
    // movement branch drives the PlayerCameraManager at [this+0x470]. That is also why the earlier
    // "HERO MOVED" was a false positive: it was moving the DefaultPawn spectator via the camera path.
    // AddMovementInput(FVector WorldDirection, float ScaleValue, bool bForce) — ParmsSize=29:
    // vec(24 doubles) + float@0x18 + bool@0x1C. bForce=true bypasses the input-allowed gate.
    // ★ Re-assert the movement mode EVERY tick. The one-shot SetMovementMode(Walking) flipped straight to 3
    // (MOVE_Falling) and STUCK there even after the hero settled at a stable Z — and in MOVE_Falling horizontal
    // input is scaled by AirControl (~0 in a MOBA), which exactly explains vel.X==vel.Y==0 while gravity works.
    // kMoveMode=5 (MOVE_Flying) has no gravity and full directional control, so it ISOLATES "is AddMovementInput
    // reaching the CMC at all?" from "is the walking/floor state broken?".
    if(g_mtSmThunk && LooksLikePtr(g_mtCMC)){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        g_pbuf[0]=(uint8_t)kMoveMode; g_pbuf[1]=0;
        CallGuarded(g_mtSmFn,g_mtSmThunk,g_mtSmCh,(void*)g_mtCMC,g_pbuf,g_rbuf);
    }
    bool f1=true;
    if(g_mtAmiThunk){
        memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf));
        uint32_t vo=g_mtAmiCh?ParamOffset(g_mtAmiCh,"WorldDirection"):0xFFFFFFFF;
        uint32_t so=g_mtAmiCh?ParamOffset(g_mtAmiCh,"ScaleValue"):0xFFFFFFFF;
        uint32_t bo=g_mtAmiCh?ParamOffset(g_mtAmiCh,"bForce"):0xFFFFFFFF;
        if(vo==0xFFFFFFFF||vo>200) vo=0; if(so==0xFFFFFFFF||so>200) so=0x18; if(bo==0xFFFFFFFF||bo>200) bo=0x1C;
        *(double*)(g_pbuf+vo+0)=1.0; *(double*)(g_pbuf+vo+8)=0.0; *(double*)(g_pbuf+vo+16)=0.0;  // +X world dir
        *(float*)(g_pbuf+so)=1.0f;                                                                // ScaleValue
        g_pbuf[bo]=1;                                                                             // bForce = true
        f1=CallGuarded(g_mtAmiFn,g_mtAmiThunk,g_mtAmiCh,(void*)g_mtHero,g_pbuf,g_rbuf);
        if(rep==2) Markerf("[MT] AddMovementInput(hero, (1,0,0), 1.0, bForce=true) fault=%d (vec@0x%X scale@0x%X force@0x%X)\r\n",f1,vo,so,bo);
    } else if(rep==2) Marker("[MT] AddMovementInput NOT RESOLVED\r\n");
    if(rep%8==0){
        double x,y,z;
        if(MtLoc(&x,&y,&z)){
            double d=(x-g_mtX0)*(x-g_mtX0)+(y-g_mtY0)*(y-g_mtY0);
            // Is the input REACHING the CMC? Velocity + ControlInputVector split "input not delivered"
            // from "input delivered but movement suppressed".
            double vx=0,vy=0,vz=0; uint8_t mm=255;
            if(LooksLikePtr(g_mtCMC)){
                uint32_t vo2=PropOffsetOnClass(ClassOf(g_mtCMC),"Velocity");
                if(vo2!=0xFFFFFFFF&&SafeReadable((void*)(g_mtCMC+vo2),24)){ vx=*(double*)(g_mtCMC+vo2); vy=*(double*)(g_mtCMC+vo2+8); vz=*(double*)(g_mtCMC+vo2+16); }
                uint32_t mmo=PropOffsetOnClass(ClassOf(g_mtCMC),"MovementMode");
                if(mmo!=0xFFFFFFFF&&SafeReadable((void*)(g_mtCMC+mmo),1)) mm=*(uint8_t*)(g_mtCMC+mmo);
            }
            // ★ THE DECISIVE SPLIT: APawn::ControlInputVector is what AddMovementInput accumulates into, and
            // LastControlInputVector is what the CMC actually CONSUMED last tick (both UPROPERTY(Transient)).
            //   ControlInput != 0            => AddMovementInput WORKS; the CMC is ignoring/zeroing it.
            //   ControlInput == 0 but Last!=0 => it IS being consumed, but produces no acceleration.
            //   both == 0                     => AddMovementInput never accumulated (wrong pawn/movement comp).
            double cx=0,cy=0,cz=0, lx=0,ly=0,lz=0, ax=0,ay=0,az=0;
            uint32_t cio=PropOffsetOnClass(ClassOf(g_mtHero),"ControlInputVector");
            if(cio!=0xFFFFFFFF&&SafeReadable((void*)(g_mtHero+cio),24)){ cx=*(double*)(g_mtHero+cio); cy=*(double*)(g_mtHero+cio+8); cz=*(double*)(g_mtHero+cio+16); }
            uint32_t lio=PropOffsetOnClass(ClassOf(g_mtHero),"LastControlInputVector");
            if(lio!=0xFFFFFFFF&&SafeReadable((void*)(g_mtHero+lio),24)){ lx=*(double*)(g_mtHero+lio); ly=*(double*)(g_mtHero+lio+8); lz=*(double*)(g_mtHero+lio+16); }
            uint32_t aco=LooksLikePtr(g_mtCMC)?PropOffsetOnClass(ClassOf(g_mtCMC),"Acceleration"):0xFFFFFFFF;
            if(aco!=0xFFFFFFFF&&SafeReadable((void*)(g_mtCMC+aco),24)){ ax=*(double*)(g_mtCMC+aco); ay=*(double*)(g_mtCMC+aco+8); az=*(double*)(g_mtCMC+aco+16); }
            Markerf("[MT] t+%ld loc=(%.1f,%.1f,%.1f) vel=(%.1f,%.1f,%.1f) mode=%u | ControlInput=(%.2f,%.2f,%.2f)@0x%X LastCtrl=(%.2f,%.2f,%.2f) Accel=(%.1f,%.1f,%.1f)@0x%X %s\r\n",
                    rep,x,y,z,vx,vy,vz,mm,cx,cy,cz,cio,lx,ly,lz,ax,ay,az,aco,
                    d>4.0?"<<<<<< THE HERO IS MOVING":"(no XY change)");
        }
    }
    if(rep>=80){
        double x,y,z;
        if(MtLoc(&x,&y,&z)){
            double dx=x-g_mtX0, dy=y-g_mtY0, dz=z-g_mtZ0;
            Markerf("[MT] FINAL loc=(%.1f, %.1f, %.1f)  delta=(%.1f, %.1f, %.1f)\r\n",x,y,z,dx,dy,dz);
            bool moved=(dx*dx+dy*dy)>25.0;
            Markerf("[MT] ★ VERDICT: %s\r\n", moved
                ? "HERO MOVED via native MoveForward => the movement path WORKS; the only gap is key->axis binding"
                : "HERO DID NOT MOVE => movement is gated deeper (see CMC MovementMode / Velocity above)");
        }
        Marker("[MT] === done ===\r\n"); g_done=1;
    }
}
static void DoUFuncDump(){
    Marker("[UF] === UFunction field dump (find Script + PropertiesSize) ===\r\n");
    uintptr_t L=FindInstExactClass("LocalPlayer"); if(!L)L=FindInstClassSub("LocalPlayer");
    uintptr_t pc = LooksLikePtr(L)?(SafeReadable((void*)(L+0x38),8)?*(uintptr_t*)(L+0x38):0):0;
    uint32_t po = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"Pawn"):0xFFFFFFFF; uint32_t pawnOff=(po!=0xFFFFFFFF)?po:0x3F8;
    uintptr_t hero = LooksLikePtr(pc)?(SafeReadable((void*)(pc+pawnOff),8)?*(uintptr_t*)(pc+pawnOff):0):0;
    if(!LooksLikePtr(hero)){ Marker("[UF] no hero\r\n"); return; }
    void* fn=0; uintptr_t th=0,ch=0; ResolveFunc(ClassOf(hero),"ReceiveRestarted",&fn,&th,&ch);
    if(!fn) ResolveFunc(ClassOf(hero),"BP_PostSetupCosmetics",&fn,&th,&ch);
    if(!fn){ Marker("[UF] no BP fn resolved\r\n"); return; }
    uintptr_t f=(uintptr_t)fn; char nm[128]="?"; GetFNameStr(NameId(f),nm,sizeof(nm));
    Markerf("[UF] UFunction '%s' @0x%llX (Func@+0xE0=0x%llX == ProcessInternal base+0x13454A0=0x%llX?)\r\n",
            nm,(unsigned long long)f,(unsigned long long)(SafeReadable((void*)(f+0xE0),8)?*(uintptr_t*)(f+0xE0):0),(unsigned long long)(g_modBase+kPiRva));
    for(uint32_t o=0x40;o<0x100;o+=8){ if(!SafeReadable((void*)(f+o),8))break; uint64_t q=*(uint64_t*)(f+o); int lo=(int)(uint32_t)q,hi=(int)(uint32_t)(q>>32);
        Markerf("[UF]   +0x%X: 0x%016llX  i32(lo=%d hi=%d)%s\r\n",o,(unsigned long long)q,lo,hi, LooksLikePtr(q)?" [ptr]":""); }
    Marker("[UF] (look for: PropertiesSize=small int32; Script=TArray {heap-ptr, num>0, max}) ===\r\n");
}
// Deploy step 7: create the cosmetics controller via BP setup (ProcessEvent) so RefreshCosmetics builds the mesh.
static void* g_bdCicsFn=0; static void* g_bdPscFn=0; static void* g_bdTlcsFn=0;      // BP UFunction*s
static void* g_bdGccFn=0;  static uintptr_t g_bdGccThunk=0,g_bdGccCh=0;             // GetCosmeticsController (native)
static volatile long g_bdReps=0; static uint8_t g_bdPaid[16]={0};
static bool ResolveBPDeploy(){
    if(!ResolveCosmetics()) return false;      // g_cmHero + RefreshCosmetics/vis
    ResolveLoadCensus();                        // pafs/load/lam/world (best-effort)
    uintptr_t hc=ClassOf(g_cmHero), th=0, ch=0;
    ResolveFunc(hc,"ClientInitialComponentSetup",&g_bdCicsFn,&th,&ch);
    ResolveFunc(hc,"BP_PostSetupCosmetics",&g_bdPscFn,&th,&ch);
    ResolveFunc(hc,"TryLocalControlSetup",&g_bdTlcsFn,&th,&ch);
    ResolveFunc(hc,"GetCosmeticsController",&g_bdGccFn,&g_bdGccThunk,&g_bdGccCh);
    Markerf("[BD] hero=0x%llX cicsFn=0x%llX pscFn=0x%llX tlcsFn=0x%llX gccThunk=0x%llX peRva=0x%llX\r\n",
            (unsigned long long)g_cmHero,(unsigned long long)(uintptr_t)g_bdCicsFn,(unsigned long long)(uintptr_t)g_bdPscFn,
            (unsigned long long)(uintptr_t)g_bdTlcsFn,(unsigned long long)g_bdGccThunk,(unsigned long long)(g_modBase+kProcEventRva));
    return g_cmHero!=0;
}
static uintptr_t BdGetController(){ if(!g_bdGccThunk)return 0; memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); if(CallGuarded(g_bdGccFn,g_bdGccThunk,g_bdGccCh,(void*)g_cmHero,g_pbuf,g_rbuf))return 0; return *(uintptr_t*)g_rbuf; }
static void DoBPDeploy(){
    long rep=InterlockedIncrement(&g_bdReps);
    if(rep==1){
        Marker("[BD] === BP deploy setup via ProcessEvent ===\r\n");
        Markerf("[BD] controller BEFORE=0x%llX skeletal BEFORE=%d\r\n",(unsigned long long)BdGetController(),CountHeroSkeletals());
        // (re)assign the CosmeticsAssetID + async-load the skin
        if(g_pafsThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); LcSetFStr(g_pbuf,KSKIN); if(!CallGuarded(g_pafsFn,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf)) memcpy(g_bdPaid,g_rbuf,16); }
        uint32_t caOff=PropOffsetOnClass(ClassOf(g_cmHero),"CosmeticsAssetID"); uint32_t ovOff=PropOffsetOnClass(ClassOf(g_cmHero),"OverrideCosmeticsAssetID");
        if(*(uint64_t*)g_bdPaid){ if(caOff!=0xFFFFFFFF&&SafeReadable((void*)(g_cmHero+caOff),16))memcpy((void*)(g_cmHero+caOff),g_bdPaid,16); if(ovOff!=0xFFFFFFFF&&SafeReadable((void*)(g_cmHero+ovOff),16))memcpy((void*)(g_cmHero+ovOff),g_bdPaid,16);
            if(g_lcLoadThunk){ static uint8_t lb[16]; memcpy(lb,g_bdPaid,16); memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); *(uint64_t*)(g_pbuf+0)=(uint64_t)g_lcWorld; *(uint64_t*)(g_pbuf+8)=(uint64_t)lb; *(uint32_t*)(g_pbuf+16)=1; *(uint32_t*)(g_pbuf+20)=1; CallGuarded(g_lcLoadFn,g_lcLoadThunk,g_lcLoadChild,(void*)g_lam,g_pbuf,g_rbuf); } }
        // ★ BP setup via ProcessEvent — creates components + cosmetics controller
        Marker(CallGuardedBP(g_cmHero,g_bdCicsFn)?"[BD] ClientInitialComponentSetup FAULTED\r\n":"[BD] ClientInitialComponentSetup called\r\n");
        Marker(CallGuardedBP(g_cmHero,g_bdPscFn) ?"[BD] BP_PostSetupCosmetics FAULTED\r\n"     :"[BD] BP_PostSetupCosmetics called\r\n");
    }
    // every rep: RefreshCosmetics (native) + keep Alive/visible; rebuild once the controller + async asset are ready
    if(g_cmRefThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmRefFn,g_cmRefThunk,g_cmRefChild,(void*)g_cmHero,g_pbuf,g_rbuf); }
    if(SafeReadable((void*)(g_cmHero+0x1090),1)) *(uint8_t*)(g_cmHero+0x1090)=1;
    if(SafeReadable((void*)(g_cmHero+0x1BE8),1)) *(uint8_t*)(g_cmHero+0x1BE8)=0;
    if(g_cmVisThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmVisFn,g_cmVisThunk,g_cmVisChild,(void*)g_cmHero,g_pbuf,g_rbuf); }
    if(rep==1||rep==8||rep==16) Markerf("[BD] rep %ld: controller=0x%llX skeletal=%d\r\n",rep,(unsigned long long)BdGetController(),CountHeroSkeletals());
}
// Deploy step 8: give the hero the PC's PlayerState (the deploy-context the BP setup reads), then retry the BP setup.
static void* g_cxPsOrpFn=0; static uintptr_t g_cxPsOrpThunk=0,g_cxPsOrpCh=0;   // OnRep_PlayerState (native)
static volatile long g_cxReps=0; static uint8_t g_cxPaid[16]={0};
static bool ResolveContext(){
    if(!ResolveBPDeploy()) return false;   // g_cmHero + BP fns (g_bdCicsFn/g_bdPscFn) + RefreshCosmetics + pafs/load
    ResolveFunc(ClassOf(g_cmHero),"OnRep_PlayerState",&g_cxPsOrpFn,&g_cxPsOrpThunk,&g_cxPsOrpCh);
    Markerf("[CX] OnRep_PlayerState thunk=0x%llX (BP fns from BPDeploy)\r\n",(unsigned long long)g_cxPsOrpThunk);
    return true;
}
static void DoContext(){
    long rep=InterlockedIncrement(&g_cxReps); uintptr_t hero=g_cmHero;
    if(rep==1){
        Marker("[CX] === context reconstruction: give the hero a PlayerState + retry BP setup ===\r\n");
        uintptr_t Lp=FindInstExactClass("LocalPlayer"); if(!Lp)Lp=FindInstClassSub("LocalPlayer");
        uintptr_t pc = LooksLikePtr(Lp)?(SafeReadable((void*)(Lp+0x38),8)?*(uintptr_t*)(Lp+0x38):0):0;
        uint32_t pcPsOff = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"PlayerState"):0xFFFFFFFF;
        uintptr_t ps = (LooksLikePtr(pc)&&pcPsOff!=0xFFFFFFFF&&SafeReadable((void*)(pc+pcPsOff),8))?*(uintptr_t*)(pc+pcPsOff):0;
        char psn[96]="<none>"; if(LooksLikePtr(ps))ClassName(ps,psn,sizeof(psn));
        Markerf("[CX] PC=0x%llX PlayerState@+0x%X = 0x%llX (%s)\r\n",(unsigned long long)pc,pcPsOff,(unsigned long long)ps,psn);
        uint32_t hPsOff=PropOffsetOnClass(ClassOf(hero),"PlayerState"); if(hPsOff==0xFFFFFFFF)hPsOff=0x3D8;
        uint32_t hLpsOff=PropOffsetOnClass(ClassOf(hero),"LocalPlayerState");
        if(LooksLikePtr(ps)){ if(SafeReadable((void*)(hero+hPsOff),8))*(uintptr_t*)(hero+hPsOff)=ps; if(hLpsOff!=0xFFFFFFFF&&SafeReadable((void*)(hero+hLpsOff),8))*(uintptr_t*)(hero+hLpsOff)=ps;
            Markerf("[CX] set hero PlayerState@+0x%X + LocalPlayerState@+0x%X = 0x%llX\r\n",hPsOff,hLpsOff,(unsigned long long)ps); }
        else Marker("[CX] PC has NO PlayerState — that itself may be the gap\r\n");
        if(g_cxPsOrpThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); Marker(CallGuarded(g_cxPsOrpFn,g_cxPsOrpThunk,g_cxPsOrpCh,(void*)hero,g_pbuf,g_rbuf)?"[CX] OnRep_PlayerState FAULTED\r\n":"[CX] OnRep_PlayerState done\r\n"); }
        // set the CosmeticsAssetID too
        if(g_pafsThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); LcSetFStr(g_pbuf,KSKIN); if(!CallGuarded(g_pafsFn,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf))memcpy(g_cxPaid,g_rbuf,16); }
        uint32_t caOff=PropOffsetOnClass(ClassOf(hero),"CosmeticsAssetID"); if(*(uint64_t*)g_cxPaid&&caOff!=0xFFFFFFFF&&SafeReadable((void*)(hero+caOff),16))memcpy((void*)(hero+caOff),g_cxPaid,16);
        // ★ retry the BP deploy setup now that PlayerState is present
        Marker(CallGuardedBP(hero,g_bdCicsFn)?"[CX] ClientInitialComponentSetup FAULTED (still)\r\n":"[CX] ★ ClientInitialComponentSetup OK\r\n");
        Marker(CallGuardedBP(hero,g_bdPscFn) ?"[CX] BP_PostSetupCosmetics FAULTED (still)\r\n"     :"[CX] ★ BP_PostSetupCosmetics OK\r\n");
    }
    if(g_cmRefThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmRefFn,g_cmRefThunk,g_cmRefChild,(void*)hero,g_pbuf,g_rbuf); }
    if(SafeReadable((void*)(hero+0x1090),1))*(uint8_t*)(hero+0x1090)=1;
    if(SafeReadable((void*)(hero+0x1BE8),1))*(uint8_t*)(hero+0x1BE8)=0;
    if(g_cmVisThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmVisFn,g_cmVisThunk,g_cmVisChild,(void*)hero,g_pbuf,g_rbuf); }
    if(rep==1||rep==8||rep==16) Markerf("[CX] rep %ld: controller=0x%llX skeletal=%d\r\n",rep,(unsigned long long)BdGetController(),CountHeroSkeletals());
}
// Deploy step 9: call the game's own deploy ORCHESTRATOR BP events (they run the init sequence in order internally).
static void* g_deRestartFn=0; static void* g_deSpawnedFn=0; static void* g_deRlcFn=0; static void* g_deTlcsFn=0;
static volatile long g_deReps=0;
static bool ResolveDeployEvt(){
    if(!ResolveContext()) return false;   // hero + BP fns + OnRep_PlayerState (via ResolveBPDeploy chain)
    uintptr_t hc=ClassOf(g_cmHero), th=0, ch=0;
    ResolveFunc(hc,"ReceiveRestarted",&g_deRestartFn,&th,&ch);
    ResolveFunc(hc,"OnLocalPlayer_CharacterSpawned",&g_deSpawnedFn,&th,&ch);
    ResolveFunc(hc,"RefreshLocalControl",&g_deRlcFn,&th,&ch);
    ResolveFunc(hc,"TryLocalControlSetup",&g_deTlcsFn,&th,&ch);
    Markerf("[DE] restartFn=0x%llX spawnedFn=0x%llX rlcFn=0x%llX tlcsFn=0x%llX\r\n",
            (unsigned long long)(uintptr_t)g_deRestartFn,(unsigned long long)(uintptr_t)g_deSpawnedFn,(unsigned long long)(uintptr_t)g_deRlcFn,(unsigned long long)(uintptr_t)g_deTlcsFn);
    return true;
}
static void DoDeployEvt(){
    long rep=InterlockedIncrement(&g_deReps); uintptr_t hero=g_cmHero;
    if(rep==1){
        Marker("[DE] === deploy orchestrator events (PlayerState set first) ===\r\n");
        // give the hero the PC's PlayerState (same as MODE_CONTEXT) + CosmeticsAssetID
        uintptr_t Lp=FindInstExactClass("LocalPlayer"); if(!Lp)Lp=FindInstClassSub("LocalPlayer");
        uintptr_t pc = LooksLikePtr(Lp)?(SafeReadable((void*)(Lp+0x38),8)?*(uintptr_t*)(Lp+0x38):0):0;
        uint32_t pcPsOff = LooksLikePtr(pc)?PropOffsetOnClass(ClassOf(pc),"PlayerState"):0xFFFFFFFF;
        uintptr_t ps = (LooksLikePtr(pc)&&pcPsOff!=0xFFFFFFFF&&SafeReadable((void*)(pc+pcPsOff),8))?*(uintptr_t*)(pc+pcPsOff):0;
        uint32_t hPsOff=PropOffsetOnClass(ClassOf(hero),"PlayerState"); if(hPsOff==0xFFFFFFFF)hPsOff=0x3D8;
        uint32_t hLpsOff=PropOffsetOnClass(ClassOf(hero),"LocalPlayerState");
        if(LooksLikePtr(ps)){ if(SafeReadable((void*)(hero+hPsOff),8))*(uintptr_t*)(hero+hPsOff)=ps; if(hLpsOff!=0xFFFFFFFF&&SafeReadable((void*)(hero+hLpsOff),8))*(uintptr_t*)(hero+hLpsOff)=ps; Markerf("[DE] PlayerState set = 0x%llX\r\n",(unsigned long long)ps); }
        if(g_pafsThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); LcSetFStr(g_pbuf,KSKIN); uint8_t paid[16]={0}; if(!CallGuarded(g_pafsFn,g_pafsThunk,g_pafsChild,(void*)g_lam,g_pbuf,g_rbuf))memcpy(paid,g_rbuf,16); uint32_t caOff=PropOffsetOnClass(ClassOf(hero),"CosmeticsAssetID"); if(*(uint64_t*)paid&&caOff!=0xFFFFFFFF&&SafeReadable((void*)(hero+caOff),16))memcpy((void*)(hero+caOff),paid,16); }
        // ★ the game's own deploy orchestrators (ordered init)
        Marker(CallGuardedBP(hero,g_deRestartFn)?"[DE] ReceiveRestarted FAULTED\r\n":"[DE] ★ ReceiveRestarted OK\r\n");
        Marker(CallGuardedBP(hero,g_deSpawnedFn)?"[DE] OnLocalPlayer_CharacterSpawned FAULTED\r\n":"[DE] ★ OnLocalPlayer_CharacterSpawned OK\r\n");
        Marker(CallGuardedBP(hero,g_deRlcFn)   ?"[DE] RefreshLocalControl FAULTED\r\n":"[DE] ★ RefreshLocalControl OK\r\n");
        Marker(CallGuardedBP(hero,g_deTlcsFn)  ?"[DE] TryLocalControlSetup FAULTED\r\n":"[DE] ★ TryLocalControlSetup OK\r\n");
    }
    if(g_cmRefThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmRefFn,g_cmRefThunk,g_cmRefChild,(void*)hero,g_pbuf,g_rbuf); }
    if(SafeReadable((void*)(hero+0x1090),1))*(uint8_t*)(hero+0x1090)=1;
    if(SafeReadable((void*)(hero+0x1BE8),1))*(uint8_t*)(hero+0x1BE8)=0;
    if(g_cmVisThunk){ memset(g_pbuf,0,sizeof(g_pbuf)); memset(g_rbuf,0,sizeof(g_rbuf)); CallGuarded(g_cmVisFn,g_cmVisThunk,g_cmVisChild,(void*)hero,g_pbuf,g_rbuf); }
    if(rep==1||rep==8||rep==16) Markerf("[DE] rep %ld: controller=0x%llX skeletal=%d\r\n",rep,(unsigned long long)BdGetController(),CountHeroSkeletals());
}
// Game-thread visit (ONE): discover the hero PrimaryAssetType, enumerate its ids, fire the async load.
static void DoLoadCensus(){
    static const wchar_t* kCand[] = { L"LokiHeroData:x", L"LokiHero:x", L"HeroData:x", L"Hero:x",
        L"LokiCharacterData:x", L"LokiCharacter:x", L"Character:x", L"LokiHeroDefinition:x",
        L"HeroDefinition:x", L"PlayableHero:x", L"Hunter:x", L"LokiHunter:x", L"HeroLoadout:x" };
    for(unsigned c=0;c<sizeof(kCand)/sizeof(kCand[0]);c++){
        uint32_t tid=LcTypeId(kCand[c]);
        static uint64_t tmp[LC_NMAX][2]; int num = tid ? LcQueryIds(tid,tmp,LC_NMAX) : 0;
        Markerf("[LOAD] type '%ls' -> tid=0x%X ids=%d\r\n",kCand[c],tid,num);
        if(num>0){ g_lcNum = num<LC_NMAX?num:LC_NMAX; for(int i=0;i<g_lcNum;i++){ g_lcIds[i][0]=tmp[i][0]; g_lcIds[i][1]=tmp[i][1]; }
            int k=0; for(const wchar_t* p=kCand[c]; *p && k<47; ++p) g_lcHeroType[k++]=(char)*p; g_lcHeroType[k]=0; break; }
    }
    if(g_lcNum<=0){ Marker("[LOAD] NO hero PrimaryAssetType matched any candidate — extend kCand (the log lists what was tried).\r\n"); g_lcFired=1; return; }
    Markerf("[LOAD] hero type '%s' has %d assets — firing AsyncLoadPrimaryAssets on the first %d...\r\n",g_lcHeroType,g_lcNum,g_lcNum);
    LcFireLoad();
    Markerf("[LOAD] AsyncLoadPrimaryAssets fired (handle=0x%llX). Async — worker re-censuses after settle.\r\n",(unsigned long long)g_lcHandle);
    g_lcFired=1;
}
// Read-only class census (off-thread): what hero / Loki-PC classes are resolvable now.
static void LcCensusClasses(const char* tag){
    uintptr_t hp =FindHeroPawnClass();               char n1[160]="-"; if(hp)ObjName(hp,n1,sizeof(n1));
    uintptr_t bh =FindObjNamePreSuf("BP_HERO_","_C"); char n2[160]="-"; if(bh)ObjName(bh,n2,sizeof(n2));
    uintptr_t lhc=FindInstClassSub("LokiHeroCharacter");
    uintptr_t lc =FindInstClassSub("LokiCharacter");
    uintptr_t devPc =FindObjNamePreSuf("BP_LokiPlayerController_Dev","_C");
    uintptr_t devPc2=FindObjExact("BP_LokiPlayerController_Dev_C");
    Markerf("[LOAD] --- class census (%s) ---\r\n",tag);
    Markerf("[LOAD]   heroPawnClass=0x%llX(%s) BP_HERO_*_C=0x%llX(%s)\r\n",(unsigned long long)hp,n1,(unsigned long long)bh,n2);
    Markerf("[LOAD]   LokiHeroCharacter inst=0x%llX  LokiCharacter inst=0x%llX\r\n",(unsigned long long)lhc,(unsigned long long)lc);
    Markerf("[LOAD]   BP_LokiPlayerController_Dev*_C=0x%llX  exact=0x%llX\r\n",(unsigned long long)devPc,(unsigned long long)devPc2);
}
// Phase-2 scoping (read-only): what LokiCharacter-ancestry actors are live (heroes vs pool templates), what the local
// networked PC is + whether it possesses a pawn, and whether a BP_Dev PC instance exists. Decides "possess existing"
// vs "spawn new" for Phase 2.
static void LcCensusDeep(){
    Marker("[DEEP] --- live LokiCharacter-ancestry instances (cap 24) ---\r\n");
    int n=0;
    ForEachObject([&](uintptr_t o)->bool{
        char on[160]; on[0]=0; ObjName(o,on,sizeof(on)); if(strncmp(on,"Default__",9)==0) return false;
        uintptr_t cls=ClassOf(o); if(!cls) return false;
        if(!SuperChainHas(cls,"LokiCharacter")) return false;
        char cn[128]="?"; ClassName(o,cn,sizeof(cn));
        Markerf("[DEEP]   obj=0x%llX cls=%s name=%s\r\n",(unsigned long long)o,cn,on);
        return (++n>=24);
    });
    Markerf("[DEEP]   (%d LokiCharacter-ancestry instances logged)\r\n",n);
    uintptr_t pc=FindInstExactClass("LokiPlayerController"); if(!pc) pc=FindInstClassSub("LokiPlayerController");
    if(pc){
        char cn[128]="?"; ClassName(pc,cn,sizeof(cn));
        uint32_t pawnOff=PropOffsetOnClass(ClassOf(pc),"Pawn");
        uintptr_t pawn=(pawnOff!=0xFFFFFFFF && SafeReadable((void*)(pc+pawnOff),8))?*(uintptr_t*)(pc+pawnOff):0;
        char pcn[128]="-",pon[160]="-"; if(LooksLikePtr(pawn)){ ClassName(pawn,pcn,sizeof(pcn)); ObjName(pawn,pon,sizeof(pon)); }
        Markerf("[DEEP] local PC=0x%llX cls=%s pawnOff=0x%X pawn=0x%llX (cls=%s name=%s)\r\n",
            (unsigned long long)pc,cn,pawnOff,(unsigned long long)pawn,pcn,pon);
    } else Marker("[DEEP] no LokiPlayerController instance\r\n");
    uintptr_t devInst=FindInstClassSub("BP_LokiPlayerController_Dev");
    char dcn[128]="-",don[160]="-"; if(devInst){ ClassName(devInst,dcn,sizeof(dcn)); ObjName(devInst,don,sizeof(don)); }
    Markerf("[DEEP] BP_Dev PC live instance=0x%llX (cls=%s name=%s)\r\n",(unsigned long long)devInst,dcn,don);
}

extern "C" void OnPI(void* /*ctx*/, void* frame, void* /*res*/){
    if(g_done || g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;
    if(!LooksLikePtr((uintptr_t)frame)) return;
    g_inHook=1;
    memcpy(g_template, frame, sizeof(g_template));   // capture a live FFrame template (primitive prerequisite)
    long h=InterlockedIncrement(&g_hitsGT);
    if(kMode==MODE_SPECTATOR_CAM){ if(g_moveArmed && !g_moveDone){ DoStepMove(); g_inHook=0; return; } if(h==1) Marker("[HOOK] fired (spectator-cam) — transient overlay-hide\r\n"); DoSpectatorCam(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_DEBUGCAM){ if(h==1) Marker("[HOOK] fired (debug-cam) — hiding overlay + enabling debug camera\r\n"); DoDebugCam(); g_inHook=0; return; }
    if(kMode==MODE_FREECAM){ if(h==1) Marker("[HOOK] fired (free-cam) — spawn camera + retarget view + puppet\r\n"); DoFreeCam(); g_inHook=0; return; }
    if(kMode==MODE_LOAD_CENSUS){ if(!g_lcFired){ if(h==1) Marker("[HOOK] fired (load-census) — firing hero asset load on the game thread.\r\n"); DoLoadCensus(); } g_done=1; g_inHook=0; return; }
    if(kMode==MODE_CAMFRAME){ DoCamFrame(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_COSMENUM){ DoCosmEnum(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_SETCOSMETIC){ DoSetCosmetic(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_BPDEPLOY){ DoBPDeploy(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_CONTEXT){ DoContext(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_DEPLOYEVT){ DoDeployEvt(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_BPTEST){ DoBPTest(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_BPTEST2){ DoBPTest2(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_BPTEST3){ DoBPTest3(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_BPCALL){ DoBPCall(); g_done=1; g_inHook=0; return; }
    if(kMode==MODE_DEVSWAP){ DoDevSwap(); g_inHook=0; return; }
    if(kMode==MODE_MOVETEST){ DoMoveTest(); g_inHook=0; return; }
    Markerf("[HOOK] fired on game thread (hitsGT=%ld) — primitive template captured.\r\n",h);
    if(kMode==MODE_POSSESS_DP) DoPossessDP();
    else if(kMode==MODE_SPAWN_HERO) DoSpawnHero();
    else if(kMode==MODE_SPAWN_P2) DoSpawnP2();
    else if(kMode==MODE_SWAP) DoSwap();
    else if(kMode==MODE_POSSESS) DoPossess();
    else if(kMode==MODE_DEPLOY) DoDeploy();
    else if(kMode==MODE_UNHIDE) DoUnhide();
    else if(kMode==MODE_NPOSSESS) DoNPossess();
    else if(kMode==MODE_CRESTART) DoCRestart();
    else if(kMode==MODE_LIVINGSTATE) DoLivingState();
    else if(kMode==MODE_COSMETICS) DoCosmetics();
    else Census();
    g_done=1; g_inHook=0;
}

static DWORD WINAPI Worker(LPVOID){
    // fresh marker
    HANDLE h=CreateFileA(kMarkerPath,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr); if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);
    HMODULE hExe=GetModuleHandleA("SUPERVIVE-Win64-Shipping.exe"); if(!hExe){Marker("[0] FAIL module\r\n");return 1;}
    g_modBase=(uintptr_t)hExe; AddVectoredExceptionHandler(1,CrashVEH);
    Markerf("[0] ds_hybrid attached. base=0x%llX mode=%d\r\n",(unsigned long long)g_modBase,kMode);
    { HANDLE rt=CreateThread(nullptr,0,RawInputThread,nullptr,0,nullptr); if(rt)CloseHandle(rt); }   // S78c: raw mouse capture
    g_gameTid=WaitTid(120000); if(!g_gameTid){Marker("[1] FAIL gameTid\r\n");return 2;}
    Markerf("[1] gameTid=%lu\r\n",g_gameTid);
    if(kMode==MODE_SWAP_CENSUS){ DoSwapCensus(); Marker("[3b] swap-census done (read-only, no hook held).\r\n"); return 0; }
    if(kMode==MODE_CAMFIX){ DoCamFix(); Marker("[3b] camfix done (off-thread, no hook held).\r\n"); return 0; }
    if(kMode==MODE_DEPLOYRECON){ DoDeployRecon(); Marker("[3b] deploy-recon done (read-only, no hook held).\r\n"); return 0; }
    if(kMode==MODE_STATERECON){ DoStateRecon(); Marker("[3b] state-recon done (read-only, no hook held).\r\n"); return 0; }
    if(kMode==MODE_MESHDIAG){ DoMeshDiag(); Marker("[3b] mesh-diag done (read-only, no hook held).\r\n"); return 0; }
    if(kMode==MODE_MESHMGRRECON){ DoMeshMgrRecon(); Marker("[3b] mesh-mgr-recon done (read-only, no hook held).\r\n"); return 0; }
    if(kMode==MODE_VTDUMP){ DoVtDump(); Marker("[3b] vtdump done (read-only, no hook held).\r\n"); return 0; }
    if(kMode==MODE_UFUNCDUMP){ DoUFuncDump(); Marker("[3b] ufuncdump done (read-only, no hook held).\r\n"); return 0; }
    // S78 #4: wait for the UMG widgets (incl. the WBP_UI_MatchTransition overlay) to spawn before censusing — a
    // too-early census gets few widgets and misses the overlay (hid 0/3). Poll the count until high/stable
    // (min 6s floor, cap 30s) instead of the old fixed 12s sleep, so inject timing is self-correcting.
    if(kMode==MODE_SPECTATOR_CAM||kMode==MODE_DEBUGCAM||kMode==MODE_FREECAM){ Marker("[1b] polling until UMG widgets have spawned...\r\n"); WaitForWidgets(1500,6000,30000); }
    // Resolve targets OFF the game thread (read-only object walk) so the hook does minimal game-thread work.
    if(kMode==MODE_POSSESS_DP){ if(!ResolvePossessDP()){ Marker("[1] possess resolve failed — aborting\r\n"); return 7; } }
    if(kMode==MODE_SPAWN_HERO){ if(!ResolveSpawnHero()){ Marker("[1] spawn-hero resolve failed — aborting\r\n"); return 8; } }
    if(kMode==MODE_SPAWN_P2){ if(!ResolveSpawnP2()){ Marker("[1] spawn-P2 resolve failed — aborting\r\n"); return 10; } }
    if(kMode==MODE_SWAP){ if(!ResolveSwap()){ Marker("[1] swap resolve failed — aborting\r\n"); return 11; } }
    if(kMode==MODE_POSSESS){ if(!ResolvePossess()){ Marker("[1] possess resolve failed — aborting\r\n"); return 12; } }
    if(kMode==MODE_DEPLOY){ if(!ResolveDeploy()){ Marker("[1] deploy resolve failed — aborting\r\n"); return 13; } }
    if(kMode==MODE_UNHIDE){ if(!ResolveUnhide()){ Marker("[1] unhide resolve failed — aborting\r\n"); return 14; } }
    if(kMode==MODE_NPOSSESS){ if(!ResolveNPossess()){ Marker("[1] npossess resolve failed — aborting\r\n"); return 15; } }
    if(kMode==MODE_CRESTART){ if(!ResolveCRestart()){ Marker("[1] crestart resolve failed — aborting\r\n"); return 16; } }
    if(kMode==MODE_CAMFRAME){ if(!ResolveCamFrame()){ Marker("[1] camframe resolve failed — aborting\r\n"); return 17; } }
    if(kMode==MODE_LIVINGSTATE){ if(!ResolveLivingState()){ Marker("[1] livingstate resolve failed — aborting\r\n"); return 18; } }
    if(kMode==MODE_COSMETICS){ if(!ResolveCosmetics()){ Marker("[1] cosmetics resolve failed — aborting\r\n"); return 19; } }
    if(kMode==MODE_COSMENUM){ if(!ResolveLoadCensus()){ Marker("[1] cosmenum resolve failed — aborting\r\n"); return 20; } }
    if(kMode==MODE_SETCOSMETIC){ if(!ResolveLoadCensus()||!ResolveCosmetics()){ Marker("[1] setcosmetic resolve failed — aborting\r\n"); return 21; } }
    if(kMode==MODE_BPDEPLOY){ if(!ResolveBPDeploy()){ Marker("[1] bpdeploy resolve failed — aborting\r\n"); return 22; } }
    if(kMode==MODE_CONTEXT){ if(!ResolveContext()){ Marker("[1] context resolve failed — aborting\r\n"); return 23; } }
    if(kMode==MODE_DEPLOYEVT){ if(!ResolveDeployEvt()){ Marker("[1] deployevt resolve failed — aborting\r\n"); return 24; } }
    if(kMode==MODE_SPECTATOR_CAM){ ResolveSpectatorCam(); ProbeCamera(); ProbeViewYaw(); ProbeSensitivity(); if(kTakeoverCam) ResolveTakeover(); }
    if(kMode==MODE_DEBUGCAM){ ResolveSpectatorCam(); ResolveDebugCam(); }   // spectator resolve populates the overlay-hide widgets
    if(kMode==MODE_FREECAM){ ResolveFreeCam(); }
    if(kMode==MODE_LOAD_CENSUS){ if(!ResolveLoadCensus()){ Marker("[1] load-census resolve failed — aborting\r\n"); return 9; } LcCensusClasses("PRE-load"); }
    g_pi=(uint8_t*)(g_modBase+kPiRva);
    memcpy(g_stolen,g_pi,5); g_stub=BuildHook((uintptr_t)g_pi,g_stolen); if(!g_stub||!g_tramp){Marker("[2] FAIL BuildHook\r\n");return 3;}
    if(kMode==MODE_SPECTATOR_CAM){
        // S78c: TRANSIENT overlay-hide (no standing .text hook — the anti-tamper reliably catches a standing hook,
        // even at 8s; it crashed 3x). Cycle install → one DoSpectatorCam (hides the loading widgets + captures the
        // FFrame template for the primitive) → uninstall, for ~kSpectatorHookMs. Same µs-exposure dodge as movement.
        Marker("[2] transient overlay-hide starting...\r\n");
        DWORD ohT0=GetTickCount();
        while(GetTickCount()-ohT0 < kSpectatorHookMs){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+50; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] overlay-hide done (transient, hitsGT=%ld) — no standing .text hook was ever held.\r\n",(long)g_hitsGT);
    } else if(kMode==MODE_LOAD_CENSUS){
        // S77 dodge: fire the load via a TRANSIENT-per-fire hook (never a standing .text hook the anti-tamper
        // catches). Install -> OnPI fires the load once -> uninstall; then wait off-thread for the async load and
        // re-census. The census walks are read-only RPM (no hook needed).
        Marker("[2] load-census: transient hook to fire the hero asset load...\r\n");
        DWORD lcT0=GetTickCount();
        while(!g_done && GetTickCount()-lcT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+50; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] load fired=%ld (hitsGT=%ld). Waiting 8s for the async load to settle...\r\n",(long)g_lcFired,(long)g_hitsGT);
        Sleep(8000);
        LcCensusClasses("POST-load");
        LcCensusDeep();
        Marker("[3b] load-census done.\r\n");
        return 0;
    } else if(kMode==MODE_SPAWN_P2){
        // S77 dodge: fire the spawn via a TRANSIENT-per-fire hook (never a standing .text hook the anti-tamper
        // catches). Install -> OnPI runs DoSpawnP2 ONCE on the game thread -> uninstall. One-shot; g_done gates it.
        Marker("[2] spawn-P2: transient hook to fire the spawn on the game thread...\r\n");
        DWORD spT0=GetTickCount();
        while(!g_done && GetTickCount()-spT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+150; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] spawn-P2 fired (hitsGT=%ld done=%ld) — hook never held standing.\r\n",(long)g_hitsGT,(long)g_done);
        return 0;
    } else if(kMode==MODE_SWAP){
        // Transient-per-fire hook (anti-tamper dodge): OnPI spawns the BP_Dev PC + applies the swap ONCE on the game
        // thread, then uninstall. Then monitor off-thread whether the game keeps the swap or reverts/crashes.
        Marker("[2] swap: transient hook to spawn+swap on the game thread...\r\n");
        DWORD swT0=GetTickCount();
        while(!g_done && GetTickCount()-swT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+200; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] swap fired (done=%ld devPc=0x%llX) — hook never held standing. Monitoring...\r\n",(long)g_done,(unsigned long long)g_swDevPc);
        if(g_swDevPc){
            for(int i=0;i<20;i++){ Sleep(500);
                uintptr_t cur = SafeReadable((void*)(g_swL+g_swLpcOff),8)?*(uintptr_t*)(g_swL+g_swLpcOff):0;
                char ccn[96]="-"; if(LooksLikePtr(cur))ClassName(cur,ccn,sizeof(ccn));
                Markerf("[SW] t+%.1fs L->PC=0x%llX(%s) %s\r\n",(i+1)*0.5,(unsigned long long)cur,ccn,
                        cur==g_swDevPc?"<< STILL OURS (swap holding)":(cur==g_swOldPc?"(REVERTED to native PC)":"(changed to other)"));
                if(cur==g_swOldPc){ Marker("[SW] REVERTED — the game reasserted the native PC. Phase-3 gate: it won't relinquish local control.\r\n"); break; }
            }
        }
        Marker("[3b] swap-monitor done.\r\n");
        return 0;
    } else if(kMode==MODE_POSSESS){
        // Transient-per-fire hook (anti-tamper dodge): OnPI spawns the hero + possesses + drives drop-in ONCE, then
        // uninstall. Then monitor PC->Pawn off-thread for stability / whether the hero possession sticks.
        Marker("[2] possess: transient hook to spawn+possess+drop-in on the game thread...\r\n");
        DWORD poT0=GetTickCount();
        while(!g_done && GetTickCount()-poT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+300; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] possess fired (done=%ld hero=0x%llX) — hook never held standing. Monitoring...\r\n",(long)g_done,(unsigned long long)g_poHero);
        if(g_poHero && g_poPc){
            for(int i=0;i<20;i++){ Sleep(500);
                uintptr_t pw = SafeReadable((void*)(g_poPc+g_poPawnOff),8)?*(uintptr_t*)(g_poPc+g_poPawnOff):0;
                char pn[96]="-"; if(LooksLikePtr(pw))ClassName(pw,pn,sizeof(pn));
                Markerf("[PO] t+%.1fs PC->Pawn=0x%llX(%s) %s\r\n",(i+1)*0.5,(unsigned long long)pw,pn,
                        pw==g_poHero?"<< HERO (possession holding)":(pw?"(other pawn)":"(null)"));
            }
        }
        Marker("[3b] possess-monitor done.\r\n");
        return 0;
    } else if(kMode==MODE_DEPLOY){
        Marker("[2] deploy: transient hook to un-hide + bind input on the game thread...\r\n");
        DWORD dpT0=GetTickCount();
        while(!g_done && GetTickCount()-dpT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+200; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] deploy fired (done=%ld). alive-monitoring 5s...\r\n",(long)g_done);
        for(int i=0;i<10;i++) Sleep(500);
        Marker("[3b] deploy done.\r\n");
        return 0;
    } else if(kMode==MODE_UNHIDE){
        Marker("[2] unhide: transient hook to reveal hero + set view target...\r\n");
        DWORD uhT0=GetTickCount();
        while(!g_done && GetTickCount()-uhT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+200; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] unhide fired (done=%ld). Monitoring view target 8s...\r\n",(long)g_done);
        for(int i=0;i<16;i++){ Sleep(500);
            if(LooksLikePtr(g_uhCam) && SafeReadable((void*)(g_uhCam+0x420),8)){ uintptr_t vt=*(uintptr_t*)(g_uhCam+0x420); char vcn[64]="-"; if(LooksLikePtr(vt))ClassName(vt,vcn,sizeof(vcn));
                Markerf("[UH] t+%.1fs camViewTarget@+0x420=0x%llX(%s) %s\r\n",(i+1)*0.5,(unsigned long long)vt,vcn, vt==g_uhHero?"<< HERO":"(other)"); } }
        Marker("[3b] unhide done.\r\n");
        return 0;
    } else if(kMode==MODE_NPOSSESS){
        Marker("[2] npossess: transient hook to restore+possess+reveal on the game thread...\r\n");
        DWORD npT0=GetTickCount();
        while(!g_done && GetTickCount()-npT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] npossess fired (done=%ld). Monitoring pawn + view target 12s...\r\n",(long)g_done);
        for(int i=0;i<24;i++){ Sleep(500);
            uintptr_t pw = SafeReadable((void*)(g_npNative+g_npPawnOff),8)?*(uintptr_t*)(g_npNative+g_npPawnOff):0; char pn[80]="-"; if(LooksLikePtr(pw))ClassName(pw,pn,sizeof(pn));
            uintptr_t vt = (LooksLikePtr(g_npCam)&&SafeReadable((void*)(g_npCam+0x420),8))?*(uintptr_t*)(g_npCam+0x420):0; char vn[80]="-"; if(LooksLikePtr(vt))ClassName(vt,vn,sizeof(vn));
            Markerf("[NP] t+%.1fs PC->Pawn=0x%llX(%s)%s camTgt=0x%llX(%s)%s\r\n",(i+1)*0.5,
                    (unsigned long long)pw,pn,(pw==g_npHero?" HERO":""),(unsigned long long)vt,vn,(vt==g_npHero?" <<HERO":"")); }
        Marker("[3b] npossess done.\r\n");
        return 0;
    } else if(kMode==MODE_CRESTART){
        Marker("[2] crestart: transient hook to run client-side possession setup...\r\n");
        DWORD crT0=GetTickCount();
        while(!g_done && GetTickCount()-crT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] crestart fired (done=%ld). Monitoring pawn + view target 10s...\r\n",(long)g_done);
        for(int i=0;i<20;i++){ Sleep(500);
            uintptr_t pw = SafeReadable((void*)(g_crPc+0x3F8),8)?*(uintptr_t*)(g_crPc+0x3F8):0; char pn[64]="-"; if(LooksLikePtr(pw))ClassName(pw,pn,sizeof(pn));
            uintptr_t vt = (LooksLikePtr(g_crCam)&&SafeReadable((void*)(g_crCam+0x420),8))?*(uintptr_t*)(g_crCam+0x420):0; char vn[64]="-"; if(LooksLikePtr(vt))ClassName(vt,vn,sizeof(vn));
            Markerf("[CR] t+%.1fs PC->Pawn=0x%llX(%s)%s camTgt=0x%llX(%s)%s\r\n",(i+1)*0.5,
                    (unsigned long long)pw,pn,(pw==g_crHero?" HERO":""),(unsigned long long)vt,vn,(vt==g_crHero?" <<HERO":"")); }
        Marker("[3b] crestart done.\r\n");
        return 0;
    } else if(kMode==MODE_LIVINGSTATE){
        Marker("[2] livingstate: transient hook to set Alive + fire visibility handlers...\r\n");
        DWORD lsT0=GetTickCount();
        while(!g_done && GetTickCount()-lsT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] livingstate fired (done=%ld). Monitoring raw LivingState@0x1090 8s...\r\n",(long)g_done);
        for(int i=0;i<16;i++){ Sleep(500);
            uint8_t v = (LooksLikePtr(g_lsHero)&&SafeReadable((void*)(g_lsHero+LS_LIVINGSTATE),1))?*(uint8_t*)(g_lsHero+LS_LIVINGSTATE):0xFF;
            uint8_t pd= (LooksLikePtr(g_lsHero)&&SafeReadable((void*)(g_lsHero+LS_PREDROP),1))?*(uint8_t*)(g_lsHero+LS_PREDROP):0xFF;
            Markerf("[LS] t+%.1fs LivingState=%d predrop=%d %s\r\n",(i+1)*0.5,v,pd,(v==(uint8_t)KALIVEVAL?"(held Alive)":"(reset)")); }
        Marker("[3b] livingstate done.\r\n");
        return 0;
    } else if(kMode==MODE_COSMETICS){
        Marker("[2] cosmetics: transient hook to call RefreshCosmetics...\r\n");
        DWORD cmT0=GetTickCount();
        while(!g_done && GetTickCount()-cmT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+300; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3] cosmetics fired (done=%ld).\r\n",(long)g_done);
        for(int i=0;i<6;i++) Sleep(500);
        Marker("[3b] cosmetics done.\r\n");
        return 0;
    } else if(kMode==MODE_COSMENUM){
        Marker("[2] cosmenum: transient hook to query cosmetics types...\r\n");
        DWORD ceT0=GetTickCount();
        while(!g_done && GetTickCount()-ceT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+400; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3b] cosmenum done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_SETCOSMETIC){
        // Re-fire over ~12s so RefreshCosmetics rebuilds once the async skin asset lands.
        Marker("[2] setcosmetic: assigning skin + re-refreshing over ~12s...\r\n");
        DWORD scT0=GetTickCount();
        while(GetTickCount()-scT0 < 12000){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+300; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(600);
        }
        Markerf("[3b] setcosmetic done (%ld reps).\r\n",(long)g_scReps);
        return 0;
    } else if(kMode==MODE_BPDEPLOY){
        // Re-fire over ~14s: rep 1 runs the BP setup (creates the controller); later reps RefreshCosmetics as the
        // async skin lands + the controller builds the mesh.
        Marker("[2] bpdeploy: BP setup via ProcessEvent + re-refresh over ~14s...\r\n");
        DWORD bdT0=GetTickCount();
        while(GetTickCount()-bdT0 < 14000){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+400; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(700);
        }
        Markerf("[3b] bpdeploy done (%ld reps).\r\n",(long)g_bdReps);
        return 0;
    } else if(kMode==MODE_CONTEXT){
        Marker("[2] context: set PlayerState + retry BP setup + re-refresh over ~14s...\r\n");
        DWORD cxT0=GetTickCount();
        while(GetTickCount()-cxT0 < 14000){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+400; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(700);
        }
        Markerf("[3b] context done (%ld reps).\r\n",(long)g_cxReps);
        return 0;
    } else if(kMode==MODE_DEPLOYEVT){
        Marker("[2] deployevt: deploy orchestrator events + re-refresh over ~14s...\r\n");
        DWORD deT0=GetTickCount();
        while(GetTickCount()-deT0 < 14000){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+400; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(700);
        }
        Markerf("[3b] deployevt done (%ld reps).\r\n",(long)g_deReps);
        return 0;
    } else if(kMode==MODE_BPTEST){
        Marker("[2] bptest: transient hook to test a BP getter via ProcessEvent...\r\n");
        DWORD btT0=GetTickCount();
        while(!g_done && GetTickCount()-btT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3b] bptest done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_BPTEST2){
        Marker("[2] bptest2: transient hook; OnPI raw-unhooks then tests ProcessEvent...\r\n");
        DWORD b2T0=GetTickCount();
        while(!g_done && GetTickCount()-b2T0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3b] bptest2 done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_BPTEST3){
        Marker("[2] bptest3: transient hook; test ProcessEvent on a native member...\r\n");
        DWORD b3T0=GetTickCount();
        while(!g_done && GetTickCount()-b3T0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3b] bptest3 done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_MOVETEST){
        // Movement input must be fed EVERY frame (AddMovementInput is consumed per-tick), so hook in tight bursts.
        Marker("[2] movetest: driving native MoveForward/MoveRight ~12s...\r\n");
        DWORD t0=GetTickCount();
        while(!g_done && GetTickCount()-t0 < 20000){
            g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+120; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(60);
        }
        Markerf("[3b] movetest done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_DEVSWAP){
        Marker("[2] devswap: swap to the BP_Dev PC + ClientRestart there; monitoring ~10s...\r\n");
        DWORD t0=GetTickCount();
        while(!g_done && GetTickCount()-t0 < 22000){
            g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+140; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(400);
        }
        Markerf("[3b] devswap done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_BPCALL){
        // Transient hook only to reach the game thread + capture the FFrame template; DoBPCall RawUnhook()s itself
        // before running any BP bytecode, so no .text hook is held across the deploy calls (anti-tamper dodge).
        Marker("[2] bpcall: transient hook; validate the BP invoker then run the deploy setup...\r\n");
        DWORD bcT0=GetTickCount();
        while(!g_done && GetTickCount()-bcT0 < 30000){
            if(InstallHookFast()){ DWORD md=GetTickCount()+250; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(25);
        }
        Markerf("[3b] bpcall done (done=%ld).\r\n",(long)g_done);
        return 0;
    } else if(kMode==MODE_CAMFRAME){
        // Re-apply the camera-component offset repeatedly (transient hook per apply) to hold it vs any per-frame reset.
        Marker("[2] camframe: applying camera offset repeatedly (~8s)...\r\n");
        DWORD frT0=GetTickCount();
        while(GetTickCount()-frT0 < 8000){
            g_done=0; g_inHook=0;
            if(InstallHookFast()){ DWORD md=GetTickCount()+120; while(!g_done && GetTickCount()<md) Sleep(0); UninstallHookFast(); }
            Sleep(180);
        }
        Markerf("[3b] camframe done (%ld applications).\r\n",(long)g_cfrReps);
        return 0;
    } else {
        if(!InstallHook()){Marker("[2] FAIL InstallHook\r\n");return 4;}
        Marker("[2] hook installed — waiting for a game-thread ProcessInternal...\r\n");
        int waitIters=((kMode==MODE_DEBUGCAM||kMode==MODE_FREECAM)?18000:600);
        for(int i=0;i<waitIters && !g_done;i++) Sleep(20);
        UninstallHook();
        Markerf("[3] hook UNINSTALLED (hitsGT=%ld).\r\n",(long)g_hitsGT);
    }
    // S77 phase-3: CONTINUOUS movement via TRANSIENT-PER-STEP (no standing .text hook — the proven dodge). Poll
    // WASD OFF-THREAD; per step, install the hook -> OnPI does ONE K2_SetActorLocation to the updated pos ->
    // uninstall. The .text patch exists only ~microseconds per step, so the integrity check almost never sees it.
    if(kMode==MODE_SPECTATOR_CAM){
        g_hwnd=FindWindowA(nullptr,"SUPERVIVE");
        // S78 #2: try the DURABLE per-frame VTABLE hook first (removes the ProcessInternal dependency that stalled
        // movement). Sweep the CameraManager's vtable for the per-frame slot, then swap in our stub (heap-only, no
        // .text). If it doesn't take, fall back to the transient-per-step loop.
        bool vtActive=false; uintptr_t vtCam=FindInstClassSub("CameraManager");
        if(IsHeapObj(vtCam)){ int slot=FindPerFrameSlot(vtCam); if(slot>=0) vtActive=InstallVtableMove(vtCam,slot); }
        Markerf("[move] movement loop LIVE via %s (WASD fly; %s; Space/Ctrl up/down; Shift=boost)\r\n",
                vtActive?"VTABLE per-frame hook":"transient-per-step",
                g_viewYawEnabled?"MOUSE steers (arrows nudge)":"arrows steer");
        DWORD t0=GetTickCount(); DWORD lastHb=0, lastDisc=0; long steps=0; int anyKey=0; long instFail=0;
        while(GetTickCount()-t0 < 3600000){   // ~60 min (was 15) so the fly-cam doesn't expire mid-session
            // No focus gate: GetAsyncKeyState reads global hardware key state (works regardless of foreground).
            // Read keys FIRST + unconditionally (so keysSeen reflects detection even before the world-loc seed).
            bool wDn=(GetAsyncKeyState('W')&0x8000)!=0, sDn=(GetAsyncKeyState('S')&0x8000)!=0,
                 aDn=(GetAsyncKeyState('A')&0x8000)!=0, dDn=(GetAsyncKeyState('D')&0x8000)!=0,
                 upDn=(GetAsyncKeyState(VK_SPACE)&0x8000)!=0, dnDn=(GetAsyncKeyState(VK_CONTROL)&0x8000)!=0;
            bool anyDn = wDn||sDn||aDn||dDn||upDn||dnDn; if(anyDn) anyKey++;
            ApplySensReduction();   // S78b: keep mouse-look sensitivity clamped down (re-write each iteration)
            if(GetAsyncKeyState(VK_LEFT)&0x8000)  g_manualYawOff-=3.0;   // arrows nudge on top of the mouse yaw
            if(GetAsyncKeyState(VK_RIGHT)&0x8000) g_manualYawOff+=3.0;
            double vy; double heading = kTakeoverCam ? (g_camYaw + g_manualYawOff)   // take-over: my own controlled yaw
                                                      : ((ReadViewYaw(&vy) ? vy : 0.0) + g_manualYawOff);   // native view yaw
            g_spYaw2 = heading;
            double yr=heading*3.14159265358979/180.0, c=cos(yr), s=sin(yr), dx=0,dy=0,dz=0;
            if(wDn){ dx+=c; dy+=s; }  if(sDn){ dx-=c; dy-=s; }
            if(dDn){ dx-=s; dy+=c; }  if(aDn){ dx+=s; dy-=c; }
            if(upDn) dz+=1; if(dnDn) dz-=1;
            double sp=kMoveSpeed, spV=kMoveSpeedV;
            if(GetAsyncKeyState(VK_SHIFT)&0x8000){ sp*=kBoostMul; spV*=kBoostMul; }   // S78 #3: Shift boost
            // diff auto-lock (quat/FRotator) only if the getter didn't resolve (the getter is the yaw ground truth)
            if(!g_rotThunk && !g_viewYawEnabled && GetTickCount()-lastDisc>=1000){ DiscoverYaw(); lastDisc=GetTickCount(); }
            bool canMove = !vtActive || g_spSeededVt;   // vtable path: wait for the world-loc seed before flying
            if((dx||dy||dz) && canMove){
                g_spX+=dx*sp; g_spY+=dy*sp; g_spZ+=dz*spV;
                if(g_spZ>kZMax) g_spZ=kZMax; if(g_spZ<kZMin) g_spZ=kZMin;
                if(vtActive){ g_moveDirty=1; Sleep(6); }   // per-frame vtable hook applies the pending pos
                else {
                    g_moveDone=0; g_moveArmed=1; g_done=0; g_inHook=0;
                    bool inst=false; for(int r=0;r<4 && !inst;r++){ if(InstallHookFast()){ inst=true; DWORD md=GetTickCount()+60; while(!g_moveDone && GetTickCount()<md) Sleep(0); UninstallHookFast(); steps++; } }
                    if(!inst) instFail++;
                    Sleep(6);
                }
            } else Sleep(anyDn?6:20);
            if(GetTickCount()-lastHb>=5000){
                double vy2=0; bool haveVy=ReadViewYaw(&vy2);
                Markerf("[move] alive via=%s fired=%ld vtTicks=%ld seeded=%ld keysSeen=%d W=%d pos=(%.0f,%.0f,%.0f) yaw=%.0f viewYaw=%s%.0f foc=%d\r\n",
                    vtActive?"vt":"tr",(long)g_fired,(long)g_vtTicks,(long)g_spSeededVt,anyKey,wDn?1:0,g_spX,g_spY,g_spZ,g_spYaw2,haveVy?"":"(unlocked)",vy2,IsGameFocused()?1:0);
                // S78c stage 1: raw mouse capture + POV-rotation discovery. Log accumulated mouse delta (then reset)
                // + the CameraManager CameraCachePrivate doubles (0x14A8..0x14E0) so a live rotate reveals which
                // offset is the POV yaw (it swings). The POV rotation is what we'll override with a slow value.
                long mdx=InterlockedExchange(&g_mouseDX,0), mdy=InterlockedExchange(&g_mouseDY,0), mev=InterlockedExchange(&g_mouseEvents,0);
                Markerf("[raw] events=%ld dx=%ld dy=%ld\r\n",mev,mdx,mdy);
                if(IsHeapObj(g_camMgr) && SafeReadable((void*)(g_camMgr+0x420),8)){ uintptr_t vt=*(uintptr_t*)(g_camMgr+0x420);
                    char vcn[64]="?"; if(IsHeapObj(vt))ClassName(vt,vcn,sizeof(vcn));
                    Markerf("[TO] viewTarget@cam+0x420=0x%llX (%s) myCam=0x%llX %s\r\n",(unsigned long long)vt,vcn,(unsigned long long)g_myCam,(vt==g_myCam)?"<< MINE":"(reverted)"); }
                anyKey=0; lastHb=GetTickCount();
            }
        }
        RestoreVtable();   // put the CameraManager's original vtable pointer back before the worker exits
    }
    Markerf("[3b] done (hitsGT=%ld done=%ld).\r\n",(long)g_hitsGT,(long)g_done);
    return 0;
}
BOOL APIENTRY DllMain(HMODULE h,DWORD r,LPVOID){if(r==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(h);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;}
