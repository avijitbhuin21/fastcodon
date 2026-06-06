# P14 TLS — real handshake + HTTPS GET against a live host, driven non-blocking through the
# reactor pattern (TLS_WANT_READ/WRITE -> wait on the fd). Validates fastcodon.tls end-to-end.
# Needs OpenSSL linked + network. Run: codon run -l ws2_32 -l <libcrypto> -l <libssl> this.py

from fastcodon.net.socket import tcp_socket
from fastcodon.net.selector import Selector, EV_READ, EV_WRITE
from fastcodon.tls import (TLSContext, openssl_version,
                           TLS_OK, TLS_WANT_READ, TLS_WANT_WRITE, TLS_CLOSED, TLS_ERROR)

from C import ERR_get_error() -> u64 as _err_get
from C import WSAGetLastError() -> i32 as _wsa_err

HOST = "one.one.one.one"
IP = "1.1.1.1"
PORT = 443

def _wait(sel: Selector, fd: int, status: int):
    ev = EV_READ if status == TLS_WANT_READ else EV_WRITE
    sel.modify(fd, ev)
    sel.select(2000)

def main():
    print("OpenSSL:", openssl_version())

    # resolve via a plain connect to the host's IP — use a fixed reachable IP path:
    # (example.com is reachable; connect by hostname requires DNS — use a known IP literal.)
    sock = tcp_socket()
    sock.setblocking(False)
    sock.connect(IP, PORT)

    sel = Selector()
    sel.register(sock.fd, EV_WRITE)
    cwait = 0
    while cwait < 8:                       # wait for TCP connect to complete (writable)
        cwait += 1
        ready = sel.select(2000)
        if len(ready) > 0:
            break
    print("tcp connected after", cwait, "wait(s)")

    ctx = TLSContext(server=False)
    ctx.set_verify(False)                  # skip cert verify for this smoke test
    conn = ctx.wrap(sock, server=False, server_hostname=HOST)

    # drive the non-blocking handshake
    tries = 0
    while tries < 25:
        tries += 1
        st = conn.handshake()
        if st == TLS_OK:
            break
        if st == TLS_WANT_READ or st == TLS_WANT_WRITE:
            _wait(sel, sock.fd, st)
        else:
            print("handshake error status:", st, "ssl_err:", int(_err_get()),
                  "wsa:", int(_wsa_err())); return
    print("handshake: OK after", tries, "step(s)")

    # send a minimal HTTP/1.1 request
    req = "GET / HTTP/1.1\r\nHost: " + HOST + "\r\nConnection: close\r\n\r\n"
    sent = False
    while not sent:
        st = conn.write(req)
        if st > 0:
            sent = True
        else:
            sel.modify(sock.fd, EV_WRITE); sel.select(2000)

    # read the response head
    sel.modify(sock.fd, EV_READ)
    resp = ""
    reads = 0
    while reads < 25 and len(resp) < 256:
        reads += 1
        data = conn.read(512)
        if data != "":
            resp += data
        else:
            sel.select(2000)
    head = resp.split("\r\n")[0] if resp != "" else "(empty)"
    print("HTTP status line:", head)
    assert head.startswith("HTTP/1.1"), "did not get an HTTP response"
    print("PASS: TLS handshake + HTTPS GET works end-to-end")

    conn.shutdown(); conn.close(); sock.close(); sel.close(); ctx.close()

main()
