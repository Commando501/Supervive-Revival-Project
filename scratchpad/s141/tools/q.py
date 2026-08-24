import sys, json, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
recs = json.load(open('recs.json'))
FOLDS = {0x0F7EC20:'VOID ret0(c20000)',0x0F7EB50:'NULL/false(33c0c3)',0x0F7EB60:'false(32c0c3)',
         0x0B9E1F0:'true(b001c3)',0x0FC6CF0:'0.0f(0f57c0c3)'}
import collections
implcount = collections.Counter(r[3] for r in recs)
thunkcount = collections.Counter(r[2] for r in recs)
def grade(rva):
    if rva in FOLDS: return 'FOLD:'+FOLDS[rva]
    n = im.page_nonzero(rva)
    if n == 0: return 'DARK(0/4096)'
    return f'REAL?(page {n}/4096)'
terms = sys.argv[1:]
for t in terms:
    hits = [r for r in recs if t.lower() in r[1].lower()]
    print(f"=== '{t}'  {len(hits)} hit(s)")
    for rec_va, name, thunk, impl in sorted(hits, key=lambda x:x[1]):
        print(f"   {name:44s} rec@.data {rec_va:#010x} thunk {thunk:#09x}(fold{thunkcount[thunk]}) impl {impl:#09x}(fold{implcount[impl]})  {grade(impl)}")
