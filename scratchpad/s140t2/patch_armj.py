import sys
p = 'tools/sigbypass-mod/tutorial_launch.cpp'
s = open(p, encoding='utf-8', newline='').read()
CRLF = chr(13) + chr(10)
BS = chr(92)
RN = BS + 'r' + BS + 'n'


def rep(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, (label, n)
    s = s.replace(old, new, 1)
    print('ok:', label)


# ---- 1. parameterise the sentinel, and give the player its own ----
rep('static const double kShSentinel [3]={ 0.0009765625, 0.0,          0.0};',
    CRLF.join([
'// ARM J (S140 Tier 2 follow-up) turns the sentinel MAGNITUDE into a knob. ARM H deliberately used',
'// 2^-10 = 0.0009765625 uu/s so it could not perturb the system under test. ARM J deliberately uses',
'// a LARGE value, because the question changed: an adversarial verifier showed a small non-zero',
'// Velocity can CONVERT A NO-WRITE INTO A WRITE (below-tolerance arms SKIP the store), so what ARM H',
'// measured about Velocity may be an artifact of ARM H\'s own sentinel. ARM J perturbs BY DESIGN.',
'#ifndef KSHSENTX',
'#define KSHSENTX 0.0009765625',
'#endif',
'#ifndef KSHPLRX',
'#define KSHPLRX  0.0',
'#endif',
'#ifndef KSHPLRY',
'#define KSHPLRY  0.0',
'#endif',
'static const double kShSentinel [3]={ (double)(KSHSENTX), 0.0,               0.0};',
'static const double kShPlrVel   [3]={ 0.0,                (double)(KSHPLRY), 0.0};']),
    '1. sentinel knobs')

# ---- 2. ARM J: also write the PLAYER velocity, and record start locations ----
rep(CRLF.join([
'    Marker("[SNP] ---- AFTER THE WRITES (raw) ----' + RN + '");',
'    ShDump("BOT-armed",g_shBotCmc); ShDump("PLR-armed",g_shPlrCmc);']),
    CRLF.join([
'#if (KBSPSARMS & 0x800)',
'    // ---- ARM J: the FIXED-POINT TEST. Give the PLAYER its own large velocity, on a DIFFERENT',
'    //      AXIS, so the two objects stay distinguishable and cross-contamination is visible.',
'    //   The player is UNTREATED by ARM G (no AttributeSetStorage), so this is a two-arm design:',
'    //     both move   -> the mover works regardless of GAS; the wall is purely Acceleration->Velocity',
'    //     only bot    -> the GAS treatment matters downstream too',
'    //     neither     -> the MOVER itself is blocked, and Velocity is not the variable',
'    if(LooksLikePtr(g_shPlrCmc)&&SafeWritable((void*)(g_shPlrCmc+0xE8),24)){',
'        memcpy((void*)(g_shPlrCmc+0xE8),kShPlrVel,24);',
'        Markerf("[SNP] ARM J: PLAYER Velocity = (0, %g, 0) -> readback %s' + RN + '",(double)(KSHPLRY),',
'                ShEq3(g_shPlrCmc+0xE8,kShPlrVel)?"OK":"*** FAILED ***");',
'    }',
'#endif',
'    Marker("[SNP] ---- AFTER THE WRITES (raw) ----' + RN + '");',
'    ShDump("BOT-armed",g_shBotCmc); ShDump("PLR-armed",g_shPlrCmc);',
'    // Latch the start locations so the sampler can report DISTANCE TRAVELLED, which is the only',
'    // observable that matters if the velocity persists.',
'    for(int k=0;k<2;k++){',
'        uintptr_t pawn=k?g_shPlrPawn:g_shBotPawn; if(!LooksLikePtr(pawn))continue;',
'        uint32_t rc=PropOffsetSuper(ClassOf(pawn),"RootComponent");',
'        uintptr_t root=(rc!=0xFFFFFFFF&&SafeReadable((void*)(pawn+rc),8))?*(uintptr_t*)(pawn+rc):0;',
'        if(LooksLikePtr(root)&&SafeReadable((void*)(root+0x158),24)) memcpy(g_shLoc0[k],(void*)(root+0x158),24);',
'    }']),
    '2. ARM J player write + start locations')

# ---- 3. the start-location globals ----
rep('static int  g_shBotFlag0=-1,    g_shPlrFlag0=-1;',
    CRLF.join([
'static int  g_shBotFlag0=-1,    g_shPlrFlag0=-1;',
'static double g_shLoc0[2][3]={{0,0,0},{0,0,0}};']),
    '3. start-location globals')

# ---- 4. sampler reports distance travelled ----
rep(CRLF.join([
'            if(LooksLikePtr(root)&&SafeReadable((void*)(root+0x158),24)){',
'                const double* L=(const double*)(root+0x158);',
'                Markerf("[SNP] %-14s loc (%.3f, %.3f, %.3f)' + RN + '",k?"PLR":"BOT",L[0],L[1],L[2]); }']),
    CRLF.join([
'            if(LooksLikePtr(root)&&SafeReadable((void*)(root+0x158),24)){',
'                const double* L=(const double*)(root+0x158);',
'                double dx=L[0]-g_shLoc0[k][0],dy=L[1]-g_shLoc0[k][1],dz=L[2]-g_shLoc0[k][2];',
'                double d=(dx*dx+dy*dy+dz*dz); d=(d>0.0)?__builtin_sqrt(d):0.0;',
'                Markerf("[SNP] %-14s loc (%.3f, %.3f, %.3f)  moved %.3f uu' + RN + '",k?"PLR":"BOT",',
'                        L[0],L[1],L[2],d); }']),
    '4. distance travelled')

open(p, 'w', encoding='utf-8', newline='').write(s)
print('tutorial_launch.cpp patched')

# ---- 5. build variant ----
p2 = 'tools/sigbypass-mod/build.ps1'
b = open(p2, encoding='utf-8', newline='').read()
a = ("        'sentinel-burst'      = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=" + BS + '"' + BS + '"' +
     "','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x7A0')")
assert b.count(a) == 1
new = a + CRLF + CRLF.join([
"        # ARM J -- THE FIXED-POINT TEST (S140 Tier 2 follow-up). ARM H's 2^-10 sentinel was chosen",
"        #   to be INERT; a verifier then showed a small non-zero Velocity can CONVERT A NO-WRITE",
"        #   INTO A WRITE, so what ARM H measured about Velocity may be its own artifact. ARM J",
"        #   writes a LARGE velocity ONCE (600 uu/s), on DIFFERENT AXES for bot and player, and",
"        #   watches whether it persists and whether the pawn TRANSLATES. It PERTURBS BY DESIGN --",
"        #   that is the point, and it is the opposite of ARM H. bit9 (H) + bit11 (J), NO bit10.",
"        'sentinel-big'        = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=" + BS + '"' + BS + '"' +
"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0xBA0','-DKSHSENTX=600.0','-DKSHPLRY=600.0')",
])
b = b.replace(a, new, 1)
open(p2, 'w', encoding='utf-8', newline='').write(b)
print('build.ps1 patched')
