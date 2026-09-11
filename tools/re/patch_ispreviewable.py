import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 62212
# IsPreviewable UFunction Func slots (obj+0xE0). Patch the tile override (CatalogEntryWithPreview);
# also the base + random selectable overrides, so every selectable's IsPreviewable returns true.
FUNC_SLOTS = [int(x,16) for x in sys.argv[2:]] or [
    0x26D001D6FE0,   # HeroPickerSelectable_CatalogEntryWithPreview_C (the tile)
    0x26D001D4DE0,   # HeroPickerSelectable_C (base)
]
# native stub: void(rcx=Context, rdx=FFrame&, r8=Result) { if(r8) *(byte*)r8 = 1; return; }
STUB = bytes([0x4D,0x85,0xC0, 0x74,0x04, 0x41,0xC6,0x00,0x01, 0xC3])

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.VirtualAllocEx.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD,wintypes.DWORD]
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h: print("OpenProcess failed", ctypes.get_last_error()); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wpm(a,data):
    b=(ctypes.c_ubyte*len(data)).from_buffer_copy(data); r=ctypes.c_size_t(0)
    return k32.WriteProcessMemory(h,ctypes.c_void_p(a),b,len(data),ctypes.byref(r)) and r.value==len(data)

# allocate one remote executable stub (shared by all slots)
stub_addr = k32.VirtualAllocEx(h, None, 0x1000, 0x3000, 0x40)  # MEM_COMMIT|RESERVE, PAGE_EXECUTE_READWRITE
if not stub_addr: print("VirtualAllocEx failed", ctypes.get_last_error()); sys.exit(1)
if not wpm(stub_addr, STUB): print("write stub failed"); sys.exit(1)
print(f"stub @0x{stub_addr:X} = {STUB.hex()}")

BASE=0x7FF682A80000
for slot in FUNC_SLOTS:
    cur = rpm(slot, 8)
    if not cur: print(f"  slot 0x{slot:X}: unreadable"); continue
    curv = int.from_bytes(cur,"little")
    inrange = BASE < curv < BASE+0xC000000
    print(f"  slot 0x{slot:X}: current Func=0x{curv:X} (in .text={inrange})")
    if not inrange:
        print(f"    -> NOT a code ptr, skipping (wrong offset?)"); continue
    if wpm(slot, stub_addr.to_bytes(8,"little")):
        print(f"    -> swapped Func -> stub 0x{stub_addr:X}")
    else:
        print(f"    -> WPM failed")
print("done. IsPreviewable now returns true; click an owned hero -> it should preview into the center.")
