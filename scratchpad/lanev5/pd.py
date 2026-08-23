import csv, bisect, sys
rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f):
        rows.append((int(x['begin_rva'],16), int(x['end_rva'],16), int(x['size']), int(x['unwind_rva'],16), int(x['seen_in_dumps'])))
rows.sort()
begins=[a for a,_,_,_,_ in rows]
def containing(rva):
    i=bisect.bisect_right(begins, rva)-1
    if i<0: return None,None
    b,e,s,u,seen=rows[i]
    if not (b<=rva<e): return None,rows[i]
    # walk back over contiguous chain
    j=i
    while j>0 and rows[j-1][1]==rows[j][0]:
        j-=1
    # walk forward
    k=i
    while k+1<len(rows) and rows[k][1]==rows[k+1][0]:
        k+=1
    return (rows[j][0], rows[k][1], i-j, rows[i]), rows[i]
for a in sys.argv[1:]:
    rva=int(a,16)
    c,row=containing(rva)
    if c:
        print("0x%08X  ROW begin=0x%X end=0x%X size=%d seen=%d | CHAIN entry=0x%X end=0x%X (rowidx+%d)" % (
            rva, row[0], row[1], row[2], row[4], c[0], c[1], c[2]))
    else:
        print("0x%08X  NOT COVERED (no pdata row). nearest-below: begin=0x%X end=0x%X seen=%s" % (rva, row[0], row[1], row[4]) if row else "no row")
