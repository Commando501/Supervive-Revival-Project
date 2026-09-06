import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s131\tools")
import rectab
rectab.P['merged4']=r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
recs=rectab.scan('merged4'); groups=rectab.runs(recs)
for key in sys.argv[1:]:
    for g in groups:
        names=[r['name'] for r in g]
        if key in names:
            emp=[r['name'] for r in g if r['impl'] in rectab.FOLD]
            print("run w/ %-34s n=%-3d EMPTY=%d/%d : %s"%(key,len(g),len(emp),len(g),", ".join(emp) or "-"))
            break
    else:
        print("run w/ %-34s NOT FOUND"%key)
