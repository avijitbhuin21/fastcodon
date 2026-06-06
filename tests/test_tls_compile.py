# P14 TLS — compile-level exercise of the OpenSSL wrapper API surface. A real handshake needs
# OpenSSL linked (see fastcodon/tls/tls.codon header); this validates the Codon code itself.
from fastcodon.tls import TLSContext, openssl_version, TLS_OK, TLS_WANT_READ, TLS_WANT_WRITE
from fastcodon.net.socket import tcp_socket

def main():
    print("OpenSSL:", openssl_version())
    ctx = TLSContext(server=False)
    ctx.set_verify(False)

    s = tcp_socket()
    s.setblocking(False)
    conn = ctx.wrap(s, server=False, server_hostname="example.com")

    st = conn.handshake()
    if st == TLS_WANT_READ or st == TLS_WANT_WRITE:
        print("handshake in progress (expected without a peer)")
    elif st == TLS_OK:
        print("handshake complete")
    else:
        print("handshake status:", st)

    conn.close()
    s.close()
    ctx.close()

main()
