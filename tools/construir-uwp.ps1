# Compila, empaqueta y firma Street Fighter EX Plus Alpha Recomp para Xbox (UWP).
#
# Hace las cuatro cosas de un tirón, porque con el generador de Visual Studio es MSBuild quien empaqueta
# y firma al final de la compilación:
#   1. SDL2 estática para WindowsStore (SDL3 no tiene WinRT; 2.30.2 es la probada);
#   2. la versión del paquete en el manifiesto y los mosaicos en UWP\Assets\ (el CMake empaqueta lo que haya ahí);
#   3. configurar el juego con CMAKE_SYSTEM_NAME=WindowsStore, sin lanzador, sin herramientas de depuración y sin Vulkan;
#   4. compilar el destino psx-runtime, que sale empaquetado en .msix y firmado con tu certificado.
#
# Adaptado del UWP\Generate-UWP-VS2019.ps1 del proyecto del juego: aquí el generador es Visual Studio 17 2022,
# la versión del paquete y el certificado los pones tú, y -OverlaysEstaticos mete en el ejecutable los overlays
# compilados (docs/HOW-IT-WORKS.es.md §«El vídeo de la intro»: sin ellos el reproductor corre en el intérprete y el
# vídeo de la presentación baja a 0,77x).
#
# DÓNDE SE ESCRIBE: en PowerShell —tecla Windows, escribe «powershell», Enter—, en una ventana NORMAL: no hace falta
# «ejecutar como administrador», y usarlo además rompería la firma, porque el certificado está en el almacén del
# usuario que ejecuta la orden. Desde la carpeta de este repositorio. PowerShell 7 no hace falta: con la 5.1 que trae
# Windows basta, y por eso los ejemplos llevan -ExecutionPolicy Bypass (un Windows de fábrica no ejecuta un .ps1).
#
#   powershell -ExecutionPolicy Bypass -File tools\construir-uwp.ps1 `
#       -Raiz C:\sfexpa\plusalpha-recomp -Version 1.0.0.0 -Certificado <huella de tu certificado>
#
# La versión SUBE en cada paquete nuevo: la consola no cambia los mosaicos de un paquete que tenga la misma.
#
# Recompilaciones — https://github.com/jajdp/sfexpa-xbox
# PolyForm Noncommercial License 1.0.0
param(
    # La raíz del árbol del juego ya parcheado (tools\apply_uwp.py).
    [Parameter(Mandatory = $true)][string]$Raiz,
    # La versión del paquete, de cuatro números.
    [Parameter(Mandatory = $true)][string]$Version,
    # La huella SHA-1 de tu certificado de firma, en el almacén del usuario (docs/INSTALL.es.md §5).
    [Parameter(Mandatory = $true)][string]$Certificado,
    # Dónde dejar el .msix. Por defecto, <raíz>\paquete-<versión>.
    [string]$Salida = '',
    # Los once mosaicos del paquete. Por defecto, package\Assets de este repositorio, que viene VACÍA:
    # pon los tuyos (docs/ASSETS.es.md). Los del paquete que corre en la consola son arte del juego y no se publican.
    [string]$Mosaicos = '',
    # El código de SDL2 se descarga una vez; por defecto, <raíz>\UWP-Build\_deps.
    [string]$Descargas = '',
    [string]$OverlaysEstaticos = '',
    [string]$Configuracion = 'Release',
    [switch]$SoloSdl,
    [switch]$SoloConfigurar,
    # SDL lleva un parche propio (tools\parche_uwp_reanudar.py anota el estado de la activación): la primera vez
    # después de aplicarlo hay que volver a compilarlo e instalarlo aunque ya exista.
    [switch]$RehacerSdl
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Repo = Split-Path -Parent $PSScriptRoot
if (-not $Salida)    { $Salida    = Join-Path $Raiz "paquete-$Version" }
if (-not $Mosaicos)  { $Mosaicos  = Join-Path $Repo 'package\Assets' }

$Juego       = Join-Path $Raiz 'PlusAlphaProject'
$Build       = Join-Path $Raiz 'UWP-Build'
$Deps        = Join-Path $Build '_deps'
if (-not $Descargas) { $Descargas = $Deps }
$SdlVersion  = '2.30.2'
$SdlZip      = Join-Path $Descargas "SDL-release-$SdlVersion.zip"
$SdlFuente   = Join-Path $Deps "SDL-release-$SdlVersion"
$SdlBuild    = Join-Path $Deps 'sdl2-build'
$SdlInstall  = Join-Path $Deps 'sdl2-install'
$SdlConfig   = Join-Path $SdlInstall 'cmake\SDL2Config.cmake'
$Generador   = 'Visual Studio 17 2022'

foreach ($exigido in @((Join-Path $Juego 'CMakeLists.txt'), (Join-Path $Raiz 'psxrecomp\runtime'))) {
    if (-not (Test-Path -LiteralPath $exigido)) {
        throw "-Raiz no es la raíz de un árbol del juego (falta $exigido). Clónalo con --recurse-submodules; docs/INSTALL.es.md §2."
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $Raiz 'UWP\SDL_winrt_main_NonXAML.cpp'))) {
    throw "el árbol no está parcheado: falta UWP\SDL_winrt_main_NonXAML.cpp. Pasa primero tools\apply_uwp.py (docs/INSTALL.es.md §3)."
}
if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw "-Version tiene que ser de cuatro números, como 1.0.0.0 (es: $Version)" }
# -Certificado es la HUELLA del certificado (40 dígitos hexadecimales), no un archivo .pfx ni una ruta: es lo que
# MSBuild espera en PackageCertificateThumbprint. Se comprueba la forma aquí porque, si no, el error llega al final
# de la compilación entera y dice solo que no pudo firmar.
$Certificado = $Certificado.Trim() -replace '[\s:]', ''
if ($Certificado -notmatch '^[0-9A-Fa-f]{40}$') {
    throw ("-Certificado tiene que ser la huella SHA-1 de tu certificado, 40 dígitos hexadecimales (es: $Certificado). " +
           "La ves con: Get-ChildItem Cert:\CurrentUser\My | Format-List Subject, Thumbprint — docs/INSTALL.es.md §5.")
}

$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath
if (-not $vs) { throw 'no encuentro Visual Studio (vswhere no devolvió nada): docs/INSTALL.es.md §1' }
$cmake = Join-Path $vs 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
if (-not (Test-Path -LiteralPath $cmake)) { $cmake = (Get-Command cmake).Source }
Write-Output "cmake: $cmake"

function CMake([string[]]$Argumentos) {
    Write-Output ("cmake " + ($Argumentos -join ' '))
    & $cmake @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "cmake terminó con el código $LASTEXITCODE" }
}

# 1. SDL2 para WindowsStore, estática (igual que el script del proyecto)
New-Item -ItemType Directory -Path $Descargas, $Deps -Force | Out-Null
if (-not (Test-Path -LiteralPath $SdlZip)) {
    Invoke-WebRequest -Uri "https://github.com/libsdl-org/SDL/archive/refs/tags/release-$SdlVersion.zip" -OutFile $SdlZip
}
Write-Output ("SDL2 zip: {0:N0} B  SHA-256 {1}" -f (Get-Item -LiteralPath $SdlZip).Length, (Get-FileHash -LiteralPath $SdlZip -Algorithm SHA256).Hash)
if (-not (Test-Path -LiteralPath (Join-Path $SdlFuente 'CMakeLists.txt'))) {
    Expand-Archive -LiteralPath $SdlZip -DestinationPath $Deps -Force
}

# El parche de SDL (la mitad de tools\parche_uwp_reanudar.py que vive en su código: SDL es quien recibe la activación
# UWP y por tanto el único que sabe si el sistema está relanzando la app tras terminarla). No se puede aplicar antes,
# porque hasta aquí SDL no estaba descargado; y si escribe algo, hay que volver a compilarlo.
$py = (Get-Command py -ErrorAction Ignore); $python = if ($py) { @('py', '-3') } else { @('python') }
$salidaParche = & $python[0] $python[1..($python.Count - 1)] (Join-Path $PSScriptRoot 'parche_uwp_reanudar.py') $Raiz "--sdl=$SdlFuente" 2>&1
Write-Output ("parche de SDL: " + ($salidaParche -join ' | '))
if ($LASTEXITCODE -ne 0) { throw "parche_uwp_reanudar.py falló: $salidaParche" }
if ($salidaParche -match 'SDL_winrtapp_direct3d') { $RehacerSdl = $true; Write-Output 'SDL cambió: se vuelve a compilar' }

if ($RehacerSdl -or -not (Test-Path -LiteralPath $SdlConfig)) {
    CMake @('-S', $SdlFuente, '-B', $SdlBuild, '-G', $Generador, '-A', 'x64',
            '-DCMAKE_SYSTEM_NAME=WindowsStore', '-DCMAKE_SYSTEM_VERSION=10.0',
            "-DCMAKE_INSTALL_PREFIX=$SdlInstall", '-DSDL_SHARED=OFF', '-DSDL_STATIC=ON', '-DSDL_TEST=OFF')
    CMake @('--build', $SdlBuild, '--config', $Configuracion, '--target', 'install', '--parallel')
}
if (-not (Test-Path -LiteralPath $SdlConfig)) { throw "No se instaló SDL2Config.cmake en $SdlConfig" }
if ($SoloSdl) { return }

# 2. Manifiesto y mosaicos: la versión del paquete y tu arte (el CMake del juego empaqueta todo UWP\Assets\)
$Manifiesto = Join-Path $Raiz 'UWP\Package.appxmanifest'
$m = [IO.File]::ReadAllText($Manifiesto)

# El Publisher del manifiesto tiene que ser el sujeto EXACTO del certificado. Se comprueba aquí, antes de compilar
# nada: si no, el error llega al final de la compilación entera y solo dice que no pudo firmar.
$publisher = ([regex]::Match($m, '<Identity\b[^>]*?\bPublisher="([^"]*)"', 'Singleline')).Groups[1].Value
$cert = Get-ChildItem -LiteralPath "Cert:\CurrentUser\My\$Certificado" -ErrorAction Ignore
if (-not $cert) {
    throw ("no hay ningún certificado con la huella $Certificado en tu almacén personal. " +
           "Los tuyos: Get-ChildItem Cert:\CurrentUser\My | Format-List Subject, Thumbprint — docs/INSTALL.es.md §4.")
}
if ($publisher -match 'CHANGE-ME') {
    throw ("el manifiesto todavía tiene el Publisher de ejemplo ($publisher). Ponle el sujeto de tu certificado, " +
           "que es «$($cert.Subject)» — docs/INSTALL.es.md §5.")
}
if ($publisher -ne $cert.Subject) {
    throw ("el Publisher del manifiesto («$publisher») no es el sujeto del certificado («$($cert.Subject)»). " +
           "Tienen que ser idénticos letra por letra, o MSBuild falla al firmar — docs/INSTALL.es.md §5.")
}
Write-Output "certificado: $($cert.Subject) (coincide con el manifiesto)"
$m2 = [regex]::Replace($m, '(<Identity\b[^>]*?\bVersion=")[^"]+(")', "`${1}$Version`${2}", 'Singleline')
if ($m2 -ne $m) { [IO.File]::WriteAllText($Manifiesto, $m2, (New-Object Text.UTF8Encoding $false)); Write-Output "manifiesto: Version=$Version" }
$png = @()
if (Test-Path -LiteralPath $Mosaicos) {
    $png = @(Get-ChildItem -LiteralPath $Mosaicos -Filter *.png -File)
    if ($png.Count) {
        New-Item -ItemType Directory -Force (Join-Path $Raiz 'UWP\Assets') | Out-Null
        $png | Copy-Item -Destination (Join-Path $Raiz 'UWP\Assets') -Force
        Write-Output ("mosaicos: {0} PNG de {1}" -f $png.Count, $Mosaicos)
    }
}
if (-not $png.Count) {
    throw ("no hay ningún PNG en $Mosaicos. Los once mosaicos del paquete los pones tú: " +
           "docs/ASSETS.es.md dice qué tamaños y con qué nombres. Sin ellos la consola muestra el paquete sin icono.")
}

# 3. Configurar el juego (WindowsStore, sin lanzador, sin herramientas de depuración, sin Vulkan)
$Estaticos = ''
if ($OverlaysEstaticos) {
    if (-not (Test-Path -LiteralPath $OverlaysEstaticos)) { throw "no existe $OverlaysEstaticos" }
    $Estaticos = (Resolve-Path -LiteralPath $OverlaysEstaticos).Path -replace '\\', '/'
    Write-Output "overlays estáticos: $Estaticos"
}
# La rama main del proyecto trae su propio mecanismo de overlays estáticos (PSX_STATIC_OVERLAY_DIR con un sources.cmake);
# la etiqueta v0.2.3-alpha usaba la opción PLUSALPHA_OVERLAY_STATIC_C.
$OpcionOverlays = "-DPLUSALPHA_OVERLAY_STATIC_C=$Estaticos"
if ([IO.File]::ReadAllText((Join-Path $Juego 'CMakeLists.txt')).Contains('PSX_STATIC_OVERLAY_DIR')) {
    $OpcionOverlays = '-DPSX_STATIC_OVERLAY_DIR='
    if ($Estaticos) {
        $dirOv = Split-Path -Parent $OverlaysEstaticos
        [IO.File]::WriteAllText((Join-Path $dirOv 'ov_vacio.c'), "/* sources.cmake: la lista de fuentes extra no puede ir vacía */`n", (New-Object Text.UTF8Encoding $false))
        $sc = @(
            '# Generado por construir-uwp.ps1 (port de Xbox): los overlays estáticos de compile_overlays.py --static.',
            "set(PSX_STATIC_OVERLAY_DISPATCH `"$Estaticos`")",
            "set(PSX_STATIC_OVERLAY_SOURCES `"$(((Join-Path $dirOv 'ov_vacio.c') -replace '\\', '/'))`")",
            '# Con ~63 000 funciones el objeto pasa del límite de secciones de COFF (C1128).',
            'if(MSVC)',
            '    set_source_files_properties("${PSX_STATIC_OVERLAY_DISPATCH}" PROPERTIES COMPILE_OPTIONS "/bigobj")',
            'endif()')
        [IO.File]::WriteAllText((Join-Path $dirOv 'sources.cmake'), (($sc -join "`n") + "`n"), (New-Object Text.UTF8Encoding $false))
        $OpcionOverlays = "-DPSX_STATIC_OVERLAY_DIR=$($dirOv -replace '\\', '/')"
    }
}
Write-Output "opción de overlays: $OpcionOverlays"
CMake @('-S', $Juego, '-B', $Build, '-G', $Generador, '-A', 'x64',
        '-DCMAKE_SYSTEM_NAME=WindowsStore', '-DCMAKE_SYSTEM_VERSION=10.0',
        "-DSDL2_DIR=$(Split-Path -Parent $SdlConfig)",
        '-DPSX_LAUNCHER=OFF', '-DPSX_DEBUG_TOOLS=OFF', '-DPSX_ENABLE_VULKAN=OFF',
        $OpcionOverlays)
if ($SoloConfigurar) { return }

# 4. Compilar y empaquetar, firmado con tu certificado. AppxPackageValidationEnabled=false: la validación del paquete
#    (regla de la Tienda, APPX3207) limita cada imagen a 200 KB y una pantalla de carga en condiciones pesa más; la
#    consola en modo desarrollador no tiene ese límite.
New-Item -ItemType Directory -Path $Salida -Force | Out-Null
CMake @('--build', $Build, '--config', $Configuracion, '--target', 'psx-runtime', '--parallel', '--',
        '/p:AppxBundle=Never', '/p:AppxPackageValidationEnabled=false',
        '/p:AppxPackageSigningEnabled=true', "/p:PackageCertificateThumbprint=$Certificado",
        '/p:GenerateAppInstallerFile=false', "/p:AppxPackageDir=$Salida\")
Get-ChildItem -LiteralPath $Salida -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize | Out-String -Width 300
Write-Output "Ahora: instala el .msix en la consola por el Device Portal y sube tu disco y tu BIOS (docs/INSTALL.es.md §7)."
