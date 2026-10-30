#!/usr/bin/env bash

set -euo pipefail

PACKAGE_DIR="lytescope_0.3.0"
OUTPUT_FILE="lytescope.deb"

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf -- "$STAGING_DIR"' EXIT

cp -a "$PACKAGE_DIR" "$STAGING_DIR/package"

PACKAGE_ROOT="$STAGING_DIR/package"
LIBRARY_DIR="$PACKAGE_ROOT/usr/local/lib/lytescope"

# Exclude compiled Python files created during testing.
find "$LIBRARY_DIR" -type f \
  \( -name '*.pyc' -o -name '*.pyo' \) -delete

find "$LIBRARY_DIR" -depth -type d \
  -name '__pycache__' -empty -delete

# Set directory and Python module permissions.
find "$PACKAGE_ROOT" -type d -exec chmod 755 {} +

find "$LIBRARY_DIR" -type f \
  -name '*.py' -exec chmod 644 {} +

chmod 755 "$PACKAGE_ROOT/DEBIAN/postinst"
chmod 755 "$PACKAGE_ROOT/DEBIAN/prerm"
chmod 755 "$PACKAGE_ROOT/DEBIAN/postrm"

chmod 755 "$PACKAGE_ROOT/usr/local/bin/lytescope"
chmod 755 "$LIBRARY_DIR/build_payload.py"
chmod 600 "$PACKAGE_ROOT/etc/lytescope/agent.conf"
chmod 644 "$PACKAGE_ROOT/DEBIAN/control"
chmod 644 "$PACKAGE_ROOT/DEBIAN/conffiles"
chmod 644 "$PACKAGE_ROOT/etc/systemd/system/lytescope.service"

AGENT_VERSION="$(
  awk '/^Version:/ {print $2}' "$PACKAGE_ROOT/DEBIAN/control"
)"

if [ -z "$AGENT_VERSION" ]; then
  echo "Missing package version in DEBIAN/control" >&2
  exit 1
fi

printf '%s\n' "$AGENT_VERSION" > "$LIBRARY_DIR/version"
chmod 644 "$LIBRARY_DIR/version"

dpkg-deb --root-owner-group \
  --build "$PACKAGE_ROOT" "$OUTPUT_FILE"

echo "Built $OUTPUT_FILE (version $AGENT_VERSION)"