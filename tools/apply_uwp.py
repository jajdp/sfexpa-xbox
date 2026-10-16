#!/usr/bin/env python3
"""Aplica el port de Xbox a un árbol de Street Fighter EX Plus Alpha (plusalpha-recomp).

Uso:
    python tools/apply_uwp.py <raíz del árbol del juego>
    python tools/apply_uwp.py --list

La raíz es la carpeta que tiene `PlusAlphaProject\\` y el framework en `psxrecomp\\` (clónala con
`--recurse-submodules`). Cada paso es idempotente y comprueba lo que espera encontrar antes de
escribir, así que pasarlo dos veces no cambia nada y, si un paso no reconoce el árbol, se detiene
ahí en vez de dejarlo a medias.

Después de esto: `tools\\construir-uwp.ps1`, que compila, empaqueta y firma (docs/INSTALL.es.md §6).

Los overlays del juego van aparte, porque salen de TU disco y tardan: docs/HOW-IT-WORKS.es.md
explica por qué hacen falta y `tools\\captura_variantes.ps1` y `tools\\overlays_estaticos.ps1` los
producen. Sin ellos el juego corre, pero la presentación va a 0,77x y algunos escenarios se
arrastran.

Recompilaciones — https://github.com/jajdp/sfexpa-xbox
PolyForm Noncommercial License 1.0.0
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERR = os.path.join(REPO, 'tools')
ENTRADA = os.path.join(REPO, 'src', 'SDL_winrt_main_NonXAML.cpp')
MANIFIESTO = os.path.join(REPO, 'package', 'Package.appxmanifest')

MARCA = 'sfexpa-xbox (Recompilaciones)'
PROYECTO_BASE = 'guimaraf/plusalpha-recomp'

# Los pasos informan en castellano, con acentos, y la consola de Windows arranca en una página de
# códigos que no los tiene (cp1252 o cp850): sin esto, imprimir el informe de un paso levanta un
# UnicodeEncodeError y el port se interrumpe a media aplicación. Se arregla aquí, para la salida
# propia, y en el entorno de los subprocesos, para la suya.
for _flujo in (sys.stdout, sys.stderr):
    if hasattr(_flujo, 'reconfigure'):
        _flujo.reconfigure(encoding='utf-8', errors='replace')
ENTORNO_HIJOS = dict(os.environ, PYTHONIOENCODING='utf-8:replace', PYTHONUTF8='1')

# El orden importa: primero el framework, luego lo que se apoya en él. `parche_reanudar.py` necesita
# la ranura de suspensión que crea `parche_estado_guardado.py`; `parche_fps_r3.py`, el contador que
# pone `parche_contador_fps.py`; y `parche_raster_hilo.py` va al final, porque parte del
# `gpu_sw_renderer.c` original y es el que más toca.
PASOS = [
    ('parche_xa_zigzag.py',           'la música del disco, remuestreada como en el hardware'),
    ('parche_validacion_estatica.py', 'que la validación de los overlays estáticos se invalide'),
    ('parche_createfile.py',          'CreateFileA no existe en UWP (overlay_loader.c)'),
    ('parche_compile_overlays.py',    'el generador de overlays prueba cada captura, no solo la última'),
    ('parche_estado_guardado.py',     'cargar un estado guardado sin que el juego se caiga'),
    ('parche_reanudar.py',            'guardar cada 10 s y volver donde lo dejaste tras la terminación'),
    ('parche_uwp_reanudar.py',        'la entrada UWP y SDL anotan el motivo del arranque'),
    ('parche_contador_fps.py',        'el contador de FPS en pantalla: en la consola no hay barra de título'),
    ('parche_fps_r3.py',              'R3 enciende y apaga el contador'),
    ('parche_gp0_ligero.py',          'la GPU sin los registros de depuración que la consola no lee'),
    ('parche_fases.py',               'en qué se va el tiempo de cada segundo, en el registro'),
    ('parche_raster_hilo.py',         'el dibujo rápido y la pasada ancha en otro núcleo: 60 FPS en 16:9'),
]

# El nombre del ejecutable. El proyecto llama `exPlusAlpha` al binario de escritorio, y el manifiesto
# y la consola esperan `StreetFighterEXPlusAlphaRecomp.exe`. Va al FINAL del CMakeLists, donde el
# destino ya existe y gana al valor anterior: así no hace falta ancla ninguna y no se copia aquí
# ni una línea del CMakeLists del proyecto.
BLOQUE_CMAKE = '''
# ''' + MARCA + ''': el nombre del ejecutable del paquete. El proyecto renombró el binario de
# escritorio a exPlusAlpha, pero Package.appxmanifest y las herramientas de la consola esperan
# StreetFighterEXPlusAlphaRecomp.exe. Al final del archivo gana al valor anterior.
if(CMAKE_SYSTEM_NAME STREQUAL "WindowsStore")
    set_target_properties(psx-runtime PROPERTIES OUTPUT_NAME "StreetFighterEXPlusAlphaRecomp")
endif()
'''


def copiar_si_hace_falta(origen, destino, que, hechos, solo_si_no_esta=False):
    """Copia `origen` sobre `destino` si el contenido cambia. Devuelve True si escribió.

    Con `solo_si_no_esta`, no pisa un destino que ya lleve la marca de este repositorio: es para el
    manifiesto, que quien clone TIENE que editar (su Identity, su Publisher) y que no queremos
    devolver a los nuestros en la siguiente pasada.
    """
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(origen, 'rb') as f:
        fuente = f.read()
    actual = None
    if os.path.isfile(destino):
        with open(destino, 'rb') as f:
            actual = f.read()
        if solo_si_no_esta and MARCA.encode() in actual:
            return False
    if actual == fuente:
        return False
    with open(destino, 'wb') as f:
        f.write(fuente)
    hechos.append(que)
    return True


def main():
    if '--list' in sys.argv[1:]:
        print('El port, en orden:\n')
        print('  %-32s %s' % ('(entrada WinRT)', 'src/SDL_winrt_main_NonXAML.cpp -> <arbol>/UWP/'))
        print('  %-32s %s' % ('(manifiesto)', 'package/Package.appxmanifest -> <arbol>/UWP/'))
        print('  %-32s %s' % ('(CMakeLists)', 'el nombre del ejecutable del paquete'))
        for n, (script, que) in enumerate(PASOS, 1):
            print('  %2d. %-28s %s' % (n, script, que))
        print('\nY despues, fuera de aqui: los overlays (docs/HOW-IT-WORKS.es.md) y '
              'tools/construir-uwp.ps1.')
        return 0

    sys.argv = [a for a in sys.argv if a != '--list']
    raiz = parchear.raiz()
    if not os.path.isfile(ENTRADA):
        sys.exit('falta en el repositorio: %s' % ENTRADA)
    if not os.path.isfile(MANIFIESTO):
        sys.exit('falta en el repositorio: %s' % MANIFIESTO)

    hechos = []

    # 1. La entrada WinRT. El CMakeLists del proyecto ya la compila en su bloque WindowsStore, así
    #    que solo hay que poner la nuestra: une las partes del disco al arrancar, atiende el botón B
    #    y anota el motivo del arranque para la reanudación.
    copiar_si_hace_falta(ENTRADA, os.path.join(raiz, 'UWP', 'SDL_winrt_main_NonXAML.cpp'),
                         'UWP/SDL_winrt_main_NonXAML.cpp', hechos)

    # 2. El manifiesto. Hay que editarlo (Identity, Publisher, PhoneProductId): si ya lleva la marca,
    #    no se toca.
    destino_m = os.path.join(raiz, 'UWP', 'Package.appxmanifest')
    if copiar_si_hace_falta(MANIFIESTO, destino_m, 'UWP/Package.appxmanifest', hechos,
                            solo_si_no_esta=True):
        print('-- UWP/Package.appxmanifest puesto. EDITALO: Identity Name, Publisher (= el sujeto\n'
              '   exacto de tu certificado) y PhoneProductId. docs/INSTALL.es.md §5.')

    # 3. El nombre del ejecutable, al final del CMakeLists del juego.
    cmake = os.path.join(raiz, 'PlusAlphaProject', 'CMakeLists.txt')
    with open(cmake, 'rb') as f:
        crudo = f.read().decode('utf-8')
    eol = '\r\n' if '\r\n' in crudo else '\n'
    texto = crudo.replace('\r\n', '\n')
    if MARCA not in texto:
        nuevo = texto.rstrip('\n') + '\n' + BLOQUE_CMAKE
        tmp = cmake + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(nuevo.replace('\n', eol).encode('utf-8'))
        os.replace(tmp, cmake)
        hechos.append('PlusAlphaProject/CMakeLists.txt: el nombre del ejecutable')

    # 4. Los parches, en orden.
    for script, que in PASOS:
        ruta = os.path.join(HERR, script)
        if not os.path.isfile(ruta):
            sys.exit('falta en el repositorio: tools/%s' % script)
        print('-- %-30s %s' % (script, que))
        r = subprocess.run([sys.executable, ruta, raiz], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=ENTORNO_HIJOS)
        salida = (r.stdout or '').strip()
        if salida:
            print('\n'.join('   ' + l for l in salida.split('\n')))
        if r.returncode != 0:
            print((r.stderr or '').strip())
            sys.exit('\nse detuvo en %s (nada mas se aplico). El arbol no es el que este paso '
                     'espera: comprueba que es %s con sus submodulos y que los pasos anteriores '
                     'estan puestos.' % (script, PROYECTO_BASE))
        if salida and 'ya estaba' not in salida:
            hechos.append(script)

    total = len(PASOS) + 3
    if hechos:
        print('\nListo: %d de los %d pasos escribieron algo; el resto ya estaba puesto.'
              % (len(hechos), total))
    else:
        print('\nListo: el port ya estaba aplicado entero, no hubo nada que cambiar.')
    print('Ahora: tools/construir-uwp.ps1 para compilar, empaquetar y firmar '
          '(docs/INSTALL.es.md §6).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
