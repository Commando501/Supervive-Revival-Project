#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ticksniff.py -- READ-ONLY decoder for FTickFunction state on a live SUPERVIVE process.

WHY THIS EXISTS
---------------
UActorComponent::PrimaryComponentTick and AActor::PrimaryActorTick are FTickFunction
STRUCT MEMBERS, not UPROPERTYs, so every reflection-driven probe in tools/re/ is
structurally blind to them.  There is no UProperty named "PrimaryComponentTick" whose
offset a live class walk can resolve -- absence there is an INSTRUMENT LIMIT, not a
statement about the object.  This tool reads the raw bytes instead.

ALL OFFSETS BELOW ARE MEASURED OFFLINE FROM dumps/merged13.dump.exe.
Run  python ticksniff.py --selftest  to re-verify every one of them against the cold
image.  It asserts exact instruction bytes at named addresses AND runs negative
controls (bytes that must be ABSENT), so a vacuous pass is detectable.  No live
process is required for the selftest.

    python ticksniff.py --selftest
    python ticksniff.py --selftest --image <other .dump.exe>
    python ticksniff.py --pid 1234 --base 0x7FF6xxxxxxxx --comp 0x1B4021B60A0
    python ticksniff.py --pid 1234 --base 0x7FF6xxxxxxxx --actor 0x1B3857EA4C0
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys

# ---------------------------------------------------------------------------
# LAYOUT.  Every line names the instruction that measured it.
# ---------------------------------------------------------------------------
ACTOR_TICK_OFF = 0x38   # AActor::PrimaryActorTick             [M] AActor ctor 0x3371836
COMP_TICK_OFF = 0x40    # UActorComponent::PrimaryComponentTick [M] UAC ctor 0x3596B1F

# FTickFunction, sizeof 0x28.  [M] UHT SizeOfOuter == 0x28 in the FBoolPropertyParams
# of every FTickFunction bool, and the ctor initialises exactly +0x08..+0x27.
TF_VPTR = 0x00          # [M] ctor 0x3EBE0CD  mov [rcx],rax
TF_TICKGROUP = 0x08     # [M] AActor::SetTickGroup 0x339E930 = 88 51 40 c3   (0x40-0x38)
TF_ENDTICKGROUP = 0x09  # [M] ctor 0x3EBE0C7 mov word [rcx+8],0 (2-byte store covers both)
TF_FLAGS = 0x0A         # [M] UHT SetBitFuncs 0x32BB170/80/90/A0 "or byte [rcx+0x0A],mask"
TF_TICKSTATE = 0x0B     # [M] AActor::IsActorTickEnabled 0x338EAC0 = 80 79 43 00 0f 95 c0 c3
TF_TICKINTERVAL = 0x0C  # [M] AActor::GetActorTickInterval 0x3386300 = f3 0f 10 41 44 c3
TF_PREREQ_DATA = 0x10   # [M] FTickFunction::AddPrerequisite 0x3EC4080 mov rbp,[rdi+0x10]
TF_PREREQ_NUM = 0x18    # [M] 0x3EC4084 movsxd rsi,[rdi+0x18]   (element stride 0x10)
TF_PREREQ_MAX = 0x1C    # [M] 0x3EC40DD cmp eax,[rdi+0x1c]
TF_INTERNALDATA = 0x20  # [M] FTickFunction::SetTickFunctionEnable 0x3EF73BF mov rbx,[rcx+0x20]
TF_SIZE = 0x28
TF_TARGET = 0x28        # derived-class member; both derived tick fns put Target here.
                        # [M] FActorComponentTickFunction::ExecuteTick 0x35AA72F
                        # [M] FActorTickFunction::ExecuteTick          0x33831AA

# Bits in the +0x0A byte.
TF_BIT_TICK_EVEN_WHEN_PAUSED = 0x01      # [M] UHT setbit 0x32BB170 = 80 49 0a 01 c3
TF_BIT_CAN_EVER_TICK = 0x02              # [M] UHT setbit 0x32BB180 = 80 49 0a 02 c3
TF_BIT_START_WITH_TICK_ENABLED = 0x04    # [M] UHT setbit 0x32BB190 = 80 49 0a 04 c3
TF_BIT_ALLOW_ON_DEDICATED_SERVER = 0x08  # [M] UHT setbit 0x32BB1A0 = 80 49 0a 08 c3
TF_BIT_HIGH_PRIORITY = 0x10              # [M] FTickFunction::SetPriorityIncludingPrerequisites
                                         #     0x3EF6F09..0x3EF6F30 rmw of bit 4; and
                                         #     0x3EED678 uses it to pick a parallel task array
TF_BIT_RUN_ON_ANY_THREAD = 0x20          # [I, strong] declaration order + elimination.
                                         #     NO measured read/write site was found.

# ETickState.  [M] ctor 0x3EBE0D6 writes 1 (stock default ETickState::Enabled);
# IsActorTickEnabled / IsComponentTickEnabled are exactly "TickState != 0".
TICK_STATE = {0: "Disabled", 1: "Enabled", 2: "CoolingDown"}

# ETickingGroup names are stock UE 5.4 order -- [I], not re-measured here.
TICK_GROUP = {0: "TG_PrePhysics", 1: "TG_StartPhysics", 2: "TG_DuringPhysics",
              3: "TG_EndPhysics", 4: "TG_PostPhysics", 5: "TG_PostUpdateWork",
              6: "TG_LastDemotable", 7: "TG_NewlySpawned"}

# FTickFunction::FInternalData, sizeof 0x30  [M] sized delete "mov edx,0x30" at 0x3EC44B2
ID_FLAGS = 0x00          # bit0 bRegistered [M]: SET at 0x3EC44D7 "or byte [rax],1";
                         #                       TESTED at 0x3EF73CE and 0x3EC402F
ID_ACTUAL_TG = 0x01      # [M] 0x3EED680 movzx ecx, byte [rax+1]
ID_ACTUAL_ETG = 0x02     # [M] 0x3EED688 movzx esi, byte [rax+2]
ID_TASKPOINTER = 0x10    # [M] 0x3EED674 mov [rax+0x10],rbx ; 0x3EED684 mov r14,[rax+0x10]
ID_LASTTICKTIME = 0x24   # [M] 0x3EF7407 mov dword [rax+0x24], 0xbf800000  (= -1.0f)
ID_TICKTASKLEVEL = 0x28  # [M] 0x3EF73DF mov rbx,[rbx+0x28]
ID_SIZE = 0x30
ID_BIT_REGISTERED = 0x01
ID_BIT_WAS_INTERVAL = 0x02   # [I] declaration order; not measured

# Tick-function vtable RVAs -> class name.  Named from each vtable slot 2
# (FTickFunction::DiagnosticMessage), whose only string literal IS the name.  [M]
TICKFN_VTABLE_RVA = {
    0x0823F7A8: "FTickFunction (base)",         # installed by the ctor at 0x3EBE0C0
    0x07E08A68: "FActorTickFunction",           # slot2 0x337EB90 -> U'[TickActor]'
    0x07E08B38: "FActorComponentTickFunction",  # slot2 0x35A95D0 -> U'[TickComponent]'
}

# Useful neighbours on UActorComponent, all [M] from UHT SetBitFunc bodies.
UAC_BIT = {
    "bReplicates":     (0xB0, 0x40),   # setbit 0x3555C10 = or byte [rcx+0xB0],0x40
    "bNetAddressable": (0xB0, 0x10),   # setbit 0x3555BF0 = or byte [rcx+0xB0],0x10
    "bAutoActivate":   (0xB2, 0x04),   # setbit 0x3555C20 = or byte [rcx+0xB2],0x04
    "bIsActive":       (0xB2, 0x08),   # setbit 0x3555C30 = or byte [rcx+0xB2],0x08
}
UAC_OWNER = 0xB8              # [M] S132, and 0x35AA7B1 mov rbx,[rbx+0xb8]
UAC_VT_TICKCOMPONENT = 0x3D0  # [I,strong] ExecuteTick 0x35AA7FD  call [Target->vt+0x3D0] with
                              #   rcx=this, xmm1=DeltaTime*TimeDilation, r8d=TickType, r9=tickfn
                              #   -- exactly TickComponent(float,ELevelTick,FActorComponentTickFunction*).
                              #   UActorComponent 0x35C4370 ; ULokiCharacterMovementComponent
                              #   OVERRIDES it with 0x55C2B90 (two-sided vtable control).
UAC_VT_ADDITIONALSTATOBJECT = 0x440  # [I,strong] ExecuteTick 0x35AA7A2 one-arg call, result
                              #   discarded; both UActorComponent and ULokiCMC read the null fold
                              #   0xF7EB50 there -- an EMPTY base, not a strip.
UAC_BREGISTERED = (0xB0, 0x01)  # [M] ExecuteTick 0x35AA7A8 test byte [Target+0xB0],1 -> HARD GATE:
                              #   TickComponent is not reached unless this bit is set.
UAC_BTICKINEDITOR = (0xB1, 0x40)  # [I] ExecuteTick 0x35AA757 / 0x35AA7BD  test bpl,0x40
ACTOR_CUSTOMTIMEDILATION = 0x78   # [M] ExecuteTick 0x35AA7DD movss xmm1,[Owner+0x78]
ACTOR_VT_SHOULDTICKIFVIEWPORTSONLY = 0x558  # [I,strong] ExecuteTick 0x35AA7CE
CMC_POSTPHYSICS_TICK_OFF = 0x778  # [M] UHT FStructPropertyParams record .rdata 0x7FB19B0


# ---------------------------------------------------------------------------
# pure decode -- no process needed, importable, testable
# ---------------------------------------------------------------------------
def decode_tickfunction(raw, internal=None, image_base=None):
    """raw: >= 0x28 bytes starting AT the FTickFunction (0x30 to also get Target).
       internal: optional >= 0x30 bytes read from *InternalData.
       image_base: live module base, used only to name the vptr."""
    if len(raw) < TF_SIZE:
        raise ValueError("need at least 0x28 bytes")
    vptr, = struct.unpack_from("<Q", raw, TF_VPTR)
    flags = raw[TF_FLAGS]
    state = raw[TF_TICKSTATE]
    interval, = struct.unpack_from("<f", raw, TF_TICKINTERVAL)
    pq_data, = struct.unpack_from("<Q", raw, TF_PREREQ_DATA)
    pq_num, = struct.unpack_from("<i", raw, TF_PREREQ_NUM)
    pq_max, = struct.unpack_from("<i", raw, TF_PREREQ_MAX)
    idata, = struct.unpack_from("<Q", raw, TF_INTERNALDATA)
    target = None
    if len(raw) >= TF_TARGET + 8:
        target, = struct.unpack_from("<Q", raw, TF_TARGET)

    vname = None
    vrva = None
    if image_base:
        vrva = vptr - image_base
        if 0 <= vrva < (1 << 32):
            vname = TICKFN_VTABLE_RVA.get(vrva)
        else:
            vrva = None

    out = {
        "vptr": vptr, "vptr_rva": vrva, "vptr_name": vname,
        "TickGroup": raw[TF_TICKGROUP],
        "TickGroup_name": TICK_GROUP.get(raw[TF_TICKGROUP], "?"),
        "EndTickGroup": raw[TF_ENDTICKGROUP],
        "EndTickGroup_name": TICK_GROUP.get(raw[TF_ENDTICKGROUP], "?"),
        "flags_byte": flags,
        "bTickEvenWhenPaused": bool(flags & TF_BIT_TICK_EVEN_WHEN_PAUSED),
        "bCanEverTick": bool(flags & TF_BIT_CAN_EVER_TICK),
        "bStartWithTickEnabled": bool(flags & TF_BIT_START_WITH_TICK_ENABLED),
        "bAllowTickOnDedicatedServer": bool(flags & TF_BIT_ALLOW_ON_DEDICATED_SERVER),
        "bHighPriority": bool(flags & TF_BIT_HIGH_PRIORITY),
        "bRunOnAnyThread_INFERRED": bool(flags & TF_BIT_RUN_ON_ANY_THREAD),
        "TickState": state, "TickState_name": TICK_STATE.get(state, "?"),
        "bTickFunctionEnabled": state != 0,
        "TickInterval": interval,
        "Prerequisites": {"Data": pq_data, "Num": pq_num, "Max": pq_max},
        "InternalData": idata,
        "Target": target,
    }
    if idata == 0:
        out["bRegistered"] = False
        out["bRegistered_why"] = ("InternalData == NULL -> the tick function was NEVER "
                                  "registered with the tick task manager")
    elif internal is not None and len(internal) >= ID_SIZE:
        f0 = internal[ID_FLAGS]
        out["bRegistered"] = bool(f0 & ID_BIT_REGISTERED)
        out["bWasInterval_INFERRED"] = bool(f0 & ID_BIT_WAS_INTERVAL)
        out["ActualTickGroup"] = internal[ID_ACTUAL_TG]
        out["ActualEndTickGroup"] = internal[ID_ACTUAL_ETG]
        out["TaskPointer"], = struct.unpack_from("<Q", internal, ID_TASKPOINTER)
        out["LastTickGameTimeSeconds"], = struct.unpack_from("<f", internal, ID_LASTTICKTIME)
        out["TickTaskLevel"], = struct.unpack_from("<Q", internal, ID_TICKTASKLEVEL)
    else:
        out["bRegistered"] = None   # InternalData exists but was not read
    return out


def format_decode(d):
    L = []
    L.append("  vptr           0x%016X  rva %s  %s" % (
        d["vptr"],
        ("0x%X" % d["vptr_rva"]) if d["vptr_rva"] is not None else "n/a",
        d["vptr_name"] or "(unknown tick-function class -- NOT evidence of anything)"))
    L.append("  TickGroup      %d (%s)   EndTickGroup %d (%s)" % (
        d["TickGroup"], d["TickGroup_name"], d["EndTickGroup"], d["EndTickGroup_name"]))
    L.append("  flags @+0x0A   0x%02X" % d["flags_byte"])
    for k in ("bTickEvenWhenPaused", "bCanEverTick", "bStartWithTickEnabled",
              "bAllowTickOnDedicatedServer", "bHighPriority", "bRunOnAnyThread_INFERRED"):
        L.append("      %-30s %s" % (k, d[k]))
    L.append("  TickState      %d (%s)  => bTickFunctionEnabled = %s" % (
        d["TickState"], d["TickState_name"], d["bTickFunctionEnabled"]))
    L.append("  TickInterval   %g" % d["TickInterval"])
    L.append("  Prerequisites  Data=0x%X Num=%d Max=%d" % (
        d["Prerequisites"]["Data"], d["Prerequisites"]["Num"], d["Prerequisites"]["Max"]))
    L.append("  InternalData   0x%X" % d["InternalData"])
    L.append("  bRegistered    %s%s" % (
        d["bRegistered"],
        ("   [" + d["bRegistered_why"] + "]") if "bRegistered_why" in d else ""))
    for k in ("ActualTickGroup", "ActualEndTickGroup", "TaskPointer",
              "LastTickGameTimeSeconds", "TickTaskLevel"):
        if k in d:
            v = d[k]
            L.append("      %-26s %s" % (k, ("0x%X" % v) if isinstance(v, int) else v))
    if d["Target"] is not None:
        L.append("  Target(+0x28)  0x%X" % d["Target"])
    return "\n".join(L)


# ---------------------------------------------------------------------------
# live read.  READ-ONLY: PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, nothing else.
# ---------------------------------------------------------------------------
class Reader(object):
    PROCESS_VM_READ = 0x0010
    PROCESS_QUERY_INFORMATION = 0x0400

    def __init__(self, pid):
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k = k
        k.OpenProcess.restype = wt.HANDLE
        self.h = k.OpenProcess(self.PROCESS_VM_READ | self.PROCESS_QUERY_INFORMATION,
                               False, int(pid))
        if not self.h:
            raise OSError("OpenProcess(%d) failed: %d" % (pid, ctypes.get_last_error()))

    def read(self, addr, n):
        buf = (ctypes.c_ubyte * n)()
        got = ctypes.c_size_t(0)
        ok = self.k.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n,
                                      ctypes.byref(got))
        if not ok or got.value != n:
            return None
        return bytes(bytearray(buf))

    def close(self):
        if self.h:
            self.k.CloseHandle(self.h)
            self.h = None


def sniff(pid, base, ptr, kind="component"):
    """kind 'component' -> ptr is a UActorComponent*; 'actor' -> ptr is an AActor*."""
    off = COMP_TICK_OFF if kind == "component" else ACTOR_TICK_OFF
    r = Reader(pid)
    try:
        tf_addr = ptr + off
        raw = r.read(tf_addr, 0x30)          # 0x28 struct + Target at +0x28
        if raw is None:
            print("READ FAILED at 0x%X -- wrong pointer, wrong pid, or unmapped." % tf_addr)
            return None
        d = decode_tickfunction(raw, None, base)
        if d["InternalData"]:
            internal = r.read(d["InternalData"], ID_SIZE)
            if internal is not None:
                d = decode_tickfunction(raw, internal, base)

        print("object     0x%X  (%s)   tickfn @ 0x%X  (+0x%X)" % (ptr, kind, tf_addr, off))
        # ---- BUILT-IN POSITIVE CONTROL ----------------------------------
        # For a PRIMARY tick function, Target (tickfn+0x28) is the owning object
        # itself.  If this fails, the pointer or the offset is wrong and every field
        # below is plausible-looking garbage.  This is what catches the
        # self-validating wrong read.
        ctrl = (d["Target"] == ptr)
        print("CONTROL    Target(+0x28) == object pointer  : %s%s" % (
            "PASS" if ctrl else "FAIL",
            "" if ctrl else "   <-- DECODE IS NOT TRUSTWORTHY"))
        print("CONTROL    vptr is a known tick-fn class     : %s (%s)" % (
            "PASS" if d["vptr_name"] else "UNKNOWN", d["vptr_name"] or "?"))
        print(format_decode(d))

        if kind == "component":
            extra = r.read(ptr + 0xB0, 0x10)
            if extra:
                print("  UActorComponent  +0xB0=0x%02X +0xB1=0x%02X +0xB2=0x%02X" % (
                    extra[0], extra[1], extra[2]))
                for nm in sorted(UAC_BIT):
                    o, m = UAC_BIT[nm]
                    print("      %-18s %s" % (nm, bool(extra[o - 0xB0] & m)))
                own, = struct.unpack_from("<Q", extra, UAC_OWNER - 0xB0)
                print("      Owner(+0xB8)       0x%X" % own)
        return d
    finally:
        r.close()


# ---------------------------------------------------------------------------
# offline selftest against the cold image
# ---------------------------------------------------------------------------
DEFAULT_IMAGE = os.path.join("G:\\", "git", "Supervive Revival Project", "dumps",
                             "merged13.dump.exe")

POSITIVE = [
    (0x35BC510, "48895c240857 4883ec20 f6414a02",
     "UActorComponent::SetComponentTickEnabled tests [this+0x4A]&2 -> tick@+0x40, bCanEverTick=+0x0A bit1"),
    (0x339B750, "48895c240857 4883ec20 f6414202",
     "AActor::SetActorTickEnabled tests [this+0x42]&2 -> tick@+0x38, same bit"),
    (0x35BC6D0, "f30f11494c c3",
     "UActorComponent::SetComponentTickInterval writes [this+0x4C] -> TickInterval @ tick+0x0C"),
    (0x339B790, "f30f114944 c3",
     "AActor::SetActorTickInterval writes [this+0x44] -> same"),
    (0x35AC610, "f30f10414c c3", "UActorComponent::GetComponentTickInterval reads [this+0x4C]"),
    (0x3386300, "f30f104144 c3", "AActor::GetActorTickInterval reads [this+0x44]"),
    (0x35B1E40, "80794b00 0f95c0 c3",
     "UActorComponent::IsComponentTickEnabled = [this+0x4B]!=0 -> TickState @ tick+0x0B"),
    (0x338EAC0, "807943000f95c0c3", "AActor::IsActorTickEnabled = [this+0x43]!=0 -> same"),
    (0x339E930, "885140 c3", "AActor::SetTickGroup writes byte [this+0x40] -> TickGroup @ tick+0x08"),
    (0x35BE260, "885148 c3", "UActorComponent::SetTickGroup writes byte [this+0x48] -> same"),
    (0x339E940, "0fb6414224fe0ac2884142c3",
     "AActor::SetTickableWhenPaused rmw [this+0x42] mask 0x01 -> bTickEvenWhenPaused = +0x0A bit0"),
    (0x35BE270, "0fb6414a24fe0ac288414ac3",
     "UActorComponent::SetTickableWhenPaused rmw [this+0x4A] mask 0x01 -> same"),
    (0x32BB170, "80490a01c3", "UHT SetBitFunc bTickEvenWhenPaused         -> or [rcx+0x0A],0x01"),
    (0x32BB180, "80490a02c3", "UHT SetBitFunc bCanEverTick                -> or [rcx+0x0A],0x02"),
    (0x32BB190, "80490a04c3", "UHT SetBitFunc bStartWithTickEnabled       -> or [rcx+0x0A],0x04"),
    (0x32BB1A0, "80490a08c3", "UHT SetBitFunc bAllowTickOnDedicatedServer -> or [rcx+0x0A],0x08"),
    (0x3EBE0C0, "488d05", "FTickFunction::FTickFunction begins with the vtable LEA"),
    (0x3EBE0C7, "66c741080000",
     "ctor: mov word [rcx+8],0 -- ONE 2-byte store covers TickGroup+EndTickGroup"),
    (0x3EBE0CD, "488901", "ctor: mov [rcx],rax -- FTickFunction HAS a vptr at +0x00"),
    (0x3EBE0D0, "0fb6410a 24c8", "ctor: read-modify-write of the +0x0A flag byte"),
    (0x3EBE0D6, "c6410b01", "ctor: TickState = 1 -> ETickState::Enabled == 1"),
    (0x3EBE0DA, "0c08",
     "ctor: or al,8 -> bAllowTickOnDedicatedServer defaults TRUE (stock UE default)"),
    (0x3EBE0E1, "89410c", "ctor: TickInterval = 0"),
    (0x3EBE0E4, "488941104889411848894120",
     "ctor zeroes +0x10/+0x18/+0x20 and stops -> sizeof(FTickFunction) == 0x28"),
    (0x3EF73BF, "488b5920", "SetTickFunctionEnable: mov rbx,[rcx+0x20] -> InternalData @ +0x20"),
    (0x3EF73CE, "f60301",
     "SetTickFunctionEnable: test byte [InternalData],1 -> bRegistered = bit0 of *InternalData"),
    (0x3EC44D7, "800801", "tick registrar 0x3EC4390: or byte [InternalData],1 -- SETS bRegistered"),
    (0x3EF6F09, "0fb6510a", "SetPriorityIncludingPrerequisites reads +0x0A ..."),
    (0x3EF6F10, "c0e804 2401", "... shr 4 / and 1 -> bHighPriority = +0x0A bit4 (0x10)"),
    (0x35AA72F, "488b5928", "FActorComponentTickFunction::ExecuteTick: Target @ tickfn+0x28"),
    (0x33831AA, "488b4128", "FActorTickFunction::ExecuteTick: Target @ tickfn+0x28"),
    (0x35AA7A2, "ff9040040000",
     "ExecuteTick: one-arg virtual at component vt disp 0x440, result discarded (AdditionalStatObject)"),
    (0x35AA7A8, "f683b00000000174",
     "ExecuteTick: test byte [Target+0xB0],1 / je -- UActorComponent::bRegistered HARD GATE"),
    (0x35AA7EC, "488b4f28 4c8bcf",
     "ExecuteTick: rcx = tickfn->Target, r9 = tickfn ..."),
    (0x35AA7FD, "ff90d0030000",
     "... call [Target->vtable+0x3D0] = TickComponent(float,ELevelTick,FActorComponentTickFunction*)"),
    (0x3596B04, "488d4f40", "UActorComponent ctor: lea rcx,[this+0x40] before the FTickFunction ctor"),
    (0x3596B1F, "48894740", "UActorComponent ctor: mov [this+0x40], FActorComponentTickFunction vtable"),
    (0x3371821, "488d4f38", "AActor ctor: lea rcx,[this+0x38]"),
    (0x3371836, "48894738", "AActor ctor: mov [this+0x38], FActorTickFunction vtable"),
    (0x3555C30, "8089b200000008c3", "UHT SetBitFunc UActorComponent::bIsActive -> or [rcx+0xB2],0x08"),
    (0x3555C20, "8089b200000004c3", "UHT SetBitFunc UActorComponent::bAutoActivate -> or [rcx+0xB2],0x04"),
]

NEGATIVE = [
    (0x35BC510, "f6414202", "the COMPONENT setter must NOT use the ACTOR offset 0x42"),
    (0x339B750, "f6414a02", "the ACTOR setter must NOT use the COMPONENT offset 0x4A"),
    (0x32BB180, "80490a20c3", "bCanEverTick is not bit5"),
    (0x00F7EC20, "48895c2408", "the void fold 0xF7EC20 is not a real prologue (fold sanity)"),
]


def selftest(image=DEFAULT_IMAGE):
    if not os.path.exists(image):
        print("SELFTEST SKIPPED: image not found: %s" % image)
        return 2
    data = open(image, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        print("not a PE")
        return 1
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    for i in range(nsec):
        o = pe + 24 + optsz + i * 40
        vsz, va, rsz, rptr = struct.unpack_from("<IIII", data, o + 8)
        if va != rptr:
            print("IMAGE IS NOT FLAT (va != rptr) -- these RVAs are not file offsets")
            return 1
    print("image      %s   (%d bytes, flat: RVA == file offset)" % (image, len(data)))

    npass = nfail = 0
    print("\n--- POSITIVE CONTROLS (bytes must be PRESENT) ---")
    for rva, hexs, why in POSITIVE:
        want = bytes.fromhex(hexs.replace(" ", ""))
        got = data[rva:rva + len(want)]
        ok = (got == want)
        npass += ok
        nfail += (not ok)
        print("  %-4s 0x%08X  %s" % ("PASS" if ok else "FAIL", rva, why))
        if not ok:
            print("        want %s" % want.hex())
            print("        got  %s" % got.hex())
    print("\n--- NEGATIVE CONTROLS (bytes must be ABSENT) ---")
    for rva, hexs, why in NEGATIVE:
        bad = bytes.fromhex(hexs.replace(" ", ""))
        ok = (data[rva:rva + len(bad)] != bad)
        npass += ok
        nfail += (not ok)
        print("  %-4s 0x%08X  %s" % ("PASS" if ok else "FAIL", rva, why))

    print("\n--- DECODER ROUND-TRIP on a synthetic tick function built to the ctor defaults ---")
    base = 0x7FF608F40000
    syn = bytearray(0x30)
    struct.pack_into("<Q", syn, TF_VPTR, base + 0x07E08B38)
    syn[TF_FLAGS] = 0x08
    syn[TF_TICKSTATE] = 1
    d = decode_tickfunction(bytes(syn), None, base)
    checks = [
        (d["vptr_name"] == "FActorComponentTickFunction", "vptr names FActorComponentTickFunction"),
        (d["bAllowTickOnDedicatedServer"] is True, "ctor default bAllowTickOnDedicatedServer == True"),
        (d["bCanEverTick"] is False, "ctor default bCanEverTick == False"),
        (d["bTickFunctionEnabled"] is True, "ctor default TickState == Enabled"),
        (d["bRegistered"] is False, "InternalData == NULL decodes as bRegistered False"),
    ]
    for ok, why in checks:
        npass += ok
        nfail += (not ok)
        print("  %-4s %s" % ("PASS" if ok else "FAIL", why))

    print("\nSELFTEST: %d pass, %d fail" % (npass, nfail))
    return 0 if nfail == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--base", type=lambda s: int(s, 0),
                    help="live SUPERVIVE-Win64-Shipping module base")
    ap.add_argument("--comp", type=lambda s: int(s, 0), help="UActorComponent*")
    ap.add_argument("--actor", type=lambda s: int(s, 0), help="AActor*")
    a = ap.parse_args()
    if a.selftest or not (a.pid and (a.comp or a.actor)):
        return selftest(a.image)
    if a.comp:
        sniff(a.pid, a.base or 0, a.comp, "component")
    if a.actor:
        sniff(a.pid, a.base or 0, a.actor, "actor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
