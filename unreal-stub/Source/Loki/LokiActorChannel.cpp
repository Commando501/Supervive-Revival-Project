#include "LokiActorChannel.h"
#include "Net/DataBunch.h"

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
	}

	Super::ReceivedBunch(Bunch);
}
