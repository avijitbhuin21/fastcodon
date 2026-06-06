#!/usr/bin/env bash
# Run all fastcodon leaf tests on Linux/macOS (the POSIX backend). Verifies P11/P12/P13/P31
# unconditionally; the TLS (P14) live test additionally needs OpenSSL + network and is allowed
# to be skipped offline. Exits non-zero if any required test fails.
#
#   ./scripts/run_tests.sh
set -uo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
export CODON_PATH="$repo"
codon="${CODON_HOME:+$CODON_HOME/bin/}codon"

# Regenerate the platform config for this host (Linux/macOS).
"$repo/scripts/setup.sh"

pass=0; fail=0
run() {  # run <name> <file> [extra codon args...]
  local name="$1"; local file="$2"; shift 2
  echo "===== $name ====="
  if out="$("$codon" run "$@" "$repo/tests/$file" 2>&1)"; then
    echo "$out" | tail -1
    if echo "$out" | grep -q "^PASS:"; then pass=$((pass+1)); else echo "$out"; fail=$((fail+1)); fi
  else
    echo "$out"; fail=$((fail+1))
  fi
}

# Core leaves — no external libs needed (libc provides sockets/poll; crypto is pure Codon).
run "sockets (P11)"  test_socket.py
run "selector (P12)" test_selector.py
run "crypto (P13)"   test_crypto.py
run "reactor (P31)"  test_reactor.py

# TLS (P14) — link system OpenSSL. Network failure is reported but not fatal (CI may be offline).
echo "===== tls (P14, OpenSSL + network) ====="
if tls_out="$("$codon" run -l ssl -l crypto "$repo/tests/test_tls_live.py" 2>&1)"; then
  echo "$tls_out" | tail -1
  echo "$tls_out" | grep -q "^PASS:" && pass=$((pass+1)) || echo "(tls: no PASS — likely offline; not counted as failure)"
else
  echo "$tls_out" | tail -2
  echo "(tls: link/run failed — see above; not counted as a hard failure here)"
fi

echo
echo "==================== summary: $pass passed, $fail failed ===================="
[ "$fail" -eq 0 ]
