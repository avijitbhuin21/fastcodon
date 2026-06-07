# L5 (P51–P54) — the compile-time validation/serialization layer over real models.
#   * model_validate_json: coercion (incl. lax "42"->42), nested models, List[T], Optional[T]
#   * structured (loc, msg, type) errors for missing fields + bad types (returned, not raised)
#   * model_dump_json / model_dump: model -> JSON round-trip
#   * model_json_schema: model -> JSON Schema (object/properties/required, nested inlined)
#
# Exception-free API: validation RETURNS (model, errors) — Codon's exception unwinding faults on the
# current toolchain (the `seq_exc_filter` relocation bug), so the layer never raises.

from fastcodon.json import loads
from fastcodon.validate import (BaseModel, model_validate_json, model_validate, model_dump_json,
                                model_dump, model_json_schema, format_errors)


class Address(BaseModel):
    city: str
    zip: int


class User(BaseModel):
    id: int
    name: str
    age: float
    tags: List[str]
    addrs: List[Address]
    nick: Optional[str]


def test_validate_ok():
    src = ('{"id":7,"name":"bob","age":30.5,"tags":["x","y"],'
           '"addrs":[{"city":"NYC","zip":10001},{"city":"LA","zip":90001}],"nick":"bobby"}')
    u, errs = model_validate_json(src, User)
    assert len(errs) == 0, format_errors(errs)
    assert u.id == 7
    assert u.name == "bob"
    assert u.age == 30.5
    assert u.tags == ["x", "y"]
    assert len(u.addrs) == 2
    assert u.addrs[0].city == "NYC"
    assert u.addrs[1].zip == 90001
    assert u.nick.__bool__() and u.nick == "bobby"
    print("ok -> validate nested + List + Optional")


def test_lax_coercion():
    u, errs = model_validate_json(
        '{"id":"42","name":"x","age":"3.5","tags":[],"addrs":[],"nick":null}', User)
    assert len(errs) == 0, format_errors(errs)
    assert u.id == 42           # "42" -> 42
    assert u.age == 3.5         # "3.5" -> 3.5
    assert not u.nick.__bool__()   # null -> None
    print("ok -> lax coercion (str->int/float, null->None)")


def test_errors():
    # missing required `id`; `age` is not a number.
    obj, errs = model_validate_json(
        '{"name":"x","age":"notnum","tags":[],"addrs":[],"nick":null}', User)
    found_missing = False
    found_age = False
    for e in errs:
        if e.loc == "id" and e.type == "missing":
            found_missing = True
        if e.loc == "age" and e.type == "float_parsing":
            found_age = True
    assert found_missing, "expected missing error for id: " + format_errors(errs)
    assert found_age, "expected float_parsing error for age: " + format_errors(errs)
    print("ok -> structured errors (missing + type)")


def test_nested_error_loc():
    obj, errs = model_validate_json(
        '{"id":1,"name":"x","age":1.0,"tags":[],'
        '"addrs":[{"city":"A","zip":1},{"city":"B","zip":"bad"}],"nick":null}', User)
    found = False
    for e in errs:
        if e.loc == "addrs.1.zip" and e.type == "int_parsing":
            found = True
    assert found, "expected nested error loc addrs.1.zip: " + format_errors(errs)
    print("ok -> nested/indexed error loc (addrs.1.zip)")


def test_dump_roundtrip():
    src = ('{"id":7,"name":"bob","age":30.5,"tags":["x","y"],'
           '"addrs":[{"city":"NYC","zip":10001}],"nick":"bobby"}')
    u, _ = model_validate_json(src, User)
    out = model_dump_json(u)
    assert out.find('"city":"NYC"') >= 0, "dump missing nested city: " + out
    assert out.find('"id":7') >= 0
    u2, errs2 = model_validate_json(out, User)         # round-trips back to an equal model
    assert len(errs2) == 0
    assert u2.id == u.id
    assert u2.addrs[0].zip == u.addrs[0].zip
    assert u2.tags == u.tags
    print("ok -> model_dump_json round-trip")


def test_schema():
    sch = model_json_schema(User)
    assert sch.find('"type":"object"') >= 0
    assert sch.find('"properties"') >= 0
    assert sch.find('"id"') >= 0
    assert sch.find('"integer"') >= 0      # id
    assert sch.find('"number"') >= 0       # age
    assert sch.find('"array"') >= 0        # tags/addrs
    assert sch.find('"city"') >= 0         # nested Address inlined
    assert sch.find('"required"') >= 0     # id/name/... required, nick not
    print("ok -> model_json_schema")


def main():
    test_validate_ok()
    test_lax_coercion()
    test_errors()
    test_nested_error_loc()
    test_dump_roundtrip()
    test_schema()
    print("PASS: L5 validation/serialization/schema")


main()
