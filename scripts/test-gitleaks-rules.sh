#!/usr/bin/env bash
# Tests the custom Patreon rules in .gitleaks.toml.
#
# Writes synthetic matching and non-matching samples to a temporary directory
# OUTSIDE the repo, runs `gitleaks detect --no-git` on each one, and checks
# which Patreon rules fire. The samples are built from pieces at runtime so
# this script itself never contains a string the rules would flag.
#
# Usage: scripts/test-gitleaks-rules.sh
# Needs: gitleaks, jq

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="$repo_root/.gitleaks.toml"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# "patreon" + ".com" joined at runtime so no literal host appears here.
host="patreon"
dom="${host}.com"
udom="${host}usercontent.com"
# Low-entropy synthetic tokens: long enough for the rules, not a real value.
tok="$(printf 'x%.0s' {1..24})"

failures=0

# check <name> <expected patreon rule ids, space-separated, or "none"> <sample text>
check() {
  local name="$1" expected="$2" text="$3"
  local dir="$work/$name"
  mkdir -p "$dir"
  printf '%s\n' "$text" > "$dir/sample.txt"

  gitleaks detect --no-git --no-banner --log-level error \
    --source "$dir" --config "$config" \
    --report-format json --report-path "$dir/report.json" --exit-code 0

  local got
  got="$(jq -r '[.[].RuleID | select(startswith("patreon-"))] | unique | join(" ")' "$dir/report.json")"
  [[ -z "$got" ]] && got="none"

  if [[ "$got" == "$expected" ]]; then
    printf 'PASS  %-28s fired: %s\n' "$name" "$got"
  else
    printf 'FAIL  %-28s expected: %s, fired: %s\n' "$name" "$expected" "$got"
    failures=$((failures + 1))
  fi
}

echo "Matching samples (each rule must fire):"
check feed-url        patreon-rss-feed \
  "https://www.${dom}/rss/1234567?auth=${tok}&show=42"
check feed-url-auth-later patreon-rss-feed \
  "<link>https://www.${dom}/rss/1234567?show=42&auth=${tok}</link>"
check enclosure-url   patreon-rss-enclosure \
  "https://www.${dom}/api/rss/u/${tok}/post/1/audio.mp3"
check signed-url      patreon-signed-url \
  "https://c10.${udom}/4/${host}-media/p/post/1/audio.mp3?token-time=1&sig=abc"

echo
echo "Non-matching samples (no Patreon rule may fire):"
check placeholder-auth-redacted none \
  "https://www.${dom}/rss/0?auth-redacted&show=0"
check placeholder-shapes none \
  "feed: https://www.${dom}/rss/<creatorId>?auth=<token>&show=<id>
enclosure: https://www.${dom}/api/rss/u/<per-user-token>/...?sig=<signature>"
check short-enclosure-id none \
  "https://www.${dom}/api/rss/u/short/post/1"
check public-feed none \
  "https://feeds.megaphone.fm/blank-check"

echo
if (( failures > 0 )); then
  echo "$failures check(s) failed."
  exit 1
fi
echo "All checks passed."
