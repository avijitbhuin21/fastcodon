# P11 socket leaf — single-process non-blocking TCP echo.
# Drives a listener + client in one event loop (no threads): connect (in-progress),
# accept, send, recv, echo, recv — all non-blocking. Cross-platform.

from fastcodon.net.socket import listen_tcp, tcp_socket, Socket, INVALID_HANDLE

PORT = 8137

def main():
    server = listen_tcp("127.0.0.1", PORT, backlog=8)
    server.setblocking(False)

    client = tcp_socket()
    client.setblocking(False)
    established = client.connect("127.0.0.1", PORT)
    print("connect immediate:", established)

    conn = Socket(INVALID_HANDLE)   # server-side accepted connection
    got_echo = ""
    sent = False
    echoed = False
    spins = 0

    while spins < 100000:
        spins += 1

        # 1) accept the inbound connection once
        if not conn.valid:
            c = server.accept()
            if c.valid:
                conn = c
                conn.setblocking(False)

        # 2) client sends once (after connect completes the socket is writable locally)
        if conn.valid and not sent:
            client.send("ping")
            sent = True

        # 3) server echoes what it receives
        if conn.valid and not echoed:
            data = conn.recv(64)
            if data != "":
                conn.send(data)
                echoed = True

        # 4) client reads the echo back
        if echoed:
            r = client.recv(64)
            if r != "":
                got_echo = r
                break

    print("spins:", spins)
    print("echo received:", got_echo)
    assert got_echo == "ping", "expected 'ping', got '" + got_echo + "'"
    print("PASS: socket echo round-trip works")

    conn.close()
    client.close()
    server.close()

main()
