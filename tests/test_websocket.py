# P24 WebSocket leaf — verify RFC 6455 handshake + frame codec against spec vectors.
from fastcodon.websocket import (accept_key, build_handshake_response,
                                 Frame, encode_frame, decode_frame,
                                 build_close_payload, parse_close_payload,
                                 OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG)
from fastcodon.sys.buf import bytes_to_str, byte_at

def bs(vals: List[int]) -> str:
    """Build a byte str from a list of byte values."""
    b = List[byte]()
    for v in vals:
        b.append(byte(v & 0xff))
    return bytes_to_str(b)

def hexstr(s: str) -> str:
    digits = "0123456789abcdef"
    out = ""
    for i in range(len(s)):
        c = byte_at(s, i)
        out += digits[(c >> 4) & 0xf]
        out += digits[c & 0xf]
        out += " "
    return out

def eq(name: str, got: str, want: str):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got [" + hexstr(got) + "] want [" + hexstr(want) + "]"

def eqi(name: str, got: int, want: int):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name + ": got " + str(got) + " want " + str(want)

def eqb(name: str, got: bool, want: bool):
    status = "ok" if got == want else "FAIL"
    print(name, "->", status)
    assert got == want, name

def main():
    # --- Handshake (RFC 6455 §1.3) ---
    eq("accept_key", accept_key("dGhlIHNhbXBsZSBub25jZQ=="),
       "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")
    resp = build_handshake_response("dGhlIHNhbXBsZSBub25jZQ==")
    eqb("handshake 101 line",
        resp.startswith("HTTP/1.1 101 Switching Protocols\r\n"), True)
    eqb("handshake accept header",
        "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n" in resp, True)

    # --- Unmasked text "Hello" (RFC 6455 §5.7) ---
    hello_unmasked = bs([0x81, 0x05, 0x48, 0x65, 0x6c, 0x6c, 0x6f])
    eq("encode unmasked Hello", encode_frame(OP_TEXT, "Hello"), hello_unmasked)

    dec = decode_frame(hello_unmasked)
    assert dec is not None, "decode unmasked Hello returned None"
    f, consumed = dec
    eqi("decode unmasked opcode", f.opcode, OP_TEXT)
    eqb("decode unmasked fin", f.fin, True)
    eq("decode unmasked payload", f.payload, "Hello")
    eqi("decode unmasked consumed", consumed, 7)

    # --- Masked text "Hello" (RFC 6455 §5.7) ---
    hello_masked = bs([0x81, 0x85, 0x37, 0xfa, 0x21, 0x3d,
                       0x7f, 0x9f, 0x4d, 0x51, 0x58])
    dec2 = decode_frame(hello_masked)
    assert dec2 is not None, "decode masked Hello returned None"
    f2, consumed2 = dec2
    eqi("decode masked opcode", f2.opcode, OP_TEXT)
    eq("decode masked payload", f2.payload, "Hello")
    eqi("decode masked consumed", consumed2, 11)
    eqb("decode masked flag", f2.masked, True)

    # Re-encode masked with the same key reproduces the spec bytes.
    mk = bs([0x37, 0xfa, 0x21, 0x3d])
    eq("encode masked Hello", encode_frame(OP_TEXT, "Hello", mask=True, mask_key=mk),
       hello_masked)

    # --- 200-byte payload: forces 126/2-byte extended length ---
    p200 = bs([(i * 7 + 3) & 0xff for i in range(200)])
    enc200 = encode_frame(OP_BIN, p200)
    eqi("200 second byte == 126", byte_at(enc200, 1), 126)
    d200 = decode_frame(enc200)
    assert d200 is not None, "200 decode None"
    f200, c200 = d200
    eq("200 roundtrip payload", f200.payload, p200)
    eqi("200 consumed", c200, len(enc200))
    eqi("200 opcode", f200.opcode, OP_BIN)

    # --- 70000-byte payload: forces 127/8-byte extended length ---
    p70k = bs([(i * 13 + 5) & 0xff for i in range(70000)])
    enc70k = encode_frame(OP_BIN, p70k)
    eqi("70k second byte == 127", byte_at(enc70k, 1), 127)
    d70k = decode_frame(enc70k)
    assert d70k is not None, "70k decode None"
    f70k, c70k = d70k
    eqb("70k payload match", f70k.payload == p70k, True)
    eqi("70k consumed", c70k, len(enc70k))

    # Masked round-trip of the 200-byte payload.
    encm = encode_frame(OP_BIN, p200, mask=True, mask_key=bs([0x01, 0x02, 0x03, 0x04]))
    dm = decode_frame(encm)
    assert dm is not None, "masked 200 decode None"
    fm, cm = dm
    eq("masked 200 roundtrip", fm.payload, p200)
    eqb("masked 200 flag", fm.masked, True)

    # --- ping / pong / close opcode round-trips ---
    for op in [OP_PING, OP_PONG, OP_CLOSE]:
        e = encode_frame(op, "ab")
        de = decode_frame(e)
        assert de is not None, "ctrl decode None"
        ff, cc = de
        eqi("ctrl opcode " + str(op), ff.opcode, op)
        eq("ctrl payload " + str(op), ff.payload, "ab")

    # --- Close code 1000 + reason round-trip ---
    close_payload = build_close_payload(1000, "bye")
    code, reason = parse_close_payload(close_payload)
    eqi("close code", code, 1000)
    eq("close reason", reason, "bye")
    eframe = encode_frame(OP_CLOSE, close_payload)
    dcf = decode_frame(eframe)
    assert dcf is not None, "close frame decode None"
    cf, ccons = dcf
    eqi("close frame opcode", cf.opcode, OP_CLOSE)
    code2, reason2 = parse_close_payload(cf.payload)
    eqi("close frame code", code2, 1000)
    eq("close frame reason", reason2, "bye")

    # --- Partial buffer handling ---
    eqb("partial 1 byte -> None", decode_frame(bs([0x81])) is None, True)
    # header says payload len 5 but only 3 payload bytes present
    eqb("partial payload -> None",
        decode_frame(bs([0x81, 0x05, 0x48, 0x65, 0x6c])) is None, True)
    # extended-length header truncated
    eqb("partial ext-len -> None",
        decode_frame(bs([0x82, 0x7e, 0x00])) is None, True)
    # masked, mask key truncated
    eqb("partial mask-key -> None",
        decode_frame(bs([0x81, 0x85, 0x37, 0xfa])) is None, True)

    print("PASS: all websocket vectors match")

main()
