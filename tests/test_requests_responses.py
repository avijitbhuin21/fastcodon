# P62 — Request (over Scope+body) and response constructors.
from fastcodon.asgi import Scope, Response
from fastcodon.web import (Request, plain_text, html, json_str, json_response, redirect,
                           with_header, set_cookie)
from fastcodon.json.value import JsonValue

def eq(name: str, got: str, want: str):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + repr(got) + " want " + repr(want)

def eqi(name: str, got: int, want: int):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + str(got) + " want " + str(want)

def eqb(name: str, got: bool, want: bool):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name

def mkscope(method: str, path: str, qs: str, headers: List[Tuple[str, str]]) -> Scope:
    return Scope("http", method, path, qs, "1.1", headers)

def header_get(resp: Response, name: str) -> str:
    key = name.lower()
    for (k, v) in resp.headers:
        if k.lower() == key:
            return v
    return ""

def main():
    # --- Request basics ---
    hdrs = [("Host", "example.com:8080"), ("Cookie", "a=1; b=2"),
            ("Content-Type", "application/json")]
    sc = mkscope("POST", "/items", "page=2&q=hi", hdrs)
    req = Request(sc, "{\"name\":\"box\",\"qty\":3}")
    eq("Request.method", req.method(), "POST")
    eq("Request.path", req.path(), "/items")
    eq("Request.query_params q", req.query_params().get("q"), "hi")
    eq("Request.header host", req.header("host"), "example.com:8080")
    eq("Request.url host", req.url().host, "example.com")
    eqi("Request.url port", req.url().port, 8080)
    eq("Request.url path", req.url().path, "/items")

    ck = req.cookies()
    eq("Request.cookies a", ck["a"], "1")
    eq("Request.cookies b", ck["b"], "2")

    jv = req.json()
    eq("Request.json name", jv["name"].as_str(), "box")
    eqi("Request.json qty", jv["qty"].as_int(), 3)

    # --- form: urlencoded ---
    sc2 = mkscope("POST", "/f", "", [("Content-Type", "application/x-www-form-urlencoded")])
    req2 = Request(sc2, "name=alice&tag=x&tag=y")
    fd = req2.form()
    eq("form urlencoded field", fd.get("name"), "alice")
    eqi("form urlencoded get_list", len(fd.get_list("tag")), 2)

    # --- form: multipart with a file ---
    boundary = "----b"
    mbody = ("--" + boundary + "\r\n"
             "Content-Disposition: form-data; name=\"title\"\r\n\r\n"
             "Hello\r\n"
             "--" + boundary + "\r\n"
             "Content-Disposition: form-data; name=\"doc\"; filename=\"a.txt\"\r\n"
             "Content-Type: text/plain\r\n\r\n"
             "FILEDATA\r\n"
             "--" + boundary + "--\r\n")
    sc3 = mkscope("POST", "/u", "",
                  [("Content-Type", "multipart/form-data; boundary=" + boundary)])
    req3 = Request(sc3, mbody)
    fd3 = req3.form()
    eq("form multipart field", fd3.get("title"), "Hello")
    f = fd3.get_file("doc")
    assert f is not None, "multipart file present"
    eq("form multipart filename", f.filename, "a.txt")
    eq("form multipart filedata", f.read(), "FILEDATA")
    eq("form multipart file ct", f.content_type, "text/plain")

    # --- responses ---
    r1 = plain_text("hi")
    eqi("plain_text status", r1.status, 200)
    eq("plain_text body", r1.body, "hi")
    eq("plain_text ct", header_get(r1, "content-type"), "text/plain; charset=utf-8")

    r2 = html("<h1>x</h1>", status=201)
    eqi("html status", r2.status, 201)
    eq("html ct", header_get(r2, "content-type"), "text/html; charset=utf-8")

    obj = JsonValue.object({"ok": JsonValue.from_bool(True)})
    r3 = json_response(obj)
    eq("json_response body", r3.body, "{\"ok\":true}")
    eq("json_response ct", header_get(r3, "content-type"), "application/json")

    r4 = redirect("/login")
    eqi("redirect status", r4.status, 307)
    eq("redirect location", header_get(r4, "location"), "/login")

    r5 = json_str("{\"a\":1}")
    eq("json_str body", r5.body, "{\"a\":1}")

    # header + cookie mutators
    r6 = with_header(plain_text("x"), "X-Custom", "yes")
    eq("with_header", header_get(r6, "x-custom"), "yes")
    r7 = set_cookie(plain_text("x"), "sid", "abc", http_only=True)
    sc_hdr = header_get(r7, "set-cookie")
    assert "sid=abc" in sc_hdr and "HttpOnly" in sc_hdr, "set_cookie: " + sc_hdr
    print("set_cookie -> ok")

    print("PASS: requests/responses (P62)")

main()
