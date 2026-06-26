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
	"sync"
	"time"
)

// Logger writes a human-readable trace of every request to a file and stdout.
type Logger struct {
	mu  sync.Mutex
	f   *os.File
	seq int
}

// NewLogger opens (appending) the capture log at path.
func NewLogger(path string) (*Logger, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return nil, err
	}
	return &Logger{f: f}, nil
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

		l.mu.Lock()
		l.f.WriteString(b.String())
		l.f.Sync()
		l.mu.Unlock()

		// Compact line to stdout for live watching.
		fmt.Printf("#%d %s %s -> %d\n", n, r.Method, r.URL.Path, rec.status)
	})
}

// Event writes a timestamped one-off line to the capture log (and stdout). Used
// for things that aren't a single request/response — e.g. WebSocket frames that
// arrive on a long-lived hijacked connection.
func (l *Logger) Event(format string, args ...any) {
	line := fmt.Sprintf("\n* %s  %s\n", time.Now().Format("15:04:05.000"), fmt.Sprintf(format, args...))
	l.mu.Lock()
	l.f.WriteString(line)
	l.f.Sync()
	l.mu.Unlock()
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
