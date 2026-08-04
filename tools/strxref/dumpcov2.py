#!/usr/bin/env python3
"""dumpcov2.py -- union / novelty analysis over cached .text page bitsets."""
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumpcov import Img, page_bits, PAGE

DUMPS = r"G:\git\Supervive Revival Project\dumps"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "pagecov.json")

NAMES = ["menu", "store", "roster", "missions", "loadout",
         "accountpass", "vmbuild", "toggles", "rcb"]


def load():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            d = json.load(f)
        return {k: bytes.fromhex(v) for k, v in d.items()}
    out = {}
    for n in NAMES:
        p = os.path.join(DUMPS, n, "SUPERVIVE-Win64-Shipping.dump.exe")
        im = Img(p)
        t = im.sec(".text")
        bits, npg = page_bits(p, t[1], t[2])
        out[n] = bytes(bits)
        print(f"scanned {n}: {sum(bits)}/{npg}")
    p = os.path.join(DUMPS, "merged.dump.exe")
    im = Img(p)
    t = im.sec(".text")
    bits, npg = page_bits(p, t[1], t[2])
    out["merged"] = bytes(bits)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as f:
        json.dump({k: v.hex() for k, v in out.items()}, f)
    return out


def u(a, b):
    return bytes(x | y for x, y in zip(a, b))


def main():
    cov = load()
    N = len(cov["merged"])
    TEXT_RVA = 0x1000

    print("=" * 92)
    print("A. IS merged.dump.exe ACTUALLY A MERGE?")
    print("=" * 92)
    m = cov["merged"]
    for n in NAMES:
        c = cov[n]
        only_in = sum(1 for i in range(N) if c[i] and not m[i])
        print(f"  pages in {n:<12} but NOT in merged.dump.exe : {only_in:6d}")
    # the 5 inputs the manifest names
    inputs5 = ["menu", "store", "roster", "missions", "loadout"]
    un5 = bytes(N)
    for n in inputs5:
        un5 = u(un5, cov[n])
    print(f"\n  union of the 5 manifest inputs : {sum(un5):6d} pages ({100.0*sum(un5)/N:.2f}%)")
    print(f"  merged.dump.exe                : {sum(m):6d} pages ({100.0*sum(m)/N:.2f}%)")
    print(f"  best single input (loadout)    : {sum(cov['loadout']):6d} pages")
    print(f"  merged == union-of-5 ? {un5 == m}")
    print(f"  merged == loadout    ? {cov['loadout'] == m}")

    print()
    print("=" * 92)
    print("B. WHAT A CORRECT MERGE OF EVERYTHING WOULD GIVE")
    print("=" * 92)
    same_base = [n for n in NAMES if n != "rcb"]
    un_sb = bytes(N)
    for n in same_base:
        un_sb = u(un_sb, cov[n])
    un_all = u(un_sb, cov["rcb"])
    print(f"  union of 8 same-base dumps       : {sum(un_sb):6d} ({100.0*sum(un_sb)/N:.2f}%)"
          f"   delta vs merged = +{sum(un_sb)-sum(m)} pages"
          f" (+{(sum(un_sb)-sum(m))*PAGE/1048576:.2f} MB)")
    print(f"  union incl. rcb (different base) : {sum(un_all):6d} ({100.0*sum(un_all)/N:.2f}%)"
          f"   delta vs merged = +{sum(un_all)-sum(m)} pages"
          f" (+{(sum(un_all)-sum(m))*PAGE/1048576:.2f} MB)")

    print()
    print("=" * 92)
    print("C. MARGINAL NOVELTY -- pages each dump adds ON TOP OF merged.dump.exe")
    print("=" * 92)
    print(f"  {'dump':<14} {'own pages':>10} {'NEW vs merged':>14} {'new MB':>9}")
    for n in NAMES:
        c = cov[n]
        new = sum(1 for i in range(N) if c[i] and not m[i])
        print(f"  {n:<14} {sum(c):10d} {new:14d} {new*PAGE/1048576:8.2f}M")

    print()
    print("=" * 92)
    print("D. GREEDY INCREMENTAL MERGE ORDER (what each dump is worth, in order)")
    print("=" * 92)
    acc = bytes(N)
    remaining = list(NAMES)
    step = 0
    while remaining:
        best = None
        bestgain = -1
        for n in remaining:
            g = sum(1 for i in range(N) if cov[n][i] and not acc[i])
            if g > bestgain:
                bestgain, best = g, n
        acc = u(acc, cov[best])
        step += 1
        print(f"  {step}. +{best:<12} gain {bestgain:6d} pages ({bestgain*PAGE/1048576:6.2f} MB)"
              f"  -> cumulative {sum(acc):6d} ({100.0*sum(acc)/N:.2f}%)")
        remaining.remove(best)

    print()
    print("=" * 92)
    print("E. PAIRWISE JACCARD / OVERLAP")
    print("=" * 92)
    hdr = "        " + "".join(f"{n[:7]:>8}" for n in NAMES)
    print(hdr)
    for a in NAMES:
        row = f"{a[:7]:<8}"
        for b in NAMES:
            ia = sum(1 for i in range(N) if cov[a][i] and cov[b][i])
            un = sum(1 for i in range(N) if cov[a][i] or cov[b][i])
            row += f"{100.0*ia/un:7.1f}%"
        print(row)

    print()
    print("=" * 92)
    print("F. THE CORE -- pages covered by EVERY dump vs pages covered by exactly one")
    print("=" * 92)
    allc = bytes(N)
    for i in range(N):
        pass
    core = sum(1 for i in range(N) if all(cov[n][i] for n in NAMES))
    anyc = sum(1 for i in range(N) if any(cov[n][i] for n in NAMES))
    once = sum(1 for i in range(N) if sum(1 for n in NAMES if cov[n][i]) == 1)
    print(f"  covered by ALL 9 dumps  : {core:6d} ({100.0*core/N:.2f}% of .text)   <- always-run code")
    print(f"  covered by >=1 dump     : {anyc:6d} ({100.0*anyc/N:.2f}%)")
    print(f"  covered by EXACTLY one  : {once:6d}   <- state-specific code")
    print(f"  NEVER covered           : {N-anyc:6d} ({100.0*(N-anyc)/N:.2f}%)   <- the dark half")


if __name__ == "__main__":
    main()
