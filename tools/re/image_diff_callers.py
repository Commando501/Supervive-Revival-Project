# image_diff_callers.py -- BEFORE/AFTER decrypted-image diff: which .text pages did an action run,
# and who calls a given target?  (S120, 2026-08-14)
#
# THE INSTRUMENT THIS PROJECT LACKED. .text is demand-decrypted on execution and decryption is
# MONOTONE within a process lifetime (FK-18/19), so:
#     usmapdump dumpimage <exe-name> dumps/x-BEFORE     # snapshot
#     <perform the action>
#     usmapdump dumpimage <exe-name> dumps/x-AFTER      # snapshot again
# pages ZERO in BEFORE and non-zero in AFTER are EXACTLY the code the action ran. First use (the
# hero-mastery claim) isolated the flow to 20 pages / 80 KB and recovered a call site no static
# search could find, because its page was zero in every prior image.
#
# WARNING function starts on this build are found by locating rel32 call TARGETS landing in the
#   page. The usual int3-padding backscan DOES NOT WORK here.
# WARNING page granularity is 0x1000, so a target whose page was already decrypted by a NEIGHBOUR
#   cannot be isolated -- 'present in BEFORE' is not proof the function itself ran.
#
# Find who calls the hero-mastery claim builder, using a BEFORE/AFTER decrypted-image diff.
#
# WHY THIS WORKS: this build demand-decrypts .text pages on execution, and decryption is MONOTONE
# within one process lifetime (FK-18/19). So pages that are zero in BEFORE and non-zero in AFTER
# were decrypted BY the activity between the two snapshots — here, exactly one claim flow.
# dumpimage writes file-offset == RVA, so indexing is direct.
#
#   usage: diffcallers.py <before.dump.exe> <after.dump.exe> <targetRVA-hex> [more targets...]
import sys, struct

before = open(sys.argv[1], 'rb').read()
after = open(sys.argv[2], 'rb').read()
targets = [int(a, 16) for a in sys.argv[3:]]

# --- PE section table: find .text ---
def sections(buf):
    pe = struct.unpack_from('<I', buf, 0x3C)[0]
    nsec = struct.unpack_from('<H', buf, pe + 6)[0]
    opt = struct.unpack_from('<H', buf, pe + 20)[0]
    out = []
    off = pe + 24 + opt
    for i in range(nsec):
        name = buf[off:off + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, raw = struct.unpack_from('<IIII', buf, off + 8)
        out.append((name, va, max(vsz, rsz)))
        off += 40
    return out

secs = sections(after)
text = [s for s in secs if s[0] == '.text'][0]
tname, tva, tsz = text
print('.text RVA 0x%X size 0x%X  (image %d bytes)' % (tva, tsz, len(after)))

PAGE = 0x1000
newly = []
for rva in range(tva, tva + tsz, PAGE):
    b = before[rva:rva + PAGE]
    a = after[rva:rva + PAGE]
    if len(a) < PAGE:
        break
    bz = (b.count(0) == len(b)) if b else True
    az = (a.count(0) == len(a))
    if bz and not az:
        newly.append(rva)
print('pages newly decrypted between BEFORE and AFTER: %d  (%.2f KB)' % (len(newly), len(newly) * 4))
if newly:
    lo, hi = min(newly), max(newly)
    print('   span 0x%X .. 0x%X' % (lo, hi + PAGE))
newset = set(newly)

# --- find rel32 CALL sites targeting each requested RVA ---
print()
for t in targets:
    hits = []
    # E8 rel32 : target = site + 5 + rel32
    start, end = tva, tva + tsz - 5
    i = start
    while True:
        i = after.find(b'\xE8', i, end)
        if i < 0:
            break
        rel = struct.unpack_from('<i', after, i + 1)[0]
        if i + 5 + rel == t:
            hits.append(i)
        i += 1
    print('CALL sites -> 0x%X : %d' % (t, len(hits)))
    for s in hits:
        page = s & ~(PAGE - 1)
        tag = '  <-- NEWLY DECRYPTED (this is the claim flow)' if page in newset else ''
        # was this call site itself readable before?
        wasz = before[page:page + PAGE].count(0) == PAGE
        print('   site 0x%07X   page 0x%07X  before=%s%s' % (s, page, 'ZERO' if wasz else 'present', tag))
