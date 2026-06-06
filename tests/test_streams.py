# P32 async-streams leaf — a REAL loopback echo over the callback reactor.
#
# Topology (one process, one Reactor, no threads):
#   * a listening socket on 127.0.0.1:PORT, registered via an Acceptor IOHandler;
#   * on accept, the server wraps the connection in a Stream and echoes one message back using
#     the async read/write path (read_until a newline delimiter, then write it straight back);
#   * a client Stream connects, write()s a message, read_until()s the echo, asserts equality,
#     then stops the reactor.
#   * a safety Timeout (P33) stops the reactor after a few seconds so a bug can't hang CI.
#
# Everything is driven by reactor.run_forever(); completions chain via Continuation objects whose
# run() reads results off self.c (the Completion the continuation was attached to).

from fastcodon.net.socket import listen_tcp, Socket
from fastcodon.net.selector import EV_READ
from fastcodon.reactor import Reactor, IOHandler
from fastcodon.aio.streams import Stream, Completion, Continuation, wrap_stream, connect_stream
from fastcodon.aio.timeout import Timeout, TimeoutAction

PORT = 54344
MSG = "hello async streams\n"     # newline so we can use read_until


class State:
    got: str
    ok: bool
    def __init__(self):
        self.got = ""
        self.ok = False


# ---- server side: read_until('\n'), then echo it back -------------------------------------
class ServerEchoWritten(Continuation):
    """Write finished -> close the server stream."""
    s: Stream
    def __init__(self, s: Stream):
        super().__init__()
        self.s = s
    def run(self):
        self.s.close()

class ServerGotLine(Continuation):
    """Read finished -> echo the bytes straight back."""
    s: Stream
    def __init__(self, s: Stream):
        super().__init__()
        self.s = s
    def run(self):
        if self.errored:
            self.s.close()
            return
        self.s.write(self.data).then(ServerEchoWritten(self.s))

class Acceptor(IOHandler):
    r: Reactor
    server: Socket
    def __init__(self, r: Reactor, server: Socket):
        self.r = r
        self.server = server
    def on_readable(self):
        while True:
            c = self.server.accept()
            if not c.valid:
                break
            st = wrap_stream(self.r, c)
            st.read_until("\n").then(ServerGotLine(st))


# ---- client side: connect, write, read_until('\n'), assert, stop --------------------------
class ClientGotEcho(Continuation):
    r: Reactor
    st: Stream
    state: State
    def __init__(self, r: Reactor, st: Stream, state: State):
        super().__init__()
        self.r = r
        self.st = st
        self.state = state
    def run(self):
        self.state.got = self.data
        self.state.ok = (self.data == MSG)
        self.st.close()
        self.r.stop()

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
        self.st.read_until("\n").then(ClientGotEcho(self.r, self.st, self.state))


# ---- safety watchdog (P33 timeout primitive) ----------------------------------------------
class StopReactor(TimeoutAction):
    r: Reactor
    def __init__(self, r: Reactor):
        self.r = r
    def run(self):
        print("WATCHDOG fired (timeout) — stopping reactor")
        self.r.stop()


def main():
    r = Reactor()

    server = listen_tcp("127.0.0.1", PORT, backlog=16)
    server.setblocking(False)
    r.register(server.fd, Acceptor(r, server), EV_READ)

    state = State()
    client = connect_stream(r, "127.0.0.1", PORT)
    client.write(MSG).then(ClientWritten(r, client, state))

    watchdog = Timeout(r, 5.0, StopReactor(r)).start()

    r.run_forever()
    watchdog.done()

    print("echo received:", repr(state.got))
    assert state.ok, "expected " + repr(MSG) + ", got " + repr(state.got)
    print("PASS: async streams loopback echo ok")

    server.close()
    r.close()

main()
