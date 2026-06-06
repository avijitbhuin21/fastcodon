#!/usr/bin/env bash
# fastcodon dev helper (Linux/macOS). Sets the Codon env, then runs/builds.
#
#   ./scripts/dev.sh run   tests/test_socket.py
#   ./scripts/dev.sh build tests/test_socket.py out
#
# On POSIX, libc already exports socket/epoll/kqueue symbols, so no `-l` is needed for the
# net leaves (TLS will add `-lssl -lcrypto`). Override CODON_HOME if codon isn't on PATH.
set -euo pipefail

mode="${1:?usage: dev.sh run|build <script> [out]}"
script="${2:?missing script}"
out="${3:-a.out}"

repo="$(cd "$(dirname "$0")/.." && pwd)"
export CODON_PATH="$repo"
codon="${CODON_HOME:+$CODON_HOME/bin/}codon"   # else assume `codon` on PATH

case "$mode" in
  run)   exec "$codon" run "$script" ;;
  build) "$codon" build -o "$out" "$script" && echo "built: $out" ;;
  *)     echo "unknown mode: $mode" >&2; exit 2 ;;
esac
