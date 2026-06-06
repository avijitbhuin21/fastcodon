# P21 JSON leaf — verify the RFC 8259 encoder + decoder against vectors and round-trips.
from fastcodon.json import (JsonValue, loads, dumps,
                            NULL, BOOL, INT, FLOAT, STR, ARRAY, OBJECT)

def check(name: str, cond: bool):
    status = "ok" if cond else "FAIL"
    print(name, "->", status)
    assert cond, name + " failed"

def main():
    # ---- RFC 8259 sample object ----
    v = loads('{"a":1,"b":[true,false,null],"s":"hiA"}')
    check("sample is object", v.is_object())
    check("sample a==1", v["a"].as_int() == 1)
    b = v["b"]
    check("sample b is array len 3", b.is_array() and len(b) == 3)
    check("sample b[0] true", b.as_list()[0].as_bool() == True)
    check("sample b[1] false", b.as_list()[1].as_bool() == False)
    check("sample b[2] null", b.as_list()[2].is_null())
    check("sample s == hiA", v["s"].as_str() == "hiA")

    # ---- numbers: negative, decimal, exponent ----
    check("int 0", loads("0").as_int() == 0)
    check("negative int", loads("-42").as_int() == -42)
    check("decimal", abs(loads("1.5").as_float() - 1.5) < 1e-12)
    check("neg decimal", abs(loads("-3.25").as_float() + 3.25) < 1e-12)
    check("exponent 1e3", abs(loads("1e3").as_float() - 1000.0) < 1e-9)
    check("exponent 1.5E-2", abs(loads("1.5E-2").as_float() - 0.015) < 1e-12)
    check("big int", loads("1000000000000").as_int() == 1000000000000)

    # ---- literals ----
    check("true literal", loads("true").as_bool() == True)
    check("false literal", loads("false").as_bool() == False)
    check("null literal", loads("null").is_null())

    # ---- whitespace insignificance ----
    w = loads('  {  "x" :  [ 1 , 2 ,3 ]  }  ')
    check("ws object x len 3", len(w["x"]) == 3)
    check("ws x[2]==3", w["x"].as_list()[2].as_int() == 3)

    # ---- empty containers ----
    check("empty object", loads("{}").is_object() and len(loads("{}")) == 0)
    check("empty array", loads("[]").is_array() and len(loads("[]")) == 0)

    # ---- escapes (decode) ----
    e = loads('"a\\"b\\\\c\\n\\t\\/\\u0041\\u00e9"')
    # expected: a"b\c<newline><tab>/Aé   (é is UTF-8 C3 A9)
    es = e.as_str()
    # decoded bytes: a " b \ c \n \t / A 0xC3 0xA9
    check("escape quote", es[0:3] == 'a"b')
    check("escape backslash present", ord(es[3]) == 92)
    check("escape c", es[4] == "c")
    check("escape newline", ord(es[5]) == 10)
    check("escape tab", ord(es[6]) == 9)
    check("escape slash", es[7] == "/")
    check("escape \\u0041 -> A", es[8] == "A")
    # é = U+00E9 -> UTF-8 0xC3 0xA9
    check("escape \\u00e9 byte0", ord(es[9]) == 0xC3)
    check("escape \\u00e9 byte1", ord(es[10]) == 0xA9)

    # surrogate pair: U+1F600 (grinning face) -> UTF-8 F0 9F 98 80
    sp = loads('"\\uD83D\\uDE00"').as_str()
    check("surrogate len 4 bytes", len(sp) == 4)
    check("surrogate byte0", ord(sp[0]) == 0xF0)
    check("surrogate byte3", ord(sp[3]) == 0x80)

    # ---- escapes (encode) ----
    enc = dumps(JsonValue.from_str("a\"b\\c\nd\te"))
    check("encode escapes", enc == '"a\\"b\\\\c\\nd\\te"')
    # control char -> \u00XX (build a 1-byte string holding 0x01)
    ctrl = byte(1)
    encc = dumps(JsonValue.from_str(str(__ptr__(ctrl), 1)))
    check("encode control \\u0001", encc == '"\\u0001"')

    # ---- nested structure encode ----
    inner = JsonValue.object({"n": JsonValue.from_int(7),
                              "list": JsonValue.array([JsonValue.from_str("x"),
                                                       JsonValue.null()])})
    nested = JsonValue.array([inner, JsonValue.from_bool(True)])
    ns = dumps(nested)
    rn = loads(ns)
    check("nested roundtrip is array", rn.is_array() and len(rn) == 2)
    check("nested inner n==7", rn.as_list()[0]["n"].as_int() == 7)
    check("nested inner list[0]==x", rn.as_list()[0]["list"].as_list()[0].as_str() == "x")
    check("nested inner list[1] null", rn.as_list()[0]["list"].as_list()[1].is_null())
    check("nested [1] true", rn.as_list()[1].as_bool() == True)

    # ---- encode scalars ----
    check("dumps null", dumps(JsonValue.null()) == "null")
    check("dumps true", dumps(JsonValue.from_bool(True)) == "true")
    check("dumps int", dumps(JsonValue.from_int(-17)) == "-17")
    check("dumps empty arr", dumps(JsonValue.array(List[JsonValue]())) == "[]")
    check("dumps empty obj", dumps(JsonValue.object(Dict[str, JsonValue]())) == "{}")

    # ---- round-trip the sample ----
    rt = loads(dumps(v))
    check("roundtrip a==1", rt["a"].as_int() == 1)
    check("roundtrip s==hiA", rt["s"].as_str() == "hiA")
    check("roundtrip b len 3", len(rt["b"]) == 3)

    # ---- malformed input raises ----
    threw = False
    try:
        loads('{"a":}')
    except ValueError:
        threw = True
    check("malformed object raises", threw)

    threw2 = False
    try:
        loads("[1,2")
    except ValueError:
        threw2 = True
    check("unterminated array raises", threw2)

    threw3 = False
    try:
        loads("nul")
    except ValueError:
        threw3 = True
    check("bad literal raises", threw3)

    print("PASS: all json vectors match")

main()
