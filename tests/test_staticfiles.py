# P65 — StaticFiles: serve real files via a {path:path} route; reject traversal; guess content-type.
from fastcodon.asgi import Scope, Response
from fastcodon.web import Request, Router, WebApp, Middleware, StaticFiles

from C import remove(cobj) -> i32

DATA = "__sf_data.txt"
PAGE = "__sf_page.html"

def write_file(path: str, content: str):
    f = open(path, "w")
    f.write(content)
    f.close()

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

def mkscope(path: str) -> Scope:
    return Scope("http", "GET", path, "", "1.1", List[Tuple[str, str]]())

def main():
    write_file(DATA, "STATIC-OK")
    write_file(PAGE, "<h1>hi</h1>")

    router = Router()
    router.get("/static/{path:path}", StaticFiles(".", index=DATA))
    app = WebApp(router, List[Middleware]())

    # existing file -> 200 + content + text/plain content-type (.txt)
    r1 = app.handle(mkscope("/static/" + DATA), "")
    eqi("static hit status", r1.status, 200)
    eq("static hit body", r1.body, "STATIC-OK")
    eq("static .txt content-type", hget(r1, "content-type"), "text/plain; charset=utf-8")

    # html content-type guess
    r2 = app.handle(mkscope("/static/" + PAGE), "")
    eqi("static html status", r2.status, 200)
    eq("static html content-type", hget(r2, "content-type"), "text/html; charset=utf-8")
    eq("static html body", r2.body, "<h1>hi</h1>")

    # missing file -> 404 (no crash even though the file does not exist)
    r3 = app.handle(mkscope("/static/does_not_exist.txt"), "")
    eqi("static missing -> 404", r3.status, 404)

    # path traversal -> 404 (rejected before disk)
    r4 = app.handle(mkscope("/static/../" + DATA), "")
    eqi("static traversal -> 404", r4.status, 404)

    # index: a request whose path param is "" serves the configured index file
    sf = StaticFiles(".", index=DATA)
    req = Request(mkscope("/static/"), "")
    req.path_params["path"] = ""
    r5 = sf.handle(req)
    eqi("static index status", r5.status, 200)
    eq("static index body", r5.body, "STATIC-OK")

    remove(DATA.c_str())
    remove(PAGE.c_str())
    print("PASS: staticfiles (P65)")

main()
