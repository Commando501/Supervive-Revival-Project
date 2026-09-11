import sys, struct
P = sys.argv[1] if len(sys.argv) > 3 else r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\Binds.Cache"
if len(sys.argv) > 3:
    off = int(sys.argv[2], 0); n = int(sys.argv[3], 0)
else:
    off = int(sys.argv[1], 0); n = int(sys.argv[2], 0)
d = open(P, 'rb').read()
for i in range(0, n, 16):
    c = d[off+i:off+i+16]
    if not c: break
    h = ' '.join(f'{b:02x}' for b in c)
    a = ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)
    print(f'{off+i:08x}  {h:<47}  {a}')
