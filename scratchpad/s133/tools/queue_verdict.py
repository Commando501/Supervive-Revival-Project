#!/usr/bin/env python3
"""S133 queue/party action sweep — PRE-REGISTERED verdict tool.

DESIGN
------
20 UPartyManager dark impls sit on exactly FOUR dark pages, and they partition by
which UI action reaches them. That gives every phase a target page AND a built-in
spatial negative control (the other three pages must stay dark):

  phase 1  BOTS -> FIND MATCH          target 0x5875000  (TryJoinQueue + 6 others)
  phase 2  READY / FILL / OPEN / EMOTE target 0x5879000  (TrySetIsReady, TrySetFill-
                                                          Preference, TrySetIsOpen,
                                                          TrySendEmote, TrySendInvite,
                                                          TrySendRequest)
  phase 3  CUSTOM GAME create/configure target 0x5873000 + 0x5874000

CONFOUND, STATED UP FRONT: a 4 KiB page holds many functions, so page 0x5875000
lighting proves SOME of its seven functions ran, NOT that TryJoinQueue did.
Attribution needs the second instrument (capture.log / Loki.log) -- this tool
reports the page result and the control result; it does not claim attribution.

usage: python queue_verdict.py <before.dump.exe> <after.dump.exe> [--label X]
"""
import sys, io, argparse

PAGE = 4096
TEXT_RVA, TEXT_VSZ = 0x1000, 0x7649000
NP = TEXT_VSZ // PAGE + (1 if TEXT_VSZ % PAGE else 0)

TARGETS = {
    0x5875000: "TryJoinQueue, TryCustomGameSetState/Start, TryDeclineInvite/Request, TryJoinParty(BySecret)",
    0x5879000: "TrySendEmote/Invite/Request, TrySetFillPreference, TrySetIsOpen, TrySetIsReady",
    0x5873000: "TryCustomGameChangeTeam/MovePlayer/SetDescription/SetDetails/SetDisabledAssets",
    0x5874000: "TryCustomGameSetInProgress, TryCustomGameSetPassword",
}
OTHER = {
    0x5712000: "UChatManager", 0x571b000: "UChatManager", 0x571c000: "UChatManager",
    0x5744000: "UChatManager", 0x574a000: "UChatManager",
    0x5607000: "UPartyModel", 0x586e000: "UPersonalizationManager",
    0x4e97000: "UPlatformInventoryManager", 0x57a2000: "UPlatformInventoryManager",
    0x5863000: "USocialManager", 0x5865000: "USocialManager",
    0x579f000: "UStorefrontManager",
}


def bitmap(path):
    bm = bytearray(NP)
    with open(path, 'rb') as f:
        f.seek(TEXT_RVA)
        for i in range(NP):
            b = f.read(PAGE)
            if not b:
                break
            if b.count(0) != len(b):
                bm[i] = 1
    return bm


def pg(rva):
    return (rva - TEXT_RVA) // PAGE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('before')
    ap.add_argument('after')
    ap.add_argument('--label', default='')
    a = ap.parse_args()

    B, A = bitmap(a.before), bitmap(a.after)
    print(f"BEFORE {a.before}: {sum(B)} pages")
    print(f"AFTER  {a.after}: {sum(A)} pages")
    gained = [i for i in range(NP) if A[i] and not B[i]]
    lost = [i for i in range(NP) if B[i] and not A[i]]
    print(f"NEWLY DECRYPTED: {len(gained)} pages"
          + (f"   ({len(gained)*PAGE/1024:.0f} KB)" if gained else ""))
    print(f"[CTRL] pages LOST (must be 0 -- .text decryption is monotone within a "
          f"lifetime): {len(lost)}"
          + ("   <-- INSTRUMENT FAULT" if lost else "   PASS"))
    print()

    print("PRE-REGISTERED UPartyManager TARGET PAGES")
    for rva in sorted(TARGETS):
        i = pg(rva)
        was, now = ('LIT' if B[i] else 'DARK'), ('LIT' if A[i] else 'DARK')
        mark = '  *** LIT UP ***' if (now == 'LIT' and was == 'DARK') else ''
        print(f"  {rva:#010x}  {was:4s} -> {now:4s}{mark}")
        print(f"              {TARGETS[rva]}")
    print()
    print("OTHER PRE-REGISTERED MENU-MANAGER DARK PAGES (context, not controls)")
    for rva in sorted(OTHER):
        i = pg(rva)
        was, now = ('LIT' if B[i] else 'DARK'), ('LIT' if A[i] else 'DARK')
        mark = '  *** LIT UP ***' if (now == 'LIT' and was == 'DARK') else ''
        print(f"  {rva:#010x}  {was:4s} -> {now:4s}  {OTHER[rva]}{mark}")

    if gained:
        print()
        print("ALL newly decrypted pages, grouped into runs:")
        runs = []
        s0 = gained[0]
        prev = gained[0]
        for i in gained[1:]:
            if i != prev + 1:
                runs.append((s0, prev))
                s0 = i
            prev = i
        runs.append((s0, prev))
        for lo, hi in runs:
            print(f"   {TEXT_RVA+lo*PAGE:#010x} .. {TEXT_RVA+(hi+1)*PAGE-1:#010x}"
                  f"  ({hi-lo+1} pages)")


if __name__ == '__main__':
    main()
