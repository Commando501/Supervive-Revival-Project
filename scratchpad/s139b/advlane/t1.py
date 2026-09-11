exec(open('H.py').read())
print('page 35EC000 nz=%d/4096' % pnz(0x35EC000))
dump(0x035EC850, 0x035EC8A0)
print('--- jb target 0x35EE577 ---')
dump(0x035EE577, 0x035EE5A0)
print('--- rip-rel const at 0x035EC873 ---')
# recompute machine-side below
