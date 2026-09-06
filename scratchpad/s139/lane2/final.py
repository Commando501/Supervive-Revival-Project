import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import vslots
from grade import grade, extent
L=vslots(0x088F8570,413); C=vslots(0x07FBED58,413)
NAMES={
 122:'UActorComponent::TickComponent',
 153:'UMovementComponent::GetMaxSpeed',
 154:'IsExceedingMaxSpeed',
 156:'UMovementComponent::ShouldSkipUpdate',
 159:'SetUpdatedComponent',
 188:'UCharacterMovementComponent::RequestPathMove  [POSITIVE CONTROL]',
 192:'IsCrouching',193:'IsFalling',194:'IsMovingOnGround',195:'IsSwimming',196:'IsFlying',
 199:'AddInputVector',200:'ConsumeInputVector',
 204:'ComputeAnalogInputModifier',
 206:'SetMovementMode',
 215:'HasValidData',
 228:'StartNewPhysics',
 246:'CalcVelocity',247:'GetMaxJumpHeight',249:'GetMinAnalogSpeed',
 250:'GetMaxAcceleration',251:'GetMaxBrakingDeceleration',
 262:'PhysFalling',
 274:'ControlledCharacterMove',
 286:'(PerformMovement-tail virtual, unnamed)',
 288:'SetDefaultMovementMode',
 299:'IsWalkable',
 302:'PhysWalking',303:'PhysNavWalking',304:'PhysFlying',305:'PhysSwimming',306:'PhysCustom',
 317:'K2_FindFloor',319:'K2_ComputeFloorDist',325:'CapsuleTouched',
 327:'ConstrainInputAcceleration',328:'ScaleInputAcceleration',
 341:'PerformMovement',
 409:'PhysDashing (engine-added MOVE_Dashing)',
 412:'IsDashing',
}
print("%-4s %-7s %-46s %-11s %-24s %-11s %-22s %s"%("slot","disp","name","CMC","gradeCMC","LOKI","gradeLOKI","OVERRIDE?"))
for i in sorted(NAMES):
    gc,_,_=grade(C[i]); gl,exl,_=grade(L[i])
    ov = "OVERRIDE" if L[i]!=C[i] else "inherited"
    sz = (exl[1]-exl[0]) if exl else -1
    print("%-4d 0x%04X  %-46s 0x%07X %-24s 0x%07X %-22s %s (%dB)"%(i,i*8,NAMES[i],C[i],gc,L[i],gl,ov,sz))
