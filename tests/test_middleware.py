# P64 — middleware stack: CORS, TrustedHost, ExceptionMiddleware, wired via WebApp.
from fastcodon.asgi import Scope, Response
from fastcodon.web import (Request, Endpoint, Router, plain_text,
                           Middleware, CORSMiddleware, TrustedHostMiddleware,
                           ErrorHandler, ExceptionMiddleware, WebApp)

def eq(name: str, got: str, want: str):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name + ": got " + repr(got) + " want " + repr(want)

def eqi(name: str, got: int, want: int):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name + ": got " + str(got) + " want " + str(want)

def hget(resp: Response, name: str) -> str:
    key = name.lower()
    for (k, v) in resp.headers:
        if k.lower() == key:
            return v
    return ""

# --- endpoints ---
class HomeEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("home")

class BoomEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("raw error body", 500)

# --- custom error pages ---
class NotFoundPage(ErrorHandler):
    def handle(self, request: Request, status: int) -> Response:
        return plain_text("custom 404 for " + request.path(), 404)

class ServerErrPage(ErrorHandler):
    def handle(self, request: Request, status: int) -> Response:
        return plain_text("custom 500", 500)

def mkscope(method: str, path: str, headers: List[Tuple[str, str]]) -> Scope:
    return Scope("http", method, path, "", "1.1", headers)

def main():
    router = Router()
    router.get("/", HomeEP())
    router.get("/boom", BoomEP())

    exc = ExceptionMiddleware()
    exc.add(404, NotFoundPage())
    exc.add(500, ServerErrPage())

    mids = List[Middleware]()
    mids.append(TrustedHostMiddleware(["example.com", "*.test.com"]))
    mids.append(CORSMiddleware(["https://app.com"]))
    mids.append(exc)
    app = WebApp(router, mids)

    # 1) normal request: 200, CORS header for an allowed origin
    r1 = app.handle(mkscope("GET", "/",
                            [("Host", "example.com"), ("Origin", "https://app.com")]), "")
    eqi("GET / status", r1.status, 200)
    eq("GET / body", r1.body, "home")
    eq("CORS allow-origin", hget(r1, "access-control-allow-origin"), "https://app.com")

    # 2) CORS preflight -> 204 with methods/headers
    r2 = app.handle(mkscope("OPTIONS", "/",
                            [("Host", "example.com"), ("Origin", "https://app.com"),
                             ("Access-Control-Request-Method", "GET")]), "")
    eqi("preflight status", r2.status, 204)
    assert hget(r2, "access-control-allow-methods") != "", "preflight methods header"
    eq("preflight allow-origin", hget(r2, "access-control-allow-origin"), "https://app.com")
    print("preflight headers -> ok")

    # 3) disallowed origin -> no CORS header, still 200
    r3 = app.handle(mkscope("GET", "/",
                            [("Host", "example.com"), ("Origin", "https://evil.com")]), "")
    eqi("bad-origin status", r3.status, 200)
    eq("bad-origin no CORS header", hget(r3, "access-control-allow-origin"), "")

    # 4) TrustedHost rejects an unknown Host (outermost middleware short-circuits) -> 400
    r4 = app.handle(mkscope("GET", "/", [("Host", "evil.com")]), "")
    eqi("bad host -> 400", r4.status, 400)

    # 5) TrustedHost wildcard subdomain passes
    r5 = app.handle(mkscope("GET", "/", [("Host", "api.test.com")]), "")
    eqi("subdomain host -> 200", r5.status, 200)

    # 6) ExceptionMiddleware maps a 404 to the custom page
    r6 = app.handle(mkscope("GET", "/missing", [("Host", "example.com")]), "")
    eqi("404 status", r6.status, 404)
    eq("custom 404 body", r6.body, "custom 404 for /missing")

    # 7) ExceptionMiddleware maps a handler-returned 500 to the custom page
    r7 = app.handle(mkscope("GET", "/boom", [("Host", "example.com")]), "")
    eqi("500 status", r7.status, 500)
    eq("custom 500 body", r7.body, "custom 500")

    print("PASS: middleware stack (P64)")

main()
