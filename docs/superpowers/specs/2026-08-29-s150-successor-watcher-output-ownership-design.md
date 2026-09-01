# S150 Successor Watcher and Output Ownership Design

Date: 2026-08-29

Status: draft for user review; identity-neutral design only

Predecessor terminal report:
`docs/s150-flight2-recoverlaunch-terminal-watcher-refusal.md`

Frozen predecessor tracker:
`.superpowers/sdd/2026-08-27-s150-capture-generation/task-5-controller-report.md`

## Authorization boundary

This document designs the offline successor to terminal S150 Flight 2. It does
not authorize an implementation plan, a production edit, a live label, a GUID,
an intended flight date, `RecoverLaunch`, `Arm`, a launcher invocation, or any
game/process action.

The user must approve this design before an implementation plan is written.
Offline implementation and verification will still stop before a live identity
is bound. A later identity-bound candidate requires its own freeze, manifest,
reviews, final offline GO, and new explicit live authorization.

Flight 2 is immutable and retired. Its controller, test, manifest, tracker,
namespace, evidence, and consumed authorization must never be edited, retried,
or reinterpreted as a successor.

## Decision summary

The successor will repair both independently proven Flight 2 trust-boundary
defects:

1. Admit watcher startup only through a successor-local canonical raw-byte
   envelope layered over the unchanged S149 semantic parser.
2. Give the long-lived backend its own stdout and stderr files, derived from
   the controlled capture archive parent, so neither stream can inherit the
   bounded launcher child's outputs.
3. Replace launcher-output quiet sampling with read-only identity anchors plus
   writer-denying terminal leases. A terminal receipt is valid only when no
   writer exists and the exact held streams remain unchanged through durable
   admission evidence.
4. Implement and review these seams without a live identity. Bind one immutable
   label/GUID/date only when the neutral work is green and a realistic same-day
   review and flight window has been selected.

This preserves the current fail-closed process identity, command, hash,
liveness, timestamp, no-reparse, no-clobber, cleanup, one-use, and no-retry
policies. It does not relax admission or rely on a longer quiet interval.

## Established evidence

### Watcher refusal

The pinned watcher executable is 3,988,480 bytes with SHA-256
`6DAA73BF7238C0A0D91490CA10C38096F88CAA3841C333BBA89B8C55A57B2FCF`.
For the reviewed no-timeout command it unconditionally emits four semantic
startup lines, the log-tail offset line, and a final blank line.

The preserved Flight 2 watcher stdout is 352 bytes with SHA-256
`CE5A4D371130F9C023BFDAD3528877E9596F246F322A0BE1356564A51EEE4461`.
Its zero-based LF offsets are `52,123,245,290,350,351`. It therefore contains:

- five nonempty ASCII lines;
- one final blank line;
- exactly six `0x0A` bytes;
- no `0x0D`, BOM, NUL, or non-ASCII byte; and
- exact terminal bytes `0A 0A`.

The frozen controller enters the shared S149 parser only when the nonempty line
count equals four. The real five-line envelope can therefore never be admitted.
The frozen Arm gate repeats the same contradiction. The unchanged shared S149
parser correctly validates the four semantic lines and their generation times,
but intentionally tolerates additional text.

### Launcher receipt drift

The controlled backend was started with stderr redirected to
`docs/server.out.log` and stdout inherited. The backend request middleware
writes a compact line to stdout for each request. The backend therefore kept a
writer to `launcher.stdout.log` after the direct launcher PowerShell child had
exited.

Flight 2 recorded a 602-byte launcher stdout prefix with SHA-256
`BFE367469C77DE74EB2E61E7B6FC9FE6C686AF6EE9A2AC655FF9D49177DCF875`.
The later health request appended `#2 GET /healthz -> 200\n`, producing the
final 625-byte file with SHA-256
`15E75FB1FC269F8CA3409AB8011986D6AA4E9D85F37CE5545F8A3692E47008DD`.

The existing two equal samples 50 ms apart proved only momentary quietness.
They did not prove writer absence, and no later gate revalidated the recorded
receipt against the final file.

### Terminal safety state

Flight 2 did not write `fresh-admission.json`, did not invoke Arm or the stager,
and did not inject. Exact cleanup reached a stable zero census for all six
protected names, and the dump directory remained empty. The terminal report is
17,543 bytes with SHA-256
`978AFACEAC1EDF2C8B0BFC9E24C75B126E975BEE768BB154418215D89CBB2021`.
The post-failure audit is 1,131 bytes with SHA-256
`EA721DBA7BEAFD48411A1776EC9420199F966397589F5A761895BA8889E515FF`.

## Alternatives considered

| Boundary | Approach | Decision | Reason |
|---|---|---|---|
| Watcher | Successor-local canonical byte renderer, then unchanged S149 parser | Selected | Exact producer contract with the smallest provenance blast radius |
| Watcher | Add or replace a strict function in the shared S149 gate | Rejected | Unnecessarily changes a historical shared gate and every dependent pin |
| Watcher | Accept four or more lines, or ignore extras | Rejected | Fails open and admits unreviewed suffixes |
| Launcher output | Separate backend sinks plus writer-denying launcher leases | Selected | Proves ownership and terminality directly |
| Launcher output | Pipe/pump broker process | Rejected for now | Can be safe, but adds backpressure, process identity, cleanup, and provenance machinery |
| Launcher output | Longer quiet wait or more equal samples | Rejected | A long-lived writer can remain quiet beyond any finite interval |
| Backend output | Redirect to `NUL`, detach, or discard | Rejected | Loses forensic evidence and weakens output ownership |
| Lifecycle | Identity-neutral work followed by one late immutable binding | Selected | Avoids date expiry while preserving one reviewed live instance |
| Lifecycle | Allocate identity before ordinary engineering work | Rejected | The date can expire before review or authorization |
| Lifecycle | Caller-supplied runtime label/GUID/date | Rejected | Broadens live capability and defeats immutable provenance |

## Watcher startup envelope contract

### Pure validation seam

One successor-local pure helper will accept raw bytes and all expected dynamic
values. It must not read files, inspect processes, read a clock, or use mutable
controller globals. Both RecoverLaunch and Arm must call this same helper.

Conceptually, its inputs are:

- raw watcher stdout bytes;
- expected game PID;
- expected watcher PID and start ticks;
- admitted and actual log creation ticks;
- actual last-write and current ticks;
- exact Loki path; and
- exact watcher output directory.

Validation occurs in this order:

1. Require a maximum of 4,096 bytes and an ASCII-only byte sequence.
2. Require no BOM, NUL, CR, or non-ASCII byte.
3. Require exactly six LF bytes and exact final bytes `0A 0A`.
4. Extract only the fifth line's offset token. Require the ASCII grammar
   `0|[1-9][0-9]{0,18}`, a successful nonnegative `Int64` parse, no sign,
   leading zero, whitespace, Unicode digit, or overflow.
5. Canonically render the complete expected envelope with ASCII and LF:

   ```text
   crashwatch: pid <expected PID> (SUPERVIVE-Win64-Shipping.exe)\n
     log     : <exact full Loki path>\n
     outDir  : <exact full output directory>\n
     poll    : 50 ms   suspend-on-trigger: true\n
     log tail starts at offset <canonical Int64 decimal> (older markers ignored)\n
   \n
   ```

6. Require equal byte length and ordinal byte-for-byte identity between the
   rendered and observed envelopes.
7. Decode only after the raw comparison and call unchanged
   `Get-S149WatcherReceiptResult` with every existing PID, path, suspension,
   creation-time, last-write-time, and current-time argument.
8. Additionally require `lastWriteUtcTicks >= creationUtcTicks`.

The result is structured and first-failure-wins. It contains a stable reason,
raw byte length, uppercase SHA-256, parsed offset, and the supplied timestamp
fields. Text normalization, trimming, or split-and-rejoin equality is forbidden.

The S149 gate remains byte-identical, including its watcher command parser and
receipt parser. The watcher executable also remains byte-identical.

### Coherent live-writer snapshots

The watcher remains a legitimate writer while alive, so neither its stdout nor
stderr can use a writer-denying lease. A successor-local snapshot helper will
instead, for each stream:

1. perform ordinary-file and component-wise no-reparse admission;
2. open read-only with `FileShare.ReadWrite`, omitting delete sharing, and keep
   that identity handle open while the second sample is acquired;
3. capture creation ticks, last-write ticks, path length, and stream length;
4. read exactly the captured length from the same stream;
5. refresh metadata and require creation, last-write, path length, stream
   length, and bytes-read length to remain identical;
6. hash the raw bytes;
7. while the first identity handle still prevents delete/rename/replacement,
   take a second bounded snapshot; and
8. require identical metadata, length, and hash across both snapshots.

Incomplete or changing startup samples remain unadmitted until the existing
ten-second deadline. A malformed complete sample is never admitted. Immediately
before `fresh-admission.json`, RecoverLaunch repeats coherent snapshots of both
streams and requires exact equality with the accepted samples. It repeats both
checks once more after the durable receipt; drift is a terminal
launcher-boundary failure followed by exact cleanup. A receipt written
immediately before such a failure cannot pass Arm because its runtime and
watcher revalidations will fail after cleanup.

Watcher stderr must be exactly zero bytes with the empty SHA-256. Its creation
and last-write ticks are pinned just like stdout. An initially empty stderr that
receives a delayed append is drift and must refuse. RecoverLaunch retains the
read-only watcher identity handles through fresh admission or cleanup. Arm
opens new read-only identity handles and retains them through both Arm watcher
checks, allowing legitimate writes but preventing leaf replacement during the
admission interval.

The fresh-admission record pins:

- raw stdout byte length and SHA-256;
- stdout creation and last-write ticks;
- newline form `LF`;
- parsed log-tail offset;
- the canonical envelope validation result; and
- zero-byte watcher stderr size, empty SHA-256, creation ticks, and last-write
  ticks.

Arm takes new coherent two-snapshot samples of both streams, compares every
admitted raw and metadata field, and reruns the same pure canonical helper for
stdout. Any appended stdout or stderr byte refuses Arm. All preparation,
launcher held-stream confirmation, argument construction, provenance
confirmation, marker snapshotting, and stager-output anchor creation must occur
before the second watcher check. That final coherent stdout/stderr check then
directly fences the CreateNew `stager-invoked.json` receipt and the single child
call; no other admission or preparation operation may intervene.

## Output ownership contract

### Canonical controlled paths

No new caller-supplied backend-output parameter is needed. In controlled mode,
the controller derives all four outputs from its exact retirement root. The
launcher independently derives the retirement root as the canonical parent of
the already required `S150CaptureArchiveDirectory` and derives the two backend
outputs from that root.

The archive leaf must be exactly `capture-archive`. The four output leaves are:

```text
<retirement>\launcher.stdout.log
<retirement>\launcher.stderr.log
<retirement>\backend.stdout.log
<retirement>\backend.stderr.log
```

All four paths must be strictly inside the successor retirement namespace,
absent before controller creation, ordinary, and component-wise non-reparse.
Windows full paths are compared with `OrdinalIgnoreCase`; literal leaf names
such as `capture-archive`, `backend.stdout.log`, and `backend.stderr.log` are
compared case-sensitively and must be exact. The controller binds all four
paths; the launcher independently binds the exact archive, retirement parent,
and two backend siblings.

Only the controlled backend start changes:

- stdout redirects to `<retirement>\backend.stdout.log`;
- stderr redirects to `<retirement>\backend.stderr.log`; and
- neither backend stream inherits a launcher stream.

After the Go build and immediately before the inner backend `Start-Process`,
the launcher repeats canonical ordinary/component-no-reparse admission. It
requires the archive path to equal the controller's exact capture archive, its
parent to equal the exact retirement root, and the two precreated backend
leaves to remain the exact ordinary sibling paths. The potentially lengthy
build may not separate the final path gate from process creation.

`docs/server.out.log` remains the legacy sink for non-controlled launches only.
The successor still preserves and moves the current pre-launch
`docs/server.out.log` as checkpoint evidence, but a controlled launch does not
create a new active-path copy.

### Continuous no-clobber identity anchors

Before `launcher-invoked.json`, the successor controller creates and anchors all
four output files. For each path it must:

1. repeat absence and component-wise no-reparse validation;
2. open CreateNew with a temporary `ReadWrite/FileShare.ReadWrite` stream;
3. durably flush the empty file;
4. while that creator remains open, open a persistent read-only identity anchor
   with `FileShare.ReadWrite`; and
5. close only the temporary creator.

This handoff has no unanchored close/reopen interval. The persistent read-only
anchor excludes delete sharing, so the leaf cannot be deleted, renamed, or
replaced, while still allowing the one authorized redirection writer.

All four persistent identity anchors survive launcher execution and either the
durable RecoverLaunch admission or durable cleanup result. Any partially
created anchor set is disposed only by the outer `finally`. The existing
generic child-output runner remains available for the stager. The successor
launcher composes a distinct terminal-output runner from the existing exact
process-binding, command, hash, watchdog, and cleanup primitives rather than
copying them, so terminal proof is not silently imposed on unrelated historical
child boundaries and inherited logic cannot drift in a duplicate.

### Launcher terminal leases

After the exact direct launcher child exits, the controller attempts to open
launcher stdout and stderr read-only with `FileShare.Read`. The existing
read-only identity anchors are compatible with this open; any descendant,
redirection worker, game, backend, or other writer is not. To accommodate only
bounded Windows redirection-handle release, acquisition may retry for at most
2,000 ms at 25 ms intervals. Every attempt must be the same writer-denying
`Read/FileShare.Read` open. File quietness, equal samples, or elapsed time can
never count as success. Deadline expiry is a terminal admission refusal.

Once acquired, each lease denies new write, delete, or rename access. The
controller hashes and sizes the exact held stream, preserves its position, and
reads timestamps while both the terminal lease and identity anchor remain held.
It enforces the existing 32 MiB per-stream ceiling.

Both launcher leases stay open through:

- `launcher-result.json`;
- `launcher-result.receipt.json`;
- same-stream confirmation immediately before and after
  `fresh-admission.json`; or
- on failure, durable `launcher-cleanup-result.json`.

Partial acquisition is also fail-closed. If stdout seals and stderr does not,
the stdout lease remains held while exact cleanup stops only validated
identities and proves stable zero. Cleanup then attempts writer-denying
finalization of the missing launcher stream and reconfirms the already sealed
stream, recording both only as cleanup evidence. A `launcher-result.json`
written for the failed attempt is never rewritten, and post-cleanup hashes can
never convert the failed boundary into admission success.

The fresh-admission receipt contains the terminal launcher stdout/stderr
size/hash/timestamp records. Arm reopens writer-denying leases, compares the
same raw metadata and hashes, and holds them through the complete Arm boundary.
Any missing file, writer, reparse drift, byte drift, metadata drift, or failed
same-stream confirmation refuses before `stager-invoked.json`.

### Backend logs are live evidence, not terminal receipts

Backend stdout and stderr remain intentionally mutable while the exact backend
is alive. Fresh admission may record canonical paths, creation identity, a
bounded point-in-time prefix snapshot, and an explicit `mutableWhileBackendLive`
classification. It must not claim a final whole-file hash.

On launcher-boundary failure, exact cleanup stops the admitted game, watcher,
and backend identities in the existing order and proves stable zero. Only after
the backend stops may cleanup acquire writer-denying leases on both backend
logs and record final hashes. A post-cleanup terminal hash is cleanup evidence
only and must never be adopted retroactively as a successful launcher receipt.

If launcher sealing fails because an unexpected writer exists, cleanup stops
only exact validated process identities. It never sweeps by name or kills an
unknown holder merely to make a lease succeed. Any inability to finalize
cleanup evidence remains an explicit cleanup failure.

Every identity anchor and any acquired terminal lease is released in one outer
`finally`, after the durable success or cleanup boundary. No exceptional path
may leak a test or production handle.

## RecoverLaunch and Arm ordering

### RecoverLaunch

The successor preserves the reviewed checkpoint, provenance, no-reparse,
capture-generation, certificate, crashpad, process, and one-use gates. The
changed portion is ordered as follows:

1. Complete the historical/zero-runtime checkpoint and consume the new
   identity only after all pre-mutation gates pass.
2. Create the retirement namespace, capture archive, watcher dump directory,
   and all four output identity anchors with CreateNew semantics.
3. Durably write the invocation and handoff receipts.
4. Invoke exactly one controlled launcher child with the exact derived output
   contract.
5. Bind and validate the direct launcher child exactly, wait boundedly, and
   acquire both launcher terminal leases after its exit.
6. Write and same-stream confirm the launcher result evidence.
7. Admit exact fresh backend/game state, capture generation, archive set,
   certificates, and health.
8. Start one exact watcher, admit only its canonical raw stdout envelope, and
   admit exact-empty coherent stderr.
9. Reconfirm launcher leases and coherent snapshots of both watcher streams,
   durably write fresh admission, then reconfirm both evidence classes.
10. On any failure, retain all evidence, perform exact cleanup, record final
    backend logs after backend stop when possible, and never retry.

### Arm

Arm remains a separate host invocation. It must:

1. load the exact same-label/same-generation/same-date fresh admission;
2. acquire and hold writer-denying launcher-output leases;
3. revalidate backend/game/watcher PID, start time, path, hash, command, and
   liveness tuples;
4. revalidate capture generation, archive exact set, certificate triplet,
   health, date, ledger and label absences, and provenance leases;
5. revalidate terminal launcher streams against the admitted records and
   complete every remaining argument, marker, provenance, date, and output
   preparation step;
6. revalidate coherent canonical watcher stdout and exact-empty stderr a second
   time as the final admission operation; and
7. immediately write one `stager-invoked.json` and invoke exactly one stager
   child, with no intervening preparation or admission work.

No change weakens the stager, mutation, cleanup, or no-retry policy.

## Identity-neutral TDD route

Production behavior must not change before watched RED evidence exists. Before
writing implementation code, the implementation session must also load the
test-quality guidance referenced by the TDD workflow.

### Required RED evidence

1. Replay the exact preserved 352-byte Flight 2 watcher receipt against the
   frozen controller and prove both RecoverLaunch startup and Arm contracts
   reject it because of the exact-four-line condition.
2. Rehash the frozen Flight 2 controller before and after RED and require exact
   SHA-256
   `BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09`.
3. Use real temporary NTFS files and processes to reproduce a delayed inherited
   descendant append after the old two-sample receipt has returned. Require the
   recorded prefix hash to differ from the final file hash.
4. Demonstrate that the current controlled launcher has no distinct backend
   stdout ownership contract.

### Pure watcher GREEN matrix

Positive fixtures include the exact Flight 2 352-byte receipt, the historical
S149 348-byte startup prefix, and a synthetic canonical offset zero.

Negative fixtures include:

- missing fifth line, sixth nonempty line, duplicate or reordered line;
- extra blank line, missing final blank line, or truncated write;
- wrong PID, Loki path, output directory, poll value, or suspension value;
- offset `-1`, `+1`, `00`, Unicode digits, overflow, missing digits, changed
  prose, or trailing space;
- UTF-8 BOM, CRLF, lone CR, NUL, non-ASCII, or any raw-byte drift;
- creation mismatch, stale/future generation, zero watcher identity, or
  `now < watcherStart`;
- nonempty watcher stderr;
- delayed watcher-stderr append after an initially empty sample; and
- append between initial acceptance and either RecoverLaunch or Arm
  revalidation.

The snapshot helper is tested separately with a test-owned held writer and
metadata mutation. Both production callers must invoke the same pure helper;
the fifth-line grammar must not be duplicated.

### Real NTFS output GREEN matrix

Tests must prove:

- a fake long-lived backend writes only backend stdout/stderr while both
  launcher leases succeed;
- a non-backend inherited descendant writer makes launcher sealing refuse;
- the exact Windows PowerShell 5.1 native invocation shape used for the game is
  exercised with a long-lived detached fixture; any inherited launcher writer
  is an offline NO-GO that reopens this design before identity binding;
- stdout and stderr are independent, including empty stderr;
- a pre-existing path refuses with unchanged bytes and zero child starts;
- a junction or other reparse component refuses;
- a held writer refuses sealing and exact cleanup still runs;
- post-stop backend finalization is labelled cleanup-only;
- write, delete, and rename fail while a terminal lease is held and work only
  after release;
- the hash is computed and reconfirmed from the same held stream;
- the bounded terminal-open loop succeeds only on an actual
  `Read/FileShare.Read` lease after Windows PowerShell releases its writer;
- output ceilings remain bounded; and
- every test-owned child and descendant is stopped by exact identity with zero
  residual fixture processes.

## Provenance and regression requirements

The identity-neutral phase may add a pure successor evidence helper and tests
and may change only the controlled branch of `configs/launch-redirect.ps1`.
`configs/s150-capture-generation.ps1`, the shared S149 gate, the watcher, and
all Flight 2 frozen artifacts do not need to change.

The future identity-bound controller must pin and lease every new helper and
the changed launcher. Its source-contract test must account for each modified
function extent while requiring all unaffected inherited extents to remain
ordinally identical.

A static AST/source regression must prove the non-controlled backend
`Start-Process` branch remains byte-for-byte unchanged and never evaluates the
controlled retirement/output derivation. Ordinary launcher behavior is outside
the successor delta.

Before identity binding, run fresh evidence for:

- the new RED/GREEN watcher and output suites;
- the unchanged frozen Flight 2 companion test and exact frozen hashes;
- S150 capture-generation behavior;
- S149 bind gate, stage plan, stager safety, compile policy, and bind contract;
- S148 build contract and behavior;
- S147 natural-state and input-plan tests;
- PowerShell AST, ASCII/no-BOM, no-clobber, reparse, cleanup, and process-census
  contracts;
- affected backend and DLL A/B reproducibility and DLL verification; and
- the three frozen S147 RAW sentinels.

Any mismatch is a hard NO-GO. Expected values are never revised to match an
unexpected result. No commit is made unless the user explicitly asks for one.
Unrelated working-tree changes remain untouched.

## Historical baseline and late identity binding

Before the first successor implementation edit, create a dedicated historical
baseline at a new fixed path with CreateNew semantics. Durably flush it, reopen
it read-only, hash the reopened bytes, and record its own path, size, SHA-256,
creation ticks, and last-write ticks in the offline evidence. This freeze must
precede any changed byte in `configs/launch-redirect.ps1` or a successor helper.

The baseline pins exact paths, sizes, hashes, timestamps where meaningful, and
directory topology for:

- the six frozen Flight 2 design/plan/controller/test/manifest/tracker inputs;
- the terminal report and post-failure audit;
- the exact Flight 2 retirement topology and all 15 retained files;
- the ordinary empty Flight 2 dump directory;
- the absence of fresh-admission and stager receipts;
- the cleanup and launcher-drift evidence;
- the generated active-path backend, capture, server-output, and certificate
  state; and
- the terminal no-retry/no-Arm conclusion.

It also pins the pre-successor controlled launcher itself, including the Flight
2 hash
`A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D`,
and the complete scoped source state from which the successor edit begins.

This baseline is historical evidence, not an offline GO.

Only after neutral implementation, full regression evidence, and independent
review are green may one late identity-binding pass occur:

1. Select a realistic same-day verification/review window.
2. Generate one unused label, UUID D/N pair, and intended local date.
3. Collision-check every derived retirement, dump, receipt, runtime-evidence,
   and ledger path.
4. Bind the literals into one new sibling controller/test and pure Plan.
5. Freeze the identity-bound spec, plan, controller, test, launcher/helper
   inputs, and evidence in a unique CreateNew manifest. That manifest must pin
   the exact historical-baseline file/hash and independently enumerate every
   leaf asserted by the baseline; neither a transitive reference nor the
   baseline's self-claim is sufficient.
6. Rerun all identity-affected gates and obtain separate implementation-safety
   and evidence/provenance reviews.
7. Publish an exact final offline GO containing the manifest hash, controller
   hash, identity, date, zero census, namespace absences, and provenance pins.
8. Stop. Offline GO is not live authorization.

After binding, no edit, relabel, GUID replacement, manifest replacement, or
expected-value substitution is allowed. Expiry, gate failure, review finding,
or provenance mismatch retires that candidate and requires a new identity and
complete re-freeze.

## Live boundary after a future GO

A new explicit user instruction must cite the exact successor label, generation
GUID, controller SHA-256, review-manifest SHA-256, permitted mode, and
`-Execute`. The safest authorization scope is exactly one
`RecoverLaunch -Execute`. It is consumed even by a read-only refusal. No
automatic retry or auto-chained Arm is permitted.

After successful RecoverLaunch, publish and review the exact fresh-admission,
launcher-terminal, watcher-envelope, process, capture, certificate, archive,
and health evidence. Require a second explicit instruction citing the same
label, GUID, controller hash, manifest hash, exact fresh-admission path and
SHA-256, mode `Arm`, and `-Execute` before exactly one Arm invocation.

A RecoverLaunch failure is terminal: retain evidence, perform only the reviewed
exact-identity cleanup, prove stable zero, and never retry. An Arm refusal before
`stager-invoked.json` writes no stager receipt and starts no child; it preserves
the admitted runtime/evidence without inferring authority for an automatic
shutdown. An Arm failure after `stager-invoked.json` preserves all receipts and
provenance and stops: no automatic cleanup, retry, relabel, or second child is
permitted. Any later runtime retirement is a separately reviewed and authorized
operation.

## Acceptance criteria for this design

This design is ready for implementation planning only when the user approves:

- canonical raw watcher rendering over the unchanged S149 parser;
- separate derived backend stdout/stderr sinks;
- continuous read-only identity anchors and writer-denying launcher leases;
- intentionally mutable backend logs while the backend is live;
- identity-neutral TDD followed by late immutable binding; and
- separate future RecoverLaunch and Arm authorizations.

Until then, the correct state is:

`FLIGHT2_PRESERVED; SUCCESSOR_DESIGN_PENDING_REVIEW; NO_IDENTITY; NO_LIVE_ACTION`
