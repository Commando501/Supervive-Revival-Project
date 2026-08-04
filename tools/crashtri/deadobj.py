#!/usr/bin/env python
"""deadobj.py -- identify the dead ViewTarget.Target in a SUPERVIVE camera-crash minidump.

READ-ONLY.  Uses mdctx.MD (whose MINIDUMP_THREAD offsets are corrected; the older
tools/re/parse_minidump.py has them wrong).

For the camera-UAF family (fault PC = base+0x3C5DC52):
  rdi = APlayerCameraManager   rbx = rsi = &PCM->ViewTarget (PCM+0x420)
  rcx = ViewTarget.Target      rax = *(void**)rcx  (the vptr)  == 0 at the fault

Reports the exact dumped window around Target, scans it for UObject headers
(this build: vtable@0x00, InternalIndex@0x10, UClass*@0x18, FName@0x20,
Outer@0x28), and prints each header's offset relative to Target.

usage:  deadobj.py <dump.dmp> [<dump.dmp> ...]
"""
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdctx import MD, hexdump

NL = chr(10)


def is_img(md, v, gb, gsz):
    return gb <= v < gb + gsz


def looks_heap(v):
    return 0x10000000000 <= v < 0x7F0000000000 and (v & 7) == 0


def scan_objects(md, lo, hi, gb, gsz):
    """UObject-header candidates in [lo,hi): vptr into image + UClass* + Outer heap ptrs"""
    out = []
    a = (lo + 7) & ~7
    while a + 0x30 <= hi:
        v = md.q(a)
        if v is not None and is_img(md, v, gb, gsz):
            cls = md.q(a + 0x18)
            out_er = md.q(a + 0x28)
            idx = md.q(a + 0x10)
            if cls and out_er and looks_heap(cls) and looks_heap(out_er):
                out.append(dict(addr=a, vptr=v, rva=v - gb, cls=cls, outer=out_er,
                                internal=(idx or 0) & 0xFFFFFFFF,
                                fname=md.read(a + 0x20, 8)))
        a += 8
    return out


def report(path):
    md = MD(path)
    game = [m for m in md.mods if m[2].lower().startswith('supervive')]
    gb, gsz = game[0][0], game[0][1]
    c = md.ctx(md.exc['ctx'])
    rcx, rbx, rdi, rax = c['rcx'], c['rbx'], c['rdi'], c['rax']
    print("=" * 78)
    print("%s" % os.path.basename(os.path.dirname(path)))
    print("  base=0x%X  PCM=0x%X  &ViewTarget=PCM+0x%X  Target=0x%X  vptr(rax)=0x%X"
          % (gb, rdi, rbx - rdi, rcx, rax))
    print("  Target & 0xFF = 0x%02X   (a valid UObject* is >=8-aligned)" % (rcx & 0xFF))
    win = None
    for sa, sz, sr in md.ranges:
        if sa <= rcx < sa + sz:
            win = (sa, sz)
    print("  captured window: 0x%X .. 0x%X (%d B), Target at +0x%X"
          % (win[0], win[0] + win[1], win[1], rcx - win[0]) if win else "  (no window)")

    objs = scan_objects(md, win[0], win[0] + win[1], gb, gsz)
    print("  UObject headers found in that window: %d" % len(objs))
    for o in objs:
        idx, num = struct.unpack('<II', o['fname'])
        print("    obj 0x%X  (Target%+d = Target+0x%X)  vtable rva 0x%X  "
              "InternalIndex=%d  Class=0x%X  Outer=0x%X  FName=(%d,0x%X)"
              % (o['addr'], o['addr'] - rcx, o['addr'] - rcx, o['rva'],
                 o['internal'], o['cls'], o['outer'], idx, num))
    # the camera manager, for comparison
    pcm_cls = md.q(rdi + 0x18)
    pcm_outer = md.q(rdi + 0x28)
    pcm_idx = (md.q(rdi + 0x10) or 0) & 0xFFFFFFFF
    print("    PCM 0x%X  vtable rva 0x%X  InternalIndex=%d  Class=0x%X  Outer=0x%X"
          % (rdi, (md.q(rdi) or 0) - gb, pcm_idx, pcm_cls or 0, pcm_outer or 0))
    same = [o for o in objs if o['outer'] == pcm_outer]
    print("    -> %d of them share the PCM's Outer (same level/world)" % len(same))
    print("")
    print("  bytes at Target-0x40 .. Target+0x60:")
    b = md.read(rcx - 0x40, 0xA0)
    print(hexdump(b, base=-0x40) if b else "   (absent)")
    return dict(md=md, gb=gb, rcx=rcx, rdi=rdi, rbx=rbx, objs=objs)


if __name__ == '__main__':
    for p in sys.argv[1:]:
        report(p)
