import hashlib,struct,os,glob
def text_digest(p):
    d=open(p,"rb").read()
    pe=struct.unpack_from("<I",d,0x3C)[0]
    nsec=struct.unpack_from("<H",d,pe+6)[0]; opt=struct.unpack_from("<H",d,pe+20)[0]
    st=pe+24+opt
    for i in range(nsec):
        o=st+i*40; nm=d[o:o+8].rstrip(b"\0").decode()
        if nm==".text":
            sz=struct.unpack_from("<I",d,o+16)[0]; ptr=struct.unpack_from("<I",d,o+20)[0]
            return hashlib.sha256(d[ptr:ptr+sz]).hexdigest()[:16], sz
    return None,None
KNOWN={"play":"9bc10a4552c596e1","dismount":"53483e6181bb3583","dropplane_b1only":"5b4467b0105dec1a",
 "droppod_pe_cdopoke":"249a3cd2190eb334","dismount_landstart":"0d5fa554edac53c5","rideable":"dd2281adce965add",
 "poolspawn_cdopoke":"efe8db553bf511ba","poolspawn_cdoctrl":"85f3cee44c31b1cd","botai":None,
 "botspawn":None,"botteam":None,"botspawn_readonly":None}
print(f"{'variant':28s} {'computed':18s} {'CLAUDE.md/doc says':18s} match  .textRawSize")
ok=0; tot=0
for f in sorted(glob.glob("tools/sigbypass-mod/build/tutorial_launch_*.dll")):
    v=os.path.basename(f)[len("tutorial_launch_"):-4]
    h,sz=text_digest(f)
    exp=KNOWN.get(v)
    tot+=1
    m="-" if exp is None else ("YES" if h==exp else "NO ")
    if m=="YES": ok+=1
    print(f"  {v:26s} {h:18s} {str(exp):18s} {m:5s}  {sz}")
print(f"\nverified against recorded digests: {ok} matched")
