export const meta = {
  name: 's140-tier1-cfg',
  description: 'S140 Tier 1: sound CFG analysis of the physics-step wall (offline, no launches)',
  phases: [
    { title: 'Analyze', detail: 'six independent offline RE lanes' },
    { title: 'Refute', detail: 'adversarial verifier per lane' },
    { title: 'Synthesize', detail: 'adjudicate and write the settled doc' },
  ],
}

const ROOT = 'G:/git/Supervive Revival Project'

const PRE = [
  'You are an offline reverse-engineering lane in the SUPERVIVE revival project at ' + ROOT + '.',
  '',
  'STEP 1: read scratchpad/s140/BRIEF.md IN FULL. It is the shared brief and it governs.',
  'STEP 2: read the S139 block of CLAUDE.md (search for S139 2026-08-23) for context.',
  'STEP 3: read your own task file, named below, and execute it.',
  '',
  'HARD RULES:',
  '- OFFLINE ONLY. Do NOT launch the game, do NOT inject, do NOT stage a world, do NOT run any',
  '  command that touches a live process. Static analysis of dumps/merged13.dump.exe plus reading',
  '  repo files ONLY.',
  '- Grade EVERY claim [M] / [I] / [S] and state the positive control you ran and what it returned.',
  '  A finding with no control is not a finding. An [I] stated as [M] is the costliest error here.',
  '- Recompute every RVA with a machine. Print raw samples, not just verdicts.',
  '- If you cannot answer offline, SAY SO and say precisely what live read would answer it. An honest',
  '  not-established-here-are-the-survivors is the correct output when that is the truth.',
  '',
  'You have python 3.13 and capstone 5.0.7. Shared instruments exist at',
  'scratchpad/s140/tools/peimg.py and scratchpad/s140/tools/cfg.py (both self-tested).',
  'Write scratch under scratchpad/s140/.',
  '',
].join('\n')

const POST = [
  '',
  '',
  'DELIVERABLE: write your full findings to the output file named below, as markdown.',
  'Then RETURN a compact summary (at most 2500 words) containing every load-bearing claim with its',
  'grade, every address you determined, your control results, and anything you could NOT establish.',
  'Your returned text IS the data another agent will adjudicate - do not write it as a message to a',
  'human.',
].join('\n')

const LANES = [
  { key: 'L1-cfg-exits',      task: 'scratchpad/s140/lanes/PROMPT-L1.md', out: 'scratchpad/s140/lanes/L1-cfg-exits.md' },
  { key: 'L2-exit-semantics', task: 'scratchpad/s140/lanes/PROMPT-L2.md', out: 'scratchpad/s140/lanes/L2-exit-semantics.md' },
  { key: 'L3-ladder-engine',  task: 'scratchpad/s140/lanes/PROMPT-L3.md', out: 'scratchpad/s140/lanes/L3-ladder-engine.md' },
  { key: 'L4-ladder-loki',    task: 'scratchpad/s140/lanes/PROMPT-L4.md', out: 'scratchpad/s140/lanes/L4-ladder-loki.md' },
  { key: 'L5-12b0-writers',   task: 'scratchpad/s140/lanes/PROMPT-L5.md', out: 'scratchpad/s140/lanes/L5-12b0-writers.md' },
  { key: 'L6-latch-validity', task: 'scratchpad/s140/lanes/PROMPT-L6.md', out: 'scratchpad/s140/lanes/L6-latch-validity.md' },
]

const VER = [
  'You are an ADVERSARIAL VERIFIER in the SUPERVIVE revival project at ' + ROOT + '. Your job is to',
  'REFUTE, not to agree. The dominant error mode in this project is an instrument blind spot recorded',
  'as a property of the game; adversarial verification has caught four wrong headlines in the last two',
  'sessions, including two by the session lead.',
  '',
  'FIRST read scratchpad/s140/BRIEF.md in full. Then read the lane task file and the lane output file',
  'named below.',
  '',
  'OFFLINE ONLY - no launches, no injection. python 3.13 and capstone 5.0.7 available.',
  'dumps/merged13.dump.exe, ImageBase 0x7FF608F40000, RVA == file offset.',
  '',
  'DO NOT take the lane report at face value. For every load-bearing claim:',
  '- RE-READ THE BYTES YOURSELF at the addresses it names, with your own code. Recompute every rel32',
  '  and every RVA with a machine.',
  '- Check the GRADE: is anything marked [M] that is really [I]?',
  '- Check the CONTROL: did they state a positive control, and does it actually discriminate? A',
  '  control that would pass even if the claim were false is not a control. A negative result with no',
  '  positive control is UNINTERPRETABLE, not a negative.',
  '- Check the specific traps in the brief: linear-sweep-vs-CFG, forward-only branch predicates,',
  '  byte-pattern disp scans, set-collapsing of signed zero, verdict lines contradicted by their own',
  '  samples, crossing a function boundary with an inference, UHT prefix-stripping, folded RVAs naming',
  '  nothing, floors reported as counts.',
  '- Check for OVER-GENERALISATION: a result true of one function or variant restated as general.',
  '- Look for what the lane did NOT do: an enumeration it called complete that is a floor, an',
  '  alternative explanation it did not consider, a question it declared settled without evidence.',
  '',
  'Report: CONFIRMED claims (with what you independently re-derived), DOWNGRADED claims (with the',
  'correct grade and why), REFUTED claims (with counter-evidence, addresses and bytes), and GAPS.',
  'Be specific and quote bytes. If the lane is largely sound, say so - a verifier that manufactures',
  'objections is as useless as one that rubber-stamps.',
  '',
].join('\n')

phase('Analyze')

const results = await pipeline(
  LANES,
  function (lane) {
    return agent(PRE + 'YOUR TASK FILE: ' + lane.task + '\nYOUR OUTPUT FILE: ' + lane.out + POST,
      { label: lane.key, phase: 'Analyze' })
  },
  function (report, lane) {
    const body = (typeof report === 'string') ? report : JSON.stringify(report)
    return agent(
      VER + 'LANE TASK FILE: ' + lane.task + '\nLANE OUTPUT FILE: ' + lane.out +
      '\n\nHere is the report the lane returned:\n---\n' + body + '\n---\n',
      { label: 'verify:' + lane.key, phase: 'Refute' }
    ).then(function (v) {
      return { key: lane.key, out: lane.out, report: body, verdict: v }
    })
  }
)

const good = results.filter(Boolean)
log('lanes complete: ' + good.length + ' of ' + LANES.length)

phase('Synthesize')

const bundle = good.map(function (r) {
  const vd = (typeof r.verdict === 'string') ? r.verdict : JSON.stringify(r.verdict)
  return '########## LANE ' + r.key + '  (file: ' + r.out + ')\n' +
    '=== LANE REPORT ===\n' + r.report + '\n\n=== ADVERSARIAL VERDICT ===\n' + vd + '\n'
}).join('\n\n')

const SYN = [
  'You are the SYNTHESIS AGENT for S140 Tier 1 in the SUPERVIVE revival project at ' + ROOT + '.',
  '',
  'Read scratchpad/s140/BRIEF.md in full first. You have six analysis lanes, each followed by an',
  'adversarial verifier. Your job is to ADJUDICATE - where lane and verifier disagree, go read the',
  'bytes yourself and decide. You have python 3.13 and capstone 5.0.7 and dumps/merged13.dump.exe',
  '(ImageBase 0x7FF608F40000, RVA == file offset). OFFLINE ONLY. The lane output files listed below',
  'are on disk and you may read them for detail.',
  '',
  bundle,
  '',
  'ADJUDICATE, then WRITE docs/s140-tier1-cfg.md with exactly these sections:',
  '',
  '1. A1 - the sound exit set. Diffed against the prior six (0x035E9F1F, 0x035E9F28, 0x035E9F97,',
  '   0x035E9FA4, 0x035E9FBD, 0x035EA25D). For each exit: address, condition, field plus offset plus',
  '   owning class, whether already measured live, and whether the measured object is provably the',
  '   same object. STATE PLAINLY whether the six survives. Include the dominance result and the',
  '   indirect-jump, noreturn and loop findings.',
  '',
  '2. A2 - the ranked progress-ladder table, for BOTH engine PerformMovement and',
  '   ULokiCMC PerformMovement, with per-field discriminating power (GOOD/WEAK/USELESS) and any',
  '   required baseline. Make it directly usable by a future live probe.',
  '',
  '3. A3 - the +0x12B0 writer set, each graded, and a precise statement of what an advancing value',
  '   does and does not prove.',
  '',
  '4. A4 - latch validity (the lane the session lead added): is latch==0 proves StartNewPhysics never',
  '   ran a SOUND inference? Include the vtable disp-0x720 re-derivation and its controls.',
  '',
  '5. What this means for the contradiction. Given A1, is the contradiction REAL, or was there a',
  '   seventh exit or an invalid instrument all along? If it survives, name the two or three best',
  '   remaining explanations, each with what would test it, ranked by cost. If it dissolves, say so',
  '   loudly and name what has to be re-graded.',
  '',
  '6. Corrections to CLAUDE.md and docs/s139-*.md - quote the stale text verbatim and give the',
  '   replacement. This project loses corrections when digests are not updated. Also flag any claim in',
  '   the brief itself, including the five pre-fan-out items the session lead verified, that turned',
  '   out wrong.',
  '',
  '7. Open / not established offline - what could not be answered, and the exact live read that would',
  '   answer each. Rank by value.',
  '',
  'RULES FOR THE WRITE-UP:',
  '- Grade every claim [M]/[I]/[S] with its control. Where lane and verifier disagreed, say who was',
  '  right and why - the disagreements are the most valuable content.',
  '- Do not launder an [I] into an [M]. Do not report a floor as a count.',
  '- Quote bytes for anything load-bearing.',
  '- If something is unanswerable offline, say so.',
  '- No overstatement: this is not a bot; the GAS port is a process-wide CDO poke and a diagnosis, not',
  '  a shipping fix.',
  '',
  'Then RETURN an executive summary of at most 1800 words: the headline finding, whether the six',
  'survived, whether the latch instrument is valid, whether the contradiction is real, the single best',
  'next move, and the list of corrections needed.',
].join('\n')

const synth = await agent(SYN, { label: 'synthesis', phase: 'Synthesize' })

return { synth: synth, lanes: good.map(function (r) { return { key: r.key, out: r.out } }) }
