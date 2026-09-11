# Analyze gt_sampler.py output: locate the freeze window and rank exe frames (the blocking chain).
# usage: sample_analyze.py <samples.txt> [tail_n=140]
#
# Method: the game thread frozen in one ~20s frame keeps a deep call chain on-stack across many
# consecutive samples, so the caller addresses of the blocking function dominate the freeze window.
# We trim the menu-parked tail (client returned to menu = constant system RIP), take the last
# tail_n in-world samples (~the freeze + lead-in), and rank exe return-addresses by frequency.
import sys, collections

path = sys.argv[1]
tail_n = int(sys.argv[2]) if len(sys.argv) > 2 else 140

mods = []   # (base, size, name)
samples = []  # (ts, rip_str, rip_val, rsp, [frames])
for line in open(path):
    line = line.rstrip("\n")
    if line.startswith("# MOD"):
        _, _, b, s, nm = line.split(None, 4)
        mods.append((int(b, 16), int(s, 16), nm)); continue
    if line.startswith("#") or not line.strip(): continue
    if " RIP=" not in line: continue
    try:
        ts = float(line.split(None, 1)[0])
        rip = line.split("RIP=")[1].split()[0]
        rsp = int(line.split("RSP=")[1].split()[0], 16)
        frames = [f for f in line.split("|",1)[1].split()] if "|" in line else []
        ripval = int(rip.split("0x")[1], 16) if rip.startswith("0x") else -1
        samples.append((ts, rip, ripval, rsp, frames))
    except Exception:
        continue

def modof(a):
    for b, s, nm in mods:
        if b <= a < b + s: return "%s+0x%X" % (nm, a - b)
    return "0x%X" % a

if not samples:
    print("no samples parsed"); sys.exit(0)

# menu-parked detection: trailing run with an identical RIP string (constant system wait)
last_rip = samples[-1][1]
i = len(samples) - 1
parked = 0
while i >= 0 and samples[i][1] == last_rip:
    parked += 1; i -= 1
print("total samples=%d  trailing-constant-RIP(menu-parked?)=%d  RIP=%s (%s)"
      % (len(samples), parked, last_rip, modof(int(last_rip.split('0x')[1],16)) if last_rip.startswith('0x') else last_rip))

inworld = samples[:len(samples)-parked] if parked > 3 else samples
window = inworld[-tail_n:]
if window:
    print("freeze-window: %d samples  span=%.1fs  (ts %.1f .. %.1f)"
          % (len(window), window[-1][0]-window[0][0], window[0][0], window[-1][0]))

# RIP module histogram over the window (are we in a wait or burning exe code?)
riphist = collections.Counter()
for ts, rip, rv, rsp, fr in window:
    if rip.startswith("EXE+"): riphist["EXE"] += 1
    elif rv >= 0: riphist[modof(rv).split("+")[0]] += 1
    else: riphist[rip] += 1
print("\nRIP location histogram (window):")
for nm, c in riphist.most_common(8):
    print("  %5d  %s" % (c, nm))

# exe-frame frequency over the window = the blocking call chain
fh = collections.Counter()
for ts, rip, rv, rsp, fr in window:
    for f in set(fr):   # set: count each addr once per sample
        fh[f] += 1
print("\nTop exe return-addresses in freeze window (addr : #samples / %d):" % len(window))
for addr, c in fh.most_common(30):
    print("  %5d (%3d%%)  EXE%s" % (c, 100*c//max(1,len(window)), addr))
