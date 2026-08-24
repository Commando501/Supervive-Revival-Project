export const meta = {
  name: 's142-doc-repair',
  description: 'Propagate the S139-S141 movement arc into the docs that did not keep up',
  phases: [
    { title: 'Repair', detail: 'three lanes: S139 docs, ignorance map, repo sweep' },
    { title: 'Refute', detail: 'adversarial verifier per lane' },
  ],
}

const ROOT = 'G:/git/Supervive Revival Project'

const PRE = [
  'You are repairing project documentation in the SUPERVIVE revival project at ' + ROOT + '.',
  '',
  'STEP 1: read scratchpad/s142-docs/BRIEF.md IN FULL. It carries the CURRENT TRUTH and it governs.',
  'STEP 2: read your task file, named below, and execute it.',
  '',
  'HARD RULES:',
  '- OFFLINE. Do NOT launch the game, do NOT inject, do NOT touch a live process.',
  '- This is DOCUMENTATION REPAIR, not new RE. Cite the settled docs; do not re-derive them.',
  '- Stay strictly inside the files your task file says you own. Other lanes own other files and',
  '  edit them concurrently.',
  '- DO NOT REWRITE HISTORY. Dated records are preserved deliberately in this repo. Annotate with',
  '  banners and in-place retractions that KEEP the original text visible.',
  '- Grade every claim [M] / [I] / [S]. Never launder an [I] into an [M].',
  '- Rule 9: grep for a claim before correcting one instance of it, and report the grep.',
  '- Minimal diffs. No reflowing, no restructuring, no typo fixes, no gratuitous rewording.',
  '',
].join('\n')

const POST = [
  '',
  '',
  'When done, RETURN a summary (at most 2000 words): every file you changed, every claim you',
  'retracted and its replacement, your grep evidence that you found all instances, what you',
  'deliberately left alone and why, and anything you could not resolve. Your returned text will be',
  'adjudicated - write it as data, not as a message to a human.',
].join('\n')

const LANES = [
  { key: 'A-s139-docs',      task: 'scratchpad/s142-docs/PROMPT-A.md' },
  { key: 'B-ignorance-map',  task: 'scratchpad/s142-docs/PROMPT-B.md' },
  { key: 'C-repo-sweep',     task: 'scratchpad/s142-docs/PROMPT-C.md' },
]

const VER = [
  'You are an ADVERSARIAL VERIFIER of a DOCUMENTATION REPAIR in the SUPERVIVE revival project at ',
  ROOT + '. Your job is to REFUTE, not to agree.',
  '',
  'FIRST read scratchpad/s142-docs/BRIEF.md in full, then the lane task file named below, then',
  'actually READ THE FILES THE LANE EDITED (use git diff to see exactly what changed).',
  '',
  'OFFLINE ONLY. Do not edit any file yourself - report only.',
  '',
  'Check specifically, and be hard about it:',
  '- **Did it over-correct?** The single biggest risk here. Most of these documents contain GOOD',
  '  evidence alongside one dead inference. A banner that reads as "this document is wrong" destroys',
  '  real measurements. Verify each surviving result is explicitly preserved.',
  '- **Did it confuse measurement with inference?** +0x16C8 really did read 0. If any annotation',
  '  implies the probe misread the byte, that is a REFUTED edit.',
  '- **Did it rewrite history?** Original claim text must remain visible. Deleted or silently',
  '  reworded original text is a violation.',
  '- **Rule 9 compliance:** did it fix ONE instance and leave others? Run your own scoped greps over',
  '  the files it owns and report any instance it missed. A partial correction is worse than none.',
  '- **Are the new claims accurate against the BRIEF and the settled docs?** Check addresses, byte',
  '  strings and numbers by reading the sources. Flag any invented or mis-transcribed detail.',
  '- **Grades:** anything marked [M] that is really [I]?',
  '- **Scope creep:** did it edit files it does not own, reflow paragraphs, or make cosmetic changes',
  '  that bloat the diff?',
  '',
  'Report CONFIRMED / DOWNGRADED / REFUTED edits and GAPS, with file:line and verbatim quotes. If',
  'the lane is largely sound, say so plainly - a verifier that manufactures objections is as useless',
  'as one that rubber-stamps.',
  '',
].join('\n')

phase('Repair')

const results = await pipeline(
  LANES,
  function (lane) {
    return agent(PRE + 'YOUR TASK FILE: ' + lane.task + POST,
      { label: lane.key, phase: 'Repair' })
  },
  function (report, lane) {
    const body = (typeof report === 'string') ? report : JSON.stringify(report)
    return agent(
      VER + 'LANE TASK FILE: ' + lane.task +
      '\n\nHere is what the lane reported:\n---\n' + body + '\n---\n',
      { label: 'verify:' + lane.key, phase: 'Refute' }
    ).then(function (v) { return { key: lane.key, report: body, verdict: v } })
  }
)

const good = results.filter(Boolean)
log('lanes complete: ' + good.length + ' of ' + LANES.length)
return { lanes: good }
