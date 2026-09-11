# LANE V4-bit ADVERSARIAL REFUTATION — raw evidence (dumps/merged12.dump.exe, ImageBase 0x7ff6af000000, file off == RVA)

PE: 10 sections, all PtrRaw==VA. .text VA 0x1000 VS 0x7649000. .rdata 0x764a000. .data 0x99c7000.
.text pages nonzero: 16772/30281 = 55.39%

## (a) setter bytes  [CONFIRMED]
0x45cf990 83 89 88 04 00 00 01 c3   or dword [rcx+0x488],1    bStartAILogicOnPossess
0x45cf9a0 83 89 88 04 00 00 02 c3   or dword [rcx+0x488],2    bStopAILogicOnUnposses
0x45cf9e0 83 89 88 04 00 00 04 c3   or dword [rcx+0x488],4    bLOSflag
0x45cf9f0 83 89 88 04 00 00 08 c3   or dword [rcx+0x488],8    bSkipExtraLOSChecks
0x45cfa00 83 89 88 04 00 00 10 c3   or dword [rcx+0x488],0x10 bAllowStrafe
0x45cfa10 83 89 88 04 00 00 20 c3   or dword [rcx+0x488],0x20 bWantsPlayerState
0x45cfa20 83 89 88 04 00 00 40 c3   or dword [rcx+0x488],0x40 bSetControlRotationFromPawnOrientation
page 0x45cf000 nonzero 3840/4096 (LIT). None equals any of the 5 known folds.

## (b) naming  [CONFIRMED, with an address-arithmetic error in the lane's prose]
correct VA = 0x7ff6af000000 + 0x45CFA10 = 0x7FF6B35CFA10 (lane printed 0x7FF6AF45CFA10 -> 0 hits)
qword scan 0x7FF6B35CFA10 -> exactly 1 hit @ 0x842D248 ; recbase 0x842D248-0x38 = 0x842D210
all seven ptr sites: 0x842d108/148/188/1c8/208/248/288, each multiplicity 1, stride 0x40
FBoolPropertyParams layout verified = stock UE:
  +0x00 NameUTF8  +0x08 RepNotify(0)  +0x10 PropertyFlags  +0x18 genflags  +0x1C objflags
  +0x20/+0x28 Setter/Getter(0)  +0x30 ArrayDim  +0x32 ElementSize  +0x34 SizeOfOuter  +0x38 SetBitFunc
name @0x842D8A0 = "bWantsPlayerState" (ASCII, exactly 1 occurrence image-wide;
  control: "PathFollowingComponent" ASCII = 3 occurrences, so duplicates WOULD be found)

## (c) owner  [CONFIRMED + a 3rd independent instrument]
0x842D210 referenced by exactly 1 qword @0x842D4C8 -> PropPointers[5] of array 0x842D4A0 (15 slots, idx15 is not a record)
array referenced by exactly 1 qword @0x842D738 -> FClassParams 0x842D710
  +0x00 0x45CCB60  +0x08 -> "Engine"  +0x28 -> 0x842D4A0  +0x38 0x10078162  +0x3C 0x008802A4
  bitfield decode: deps=2 funcs=22 props=15 interfaces=4   (15 == 15 enumerated)
0x45CCBA6 lea rdx,[rip+0x3E604C5] -> 0x842D072 L"AIController"   (recomputed by machine)
0x45CCBB5 lea rcx,[rip+0x3E5A824] -> 0x84273E0 L"/Script/AIModule"
NEW: 0x45CCBF5 mov dword [rsp+0x20], 0x4E0  == InSize passed to GetPrivateStaticClassBody
     -> sizeof(AAIController)=0x4E0 measured WITHOUT the UHT record.
     AController: 0x36B18D5 mov dword [rsp+0x20], 0x450.
PropertyFlags 0x0010000000000005 = CPF_Edit|CPF_BlueprintVisible|CPF_NativeAccessSpecifierPublic
POSITIVE CONTROL the lane lacked: AController::PlayerState rec 0x800BF80 propflags
     0x0114000100000034 has CPF_Net(0x20) SET -> the "not CPF_Net" test can fire.

## (d) uniqueness  [CONFIRMED, on a strictly BROADER census than the lane's]
my census: every 8-aligned .rdata/.data record with (genflags & 0x3f)==0x0C, valid name, tail->.text
  = 13,104 records (10,310 genflags 0x4C NativeBool + 2,791 genflags 0x0C + 3 junk),
  43 of them with NON-NULL RepNotify.  The lane's filter (genflags==0x0C AND RepNotify==0, n=2778)
  EXCLUDES the 10,310 and the 43 -- two unstated blind spots.
  ALL 13,104 setters decoded (0 undecoded), 0 on dark pages.
  Exactly 7 write disp 0x488 -> the same seven, masks 0x01..0x40, no gaps, no duplicates.

## (e) offset ownership  [CONFIRMED]
AController bAttachToPawn rec 0x800C210, SizeOfOuter 0x450, setter 0x36B3B30 =
  80 89 48 04 00 00 01 c3 = or byte [rcx+0x448],1   (different offset, byte-sized)
AAIController first non-bool member PathFollowingComponent Offset field (+0x32) = 1168 = 0x490.

## blocker bytes  [CONFIRMED verbatim]
045D6D10 40 53 / 48 83 ec 20 / 48 8b d9 / e8 e2 c2 10 ff -> 0x36E3000
045D6D1E f6 83 88 04 00 00 20   test byte [rbx+0x488],0x20
045D6D25 74 25                  je 0x45D6D4C
045D6D27 8b 43 0c / c1 e8 1e / f6 d0 / a8 01 / 74 19   (ObjectFlags@+0x0C bit30 must be clear)
045D6D36 e8 15 7a db fe -> 0x338E750 ; 045D6D3B 83 f8 03 cmp eax,3 ; 74 0c
045D6D46 ff 90 88 08 00 00      call qword [rax+0x888]   (0x888/8 = 273)
cross-check 03BBF3EE e8 5d f3 7c ff -> 0x338E750 ; 03BBF3F3 83 f8 03

## NOT DISCLOSED BY THE LANE: a SECOND reader of bit 0x20, on the POSSESSION path
045D5E55 f6 87 88 04 00 00 20   test byte [rdi+0x488],0x20   je 0x45D5E8C
inside function 0x45D5DD0 (2 vtable slots: 0x8431C00, 0x845B328; 1 rel32 caller 0x563BF59).
That function reads [rdi+0x490] (=PathFollowingComponent), virtual-calls [+0x4c0] on it,
then on bit 0x20 builds FName idx 0x140 and calls vtable [+0x7f8]  == AAIController::OnPossess /
ChangeState(NAME_Playing) shape.  [I] on the name; [M] that a 2nd bit-0x20 branch exists.

## clearing sites  [CONFIRMED; ctor transcription INCOMPLETE; attribution UPGRADED [I]->[M]]
AAIController ctor = 0x45D17D0 [M]: InClassConstructor 0x45D0770 =
  48 8b 01 / 48 85 c0 / 74 0b / 48 8b d1 / 48 8b c8 / e9 4d 10 00 00
  rel32 0x104D, next 0x45D0783 -> 0x45D17D0.
Inside it, +0x488 is touched FOUR times, not two:
  045D18B2 83 8f 88 04 00 00 40  or dword [rdi+0x488],0x40
  045D19A2 8b 8f 88 04 00 00     mov ecx,[rdi+0x488]
  045D19AD 83 e1 df / 045D19B0 83 c9 08 / 045D19B3 89 8f 88 04 00 00   (STORE #1)
  045D19B9 83 e1 fe / 045D19C3 83 c9 02 / 045D19CF 89 8f 88 04 00 00   (STORE #2, lane omitted)
  bit 0x20 clear after both -> conclusion unaffected.
0x554B5A9 83 a7 88 04 00 00 df  and dword [rdi+0x488],0xFFFFFFDF
  owner func 0x554B430 (pdata_union row 0x554B430..0x554B671).
  ALokiBotController::GetPrivateStaticClass = 0x52EA940:
     052EA986 lea rdx,[rip+0x35DF2E5] -> 0x88C9C72 L"LokiBotController"
     052EA995 lea rcx,[rip+0x352A924] -> 0x88152C0 L"/Script/Loki"
     052EA9D5 mov dword [rsp+0x20], 0x6A8    (sizeof)
     InClassConstructor slot ([r11-0x30]) = 0x52EB760 =
       48 8b 09 / 48 85 c9 / 0f 85 c4 fc 25 00 / c3
       rel32 0x25FCC4, next 0x52EB76C -> 0x554B430
  => 0x554B430 IS ALokiBotController::ALokiBotController  [M]
REFUTED SUPPORT: lane said "No ASCII class-name string for LokiBotController ... (0 hits each)".
  ASCII "LokiBotController" has 1 hit @0x8B121C6 inside
  "C:\TheoryCraft\build-staging\Loki\Source\Loki\AI\Bots\LokiBotController.cpp".
  And the AAIController route used the WIDE literal, which exists and IS lea'd.

## scanner control note
KERNEL32 ASCII occurrences in this dumped image = 0 (wide = 2).
The repo's suggested "also scan for KERNEL32" ASCII control FAILS HERE and reads as a broken scanner.
