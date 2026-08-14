#!/usr/bin/env python3
"""Join: jump-table case -> delegate offset  X  live bound/unbound state.

Case->offset table is from the JumpTable extraction (live disasm + offline
byte-scan cross-check, self-tested on idx 8/19/23).
Bound set is measured live this session (delegates.py, self-tested, re-read
7 min later byte-identical).

Names are .rdata order from server/internal/lobby/vocabulary.go and are
INFERRED except idx 8/19/23, which are MEASURED from the descriptor FStrings.
"""

# idx -> (delegate offsets broadcast by that case)
CASES = {
    0: [], 1: [0x228], 2: [0x1100, 0x1110], 3: [0x1130], 4: [0x1140],
    5: [0x1160], 6: [0x1180], 7: [0x11A0], 8: [0x11B0], 9: [0x11C0],
    10: [0x11D0], 11: [0x1240], 12: [0x1260], 13: [0x1280], 14: [0x12B0],
    15: [0x12D0], 16: [0x12F0], 17: [0x1308, 0x1318], 18: [0x1308, 0x1318],
    19: [0x1510], 20: [0x1520], 21: [0x1530], 22: [0x1540], 23: [0x1550],
    24: [0x1630], 25: [0x1640], 26: [0x1650], 27: [0x1660], 28: [0x1670],
    29: [0x16C0], 30: [0x16D0], 31: [0x16F0], 32: [0x16E0],
}

BOUND = {0x12C0, 0x12D0, 0x12E0, 0x1570, 0x1590, 0x15A0, 0x15C0, 0x15D0,
         0x15F0, 0x1600, 0x1610, 0x1630, 0x1640, 0x1650, 0x1660, 0x1670}

MEASURED = {8, 19, 23}  # names proven from the descriptor FString buffers

NAMES = [  # .rdata order, vocabulary.go
    "connectNotif", "disconnectNotif", "partyLeaveNotif", "partyInviteNotif",
    "partyGetInvitedNotif", "partyJoinNotif", "partyRejectNotif",
    "partyKickNotif", "partyDataUpdateNotif", "partyConnectNotif",
    "partyDisconnectNotif", "partyNotif", "personalChatNotif",
    "partyChatNotif", "channelChatNotif", "userStatusNotif", "messageNotif",
    "userBannedNotification", "userUnbannedNotification", "matchmakingNotif",
    "setReadyConsentNotif", "setRejectConsentNotif", "rematchmakingNotif",
    "dsNotif", "acceptFriendsNotif", "requestFriendsNotif", "unfriendNotif",
    "cancelFriendsNotif", "rejectFriendsNotif", "blockPlayerNotif",
    "unblockPlayerNotif", "errorNotif", "messageSessionNotif",
]

# ---- self-test: the three MEASURED anchors must line up ------------------
anchors = {8: (0x11B0, "partyDataUpdateNotif"),
           19: (0x1510, "matchmakingNotif"),
           23: (0x1550, "dsNotif")}
for i, (off, nm) in anchors.items():
    assert CASES[i] == [off], f"case {i} offset mismatch"
    assert NAMES[i] == nm, f"case {i} name mismatch: {NAMES[i]} != {nm}"
assert len(NAMES) == 33 and len(CASES) == 33
print("[HARNESS] self-test PASS: 3 measured anchors agree on offset AND name\n")

hits = []
for idx in range(33):
    offs = CASES[idx]
    b = [o for o in offs if o in BOUND]
    if b:
        hits.append((idx, b, NAMES[idx]))

print("=" * 74)
print("THE SHORTLIST — notif types whose delegate HAS A LISTENER")
print("=" * 74)
print(f"{'enum':>4} {'idx':>4}  {'delegate':>9}  {'type':<24} name evidence")
for idx, b, nm in hits:
    ev = "MEASURED" if idx in MEASURED else "inferred (.rdata order)"
    print(f"{idx+1:>4} {idx:>4}  " + ",".join(f"+0x{o:x}" for o in b) +
          f"  {nm:<24} {ev}")
print(f"\n{len(hits)} of 33 notif types can reach a subscriber.\n")

used = {o for offs in CASES.values() for o in offs}
orphan = sorted(BOUND - used)
print("BOUND delegates NOT broadcast by any notif case "
      f"({len(orphan)}) -> response delegates, not notif delegates:")
print("   " + " ".join(f"+0x{o:x}" for o in orphan))

unbound_cases = [i for i in range(33)
                 if CASES[i] and not any(o in BOUND for o in CASES[i])]
print(f"\nNotif cases with NO listener: {len(unbound_cases)} "
      f"(+ idx 0 which broadcasts nothing at all)")
print("   " + ", ".join(f"{i}:{NAMES[i]}" for i in unbound_cases))
