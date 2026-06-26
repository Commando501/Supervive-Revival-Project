// Package iam implements the minimal subset of AccelByte's IAM REST API needed
// to get the SUPERVIVE client past its login screen.
//
// The real login paths compiled into the client are LoginWithUsernamePassword,
// LoginWithSteam and LoginWithTheorycraftLauncher. In AccelByte's SDK these all
// terminate at the OAuth token endpoints below and then a /users/me lookup. We
// accept any credentials and mint a synthetic, validly-signed account so the
// client believes it is authenticated.
package iam

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"

	"supervive-revival/server/internal/token"
)

func nowISO() string { return time.Now().UTC().Format("2006-01-02T15:04:05.000Z") }

// Service wires the IAM handlers to the token signer.
type Service struct {
	Signer *token.Signer

	mu        sync.Mutex
	namespace string            // last namespace observed from a request path
	names     map[string]string // userID -> chosen display name
}

// New creates an IAM service with a sensible default namespace (overwritten as
// soon as we observe the client's real namespace in a request).
func New(s *token.Signer) *Service {
	return &Service{Signer: s, namespace: "supervive", names: map[string]string{}}
}

func (s *Service) savedName(uid string) (string, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	n, ok := s.names[uid]
	return n, ok
}

func (s *Service) saveName(uid, name string) {
	s.mu.Lock()
	s.names[uid] = name
	s.mu.Unlock()
}

// Register attaches all IAM routes to the mux. Go 1.22+ pattern routing gives us
// method + path-wildcard matching.
func (s *Service) Register(mux *http.ServeMux) {
	// AccelByte SDK (IamServerUrl = http://localhost:8080/iam), v3 API.
	mux.HandleFunc("GET /iam/v3/oauth/jwks", s.handleJWKS)
	mux.HandleFunc("GET /iam/v1/oauth/jwks", s.handleJWKS)
	mux.HandleFunc("POST /iam/v3/oauth/token", s.handleToken)
	mux.HandleFunc("POST /iam/v3/oauth/platforms/{platformId}/token", s.handlePlatformToken)
	mux.HandleFunc("GET /iam/v3/public/users/me", s.handleUsersMe)
	mux.HandleFunc("GET /iam/v3/public/namespaces/{namespace}/users/me", s.handleUsersMe)
	mux.HandleFunc("GET /iam/v3/public/namespaces/{namespace}", s.handleNamespace)
	mux.HandleFunc("POST /iam/v3/oauth/verify", s.handleVerify)
	mux.HandleFunc("POST /iam/v3/public/oauth/verify", s.handleVerify)

	// AccelByte SDK v4 (IamServerUrl/iam + /v4/...). This is what the Steam login
	// actually uses: POST /iam/v4/oauth/platforms/steam/token.
	mux.HandleFunc("GET /iam/v4/oauth/jwks", s.handleJWKS)
	mux.HandleFunc("POST /iam/v4/oauth/token", s.handleToken)
	mux.HandleFunc("POST /iam/v4/oauth/token/exchange", s.handleToken)
	mux.HandleFunc("POST /iam/v4/oauth/authenticateWithLink", s.handleToken)
	mux.HandleFunc("POST /iam/v4/oauth/platforms/{platformId}/token", s.handlePlatformToken)
	mux.HandleFunc("GET /iam/v4/public/namespaces/{namespace}/users/me", s.handleUsersMe)
	mux.HandleFunc("GET /iam/v4/public/namespaces/{namespace}/users/{userId}", s.handleUsersMe)
	mux.HandleFunc("GET /iam/v4/public/namespaces/{namespace}", s.handleNamespace)
	mux.HandleFunc("POST /iam/v4/oauth/verify", s.handleVerify)

	// AccelByte service-time endpoints (Basic/Platform). The SDK checks these.
	mux.HandleFunc("GET /basic/v1/public/misc/time", s.handleTime)
	mux.HandleFunc("GET /platform/public/misc/time", s.handleTime)
	mux.HandleFunc("GET /iam/v3/public/misc/time", s.handleTime)

	// Display-name / onboarding screen (CHOOSE DISPLAY NAME AND TAG).
	mux.HandleFunc("GET /iam/v3/public/inputValidations", s.handleInputValidations)
	mux.HandleFunc("GET /iam/v4/public/inputValidations", s.handleInputValidations)
	mux.HandleFunc("GET /v3/public/inputValidations", s.handleInputValidations)
	mux.HandleFunc("GET /iam/v3/public/namespaces/{namespace}/users/availability", s.handleAvailability)
	mux.HandleFunc("GET /iam/v4/public/namespaces/{namespace}/users/availability", s.handleAvailability)
	// Saving the chosen name (try the common AccelByte update verbs/paths).
	mux.HandleFunc("PUT /iam/v3/public/namespaces/{namespace}/users/me", s.handleUpdateMe)
	mux.HandleFunc("PATCH /iam/v3/public/namespaces/{namespace}/users/me", s.handleUpdateMe)
	mux.HandleFunc("PUT /iam/v4/public/namespaces/{namespace}/users/me", s.handleUpdateMe)
	mux.HandleFunc("PATCH /iam/v4/public/namespaces/{namespace}/users/me", s.handleUpdateMe)

	// Theorycraft PostAuthService (ProdPostAuthURL = http://localhost:8080),
	// AccelByte v4/v3 API mounted at the root (no /iam prefix). This is the
	// path the Steam login actually uses (LogLokiAuthManager).
	mux.HandleFunc("GET /v3/oauth/jwks", s.handleJWKS)
	mux.HandleFunc("GET /v4/oauth/jwks", s.handleJWKS)
	mux.HandleFunc("POST /v3/oauth/token", s.handleToken)
	mux.HandleFunc("POST /v4/oauth/token", s.handleToken)
	mux.HandleFunc("POST /v4/oauth/token/exchange", s.handleToken)
	mux.HandleFunc("POST /v4/oauth/authenticateWithLink", s.handleToken)
	mux.HandleFunc("POST /v4/oauth/platforms/{platformId}/token", s.handlePlatformToken)
	mux.HandleFunc("GET /v3/public/users/me", s.handleUsersMe)
	mux.HandleFunc("GET /v4/public/namespaces/{namespace}/users/me", s.handleUsersMe)
	mux.HandleFunc("GET /v4/public/namespaces/{namespace}/users/{userId}", s.handleUsersMe)
	mux.HandleFunc("GET /v3/public/namespaces/{namespace}", s.handleNamespace)
	mux.HandleFunc("GET /v1/public/misc/time", s.handleTime)
	mux.HandleFunc("POST /v3/oauth/verify", s.handleVerify)
	mux.HandleFunc("POST /v4/oauth/verify", s.handleVerify)
}

// handleTime answers AccelByte's server-time check.
func (s *Service) handleTime(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"currentTime": nowISO()})
}

// handleInputValidations returns the field rules the onboarding screen ("CHOOSE
// DISPLAY NAME AND TAG") reads. An empty stub here makes the screen show "must
// be between 0 and 0 characters", so real min/max are required.
func (s *Service) handleInputValidations(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"data": []map[string]any{
			{"field": "displayName", "validation": validation(3, 16, true, false)},
			{"field": "uniqueDisplayName", "validation": validation(3, 16, false, false)},
			{"field": "tag", "validation": validation(4, 5, false, true)},
			{"field": "username", "validation": validation(3, 32, false, false)},
		},
	})
}

// validation builds an AccelByte field-validation object.
func validation(min, max int, allowSpace, digitsOnly bool) map[string]any {
	return map[string]any{
		"allowAllSpecialCharacters":    false,
		"allowDigit":                   true,
		"allowLetter":                  !digitsOnly,
		"allowSpace":                   allowSpace,
		"allowUnicode":                 false,
		"description":                  map[string]any{"languages": map[string]any{"en": "Allowed"}},
		"isCustomRegex":                false,
		"letterCase":                   "MIXED",
		"maxLength":                    max,
		"maxRepeatingAlphaNum":         0,
		"maxRepeatingSpecialCharacter": 0,
		"minCharType":                  0,
		"minLength":                    min,
		"regex":                        "",
		"specialCharacterLocation":     "ANYWHERE",
		"specialCharacters":            []string{"_", "-", "."},
	}
}

// handleAvailability reports a requested name as free.
func (s *Service) handleAvailability(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"available": true})
}

// handleUpdateMe accepts the chosen display name and persists it so a later
// users/me reflects it, then returns the updated profile.
func (s *Service) handleUpdateMe(w http.ResponseWriter, r *http.Request) {
	ns := s.ns(r.PathValue("namespace"))
	claims := bearerClaims(r)
	uid, _ := claims["sub"].(string)
	if uid == "" {
		uid = token.UserIDFor("player")
	}

	var body map[string]any
	json.NewDecoder(r.Body).Decode(&body)
	name := firstString(body, "displayName", "uniqueDisplayName", "userName", "username")
	if name != "" {
		s.saveName(uid, name)
	} else if saved, ok := s.savedName(uid); ok {
		name = saved
	} else {
		name = "Reviver"
	}

	writeJSON(w, map[string]any{
		"userId":            uid,
		"namespace":         ns,
		"displayName":       name,
		"uniqueDisplayName": name,
		"emailAddress":      "player@supervive.local",
		"country":           "US",
		"emailVerified":     true,
		"enabled":           true,
		"bans":              []any{},
	})
}

func firstString(m map[string]any, keys ...string) string {
	for _, k := range keys {
		if v, ok := m[k].(string); ok && v != "" {
			return v
		}
	}
	return ""
}

func (s *Service) setNamespace(ns string) {
	if ns == "" {
		return
	}
	s.mu.Lock()
	s.namespace = ns
	s.mu.Unlock()
}

func (s *Service) ns(fromPath string) string {
	if fromPath != "" {
		s.setNamespace(fromPath)
		return fromPath
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.namespace
}

// handleToken serves grant_type=client_credentials | password | refresh_token |
// authorization_code. Username/password login lands here.
func (s *Service) handleToken(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	grant := r.FormValue("grant_type")
	clientID := basicClientID(r)
	ns := s.ns("")

	switch grant {
	case "client_credentials":
		// SDK service token — not tied to a player.
		s.writeToken(w, tokenParams{
			Namespace:   ns,
			ClientID:    clientID,
			UserID:      "",
			DisplayName: "",
			IsClient:    true,
		})
	default:
		// password / authorization_code / refresh_token -> a player session.
		key := r.FormValue("username")
		if key == "" {
			key = r.FormValue("code")
		}
		if key == "" {
			key = "player"
		}
		uid := token.UserIDFor(key)
		s.writeToken(w, tokenParams{
			Namespace:   ns,
			ClientID:    clientID,
			UserID:      uid,
			DisplayName: displayNameFor(key),
		})
	}
}

// handlePlatformToken serves LoginWithSteam / LoginWithTheorycraftLauncher.
func (s *Service) handlePlatformToken(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	platform := r.PathValue("platformId")
	clientID := basicClientID(r)
	ns := s.ns("")

	// Use the platform user id if supplied, else the platform name, as the key.
	key := r.FormValue("platform_user_id")
	if key == "" {
		key = "platform:" + platform
	}
	uid := token.UserIDFor(key)
	s.writeToken(w, tokenParams{
		Namespace:      ns,
		ClientID:       clientID,
		UserID:         uid,
		DisplayName:    displayNameFor(key),
		PlatformID:     platform,
		PlatformUserID: r.FormValue("platform_user_id"),
	})
}

func (s *Service) handleJWKS(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, s.Signer.JWKS())
}

func (s *Service) handleNamespace(w http.ResponseWriter, r *http.Request) {
	ns := s.ns(r.PathValue("namespace"))
	writeJSON(w, map[string]any{
		"namespace":   ns,
		"displayName": "SUPERVIVE",
		"status":      "ACTIVE",
		"type":        "Game",
	})
}

func (s *Service) handleUsersMe(w http.ResponseWriter, r *http.Request) {
	ns := s.ns(r.PathValue("namespace"))
	claims := bearerClaims(r)
	uid, _ := claims["sub"].(string)
	if uid == "" {
		uid = token.UserIDFor("player")
	}
	name, _ := claims["display_name"].(string)
	if name == "" || name == "platform" {
		name = "Reviver"
	}
	if saved, ok := s.savedName(uid); ok {
		name = saved
	}
	if nsClaim, _ := claims["namespace"].(string); nsClaim != "" {
		ns = nsClaim
	}
	// Present the account as ALREADY having a valid unique display name
	// ("Name#1234") so the client skips the "CHOOSE DISPLAY NAME" onboarding.
	tag := tagFor(uid)
	unique := name + "#" + tag
	writeJSON(w, map[string]any{
		"userId":            uid,
		"namespace":         ns,
		"displayName":       name,
		"uniqueDisplayName": unique,
		"tag":               tag,
		"emailAddress":      "player@supervive.local",
		"country":           "US",
		"emailVerified":     true,
		"phoneVerified":     false,
		"enabled":           true,
		"deletionStatus":    false,
		"bans":              []any{},
		"roles":             []any{},
		"permissions":       permissions(ns),
		"platformId":        "",
		"platformUserId":    "",
	})
}

// tagFor derives a stable 4-digit tag from a user id.
func tagFor(uid string) string {
	var sum int
	for _, c := range uid {
		sum = (sum*31 + int(c)) % 10000
	}
	return fmtTag(sum)
}

func fmtTag(n int) string {
	s := "0000" + itoa(n)
	return s[len(s)-4:]
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b []byte
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	return string(b)
}

// handleVerify validates an opaque/JWT token. We trust everything.
func (s *Service) handleVerify(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	writeJSON(w, map[string]any{"active": true})
}

// ---- token response construction ----

type tokenParams struct {
	Namespace      string
	ClientID       string
	UserID         string
	DisplayName    string
	PlatformID     string
	PlatformUserID string
	IsClient       bool
}

func (s *Service) writeToken(w http.ResponseWriter, p tokenParams) {
	now := token.Now()
	const ttl = 86400

	unique := ""
	if p.DisplayName != "" {
		unique = p.DisplayName + "#0001"
	}
	claims := map[string]any{
		"namespace":    p.Namespace,
		"display_name": p.DisplayName,
		// AuthManager reads UniqueDisplayName from the token; a non-empty value
		// keeps ELokiAuthState out of AwaitingUniqueDisplayName (skips onboarding).
		"unique_display_name": unique,
		"uniqueDisplayName":   unique,
		"roles":               []any{},
		"permissions":         permissions(p.Namespace),
		"bans":                []any{},
		"jflgs":               0,
		"sub":                 p.UserID,
		"iat":                 now,
		"exp":                 now + ttl,
		"nbf":                 now - 60,
		"client_id":           p.ClientID,
		"country":             "US",
		"scope":               "commerce account social publishing analytics",
		"is_comply":           true,
	}
	if p.IsClient {
		delete(claims, "sub")
	}

	access, err := s.Signer.Sign(claims)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	refresh, _ := s.Signer.Sign(map[string]any{
		"sub": p.UserID, "iat": now, "exp": now + ttl*2, "typ": "refresh",
		"namespace": p.Namespace, "client_id": p.ClientID,
	})

	resp := map[string]any{
		"access_token":       access,
		"refresh_token":      refresh,
		"expires_in":         ttl,
		"refresh_expires_in": ttl * 2,
		"token_type":          "Bearer",
		"namespace":           p.Namespace,
		"display_name":        p.DisplayName,
		"unique_display_name": unique,
		"user_id":             p.UserID,
		"platform_id":        p.PlatformID,
		"platform_user_id":   p.PlatformUserID,
		"roles":              []any{},
		"permissions":        permissions(p.Namespace),
		"bans":               []any{},
		"jflgs":              0,
		"scope":              "commerce account social publishing analytics",
		"is_comply":          true,
	}
	writeJSON(w, resp)
}

func permissions(ns string) []map[string]any {
	return []map[string]any{
		{"Resource": "NAMESPACE:" + ns + ":*", "Action": 15},
		{"Resource": "ADMIN:NAMESPACE:" + ns + ":*", "Action": 15},
	}
}

// ---- helpers ----

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(v)
}

// basicClientID pulls the client_id out of the HTTP Basic auth header used by
// AccelByte's OAuth token requests (base64(client_id:client_secret)).
func basicClientID(r *http.Request) string {
	if u, _, ok := r.BasicAuth(); ok {
		return u
	}
	return r.FormValue("client_id")
}

// bearerClaims decodes (without verifying — we minted it) the payload of the
// bearer JWT so endpoints like /users/me return a user consistent with the
// token that was issued at login.
func bearerClaims(r *http.Request) map[string]any {
	auth := r.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return nil
	}
	parts := strings.Split(strings.TrimPrefix(auth, "Bearer "), ".")
	if len(parts) != 3 {
		return nil
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil
	}
	var claims map[string]any
	if json.Unmarshal(payload, &claims) != nil {
		return nil
	}
	return claims
}

func displayNameFor(key string) string {
	if key == "" || key == "player" || strings.HasPrefix(key, "platform:") {
		return "Reviver"
	}
	if i := strings.IndexAny(key, "@:"); i > 0 {
		return key[:i]
	}
	return key
}
