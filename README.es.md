# Street Fighter EX Plus Alpha en la Xbox — el port UWP

Cómo coger la recompilación estática de *Street Fighter EX Plus α* (PlayStation, 1997, `SLUS-00548`) que
hace [plusalpha-recomp](https://github.com/guimaraf/plusalpha-recomp) y hacerla correr **en una Xbox Series
en modo desarrollador**, como un paquete UWP que compilas y firmas tú.

*(English: [README.md](README.md))*

No es una teoría: el juego arranca, pasa la presentación de Capcom a velocidad normal, llega al título y se
juega con mando, en 16:9, a **60 FPS**, con un contador de FPS en pantalla, y vuelve donde lo dejaste
después de que la consola lo cierre.

## Qué es este repositorio

**Una receta y las herramientas que la aplican.** El proyecto del juego ya trae un perfil UWP —su autor lo
escribió y nunca publicó el paquete—, así que esto no es un port desde cero: es todo lo que a ese perfil le
faltaba para ser un juego que se pueda jugar en una consola. Trece parches con anclas, una entrada WinRT y
el script que compila. Todo esto se aplica **a tu propia copia** del proyecto del juego, en tu máquina.

## Qué **no** es

Aquí no hay **código del juego, ni imagen del disco, ni BIOS, ni ejecutable compilado, ni paquete `.msix`,
ni arte**. Esto no produce un juego jugable por sí solo, y nada de lo que puedas descargar aquí es un juego.
Necesitas tu propia copia volcada legalmente del disco, una BIOS de consola y el proyecto del juego
compilando antes de empezar. Está detallado en [`NOTICE.es.md`](NOTICE.es.md).

Los mosaicos del paquete **tampoco** están: los de la consola de verdad se hicieron con el arte del propio
juego, que es de Capcom. Los tuyos los pones tú —[`docs/ASSETS.es.md`](docs/ASSETS.es.md) dice los tamaños
exactos, y el script de compilación se detiene con un mensaje claro si la carpeta está vacía.

Ni los **overlays compilados**. Son la pieza que más pesa en el rendimiento de este port, y son *código del
juego leído de tu disco*: las herramientas que los producen están aquí; el resultado, nunca.

## Qué hace falta antes

| | |
|---|---|
| El proyecto del juego | [guimaraf/plusalpha-recomp](https://github.com/guimaraf/plusalpha-recomp), sobre su fork de [psxrecomp](https://github.com/guimaraf/psxrecomp-plusalpha), clonado con `--recurse-submodules` y **compilando y corriendo en tu PC primero** |
| Tu propio disco | Un volcado NTSC-U de `SLUS-00548`, más una **BIOS SCPH-1001 de consola**: este juego no arranca sin ella |
| Visual Studio | 2022, con las herramientas de C++ **y el componente de UWP para C++**: aquí es MSBuild quien empaqueta y firma, así que la carga de trabajo UWP hace falta de verdad. El generador está fijado como `Visual Studio 17 2022` en una línea de [`tools/construir-uwp.ps1`](tools/construir-uwp.ps1) |
| PowerShell | La que Windows ya trae: **PowerShell 7 no hace falta**. Las órdenes llevan `-ExecutionPolicy Bypass` porque un Windows de fábrica no ejecuta un `.ps1` sin eso |
| Python 3 | Para los parches. Nada más que la biblioteca estándar |
| Una Xbox en modo desarrollador | Y un certificado con el que firmar: uno autofirmado sirve ([`docs/INSTALL.es.md`](docs/INSTALL.es.md) §5) |
| Solo para los overlays | MSYS2 con `gcc`, y el recompilador del propio framework compilado una vez ([`docs/HOW-IT-WORKS.es.md`](docs/HOW-IT-WORKS.es.md)) |

SDL2 2.30.2 se descarga y se compila sola: SDL3 no tiene backend de WinRT, así que la 2.30.2 es con la que
esto funciona.

## Cómo va

Dos órdenes. La §0 de [`docs/INSTALL.es.md`](docs/INSTALL.es.md) explica la terminal con más calma, y el
resto de esa guía es la versión larga de estas dos líneas.

> **Dónde se escribe esto:** en **PowerShell** —pulsa la tecla **Windows**, escribe `powershell` y
> pulsa **Enter**—, en una ventana **normal**: no hace falta «ejecutar como administrador», y usarlo
> además rompería el paso de la firma, porque el certificado vive en el almacén del usuario que
> ejecuta la orden. Desde la carpeta de este repositorio.

```powershell
# 1. parchear tu copia del proyecto del juego (idempotente, atómico, no borra nada)
python tools\apply_uwp.py <ruta de la raíz del proyecto del juego>

# 2. compilar, empaquetar y firmar (tus mosaicos, tu certificado)
powershell -ExecutionPolicy Bypass -File tools\construir-uwp.ps1 `
    -Raiz <ruta del proyecto> -Version 1.0.0.0 -Certificado <la huella de tu certificado>
```

`python tools\apply_uwp.py --list` imprime los trece pasos y qué resuelve cada uno.

Después, instalar el `.msix` por el Device Portal, subir tu disco y tu BIOS al `LocalState` de la aplicación
y —si quieres la presentación de Capcom a velocidad normal— compilar los overlays. Paso a paso, con el lado
de la consola: **[`docs/INSTALL.es.md`](docs/INSTALL.es.md)**.

## Qué hubo que resolver

Cada una de estas cosas fue un fallo real en la consola, y casi todas tapaban la siguiente. El detalle, con
lo que decía el registro en cada caso y lo que se midió, está en
**[`docs/HOW-IT-WORKS.es.md`](docs/HOW-IT-WORKS.es.md)**.

| | Síntoma | Arreglo |
|---|---|---|
| 1 | El disco no subía: HTTP 500 | Las subidas pasan por `D:\DevelopmentFiles`, que es pequeño y suele estar lleno. El disco se parte en trozos de 150 MiB y la entrada los une en el primer arranque |
| 2 | La **B** cerraba el juego | En una Xbox, B es también «atrás», y SDL se lo entrega al sistema si no le pides que no |
| 3 | El vídeo de la presentación iba a 0,77x | El reproductor de vídeo no está en el ejecutable del juego: se carga del disco al vuelo, y un overlay interpretado no llega en este procesador. Se compila **dentro** del paquete; en tres intentos, porque la captura solo guarda la última foto y el generador elegía mal los bytes de las entradas huérfanas |
| 4 | El escenario de Sakura, y el de C. Jack, se arrastraban | La versión publicada compila el 58 % del ejecutable del juego; la rama `main` del proyecto compila el 79,2 %, y lo que esos escenarios interpretaban está en la diferencia |
| 5 | Se cerraba en las pantallas de carga | La validación de los overlays estáticos cacheaba su veredicto para siempre: los contadores de generación que vigilaba solo los mueve maquinaria que una consola no tiene |
| 6 | `CreateFileA` truncaba un descriptor | Es solo de escritorio; en una compilación UWP, MSVC le supuso un `int` de retorno |
| 7 | `C1128` | 63 000 funciones compiladas en un solo objeto necesitan `/bigobj` |
| 8 | La música sonaba peor que en la consola | El remuestreo del XA era lineal de dos puntos y se reiniciaba en cada sector. Ahora hace el «zigzag» de 25 puntos del propio hardware, y el SPU interpola en cúbico |
| 9 | Al volver de Home empezaba de cero | El modo desarrollador *termina* un juego suspendido. La máquina entera se guarda cuando la ventana pasa a segundo plano y se restaura cuando el sistema la relanza |
| 10 | 54-55 FPS en 16:9 | Tres pasos: un camino rápido en el rasterizador, los anillos de depuración de la GPU fuera de la compilación, y la pasada ancha a un hilo de trabajo: **60 sostenidos** |
| 11 | No había forma de saber a cuántos FPS iba | Una consola no tiene barra de título, que es donde el runtime lo escribe. Un contador en pantalla, que se enciende y apaga con **R3** |
| 12 | Cargar un estado guardado caía a 0,55x y se cerraba | Cinco cosas que el estado no llevaba; la quinta era nuestra |
| 13 | El ejecutable tenía otro nombre | `main` renombró el binario de escritorio; el manifiesto y la consola esperan el de antes |

## Créditos y licencia

Port y herramientas de **Recompilaciones**. Publicado bajo la
[PolyForm Noncommercial License 1.0.0](LICENSE), la misma del framework psxrecomp del que esto es un
derivado.

Los comentarios de los parches van en español, que es donde se escribieron; lo que escriben *dentro* del
árbol del juego va en inglés, como el resto del runtime. La documentación está en los dos idiomas.

*Street Fighter EX Plus α* es © Capcom / Arika. Este proyecto no está afiliado a ellos, ni a Sony, ni a
Microsoft, ni a los autores del proyecto del juego o del framework, y no distribuye nada que les pertenezca.
El detalle —qué hay y qué no hay aquí exactamente, y cómo pedir una retirada— está en
[`NOTICE.es.md`](NOTICE.es.md). Quien tenga derechos sobre este material puede escribir a
**jajdpmail@gmail.com**.
