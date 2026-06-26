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
type Conn struct {
	c  net.Conn
	br *bufio.Reader
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
	return &Conn{c: conn, br: brw.Reader}, nil
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
func (c *Conn) WriteFrame(opcode byte, payload []byte) error {
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

// WriteText sends a text frame.
func (c *Conn) WriteText(s string) error { return c.WriteFrame(OpText, []byte(s)) }

// Pong replies to a ping with the same payload.
func (c *Conn) Pong(payload []byte) error { return c.WriteFrame(OpPong, payload) }

// Close sends a close frame and closes the socket.
func (c *Conn) Close() error {
	_ = c.WriteFrame(OpClose, nil)
	return c.c.Close()
}

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
