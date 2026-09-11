package pingecho

import (
	"encoding/binary"
	"net"
	"testing"
	"time"
)

// These tests stand in for the game client. They build a byte-exact UE ping packet and then run
// the CLIENT'S OWN acceptance checks against whatever comes back, so a pass means "the real
// client would have accepted this reply" rather than "our server sent something".
//
// Everything here is transcribed from UE 5.4
// Engine/Source/Runtime/Online/ICMP/Private/{UDPPing.cpp,Icmp.cpp} — see the package comment.

const (
	pingDataHigh = 0xaaaaaaaa
	pingDataLow  = 0xbbbbbbbb

	offID       = 0
	offSequence = 2
	offChecksum = 4
	offTimeCode = 6
	offMagic    = 14
)

// ueChecksum is Icmp.cpp:25 CalculateChecksum -- the 16-bit one's-complement sum, summed over
// NATIVE-endian uint16s (UE reinterpret_casts the buffer, so it is host order by construction).
func ueChecksum(b []byte) uint16 {
	sum := 0
	i := 0
	for ; i+1 < len(b); i += 2 {
		sum += int(binary.LittleEndian.Uint16(b[i:]))
	}
	if i < len(b) {
		sum += int(b[i])
	}
	sum = (sum >> 16) + (sum & 0xFFFF)
	sum += sum >> 16
	return uint16(^sum)
}

// buildClientPacket reproduces UDPEchoImpl's send path exactly.
func buildClientPacket(id, seq uint16, timeCode uint64) []byte {
	p := make([]byte, StockUEPacketSize)
	binary.BigEndian.PutUint16(p[offID:], id)         // HtoNS
	binary.BigEndian.PutUint16(p[offSequence:], seq)  // HtoNS
	binary.LittleEndian.PutUint16(p[offChecksum:], 0) // zeroed before checksumming
	// ⚠ TimeCode is written with NO byte swap (TimeCodeStart[0] = TimeCode), i.e. host order.
	binary.LittleEndian.PutUint64(p[offTimeCode:], timeCode)
	binary.BigEndian.PutUint32(p[offMagic:], pingDataHigh)   // HtoNL
	binary.BigEndian.PutUint32(p[offMagic+4:], pingDataLow)  // HtoNL
	binary.LittleEndian.PutUint16(p[offChecksum:], ueChecksum(p))
	return p
}

// acceptsAsClient runs UDPEchoImpl's reply validation. Returns "" on accept, else the reason.
func acceptsAsClient(t *testing.T, reply []byte, sentID, sentSeq uint16, sentTimeCode uint64) string {
	t.Helper()
	if len(reply) < MinPacketSize {
		return "BytesRead != ResultPacketSize"
	}
	// checksum: stash, zero, recompute over the whole packet, compare
	recv := binary.LittleEndian.Uint16(reply[offChecksum:])
	scratch := append([]byte(nil), reply...)
	binary.LittleEndian.PutUint16(scratch[offChecksum:], 0)
	if local := ueChecksum(scratch); recv != local {
		return "checksum mismatch"
	}
	// magic numbers, compared WITHOUT a byte swap against host constants
	if binary.LittleEndian.Uint32(reply[offMagic:]) != swap32(pingDataHigh) ||
		binary.LittleEndian.Uint32(reply[offMagic+4:]) != swap32(pingDataLow) {
		return "magic number mismatch"
	}
	if binary.BigEndian.Uint16(reply[offID:]) != sentID {
		return "id mismatch"
	}
	if binary.BigEndian.Uint16(reply[offSequence:]) != sentSeq {
		return "sequence mismatch"
	}
	if binary.LittleEndian.Uint64(reply[offTimeCode:]) != sentTimeCode {
		return "timecode altered -- DeltaTime would be wrong"
	}
	return ""
}

func swap32(v uint32) uint32 {
	b := make([]byte, 4)
	binary.BigEndian.PutUint32(b, v)
	return binary.LittleEndian.Uint32(b)
}

func dial(t *testing.T, s *Server) *net.UDPConn {
	t.Helper()
	c, err := net.DialUDP("udp", nil, s.Addr())
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	t.Cleanup(func() { c.Close() })
	_ = c.SetDeadline(time.Now().Add(3 * time.Second))
	return c
}

// TestEchoIsAcceptedByClientValidation is the headline: a real UE packet in, a reply out that
// passes every check UDPEchoImpl performs.
func TestEchoIsAcceptedByClientValidation(t *testing.T) {
	s, err := Start("127.0.0.1:0")
	if err != nil {
		t.Fatalf("start: %v", err)
	}
	defer s.Close()

	const id, seq = 0x1234, 7
	tc := uint64(0x0011223344556677)
	c := dial(t, s)

	if _, err := c.Write(buildClientPacket(id, seq, tc)); err != nil {
		t.Fatalf("write: %v", err)
	}
	buf := make([]byte, 128)
	n, err := c.Read(buf)
	if err != nil {
		t.Fatalf("no reply (the client would log 'Could not ping target host'): %v", err)
	}
	if reason := acceptsAsClient(t, buf[:n], id, seq, tc); reason != "" {
		t.Fatalf("client would REJECT the reply: %s", reason)
	}
	if got := s.Echoed(); got != 1 {
		t.Errorf("Echoed() = %d, want 1", got)
	}
}

// TestChecksumHelperMatchesUE is the positive control for the TEST'S OWN instrument. If our
// checksum were wrong, the test above could pass against a broken server (both sides sharing the
// same mistake), so pin it against the property UE relies on: a packet carrying its correct
// checksum sums, with the field zeroed, back to that same value.
func TestChecksumHelperMatchesUE(t *testing.T) {
	p := buildClientPacket(0xBEEF, 3, 0x99)
	stored := binary.LittleEndian.Uint16(p[offChecksum:])
	scratch := append([]byte(nil), p...)
	binary.LittleEndian.PutUint16(scratch[offChecksum:], 0)
	if got := ueChecksum(scratch); got != stored {
		t.Fatalf("checksum helper inconsistent: stored %#04x, recomputed %#04x", stored, got)
	}
	if stored == 0 {
		t.Error("checksum is 0 -- suspicious; the helper may not be summing anything")
	}
}

// TestOutOfRangeDatagramsAreDropped is the NEGATIVE CONTROL: the server must be making a size
// decision, not blindly bouncing every datagram, or it would be a general UDP reflector.
//
// ⚠ This test originally asserted an EXACT 22-byte gate and passed -- while the real game, which
// sends 30 bytes, was being silently dropped. The test agreed with the stock engine source and
// the source did not describe this build. Widening the gate is what fixed the game; the control
// is kept, re-aimed at the actual bounds. **A green test against the wrong spec is still red.**
func TestOutOfRangeDatagramsAreDropped(t *testing.T) {
	s, err := Start("127.0.0.1:0")
	if err != nil {
		t.Fatalf("start: %v", err)
	}
	defer s.Close()

	for _, tc := range []struct {
		name string
		size int
	}{
		{"too short", MinPacketSize - 1},
		{"too long", MaxPacketSize + 1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c := dial(t, s)
			_ = c.SetDeadline(time.Now().Add(400 * time.Millisecond))
			if _, err := c.Write(make([]byte, tc.size)); err != nil {
				t.Fatalf("write: %v", err)
			}
			buf := make([]byte, 256)
			if n, err := c.Read(buf); err == nil {
				t.Fatalf("server echoed a %d-byte datagram; it must drop those", n)
			}
		})
	}
	if s.Echoed() != 0 {
		t.Errorf("Echoed() = %d, want 0", s.Echoed())
	}
	if s.Dropped() != 2 {
		t.Errorf("Dropped() = %d, want 2", s.Dropped())
	}
}

// TestRealClientSizeIsEchoed pins the actual measured size of THIS build's ping (30 bytes), so a
// future tightening of the gate back toward the stock 22 fails here instead of in the game.
func TestRealClientSizeIsEchoed(t *testing.T) {
	const observedClientSize = 30
	s, err := Start("127.0.0.1:0")
	if err != nil {
		t.Fatalf("start: %v", err)
	}
	defer s.Close()

	c := dial(t, s)
	pkt := make([]byte, observedClientSize)
	for i := range pkt {
		pkt[i] = byte(i)
	}
	if _, err := c.Write(pkt); err != nil {
		t.Fatalf("write: %v", err)
	}
	buf := make([]byte, 256)
	n, err := c.Read(buf)
	if err != nil {
		t.Fatalf("the %d-byte size the real client sends was not echoed: %v", observedClientSize, err)
	}
	if n != observedClientSize || string(buf[:n]) != string(pkt) {
		t.Fatalf("echo not verbatim: got %d bytes, want %d identical", n, observedClientSize)
	}
}

// TestTimeCodeIsPreservedByteForByte guards the subtlest failure: rewriting the TimeCode would
// still checksum fine and still pass id/seq/magic, but DeltaTime is computed from it, so the
// reported latency would be garbage (or the reply rejected by the 0 <= dt < 60000s bound).
func TestTimeCodeIsPreservedByteForByte(t *testing.T) {
	s, err := Start("127.0.0.1:0")
	if err != nil {
		t.Fatalf("start: %v", err)
	}
	defer s.Close()

	tc := uint64(0xFEDCBA9876543210)
	c := dial(t, s)
	if _, err := c.Write(buildClientPacket(1, 1, tc)); err != nil {
		t.Fatalf("write: %v", err)
	}
	buf := make([]byte, 128)
	if _, err := c.Read(buf); err != nil {
		t.Fatalf("no reply: %v", err)
	}
	if got := binary.LittleEndian.Uint64(buf[offTimeCode:]); got != tc {
		t.Fatalf("TimeCode changed: sent %#016x, got %#016x", tc, got)
	}
}

func TestPingPortDefaultsTo443(t *testing.T) {
	if got := PingPort(); got != 443 {
		t.Errorf("PingPort() = %d, want 443 (must match the served FRegionRoute.PingPort)", got)
	}
	t.Setenv("AGS_PING_PORT", "7777")
	if got := PingPort(); got != 7777 {
		t.Errorf("PingPort() with env = %d, want 7777", got)
	}
	t.Setenv("AGS_PING_PORT", "garbage")
	if got := PingPort(); got != 443 {
		t.Errorf("PingPort() with junk = %d, want the 443 fallback", got)
	}
}
