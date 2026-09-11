import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im = Img()
IB = im.imagebase
d = im.data
# 1) find ASCII 'TimeSinceFallingStart' image-wide
name=b'TimeSinceFallingStart\x00'
occ=[]; i=d.find(name)
while i!=-1: occ.append(i); i=d.find(name,i+1)
print("ASCII 'TimeSinceFallingStart\0' occurrences (file offsets == rva):", [hex(x) for x in occ])
# also without NUL
occ2=[]; i=d.find(b'TimeSinceFallingStart')
while i!=-1: occ2.append(i); i=d.find(b'TimeSinceFallingStart',i+1)
print("  without NUL:", [hex(x) for x in occ2])
# wide
w = 'TimeSinceFallingStart'.encode('utf-16-le')
occw=[]; i=d.find(w)
while i!=-1: occw.append(i); i=d.find(w,i+1)
print("  UTF-16LE:", [hex(x) for x in occw])

for rva in occ2:
    va = IB + rva
    p = struct.pack('<Q', va)
    ptrs=[]; i=d.find(p)
    while i!=-1: ptrs.append(i); i=d.find(p,i+1)
    print(f"  pointers to VA {va:#x} (rva {rva:#x}):", [hex(x) for x in ptrs])
    for pr in ptrs:
        prva = pr
        print(f"    record at rva {prva:#x}: {d[prva:prva+0x40].hex()}")
        p2 = struct.pack('<Q', IB+prva)
        pp=[]; j=d.find(p2)
        while j!=-1: pp.append(j); j=d.find(p2,j+1)
        print(f"    pointers to the record:", [hex(x) for x in pp])
