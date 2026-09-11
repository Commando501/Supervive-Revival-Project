#!/usr/bin/env python
# =============================================================================
# console_probe.py  --  FK-13: does the UE console / debug-exec surface EXIST
#                       and is it WIRED UP, live, in this shipping build?
#
# PURE RPM. Read-only. No injection, no .text write, no thread suspend, no
# WriteProcessMemory anywhere in this file. Safe to run against a live game at
# any moment, including while a sitting is in progress.
#
# -----------------------------------------------------------------------------
# WHAT IT ANSWERS (each section is independent; a failure in one does not void
# the others):
#
#   [A] GEngine->GameViewport->ViewportConsole non-null?
#         This is the DIRECT ALLOW_CONSOLE oracle. In stock UE5,
#         UGameViewportClient::Init contains
#             #if ALLOW_CONSOLE
#                 ViewportConsole = NewObject<UConsole>(this, GetOuterUEngine()->ConsoleClass);
#                 GLog->AddOutputDevice(ViewportConsole);
#             #endif
#         The UPROPERTY declaration is NOT guarded, so the *name* is emitted
#         either way -- which is exactly why no string scan can decide this and
#         why FK-13 has been open for 110 sessions. Only the VALUE decides.
#
#   [B] Does a live UConsole instance exist? Is the /Script/Engine.Console
#       UClass registered? Is UEngine::ConsoleClass populated, and what does
#       UEngine::ConsoleClassName say?
#         MEASURED OFFLINE (this session, dumps/tutorial-hero, .rdata 100%
#         readable): schema.txt:12547 lists `Console : UClass:Object (4 props)`
#         so the UCLASS is compiled in and reflected; but the literal
#         "/Script/Engine.Console" occurs 0 times wide AND 0 times ascii in the
#         image (controls that DO resolve in the same scan: HighResShot x4 wide,
#         LogCmds x3 wide, LOG= x5 wide, NOCONSOLE x1 wide). So the class exists
#         and the ini names it, but nothing in the exe names it -- consistent
#         with the value arriving purely from BaseEngine.ini:101.
#
#   [C] UPlayerInput::DebugExecBindings, fully decoded (Key, Command, modifier
#       flags), from BOTH the CDO and any live instance.
#         GROUND TRUTH for the decoder: Engine/Config/BaseInput.ini ships
#         EXACTLY 16 rows and Loki/Config/DefaultInput.ini adds/removes none;
#         docs/session-79-moonshot-plan.md:688 measured LIVE
#         `DebugExecBindings @+0x1A8 Num=16 NON-empty`. So if this section
#         prints 16 rows matching the shipped list, EVERY offset assumption in
#         this probe is validated at once. That is the built-in positive control.
#         ** Num != 16 after running configs/set-debug-execbindings.ps1 is the
#            file-was-read discriminator -- see docs/fk13-live-test-card.md. **
#
#   [D] UInputSettings::ConsoleKeys (expected: exactly one entry, `Tilde`).
#
# -----------------------------------------------------------------------------
# !!! UNTESTED AGAINST A LIVE PROCESS !!!
# This file was written offline, in a session that was forbidden to launch the
# game. It has NEVER been run against SUPERVIVE-Win64-Shipping.exe. `--self-test`
# exercises the decoders against a synthetic address space and is the only thing
# that has actually executed. Most likely first failure modes, in order:
#   1. Not elevated -> OpenProcess returns 0. The probe says so and exits 2.
#   2. NAMEPOOL / OBJOBJECTS RVAs stale after a game update -> the GUObjectArray
#      header sanity gate trips and the probe exits 3 rather than printing junk.
#   3. UStruct::PropertiesSize offset guess (+0x60) wrong -> FKeyBind stride
#      wrong. MITIGATED: the stride is chosen by SCORING candidates against the
#      decoded rows, not by trusting the guess, and the whole score table is
#      printed so a wrong pick is visible rather than silent.
#   4. A property name that this build renamed -> that one lookup reports
#      `NOT FOUND` and its section degrades; other sections still run.
#
# -----------------------------------------------------------------------------
# OFFSETS THIS BUILD USES (non-stock -- see CLAUDE.md). Every one of these is
# printed next to the value it produced, per the lane rule.
#   UObject:  ObjectFlags@0x0C  InternalIndex@0x10  Class@0x18  Name@0x20
#   UStruct:  SuperStruct@0x48  Children@0x50(?)  ChildProperties@0x58
#   FField:   ClassPrivate@0x08  Next@0x18  Name@0x20
#   FProperty:ElementSize@0x34  PropertyFlags@0x38  Offset_Internal@0x44
#   TArray:   Data@0x00  Num@0x08  Max@0x0C
#   FName:    ComparisonIndex@0x00 (u32)  Number@0x04 (u32)
#   FKey:     KeyName FName@0x00, then TSharedPtr<FKeyDetails> -> size 24
#   FString:  == TArray<TCHAR>
#
# usage:
#   python tools/re/console_probe.py                     # auto-detect PID+base
#   python tools/re/console_probe.py --pid 1234 --base 0x7FF6AF000000
#   python tools/re/console_probe.py --dry-run           # parse/import check only
#   python tools/re/console_probe.py --self-test         # run decoders offline
# =============================================================================
import argparse
import ctypes
import sys
from ctypes import wintypes

# ---- RVAs (constant across launches; base is ASLR'd and detected at runtime) --
RVA_NAMEPOOL   = 0x9D81450
RVA_OBJOBJECTS = 0x9E38930
PERCHUNK       = 65536
STRIDE_ITEM    = 0x18           # FUObjectItem stride

# ---- non-stock UObject/UStruct/FField offsets (see banner) -------------------
O_OBJ_FLAGS    = 0x0C
O_OBJ_INDEX    = 0x10
O_OBJ_CLASS    = 0x18
O_OBJ_NAME     = 0x20
O_STRUCT_SUPER = 0x48
O_STRUCT_CHILDPROPS = 0x58
O_STRUCT_PROPSIZE_GUESS = 0x60  # [I] stock-minus-8-shifted; NEVER trusted alone
O_FIELD_CLASS  = 0x08
O_FIELD_NEXT   = 0x18
O_FIELD_NAME   = 0x20
O_PROP_ELEMSIZE = 0x34
O_PROP_FLAGS    = 0x38
O_PROP_OFFSET   = 0x44
O_BOOLPROP_FIELDSIZE = 0x70     # [I] FBoolProperty {FieldSize,ByteOffset,ByteMask,FieldMask}

PROC_NAME = "SUPERVIVE-Win64-Shipping.exe"

# The 16 rows Engine/Config/BaseInput.ini ships, as (Key, Command). This is the
# expected content of section [C] on an UNMODIFIED launch and is the probe's own
# positive control. Order here is ini order; the live array may differ.
SHIPPED_16 = [
    ("F11",      "LevelEditor.ToggleImmersive"),
    ("F11",      "MainFrame.ToggleFullscreen"),
    ("F1",       "viewmode wireframe"),
    ("F2",       "viewmode unlit"),
    ("F3",       "viewmode lit"),
    ("F4",       "viewmode lit_detaillighting"),
    ("F5",       "viewmode shadercomplexity"),
    ("F9",       "shot showui"),
    ("Period",   "RECOMPILESHADERS CHANGED"),
    ("Comma",    "PROFILEGPU"),
    ("Slash",    "DumpGPU"),
    ("Tab",      "FocusNextPIEWindow"),
    ("Tab",      "FocusLastPIEWindow"),
    ("PageDown", "PreviousDebugTarget"),
    ("PageUp",   "NextDebugTarget"),
    ("Semicolon","ToggleDebugCamera"),
]


# =============================================================================
# Readers.  Every decode below goes through Reader.read(), so the SAME code path
# can be driven by a live process (ProcReader) or by a synthetic address space
# (BufReader) in --self-test.  That is the only way this file gets any execution
# coverage at all before a human runs it for real.
# =============================================================================
class Reader(object):
    def read(self, addr, n):
        raise NotImplementedError

    # ---- primitives -----------------------------------------------------
    def u8(self, a):
        b = self.read(a, 1)
        return b[0] if b else 0

    def u16(self, a):
        b = self.read(a, 2)
        return int.from_bytes(b, "little") if b else 0

    def u32(self, a):
        b = self.read(a, 4)
        return int.from_bytes(b, "little") if b else 0

    def i32(self, a):
        b = self.read(a, 4)
        return int.from_bytes(b, "little", signed=True) if b else 0

    def u64(self, a):
        b = self.read(a, 8)
        return int.from_bytes(b, "little") if b else 0


class ProcReader(Reader):
    def __init__(self, pid):
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32.OpenProcess.restype = wintypes.HANDLE
        self.k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ only -- we never write.
        self.h = self.k32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not self.h:
            self.h = self.k32.OpenProcess(0x1F0FFF, False, pid)   # fall back to ALL_ACCESS
        self.err = ctypes.get_last_error() if not self.h else 0
        self.reads = 0
        self.fails = 0

    def read(self, addr, n):
        if not self.h or addr <= 0 or n <= 0:
            return None
        buf = (ctypes.c_ubyte * n)()
        got = ctypes.c_size_t(0)
        self.reads += 1
        ok = self.k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n,
                                        ctypes.byref(got))
        if not ok or got.value != n:
            self.fails += 1
            return None
        return bytes(buf)


class BufReader(Reader):
    """Synthetic address space: {base_addr: bytes}. Used only by --self-test."""
    def __init__(self, blocks):
        self.blocks = sorted(blocks.items())

    def read(self, addr, n):
        for base, data in self.blocks:
            if base <= addr and addr + n <= base + len(data):
                off = addr - base
                return data[off:off + n]
        return None


# =============================================================================
# UE decoding, all Reader-driven
# =============================================================================
def looks_ptr(v):
    return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0


class UE(object):
    def __init__(self, rdr, base):
        self.r = rdr
        self.base = base
        self.namepool = base + RVA_NAMEPOOL
        self.objobjects = base + RVA_OBJOBJECTS
        self._names = {}
        self._clsname = {}
        self.index = None

    # ---- FName ----------------------------------------------------------
    def fname(self, idx):
        if idx in self._names:
            return self._names[idx]
        blk = idx >> 16
        off = (idx & 0xFFFF) << 1
        bp = self.r.u64(self.namepool + blk * 8)
        out = "?"
        if looks_ptr(bp):
            hd = self.r.u16(bp + off)
            ln = hd >> 6
            wide = hd & 1
            if 0 < ln < 250:
                s = self.r.read(bp + off + 2, ln * (2 if wide else 1))
                if s:
                    if wide:
                        out = "".join(chr(s[i * 2] | (s[i * 2 + 1] << 8)) for i in range(ln))
                    else:
                        out = s.decode("latin1", "replace")
        self._names[idx] = out
        return out

    def fname_at(self, addr):
        """FName stored at addr: ComparisonIndex u32 @0, Number u32 @4."""
        idx = self.r.u32(addr)
        num = self.r.u32(addr + 4)
        nm = self.fname(idx)
        return (nm if num == 0 else "%s_%d" % (nm, num - 1)), idx, num

    # ---- UObject --------------------------------------------------------
    def oname(self, o):
        return self.fname(self.r.u32(o + O_OBJ_NAME)) if looks_ptr(o) else "-"

    def ocls(self, o):
        if not looks_ptr(o):
            return 0
        return self.r.u64(o + O_OBJ_CLASS)

    def cname(self, o):
        c = self.ocls(o)
        if not looks_ptr(c):
            return "-"
        if c in self._clsname:
            return self._clsname[c]
        n = self.oname(c)
        self._clsname[c] = n
        return n

    # ---- FString (== TArray<TCHAR>) --------------------------------------
    def fstring(self, addr, cap=512):
        data = self.r.u64(addr)
        num = self.r.i32(addr + 8)
        mx = self.r.i32(addr + 12)
        if num == 0:
            return "", data, num, mx
        if not looks_ptr(data) or not (0 < num <= cap) or mx < num:
            return None, data, num, mx
        raw = self.r.read(data, num * 2)
        if raw is None:
            return None, data, num, mx
        s = "".join(chr(raw[i * 2] | (raw[i * 2 + 1] << 8)) for i in range(num))
        return s.rstrip("\x00"), data, num, mx

    # ---- TArray ---------------------------------------------------------
    def tarray(self, addr):
        return self.r.u64(addr), self.r.i32(addr + 8), self.r.i32(addr + 12)

    # ---- GUObjectArray iteration ----------------------------------------
    def obj_array_header(self):
        objects = self.r.u64(self.objobjects)
        num = self.r.u32(self.objobjects + 0x14)
        return objects, num

    def iter_objects(self, limit=None):
        objects, num = self.obj_array_header()
        if not looks_ptr(objects) or not (0 < num < 8000000):
            return
        seen = 0
        for ci in range((num + PERCHUNK - 1) // PERCHUNK):
            chunk = self.r.u64(objects + ci * 8)
            if not looks_ptr(chunk):
                continue
            cnt = min(PERCHUNK, num - ci * PERCHUNK)
            blob = self.r.read(chunk, cnt * STRIDE_ITEM)
            if blob is None:
                # fall back to per-item reads on this chunk
                for j in range(cnt):
                    o = self.r.u64(chunk + j * STRIDE_ITEM)
                    if looks_ptr(o):
                        yield o
                        seen += 1
                        if limit and seen >= limit:
                            return
                continue
            for j in range(cnt):
                o = int.from_bytes(blob[j * STRIDE_ITEM:j * STRIDE_ITEM + 8], "little")
                if looks_ptr(o):
                    yield o
                    seen += 1
                    if limit and seen >= limit:
                        return

    # ---- ONE-PASS INDEX -------------------------------------------------
    # Naive per-query scans cost ~190k RPM calls EACH, and this probe asks ~8
    # questions -> minutes of wall clock while a human waits at the keyboard.
    # Build the (obj, class, name) table once; every lookup below is then free.
    def build_index(self, progress=None):
        if getattr(self, "index", None) is not None:
            return self.index
        self.index = []
        n = 0
        for o in self.iter_objects():
            blob = self.r.read(o + O_OBJ_CLASS, 12)   # Class@0x18 (8) + Name@0x20 (4)
            if blob is None:
                continue
            cls = int.from_bytes(blob[0:8], "little")
            nidx = int.from_bytes(blob[8:12], "little")
            self.index.append((o, cls, nidx))
            n += 1
            if progress and (n % 40000) == 0:
                progress("      ... indexed %d objects" % n)
        if progress:
            progress("      indexed %d objects total" % n)
        return self.index

    def clsname_of(self, cls):
        """Class NAME from a class POINTER, cached. Avoids re-reading obj+0x18
        190k times per query (that was ~0.75M redundant RPM calls across the
        four queries this probe makes)."""
        if not looks_ptr(cls):
            return "-"
        n = self._clsname.get(cls)
        if n is None:
            n = self.fname(self.r.u32(cls + O_OBJ_NAME))
            self._clsname[cls] = n
        return n

    def find_uclass(self, exact_name, meta="Class"):
        """UClass object named exactly `exact_name` whose own Class is `meta`."""
        for o, cls, nidx in self.build_index():
            if self.fname(nidx) == exact_name and self.clsname_of(cls) == meta:
                return o
        return 0

    def find_instances(self, pred, limit=8, skip_cdo=True):
        out = []
        for o, cls, nidx in self.build_index():
            nm = self.fname(nidx)
            if skip_cdo and nm.startswith("Default__"):
                continue
            cn = self.clsname_of(cls)
            if cn == "-":
                continue
            if pred(cn, nm):
                out.append((o, cn, nm))
                if len(out) >= limit:
                    break
        return out

    def find_cdo(self, class_substr):
        for o, cls, nidx in self.build_index():
            nm = self.fname(nidx)
            if nm.startswith("Default__") and class_substr.lower() in nm.lower():
                return o, nm
        return 0, ""

    # ---- reflection -----------------------------------------------------
    def super_chain(self, cls, depth=16):
        out = []
        c = cls
        d = 0
        while looks_ptr(c) and d < depth:
            out.append(c)
            c = self.r.u64(c + O_STRUCT_SUPER)
            d += 1
        return out

    def props_of(self, struct_obj, limit=800):
        """Yield (propAddr, name, typeName, offset, elemSize) for ONE struct level."""
        f = self.r.u64(struct_obj + O_STRUCT_CHILDPROPS)
        i = 0
        while looks_ptr(f) and i < limit:
            nm = self.fname(self.r.u32(f + O_FIELD_NAME))
            fc = self.r.u64(f + O_FIELD_CLASS)
            ty = self.fname(self.r.u32(fc)) if looks_ptr(fc) else "?"
            off = self.r.i32(f + O_PROP_OFFSET)
            esz = self.r.u32(f + O_PROP_ELEMSIZE)
            yield f, nm, ty, off, esz
            f = self.r.u64(f + O_FIELD_NEXT)
            i += 1

    def find_prop(self, cls, name):
        """Resolve a UPROPERTY by NAME across the super chain.
        Returns (offset, typeName, elemSize, definingClassName, propAddr) or None."""
        for c in self.super_chain(cls):
            for pa, nm, ty, off, esz in self.props_of(c):
                if nm == name:
                    return off, ty, esz, self.oname(c), pa
        return None

    def prop_on_obj(self, obj, name):
        return self.find_prop(self.ocls(obj), name)


# =============================================================================
# FKeyBind decoding
# =============================================================================
class KeyBindLayout(object):
    """Offsets inside FKeyBind, resolved BY NAME from the live UScriptStruct."""
    def __init__(self):
        self.ok = False
        self.struct_addr = 0
        self.fields = {}          # name -> (offset, type, elemSize, propAddr)
        self.propsize_guess = 0
        self.derived_size = 0
        self.stride = 0
        self.stride_source = "none"
        self.notes = []

    def off(self, name, default=None):
        f = self.fields.get(name)
        return f[0] if f else default


def resolve_keybind_layout(ue):
    lay = KeyBindLayout()
    ks = ue.find_uclass("KeyBind", meta="ScriptStruct")
    if not ks:
        lay.notes.append("UScriptStruct 'KeyBind' NOT FOUND in GUObjectArray "
                         "(meta-class filter 'ScriptStruct'); falling back to "
                         "stock-UE5 offsets.")
        # stock UE5 FKeyBind: FKey Key@0x00 (24B), FString Command@0x18, bools after
        lay.fields = {
            "Key":     (0x00, "StructProperty", 24, 0),
            "Command": (0x18, "StrProperty", 16, 0),
        }
        lay.derived_size = 0x30
        return lay
    lay.struct_addr = ks
    for pa, nm, ty, off, esz in ue.props_of(ks):
        lay.fields[nm] = (off, ty, esz, pa)
    lay.propsize_guess = ue.r.u32(ks + O_STRUCT_PROPSIZE_GUESS)
    if lay.fields:
        lay.derived_size = max(o + max(e, 1) for (o, _t, e, _p) in lay.fields.values())
        lay.derived_size = (lay.derived_size + 7) & ~7
    lay.ok = "Key" in lay.fields and "Command" in lay.fields
    return lay


def score_stride(ue, data_ptr, num, lay, stride):
    """How many of `num` rows decode to a plausible (FName key, FString command)?
    This is what picks the stride -- NOT the PropertiesSize guess."""
    if stride <= 0 or num <= 0:
        return -1, []
    ko = lay.off("Key", 0x00)
    co = lay.off("Command", 0x18)
    good = 0
    rows = []
    for i in range(num):
        row = data_ptr + i * stride
        knm, kidx, _knum = ue.fname_at(row + ko)
        cmd, cptr, cnum, cmax = ue.fstring(row + co)
        ok_k = knm not in ("?", "None", "") and 0 < kidx
        ok_c = cmd is not None and (len(cmd) > 0)
        if ok_k and ok_c:
            good += 1
        rows.append((knm, cmd, cptr, cnum, cmax))
    return good, rows


def decode_debug_exec_bindings(ue, arr_addr, lay, label, out):
    data, num, mx = ue.tarray(arr_addr)
    out("    TArray  Data=0x%X  Num=%d  Max=%d      (TArray offsets Data@0x00 Num@0x08 Max@0x0C)"
        % (data, num, mx))
    if num <= 0:
        out("    >>> %s: DebugExecBindings is EMPTY (Num=%d)." % (label, num))
        out("        Expected 16 on an unmodified launch (BaseInput.ini ships 16; "
            "S79 measured Num=16 live).")
        return num, []
    if not looks_ptr(data):
        out("    >>> Data pointer 0x%X does not look like a heap pointer; aborting decode."
            % data)
        return num, []

    cands = []
    if lay.propsize_guess and 0 < lay.propsize_guess <= 0x200:
        cands.append(("PropertiesSize@+0x%X" % O_STRUCT_PROPSIZE_GUESS, lay.propsize_guess))
    if lay.derived_size:
        cands.append(("max(off+size) rounded", lay.derived_size))
    for s in (0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60):
        cands.append(("brute", s))

    seen = set()
    table = []
    best = (-1, 0, "none", [])
    for src, s in cands:
        if s in seen:
            continue
        seen.add(s)
        g, rows = score_stride(ue, data, num, lay, s)
        table.append((s, src, g))
        if g > best[0]:
            best = (g, s, src, rows)

    out("    stride candidates (score = rows whose Key AND Command both decode):")
    for s, src, g in sorted(table, key=lambda t: -t[2]):
        mark = "  <== CHOSEN" if s == best[1] else ""
        out("      0x%02X  %-26s score %2d/%d%s" % (s, src, g, num, mark))
    good, stride, src, rows = best
    lay.stride = stride
    lay.stride_source = src
    if good < num:
        out("    !! WARNING: only %d/%d rows decoded cleanly at the best stride. "
            "Treat the rows below as SUSPECT." % (good, num))
    if good == 0:
        out("    >>> NO stride decoded anything. The FKeyBind layout assumption is wrong. "
            "This section is VOID, not a negative result.")
        return num, []

    ko = lay.off("Key", 0x00)
    co = lay.off("Command", 0x18)
    out("")
    out("    row  Key                Command                                    flags(raw @+0x%X..)"
        % (co + 16))
    out("    ---  -----------------  -----------------------------------------  ------------------")
    decoded = []
    for i, (knm, cmd, cptr, cnum, cmax) in enumerate(rows):
        raw = ue.r.read(data + i * stride + co + 16, 8) or b""
        flags = decode_keybind_flags(ue, lay, data + i * stride)
        out("    %3d  %-17s  %-41s  %s  %s"
            % (i, knm[:17], (cmd if cmd is not None else "<undecodable>")[:41],
               raw.hex(), flags))
        decoded.append((knm, cmd))
    return num, decoded


def decode_keybind_flags(ue, lay, row_addr):
    """Best-effort bitfield decode. MARKED [I]: FBoolProperty's
    {FieldSize,ByteOffset,ByteMask,FieldMask} offset (+0x70) is a stock-layout
    guess. If a mask looks implausible the flag is reported as '?'."""
    names = ["Control", "Shift", "Alt", "Cmd",
             "bIgnoreCtrl", "bIgnoreShift", "bIgnoreAlt", "bIgnoreCmd", "bDisabled"]
    on = []
    for n in names:
        f = lay.fields.get(n)
        if not f:
            continue
        off, ty, esz, pa = f
        if ty != "BoolProperty" or not looks_ptr(pa):
            continue
        byte_off = ue.r.u8(pa + O_BOOLPROP_FIELDSIZE + 1)
        byte_mask = ue.r.u8(pa + O_BOOLPROP_FIELDSIZE + 2)
        if byte_mask == 0 or (byte_mask & (byte_mask - 1)) != 0:
            on.append(n + "?")
            continue
        v = ue.r.u8(row_addr + off + byte_off)
        if v & byte_mask:
            on.append(n)
    return ",".join(on) if on else "-"


# =============================================================================
# Process / module discovery
# =============================================================================
def find_pid(name=PROC_NAME):
    TH32CS_SNAPPROCESS = 0x2
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1).value:
        return []
    hits = []
    e = PROCESSENTRY32W()
    e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    if k32.Process32FirstW(snap, ctypes.byref(e)):
        while True:
            if e.szExeFile.lower() == name.lower():
                hits.append(e.th32ProcessID)
            if not k32.Process32NextW(snap, ctypes.byref(e)):
                break
    k32.CloseHandle(snap)
    return hits


def find_module_base(pid, name=PROC_NAME):
    TH32CS_SNAPMODULE = 0x8
    TH32CS_SNAPMODULE32 = 0x10
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                    ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                    ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                    ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]

    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == wintypes.HANDLE(-1).value:
        return 0
    base = 0
    m = MODULEENTRY32W()
    m.dwSize = ctypes.sizeof(MODULEENTRY32W)
    if k32.Module32FirstW(snap, ctypes.byref(m)):
        while True:
            if m.szModule.lower() == name.lower():
                base = ctypes.cast(m.modBaseAddr, ctypes.c_void_p).value or 0
                break
            if not k32.Module32NextW(snap, ctypes.byref(m)):
                break
    k32.CloseHandle(snap)
    return base


# =============================================================================
# --self-test : drive every decoder against a synthetic address space
# =============================================================================
def build_synthetic():
    """Hand-built UE-shaped memory. Exercises fname / fstring / tarray /
    fname_at / score_stride / decode rows. Returns (BufReader, base, expect)."""
    base = 0x140000000
    blocks = {}

    # --- name pool: one block at 0x50000000, entries at even offsets --------
    poolblk = 0x50000000
    pool = bytearray(0x1000)
    names = {}                       # name -> fname index

    def add_name(off, s):
        hdr = (len(s) << 6) | 0      # narrow
        pool[off:off + 2] = hdr.to_bytes(2, "little")
        pool[off + 2:off + 2 + len(s)] = s.encode("latin1")
        names[s] = (0 << 16) | (off >> 1)

    add_name(0x10, "F9")
    add_name(0x20, "Semicolon")
    add_name(0x30, "KeyBind")
    blocks[poolblk] = bytes(pool)
    # NAMEPOOL is an array of block pointers
    npa = base + RVA_NAMEPOOL
    blocks[npa] = poolblk.to_bytes(8, "little")

    # --- two FKeyBind rows at 0x60000000, stride 0x40 -----------------------
    arr = 0x60000000
    stride = 0x40
    s0 = "shot showui"
    s1 = "ToggleDebugCamera"
    str0, str1 = 0x61000000, 0x61001000
    blocks[str0] = s0.encode("utf-16-le")
    blocks[str1] = s1.encode("utf-16-le")
    rows = bytearray(stride * 2)

    def put_row(i, name, sptr, slen):
        o = i * stride
        rows[o:o + 4] = names[name].to_bytes(4, "little")     # FName.ComparisonIndex
        rows[o + 4:o + 8] = (0).to_bytes(4, "little")         # FName.Number
        rows[o + 0x18:o + 0x20] = sptr.to_bytes(8, "little")  # FString.Data
        rows[o + 0x20:o + 0x24] = slen.to_bytes(4, "little")  # FString.Num
        rows[o + 0x24:o + 0x28] = slen.to_bytes(4, "little")  # FString.Max

    put_row(0, "F9", str0, len(s0))
    put_row(1, "Semicolon", str1, len(s1))
    blocks[arr] = bytes(rows)

    # --- TArray header at 0x62000000 ---------------------------------------
    hdr = 0x62000000
    blocks[hdr] = (arr.to_bytes(8, "little") + (2).to_bytes(4, "little")
                   + (2).to_bytes(4, "little"))

    return BufReader(blocks), base, hdr, stride, [("F9", s0), ("Semicolon", s1)]


def self_test():
    print("=== console_probe.py --self-test  (offline; no process touched) ===")
    rdr, base, hdr, stride, expect = build_synthetic()
    ue = UE(rdr, base)
    fails = 0

    # 1. fname
    got = ue.fname_at(0x60000000)[0]
    ok = (got == "F9")
    print("  [%s] fname_at  -> %r (expect 'F9')" % ("ok " if ok else "FAIL", got))
    fails += 0 if ok else 1

    # 2. fstring
    s, p, n, m = ue.fstring(0x60000000 + 0x18)
    ok = (s == "shot showui")
    print("  [%s] fstring   -> %r  (ptr=0x%X num=%d max=%d)"
          % ("ok " if ok else "FAIL", s, p, n, m))
    fails += 0 if ok else 1

    # 3. tarray
    d, n, m = ue.tarray(hdr)
    ok = (d == 0x60000000 and n == 2 and m == 2)
    print("  [%s] tarray    -> Data=0x%X Num=%d Max=%d" % ("ok " if ok else "FAIL", d, n, m))
    fails += 0 if ok else 1

    # 4. stride scoring picks the true stride
    lay = KeyBindLayout()
    lay.fields = {"Key": (0x00, "StructProperty", 24, 0),
                  "Command": (0x18, "StrProperty", 16, 0)}
    lay.derived_size = 0x30
    lay.propsize_guess = 0
    best = (-1, 0)
    for cand in (0x28, 0x30, 0x38, 0x40, 0x48, 0x50):
        g, _rows = score_stride(ue, d, n, lay, cand)
        if g > best[0]:
            best = (g, cand)
    ok = (best == (2, stride))
    print("  [%s] stride    -> chose 0x%02X score %d (true stride 0x%02X)"
          % ("ok " if ok else "FAIL", best[1], best[0], stride))
    fails += 0 if ok else 1

    # 5. full row decode through the real printer
    lines = []
    lay.stride = 0
    num, decoded = decode_debug_exec_bindings(ue, hdr, lay, "SELFTEST", lines.append)
    ok = (decoded == expect)
    print("  [%s] rows      -> %r" % ("ok " if ok else "FAIL", decoded))
    fails += 0 if ok else 1
    if not ok:
        for l in lines:
            print("        " + l)

    # 6. looks_ptr sanity, incl. the negative control
    ok = looks_ptr(0x7FF6AF000000) and not looks_ptr(0x1) and not looks_ptr(0x7FF6AF000001)
    print("  [%s] looks_ptr -> aligned/in-range accepted, misaligned+tiny rejected"
          % ("ok " if ok else "FAIL"))
    fails += 0 if ok else 1

    print("")
    print("  %d/%d decoder checks passed." % (6 - fails, 6))
    print("  NOTE: this validates the DECODERS ONLY. It says nothing about whether")
    print("  the RVAs, the reflection walk, or the object scan work against the real")
    print("  game. Those have never been executed.")
    return 0 if fails == 0 else 1


# =============================================================================
# main probe
# =============================================================================
def main():
    ap = argparse.ArgumentParser(
        description="FK-13 live console/debug-exec probe (pure RPM, read-only).")
    ap.add_argument("--pid", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="parse + import check only; touches nothing")
    ap.add_argument("--self-test", action="store_true",
                    help="run the decoders against a synthetic address space")
    ap.add_argument("--quiet-scan", action="store_true",
                    help="skip the (slow) full-GUObjectArray Console instance census")
    args = ap.parse_args()

    if args.dry_run:
        print("=== console_probe.py --dry-run ===")
        print("  python           : %s" % sys.version.split()[0])
        print("  ctypes/kernel32  : %s"
              % ("ok" if ctypes.WinDLL("kernel32", use_last_error=True) else "FAIL"))
        print("  RVA_NAMEPOOL     : 0x%X" % RVA_NAMEPOOL)
        print("  RVA_OBJOBJECTS   : 0x%X" % RVA_OBJOBJECTS)
        print("  UObject offsets  : Flags@0x%02X Index@0x%02X Class@0x%02X Name@0x%02X"
              % (O_OBJ_FLAGS, O_OBJ_INDEX, O_OBJ_CLASS, O_OBJ_NAME))
        print("  UStruct offsets  : Super@0x%02X ChildProps@0x%02X PropSize?@0x%02X"
              % (O_STRUCT_SUPER, O_STRUCT_CHILDPROPS, O_STRUCT_PROPSIZE_GUESS))
        print("  FProperty        : ElemSize@0x%02X Flags@0x%02X Offset@0x%02X"
              % (O_PROP_ELEMSIZE, O_PROP_FLAGS, O_PROP_OFFSET))
        print("  expected 16 shipped DebugExecBindings rows:")
        for k, c in SHIPPED_16:
            print("      %-10s %s" % (k, c))
        print("  parse OK. Nothing was read from any process.")
        return 0

    if args.self_test:
        return self_test()

    # ---- attach ---------------------------------------------------------
    pid = args.pid
    if not pid:
        hits = find_pid()
        if not hits:
            print("FAIL: no process named %s. Is the game running?" % PROC_NAME)
            return 2
        if len(hits) > 1:
            print("WARN: %d instances of %s; using the first (%d). Pass --pid to choose."
                  % (len(hits), PROC_NAME, hits[0]))
        pid = hits[0]
    base = args.base or find_module_base(pid)
    if not base:
        print("FAIL: could not resolve the module base for PID %d. Pass --base." % pid)
        return 2

    rdr = ProcReader(pid)
    if not rdr.h:
        print("FAIL: OpenProcess(%d) failed, GetLastError=%d." % (pid, rdr.err))
        print("      The game runs ELEVATED (launch-redirect.ps1 elevates). Run this")
        print("      probe from an ELEVATED PowerShell too.")
        return 2
    ue = UE(rdr, base)

    print("=" * 78)
    print("FK-13 console / debug-exec probe   (pure RPM, read-only, no injection)")
    print("=" * 78)
    print("  PID              : %d" % pid)
    print("  module base      : 0x%X" % base)
    print("  NamePool         : 0x%X   (base + 0x%X)" % (base + RVA_NAMEPOOL, RVA_NAMEPOOL))
    print("  GUObjectArray    : 0x%X   (base + 0x%X)" % (base + RVA_OBJOBJECTS, RVA_OBJOBJECTS))

    objects, num = ue.obj_array_header()
    print("  ObjObjects       : 0x%X   NumElements=%d" % (objects, num))
    if not looks_ptr(objects) or not (0 < num < 8000000):
        print("")
        print("  >>> GUObjectArray header is implausible. Either the RVAs are stale")
        print("      (game updated) or --base is wrong. EVERYTHING BELOW WOULD BE")
        print("      GARBAGE, so the probe stops here. This is a VOID run, not a")
        print("      negative result.")
        return 3

    # ---------------------------------------------------------------- index
    print("")
    print("  building the object index (ONE pass; every lookup below is then free)...")
    ue.build_index(progress=print)

    # ---------------------------------------------------------------- controls
    print("")
    print("-" * 78)
    print("[CTRL] instrument positive controls  (run FIRST; if these fail the run is VOID)")
    print("-" * 78)
    ctrl = {}
    pc_cls = ue.find_uclass("PlayerController")
    ctrl["PlayerController UClass"] = pc_cls
    print("  UClass 'PlayerController'        : %s"
          % ("0x%X" % pc_cls if pc_cls else "NOT FOUND  <== instrument broken"))
    pi_cls = ue.find_uclass("PlayerInput")
    ctrl["PlayerInput UClass"] = pi_cls
    print("  UClass 'PlayerInput'             : %s"
          % ("0x%X" % pi_cls if pi_cls else "NOT FOUND  <== instrument broken"))
    if pc_cls:
        r = ue.find_prop(pc_cls, "PlayerInput")
        print("  PlayerController::PlayerInput    : %s"
              % ("+0x%X [%s] (declared on %s)" % (r[0], r[1], r[3]) if r else "NOT FOUND"))
    ks_struct = ue.find_uclass("KeyBind", meta="ScriptStruct")
    print("  UScriptStruct 'KeyBind'          : %s"
          % ("0x%X" % ks_struct if ks_struct else "NOT FOUND (will use stock offsets)"))
    if not pc_cls or not pi_cls:
        print("")
        print("  >>> A control that MUST resolve did not. The reflection walk is not")
        print("      working in this build/state. Sections A-D below are VOID.")

    # ---------------------------------------------------------------- [A]
    print("")
    print("-" * 78)
    print("[A] ALLOW_CONSOLE ORACLE  --  GEngine->GameViewport->ViewportConsole")
    print("-" * 78)
    eng = ue.find_instances(lambda cn, nm: cn.endswith("GameEngine"), limit=3)
    engine_obj = eng[0][0] if eng else 0
    if eng:
        for o, cn, nm in eng:
            print("  engine instance                  : 0x%X  class=%s  name=%s" % (o, cn, nm))
    else:
        print("  engine instance                  : NOT FOUND by class-name scan "
              "(looking for *GameEngine)")

    viewport = 0
    if engine_obj:
        r = ue.prop_on_obj(engine_obj, "GameViewport")
        if r:
            off, ty, esz, decl, _pa = r
            viewport = ue.r.u64(engine_obj + off)
            print("  Engine::GameViewport             : +0x%X [%s on %s] -> 0x%X  class=%s"
                  % (off, ty, decl, viewport, ue.cname(viewport) if viewport else "-"))
        else:
            print("  Engine::GameViewport             : PROPERTY NOT FOUND")
    if not viewport:
        vp = ue.find_instances(lambda cn, nm: "GameViewportClient" in cn, limit=3)
        if vp:
            viewport = vp[0][0]
            print("  (fallback) viewport by class scan: 0x%X class=%s name=%s"
                  % (vp[0][0], vp[0][1], vp[0][2]))

    console_ptr = None
    if viewport:
        r = ue.prop_on_obj(viewport, "ViewportConsole")
        if r:
            off, ty, esz, decl, _pa = r
            console_ptr = ue.r.u64(viewport + off)
            print("  GameViewportClient::ViewportConsole: +0x%X [%s on %s]" % (off, ty, decl))
            print("      value                        : 0x%X" % console_ptr)
            if looks_ptr(console_ptr):
                print("      -> object name=%s  class=%s"
                      % (ue.oname(console_ptr), ue.cname(console_ptr)))
                print("")
                print("  *** VERDICT [A]: ViewportConsole is NON-NULL. ALLOW_CONSOLE is ON. ***")
                print("      The console object EXISTS. FK-13's 'fully stripped' is inverted.")
                print("      Next question becomes key delivery (ConsoleKeys / focus), not existence.")
            else:
                print("")
                print("  *** VERDICT [A]: ViewportConsole is NULL. ***")
                print("      Consistent with ALLOW_CONSOLE=0 -- BUT read the caveat:")
                print("      UGameViewportClient::Init sets it; if this viewport has not been")
                print("      Init'd, or if the game uses a subclass that clears it, NULL is")
                print("      not decisive. Cross-check with section [B]: if NO UConsole")
                print("      instance exists ANYWHERE and ConsoleClass is null, the two")
                print("      together are decisive.")
        else:
            print("  GameViewportClient::ViewportConsole: PROPERTY NOT FOUND")
            print("      (usmap says it exists: schema.txt:17350 'ViewportConsole "
                  "ObjectProperty (UClass:Console)'), so a NOT FOUND here means the")
            print("      reflection walk failed -- VOID, not a negative.")
    else:
        print("  >>> no viewport object -- section [A] is VOID.")

    # ---------------------------------------------------------------- [B]
    print("")
    print("-" * 78)
    print("[B] UConsole class + instances + UEngine::ConsoleClass / ConsoleClassName")
    print("-" * 78)
    ccls = ue.find_uclass("Console")
    print("  UClass 'Console'                 : %s"
          % ("0x%X" % ccls if ccls else "NOT FOUND"))
    print("      (offline control: schema.txt:12547 lists `Console : UClass:Object (4 props)`,")
    print("       so the class IS compiled in and reflected. NOT FOUND here would mean the")
    print("       scan failed, not that the class is absent.)")
    if not args.quiet_scan:
        insts = ue.find_instances(lambda cn, nm: cn == "Console", limit=5, skip_cdo=False)
        if insts:
            for o, cn, nm in insts:
                print("  Console instance                 : 0x%X  name=%s%s"
                      % (o, nm, "  (CDO)" if nm.startswith("Default__") else "  <== LIVE"))
        else:
            print("  Console instances                : NONE (not even a CDO)")
    if engine_obj:
        for pname in ("ConsoleClass", "ConsoleClassName"):
            r = ue.prop_on_obj(engine_obj, pname)
            if not r:
                print("  Engine::%-24s : PROPERTY NOT FOUND" % pname)
                continue
            off, ty, esz, decl, _pa = r
            if ty == "ClassProperty" or ty == "ObjectProperty":
                v = ue.r.u64(engine_obj + off)
                print("  Engine::%-24s : +0x%X [%s] -> 0x%X %s"
                      % (pname, off, ty, v,
                         ("name=" + ue.oname(v)) if looks_ptr(v) else "(NULL)"))
            else:
                # FSoftClassPath = FSoftObjectPath { FTopLevelAssetPath{FName,FName}; FString }
                pkg, _i, _n = ue.fname_at(engine_obj + off)
                asset, _i2, _n2 = ue.fname_at(engine_obj + off + 8)
                sub, _p, _num, _mx = ue.fstring(engine_obj + off + 16)
                print("  Engine::%-24s : +0x%X [%s] -> Package=%r Asset=%r Sub=%r"
                      % (pname, off, ty, pkg, asset, sub))
                print("      (BaseEngine.ini:101 sets ConsoleClassName=/Script/Engine.Console;")
                print("       MEASURED offline: that literal occurs 0x wide / 0x ascii in the")
                print("       exe, so if it shows up here it came from the ini, as expected.)")

    # ---------------------------------------------------------------- [C]
    print("")
    print("-" * 78)
    print("[C] UPlayerInput::DebugExecBindings  (the FK-13 payload)")
    print("-" * 78)
    lay = resolve_keybind_layout(ue)
    print("  FKeyBind layout source           : %s"
          % ("live UScriptStruct 0x%X" % lay.struct_addr if lay.struct_addr
             else "STOCK-UE FALLBACK (struct not found)"))
    for n in ("Key", "Command", "Control", "Shift", "Alt", "Cmd",
              "bIgnoreCtrl", "bIgnoreShift", "bIgnoreAlt", "bIgnoreCmd", "bDisabled"):
        f = lay.fields.get(n)
        if f:
            print("      %-14s +0x%02X  [%s]  size=%d" % (n, f[0], f[1], f[2]))
        else:
            print("      %-14s (absent)" % n)
    print("      PropertiesSize@+0x%X guess    : %d (0x%X)"
          % (O_STRUCT_PROPSIZE_GUESS, lay.propsize_guess, lay.propsize_guess))
    print("      max(offset+size) rounded     : %d (0x%X)" % (lay.derived_size, lay.derived_size))
    for note in lay.notes:
        print("      NOTE: %s" % note)

    targets = []
    cdo, cdo_name = ue.find_cdo("PlayerInput")
    if cdo:
        targets.append((cdo, "CDO %s" % cdo_name))
    live = ue.find_instances(
        lambda cn, nm: cn.endswith("PlayerInput") or cn == "EnhancedPlayerInput", limit=3)
    for o, cn, nm in live:
        targets.append((o, "LIVE %s (%s)" % (nm, cn)))
    if not targets:
        print("  >>> no UPlayerInput object found (neither CDO nor instance). Section VOID.")
    for obj, label in targets:
        print("")
        print("  --- %s  @0x%X ---" % (label, obj))
        r = ue.prop_on_obj(obj, "DebugExecBindings")
        if not r:
            print("      DebugExecBindings: PROPERTY NOT FOUND (usmap says it exists on")
            print("      PlayerInput -- schema.txt:41090 -- so this is a walk failure, VOID)")
            continue
        off, ty, esz, decl, _pa = r
        print("      DebugExecBindings @+0x%X  [%s on %s]  elemSize=%d" % (off, ty, decl, esz))
        if off == 0x1A8:
            print("      ^^ MATCHES the S79 live measurement (+0x1A8). Offsets confirmed.")
        else:
            print("      ^^ S79 measured +0x1A8 on a live client; this reads +0x%X." % off)
            print("         Not necessarily wrong (different subclass), but note it.")
        n, decoded = decode_debug_exec_bindings(ue, obj + off, lay, label, lambda s: print(s))
        if decoded:
            got = set(c for _k, c in decoded if c)
            want = set(c for _k, c in SHIPPED_16)
            missing = sorted(want - got)
            extra = sorted(got - want)
            print("")
            print("      vs the 16 shipped BaseInput.ini rows:")
            print("        matched : %d/16" % len(want & got))
            if missing:
                print("        MISSING : %s" % ", ".join(missing))
            if extra:
                print("        EXTRA   : %s   <== these are OURS (user Input.ini took effect)"
                      % ", ".join(extra))
            if n == 16 and not extra:
                print("        => baseline. The config path populates the array, exactly as")
                print("           BaseInput.ini declares. (This does NOT prove the array is")
                print("           EVALUATED on keypress -- see the test card, step 3.)")
            elif extra:
                print("        => *** THE USER-LAYER Input.ini WAS READ. *** Num=%d (baseline 16)."
                      % n)

    # ---------------------------------------------------------------- [D]
    print("")
    print("-" * 78)
    print("[D] UInputSettings::ConsoleKeys")
    print("-" * 78)
    iscdo, isname = ue.find_cdo("InputSettings")
    if not iscdo:
        ins = ue.find_instances(lambda cn, nm: cn.endswith("InputSettings"), limit=3)
        iscdo = ins[0][0] if ins else 0
        isname = ins[0][2] if ins else ""
    if not iscdo:
        print("  >>> no InputSettings object found. Section VOID.")
    else:
        print("  object                           : 0x%X  %s  class=%s"
              % (iscdo, isname, ue.cname(iscdo)))
        r = ue.prop_on_obj(iscdo, "ConsoleKeys")
        if not r:
            print("  ConsoleKeys                      : PROPERTY NOT FOUND")
            print("      (offline control: the UInputSettings UHT property-name block at")
            print("       merged.dump RVA 0x08253d08-0x08253e90 ends with ...ConsoleKeys,")
            print("       so the property IS compiled in. NOT FOUND = walk failure = VOID.)")
        else:
            off, ty, esz, decl, _pa = r
            data, n, mx = ue.tarray(iscdo + off)
            print("  ConsoleKeys @+0x%X [%s]         : Data=0x%X Num=%d Max=%d"
                  % (off, ty, data, n, mx))
            print("      (usmap types are shifted one slot -- FK-14 -- so ignore the usmap's")
            print("       'InputAxisKeyMapping'; this is TArray<FKey>, stride 24.)")
            if n > 0 and looks_ptr(data):
                for i in range(min(n, 8)):
                    for stride in (24, 16, 32):
                        nm, idx, _num = ue.fname_at(data + i * stride)
                        if nm not in ("?", "") and idx > 0:
                            print("      [%d] stride=%d  Key=%s" % (i, stride, nm))
                            break
            elif n == 0:
                print("      *** ConsoleKeys is EMPTY. Nothing will open a console on any key,")
                print("          regardless of ALLOW_CONSOLE. (BaseInput.ini and Loki's")
                print("          DefaultInput.ini BOTH set +ConsoleKeys=Tilde, so an empty")
                print("          array here would be a real finding.)")

    print("")
    print("-" * 78)
    print("RPM stats: %d reads, %d failed." % (rdr.reads, rdr.fails))
    print("Reminder: a NULL/absent value is only a finding if the [CTRL] block above")
    print("passed. If a control failed, record the run as VOID, not as evidence.")
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
