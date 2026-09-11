import sys, os, struct, glob
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis

ROOT = r"G:\git\Supervive Revival Project\dumps"
imgs = []
for p in sorted(glob.glob(os.path.join(ROOT, "merged*.dump.exe"))):
    imgs.append((os.path.basename(p), fkdis.Img(p)))
# also every single-state dump
for p in sorted(glob.glob(os.path.join(ROOT, "*", "SUPERVIVE-Win64-Shipping.dump.exe"))):
    imgs.append((os.path.basename(os.path.dirname(p)), fkdis.Img(p)))

targets = [int(x,0) for x in sys.argv[1:]]
for t in targets:
    hits = []
    for name, im in imgs:
        d = im.read(t & ~0xFFF, 0x1000)
        if d and any(d):
            hits.append(name)
    print(f"0x{t:08X}  page 0x{t&~0xFFF:08X}  LIT in {len(hits)}/{len(imgs)}: {', '.join(hits[:8])}{'...' if len(hits)>8 else ''}")
