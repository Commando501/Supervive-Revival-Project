// Package capture provides request-logging middleware and a catch-all stub.
//
// Because the official SUPERVIVE servers are dead we cannot sniff a working
// session. Instead we redirect the client at our server and learn the protocol
// from what it sends: every request (matched or not) is logged to docs and
// stdout, and any route we have not implemented yet returns an empty-success
// JSON stub so the client keeps going and reveals its *next* call.
package capture

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// Logger writes a human-readable trace of every request to a file and stdout.
type Logger struct {
	mu   sync.Mutex
	f    *os.File
	seq  int
	path string
	size int64 // current file size, guarded by mu
	max  int64 // rotate when a write would push size past this; 0 = no cap
}

// NewLogger opens the capture log at path, starting it FRESH each launch:
// the previous run's log is kept once as path+".prev" instead of appended to.
// Appending across launches let the file reach 12.9 GB (2026-07-06), too big
// to grep or read, which defeats its purpose. maxBytes bounds the file
// mid-run the same way (rotate to .prev, continue fresh); 0 disables the cap.
func NewLogger(path string, maxBytes int64) (*Logger, error) {
	rotate(path)
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return nil, err
	}
	return &Logger{f: f, path: path, max: maxBytes}, nil
}

// rotate preserves path as path+".prev" (replacing any older .prev) so the
// most recent prior traffic stays available after a fresh start.
func rotate(path string) {
	if fi, err := os.Stat(path); err != nil || fi.Size() == 0 {
		return
	}
	os.Remove(path + ".prev")
	os.Rename(path, path+".prev")
}

// write appends s to the log, rotating first if it would exceed the cap.
// Rotation keeps the full log as .prev rather than truncating in place: the
// traffic just captured is usually exactly what an investigation needs, so
// disk use is bounded at ~2x the cap instead of losing it.
func (l *Logger) write(s string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.max > 0 && l.size+int64(len(s)) > l.max {
		l.rotateLocked()
	}
	if l.f == nil {
		return
	}
	n, _ := l.f.WriteString(s)
	l.size += int64(n)
	l.f.Sync()
}

func (l *Logger) rotateLocked() {
	l.f.Close()
	rotate(l.path)
	f, err := os.OpenFile(l.path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		// stdout still carries the compact trace; don't kill the server over it
		fmt.Printf("capture: reopen after rotation failed, file logging disabled: %v\n", err)
		l.f = nil
		return
	}
	l.f = f
	l.size = 0
	n, _ := fmt.Fprintf(l.f, "* %s  rotated at size cap; earlier entries in %s.prev\n",
		time.Now().Format("15:04:05.000"), filepath.Base(l.path))
	l.size += int64(n)
}

// Middleware wraps next, logging method/path/query/headers/body and the
// response status for each request.
func (l *Logger) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body []byte
		if r.Body != nil {
			body, _ = io.ReadAll(io.LimitReader(r.Body, 1<<20))
			r.Body = io.NopCloser(bytes.NewReader(body))
		}

		rec := &statusRecorder{ResponseWriter: w, status: 200}
		start := time.Now()
		next.ServeHTTP(rec, r)
		dur := time.Since(start)

		l.mu.Lock()
		l.seq++
		n := l.seq
		l.mu.Unlock()

		var b bytes.Buffer
		fmt.Fprintf(&b, "\n#%d %s  %s %s\n", n, start.Format("15:04:05.000"), r.Method, r.URL.RequestURI())
		fmt.Fprintf(&b, "    -> %d  (%s)\n", rec.status, dur.Round(time.Millisecond))
		for k, vs := range r.Header {
			if isInterestingHeader(k) {
				for _, v := range vs {
					fmt.Fprintf(&b, "    %s: %s\n", k, v)
				}
			}
		}
		if len(body) > 0 {
			fmt.Fprintf(&b, "    body: %s\n", string(body))
		}

		l.write(b.String())

		// Compact line to stdout for live watching.
		fmt.Printf("#%d %s %s -> %d\n", n, r.Method, r.URL.Path, rec.status)
	})
}

// Event writes a timestamped one-off line to the capture log (and stdout). Used
// for things that aren't a single request/response — e.g. WebSocket frames that
// arrive on a long-lived hijacked connection.
func (l *Logger) Event(format string, args ...any) {
	line := fmt.Sprintf("\n* %s  %s\n", time.Now().Format("15:04:05.000"), fmt.Sprintf(format, args...))
	l.write(line)
	fmt.Print(line)
}

func isInterestingHeader(k string) bool {
	switch k {
	case "Authorization", "Content-Type", "User-Agent", "X-Ab-Info", "Accept",
		"X-Theorycraft-Clientversion", "Game-Client-Version", "X-Theorycraft-Clientversion-Override":
		return true
	}
	return false
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.status = code
	s.ResponseWriter.WriteHeader(code)
}

// Hijack lets WebSocket upgrades take over the connection through the logging
// middleware. Without this, the wrapped ResponseWriter would hide the
// underlying http.Hijacker and the upgrade would fail.
func (s *statusRecorder) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	hj, ok := s.ResponseWriter.(http.Hijacker)
	if !ok {
		return nil, nil, fmt.Errorf("capture: underlying ResponseWriter is not an http.Hijacker")
	}
	s.status = 101 // reflect the switch-protocols in the request log
	return hj.Hijack()
}

// StubHandler answers any otherwise-unmatched route with an empty-success JSON
// object so the client continues. Marked clearly in the log via the middleware.
func StubHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("{}"))
}
