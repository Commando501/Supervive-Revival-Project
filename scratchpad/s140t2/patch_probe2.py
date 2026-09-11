NL = "\n"
p = 'tools/re/cmc_earlyout_readout.py'
s = open(p, encoding='utf-8', newline='').read()


def rep(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, (label, n)
    s = s.replace(old, new, 1)
    print('ok:', label)


# ---- P9: liveness. A dead-but-handle-openable PID, a wrong BASE and a decode defect all print
#          the same string today.
rep('h = k32.OpenProcess(0x1F0FFF, False, PID)',
    NL.join([
'h = k32.OpenProcess(0x1F0FFF, False, PID)',
'',
'',
'def _liveness(handle):',
'    """P9 (S140 T2 adjudication): OpenProcess SUCCEEDS on a dead process whose handle is still',
'    open, so every read then returns None and the probe prints a table of Nones that reads exactly',
'    like a game fact. Check GetExitCodeProcess: STILL_ACTIVE == 259. Name FK-32 on 0x0000DEAD."""',
'    code = wintypes.DWORD(0)',
'    if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):',
'        return "UNKNOWN (GetExitCodeProcess failed)"',
'    if code.value == 259:',
'        return None',
'    if code.value == 0x0000DEAD:',
'        return ("DEAD, exit 0x0000DEAD == FK-32, the protector NtTerminateProcess kill. "',
'                "No artifact is produced by that class.")',
'    return "DEAD, exit code %d (0x%08X)" % (code.value, code.value)',
]),
    'P9 liveness helper')

rep('def main():',
    NL.join([
'def main():',
'    dead = _liveness(h)',
'    if dead:',
'        print("!! PROCESS IS NOT RUNNING -- %s" % dead)',
'        print("!! RUN IS VOID. Every read below would be None and would read like a game fact.")',
'        return',
'    mz = rpm(BASE, 2)',
'    if mz != b"MZ":',
'        print("!! NO MZ AT BASE=0x%X (read %r) -- the BASE argument is wrong, or the module moved."',
'              % (BASE, mz))',
'        print("!! RUN IS VOID -- an image-relative check (the vptr test) cannot mean anything.")',
'        return',
]),
    'P9 gate in main')

# ---- P1: a missing player must NOT discard the bot result.
rep(NL.join([
'        print("!! NO PLAYER-CONTROLLED PAWN -- no two-sided control exists. RUN IS VOID.")',
'        return']),
    NL.join([
'        # P1 (S140 T2 adjudication): this used to `return`, DISCARDING THE ENTIRE BOT RESULT when',
'        # the player was not found. The player is a CONTROL, not a precondition -- losing it',
'        # weakens the reading, it does not void the treatment. Warn loudly and continue.',
'        print("!! NO PLAYER-CONTROLLED PAWN -- the two-sided control is MISSING and every")',
'        print("!! player column below is meaningless. The BOT reading still stands on its own")',
'        print("!! internal controls; say so explicitly in any write-up.")']),
    'P1 do not discard the bot result')

# ---- P3: the false EXIT-2 claim.
rep('''              if (wp and wp > 0x10000) else "*** NULL -- EXIT 2 WOULD BAIL ***"))''',
    NL.join([
'              if (wp and wp > 0x10000) else',
'              "UNDECIDED -- NOT a bail. A null WorldPrivate falls to a DIRECT call 0x035AFC40 "',
'              "which reads OwnerPrivate@+0xB8 and OuterPrivate@+0x28; exit 2 tests WorldPrivate "',
'              "OR that fallback. Read those two before concluding anything."))',
'        if not (wp and wp > 0x10000):',
'            print("  %-7s   OwnerPrivate@0xB8 = %s   OuterPrivate@0x28 = %s"',
'                  % (side, fmt(p(cmc + 0xB8)), fmt(p(cmc + 0x28))))']),
    'P3 the false EXIT 2 claim')

open(p, 'w', encoding='utf-8', newline='').write(s)
print('probe patched')
