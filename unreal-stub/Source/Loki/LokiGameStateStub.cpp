#include "LokiGameStateStub.h"
#include "LokiServerAuthConfigStub.h"
#include "Net/UnrealNetwork.h"
#include "UObject/UnrealType.h"
// S87 DIAGNOSTIC: ReplicateSubobjects override needs the channel/connection/netdriver/guid-cache chain.
#include "Engine/ActorChannel.h"
#include "Engine/NetConnection.h"
#include "Engine/NetDriver.h"
#include "Engine/PackageMapClient.h"
#include "Net/DataBunch.h"
#include "Net/RepLayout.h"
#include "UObject/CoreNet.h"
#include "Misc/Parse.h"
#include "Misc/CommandLine.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiGameStateStub, Log, All);

// Register one AGameStateBase inherited property by NAME as a non-push (bIsPushBased=false), COND_None
// lifetime prop. We do this instead of calling AGameStateBase::GetLifetimeReplicatedProps because the
// engine registers those props as PUSH-BASED (DOREPLIFETIME_WITH_PARAMS_FAST) and also registers the
// deprecated float ReplicatedWorldTimeSeconds. After we rebuild ClassReps at runtime + strip the float,
// the push-based inherited entries collide with our non-push scheme → "Assertion failed: bIsPushBased ==
// Other.bIsPushBased" (CoreNet.h:331). Registering by name, non-push, keeps the whole lifetime list
// consistent. Push model is a server-side dirty-tracking optimization only — the wire is identical.
static void AddGSBaseLifetimeProp(TArray<FLifetimeProperty>& Out, const TCHAR* Name)
{
	if (FProperty* P = FindFProperty<FProperty>(AGameStateBase::StaticClass(), Name))
	{
		Out.Add(FLifetimeProperty(P->RepIndex)); // COND_None, RepNotify default, bIsPushBased=false
	}
	else
	{
		UE_LOG(LogLokiGameStateStub, Warning,
		       TEXT("AddGSBaseLifetimeProp: AGameStateBase::%s not found."), Name);
	}
}

// S88 payload study: how many GameFeatureToggles the GameState seeds SERVER-SIDE, command-line-driven so the
// seed count can be swept (0/1/75/151) WITHOUT rebuilding — mirrors GetInjectBits()/GetInjectPattern() below.
// seed=0 ⇒ the array stays EMPTY == the CDO ⇒ the property is NOT in the changelist ⇒ ReplicateSubobject writes
// NO content block ⇒ isolates whether the header (N=11) is fully solved (connection should HOLD, toggles num=0).
// Defined here (above BeginPlay) because BeginPlay references it; GetInjectBits lives lower next to its use.
static int32 GetToggleSeed()
{
	static int32 Cached = []{ int32 v = LOKI_GAME_FEATURE_TOGGLE_COUNT;
		FParse::Value(FCommandLine::Get(), TEXT("toggleseed="), v); return v; }();
	return Cached;
}

ALokiGameState::ALokiGameState(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// AGameStateBase already sets bReplicates=true + bAlwaysRelevant=true + NetUpdateFrequency=100
	// in its constructor; restate them so the intent is explicit and robust to base changes.
	bReplicates = true;
	bAlwaysRelevant = true;

	// S87 NOTE: Fix #1 (this->SetNetAddressable() to make the component's outer name-stable) was TESTED and
	// REGRESSED the GameState — flipping the GameState ACTOR to a static/path GUID stops it hydrating as a
	// live replica (no "Entering game state LokiGameState", toggles num=0). Removed. The static-vs-dynamic
	// decoupling is now done on the COMPONENT itself via ULokiServerAuthConfig::IsFullNameStableForNetworking
	// (virtual override => component gets a STATIC guid, GameState stays DYNAMIC + hydrates). See §S87.

	// S85: create the "ServerAuthConfig" default subobject (a replicated ULokiServerAuthConfig) — MATCH the
	// client's LokiGameState.ServerAuthConfig subobject NAME so the actor-subobject replication associates
	// the stub's component with the client's local one. The array is left EMPTY here (so it differs from the
	// CDO and thus replicates when we seed it server-side in BeginPlay — see SeedAllToggles).
	// GUARDED (kEnableServerAuthConfig, default false): the subobject content-block framing currently desyncs
	// the client; keep it OFF so the S85c spectator baseline connection holds. See the header.
	if (kEnableServerAuthConfig)
	{
		ServerAuthConfig = CreateDefaultSubobject<ULokiServerAuthConfig>(TEXT("ServerAuthConfig"));
	}

	UE_LOG(LogLokiGameStateStub, Display,
	       TEXT("ALokiGameState constructed (/Script/Loki.LokiGameState mirror; 43 replicated props "
	            "over stock GameStateBase's 4 — session-69 schema; +ServerAuthConfig subobject S85)."));
}

void ALokiGameState::BeginPlay()
{
	Super::BeginPlay();

	// S85: populate the game-feature toggles SERVER-SIDE so the array differs from the (empty) CDO and
	// replicates to the client -> client OnRep_GameFeatureToggles -> toggles ready. Authority only.
	if (HasAuthority() && ServerAuthConfig)
	{
		const int32 ToggleSeed = GetToggleSeed();   // S88: -toggleseed=N (default 151) — sweep the payload
		ServerAuthConfig->SeedAllToggles(/*bValue=*/true, ToggleSeed);
		// S86 DIAGNOSTIC: IsNameStableForNetworking() decides the content-block branch (DataChannel.cpp:4460).
		// SetNetAddressable() in the ctor should make this TRUE; if the stub logs FALSE here, bNetAddressable
		// was reset during spawn/instancing (the S86 contradiction) — the smoking gun for the next attempt.
		UE_LOG(LogLokiGameStateStub, Display,
		       TEXT("ALokiGameState::BeginPlay: seeded %d game-feature toggles on ServerAuthConfig (%s) — "
		            "bReplicates=%d IsActive=%d IsNameStableForNetworking=%d IsSupportedForNetworking=%d."),
		       ToggleSeed, *ServerAuthConfig->GetName(),
		       (int32)ServerAuthConfig->GetIsReplicated(), (int32)ServerAuthConfig->IsActive(),
		       (int32)ServerAuthConfig->IsNameStableForNetworking(),
		       (int32)ServerAuthConfig->IsSupportedForNetworking());
	}
}

void ALokiGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	// S70: DELIBERATELY skip AGameStateBase::GetLifetimeReplicatedProps (Super = AGameStateBase). It
	// registers its props push-based + registers the deprecated float ReplicatedWorldTimeSeconds, which
	// (with our runtime ClassReps rebuild + float strip) trips the CoreNet.h:331 bIsPushBased assert.
	// Instead register AActor's props, then exactly the 4 GameStateBase props the SUPERVIVE client
	// replicates, BY NAME, non-push — keeping the lifetime list consistent + float-free.
	AActor::GetLifetimeReplicatedProps(OutLifetimeProps);
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("GameModeClass"));
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("SpectatorClass"));
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("bReplicatedHasBegunPlay"));
	AddGSBaseLifetimeProp(OutLifetimeProps, TEXT("ReplicatedWorldTimeSecondsDouble"));

	// All 43 in field-declaration order (COND_None). The RepIndex assignment that must align with the
	// client comes from declaration order (ForceSetUpReplicationData / SetUpRuntimeReplicationData), not
	// from this list; this list only enables replication + sets conditions.
	DOREPLIFETIME(ALokiGameState, bGetPreventWeaponFire);
	DOREPLIFETIME(ALokiGameState, bGetPreventMovement);
	DOREPLIFETIME(ALokiGameState, SpawnSelectEndTime);
	DOREPLIFETIME(ALokiGameState, WinningTeam);
	DOREPLIFETIME(ALokiGameState, WinningPawn);
	DOREPLIFETIME(ALokiGameState, WinStreak);
	DOREPLIFETIME(ALokiGameState, TeamScores);
	DOREPLIFETIME(ALokiGameState, TeamScoreToWin);
	DOREPLIFETIME(ALokiGameState, TeamStates);
	DOREPLIFETIME(ALokiGameState, bIsSuddenDeath);
	DOREPLIFETIME(ALokiGameState, GameOverWorldTime);
	DOREPLIFETIME(ALokiGameState, GameSuddenDeathOverWorldTime);
	DOREPLIFETIME(ALokiGameState, GameDuration);
	DOREPLIFETIME(ALokiGameState, RoundStartTime);
	DOREPLIFETIME(ALokiGameState, ReplicatedNumRemainingPlayers);
	DOREPLIFETIME(ALokiGameState, MaxPlayersPerTeam);
	DOREPLIFETIME(ALokiGameState, GameStartWorldTime);
	DOREPLIFETIME(ALokiGameState, DayNightState);
	DOREPLIFETIME(ALokiGameState, LastDayNightChangeTime);
	DOREPLIFETIME(ALokiGameState, TotalDayNightTime);
	DOREPLIFETIME(ALokiGameState, EndgamePhase);
	DOREPLIFETIME(ALokiGameState, DeathCirclePhase);
	DOREPLIFETIME(ALokiGameState, MatchStartDetails);
	DOREPLIFETIME(ALokiGameState, bDeathCircleRegenerated);
	DOREPLIFETIME(ALokiGameState, AutomaticRespawnEndPhaseOverride);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier0);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier1);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier2);
	DOREPLIFETIME(ALokiGameState, AscendingArmorOverrideTier4);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier0);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier1);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier2);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier3);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier4);
	DOREPLIFETIME(ALokiGameState, EquipmentUpgradeCostTier5);
	DOREPLIFETIME(ALokiGameState, AudioPulseMaxDistance);
	DOREPLIFETIME(ALokiGameState, AudioPulseCutoffFactorShort);
	DOREPLIFETIME(ALokiGameState, AudioPulseCutoffFactorMedium);
	DOREPLIFETIME(ALokiGameState, AudioPulseCutoffFactorLong);
	DOREPLIFETIME(ALokiGameState, NumTeams);
	DOREPLIFETIME(ALokiGameState, LokiDebugTarget);
	DOREPLIFETIME(ALokiGameState, DeathCircle);
	DOREPLIFETIME(ALokiGameState, CurrentPhase);
}

// S87 EMPIRICAL bit-injection: how many extra bits to write AFTER the ServerAuthConfig subobject GUID
// (before the stable bit) to MATCH the SUPERVIVE client's subobject-read framing. The S87 offline decode
// pinned the client reading bStablyNamed at ~bit 20-21 vs stock bit 10 ⇒ ~10-11 extra bits. SWEEP this
// (start 10, then 11) — and if the client interprets the bits, also kInjectPattern — until a live run shows
// the client reads bStablyNamed=1 + ReceiveProperties OK (no "Unable to read sub-object class", connection
// holds) + GameFeatureToggles num=151 on the client (scratchpad/gft_num.py). decode_cb.py + the SPLICED
// BLOCK dump verify each build's wire offline before launching.
// S87 empirical bit-injection sweep — read from the stub command line so N + pattern can be swept by
// relaunching the stub (no rebuild): add e.g. -injectbits=11 -injectpattern=0 to the UnrealEditor-Cmd args.
// Defaults chosen from the sweep so far: N=10 removed "Unable to read sub-object class" (client reached the
// stable branch + read the whole payload; terminator 8352->2400), N=11 regressed to "Invalid field 12"
// (non-monotonic ⇒ the client INTERPRETS the injected bits, so pattern matters too).
static int32 GetInjectBits()
{
	// S87 sweep result: N=11 is the HEADER solution — the client reads bStablyNamed at absolute bit 21
	// (decoded from N=9 bit21=0 → non-stable vs N=10 bit21=1 → stable), i.e. its subobject-header extra
	// field is 11 bits. With N=11 the client reaches the stable branch (NO "Unable to read sub-object
	// class") and enters the ServerAuthConfig PAYLOAD; the remaining drop ("Invalid field 12 in
	// LokiGameState") is a SECOND framing diff in the GameFeatureToggles TArray<bool> payload (leftover
	// bits → spurious block). Default 11; still command-line overridable for the payload study.
	static int32 Cached = []{ int32 v = 11; FParse::Value(FCommandLine::Get(), TEXT("injectbits="), v); return v; }();
	return Cached;
}
static uint32 GetInjectPattern()
{
	static uint32 Cached = []{ int32 v = 0; FParse::Value(FCommandLine::Get(), TEXT("injectpattern="), v); return (uint32)v; }();
	return Cached;
}

// S88 PAYLOAD splice lever — the header (N=11) is solved; the seed sweep (0 holds; 1/75/151 all desync at the
// SAME "Invalid replicated field 12") proved a FIXED, per-array framing diff in the dynamic-array serialization
// of GameFeatureToggles (TArray<bool>). The stub writes stock UE5.4:
//   payload = [lead checksum bit][arrayHandle packed][ArrayNum uint16=16b][N×(elemHandle+1bit)][arrEnd 0][objEnd 0]
// so payload bit 9 = just after the arrayHandle (before ArrayNum), payload bit 25 = just after ArrayNum.
// -paybits=N   : splice N bits into the payload (N<0 REMOVES |N| bits) — this is what matches the client's read.
// -payat=D     : payload bit-offset to splice at (default 25 = right after the 16-bit ArrayNum).
// -paypat=P    : LSB-first bit pattern for inserted bits (default 0).
// NumPayloadBits is re-encoded (+N) so the content block stays self-consistent. N=0 = exact stock behavior.
static int32 GetPayBits()
{
	static int32 Cached = []{ int32 v = 0; FParse::Value(FCommandLine::Get(), TEXT("paybits="), v); return v; }();
	return Cached;
}
static int32 GetPayAt()
{
	static int32 Cached = []{ int32 v = 25; FParse::Value(FCommandLine::Get(), TEXT("payat="), v); return v; }();
	return Cached;
}
static uint32 GetPayPattern()
{
	static uint32 Cached = []{ int32 v = 0; FParse::Value(FCommandLine::Get(), TEXT("paypat="), v); return (uint32)v; }();
	return Cached;
}

// S88 POST-STABLE inject — the payload-splice sweep (paybits=16) did NOT change the "field 12" failure, proving
// the divergence is NOT in the array payload but BEFORE it: seed=0 (bHasRepLayout=0, NO NumPayloadBits/payload
// read) HOLDS while every non-empty seed fails identically ⇒ the client reads an EXTRA header field AFTER the
// stable bit (before NumPayloadBits) that the stub doesn't write, so it reads NumPayloadBits from a shifted
// position and mis-bounds the payload. -postbits=M injects M bits right after the stable bit (before the
// re-encoded NumPayloadBits); -postpat=P is the LSB-first pattern. Sweep M to align the client's NumPayloadBits read.
static int32 GetPostBits()
{
	static int32 Cached = []{ int32 v = 0; FParse::Value(FCommandLine::Get(), TEXT("postbits="), v); return v; }();
	return Cached;
}
static uint32 GetPostPattern()
{
	static uint32 Cached = []{ int32 v = 0; FParse::Value(FCommandLine::Get(), TEXT("postpat="), v); return (uint32)v; }();
	return Cached;
}

bool ALokiGameState::ReplicateSubobjects(UActorChannel* Channel, FOutBunch* Bunch, FReplicationFlags* RepFlags)
{
	if (kEnableServerAuthConfig && ServerAuthConfig && Channel && Channel->Connection && Bunch)
	{
		// Write the FULL content block (bHasRepLayout + bIsActor + GUID + stable-bit + payload-len + payload)
		// into a SCRATCH bunch, then re-emit it into the real Bunch with kInjectBits extra bits SPLICED in
		// right AFTER the subobject GUID. This is the only lever: WriteContentBlockHeader/ReplicateSubobject
		// are non-virtual and the payload is generated deep inside FObjectReplicator::ReplicateProperties ->
		// WriteContentBlockPayload, so we reuse the engine's correct block and splice the extra bit-field the
		// SUPERVIVE client's modified subobject deserialization expects between the GUID and the stable bit.
		FOutBunch Scratch(Channel, false);
		const bool bWrote = Channel->ReplicateSubobject(ServerAuthConfig, Scratch, *RepFlags);
		const int64 Total = Scratch.GetNumBits();
		// S89: do NOT early-return when the property block wrote nothing (bWrote=false — e.g. seed=0's empty
		// array on every rep after the initial one) IF a toggle-RPC broadcast is armed; the RPC path below must
		// still run. The property-emit code below is a clean no-op when Total<=0 (the `else { AppendRange(0,
		// Total); }` branch appends nothing).
		if ((!bWrote || Total <= 0 || Scratch.IsError()) && PendingToggleRPCUpdates <= 0)
		{
			return bWrote;
		}

		// Splice point = bHasRepLayout(1b) + bIsActor(1b) + GUID (SerializeIntPacked64 of ObjectId, 8 bits per
		// 7-bit group). Compute the GUID's on-wire bit length from its value.
		FNetGUIDCache* Cache = (Channel->Connection->Driver && Channel->Connection->Driver->GuidCache.IsValid())
		                           ? Channel->Connection->Driver->GuidCache.Get() : nullptr;
		const FNetworkGUID CompGUID = Cache ? Cache->GetOrAssignNetGUID(ServerAuthConfig) : FNetworkGUID();
		int32 GuidGroups = 1;
		for (uint64 t = CompGUID.ObjectId >> 7; t != 0; t >>= 7) { ++GuidGroups; }
		const int64 SpliceBit = 2 + (int64)GuidGroups * 8;

		Bunch->bReliable |= Scratch.bReliable;

		auto AppendRange = [&](int64 StartBit, int64 NumBits)
		{
			if (NumBits <= 0) { return; }
			TArray<uint8> Tmp;
			Tmp.AddZeroed((int32)((NumBits + 7) / 8));
			const uint8* Src = Scratch.GetData();
			for (int64 i = 0; i < NumBits; ++i)
			{
				const int64 sb = StartBit + i;
				const uint8 b = (Src[sb >> 3] >> (sb & 7)) & 1u;
				Tmp[i >> 3] |= (uint8)(b << (i & 7));
			}
			Bunch->SerializeBits(Tmp.GetData(), NumBits);
		};

		// Read a SerializeIntPacked value out of the SCRATCH bunch at a bit offset (to recover NumPayloadBits
		// and its on-wire width so the payload splice can re-encode it). 8-bit groups, bit0=continuation.
		auto ReadPackedFromScratch = [&](int64 StartBit, uint32& OutVal, int64& OutBits)
		{
			const uint8* Src = Scratch.GetData();
			uint32 val = 0; int shift = 0; int64 p = StartBit;
			for (int g = 0; g < 5; ++g)
			{
				uint8 byte = 0;
				for (int k = 0; k < 8; ++k)
				{
					const int64 sb = p + k;
					byte |= (uint8)((((Src[sb >> 3] >> (sb & 7)) & 1u)) << k);
				}
				p += 8;
				val |= (uint32)(byte >> 1) << shift;
				shift += 7;
				if (!(byte & 1)) break;
			}
			OutVal = val; OutBits = p - StartBit;
		};

		const int32  InjectBits    = GetInjectBits();
		const uint32 InjectPattern = GetInjectPattern();
		const int32  PayBits       = GetPayBits();
		const int32  PostBits      = GetPostBits();
		const int64 EmitStart = Bunch->GetNumBits();
		if (SpliceBit <= Total)
		{
			AppendRange(0, SpliceBit);                        // header up through the GUID
			for (int32 k = 0; k < InjectBits; ++k)            // N injected bits (LSB-first pattern)
			{
				Bunch->WriteBit((InjectPattern >> k) & 1u);
			}
			if (PayBits == 0 && PostBits == 0)
			{
				AppendRange(SpliceBit, Total - SpliceBit);    // stable bit + payload length + payload (stock)
			}
			else
			{
				// S88 splice. Scratch layout after the GUID: [stable @ SpliceBit][NumPayloadBits packed @
				// SpliceBit+1][payload]. Emit: stable bit, POST-stable inject (PostBits, before NumPayloadBits),
				// re-encoded NumPayloadBits (+PayBits), then the payload with PayBits inserted/removed at payat.
				AppendRange(SpliceBit, 1);                    // the stable bit
				const uint32 PostPat = GetPostPattern();
				for (int32 k = 0; k < PostBits; ++k)          // POST-stable injected bits (before NumPayloadBits)
				{
					Bunch->WriteBit(k < 32 ? ((PostPat >> k) & 1u) : 0u);
				}
				uint32 OldNPB = 0; int64 NpbBits = 0;
				ReadPackedFromScratch(SpliceBit + 1, OldNPB, NpbBits);
				const int64 PayStart = SpliceBit + 1 + NpbBits;
				const int32 PayAt    = FMath::Clamp(GetPayAt(), 0, (int32)OldNPB);
				const uint32 PayPat  = GetPayPattern();
				const int64 NewNPB   = (int64)OldNPB + PayBits;
				uint32 NewNPBEnc     = (uint32)FMath::Max<int64>(NewNPB, 0);
				Bunch->SerializeIntPacked(NewNPBEnc);                              // re-encoded payload length
				if (PayBits >= 0)
				{
					AppendRange(PayStart, PayAt);                                  // payload[0..PayAt)
					for (int32 k = 0; k < PayBits; ++k)                            // PayBits inserted bits
					{
						Bunch->WriteBit(k < 32 ? ((PayPat >> k) & 1u) : 0u);
					}
					AppendRange(PayStart + PayAt, (int64)OldNPB - PayAt);          // payload[PayAt..end)
				}
				else
				{
					const int64 Rem = FMath::Min<int64>(-PayBits, (int64)OldNPB - PayAt);
					AppendRange(PayStart, PayAt);                                  // payload[0..PayAt)
					AppendRange(PayStart + PayAt + Rem, (int64)OldNPB - PayAt - Rem); // payload[PayAt+Rem..end)
				}
			}
		}
		else
		{
			AppendRange(0, Total);                            // fallback: emit unspliced
		}

		static bool bLoggedSAC = false;
		if (!bLoggedSAC)
		{
			bLoggedSAC = true;
			const int64 Emitted = Bunch->GetNumBits() - EmitStart;
			UE_LOG(LogLokiGameStateStub, Display,
			       TEXT("ReplicateSubobjects SPLICE (S87/S88): compGUID=%s ObjectId=%llu guidGroups=%d spliceBit=%lld "
			            "scratchBits=%lld injectBits=%d pattern=0x%X postBits=%d payBits=%d payAt=%d payPat=0x%X -> emittedBits=%lld"),
			       *CompGUID.ToString(), (unsigned long long)CompGUID.ObjectId, GuidGroups, SpliceBit,
			       Total, InjectBits, InjectPattern, PostBits, PayBits, GetPayAt(), GetPayPattern(), Emitted);

			// Dump the emitted (spliced) content block, LSB-first, for offline decode_cb.py verification.
			if (Emitted > 0 && Emitted < 8192)
			{
				const uint8* Data = Bunch->GetData();
				const int64 NumBytes = (Emitted + 7) / 8;
				TArray<uint8> Buf;
				Buf.AddZeroed((int32)NumBytes);
				for (int64 i = 0; i < Emitted; ++i)
				{
					const int64 sb = EmitStart + i;
					Buf[i >> 3] |= (uint8)(((Data[sb >> 3] >> (sb & 7)) & 1u) << (i & 7));
				}
				FString Hex;
				Hex.Reserve((int32)NumBytes * 3);
				for (int64 i = 0; i < NumBytes; ++i) { Hex.Appendf(TEXT("%02X "), Buf[i]); }
				UE_LOG(LogLokiGameStateStub, Display,
				       TEXT("ServerAuthConfig SPLICED BLOCK (S87): startBit=%lld numBits=%lld bytes(LSB): %s"),
				       EmitStart, Emitted, *Hex);
			}
		}

		// ★ S89 RPC ROUTE — emit hand-rolled, header-spliced MulticastSetGameFeatureToggle content block(s).
		// The RPC RESOLVES the component on the client (unlike the property array, S88), but the engine's own RPC
		// write (ProcessRemoteFunction → PrepareForRemoteFunction, non-virtual) omits the 11-bit subobject-header
		// field, so the client overflows NumPayloadBits (live-proven). Rebuild the RPC content block via the
		// engine helpers (WriteFieldHeaderAndPayload + WriteContentBlockPayload) into a scratch bunch, then splice
		// the SAME InjectBits after the GUID + emit. The RPC's bHasRepLayout=0 block only needs the header fix.
		bool bEmittedRPC = false;
		if (PendingToggleRPCUpdates > 0)
		{
			UNetDriver* Driver = Channel->Connection->Driver;
			UFunction* Func = ULokiServerAuthConfig::StaticClass()->FindFunctionByName(TEXT("MulticastSetGameFeatureToggle"));
			const FClassNetCache* ClassCache = (Driver && Driver->NetCache.IsValid())
			    ? Driver->NetCache->GetClassNetCache(ULokiServerAuthConfig::StaticClass()) : nullptr;
			const FFieldNetCache* FieldCache = (ClassCache && Func) ? ClassCache->GetFromField(Func) : nullptr;
			TSharedPtr<FRepLayout> RpcRepLayout = (Driver && Func) ? Driver->GetFunctionRepLayout(Func) : nullptr;
			if (Func && ClassCache && FieldCache && RpcRepLayout.IsValid())
			{
				Bunch->bReliable = true;   // toggle delivery must be reliable
				bEmittedRPC = true;
				const int32 Count = FMath::Clamp(ToggleRPCCount, 0, 255);
				FString FirstHex;
				for (int32 i = 0; i < Count; ++i)
				{
					// param frame {uint8 Toggle; uint8 bValue;} — matches the RE'd 2-byte layout (Toggle@0, bValue@1)
					uint8 Parms[2] = { (uint8)i, (uint8)1 };
					FNetBitWriter ParamWriter(Channel->Connection->PackageMap, 0);
					RpcRepLayout->SendPropertiesForRPC(Func, Channel, ParamWriter, Parms);
					FNetBitWriter FieldWriter(Channel->Connection->PackageMap, 0);
					Channel->WriteFieldHeaderAndPayload(FieldWriter, ClassCache, FieldCache, nullptr, ParamWriter);
					FOutBunch RpcScratch(Channel, false);
					Channel->WriteContentBlockPayload(ServerAuthConfig, RpcScratch, /*bHasRepLayout=*/false, FieldWriter);

					const int64 RTotal = RpcScratch.GetNumBits();
					const uint8* RSrc = RpcScratch.GetData();
					if (i == 0 && RTotal > 0 && RTotal < 4096)
					{
						const int64 NB = (RTotal + 7) / 8;
						for (int64 b = 0; b < NB; ++b) { FirstHex.Appendf(TEXT("%02X "), RSrc[b]); }
					}
					auto RAppend = [&](int64 StartBit, int64 NumBits)
					{
						if (NumBits <= 0) { return; }
						TArray<uint8> Tmp; Tmp.AddZeroed((int32)((NumBits + 7) / 8));
						for (int64 b = 0; b < NumBits; ++b) { const int64 sb = StartBit + b; Tmp[b >> 3] |= (uint8)(((RSrc[sb >> 3] >> (sb & 7)) & 1u) << (b & 7)); }
						Bunch->SerializeBits(Tmp.GetData(), NumBits);
					};
					if (SpliceBit <= RTotal)
					{
						RAppend(0, SpliceBit);                                       // header through the GUID
						for (int32 k = 0; k < InjectBits; ++k) { Bunch->WriteBit((InjectPattern >> k) & 1u); }
						RAppend(SpliceBit, RTotal - SpliceBit);                      // stable + NumPayloadBits + field
					}
					else { RAppend(0, RTotal); }
				}
				static bool bLoggedRPC = false;
				if (!bLoggedRPC)
				{
					bLoggedRPC = true;
					UE_LOG(LogLokiGameStateStub, Display,
					       TEXT("ReplicateSubobjects S89-RPC: emitted %d spliced MulticastSetGameFeatureToggle blocks "
					            "(injectBits=%d, spliceBit=%lld). First RPC scratch(LSB, pre-splice): %s"),
					       Count, InjectBits, SpliceBit, *FirstHex);
				}
			}
			else
			{
				static bool bLoggedRPCFail = false;
				if (!bLoggedRPCFail)
				{
					bLoggedRPCFail = true;
					UE_LOG(LogLokiGameStateStub, Warning,
					       TEXT("ReplicateSubobjects S89-RPC MISSING deps (Func=%d ClassCache=%d FieldCache=%d RepLayout=%d) — no RPC blocks."),
					       Func ? 1 : 0, ClassCache ? 1 : 0, FieldCache ? 1 : 0, RpcRepLayout.IsValid() ? 1 : 0);
				}
			}
			--PendingToggleRPCUpdates;
		}

		return bWrote || bEmittedRPC;
	}

	return Super::ReplicateSubobjects(Channel, Bunch, RepFlags);
}
