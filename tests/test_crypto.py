# P13 crypto leaf — verify SHA-1, SHA-256, HMAC-SHA256, base64 against known vectors.
from fastcodon.crypto import (sha1_hex, sha256_hex, hmac_sha256_hex,
                              b64encode, b64decode)

def eq(name: str, got: str, want: str):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + got + " want " + want

def main():
    # SHA-1 (RFC 3174 / well-known)
    eq("sha1('')",    sha1_hex(""),    "da39a3ee5e6b4b0d3255bfef95601890afd80709")
    eq("sha1('abc')", sha1_hex("abc"), "a9993e364706816aba3e25717850c26c9cd0d89d")

    # SHA-256 (FIPS 180-4)
    eq("sha256('')",    sha256_hex(""),
       "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    eq("sha256('abc')", sha256_hex("abc"),
       "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    # HMAC-SHA256 (RFC 4231-style)
    eq("hmac('','')", hmac_sha256_hex("", ""),
       "b613679a0814d9ec772f95d778c35fc5ff1697c493715653c6c712144292c5ad")
    eq("hmac('key','The quick brown fox jumps over the lazy dog')",
       hmac_sha256_hex("key", "The quick brown fox jumps over the lazy dog"),
       "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8")

    # base64 (RFC 4648)
    eq("b64('Man')",  b64encode("Man"),  "TWFu")
    eq("b64('Ma')",   b64encode("Ma"),   "TWE=")
    eq("b64('M')",    b64encode("M"),     "TQ==")
    eq("b64('foob')", b64encode("foob"), "Zm9vYg==")
    eq("b64 roundtrip", b64decode(b64encode("hello, codon!")), "hello, codon!")

    # WebSocket Sec-WebSocket-Accept (RFC 6455 example): base64(sha1(key + GUID))
    from fastcodon.crypto import sha1
    key = "dGhlIHNhbXBsZSBub25jZQ=="
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    eq("ws-accept", b64encode(sha1(key + guid)), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

    print("PASS: all crypto vectors match")

main()
