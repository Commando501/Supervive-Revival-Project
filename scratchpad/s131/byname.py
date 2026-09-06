import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s131\tools")
import rectab
rectab.P['merged4'] = r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
recs = rectab.scan('merged4')
FOLD = rectab.FOLD
want = set(sys.argv[1:])
for r in sorted(recs, key=lambda r:r['name']):
    if r['name'] in want:
        cls = FOLD.get(r['impl'], 'REAL')
        print("%-42s rec=0x%08X thunk=0x%08X impl=0x%08X  %s" % (r['name'], r['rec'], r['thunk'], r['impl'], cls))
