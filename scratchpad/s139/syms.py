import sys, struct, json, os, re
sys.path.insert(0,'scratchpad/s139')
from img import DATA, IMAGEBASE, SECS, sec_of, q
TEXT_LO, TEXT_HI = 0x1000, 0x764A000
RD_LO, RD_HI = 0x764A000, 0x99C7000
DT_LO, DT_HI = 0x99C7000, 0xA0B7000
CACHE='scratchpad/s139/syms.json'

def build():
    syms={}   # rva -> name
    ident=re.compile(rb'^[A-Za-z_][A-Za-z0-9_]{2,127}\x00')
    n=0
    # scan .data for {name_ptr, thunk, impl}
    for off in range(DT_LO, DT_HI-24, 8):
        v0=struct.unpack_from('<Q',DATA,off)[0]
        if not (IMAGEBASE+RD_LO <= v0 < IMAGEBASE+RD_HI): continue
        s=v0-IMAGEBASE
        m=ident.match(DATA[s:s+130])
        if not m: continue
        name=DATA[s:s+m.end()-1].decode('latin1')
        v1=struct.unpack_from('<Q',DATA,off+8)[0]
        v2=struct.unpack_from('<Q',DATA,off+16)[0]
        if not (IMAGEBASE+TEXT_LO <= v1 < IMAGEBASE+TEXT_HI): continue
        if not (IMAGEBASE+TEXT_LO <= v2 < IMAGEBASE+TEXT_HI): continue
        t=v1-IMAGEBASE; i=v2-IMAGEBASE
        syms.setdefault(t,[]).append("exec"+name)
        syms.setdefault(i,[]).append(name)
        n+=1
    return syms,n

if os.path.exists(CACHE):
    SYMS={int(k):v for k,v in json.load(open(CACHE)).items()}
else:
    SYMS,n=build()
    json.dump({str(k):v for k,v in SYMS.items()}, open(CACHE,'w'))
    print("built %d records, %d rvas"%(n,len(SYMS)), file=sys.stderr)

# add uesymbols
try:
    ue=json.load(open('tools/strxref/index/uesymbols.json'))['symbols']
    for k,v in ue.items():
        r=int(k,16)
        nm=[x for x in v.get('names',[]) if not x.endswith('.cpp') and not x.endswith('.h')]
        cls=v.get('class','')
        for x in nm:
            lbl=(cls+"::"+x) if cls else x
            SYMS.setdefault(r,[]).append(lbl)
except Exception as e:
    print("ue syms fail",e,file=sys.stderr)

FOLDS={0x00F7EC20:'FOLD_ret0(void)',0x00F7EB50:'FOLD_null',0x00F7EB60:'FOLD_false',0x00B9E1F0:'FOLD_true',0x00FC6CF0:'FOLD_0.0f'}
def name(rva):
    if rva in FOLDS: return FOLDS[rva]
    v=SYMS.get(rva)
    if v: return "/".join(sorted(set(v))[:3])
    return None
if __name__=="__main__":
    for a in sys.argv[1:]:
        r=int(a,16); print("0x%08X %s"%(r,name(r)))
