# P61 — Starlette-equivalent datastructures (sans-I/O, exception-free).
from fastcodon.web import Headers, MutableHeaders, QueryParams, UploadFile, FormData, URL, State

def eq(name: str, got: str, want: str):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + repr(got) + " want " + repr(want)

def eqi(name: str, got: int, want: int):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + str(got) + " want " + str(want)

def eqb(name: str, got: bool, want: bool):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name

def main():
    # --- Headers: case-insensitive multidict ---
    hl = [("Content-Type", "text/html"), ("X-Tag", "a"), ("x-tag", "b")]
    h = Headers(hl)
    eq("Headers.get ci", h.get("content-type"), "text/html")
    eq("Headers.get default", h.get("missing", "def"), "def")
    eqi("Headers.get_all", len(h.get_all("X-Tag")), 2)
    eq("Headers.get_all order", h.get_all("x-tag")[0] + h.get_all("x-tag")[1], "ab")
    eqb("Headers contains", h.contains("X-TAG"), True)
    eqb("Headers not contains", h.contains("nope"), False)
    eqi("Headers len", len(h), 3)

    # --- MutableHeaders ---
    m = MutableHeaders.new()
    m.append("A", "1")
    m.append("A", "2")
    eqi("MutableHeaders append", len(m.get_all("A")), 2)
    m.set("A", "9")
    eqi("MutableHeaders set replaces", len(m.get_all("A")), 1)
    eq("MutableHeaders set value", m.get("a"), "9")
    eq("MutableHeaders setdefault keeps", m.setdefault("A", "x"), "9")
    eq("MutableHeaders setdefault adds", m.setdefault("B", "7"), "7")
    m.delete("A")
    eqb("MutableHeaders delete", m.contains("A"), False)

    # --- QueryParams ---
    q = QueryParams("a=1&b=2&a=3&flag")
    eq("QueryParams get first", q.get("a"), "1")
    eqi("QueryParams get_list", len(q.get_list("a")), 2)
    eq("QueryParams empty flag", q.get("flag"), "")
    eqb("QueryParams contains", q.contains("b"), True)
    eq("QueryParams decode", QueryParams("q=a%20b").get("q"), "a b")

    # --- URL parsing ---
    u = URL.parse("https://user:pw@example.com:8443/path/to?x=1&y=2#frag")
    eq("URL scheme", u.scheme, "https")
    eq("URL host", u.host, "example.com")
    eqi("URL port", u.port, 8443)
    eq("URL path", u.path, "/path/to")
    eq("URL query", u.query, "x=1&y=2")
    eq("URL fragment", u.fragment, "frag")
    u2 = URL.parse("/just/a/path?z=9")
    eq("URL relative path", u2.path, "/just/a/path")
    eq("URL relative query", u2.query, "z=9")
    eqi("URL relative no port", u2.port, -1)
    eq("URL str roundtrip", str(URL.parse("http://h:80/p?q=1")), "http://h:80/p?q=1")
    eq("URL replace path", URL.parse("http://h/a").replace(path="/b").path, "/b")

    # --- FormData + UploadFile ---
    fd = FormData()
    fd.add_field("name", "alice")
    fd.add_field("tag", "x")
    fd.add_field("tag", "y")
    uf = UploadFile("a.txt", "text/plain", [("Content-Type", "text/plain")], "filebytes")
    fd.add_file("upload", uf)
    eq("FormData field", fd.get("name"), "alice")
    eqi("FormData get_list", len(fd.get_list("tag")), 2)
    eqb("FormData contains file", fd.contains("upload"), True)
    f = fd.get_file("upload")
    assert f is not None, "get_file"
    eq("UploadFile filename", f.filename, "a.txt")
    eq("UploadFile read", f.read(), "filebytes")
    eqi("UploadFile size", f.size(), 9)

    # --- State ---
    st = State()
    st.set("request_id", "r-123")
    eq("State get", st.get("request_id"), "r-123")
    eq("State default", st.get("missing", "?"), "?")
    eqb("State contains", st.contains("request_id"), True)

    print("PASS: web datastructures (P61)")

main()
