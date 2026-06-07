# P42b milestone — a STREAMED (chunked) response OUT over loopback, driven by ONE Reactor.
#
# The app returns Response.stream(producer); the producer emits N distinct blocks pulled one at a
# time (never the whole body at once). The server frames them as HTTP/1.1 chunked transfer-encoding.
# The client asserts 200 + Transfer-Encoding: chunked + NO Content-Length, reads to EOF, de-chunks
# client-side, and checks the reassembled body equals the concatenation of all blocks.

from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import Server, ASGIApp, Scope, Response, BodyProducer

PORT = 54351
NBLOCKS = 100
REQUEST = "GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"


def block_for(i: int) -> str:
    # A distinct, multi-byte block per index so reassembly order is actually verified.
    return "block-" + str(i) + "-payload\n"


def expected_body() -> str:
    out = List[str]()
    for i in range(NBLOCKS):
        out.append(block_for(i))
    return "".join(out)


class CounterProducer(BodyProducer):
    n: int
    i: int
    def __init__(self, n: int):
        self.n = n
        self.i = 0
    def next_chunk(self) -> str:
        if self.i >= self.n:
            return ""
        b = block_for(self.i)
        self.i += 1
        return b


class StreamApp(ASGIApp):
    def handle(self, scope: Scope, body: str) -> Response:
        return Response.stream(CounterProducer(NBLOCKS), content_type="text/plain")


class State:
    head: str
    body_raw: str       # raw chunked bytes after the header block
    ok: bool
    def __init__(self):
        self.head = ""
        self.body_raw = ""
        self.ok = False


def dechunk(data: str) -> str:
    # Decode an HTTP/1.1 chunked body into the underlying bytes.
    out = List[str]()
    pos = 0
    n = len(data)
    while pos < n:
        line_end = data.find("\r\n", pos)
        if line_end < 0:
            break
        size_line = data[pos:line_end]
        semi = size_line.find(";")
        if semi >= 0:
            size_line = size_line[:semi]
        size_line = size_line.strip()
        size = 0
        for ch in size_line:
            c = ord(ch)
            if 48 <= c <= 57:
                size = size * 16 + (c - 48)
            elif 97 <= c <= 102:
                size = size * 16 + (c - 97 + 10)
            elif 65 <= c <= 70:
                size = size * 16 + (c - 65 + 10)
        ds = line_end + 2
        if size == 0:
            break
        out.append(data[ds:ds + size])
        pos = ds + size + 2          # skip the chunk data + trailing CRLF
    return "".join(out)


# ---- client continuation chain -------------------------------------------------------------
class ClientReadBody(Continuation):
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
            self.state.body_raw += self.data
        if self.eof:
            self.st.close()
            self.r.stop()
            return
        self.st.read_some().then(ClientReadBody(self.r, self.st, self.state))


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
        self.state.head = self.data
        self.st.read_some().then(ClientReadBody(self.r, self.st, self.state))


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


class Watchdog(TimerCallback):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired (timeout) — stopping reactor")
        self.r.stop()


def main():
    r = Reactor()
    srv = Server(r, StreamApp(), "127.0.0.1", PORT)
    srv.serve()

    state = State()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(REQUEST).then(ClientWritten(r, client, state))

    r.call_later(5.0, Watchdog(r))
    r.run_forever()

    head = state.head
    print("head:", repr(head[:80]))
    assert head.startswith("HTTP/1.1 200"), "bad status: " + repr(head[:32])
    assert head.lower().find("transfer-encoding: chunked") >= 0, "missing chunked TE"
    assert head.lower().find("content-length:") < 0, "must NOT have Content-Length when streaming"

    body = dechunk(state.body_raw)
    exp = expected_body()
    assert len(body) == len(exp), "body length " + str(len(body)) + " != " + str(len(exp))
    assert body == exp, "reassembled body mismatch"

    print("PASS: streamed", NBLOCKS, "chunks OUT,", len(body), "bytes reassembled correctly")
    srv.stop()
    r.close()


main()
