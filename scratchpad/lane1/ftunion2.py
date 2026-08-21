import sys, glob, struct, array, collections
sys.path.insert(0,'tools/strxref')
import mdpdata as MD
dumps=sorted(glob.glob(r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp"))
tabs=[]
for p in dumps:
    try: d=MD.sane(MD.parse_ft(p,quiet=True))
    except Exception: continue
    if d and d['count']==524439: tabs.append(d)
N=524439
BEG=array.array('I',bytes(4*N)); END=array.array('I',bytes(4*N)); PHB=array.array('I',bytes(4*N))
for d in tabs:
    e=d['entries']
    for i in range(N):
        b,en,u=struct.unpack_from('<III',e,i*12)
        if en-b>1:
            if not END[i]: BEG[i]=b; END[i]=en
        else:
            if not PHB[i]: PHB[i]=b
nreal=sum(1 for i in range(N) if END[i])
print(f"tables={len(tabs)} slots={N} real-in-union={nreal} never-real={N-nreal}")
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); T=0x1000; TE=T+NP*0x1000
def pg(r): return (r-T)//0x1000 if T<=r<TE else None
pages_real=bytearray(NP); pages_any=bytearray(NP)
nr_in=0; nph_in=0
for i in range(N):
    if END[i]:
        p=pg(BEG[i])
        if p is not None:
            pages_real[p]=1; pages_any[p]=1; nr_in+=1
            p2=pg(END[i]-1)
            if p2 is not None:
                for q in range(p,p2+1): pages_real[q]=1; pages_any[q]=1
    else:
        p=pg(PHB[i])
        if p is not None: pages_any[p]=1; nph_in+=1
dark=[i for i in range(NP) if bm[i]==0]; lit=[i for i in range(NP) if bm[i]==1]
def f(sel,arr): return sum(1 for i in sel if arr[i])
print(f"real function extents inside .text: {nr_in}; never-real slots inside .text: {nph_in}")
print()
print("POSITIVE CONTROL -- is a dark page real code?")
print(f"  DARK pages ({len(dark)}): covered by a REAL extent {f(dark,pages_real)} ({100.0*f(dark,pages_real)/len(dark):.2f}%) ; carry ANY function begin (real or placeholder) {f(dark,pages_any)} ({100.0*f(dark,pages_any)/len(dark):.2f}%)")
print(f"  LIT  pages ({len(lit)}): covered by a REAL extent {f(lit,pages_real)} ({100.0*f(lit,pages_real)/len(lit):.2f}%) ; ANY begin {f(lit,pages_any)} ({100.0*f(lit,pages_any)/len(lit):.2f}%)")
# how many NEVER-REAL functions land in dark vs lit pages (via placeholder begin, +-1 page tolerance)
nr_dark=0; nr_lit=0; nr_near=0
for i in range(N):
    if END[i]: continue
    p=pg(PHB[i])
    if p is None: continue
    if bm[p]==0: nr_dark+=1
    else:
        # tolerance: placeholder begin is approximate (measured slop ~<=1 page)
        if (p>0 and bm[p-1]==0) or (p+1<NP and bm[p+1]==0): nr_near+=1
        else: nr_lit+=1
print()
print(f"NEVER-DECRYPTED functions (no real extent in ANY of {len(tabs)} minidumps): {nph_in} inside .text")
print(f"   placeholder begin lands on a DARK page: {nr_dark} ({100.0*nr_dark/nph_in:.2f}%)")
print(f"   lands on a LIT page but adjacent to dark: {nr_near} ({100.0*nr_near/nph_in:.2f}%)")
print(f"   lands on a LIT page not adjacent to dark: {nr_lit} ({100.0*nr_lit/nph_in:.2f}%)")
open('scratchpad/lane1/pages_real.bin','wb').write(bytes(pages_real))
open('scratchpad/lane1/pages_any.bin','wb').write(bytes(pages_any))
import pickle
pickle.dump({'BEG':BEG,'END':END,'PHB':PHB},open('scratchpad/lane1/ft.pkl','wb'))
