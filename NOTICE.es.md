# Aviso

*(English: [NOTICE.md](NOTICE.md))*

## Sin afiliación

Esto es un proyecto de aficionado, no oficial y sin ánimo de lucro. **No está afiliado a Capcom,
Arika, Sony ni Microsoft**, ni a sus filiales, ni cuenta con su respaldo o aprobación, ni lo está
con el autor del framework [psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp) ni con el
del [proyecto del juego](https://github.com/guimaraf/plusalpha-recomp) sobre el que se apoya este
port. *Street Fighter*, *Street Fighter EX Plus α*, *Xbox* y todos los nombres y marcas
relacionados son de sus respectivos propietarios, y aquí se usan solo para decir con qué funciona
esto.

Aquí no se vende nada, y nada de esto está monetizado.

## Qué no distribuye este repositorio

Ni código del juego. Ni imagen del disco. Ni BIOS. Ni ejecutable compilado. Ni paquete `.msix`. Ni
partidas. Ni arte, sonido, música o tipografías del juego: tampoco los mosaicos del paquete, y por
eso `package/Assets/` está vacía y [`docs/ASSETS.es.md`](docs/ASSETS.es.md) te pide los tuyos.

**Ni los overlays compilados.** El rendimiento de este port depende de compilar, dentro del
paquete, el código que el juego carga del disco mientras corre. Ese código es *del juego*, leído de
tu propio disco: las herramientas que lo capturan y lo compilan están aquí; las capturas y el
`overlays_static.c` que sale de ellas, no —el `.gitignore` los bloquea por nombre.

Nada de esto produce un juego jugable por sí solo. Necesitas tu propia copia volcada legalmente del
disco, una BIOS de consola y el proyecto del juego compilando, y este repositorio no te da ninguna
de las tres ni puede dártelas.

## Qué contiene de trabajo de otros

**Parches contra el framework psxrecomp.** Los trece parches citan en total **117 líneas** del
código del framework, repartidas en **48 anclas**: el texto que cada parche comprueba antes de
escribir, para fallar en seguro en vez de estropear un árbol que no reconoce. El framework que usa
el juego ([guimaraf/psxrecomp-plusalpha](https://github.com/guimaraf/psxrecomp-plusalpha), un fork
de psxrecomp) lleva la **PolyForm Noncommercial License 1.0.0**, © 2026 Matthew Stan, que permite
obras derivadas sin ánimo de lucro; este repositorio es una de ellas, y se publica bajo
[esa misma licencia](LICENSE).

**Ni una línea de código del proyecto del juego.**
[guimaraf/plusalpha-recomp](https://github.com/guimaraf/plusalpha-recomp) no lleva ninguna licencia,
así que no se reproduce nada suyo. Por eso también `tools/apply_uwp.py` añade su bloque de CMake al
**final** del archivo: un ancla habría significado copiar una línea suya. El único archivo de aquí
que comparte forma con uno de ese proyecto es `package/Package.appxmanifest` —un manifiesto de
paquete es un esquema fijo de Microsoft, así que los nombres de los elementos son los mismos en
cualquiera—; la identidad, el publicador, la familia de dispositivos, la versión y la descripción
son nuestros, y de todas formas tienes que cambiarlos por los tuyos.

**`src/SDL_winrt_main_NonXAML.cpp`** es la entrada WinRT de SDL, *puesta en el dominio público por
David Ludwig*, con las dos cosas que este port necesitaba marcadas dentro: unir el disco partido en
el primer arranque, y anotar por qué se inició la aplicación para que el runtime pueda decidir si
restaura. El original es parte de [SDL](https://github.com/libsdl-org/SDL).

**Las tablas del filtro XA** de `tools/parche_xa_zigzag.py` —7 × 29 coeficientes— son el filtro de
interpolación del propio controlador de CD, tal como lo documenta
[psx-spx](https://psx-spx.consoledev.net) («CDROM XA Audio ADPCM Compression»). Son una descripción
del hardware, no el código de nadie, y el script las comprueba (ganancia en continua y simetría)
antes de escribir nada.

**Aquí no hay ninguna captura de pantalla.** Una captura de esto funcionando sería casi toda arte de
Capcom, y estaría mostrando su trabajo en vez de este.

## Retirada y contacto

Si tienes derechos sobre este material y quieres que algo de aquí se quite o se cambie, escribe a
**jajdpmail@gmail.com** diciendo a qué te opones y en calidad de qué escribes.

Las peticiones de quien tiene los derechos se atienden: se quita la parte en disputa, o se retira el
repositorio, sin discutir, y recibirás una respuesta confirmándolo. No hace falta ningún aviso ni
proceso legal más allá de ese correo para llegar a la persona que mantiene esto.
