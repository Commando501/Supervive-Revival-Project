exec(open(r"scratchpad/s140/syn/adj.py").read().split("print(\"\n=== CONTROLS")[0])
print("DARK 0x5A6AC40 page_nz=",pagenz(0x5A6AC40))
print("\n=== LOAD-BEARING BYTES ===")
sites=[
 (0x035E9F17,3,"call [rdx+0x6b8] HasValidData"),
 (0x035E9F1F,2,"EXIT1 je 0x35EB1A7"),
 (0x035E9F28,2,"EXIT2 je 0x35EB1A7"),
 (0x035E9F97,2,"EXIT3 je 0x35EB7CF"),
 (0x035E9FA4,2,"EXIT4 jne 0x35EB7CF"),
 (0x035E9FB5,2,"call [rax+0x4c0] IsSimulatingPhysics"),
 (0x035E9FBD,2,"EXIT5 jne 0x35EB7CF"),
 (0x035EA25D,2,"EXIT6 je 0x35EB150"),
 (0x035EB126,2,"mov rax,[rbx]"),
 (0x035EB129,2,"xor r8d,r8d ITERATIONS=0"),
 (0x035EB137,2,"mov rcx,rbx"),
 (0x035EB13A,2,"CALL [rax+0x720] StartNewPhysics"),
 (0x035EB140,2,"post-SNP mov rax,[rbx]"),
 (0x035EB146,2,"call [rax+0x6b8] HasValidData #2"),
 (0x035EB14E,2,"jne 0x35EB1CB  (FALLTHROUGH=BAIL 0x35EB150)"),
 (0x035EB554,2,"mov rax,[rbx]"),
 (0x035EB566,2,"mov rcx,rbx"),
 (0x035EB569,2,"CALL [rax+0xa50] -> A50 CLEAR"),
 (0x035E9EFD,2,"mov rbx,rcx  (this)"),
 (0x0530ABF0,6,"A50 clear body"),
 (0x055C2430,10,"ULokiCMC::StartNewPhysics"),
 (0x055B85C1,2,"Loki PM -> Super call"),
 (0x055B8414,2,"+0x12B0 writer A"),
 (0x055C248B,2,"+0x12B0 writer B"),
 (0x055A74D6,2,"+0x12B0 writer C"),
 (0x055B7CCD,2,"+0x12B0 writer D"),
 (0x055BDD22,2,"+0x12B0 writer E"),
 (0x0530AC10,10,"GetRecentVelocity impl"),
 (0x035E64C0,16,"HasValidData full"),
 (0x03C9B0A0,14,"IsSimulatingPhysics"),
]
for a,n,nm in sites:
    print("-- %s"%nm)
    for ad,b,t in dis(a,n): print("   %#010x  %-24s %s"%(ad,b,t))
