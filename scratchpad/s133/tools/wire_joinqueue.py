#!/usr/bin/env python3
"""S133: wire POST joinQueue/leaveQueue into the mux, add playerState.InQueue, and make
every party echo carry the flag (or the next poll snaps it back — the S122 defect)."""
import io

# ---------- 1. playerState.InQueue ----------
P = 'server/internal/interactive/store.go'
s = io.open(P, encoding='utf-8').read()
anchor = "\tSoloMode string `json:\"-\"`\n"
assert anchor in s, 'SoloMode anchor not found'
add = anchor + """
\t// InQueue is true between the FIND MATCH click (POST .../joinQueue) and a cancel.
\t// Echoed as the party's and the member's `inQueue` boolean so the client's queued
\t// state survives the next /party poll — without it the poll re-serves false and the
\t// UI snaps back, exactly the defect handleSetTargetQueues exists to remove.
\t//
\t// TRANSIENT (json:"-"), for the same reason SoloMode is: a persisted "queued" flag
\t// would make a FRESH boot claim the player is already searching for a match, with no
\t// matchmaker to ever clear it. Queue state is a property of a live session.
\tInQueue bool `json:\"-\"`
"""
s = s.replace(anchor, add)
io.open(P, 'w', encoding='utf-8').write(s)
print('store.go: added playerState.InQueue')

# ---------- 2. accessor next to selectedQueue ----------
P = 'server/internal/interactive/interactive.go'
s = io.open(P, encoding='utf-8').read()
i = s.index('func (s *Service) selectedQueue(id string) string {')
acc = """// inQueue reports whether the player has clicked FIND MATCH and not cancelled.
// Gated by AGS_JOIN_QUEUE=0, which restores the pre-S133 wire byte-for-byte.
func (s *Service) inQueue(id string) bool {
\tif os.Getenv("AGS_JOIN_QUEUE") == "0" {
\t\treturn false
\t}
\tst := s.store.get(id)
\tif st == nil {
\t\treturn false
\t}
\treturn st.InQueue
}

"""
s = s[:i] + acc + s[i:]

# ---------- 3. routes ----------
route_anchor = '\tmux.HandleFunc("POST /party/parties/{partyId}/setTargetQueues", s.handleSetTargetQueues)\n'
assert route_anchor in s, 'route anchor not found'
s = s.replace(route_anchor, route_anchor + """
\t// S133: FIND MATCH. Discovered by DRIVING the button during an FK-20 decryption run,
\t// not by a capture sweep — see joinqueue.go for the wire evidence and for why the
\t// response must be an FParty under an advanced Version (UPartyModel::SetParty).
\tmux.HandleFunc("POST /party/parties/{partyId}/joinQueue", s.handleJoinQueue)
\tmux.HandleFunc("POST /party/parties/{partyId}/leaveQueue", s.handleLeaveQueue)
\tmux.HandleFunc("POST /party/parties/{partyId}/cancelQueue", s.handleLeaveQueue)
""")

# ---------- 4. every party echo applies the flag ----------
old = ('writeJSON(w, buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id), '
       's.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion()))')
new = 's.writeParty(w, r, id)'
n = s.count(old)
s = s.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(s)
print(f'interactive.go: added inQueue(), 3 routes, and routed {n} party echoes through writeParty')
