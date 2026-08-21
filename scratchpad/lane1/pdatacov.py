import csv, collections
bm=open('dumps/merged5.dump.exe.textbm','rb').read()
TEXT_RVA=0x1000; NP=len(bm)
TEXT_END=TEXT_RVA+NP*0x1000
# pages covered by at least one .pdata function extent
covered=bytearray(NP)
nfun=0; darkfun=0; litfun=0; outside=0
funpages_dark=collections.Counter()
with open('tools/strxref/index/pdata_union.csv') as f:
    rd=csv.DictReader(f)
    for r in rd:
        b=int(r['begin_rva'],16); e=int(r['end_rva'],16)
        if not (TEXT_RVA<=b<TEXT_END): outside+=1; continue
        nfun+=1
        p0=(b-TEXT_RVA)//0x1000; p1=(min(e,TEXT_END-1)-TEXT_RVA)//0x1000
        for p in range(p0,p1+1):
            if p<NP: covered[p]=1
        if bm[p0]==0: darkfun+=1
        else: litfun+=1
ncov=sum(covered)
dark_pages=[i for i in range(NP) if bm[i]==0]
dark_cov=sum(1 for i in dark_pages if covered[i])
lit_pages=[i for i in range(NP) if bm[i]==1]
lit_cov=sum(1 for i in lit_pages if covered[i])
print(f".pdata union rows inside .text: {nfun}  (outside .text: {outside})")
print(f"pages covered by >=1 .pdata extent: {ncov}/{NP} ({100.0*ncov/NP:.2f}%)")
print(f"  of {len(dark_pages)} DARK pages: {dark_cov} covered by a .pdata function extent ({100.0*dark_cov/len(dark_pages):.2f}%)  [POSITIVE CONTROL: dark==real code, not padding]")
print(f"  of {len(lit_pages)} LIT  pages: {lit_cov} covered ({100.0*lit_cov/len(lit_pages):.2f}%)  [control]")
print(f"functions whose ENTRY page is dark: {darkfun} / {nfun} ({100.0*darkfun/nfun:.2f}%)   lit: {litfun}")
