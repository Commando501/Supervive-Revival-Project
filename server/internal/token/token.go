// Package token issues and serves AccelByte-shaped RS256 JWTs.
//
// AccelByte's IAM signs access tokens as RS256 JWTs. The game's AccelByte SDK
// validates every token's signature against the public key published at
// /iam/v3/oauth/jwks. To get the client past login we must therefore (a) sign
// tokens with an RSA key we control and (b) serve the matching public key as a
// JWKS whose `kid` matches the token header.
//
// Implemented with pure stdlib (crypto/rsa) so the server has zero external
// dependencies and builds offline.
package token

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"math/big"
	"sync"
	"time"
)

// Signer holds the RSA keypair used to sign and publish tokens.
type Signer struct {
	priv *rsa.PrivateKey
	kid  string
}

// NewSigner generates a fresh 2048-bit RSA keypair. The key is ephemeral per
// process run; that is fine because the JWKS is fetched live by the client.
func NewSigner() (*Signer, error) {
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, err
	}
	return &Signer{priv: priv, kid: "supervive-revival-key-1"}, nil
}

// KID returns the key id embedded in token headers and the JWKS entry.
func (s *Signer) KID() string { return s.kid }

// Sign serializes claims to a compact RS256 JWT.
func (s *Signer) Sign(claims map[string]any) (string, error) {
	header := map[string]any{"alg": "RS256", "typ": "JWT", "kid": s.kid}

	hb, err := json.Marshal(header)
	if err != nil {
		return "", err
	}
	cb, err := json.Marshal(claims)
	if err != nil {
		return "", err
	}

	signingInput := b64(hb) + "." + b64(cb)
	digest := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, s.priv, crypto.SHA256, digest[:])
	if err != nil {
		return "", err
	}
	return signingInput + "." + b64(sig), nil
}

// JWKS returns the public JSON Web Key Set document served at
// /iam/v3/oauth/jwks.
func (s *Signer) JWKS() map[string]any {
	pub := s.priv.PublicKey

	eBytes := make([]byte, 8)
	binary.BigEndian.PutUint64(eBytes, uint64(pub.E))
	// trim leading zero bytes from the exponent
	i := 0
	for i < len(eBytes)-1 && eBytes[i] == 0 {
		i++
	}

	return map[string]any{
		"keys": []map[string]any{{
			"kty": "RSA",
			"use": "sig",
			"alg": "RS256",
			"kid": s.kid,
			"n":   b64(pub.N.Bytes()),
			"e":   b64(eBytes[i:]),
		}},
	}
}

func b64(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

// ---- simple monotonic-ish user id allocation for synthetic accounts ----

var (
	mu        sync.Mutex
	userIDs   = map[string]string{}
	idCounter = big.NewInt(0)
)

// UserIDFor returns a stable synthetic AccelByte user id (32 hex chars) for a
// given login key (username, steam id, etc.), creating one on first sight.
func UserIDFor(key string) string {
	mu.Lock()
	defer mu.Unlock()
	if id, ok := userIDs[key]; ok {
		return id
	}
	// Derive a deterministic-looking 32-char hex id from the key.
	sum := sha256.Sum256([]byte("supervive-revival:" + key))
	id := encodeHex(sum[:16])
	userIDs[key] = id
	return id
}

func encodeHex(b []byte) string {
	const hexdigits = "0123456789abcdef"
	out := make([]byte, len(b)*2)
	for i, v := range b {
		out[i*2] = hexdigits[v>>4]
		out[i*2+1] = hexdigits[v&0x0f]
	}
	return string(out)
}

// Now is exposed for handlers that build claims.
func Now() int64 { return time.Now().Unix() }
