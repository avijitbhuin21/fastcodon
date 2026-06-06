# Codon-FastAPI — Roadmap

**Goal:** Recreate **FastAPI** — to *full feature parity* — in **pure Codon**, so that an
ASGI-class web framework compiles to native machine code and runs at native speed (no CPython
interpreter, no Rust `pydantic-core`, no C extension shims). The output is a Codon library
(`codon-libraries/`) you can `import` to write FastAPI-style apps that build to a standalone binary.

**Locked architectural decisions (2026-06-06):**

| Decision | Choice | Consequence for the graph |
|----------|--------|---------------------------|
| Concurrency model | **Native async event loop** (real `epoll`/`kqueue`/IOCP + coroutines) | The deepest leaf is an *I/O reactor*, not a thread pool. Highest perf ceiling, hardest bottom layer. |
| Feature scope | **Full FastAPI parity** | OpenAPI/Swagger UI, WebSockets, background tasks, full dependency injection, security utilities all enter the graph. |
| Platform | **Cross-platform from day one** | The socket + selector + TLS leaves are abstracted behind a platform shim with Windows *and* POSIX backends built together. |

---

## 0. Master checklist — what we need / what we have / what to build

**Legend:** ✅ have (Codon stdlib, import & use) · ⚠️ partial (exists but needs extension) ·
❌ build (net-new) · ⬜ not started · 🔄 in progress · ✔️ done+verified

> **Progress (2026-06-06):** the **L1 native leaves are DONE** — `fastcodon/net/socket.codon`
> (P11), `fastcodon/net/selector.codon` (P12), `fastcodon/crypto/*` (P13), `fastcodon/tls/*` (P14),
> and the async reactor `fastcodon/reactor.codon` (P31).
>
> **The full L2 codec layer is now DONE** (all pure-Codon, JIT-verified green on Windows): JSON
> enc/dec `fastcodon/json/*` (P21), URL/query/cookies/HTTP-dates `fastcodon/urllib/*` (P22), the
> sans-I/O HTTP/1.1 parser `fastcodon/http/*` (P23), the WebSocket frame codec + handshake
> `fastcodon/websocket/*` (P24), and the multipart/form-data parser `fastcodon/multipart/*` (P25).
> **L3 async runtime** `fastcodon/aio/*` is DONE: streams (P32, buffered read/write + backpressure
> over the callback reactor via Completion/Continuation objects, since Codon has no `await`) and
> structured concurrency (P33, CancelScope/TaskGroup/Event/Semaphore/sleep on the timer queue).
> **L4 is underway: the ASGI server core + HTTP/1.1 transport (P41/P42) are DONE** —
> `fastcodon/asgi/*` accepts connections on the reactor, parses requests via the `http` parser,
> drives an `ASGIApp.handle(scope, body) -> Response` (buffered v1; streaming receive/send deferred),
> serializes the response, and does keep-alive. **Milestone hit: a real server serves
> `{"hello":"world"}` over an actual TCP socket** (`tests/test_server.py`).
>
> Each component ships a green test in `tests/`. **Whole suite: 13/13 tests pass**, runtime-verified
> on Windows real hardware AND the Linux x86_64/arm64 + macOS arm64 CI matrix (macOS x86_64 is
> gated on the scarce, deprecated Intel runner). A macOS-only non-blocking-connect bug (ENOTCONN)
> was caught by CI and fixed (`Socket.so_error()` + a `connecting` state in the stream).
>
> **Cross-platform verification matrix — runtime-verified on real hardware/CI:**
> - **Windows** x86_64 — ✔️ JIT + native AOT: TCP echo, selector echo, RFC crypto vectors, a
>   5-client async echo server, and a real **TLS 1.3 handshake + HTTPS GET**.
> - **Linux x86_64** — ✔️ green on CI runner (stock upstream Codon v0.19.6).
> - **Linux arm64** (glibc) — ✔️ green on CI runner.
> - **macOS arm64** (Apple Silicon) — ✔️ green on CI runner.
> - **macOS x86_64** — same code; CI gated on a (scarce, deprecated) Intel runner.
>
> CI: `.github/workflows/leaves-ci.yml` on `github.com/avijitbhuin21/fastcodon`. Three real bugs
> that the Windows-only build masked were caught and fixed by running on real Linux/macOS:
> 1. stock Codon uses `str.ptr`/`.len` (the fork uses `_ptr`/`_len`) → access bytes only via the
>    public `ord()`/`str(ptr,len)` API (`fastcodon/sys/buf.codon`);
> 2. stock Codon's parser rejects `0o` octal literals → use decimal;
> 3. **Apple-arm64 variadic ABI:** `fcntl(int,int,...)` passes varargs on the *stack* on Apple
>    Silicon, so a fixed-arity FFI decl put `O_NONBLOCK` in a register → `setblocking()` silently
>    failed → `accept()` blocked and hung the reactor. Fixed by declaring `fcntl` variadic (`...`).
>    (x86_64 and Linux-arm64 pass varargs in registers, so only Apple Silicon was affected.)
>
> See `codon-libraries/README.md` for the toolchain + how to build/run.

Update the **Done** column as phases go green. The **Need-it-for** column traces each item back to
the FastAPI feature that requires it, so nothing is built that the graph doesn't actually need.

### L1 — Native leaves (OS / C-FFI primitives)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| Sockets (create/bind/listen/accept/connect/recv/send/close, non-blocking) | FFI: Winsock2 / BSD | ❌ build | `P11` | ✔️ | Every byte in/out — the whole server |
| I/O selector (`poll`/`WSAPoll`; epoll/kqueue later) | FFI | ❌ build | `P12` | ✔️ | Async reactor readiness |
| crypto: SHA-1, SHA-256, HMAC, base64/base64url | pure-Codon | ❌ build | `P13` | ✔️ | WS handshake, JWT/OAuth2 |
| TLS (handshake + read/write) | FFI: OpenSSL | ❌ build | `P14` | ✔️ | HTTPS / WSS (deferrable to 1.x) |
| Regex (`re`) | ✅ stdlib | ✅ have | — | ✔️ | Route path converters |
| Monotonic clock / `time` | ✅ stdlib | ✅ have | — | ✔️ | Timers, timeouts, HTTP `Date` |
| Threads (`threading`) | ✅ stdlib | ✅ have | — | ✔️ | `run_in_threadpool` for blocking deps |
| `datetime` | ✅ stdlib | ✅ have | — | ✔️ | RFC 7231 dates, cookie expiry |
| `bytes` / UTF-8 / `simd` | ✅ stdlib | ✅ have | — | ✔️ | All parsing & framing |
| C-FFI machinery (`c_stubs`, `dlopen`) | ✅ stdlib | ✅ have | — | ✔️ | Reaching every FFI leaf |
| Coroutine scheduler (`Future`/`Task`/`Timer`/`EventLoop`) | ⚠️ `asyncio.codon` (972 ln) | ⚠️ partial | `P31` | ✔️ | Reactor built as a callback/Handler loop atop the Selector (P31 done) |

### L2 — Pure-Codon codecs (sans-I/O)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| JSON encoder + decoder | pure-Codon | ❌ build | `P21` | ✔️ | Request/response bodies, Pydantic, OpenAPI |
| URL / percent-encoding / query-string | pure-Codon | ❌ build | `P22` | ✔️ | Routing, `QueryParams`, `url_for` |
| Cookies (parse/serialize) | pure-Codon | ❌ build | `P22` | ✔️ | Sessions, `Cookie` params |
| HTTP date formatting (RFC 7231) | pure-Codon (`datetime`✓) | ❌ build | `P22` | ✔️ | Response headers |
| HTTP/1.1 parser (sans-io state machine) | pure-Codon | ❌ build | `P23` | ✔️ | The HTTP transport |
| WebSocket frame codec + handshake (RFC 6455) | pure-Codon (`P13`) | ❌ build | `P24` | ✔️ | WebSocket support |
| multipart/form-data parser | pure-Codon | ❌ build | `P25` | ✔️ | `Form`/`File` uploads |

### L3 — Async runtime (reactor + anyio-equivalent)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| Async I/O reactor (Handler-based loop + timers over the Selector) | pure-Codon (`P12`) | ❌ build | `P31` | ✔️ | All async I/O |
| Async socket streams (read/write coros, backpressure) | pure-Codon (`P31`,`P14`) | ❌ build | `P32` | ✔️ | HTTP/WS transports |
| anyio-equiv: task groups, cancel scopes, timeouts, memory streams | pure-Codon (`threading`✓) | ❌ build | `P33` | ✔️ | Structured concurrency, Starlette — CancelScope/TaskGroup/Event/Semaphore/sleep on the timer queue (`aio/scope,taskgroup,sync,sleep`) |

### L4 — Protocol servers (uvicorn-equivalent)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| ASGI server core (lifespan, scope/receive/send, shutdown) | pure-Codon (`P32`) | ❌ build | `P41` | ✔️ | Hosting any ASGI app — v1 `ASGIApp.handle(scope,body)->Response` (buffered; streaming send/recv deferred) |
| HTTP transport (parser↔streams, keep-alive, streaming) | pure-Codon (`P23`,`P32`) | ❌ build | `P42` | ✔️ | Serving HTTP — accept loop + continuation state machine; keep-alive; serves `{"hello":"world"}` |
| Streaming ASGI `receive`/`send` (chunked request body in, streamed response out) | pure-Codon (`P42`,`P32`) | ❌ build | `P42b` | ⬜ | Large/streamed payloads — enriches the buffered v1 `handle(scope,body)->Response` contract (the part deferred in `P41`/`P42`) |
| WebSocket transport (upgrade + codec over streams) | pure-Codon (`P24`,`P32`) | ❌ build | `P43` | ⬜ | Serving WS |
| HTTP/2 | pure-Codon | ❌ build | `P44` | ⬜ | Optional parity (1.x) |

### L5 — Validation / serialization (Pydantic-equivalent, compile-time core)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| Schema/model layer (compile-time field metadata) | pure-Codon (static introspection✓) | ❌ build | `P51` | ⬜ | Models, params, DI |
| Validation engine (coercion/constraints/unions/nested) | pure-Codon (compile-time) | ❌ build | `P52` | ⬜ | Request validation, 422 errors |
| Serializers (model → dict/JSON) | pure-Codon (`P21`) | ❌ build | `P53` | ⬜ | `response_model` |
| JSON-Schema generation | pure-Codon | ❌ build | `P54` | ⬜ | OpenAPI document |

### L6 — ASGI toolkit (Starlette-equivalent)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| Datastructures (`Headers`/`URL`/`QueryParams`/`FormData`/`UploadFile`) | pure-Codon (`P22`,`P25`) | ❌ build | `P61` | ⬜ | Request/response surface |
| Requests / Responses (JSON/Streaming/File/Redirect) | pure-Codon (`P21`,`P32`) | ❌ build | `P62` | ⬜ | Handler I/O |
| Routing (path compile, converters, mounts, `url_for`) | pure-Codon (`re`✓,`P22`) | ❌ build | `P63` | ⬜ | Dispatch |
| Middleware (errors, CORS, GZip, TrustedHost, sessions) | pure-Codon (`P33`) | ❌ build | `P64` | ⬜ | Cross-cutting concerns |
| WS endpoints / Background tasks / StaticFiles / exc handlers | pure-Codon | ❌ build | `P65` | ⬜ | Parity features |
| Templating (Jinja2-equiv) | pure-Codon | ❌ build | `P65` | ⬜ | Optional / late add |

### L7 — FastAPI layer (full parity)

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| App + APIRouter + decorators (`@app.get/post/...`) | pure-Codon (`P63`) | ❌ build | `P71` | ⬜ | The public API |
| Param declaration (`Path`/`Query`/`Header`/`Cookie`/`Body`/`Form`/`File`) | pure-Codon (`P52`) | ❌ build | `P72` | ⬜ | Typed endpoints |
| Dependency Injection (`Depends`, sub-deps, `yield`, caching) | pure-Codon (compile-time) | ❌ build | `P73` | ⬜ | DI system |
| OpenAPI generation + Swagger UI + ReDoc | pure-Codon (`P54`,`P65`) | ❌ build | `P74` | ⬜ | `/docs`, `/redoc` |
| Security utils (OAuth2/API-key/Basic/Bearer/JWT) | pure-Codon (`P13`) | ❌ build | `P75` | ⬜ | Auth |
| Error model (`HTTPException`, `RequestValidationError`→422) | pure-Codon (`P52`) | ❌ build | `P76` | ⬜ | Error responses |
| Test client (in-process ASGI) | pure-Codon (`P41`) | ❌ build | `P77` | ⬜ | The test suite |

### Tooling / project

| Component | Source | Status | Phase | Done | Need-it-for |
|-----------|--------|:------:|:-----:|:----:|-------------|
| Library layout + test harness + smoke target | — | ❌ build | `P00` | ⬜ | Everything |
| Parity test port (FastAPI tutorial apps) | — | ❌ build | `P81` | ⬜ | Correctness proof |
| Benchmarks vs CPython uvicorn+FastAPI | — | ❌ build | `P82` | ⬜ | The perf claim |

**Tally:** 9 ✅ have · 1 ⚠️ partial (extend) · ~37 ❌ to build. The 9 we have collapse most of the
classic "hard" leaves (regex, threads, timers, coroutine scheduler) — the real net-new work is
**sockets+selector+TLS (L1)**, the **codecs (L2)**, and everything pure-Codon above the reactor.

---

## 0.5 Build vs. borrow — sourcing strategy

Not every ❌ has to be written from scratch. Codon links C trivially via FFI (it already FFIs
zlib/bz2/OpenBLAS/OpenSSL), and Rust crates can be reused by building a `cdylib` with a `extern "C"`
ABI (one `cbindgen` header). So each component has up to three paths:

- **🔨 Build (pure Codon)** — the *value-add*. Things that either don't exist elsewhere or where
  Codon's compile-time type knowledge is the whole point (validation, the framework itself). No
  borrow can match a compile-time-generated validator.
- **📦 Borrow (FFI)** — *commodity or dangerous* plumbing where a mature library is strictly better
  than anything we'd write (TLS, crypto) or saves weeks at equal quality (HTTP parser, JSON).
- **⚖️ Either** — viable both ways; pick per the **purity vs. speed-to-v1** trade-off below.

**Guiding principle — "borrow to bootstrap, replace to purify."** Borrowing a C/Rust lib still
produces a native binary, just not pure-Codon *source*, and adds cross-platform link work (the
exact Windows pain in `PLAN.md`). So: borrow the hard commodity leaves to reach a working v1 fast,
then optionally reimplement them in pure Codon later, leaf-by-leaf, behind the same interface —
each swap is invisible to everything above it (that's the payoff of the bottom-up graph).

### Sourcing table

**Strategy:** 🔨 build pure-Codon · 📦 borrow (FFI) · ⚖️ either. **Lib?** = worth releasing as a
standalone Codon library, reusable beyond FastAPI.

| Component | Strategy | Community options to reuse (lang) | Lib? | Recommendation |
|-----------|:--------:|-----------------------------------|:----:|----------------|
| **TLS** | 📦 **borrow** | OpenSSL, mbedTLS, BearSSL (C); **rustls** (Rust, memory-safe); SChannel (Win native) | ✅ `tls` | **Never hand-roll TLS.** OpenSSL (already in our toolchain, cross-platform) or rustls-ffi for safety. |
| **crypto** (SHA1/256, HMAC, base64) | ⚖️ either | libsodium, OpenSSL `libcrypto` (C); single-header SHA/HMAC | ✅ `crypto` | Tiny & self-contained → **build** pure-Codon; or reuse `libcrypto` *if* TLS already pulls OpenSSL. |
| **HTTP/1.1 parser** | 📦 **borrow** | **llhttp** (C, Node.js), **picohttpparser** (C, tiny); httparse (Rust) | ✅ `http` | Borrow **llhttp** (prod-grade, chunked/keep-alive) or picohttpparser (simplest). Decades of edge-cases baked in. |
| **JSON** | ⚖️ either | **yyjson** (C, fast r/w), **simdjson** (C++, fastest parse), RapidJSON (C++); serde_json (Rust) | ✅ `json` | **Both:** borrow yyjson for the *dynamic* path now; build a pure-Codon *compile-time* codec for typed models (monomorphic → the perf edge CPython can't get). |
| **WebSocket codec** | ⚖️ either | wslay (C); tungstenite (Rust) | ✅ `websocket` | Framing is a small state machine → **build**; handshake reuses `crypto`. Borrow only if schedule slips. |
| **HTTP/2** | 📦 **borrow** | **nghttp2** (C) | ✅ ext | Complex HPACK/flow-control → borrow nghttp2 when we get to `P44`. |
| **Sockets** | ⚖️ either | **libuv** (C); raw Winsock/BSD | ✅ `net` | Thin syscall shim (small) — **build**; *or* fold into libuv (see fork below). |
| **I/O selector / reactor** | ⚖️ either | **libuv** (C, epoll+kqueue+**IOCP**), libev, libevent | ✅ `net` | The **big decision** — see "libuv fork" below. Borrowing libuv erases the #1 risk (Windows IOCP). |
| **URL / query parsing** | ⚖️ either | **ada** (C++, WHATWG URL, Node.js); http-parser url | ✅ `urllib` | **Build** (small); borrow ada only if we need strict WHATWG conformance. |
| **multipart/form-data** | 🔨 build | multipart-parser-c (C) | — | Simple boundary state machine → **build**. |
| **Validation engine** (Pydantic-equiv) | 🔨 **build** | *(pydantic-core is Rust but runtime-reflection — wrong model for us)* | ✅ `validate` | **Build pure-Codon.** This is the compile-time superpower — **cannot** be borrowed. The core differentiator. |
| **ASGI server / HTTP+WS transport** | 🔨 build | *(mongoose/h2o/libmicrohttpd exist but own the socket loop — breaks the ASGI contract)* | ✅ `asgi` | **Build.** The server *is* the framework; a borrowed server can't expose our `scope/receive/send`. |
| **Routing, datastructures, middleware** | 🔨 build | — | ⚖️ | **Build** — pure framework logic (uses `re`✓). |
| **DI / params / OpenAPI / security / FastAPI layer** | 🔨 build | — | — | **Build.** The whole point of the project; nothing to borrow. |
| **Swagger UI / ReDoc assets** | 📦 vendor | Swagger-UI, ReDoc (static JS/CSS bundles) | — | **Vendor** the static bundles (not code we write); just serve them. |

### The "libuv fork" — the one big borrow decision

The single highest-leverage borrow is **libuv** (the C event-loop library behind Node.js and
`uvloop`). It bundles **sockets + cross-platform readiness/completion (epoll, kqueue, *and* Windows
IOCP) + timers + thread pool** in one mature, MIT-licensed lib. Two paths:

- **A — Borrow libuv for L1/L3.** Collapses `P11`+`P12`+`P31`+`P32` into writing Codon bindings.
  **Pros:** erases the project's #1 risk (Windows IOCP, §6), instant cross-platform, battle-tested.
  **Cons:** a C dependency to build/link on all 3 platforms; an impedance mismatch to bridge between
  libuv's callback/completion model and Codon's `asyncio` coroutine scheduler.
- **B — Pure-Codon reactor.** Build sockets + selector + reactor ourselves on raw syscalls.
  **Pros:** truly single-source, full control, no extra link deps. **Cons:** we own the IOCP-vs-
  readiness platform split — the hardest, riskiest code in the plan.

> **Recommendation:** strongly consider **A (libuv) for v1** to de-risk Windows and reach a running
> server fast, then keep **B** as a "purify" follow-up behind the same `net`/reactor interface.
> *(This is the one open decision worth making before `P11` — flagged in §5 / §8.)*

### What this means — the borrow/build split

- **Must borrow (don't ever build):** TLS, HTTP/2. *(2)*
- **Strongly recommend borrowing to bootstrap:** HTTP/1.1 parser, JSON (dynamic path), and —
  pending the fork above — possibly the whole socket+reactor layer via libuv. *(~2–4)*
- **Build pure-Codon (the value-add, ~25+ components):** the validation engine, serializers,
  JSON-Schema, ASGI server, HTTP/WS transport logic, routing, datastructures, middleware, DI,
  param binding, OpenAPI, security, multipart, and the entire Starlette+FastAPI surface.

**Net:** roughly **4–6 commodity leaves can be borrowed** to slash risk and time; the **framework's
differentiating ~25+ pieces are ours to build** — exactly where Codon's compile-time speed wins.

### Standalone libraries to spin out (reusable beyond FastAPI)

These are worth structuring as independent Codon packages from day one (the bottom-up order builds
them in isolation anyway), valuable to the wider Codon ecosystem on their own:

`json` · `crypto` · `tls` · `http` (parser) · `websocket` · `net`/`asyncnet` (sockets+selector+
reactor+streams) · `validate` (Pydantic-equivalent) · `urllib`. **→ 8 reusable libraries** fall out
of this project as a side effect.

---

## 1. Methodology — graph first, then build bottom-up

This roadmap is driven by a **dependency graph**, exactly as specified:

1. **Decompose top-down.** Start at the root (`FastAPI`). Branch to everything it depends on.
   Branch each of those to *their* dependencies. Recurse until every path terminates at a
   **leaf** — a "very lowest level" primitive that depends on nothing further inside our scope
   (an OS syscall via C FFI, or a self-contained pure-Codon algorithm).
2. **Stop at the leaves.** A node is a leaf when it bottoms out at one of:
   - the OS / libc / Winsock / OpenSSL (reached through Codon's C FFI), or
   - a self-contained algorithm with no internal dependencies (e.g. a JSON tokenizer), or
   - **something Codon's stdlib already provides** (see §3 — these are pre-satisfied leaves).
3. **Implement bottom-up.** Build the leaves first, verify each in isolation, then build each
   layer only once *all* of its dependencies are green. Nothing is started before its children
   exist. The graph's topological order *is* the build order.

> **Why bottom-up:** every upper node is defined in terms of native, already-tested lower nodes,
> so each layer is the only new variable when something breaks. No mocks, no stubs to revisit.

---

## 2. The dependency graph

### 2.1 Layered DAG (root at top, leaves at bottom)

```
                                ┌───────────────────────────┐
  L7  FastAPI layer             │          FastAPI          │
                                └──────────────┬────────────┘
                          ┌────────────────────┼─────────────────────┐
                          ▼                    ▼                      ▼
  L6  ASGI toolkit  ┌──────────┐        ┌────────────┐        ┌──────────────┐
      (Starlette)   │ Routing  │        │ Requests/  │        │  Middleware  │
                    │ Responses│        │ WebSocket  │        │  Background  │
                    └────┬─────┘        │ endpoints  │        │  StaticFiles │
                         │              └─────┬──────┘        └──────┬───────┘
              ┌──────────┴───────┬────────────┴───────────┬─────────┘
              ▼                  ▼                         ▼
  L5  Validation/serialize  ┌─────────────┐        L4  Protocol servers
      (Pydantic-equiv)      │  Datastruct │            ┌──────────────────┐
      ┌───────────────┐     │ Headers/URL │            │ ASGI server core │
      │ Schema/model  │     │ QueryParams │            │  (uvicorn-equiv) │
      │ Validators    │     │ FormData    │            │  HTTP transport  │
      │ Serializers   │     │ UploadFile  │            │  WS transport    │
      │ JSON-Schema   │     └──────┬──────┘            └────────┬─────────┘
      └───────┬───────┘            │                            │
              │                    │           ┌────────────────┴──────────┐
              │                    │           ▼                           ▼
  L3  Async runtime          ┌──────────────────────┐         ┌──────────────────────┐
      (anyio-equiv)          │  Async socket streams│         │   anyio-equivalent   │
                             │  read()/write() coros│         │ task groups / cancel │
                             └───────────┬──────────┘         │  sync primitives     │
                                         │                    └──────────┬───────────┘
                                         └─────────────┬─────────────────┘
                                                       ▼
                                         ┌──────────────────────────┐
                                         │   Async I/O reactor      │  ← integrate selector
                                         │ (add_reader/add_writer,  │    into Codon's EXISTING
                                         │  proactor on Windows)    │    asyncio EventLoop
                                         └────────────┬─────────────┘
              ┌────────────────────────┬──────────────┼─────────────┬──────────────────────┐
  L2 pure-   ▼                ▼        ▼               │             ▼            ▼          ▼
  Codon  ┌───────┐      ┌──────────┐ ┌─────────┐      │       ┌──────────┐ ┌──────────┐ ┌────────┐
  codecs │ JSON  │      │ HTTP/1.1 │ │WebSocket│      │       │ multipart│ │ URL/query│ │ Cookies│
         │enc/dec│      │  parser  │ │frame +  │      │       │  parser  │ │ percent- │ │ HTTP   │
         │       │      │ (sans-io)│ │handshake│      │       │          │ │ encoding │ │ dates  │
         └───┬───┘      └────┬─────┘ └────┬────┘      │       └────┬─────┘ └────┬─────┘ └───┬────┘
             │               │            │           │            │            │           │
  L1 native  ▼               ▼            ▼           ▼            ▼            ▼           ▼
  leaves  ┌──────────────────────────────────────────────────────────────────────────────────┐
  (FFI /  │  Sockets(FFI)   I/O selector(FFI)   TLS(FFI)   crypto: SHA1/SHA256/HMAC/base64     │
  stdlib) │  Winsock/BSD    epoll/kqueue/IOCP   OpenSSL/   ─────────────────────────────────── │
          │                                     SChannel   [stdlib✓] re · time · threading ·   │
          │                                                datetime · bytes/UTF-8 · simd        │
          └──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 The same graph as an explicit edge list (who-depends-on-whom)

```
FastAPI
├── Routing (L6)                        ── re✓, URL/query(L2), Validation(L5)
├── Requests/Responses (L6)             ── Datastructures(L6), JSON(L2), Async streams(L3)
├── WebSocket endpoints (L6)            ── WS transport(L4), WS codec(L2)
├── Middleware/Background/Static (L6)   ── Async runtime(L3), Datastructures(L6)
├── Dependency Injection (L7)           ── Validation(L5), introspection (compile-time)
├── OpenAPI + Swagger/ReDoc (L7)        ── JSON-Schema(L5), JSON(L2), StaticFiles(L6)
├── Security utils (OAuth2/JWT) (L7)    ── crypto(L1), base64(L1), JSON(L2)
│
├── Pydantic-equiv  (L5) ─────────────► JSON(L2), typing/introspection (compile-time✓)
│   ├── Schema/model      (compile-time field metadata)
│   ├── Validators        (coercion, constraints, unions, nested)
│   ├── Serializers       (model → dict/JSON)
│   └── JSON-Schema gen
│
├── Starlette-equiv (L6) ─────────────► ASGI server(L4), Async runtime(L3), codecs(L2)
│
└── uvicorn-equiv   (L4) ─────────────► HTTP parser(L2), WS codec(L2), Async runtime(L3)
        └── Async runtime (L3) ───────► Async reactor(L3 base) ─► Sockets+Selector+TLS (L1)
                └── Async reactor ─────► EXTENDS Codon's asyncio EventLoop (coro scheduler✓)
```

### 2.3 Leaf inventory — "the very lowest level we have"

These are where every branch terminates. Build order starts here.

| Leaf | Status | How it bottoms out |
|------|--------|--------------------|
| **Sockets** | ❌ build (FFI) | `socket/bind/listen/accept/connect/recv/send/close`, non-blocking, `SO_REUSEADDR`. Winsock2 vs BSD behind a shim. |
| **I/O selector** | ❌ build (FFI) | `epoll` (Linux), `kqueue` (macOS/BSD), IOCP or `WSAPoll` (Windows). One `Selector` interface, 3 backends. |
| **TLS** | ❌ build (FFI) | OpenSSL (POSIX) / SChannel (Windows) for HTTPS + WSS. Can be deferred to a sub-milestone. |
| **crypto** (SHA-1, SHA-256, HMAC, base64) | ❌ build | SHA-1+base64 for the WebSocket handshake; SHA-256/HMAC/base64url for JWT/OAuth2. Pure-Codon or OpenSSL FFI. |
| `re` (regex) | ✅ stdlib | Route path compilation & converters. |
| `time` / monotonic clock | ✅ stdlib | Timers, timeouts, HTTP `Date`. |
| `threading` | ✅ stdlib | Thread-pool offload for blocking deps (`run_in_threadpool`). |
| `datetime` | ✅ stdlib | RFC 7231 date formatting, cookie expiry. |
| `bytes` / UTF-8 / `simd` | ✅ stdlib | All parsing & framing. |
| **coroutine scheduler** (`Future`/`Task`/`Timer`/`EventLoop`) | ⚠️ partial — `asyncio.codon` exists | **Reuse it.** It schedules coroutines + timers but has **no I/O readiness**. The L3 reactor's job is to *add* `add_reader`/`add_writer` and drive it from the selector. |

---

## 3. Grounding: what Codon already gives us vs. the gaps

Measured against `codon-next/stdlib/` so the graph distinguishes "build" from "already have":

**Pre-satisfied leaves (import, don't reimplement):**
`threading`, `time`, `datetime`, `re`, `collections`, `itertools`, `functools`, `operator`,
`heapq`, `bisect`, `random`, `string`, `simd`, `pickle`, `gzip`/`bz2`, and the C-FFI machinery
(`internal.c_stubs`, `internal.dlopen`).

**The reusable async half — `stdlib/asyncio.codon` (972 lines):**
Ships a real `EventLoop` with `Future`, `Task`, `Timer`, `TimerHandle`, `run()`,
`run_until_complete()`, `create_task()`, `gather()`. **But it is a compute+timer scheduler only**
— grep confirms **no** `add_reader`/`add_writer`/`selector`/socket awareness. This is the single
most important grounding fact: our async leaf is *not* "write an event loop from scratch," it is
**"bolt an I/O reactor onto the existing scheduler."**

**True gaps we must build (the ❌ leaves + the L2 codecs):**
`socket`, I/O `selector`, `ssl/TLS`, `json`, `http` (HTTP/1.1 parser), WebSocket frame codec,
`multipart`, URL/percent-encoding/query-string, cookies, crypto (SHA-1/256, HMAC, base64).

**The Codon-native opportunity (why this beats CPython FastAPI, not just ties it):**
Pydantic (L5) in CPython needs a Rust core (`pydantic-core`) because Python types are runtime
values. **Codon knows every type at compile time.** So validators and serializers can be
*generated at compile time* from the annotations — monomorphic, branch-predictable, zero
reflection. Likewise the DI graph (L7) and OpenAPI schema (L7) are largely computable at compile
time. Design the L5/L7 layers around `static[...]` / compile-time introspection, not runtime dicts.

---

## 4. Bottom-up build order (the topological schedule)

Each phase builds only on green phases below it. **`PXX` = phase id; verify-before-ascend.**

### Phase 0 — Project scaffolding
- `P00` Library layout under `codon-libraries/` (module tree mirroring the layers), a test
  harness pattern, and a tiny `codon run` smoke target. Decide naming (e.g. `fastcodon`).

### Phase 1 — L1 native leaves (FFI)  ⟵ *start here*
- `P11` **Sockets shim** — cross-platform `socket` over Winsock2 / BSD via FFI: create, bind,
  listen, accept, connect, recv, send, close, non-blocking, options. *Verify:* blocking
  echo server/client round-trip on Windows **and** POSIX.
- `P12` **I/O selector** — one `Selector` interface; `epoll`/`kqueue`/`WSAPoll`(or IOCP) backends.
  *Verify:* register N non-blocking sockets, get correct readiness events on all platforms.
- `P13` **crypto primitives** — SHA-1, SHA-256, HMAC-SHA256, base64/base64url. *Verify:* RFC
  test vectors. (Pure-Codon first; OpenSSL-FFI optional later for speed.)
- `P14` **TLS** *(may run in parallel / be deferred to a 1.x milestone)* — OpenSSL / SChannel
  handshake + read/write. *Verify:* HTTPS GET against a known host.

### Phase 2 — L2 pure-Codon codecs (sans-I/O, unit-testable in isolation)
- `P21` **JSON** encoder + decoder. *Verify:* JSON test suite (RFC 8259), round-trip, numbers,
  unicode, big payloads.
- `P22` **URL / percent-encoding / query-string** parse+build; **cookies**; **HTTP dates** (RFC 7231).
- `P23` **HTTP/1.1 parser** (sans-io, h11-style state machine): request line, headers, body,
  `Content-Length`, chunked transfer, keep-alive, pipelining. *Verify:* malformed-input corpus,
  chunked edge cases.
- `P24` **WebSocket frame codec + handshake** (RFC 6455): masking, fragmentation, control frames,
  close codes; `Sec-WebSocket-Accept` via `P13` SHA-1+base64. *Verify:* Autobahn-style cases.
- `P25` **multipart/form-data** streaming parser (boundaries, headers, file parts). *Verify:*
  multi-file uploads, boundary-split-across-reads.

### Phase 3 — L3 async runtime (the reactor + anyio-equivalent)
- `P31` **Async I/O reactor** — extend `asyncio.EventLoop` with `add_reader`/`add_writer`
  (proactor on Windows if IOCP), driven by `P12`'s selector + the existing timer heap.
  *Verify:* an awaitable accept-loop that echoes over real sockets.
- `P32` **Async socket streams** — `recv`/`send` coroutines, buffering, backpressure, half-close;
  optional TLS stream wrapping `P14`. *Verify:* concurrent streamed transfers.
- `P33` **anyio-equivalent** — task groups, cancellation scopes, timeouts, sync primitives
  (Lock/Event/Semaphore already partly in `threading`), memory object streams,
  `run_in_threadpool`. *Verify:* structured-concurrency cancellation tests.

### Phase 4 — L4 protocol servers (uvicorn-equivalent)
- `P41` **ASGI server core** — connection lifecycle, lifespan protocol, the `scope/receive/send`
  contract, graceful shutdown, signals/config/logging.
- `P42` **HTTP transport** — wire `P23` parser to `P32` streams: keep-alive, request/response
  streaming, expect-100, timeouts. *Verify:* serve raw ASGI apps; HTTP/1.1 conformance.
  *(Done as a buffered v1: full request in, one `Response` out. The streaming part is `P42b`.)*
- `P42b` **Streaming `receive`/`send`** — enrich the v1 server so request bodies stream in (chunked
  without full buffering) and responses stream out (`StreamingResponse`/`FileResponse`), via
  continuation-driven body chunks over `P32`. *Verify:* stream a large body both directions without
  buffering it whole.
- `P43` **WebSocket transport** — upgrade handshake + `P24` codec over `P32`. *Verify:* echo WS app.
- `P44` *(later)* **HTTP/2** — optional parity milestone.

### Phase 5 — L5 validation/serialization (Pydantic-equivalent)  ⟵ *compile-time core*
- `P51` **Schema/model layer** — model declaration + compile-time field metadata via Codon
  static introspection (`__fields__`-equivalent, defaults, aliases, constraints).
- `P52` **Validation engine** — compile-time-generated coercion + constraints (gt/lt/len/regex),
  optionals, unions, nested models, sequences; structured validation errors.
- `P53` **Serializers** — model → dict/JSON (via `P21`), include/exclude, by-alias, nested.
- `P54` **JSON-Schema generation** — model → JSON Schema (feeds OpenAPI). *Verify:* schema matches
  Pydantic output for a representative model set.

### Phase 6 — L6 ASGI toolkit (Starlette-equivalent)
- `P61` **Datastructures** — `Headers`/`MutableHeaders`, `URL`, `QueryParams`, `FormData`,
  `UploadFile`, `State`.
- `P62` **Requests / Responses** — `Request` (streamed body, json, form via `P25`), `Response`,
  `JSONResponse`, `PlainText`/`HTML`, `StreamingResponse`, `FileResponse`, `RedirectResponse`.
- `P63` **Routing** — path compilation (`P22`+`re`), converters (`int`/`str`/`path`/`uuid`),
  mounts, route matching, `url_for`.
- `P64` **Middleware** — pure-ASGI middleware stack: errors, CORS, GZip, TrustedHost, sessions.
- `P65` **WebSocket endpoint API**, **Background tasks**, **StaticFiles**, exception handlers.
  *(Templating/Jinja2 is an optional late add — likely a minimal template engine or skip.)*

### Phase 7 — L7 FastAPI layer (full parity)
- `P71` **App + APIRouter + decorators** (`@app.get/post/...`), route registration.
- `P72` **Parameter declaration** — `Path`/`Query`/`Header`/`Cookie`/`Body`/`Form`/`File`,
  bound to `P52` validation; request-body→model; `response_model` filtering via `P53`.
- `P73` **Dependency Injection** — `Depends`, sub-dependencies, `yield` deps (setup/teardown),
  per-request caching, security as dependencies. Resolve the DI graph at compile time where possible.
- `P74` **OpenAPI generation** — routes + `P54` schemas → OpenAPI 3.1 document; **Swagger UI**
  + **ReDoc** routes (serve static assets via `P65` StaticFiles, inject the spec).
- `P75` **Security utilities** — OAuth2 (password/bearer), API keys, HTTP Basic/Bearer, JWT
  encode/verify via `P13` crypto.
- `P76` **Error model** — `HTTPException`, `RequestValidationError` → 422 with Pydantic-style detail.
- `P77` **Test client** — in-process ASGI test client (httpx-equivalent surface) for the suite.

### Phase 8 — Parity hardening
- `P81` Port FastAPI's own tutorial/test apps; diff behavior against CPython FastAPI.
- `P82` Benchmark vs CPython `uvicorn`+FastAPI (plaintext/JSON/validation) — quantify the native win.
- `P83` Docs + examples + the public API surface freeze.

---

## 5. Critical-path & parallelism notes

- **Critical path to "hello world over HTTP":**
  `P11 → P12 → P31 → P32 → P41 → P42 → P62 → P63 → P71`. Everything else hangs off this spine.
  Aim to reach a raw "serve `{"hello":"world"}`" milestone as early as **end of Phase 4**
  (ASGI app, before Pydantic/FastAPI sugar exists).
- **Parallelizable once Phase 1 is green:** the L2 codecs (`P21`–`P25`) are sans-I/O and
  independent — they can be built/tested concurrently. **L5 validation (`P51`–`P54`)** only needs
  `P21` (JSON) + the compiler's introspection, so it can proceed in parallel with the whole
  L3/L4 server track.
- **TLS (`P14`) and HTTP/2 (`P44`) are deferrable** without blocking parity of the core path;
  schedule them as 1.x milestones if they threaten the critical path.

---

## 6. Risks (honest)

1. **The I/O reactor (`P31`).** Marrying a selector to Codon's existing coroutine scheduler is the
   highest-uncertainty node — especially Windows: `epoll`/`kqueue` are readiness models, IOCP is a
   *completion* model. May need a proactor abstraction or a `WSAPoll` readiness fallback on Windows.
2. **Codon async semantics.** Need to confirm how far `asyncio.codon`'s coroutines compose with
   FFI blocking calls and threads, and whether cancellation/await points behave as ASGI expects.
3. **Compile-time validation (`P52`).** The big payoff *and* the biggest design unknown — how much
   of Pydantic's dynamic behavior (unions, discriminated unions, arbitrary nesting) maps to Codon
   static metaprogramming vs. needs a runtime fallback.
4. **TLS cross-platform** (OpenSSL vs SChannel) is a notorious time sink; keep it off the critical path.
5. **Full-parity surface is large.** OpenAPI 3.1 + Swagger/ReDoc + the security utilities are
   broad; scope each as its own milestone and don't let them block the runnable core.
6. **C-FFI portability.** Winsock vs BSD socket struct/const differences must be centralized in the
   `P11` shim so nothing above L1 sees a platform `#ifdef`.

---

## 7. Definition of success

A pure-Codon library where an app written with FastAPI-style decorators —
path/query/body params, Pydantic-style models with validation, dependency injection, WebSockets,
and auto-generated OpenAPI docs at `/docs` — **compiles to a single native binary**, serves real
HTTP/WS traffic cross-platform on its own async event loop, and is **measurably faster** than the
same app on CPython + uvicorn + FastAPI.

---

## 8. Status & immediate next step

- **Now:** graph defined; build order fixed; Codon stdlib surveyed (async scheduler reusable,
  sockets/JSON/HTTP/TLS are net-new). Decisions locked (§intro table).
- **Next action:** **`P00` scaffolding**, then **`P11` (sockets FFI)** — the deepest leaf — with a
  cross-platform echo round-trip as the first green test. Build strictly upward from there.

> Maintenance: keep this graph the source of truth. When a node is built+verified, mark its phase
> green; never start a node before all of its children (lower phases) are green.
