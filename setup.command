#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"
chmod +x ./install.sh

echo "Starting salah-bar installer..."
echo
./install.sh

echo
echo "Installation finished. Press Enter to close this window."
read -r