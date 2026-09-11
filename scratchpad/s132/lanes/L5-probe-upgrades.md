# S132 LANE 5 — SPECIFY THE PROBE UPGRADES

Offline only. Zero launches, zero injections, no repo file edited. Every address below was read from
`dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA) with
`scratchpad/fk27/fkdis.py` or a python read of the same image; every RVA was computed by machine.

---

## 0. HEADLINE CLAIMS, GRADED

| # | claim | grade |
|---|---|---|
| H1 | The probe's bool metadata is read from the **LIVE `FBoolProperty`** at `FProperty+0x70..0x73`, and those four offsets are **CORRECT** | **[M]** — `FBoolProperty::SetBoolSize` is inlined at `.text 0x01308F38`; its native branch writes `[rbx+0x70]=ElementSize`, `word[rbx+0x71]=0x0100`, `byte[rbx+0x73]=0xFF` |
| H2 | `fs=1 bo=0 bm=0x01 fm=0xFF` on every bool is **NOT a decode bug** — it is verbatim what the **native-bool branch** stores, and every bool the probe has printed so far is a native bool | **[M]** |
| H3 | The branch selector is `EPropertyGenFlags & 0x40` (`NativeBool`), read from the UHT params at `+0x18` | **[M]** — `0x01308F14 movzx eax,byte[r14+0x18]` … `0x01308F2F shr al,6; not al; test al,1; je <bitfield branch 0x01308F63>` |
| H4 | `AActor::bHidden` → `Offset_Internal 0x68`, `ByteMask 0x80`; `AActor::bAlwaysRelevant` → `Offset_Internal 0x68`, `ByteMask 0x08` | **[M]** — UHT `FBoolPropertyParams` records `.rdata 0x07F1F880` / `0x07F1F730`, `SetBitFunc` at record`+0x38` = `0x03368980` (`or byte [rcx+0x68],0x80`) / `0x032F7100` (`or byte [rcx+0x68],8`) |
| H5 | On the bitfield branch **`FieldMask == ByteMask`**, so the existing `raw & fm` decode is right for bitfields too | **[M]** — `0x01308FBD movzx eax,byte[rbx+0x72]; 0x01308FC1 mov byte[rbx+0x73],al` |
| H6 | `USceneComponent::ComponentVelocity` Offset = **`0x1A0`** | **[M]** — UHT `FGenericPropertyParams` record `.rdata 0x07EDFD40`, Offset field (`uint16 @ +0x32`) = 416. **This UPGRADES S131**, whose own tool (`scratchpad/s131/tools/pod_live_read.py:87`) labels the offset *"[I] from lane 3"* |
| H7 | `FProperty::ElementSize @ +0x34` | **[M]** — `0x01308F49 mov dword [rbx+0x34], r8d`, `r8d` = the params' ElementSize `word[r14+0x32]`. S126 recorded this as **[I] by arithmetic**; it is now measured |
| H8 | `AttachedCrewPods` = pod`+0x490`, `TArray<ALokiDropPod@>` | **[M]** as an Angelscript-bytecode offset (`tools/asdump/out/a/GameMode.DropPhase.LokiDropPod.as.txt:304`, `ADDSi W0:1168` = 0x490; S131 established the ADDSi-operand-is-a-byte-offset rule at 76:0 live agreement). Whether the **live FProperty** agrees is exactly what the patch's cross-check measures — do not pre-empt it |
| H9 | The three additions cannot move the `.text` of `play`, `dropplane_b1only`, `rideable`, `cheatmgr*`, `dropmarkers*`, `phaseladder*` | **[I, strong]** — they live only in functions reachable solely from `PdPodDump`, which is called only under `kRunMode==RM_DROPPOD` / `RM_POOLSPAWN`, and `kRunMode` is a compile-time constant. **Must still be verified by hash, not by argument** (§4) |

**Positive control for the whole §1 measurement.** The same instrument, run over the two properties
this project already holds `[M]` from a *completely different* route (S130's walk of AActor's
114-entry `PropPointers` array), reproduces both exactly:
`bCanEverReplicate` SetBitFunc `0x02078900` = `mov byte [rcx+0x6c],1` (0x6C ✓) and
`bEnablePooling` SetBitFunc `0x03368BF0` = `mov byte [rcx+0x2d3],1` (0x2D3 ✓), both with
genFlags `0x4C` = `Bool|NativeBool`. Two known answers reproduced ⇒ the record layout reading is not
a coincidence.

---

## 1. EXACTLY HOW THE PROBE RESOLVES A PROPERTY, AND HOW IT DECODES A BOOL

### 1.1 Name resolution — `PdFindPropOn`, `tools/sigbypass-mod/tutorial_launch.cpp:9827-9855`

```
9827  static uintptr_t PdFindPropOn(uintptr_t cls,const char* name,uint32_t* offOut,uint32_t* elemOut,
9828                                char* type,size_t tsz,char* sname,size_t ssz,char* owner,size_t osz){
...
9836      for(uintptr_t c=cls; LooksLikePtr(c)&&g<12;
9837          c=(SafeReadable((void*)(c+0x48),8)?*(uintptr_t*)(c+0x48):0), g++){
9838          uintptr_t f=SafeReadable((void*)(c+UFUNC_CHILDPROPS),8)?*(uintptr_t*)(c+UFUNC_CHILDPROPS):0;
9839          int i=0;
9840          while(LooksLikePtr(f)&&i<400){
9841              if(NameIs(f,name)){
9842                  if(offOut &&SafeReadable((void*)(f+FPROP_OFFSET),4))   *offOut =*(uint32_t*)(f+FPROP_OFFSET);
9843                  if(elemOut&&SafeReadable((void*)(f+FPROP_ELEMSIZE),4)) *elemOut=*(uint32_t*)(f+FPROP_ELEMSIZE);
9844                  PdTypeOf(f,type,tsz,sname,ssz);
...
9851              uintptr_t nx=SafeReadable((void*)(f+FIELD_NEXT),8)?*(uintptr_t*)(f+FIELD_NEXT):0; f=nx; i++;
```

Walk `UStruct::SuperStruct` (`+0x48`); at each level walk `ChildProperties`
(`UFUNC_CHILDPROPS = 0x58`) through `FField::Next` (`FIELD_NEXT = 0x18`), comparing FName strings with
`strcmp` (`NameIs`, **case-sensitive**). Returns the **live `FProperty*`**, `Offset_Internal`
(`FPROP_OFFSET = 0x44`) and `ElementSize` (`FPROP_ELEMSIZE = 0x34`).

**This settles the question the task poses: the shim reads LIVE `FProperty` objects, not the `.rdata`
UHT `FBoolPropertyParams`. The UHT records appear nowhere in the shim.**

### 1.2 Bool decode — `PdFmtValue`, `tutorial_launch.cpp:9865-9887`

```
9865      if(!strcmp(type,"BoolProperty")){
9866          uint8_t fs=0,bo=0,bm=0,fm=0; int haveMeta=0;
9867          if(LooksLikePtr(prop)&&SafeReadable((void*)(prop+FBOOLPROP_FIELDSIZE),4)){
9868              fs=*(uint8_t*)(prop+FBOOLPROP_FIELDSIZE); bo=*(uint8_t*)(prop+FBOOLPROP_BYTEOFFSET);
9869              bm=*(uint8_t*)(prop+FBOOLPROP_BYTEMASK);  fm=*(uint8_t*)(prop+FBOOLPROP_FIELDMASK);
9870              haveMeta=1;
9871          }
9872          int plausible = haveMeta && fs>=1 && fs<=8 && bm!=0 && fm!=0 && bo<=8;
9873          uintptr_t ba = plausible ? (a+bo) : a;
...
9875          uint8_t raw=*(uint8_t*)ba;
9876          int v = plausible ? ((raw & fm)!=0) : (raw!=0);
```

with, at `9812-9815`:

```
9812  constexpr uintptr_t FBOOLPROP_FIELDSIZE  = 0x70;
9813  constexpr uintptr_t FBOOLPROP_BYTEOFFSET = 0x71;
9814  constexpr uintptr_t FBOOLPROP_BYTEMASK   = 0x72;
9815  constexpr uintptr_t FBOOLPROP_FIELDMASK  = 0x73;
```

and the comment at `9809-9811` grading them **[I], not [M]** (`sizeof(FProperty)==0x70` from FK-14
plus stock UE layout).

### 1.3 WHY EVERY BOOL READS `fs=1 bo=0 bm=0x01 fm=0xFF`

**It is not the wrong struct, not the wrong field, and not `FBoolPropertyParams` being confused with
`FBoolProperty`. The code reads the right four bytes and they genuinely all hold that value, because
every bool it has been pointed at so far is a NATIVE `bool`, not a C++ bitfield.**

`FBoolProperty::SetBoolSize` is inlined into the UHT `FBoolProperty` constructor. Verbatim from
`merged4` (the `.pdata` chain for this function is
`0x1308E20 → 0x1308E2E → 0x1308E9B → 0x1308F0A → 0x1308F38..0x1308FCF`):

```
;; the ctor's derive-from-a-scratch-buffer step
0x01308ECE  41ffd7               call r15                      ; SetBitFunc(Buffer)   <- the UHT thunk
0x01308ED3  4885f6               test rsi, rsi                 ; rsi = SizeOfOuter
0x01308EE0  0fb61439             movzx edx, byte [rcx + rdi]   ; scan Buffer for the first non-zero byte
0x01308EE4  84d2                 test dl, dl
0x01308EE6  750b                 jne 0x1308EF3
0x01308EF3  8be8                 mov ebp, eax                  ; ebp = BYTE INDEX   -> Offset_Internal
0x01308EF5  448be2               mov r12d, edx                 ; r12d = BYTE VALUE  -> the bitmask
0x01308EFB  e89025caff           call 0xffab490                ; FMemory::Free(Buffer)
0x01308F0A  8bd5                 mov edx, ebp
0x01308F0C  488bcb               mov rcx, rbx                  ; rbx = the FProperty
0x01308F0F  e8eca6feff           call 0x2f3600                 ; SetOffset_Internal(ByteIndex)
0x01308F14  410fb64618           movzx eax, byte [r14 + 0x18]  ; params EPropertyGenFlags (0x0C / 0x4C)
0x01308F19  450fb74632           movzx r8d, word [r14 + 0x32]  ; params ElementSize
0x01308F2F  c0e806               shr al, 6                     ; bit 6 = EPropertyGenFlags::NativeBool (0x40)
0x01308F32  f6d0                 not al
0x01308F34  a801                 test al, 1
0x01308F36  742b                 je 0x1308F63                  ; -> BITFIELD branch

;; NATIVE-BOOL branch  (this is where every line the probe has ever printed came from)
0x01308F42  48094338             or  qword [rbx+0x38], 0x1040000200  ; PropertyFlags |= POD|NoDtor|ZeroCtor
0x01308F49  44894334             mov dword [rbx+0x34], r8d           ; ElementSize     <- FPROP_ELEMSIZE = 0x34
0x01308F4D  44884370             mov byte  [rbx+0x70], r8b           ; FieldSize  = 1  <- FBOOLPROP_FIELDSIZE
0x01308F51  66c743710001         mov word  [rbx+0x71], 0x0100        ; ByteOffset = 0, ByteMask = 1
0x01308F57  c64373ff             mov byte  [rbx+0x73], 0xff          ; FieldMask  = 255 <- FBOOLPROP_FIELDMASK
0x01308F62  c3                   ret

;; BITFIELD branch
0x01308F96  c6437100             mov byte  [rbx+0x71], 0             ; ByteOffset = 0
0x01308FA4  0fb6540c50           movzx edx, byte [rsp+rcx+0x50]      ; ((uint8*)&TestBitmask)[i]
0x01308FA9  885372               mov byte  [rbx+0x72], dl            ; ByteMask = that byte  (0x80 / 0x08)
0x01308FBD  0fb64372             movzx eax, byte [rbx+0x72]
0x01308FC1  884373               mov byte  [rbx+0x73], al            ; FieldMask = ByteMask
```

Consequences, all `[M]`:

1. **`FBOOLPROP_FIELDSIZE/BYTEOFFSET/BYTEMASK/FIELDMASK = 0x70/0x71/0x72/0x73` are CORRECT.** The
   `[I]` grade at `tutorial_launch.cpp:9809-9811` can be upgraded, and `FPROP_ELEMSIZE = 0x34`
   (S126's "[I] by arithmetic") with it.
2. **`fs=1 bo=0 bm=0x01 fm=0xFF` is exactly the constant the native branch stores.** Nothing is
   mis-decoded. What the value *lacks* is discriminating power: it is identical on every native bool
   in the image, so it cannot separate "we are reading `FBoolProperty` metadata" from "we are reading
   four bytes of unrelated memory that happen to be `01 00 01 FF`".
3. **`v = (raw & fm) != 0` is the engine's own `GetPropertyValue`** and is correct on both branches —
   native (`fm=0xFF`: any non-zero byte is true) and bitfield (`fm==bm`: one bit).
   **There is no bug to fix. What is missing is a control.**
4. The `plausible` gate at `9872` (`bm!=0 && fm!=0 && bo<=8`) already accepts a bitfield correctly
   (`bm=fm=0x80`, `bo=0`, `fs=1`), so the two-sided control exercises the *decoder* end to end, not
   only the four-byte read.

### 1.4 THE CONTROL THE HANDOFF ASKS FOR IS AVAILABLE AND FULLY MEASURED

UHT `FBoolPropertyParams` records (layout confirmed empirically against four properties; `NameUTF8`
`+0x00`, `PropertyFlags` `+0x10`, `EPropertyGenFlags | EObjectFlags` `+0x18`,
`ArrayDim | ElementSize | SizeOfOuter` `+0x30`, **`SetBitFunc` `+0x38`**):

| property | record | genFlags | SizeOfOuter | SetBitFunc | body |
|---|---|---|---|---|---|
| `bAlwaysRelevant` | `.rdata 0x07F1F730` | `0x0C` Bool | `0x390` | `0x032F7100` | `or byte [rcx+0x68], 8` |
| `bHidden` | `.rdata 0x07F1F880` | `0x0C` Bool | `0x390` | `0x03368980` | `or byte [rcx+0x68], 0x80` |
| `bCanEverReplicate` | `.rdata 0x07F1FDF0` | `0x4C` Bool\|**NativeBool** | `0x390` | `0x02078900` | `mov byte [rcx+0x6c], 1` |
| `bEnablePooling` | `.rdata 0x07F21160` | `0x4C` Bool\|**NativeBool** | `0x390` | `0x03368BF0` | `mov byte [rcx+0x2d3], 1` |

⇒ live, the first two must read **`off = 0x68` for BOTH**, with **`bm = 0x80` vs `bm = 0x08`** and
`fm == bm`. **Same offset, different mask** is unproducible by constant garbage, and unproducible by
reading the wrong four bytes — a wrong-offset read of two `FField`s would not systematically differ
by exactly `0x80` vs `0x08`.

⚠ Caveats that belong in the record:
- `SetOffset_Internal` (`0x2F3600`) sits on an **all-zero (undecrypted) page** in `merged4` —
  **COVERAGE-BLOCKED**, so "the ByteIndex becomes `Offset_Internal`" is `[I, strong]` from the call
  shape (`mov edx,ByteIndex; mov rcx,FProperty; call`), not from the callee's bytes. It is
  corroborated live: the shim's existing calibration already resolves `bCanEverReplicate` by name to
  `0x6C`, which is precisely the byte index its `SetBitFunc` writes.
- These `SetBitFunc` thunks are **ICF-folded**: `0x02078900` is pointed at by **8** `.rdata` qwords,
  `0x032F7100` by 2, `0x03368980` and `0x03368BF0` by 1 each. **A thunk address identifies nothing**;
  the *record → thunk* pointer is what binds the body to the property name, and that is what was read.
- It is `[I]`, not `[M]`, that AActor's UHT bools appear in the live `ChildProperties` chain at all —
  the file's own comment at `10034-10036` says so for the existing calibration. The patch therefore
  treats *not resolved* as a first-class outcome, never as a FAIL.

---

## 2. THE PATCHES

All three additions are confined to the `PdPodDump` family. **Apply BOTTOM-UP (highest line number
first)** or the later line numbers shift. Line numbers are against the current
`tools/sigbypass-mod/tutorial_launch.cpp` (14,793 lines).

⚠ The file has **no `<math.h>`** and uses **`__builtin_sqrt`** (clang++ build — see the `Build:` line
in the file header at line 13, and existing uses at `2975`, `3040`, `4267`, `12587`). Patch G uses
`__builtin_sqrt` for that reason; plain `sqrt` will not compile.

### PATCH A — the AttachedCrewPods offset constant · **insert after line 9807**

```cpp
constexpr uint32_t PDPOD_OFF_CREWPODS = 0x490;   // ADDSi     1168   TArray<ALokiDropPod@>, 16 B
```

### PATCH B — the two-sided bool control · **insert after line 10026** (between `PdPodSweep`'s closing `}` and the `PdPodCalibrate` comment block)

```cpp
// ══ S132 — THE TWO-SIDED BOOL CONTROL ═════════════════════════════════════════════════════════════
// Every bool this readout has ever printed reads fs=1 bo=0 bm=0x01 fm=0xFF. That is CORRECT and it is
// NOT a bug: it is verbatim what FBoolProperty::SetBoolSize's NATIVE-BOOL branch stores. Measured
// offline in dumps/merged4.dump.exe (the ctor's .pdata chain is 0x1308E20..0x1308FCF):
//     0x01308F14  movzx eax, byte [r14+0x18]     ; UHT params EPropertyGenFlags   (0x0C / 0x4C)
//     0x01308F2F  shr al,6 / not al / test al,1  ; bit 6 == EPropertyGenFlags::NativeBool (0x40)
//     0x01308F49  mov dword [rbx+0x34], r8d      ; ElementSize        <- FPROP_ELEMSIZE  = 0x34
//     0x01308F4D  mov byte  [rbx+0x70], r8b      ; FieldSize  = 1     <- FBOOLPROP_FIELDSIZE
//     0x01308F51  mov word  [rbx+0x71], 0x0100   ; ByteOffset = 0, ByteMask = 1
//     0x01308F57  mov byte  [rbx+0x73], 0xff     ; FieldMask  = 255   <- FBOOLPROP_FIELDMASK
// So the four bytes ARE read in the right place -- but the value is CONSTANT across every native bool
// in the image, so it cannot tell "we are reading FBoolProperty metadata" from "we are reading four
// bytes of something else that happen to be 01 00 01 FF". Self-consistent, and it proves nothing.
//
// AActor ships two BITFIELD bools that break the tie, and their UHT records name the answer:
//     bAlwaysRelevant  FBoolPropertyParams .rdata 0x07F1F730  SetBitFunc(+0x38) 0x032F7100
//                      = `or byte [rcx+0x68], 8`      -> Offset_Internal 0x68, ByteMask 0x08
//     bHidden          FBoolPropertyParams .rdata 0x07F1F880  SetBitFunc(+0x38) 0x03368980
//                      = `or byte [rcx+0x68], 0x80`   -> Offset_Internal 0x68, ByteMask 0x80
// Both carry genFlags 0x0C (Bool, NativeBool CLEAR) and SizeOfOuter 0x390, and the ctor derives the
// pair by zeroing a SizeOfOuter buffer, calling that thunk, and taking the first non-zero byte's INDEX
// as Offset_Internal and its VALUE as the mask (0x01308ECE / 0x01308EF3 / 0x01308EF5 / 0x01308F0F).
// The bitfield branch then closes with FieldMask = ByteMask (0x01308FBD / 0x01308FC1).
// ⇒ SAME Offset_Internal, DIFFERENT ByteMask. No constant garbage at +0x70..0x73 can produce that --
//   which is exactly the property the existing single-value reading lacks.
//
// POSITIVE CONTROL FOR THE OFFLINE MEASUREMENT ITSELF: the same record walk reproduces the two values
// this project holds [M] from a completely different instrument (S130's walk of AActor's 114-entry
// PropPointers array) -- bCanEverReplicate -> 0x02078900 `mov byte [rcx+0x6c],1` and bEnablePooling ->
// 0x03368BF0 `mov byte [rcx+0x2d3],1`, both genFlags 0x4C = Bool|NativeBool.
//
// ⚠ NOT RESOLVED IS NOT A FAIL. It is [I], not [M], that AActor's UHT bools appear in the live FField
//   ChildProperties chain at all (the same caveat PdPodCalibrate already carries). A non-resolve
//   prints UNAVAILABLE -- never a zero, never a FAIL.
// ⚠ The SetBitFunc thunks are ICF-FOLDED (0x02078900 has 8 .rdata pointers to it), so a thunk ADDRESS
//   identifies nothing. The record -> thunk pointer is what binds the body to the property name.
#ifndef KPDBOOLCTL
#define KPDBOOLCTL 1        // 0 = compile the two-sided control out entirely
#endif
#ifndef KPDBHIDDENOFF
#define KPDBHIDDENOFF   0x68    // [M] both bitfields' Offset_Internal
#endif
#ifndef KPDBHIDDENMASK
#define KPDBHIDDENMASK  0x80    // [M] bHidden's ByteMask
#endif
#ifndef KPDBALWAYSMASK
#define KPDBALWAYSMASK  0x08    // [M] bAlwaysRelevant's ByteMask
#endif

static int g_pdPodBoolCtl=-1;   // -1 UNAVAILABLE (did not resolve) / 0 FAIL / 1 PASS

struct PdBoolMeta { uintptr_t prop; uint32_t off; uint32_t elem; uint8_t fs,bo,bm,fm; };

// 1 ok | 0 NOT RESOLVED BY NAME | -1 resolved but not a BoolProperty | -2 meta bytes unreadable
static int PdReadBoolMeta(uintptr_t cls,const char* name,PdBoolMeta* m){
    m->prop=0; m->off=0xFFFFFFFF; m->elem=0; m->fs=0; m->bo=0; m->bm=0; m->fm=0;
    uint32_t off=0xFFFFFFFF, elem=0; char t[48],s[48],ow[96];
    uintptr_t p=PdFindPropOn(cls,name,&off,&elem,t,sizeof(t),s,sizeof(s),ow,sizeof(ow));
    if(!p) return 0;
    m->prop=p; m->off=off; m->elem=elem;
    if(strcmp(t,"BoolProperty")!=0) return -1;
    if(!SafeReadable((void*)(p+FBOOLPROP_FIELDSIZE),4)) return -2;
    m->fs=*(uint8_t*)(p+FBOOLPROP_FIELDSIZE);
    m->bo=*(uint8_t*)(p+FBOOLPROP_BYTEOFFSET);
    m->bm=*(uint8_t*)(p+FBOOLPROP_BYTEMASK);
    m->fm=*(uint8_t*)(p+FBOOLPROP_FIELDMASK);
    return 1;
}
static const char* PdBoolMetaWhy(int r){
    return (r==1)?"ok":(r==0)?"NOT RESOLVED BY NAME":
           (r==-1)?"RESOLVED BUT NOT A BoolProperty":"META BYTES UNREADABLE";
}
static void PdPodBoolControl(uintptr_t pod,uintptr_t cls,const char* clsName){
#if !KPDBOOLCTL
    (void)pod;(void)cls;(void)clsName; return;
#else
    PdBoolMeta h,a;
    int rh=PdReadBoolMeta(cls,"bHidden",&h), ra=PdReadBoolMeta(cls,"bAlwaysRelevant",&a);
    Markerf("[PD] bool TWO-SIDED CONTROL on %s -- two AActor BITFIELDS that share Offset_Internal 0x%X "
            "and differ ONLY in ByteMask (0x%02X vs 0x%02X, [M] from their UHT SetBitFunc bodies "
            "0x03368980 / 0x032F7100)\r\n",
            clsName,(unsigned)KPDBHIDDENOFF,(unsigned)KPDBHIDDENMASK,(unsigned)KPDBALWAYSMASK);
    if(rh==1) Markerf("[PD]   bHidden         @0x%-4X fs=%u bo=%u bm=0x%02X fm=0x%02X elem=%u\r\n",
                      h.off,(unsigned)h.fs,(unsigned)h.bo,(unsigned)h.bm,(unsigned)h.fm,h.elem);
    else      Markerf("[PD]   bHidden         *** %s -- this is NOT a zero and NOT a FAIL; the control "
                      "is UNAVAILABLE on this class chain. ***\r\n",PdBoolMetaWhy(rh));
    if(ra==1) Markerf("[PD]   bAlwaysRelevant @0x%-4X fs=%u bo=%u bm=0x%02X fm=0x%02X elem=%u\r\n",
                      a.off,(unsigned)a.fs,(unsigned)a.bo,(unsigned)a.bm,(unsigned)a.fm,a.elem);
    else      Markerf("[PD]   bAlwaysRelevant *** %s -- this is NOT a zero and NOT a FAIL; the control "
                      "is UNAVAILABLE on this class chain. ***\r\n",PdBoolMetaWhy(ra));
    if(rh!=1||ra!=1){
        g_pdPodBoolCtl=-1;
        Marker("[PD]   VERDICT: UNAVAILABLE -- at least one side did not resolve, so NOTHING is claimed "
               "about the FBOOLPROP_* decode either way. Do NOT read this as a failure.\r\n");
        return; }
    int sameOff  = (h.off==a.off);
    int diffMask = (h.bm!=a.bm) && h.bm && a.bm;
    int exact    = (h.off==(uint32_t)KPDBHIDDENOFF) && (a.off==(uint32_t)KPDBHIDDENOFF) &&
                   (h.bm==(uint8_t)KPDBHIDDENMASK)  && (a.bm==(uint8_t)KPDBALWAYSMASK);
    int fmEcho   = (h.fm==h.bm) && (a.fm==a.bm);
    g_pdPodBoolCtl = (sameOff&&diffMask)?1:0;
    Markerf("[PD]   VERDICT: %s | sameOffset=%s | differentByteMask=%s | exact-vs-[M]=%s | "
            "FieldMask==ByteMask (the bitfield branch's own tail, .text 0x01308FBD/0x01308FC1)=%s\r\n",
            g_pdPodBoolCtl?"PASS":"*** FAIL ***",
            sameOff?"yes":"*** no ***", diffMask?"yes":"*** no ***",
            exact?"MATCH":"*** DIFFERS -- audit, do not silently accept ***",
            fmEcho?"yes":"*** no ***");
    if(!g_pdPodBoolCtl)
        Marker("[PD]   *** FAIL means FProperty+0x70..0x73 are NOT FieldSize/ByteOffset/ByteMask/"
               "FieldMask on this build. EVERY bool this readout prints is then UNINTERPRETABLE, "
               "bIsTeamLeaderPod included. ***\r\n");
    else
        Marker("[PD]   PASS means two bools at the SAME Offset_Internal decoded to DIFFERENT ByteMasks. "
               "No constant garbage at +0x70..0x73 can produce that, so the bool decode is calibrated.\r\n");
    // The VALUES are free once the decode is calibrated, and bHidden is a real signal on this surface:
    // the fifth wall's own tail un-hides the actor it places (S131 lanes2).
    { char v1[192]="",w1[128]="",v2[192]="",w2[128]="";
      PdFmtValue(pod,h.off,h.elem,"BoolProperty",h.prop,v1,sizeof(v1),w1,sizeof(w1));
      PdFmtValue(pod,a.off,a.elem,"BoolProperty",a.prop,v2,sizeof(v2),w2,sizeof(w2));
      Markerf("[PD]   values on this pod: bHidden=%s  bAlwaysRelevant=%s\r\n",v1,v2); }
#endif
}
```

### PATCH C — call it · **replace line 10076**

```cpp
    if(doCalibrate) PdPodCalibrate(cls,cn);
```
with
```cpp
    if(doCalibrate){ PdPodCalibrate(cls,cn); PdPodBoolControl(pod,cls,cn); }
```

`doCalibrate` is already `i==0`, i.e. once per dump on pod[0]. No new gate, no extra
`GUObjectArray` sweep — the control is two `PdFindPropOn` walks.

### PATCH D — the velocity reader · **insert after line 9988** (right after `PdPodLoc`'s closing `}`)

```cpp
// ComponentVelocity off the pod's ROOT component. S131 is what makes this worth a line: the E1 pod read
// (20000.0, 0, 0) while three control pods read 0.0, and the cooked asset's ProjectileMovement
// InitialSpeed/MaxSpeed = 20000 is what settled that the number was the GAME's and not our KPDSPAWNZ.
// ⚠ PdPodSweep can NEVER see this: it walks the POD's class chain, and ComponentVelocity lives on the
//   root COMPONENT. That is why S131 had to read it with an external RPM tool
//   (scratchpad/s131/tools/pod_live_read.py:83) instead of off the in-arm marker.
// [M] USceneComponent::ComponentVelocity Offset = 0x1A0 -- UHT FGenericPropertyParams record
// .rdata 0x07EDFD40, Offset field (uint16 @ +0x32) = 416. Its sibling record for RelativeLocation,
// .rdata 0x07EDFC80, reads 344 = 0x158 -- this file's own long-standing fallback, i.e. two known
// answers out of one read. ⇒ S131's own "[I] from lane 3" note on 0x1A0 is upgraded to [M].
// The offset is still resolved BY NAME at runtime; 0x1A0 is the CROSS-CHECK, never the source.
// return: 1 doubles | 2 floats | 0 no root | -1 NOT RESOLVED BY NAME | -2 unreadable | -3 bad type/size
static int PdPodVel(uintptr_t root,double* out3,uint32_t* offOut,uint32_t* elemOut){
    out3[0]=out3[1]=out3[2]=0; if(offOut)*offOut=0xFFFFFFFF; if(elemOut)*elemOut=0;
    if(!LooksLikePtr(root)) return 0;
    uint32_t vo=0xFFFFFFFF, ve=0; char t[48],s[48],ow[96];
    uintptr_t p=PdFindPropOn(ClassOf(root),"ComponentVelocity",&vo,&ve,t,sizeof(t),s,sizeof(s),ow,sizeof(ow));
    if(!p) return -1;
    if(offOut)*offOut=vo; if(elemOut)*elemOut=ve;
    if(strcmp(t,"StructProperty")!=0) return -3;
    // ElementSize is CHECKED, exactly as PdFmtValue's StructProperty arm does: 24 = 3x double (LWC),
    // 12 = 3x float. Anything else REFUSES rather than printing a fabricated triple.
    if(ve==24){ if(!SafeReadable((void*)(root+vo),24)) return -2;
        double* V=(double*)(root+vo); out3[0]=V[0]; out3[1]=V[1]; out3[2]=V[2]; return 1; }
    if(ve==12){ if(!SafeReadable((void*)(root+vo),12)) return -2;
        float* V=(float*)(root+vo); out3[0]=(double)V[0]; out3[1]=(double)V[1]; out3[2]=(double)V[2]; return 2; }
    return -3;
}
```

### PATCH E — the TArray field printer · **insert after line 9965** (right after `PdPodField`'s closing `}`)

```cpp
// One TArray field of one pod: resolved BY NAME exactly like PdPodField, then the TArray header
// {Data, Num, Max} decoded EXPLICITLY. Routing this through PdPodField would print
// "<ArrayProperty, size=16 -- no decoder>" for a POPULATED array and for an EMPTY one alike -- i.e. it
// prints the same string for the two outcomes the reader cares about. ElementSize is CHECKED
// (16 == sizeof(TArray)), never assumed, and an implausible header is SAID to be implausible instead
// of being reported as a count.
static void PdPodArrayField(uintptr_t pod,uintptr_t cls,const char* name,uint32_t asOff,const char* expect){
    uint32_t off=0xFFFFFFFF, elem=0; char type[48], sname[48], owner[96];
    uintptr_t prop=PdFindPropOn(cls,name,&off,&elem,type,sizeof(type),sname,sizeof(sname),owner,sizeof(owner));
    char cross[128];
    if(!KPDPODASOFF||asOff==0xFFFFFFFF) strncpy_s(cross,sizeof(cross),"",_TRUNCATE);
    else if(!prop)      _snprintf_s(cross,sizeof(cross),_TRUNCATE," | AS offset 0x%X (name resolution FAILED)",asOff);
    else if(off==asOff) _snprintf_s(cross,sizeof(cross),_TRUNCATE," | AS 0x%X AGREE",asOff);
    else                _snprintf_s(cross,sizeof(cross),_TRUNCATE," | AS 0x%X *** DISAGREE ***",asOff);
    if(!prop){
        g_pdPodNameFail++;
        Markerf("[PD]   %-20s *** NOT RESOLVED BY NAME on this class chain -- this is NOT a zero and NOT "
                "an empty array; it means the readout could not find the property. ***%s\r\n",name,cross);
        if(KPDPODASOFF&&asOff!=0xFFFFFFFF){
            if(SafeReadable((void*)(pod+asOff),16))
                Markerf("[PD]   %-20s   [AS-OFFSET FALLBACK, not a by-name read] TArray@0x%X: Data=0x%llX "
                        "Num=%d Max=%d\r\n",name,asOff,
                        (unsigned long long)*(uintptr_t*)(pod+asOff),
                        *(int32_t*)(pod+asOff+8),*(int32_t*)(pod+asOff+12));
            else Markerf("[PD]   %-20s   [AS-OFFSET FALLBACK] 0x%X UNREADABLE\r\n",name,asOff);
        }
        if(expect&&expect[0]) Markerf("[PD]   %-20s   expect: %s\r\n",name,expect);
        return; }
    if(KPDPODASOFF&&asOff!=0xFFFFFFFF){ if(off==asOff) g_pdPodAgree++; else g_pdPodDisagree++; }
    if(strcmp(type,"ArrayProperty")!=0||elem!=16){
        Markerf("[PD]   %-20s @0x%-4X %-16s size=%-3u = *** NOT DECODED: expected ArrayProperty with "
                "ElementSize 16 (sizeof(TArray)); REFUSING to decode ***%s\r\n",name,off,type,elem,cross);
        if(expect&&expect[0]) Markerf("[PD]   %-20s   expect: %s\r\n",name,expect);
        return; }
    if(!SafeReadable((void*)(pod+off),16)){
        Markerf("[PD]   %-20s @0x%-4X %-16s = UNREADABLE -- instrument, NOT an empty array%s\r\n",
                name,off,type,cross);
        return; }
    uintptr_t data=*(uintptr_t*)(pod+off);
    int32_t num=*(int32_t*)(pod+off+8), max=*(int32_t*)(pod+off+12);
    int sane = (num>=0 && max>=0 && num<=max && max<=65536) &&
               ((num==0&&max==0&&data==0) || LooksLikePtr(data));
    Markerf("[PD]   %-20s @0x%-4X %-16s size=%-3u = TArray{Data=0x%llX Num=%d Max=%d}%s%s\r\n",
            name,off,type,elem,(unsigned long long)data,num,max,
            sane?"":"   *** HEADER IMPLAUSIBLE -- do NOT read Num as a count ***",cross);
    if(sane&&num>0&&LooksLikePtr(data)){
        int show=(num>8)?8:num;
        for(int k=0;k<show;k++){
            if(!SafeReadable((void*)(data+(uintptr_t)k*8),8)){
                Markerf("[PD]   %-20s   [%d] UNREADABLE\r\n",name,k); continue; }
            uintptr_t e=*(uintptr_t*)(data+(uintptr_t)k*8);
            if(!e){ Markerf("[PD]   %-20s   [%d] null\r\n",name,k); continue; }
            char en[96]="?",ec[96]="?"; GetFNameStr(NameId(e),en,sizeof(en));
            uintptr_t c=ClassOf(e); if(c) GetFNameStr(NameId(c),ec,sizeof(ec));
            Markerf("[PD]   %-20s   [%d] 0x%llX '%s' cls=%s%s\r\n",name,k,(unsigned long long)e,en,ec,
                    GcAlive(e)?"":"  [NOT GcAlive]");
        }
        if(num>show) Markerf("[PD]   %-20s   ... %d more not shown -- DO NOT COUNT THESE LINES, parse Num\r\n",
                             name,num-show);
    }
    if(expect&&expect[0]) Markerf("[PD]   %-20s   expect: %s\r\n",name,expect);
}
```

### PATCH F — print AttachedCrewPods · **insert after line 10087** (after the `LeaderPod` block, before `PilotPlayerState`)

```cpp
    // S132: the crew-pod array, EXPLICITLY. PdPodSweep cannot substitute for this -- its cap
    // (KPDPODSWEEPCAP) and its "keep a no-decoder type only if its first 8 bytes are non-zero" rule
    // mean an EMPTY AttachedCrewPods is SUPPRESSED and a populated one prints only
    // "<ArrayProperty, size=16>". Neither is a reading.
    // AS offset 0x490 = `ADDSi W0:1168` in GameMode.DropPhase.LokiDropPod.as (the operand is a byte
    // offset from `this`; S131 measured that rule at 76:0 live agreement). By-name is still the source.
    PdPodArrayField(pod,cls,"AttachedCrewPods",PDPOD_OFF_CREWPODS,
               "Num=0 on every pod SpawnDropPodForTeam produced: QueueCrewForPodSpawn is the only "
               "writer and it appends to the LEADER pod per queued crew member. Num>0 would mean crew "
               "queuing ran, which nothing on the measured route calls.");
```

### PATCH G — the velocity line · **insert after line 10138** (after the location block's closing `}`, before `if(detail) PdPodSweep(pod,cls);`)

```cpp
    // ComponentVelocity, on its OWN line directly under the location. Deliberately not spliced into the
    // three location format strings (first-sample / delta / table-full) -- that is three edits and three
    // chances to mis-order a vararg, for no gain. A ZERO here is a real reading; NOT RESOLVED is a
    // different state and says so in words.
    { double V[3]; uint32_t vo=0xFFFFFFFF, ve=0; int vr=PdPodVel(root,V,&vo,&ve);
      double sp=(vr==1||vr==2)?__builtin_sqrt(V[0]*V[0]+V[1]*V[1]+V[2]*V[2]):0.0;
      if(vr==1||vr==2){
          Markerf("[PD]   velocity: ComponentVelocity@0x%X (%s) = (%.1f, %.1f, %.1f)  |v|=%.1f uu/s -> %s\r\n",
                  vo,(vr==1)?"3x double, ElementSize=24":"3x float, ElementSize=12",
                  V[0],V[1],V[2],sp,(sp>1.0)?"*** MOVING ***":"at rest (a real zero, read by name)");
          if(vo!=0x1A0)
              Markerf("[PD]   velocity: *** by-name offset 0x%X DISAGREES with the [M] UHT record value "
                      "0x1A0 (.rdata 0x07EDFD40) -- audit before trusting the numbers above ***\r\n",vo);
      }
      else if(vr==0)  Marker("[PD]   velocity: no RootComponent -- UNAVAILABLE (instrument, not a zero)\r\n");
      else if(vr==-1) Marker("[PD]   velocity: ComponentVelocity *** NOT RESOLVED BY NAME on the root "
                             "component's class chain -- this is NOT a zero. ***\r\n");
      else if(vr==-2) Markerf("[PD]   velocity: ComponentVelocity@0x%X UNREADABLE -- instrument, not a zero\r\n",vo);
      else            Markerf("[PD]   velocity: ComponentVelocity@0x%X type/ElementSize=%u is neither a "
                              "24-byte nor a 12-byte FVector -- REFUSING to decode rather than print a "
                              "fabricated triple\r\n",vo,ve); }
```

### PATCH H — surface the verdict in the summary · **replace lines 10184-10188**

```cpp
    Markerf("[PD] ===== POD STATE (%s) end. AS-vs-live offsets: %d agree, %d DISAGREE, %d name lookups "
            "failed | calibration=%s | bool two-sided control=%s | dumps=%d, pod-samples that MOVED so "
            "far=%d =====\r\n",
            when,g_pdPodAgree,g_pdPodDisagree,g_pdPodNameFail,
            (g_pdPodCalOk==1)?"PASS":(g_pdPodCalOk==0)?"MISMATCH":"unavailable",
            (g_pdPodBoolCtl==1)?"PASS":(g_pdPodBoolCtl==0)?"*** FAIL ***":"UNAVAILABLE (did not resolve)",
            g_pdPodDumps,g_pdPodMoved);
```

---

## 3. WHAT EACH ADDITION IS WORTH, AND WHAT IT CANNOT SAY

- **(1) two-sided bool control.** Turns `bIsTeamLeaderPod = true` from a value resting on an **[I]**
  struct layout into one resting on a within-run, same-instrument calibration. It is the bool analogue
  of the offset calibration already present (`bCanEverReplicate` 0x6C / `bEnablePooling` 0x2D3) and
  closes the last calibration gap on this readout. Cost: two `PdFindPropOn` walks per dump. No sweep,
  no call, no write.
  ⚠ It does **not** validate the AS-offset cross-check, the `Offset_Internal` of any Angelscript
  member, or anything in `PdWalkParams`. It validates the four bytes at `FProperty+0x70..0x73` and the
  `raw & FieldMask` decode — nothing more.
- **(2) AttachedCrewPods.** Adds an offline-predicted `[M]` offset (0x490) to the AS-vs-live tally
  (currently 5 fields), and separates an empty array from a *suppressed* one. Pre-register the
  expectation — `Num = 0` — before flying.
- **(3) ComponentVelocity.** This is the field that named the mover in S131, and **the in-arm probe
  literally cannot see it today**: `PdPodSweep` walks the *pod's* class chain while the property lives
  on the root *component*, which is why S131 needed an external RPM tool. Adding it removes an
  out-of-band dependency from the armed window.

---

## 4. `.text` BLAST RADIUS — EXACTLY WHAT GATING IS NEEDED

### 4.1 The mechanism this file relies on
`static const int kRunMode = KRUNMODE;` (line 164) is a compile-time constant, so every
`if(kRunMode==RM_X){ DoX(); … }` in `OnPI` (lines 1255-1272) folds at `-O2`, `DoX` becomes
unreferenced, and clang drops it plus everything reachable only from it. The file already documents
and depends on this (the `DpCensus` latch comment, ~6265-6272).

### 4.2 Call-graph audit of everything the patches touch
Every caller in the file was grepped:

| symbol | callers | compiled into |
|---|---|---|
| `PdFindPropOn` | `PdPodField`, `PdPodCalibrate` (+ the new `PdReadBoolMeta`, `PdPodVel`, `PdPodArrayField`) | pod-dump family only |
| `PdFmtValue` | `PdPodField`, `PdPodSweep` (+ new `PdPodBoolControl`) | pod-dump family only |
| `PdPodField` / `PdPodLoc` / `PdPodSweep` / `PdPodCalibrate` / `PdPodOne` | `PdPodOne` / `PdPodDump` | pod-dump family only |
| `PdPodDump` | `PdLadderStep` (RM_DROPPOD) ×4, `SpLadder` (RM_POOLSPAWN) ×5 | **RM_DROPPOD + RM_POOLSPAWN only** |

⇒ **No patch touches a function any other run mode compiles.** Expected: only `droppod-*` and
`poolspawn-*` change.

### 4.3 THE THREE WAYS THIS COULD STILL BITE — flag these to whoever applies the patch
1. **⛔ DO NOT put any of this into `PdTypeOf` (line 8327).** It is called by `PdWalkParams`
   (line 8352), which `RM_RIDEABLE`, `RM_DROPPLANE`, `RM_DROPMARKERS` and `RM_POOLSPAWN` all use. A
   change there moves `rideable` (`e221e4e415834067`) and `dropplane_b1only` (`5b4467b0105dec1a`).
   The patches route around it by using `PdFindPropOn`, which also returns `ElementSize` — strictly
   better here.
2. **⛔ DO NOT put any of this into `PropOffsetSuper` (line 2023) or `DpEvalClass` (line 6202).** Both
   are global. `DpEvalClass` is the recorded precedent: S131 added **one ungated `strstr`** and moved
   `dropplane_b1only`'s `.text` hash **while its `.text` SIZE stayed identical** at 120,832 B (the
   addition fitted inside the section's 512-byte padding). That is why the fix there was
   `&&(kRunMode==RM_DROPPOD||kRunMode==RM_POOLSPAWN)`. If a successor wants the bool control in
   `RM_RIDEABLE` too, it needs that same explicit `kRunMode` disjunction — **and it will then move
   `rideable`'s hash, which must be a deliberate, recorded rebase, not a side effect.**
3. **⚠ Argument is not verification.** clang pools string literals and merges identical bodies; the
   elimination of ~20 new literals referenced only from dead code is expected but not guaranteed.
   **Verify by hash, not by reasoning** (standing rule: "diff `.text`, never size"):

```
# BEFORE the edit, record the baselines; AFTER, these three must be IDENTICAL:
build.ps1 -Name tutorial_launch -Variant play              -> .text 9bc10a4552c596e1   (hard regression gate)
build.ps1 -Name tutorial_launch -Variant dropplane-b1only  -> .text 5b4467b0105dec1a   (Route E precondition)
build.ps1 -Name tutorial_launch -Variant rideable          -> .text e221e4e415834067
# EXPECTED TO MOVE (re-record in build.ps1 / BUILD.md / CLAUDE.md):
  droppod-pe-cdopoke  249a3cd2190eb334  ->  new
  droppod-pe-cdoctrl  61fd0745c23e89f0  ->  new
  poolspawn-cdopoke   efe8db553bf511ba  ->  new
  poolspawn-cdoctrl   85f3cee44c31b1cd  ->  new
```
   Use `tools/sigbypass-mod/verify_dll.py`, or the section-hash snippet in
   `docs/s109-dump-forensics.md` §23. ⚠ `-Variant X` **requires** `-Name tutorial_launch` (the S125
   guard at `build.ps1:81` throws otherwise), but a *typo'd variant name* is a different failure —
   read the built-artifact list, do not assume.
4. **⚠ Paired arms must be rebuilt together.** `droppod-pe-cdopoke`/`-cdoctrl` and
   `poolspawn-cdopoke`/`-cdoctrl` are A/B pairs. Rebuilding one and not the other leaves an A/B
   between two different source revisions — the mirror image of the "A/B against a copy of itself"
   failure the build table warns about.

### 4.4 New knobs introduced
`KPDBOOLCTL` (default 1), `KPDBHIDDENOFF` (0x68), `KPDBHIDDENMASK` (0x80), `KPDBALWAYSMASK` (0x08).
All `#ifndef`-guarded; no `build.ps1` entry is required, and none appears in any variant other than
the two run modes above. A `-DKPDBOOLCTL=0` arm reproduces the pre-S132 marker output exactly and is
the control if the new lines are ever suspected of costing game-thread time.

---

## 5. FREE BY-PRODUCTS OF THIS LANE (worth propagating even if the patches are not applied)

1. **`FBOOLPROP_FIELDSIZE/BYTEOFFSET/BYTEMASK/FIELDMASK = 0x70/0x71/0x72/0x73` are `[M]`, not `[I]`.**
   Update the comment at `tutorial_launch.cpp:9809-9811`.
2. **`FPROP_ELEMSIZE = 0x34` is `[M]`, not "[I] by arithmetic from two [M] constants".** Update the
   S126 correction block at `tutorial_launch.cpp:8027-8043` — its own stated test ("expect Int=4,
   Vector=24, Bool=1; if they still read 1, this is wrong again") is now settled from the binary:
   `0x01308F49 mov dword [rbx+0x34], r8d`, with `r8d` loaded from the params' ElementSize.
3. **`USceneComponent::ComponentVelocity @ 0x1A0` is `[M]`** (UHT record `.rdata 0x07EDFD40`, Offset
   `uint16 @ +0x32` = 416), upgrading `scratchpad/s131/tools/pod_live_read.py:87`'s own "[I] from lane
   3" note. The same read confirms `RelativeLocation @ 0x158` `[M]` (record `.rdata 0x07EDFC80` = 344)
   — the offset this file has carried as an unverified *fallback* for many sessions.
4. **The UHT `FBoolPropertyParams` layout for this build, for reuse:**
   `NameUTF8 +0x00 · RepNotifyFuncUTF8 +0x08 · PropertyFlags(u64) +0x10 · EPropertyGenFlags(u32) +0x18
   · EObjectFlags(u32) +0x1C · SetterFunc +0x20 · GetterFunc +0x28 · ArrayDim(u16) +0x30 ·
   ElementSize(u16) +0x32 · SizeOfOuter(u32) +0x34 · SetBitFunc +0x38`.
   ⚠ For the non-bool `FGenericPropertyParams` the `+0x30` block is `ArrayDim(u16) +0x30 ·
   **Offset(u16)** +0x32` — **not ElementSize**. Reading `+0x32` as ElementSize on a non-bool record
   is a trap that yields a plausible small integer (it is how `ComponentVelocity` first read
   "ElementSize=416").
   `EPropertyGenFlags`: `Bool = 0x0C`, `Struct = 0x19`, `NativeBool = 0x40` — verified against four
   properties whose native/bitfield status is independently known from their `SetBitFunc` opcode
   (`mov` vs `or`).
5. **A cheap general method:** *to learn a native bool's offset and bit with no live process, find its
   name string in `.rdata`, find the qword pointing at it, read `+0x38`, disassemble three bytes.* It
   works for every UHT bool in the image and needs no decrypted `.text` page beyond the two-instruction
   thunk.

---

## 6. LIMITS OF THIS LANE

- No file was edited. Nothing here has been compiled or flown.
- `SetOffset_Internal` (`0x2F3600`) is on an **all-zero page** in `merged4` — COVERAGE-BLOCKED. The
  ByteIndex→`Offset_Internal` step is therefore `[I, strong]` from the call shape plus the live
  corroboration that `bCanEverReplicate` already resolves by name to `0x6C`.
- Only **one** `mov byte [reg+0x73], 0xFF` exists in `merged4`'s decrypted `.text` (`0x01308F57`).
  That is a **floor, not a count** — ~45 % of `.text` is undecrypted. It is sufficient here because
  the single hit sits inside a function whose surrounding code is unambiguously the `FBoolProperty`
  ctor, but "there is exactly one `SetBoolSize`" is NOT a claim this lane makes.
- Whether `bHidden` / `bAlwaysRelevant` appear in the LIVE `ChildProperties` chain of a pod's class is
  `[I]`. The patch prints UNAVAILABLE if they do not; that outcome is a coverage limit of the control,
  not a result about the decode, and the code says so in words.
- `AttachedCrewPods @ 0x490` is `[M]` only as an **Angelscript-bytecode** offset. The patch's AGREE /
  DISAGREE line is the live test; do not record agreement before it has run.
