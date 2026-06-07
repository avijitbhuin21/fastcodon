# P63 — routing: path compile + converters, dispatch (404/405), mounts, url_for.
from fastcodon.asgi import Scope, Response
from fastcodon.web import Request, Endpoint, Router, compile_path, plain_text

def eq(name: str, got: str, want: str):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name + ": got " + repr(got) + " want " + repr(want)

def eqi(name: str, got: int, want: int):
    print(name, "->", "ok" if got == want else "FAIL")
    assert got == want, name + ": got " + str(got) + " want " + str(want)

def mkreq(method: str, path: str) -> Request:
    return Request(Scope("http", method, path, "", "1.1", List[Tuple[str, str]]()), "")

def body_of(resp: Response) -> str:
    return resp.body

# --- endpoints ---
class HomeEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("home")

class UserEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("user:" + request.path_param("id"))

class PostEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("post:" + request.path_param("pid") + ":" + request.path_param("slug"))

class FileEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("file:" + request.path_param("rest"))

class CreateEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("created", 201)

class SubEP(Endpoint):
    def handle(self, request: Request) -> Response:
        return plain_text("sub:" + request.path_param("x"))

def main():
    # --- compile_path sanity ---
    (pat, names) = compile_path("/users/{id}/posts/{pid:int}")
    eqi("compile param count", len(names), 2)
    eq("compile names", names[0] + "," + names[1], "id,pid")

    # --- router ---
    r = Router()
    r.get("/", HomeEP())
    r.get("/users/{id}", UserEP(), name="user")
    r.get("/posts/{pid:int}/{slug}", PostEP())
    r.get("/files/{rest:path}", FileEP())
    r.post("/items", CreateEP())

    # static
    eq("GET /", body_of(r.dispatch(mkreq("GET", "/"))), "home")
    # str converter
    eq("GET /users/alice", body_of(r.dispatch(mkreq("GET", "/users/alice"))), "user:alice")
    # int converter + multi param
    eq("GET /posts/42/hello", body_of(r.dispatch(mkreq("GET", "/posts/42/hello"))), "post:42:hello")
    # int converter rejects non-digits -> 404
    eqi("GET /posts/abc/x -> 404", r.dispatch(mkreq("GET", "/posts/abc/x")).status, 404)
    # path converter captures slashes
    eq("GET /files/a/b/c.txt", body_of(r.dispatch(mkreq("GET", "/files/a/b/c.txt"))), "file:a/b/c.txt")
    # POST create
    eqi("POST /items -> 201", r.dispatch(mkreq("POST", "/items")).status, 201)

    # 404 unknown path
    eqi("GET /nope -> 404", r.dispatch(mkreq("GET", "/nope")).status, 404)
    # 405 wrong method (path matches, method doesn't)
    resp405 = r.dispatch(mkreq("DELETE", "/items"))
    eqi("DELETE /items -> 405", resp405.status, 405)
    allow = ""
    for (k, v) in resp405.headers:
        if k.lower() == "allow":
            allow = v
    eq("405 Allow header", allow, "POST")

    # HEAD falls back to GET route
    eqi("HEAD / -> 200", r.dispatch(mkreq("HEAD", "/")).status, 200)

    # --- url_for ---
    p = Dict[str, str]()
    p["id"] = "bob"
    u = r.url_for("user", p)
    assert u != "", "url_for user"
    eq("url_for user", u, "/users/bob")

    # --- mounts ---
    sub = Router()
    sub.get("/widget/{x}", SubEP(), name="widget")
    top = Router()
    top.get("/", HomeEP())
    top.mount("/admin", sub)
    eq("mounted GET /admin/widget/7",
       body_of(top.dispatch(mkreq("GET", "/admin/widget/7"))), "sub:7")
    eqi("mounted miss -> 404", top.dispatch(mkreq("GET", "/admin/nope")).status, 404)
    # url_for through the mount prepends the prefix
    pw = Dict[str, str]()
    pw["x"] = "9"
    uw = top.url_for("widget", pw)
    assert uw != "", "url_for widget"
    eq("url_for mounted", uw, "/admin/widget/9")

    print("PASS: routing (P63)")

main()
