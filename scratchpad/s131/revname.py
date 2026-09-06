import sys, os
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s131\tools")
import rectab
rectab.P['merged4'] = r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
recs = rectab.scan('merged4')
print("records scanned: %d (unit: records)" % len(recs), file=sys.stderr)
byimpl={}; bythunk={}
for r in recs:
    byimpl.setdefault(r['impl'],[]).append(r['name'])
    bythunk.setdefault(r['thunk'],[]).append(r['name'])
targets = [int(x,0) for x in sys.argv[1:]]
for t in targets:
    i = byimpl.get(t); th = bythunk.get(t)
    print("0x%08X  impl-of=%s  thunk-of=%s" % (t,
        ("%d:%s"%(len(i), i[:6]) if i else "-"),
        ("%d:%s"%(len(th), th[:6]) if th else "-")))
