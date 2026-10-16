#!/bin/bash
# Versioned tools from official releases, checked against pinned SHA-256 digests.
set -euo pipefail
destination=${CI_TOOLS_DIR:-${RUNNER_TEMP:-/tmp}/openwrt-ci-tools}
mkdir -p "$destination"
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
case "${1:-lint}" in
  lint)
    archive=actionlint_1.7.7_linux_amd64.tar.gz
    curl -fL --retry 3 --connect-timeout 15 --max-time 120 \
      "https://github.com/rhysd/actionlint/releases/download/v1.7.7/$archive" -o "$temporary/$archive"
    echo "023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757  $temporary/$archive" | sha256sum -c -
    tar -xzf "$temporary/$archive" -C "$destination" actionlint
    "$destination/actionlint" -version
    ;;
  build)
    archive=sccache-v0.18.0-x86_64-unknown-linux-musl.tar.gz
    curl -fL --retry 3 --connect-timeout 15 --max-time 120 \
      "https://github.com/mozilla/sccache/releases/download/v0.18.0/$archive" -o "$temporary/$archive"
    echo "45f1447fbe231e3037bde351ef70677dd212216c8d62ae7ca409fecc4d6acc89  $temporary/$archive" | sha256sum -c -
    tar -xzf "$temporary/$archive" -C "$temporary"
    install -m 0755 "$temporary/${archive%.tar.gz}/sccache" "$destination/sccache"
    "$destination/sccache" --version
    ;;
  *) echo 'Usage: ci-tools.sh lint|build' >&2; exit 2 ;;
esac
if [ -n "${GITHUB_PATH:-}" ]; then echo "$destination" >> "$GITHUB_PATH"; fi
