# P65 — WebSocket routing through a WebApp: an upgrade on a {room} WS route, echoed with the
# path param prefixed, proving WS routes dispatch through the existing L4 ws_transport.
from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import Server, Scope, WebSocketSender, WebSocketEndpoint
from fastcodon.websocket import encode_frame, decode_frame, OP_TEXT
from fastcodon.web import Router, WSEndpointFactory, WebApp, Middleware

PORT = 54377
MESSAGE = "ping"
EXPECT = "lobby:ping"

UPGRADE = ("GET /ws/lobby HTTP/1.1\r\n"
           "Host: x\r\n"
           "Upgrade: websocket\r\n"
           "Connection: Upgrade\r\n"
           "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
           "Sec-WebSocket-Version: 13\r\n"
           "\r\n")


class EchoEndpoint(WebSocketEndpoint):
    room: str
    def __init__(self, room: str):
        self.room = room
    def on_message(self, ws: WebSocketSender, data: str, is_text: bool) -> None:
        ws.send_text(self.room + ":" + data)


class EchoFactory(WSEndpointFactory):
    def create(self, params: Dict[str, str]) -> WebSocketEndpoint:
        room = params["room"] if "room" in params else "?"
        ep: WebSocketEndpoint = EchoEndpoint(room)
        return ep


def build_app() -> WebApp:
    router = Router()
    router.websocket("/ws/{room}", EchoFactory())
    return WebApp(router, List[Middleware]())


class St:
    head: str
    rbuf: str
    got: str
    op: int
    done: bool
    def __init__(self):
        self.head = ""
        self.rbuf = ""
        self.got = ""
        self.op = -1
        self.done = False


class ReadFrame(Continuation):
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
        if len(self.data) > 0:
            self.s.rbuf += self.data
        res = decode_frame(self.s.rbuf)
        if res is not None:
            (frame, consumed) = res
            self.s.op = frame.opcode
            self.s.got = frame.payload
            self.s.done = True
            self.st.close(); self.r.stop(); return
        if self.eof:
            self.r.stop(); return
        self.st.read_some().then(ReadFrame(self.r, self.st, self.s))


class Sent(Continuation):
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
        self.st.read_some().then(ReadFrame(self.r, self.st, self.s))


class GotHandshake(Continuation):
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
        self.s.head = self.data
        frame = encode_frame(OP_TEXT, MESSAGE, mask=True, mask_key="abcd")
        self.st.write(frame).then(Sent(self.r, self.st, self.s))


class Wrote(Continuation):
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
        self.st.read_until("\r\n\r\n").then(GotHandshake(self.r, self.st, self.s))


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

    s = St()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(UPGRADE).then(Wrote(r, client, s))

    r.call_later(5.0, Watchdog(r))
    r.run_forever()

    assert s.head.startswith("HTTP/1.1 101"), "bad status: " + repr(s.head[:32])
    assert s.done, "no echo frame received"
    assert s.op == OP_TEXT, "echo opcode " + str(s.op)
    assert s.got == EXPECT, "echo payload " + repr(s.got) + " != " + repr(EXPECT)

    print("PASS: websocket route {room} dispatched + echoed", repr(EXPECT))
    srv.stop()
    r.close()


main()
