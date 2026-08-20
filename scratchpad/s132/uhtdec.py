#!/usr/bin/env python3
"""Decode UECodeGen_Private::F*PropertyParams records."""
import sys, struct
sys.path.insert(0,'scratchpad/s132')
from uht import img

GEN = {
 0x00:"Byte",0x01:"Int8",0x02:"Int16",0x03:"Int",0x04:"Int64",0x05:"UInt16",0x06:"UInt32",
 0x07:"UInt64",0x08:"UnsizedInt",0x09:"UnsizedUInt",0x0A:"Float",0x0B:"Double",0x0C:"Bool",
 0x0D:"SoftClass",0x0E:"WeakObject",0x0F:"LazyObject",0x10:"SoftObject",0x11:"Class",
 0x12:"Object",0x13:"Interface",0x14:"Name",0x15:"Str",0x16:"Array",0x17:"Map",0x18:"Set",
 0x19:"Struct",0x1A:"Delegate",0x1B:"InlineMulticastDelegate",0x1C:"SparseMulticastDelegate",
 0x1D:"Text",0x1E:"Enum",0x1F:"FieldPath",0x20:"LargeWorldCoordinatesReal",0x21:"Optional",
}
FLAG_NATIVEBOOL = 0x40
FLAG_OBJECTPTR  = 0x80

CPF = [
 (0x0000000000000001,"Edit"),(0x0000000000000002,"ConstParm"),(0x0000000000000004,"BlueprintVisible"),
 (0x0000000000000008,"ExportObject"),(0x0000000000000010,"BlueprintReadOnly"),(0x0000000000000020,"Net"),
 (0x0000000000000040,"EditFixedSize"),(0x0000000000000080,"Parm"),(0x0000000000000100,"OutParm"),
 (0x0000000000000200,"ZeroConstructor"),(0x0000000000000400,"ReturnParm"),(0x0000000000000800,"DisableEditOnTemplate"),
 (0x0000000000001000,"NonNullable"),(0x0000000000002000,"Transient"),(0x0000000000004000,"Config"),
 (0x0000000000010000,"DisableEditOnInstance"),(0x0000000000020000,"EditConst"),(0x0000000000040000,"GlobalConfig"),
 (0x0000000000080000,"InstancedReference"),(0x0000000000200000,"DuplicateTransient"),
 (0x0000000001000000,"SaveGame"),(0x0000000002000000,"NoClear"),(0x0000000008000000,"ReferenceParm"),
 (0x0000000010000000,"BlueprintAssignable"),(0x0000000020000000,"Deprecated"),(0x0000000040000000,"IsPlainOldData"),
 (0x0000000080000000,"RepSkip"),(0x0000000100000000,"RepNotify"),(0x0000000200000000,"Interp"),
 (0x0000000400000000,"NonTransactional"),(0x0000000800000000,"EditorOnly"),(0x0000001000000000,"NoDestructor"),
 (0x0000004000000000,"AutoWeak"),(0x0000008000000000,"ContainsInstancedReference"),(0x0000010000000000,"AssetRegistrySearchable"),
 (0x0000020000000000,"SimpleDisplay"),(0x0000040000000000,"AdvancedDisplay"),(0x0000080000000000,"Protected"),
 (0x0000100000000000,"BlueprintCallable"),(0x0000200000000000,"BlueprintAuthorityOnly"),(0x0000400000000000,"TextExportTransient"),
 (0x0000800000000000,"NonPIEDuplicateTransient"),(0x0001000000000000,"ExposeOnSpawn"),(0x0002000000000000,"PersistentInstance"),
 (0x0004000000000000,"UObjectWrapper"),(0x0008000000000000,"HasGetValueTypeHash"),(0x0010000000000000,"NativeAccessSpecifierPublic"),
 (0x0020000000000000,"NativeAccessSpecifierProtected"),(0x0040000000000000,"NativeAccessSpecifierPrivate"),
 (0x0080000000000000,"SkipSerialization"),
]
def cpf(v):
    out=[n for m,n in CPF if v & m]
    rest = v & ~sum(m for m,_ in CPF)
    if rest: out.append(hex(rest))
    return "|".join(out) if out else "0"

# variable tail size per gen-flag family (bytes after the 0x38 fixed head)
def rec(im, rva):
    d = im.read(rva, 0x60)
    name = im.cstr(im.va2rva(struct.unpack_from("<Q",d,0)[0]))
    repn = struct.unpack_from("<Q",d,8)[0]
    repname = im.cstr(im.va2rva(repn)) if repn else None
    pflags = struct.unpack_from("<Q",d,0x10)[0]
    gflags = struct.unpack_from("<I",d,0x18)[0]
    oflags = struct.unpack_from("<I",d,0x1C)[0]
    setter = struct.unpack_from("<Q",d,0x20)[0]
    getter = struct.unpack_from("<Q",d,0x28)[0]
    arrdim = struct.unpack_from("<H",d,0x30)[0]
    off    = struct.unpack_from("<H",d,0x32)[0]
    base   = gflags & 0x3F
    return dict(rva=rva, name=name, repnotify=repname, pflags=pflags, gflags=gflags,
                gname=GEN.get(base,hex(base)), nativebool=bool(gflags&FLAG_NATIVEBOOL),
                objptr=bool(gflags&FLAG_OBJECTPTR), oflags=oflags,
                setter=setter, getter=getter, arraydim=arrdim, off=off, raw=d)

def show(im, rva, tail=0x28):
    r = rec(im, rva)
    print(f"  rec @rva {hex(rva)}  name={r['name']!r:34s} gen={r['gname']}"
          + (" |NativeBool" if r['nativebool'] else "") + (" |ObjectPtr" if r['objptr'] else "")
          + f"  ArrayDim={r['arraydim']}  +0x32={hex(r['off'])}")
    print(f"        PropertyFlags=0x{r['pflags']:016x}  {cpf(r['pflags'])}")
    if r['repnotify']: print(f"        RepNotifyFunc={r['repnotify']!r}")
    d=r['raw']
    print("        tail: " + " ".join(f"{b:02x}" for b in d[0x30:0x30+tail]))
    return r

if __name__=="__main__":
    im = img(sys.argv[2] if len(sys.argv)>2 else "merged4")
    show(im, int(sys.argv[1],0))
