import re,sys,collections
NAMES='scratchpad/s134/laneb/allmaps.names.txt'
pkgnames={}; cur=None
for line in open(NAMES,encoding='utf-8',errors='replace'):
    if line.startswith('# ====='): break
    if line.startswith('# FAIL'): continue
    if line.startswith('# '): cur=line[2:].strip(); pkgnames[cur]=set(); continue
    if cur and line.startswith('  '): pkgnames[cur].add(line[2:].rstrip('\n'))
def mapof(p):
    m=re.search(r'/([^/]+)/_Generated_/',p)
    return m.group(1) if m else p.split('/')[-1].replace('.umap','')
for t in sys.argv[1:]:
    hits=collections.Counter(); pk=0
    for p,s in pkgnames.items():
        n=sum(1 for x in s if t.lower() in x.lower())
        if n: pk+=1; hits[mapof(p)]+=n
    print('\n=== substr %-38s pkgs=%d maps=%d totalNames=%d'%(t,pk,len(hits),sum(hits.values())))
    for k,v in hits.most_common(20): print('      %5d  %s'%(v,k))
