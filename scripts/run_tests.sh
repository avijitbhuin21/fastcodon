#!/usr/bin/env bash
# Run all fastcodon leaf tests on Linux/macOS (the POSIX backend). Each test runs under a
# portable wall-clock watchdog (pure bash — no GNU `timeout`, so it works on macOS too) so a
# misbehaving test fails fast and prints its output instead of hanging CI. P11/P12/P13/P31 are
# required; the TLS (P14) live test needs OpenSSL + network and is allowed to fail (reported).
#
#   ./scripts/run_tests.sh
set -uo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
export CODON_PATH="$repo"
codon="${CODON_HOME:+$CODON_HOME/bin/}codon"
TIMEOUT="${TEST_TIMEOUT:-45}"   # seconds per test

"$repo/scripts/setup.sh"

pass=0; fail=0

# run_test <name> <file> <required:0|1> [extra codon args...]
run_test() {
  local name="$1" file="$2" required="$3"; shift 3
  echo "===== $name ====="
  local log; log="$(mktemp)"
  "$codon" run "$@" "$repo/tests/$file" >"$log" 2>&1 &
  local pid=$! secs=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 1; secs=$((secs+1))
    if [ "$secs" -ge "$TIMEOUT" ]; then
      kill -9 "$pid" 2>/dev/null
      echo "  TIMEOUT after ${secs}s"; sed 's/^/  | /' "$log"
      [ "$required" = "1" ] && fail=$((fail+1)) || echo "  (optional — not counted)"
      rm -f "$log"; return
    fi
  done
  wait "$pid"; local rc=$?
  if [ "$rc" -eq 0 ] && grep -q "^PASS:" "$log"; then
    grep "^PASS:" "$log" | sed 's/^/  /'; pass=$((pass+1))
  else
    sed 's/^/  | /' "$log"
    if [ "$required" = "1" ]; then fail=$((fail+1)); else echo "  (optional — not counted as failure)"; fi
  fi
  rm -f "$log"
}

run_test "sockets (P11)"  test_socket.py    1
run_test "selector (P12)" test_selector.py  1
run_test "crypto (P13)"   test_crypto.py    1
run_test "reactor (P31)"  test_reactor.py   1
# TLS needs system OpenSSL (-lssl -lcrypto) + outbound network; optional in CI.
run_test "tls (P14)"      test_tls_live.py  0  -l ssl -l crypto

echo
echo "==================== summary: $pass passed, $fail failed ===================="
[ "$fail" -eq 0 ]
