// Command ags is the SUPERVIVE Revival community backend.
//
// It impersonates the backend services the game client talks to after the
// official servers were shut down:
//   - AccelByte Gaming Services (IAM/platform/basic) on plain HTTP :8080,
//     reached via the client's -ini: AccelByte BaseUrl override.
//   - Theorycraft's own "project Loki" services (client-config + the Steam
//     account/auth host) on HTTPS :443, reached by redirecting their hostnames
//     to 127.0.0.1 via the hosts file. The TLS cert is appended to the game's
//     libcurl CA bundle so verification still passes.
//
// Unimplemented routes return an empty-success stub and every request is logged
// to docs/capture.log so the protocol can be grown until the client reaches the
// main menu.
package main

import (
	"crypto/tls"
	"flag"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"

	"supervive-revival/server/internal/admin"
	"supervive-revival/server/internal/capture"
	"supervive-revival/server/internal/iam"
	"supervive-revival/server/internal/interactive"
	"supervive-revival/server/internal/lobby"
	"supervive-revival/server/internal/loki"
	"supervive-revival/server/internal/menu"
	"supervive-revival/server/internal/ws"
	"supervive-revival/server/internal/tlscert"
	"supervive-revival/server/internal/token"
)

func main() {
	httpAddr := flag.String("http", ":8080", "plain HTTP listen address (AccelByte)")
	httpsAddr := flag.String("https", ":443", "HTTPS listen address (Theorycraft hosts)")
	logPath := flag.String("log", filepath.Join("docs", "capture.log"), "capture log path (starts fresh each launch; previous run kept as .prev)")
	logMaxMB := flag.Int64("log-max-mb", 256, "capture log size cap in MB; at the cap it rotates to .prev and continues fresh (0 = unlimited)")
	certDir := flag.String("certs", "certs", "directory for the generated TLS cert/key")
	menuConfig := flag.String("config", "", "optional JSON config for menu/store content (see configs/store.example.json); empty defaults to state/menu-config.json (the admin panel's save target)")
	adminAddr := flag.String("admin", "127.0.0.1:9210", "admin panel listen address (loopback-only guard applies); empty disables")
	flag.Parse()

	// Load the operator config (heroes/store SKUs/prices) over the built-in defaults.
	// A missing/invalid file leaves the defaults in place (logged). With no -config
	// we default to state/menu-config.json — the file the admin panel persists to —
	// so panel edits survive the launch script's rebuild+restart (the script passes
	// no -config and runs ags with cwd=server/, same place state/interactive.json
	// already lives). 2026-07-08.
	if *menuConfig == "" {
		*menuConfig = filepath.Join("state", "menu-config.json")
	}
	menu.Load(*menuConfig)

	if err := os.MkdirAll(filepath.Dir(*logPath), 0o755); err != nil {
		log.Fatalf("log dir: %v", err)
	}

	signer, err := token.NewSigner()
	if err != nil {
		log.Fatalf("signer: %v", err)
	}

	logger, err := capture.NewLogger(*logPath, *logMaxMB<<20)
	if err != nil {
		log.Fatalf("capture log: %v", err)
	}

	mux := http.NewServeMux()
	iam.New(signer).Register(mux)
	loki.New().Register(mux)
	menu.New().Register(mux)
	interSvc := interactive.New()
	interSvc.Register(mux)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("ok")) })

	// Catch-all: WebSocket upgrades (lobby/messaging) get a real handshake +
	// frame logging; everything else gets the empty-success stub. Routing here
	// (rather than a fixed /lobby path) also captures the messenger's ws path,
	// whatever it turns out to be.
	lobbySvc := lobby.New(logger)
	// On a loadout change, drop the player's messenger socket so the client reconnects
	// and re-applies its party promptly (the S85 avatar-switch latency fix — the client
	// applies the party only on a messenger-reconnect resync, not on HTTP polls).
	interSvc.SetPartyDirtyNotifier(lobbySvc.MarkDirty)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if ws.IsUpgrade(r) {
			lobbySvc.Handle(w, r)
			return
		}
		capture.StubHandler(w, r)
	})

	handler := logger.Middleware(mux)

	log.Printf("SUPERVIVE Revival AGS backend")
	log.Printf("  capture log: %s", *logPath)

	// Admin control panel (2026-07-08): its OWN mux + listener so nothing can
	// collide with an impersonated client route, loopback-bound by default and
	// double-guarded (admin.Guard rejects non-loopback peers even if -admin is
	// rebound wide). Runs outside the capture middleware so panel traffic never
	// pollutes docs/capture.log.
	if *adminAddr != "" {
		adminMux := http.NewServeMux()
		admin.New(interSvc).Register(adminMux)
		handler := admin.Guard(adminMux)
		// Bind BOTH loopback stacks when the host is loopback/localhost. Browsers
		// resolve `localhost` to IPv6 ::1 first on Windows, but a single
		// 127.0.0.1 listener only answers IPv4 — so `http://localhost:9210`
		// connection-refuses every fetch and the panel shows "Can't reach the ags
		// backend" while curl (which falls back to IPv4) works. Listening on 127.0.0.1
		// AND [::1] makes localhost/127.0.0.1/::1 all work (2026-07-10 fix). A
		// non-loopback -admin (operator opted into wider binding) uses the single
		// addr as given; the Guard still rejects non-loopback peers.
		for _, addr := range adminListenAddrs(*adminAddr) {
			go func(addr string) {
				log.Printf("  ADMIN  panel on http://%s/", addr)
				if err := http.ListenAndServe(addr, handler); err != nil {
					log.Printf("admin %s: %v (this listener disabled)", addr, err)
				}
			}(addr)
		}
	}

	// HTTPS listener for the hijacked Theorycraft hostnames.
	cert, crtPath, err := tlscert.EnsureCert(*certDir)
	if err != nil {
		log.Fatalf("tls cert: %v", err)
	}
	log.Printf("  TLS cert (append to game cacert.pem): %s", crtPath)
	go func() {
		srv := &http.Server{
			Addr:      *httpsAddr,
			Handler:   handler,
			TLSConfig: &tls.Config{Certificates: []tls.Certificate{cert}},
		}
		log.Printf("  HTTPS  listening on %s", *httpsAddr)
		if err := srv.ListenAndServeTLS("", ""); err != nil {
			log.Fatalf("https: %v", err)
		}
	}()

	// HTTP listener for AccelByte (BaseUrl=http://localhost:8080).
	log.Printf("  HTTP   listening on %s", *httpAddr)
	if err := http.ListenAndServe(*httpAddr, handler); err != nil {
		log.Fatal(err)
	}
}

// adminListenAddrs expands a loopback/localhost admin address into one bind per
// loopback stack (127.0.0.1 + [::1]) so the panel answers on IPv4 and IPv6 —
// `localhost` prefers ::1 on Windows, so a lone 127.0.0.1 listener leaves the
// browser's fetches connection-refused. A non-loopback host (operator chose a
// wider bind) is returned unchanged as a single addr. An unparseable addr also
// passes through untouched so the caller surfaces the bind error.
func adminListenAddrs(addr string) []string {
	host, port, err := net.SplitHostPort(addr)
	if err != nil {
		return []string{addr}
	}
	isLoopback := host == "localhost"
	if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
		isLoopback = true
	}
	if !isLoopback {
		return []string{addr}
	}
	return []string{
		net.JoinHostPort("127.0.0.1", port),
		net.JoinHostPort("::1", port),
	}
}
