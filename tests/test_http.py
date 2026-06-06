# P23 http leaf — verify the sans-I/O HTTP/1.1 request parser against the spec vectors.
from fastcodon.http import Request, RequestParser, keep_alive

def parse_one(data: str) -> Request:
    p = RequestParser()
    p.feed(data)
    r = p.result()
    assert r is not None, "expected a complete request, got None"
    return r

def main():
    # 1) Simple GET
    r = parse_one("GET /path?q=1 HTTP/1.1\r\nHost: example.com\r\nUser-Agent: x\r\n\r\n")
    assert r.method == "GET", "method " + r.method
    assert r.target == "/path?q=1", "target " + r.target
    assert r.http_version == "1.1", "version " + r.http_version
    assert r.get("Host") == "example.com", "Host"
    assert r.body == "", "body should be empty"
    assert keep_alive(r) == True, "GET keep_alive"
    print("ok -> simple GET")

    # 2) Content-Length POST
    r = parse_one("POST /submit HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\n\r\nhello")
    assert r.method == "POST", "method"
    assert r.target == "/submit", "target"
    assert r.body == "hello", "body " + r.body
    print("ok -> Content-Length POST")

    # 3) Chunked
    r = parse_one("POST /up HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n"
                  "5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n")
    assert r.body == "hello world", "chunked body " + r.body
    print("ok -> chunked body")

    # 4) Split feed across two arbitrary slices -> parses identically.
    full = "GET /path?q=1 HTTP/1.1\r\nHost: example.com\r\nUser-Agent: x\r\n\r\n"
    cut = 20
    p = RequestParser()
    p.feed(full[:cut])
    assert p.result() is None, "should be incomplete before terminator"
    p.feed(full[cut:])
    r2 = p.result()
    assert r2 is not None, "should be complete after terminator"
    assert r2.method == "GET" and r2.target == "/path?q=1", "split GET fields"
    assert r2.http_version == "1.1", "split version"
    assert r2.get("Host") == "example.com", "split Host"
    print("ok -> split feed")

    # 5) Connection: close -> keep_alive False
    r = parse_one("GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
    assert keep_alive(r) == False, "Connection: close keep_alive"
    print("ok -> Connection: close")

    # 6) Case-insensitive header lookup
    r = parse_one("POST /submit HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\n\r\nhello")
    assert r.get("content-length") == "5", "case-insensitive content-length"
    assert r.get("CONTENT-LENGTH") == "5", "uppercase content-length"
    print("ok -> case-insensitive header lookup")

    print("PASS: all http parser vectors match")

main()
