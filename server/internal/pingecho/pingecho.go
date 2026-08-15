// Package pingecho implements the UDP echo responder that UE's ICMP module pings to measure
// region latency — the last missing piece of the FK-5 latency pipeline (S121, 2026-08-15).
//
// WHY THIS EXISTS
// ---------------
// `GET /core-game/regions` hands the client an FRegionRoute containing PingHost/PingPort.
// ULatencyManager creates one ULatencyMeasurer per route and calls FIcmp::UDPEcho against that
// address every ~30 s. With nothing listening the client logs, five times per cycle:
//
//	LogLatencyManager: Warning: Could not ping target host: 127.0.0.1:443. Result: 4
//
// and the menu shows "— ms" forever. This answers those pings so a real number appears.
//
// ⚠ It is a UDP ECHO, not ICMP. UE's own diagnostics say "EPingType::ICMP should not specify a
// port number", and this path takes PingAddress + PingPort — so a port implies UDP. Nothing here
// needs raw sockets or admin rights, which is the whole reason this is cheap.
//
// THE PROTOCOL — [M], read from the shipped engine source, not inferred
// --------------------------------------------------------------------
// UE 5.4 `Engine/Source/Runtime/Online/ICMP/Private/UDPPing.cpp`, `UDPEchoImpl` (the SINGLE-echo
// path; `UDPEchoMany` is a separate implementation in the same file with a compatible layout):
//
//	PayloadSize = 4 * sizeof(uint32) = 16
//	PacketSize  = sizeof(FUDPPingHeader) + PayloadSize = 6 + 16 = 22
//
//	off  0  uint16 Id          HtoNS(pid)
//	off  2  uint16 Sequence    HtoNS(seq)
//	off  4  uint16 Checksum    CalculateChecksum(whole 22B with this field zeroed)
//	off  6  uint64 TimeCode    FPlatformTime::Cycles64()  — HOST byte order, never swapped
//	off 14  uint32 PingDataHigh = HtoNL(0xaaaaaaaa)
//	off 18  uint32 PingDataLow  = HtoNL(0xbbbbbbbb)
//
// ★★ A VERBATIM ECHO SATISFIES EVERY ACCEPTANCE CONDITION, so this responder deliberately does
// NOT parse or rebuild the packet. All six client-side checks are byte-preserving:
//
//  1. BytesRead == 22                                   -> echo the same length
//  2. checksum: zero the field, recompute over 22 B, compare to the value that arrived
//     -> identical bytes give an identical result, so we never compute a checksum at all
//  3. MagicNumber[0]==0xaaaaaaaa && [1]==0xbbbbbbbb      -> preserved
//     (cute detail: both constants are byte-order palindromes, so the missing NtoHL is moot)
//  4. Id == SentId && Sequence == SentSeq  (after NtoHS) -> preserved
//  5. DeltaTime from the echoed TimeCode in [0, 60000s)  -> preserved; the CLIENT supplies the
//     clock, so we must NOT touch those 8 bytes. Rewriting them would produce a wild latency.
//  6. Result.ReplyFrom == Result.ResolvedAddress         -> the reply must come FROM the address
//     the client sent TO. A single socket bound to that addr:port answers from it automatically;
//     binding 0.0.0.0 on a multi-homed host could reply from a different source IP and fail
//     this check silently. Hence AGS_PING_ADDR defaults to an explicit 127.0.0.1.
//
// ⇒ Rebuilding the packet would add five ways to get it wrong and zero benefit. Echo the bytes.
//
// ⚠ Size discipline: datagrams that are not exactly 22 bytes are counted and dropped, not echoed.
// A bare echo of arbitrary UDP would make this a (tiny) reflector; the length check keeps it
// answering only the thing it is for. Loopback-only by default for the same reason.
package pingecho

import (
	"log"
	"net"
	"os"
	"sync/atomic"
	"time"
)

// StockUEPacketSize is what UE 5.4's stock UDPEchoImpl builds: FUDPPingHeader (6) +
// PayloadSize (4*sizeof(uint32) = 16) = 22.
//
// ⚠⚠ THE SHIPPING CLIENT DOES NOT SEND 22 — IT SENDS 30. [M] Measured from the live game:
//
//	[pingecho] dropped 30-byte datagram from 127.0.0.1:58540 (want 22)
//
// So this build's engine differs from the stock source. That is exactly why this responder ECHOES
// VERBATIM instead of parsing: the reply is correct at any layout, and the only thing that had to
// change was my own size gate. An exact-22 check — which the stock source appears to justify —
// silently dropped every real ping while a hand-written 22-byte probe sailed through, i.e. the
// test passed and the game still failed.
//
// ⇒ Read the engine source for the SHAPE of the protocol, but let the wire tell you the SIZE.
const StockUEPacketSize = 22

// Accepted datagram sizes. Wide enough to cover engine variations (22 stock, 30 in this build),
// narrow enough that this cannot be used as a general UDP reflector.
const (
	MinPacketSize = 8
	MaxPacketSize = 128
)

// Server is a running echo responder.
type Server struct {
	conn    *net.UDPConn
	echoed  atomic.Uint64
	dropped atomic.Uint64
}

// Addr reports the bound address (useful when the port was auto-assigned in tests).
func (s *Server) Addr() *net.UDPAddr { return s.conn.LocalAddr().(*net.UDPAddr) }

// Echoed / Dropped are counters for the admin panel and for tests.
func (s *Server) Echoed() uint64  { return s.echoed.Load() }
func (s *Server) Dropped() uint64 { return s.dropped.Load() }

// Close stops the responder.
func (s *Server) Close() error { return s.conn.Close() }

// Start binds addr ("host:port") and serves echoes until Close.
//
// Returns the Server so callers can read counters; the goroutine exits when conn is closed.
func Start(addr string) (*Server, error) {
	ua, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return nil, err
	}
	conn, err := net.ListenUDP("udp", ua)
	if err != nil {
		return nil, err
	}
	s := &Server{conn: conn}
	go s.loop()
	return s, nil
}

func (s *Server) loop() {
	buf := make([]byte, 512) // generous: anything != PacketSize is dropped anyway
	var loggedFirst, loggedShape bool
	for {
		n, from, err := s.conn.ReadFromUDP(buf)
		if err != nil {
			return // closed
		}
		if n < MinPacketSize || n > MaxPacketSize {
			// Outside any plausible ping. Counted so a silent mismatch is visible rather than
			// mysterious — if pings arrive but nothing echoes, this counter is the tell.
			if d := s.dropped.Add(1); d <= 3 {
				log.Printf("[pingecho] dropped %d-byte datagram from %s (outside %d..%d)",
					n, from, MinPacketSize, MaxPacketSize)
			}
			continue
		}
		// One-time hex dump of the first packet actually seen. This is how the 30-vs-22 size
		// discrepancy was caught, and it makes the real wire format re-checkable from the log
		// instead of trusted from the engine source.
		if !loggedShape {
			loggedShape = true
			log.Printf("[pingecho] first ping is %d bytes: %x", n, buf[:n])
			if n != StockUEPacketSize {
				log.Printf("[pingecho] NOTE: stock UE 5.4 UDPEchoImpl builds %d bytes; this build "+
					"sends %d. Echoing verbatim, which is layout-independent.", StockUEPacketSize, n)
			}
		}
		// VERBATIM echo. Do not parse, do not rebuild, do not touch the TimeCode.
		if _, err := s.conn.WriteToUDP(buf[:n], from); err != nil {
			continue
		}
		c := s.echoed.Add(1)
		if !loggedFirst {
			loggedFirst = true
			// The receipt worth grepping for: this is the moment "— ms" can become a number.
			log.Printf("[pingecho] first echo -> %s (%d bytes); latency should now resolve", from, n)
		} else if c%50 == 0 {
			log.Printf("[pingecho] %d echoes (last from %s)", c, from)
		}
	}
}

// StartFromEnv starts the responder using the same knobs the regions payload uses, so the served
// PingHost/PingPort and the listener cannot drift apart.
//
//	AGS_PING_ADDR  listen address           (default 127.0.0.1)
//	AGS_PING_PORT  listen + served port     (default 443)
//	AGS_PING_ECHO=0 disables it entirely — the measured-broken control arm, which reproduces
//	                "Could not ping target host … Result: 4" and the "— ms" row on demand.
//
// A bind failure is logged and tolerated: the responder is an enhancement, and taking the whole
// backend down because UDP 443 is busy would be a bad trade.
func StartFromEnv() *Server {
	if os.Getenv("AGS_PING_ECHO") == "0" {
		log.Printf("[pingecho] disabled (AGS_PING_ECHO=0); expect 'Could not ping target host' and '— ms'")
		return nil
	}
	host := envOr("AGS_PING_ADDR", "127.0.0.1")
	port := envOr("AGS_PING_PORT", "443")
	addr := net.JoinHostPort(host, port)
	s, err := Start(addr)
	if err != nil {
		log.Printf("[pingecho] WARNING: could not bind UDP %s: %v -- region latency will stay '— ms'", addr, err)
		return nil
	}
	log.Printf("[pingecho] UDP echo responder on %s (UE ICMP-module ping, %d..%d byte datagrams)", addr, MinPacketSize, MaxPacketSize)
	return s
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

// PingPort reports the port the regions payload should advertise, so handleCoreGameRegions and
// this listener always agree. Kept here rather than duplicated in the handler.
func PingPort() int {
	p := envOr("AGS_PING_PORT", "443")
	n := 0
	for _, c := range p {
		if c < '0' || c > '9' {
			return 443
		}
		n = n*10 + int(c-'0')
	}
	if n <= 0 || n > 65535 {
		return 443
	}
	return n
}

// unused, but documents the cadence for anyone reading: UE re-pings every ~29.75 s + jitter,
// and ULatencyMeasurer averages 5 samples before it reports a number.
var _ = time.Second
