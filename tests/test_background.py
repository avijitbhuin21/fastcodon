# P65 — background tasks: a handler queues a task that runs AFTER the response is written.
# A routed WebApp is served over the real L4 server; the task mutates a shared Box, asserted after.
from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import Server, Scope, Response, BackgroundTask
from fastcodon.web import Request, Endpoint, Router, WebApp, Middleware, plain_text

PORT = 54379
REQUEST = "GET /go HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"


class Box:
    n: int
    log: str
    def __init__(self):
        self.n = 0
        self.log = ""


class IncTask(BackgroundTask):
    box: Box
    amount: int
    def __init__(self, box: Box, amount: int):
        self.box = box
        self.amount = amount
    def run(self) -> None:
        self.box.n += self.amount
        self.box.log += "task;"


class GoEP(Endpoint):
    box: Box
    def __init__(self, box: Box):
        self.box = box
    def handle(self, request: Request) -> Response:
        resp = plain_text("queued")
        resp.add_task(IncTask(self.box, 5))
        resp.add_task(IncTask(self.box, 100))
        return resp


def build_app(box: Box) -> WebApp:
    router = Router()
    router.get("/go", GoEP(box))
    return WebApp(router, List[Middleware]())


class St:
    body: str
    def __init__(self):
        self.body = ""


class GotBody(Continuation):
    r: Reactor
    st: Stream
    s: St
    def __init__(self, r: Reactor, st: Stream, s: St):
        super().__init__()
        self.r = r
        self.st = st
        self.s = s
    def run(self):
        self.s.body = self.data
        self.st.close()
        self.r.stop()


class GotHeaders(Continuation):
    r: Reactor
    st: Stream
    s: St
    def __init__(self, r: Reactor, st: Stream, s: St):
        super().__init__()
        self.r = r
        self.st = st
        self.s = s
    def run(self):
        if self.errored:
            self.r.stop(); return
        head = self.data
        clen = 0
        idx = head.lower().find("content-length:")
        if idx >= 0:
            after = head[idx + len("content-length:"):]
            le = after.find("\r\n")
            clen = int((after[:le] if le >= 0 else after).strip())
        if clen <= 0:
            self.st.close(); self.r.stop(); return
        self.st.read(clen).then(GotBody(self.r, self.st, self.s))


class Written(Continuation):
    r: Reactor
    st: Stream
    s: St
    def __init__(self, r: Reactor, st: Stream, s: St):
        super().__init__()
        self.r = r
        self.st = st
        self.s = s
    def run(self):
        if self.errored:
            self.r.stop(); return
        self.st.read_until("\r\n\r\n").then(GotHeaders(self.r, self.st, self.s))


class Watchdog(TimerCallback):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired — stopping reactor")
        self.r.stop()


def main():
    box = Box()
    r = Reactor()
    srv = Server(r, build_app(box), "127.0.0.1", PORT)
    srv.serve()

    s = St()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(REQUEST).then(Written(r, client, s))

    r.call_later(5.0, Watchdog(r))
    r.run_forever()

    assert s.body == "queued", "bad body: " + repr(s.body)
    # both queued tasks ran exactly once, in order, after the response
    assert box.n == 105, "background tasks did not run as expected: n=" + str(box.n)
    assert box.log == "task;task;", "task log: " + box.log

    print("PASS: background tasks ran post-response (n=105)")
    srv.stop()
    r.close()


main()
