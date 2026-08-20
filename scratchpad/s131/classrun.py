import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s131\tools")
import rectab
rectab.P['merged4']=r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
recs=rectab.scan('merged4')
groups=rectab.runs(recs)
key=sys.argv[1]
for g in groups:
    names=[r['name'] for r in g]
    if key in names:
        print("RUN of %d records containing %r  (rec 0x%08X..0x%08X)"%(len(g),key,g[0]['rec'],g[-1]['rec']))
        for r in g:
            cls = rectab.FOLD.get(r['impl'],'REAL')
            print("   %-42s thunk=0x%08X impl=0x%08X  %s"%(r['name'],r['thunk'],r['impl'],cls))
        print()
