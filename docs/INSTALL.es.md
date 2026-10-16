# Construir el port y meterlo en la consola

*(English: [INSTALL.md](INSTALL.md))*

Once pasos. Del 1 al 5 se hacen una sola vez; a partir del 7, rehacer el paquete son dos órdenes.

## 0. Antes de empezar: dónde se escriben las órdenes

Esta guía está llena de bloques como este. **Todos son órdenes que tecleas tú** en una ventana de
terminal, y cada uno dice arriba desde dónde. Si nunca has usado una, aquí está todo lo que hace
falta saber; si ya sabes, sáltate esta sección.

### La terminal: PowerShell

Todo lo de esta guía va en **PowerShell**, la terminal normal de Windows:

1. Pulsa la tecla **Windows**.
2. Escribe `powershell`.
3. Pulsa **Enter** sobre *Windows PowerShell*.

Se abre una ventana con una línea que acaba en `>`. Ahí escribes la orden y pulsas **Enter**.

**Moverte a una carpeta.** Casi todas las órdenes se escriben *desde una carpeta concreta*,
normalmente la de este repositorio. Para ir a ella se usa `cd` y la ruta, entre comillas si tiene
espacios:

```powershell
cd "C:\Users\tu-usuario\Downloads\sfexpa-xbox"
```

**Un atajo que ahorra errores:** abre la carpeta en el Explorador de archivos, haz clic en la barra
de direcciones, escribe `powershell` encima de lo que ponga y pulsa **Enter**. Se abre PowerShell ya
situado ahí.

⚠ Algunas órdenes son largas y se parten en varias líneas con una **comilla invertida** (`` ` ``) al
final de cada una. Cópialas enteras, con esas comillas: son las que dicen «sigue en la línea de
abajo».

### No hace falta administrador — y es mejor no usarlo

Nada de esta guía necesita «ejecutar como administrador». Todo se construyó y se probó con una
cuenta normal.

> ⚠ Y en un paso concreto, ser administrador lo **estropea**: el certificado del §4 se crea en el
> almacén del usuario que ejecuta la orden. Si lo creas en una ventana elevada, acaba en el almacén
> del administrador, y al firmar —que harás como tú— MSBuild no lo encuentra y la compilación entera
> falla en el último paso.
>
> Lo único que pide administrador es el **instalador** de Visual Studio, que lo pide él solo.

### Por qué las órdenes de PowerShell llevan `-ExecutionPolicy Bypass`

Un Windows recién instalado **no ejecuta archivos `.ps1`**: su política está en `Restricted` y
responde algo como «no se puede cargar porque la ejecución de scripts está deshabilitada». El
`-ExecutionPolicy Bypass` de los ejemplos levanta esa restricción **solo para esa orden**, sin
cambiar nada en tu sistema.

**PowerShell 7 (`pwsh`) no hace falta** para nada de aquí. Con la que trae Windows basta.

### Cómo saber si una orden funcionó

Las de esta guía terminan diciendo qué hicieron, y si algo va mal lo dicen también. Una orden que no
imprime nada suele haber funcionado; para confirmarlo, esto responde `True` cuando la anterior
terminó bien:

```powershell
$?
```

---

## 1. Lo que hace falta antes

| | Para qué |
|---|---|
| **Visual Studio 2022** con las herramientas de C++ **y el componente de UWP para C++** | Compilar, empaquetar y firmar. Aquí es MSBuild quien hace el paquete, así que el componente de UWP hace falta de verdad |
| **Python 3** | Los parches. Nada más que la biblioteca estándar |
| **Git** | Clonar el proyecto del juego con sus submódulos |
| **Tu disco y tu BIOS** | Un volcado NTSC-U de `SLUS-00548` (`.bin` + `.cue`) y una **BIOS SCPH-1001 de consola**. Este juego no arranca sin ella |
| **Una Xbox Series en modo desarrollador** | Instalar el paquete |
| *Solo para los overlays (§10)* | **MSYS2** con `gcc`, y el recompilador del propio framework compilado una vez |

### Qué Visual Studio

El generador está fijado en una línea de `tools/construir-uwp.ps1`:

```powershell
$Generador = 'Visual Studio 17 2022'
```

Con otra versión de Visual Studio hay que cambiar esa línea. La ruta de `cmake.exe` sí se busca
sola, con `vswhere -latest`, y si no la encuentra usa el `cmake` del PATH.

> ⚠ **Más nueva no es automáticamente mejor aquí.** Microsoft lleva años reduciendo el soporte de
> UWP, y este port se apoya en las extensiones de C++/CX y en el objetivo WindowsStore de MSBuild.
> Si una versión futura deja caer cualquiera de las dos, esta receta no funciona en ella por muy
> nueva que sea.

SDL2 no hay que instalarlo: `tools/construir-uwp.ps1` descarga el código de la 2.30.2 y lo compila
para WindowsStore la primera vez. **SDL3 no sirve**: no tiene backend de WinRT.

---

## 2. El proyecto del juego

Este repositorio no trae el juego: trae lo que hay que hacerle. Clona el proyecto **con sus
submódulos** (el framework es uno de ellos):

> **Dónde se escribe:** en **PowerShell** —pulsa la tecla **Windows**, escribe `powershell` y
> pulsa **Enter**—, en una ventana **normal**: no hace falta «ejecutar como administrador»,
> desde la carpeta donde quieras el árbol.

```powershell
git clone --recurse-submodules https://github.com/guimaraf/plusalpha-recomp.git C:\sfexpa\plusalpha-recomp
```

Son unos 200 MB: el C del ejecutable del juego viene generado dentro del repositorio.

⚠ **Compílalo y pruébalo en tu PC primero**, siguiendo las instrucciones del propio proyecto. Si no
corre en el PC, no va a correr en la consola, y aquí tendrías dos problemas a la vez en vez de uno.

**Sobre la versión.** Esta receta se escribió y se probó contra la rama `main` del proyecto, commit
`9e87fa7` (framework `eec0c31`). Los parches comprueban lo que esperan encontrar antes de escribir,
así que si el proyecto cambia por debajo, el que no cuadre se detiene y lo dice en vez de estropear
el árbol. La rama `main` es a propósito: su C del ejecutable cubre el **79,2 %** del juego, mientras
el de la última versión publicada cubre el 58 %, y en esa diferencia está el escenario de Sakura
yendo a velocidad normal ([`HOW-IT-WORKS.es.md`](HOW-IT-WORKS.es.md)).

---

## 3. Aplicar el port

> **Dónde se escribe:** en **PowerShell** —pulsa la tecla **Windows**, escribe `powershell` y
> pulsa **Enter**—, en una ventana **normal**: no hace falta «ejecutar como administrador»,
> desde la carpeta de este repositorio.

```powershell
python tools\apply_uwp.py C:\sfexpa\plusalpha-recomp
```

Va diciendo qué hace cada paso. Lo que verás es una línea por parche, y al final cuántos
escribieron algo.

Tres cosas que conviene saber:

- **Es idempotente.** Pasarlo dos veces no cambia nada: cada parche deja su firma dentro del
  archivo y, si la encuentra, se salta.
- **Es todo o nada, parche a parche.** Cada ancla tiene que aparecer exactamente una vez. Si una no
  cuadra, ese parche no escribe *nada* y el proceso se detiene ahí diciendo cuál y cuántas veces la
  encontró. Los parches anteriores se quedan puestos, y volver a pasarlo después de arreglarlo
  continúa donde estaba.
- **No borra nada.** Los dos parches que necesitan el original lo dejan al lado, como
  `<archivo>.original`.

Para ver los pasos sin tocar nada:

```powershell
python tools\apply_uwp.py --list
```

---

## 4. Un certificado para firmar

El modo desarrollador acepta paquetes autofirmados. Crea uno y **apunta su sujeto y su huella**: el
`Publisher` del manifiesto tiene que coincidir con el sujeto letra por letra.

⚠ Aquí importa de verdad lo de **no** abrir la ventana «como administrador»: el certificado se
crea en el almacén del usuario que ejecuta la orden, así que elevado acabaría en el del
administrador y después MSBuild, corriendo como tú, no lo encontraría.

> **Dónde se escribe:** en **PowerShell** —pulsa la tecla **Windows**, escribe `powershell` y
> pulsa **Enter**—, en una ventana **normal**: no hace falta «ejecutar como administrador»,
> desde cualquier carpeta.

```powershell
$c = New-SelfSignedCertificate -Type Custom -Subject "CN=TuNombre" `
       -KeyUsage DigitalSignature -FriendlyName "Firma UWP" `
       -CertStoreLocation "Cert:\CurrentUser\My" `
       -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
$c.Thumbprint     # esto es lo que se pasa en -Certificado
```

Si lo pierdes, los que ya tienes se listan así:

```powershell
Get-ChildItem Cert:\CurrentUser\My | Format-List Subject, Thumbprint
```

---

## 5. El manifiesto: tu identidad

`apply_uwp.py` copió `package/Package.appxmanifest` al árbol la primera vez. **Edítalo** —el del
repositorio, para no perderlo al volver a pasar el script— y cambia:

```xml
<Identity Name="TU-NOMBRE-DE-PAQUETE"
          Publisher="CN=TuNombre"
          Version="1.0.0.0" />
<mp:PhoneIdentity PhoneProductId="un GUID tuyo" ... />
...
<PublisherDisplayName>TuNombre</PublisherDisplayName>
```

- **`Publisher` tiene que ser el sujeto exacto de tu certificado** (§4). Si no lo es, la
  compilación llega hasta el final y falla al firmar.
- Un GUID nuevo lo da `[guid]::NewGuid()` en PowerShell.
- La `Version` la pone `construir-uwp.ps1` con su `-Version`; no hace falta tocarla aquí.

Después, vuelve a pasar `apply_uwp.py` para llevarlo al árbol. El script **no pisa** un manifiesto
que ya tenga su marca, así que tus cambios en el árbol sobreviven; el que manda es el del
repositorio si borras el del árbol.

---

## 6. Los mosaicos del paquete

`package/Assets/` viene **vacía a propósito**: los mosaicos del port real son arte del juego.
[`ASSETS.es.md`](ASSETS.es.md) dice los once nombres y medidas, y trae una orden que los genera
lisos en un momento. Sin ningún PNG ahí, el paso siguiente se detiene y te lo dice.

---

## 7. Compilar, empaquetar y firmar

> **Dónde se escribe:** en **PowerShell** —pulsa la tecla **Windows**, escribe `powershell` y
> pulsa **Enter**—, en una ventana **normal**: no hace falta «ejecutar como administrador»,
> desde la carpeta de este repositorio.

```powershell
powershell -ExecutionPolicy Bypass -File tools\construir-uwp.ps1 `
    -Raiz C:\sfexpa\plusalpha-recomp -Version 1.0.0.0 -Certificado <tu huella>
```

Hace cuatro cosas seguidas: compila SDL2 para WindowsStore (la primera vez; unos minutos), pone la
versión en el manifiesto y copia tus mosaicos, configura el juego para `WindowsStore` sin lanzador,
sin herramientas de depuración y sin Vulkan, y compila el destino `psx-runtime`, que MSBuild
empaqueta y firma.

Sale, en `<raíz>\paquete-<versión>\`:

- `psx-runtime_<versión>_x64.msix` — el paquete,
- `psx-runtime_<versión>_x64.cer` — la parte pública de tu certificado,
- `Dependencies\x64\Microsoft.VCLibs.x64.14.00.appx` — la dependencia del §8.1, que MSBuild pone ahí
  por ti.

**El disco y la BIOS no van dentro**: van a la consola aparte, en el §9.

⚠ **La versión sube en cada paquete nuevo.** La consola no cambia los mosaicos, ni el contenido, de
un paquete que tenga la misma versión que el instalado.

Con los overlays del §10, se le añade `-OverlaysEstaticos <ruta a overlays_static.c>`.

---

## 8. Instalarlo en la consola

### Antes de tocar nada: cómo tiene que estar la consola

- **En modo desarrollador**, con Dev Home instalado. Si no lo está, eso es un trámite aparte con
  Microsoft y no lo cubre esta guía.
- **Encendida y con tu perfil iniciado.** ⚠ Sin un usuario conectado, la consola **no abre
  aplicaciones**: el paquete se instala, aparece en la lista y al lanzarlo no pasa nada. Es de las
  cosas que más tiempo cuestan averiguar.
- **En la misma red que tu PC.**
- **Su dirección**, que te la dice **Dev Home** en la propia consola. El Device Portal escucha en
  el puerto **11443** por HTTPS.
- **Usuario y contraseña del portal**: los que definiste en **Dev Home → Remote Access Settings**
  al activar el acceso remoto.

### 8.1 La dependencia: VCLibs

El ejecutable usa el CRT del App Container —`msvcp140_app.dll`, `vcruntime140_app.dll`,
`vccorlib140_app.dll`—, que no va dentro del paquete sino en un **paquete de marco** que hay que
instalar **una vez por consola**.

No hay que ir a buscarlo: MSBuild lo deja en `<salida>\Dependencies\x64\Microsoft.VCLibs.x64.14.00.appx`
al empaquetar (§7). Los paquetes siguientes, y las versiones siguientes de este, ya lo encuentran
instalado.

### 8.2 Subirlo

Abre `https://<ip-de-la-consola>:11443` en el navegador de tu PC.

⚠ El navegador avisará de que **el certificado del sitio no es de confianza**. Es normal y no es
un problema: ese certificado es de la propia consola, que se lo hace ella. Entra de todas formas
— en Edge y en Chrome, **Avanzado** → **Continuar a … (no seguro)**; en Firefox, **Avanzado** →
**Aceptar el riesgo y continuar**. Después te pedirá el usuario y la contraseña del portal
(los que definiste en Dev Home).

Ya dentro, en **My games & apps → Add**:

1. **App package** → tu `.msix`.
2. **Certificate** → no hace falta: el paquete va firmado y el modo desarrollador lo acepta.
3. **Optional packages / Dependency** → aquí es donde se añade
   `Microsoft.VCLibs.x64.14.00.appx`, la primera vez.
4. **Next → Install**, y esperar al *Package successfully registered*.

> **La consola no te va a pedir el certificado con el que firmaste.** En modo desarrollador
> instala cualquier paquete que venga firmado, sin necesidad de conocer a quien firma: la pantalla
> **Add** ni siquiera tiene casilla para él. El certificado hizo falta en tu PC, para firmar
> (§4), y ahí se acaba su papel.
>
> Si alguna vez el portal rechazara la firma, lo que hay que registrar en la consola es la **parte
> pública** de tu certificado —el `.cer` que sale junto al paquete, o sacado de él así—:
>
> ```powershell
> (Get-AuthenticodeSignature -LiteralPath "<tu .msix>").SignerCertificate |
>     Export-Certificate -FilePath "$env:USERPROFILE\Desktop\firma.cer"
> ```

### 8.3 Si sale `There is not enough space on the disk`

No es que la consola esté llena, y el mensaje engaña. **La primera instalación de una familia de
paquetes va a `D:\DevelopmentFiles`**, una partición de unos 5 GB que el modo desarrollador guarda
justo para eso; las *actualizaciones* de una familia ya registrada van a otro almacenamiento. Esa
partición se llena con la primera versión de todo lo que hayas instalado alguna vez, y
**desinstalar un juego no la vacía**.

La salida es conseguir que tu paquete entre como **actualización** y no como primera instalación,
con una *semilla*: un paquete con la **misma identidad** —mismo `Identity Name` y mismo
`Publisher`— pero con una **versión más baja** y un ejecutable mínimo dentro, que no tiene que
arrancar nunca. Se instala esa primero (con la dependencia de VCLibs) y después el de verdad, que
el portal toma como actualización.

### 8.4 El primer arranque

El primer arranque **sin datos no hace nada visible**: crea las carpetas de `LocalState` y se
cierra. En el registro queda `CREATE_FOLDERS_SUCCESS`. No es un fallo: es lo que tiene que pasar
antes de que puedas subir el disco. Súbelos (§9) y vuelve a abrirlo.

---

## 9. El disco, la BIOS y la configuración

Viven en la carpeta de datos de la propia aplicación, la que creó ese primer arranque:

```text
…\Packages\<identidad>\LocalState\PSXRecomp\SLUS-00548\
    bios\    disc\    config\    saves\    logs\
```

Se sube todo por el **File explorer** del Device Portal, dentro del `LocalState` de esta
aplicación:

| Qué | Dónde | Cómo |
|---|---|---|
| La **BIOS** | `bios\` | `SCPH1001.BIN` tal cual |
| El **disco** | `disc\` | El `.bin` **partido** y el `.cue` renombrado a `game.cue` |
| La **configuración** | `config\` | `settings.toml` y `game.toml` |

### El disco, partido

El portal responde **500** al subir los 528 MB del `.bin` de una vez: las subidas pasan por
`D:\DevelopmentFiles`, que es pequeño. Se parte en trozos de 150 MiB y la entrada del port los une
una sola vez, en el siguiente arranque, dejando constancia en `logs\partes.txt`:

> **Dónde se escribe:** en **PowerShell**, en una ventana normal, desde la carpeta de este
> repositorio.

```powershell
python tools\partir_disco.py "C:\ruta\a\tu\disco.bin" C:\sfexpa\partes
```

Sube los `disco.bin.parte1`, `.parte2`… a `disc\`.

⚠ **El `.cue` tiene que llamarse `game.cue`** en `disc\`, y dentro, su línea `FILE` tiene que
nombrar el `.bin` con su nombre original —el del archivo que partiste, sin el `.parteN`—. Para un
volcado de una sola pista queda así:

```text
FILE "Street Fighter EX Plus Alpha (USA).bin" BINARY
  TRACK 01 MODE2/2352
    INDEX 01 00:00:00
```

### Los ajustes

El proyecto ya trae un `settings.toml` pensado para la consola (renderizador por software, pantalla
completa, sin lanzador, los dos mandos en `auto` y modo digital). Lo que hay que añadirle para tener
lo que este port da:

| Archivo | Sección | Clave | Para qué |
|---|---|---|---|
| `settings.toml` | `[video]` | `aspect_ratio = "16:9"` | La pantalla ancha. La consola no trae la clave: se añade |
| `settings.toml` | `[video]` | `show_fps = true` | El contador de FPS de fábrica (**R3** lo apaga y enciende) |
| `settings.toml` | `[audio]` | `spu_hq = true` | El SPU interpola en cúbico en vez de coger la muestra más cercana |
| `game.toml` | `[widescreen]` | `gte_game_mode = true` | Reconoce las peleas como 3D por la actividad de la GTE. Sin esto, todo sale en 4:3 con franjas |
| `game.toml` | `[widescreen]` | `nw_phase_backdrop = true` | Estira el fondo 2D para que no queden franjas a los lados |
| `game.toml` | `[runtime]` | `overlay_cache = false` | En la consola no sirve de nada y escribe capturas en cada arranque. En el PC, al contrario, es lo que hace falta para el §10 |

En cada arranque la entrada del port **siembra** el `game.toml` desde dentro del paquete y deja en
paz el `settings.toml` si ya existe: ese es tuyo.

Lee `logs\debug_log.txt`. En una consola es lo único que tienes, y es donde sale la línea `[FPS]`
con la velocidad real.

---

## 10. Los overlays: la presentación a velocidad normal

Esto es opcional y lleva su tiempo, pero es la diferencia entre que la presentación de Capcom vaya a
**0,77x** y que vaya a **1,00x**, y entre que algunos escenarios se arrastren y que no.

El por qué está en [`HOW-IT-WORKS.es.md`](HOW-IT-WORKS.es.md); lo que hay que hacer es:

1. **Capturar en el PC.** Una copia de prueba del juego en el PC, con `overlay_cache = true` en su
   `game.toml`, escribe `overlay_captures.json`. El runtime la **reescribe** en cada disparo y solo
   conserva la última foto de la RAM, así que hay que copiar cada versión mientras corre:

   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\captura_variantes.ps1 `
       -Juego C:\sfexpa\prueba -Salida C:\sfexpa\capturas -Segundos 150
   ```

2. **Unirlas**, una entrada por variante:

   ```powershell
   python tools\capturas_variantes.py C:\sfexpa\capturas --unir C:\sfexpa\capturas\unidas.json
   ```

3. **Compilarlas**, con el recompilador del framework ya construido y un `gcc` de MSYS2:

   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\overlays_estaticos.ps1 `
       -Raiz C:\sfexpa\plusalpha-recomp -Capturas C:\sfexpa\capturas\unidas.json -Salida C:\sfexpa\overlays-v1
   ```

4. **Compilar el paquete con ellos**, añadiendo al §7:

   ```powershell
   -OverlaysEstaticos C:\sfexpa\overlays-v1\overlays_static.c
   ```

Las capturas del PC solo ven la presentación, el título y la demostración. El código de las peleas y
de cada escenario solo aparece **jugando**, y para eso hay que instalar una versión con
`overlay_cache = true`, jugar, bajar las capturas numeradas de `logs\` con el **File explorer** del
Device Portal y reducirlas con `tools/capturas_consola.py`, que se queda con una por configuración
de código. Con eso, el paso 3 otra vez.

⚠ Las capturas y el `overlays_static.c` que sale de ellas son **código del juego leído de tu
disco**. No se publican, y el `.gitignore` de este repositorio los bloquea por nombre.

---

## 11. Quitarlo de la consola

⚠ **Se van tus partidas.** Viven dentro del paquete, en su `LocalState`, y desaparecen con él. Si
quieres conservarlas, bájalas antes desde el **File explorer** del Device Portal: están en
`LocalState\PSXRecomp\SLUS-00548\saves`.

Para desinstalar, en el Device Portal: **My games & apps**, busca el juego en la lista, y
**Remove**. Nada de tu PC se toca: el `.msix`, el proyecto, tu disco y tu BIOS siguen donde
estaban.

Reinstalar después empieza de cero, con las partidas en blanco. Si lo que quieres es **actualizar**
sin perderlas, no desinstales: instala encima un paquete con una **versión mayor** —el `-Version`
que le pasas a `construir-uwp.ps1` (§7)—. La misma versión no reemplaza nada.

---

## Si algo no sale bien

| Síntoma | Causa |
|---|---|
| El paquete instala y al abrirlo no pasa nada | Lo primero: ¿hay un **perfil iniciado** en la consola? Sin usuario conectado no abre aplicaciones. Lo segundo: el **primer arranque sin datos** solo crea las carpetas y se cierra (§8.4) |
| `There is not enough space on the disk` | No está llena: es `D:\DevelopmentFiles` (§8.3) |
| Dice que falta una dependencia | Falta el VCLibs del §8.1, que se añade en la pantalla **Add** la primera vez |
| Falla al firmar, al final de la compilación | El `Publisher` del manifiesto no es el sujeto exacto de tu certificado (§5), o el certificado se creó en una ventana de administrador (§0) |
| La presentación va lenta, o un escenario se arrastra | Faltan los overlays (§10). Es lo que más rendimiento da en este port |
| `C1128` al compilar | El objeto de los overlays pasa del límite de secciones de COFF: necesita `/bigobj`, que `construir-uwp.ps1` pone en el `sources.cmake` que escribe. Si compilas a mano, te falta esa opción |
| No hay mando | El `settings.toml` tiene que tener los dos mandos en `auto`; el del proyecto ya viene así. Cuando funciona, el registro dice `opened controller` |
| El juego empieza de cero al volver de Home | Es lo normal sin `parche_reanudar.py` y `parche_uwp_reanudar.py`: el modo desarrollador termina un juego suspendido. Con ellos, la máquina se guarda al pasar a segundo plano y se restaura al relanzar |
| Las peleas no llegan a 60 FPS en 16:9 | `parche_raster_hilo.py` es el que recupera eso, y es el último del `apply_uwp.py`: comprueba que entró |
| El 16:9 sale con franjas | Falta el bloque `[widescreen]` del `game.toml` (§9) |
| La música suena con siseo | Falta `parche_xa_zigzag.py`, o `spu_hq = true` en `[audio]` (§9) |
