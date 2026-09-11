#include "LokiWorldSettingsStub.h"
#include "GameFramework/Actor.h"
#include "Net/UnrealNetwork.h"
#include "UObject/UnrealType.h"

// Non-push GetLifetimeReplicatedProps (S70 mirror pattern). We deliberately do NOT call Super
// (AWorldSettings -> AInfo -> AActor), because AWorldSettings/AInfo register their derived props push-based via
// the engine's DOREPLIFETIME_WITH_PARAMS_FAST, which trips the CoreNet.h:331 bIsPushBased assert against the
// stub's non-push ClassReps rebuild. Instead we call AActor::GetLifetimeReplicatedProps directly (exactly what
// the S70 GameState / PC / PlayerState mirrors do — AActor's props ARE consistent with the rebuild), then
// register every replicated prop declared by AInfo/AWorldSettings/this class NON-PUSH (bIsPushBased=false,
// COND_None) at its rebuilt RepIndex.
void ALokiWorldSettings::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const
{
	AActor::GetLifetimeReplicatedProps(Out);

	int32 Added = 0;
	for (TFieldIterator<FProperty> It(GetClass()); It; ++It)
	{
		FProperty* P = *It;
		if (!(P->PropertyFlags & CPF_Net))
		{
			continue;
		}
		UClass* OwnerCls = P->GetOwnerClass();
		// Skip props owned by AActor or its supers (AActor::GetLifetimeReplicatedProps already added them).
		// AActor->IsChildOf(OwnerCls) is true exactly when OwnerCls is AActor or an ancestor of AActor.
		if (!OwnerCls || AActor::StaticClass()->IsChildOf(OwnerCls))
		{
			continue;
		}
		Out.Add(FLifetimeProperty(P->RepIndex)); // COND_None, RepNotify default, bIsPushBased=false
		++Added;
	}

	UE_LOG(LogTemp, Display,
	       TEXT("ALokiWorldSettings::GetLifetimeReplicatedProps: registered %d derived props NON-PUSH (total lifetime %d)."),
	       Added, Out.Num());
}
