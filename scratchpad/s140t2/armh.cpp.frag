// ══════════════════════════════════════════════════════════════════════════════════════════════
// ★★★★★ S140 TIER 2 — ARM H: DOES `ULokiCMC::StartNewPhysics` ACTUALLY RUN?
//
// THE QUESTION. S139 recorded [M] "StartNewPhysics has NEVER run on either component", from
// CMC+0x16C8 reading 0. S140 Tier 1 RETRACTED that: +0x16C8 is not a latch, it is a per-frame
// TOptional<FVector> validity flag, SET by StartNewPhysics at 0x055C2469 and CLEARED later in the
// SAME engine PerformMovement call by ULokiCMC vtable disp 0xA50 (0x0530ABF0), on a path the
// StartNewPhysics call site DOMINATES. An off-thread reader sees 0 whether the step runs every
// frame or never runs at all. The instrument was invalid; the question is still open.
//
// THE DURABLE RECEIPT is the PAYLOAD, not the flag:
//     0x055C2448  movups xmm0,[rcx+0xe8]        ; Velocity   (3 doubles, LWC)
//     0x055C244F  movups [rcx+0x16b0], xmm0     ; snapshot X,Y   <-- the only CMC-side writer
//     0x055C2456  movsd  xmm1,[rcx+0xf8]
//     0x055C245E  movsd  [rcx+0x16c0], xmm1     ; snapshot Z
//     0x055C2469  mov byte [rcx+0x16c8], 1      ; the flag
//     0x055C2470  jmp 0x3600990                 ; tail -> engine StartNewPhysics
// disp 0xA50 clears ONLY the flag byte; it never touches the payload.
//
// ⚠⚠⚠ WHY THE HANDOFF DESIGN ALONE IS NOT ENOUGH, AND WHAT THIS ARM ADDS.
//   The handoff says: write a sentinel into Velocity, and read the payload. But a payload of
//   (0,0,0) is EXACTLY the degeneracy Tier 1 §7 warns about -- with Velocity resting at (0,0,0)
//   and NewObject zero-filling, "snapshotted a zero Velocity" and "never written at all" are the
//   SAME BYTES. S139 already banked `R1.velsnap@0x16B0 (0.000,0.000,0.000)` and it means nothing.
//   => THIS ARM PRE-POISONS THE PAYLOAD FIRST. A distinctive value written into +0x16B0..+0x16C7
//   makes "never written" and "written with zeros" different bytes, and it does so WITHOUT
//   touching Velocity at all.
//
// ★ THE POISON IS PROVABLY UNREACHABLE BY ANY CONSUMER. The payload only reader is
//   GetRecentVelocity (.data 0x09BC9AD0 -> impl 0x0530AC10, plus the same cmove idiom at
//   0x0530C7FF and 0x0559C59E): `cmp byte [rcx+0x16c8],0 / mov eax,0x16b0 / mov r8d,0xe8 /
//   cmove eax,r8d` -- it returns the PAYLOAD only when the flag is NON-ZERO, and the only writer
//   of flag=1 writes the payload 0x1A bytes earlier in the same straight-line block. So while the
//   flag is 0 the poison cannot be read, and the instant it becomes 1 the poison is already gone.
//   The arm reads the flag first and REFUSES to poison if it is non-zero.
//
// TWO OBJECTS, TWO ROLES, ONE RUN:
//   BOT    -- poison the payload AND write a sentinel into Velocity. If StartNewPhysics runs, the
//             payload must come back holding THE SENTINEL, which validates the whole mechanism
//             end to end (payload == a copy of Velocity) rather than merely "something wrote it".
//   PLAYER -- poison the payload ONLY. Velocity is NOT touched. If StartNewPhysics runs, the
//             payload must come back (0,0,0). This is the VELOCITY-WRITE-FREE arm: it settles the
//             same question with zero perturbation of the system under test, so if the two arms
//             disagree the disagreement is itself the finding.
//   The two poisons are DIFFERENT VALUES, so each object payload must carry its OWN poison --
//   a two-sided addressing control that fails loudly if the CMC resolution is wrong.
//
// ⚠ THE SENTINEL IS 2^-10 = 0.0009765625 uu/s. Exactly representable, and ~0.001 uu/s is
//   physically inert. Do NOT use a large value (an offline lane proposed (1234.5, 6789.25,
//   -4242.125) = ~8,000 uu/s): if the physics step IS running, that launches the pawn and
//   perturbs the very thing being measured.
//
// ⚠⚠ THE READ CANNOT HAPPEN HERE. BsLadderStep runs ON THE GAME THREAD inside OnPI, so every
//   Sleep() in it BLOCKS THE GAME THREAD and NO FRAMES PASS. A write-Sleep-read inside this
//   function would be guaranteed to read the un-updated payload and would have been written up as
//   "StartNewPhysics does not run" -- a false negative manufactured by the instrument. The
//   sampling therefore runs on the WORKER thread AFTER FsDisarm (the RM_DROPPLANE B4 precedent),
//   where Sleep() costs the game nothing.
//
// RISK CLASS: DATA. Three aligned stores inside two existing allocations (2 x 24-byte scratch
//   payload + 1 x 24-byte Velocity), every one readback-verified, Velocity restored to (0,0,0) at
//   the end. No module-image write, no PI hook, no SpawnActor, no CDO poke of its own.
// ══════════════════════════════════════════════════════════════════════════════════════════════
#if (KBSPSARMS & 0x200)
static const double kShBotPoison[3]={-9876.5,      -8765.25,     -7654.125};
static const double kShPlrPoison[3]={-1234.5,      -2345.25,     -3456.125};
static const double kShSentinel [3]={ 0.0009765625, 0.0,          0.0};

static uintptr_t g_shBotCmc=0,  g_shPlrCmc=0, g_shBotPawn=0, g_shPlrPawn=0;
static int  g_shBotPoisoned=0,  g_shPlrPoisoned=0, g_shSentinelOK=0, g_shArmed=0;
static int  g_shBotFlag0=-1,    g_shPlrFlag0=-1;

// 24 raw bytes -> "xx xx xx ..".  RAW FIRST, DERIVE AFTER: a formatted double print hides a signed
// zero, and that exact defect cost S139 flight 3 its finding for an hour.
static void ShHex24(uintptr_t a,char* out,size_t n){
    out[0]=0; if(!SafeReadable((void*)a,24)){ _snprintf_s(out,n,_TRUNCATE,"<unreadable>"); return; }
    const uint8_t* p=(const uint8_t*)a; int o=0;
    for(int i=0;i<24&&o<(int)n-4;i++) o+=_snprintf_s(out+o,n-o,_TRUNCATE,"%02X%s",p[i],((i&7)==7&&i!=23)?"|":"");
}
static int ShEq3(uintptr_t a,const double* v){
    if(!SafeReadable((void*)a,24)) return 0;
    const double* p=(const double*)a;
    return (p[0]==v[0]&&p[1]==v[1]&&p[2]==v[2])?1:0;
}
static int ShIsZero3(uintptr_t a){
    if(!SafeReadable((void*)a,24)) return 0;
    const double* p=(const double*)a;
    return (p[0]==0.0&&p[1]==0.0&&p[2]==0.0)?1:0;
}
static void ShDump(const char* tag,uintptr_t cmc){
    if(!LooksLikePtr(cmc)){ Markerf("[SNP] %-14s CMC is NULL\r\n",tag); return; }
    char hp[128],hv[128]; ShHex24(cmc+0x16B0,hp,sizeof(hp)); ShHex24(cmc+0xE8,hv,sizeof(hv));
    Markerf("[SNP] %-14s payload@0x16B0 RAW %s\r\n",tag,hp);
    Markerf("[SNP] %-14s Velocity@0xE8  RAW %s\r\n",tag,hv);
    if(SafeReadable((void*)(cmc+0x16B0),24)){ const double* p=(const double*)(cmc+0x16B0);
        Markerf("[SNP] %-14s payload dec (%.10g, %.10g, %.10g)\r\n",tag,p[0],p[1],p[2]); }
    if(SafeReadable((void*)(cmc+0xE8),24)){ const double* v=(const double*)(cmc+0xE8);
        Markerf("[SNP] %-14s Velocity dec (%.10g, %.10g, %.10g)\r\n",tag,v[0],v[1],v[2]); }
    uint8_t fl=SafeReadable((void*)(cmc+0x16C8),1)?*(uint8_t*)(cmc+0x16C8):0xFF;
    float t12=SafeReadable((void*)(cmc+0x12B0),4)?*(float*)(cmc+0x12B0):-1.0f;
    Markerf("[SNP] %-14s flag@0x16C8=%u  TimeSinceFallingStart@0x12B0=%.4f\r\n",tag,fl,(double)t12);
    if(SafeReadable((void*)(cmc+0x328),24)){ const double* A=(const double*)(cmc+0x328);
        Markerf("[SNP] %-14s Accel@0x328 (%.6g, %.6g, %.6g)\r\n",tag,A[0],A[1],A[2]); }
}
// The three FREE READS Tier 1 §7 ranks 2,3,4 -- never taken live by anyone.
static void ShFreeReads(const char* tag,uintptr_t cmc){
    if(!LooksLikePtr(cmc)) return;
    uintptr_t wp =SafeReadable((void*)(cmc+0xC0),8)?*(uintptr_t*)(cmc+0xC0):0;
    int32_t  ja  =SafeReadable((void*)(cmc+0x3DC),4)?*(int32_t*)(cmc+0x3DC):-999;
    float    mts =SafeReadable((void*)(cmc+0x3E0),4)?*(float*)(cmc+0x3E0):-1.0f;
    int32_t  msi =SafeReadable((void*)(cmc+0x3E4),4)?*(int32_t*)(cmc+0x3E4):-999;
    uintptr_t vp =SafeReadable((void*)cmc,8)?*(uintptr_t*)cmc:0;
    uintptr_t lvt=g_modBase+0x088F8570, evt=g_modBase+0x07FBED58;
    char wn[96]; wn[0]=0; if(LooksLikePtr(wp)) GetFNameStr(NameId(wp),wn,sizeof(wn));
    Markerf("[SNP] %-14s WorldPrivate@0xC0=0x%llX '%s'  %s\r\n",tag,(unsigned long long)wp,wn,
            LooksLikePtr(wp)?"NON-NULL -> engine PerformMovement exit 2 input is satisfied"
                           :"*** NULL -- exit 2 would bail ***");
    Markerf("[SNP] %-14s NumJumpApexAttempts@0x3DC=%d  MaxSimulationTimeStep@0x3E0=%.6g  "
            "MaxSimulationIterations@0x3E4=%d %s\r\n",tag,ja,(double)mts,msi,
            (msi>0)?"(>0 -> engine StartNewPhysics 4th early-out 0x036009B5 does NOT bail)"
                  :"*** <=0 -- THE 4TH EARLY-OUT BAILS ***");
    Markerf("[SNP] %-14s vptr=0x%llX  ULokiCMC vt=0x%llX  engine vt=0x%llX -> %s\r\n",tag,
            (unsigned long long)vp,(unsigned long long)lvt,(unsigned long long)evt,
            (vp==lvt)?"ULokiCMC (disp 0x720 = 0x055C2430, the function under test)"
                    :((vp==evt)?"*** ENGINE UCharacterMovementComponent -- disp 0x720 = 0x03600990 and "
                                "NOTHING touches +0x16C8/+0x16B0. THE WHOLE TEST IS VOID. ***"
                              :"*** NEITHER KNOWN VTABLE -- report raw, do not interpret ***"));
}
// Resolve the CMC off a pawn BY NAME, then assert the two mandatory identity controls.
// ⚠ A hardcoded offset that "agrees" with a by-name read is NOT corroboration when both can read
//   zero (recorded S138 defect: Velocity is CMC+0xE8, not the +0xE0 one probe hardcoded). So the
//   by-name resolve is REQUIRED and 0x458 is printed only as a cross-check, never as a fallback.
static uintptr_t ShResolveCmc(const char* tag,uintptr_t pawn){
    if(!LooksLikePtr(pawn)){ Markerf("[SNP] %-14s REFUSED: pawn is NULL\r\n",tag); return 0; }
    uintptr_t cls=ClassOf(pawn); if(!LooksLikePtr(cls)){
        Markerf("[SNP] %-14s REFUSED: pawn has no class\r\n",tag); return 0; }
    uint32_t off=PropOffsetSuper(cls,"CharacterMovement");
    if(off==0xFFFFFFFF){ Markerf("[SNP] %-14s REFUSED: no 'CharacterMovement' UPROPERTY on the pawn "
                                 "class. NOT falling back to 0x458 -- an unvalidated offset here "
                                 "would read a stranger.\r\n",tag); return 0; }
    uintptr_t cmc=SafeReadable((void*)(pawn+off),8)?*(uintptr_t*)(pawn+off):0;
    uintptr_t alt=SafeReadable((void*)(pawn+0x458),8)?*(uintptr_t*)(pawn+0x458):0;
    char cn[128]; cn[0]=0; if(LooksLikePtr(cmc)&&LooksLikePtr(ClassOf(cmc)))
        GetFNameStr(NameId(ClassOf(cmc)),cn,sizeof(cn));
    Markerf("[SNP] %-14s pawn=0x%llX CharacterMovement@0x%X = 0x%llX class='%s'  (+0x458 reads "
            "0x%llX, %s)\r\n",tag,(unsigned long long)pawn,off,(unsigned long long)cmc,cn,
            (unsigned long long)alt,(alt==cmc)?"AGREES":"DISAGREES -- by-name wins");
    if(!LooksLikePtr(cmc)){ Markerf("[SNP] %-14s REFUSED: CharacterMovement is NULL\r\n",tag); return 0; }
    // CONTROL 1 -- ALokiCharacter has its OWN live bytes at +0x16B0/+0x16C8. A probe aimed at the
    // PAWN instead of the COMPONENT decodes a plausible WRONG value. CharacterOwner must be the pawn.
    uintptr_t owner=SafeReadable((void*)(cmc+0x198),8)?*(uintptr_t*)(cmc+0x198):0;
    // CONTROL 2 -- FActorComponentTickFunction::Target. PrimaryComponentTick is UActorComponent+0x40
    // [M, S139] and sizeof(FTickFunction) is 0x28, so Target sits at +0x68 and must equal the CMC.
    uintptr_t tgt=SafeReadable((void*)(cmc+0x68),8)?*(uintptr_t*)(cmc+0x68):0;
    Markerf("[SNP] %-14s CONTROL1 CharacterOwner@0x198=0x%llX vs pawn 0x%llX -> %s\r\n",tag,
            (unsigned long long)owner,(unsigned long long)pawn,(owner==pawn)?"PASS":"*** FAIL ***");
    Markerf("[SNP] %-14s CONTROL2 TickFn.Target@0x68=0x%llX vs cmc 0x%llX -> %s\r\n",tag,
            (unsigned long long)tgt,(unsigned long long)cmc,(tgt==cmc)?"PASS":"*** FAIL ***");
    if(owner!=pawn||tgt!=cmc){
        Markerf("[SNP] %-14s REFUSED: an identity control FAILED. Nothing is written to this "
                "object. This is an INSTRUMENT statement, not a result.\r\n",tag); return 0; }
    ShFreeReads(tag,cmc);
    return cmc;
}

static void BsPsSentinel(){
    Marker("[SNP] ================ ARM H: THE PAYLOAD-POISON / SENTINEL TEST ================\r\n");
    Marker("[SNP] QUESTION: does ULokiCMC::StartNewPhysics 0x055C2430 execute on these components?\r\n"
           "[SNP] The flag at +0x16C8 CANNOT answer it (S140 Tier 1: cleared every frame by vtable\r\n"
           "[SNP] disp 0xA50 = 0x0530ABF0 on a path the call DOMINATES -- it reads 0 in every world).\r\n"
           "[SNP] The PAYLOAD at +0x16B0 is durable: its only CMC-side writer is 0x055C244F, inside\r\n"
           "[SNP] StartNewPhysics on the Iterations==0 path.\r\n");
    Marker("[SNP] ---- PRE-REGISTERED OUTCOME TABLE (written BEFORE any write; do not reinterpret) ----\r\n");
    Marker("[SNP]   BOT   (payload poisoned AND Velocity = sentinel 2^-10):\r\n"
           "[SNP]     payload == SENTINEL  -> StartNewPhysics RAN, and the payload is a copy of\r\n"
           "[SNP]                             Velocity. Mechanism validated end to end.        [M]\r\n"
           "[SNP]     payload == (0,0,0)   -> StartNewPhysics RAN, and something ZEROED Velocity\r\n"
           "[SNP]                             before the snapshot. Also a major finding.       [M]\r\n"
           "[SNP]     payload == POISON    -> StartNewPhysics did NOT run in the window.        [M]\r\n"
           "[SNP]     anything else        -> UNMODELLED. Report raw; do not interpret.\r\n");
    Marker("[SNP]   PLAYER (payload poisoned, Velocity NOT touched -- the write-free arm):\r\n"
           "[SNP]     payload == (0,0,0)   -> StartNewPhysics RAN.                             [M]\r\n"
           "[SNP]     payload == POISON    -> StartNewPhysics did NOT run in the window.       [M]\r\n"
           "[SNP]     payload == BOT poison or BOT sentinel -> the CMC resolution is WRONG and\r\n"
           "[SNP]                             the run is VOID. (This is why the poisons differ.)\r\n");
    Marker("[SNP]   The two arms must AGREE unless there is a real bot/player asymmetry -- and S139\r\n"
           "[SNP]   flight 1 measured them identical on every structural field, so a disagreement\r\n"
           "[SNP]   would itself be the result.\r\n");

    uintptr_t ctl=g_psLbCtl[1];
    if(LooksLikePtr(ctl)){
        uintptr_t bp=SafeReadable((void*)(ctl+0x3F8),8)?*(uintptr_t*)(ctl+0x3F8):0;
        g_shBotPawn=bp;
        g_shBotCmc=ShResolveCmc("BOT",bp);
    } else Marker("[SNP] BOT arm SKIPPED: ARM D produced no LokiBotController. STAGING statement.\r\n");

    g_shPlrPawn=g_bsPlayerHero;
    if(LooksLikePtr(g_shPlrPawn)) g_shPlrCmc=ShResolveCmc("PLAYER",g_shPlrPawn);
    else Marker("[SNP] PLAYER arm SKIPPED: the A0 world scan latched no player hero.\r\n");

    if(!LooksLikePtr(g_shBotCmc)&&!LooksLikePtr(g_shPlrCmc)){
        Marker("[SNP] ARM H REFUSED: neither component resolved. Nothing was written.\r\n"); return; }

    Marker("[SNP] ---- BEFORE (raw) ----\r\n");
    ShDump("BOT-before",g_shBotCmc); ShDump("PLR-before",g_shPlrCmc);

    // ---- POISON. Refuse if the flag is already set: that would mean we are racing the step, and
    //      a payload written while the flag is 1 IS readable by GetRecentVelocity.
    if(LooksLikePtr(g_shBotCmc)){
        g_shBotFlag0=SafeReadable((void*)(g_shBotCmc+0x16C8),1)?*(uint8_t*)(g_shBotCmc+0x16C8):0xFF;
        if(g_shBotFlag0!=0){
            Markerf("[SNP] BOT NOT POISONED: flag@0x16C8 reads %d, not 0. That is the SEVENTH-BAIL "
                    "state (Tier 1 4.4) and is itself a finding -- report it. Poisoning now would be "
                    "readable by GetRecentVelocity.\r\n",g_shBotFlag0);
        } else if(SafeWritable((void*)(g_shBotCmc+0x16B0),24)){
            memcpy((void*)(g_shBotCmc+0x16B0),kShBotPoison,24);
            g_shBotPoisoned=ShEq3(g_shBotCmc+0x16B0,kShBotPoison);
            Markerf("[SNP] BOT poison written -> readback %s\r\n",g_shBotPoisoned?"OK":"*** FAILED ***");
        } else Marker("[SNP] BOT payload NOT WRITABLE -> not poisoned\r\n");
    }
    if(LooksLikePtr(g_shPlrCmc)){
        g_shPlrFlag0=SafeReadable((void*)(g_shPlrCmc+0x16C8),1)?*(uint8_t*)(g_shPlrCmc+0x16C8):0xFF;
        if(g_shPlrFlag0!=0){
            Markerf("[SNP] PLAYER NOT POISONED: flag@0x16C8 reads %d, not 0 (see above).\r\n",g_shPlrFlag0);
        } else if(SafeWritable((void*)(g_shPlrCmc+0x16B0),24)){
            memcpy((void*)(g_shPlrCmc+0x16B0),kShPlrPoison,24);
            g_shPlrPoisoned=ShEq3(g_shPlrCmc+0x16B0,kShPlrPoison);
            Markerf("[SNP] PLAYER poison written -> readback %s\r\n",g_shPlrPoisoned?"OK":"*** FAILED ***");
        } else Marker("[SNP] PLAYER payload NOT WRITABLE -> not poisoned\r\n");
    }

    // ---- SENTINEL: BOT ONLY. The player stays velocity-clean so its arm is write-free.
    if(LooksLikePtr(g_shBotCmc)&&SafeWritable((void*)(g_shBotCmc+0xE8),24)){
        memcpy((void*)(g_shBotCmc+0xE8),kShSentinel,24);
        g_shSentinelOK=ShEq3(g_shBotCmc+0xE8,kShSentinel);
        Markerf("[SNP] BOT sentinel Velocity = (2^-10, 0, 0) -> readback %s\r\n",
                g_shSentinelOK?"OK":"*** FAILED ***");
    } else if(LooksLikePtr(g_shBotCmc)) Marker("[SNP] BOT Velocity NOT WRITABLE -> no sentinel\r\n");

    Marker("[SNP] ---- AFTER THE WRITES (raw) ----\r\n");
    ShDump("BOT-armed",g_shBotCmc); ShDump("PLR-armed",g_shPlrCmc);
    g_shArmed=1;
    Marker("[SNP] ARM H armed. THE READ HAPPENS ON THE WORKER THREAD AFTER FsDisarm -- this function\r\n"
           "[SNP] runs on the GAME THREAD, so sleeping here would stop the frames the test needs.\r\n");
}

// ---- THE SAMPLER. Worker thread, AFTER FsDisarm, so Sleep() costs the game nothing.
static void ShSampleLoop(){
    if(!g_shArmed){ Marker("[SNP] sampler SKIPPED: ARM H never armed.\r\n"); return; }
    static const DWORD kAt[5]={250,750,2000,5000,10000};
    Marker("[SNP] ================ ARM H SAMPLER (worker thread, game thread free) ================\r\n");
    DWORD t0=GetTickCount(),prev=0;
    for(int i=0;i<5;i++){
        if(kAt[i]>prev) Sleep(kAt[i]-prev);
        prev=kAt[i];
        Markerf("[SNP] ---- sample %d at t=+%lu ms (elapsed %lu ms) ----\r\n",i,(unsigned long)kAt[i],
                (unsigned long)(GetTickCount()-t0));
        ShDump("BOT",g_shBotCmc); ShDump("PLR",g_shPlrCmc);
        for(int k=0;k<2;k++){
            uintptr_t pawn=k?g_shPlrPawn:g_shBotPawn; if(!LooksLikePtr(pawn))continue;
            uint32_t rc=PropOffsetSuper(ClassOf(pawn),"RootComponent");
            uintptr_t root=(rc!=0xFFFFFFFF&&SafeReadable((void*)(pawn+rc),8))?*(uintptr_t*)(pawn+rc):0;
            if(LooksLikePtr(root)&&SafeReadable((void*)(root+0x158),24)){
                const double* L=(const double*)(root+0x158);
                Markerf("[SNP] %-14s loc (%.3f, %.3f, %.3f)\r\n",k?"PLR":"BOT",L[0],L[1],L[2]); }
        }
    }
    // ---- VERDICT, computed from the OBSERVED bytes. A verdict line whose terms are all trivially
    //      true is a recorded defect class in this repo ("a verdict line can lie"), so every cell
    //      below is decided by an equality against a value we wrote or against exact zero.
    Marker("[SNP] ---------------- ARM H VERDICT ----------------\r\n");
    for(int k=0;k<2;k++){
        const char* tag=k?"PLAYER":"BOT";
        uintptr_t cmc=k?g_shPlrCmc:g_shBotCmc;
        int poisoned=k?g_shPlrPoisoned:g_shBotPoisoned;
        const double* poison=k?kShPlrPoison:kShBotPoison;
        if(!LooksLikePtr(cmc)){ Markerf("[SNP] %s: no component -- NO RESULT.\r\n",tag); continue; }
        if(!poisoned){ Markerf("[SNP] %s: the poison never landed -- UNINTERPRETABLE, not a null.\r\n",tag); continue; }
        int isPoison =ShEq3(cmc+0x16B0,poison);
        int isZero   =ShIsZero3(cmc+0x16B0);
        int isSent   =ShEq3(cmc+0x16B0,kShSentinel);
        int isOther  =ShEq3(cmc+0x16B0,k?kShBotPoison:kShPlrPoison);
        int velSent  =ShEq3(cmc+0xE8,kShSentinel);
        Markerf("[SNP] %s: payload isPoison=%d isZero=%d isSentinel=%d isOTHERobjectsPoison=%d | "
                "Velocity isSentinel=%d\r\n",tag,isPoison,isZero,isSent,isOther,velSent);
        if(isOther)
            Markerf("[SNP] %s: *** VOID -- this payload holds the OTHER object poison. The CMC "
                    "resolution is wrong. Nothing else in this run may be interpreted. ***\r\n",tag);
        else if(isSent)
            Markerf("[SNP] %s: ***** StartNewPhysics RAN. The payload holds the sentinel we put in "
                    "Velocity, so 0x055C244F executed and the payload IS a copy of Velocity. *****\r\n",tag);
        else if(isZero)
            Markerf("[SNP] %s: ***** StartNewPhysics RAN -- the poison was overwritten with zeros. "
                    "%s *****\r\n",tag,k?"(Expected for the write-free arm: Velocity rests at 0.)"
                                       :"(But our sentinel is GONE from the payload, so something "
                                        "zeroed Velocity first -- read the Velocity line.)");
        else if(isPoison)
            Markerf("[SNP] %s: ***** StartNewPhysics did NOT run in the sampled window. The poison "
                    "is untouched after 10 s of frames. *****\r\n",tag);
        else
            Markerf("[SNP] %s: UNMODELLED payload value -- report the raw hex, do not interpret.\r\n",tag);
    }
    // ---- RESTORE the one field that could matter. The payload is a scratch buffer with a single
    //      flag-gated reader; Velocity is not. RM_PLAY zeroes it on exit for the same reason.
    if(LooksLikePtr(g_shBotCmc)&&g_shSentinelOK&&SafeWritable((void*)(g_shBotCmc+0xE8),24)){
        double z[3]={0.0,0.0,0.0}; memcpy((void*)(g_shBotCmc+0xE8),z,24);
        Markerf("[SNP] restore: BOT Velocity -> (0,0,0)  readback %s\r\n",
                ShIsZero3(g_shBotCmc+0xE8)?"OK":"*** FAILED ***");
    }
    Markerf("[SNP] ARM H done (botCmc=0x%llX plrCmc=0x%llX botPoison=%d plrPoison=%d sentinel=%d "
            "botFlag0=%d plrFlag0=%d)\r\n",(unsigned long long)g_shBotCmc,(unsigned long long)g_shPlrCmc,
            g_shBotPoisoned,g_shPlrPoisoned,g_shSentinelOK,g_shBotFlag0,g_shPlrFlag0);
}
#endif  // KBSPSARMS & 0x200
