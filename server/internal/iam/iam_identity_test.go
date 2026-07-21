package iam

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"supervive-revival/server/internal/token"
)

// subFromTokenResponse pulls the JWT `sub` claim out of an /oauth/token response body.
func subFromTokenResponse(t *testing.T, body []byte) string {
	t.Helper()
	var resp struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.Unmarshal(body, &resp); err != nil || resp.AccessToken == "" {
		t.Fatalf("no access_token in response: %s", body)
	}
	parts := strings.Split(resp.AccessToken, ".")
	if len(parts) != 3 {
		t.Fatalf("malformed JWT: %q", resp.AccessToken)
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		t.Fatalf("decode payload: %v", err)
	}
	var claims map[string]any
	json.Unmarshal(payload, &claims)
	sub, _ := claims["sub"].(string)
	return sub
}

func postForm(t *testing.T, s *Service, h http.HandlerFunc, path string, form url.Values, pathVals map[string]string) []byte {
	t.Helper()
	req := httptest.NewRequest("POST", path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	for k, v := range pathVals {
		req.SetPathValue(k, v)
	}
	rec := httptest.NewRecorder()
	h(rec, req)
	return rec.Body.Bytes()
}

// TestAuthPathsAgreeOnOneUserID is the direct guard for the S85 avatar-switch bug.
//
// The client authenticates through the Steam platform-token endpoint AND the plain
// /oauth/token grant (and refreshes on a timer), each WITHOUT a stable user
// identifier. If those paths mint different user ids for the same physical player,
// its subsystems disagree about "me": the party rendered id A's loadout while avatar
// equips were written under id B, so no switch ever reached the card. Every
// unidentified-user path must resolve to token.LocalPlayerID().
func TestAuthPathsAgreeOnOneUserID(t *testing.T) {
	signer, err := token.NewSigner()
	if err != nil {
		t.Fatalf("signer: %v", err)
	}
	s := New(signer)
	want := token.LocalPlayerID()

	// 1. Steam platform login, no platform_user_id (what the real client sends).
	steamBody := postForm(t, s, s.handlePlatformToken, "/iam/v4/oauth/platforms/steam/token",
		url.Values{"grant_type": {"urn:ietf:params:oauth:grant-type:platform_token"}},
		map[string]string{"platformId": "steam"})
	if got := subFromTokenResponse(t, steamBody); got != want {
		t.Fatalf("steam login sub = %s, want canonical %s", got, want)
	}

	// 2. /oauth/token refresh with no username and no code — the path that used to
	//    fall through to the ad-hoc "player" key and split the identity.
	for _, grant := range []string{"refresh_token", "authorization_code", "password"} {
		body := postForm(t, s, s.handleToken, "/iam/v4/oauth/token",
			url.Values{"grant_type": {grant}, "code": {"opaque-code-differs-every-login"}}, nil)
		if got := subFromTokenResponse(t, body); got != want {
			t.Fatalf("grant %q sub = %s, want canonical %s (identity must not diverge, and must NOT key on the opaque code)", grant, got, want)
		}
	}

	// 3. A real username still gets its own distinct id (we only canonicalize the
	//    unidentified fallback, we don't collapse genuine accounts).
	named := postForm(t, s, s.handleToken, "/iam/v4/oauth/token",
		url.Values{"grant_type": {"password"}, "username": {"someone-else"}}, nil)
	if got := subFromTokenResponse(t, named); got == want {
		t.Fatalf("a named username must NOT collapse to the local player id (got %s)", got)
	}
}
