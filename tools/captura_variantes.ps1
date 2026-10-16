# Corre una copia de prueba del juego en el PC (con overlay_cache = true en su game.toml) y guarda CADA versión que
# el runtime escribe de overlay_captures.json. Hace falta porque el runtime la REESCRIBE en cada disparo de la captura
# automática y solo conserva la última foto de la RAM: el reproductor de vídeo está en memoria mientras dura la
# presentación, y en las fotos posteriores esas direcciones ya tienen datos. Copiando cada versión quedan las variantes
# de la presentación, del título y de la demostración, que es lo que luego une capturas_variantes.py --unir.
#
# Las capturas son CÓDIGO DEL JUEGO leído de tu disco: quedan en tu -Salida y no se publican (docs/ASSETS.es.md).
#
# DÓNDE SE ESCRIBE: en PowerShell, en una ventana normal (no hace falta administrador), desde la carpeta de este
# repositorio. Con la PowerShell 5.1 que trae Windows basta.
#
#   powershell -ExecutionPolicy Bypass -File tools\captura_variantes.ps1 `
#       -Juego C:\sfexpa\prueba -Salida C:\sfexpa\capturas -Segundos 150
#
# Recompilaciones — https://github.com/jajdp/sfexpa-xbox
# PolyForm Noncommercial License 1.0.0
param(
    # La carpeta de la copia de prueba: el .exe del PC, su game.toml con overlay_cache = true, el disco y la BIOS.
    [Parameter(Mandatory = $true)][string]$Juego,
    # Donde dejar las copias. Por defecto, <juego>\capturas.
    [string]$Salida = '',
    # 150 s alcanzan para la presentación, el título y una vuelta de la demostración.
    [int]$Segundos = 150,
    # El nombre del ejecutable de la copia de prueba, si lo tienes con otro.
    [string]$Exe = 'StreetFighterEXPlusAlphaRecomp.exe'
)
$ErrorActionPreference = 'Stop'
$dst = (Resolve-Path -LiteralPath $Juego).Path
if (-not $Salida) { $Salida = Join-Path $dst 'capturas' }
$caps = $Salida
$exe = Join-Path $dst $Exe
if (-not (Test-Path -LiteralPath $exe)) { throw "no existe $exe (-Juego es la carpeta de la copia de prueba del PC)" }
$gt = Join-Path $dst 'game.toml'
if (-not (Test-Path -LiteralPath $gt)) { throw "no existe $gt" }
if (([IO.File]::ReadAllText($gt) -notmatch '(?m)^\s*overlay_cache\s*=\s*true')) {
    throw "el game.toml de $dst no tiene overlay_cache = true: sin eso el runtime no escribe ninguna captura"
}
New-Item -ItemType Directory -Force $caps | Out-Null
$json = Join-Path $dst 'overlay_captures.json'
if (Test-Path -LiteralPath $json) {
    $viejo = Join-Path $caps ('previa-' + (Get-Item -LiteralPath $json).LastWriteTime.ToString('yyyyMMdd-HHmmss') + '.json')
    Move-Item -LiteralPath $json -Destination $viejo
    "apartada la captura anterior: $viejo"
}
$p = Start-Process -FilePath $exe -ArgumentList '--no-launcher', '--game', $gt -WorkingDirectory $dst -PassThru -RedirectStandardError (Join-Path $dst 'stderr.txt') -RedirectStandardOutput (Join-Path $dst 'stdout.txt')
$t0 = Get-Date
$ultima = $null
$n = 0
while (((Get-Date) - $t0).TotalSeconds -lt $Segundos) {
    Start-Sleep -Milliseconds 500
    $p.Refresh(); if ($p.HasExited) { "terminó solo: $($p.ExitCode)"; break }
    if (-not (Test-Path -LiteralPath $json)) { continue }
    $fi = Get-Item -LiteralPath $json
    $firma = "$($fi.Length)|$($fi.LastWriteTimeUtc.Ticks)"
    if ($firma -eq $ultima) { continue }
    # El runtime la escribe desde un hilo: esperar a que deje de crecer y que cierre con ']'
    Start-Sleep -Milliseconds 700
    $fi = Get-Item -LiteralPath $json
    $firma = "$($fi.Length)|$($fi.LastWriteTimeUtc.Ticks)"
    try { $txt = [IO.File]::ReadAllText($json) } catch { continue }
    if (-not $txt.TrimEnd().EndsWith(']')) { continue }
    $ultima = $firma
    $n++
    $seg = [int]((Get-Date) - $t0).TotalSeconds
    $copia = Join-Path $caps ('{0:D3}s-overlay_captures.json' -f $seg)
    [IO.File]::WriteAllText($copia, $txt, (New-Object Text.UTF8Encoding $false))
    "{0,4} s: copia {1} ({2:N0} B)" -f $seg, (Split-Path -Leaf $copia), $txt.Length
}
$p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id }
"copias: $n"
Get-ChildItem -LiteralPath $caps -File | Select-Object Name, Length | Format-Table -AutoSize | Out-String
