#!/usr/bin/env python3
"""Look up exact function bounds from the recovered .pdata union."""
import csv, bisect, sys, os

CSV = r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv"
_starts = None
_rows = None

def load():
    global _starts, _rows
    if _starts is not None:
        return
    _rows = []
    with open(CSV) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            _rows.append((int(row[0], 16), int(row[1], 16), int(row[2]), row[4]))
    _rows.sort()
    _starts = [x[0] for x in _rows]

def find(rva):
    load()
    i = bisect.bisect_right(_starts, rva) - 1
    if i < 0:
        return None
    b, e, sz, seen = _rows[i]
    if b <= rva < e:
        return (b, e, sz, seen)
    return None

if __name__ == "__main__":
    for a in sys.argv[1:]:
        rva = int(a, 0)
        r = find(rva)
        if r:
            print(f"0x{rva:08X} -> fn 0x{r[0]:08X}..0x{r[1]:08X} size={r[2]} seen_in={r[3]}")
        else:
            print(f"0x{rva:08X} -> no pdata entry")
