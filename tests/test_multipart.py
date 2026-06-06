# P25 multipart leaf — verify RFC 7578 multipart/form-data parsing.
from fastcodon.multipart import Part, parse_multipart, MultipartParser

CRLF = "\r\n"
BOUNDARY = "----codonBoundary"
DELIM = "--" + BOUNDARY


def build_body() -> str:
    # Construct the canonical test body with explicit CRLFs (no stray whitespace).
    return (
        DELIM + CRLF
        + 'Content-Disposition: form-data; name="field1"' + CRLF
        + CRLF
        + "value1" + CRLF
        + DELIM + CRLF
        + 'Content-Disposition: form-data; name="file1"; filename="a.txt"' + CRLF
        + "Content-Type: text/plain" + CRLF
        + CRLF
        + "file contents here" + CRLF
        + DELIM + "--" + CRLF
    )


def check(parts: List[Part], label: str):
    assert len(parts) == 2, label + ": expected 2 parts, got " + str(len(parts))

    p0 = parts[0]
    assert p0.name == "field1", label + ": p0.name=" + p0.name
    assert p0.filename is None, label + ": p0.filename should be None"
    assert p0.data == "value1", label + ": p0.data=" + p0.data

    p1 = parts[1]
    assert p1.name == "file1", label + ": p1.name=" + p1.name
    assert p1.filename is not None, label + ": p1.filename should be set"
    assert p1.filename == "a.txt", label + ": p1.filename=" + str(p1.filename)
    assert p1.content_type is not None, label + ": p1.content_type should be set"
    assert p1.content_type == "text/plain", label + ": p1.content_type=" + str(p1.content_type)
    assert p1.data == "file contents here", label + ": p1.data=" + p1.data


def main():
    body = build_body()

    # 1) One-shot parse.
    parts = parse_multipart(body, BOUNDARY)
    check(parts, "one-shot")
    print("ok: one-shot parse")

    # 2) Streaming parse, split at an awkward point: middle of the 2nd boundary.
    # Find the second occurrence of the delimiter and split inside it.
    first = body.find(DELIM)
    second = body.find(DELIM, first + len(DELIM))
    split_at = second + 4  # a few bytes into "--" + boundary token
    mp = MultipartParser(BOUNDARY)
    mp.feed(body[:split_at])
    mp.feed(body[split_at:])
    sparts = mp.parts()
    check(sparts, "streaming")
    print("ok: streaming parse (split mid-boundary)")

    # 3) Body whose data contains bytes that look like a partial boundary but
    # aren't a real delimiter -> must NOT split incorrectly.
    tricky_data = "abc--" + BOUNDARY[:5] + "xyz\r\n--notTheBoundary def"
    tricky = (
        DELIM + CRLF
        + 'Content-Disposition: form-data; name="blob"' + CRLF
        + CRLF
        + tricky_data + CRLF
        + DELIM + "--" + CRLF
    )
    tparts = parse_multipart(tricky, BOUNDARY)
    assert len(tparts) == 1, "tricky: expected 1 part, got " + str(len(tparts))
    assert tparts[0].name == "blob", "tricky: name=" + tparts[0].name
    assert tparts[0].data == tricky_data, "tricky: data=" + tparts[0].data
    print("ok: partial-boundary-in-data not mis-split")

    print("PASS: all multipart vectors match")


main()
