================================================================================
S85 — THE "Invalid replicated field 32" DESYNC, DIFFED PROPERLY (client vs stub)
================================================================================
Date: 2026-07-21.  Branch: dedicated-server-stub.  Live read-only RPM capture off the
MENU client (no DS session needed — the whole chain to LokiCharacter loads at the menu).
Predecessor: docs/session-84-hero-mirror-scope.txt (§9-§11 left field 32 undiagnosed).
Memory: supervive-dedicated-server-status.

--------------------------------------------------------------------------------
0. WHAT THIS SESSION DID
--------------------------------------------------------------------------------
S84 possess-a-Loki-character succeeds server-side ("spawned + possessed ALokiMinionCharacter"
+ "Join succeeded") then the STUB closes the channel ~360ms later on:
    LogRep: Error: ReceivedBunch: Invalid replicated field 32 in LokiMinionCharacter
Two S84 fixes failed because, in the author's own words, "the diff was never a diff" — only the
STUB's cumulative FClassNetCache index space was ever computed; the CLIENT's was ASSUMED identical.
This session built the missing half and diffed them.

NEW TOOL: tools/re/netcache_chain.py — walks the CLIENT's full inheritance chain
(Object->Actor->LokiActor->Pawn->Character->LokiCharacter[->LokiMinionCharacter]) and reproduces
the stub's DumpClassNetCacheLayout (Loki.cpp:1080) EXACTLY: recurse to super first, then one field
index per OWN CPF_Net property (ArrayDim collapsed), then one per OWN name-sorted net function.
It auto-diffs each tier vs the stub's per-tier (reps,funcs) and names the FIRST divergent tier.
Run: netcache_chain.py <PID> <BASE-hex> LokiCharacter   (this session: PID 40736 base 0x7FF6AF000000)

--------------------------------------------------------------------------------
1. THE ANSWER (cross-verified, not assumed)
--------------------------------------------------------------------------------
CLIENT field [32] = FUNC ServerMovePacked (Character tier)
STUB   field [32] = PROP CustomAnimationState (LokiCharacter tier)   <- the documented error

MECHANISM: the autonomous-proxy client fires ServerMovePacked (its core movement Server RPC) the
instant it possesses the pawn. It addresses that RPC by ITS FClassNetCache index = 32. The stub
receives "field 32", looks it up in ITS cache = CustomAnimationState (a COND_SimulatedOnly property,
not a receivable RPC) => "Invalid replicated field 32" => Replicator.ReceivedBunch fails => close.
That is a 100% match to the live symptom firing right after Join.

PER-TIER DIFF (client measured vs stub S84):
    tier            client(reps,funcs)   stub(reps,funcs)   verdict
    Object          (0,0)                (0,0)              match
    Actor           (11,0)               (11,0)             match   (incl. injected ServerState @10)
    LokiActor       (0,0)                (0,0)              match
    Pawn            (3,0)                (3,0)              match
    Character       (12,7)               (10,7)             *** DIVERGE (+2 reps) ***   <- causes field 32
    LokiCharacter   (13,14)              (2,14)             *** DIVERGE (+11 reps) ***  <- next desync

FIRST DIVERGENT TIER = Character. Its own fields start at client base index 14; the +2 shifts every
field at/after 14 by +2 on the wire, so client 32 (ServerMovePacked, Character's name-sorted-last
net func) lands where the stub expects LokiCharacter's 2nd property. Cumulative bases:
    stub  : Actor 0..10 | Pawn 11..13 | Character reps 14..23 funcs 24..30 | LokiCharacter base 31
    client: Actor 0..10 | Pawn 11..13 | Character reps 14..25 funcs 26..32 | LokiCharacter base 33

--------------------------------------------------------------------------------
2. TWO STALE "FACTS" CORRECTED (both were measurement bugs — the project's 9th/10th)
--------------------------------------------------------------------------------
(A) LokiCharacter is NOT "2 replicated props" (S73/S84). It is 13. Proof: the 13 CPF_Net props sit
    at ChildProperties list positions [24,29,49,60,66,110,120,121,122,123,125,148,158] of 182 total.
    rep_expand_class.py caps its walk at i<40, so it saw only the 2 before position 40 (OutOfBounds@24,
    CustomAnimationState@29) and missed the other 11. netcache_chain.py (i<512) sees all 13.
    (scratchpad probe: lokichar_props.py.)
(B) The Character tier is NOT (10,7) on the client. It is (12,7). This one is a GENUINE structural
    difference, not a cap: SUPERVIVE's custom-engine ACharacter DROPPED stock RepRootMotion and ADDED
    ReplicatedCharacterMovement + ReplicatedGravityScale, netting 12. The stub inherits stock UE5.4
    ACharacter (minus a RepRootMotion strip) = 10.

--------------------------------------------------------------------------------
3. GROUND TRUTH FOR THE FIX (full prop lists + types; live capture, struct_types.py)
--------------------------------------------------------------------------------
CLIENT Character — 12 own CPF_Net props, in field order:
   0 ReplicatedBasedMovement               Struct BasedMovementInfo          (0x1005 member-wise) [engine FBasedMovementInfo]
   1 AnimRootMotionTranslationScale        Float
   2 ReplicatedServerLastTransformUpdateTimeStamp Float
   3 ReplayLastTransformUpdateTimeStamp    Float
   4 ReplicatedMovementMode                Byte
   5 ReplicatedGravityDirection            Struct Vector_NetQuantizeNormal   (NetSerialize, 1 cmd) [engine]
   6 bIsCrouched                           Bool
   7 bProxyIsJumpForceApplied              Bool
   8 JumpMaxHoldTime                       Float
   9 JumpMaxCount                          Int
  10 ReplicatedCharacterMovement           Struct RepCharacterMovement       (NetSerialize, 1 cmd)  <- verify engine vs Loki
  11 ReplicatedGravityScale                Float
CLIENT Character — 7 own net funcs (name-sorted): ClientAdjustPosition, ClientCheatFly, ClientCheatGhost,
  ClientCheatWalk, ClientMoveResponsePacked, RootMotionDebugClientPrintOnScreen, ServerMovePacked.
  (ServerMovePacked sorts LAST => it is Character index 32 on the client.)

CLIENT LokiCharacter — 13 own CPF_Net props, in field order:
   0 OutOfBoundsBufferTimeRemaining        Float
   1 CustomAnimationState                  Enum  (3-value ECharacterCustomAnimationState — already mirrored)
   2 bIdle                                 Bool
   3 bCharacterMovementEnabled             Bool
   4 MaxLevel                              Int
   5 Experience                            Int
   6 RepMovementFollowActor                Struct LokiRepCharacterMovement_FollowActor (0x1005 member-wise)  [Loki custom]
   7 RepMovementGlide                      Struct LokiRepCharacterMovement_Glide       (0xE001 member-wise)  [Loki custom]
   8 RepMovementGrind                      Struct LokiRepCharacterMovement_Grind       (0x1005 member-wise)  [Loki custom]
   9 RepMovementServerRotation             Struct Rotator                              (NetSerialize, 1 cmd) [engine FRotator]
  10 LivingState                           Enum
  11 DebugModes                            UInt32
  12 bWallJumped                           Bool
CLIENT LokiCharacter — 14 own net funcs (already mirrored correctly in LokiCharacterStub.h, count matches).

--------------------------------------------------------------------------------
4. THE FIX (step #2 — NOT done this session; scope is now exact)
--------------------------------------------------------------------------------
The mirror must make each tier own the CLIENT's counts so the FClassNetCache index space aligns:
  * Character tier -> 12 reps (currently 10). The 2 missing are structural. Options:
      - Inject the missing CPF_Net props onto the stub's ACharacter ClassReps the way AActor's
        ServerState is injected (Loki.cpp ForceSetUpReplicationData / InjectServerStateReplicatedProperty),
        OR add a native ACharacter-subclass tier — BUT the props must resolve to the Character LEVEL so
        the boundary lands at 12, not shift into LokiCharacter. Simplest: match the client's exact 12
        (drop RepRootMotion, add ReplicatedCharacterMovement + ReplicatedGravityScale) at the ACharacter
        level. VERIFY the stub's 7 Character net funcs are the SAME 7 NAMES as the client (so
        ServerMovePacked still sorts last = index 32) against the live stub boot NetCacheDump.
  * LokiCharacter tier -> 13 reps (currently 2 in LokiCharacterStub.h). Add the 11 missing props in
    field order (bIdle, bCharacterMovementEnabled, MaxLevel, Experience, RepMovementFollowActor,
    RepMovementGlide, RepMovementGrind, RepMovementServerRotation, LivingState, DebugModes, bWallJumped).
  * WIRE FORMAT (only matters AFTER the index boundary aligns and the pawn starts hydrating — the S54
    Missions lesson): the 4 Loki custom structs (LokiRepCharacterMovement_{FollowActor,Glide,Grind} +
    the Character-tier RepCharacterMovement) are member-wise/NetSerialize and will each need a matching
    USTRUCT so the leaf-cmd stream is byte-identical; engine structs (BasedMovementInfo,
    Vector_NetQuantizeNormal, Rotator) the stub gets for free. Expect to iterate on the NEXT
    "Invalid replicated field N" the same way (S54/S70 loop) once field 32 clears.
  * S70 RULE STILL APPLIES: do NOT call the engine base's GetLifetimeReplicatedProps; register base
    props BY NAME NON-PUSH or the bIsPushBased assert (CoreNet.h:331) fires.
  * CAVEAT unchanged: GAS attributes are unreplicated server-side (S80 GetMaxSpeed 0), so even a
    perfectly-hydrated possessed pawn may not MOVE — measure which GetMaxSpeed the server-possessed
    pawn runs before assuming.

Revert baseline anytime: ALokiMinionCharacter -> ADefaultPawn in LokiStubGameMode (S77/S81 spectator).

--------------------------------------------------------------------------------
5. ARTIFACTS
--------------------------------------------------------------------------------
tools/re/netcache_chain.py                    NEW — the client cumulative-index-space walker + auto-diff
scratchpad/lokichar_props.py                  all-children CPF_Net walk (resolved the 2-vs-13 cap bug)
scratchpad/struct_types.py                    struct inner-type + NetSerialize-flag dump per tier
Live capture: client PID 40736, base 0x7FF6AF000000 (S85). Classes: Character 0x1FC2BABFD80,
LokiCharacter 0x1FC2FB61A00. (LokiMinionCharacter is a match-only class; field 32 lives above it so
the menu chain to LokiCharacter is sufficient to diagnose.)

--------------------------------------------------------------------------------
6. THE FIX — IMPLEMENTED, BUILT, BOOT-VERIFIED, AND LIVE-TESTED (★ connection HOLDS)
--------------------------------------------------------------------------------
Changes (branch dedicated-server-stub):
  * unreal-stub/Source/Loki/Loki.cpp — new InjectCharacterExtraReps(): appends two CPF_Net props
    (ReplicatedCharacterMovement + ReplicatedGravityScale) to stock ACharacter (1-cmd each, same
    FLokiStructPropertyWithOffset mechanism as ServerState on AActor; offset = max existing ACharacter
    rep offset = 1568). Called right before InjectServerStateReplicatedProperty (whose rebuild covers
    them). => Character tier 10 -> 12 reps. Also added DumpClassNetCacheLayout(ALokiMinionCharacter).
  * LokiCharacterStub.h — ALokiCharacter gains 11 UPROPERTY(Replicated) (bIdle, bCharacterMovementEnabled,
    MaxLevel, Experience, RepMovement{FollowActor,Glide,Grind,ServerRotation} [scalar placeholders for the
    4 client structs — 1 ClassReps entry each, COND_SimulatedOnly so never serialized], LivingState,
    DebugModes, bWallJumped) => 2 -> 13 own reps.
  * LokiCharacterStub.cpp — ALokiCharacter::GetLifetimeReplicatedProps registers the 2 injected Character
    props + the 11 new own props, ALL COND_SimulatedOnly (never sent to the autonomous owner; slots exist
    only to align the field-cache index space, so their wire format cannot desync the owner).

BUILD: Build.bat LokiEditor Win64 Development -WarningsAsErrors -> exit 0, 59s.
BOOT DUMP (headless gate, C:\Temp\DsS85.log): Character ClassReps=26 (=14 base + 12 own), LokiCharacter
ClassReps=39 (13 own, base 33), LokiMinionCharacter ClassReps=42 (3 own, base 60); field [32] ==
ServerMovePacked on the whole character chain -- matches the client. VERIFIED before the live run.

LIVE TEST (2026-07-21, forceTutorialMatch=true, stub on 7777, launch-redirect -NoHook):
  * Client armed the tutorial match, travelled to 127.0.0.1:7777, LoadMap LVL_Tutorial, TravelCompleted,
    "Entering game state LokiGameState_2147480959" (S70 milestone held).
  * Stub: "spawned + possessed ALokiMinionCharacter LokiMinionCharacter_0 ... PC->GetPawn()=LokiMinion
    Character_0 (Role=3 hasConnection=1)" + "Join succeeded".
  * ★★★ NO "Invalid replicated field 32" (or any invalid field on LokiMinionCharacter). The S84 wall is
    GONE. ★★★
  * ★★★ CONNECTION HELD 3+ MIN in the live LVL_Tutorial world (client log advancing, still in
    LokiGameState, NO ConnectionTimeout / NetworkFailure / login-bounce) — past the S84 ~360ms drop AND
    the S81 ~20s movement-freeze drop. First server-authoritative possessed-character connection in the
    project to survive. This connection-hold was the memory's stated "real prize."
  * Client-side RPM (obj_by_class.py, PID 73220): a LIVE LokiMinionCharacter replica exists
    (0x15A91CB0080, non-CDO) => real possession replicated through, not a dead spectator.

REMAINING (the next iterations, all NON-fatal to the held connection):
  * A separate desync on the LokiPlayerState channel: stub-side ensure "ReadFieldHeaderAndPayload: Error
    reading numbits ... LokiPlayerState ... OutField: RemoteRole" (LokiActorChannel.cpp:82 = Super call;
    non-fatal ensure, fires once). Client logs "GetLocalLokiPlayerState failed to get a player state" +
    "SerializeNewActor failed to find/spawn actor ... Channel: 10". This is the LokiPlayerState mirror,
    NOT touched by the S85 change (APlayerState : AActor, unaffected by the ACharacter injection) — a
    pre-existing issue only now exposed because the connection survives long enough to exchange PlayerState
    bunches. NEXT: run netcache_chain.py against LokiPlayerState and diff vs the LokiPlayerStateStub mirror.
  * Movement/control: not yet driven. GAS attributes are unreplicated server-side (S80 GetMaxSpeed 0), so
    a possessed pawn may not move even with input — measure which GetMaxSpeed the server-possessed pawn
    runs. Client spam "AttachAudioListenerToHero called when feature toggles were not ready" is gameplay-
    init noise, not a disconnect.

--------------------------------------------------------------------------------
7. LokiPlayerState CHANNEL — DIFFED, FIXED, LIVE-VERIFIED (RemoteRole desync GONE)
--------------------------------------------------------------------------------
After the character fix the connection held long enough to expose a SECOND desync: stub ensure
"ReadFieldHeaderAndPayload: Error reading numbits ... LokiPlayerState ... OutField: RemoteRole".
Diagnosed with the SAME tool: netcache_chain.py 73220 0x7FF6AF000000 LokiPlayerState.
  * Client LokiPlayerState: PlayerState tier = 11 reps/0 funcs (MATCHED stub), LokiPlayerState tier =
    9 reps + 7 funcs (base 22): HeroClass(Class), PlatformPlayerID(Str), SpectateTeamIndex(Int),
    ParticipantMatchStartDetails(Struct CoreGameParticipantDetails member-wise), WalletStorage(Array),
    GoldSpentValue(Int), ReplicatedTeamIndex(Int), IsAnonymousBot(Bool), BattleRoyalePlayerPhase(Enum);
    funcs 31..37 with ServerSetReadyToPlay at 36.
  * Stub mirror (LokiPlayerStateStub.h) declared only 1 own rep (HeroClass) — ANOTHER S73 undercount.
    So the stub's 7 funcs sat at 23..29 and its GetMaxIndex was 30; the client's ServerSetReadyToPlay
    (field 36, fired at "ENTERING THE BREACH") was PAST the stub's range -> reader fail -> the RemoteRole
    ensure. (PlayerState is APlayerState:AActor — untouched by the ACharacter injection; pre-existing,
    only newly exposed.)
FIX: LokiPlayerStateStub.h adds the 8 missing props in client field order (scalar/string placeholders
for the struct+array — 1 ClassReps entry each, never written by the stub so not sent); .cpp registers all
9 via DOREPLIFETIME (non-push, COND_None), ctor log updated. BUILD exit 0 (7s). BOOT DUMP: LokiPlayerState
ClassReps=31 (9 own), BattleRoyalePlayerPhase[30], ServerSetReadyToPlay[36] — client-matched.
LIVE (relaunched client): possessed + Join succeeded; ★ NO ReadFieldHeaderAndPayload error, NO ensure, NO
invalid field ★. Client-side "GetLocalLokiPlayerState failed" dropped from continuous to ONE early hit
(at BeginPlay, before replication) => the local PlayerState now RESOLVES to a Loki-typed PlayerState after
possession. Connection stable in LokiGameState.

--------------------------------------------------------------------------------
8. WHERE IT STANDS NOW + the next two threads (NOT PlayerState-related)
--------------------------------------------------------------------------------
Two schema desyncs fixed (Character field-32, PlayerState RemoteRole); the client sits in the live
LVL_Tutorial world at the match-transition ("ENTERING THE BREACH"), connection stable, PlayerState +
possession resolved. Blocked on:
  (A) ULokiGameFeatureToggles "not ready" — 112x+ client errors (CursorCharacterAim, WinterEvent,
      BonfireUAVs, AttachAudioListenerToHero...). The GameFeatures subsystem loads (178 builtins + LokiWinter
      Active) but the TOGGLES readiness state is never set. This is the dominant remaining gate and is very
      likely BACKEND-driven (feature-flag config: the redirected client-config-jx-prod host and/or
      /configuration/client) — the same "serve the right payload" shape that solved passes/missions. NEXT
      thread to pull.
  (B) CreateSavedMove "Hit limit of 96 saved moves" — the client's CMC IS generating movement saved-moves
      on the possessed pawn (movement path is LIVE) but the 96-move buffer fills because the server isn't
      acking/consuming them (the stub runs no real movement/round). Relevant to the eventual "does it move"
      question; pair with the S80 GAS GetMaxSpeed measurement.
  (C) Drop-in / round-start remains server-authoritative (stub runs no real round) — the deep ceiling.

ENVIRONMENT AT HANDOFF: stub (UnrealEditor-Cmd) up on 7777 with the S85b build (logs C:\Temp\DsS85b.log);
ags armed (forceTutorialMatch=true in interactive.go — REVERT to false when done with DS testing); client
connected in LVL_Tutorial possessing LokiMinionCharacter_0 with a resolved LokiPlayerState. Revert the
possess baseline anytime: ALokiMinionCharacter -> ADefaultPawn in LokiStubGameMode.

--------------------------------------------------------------------------------
9. FEATURE-TOGGLE DEEP RE (user chose the heavy path) — model confirmed, artifacts produced
--------------------------------------------------------------------------------
MODEL (confirmed): game feature toggles are an ENUM, ELokiGameFeatureToggle = 151 values (schema.txt:61484;
UseCirclePhasesOverride=0 ... incl. AttachAudioListenerToHero/CursorCharacterAim/WinterEvent/BonfireUAVs).
`ULokiGameFeatureToggles::Get(ELokiGameFeatureToggle)` is a STATIC C++ accessor (NOT a reflected UClass —
find_uclass 'LokiGameFeatureToggles' = 0 hits), so it reads a per-PlayerController enum-indexed toggle array
+ a "ready" flag that are NATIVE (non-UPROPERTY) members — which is why they never appeared in the reflected
78 PC props. Readiness is broadcast via three PC delegates, offsets pinned live (class_props):
    LokiPlayerController+0x0A98  OnClientGameFeatureTogglesReady            (MulticastInlineDelegate)
    LokiPlayerController+0x0AA8  OnAnyClientGameFeatureToggleChanged
    LokiPlayerController+0x0AB8  OnAnyClientGameFeatureTogglesReadyOrChanged
The toggle array + ready bool are native members in that same +0xA00..+0xB00 block.

WHY STATIC STRING-XREF IS BLOCKED: the "ULokiGameFeatureToggles::Get %s called when feature toggles were not
ready" format string is packer-encrypted — wstrings/strings find only HEAP copies of the formatted message
(0xFD.../0x25D...), zero module-range (.rdata) hits. Same VMProtect wall as the S61 login strings. The
FeatureToggledChanged UFunction "thunk" (0x7FF6B44246F0) is a VMProtect trampoline (mov/setnz/add/jmp
dispatch), not the body — live single-address disasm through it is lossy.

ARTIFACTS PRODUCED (the deep path's foundation; /dumps is git-ignored):
    dumps/toggles/SUPERVIVE-Win64-Shipping.dump.exe   cold image, in-match state, 65.6% .text readable
    dumps/toggles/SUPERVIVE-Win64-Shipping.exports.txt 40627 exports sidecar
    dumps/toggles/SUPERVIVE-deobf.exe                  ★ IAT rebuilt 1107/1107 (0 unresolved) — Ghidra-ready
Captured from the in-match client (PID 27900) where the toggle code is committed. For fuller .text, dump
additional states + mergedumps (login/menu/in-match are already partially covered by prior work).

GHIDRA PLAN (the definitive trace — needs Ghidra/IDA, the tooling's explicit handoff point): load
SUPERVIVE-deobf.exe (ImageBase = live base 0x7FF6AF000000, so Ghidra addr == this doc's base+RVA 1:1).
ANCHORS:
  (1) PRIMARY — the readiness SETTER via the delegate offset: search for the constant 0xA98 (2712) used as a
      struct offset; the fn that does `lea rcx,[rXX+0xA98]` then calls the multicast broadcast
      (FMulticastScriptDelegate::ProcessMulticastDelegate — a UE-internal, NOT an import, so it won't be
      auto-named) = OnClientGameFeatureTogglesReady.Broadcast(). The BROADCASTER (not a binder/AddUnique) that
      also writes a nearby bool = the SETTER. 0xAB8 (…ReadyOrChanged) is broadcast by the setter too.
  (2) SECONDARY — committed reflection strings (unlike the encrypted log string): "AttachAudioListenerToHero"
      @ 0x7FF6B794B8E0 (RVA 0x894B8E0), "ELokiGameFeatureToggle" also committed. Xref -> Z_Construct_UEnum ->
      the ELokiGameFeatureToggle UEnum global; ULokiGameFeatureToggles::Get loads that UEnum in its error path
      to format the value name, so the UEnum global's xrefs include Get.
  (3) FALLBACK if the setter is VM-virtualized: find Get's READ of the ready flag (Get is hot code, likely NOT
      virtualized) to get the ready-flag offset, then find writers of that offset.
EXTRACT + REPORT BACK: the setter address + decompile; the ready-flag offset (bool set true near 0xA98); the
toggle-array offset + how populated; and CRUCIALLY the setter's CALLERS (Xrefs) — that names the TRIGGER and
answers config-gated vs round-gated DEFINITIVELY. Expected ROUND-GATED (per-match game-feature resolution at
server round-start; consistent with 0-at-menu / only-after-DS-travel) but NOT decompile-confirmed — treat as
strong-hypothesis given this project's 8/8 "wall = measurement bug" record. Cross-check FeatureToggleOverrides
(schema:13053) + GameFeatureToggleRequirements (schema:26359) as the missing match input.

STATUS: the deep RE has confirmed the mechanism + produced the analyzable image + pinned the delegate anchors;
the final setter decompile is a Ghidra-in-hand step (fully set up). It has NOT been reduced to a backend or
mirror fix, and current evidence points to the same server-round ceiling as drop-in.

--------------------------------------------------------------------------------
10. ★★★ GHIDRA RESULT (2026-07-22) — the readiness mechanism is a REPLICATED COMPONENT; the "round-gated
    ceiling" hypothesis (§9) is FALSIFIED. The fix is STUB-PROVIDABLE (corrects §9).
--------------------------------------------------------------------------------
The user ran Ghidra auto-analysis (project Ghidra/SuperVive.gpr, 1.4GB). I pulled results via Ghidra HEADLESS
(analyzeHeadless + custom GhidraScripts in tools/ghidra_scripts/, output in dumps/toggles/*.txt) — no GUI, no
pasting. A symbol dump (ListToggleSymbols.java) recovered Ghidra's auto-named STRING LABELS, which named the
whole mechanism:
  * s_OnRep_GameFeatureToggles            -> a RepNotify => GameFeatureToggles is a REPLICATED property
  * s_AuthSetGameFeatureToggle            -> server-AUTHORITATIVE per-toggle setter
  * s_GetFeatureTogglesReady / s_GetFeatureToggleValue / s_GetFeatureToggleWithDefaultFallb / s_BranchOnFeatureToggle
  * u_ULokiGameFeatureToggles::Get_%s_c...-> the error format string IS committed (@0x7ff6b7b1c4f0 etc.)
  * s_OnClientGameFeatureTogglesReady + ...ReadyOrChanged (the PC delegates, +0xA98/+0xAB8, confirmed)
Owning class (schema.txt:27776): **LokiServerAuthConfig : ActorComponent (4 props)** —
  OnAnyGameFeatureToggleChanged (delegate), **GameFeatureToggles (ArrayProperty, REPLICATED w/ OnRep)**,
  GameFeatureToggleDelegates (Array), GameFeatureToggleRoles (Map). It is referenced by
  **LokiGameState.ServerAuthConfig** (ObjectProperty UClass:LokiServerAuthConfig, schema.txt:25286).

MECHANISM (definitive): the server sets toggles via AuthSetGameFeatureToggle on LokiServerAuthConfig; the
REPLICATED GameFeatureToggles array replicates to each client; the client's OnRep_GameFeatureToggles fires ->
marks the client's game-feature toggles READY -> broadcasts OnClientGameFeatureTogglesReady on the
LokiPlayerController (+0xA98). ULokiGameFeatureToggles::Get(ELokiGameFeatureToggle) reads the resolved toggles
and logs "...not ready" until that OnRep. WHY THE STUB CLIENT IS STUCK: the stub's ALokiGameState provides no
replicated LokiServerAuthConfig / GameFeatureToggles, so OnRep never fires. This is delivered by REPLICATION,
NOT by a round-only server event — so §9's "round-gated ceiling" was WRONG (it was a hypothesis, hedged; now
falsified — the project's 8/8 "wall = wrong hypothesis" record holds).

★ THE FIX IS STUB-PROVIDABLE (same by-path mirror technique as ALokiGameState S70 / ALokiPlayerState S85):
mirror `LokiServerAuthConfig` as a native replicated ActorComponent (path /Script/Loki.LokiServerAuthConfig),
populate GameFeatureToggles, and replicate it to the client (as a replicated component/subobject of the
GameState — the ServerAuthConfig link — or a bAlwaysRelevant replicated actor). The client's OnRep fires ->
toggles ready. REMAINING RE FOR THE FIX (next session, best via LIVE netcache + the deobf dump): (1) the
GameFeatureToggles array ELEMENT type — usmap says ArrayProperty<MulticastInlineDelegateProperty> but that
inner is the usmap's KNOWN-UNRELIABLE container reporting (cf. S54 missions); RE the real element live
(likely a per-toggle struct: enum id + value + role). (2) The replication PATH — is LokiServerAuthConfig a
replicated component on the GameState (subobject) or an independently-relevant actor? (3) Confirm OnRep alone
flips readiness (vs also needing a PC-side step). Toggle read API recovered: GetFeatureTogglesReady,
GetFeatureToggleValue, GetFeatureToggleWithDefaultFallback, BranchOnFeatureToggle, GetCVar.

TOOLING NOTE: Ghidra headless works here (analyzeHeadless, JDK at E:\...\jdk-25). Caveat: Ghidra 12.1.2's
bundled felix 7.0.5 intermittently NPEs on JDK 25 (handleJavaVersionChange, "dataFile is null") when
compiling a new script bundle — retry / move %APPDATA%\ghidra\...\osgi aside; no compatible older JDK is
installed (only jdk-25 + jre1.8). The DecompileByRefs.java pass (Get internals/offsets) is blocked by this
flake but is NOT needed for the mechanism — it's needed to BUILD the mirror; do it next session (fresh
JVM/GUI, or a JDK21).

--------------------------------------------------------------------------------
11. LokiServerAuthConfig MIRROR — SCOPED (live capture, DS client PID 13764 base 0x7FF79D3B0000)
--------------------------------------------------------------------------------
DEFINITIVE SCHEMA (netcache_chain + rep_expand_class + class_props + authcfg_probe, live):
  * LokiServerAuthConfig : UActorComponent. Net-cache tiers:
        ActorComponent      2 reps (bReplicates, bIsActive), 0 funcs
        LokiServerAuthConfig 1 rep + 1 func:  [2] GameFeatureToggles   [3] MulticastSetGameFeatureToggle
  * ★ GameFeatureToggles = **TArray<bool>** (rep_expand: DYNARRAY -> BoolProperty inner) — the usmap's
    "ArrayProperty<MulticastInlineDelegateProperty>" inner was WRONG (the known-unreliable container report,
    as predicted). One bool per ELokiGameFeatureToggle (151 values). Offset +0x130 on the client component
    (flags 0x40000100000220). size=16 (TArray).
  * MulticastSetGameFeatureToggle = 1 own net func [NetMulticast, Reliable].
TOPOLOGY (authcfg_probe): the component is a **default subobject named "ServerAuthConfig" of LokiGameState**
  (Outer = Default__LokiGameState; also on LokiGameState_AS + BP_LokiGameState_Code_C variants) — i.e.
  CreateDefaultSubobject in the GameState constructor. Referenced by LokiGameState.ServerAuthConfig
  (ObjectProperty, NON-replicated — set locally, not on the wire). ★ ON THE DS CLIENT GameFeatureToggles
  num=0 (EMPTY) on every instance — the component exists but was never populated -> OnRep_GameFeatureToggles
  never fires -> toggles never ready. That is the exact gap.

THE FIX (scoped; same by-path-mirror + subobject technique as ALokiGameState S70):
  1. NEW unreal-stub/Source/Loki/LokiServerAuthConfigStub.{h,cpp}:
       UCLASS() class ULokiServerAuthConfig : public UActorComponent  (path /Script/Loki.LokiServerAuthConfig)
         UPROPERTY(Replicated) TArray<bool> GameFeatureToggles;              // client-matched [2]
         UFUNCTION(NetMulticast, Reliable) void MulticastSetGameFeatureToggle();  // empty; NetFields [3] align
       ctor: SetIsReplicatedByDefault(true);
       GLRP: register GameFeatureToggles (non-push). Handle the ActorComponent base tier like S70 (bReplicates/
       bIsActive) — register base reps by name non-push if calling UActorComponent::Super trips the push assert.
  2. ALokiGameState (LokiGameStateStub): CreateDefaultSubobject<ULokiServerAuthConfig>(TEXT("ServerAuthConfig"))
     in the ctor (MATCH the client subobject name so the actor-subobject NetGUID/RepLayout aligns), store it in
     a ServerAuthConfig UPROPERTY. In InitGameState populate GameFeatureToggles with 151 `true` bools (or the
     desired set; index == ELokiGameFeatureToggle value).
  3. Boot: DumpClassNetCacheLayout(ULokiServerAuthConfig::StaticClass()) -> expect ActorComponent 2 + own 1 rep
     + 1 func. Live test: watch for OnRep_GameFeatureToggles firing on the client + the 112x "not ready" errors
     STOPPING + WBP progressing past "ENTERING THE BREACH".
  ★ MAIN RISK / live-test unknown: UE 5.4 COMPONENT subobject replication. Default replicated subobjects may
    need the registered-subobject-list (AddReplicatedSubObject / bReplicateUsingRegisteredSubObjectList) rather
    than the legacy ReplicateSubobjects path; if the component's GameFeatureToggles doesn't reach the client,
    that's the knob to turn (register the component as a replicated subobject of ALokiGameState). The array is a
    simple TArray<bool> so the wire format itself is trivial (no S54-style struct desync risk).
Captures: docs/session-85 §11; live PID 13764 base 0x7FF79D3B0000; scratchpad/authcfg_probe.py.

--------------------------------------------------------------------------------
12. LokiServerAuthConfig MIRROR — BUILT + BOOT-VERIFIED + REACHES THE CLIENT; blocked on the SUBOBJECT
    WIRE (the connection regresses). GUARDED OFF pending the wire iteration.
--------------------------------------------------------------------------------
BUILT (S85d): unreal-stub/Source/Loki/LokiServerAuthConfigStub.{h,cpp} — ULokiServerAuthConfig : UActorComponent
(/Script/Loki.LokiServerAuthConfig), UPROPERTY(Replicated) TArray<bool> GameFeatureToggles (SeedAllToggles ->
151 true) + empty NetMulticast MulticastSetGameFeatureToggle; GLRP registers UActorComponent's bReplicates/
bIsActive by name non-push + our prop. LokiGameStateStub: ctor CreateDefaultSubobject<ULokiServerAuthConfig>
("ServerAuthConfig"); BeginPlay (authority) SeedAllToggles(151,true). Loki.cpp boot dump added.
BOOT DUMP (headless): ActorComponent ClassReps=2 (bReplicates,bIsActive) + LokiServerAuthConfig ClassReps=3
([2] GameFeatureToggles) NetFields=1 ([3] MulticastSetGameFeatureToggle) — CLIENT-MATCHED. SeedAllToggles fired
(151 true). Build exit 0.
LIVE (S85d): the client traveled + Joined, then the connection DROPPED on the ServerAuthConfig replication:
  stub:   Join succeeded -> ObjectReplicatorReceivedBunchFail -> UChannel::CleanUp ChIndex 0 -> ConnectionLost.
  client: "ReadContentBlockHeader: Unable to read sub-object class. Actor: LokiGameState" ->
          "InternalLoadObject: Unable to resolve object ... NOT_IN_CACHE" ->
          "ReceiveProperties: Invalid property terminator handle - Handle=8352" ->
          "RepLayout->ReceiveProperties FAILED: LokiServerAuthConfig ...LokiGameState_....ServerAuthConfig".
KEY DIAGNOSIS: the subobject ASSOCIATION WORKED — the client resolved the subobject to its OWN
LokiGameState_<n>.ServerAuthConfig (so CreateDefaultSubobject("ServerAuthConfig") name-matching is correct).
The element type is NOT the bug: GameFeatureToggles inner is a genuine native TArray<bool> on BOTH sides
(BoolProperty, ElementSize 1, FieldMask 0xFF — scratchpad/gft_inner.py). The failure is the SUBOBJECT
CONTENT-BLOCK FRAMING: "Unable to read sub-object class" fires FIRST (a UActorChannel::ReadContentBlockHeader
error), then the property cursor is misaligned -> garbage terminator handle. This is the UE 5.4 component-
subobject replication path — a wire iteration (S54-class), NOT a fundamental wall.
NEXT ITERATION SUSPECTS (in order): (1) UE 5.4 registered-subobject-list — the stub may need
bReplicateUsingRegisteredSubObjectList + AActor::AddReplicatedSubObject(ServerAuthConfig) so the content-block
header frames the subobject as stably-named (the legacy default-component path may be writing a class the client
can't read). (2) push-vs-non-push mismatch: the GameState's ClassReps are rebuilt NON-push by the stub's
ForceSetUpReplicationData (Actor-only) while the component's RepLayout is engine-built (possibly push) — the
subobject framing may inherit that inconsistency. (3) the TArray<bool> array-delta framing itself (send an
EMPTY array first to isolate content vs header). Reproduce with kEnableServerAuthConfig=true.
STATE: GUARDED — kEnableServerAuthConfig=false (LokiGameStateStub.h) compiles the component attachment OUT, so
a normal launch is byte-identical to the S85c spectator baseline (connection holds 3+ min). All the mirror code
+ boot dump stay. Flip the flag TRUE to resume the subobject-wire iteration. Captures: scratchpad/gft_inner.py,
authcfg_probe.py.

--------------------------------------------------------------------------------
13. S86 — the fix crack: engine-source root-cause via a Workflow, SetNetAddressable, and the DEEPER wall
--------------------------------------------------------------------------------
Ran a 4-agent research Workflow over the UE5.4 engine source (H:/Unreal Engine/UE_5.4) — root-caused with
file:line proof. FINDING: the client hitting "Unable to read sub-object class" (DataChannel.cpp:4777) is
reachable ONLY if the SERVER wrote the non-name-stable content-block branch (DataChannel.cpp:4460 else), which
happens iff Obj->IsNameStableForNetworking()==false. FIX APPLIED (S86): ULokiServerAuthConfig ctor calls
SetNetAddressable() -> bNetAddressable=true -> IsNameStableForNetworking() returns true unconditionally
(ActorComponent.cpp:2204). Re-enabled the flag, rebuilt (exit 0).
★ DIAGNOSTIC (added a boot-log line): the stub CONFIRMED ServerAuthConfig IsNameStableForNetworking=1,
IsSupportedForNetworking=1, bReplicates=1 (IsActive=0). So SetNetAddressable TOOK. ★ YET the client STILL drops
(fresh run, client PID 112104): LoadMap LVL_Tutorial -> "Unable to read sub-object class. Actor: LokiGameState"
-> "ReceiveProperties FAILED: LokiServerAuthConfig" -> ConnectionLost -> BP_MainMenuGameState. And the UE5.4
registered-subobject-list default is FALSE (GDefaultUseSubObjectReplicationList=false, ActorComponent.cpp:98;
Actor.cpp:155) so the stub uses the LEGACY path whose WriteContentBlockHeader DOES honor the (now-correct)
stable bit. RECONCILIATION (the sharpened root cause): the desync is UPSTREAM of the stable bit — in
`Bunch << Obj`, the SUBOBJECT-NetGUID serialization at DataChannel.cpp:4454, which runs BEFORE the stable-bit
read. If the server writes a different bit count there than the client reads, the client reads the stable bit
(and everything after) from the wrong offset -> reads 0 -> tries to read a class -> "Unable to read sub-object
class", then the payload terminator is garbage. So the fault is the PACKAGE-MAP NetGUID export of a
dynamic-outer'd subobject (outer = the runtime-spawned GameState), likely interacting with the stub's
class-net-cache suppression / by-path class GUID — NOT the content-block stable branch (that is now correct)
and NOT the TArray<bool> element type (confirmed native both sides).
NEXT ITERATION (instrumentation-led, ranked): (a) log the exact subobject the "Unable to read" is for + dump
the NetGUID type (static/dynamic) the server assigns vs what the client reads — settle the `Bunch << Obj`
bit-count mismatch directly (add a UActorChannel/PackageMap trace or a stub-side GetOrAssignNetGUID log). (b)
H-B: add ULokiServerAuthConfig to the stub's ForceSetUpReplicationData rebuild (Loki.cpp after the Actor loop)
in case the property RepLayout also diverges. (c) STRUCTURAL alternative: deliver the toggles from a
STABLY-NAMED separate always-relevant actor (its own actor channel, no dynamic-outer subobject) or via the
MulticastSetGameFeatureToggle RPC — sidesteps the dynamic-subobject NetGUID path entirely. All S86 code
(SetNetAddressable + the IsNameStableForNetworking boot diagnostic) STAYS behind kEnableServerAuthConfig=false;
baseline restored. Workflow: wf_494ee822-892 (engine-source root-cause, 5 agents).

--------------------------------------------------------------------------------
14. S86b — the STRUCTURAL conclusion + why the toggle carrier is PARKED (honest handoff)
--------------------------------------------------------------------------------
Recommended "option 3" (deliver toggles from a stably-named SEPARATE actor) FALSIFIED on reflection: the client's
readiness is fired by OnRep_GameFeatureToggles ON THE LokiServerAuthConfig COMPONENT owned by the client's
GameState. To drive it, the server must replicate to THAT component. The only channels are (a) component-subobject
property replication or (b) the MulticastSetGameFeatureToggle RPC on the component — BOTH require the component
subobject of the (dynamically-spawned) GameState to be net-addressable, i.e. both hit the IDENTICAL wall. A
separate actor's component is also a subobject of a dynamically-spawned actor => same wall. A truly stably-named
carrier would need a MAP-PLACED (loaded) actor, which the stub's minimal Entry map has none of. So there is NO way
to drive the client's component OnRep without solving the component-subobject replication.
CONFIRMED FACTS (do not re-derive): server IsNameStableForNetworking(ServerAuthConfig)=1 (SetNetAddressable took;
content-block stable branch is correct); UE5.4 registered-subobject-list default is FALSE so the stub uses the
legacy path; the client HAS the subobject (Default__LokiGameState has a ServerAuthConfig default subobject, so
every live LokiGameState replica creates one); GameFeatureToggles is a native TArray<bool> both sides. The drop is
the package-map `Bunch << Obj` (DataChannel.cpp:4454) exporting the component as a DYNAMIC object (IsFullNameStable
ForNetworking is false — the GameState outer is dynamic) whose class NetGUID comes back NOT_IN_CACHE, desyncing the
bit cursor before the stable bit. S86b instrumentation (stub -LogCmds "LogNetPackageMap Verbose") did NOT cleanly
isolate it — package-map logs reference NetGUIDs numerically in a huge trace; needs DEDICATED net-trace tooling
(map the ServerAuthConfig NetGUID number, then follow its export both sides), not grep.
WHY PARKED: replicating a component subobject of a dynamic mirror actor is a capability NO prior stub mirror needed
(S70/S71/S73 all replicated actor-level props only). It resisted the content-block fix (SetNetAddressable,
confirmed) and is now at the NetGUID-export layer; multiple ~10-min rebuild/test cycles did not converge. Honest
call: BANK the large progress (mechanism cracked, mirror built + boot-verified + reaching the client + associating
by name) and solve the package-map NetGUID export in a FOCUSED session. NEXT-SESSION PLAN: (1) log the
ServerAuthConfig NetGUID NUMBER server-side (Connection->PackageMap->GetNetGUIDFromObject at first replicate), grep
both verbose logs for that number to see the export bytes; (2) if the CLASS NetGUID misses, force-export
/Script/Loki.LokiServerAuthConfig into the client guid cache early (and verify the stub's class suppression doesn't
strip it); (3) research whether ULokiGameFeatureToggles::Get reads a GLOBAL/PC state (if so a MAP-PLACED stably-
named carrier becomes viable — but needs an IoStore/map edit). ALL S86 code stays behind kEnableServerAuthConfig=
false; the S85c spectator baseline is the running state (rebuilt exit 0).
