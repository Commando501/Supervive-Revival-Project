import pickle, collections
bms=pickle.load(open('scratchpad/lane1/bms.pkl','rb'))
NP=len(next(iter(bms.values())))
S={k:set(i for i in range(NP) if v[i]) for k,v in bms.items()}
GAME={'tutorial-hero','s129-poolgate','s131-droppod-live','s131-rideable-live','s132-dismount-live','s132-landstart-live'}
CRASH={k for k in S if k.startswith('crash-')}
MENU=set(S)-GAME-CRASH
def U(ks):
    r=set()
    for k in ks: r|=S[k]
    return r
um,ug,uc=U(MENU),U(GAME),U(CRASH)
ua=um|ug|uc
print(f"MENU-era images ({len(MENU)}): union {len(um)} pages ({100.0*len(um)/NP:.2f}%)")
print(f"TUTORIAL-WORLD images ({len(GAME)}): union {len(ug)} pages ({100.0*len(ug)/NP:.2f}%)")
print(f"CRASH-era images ({len(CRASH)}): union {len(uc)} pages ({100.0*len(uc)/NP:.2f}%)")
print(f"ALL: {len(ua)}")
print()
print(f"  tutorial-world \ menu   = {len(ug-um):5d} pages  <- measured yield of advancing to a staged world")
print(f"  menu \ tutorial-world   = {len(um-ug):5d} pages")
print(f"  crash \ (menu|game)     = {len(uc-um-ug):5d} pages")
print()
# marginal of each gameplay image over the union of ALL OTHERS
print("LEAVE-ONE-OUT unique contribution (pages this image has that NO other image has):")
for k in sorted(S):
    others=set()
    for k2 in S:
        if k2!=k: others|=S[k2]
    u=len(S[k]-others)
    if u: print(f"   {k:28s} {u:5d}")
print()
# marginal of each tutorial-world image over the MENU union
print("Marginal of each TUTORIAL-WORLD image over the MENU-era union:")
for k in sorted(GAME):
    print(f"   {k:28s} +{len(S[k]-um):5d}")
print()
# where do the tutorial-world-only pages live?
ma=pickle.load(open('scratchpad/lane1/modattr.pkl','rb'))['assign']
only=ug-um
c=collections.Counter(ma.get(p,'(unattributed / non-UObject engine+3rdparty)') for p in only)
print(f"module attribution of the {len(only)} tutorial-world-only pages:")
for m,n in c.most_common(20): print(f"   {n:5d}  {m}")
