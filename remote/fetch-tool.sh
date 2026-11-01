#!/bin/bash
# Downloads one program for a machine (prepare-unix.sh runs it), into a folder, from a pinned release — and keeps it
# only if its SHA-256 matches the release's own published checksum (copied here). Exit status 1: nothing was installed.
#   bash fetch-tool.sh starship <platform> <folder>     e.g. starship x86_64-unknown-linux-musl ~/.local/bin
set -u
STARSHIP_VERSION=v1.27.0

sha_for() {  # sha_for <release asset>: its SHA-256, from the release's checksum files
  case "$1" in
    starship-x86_64-unknown-linux-musl.tar.gz)  echo 10c8eb4cb3b761d9bf59ea828444c2dab36c900b7d69a69e08814b286969df89 ;;
    starship-aarch64-unknown-linux-musl.tar.gz) echo 341f5cbf24699fa0b27ec88965ad25f862ea09e15d35a543fd6ffdff1d2aa00d ;;
    starship-aarch64-apple-darwin.tar.gz)       echo 5362da8cb2928f98f3ce0ffda697cf0f8de70081db000dae316d6d3a404f6cf0 ;;
    starship-x86_64-apple-darwin.tar.gz)        echo 344e4d38787e0aa86dd522ae5462e6fb6da1227691f81a79ffed480a4563ccb3 ;;
  esac
}
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

tool=$1 platform=$2 folder=$3
case "$tool" in
  starship) asset="starship-$platform.tar.gz"
            url="https://github.com/starship/starship/releases/download/$STARSHIP_VERSION/$asset" ;;
  *) exit 1 ;;
esac
want=$(sha_for "$asset")
[ -n "$want" ] || exit 1                       # no pinned checksum for this platform: nothing is downloaded
tmp=$(mktemp -d) || exit 1
part="$folder/.$tool.part-$$"
trap 'rm -rf "$tmp" "$part"' EXIT
curl -fsSL --retry 2 -o "$tmp/$asset" "$url" || exit 1
[ "$(sha256_of "$tmp/$asset")" = "$want" ] || exit 1
# into the folder under a temporary name first (a copy, if the folder is on another disk), then renamed there: the
# program under its own name is always whole, even when this is cut off
place() { mv "$1" "$part" && chmod +x "$part" && mv -f "$part" "$folder/$tool"; }
tar -xzf "$tmp/$asset" -C "$tmp" starship && place "$tmp/starship"
