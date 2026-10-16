# Cómo funciona, y por qué cada parche está ahí

*(English: [HOW-IT-WORKS.md](HOW-IT-WORKS.md))*

Cada cosa de este repositorio salió de un fallo concreto en una consola de verdad. Esto cuenta cuál
fue, cómo se midió y qué lo arregló. Si solo quieres construirlo, [`INSTALL.es.md`](INSTALL.es.md)
basta.

## De dónde sale

El proyecto del juego **ya trae un perfil UWP**: su autor escribió el `UWP\` (manifiesto, entrada
WinRT, recursos y un script para Visual Studio 2019) y el framework que usa tiene un perfil
«UWP/Xbox» en su `runtime.cmake` —sin diálogos de Win32, con fibras UWP, atómicos de C11 y el
registro en `LocalState`—. Nunca publicó el paquete.

Así que el punto de partida es bueno: el C del ejecutable del juego y el de la BIOS vienen generados
en el repositorio, y una vez configurado, compilar lleva menos de un minuto. Lo que este
repositorio añade es todo lo que faltaba entre «compila» y «es un juego que se puede jugar en una
consola».

En la consola el juego corre con el **renderizador por software** del runtime, presentado por SDL2
(que en la Xbox acaba en Direct3D 11), la BIOS en modo HLE con la real como respaldo, y todos sus
datos en `LocalState\PSXRecomp\SLUS-00548\`.

## El disco no cabe por el Device Portal

Subir el `.bin` de 528 MB da **HTTP 500**. No son los nombres con espacios y paréntesis (se probó):
las subidas del portal pasan por `D:\DevelopmentFiles`, la partición de unos 5 GB del modo
desarrollador, que suele estar casi llena.

`tools/partir_disco.py` lo parte en trozos de 150 MiB y la entrada UWP los une en el arranque
siguiente, una sola vez, y lo anota en `logs\partes.txt` («partes: 4 unidas, 528049872 bytes»). Las
partes se quedan: ocupan, pero sirven de respaldo.

## La **B** cerraba el juego

En una Xbox, **B** es también «atrás», y SDL se lo entrega al sistema, que cierra la aplicación. La
entrada UWP pone `SDL_HINT_WINRT_HANDLE_BACK_BUTTON = 1` y el botón vuelve a ser un botón del
juego.

## Lo que el juego carga del disco: los overlays

**El síntoma.** El vídeo de la presentación de Capcom iba a **0,76–0,83x** (46–48 FPS) durante unos
9 segundos. En un PC de escritorio va a 1,00x.

**La causa.** El código del reproductor de vídeo no está en el ejecutable del juego: el juego lo
carga del disco en tiempo de ejecución, en `0x800D6000…`. Eso es un **overlay**, y psxrecomp lo
ejecuta en su **intérprete** salvo que lo tenga compilado. En el PC lo compila a DLL al vuelo; una
consola no puede cargar esas DLL.

**Cómo se midió.** Un medidor temporal escribía cada segundo en el registro la CPU del hilo del
emulador, el tiempo de emulación, de espera y de presentación, el MDEC, el DMA de la GPU, las
instrucciones interpretadas y los aciertos del despacho estático. Durante el vídeo: el hilo al
**99 %**, **11,5 millones** de instrucciones interpretadas por segundo (fuera del vídeo, menos de
0,5 millones) y un solo bucle, en `0x800E78DC`, con 8,7 de esos millones. El MDEC, el SPU y la GPU
juntos, menos de 30 ms por segundo: no era el dibujo.

**El arreglo** es compilar los overlays **dentro** del ejecutable, a partir de capturas de la
memoria del juego. Costó tres intentos:

| Qué llevaba | Resultado en el vídeo |
|---|---|
| Una captura del PC (90 s), 4 798 funciones | 0,77x: el despacho estático casi no acertaba |
| 29 variantes capturadas en 150 s, 11 919 funciones | 0,80x: acertaba, pero el bucle seguía interpretado |
| Las 29 variantes con el generador parcheado, 16 059 funciones y 174 fragmentos | **1,00x**, el hilo al 70-78 % |

Y dejó dos trampas que son la razón de dos herramientas de aquí:

- **La captura solo guarda la última foto.** El runtime reescribe `overlay_captures.json` en cada
  disparo y conserva solo la última imagen de la RAM. El reproductor solo está en memoria mientras
  dura la presentación: la foto del segundo 87 ya tenía datos en esas direcciones.
  `tools/captura_variantes.ps1` copia cada versión mientras el juego corre, y
  `tools/capturas_variantes.py --unir` deja una entrada por variante.
- **El generador elegía mal los bytes.** Para las entradas «huérfanas» —las que no tienen una
  función que las contenga, como el reproductor—, `compile_overlays.py --static` compilaba un
  fragmento con los bytes de la **última** captura que las mencionaba. En las fotos posteriores al
  vídeo, eso son datos, y el fragmento no salía: *«STATIC COVERAGE WARNING: 9 captured dispatch
  entry(s) have no compiled body/owner»*. `tools/parche_compile_overlays.py` hace que pruebe cada
  captura y se quede con todos los fragmentos válidos: 0 avisos. Cada fragmento se valida por
  contenido al despacharlo, así que tener varios para una dirección es seguro.

## El cierre en las pantallas de carga

Con los overlays compilados, el juego empezó a cerrarse solo en la demostración, siempre a los ~85
segundos, en plena carga, con *«FAIL-FAST unknown dispatch: addr=0x847C3C70 ra=0x80016800»*: un
salto a una dirección que no existe.

Como era determinista, se buscó por **bisección**, compilando e instalando versiones con partes de
las capturas:

| Overlays compilados | En la demostración |
|---|---|
| Todos | Se cierra |
| Ninguno | **No se cierra** |
| Solo la región del reproductor | No se cierra |
| Mitades de las 18 variantes de `0x80020000` | Se cierra con la **variante 8** sola |
| Mitades de las 85 entradas de esa variante | Se cierra con las entradas `0x8008F0A0` y `0x8008F0E4` |

La variante 8 es la imagen de esa región en la **pantalla de título**, y esas dos entradas son
fragmentos interiores de una función del título.

**La causa está en el framework.** `psx_overlay_static_code_matches` cachea si los bytes de un rango
coinciden, y solo recalcula el CRC cuando cambia la suma de las generaciones de sus páginas. Pero
las generaciones solo suben en páginas marcadas para vigilar, y eso solo lo hacen el cargador de
DLL y sljit: en una consola no hay ninguno de los dos, así que la suma no cambia nunca y **el primer
veredicto de cada variante vale para siempre**. Los fragmentos del título seguían «coincidiendo»
después de que la carga de la demostración pusiera otro código en esas direcciones: se ejecutaba
código del título sobre el de la demostración, y de ahí el puntero basura. Al revés, una variante
que no coincidía la primera vez no se usaba nunca más, aunque su código se cargara después.

`tools/parche_validacion_estatica.py` hace dos cosas: la primera validación de un rango marca sus
páginas, así que cualquier escritura posterior —de la CPU o del DMA del CD— obliga a recalcular; y
la caché pasa de 4 096 a 131 072 entradas, porque con las capturas de una partida entera cada
envoltorio tiene su propio rango y lo que no cabía se recalculaba en cada llamada.

Después de eso, 299 segundos de demostración con 12 cargas sin un cierre. El original de psxrecomp
había arreglado esto mismo por su cuenta; el fork que usa el juego no lo tiene.

## Un escenario que se arrastraba, y no eran los overlays

Quedaba un escenario concreto a **0,80x** durante toda la pelea. La medición, comparando los
segundos lentos con los normales de la misma partida:

| Por segundo | En ese escenario | Fuera |
|---|---|---|
| Emulación | 907 ms | 755 ms |
| DMA de la GPU | 133 ms | 57 ms |
| Saltos a código sin compilar | 343 000 | 48 000 |
| Aciertos del despacho estático | 11 360 | 80 013 |
| Recálculos de CRC de la validación | 7 | 1 027 |

Los overlays ya iban compilados y la validación no costaba nada. Las direcciones que más se
interpretaban **no eran de los overlays, sino del ejecutable principal**: el C que trae la versión
publicada del proyecto cubre **454 540 de los 782 336 bytes** del texto (**58,1 %**), y esas
direcciones caen en cinco huecos de los que faltan. Lo que no está compilado se interpreta en
bloques de una o dos instrucciones, y cada bloque es un salto a código sin compilar: 343 000 por
segundo. En un PC no se nota; en la consola no da abasto.

Hay dos salidas. Una es ampliar la cobertura a mano, con semillas de direcciones de entrada de
función: se buscaron las de esos huecos (destinos de `jal`, pares `lui`/`addiu`, tablas de punteros
y prólogos) y la pelea pasó a **1,06x**, pero aparecieron otros huecos en otros escenarios. La otra
—la que usa esta receta— es la rama **`main`** del proyecto, cuyo C del ejecutable sube a
**1 358 funciones y 619 384 bytes (79,2 %)** y cubre esas direcciones y las de los demás escenarios.
Con ella, una partida de 511 segundos con 15 cargas no tuvo **ni un segundo por debajo de 0,95x**.

Por eso [`INSTALL.es.md`](INSTALL.es.md) §2 dice `main` y no la última versión publicada.

## Tres cosas pequeñas que paraban la compilación

- **`CreateFileA`** solo existe en el escritorio. El barrido de la caché de DLL del framework lo usa
  para dejar una marca, y en una compilación UWP MSVC no lo encuentra declarado: le supone un
  retorno `int` y trunca el descriptor de 64 bits. `tools/parche_createfile.py` pone un `fopen`
  dentro de un `#if` de familia de API.
- **`C1128`**: con 63 000 funciones compiladas, el objeto de los overlays pasa del límite de
  secciones del formato COFF. Necesita `/bigobj`, que `construir-uwp.ps1` pone en el `sources.cmake`
  que escribe.
- **El nombre del ejecutable**: la rama `main` renombró el binario de escritorio a `exPlusAlpha`, y
  el manifiesto y la consola esperan `StreetFighterEXPlusAlphaRecomp.exe`. `apply_uwp.py` lo
  devuelve al final del `CMakeLists.txt`, donde gana al valor anterior.

## El sonido

La música de la versión de PlayStation es **XA ADPCM de 4 bits a 37,8 kHz**: ya de fábrica está por
debajo del QSound de la recreativa. El recomp lo empeoraba de dos maneras, y las dos se arreglan:

- **El remuestreo era lineal de dos puntos y se reiniciaba en cada sector**: las imágenes de la
  frecuencia de muestreo volvían a la banda audible, y cada sector dejaba una costura 18,75 veces
  por segundo. `tools/parche_xa_zigzag.py` lo cambia por la interpolación **«zigzag» de 25 puntos**
  del propio controlador de CD, con sus 7 tablas de 29 coeficientes, y conserva el estado entre
  sectores.
- **El SPU cogía la muestra más cercana**: con `spu_hq = true` interpola en cúbico. En el registro
  sale *«SPU float-shadow enabled»*.

Sigue sin **reverberación**: eso le falta a psxrecomp, no a este port.

## Volver de Home empezaba de cero

En el modo desarrollador, la consola **termina** un juego UWP que pasa a segundo plano (y cualquier
aplicación de más de 128 MB). Al volver de Home, el sistema lo relanza, y un relanzamiento es un
arranque nuevo: el juego empezaba desde el principio.

El arreglo es guardar la máquina entera **cuando la ventana se oculta, se minimiza o pierde el
foco** —la aplicación sigue corriendo unos segundos antes de suspenderse, y una vez suspendida el
bucle de eventos de WinRT no vuelve, así que después ya no se podría— y restaurarla cuando el
sistema relanza la aplicación tras haberla terminado. Son dos parches, por dónde vive cada mitad:

- `tools/parche_reanudar.py`, en el runtime: la ranura de suspensión, el guardado y la restauración,
  con las esperas necesarias (la ventana nace oculta, y un guardado disparado junto a una carga se
  ejecutaría antes y la pisaría).
- `tools/parche_uwp_reanudar.py`, en la entrada UWP **y en SDL**: el dato de si esto es un
  relanzamiento tras una terminación (`PreviousExecutionState == Terminated`) solo viene con la
  activación UWP. La primera versión lo leía con `AppInstance::GetActivatedEventArgs()` antes de
  `SDL_main`, y en la consola eso devuelve **nulo**: el registro decía «previous execution state -1»
  en cada arranque y la máquina guardada se descartaba siempre. La versión que está aquí lo anota
  **dentro de SDL**, en el manejador de activación que sí trae los argumentos, y la entrada solo lo
  pisa si obtiene un valor.

Y antes de todo eso hubo que hacer que **cargar un estado guardado funcionara**: dejaba el juego a
0,55x y lo cerraba a los pocos segundos con *«DISPATCH FATAL: misaligned target»*. Eran cinco cosas
que el estado no llevaba o no rehacía al cargar —entre ellas el `pc` de arranque, las generaciones
de las páginas vigiladas, la resincronización de las interrupciones y de los plazos de la GTE—, y la
quinta era de este port: un estado cargado antes de que el runtime considerara «empezado» el juego
se saltaba el enganche que valida los despachos. Eso es `tools/parche_estado_guardado.py`.

## 16:9 a 60 FPS

El 16:9 por software costaba **54-55 FPS** en las peleas. La causa: en el modo ancho nativo cada
primitiva se dibuja **dos veces** —una en la VRAM fiel de 512 y otra en una superficie ancha de
682— y el juego amplía su recorte. Tres pasos, por este orden, y cada uno medido:

1. **Un camino rápido en el rasterizador.** Las llamadas por píxel releían el estado de dibujo
   —máscaras, semitransparencia, ventana de textura, página y paleta— en cada píxel, porque MSVC no
   puede mantener variables globales en registros entre escrituras de 16 bits, y volvían a
   comprobar límites que el recorte del tramo ya garantiza. El camino rápido toma ese estado una vez
   por primitiva. **1,8x en banco, 56-59 FPS**, con los píxeles bit a bit idénticos: se comprobó con
   un banco que dibuja lo mismo con el original y con el nuevo, con las mismas operaciones al azar
   (5 semillas × 100 000, escala 1 y 2, con y sin filtrado), y las 40 comparaciones dan la misma
   huella.
2. **La GPU sin los registros de depuración.** `gp0_execute_command` apuntaba cada orden en un
   anillo de 1 048 576 entradas (unos 120 MB) y cada primitiva en un censo de 2 097 152 (48 MB, con
   dos lecturas de la memoria del juego). Los dos solo los lee el servidor de depuración, que la
   compilación de la consola no lleva: ahí solo costaban tiempo y memoria en cada orden.
3. **La pasada ancha, en otro núcleo.** Un anillo de órdenes de un productor y un consumidor, con el
   estado capturado, y esperas solo donde hacen falta (los rectángulos de lectura de textura o
   paleta contra las escrituras de VRAM, y al presentar, volcar o configurar). **60 FPS sostenidos**,
   con el dibujo bajando del 25-30 % al 9-16 % del cuadro y ~82 000 órdenes por segundo al hilo con
   0 esperas.

Todo eso es `tools/parche_raster_hilo.py`, que **parte del `gpu_sw_renderer.c` original** y es el
último paso del `apply_uwp.py` por eso mismo.

## El contador de FPS

Una consola no tiene barra de título, que es donde el runtime escribe `[60 fps 1.00x]`. Sin eso no
hay manera de saber si una caída es real mientras se juega.

`tools/parche_contador_fps.py` dibuja ese mismo valor con rectángulos de SDL, después de copiar el
cuadro y antes de presentarlo: arriba a la izquierda, cifras de 3×5 sobre un recuadro negro
translúcido, verde con 59 o más, amarillo de 55 a 58 y rojo por debajo. Lo gobierna el mismo ajuste
que el del título, `[video] show_fps`.

`tools/parche_fps_r3.py` le añade **R3** para encenderlo y apagarlo sin reiniciar. SELECT sería el
botón natural, pero el modo entrenamiento ya lo usa —reinicia las posiciones y repite la jugada—;
R3, en cambio, queda libre porque el mando va fijado en modo digital y ahí los clics de los sticks
del DualShock no existen, así que el juego nunca ve ese botón. La comprobación va sobre la palabra
de botones **ya combinada** del jugador 1, justo antes de entregarla al SIO: puesta antes se perdía
el caso más común, el del jugador sin dispositivo asignado, en el que los botones salen del teclado
y de todos los mandos a la vez.

## Lo que no está aquí

Tres cosas del desarrollo no se publican, y conviene saberlo para no buscarlas:

- **El informe de errores fatales** (`crash_trace.c` y sus enganches), que escribía el motivo de un
  cierre en el registro y un `psx_last_run_report.json` en `logs\`. Fue lo que permitió entender el
  cierre en las cargas, pero es diagnóstico: el port funciona sin él.
- **Los andamios de medición**: el medidor por segundo, el perfilador de fases y los scripts de
  bisección. De ahí salen todas las cifras de este documento. Lo único de esa familia que sí está es
  `tools/parche_fases.py`, que añade a la línea `[FPS]` del registro en qué se fue el tiempo de cada
  segundo, porque es lo que sirve para diagnosticar una caída en la consola de otra persona.
- **Los overlays compilados y sus capturas**, que son código del juego leído de tu disco
  ([`ASSETS.es.md`](ASSETS.es.md) y [`NOTICE.es.md`](../NOTICE.es.md)).
