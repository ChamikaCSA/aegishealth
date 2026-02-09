#!/usr/bin/env bash
# Generate self-signed TLS certificates for local development.
# Outputs: certs/ca.crt, certs/server.crt, certs/server.key
set -e

CERT_DIR="$(dirname "$0")/../certs"
mkdir -p "$CERT_DIR"

echo "Generating self-signed CA and server certificates in $CERT_DIR ..."

openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout "$CERT_DIR/ca.key" \
  -out "$CERT_DIR/ca.crt" \
  -days 365 \
  -subj "/CN=AegisHealth Dev CA"

openssl req -newkey rsa:4096 -nodes \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.csr" \
  -subj "/CN=localhost"

openssl x509 -req \
  -in "$CERT_DIR/server.csr" \
  -CA "$CERT_DIR/ca.crt" \
  -CAkey "$CERT_DIR/ca.key" \
  -CAcreateserial \
  -out "$CERT_DIR/server.crt" \
  -days 365 \
  -extfile <(printf "subjectAltName=DNS:localhost,IP:127.0.0.1")

rm -f "$CERT_DIR/server.csr" "$CERT_DIR/ca.srl"

echo "Done. Files created:"
ls -la "$CERT_DIR"
echo ""
echo "Server: certs/server.crt + certs/server.key"
echo "Client: certs/ca.crt (trust anchor)"
