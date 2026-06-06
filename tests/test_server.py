# P41/P42 milestone — a REAL HTTP/1.1 round-trip over loopback, driven by ONE Reactor.
#
# Topology (one process, one Reactor, no threads):
#   * a Server bound to 127.0.0.1:PORT runs a HelloApp whose handle() returns JSON {"hello":"world"};
#   * a client Stream connects on the SAME reactor, sends a GET, and reads the full response
#     (read the header block with read_until("\r\n\r\n"), parse Content-Length, then read the body);
#   * the client asserts the status line, the Content-Type, the Content-Length, and the exact body,
#     then stops the reactor;
#   * a watchdog call_later stops the reactor after a few seconds so a bug can't hang CI.

from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import Server, ASGIApp, Scope, Response

PORT = 54346
REQUEST = "GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"


class HelloApp(ASGIApp):
    def handle(self, scope: Scope, body: str) -> Response:
        return Response.json("{\"hello\":\"world\"}")


class State:
    raw: str          # full response bytes accumulated
    body: str
    ok: bool
    def __init__(self):
        self.raw = ""
        self.body = ""
        self.ok = False


# ---- client continuation chain: write -> read headers -> read body -> verify, stop ----------
class ClientGotBody(Continuation):
    r: Reactor
    st: Stream
    state: State
    head: str
    def __init__(self, r: Reactor, st: Stream, state: State, head: str):
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


class ClientGotHeaders(Continuation):
    r: Reactor
    st: Stream
    state: State
    def __init__(self, r: Reactor, st: Stream, state: State):
        super().__init__()
        self.r = r
        self.st = st
        self.state = state
    def run(self):
        if self.errored:
            self.r.stop()
            return
        head = self.data
        # parse Content-Length out of the header block (case-insensitive).
        clen = 0
        low = head.lower()
        idx = low.find("content-length:")
        if idx >= 0:
            after = head[idx + len("content-length:"):]
            line_end = after.find("\r\n")
            num = after[:line_end] if line_end >= 0 else after
            clen = int(num.strip())
        if clen <= 0:
            self.state.raw = head
            self.st.close()
            self.r.stop()
            return
        self.st.read(clen).then(ClientGotBody(self.r, self.st, self.state, head))


class ClientWritten(Continuation):
    r: Reactor
    st: Stream
    state: State
    def __init__(self, r: Reactor, st: Stream, state: State):
        super().__init__()
        self.r = r
        self.st = st
        self.state = state
    def run(self):
        if self.errored:
            self.r.stop()
            return
        self.st.read_until("\r\n\r\n").then(ClientGotHeaders(self.r, self.st, self.state))


# ---- safety watchdog ------------------------------------------------------------------------
class Watchdog(TimerCallback):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired (timeout) — stopping reactor")
        self.r.stop()


def main():
    r = Reactor()

    srv = Server(r, HelloApp(), "127.0.0.1", PORT)
    srv.serve()

    state = State()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(REQUEST).then(ClientWritten(r, client, state))

    r.call_later(5.0, Watchdog(r))
    r.run_forever()

    print("raw response:", repr(state.raw))

    # status line
    assert state.raw.startswith("HTTP/1.1 200"), "bad status line: " + repr(state.raw[:32])
    # Content-Type header
    assert state.raw.lower().find("content-type: application/json") >= 0, "missing JSON content-type"
    # correct Content-Length
    assert state.raw.lower().find("content-length: 17") >= 0, "missing/incorrect Content-Length"
    # exact body
    assert state.body == "{\"hello\":\"world\"}", "bad body: " + repr(state.body)

    print("PASS: asgi server served {\"hello\":\"world\"} over HTTP")

    srv.stop()
    r.close()


main()
