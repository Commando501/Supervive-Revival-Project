import csv,bisect,sys
rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for r in csv.DictReader(f):
        rows.append((int(r['begin_rva'],16),int(r['end_rva'],16),int(r['seen_in_dumps'])))
rows.sort()
begins=[r[0] for r in rows]
def chain(a):
    # find containing row, then extend contiguous chain
    i=bisect.bisect_right(begins,a)-1
    if i<0: return None
    b,e,s=rows[i]
    if not (b<=a<e): return None
    # extend left
    lo=i
    while lo>0 and rows[lo-1][1]==rows[lo][0]: lo-=1
    hi=i
    while hi+1<len(rows) and rows[hi][1]==rows[hi+1][0]: hi+=1
    return rows[lo][0],rows[hi][1],rows[i]
for a in sys.argv[1:]:
    a=int(a,16)
    print(hex(a), [ (hex(x) if isinstance(x,int) else x) for x in (chain(a) or ('NONE',))])
