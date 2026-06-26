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
	"net/http"
	"os"
	"path/filepath"

	"supervive-revival/server/internal/capture"
	"supervive-revival/server/internal/iam"
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
	logPath := flag.String("log", filepath.Join("docs", "capture.log"), "capture log path")
	certDir := flag.String("certs", "certs", "directory for the generated TLS cert/key")
	flag.Parse()

	if err := os.MkdirAll(filepath.Dir(*logPath), 0o755); err != nil {
		log.Fatalf("log dir: %v", err)
	}

	signer, err := token.NewSigner()
	if err != nil {
		log.Fatalf("signer: %v", err)
	}

	logger, err := capture.NewLogger(*logPath)
	if err != nil {
		log.Fatalf("capture log: %v", err)
	}

	mux := http.NewServeMux()
	iam.New(signer).Register(mux)
	loki.New().Register(mux)
	menu.New().Register(mux)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("ok")) })

	// Catch-all: WebSocket upgrades (lobby/messaging) get a real handshake +
	// frame logging; everything else gets the empty-success stub. Routing here
	// (rather than a fixed /lobby path) also captures the messenger's ws path,
	// whatever it turns out to be.
	lobbySvc := lobby.New(logger)
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
