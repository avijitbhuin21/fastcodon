# L6 integration — a routed WebApp (router + middleware) served over the REAL L4 HTTP server.
# One process, one Reactor: a Server runs the WebApp; a client Stream on the same reactor sends a
# GET and reads the full response. Proves the Starlette-equivalent toolkit plugs into the uvicorn-
# equivalent transport end to end.

from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import Server, Scope, Response
from fastcodon.web import (Request, Endpoint, Router, Middleware,
                           CORSMiddleware, plain_text, json_str, WebApp)

PORT = 54371
REQUEST = "GET /hello/world?x=1 HTTP/1.1\r\nHost: x\r\nOrigin: https://app.com\r\nConnection: close\r\n\r\n"


class HelloEP(Endpoint):
    def handle(self, request: Request) -> Response:
        who = request.path_param("name")
        x = request.query_params().get("x")
        return json_str("{\"hello\":\"" + who + "\",\"x\":\"" + x + "\"}")


def build_app() -> WebApp:
    router = Router()
    router.get("/hello/{name}", HelloEP())
    mids = List[Middleware]()
    mids.append(CORSMiddleware(["https://app.com"]))
    return WebApp(router, mids)


class St:
    raw: str
    body: str
    def __init__(self):
        self.raw = ""
        self.body = ""


class GotBody(Continuation):
    r: Reactor
    st: Stream
    state: St
    head: str
    def __init__(self, r: Reactor, st: Stream, state: St, head: str):
        super().__init__()
        self.r = r
        self.st = st
        self.state = state
        self.head = head
    def run(self):
        self.state.body = self.data
        self.state.raw = self.head + self.data
        self.st.close()
        self.r.stop()


class GotHeaders(Continuation):
    r: Reactor
    st: Stream
    state: St
    def __init__(self, r: Reactor, st: Stream, state: St):
        super().__init__()
        self.r = r
        self.st = st
        self.state = state
    def run(self):
        if self.errored:
            self.r.stop()
            return
        head = self.data
        clen = 0
        low = head.lower()
        idx = low.find("content-length:")
        if idx >= 0:
            after = head[idx + len("content-length:"):]
            le = after.find("\r\n")
            clen = int((after[:le] if le >= 0 else after).strip())
        if clen <= 0:
            self.state.raw = head
            self.st.close()
            self.r.stop()
            return
        self.st.read(clen).then(GotBody(self.r, self.st, self.state, head))


class Written(Continuation):
    r: Reactor
    st: Stream
    state: St
    def __init__(self, r: Reactor, st: Stream, state: St):
        super().__init__()
        self.r = r
        self.st = st
        self.state = state
    def run(self):
        if self.errored:
            self.r.stop()
            return
        self.st.read_until("\r\n\r\n").then(GotHeaders(self.r, self.st, self.state))


class Watchdog(TimerCallback):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired — stopping reactor")
        self.r.stop()


def main():
    r = Reactor()
    srv = Server(r, build_app(), "127.0.0.1", PORT)
    srv.serve()

    state = St()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(REQUEST).then(Written(r, client, state))

    r.call_later(5.0, Watchdog(r))
    r.run_forever()

    print("raw response:", repr(state.raw))
    assert state.raw.startswith("HTTP/1.1 200"), "bad status: " + repr(state.raw[:32])
    assert state.raw.lower().find("content-type: application/json") >= 0, "missing JSON content-type"
    # CORS header injected by the middleware
    assert state.raw.lower().find("access-control-allow-origin: https://app.com") >= 0, "missing CORS header"
    # routed path param + query param flowed through
    assert state.body == "{\"hello\":\"world\",\"x\":\"1\"}", "bad body: " + repr(state.body)

    print("PASS: routed WebApp served over real HTTP (L6 e2e)")
    srv.stop()
    r.close()


main()
