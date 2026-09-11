import re,sys,collections
NAMES='scratchpad/s134/laneb/allmaps.names.txt'
# path -> set(names) ; blocks are "# <path>" then indented names
pkgnames={}
cur=None
for line in open(NAMES,encoding='utf-8',errors='replace'):
    if line.startswith('# ====='): break
    if line.startswith('# FAIL'): continue
    if line.startswith('# '):
        cur=line[2:].strip(); pkgnames[cur]=set(); continue
    if cur and line.startswith('  '):
        pkgnames[cur].add(line[2:].rstrip('\n'))
print('packages parsed:',len(pkgnames),file=sys.stderr)

def mapof(p):
    m=re.search(r'/([^/]+)/_Generated_/',p)
    if m: return m.group(1)
    return p.split('/')[-1].replace('.umap','')

TOKENS=sys.argv[1:]
for t in TOKENS:
    hits=[p for p,s in pkgnames.items() if t in s]
    bymap=collections.Counter(mapof(p) for p in hits)
    print('\n=== %-42s  packages=%d  maps=%d' % (t, len(hits), len(bymap)))
    for k,v in bymap.most_common(25): print('      %5d  %s'%(v,k))
