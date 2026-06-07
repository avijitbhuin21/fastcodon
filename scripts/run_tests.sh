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

# --- L1 native leaves ---
run_test "sockets (P11)"   test_socket.py     1
run_test "selector (P12)"  test_selector.py   1
run_test "crypto (P13)"    test_crypto.py     1
run_test "reactor (P31)"   test_reactor.py    1
# --- L2 pure-Codon codecs (sans-I/O) ---
run_test "json (P21)"      test_json.py       1
run_test "urllib (P22)"    test_urllib.py     1
run_test "http (P23)"      test_http.py       1
run_test "websocket (P24)" test_websocket.py  1
run_test "multipart (P25)" test_multipart.py  1
# --- L3 async runtime (real loopback over the reactor) ---
run_test "streams (P32)"     test_streams.py     1
run_test "concurrency (P33)" test_concurrency.py 1
# --- L4 protocol server (real HTTP round-trip over loopback) ---
run_test "asgi server (P41/P42)"    test_server.py          1
run_test "stream response (P42b)"   test_stream_response.py 1
run_test "stream request (P42b)"    test_stream_request.py  1
run_test "websocket server (P43)"   test_websocket_server.py 1
# --- L5 validation (Pydantic-equivalent) ---
run_test "validate (P51-P54)"       test_validate.py        1
run_test "json non-raising (L6.1)"  test_json_safe.py       1
# --- L6 ASGI toolkit (Starlette-equivalent) ---
run_test "datastructures (P61)"     test_datastructures.py     1
run_test "requests/responses (P62)" test_requests_responses.py 1
run_test "routing (P63)"            test_routing.py            1
run_test "middleware (P64)"         test_middleware.py         1
run_test "webapp e2e (L6)"          test_webapp_server.py      1
run_test "ws routing (P65)"         test_ws_routing.py         1
run_test "staticfiles (P65)"        test_staticfiles.py        1
run_test "background tasks (P65)"   test_background.py         1
run_test "exceptions (P65)"         test_exceptions.py         1
run_test "sessions (L6.1)"          test_sessions.py           1
run_test "compress/gzip (L6.1)"     test_compress.py           1
run_test "gzip middleware (L6.1)"   test_gzip_middleware.py    1
# TLS needs system OpenSSL (-lssl -lcrypto) + outbound network; optional in CI.
run_test "tls (P14)"       test_tls_live.py   0  -l ssl -l crypto

echo
echo "==================== summary: $pass passed, $fail failed ===================="
[ "$fail" -eq 0 ]
