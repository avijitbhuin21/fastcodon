# P12 selector leaf — echo round-trip driven by the readiness Selector (poll/WSAPoll),
# not a busy spin. Exercises register/modify/unregister + EV_READ/EV_WRITE on real sockets.

from fastcodon.net.socket import listen_tcp, tcp_socket, Socket, INVALID_HANDLE
from fastcodon.net.selector import Selector, EV_READ, EV_WRITE

PORT = 8166

def main():
    server = listen_tcp("127.0.0.1", PORT, backlog=8)
    server.setblocking(False)

    client = tcp_socket()
    client.setblocking(False)
    client.connect("127.0.0.1", PORT)   # in progress

    sel = Selector()
    sel.register(server.fd, EV_READ, token=1)
    sel.register(client.fd, EV_WRITE, token=2)   # writable => connect done

    conn = Socket(INVALID_HANDLE)
    sent = False
    got = ""
    rounds = 0

    while got == "" and rounds < 1000:
        rounds += 1
        for ev in sel.select(1000):
            if ev.token == 1 and ev.readable:
                c = server.accept()
                if c.valid:
                    c.setblocking(False)
                    conn = c
                    sel.register(conn.fd, EV_READ, token=3)
            elif ev.token == 2 and ev.writable and not sent:
                client.send("ping")
                sent = True
                sel.modify(client.fd, EV_READ)        # now await the echo
            elif ev.token == 3 and ev.readable:
                data = conn.recv(64)
                if data != "":
                    conn.send(data)                   # echo
            elif ev.token == 2 and ev.readable:
                r = client.recv(64)
                if r != "":
                    got = r

    print("rounds:", rounds)
    print("echo:", got)
    assert got == "ping", "expected 'ping', got '" + got + "'"
    print("PASS: selector-driven echo works")

    sel.close()
    conn.close(); client.close(); server.close()

main()
