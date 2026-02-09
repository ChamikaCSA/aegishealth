#!/usr/bin/env bash
# Build the edge agent for the current platform (macOS, Linux, or Windows).

set -e
cd "$(dirname "$0")/.."

# Prefer venv if present
if [ -d "venv" ]; then
  source venv/bin/activate
fi

PYTHON="${PYTHON:-python3}"
if ! command -v pyinstaller &>/dev/null; then
  echo "Installing PyInstaller..."
  "$PYTHON" -m pip install pyinstaller
fi

echo "Building aegishealth-agent..."
pyinstaller --clean --noconfirm agent.spec

mkdir -p dist/agent
if [ -f dist/aegishealth-agent ]; then
  mv dist/aegishealth-agent dist/agent/
elif [ -f dist/aegishealth-agent.exe ]; then
  mv dist/aegishealth-agent.exe dist/agent/
fi

# TLS: Electron packs dist/agent as extraResource; agent-manager passes
# --tls-cert resources/agent/certs/ca.crt. PyInstaller does not embed datas
# beside the binary, so we must ship the trust anchor next to the executable.
if [ ! -f certs/ca.crt ]; then
  echo "certs/ca.crt missing — generating dev CA (replace with production CA for real releases)"
  bash "$(dirname "$0")/generate_dev_certs.sh"
fi
mkdir -p dist/agent/certs
cp certs/ca.crt dist/agent/certs/ca.crt

echo "Done. Output: dist/agent/aegishealth-agent (+ dist/agent/certs/ca.crt)"
