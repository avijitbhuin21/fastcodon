# P65 — HTTP error helpers (HTTPException-equivalent) + composition with ExceptionMiddleware.
from fastcodon.asgi import Scope, Response
from fastcodon.web import (Request, Endpoint, Router, WebApp, Middleware,
                           ExceptionMiddleware, ErrorHandler,
                           http_error, http_error_text, status_reason, plain_text)

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

class UserEP(Endpoint):
    def handle(self, request: Request) -> Response:
        uid = request.path_param("id")
        if uid != "1":
            return http_error(404, "user " + uid + " not found")
        return plain_text("user 1")

class Custom404(ErrorHandler):
    def handle(self, request: Request, status: int) -> Response:
        return plain_text("nice 404", 404)

def mkscope(path: str) -> Scope:
    return Scope("http", "GET", path, "", "1.1", List[Tuple[str, str]]())

def main():
    # bare helpers
    e = http_error(403)
    eqi("http_error status", e.status, 403)
    eq("http_error body (reason)", e.body, "{\"detail\":\"Forbidden\"}")
    eq("http_error ct", hget(e, "content-type"), "application/json")
    eq("http_error detail", http_error(422, "bad \"x\"").body, "{\"detail\":\"bad \\\"x\\\"\"}")
    eq("http_error_text", http_error_text(404).body, "Not Found")
    eq("status_reason", status_reason(418), "I'm a Teapot")

    # endpoint returns http_error -> flows through unmapped
    router = Router()
    router.get("/users/{id}", UserEP())
    app_plain = WebApp(router, List[Middleware]())
    r1 = app_plain.handle(mkscope("/users/9"), "")
    eqi("missing user status", r1.status, 404)
    eq("missing user json", r1.body, "{\"detail\":\"user 9 not found\"}")

    # with ExceptionMiddleware, a returned 404 is re-rendered by the custom handler
    exc = ExceptionMiddleware()
    exc.add(404, Custom404())
    mids = List[Middleware]()
    mids.append(exc)
    app_mapped = WebApp(router, mids)
    r2 = app_mapped.handle(mkscope("/users/9"), "")
    eqi("mapped 404 status", r2.status, 404)
    eq("mapped 404 body", r2.body, "nice 404")

    # the happy path is untouched
    r3 = app_mapped.handle(mkscope("/users/1"), "")
    eq("ok user", r3.body, "user 1")

    print("PASS: http error helpers + exception middleware (P65)")

main()
