# Compila los overlays del juego DENTRO del ejecutable: pasa un archivo de capturas por el
# compile_overlays.py --static del framework (parcheado antes con tools\parche_compile_overlays.py) y deja un
# overlays_static.c que luego se le da a construir-uwp.ps1 -OverlaysEstaticos. Sin esto, el código que el juego
# carga del disco corre en el intérprete y en la consola no llega: la presentación baja a 0,77x
# (docs/HOW-IT-WORKS.es.md).
#
# Necesita: el recompilador del framework ya compilado (psxrecomp\recompiler\build\psxrecomp-game.exe) y un
# gcc de MSYS2, que es lo que compile_overlays.py usa para los fragmentos.
#
# Las capturas y el overlays_static.c que salen son CÓDIGO DEL JUEGO leído de tu disco: no se publican.
#
#   powershell -ExecutionPolicy Bypass -File tools\overlays_estaticos.ps1 `
#       -Raiz C:\sfexpa\plusalpha-recomp -Capturas C:\sfexpa\capturas\unidas.json -Salida C:\sfexpa\overlays-v1
#
# Recompilaciones — https://github.com/jajdp/sfexpa-xbox
# PolyForm Noncommercial License 1.0.0
param(
    [Parameter(Mandatory = $true)][string]$Raiz,
    [Parameter(Mandatory = $true)][string]$Capturas,
    [Parameter(Mandatory = $true)][string]$Salida,
    # El gcc con que compile_overlays.py compila los fragmentos.
    [string]$Gcc = 'C:/msys64/mingw64/bin/gcc.exe'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Gcc)) { throw "no existe $Gcc (-Gcc apunta al gcc de MSYS2)" }
$recomp = Join-Path $Raiz 'psxrecomp\recompiler\build\psxrecomp-game.exe'
if (-not (Test-Path -LiteralPath $recomp)) {
    throw "falta el recompilador: $recomp. Compílalo antes (docs/HOW-IT-WORKS.es.md)."
}
$env:PATH = (Split-Path -Parent $Gcc) + ';' + $env:PATH
Set-Location -LiteralPath $Raiz
New-Item -ItemType Directory -Force $Salida | Out-Null
$t0 = Get-Date
& py -3 -X utf8 psxrecomp\tools\compile_overlays.py --static --captures $Capturas `
    --game-toml PlusAlphaProject\game.toml --recompiler $recomp `
    --runtime-include psxrecomp\runtime\include --out-dir $Salida --gcc $Gcc --cps
$codigo = $LASTEXITCODE
"código: $codigo  tiempo: {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds
Get-ChildItem -LiteralPath $Salida -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize | Out-String -Width 250
