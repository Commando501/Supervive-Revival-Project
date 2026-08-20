import csv, io, collections, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = os.path.join(ROOT, 'scratchpad', 's131', 'sweep_full.tsv')
DST = os.path.join(ROOT, 'scratchpad', 's131', 'lane4-record-sweep.md')
rows = list(csv.DictReader(open(SRC), delimiter='\t'))

DOC_EMPTY = {('ALokiDropPlane','AddPlayerToPlane'),('ALokiDropPlane','RemovePlayerFromPlane'),
 ('ALokiDropPlane','AuthStart'),('ALokiDropPlane','SetCanJump'),('ALokiDropPlane','OverridePlaneLocations'),
 ('ULokiRideableComponent','AuthAddPlayer'),('ULokiRideableComponent','AuthRemovePlayer'),
 ('ULokiRideableComponent','AuthSetCanJump'),('ULokiPlayerDropPlaneComponent','AuthSetCurrentRideable'),
 ('ULokiPlayerDropPlaneComponent','OnPlayerExitedDropPod'),('ALokiTeamState_TeamOnly','SetDropLeader')}
DOC_VT = {('ULokiPlayerDropPlaneComponent','ServerPassDropLeader'),
          ('ULokiPlayerDropPlaneComponent','ServerSetDropPodDestination')}
DOC_INL = {('ULokiPlayerDropPlaneComponent','AuthSetDropComplete'),('ULokiPlayerDropPlaneComponent','GetDropComplete'),
 ('ULokiPlayerDropPlaneComponent','GetDropPod'),('ULokiRideableComponent','CanExit'),
 ('ULokiPlayerDropPlaneComponent','BroadcastEventRouterReady')}
VT_FIX = {('ULokiPlayerDropPlaneComponent','ServerPassDropLeader'):
            'CORRECTED via vtable `0x8a22520+0x4c8` -> `0xf7ec20` **EMPTY**',
          ('ULokiPlayerDropPlaneComponent','ServerSetDropPodDestination'):
            'CORRECTED via vtable `0x8a22520+0x4e0` -> `0xf7ec20` **EMPTY**',
          ('ULokiPlayerDropPlaneComponent','ServerLaunchDropPod'):
            'CORRECTED via vtable `0x8a22520+0x4c0` -> `0x56face0` **REAL**'}

def old(r):
    k = (r['class'], r['func'])
    if k in DOC_EMPTY: return 'EMPTY-STUB [M, doc-named]'
    if k in DOC_VT: return 'EMPTY-VIA-VTABLE [M, doc-named]'
    if k in DOC_INL: return 'REAL-INLINED / CONST-BODY [M, doc-named]'
    if r['verdict'] == 'NO-RECORD': return 'BlueprintImplementableEvent [I-recon]'
    if r['thunk_pg'] == 'DARK-ALL3': return '**COVBLOCKED-THUNK** [I-recon]'
    if r['impl_pg'] == 'DARK-ALL3': return '**COVBLOCKED-IMPL** [I-recon]'
    return 'REAL [I-recon]'

def ev(r):
    if r['verdict'] == 'NO-RECORD':
        return 'no `.data` record; UHT flags carry no `Native` bit'
    if r['note'] and r['note'].startswith('FOLD'):
        return r['note'] + ' ; thunk `%s`' % r['thunk']
    if r['bytes12']:
        return 'bytes12 `%s` ; thunk `%s`' % (r['bytes12'], r['thunk'])
    return 'impl page dark in all 3 images ; thunk `%s`' % r['thunk']

setC = [r for r in rows if r['in_setC'] == 'C']
cnt = collections.Counter(r['verdict'] for r in setC)

L = []
A = L.append
A('# S131 LANE 4 - the `.data` record sweep over FK-22 section 2.5\n')
A('Read-only, offline. **Zero launches, zero injections, zero `.text` writes.**')
A('Tools, re-runnable from the repo root: `scratchpad/s131/tools/rectab.py`, `scratchpad/s131/tools/lane4_sweep.py`,')
A('`scratchpad/s131/tools/gen_md.py`. Images: `dumps/s129-poolgate`, `dumps/merged2.dump.exe`, `dumps/tutorial-hero`.')
A('Raw output: `scratchpad/s131/sweep_full.tsv` (112 keys x 11 columns).\n')

A('## 0. THE CONTROL, FIRST - 7/7 PASS, non-degenerate, discriminating in both directions\n')
A('| control | expected impl | source of expectation | record impl | result |')
A('|---|---|---|---|---|')
A('| `ALokiGameMode::SpawnPlayer` | `0xf7eb50` | FK-1, disassembly | `0xf7eb50` | PASS / EMPTY |')
A('| `ALokiPlayerState::AuthSetSpawnTeamLeader` | `0xf7ec20` | FK-1 | `0xf7ec20` | PASS / EMPTY |')
A('| `ALokiTeamState_TeamOnly::SetDropLeader` | `0xf7ec20` | FK-1 | `0xf7ec20` | PASS / EMPTY |')
A('| `ALokiDropPlane::OverridePlaneLocations` | `0xf7ec20` | FK-1 | `0xf7ec20` | PASS / EMPTY |')
A('| `ALokiRoundGameMode::GoToPhase` | `0x5601020` | S124, disassembly | `0x5601020` | PASS / REAL |')
A('| `ALokiGameState::BP_AuthSetCurrentPhase` | `0x567a160` | S124 | `0x567a160` | PASS / REAL |')
A('| `ALokiRoundGameMode::OnNewPhase` | `0x330c56c` | S124 | `0x330c56c` | PASS / VTABLE-FWD |\n')
A('The handoff warned that "AS functions have no record" is a degenerate control. This one is not:')
A('all seven are C++ functions whose REAL/EMPTY status was established independently by disassembly,')
A('four are EMPTY and three are REAL, and the instrument separates them correctly. [M]\n')
A('**Seven further agreements, none designed as controls, all [M]** - the sweep independently reproduces')
A('impl addresses and bytes that FK-22 and CLAUDE.md derived by disassembly:')
A('`ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` = `0x55cbb60`;')
A('`ALokiServerAnalyticsManager::AddTeamDropEvent` = `0x557eae0`, prologue `48 8b c4 48 89 58 10` = `mov rax,rsp; mov [rax+0x10],rbx`;')
A('`AuthSetDropComplete` = `0x2e09510`, bytes `c6 81 d0 00 00 00 01 c3` = `mov byte [rcx+0xd0],1; ret`;')
A('`GetDropPod` = `0x3078470` = `mov rax,[rcx+0x110]; ret`;')
A('`CanExit` = `0x525c240` = `movzx eax,byte [rcx+0x118]`;')
A('`BroadcastEventRouterReady` = `0x56dd340` = `test rdx,rdx; jne ...; ret`;')
A('`ALokiDropPodBase::SetPilotPlayerState` = `0x55e59e0`.\n')
A('**An eighth control on the vtable route [M], reproduced in TWO images (`s129`, `tuthero`):**')
A('`ULokiPlayerDropPlaneComponent` vtable `0x8a22520` - `+0x4c0 = 0x56face0` (REAL),')
A('`+0x4c8 = 0xf7ec20` (EMPTY), `+0x4d0 = 0x56f26a0`, `+0x4d8 = 0x56df250`,')
A('`+0x4e0 = 0xf7ec20` (EMPTY), `+0x4e8 = 0x56fae90` - byte-for-byte what section 2.5 records.\n')

A('## 1. Record-table layout, measured\n')
A('[M] 9 qwords, stride **0x48**; record start = `name_ptr - 8`.')
A('`+0x08` name_ptr (`.rdata char*`), `+0x10` exec thunk (`.text`), `+0x18` impl (`.text`).')
A('`+0x00` and `+0x20` are a constant dword pair; `+0x28..+0x40` are mutable runtime fields.')
A('[M] **16,277 records in 1,551 contiguous runs** over `.data` (`0x99c7000..0xa0b7000`), unit: records.')
A('Runs are **per-UClass and alphabetically sorted within a class** - that is what makes class attribution')
A('possible. Attribution is by name-set overlap against the UHT oracle `tools/re/out/uht_funcflags_tuthero.csv`;')
A('e.g. the `AddPlayerToPlane` run scores 21/21 against `ALokiDropPlane` and 1/25 against its nearest rival.')
A('**15,720 of 16,277 records attributed** to a unique class.\n')
A('[M] **Fold control over the whole table:** three of the four known folds are the top-1, top-2 and top-4')
A('impl addresses by multiplicity - `0xf7ec20` x371, `0xf7eb60` x76, `0xf7eb50` x40, `0xb9e1f0` x15.')
A('The other high-multiplicity impls are **not** folds: they are `48 8b 01 ff a0 <disp>` =')
A('`mov rax,[rcx]; jmp [rax+disp]` vtable forwarders (largest `0x3234454` x48). Two further *near*-folds')
A('exist and are worth knowing about (`0xfc57d0` x15 = zero a 16-byte out-param; `0xfc6cf0` x13 =')
A('`xorps xmm0,xmm0; ret`); [M] **no key in this sweep uses either**, so no verdict here depends on them.\n')

A('## 2. Key-set reconstruction - HONEST STATUS\n')
A('[M] **The per-key section 2.5 table is not on disk.** A repo-wide grep for `COVBLOCKED` returns')
A('**exactly one file** (unit: files) - `docs/fk22-dropphase-reachability.md` itself. The doc states the')
A('count (100) and the category split, and names about 25 keys in prose; it never enumerates the 100 and')
A('it never lists the "8 drop classes". **The 100 keys had to be reconstructed.**\n')
A('[M] **Three different 8-class sets sum to exactly 100** under the UHT oracle, so the reconstruction is')
A('under-determined. I adopt **set C** and report the superset beside it:\n')
A('```')
A('set C (adopted, 100 keys):')
A('  ALokiDropPlane 25 | ULokiPlayerDropPlaneComponent 34 | ULokiRideableComponent 18 |')
A('  ALokiTeamState_TeamOnly 7 | ALokiDropPodBase 6 | ULokiGameModeDropPlaneComponent 4 |')
A('  ULokiDropPhaseLibrary 4 | ULokiDropPhaseDebuggingTool 2')
A('the two rejected alternatives swap ULokiDropOnDeathComponent (4) in for one of the last three')
A('```\n')
A('[M] **Set C is corroborated by a signal that was not used to select it:** it contains exactly **14**')
A('non-`Native` keys, and section 2.5 independently reports **BlueprintImplementableEvent = 14**. The')
A('cross-tab over set C is 86 `Native`/HAS-RECORD vs 14 non-`Native`/NO-RECORD with **zero** off-diagonal')
A('cells. Over the 112-key superset there is exactly **one** exception, `ULokiRideableInterface::GetRidePosition`')
A('- `Native` but no record, because an interface\'s native impl is registered on the implementing class')
A('(`ULokiRideableComponent::GetRidePosition` does have one, `0x55dab50`). [I]\n')

A('## 3. New verdict counts, set C (100 keys)\n')
A('| verdict | n |')
A('|---|---|')
for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
    A('| `%s` | %d |' % (k, v))
A('')
A('**Reconciliation against section 2.5\'s split:**\n')
A('```')
A('doc BPIE 14             -> NO-RECORD 14                                  [exact]')
A('doc EMPTY-STUB 11       -> EMPTY 11, same keys                           [exact]')
A('doc EMPTY-VIA-VTABLE 2  -> REAL/RPC-SEND-STUB 2 (blind spot; vtable read corrects to EMPTY)')
A('doc COVBLOCKED-THUNK 11 -> 9 REAL + 1 EMPTY + 1 IMPL-PAGE-DARK           [10 of 11 RESOLVED]')
A('doc COVBLOCKED-IMPL 5   -> 3 IMPL-PAGE-DARK + 2 unaccounted               [residual]')
A('doc REAL 51 + INLINED 4 + CONST-BODY 2 = 57 -> REAL 57')
A('---------------------------------------------------------------------------')
A('mine: REAL 63 + REAL/RPC-SEND-STUB 7 + EMPTY 12 + IMPL-PAGE-DARK 4 + NO-RECORD 14 = 100')
A('```\n')
A('[I] **Residual: 2 keys.** The arithmetic requires 2 of the doc\'s 5 COVBLOCKED-IMPL to now read REAL and')
A('I cannot exhibit them. It is **not** a coverage effect: [M] no set-C key has an impl page dark in')
A('`merged2`+`tuthero` but lit in `s129`, so my 3-image coverage is not richer than the doc\'s 18-image union.')
A('The likely cause is that set C differs from the doc\'s key set by about 2 keys. **Do not read the')
A('reconciliation as proof the two sets are identical.**\n')

A('## 4. THE HEADLINE - the 16 coverage-blocked keys\n')
A('[M] **All 11 keys whose exec-thunk page is dark have their impl ADDRESS read straight out of `.data`,')
A('and 10 of the 11 get a definite REAL/EMPTY verdict.** The count 11 matches section 2.5\'s')
A('COVBLOCKED-THUNK = 11 exactly. Page `0x5456000` (`ULokiRideableComponent`, 7 thunks) is confirmed dark')
A('in all three images - the page-boundary finding stands - and the sweep reads past it without needing it:\n')
A('| key | thunk | impl | NEW verdict |')
A('|---|---|---|---|')
for r in rows:
    if r['in_setC'] == 'C' and r['thunk_pg'] == 'DARK-ALL3':
        A('| `%s::%s` | `%s` | `%s` | **%s** |' % (r['class'], r['func'], r['thunk'], r['impl'], r['verdict']))
A('')
A('**The two results that matter for FK-22 section 3:**')
A('- `ULokiRideableComponent::AuthPlayerEnterWorldNew` is **EMPTY** (`0xf7ec20` = `ret 0`) - a NEW empty')
A('  stub, raising the drop-class empty count from the doc\'s 13 to **14**.')
A('- `AuthPlayerEnterWorld` `0x55cce70`, `AuthPlayerEnterWorldAttachedToRidable` `0x55cd510`,')
A('  `AuthPlayerPreSpawnOnAddToPlane` `0x55cd800` and `AuthPlayerDetachPlayerFromRidable` `0x55cccb0` are')
A('  **REAL** - large bodies with security cookies. Disassembled to confirm: `0x55cce70` opens')
A('  `test rdx,rdx / je / push rbp / lea rbp,[rsp-0x170] / sub rsp,0x270`. This **confirms CLAUDE.md\'s S130')
A('  note by a fully independent route** and **retires section 2.5\'s "not-looked-at"** on this family:')
A('  a C++ route to put a player on a rideable does exist as code; what S130 measured is that it always fails.\n')
A('[M] **4 keys remain unresolved** (`IMPL-PAGE-DARK`) - `ULokiPlayerDropPlaneComponent::FindValidDropLocationInRadius`')
A('`0x5605b90`, `::SelectDropPodDestination` `0x56fa590`, `::TryLaunchDropPod` `0x56ff1d0`, and')
A('`ALokiTeamState_TeamOnly::GetDropLeader` `0x3259330`. For these the impl **address** is now known and is')
A('**not** any fold, but the body is unreadable in these images: COVERAGE-BLOCKED, not ABSENT.\n')

A('## 5. The instrument\'s own blind spot, stated [M]\n')
A('**7 of the 112 keys carry `Net`**: `ServerLaunchDropPod`, `ServerPassDropLeader`, `ServerSetDropPodDestination`,')
A('`MulticastOnDropPodLaunched`, `MulticastOnPlayerEntered`, `MulticastOnPlayerEnteredWorld`, `MulticastOnPlayerExited`.')
A('For an RPC the record\'s impl field is the **UHT-generated send stub** - all four `ULokiPlayerDropPlaneComponent`')
A('ones cluster at `0x542b2b0..0x542b600`, i.e. one translation unit - **not** the `_Implementation`. The record')
A('therefore reads REAL where the `_Implementation` is EMPTY. Section 2.5\'s vtable route is the correct one and')
A('I reproduced it (`+0x4c8` and `+0x4e0` are `0xf7ec20`). **Never grade a `Net` key from this table alone.**')
A('The three `Multicast*` keys on `ULokiRideableComponent` are UNRESOLVED by both routes here (that class\'s')
A('vtable was not located) - uninterpretable, not REAL.\n')

for tag, title, filt in [('A', 'SET C - the candidate 100-key table', lambda r: r['in_setC'] == 'C'),
                         ('B', 'Keys outside set C - superset plus FK-1 / section 3 extras', lambda r: r['in_setC'] != 'C')]:
    sel = [r for r in rows if filt(r)]
    A('\n## 6%s. %s - %d keys\n' % (tag, title, len(sel)))
    A('| key | old verdict (FK-22 2.5) | NEW verdict | impl | evidence |')
    A('|---|---|---|---|---|')
    for r in sorted(sel, key=lambda r: (r['class'], r['func'])):
        k = (r['class'], r['func'])
        nv = '**' + r['verdict'] + '**'
        if k in VT_FIX: nv += ' -- ' + VT_FIX[k]
        A('| `%s::%s` | %s | %s | `%s` | %s |' % (r['class'], r['func'], old(r), nv, r['impl'], ev(r)))

io.open(DST, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('written', DST, len(rows), 'rows')
