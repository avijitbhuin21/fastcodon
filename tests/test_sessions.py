# L6.1 — signed-cookie sessions: encode/decode round-trip, tamper rejection, persistence across
# two requests through a WebApp.
from fastcodon.asgi import Scope, Response
from fastcodon.web import (Request, Endpoint, Router, WebApp, Middleware,
                           SessionMiddleware, encode_session, decode_session, plain_text)

SECRET = "s3cr3t-key"

def eq(name: str, got: str, want: str):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name + ": got " + repr(got) + " want " + repr(want)

def eqi(name: str, got: int, want: int):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name

def eqb(name: str, got: bool, want: bool):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name

class CounterEP(Endpoint):
    def handle(self, request: Request) -> Response:
        n = 0
        if "count" in request.session:
            n = int(request.session["count"])
        n += 1
        request.session["count"] = str(n)
        request.session["who"] = "alice"
        return plain_text("count=" + str(n))

def set_cookie_value(resp: Response, name: str) -> str:
    pre = name + "="
    for (k, v) in resp.headers:
        if k.lower() == "set-cookie" and v.startswith(pre):
            rest = v[len(pre):]
            semi = rest.find(";")
            return rest[:semi] if semi >= 0 else rest
    return ""

def mkscope(cookie: str) -> Scope:
    h = List[Tuple[str, str]]()
    if cookie != "":
        h.append(("Cookie", "session=" + cookie))
    return Scope("http", "GET", "/", "", "1.1", h)

def main():
    # --- raw encode/decode round-trip ---
    d = Dict[str, str]()
    d["user"] = "bob"
    d["role"] = "admin x"        # space exercises url-encoding
    tok = encode_session(SECRET, d)
    back = decode_session(SECRET, tok)
    eq("session roundtrip user", back["user"], "bob")
    eq("session roundtrip role", back["role"], "admin x")

    # --- tamper: flip a payload char -> empty dict, no crash ---
    tampered = ("A" + tok[1:]) if tok[0] != "A" else ("B" + tok[1:])
    eqi("tampered -> empty", len(decode_session(SECRET, tampered)), 0)
    # wrong secret -> empty
    eqi("wrong secret -> empty", len(decode_session("other", tok)), 0)
    # garbage -> empty
    eqi("garbage -> empty", len(decode_session(SECRET, "not-a-token")), 0)

    # --- e2e persistence through a WebApp ---
    router = Router()
    router.get("/", CounterEP())
    mids = List[Middleware]()
    mids.append(SessionMiddleware(SECRET))
    app = WebApp(router, mids)

    r1 = app.handle(mkscope(""), "")
    eq("first visit body", r1.body, "count=1")
    cookie1 = set_cookie_value(r1, "session")
    eqb("first visit sets cookie", cookie1 != "", True)

    r2 = app.handle(mkscope(cookie1), "")
    eq("second visit body", r2.body, "count=2")

    r3 = app.handle(mkscope(set_cookie_value(r2, "session")), "")
    eq("third visit body", r3.body, "count=3")

    # tampered cookie -> session resets (count starts over)
    bad = ("Z" + cookie1[1:]) if cookie1[0] != "Z" else ("Y" + cookie1[1:])
    r4 = app.handle(mkscope(bad), "")
    eq("tampered cookie resets", r4.body, "count=1")

    print("PASS: signed-cookie sessions (L6.1)")

main()
