// armqueue.go — answer the matchmaking QUEUE with a match, so CO-OP VS. AI (and every
// other TryJoinQueue-path queue) can get past "searching…".
//
// ============================================================================
// WHY THIS FILE EXISTS
// ============================================================================
// S133 made FIND MATCH work: POST /party/parties/{p}/joinQueue is served, the client
// enters a real queued state with a running timer and a working cancel. What it does
// NOT do is ever produce a match — nothing in this server reads playerState.InQueue.
//
// [M] THE SPLIT THAT MAKES THIS NECESSARY. Native UPartyManager::IsSpecialQueue
// (fn 0x5854F5F) hardcodes which queues take which client path:
//
//	SOLO  path -> TryStartSoloMode -> POST /startSoloMode
//	              { practice, customgame, dropin, tutorialNew, training }
//	QUEUE path -> TryJoinQueue     -> POST /joinQueue
//	              { default, deathmatch, bots, tournament, armorydeathmath }
//
// `SoloMode` is written ONLY by POST /startSoloMode. `bots` is on the QUEUE path and
// therefore never sends it. So handleCoreGamePlayer's old gate — SoloMode != "" — can
// never fire for a queued player, and MatchID stays "" forever no matter how long the
// player waits. That is the exact accessibility/playability boundary for CO-OP VS. AI:
// the tile, the click, the queue, the timer and the cancel all already work.
//
// ============================================================================
// ⚠⚠ THE THING THAT MAKES THIS NON-OBVIOUS: THE CLIENT DOES NOT POLL
// ============================================================================
// [M] GET /core-game/players/{id} is fetched EXACTLY ONCE PER MESSENGER CONNECTION,
// within ~53–82 ms of connect, and never again — 1:1 across 8 captures / 12 connections
// / 12 fetches. interactive.go's own comments claiming a ~1/min poll are REFUTED, and
// docs/endpoints.md's "active poller ~17/s" is stale.
//
// Corroborating measurement: in scratchpad/s133/evidence/capture-phase2.log two
// startSoloMode calls land at 19:19:50.558 and 19:19:51.089, and the ONLY
// /core-game/players request in the whole file is at 18:56:14.318 — 23 minutes EARLIER,
// at login. So even the SOLO path's write-and-wait only ever worked because the write
// happened before the connection that fetched it.
//
// ⇒ Writing MatchID is not enough. It must be PUSHED. lobby.NotifyResource bumps one
// resource's version down the messenger and the client refetches with no reconnect;
// UCoreGameManager's init (fn 0x57BD610) registers "/core-game/players/" as a messenger
// resource prefix, the same mechanism S117 measured working on "/match-history/players/".
//
// ⚠ [S] THE PUSH ITSELF IS UNPROVEN ON THIS RESOURCE. The registration is [M] offline;
// that a push actually triggers the refetch is [I, strong] by analogy with match-history.
// Nobody has ever pushed this resource. Built-in discriminator, and it costs no launch:
// if the push does nothing but an admin socket-drop DOES refetch (measured 4/4), the
// fault is the push, not the channel.
//
// ============================================================================
// WHAT HAPPENS NEXT, IF THE PUSH LANDS — measured, not hoped for
// ============================================================================
//
//	players-fetch -> +391 ms -> GET /core-game/matches/{matchId}
//	              -> + 95 ms -> the client's own /lobby presence flips to "a":"InMatch"
//
// That presence flip is a FREE readout nobody has been using: it is the client telling
// us, on a socket we already own, that it accepted the match.
//
// Then UTravelManager decides. The game ships the mechanism in a cvar description:
// CheatPreventAutoTravelToMatch — "Will prevent the travel manager from automatically
// traveling to a match when the match state changes."
//
// ⚠⚠ AND THE MATCH DOCUMENT CANNOT CHOOSE THE MAP. [M] GameConfig.MapName /
// GameConfig.GameMode do NOT select the client's world — the travel URL is built from
// ConnectionDetails.Address alone, and the only "?game=" literal in the image belongs to
// MovieRenderPipeline. With an EMPTY address the client PARKS LOCALLY -- S62 logged
// `Attempting to travel to Match: Address:` with an empty value, then parked: no map
// loaded and zero NetConnection attempts -- and the world is then chosen by the
// force-open shim reading docs/tutorial-launch-cmd.txt.
// So MapName/GameMode here are DOCUMENTATION of intent, not a lever. Do not "fix" the
// map by editing them.
//
// ============================================================================
// KNOBS — default OFF, and OFF is byte-identical to pre-S135
// ============================================================================
//
//	AGS_ARM_QUEUE=off|arm|empty   off (default) = never write MatchID; the handler is
//	                              unchanged. arm = arm a match. empty = THE CONTROLLED
//	                              NEGATIVE (see below).
//	AGS_ARM_QUEUE_DELAY=8s        joinQueue -> arm delay, so the searching UI is visibly
//	                              real and the retry-vs-accept receipt stays readable.
//	AGS_ARM_QUEUE_QUEUES=bots     comma list of queue ids allowed to arm.
//	AGS_ARM_QUEUE_GAMEMODE=...    override GameConfig.GameMode (documentation only).
//	AGS_ARM_QUEUE_MAP=...         override GameConfig.MapName  (documentation only).
//	AGS_ARM_QUEUE_VERSION=N       pin the served Version, to isolate the monotonic gate.
//
// ★ AGS_ARM_QUEUE=empty IS THE CONTROLLED NEGATIVE AND IT IS THE WHOLE POINT.
// It serves a valid, fully-shaped CoreGamePlayer with an ADVANCING Version and an EMPTY
// MatchID, and pushes exactly as `arm` does. It therefore moves ONE FIELD relative to
// `arm`. Reverting to `off` instead would change the document and the version together
// and be uninterpretable — that is exactly the AGS_PLAYER_RANK=0 mistake S122 recorded:
// "a revert knob that returns to a catch-all changes every field at once."
package interactive

import (
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// armMode is the parsed AGS_ARM_QUEUE value.
type armMode int

const (
	armOff   armMode = iota // never write MatchID (default)
	armReal                 // arm a real match
	armEmpty                // controlled negative: advance Version, leave MatchID empty
)

func armQueueMode() armMode {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("AGS_ARM_QUEUE"))) {
	case "arm", "on", "1", "true":
		return armReal
	case "empty", "control":
		return armEmpty
	default:
		return armOff
	}
}

// armQueueDelay is how long after the FIND MATCH click the match is armed. A delay is
// deliberate, not cosmetic: it keeps S133's free receipt readable. joinQueue fires ONCE
// when accepted and retries every 10–35 s when not, so arming instantly would overlap
// the arming with the accept and make the retry signal ambiguous.
func armQueueDelay() time.Duration {
	if v := strings.TrimSpace(os.Getenv("AGS_ARM_QUEUE_DELAY")); v != "" {
		if d, err := time.ParseDuration(v); err == nil && d >= 0 {
			return d
		}
		log.Printf("interactive: armqueue: bad AGS_ARM_QUEUE_DELAY %q, using 8s", v)
	}
	return 8 * time.Second
}

// armQueueAllowed reports whether this queue id may arm. Defaults to `bots` alone so
// enabling the knob cannot silently arm BREACH, whose gamemode is a 2,215-cell Skylands
// battle royale this project has never loaded.
func armQueueAllowed(queue string) bool {
	list := strings.TrimSpace(os.Getenv("AGS_ARM_QUEUE_QUEUES"))
	if list == "" {
		list = "bots"
	}
	for _, q := range strings.Split(list, ",") {
		if strings.EqualFold(strings.TrimSpace(q), queue) {
			return true
		}
	}
	return false
}

// armTimers guards one pending arm per player so a client's joinQueue RETRY (which is
// the documented rejection symptom, and which we may still see for unrelated reasons)
// cannot stack N arms and push N version bumps.
var (
	armMu     sync.Mutex
	armTimers = map[string]*time.Timer{}
)

// scheduleArm is called from handleJoinQueue. It is a no-op unless AGS_ARM_QUEUE is set
// AND the queue is allowed, so with the knob unset joinQueue behaves exactly as it did
// before this file existed.
func (s *Service) scheduleArm(id, queue string) {
	mode := armQueueMode()
	if mode == armOff {
		return
	}
	if !armQueueAllowed(queue) {
		log.Printf("interactive: armqueue: queue %q not in AGS_ARM_QUEUE_QUEUES; not arming", queue)
		return
	}
	d := armQueueDelay()
	log.Printf("interactive: armqueue: will arm player=%s queue=%q in %s (mode=%v)", id, queue, d, mode)

	armMu.Lock()
	if t, ok := armTimers[id]; ok {
		t.Stop() // a retry replaces the pending arm rather than adding one
	}
	armTimers[id] = time.AfterFunc(d, func() { s.armQueuedMatch(id, queue, mode) })
	armMu.Unlock()
}

// cancelArm drops any pending arm and clears an armed match. Called from leaveQueue so
// CANCEL is a real cancel and the next FIND MATCH starts from a clean state.
//
// ⚠ Clearing MatchID here is what keeps the loop REPEATABLE. S107's recorded failure is
// that once /core-game/players reports a MatchID it does so forever, so the client
// believes it is already in a match and every later START is a silent no-op. The proper
// fix is the unserved POST /core-game/players/{id}/disassociate/{...} (fn 0x57A0EE0);
// until that exists, cancel is the only clear.
func (s *Service) cancelArm(id string) {
	armMu.Lock()
	if t, ok := armTimers[id]; ok {
		t.Stop()
		delete(armTimers, id)
	}
	armMu.Unlock()

	var had bool
	s.store.update(id, func(st *playerState) {
		had = st.MatchID != ""
		st.MatchID = ""
		st.MatchQueue = ""
		// MatchVersion is deliberately NOT reset: it must stay strictly monotonic per
		// player or the next arm's push is at or below the client's cached version and
		// is silently ignored. Monotonicity is the contract; the value is not state.
	})
	if had {
		log.Printf("interactive: armqueue: cleared armed match for player=%s", id)
		s.pushCoreGamePlayer(id, "armqueue-cancel")
	}
}

// armQueuedMatch writes the armed match and pushes the resource.
func (s *Service) armQueuedMatch(id, queue string, mode armMode) {
	armMu.Lock()
	delete(armTimers, id)
	armMu.Unlock()

	var (
		matchID string
		version int64
	)
	s.store.update(id, func(st *playerState) {
		// Strictly monotonic per player. Seeded from the wall clock so it is always
		// ahead of whatever the client cached from an earlier ags run, then +1 per arm.
		next := time.Now().Unix()
		if st.MatchVersion >= next {
			next = st.MatchVersion + 1
		}
		if pin := strings.TrimSpace(os.Getenv("AGS_ARM_QUEUE_VERSION")); pin != "" {
			if v, err := strconv.ParseInt(pin, 10, 64); err == nil {
				next = v
			}
		}
		st.MatchVersion = next
		st.MatchQueue = queue
		if mode == armReal {
			st.MatchID = tutorialMatchID(id)
		} else {
			st.MatchID = "" // the control arm moves the version and nothing else
		}
		// The queue has resolved either way; the client should leave the searching
		// state. (`state` is what carries this on the party document — `inQueue` is a
		// dead key, see store.go.)
		st.InQueue = false
		matchID, version = st.MatchID, st.MatchVersion
	})

	log.Printf("interactive: armqueue: ARMED player=%s queue=%q matchID=%q version=%d mode=%v",
		id, queue, matchID, version, mode)
	s.pushCoreGamePlayer(id, "armqueue")
}

// pushCoreGamePlayer nudges the client to refetch GET /core-game/players/{id}.
//
// ⚠ The version passed MUST be the one the document will actually serve, which is why it
// comes from CoreGamePlayerVersion and is not recomputed here. push.go's gate is
// "pushed > cached": too low is ignored, too high causes an unbounded refetch loop.
func (s *Service) pushCoreGamePlayer(id, label string) {
	if s.notifyResource == nil {
		log.Printf("interactive: armqueue: no resource notifier wired; "+
			"client will not refetch /core-game/players/%s until it reconnects", id)
		return
	}
	v := s.CoreGamePlayerVersion(id)
	if err := s.notifyResource(id, "/core-game/players/"+id, v, label); err != nil {
		log.Printf("interactive: armqueue: push failed for player=%s: %v", id, err)
		return
	}
	log.Printf("interactive: armqueue: pushed /core-game/players/%s version=%d label=%s", id, v, label)
}

// armQueueGameMode / armQueueMap are documentation-only overrides for the match
// document. See the header: they cannot select the client's world.
func armQueueGameMode(def string) string {
	if v := strings.TrimSpace(os.Getenv("AGS_ARM_QUEUE_GAMEMODE")); v != "" {
		return v
	}
	return def
}

func armQueueMap(def string) string {
	if v := strings.TrimSpace(os.Getenv("AGS_ARM_QUEUE_MAP")); v != "" {
		return v
	}
	return def
}
