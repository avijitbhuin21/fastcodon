# P22 urllib leaf — verify percent-encoding, query strings, cookies, HTTP dates.
from fastcodon.urllib import (quote, unquote, quote_plus, unquote_plus,
                              parse_qs, parse_qsl, urlencode,
                              parse_cookie, dump_cookie,
                              format_http_date, parse_http_date)

def eq(name: str, got: str, want: str):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + got + " want " + want

def eqi(name: str, got: int, want: int):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + str(got) + " want " + str(want)

def main():
    # --- url: quote / unquote (RFC 3986) ---
    eq("quote('a b/c')",      quote("a b/c"),          "a%20b/c")
    eq("quote safe default",  quote("/"),              "/")
    eq("quote no safe",       quote("a/b", ""),        "a%2Fb")
    eq("quote unreserved",    quote("Aa0-._~"),        "Aa0-._~")
    eq("quote_plus('a b')",   quote_plus("a b"),       "a+b")
    eq("unquote('%41%42')",   unquote("%41%42"),       "AB")
    eq("unquote lowercase",   unquote("%e2%9c%93"),    "\xe2\x9c\x93")

    # UTF-8 check mark U+2713 -> bytes E2 9C 93
    check = "\xe2\x9c\x93"
    eq("quote(checkmark)",    quote(check),            "%E2%9C%93")
    eq("unquote(%E2%9C%93)",  unquote("%E2%9C%93"),    check)

    # round-trip arbitrary bytes
    sample = "hello, world! / ? & = + #"
    eq("quote roundtrip",     unquote(quote(sample)),  sample)
    eq("quote_plus roundtrip",unquote_plus(quote_plus(sample)), sample)

    # --- querystring ---
    qsl = parse_qsl("a=1&b=2&a=3")
    assert len(qsl) == 3, "parse_qsl length"
    eq("qsl[0]", qsl[0][0] + "=" + qsl[0][1], "a=1")
    eq("qsl[1]", qsl[1][0] + "=" + qsl[1][1], "b=2")
    eq("qsl[2]", qsl[2][0] + "=" + qsl[2][1], "a=3")
    print("parse_qsl repeated keys -> ok")

    # missing '=' and empty segment handling
    qsl2 = parse_qsl("x&y=&=z&a=b")
    assert len(qsl2) == 4, "parse_qsl mixed length"
    eq("qsl2[0]", qsl2[0][0] + "|" + qsl2[0][1], "x|")
    eq("qsl2[1]", qsl2[1][0] + "|" + qsl2[1][1], "y|")
    eq("qsl2[2]", qsl2[2][0] + "|" + qsl2[2][1], "|z")
    eq("qsl2[3]", qsl2[3][0] + "|" + qsl2[3][1], "a|b")

    # parse_qs repeated keys
    qs = parse_qs("a=1&b=2&a=3")
    assert len(qs["a"]) == 2 and qs["a"][0] == "1" and qs["a"][1] == "3", "parse_qs a"
    assert qs["b"][0] == "2", "parse_qs b"
    print("parse_qs repeated keys -> ok")

    # urlencode + round-trip
    eq("urlencode", urlencode([("a", "1"), ("b", "2"), ("a", "3")]), "a=1&b=2&a=3")
    enc = urlencode([("q", "a b"), ("p", "x/y")])
    rt = parse_qsl(enc)
    eq("urlencode rt q", rt[0][0] + "=" + rt[0][1], "q=a b")
    eq("urlencode rt p", rt[1][0] + "=" + rt[1][1], "p=x/y")

    # --- cookies ---
    ck = parse_cookie("a=1; b=2")
    eq("parse_cookie a", ck["a"], "1")
    eq("parse_cookie b", ck["b"], "2")
    ck2 = parse_cookie("session=\"xyz\"; theme=dark")
    eq("parse_cookie quoted", ck2["session"], "xyz")
    eq("parse_cookie plain",  ck2["theme"],   "dark")

    sc = dump_cookie("sid", "abc", http_only=True, path="/")
    assert "sid=abc" in sc, "dump_cookie name=value: " + sc
    assert "Path=/" in sc,  "dump_cookie Path: " + sc
    assert "HttpOnly" in sc, "dump_cookie HttpOnly: " + sc
    print("dump_cookie basic -> ok")

    sc2 = dump_cookie("t", "v", secure=True, max_age=3600, same_site="Lax")
    assert "Secure" in sc2 and "Max-Age=3600" in sc2 and "SameSite=Lax" in sc2, "dump_cookie full: " + sc2
    print("dump_cookie full -> ok")

    # --- httpdate (EXACT RFC 7231 vector) ---
    eq("format_http_date(784111777)", format_http_date(784111777),
       "Sun, 06 Nov 1994 08:49:37 GMT")
    eqi("parse_http_date", parse_http_date("Sun, 06 Nov 1994 08:49:37 GMT"), 784111777)
    # round-trip a few epochs
    eqi("httpdate rt 0",          parse_http_date(format_http_date(0)),          0)
    eqi("httpdate rt 1717632000", parse_http_date(format_http_date(1717632000)), 1717632000)
    eq("format_http_date(0)", format_http_date(0), "Thu, 01 Jan 1970 00:00:00 GMT")

    print("PASS: all urllib vectors match")

main()
