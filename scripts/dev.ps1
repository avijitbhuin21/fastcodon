# fastcodon dev helper (Windows). Sets the Codon env, then runs/builds with the right link flags.
#
#   .\scripts\dev.ps1 run   tests\test_socket.py     # JIT
#   .\scripts\dev.ps1 build tests\test_socket.py out.exe
#
# Assumes the native-Windows Codon install + an LLVM clang for AOT linking. Override paths via
# $env:CODON_HOME / $env:LLVM_BIN before calling.

param(
    [Parameter(Mandatory=$true)][ValidateSet("run","build")] [string]$mode,
    [Parameter(Mandatory=$true)] [string]$script,
    [string]$out = "a.exe"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot                       # codon-libraries/
$home = if ($env:CODON_HOME) { $env:CODON_HOME } else { "C:\codon-dev\codon-next-install" }
$llvm = if ($env:LLVM_BIN)   { $env:LLVM_BIN }   else { "C:\Program Files\LLVM\bin" }

$libdir = Join-Path $home "lib\codon"
# Codon DLLs and bin first; clang LAST so it cannot shadow Codon's own LLVM DLLs (0xC0000139).
$env:PATH = "$libdir;$home\bin;$env:PATH;$llvm"
$env:CODON_PATH = $repo                                        # makes `import fastcodon...` resolve
$codon = Join-Path $home "bin\codon.exe"

# ws2_32 = Winsock (sockets/selector). Add others (ssl/crypto) here as TLS lands.
$libs = @("-l", "ws2_32")

if ($mode -eq "run") {
    & $codon run @libs $script
} else {
    & $codon build @libs -o $out $script
    if (Test-Path $out) { Write-Host "built: $out" }
}
exit $LASTEXITCODE
