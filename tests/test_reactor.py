# P31 reactor leaf — a real async echo server + N concurrent clients, all driven by ONE
# Reactor in a single process. Exercises accept fan-out, per-connection handlers, interest
# switching (write->read), timers (watchdog), and clean shutdown.

from sys import stderr
from fastcodon.net.socket import listen_tcp, tcp_socket, Socket
from fastcodon.net.selector import EV_READ, EV_WRITE
from fastcodon.reactor import Reactor, IOHandler, TimerCallback

def dbg(*args):
    # diagnostics on stderr — unbuffered, so they survive a CI watchdog kill (and avoid the
    # Windows-fork `print(flush=True)` crash).
    print(*args, file=stderr)

PORT = 8201
NCLIENTS = 5

class Box:
    done: int
    total: int
    def __init__(self, total: int):
        self.done = 0
        self.total = total

# server side: echo whatever arrives, close on EOF
class EchoConn(IOHandler):
    r: Reactor
    fd: int
    sock: Socket

    def __init__(self, r: Reactor, sock):
        self.r = r
        self.fd = sock.fd
        self.sock = sock

    def on_readable(self):
        data = self.sock.recv(256)
        if data == "":
            self.r.unregister(self.fd)
            self.sock.close()
        else:
            self.sock.send(data)

# server listener: accept all pending, wrap each in an EchoConn
class Acceptor(IOHandler):
    r: Reactor
    server: Socket

    def __init__(self, r: Reactor, server):
        self.r = r
        self.server = server

    def on_readable(self):
        while True:
            c = self.server.accept()
            if not c.valid:
                break
            c.setblocking(False)
            conn = EchoConn(self.r, c)
            self.r.register(c.fd, conn, EV_READ)

# client: once writable (connected) send a unique ping, then read the echo back
class Client(IOHandler):
    r: Reactor
    fd: int
    sock: Socket
    msg: str
    box: Box
    sent: bool

    def __init__(self, r: Reactor, sock, idx: int, box: Box):
        self.r = r
        self.fd = sock.fd
        self.sock = sock
        self.msg = "ping" + str(idx)
        self.box = box
        self.sent = False

    def on_writable(self):
        if not self.sent:
            self.sock.send(self.msg)
            self.sent = True
            self.r.want_write(self.fd, False)
            self.r.want_read(self.fd, True)

    def on_readable(self):
        echo = self.sock.recv(256)
        if echo != "":
            assert echo == self.msg, "client got '" + echo + "' want '" + self.msg + "'"
            self.box.done += 1
            dbg("client echoed:", echo, "done", self.box.done, "of", self.box.total)
            self.r.unregister(self.fd)
            self.sock.close()
            if self.box.done == self.box.total:
                self.r.stop()

class Watchdog(TimerCallback):
    r: Reactor
    box: Box
    def __init__(self, r: Reactor, box: Box):
        self.r = r
        self.box = box
    def run(self):
        dbg("WATCHDOG fired; clients done =", self.box.done)
        self.r.stop()

def main():
    r = Reactor()
    server = listen_tcp("127.0.0.1", PORT, backlog=16)
    server.setblocking(False)
    r.register(server.fd, Acceptor(r, server), EV_READ)

    box = Box(NCLIENTS)
    clients = []
    for i in range(NCLIENTS):
        cs = tcp_socket()
        cs.setblocking(False)
        cs.connect("127.0.0.1", PORT)
        r.register(cs.fd, Client(r, cs, i, box), EV_WRITE)
        clients.append(cs)

    r.call_later(8.0, Watchdog(r, box))    # safety timeout
    dbg("entering run_forever; clients:", NCLIENTS)
    r.run_forever()
    dbg("run_forever returned; done =", box.done)

    print("clients echoed:", box.done, "/", NCLIENTS)
    assert box.done == NCLIENTS, "not all clients completed"
    print("PASS: reactor async echo server handled", NCLIENTS, "clients")

    server.close()
    r.close()

main()
