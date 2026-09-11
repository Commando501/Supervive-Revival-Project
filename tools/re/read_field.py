#!/usr/bin/env python
# read_field.py -- minimal, dependency-free RPM field reader.
#   usage: read_field.py <PID> <OBJ-hex> <OFF-hex> [<OFF-hex> ...]
#
# Reads a qword at obj+off, and if it looks like a UObject pointer, decodes its
# class and name using THIS BUILD's non-stock layout (nameOff=0x20, classOff=0x18,
# ObjectFlags@0x0C, InternalIndex@0x10 -- calibrated S110, see CLAUDE.md).
#
# Written S114 because cheat_reach_probe.py's subclass-derivation walk reported
# `LokiGameInstance LIVE=0` while tools/re/obj_by_class.py found exactly one live
# BP_LokiGameInstance_C. The engine cannot run without a GameInstance, so that
# zero was an instrument bug. This tool has no derivation walk to get wrong: it
# reads one address and decodes it.
import ctypes as C
import sys

k32 = C.WinDLL('kernel32', use_last_error=True)
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400


class Reader:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess({pid}) failed: {C.get_last_error()} (elevated?)")

    def read(self, addr, n):
        buf = (C.c_ubyte * n)()
        got = C.c_size_t(0)
        ok = k32.ReadProcessMemory(C.c_void_p(self.h), C.c_void_p(addr), buf,
                                   C.c_size_t(n), C.byref(got))
        if not ok or got.value != n:
            return None
        return bytes(buf)

    def q(self, addr):
        b = self.read(addr, 8)
        return None if b is None else int.from_bytes(b, 'little')

    def d(self, addr):
        b = self.read(addr, 4)
        return None if b is None else int.from_bytes(b, 'little')


def looks_ptr(v):
    return v is not None and 0x10000 < v < 0x7FFFFFFFFFFF and (v & 7) == 0


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    pid = int(sys.argv[1], 0)
    obj = int(sys.argv[2], 16)
    offs = [int(a, 16) for a in sys.argv[3:]]
    r = Reader(pid)

    # sanity: the object itself must decode
    vt = r.q(obj)
    print(f"object 0x{obj:X}   vtable=0x{vt:X}" if looks_ptr(vt)
          else f"object 0x{obj:X}   vtable=UNREADABLE  <-- bad address?")
    cls = r.q(obj + 0x18)
    idx = r.d(obj + 0x10)
    print(f"  classPtr(+0x18)=0x{cls or 0:X}   InternalIndex(+0x10)={idx}")
    print()

    for off in offs:
        v = r.q(obj + off)
        if v is None:
            print(f"  +0x{off:<5X} UNREADABLE")
            continue
        line = f"  +0x{off:<5X} = 0x{v:016X}"
        if v == 0:
            line += "   <-- NULL"
        elif looks_ptr(v):
            vcls = r.q(v + 0x18)
            vidx = r.d(v + 0x10)
            flags = r.d(v + 0x0C)
            line += f"   -> obj? classPtr=0x{vcls or 0:X} idx={vidx} flags=0x{flags or 0:08X}"
        else:
            line += "   (not a plausible pointer)"
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
