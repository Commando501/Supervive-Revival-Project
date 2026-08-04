#!/usr/bin/env python3
r"""Minimal stdlib-only .usmap reader (Initial version, uncompressed) so we can
compare the project's mappings.usmap against Binds.Cache as a schema source."""
import struct, sys

PT = ["ByteProperty","BoolProperty","IntProperty","FloatProperty","ObjectProperty",
      "NameProperty","DelegateProperty","DoubleProperty","ArrayProperty","StructProperty",
      "StrProperty","TextProperty","InterfaceProperty","MulticastDelegateProperty",
      "WeakObjectProperty","LazyObjectProperty","AssetObjectProperty","SoftObjectProperty",
      "UInt64Property","UInt32Property","UInt16Property","Int64Property","Int16Property",
      "Int8Property","MapProperty","SetProperty","EnumProperty","FieldPathProperty",
      "OptionalProperty","Utf8StrProperty","AnsiStrProperty"]


class U:
    def __init__(self, path):
        d = open(path, 'rb').read()
        self.magic, self.ver, self.comp = struct.unpack_from('<HBB', d, 0)
        assert self.magic == 0x30C4, hex(self.magic)
        csize, dsize = struct.unpack_from('<II', d, 4)
        assert self.comp == 0, "compressed usmap not supported"
        self.d = d[12:12 + csize]
        self.o = 0
        self.size = len(self.d)
        self.names = [self._name_entry() for _ in range(self.u32())]
        self.enums = {}
        for _ in range(self.u32()):
            en = self.fname()
            vals = [self.fname() for _ in range(self.u8())]
            self.enums[en] = vals
        self.structs = {}
        self.order = []
        for _ in range(self.u32()):
            n = self.fname(); sup = self.fname()
            pcount, spcount = self.u16(), self.u16()
            props = []
            for _ in range(spcount):
                schema = self.u16(); dim = self.u8(); pn = self.fname()
                props.append((schema, dim, pn, self.ptype()))
            self.structs[n] = (sup, pcount, props)
            self.order.append(n)
        self.remaining = self.size - self.o

    def u8(self):
        v = self.d[self.o]; self.o += 1; return v

    def u16(self):
        v = struct.unpack_from('<H', self.d, self.o)[0]; self.o += 2; return v

    def u32(self):
        v = struct.unpack_from('<I', self.d, self.o)[0]; self.o += 4; return v

    def _name_entry(self):
        n = self.u8()
        s = self.d[self.o:self.o + n].decode('utf-8', 'replace'); self.o += n
        return s

    def fname(self):
        i = self.u32()
        return None if i == 0xFFFFFFFF else self.names[i]

    def ptype(self):
        t = self.u8()
        name = PT[t] if t < len(PT) else f"Unknown({t})"
        if name == "EnumProperty":
            inner = self.ptype(); return f"enum<{self.fname()}:{inner}>"
        if name == "StructProperty":
            return f"F{self.fname()}"
        if name in ("SetProperty", "ArrayProperty", "OptionalProperty"):
            return f"{name[:-8]}<{self.ptype()}>"
        if name == "MapProperty":
            k = self.ptype(); v = self.ptype(); return f"Map<{k},{v}>"
        return name


if __name__ == "__main__":
    u = U(sys.argv[1] if len(sys.argv) > 1 else
          r"G:\git\Supervive Revival Project\tools\usmapdump\mappings.usmap")
    print(f"version={u.ver} names={len(u.names):,} enums={len(u.enums):,} "
          f"structs={len(u.structs):,} unconsumed={u.remaining}")
    for t in sys.argv[2:]:
        sup, pc, props = u.structs.get(t, (None, 0, []))
        print(f"\n{t} (super={sup}, propcount={pc}, serialized={len(props)})")
        for schema, dim, pn, pt in props:
            print(f"   [{schema:>4}] dim={dim} {pt} {pn}")
