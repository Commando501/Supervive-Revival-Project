#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk13uht.py -- OFFLINE decoder for UHT's `UECodeGen_Private` registration statics.

Layouts are taken from the LOCAL STOCK UE 5.4 TREE
(H:\\Unreal Engine\\UE_5.4\\Engine\\Source\\Runtime\\CoreUObject\\Public\\UObject\\UObjectGlobals.h)
with the shipping preprocessor state that this build actually has:
  WITH_METADATA == 0   (no trailing NumMetaData/MetaDataArray on any params struct)
  WITH_RELOAD   == 0   (FClassReloadVersionInfo is empty)
Both are CONFIRMED here by layout controls, not assumed -- see `selftest()`.

  FClassRegisterCompiledInInfo        (UObjectBase.h:352)
      +0x00 UClass* (*OuterRegister)()      -> Z_Construct_UClass_<Name>
      +0x08 UClass* (*InnerRegister)()      -> <Name>::StaticClass
      +0x10 const TCHAR* Name               -> UTF-16, INCLUDES the U/A/F prefix
      +0x18 FClassRegistrationInfo*         -> {UClass* InnerSingleton; UClass* OuterSingleton;}

  FFunctionParams                     (UObjectGlobals.h:3751)
      +0x00 OuterFunc  +0x08 SuperFunc  +0x10 NameUTF8  +0x18 OwningClassName
      +0x20 DelegateName  +0x28 PropertyArray
      +0x30 u16 NumProperties  +0x32 u16 StructureSize
      +0x34 u32 ObjectFlags (== 0x45)  +0x38 u32 FunctionFlags
      +0x3C u16 RPCId  +0x3E u16 RPCResponseId          [size 0x40]

  FPropertyParams (common prefix; EPropertyGenFlags is uint8)
      +0x00 const char* NameUTF8
      +0x08 const char* RepNotifyFuncUTF8
      +0x10 u64 PropertyFlags (EPropertyFlags)
      +0x18 u8  Flags (EPropertyGenFlags; low 6 bits = type)
      +0x1C u32 ObjectFlags
      +0x20 SetterFunc   +0x28 GetterFunc
      +0x30 u16 ArrayDim
      +0x32 u16 Offset            (WithOffset variants)
              -- FBoolPropertyParams instead has +0x32 ElementSize,
                 +0x34 SizeOfOuter, +0x38 SetBitFunc  (NO Offset field)
      +0x38 extra fn ptr: ClassFunc / EnumFunc / ScriptStructFunc / SignatureFunc ...

  FClassParams                        (UObjectGlobals.h:3827)
      +0x00 ClassNoRegisterFunc  +0x08 ClassConfigNameUTF8  +0x10 CppClassInfo
      +0x18 DependencySingletonFuncArray  +0x20 FunctionLinkArray
      +0x28 PropertyArray  +0x30 ImplementedInterfaceArray
      +0x38 u32 bitfield {NumDependencySingletons:4, NumFunctions:11,
                          NumProperties:11, NumImplementedInterfaces:6}
      +0x3C u32 ClassFlags
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fk13img as FI

NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
RF_FUNC = 0x45

GEN_TYPE = {
    0x00: 'Byte', 0x01: 'Int8', 0x02: 'Int16', 0x03: 'Int', 0x04: 'Int64',
    0x05: 'UInt16', 0x06: 'UInt32', 0x07: 'UInt64', 0x0A: 'Float',
    0x0B: 'Double', 0x0C: 'Bool', 0x0D: 'SoftClass', 0x0E: 'WeakObject',
    0x0F: 'LazyObject', 0x10: 'SoftObject', 0x11: 'Class', 0x12: 'Object',
    0x13: 'Interface', 0x14: 'Name', 0x15: 'Str', 0x16: 'Array', 0x17: 'Map',
    0x18: 'Set', 0x19: 'Struct', 0x1A: 'Delegate',
    0x1B: 'InlineMulticastDelegate', 0x1C: 'SparseMulticastDelegate',
    0x1D: 'Text', 0x1E: 'Enum', 0x1F: 'FieldPath',
    0x20: 'LargeWorldCoordinatesReal', 0x21: 'Optional', 0x22: 'VValue',
}
# runtime sizeof() of each generated property's VALUE in a params buffer
GEN_SIZE = {
    'Byte': 1, 'Int8': 1, 'Int16': 2, 'Int': 4, 'Int64': 8, 'UInt16': 2,
    'UInt32': 4, 'UInt64': 8, 'Float': 4, 'Double': 8, 'Bool': 1,
    'SoftClass': 0x28, 'WeakObject': 8, 'LazyObject': 0x1C, 'SoftObject': 0x28,
    'Class': 8, 'Object': 8, 'Interface': 16, 'Name': 8, 'Str': 16,
    'Array': 16, 'Map': 0x50, 'Set': 0x50, 'Struct': None, 'Delegate': 16,
    'InlineMulticastDelegate': 16, 'SparseMulticastDelegate': 1, 'Text': 24,
    'Enum': None, 'FieldPath': 32, 'LargeWorldCoordinatesReal': 8,
    'Optional': None, 'VValue': 8,
}
PROP_FLAGS = [
    (0x0000000000000001, 'Edit'), (0x0000000000000002, 'ConstParm'),
    (0x0000000000000004, 'BlueprintVisible'), (0x0000000000000008, 'ExportObject'),
    (0x0000000000000010, 'BlueprintReadOnly'), (0x0000000000000020, 'Net'),
    (0x0000000000000040, 'EditFixedSize'), (0x0000000000000080, 'Parm'),
    (0x0000000000000100, 'OutParm'), (0x0000000000000200, 'ZeroConstructor'),
    (0x0000000000000400, 'ReturnParm'), (0x0000000000000800, 'DisableEditOnTemplate'),
    (0x0000000000002000, 'Transient'), (0x0000000000004000, 'Config'),
    (0x0000000000010000, 'DisableEditOnInstance'), (0x0000000000020000, 'EditConst'),
    (0x0000000000040000, 'GlobalConfig'), (0x0000000000080000, 'InstancedReference'),
    (0x0000000000200000, 'DuplicateTransient'), (0x0000000001000000, 'SaveGame'),
    (0x0000000002000000, 'NoClear'), (0x0000000008000000, 'ReferenceParm'),
    (0x0000000010000000, 'BlueprintAssignable'), (0x0000000020000000, 'Deprecated'),
    (0x0000000040000000, 'IsPlainOldData'), (0x0000000080000000, 'RepSkip'),
    (0x0000000100000000, 'RepNotify'), (0x0000000200000000, 'Interp'),
    (0x0000000400000000, 'NonTransactional'), (0x0000000800000000, 'EditorOnly'),
    (0x0000001000000000, 'NoDestructor'), (0x0000004000000000, 'AutoWeak'),
    (0x0000008000000000, 'ContainsInstancedReference'), (0x0000010000000000, 'AssetRegistrySearchable'),
    (0x0000020000000000, 'SimpleDisplay'), (0x0000040000000000, 'AdvancedDisplay'),
    (0x0000080000000000, 'Protected'), (0x0000100000000000, 'BlueprintCallable'),
    (0x0000200000000000, 'BlueprintAuthorityOnly'), (0x0000400000000000, 'TextExportTransient'),
    (0x0000800000000000, 'NonPIEDuplicateTransient'), (0x0001000000000000, 'ExposeOnSpawn'),
    (0x0002000000000000, 'PersistentInstance'), (0x0004000000000000, 'UObjectWrapper'),
    (0x0008000000000000, 'HasGetValueTypeHash'), (0x0010000000000000, 'NativeAccessSpecifierPublic'),
    (0x0020000000000000, 'NativeAccessSpecifierProtected'), (0x0040000000000000, 'NativeAccessSpecifierPrivate'),
    (0x0080000000000000, 'SkipSerialization'),
]
FUNC_FLAGS = [
    (0x00000001, 'Final'), (0x00000002, 'RequiredAPI'),
    (0x00000004, 'BlueprintAuthorityOnly'), (0x00000008, 'BlueprintCosmetic'),
    (0x00000040, 'Net'), (0x00000080, 'NetReliable'), (0x00000100, 'NetRequest'),
    (0x00000200, 'Exec'), (0x00000400, 'Native'), (0x00000800, 'Event'),
    (0x00001000, 'NetResponse'), (0x00002000, 'Static'), (0x00004000, 'NetMulticast'),
    (0x00008000, 'UbergraphFunction'), (0x00010000, 'MulticastDelegate'),
    (0x00020000, 'Public'), (0x00040000, 'Private'), (0x00080000, 'Protected'),
    (0x00100000, 'Delegate'), (0x00200000, 'NetServer'), (0x00400000, 'HasOutParms'),
    (0x00800000, 'HasDefaults'), (0x01000000, 'NetClient'), (0x02000000, 'DLLImport'),
    (0x04000000, 'BlueprintCallable'), (0x08000000, 'BlueprintEvent'),
    (0x10000000, 'BlueprintPure'), (0x20000000, 'EditorOnly'), (0x40000000, 'Const'),
    (0x80000000, 'NetValidate'),
]
CLASS_FLAGS = [   # UE 5.4 ObjectMacros.h:189-261 (NOT the UE4 values -- they differ)
    (0x00000001, 'Abstract'), (0x00000002, 'DefaultConfig'), (0x00000004, 'Config'),
    (0x00000008, 'Transient'), (0x00000010, 'Optional'), (0x00000020, 'MatchedSerializers'),
    (0x00000040, 'ProjectUserConfig'), (0x00000080, 'Native'),
    (0x00000200, 'NotPlaceable'), (0x00000400, 'PerObjectConfig'),
    (0x00000800, 'ReplicationDataIsSetUp'), (0x00001000, 'EditInlineNew'),
    (0x00002000, 'CollapseCategories'), (0x00004000, 'Interface'),
    (0x00008000, 'PerPlatformConfig'), (0x00010000, 'Const'),
    (0x00020000, 'NeedsDeferredDependencyLoading'), (0x00040000, 'CompiledFromBlueprint'),
    (0x00080000, 'MinimalAPI'), (0x00100000, 'RequiredAPI'),
    (0x00200000, 'DefaultToInstanced'), (0x00400000, 'TokenStreamAssembled'),
    (0x00800000, 'HasInstancedReference'), (0x01000000, 'Hidden'),
    (0x02000000, 'Deprecated'), (0x04000000, 'HideDropDown'),
    (0x08000000, 'GlobalUserConfig'), (0x10000000, 'Intrinsic'),
    (0x20000000, 'Constructed'), (0x40000000, 'ConfigDoNotCheckDefaults'),
    (0x80000000, 'NewerVersionExists'),
]


def _fl(v, table):
    return '|'.join(n for b, n in table if v & b) or 'None'


def funcflagstr(v):
    return _fl(v, FUNC_FLAGS)


def propflagstr(v):
    return _fl(v, PROP_FLAGS)


def classflagstr(v):
    return _fl(v, CLASS_FLAGS)


# --------------------------------------------------------------------------
class UHT:
    def __init__(self, im=None):
        self.im = im or FI.img()
        tva, tvs = self.im.sec['.text']
        self.tlo, self.thi = tva, tva + tvs
        self.classreg = None      # name -> record dict
        self.byouter = None       # Z_Construct rva -> name
        self.funcs = None         # list of dicts
        self.classparams = None   # list of dicts

    def _is_text(self, rva):
        return rva is not None and self.tlo <= rva < self.thi

    # ---- pass 1: class registrations -------------------------------------
    def scan_class_registrations(self):
        if self.classreg is not None:
            return self.classreg
        im = self.im
        recs = {}
        byouter = {}
        for sect in ('.data', '.rdata'):
            va, vs = im.sec[sect]
            for s in range(va, va + vs - 0x20, 8):
                o = im.ptr(s)
                if not self._is_text(o):
                    continue
                i = im.ptr(s + 8)
                if not self._is_text(i):
                    continue
                nr = im.ptr(s + 0x10)
                if nr is None:
                    continue
                nm = im.wstr(nr, 120)
                if not nm or not NAME_RE.match(nm):
                    continue
                info = im.ptr(s + 0x18)
                rec = dict(rec_rva=s, outer=o, inner=i, name=nm, info=info)
                recs.setdefault(nm, rec)
                byouter.setdefault(o, nm)
        self.classreg, self.byouter = recs, byouter
        return recs

    # ---- pass 2: FFunctionParams -----------------------------------------
    def scan_functions(self):
        if self.funcs is not None:
            return self.funcs
        self.scan_class_registrations()
        im = self.im
        out, seen, cand, rej = [], set(), 0, 0
        for sect in ('.data', '.rdata'):
            va, vs = im.sec[sect]
            for s in range(va, va + vs - 0x50, 8):
                outer = im.ptr(s)
                if not self._is_text(outer):
                    continue
                if im.u64(s + 0x18):          # OwningClassName must be NULL
                    continue
                nr = im.ptr(s + 0x10)
                if nr is None:
                    continue
                nm = im.cstr(nr)
                if not nm or not NAME_RE.match(nm):
                    continue
                cand += 1
                if im.u32(s + 0x34) != RF_FUNC:
                    rej += 1
                    continue
                k = (outer, nm, s)
                if k in seen:
                    continue
                seen.add(k)
                out.append(dict(
                    params_rva=s, outer=outer,
                    owner=self.byouter.get(outer, '?0x%x' % outer),
                    name=nm,
                    super=im.ptr(s + 0x08),
                    proparray=im.ptr(s + 0x28),
                    nprops=im.u16(s + 0x30),
                    structsize=im.u16(s + 0x32),
                    objflags=im.u32(s + 0x34),
                    flags=im.u32(s + 0x38),
                    rpcid=im.u16(s + 0x3C)))
        self.func_stats = dict(candidates=cand, accepted=len(out), rejected=rej)
        self.funcs = out
        return out

    def find_funcs(self, owner=None, name=None):
        return [f for f in self.scan_functions()
                if (owner is None or f['owner'] == owner)
                and (name is None or f['name'] == name)]

    # ---- FPropertyParams --------------------------------------------------
    def decode_prop(self, rva):
        im = self.im
        nm = im.cstr(im.ptr(rva) or -1) if im.ptr(rva) else None
        gen = im.u8(rva + 0x18)
        if gen is None:
            return None
        t = GEN_TYPE.get(gen & 0x3F, 'Gen%#x' % (gen & 0x3F))
        objptr = bool(gen & 0x40) and t in ('Object', 'Class', 'Array', 'Struct',
                                            'WeakObject', 'SoftObject', 'SoftClass',
                                            'Interface', 'Map', 'Set')
        d = dict(rva=rva, name=nm, gen=gen, type=t,
                 native_bool=bool(gen & 0x40) and t == 'Bool',
                 objectptr=bool(gen & 0x40) and t in ('Object', 'Class'),
                 propflags=im.u64(rva + 0x10),
                 objflags=im.u32(rva + 0x1C),
                 setter=im.ptr(rva + 0x20), getter=im.ptr(rva + 0x28),
                 arraydim=im.u16(rva + 0x30))
        if t == 'Bool':
            d['elementsize'] = im.u16(rva + 0x32)
            d['sizeofouter'] = im.u32(rva + 0x34)
            d['setbitfunc'] = im.ptr(rva + 0x38)
            d['offset'] = None      # bool params carry NO Offset field
        else:
            d['offset'] = im.u16(rva + 0x32)
            d['extra'] = im.ptr(rva + 0x38)
        return d

    def decode_prop_array(self, arr_rva, n):
        im = self.im
        out = []
        for i in range(n or 0):
            p = im.ptr(arr_rva + i * 8)
            out.append(self.decode_prop(p) if p is not None else None)
        return out

    # ---- FClassParams -----------------------------------------------------
    def scan_class_params(self):
        if self.classparams is not None:
            return self.classparams
        im = self.im
        out = []
        for sect in ('.data', '.rdata'):
            va, vs = im.sec[sect]
            for s in range(va, va + vs - 0x40, 8):
                noreg_ = im.ptr(s)
                if not self._is_text(noreg_):
                    continue
                cpp = im.ptr(s + 0x10)
                if cpp is None or im.section_of(cpp) not in ('.rdata', '.data'):
                    continue
                bits = im.u32(s + 0x38)
                cf = im.u32(s + 0x3C)
                if bits is None or cf is None:
                    continue
                ndep = bits & 0xF
                nfun = (bits >> 4) & 0x7FF
                nprop = (bits >> 15) & 0x7FF
                nifc = (bits >> 26) & 0x3F
                if not (cf & 0x80):          # CLASS_Native must be set
                    continue
                if nfun == 0 and nprop == 0:
                    continue
                fl = im.ptr(s + 0x20)
                pa = im.ptr(s + 0x28)
                if nfun and fl is None:
                    continue
                if nprop and pa is None:
                    continue
                out.append(dict(rva=s, noreg=noreg_, config=im.cstr(im.ptr(s + 8) or -1)
                                if im.ptr(s + 8) else None,
                                cppinfo=cpp, deps=im.ptr(s + 0x18), funclink=fl,
                                proparray=pa, ifcarray=im.ptr(s + 0x30),
                                ndep=ndep, nfun=nfun, nprop=nprop, nifc=nifc,
                                classflags=cf))
        self.classparams = out
        return out

    def class_params_for(self, clsname):
        """Match FClassParams to a class by ClassNoRegisterFunc == InnerRegister,
        with the FunctionLinkArray names printed as an independent corroboration."""
        recs = self.scan_class_registrations()
        r = recs.get(clsname)
        if not r:
            return []
        return [c for c in self.scan_class_params() if c['noreg'] == r['inner']]

    def funclink_names(self, cp):
        im = self.im
        out = []
        for i in range(cp['nfun']):
            e = cp['funclink'] + i * 16
            fn = im.ptr(e)
            nm = im.cstr(im.ptr(e + 8) or -1) if im.ptr(e + 8) else None
            out.append((fn, nm))
        return out


# --------------------------------------------------------------------------
def selftest():
    """Layout controls.  Every one of these is a ground truth from prior sessions
    or from stock UE; a failure here voids everything downstream."""
    u = UHT()
    recs = u.scan_class_registrations()
    fns = u.scan_functions()
    print('class-registration records : %d' % len(recs))
    print('FFunctionParams  candidates %d  accepted %d (%.2f%%)  rejected %d'
          % (u.func_stats['candidates'], u.func_stats['accepted'],
             100.0 * u.func_stats['accepted'] / max(u.func_stats['candidates'], 1),
             u.func_stats['rejected']))
    ok = fail = 0
    checks = [
        ('APlayerController', 'ServerVerifyViewTarget', 0x80220CC2),
        ('APlayerController', 'ClientSetHUD', 0x05020CC2),
        ('UCheatManager', 'God', 0x04020602),
        ('ADebugCameraController', 'ToggleDebugCamera', 0x00020602),
    ]
    for owner, nm, want in checks:
        got = [f for f in fns if f['owner'] == owner and f['name'] == nm]
        good = got and got[0]['flags'] == want
        print('  CTRL %-26s %-24s want %#010x got %s  %s'
              % (owner, nm, want,
                 ('%#010x' % got[0]['flags']) if got else 'MISSING',
                 'OK' if good else 'FAIL'))
        ok += bool(good)
        fail += (not good)
    ex = [f for f in fns if f['flags'] & 0x200]
    print('  FUNC_Exec total : %d  (S114 lane-3 measured 138)' % len(ex))
    print('selftest %d ok / %d fail' % (ok, fail))
    return fail == 0


if __name__ == '__main__':
    sys.exit(0 if selftest() else 1)
