# L6.1 — CRC-32 vectors + gzip encoder. Writes sample inputs and their gzip outputs to files; an
# external decompressor (the PowerShell harness) verifies they inflate back to the originals.
from fastcodon.compress import crc32, gzip_compress

def eqx(name: str, got: int, want: int):
    print(name, "->", "ok" if got == want else "FAIL", hex(got))
    assert got == want, name + ": got " + hex(got) + " want " + hex(want)

def write_bin(path: str, content: str):
    f = open(path, "wb")
    f.write(content)
    f.close()

def main():
    # --- CRC-32 known vectors ---
    eqx("crc32('')", int(crc32("")), 0)
    eqx("crc32('123456789')", int(crc32("123456789")), 0xCBF43926)
    eqx("crc32(quick brown fox)",
        int(crc32("The quick brown fox jumps over the lazy dog")), 0x414FA339)

    # --- gzip samples for external round-trip ---
    samples = ["",
               "A",
               "hello world",
               "The quick brown fox jumps over the lazy dog. " * 60,
               "ababababababababababababababcabcabcabc" * 40]
    i = 0
    total_in = 0
    total_out = 0
    for s in samples:
        write_bin("cmp_in_" + str(i) + ".txt", s)
        gz = gzip_compress(s)
        write_bin("cmp_out_" + str(i) + ".gz", gz)
        total_in += len(s)
        total_out += len(gz)
        print("sample", i, "in=", len(s), "gz=", len(gz))
        i += 1

    print("totals in=", total_in, "gz=", total_out)
    print("PASS: crc32 vectors + gzip samples written")

main()
