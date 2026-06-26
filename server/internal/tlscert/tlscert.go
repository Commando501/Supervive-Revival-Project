// Package tlscert generates a proper Root CA -> Leaf certificate chain for the
// local server's HTTPS listener (the Theorycraft hostnames we hijack via hosts).
//
// We append the ROOT to the game's loose libcurl CA bundle
// (Loki/Content/Certificates/cacert.pem) and have the server present the LEAF.
// A self-signed cert presented as the leaf trips OpenSSL's
// X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT even when trusted, so a separate
// non-CA leaf signed by the trusted root is required.
package tlscert

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"os"
	"path/filepath"
	"time"
)

// Hostnames the leaf cert is valid for. Add new ones as the client reveals them.
var Hostnames = []string{
	"accounts.projectloki.theorycraftgames.com",
	"client-config-jx-prod.prodcluster.awsinfra.theorycraftgames.com",
	"localhost",
}

// EnsureCert loads or generates the chain. It returns the TLS cert (leaf + root
// chain) and the path to the ROOT PEM to append to the game's CA bundle.
func EnsureCert(dir string) (tls.Certificate, string, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return tls.Certificate{}, "", err
	}
	rootPath := filepath.Join(dir, "root.crt")
	leafPath := filepath.Join(dir, "server.crt") // leaf + root chain
	keyPath := filepath.Join(dir, "server.key")

	if all(fileExists(rootPath), fileExists(leafPath), fileExists(keyPath)) {
		if cert, err := tls.LoadX509KeyPair(leafPath, keyPath); err == nil {
			return cert, rootPath, nil
		}
	}

	rootCert, rootKey, rootPEM, err := genRoot()
	if err != nil {
		return tls.Certificate{}, "", err
	}
	leafPEM, leafKeyPEM, err := genLeaf(rootCert, rootKey)
	if err != nil {
		return tls.Certificate{}, "", err
	}

	// server.crt holds the full chain (leaf first, then root) so the client can
	// build leaf -> root and match root against the trusted bundle.
	chainPEM := append(append([]byte{}, leafPEM...), rootPEM...)
	if err := writeAll(map[string][]byte{
		rootPath: rootPEM,
		leafPath: chainPEM,
		keyPath:  leafKeyPEM,
	}); err != nil {
		return tls.Certificate{}, "", err
	}
	cert, err := tls.X509KeyPair(chainPEM, leafKeyPEM)
	return cert, rootPath, err
}

func genRoot() (*x509.Certificate, *rsa.PrivateKey, []byte, error) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, nil, nil, err
	}
	tmpl := &x509.Certificate{
		SerialNumber:          big.NewInt(time.Now().UnixNano()),
		Subject:               pkix.Name{CommonName: "SUPERVIVE Revival Root CA", Organization: []string{"SUPERVIVE Revival"}},
		NotBefore:             time.Now().Add(-time.Hour),
		NotAfter:              time.Now().AddDate(10, 0, 0),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		BasicConstraintsValid: true,
		IsCA:                  true,
		MaxPathLen:            1,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		return nil, nil, nil, err
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		return nil, nil, nil, err
	}
	pemBytes := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	return cert, key, pemBytes, nil
}

func genLeaf(root *x509.Certificate, rootKey *rsa.PrivateKey) (leafPEM, keyPEM []byte, err error) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, nil, err
	}
	tmpl := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano() + 1),
		Subject:      pkix.Name{CommonName: "accounts.projectloki.theorycraftgames.com", Organization: []string{"SUPERVIVE Revival"}},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().AddDate(10, 0, 0),
		KeyUsage:     x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		DNSNames:     Hostnames,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, root, &key.PublicKey, rootKey)
	if err != nil {
		return nil, nil, err
	}
	leafPEM = pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	keyPEM = pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})
	return leafPEM, keyPEM, nil
}

func all(bs ...bool) bool {
	for _, b := range bs {
		if !b {
			return false
		}
	}
	return true
}

func writeAll(files map[string][]byte) error {
	for p, b := range files {
		mode := os.FileMode(0o644)
		if filepath.Ext(p) == ".key" {
			mode = 0o600
		}
		if err := os.WriteFile(p, b, mode); err != nil {
			return err
		}
	}
	return nil
}

func fileExists(p string) bool {
	_, err := os.Stat(p)
	return err == nil
}
