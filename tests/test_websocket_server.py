# P43 milestone — a real WebSocket upgrade + echo over loopback, driven by ONE Reactor.
#
#   * the app exposes a WebSocketEndpoint (EchoEndpoint) whose on_message echoes the text back;
#   * the client (a raw Stream) sends the RFC 6455 upgrade request, asserts the 101 response and the
#     Sec-WebSocket-Accept value (the RFC §1.3 vector), then sends a MASKED text frame "ping";
#   * the server's WebSocketConnection decodes it, the endpoint echoes it, and the client decodes the
#     (unmasked, server->client) reply frame and asserts the payload.
#   * a watchdog stops the reactor so a bug can't hang CI.

from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import Server, ASGIApp, Scope, WebSocketSender, WebSocketEndpoint
from fastcodon.websocket import encode_frame, decode_frame, OP_TEXT

PORT = 54353
EXPECT_ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="     # accept for key "dGhlIHNhbXBsZSBub25jZQ=="
MESSAGE = "ping"

UPGRADE = ("GET /ws HTTP/1.1\r\n"
           "Host: x\r\n"
           "Upgrade: websocket\r\n"
           "Connection: Upgrade\r\n"
           "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
           "Sec-WebSocket-Version: 13\r\n"
           "\r\n")


# ---- server app ----------------------------------------------------------------------------
class EchoEndpoint(WebSocketEndpoint):
    def on_message(self, ws: WebSocketSender, data: str, is_text: bool) -> None:
        ws.send_text(data)       # echo


class EchoWSApp(ASGIApp):
    def websocket_endpoint(self, scope: Scope) -> Optional[WebSocketEndpoint]:
        ep: WebSocketEndpoint = EchoEndpoint()
        return ep


class State:
    head: str
    rbuf: str
    got_payload: str
    got_op: int
    done: bool
    def __init__(self):
        self.head = ""
        self.rbuf = ""
        self.got_payload = ""
        self.got_op = -1
        self.done = False


# ---- client continuation chain -------------------------------------------------------------
class ClientReadFrame(Continuation):
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
        if len(self.data) > 0:
            self.state.rbuf += self.data
        res = decode_frame(self.state.rbuf)
        if res is not None:
            (frame, consumed) = res
            self.state.got_op = frame.opcode
            self.state.got_payload = frame.payload
            self.state.done = True
            self.st.close()
            self.r.stop()
            return
        if self.eof:
            self.r.stop()
            return
        self.st.read_some().then(ClientReadFrame(self.r, self.st, self.state))


class ClientSentFrame(Continuation):
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
        self.st.read_some().then(ClientReadFrame(self.r, self.st, self.state))


class ClientGotHandshake(Continuation):
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
        self.state.head = self.data
        # client->server frames MUST be masked (RFC 6455 §5.3).
        frame = encode_frame(OP_TEXT, MESSAGE, mask=True, mask_key="abcd")
        self.st.write(frame).then(ClientSentFrame(self.r, self.st, self.state))


class ClientWrote(Continuation):
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
        self.st.read_until("\r\n\r\n").then(ClientGotHandshake(self.r, self.st, self.state))


class Watchdog(TimerCallback):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired (timeout) — stopping reactor")
        self.r.stop()


def main():
    r = Reactor()
    srv = Server(r, EchoWSApp(), "127.0.0.1", PORT)
    srv.serve()

    state = State()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(UPGRADE).then(ClientWrote(r, client, state))

    r.call_later(5.0, Watchdog(r))
    r.run_forever()

    head = state.head
    print("handshake head:", repr(head[:60]))
    assert head.startswith("HTTP/1.1 101"), "bad status: " + repr(head[:32])
    assert head.find("Sec-WebSocket-Accept: " + EXPECT_ACCEPT) >= 0, "bad/missing accept"

    assert state.done, "no echo frame received"
    assert state.got_op == OP_TEXT, "echo opcode " + str(state.got_op) + " != OP_TEXT"
    assert state.got_payload == MESSAGE, "echo payload " + repr(state.got_payload)

    print("PASS: websocket upgrade + echo of", repr(MESSAGE), "round-tripped")
    srv.stop()
    r.close()


main()
