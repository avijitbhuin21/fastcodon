# L6.1 — non-raising JSON: try_loads / Request.json_safe never crash on malformed input.
from fastcodon.asgi import Scope
from fastcodon.json import try_loads, loads, dumps
from fastcodon.web import Request

def ok_case(name: str, s: str):
    (ok, v) = try_loads(s)
    print(name, "->", "ok" if ok else "FAIL")
    assert ok, name + ": expected ok for " + repr(s)

def bad_case(name: str, s: str):
    (ok, v) = try_loads(s)
    print(name, "->", "ok" if not ok else "FAIL")
    assert not ok, name + ": expected failure for " + repr(s)
    assert v.is_null(), name + ": value should be null on failure"

def main():
    # valid inputs round-trip
    (ok1, v1) = try_loads("{\"a\":1,\"b\":[true,null,\"x\"]}")
    assert ok1, "valid object"
    assert v1["a"].as_int() == 1, "a==1"
    assert len(v1["b"].as_list()) == 3, "b len 3"
    print("valid object -> ok")
    assert dumps(v1) == "{\"a\":1,\"b\":[true,null,\"x\"]}", "roundtrip: " + dumps(v1)
    print("valid roundtrip -> ok")

    ok_case("valid number", "  42.5e-2 ")
    ok_case("valid string", "\"hi\\n\\u2713\"")
    ok_case("valid nested", "[[[1]]]")
    ok_case("valid empties", "{}")

    # malformed inputs: must return (False, null), never crash
    bad_case("empty", "")
    bad_case("open brace", "{")
    bad_case("unclosed array", "[1,2")
    bad_case("missing value", "{\"a\":}")
    bad_case("bad literal", "tru")
    bad_case("trailing junk", "123abc")
    bad_case("unterminated string", "\"oops")
    bad_case("missing colon", "{\"a\" 1}")
    bad_case("bare comma", "[,]")
    bad_case("lone minus", "-")
    bad_case("bad escape", "\"a\\xb\"")

    # Request.json_safe mirrors it
    sc = Scope("http", "POST", "/", "", "1.1", List[Tuple[str, str]]())
    (g, gv) = Request(sc, "{\"n\":7}").json_safe()
    assert g and gv["n"].as_int() == 7, "json_safe valid"
    (b, bv) = Request(sc, "{not json").json_safe()
    assert (not b) and bv.is_null(), "json_safe invalid"
    print("Request.json_safe -> ok")

    # loads still works (raising API) on valid input
    assert loads("[1,2,3]").as_list()[2].as_int() == 3, "loads valid"
    print("loads valid -> ok")

    print("PASS: non-raising JSON decoder (L6.1)")

main()
