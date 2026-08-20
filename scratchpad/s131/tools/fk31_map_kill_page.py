#!/usr/bin/env python3
"""
FK-31 -- can the protector's kill target be MAPPED before it is jumped to?

S131 measured that the kill jumps to ONE FIXED ADDRESS PER BOOT SESSION -- `0x7FFB57400001` in the
current era, bit-identical across every launch, not an offset from any loaded module, and covered by
no module and no executable region (31 minidumps, 3 eras; see
scratchpad/s131/evidence/FK31-kill-address-is-constant.md).

The proposed experiment is to map an executable page there and put a `ret` at +1, so the kill jump
RETURNS instead of faulting -- and the return address on the stack then names the protector code that
decided to kill, which is what FK-10's Wall #7 has been hunting.

THIS SCRIPT ONLY ANSWERS THE PRECONDITION: is the address FREE, RESERVED, or COMMITTED right now?
  * FREE      -> the experiment is possible; --commit will map it
  * RESERVED  -> VirtualAllocEx at that base fails and the whole experiment family is DEAD.
                 Knowing that costs one command instead of a session.
  * COMMITTED -> something already owns it; report what, and do nothing.

Default is READ-ONLY (VirtualQueryEx). Pass --commit to actually map + write the `ret`.

usage: fk31_map_kill_page.py <PID> [KILL-ADDR-hex] [--commit]
"""
import ctypes, ctypes.wintypes as w, sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = w.HANDLE
k32.VirtualAllocEx.restype = w.LPVOID
k32.VirtualAllocEx.argtypes = [w.HANDLE, w.LPVOID, ctypes.c_size_t, w.DWORD, w.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("__a", w.DWORD),
                ("RegionSize", ctypes.c_size_t), ("State", w.DWORD),
                ("Protect", w.DWORD), ("Type", w.DWORD), ("__b", w.DWORD)]


STATE = {0x1000: "MEM_COMMIT", 0x2000: "MEM_RESERVE", 0x10000: "MEM_FREE"}
TYPE = {0x20000: "MEM_PRIVATE", 0x40000: "MEM_MAPPED", 0x1000000: "MEM_IMAGE", 0: "-"}
PROT = {0x01: "NOACCESS", 0x02: "READONLY", 0x04: "READWRITE", 0x08: "WRITECOPY",
        0x10: "EXECUTE", 0x20: "EXECUTE_READ", 0x40: "EXECUTE_READWRITE", 0: "-"}


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    pid = int(sys.argv[1], 0)
    addr = 0x7FFB57400001
    commit = "--commit" in sys.argv
    for a in sys.argv[2:]:
        if not a.startswith("--"):
            addr = int(a, 16)
    page = addr & ~0xFFF

    # PROCESS_QUERY_INFORMATION | VM_READ | VM_WRITE | VM_OPERATION
    h = k32.OpenProcess(0x0400 | 0x0010 | 0x0020 | 0x0008, False, pid)
    if not h:
        print("OpenProcess failed (err %d) -- alive? elevated?" % ctypes.get_last_error()); return 1

    m = MBI()
    got = k32.VirtualQueryEx(h, ctypes.c_void_p(page), ctypes.byref(m), ctypes.sizeof(m))
    if not got:
        print("VirtualQueryEx failed (err %d)" % ctypes.get_last_error()); return 1

    st = STATE.get(m.State, hex(m.State))
    print("kill address : 0x%016X   (page 0x%016X)" % (addr, page))
    print("  BaseAddress    0x%X" % (m.BaseAddress or 0))
    print("  AllocationBase 0x%X" % (m.AllocationBase or 0))
    print("  RegionSize     0x%X" % m.RegionSize)
    print("  State          %s" % st)
    print("  Protect        %s" % PROT.get(m.Protect, hex(m.Protect)))
    print("  Type           %s" % TYPE.get(m.Type, hex(m.Type)))
    print()

    if m.State == 0x10000:
        print("=> FREE. The page is unmapped, which is exactly why the kill jump faults with an")
        print("   EXECUTE access violation (ExceptionInformation[0]==8). THE EXPERIMENT IS POSSIBLE:")
        print("   VirtualAllocEx at this base should succeed and a `ret` at +1 would make the jump")
        print("   return instead of dying, exposing the caller on the stack.")
        print("   Free region size: 0x%X bytes." % m.RegionSize)
    elif m.State == 0x2000:
        print("=> RESERVED. VirtualAllocEx at this base will FAIL, and the map-a-page experiment is")
        print("   DEAD as designed. That is a real result and it cost one command.")
    else:
        print("=> ALREADY COMMITTED by something. Report the owner above; do NOT overwrite it.")

    if not commit:
        print()
        print("(read-only run -- nothing was written. Pass --commit to map the page.)")
        return 0

    if m.State != 0x10000:
        print("\nREFUSING to --commit: the page is not FREE. See above.")
        return 3

    p = k32.VirtualAllocEx(h, ctypes.c_void_p(page), 0x1000, 0x1000 | 0x2000, 0x40)
    if not p:
        print("\nVirtualAllocEx FAILED (err %d) even though the query said FREE -- that itself is a"
              % ctypes.get_last_error())
        print("finding: something is preventing the reservation. Report it, do not retry blindly.")
        return 4
    print("\nVirtualAllocEx -> 0x%X  (requested 0x%X)" % (p, page))
    if p != page:
        print("*** IT DID NOT LAND AT THE REQUESTED BASE. The experiment needs THAT address; a page")
        print("    elsewhere is useless. Leaving it alone rather than writing to the wrong place. ***")
        return 5

    # int3-fill the page, then `ret` at exactly +1. int3 everywhere else means a jump to any OTHER
    # offset in the page still traps loudly rather than executing garbage -- so a wrong-offset jump
    # stays visible instead of silently "working".
    buf = (ctypes.c_char * 0x1000)(*([b'\xCC'[0]] * 0x1000))
    buf[addr - page] = 0xC3          # ret, at the exact address the kill jumps to
    written = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(page), buf, 0x1000, ctypes.byref(written))
    print("WriteProcessMemory ok=%s wrote=%d" % (bool(ok), written.value))
    rb = (ctypes.c_char * 4)()
    k32.ReadProcessMemory(h, ctypes.c_void_p(addr - 1), rb, 4, ctypes.byref(written))
    print("readback @0x%X: %s   (expect CC C3 CC CC -- `ret` at +1, int3 elsewhere)"
          % (page, rb.raw.hex(" ")))
    print()
    print("=> The kill target is now MAPPED EXECUTABLE with a `ret` at the exact jump address.")
    print("   If the protector kills this process from now on, the jump RETURNS instead of faulting.")
    print("   ⚠ This does not PROVOKE a kill -- it only changes what happens if one occurs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
