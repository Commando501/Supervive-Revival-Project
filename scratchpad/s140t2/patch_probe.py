import io, sys
Q = chr(34)      # "
BS = chr(92)     # \
NL = "\n"
p = 'tools/re/cmc_earlyout_readout.py'
s = open(p, encoding='utf-8', newline='').read()

# ---------- 1) new offsets ----------
a = '    "ctl.randomdir":  0x658,'
assert s.count(a) == 1
s = s.replace(a, a + NL + NL.join([
'    # ---- S140 Tier 2 additions ----',
'    "cmc.world":      0xC0,     # UActorComponent::WorldPrivate -- engine PerformMovement exit 2',
'                                #   input, NEVER read live by anyone before S140 (Tier 1 1.6)',
'    "cmc.jumpapex":   0x3DC,    # NumJumpApexAttempts',
'    "cmc.maxsimstep": 0x3E0,    # MaxSimulationTimeStep',
'    "cmc.maxsimiter": 0x3E4,    # MaxSimulationIterations -- engine StartNewPhysics 0x036009B5',
'                                #   cmp r8d,[rcx+0x3e4] / jge is a FOURTH early-out, in no S139 doc',
]), 1)

# ---------- 2) sentinel vocabulary + raw hex helper ----------
a2 = 'def fmt(v):'
assert s.count(a2) == 1
s = s.replace(a2, NL.join([
'# ---- S140 Tier 2: the payload-poison / sentinel vocabulary. These MUST match tutorial_launch.cpp',
'#      ARM H (kShBotPoison / kShPlrPoison / kShSentinel) or the recogniser is silently useless.',
'SENT_BOT_POISON = (-9876.5, -8765.25, -7654.125)',
'SENT_PLR_POISON = (-1234.5, -2345.25, -3456.125)',
'SENT_VALUE      = (0.0009765625, 0.0, 0.0)',
'ZERO3           = (0.0, 0.0, 0.0)',
'',
'',
'def hex24(a):',
'    b = rpm(a, 24)',
'    if not b:',
'        return "<unreadable>"',
'    return "|".join(b[i:i + 8].hex().upper() for i in range(0, 24, 8))',
'',
'',
a2]), 1)

# ---------- 3) read the new fields ----------
a3 = '    r["MovementMode@0x231"] = u8(cmc + O["cmc.mode"])'
assert s.count(a3) == 1
s = s.replace(a3, NL.join([
'    # ---- S140 Tier 2: RAW FIRST. A formatted double print hides a signed zero, and that exact',
'    #      defect cost S139 flight 3 its finding for an hour. Record bytes; derive afterwards.',
'    r["S140.payload@0x16B0 RAW"] = hex24(cmc + O["cmc.velsnap"])',
'    r["S140.Velocity@0xE8 RAW"] = hex24(cmc + O["cmc.velocity"])',
'    r["S140.WorldPrivate@0xC0"] = p(cmc + O["cmc.world"])',
'    r["S140.NumJumpApexAttempts@0x3DC"] = u32(cmc + O["cmc.jumpapex"])',
'    r["S140.MaxSimulationTimeStep@0x3E0"] = f32(cmc + O["cmc.maxsimstep"])',
'    r["S140.MaxSimulationIterations@0x3E4"] = u32(cmc + O["cmc.maxsimiter"])',
'    r["S140.vptr"] = p(cmc)',
'    r["S140.vptr is ULokiCMC"] = (r["S140.vptr"] == BASE + 0x088F8570)',
'    r["S140.vptr is engine UCMC"] = (r["S140.vptr"] == BASE + 0x07FBED58)',
    a3]), 1)

# ---------- 4) replace the RETRACTED rank-1 verdict block ----------
i = s.find('    print("### RANK-1 VERDICT (the bisector) ###")')
j = s.find('    print()' + NL + '    print("  ⚠ Acceleration == 0 is UNINTERPRETABLE')
assert i > 0 and j > i, (i, j)

L = []
def P(txt):
    L.append('    print(' + Q + txt + Q + ')')

P('### RANK-1 -- RETRACTED (S140 Tier 1). THE LATCH IS NOT AN INSTRUMENT. ###')
P('  CMC+0x16C8 is NOT a sticky latch. It is a per-frame TOptional<FVector> validity flag: SET by')
P('  ULokiCMC::StartNewPhysics at 0x055C2469 and CLEARED later in the SAME engine PerformMovement')
P('  call by ULokiCMC vtable disp 0xA50 (0x0530ABF0), on a path the StartNewPhysics call site')
P('  DOMINATES. An off-thread reader sees 0 whether the step runs every frame or never runs at')
P('  all. Named from its own consumer GetRecentVelocity (.data 0x09BC9AD0 -> impl 0x0530AC10).')
P('  See docs/s140-tier1-cfg.md 4.2-4.7.')
P('  ==> latch == 0 proves NOTHING. The S139 verdict this probe used to print here rested on it')
P('      and is WITHDRAWN. Raw values only:')
L.append('    print("      bot latch=%s   player latch=%s   (0 is expected in EVERY world)"')
L.append('          % (fmt(A.get("R1.latch@0x16C8")), fmt(B.get("R1.latch@0x16C8"))))')
L.append('    print()')
P('### S140 TIER 2 -- THE PAYLOAD RECOGNISER (the durable receipt) ###')
P('  The PAYLOAD at CMC+0x16B0 IS durable: disp 0xA50 clears only the flag byte, and the only')
P('  CMC-side writer of the payload is 0x055C244F inside StartNewPhysics. ARM H')
P('  (build.ps1 -Variant gasattr-sentinel) POISONS it first, so never-written and written-with-')
P('  zeros are DIFFERENT BYTES -- the degeneracy docs/s140-tier1-cfg.md 7 warns about.')
L.append('    for side, r, own, other in (("BOT", A, SENT_BOT_POISON, SENT_PLR_POISON),')
L.append('                                ("PLAYER", B, SENT_PLR_POISON, SENT_BOT_POISON)):')
L.append('        pay = r.get("R1.velsnap@0x16B0")')
L.append('        vel = r.get("Velocity@0xE8 (CONTAMINATED on player)")')
L.append('        if pay is None:')
L.append('            print("  %-7s payload UNREADABLE -- no result." % side)')
L.append('            continue')
L.append('        if pay == other:')
L.append('            v = "*** VOID: holds the OTHER object poison -> the CMC resolution is WRONG ***"')
L.append('        elif pay == SENT_VALUE:')
L.append('            v = "***** StartNewPhysics RAN -- payload holds the SENTINEL from Velocity *****"')
L.append('        elif pay == own:')
L.append('            v = "***** StartNewPhysics did NOT run since the poison was written *****"')
L.append('        elif pay == ZERO3:')
L.append('            v = ("payload is EXACT ZERO. If ARM H poisoned this object -> StartNewPhysics RAN"')
L.append('                 " and snapshotted a zero Velocity. If ARM H did NOT run -> UNINTERPRETABLE:"')
L.append('                 " a never-written buffer is also zero. CHECK THE MARKER FOR [SNP] FIRST.")')
L.append('        else:')
L.append('            v = "UNMODELLED value -- report the raw hex, do not interpret."')
L.append('        print("  %-7s payload  = %-28s RAW %s" % (side, fmt(pay), r.get("S140.payload@0x16B0 RAW")))')
L.append('        print("  %-7s Velocity = %-28s RAW %s" % (side, fmt(vel), r.get("S140.Velocity@0xE8 RAW")))')
L.append('        print("  %-7s -> %s" % (side, v))')
L.append('    print()')
P('### S140 TIER 2 -- THE THREE FREE READS (Tier 1 7, ranks 2/3/4; never taken live) ###')
L.append('    for side, r in (("BOT", A), ("PLAYER", B)):')
L.append('        wp = r.get("S140.WorldPrivate@0xC0")')
L.append('        msi = r.get("S140.MaxSimulationIterations@0x3E4")')
L.append('        print("  %-7s WorldPrivate@0xC0 = %-20s -> %s" % (side, fmt(wp),')
L.append('              "non-null; engine PerformMovement exit 2 input is satisfied"')
L.append('              if (wp and wp > 0x10000) else "*** NULL -- EXIT 2 WOULD BAIL ***"))')
L.append('        print("  %-7s MaxSimulationIterations@0x3E4 = %-6s -> %s" % (side, fmt(msi),')
L.append('              "> 0; the 4th engine-StartNewPhysics early-out 0x036009B5 does NOT bail"')
L.append('              if (isinstance(msi, int) and 0 < msi < 1000)')
L.append('              else "*** <=0 or implausible -- READ THE RAW VALUE ***"))')
L.append('        print("  %-7s MaxSimulationTimeStep@0x3E0 = %-10s NumJumpApexAttempts@0x3DC = %s"')
L.append('              % (side, fmt(r.get("S140.MaxSimulationTimeStep@0x3E0")),')
L.append('                 fmt(r.get("S140.NumJumpApexAttempts@0x3DC"))))')
L.append('        print("  %-7s vptr = %-20s isULokiCMC=%s isEngineUCMC=%s"')
L.append('              % (side, fmt(r.get("S140.vptr")), fmt(r.get("S140.vptr is ULokiCMC")),')
L.append('                 fmt(r.get("S140.vptr is engine UCMC"))))')
L.append('        if not r.get("S140.vptr is ULokiCMC"):')
L.append('            print("  %-7s !! NOT the ULokiCMC vtable. If it is the ENGINE UCMC then disp 0x720" % side)')
L.append('            print("  %-7s    is 0x03600990 and NOTHING touches +0x16C8/+0x16B0 -- TEST VOID." % side)')

new = NL.join(L) + NL
s = s[:i] + new + s[j:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('probe patched')
