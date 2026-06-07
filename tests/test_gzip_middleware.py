# L6.1 — GZipMiddleware: compresses large bodies when the client accepts gzip; passes through
# otherwise. The compressed body is also written out for an external decompress round-trip check.
from fastcodon.asgi import Scope, Response
from fastcodon.web import Request, Endpoint, Router, WebApp, Middleware, GZipMiddleware, plain_text

BIG = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 50

def eq(name: str, got: str, want: str):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name

def eqb(name: str, got: bool, want: bool):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name

def hget(resp: Response, name: str) -> str:
    key = name.lower()
    for (k, v) in resp.headers:
        if k.lower() == key:
            return v
    return ""

def write_bin(path: str, content: str):
    f = open(path, "wb")
    f.write(content)
    f.close()

class BigEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text(BIG)

class TinyEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("tiny")

def scope(ae: str) -> Scope:
    h = List[Tuple[str, str]]()
    if ae != "":
        h.append(("Accept-Encoding", ae))
    return Scope("http", "GET", "/big", "", "1.1", h)

def main():
    router = Router()
    router.get("/big", BigEP())
    router.get("/tiny", TinyEP())
    mids = List[Middleware]()
    mids.append(GZipMiddleware(minimum_size=100))
    app = WebApp(router, mids)

    # client accepts gzip + body large -> compressed
    r = app.handle(scope("gzip, deflate"), "")
    eq("content-encoding", hget(r, "content-encoding"), "gzip")
    eq("vary", hget(r, "vary"), "Accept-Encoding")
    eqb("gzip magic 1f", ord(r.body[0]) == 0x1F, True)
    eqb("gzip magic 8b", ord(r.body[1]) == 0x8B, True)
    eqb("compressed smaller", len(r.body) < len(BIG), True)
    write_bin("gzmw_out.gz", r.body)
    write_bin("gzmw_in.txt", BIG)
    print("gz body len", len(r.body), "of", len(BIG))

    # no Accept-Encoding -> untouched
    r2 = app.handle(scope(""), "")
    eq("no-ae passthrough body", r2.body, BIG)
    eq("no-ae no content-encoding", hget(r2, "content-encoding"), "")

    # accepts gzip but body below minimum -> untouched
    h = List[Tuple[str, str]]()
    h.append(("Accept-Encoding", "gzip"))
    r3 = app.handle(Scope("http", "GET", "/tiny", "", "1.1", h), "")
    eq("tiny not compressed", r3.body, "tiny")
    eq("tiny no content-encoding", hget(r3, "content-encoding"), "")

    print("PASS: gzip middleware (L6.1)")

main()
