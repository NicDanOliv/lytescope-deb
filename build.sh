#!/usr/bin/env bash

set -euo pipefail

PACKAGE_DIR="lytescope_0.1.0"
OUTPUT_FILE="lytescope.deb"

chmod 755 "$PACKAGE_DIR/DEBIAN/postinst"
chmod 755 "$PACKAGE_DIR/DEBIAN/prerm"
chmod 755 "$PACKAGE_DIR/DEBIAN/postrm"

chmod 755 "$PACKAGE_DIR/usr/local/bin/lytescope"
chmod 755 "$PACKAGE_DIR/usr/local/lib/lytescope/build_payload.py"
chmod 600 "$PACKAGE_DIR/etc/lytescope/agent.conf"

dpkg-deb --build "$PACKAGE_DIR" "$OUTPUT_FILE"

echo "Built $OUTPUT_FILE"