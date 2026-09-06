import sys, struct, bisect
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
sec={s['name']:s for s in im.sections}; P=sec['.pdata']
buf = im.data[P['praw']:P['praw']+P['vsz']]
nz = sum(1 for x in buf[:0x1000] if x)
print("pdata first page nonzero:", nz, "size", hex(P['vsz']))
