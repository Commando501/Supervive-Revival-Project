#include "LokiActorChannel.h"
#include "Net/DataBunch.h"
#include "Serialization/BitReader.h"
#include "GameFramework/PlayerController.h"
#include "UObject/Class.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiActorChannel, Log, All);

void ULokiActorChannel::ReceivedBunch(FInBunch& Bunch)
{
	// Session 25: log the raw bunch bytes with metadata so we can identify
	// which bunch fails during ServerVerifyViewTarget RPC dispatch. UE's own
	// ProcessBunch will run inside Super and log the mismatch — we just want
	// the byte payload correlated with ChIndex/ChSequence.

	// Save reader position before we peek at anything.
	const int64 StartPosBits = Bunch.GetPosBits();
	const int64 TotalNumBits = Bunch.GetNumBits();

	// Copy the remaining bunch bytes (from current pos to end) into a scratch
	// buffer. UE FInBunch stores bits in an internal buffer we can access via
	// GetData().
	const int64 RemainingBits = TotalNumBits - StartPosBits;
	if (RemainingBits > 0 && RemainingBits < 1024 * 8 * 4)  // sanity cap
	{
		// Extract the remaining bits by reading from FInBunch. We use
		// FBitReaderMark to reset the position so Super sees a fresh bunch.
		FBitReaderMark Mark(Bunch);

		const int64 RemainingBytes = (RemainingBits + 7) / 8;
		TArray<uint8> Buf;
		Buf.AddZeroed(RemainingBytes);
		Bunch.SerializeBits(Buf.GetData(), RemainingBits);

		// Pop the mark so Super sees the bunch as if we never touched it.
		Mark.Pop(Bunch);

		FString HexDump;
		HexDump.Reserve(RemainingBytes * 3);
		for (int64 i = 0; i < RemainingBytes; ++i)
		{
			HexDump.Appendf(TEXT("%02X "), Buf[i]);
		}

		UE_LOG(LogLokiActorChannel, Verbose,
		       TEXT("ReceivedBunch: ChIndex=%d ChSeq=%d bReliable=%d bOpen=%d bClose=%d NumBits=%lld StartPos=%lld remaining=%lld bits"),
		       ChIndex, Bunch.ChSequence, (int32)Bunch.bReliable, (int32)Bunch.bOpen, (int32)Bunch.bClose,
		       TotalNumBits, StartPosBits, RemainingBits);
		UE_LOG(LogLokiActorChannel, Verbose,
		       TEXT("ReceivedBunch: bytes (%lld) %s"), RemainingBytes, *HexDump);

		// Session 33: if this bunch shape matches the ServerVerifyViewTarget
		// bunch we're targeting (2339 bits total, per session 25's capture),
		// try the straight-through property walk over the runtime bytes and
		// log the decoded values. This is diagnostic-only — Super still fires
		// and will fail (SUPERVIVE's client patched out has-value bits, so
		// stock UE's ReceivePropertiesForRPC will misread). See
		// docs/session-33-hasvalue-divergence.md.
		if (TotalNumBits == 2339)
		{
			ParseAndLogServerVerifyViewTargetBunch(Buf.GetData(), TotalNumBits);
		}
	}

	Super::ReceivedBunch(Bunch);
}

// Read a bit from a LSB-first packed byte buffer.
static FORCEINLINE uint8 ReadBitAt(const uint8* Buf, int64 BitPos)
{
	return (Buf[BitPos / 8] >> (BitPos % 8)) & 1u;
}

// Copy NumBits from Src (starting at SrcBit) into a fresh LSB-packed buffer
// (Dst) whose bit 0 is aligned to byte 0.
static void ExtractBits(const uint8* Src, int64 SrcBit, int64 NumBits, uint8* Dst)
{
	FMemory::Memzero(Dst, (NumBits + 7) / 8);
	for (int64 i = 0; i < NumBits; ++i)
	{
		const uint8 B = ReadBitAt(Src, SrcBit + i);
		Dst[i / 8] |= (B << (i % 8));
	}
}

void ULokiActorChannel::ParseAndLogServerVerifyViewTargetBunch(const uint8* BunchBytes, int64 BunchNumBits)
{
	// The captured bunch structure (session 25 decode):
	//   Content block header (2 bits): bOutHasRepLayout + bIsActor
	//   Outer NumPayloadBits (SerializeIntPacked, 16 bits): 2321
	//   Field header:
	//     RepIndex (SerializeInt, MaxIndex+1, ~7 bits): 94
	//     Inner NumPayloadBits (SerializeIntPacked, 16 bits): 2298
	//   RPC arg struct starts at bit 41.
	//
	// We hard-code the 41-bit offset for now; a real implementation would
	// parse the header dynamically.
	constexpr int64 kRPCStartBit = 41;
	constexpr int64 kRPCNumBits  = 2298;

	if (BunchNumBits < kRPCStartBit + kRPCNumBits)
	{
		UE_LOG(LogLokiActorChannel, Verbose,
		       TEXT("ParseAndLog: bunch too small (%lld < %lld), skipping"),
		       BunchNumBits, kRPCStartBit + kRPCNumBits);
		return;
	}

	// Extract the 2298 RPC arg bits into a fresh buffer.
	constexpr int32 kArgBytes = (kRPCNumBits + 7) / 8;
	uint8 ArgBuf[kArgBytes];
	ExtractBits(BunchBytes, kRPCStartBit, kRPCNumBits, ArgBuf);

	// Find the injected UFunction on APlayerController.
	UClass* PCClass = APlayerController::StaticClass();
	if (!PCClass)
	{
		return;
	}
	UFunction* Func = PCClass->FindFunctionByName(
		FName(TEXT("ServerVerifyViewTarget")),
		EIncludeSuperFlag::ExcludeSuper);
	if (!Func || Func->NumParms == 0)
	{
		UE_LOG(LogLokiActorChannel, Warning,
		       TEXT("ParseAndLog: no injected UFunction found"));
		return;
	}

	FBitReader Reader(ArgBuf, kRPCNumBits);
	void* Parms = FMemory_Alloca(Func->ParmsSize);
	FMemory::Memzero(Parms, Func->ParmsSize);
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		FProperty* Prop = *It;
		if (!(Prop->PropertyFlags & CPF_Parm)) break;
		if (!(Prop->PropertyFlags & CPF_ZeroConstructor))
		{
			Prop->InitializeValue_InContainer(Parms);
		}
	}

	UE_LOG(LogLokiActorChannel, Display,
	       TEXT("LiveReplay START: Func=%s NumParms=%d ParmsSize=%d Reader.Max=%lld"),
	       *Func->GetName(), Func->NumParms, Func->ParmsSize, Reader.GetNumBits());

	int32 ParamIdx = 0;
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		FProperty* Prop = *It;
		if (!(Prop->PropertyFlags & CPF_Parm)) break;

		const int32 PosBefore = Reader.GetPosBits();

		if (FObjectProperty* ObjProp = CastField<FObjectProperty>(Prop))
		{
			// FObjectProperty::NetSerializeItem needs a UPackageMap, but this
			// channel already has one on Connection. However the NetGUID data
			// in a live bunch depends on client's NetGUID cache state; for
			// diagnostic logging we just skip 18 bits (session-30 measured
			// AActor* consumption) like the boot-time SelfReplay.
			uint8 Skip[8] = {};
			Reader.SerializeBits(Skip, 18);
			UE_LOG(LogLokiActorChannel, Display,
			       TEXT("  [%d] %s (%s) SKIPPED 18 bits: Pos %d -> %d"),
			       ParamIdx, *Prop->GetName(), *Prop->GetClass()->GetName(),
			       PosBefore, Reader.GetPosBits());
		}
		else
		{
			void* PropData = Prop->ContainerPtrToValuePtr<void>(Parms);
			Prop->NetSerializeItem(Reader, /*Map=*/nullptr, PropData);
			const int32 PosAfter = Reader.GetPosBits();
			const bool bError = Reader.IsError();
			UE_LOG(LogLokiActorChannel, Display,
			       TEXT("  [%d] %s (%s) consumed %d bits: Pos %d -> %d error=%d"),
			       ParamIdx, *Prop->GetName(), *Prop->GetClass()->GetName(),
			       PosAfter - PosBefore, PosBefore, PosAfter, bError ? 1 : 0);

			if (Prop->IsA<FStrProperty>() && !bError)
			{
				const FString& S = *reinterpret_cast<FString*>(PropData);
				UE_LOG(LogLokiActorChannel, Display, TEXT("      FString = \"%s\""), *S);
			}

			if (bError)
			{
				UE_LOG(LogLokiActorChannel, Warning,
				       TEXT("  LiveReplay OVERFLOW at param [%d] %s"),
				       ParamIdx, *Prop->GetName());
				break;
			}
		}
		++ParamIdx;
	}

	const int32 FinalPos = Reader.GetPosBits();
	const int32 Leftover = kRPCNumBits - FinalPos;
	UE_LOG(LogLokiActorChannel, Display,
	       TEXT("LiveReplay END: FinalPos=%d Leftover=%d IsError=%d"),
	       FinalPos, Leftover, Reader.IsError() ? 1 : 0);

	// Destroy allocated params.
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		FProperty* Prop = *It;
		if (!(Prop->PropertyFlags & CPF_Parm)) break;
		Prop->DestroyValue_InContainer(Parms);
	}
}
