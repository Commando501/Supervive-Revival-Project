// Package ws is a dependency-free (RFC 6455) WebSocket server, just enough to
// answer the client's lobby/messaging upgrade with a 101 and read/write frames.
//
// Why hand-rolled: the project is zero-deps (stdlib only). net/http has no
// WebSocket support, but it exposes http.Hijacker, which is all we need to take
// over the TCP connection after the HTTP upgrade handshake.
//
// Context: client-config maps the `lobby` service to http://localhost:8080 and
// `messaging` to ws://localhost:8080; the AccelByte/Theorycraft clients connect
// to ws://localhost:8080/lobby/ (and the messenger to its own ws path). Our old
// catch-all answered the GET upgrade with HTTP 200, so the client logged
// "ws upgrade response not 101" and reconnect-looped. Completing the handshake
// stops that loop; logging the first frames reveals the lobby app-protocol so we
// can implement it next.
package ws

import (
	"bufio"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"
)

// rfc6455GUID is the magic value concatenated with Sec-WebSocket-Key to derive
// the Sec-WebSocket-Accept response header.
const rfc6455GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

// IsUpgrade reports whether r is a WebSocket upgrade request.
func IsUpgrade(r *http.Request) bool {
	return tokenHeaderContains(r.Header.Get("Connection"), "upgrade") &&
		strings.EqualFold(r.Header.Get("Upgrade"), "websocket")
}

// Conn is a minimal WebSocket connection over a hijacked TCP socket.
//
// writeMu serializes WriteFrame calls so a goroutine pushing a server-initiated
// notification (e.g. the dedicated-server-stub chapter's matchmaking-notif
// probe in package lobby) doesn't race the read-loop's frame writes (hb echoes,
// reply text). Reads are still single-goroutine (the read loop's responsibility).
type Conn struct {
	c       net.Conn
	br      *bufio.Reader
	writeMu sync.Mutex

	// EnvelopeStart/End are the AccelByte lobby message delimiters the CLIENT
	// asks for in its handshake, via the X-Ab-EnvelopeStart / X-Ab-EnvelopeEnd
	// request headers (literals at .rdata 0x8604890 / 0x86048A8).
	//
	// ★ S117: this is why NOTHING we have ever sent on /lobby was dispatched.
	// The client stores these two markers as FStrings on its Lobby object
	// (+0xA8 / +0xB8) and Lobby::OnMessage's completeness check (.text
	// 0x4b35a80) takes the "no framing" fast path ONLY when BOTH are empty
	// (cmp dword [X+8],1 / jg — an FString ArrayNum <= 1 is empty). Ours are
	// not empty, so every unwrapped frame we sent was logged as
	// "Message fragmented, current content buffer" and buffered forever:
	// 14 Raw Lobby Response -> 14 fragmented -> 0 dispatches, measured.
	EnvelopeStart string
	EnvelopeEnd   string
}

// Opcodes (RFC 6455 §5.2).
const (
	OpContinuation = 0x0
	OpText         = 0x1
	OpBinary       = 0x2
	OpClose        = 0x8
	OpPing         = 0x9
	OpPong         = 0xA
)

// Upgrade performs the server-side handshake and hijacks the connection. It
// echoes the first requested Sec-WebSocket-Protocol (AccelByte clients can
// require the negotiated subprotocol to be reflected back).
func Upgrade(w http.ResponseWriter, r *http.Request) (*Conn, error) {
	key := r.Header.Get("Sec-WebSocket-Key")
	if key == "" {
		return nil, errors.New("ws: missing Sec-WebSocket-Key")
	}
	hj, ok := w.(http.Hijacker)
	if !ok {
		return nil, errors.New("ws: ResponseWriter does not support hijacking")
	}
	conn, brw, err := hj.Hijack()
	if err != nil {
		return nil, fmt.Errorf("ws: hijack: %w", err)
	}

	// Capture the envelope markers BEFORE hijacking loses the request.
	envStart := r.Header.Get("X-Ab-EnvelopeStart")
	envEnd := r.Header.Get("X-Ab-EnvelopeEnd")

	sum := sha1.Sum([]byte(key + rfc6455GUID))
	accept := base64.StdEncoding.EncodeToString(sum[:])

	var b strings.Builder
	b.WriteString("HTTP/1.1 101 Switching Protocols\r\n")
	b.WriteString("Upgrade: websocket\r\n")
	b.WriteString("Connection: Upgrade\r\n")
	b.WriteString("Sec-WebSocket-Accept: " + accept + "\r\n")
	if proto := firstToken(r.Header.Get("Sec-WebSocket-Protocol")); proto != "" {
		b.WriteString("Sec-WebSocket-Protocol: " + proto + "\r\n")
	}
	b.WriteString("\r\n")
	if _, err := conn.Write([]byte(b.String())); err != nil {
		conn.Close()
		return nil, fmt.Errorf("ws: write 101: %w", err)
	}
	return &Conn{c: conn, br: brw.Reader, EnvelopeStart: envStart, EnvelopeEnd: envEnd}, nil
}

// Frame is a decoded WebSocket frame.
type Frame struct {
	Opcode  byte
	Payload []byte
}

// ReadFrame reads one frame. Client→server frames are always masked (RFC 6455
// §5.3); we unmask the payload before returning it.
func (c *Conn) ReadFrame() (Frame, error) {
	var h [2]byte
	if _, err := io.ReadFull(c.br, h[:]); err != nil {
		return Frame{}, err
	}
	opcode := h[0] & 0x0f
	masked := h[1]&0x80 != 0
	length := uint64(h[1] & 0x7f)

	switch length {
	case 126:
		var ext [2]byte
		if _, err := io.ReadFull(c.br, ext[:]); err != nil {
			return Frame{}, err
		}
		length = uint64(binary.BigEndian.Uint16(ext[:]))
	case 127:
		var ext [8]byte
		if _, err := io.ReadFull(c.br, ext[:]); err != nil {
			return Frame{}, err
		}
		length = binary.BigEndian.Uint64(ext[:])
	}

	var mask [4]byte
	if masked {
		if _, err := io.ReadFull(c.br, mask[:]); err != nil {
			return Frame{}, err
		}
	}
	payload := make([]byte, length)
	if _, err := io.ReadFull(c.br, payload); err != nil {
		return Frame{}, err
	}
	if masked {
		for i := range payload {
			payload[i] ^= mask[i%4]
		}
	}
	return Frame{Opcode: opcode, Payload: payload}, nil
}

// WriteFrame writes a single (FIN) server→server frame, unmasked per spec.
// Serialized via writeMu so concurrent writers (e.g. the read loop's hb echo
// + a probe-push goroutine) don't interleave on the underlying TCP socket.
func (c *Conn) WriteFrame(opcode byte, payload []byte) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	var hdr []byte
	b0 := byte(0x80) | (opcode & 0x0f) // FIN + opcode
	n := len(payload)
	switch {
	case n < 126:
		hdr = []byte{b0, byte(n)}
	case n < 1<<16:
		hdr = []byte{b0, 126, byte(n >> 8), byte(n)}
	default:
		hdr = make([]byte, 10)
		hdr[0] = b0
		hdr[1] = 127
		binary.BigEndian.PutUint64(hdr[2:], uint64(n))
	}
	if _, err := c.c.Write(hdr); err != nil {
		return err
	}
	_, err := c.c.Write(payload)
	return err
}

// WriteText sends a text frame, wrapped in the client's negotiated envelope.
//
// ★ S117 — THIS IS THE FIX FOR "/lobby frames are never dispatched". The client
// asks for delimiters in its handshake (measured: X-Ab-EnvelopeStart "LbS",
// X-Ab-EnvelopeEnd "LbE" on /lobby) and its Lobby::OnMessage buffers anything
// that does not carry them, forever. Wrapping here is automatically correct
// per-socket: the messenger negotiates EMPTY markers, so this is a no-op there,
// which is exactly why the messenger probes worked while every /lobby frame in
// this project's history was silently swallowed.
func (c *Conn) WriteText(s string) error {
	return c.WriteFrame(OpText, []byte(c.EnvelopeStart+s+c.EnvelopeEnd))
}

// WriteTextRaw sends a text frame with NO envelope. For probes that need to put
// exact bytes on the wire (e.g. re-testing the unwrapped form).
func (c *Conn) WriteTextRaw(s string) error { return c.WriteFrame(OpText, []byte(s)) }

// Pong replies to a ping with the same payload.
func (c *Conn) Pong(payload []byte) error { return c.WriteFrame(OpPong, payload) }

// Close sends a close frame and closes the socket.
func (c *Conn) Close() error {
	_ = c.WriteFrame(OpClose, nil)
	return c.c.Close()
}

// Drop closes the underlying connection WITHOUT sending a WS close frame — an
// abrupt disconnect the client treats like a dropped socket, exactly like its own
// heartbeat-watchdog teardown. The lobby service uses this to force a fast
// messenger reconnect (which drives the client's party state-resync + apply, the
// S85 avatar-switch latency fix). Safe to call from another goroutine while
// ReadFrame is blocked: net.Conn.Close unblocks the pending read.
func (c *Conn) Drop() error { return c.c.Close() }

// SetReadDeadline forwards to the underlying net.Conn. Used by the lobby
// service to wake a blocked ReadFrame on a timer so it can push a proactive
// server-initiated heartbeat (the Theorycraft messenger socket's watchdog
// trips ~60s after connect even though we echo "hb" on receive).
func (c *Conn) SetReadDeadline(t time.Time) error { return c.c.SetReadDeadline(t) }

func tokenHeaderContains(header, want string) bool {
	for _, part := range strings.Split(header, ",") {
		if strings.EqualFold(strings.TrimSpace(part), want) {
			return true
		}
	}
	return false
}

func firstToken(header string) string {
	if header == "" {
		return ""
	}
	return strings.TrimSpace(strings.Split(header, ",")[0])
}
