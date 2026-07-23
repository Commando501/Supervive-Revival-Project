// Package loki implements Theorycraft's own ("project Loki") backend endpoints
// that sit in front of AccelByte: the client-config service and the account/auth
// service the Steam login actually talks to.
//
// Observed from the client (Loki.log):
//   - GET https://client-config-jx-prod.../configuration/public?language=en
//     (LogClientConfig; non-fatal — client reaches the menu even on failure)
//   - Steam login -> POST https://accounts.projectloki.theorycraftgames.com/...
//     (LogLokiAuthManager "Attempting to login with Steam"; on failure:
//      "Auth Failure 14005 Request not sent")
//
// The exact accounts path/schema is still being captured; until known, those
// routes fall through to the capture stub. This package owns what we've confirmed.
package loki

import (
	"encoding/json"
	"net/http"
	"time"
)

type Service struct{}

func New() *Service { return &Service{} }

func (s *Service) Register(mux *http.ServeMux) {
	// Master client-config: service registry + display-name limits.
	// Two surfaces return the same ClientConfiguration: /configuration/public (fetched
	// once, pre-auth) and /configuration/client (polled ~1/s by ClientConfigManager,
	// post-auth). The {} catch-all left /configuration/client empty, so ClientVersions
	// was empty and Comp_MainMenu_QueueController.IsClientVersionValid returned false —
	// which fails CanControlQueue and blocks activity selection with
	// "Unable to modify activity". Serving the same config (with ClientVersions) here
	// lets the version check pass.
	mux.HandleFunc("GET /configuration/public", s.handleClientConfig)
	mux.HandleFunc("GET /configuration/client", s.handleClientConfig)

	// PostAuth service (resolved from ServiceHostnames["postauth"]). The game
	// calls {base}/postauth/... — e.g. reconcileRoles after login.
	mux.HandleFunc("POST /postauth/reconcileRoles", s.handleReconcileRoles)
	mux.HandleFunc("POST /reconcileRoles", s.handleReconcileRoles)
}

// handleReconcileRoles answers the post-login role reconcile (PostAuthReconcileResponse).
// The AuthManager reads DisplayNameTagValidation from here, which drives the
// "CHOOSE DISPLAY NAME AND TAG" screen limits (otherwise shown as 0 and 0).
func (s *Service) handleReconcileRoles(w http.ResponseWriter, r *http.Request) {
	// PostAuthReconcileResponse fields confirmed from the binary: Unique_display_name
	// and Other_display_name. A non-empty unique_display_name tells the AuthManager
	// the account is already named, so ELokiAuthState goes Authorized instead of
	// AwaitingUniqueDisplayName -> the onboarding screen is skipped.
	writeJSON(w, map[string]any{
		"roles":               []any{},
		"steamId":             r.URL.Query().Get("steam"),
		"mfa_required":        false,
		"unique_display_name": "Reviver#0001",
		"other_display_name":  "Reviver",
		// casing hedges
		"Unique_display_name": "Reviver#0001",
		"Other_display_name":  "Reviver",
		"uniqueDisplayName":   "Reviver#0001",
	})
}

// handleClientConfig returns the ClientConfiguration the game relies on: a
// service registry (looked up by name, e.g. "postauth" — which handles the
// display-name/tag step) plus DisplayNameTagValidation limits for the
// "CHOOSE DISPLAY NAME AND TAG" screen. Field names confirmed from the binary;
// UE JSON matching is case-insensitive.
func (s *Service) handleClientConfig(w http.ResponseWriter, r *http.Request) {
	const base = "http://localhost:8080"
	// ServiceHostnames is a TMap<serviceName, url> (confirmed: ServiceHostnames_Key).
	// GetServiceAddress(name) looks up by service name; the game then calls
	// {url}/{name}/{endpoint}.
	services := []string{
		"postauth", "clientconfig", "iam", "platform", "basic", "lobby",
		"session", "matchmaking", "social", "cloudsave", "telemetry", "gateway",
		"mmr", "party", "storefront", "progression", "mailbox", "referral",
		"personalization", "inventory", "playerstats", "matchhistory",
		// Added after the client logged "Could not find service address for
		// service <name>" for these exact keys. Without an address the client
		// builds a host-less URL ("No host part in the URL" / "Invalid response
		// received") — e.g. /content-service/manifest and /discord-api/account/token.
		// Note: the service NAME (lookup key) has no hyphen; the URL PATH segment
		// the client appends does (content-service, discord-api, core-game).
		"contentservice", "discordapi", "coregame",
	}
	// ServiceHostnames is TMap<serviceName, FString url> (confirmed: the client
	// logged "Object used as String" when we sent structs). Plain string values.
	hostnames := map[string]any{}
	for _, name := range services {
		hostnames[name] = base
	}
	// messaging is a websocket service: when its address is absent the client
	// logs "Messenger connection failed Bad protocol ''. Use either 'ws', 'wss',
	// or 'wss+insecure'", i.e. it uses the value directly as the ws URL. Give it a
	// ws:// scheme so the protocol parses. (The ws handshake itself is still TODO —
	// our server doesn't speak websocket yet, so it will then fail at upgrade like
	// the lobby service does.)
	hostnames["messaging"] = "ws://localhost:8080"
	// Include eTag + lastUpdated: the client likely only *applies* a fetched
	// config that is newer than its current (default 0), so without these the
	// parsed config is dropped and ServiceHostnames stays empty.
	// ClientVersions is the supported-version list; if the client's build isn't
	// in it the game shows "UPDATE REQUIRED". Build is release2.4.live-156430.
	// S73 probe: serve featureToggles. ClientConfiguration.FeatureToggles is TMap<FString, FFeatureToggle>
	// where FFeatureToggle{ Config: TMap<FString,FString> } (RE'd live). The DS client spams
	// "ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready" and stays on the tutorial
	// LOADING screen. TEST: does populating the GLOBAL config toggle set flip readiness (config-gated), or is
	// readiness set only at server round-start (round-gated)? Serve the observed gameplay toggles enabled.
	// (Malformed = whole config dropped silently per the validity model, so this is safe to iterate.)
	//
	// ★ S85 (2026-07-21) ANSWERED: NOT config-payload-gated. Readiness is PER-PlayerController — the delegates
	// OnClientGameFeatureTogglesReady / OnAnyClientGameFeatureToggleChanged / ...ReadyOrChanged live on
	// LokiPlayerController (schema.txt:26932). Ruled out by measurement (docs/session-85 §"feature toggles"):
	// the toggles are NOT delivered by any PC replicated prop (only LokiPlayerCheats+bIsAdmin), any PC Client
	// RPC (none toggle-related), any GameState replicated prop (none of the 43 is config/toggle/auth), or any
	// separate HTTP endpoint (client hits ONLY /configuration/{public,client} + /mailbox/config/version — this
	// featureToggles payload IS received, since ServiceHostnames from the same doc works). Errors appear 0x at
	// the menu and only ~2s AFTER DS travel => readiness is set by the per-match game-feature resolution the
	// real server drives during round-start (round-gated), which the stub doesn't run. Static string-xref RE of
	// ULokiGameFeatureToggles::Get is packer-blocked (format string uncommitted, same S61 login wall). Next to
	// crack it = dumpimage the now-committed .text + offline disasm, OR a client-side ready-bool shim (force).
	ftEnabled := map[string]any{"config": map[string]string{"default": "true"}}
	featureToggles := map[string]any{
		"CursorCharacterAim":        ftEnabled,
		"AttachAudioListenerToHero": ftEnabled,
		"DeadSpectatorCameraLock":   ftEnabled,
		"WinterEvent":               map[string]any{"config": map[string]string{"default": "false"}},
		"BonfireUAVs":               map[string]any{"config": map[string]string{"default": "false"}},
	}
	writeJSON(w, map[string]any{
		"serviceHostnames": hostnames,
		"clientVersions": []string{
			"release2.4.live-156430-shipping",
			"release2.4.live-156430",
			"release2.4.live",
			"156430",
		},
		"featureToggles": featureToggles,
		"eTag":           "supervive-revival-2",
		"lastUpdated":    nowISO(),
	})
}

func nowISO() string { return time.Now().UTC().Format("2006-01-02T15:04:05Z") }

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(v)
}
