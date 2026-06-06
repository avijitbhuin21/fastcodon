# fastcodon

FastAPI, rebuilt natively in [Codon](https://docs.exaloop.io) so an ASGI-class web framework
compiles to machine code and runs at native speed. See [`roadmap.md`](roadmap.md) for the full
dependency graph and bottom-up build order.

## Status

The **L1 native leaves are done and verified** (the foundation everything else stands on):

| Leaf | Module | What it does | Verified |
|------|--------|--------------|----------|
| **Sockets** (P11) | `fastcodon/net/socket.codon` | Cross-platform non-blocking TCP (Winsock / BSD) | ✔️ Windows (JIT + native AOT) |
| **Selector** (P12) | `fastcodon/net/selector.codon` | I/O readiness via `poll`/`WSAPoll` | ✔️ Windows |
| **Crypto** (P13) | `fastcodon/crypto/*` | SHA-1, SHA-256, HMAC-SHA256, base64 (pure Codon) | ✔️ RFC test vectors |
| **TLS** (P14) | `fastcodon/tls/*` | OpenSSL 3.x wrapper, non-blocking handshake | ✔️ live TLS 1.3 + HTTPS GET |
| **Reactor** (P31) | `fastcodon/reactor.codon` | Async event loop: I/O handlers + timers | ✔️ 5-client async echo server |

### Per-platform verification

| Platform | Status |
|----------|--------|
| **Windows** x86_64 | ✔️ runtime-verified — all 5 leaf tests pass under JIT *and* native AOT |
| **Linux** x86_64 / arm64 (glibc) | ✔️ POSIX branches compile to correct LLVM IR + constants audited; runtime gate = CI |
| **macOS** arm64 / x86_64 | ✔️ `__apple__` branches compile to correct IR (`__error` accessor) + audited; runtime gate = CI |

All code is cross-platform by construction: per-OS constants/signatures are selected at compile
time. The Linux/macOS backends were verified statically here — the elided POSIX/`__apple__` branches
were compiled under Linux and macOS configs and emit the right per-OS C symbols (`poll`,
`__errno_location` vs `__error`) with zero Windows symbols — and **executed on real Linux + macOS
runners via `.github/workflows/leaves-ci.yml`** (stock upstream Codon). Local POSIX execution wasn't
possible on the Windows dev box (BIOS virtualization disabled, so WSL2/Docker can't start; no Mac).
To verify locally on a Linux/macOS machine: `./scripts/run_tests.sh`.

## Architecture notes

- **Platform selection is compile-time.** Codon's `__windows__`/`__apple__` defines aren't visible
  in user code, so `fastcodon/sys/config.codon` carries hardcoded `Literal[int]` flags
  (`IS_WINDOWS`/`IS_APPLE`/`IS_LINUX`). A `Literal` is required: it makes `if IS_WINDOWS:` a static
  branch that **elides the other platform's C FFI imports** (so e.g. POSIX-only symbols don't break
  the Windows link). Run `scripts/setup.ps1` / `scripts/setup.sh` once to generate it for your OS.
- **FFI** is declared at top level with distinct per-platform aliases (`_w_*` / `_p_*`); each is
  only *called* inside the matching static branch, so the unused one is elided.
- **Concurrency** is a Handler-object reactor (like Python asyncio transports): subclass `IOHandler`
  and override `on_readable`/`on_writable`. Codon closures don't unify to one callable type, so
  virtual dispatch through a base class is the idiomatic substitute for callbacks.

## Toolchain

You need a native Codon build and (for AOT) a clang for linking.

**Windows (verified setup):**
- Codon install at `C:\codon-dev\codon-next-install` (override with `$env:CODON_HOME`).
- clang for AOT linking, e.g. `C:\Program Files\LLVM\bin` (override with `$env:LLVM_BIN`).
  > Put clang's dir at the **end** of `PATH` — ahead of Codon it shadows a DLL and crashes
  > with `0xC0000139` (ENTRYPOINT_NOT_FOUND).
- Winsock must be linked: `-l ws2_32`. For TLS, also link OpenSSL (see below).

## Build & run

```powershell
# Windows — one-time:
.\scripts\setup.ps1
# run a test under the JIT:
.\scripts\dev.ps1 run   tests\test_socket.py
# build a native binary:
.\scripts\dev.ps1 build tests\test_socket.py test_socket.exe
```

```bash
# Linux / macOS — one-time:
./scripts/setup.sh
./scripts/dev.sh run   tests/test_socket.py
./scripts/dev.sh build tests/test_socket.py test_socket
```

`CODON_PATH` must point at this `codon-libraries/` directory so `import fastcodon...` resolves
(the dev scripts set it for you). Codon finds its own stdlib automatically.

### TLS / OpenSSL linking

The FFI is platform-uniform; only the link differs. **POSIX:** `-lssl -lcrypto` against system
OpenSSL just works. **Windows:** OpenSSL must match Codon's CRT flavor —

- *JIT (verified here):* load the OpenSSL **DLLs** directly, e.g.
  `codon run -l ws2_32 -l <path>\libcrypto-3.dll -l <path>\libssl-3.dll tests\test_tls_live.py`
- *AOT:* link an OpenSSL built against the same CRT as Codon. The vcpkg `x64-windows-static-md`
  static libs currently mismatch Codon's static UCRT (the `__declspec(dllimport)` CRT-symbol
  errors); use a CRT-matched OpenSSL or wire the link to the dynamic UCRT import libs.

## Tests

`tests/` holds one self-contained test per leaf. Each prints `PASS:` on success:
`test_socket` · `test_selector` · `test_crypto` · `test_reactor` · `test_tls_live`
(+ `test_tls_compile`, which validates the TLS module compiles without OpenSSL linked).
