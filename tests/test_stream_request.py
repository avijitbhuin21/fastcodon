# P42b milestone — a STREAMED request body IN, consumed incrementally, over loopback / ONE Reactor.
#
# The app opts into streaming (wants_stream -> True) and drains the request body chunk-by-chunk via
# a pull-based RequestBody, holding only a running byte count + checksum (never the whole body). It
# then answers "<total>:<checksum>". The client sends a large *chunked* request body and asserts the
# echoed totals match what it computed locally — proving the server framed and consumed the body
# incrementally (chunks split across the 64 KB socket reads) without buffering it whole.

from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Stream, Continuation, connect_stream
from fastcodon.asgi import (Server, ASGIApp, Scope, Response,
                            BodyReader, RequestBody, Responder)

PORT = 54352
MOD = 1000000007
NLINES = 6000          # ~ tens of KB -> spans multiple socket reads
CHUNK = 256            # client frames the body in 256-byte HTTP chunks


def make_payload() -> str:
    out = List[str]()
    for i in range(NLINES):
        out.append("line-" + str(i) + "-data\n")
    return "".join(out)


def checksum_of(s: str) -> int:
    c = 0
    for i in range(len(s)):
        c += ord(s[i])
    return c % MOD


def hexlower(n: int) -> str:
    if n == 0:
        return "0"
    d = "0123456789abcdef"
    rev = List[str]()
    v = n
    while v > 0:
        rev.append(d[v & 0xf])
        v >>= 4
    out = List[str]()
    i = len(rev) - 1
    while i >= 0:
        out.append(rev[i])
        i -= 1
    return "".join(out)


def chunk_encode(payload: str, size: int) -> str:
    out = List[str]()
    pos = 0
    n = len(payload)
    while pos < n:
        end = pos + size
        if end > n:
            end = n
        piece = payload[pos:end]
        out.append(hexlower(len(piece)) + "\r\n" + piece + "\r\n")
        pos = end
    out.append("0\r\n\r\n")
    return "".join(out)


# ---- server app: incremental drain ---------------------------------------------------------
class CountReader(BodyReader):
    body: RequestBody
    responder: Responder
    total: int
    checksum: int
    def __init__(self, body: RequestBody, responder: Responder):
        super().__init__()
        self.body = body
        self.responder = responder
        self.total = 0
        self.checksum = 0
    def on_chunk(self):
        if self.errored:
            self.responder.respond(Response.text("error", status=400))
            return
        data = self.data
        # Hold ONLY running totals — the body is never accumulated whole.
        for i in range(len(data)):
            self.checksum = (self.checksum + ord(data[i])) % MOD
        self.total += len(data)
        if self.done:
            self.responder.respond(Response.text(str(self.total) + ":" + str(self.checksum)))
            return
        me: BodyReader = self            # upcast for the virtual read_chunk call (Codon thunk rule)
        self.body.read_chunk(me)         # pull the next chunk (serially)


class UploadApp(ASGIApp):
    def wants_stream(self, scope: Scope) -> bool:
        return True
    def handle_stream(self, scope: Scope, body: RequestBody, responder: Responder) -> None:
        rdr: BodyReader = CountReader(body, responder)   # upcast for the virtual read_chunk call
        body.read_chunk(rdr)


class State:
    raw: str
    body: str
    def __init__(self):
        self.raw = ""
        self.body = ""


# ---- client: send chunked body, read the buffered reply ------------------------------------
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
        self.state.raw = head
        clen = 0
        low = head.lower()
        idx = low.find("content-length:")
        if idx >= 0:
            after = head[idx + len("content-length:"):]
            le = after.find("\r\n")
            num = after[:le] if le >= 0 else after
            clen = int(num.strip())
        if clen <= 0:
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


class Watchdog(TimerCallback):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired (timeout) — stopping reactor")
        self.r.stop()


def main():
    payload = make_payload()
    exp_total = len(payload)
    exp_csum = checksum_of(payload)
    request = ("POST /upload HTTP/1.1\r\nHost: x\r\n"
               "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
               + chunk_encode(payload, CHUNK))

    r = Reactor()
    srv = Server(r, UploadApp(), "127.0.0.1", PORT)
    srv.serve()

    state = State()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(request).then(ClientWritten(r, client, state))

    r.call_later(8.0, Watchdog(r))
    r.run_forever()

    print("reply body:", repr(state.body))
    expected = str(exp_total) + ":" + str(exp_csum)
    assert state.body == expected, "got " + repr(state.body) + " want " + repr(expected)

    print("PASS: streamed", exp_total, "bytes IN incrementally; total+checksum match")
    srv.stop()
    r.close()


main()
