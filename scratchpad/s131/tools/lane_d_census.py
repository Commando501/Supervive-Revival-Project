# S131 LANE D - full .data record-table census: classify EVERY record's impl.
# Read-only, offline. Records read from a SINGLE-STATE image (.data coherent);
# impl bytes/coverage read from the union of every image on disk (.text only).
import struct, os, sys, collections, csv, json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
IMAGES = [
    ('merged4',  os.path.join(ROOT,'dumps','merged4.dump.exe')),
    ('merged3',  os.path.join(ROOT,'dumps','merged3.dump.exe')),
    ('merged2',  os.path.join(ROOT,'dumps','merged2.dump.exe')),
    ('rideable', os.path.join(ROOT,'dumps','s131-rideable-live','SUPERVIVE-Win64-Shipping.dump.exe')),
    ('droppod',  os.path.join(ROOT,'dumps','s131-droppod-live','SUPERVIVE-Win64-Shipping.dump.exe')),
    ('s129',     os.path.join(ROOT,'dumps','s129-poolgate','SUPERVIVE-Win64-Shipping.dump.exe')),
    ('tuthero',  os.path.join(ROOT,'dumps','tutorial-hero','SUPERVIVE-Win64-Shipping.dump.exe')),
]
IMAGES = [(n,p) for n,p in IMAGES if os.path.exists(p)]
RECORD_IMAGE = 's129'   # single-state; .data is coherent

_c = {}
def L(name):
    if name not in _c:
        path = dict(IMAGES)[name]
        data = open(path,'rb').read()
        pe = struct.unpack_from('<I',data,0x3C)[0]
        base = struct.unpack_from('<Q',data,pe+0x30)[0]
        nsec = struct.unpack_from('<H',data,pe+6)[0]; opt = struct.unpack_from('<H',data,pe+0x14)[0]
        secs = {}
        for i in range(nsec):
            o = pe+0x18+opt+i*40
            nm = data[o:o+8].rstrip(b'\x00').decode()
            secs[nm] = (struct.unpack_from('<I',data,o+12)[0], struct.unpack_from('<I',data,o+8)[0])
        _c[name] = (data, base, secs)
    return _c[name]

def cstr(data, rva, maxn=160):
    e = data.find(b'\x00', rva, rva+maxn)
    if e < 0: return None
    s = data[rva:e]
    if not s: return None
    try: t = s.decode('ascii')
    except Exception: return None
    return t if t.isprintable() else None

STRIDE = 0x48
def scan_records(img=RECORD_IMAGE):
    data, base, secs = L(img)
    tv,tsz = secs['.text']; rv,rsz = secs['.rdata']; dv,dsz = secs['.data']
    out=[]; o = dv - (dv%8); end = dv+dsz
    while o < end-0x20:
        n = struct.unpack_from('<Q',data,o)[0]
        if base <= n < base+len(data) and rv <= n-base < rv+rsz:
            nm = cstr(data, n-base)
            if nm and 2 <= len(nm) <= 96:
                th = struct.unpack_from('<Q',data,o+8)[0]
                im = struct.unpack_from('<Q',data,o+16)[0]
                if base<=th<base+len(data) and base<=im<base+len(data):
                    trv=th-base; irv=im-base
                    if tv<=trv<tv+tsz and tv<=irv<tv+tsz:
                        out.append(dict(rec=o-8, name=nm, thunk=trv, impl=irv))
        o += 8
    return out

_pagecache = {}
def page_lit(rva):
    pg = rva & ~0xFFF
    if pg in _pagecache: return _pagecache[pg]
    hits=[]
    for nm,_ in IMAGES:
        data,base,secs = L(nm)
        if any(data[pg:pg+0x1000]): hits.append(nm)
    _pagecache[pg] = hits
    return hits

def impl_bytes(rva, n=24):
    for nm,_ in IMAGES:
        data,base,secs = L(nm)
        pg = rva & ~0xFFF
        if any(data[pg:pg+0x1000]):
            return nm, data[rva:rva+n]
    return None, b''

def classify_bytes(b):
    if not b: return 'UNKNOWN',''
    h = b.hex()
    if b[:3] == b'\x48\x8b\x01' and len(b)>=5 and b[3]==0xff and b[4] in (0x20,0x60,0xa0,0xe0):
        return 'FORWARDER', 'mov rax,[rcx]; jmp qword [rax+disp]'
    pats = [
        (b'\x33\xc0\xc3',         'xor eax,eax; ret   -> 0/false/nullptr'),
        (b'\x31\xc0\xc3',         'xor eax,eax; ret   -> 0/false/nullptr'),
        (b'\x32\xc0\xc3',         'xor al,al; ret     -> false'),
        (b'\x30\xc0\xc3',         'xor al,al; ret     -> false'),
        (b'\xb0\x01\xc3',         'mov al,1; ret      -> true'),
        (b'\xb0\x00\xc3',         'mov al,0; ret      -> false'),
        (b'\x48\x33\xc0\xc3',     'xor rax,rax; ret   -> nullptr'),
        (b'\x48\x31\xc0\xc3',     'xor rax,rax; ret   -> nullptr'),
        (b'\x0f\x57\xc0\xc3',     'xorps xmm0,xmm0; ret -> 0.0f'),
        (b'\x66\x0f\x57\xc0\xc3', 'xorpd xmm0,xmm0; ret -> 0.0'),
        (b'\x33\xc0\xc2',         'xor eax,eax; ret imm16'),
    ]
    for p,d in pats:
        if b.startswith(p): return 'TRIVIAL', d
    if b[0] == 0xc3:
        return 'TRIVIAL', 'ret                (void, no body)'
    if b[0] == 0xc2:
        return 'TRIVIAL', 'ret 0x%04x         (void, no body)' % struct.unpack_from('<H',b,1)[0]
    return 'REAL', h[:24]

def main():
    recs = scan_records()
    print('[records] image=%s n=%d (unit: records)' % (RECORD_IMAGE, len(recs)))

    recs.sort(key=lambda r:r['rec'])
    runs=[]; cur=[]
    for r in recs:
        if cur and r['rec']-cur[-1]['rec']==STRIDE: cur.append(r)
        else:
            if cur: runs.append(cur)
            cur=[r]
    if cur: runs.append(cur)
    print('[runs] n=%d (unit: contiguous runs)' % len(runs))

    uht = list(csv.DictReader(open(os.path.join(ROOT,'tools','re','out','uht_funcflags_tuthero.csv'))))
    by_owner = collections.defaultdict(set)
    flags_of = {}
    for r in uht:
        by_owner[r['owner']].add(r['func'])
        flags_of[(r['owner'], r['func'])] = r['flags']
    name2owners = collections.defaultdict(list)
    for o,fs in by_owner.items():
        for f in fs: name2owners[f].append(o)

    attributed = 0
    for run in runs:
        names = set(x['name'] for x in run)
        votes = collections.Counter()
        for n in names:
            for o in name2owners.get(n, ()): votes[o]+=1
        ranked = sorted(((v/len(names), o) for o,v in votes.items()), reverse=True)
        cls = None
        if ranked:
            top = ranked[0]; sec = ranked[1][0] if len(ranked)>1 else 0.0
            if top[0] >= 0.6 and top[0] > sec: cls = top[1]
        for x in run:
            x['cls'] = cls or '?'
            x['flags'] = flags_of.get((cls, x['name']), '') if cls else ''
        if cls: attributed += len(run)
    print('[attribution] %d/%d records attributed to a unique UHT owner class' % (attributed, len(recs)))

    for r in recs:
        irv = r['impl']
        img, b = impl_bytes(irv)
        if img is None:
            r['verdict']='IMPL-PAGE-DARK'; r['detail']='no image on disk has this .text page'; r['bytes']=''; r['src_img']=''
            continue
        kind, detail = classify_bytes(b)
        r['bytes'] = b[:16].hex(); r['src_img'] = img
        if kind == 'TRIVIAL':   r['verdict']='EMPTY';     r['detail']=detail
        elif kind == 'FORWARDER': r['verdict']='FORWARDER'; r['detail']=detail
        else:                   r['verdict']='REAL';      r['detail']=''

    out = os.path.join(ROOT,'scratchpad','s131','laneD')
    os.makedirs(out, exist_ok=True)
    json.dump(recs, open(os.path.join(out,'recs.json'),'w'))
    print('[saved] scratchpad/s131/laneD/recs.json')
    print('[verdicts]', dict(collections.Counter(r['verdict'] for r in recs)))

if __name__ == '__main__':
    main()
