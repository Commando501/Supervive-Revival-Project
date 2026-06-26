package token

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"math/big"
	"strings"
	"testing"
)

// TestSignVerifiesAgainstJWKS reproduces what the AccelByte SDK does: take the
// public key from the JWKS document and verify a freshly-signed token's RS256
// signature. If this passes, the client will accept our tokens.
func TestSignVerifiesAgainstJWKS(t *testing.T) {
	s, err := NewSigner()
	if err != nil {
		t.Fatal(err)
	}

	tok, err := s.Sign(map[string]any{"sub": "abc", "exp": Now() + 100})
	if err != nil {
		t.Fatal(err)
	}

	// Reconstruct the public key from the JWKS exactly as a client would.
	jwks := s.JWKS()
	key := jwks["keys"].([]map[string]any)[0]
	if key["kid"] != s.KID() {
		t.Fatalf("kid mismatch: %v vs %v", key["kid"], s.KID())
	}
	nBytes, _ := base64.RawURLEncoding.DecodeString(key["n"].(string))
	eBytes, _ := base64.RawURLEncoding.DecodeString(key["e"].(string))
	pub := &rsa.PublicKey{
		N: new(big.Int).SetBytes(nBytes),
		E: int(new(big.Int).SetBytes(eBytes).Int64()),
	}

	parts := strings.Split(tok, ".")
	if len(parts) != 3 {
		t.Fatalf("expected 3 JWT parts, got %d", len(parts))
	}
	signingInput := parts[0] + "." + parts[1]
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256([]byte(signingInput))
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, digest[:], sig); err != nil {
		t.Fatalf("signature did NOT verify against JWKS public key: %v", err)
	}
}

func TestUserIDStable(t *testing.T) {
	a := UserIDFor("commando")
	b := UserIDFor("commando")
	if a != b {
		t.Fatalf("user id not stable: %s vs %s", a, b)
	}
	if len(a) != 32 {
		t.Fatalf("expected 32-char id, got %d (%s)", len(a), a)
	}
}
