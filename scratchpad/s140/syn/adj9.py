exec(open(r"scratchpad/s140/syn/adj.py").read().split("print(\"\n=== CONTROLS")[0])
# .data {name,thunk,impl} triple check
for rec,exp_impl,lbl in [(0x09BC9AD0,0x0530AC10,'GetRecentVelocity'),(0x09BC4B60,0x055AC8E0,'GetLokiCharacterMovement')]:
    n=q(rec)-IB; th=q(rec+8)-IB; im=q(rec+16)-IB
    s=D[n:n+64].split(b'\0')[0].decode('ascii','replace')
    print("rec %#010x name=%#010x '%s' thunk=%#010x impl=%#010x  expect %s %s"%(rec,n,s,th,im,hex(exp_impl),"PASS" if im==exp_impl else "FAIL"))
# uniqueness of vtable pointers
rs,re_=0x1000,0x1000+0xa724000
for t,lbl in [(0x055C2430,'LokiSNP'),(0x0530ABF0,'A50clear'),(0x055B8370,'LokiPM'),(0x03600990,'engSNP'),(0x035E9EC0,'engPM')]:
    pv=(t+IB).to_bytes(8,'little'); c=[]; i=D.find(pv,0,len(D))
    while i!=-1:
        if i%8==0: c.append(i)
        i=D.find(pv,i+1,len(D))
    print("  stored aligned ptrs to %-10s %#010x : %d  at %s"%(lbl,t,len(c),[hex(x) for x in c[:5]]))
