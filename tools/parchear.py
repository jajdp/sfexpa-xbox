# -*- coding: utf-8 -*-
"""Lo que comparten los parches de este repositorio: leer, comprobar, sustituir y escribir.

Cada `parche_*.py` de esta carpeta hace lo mismo con anclas distintas, así que la mecánica vive
aquí una sola vez:

    import parchear

    FIRMA = 'Xbox port: ...'
    CAMBIOS = [(archivo, FIRMA, viejo, nuevo), ...]

    def main():
        raiz = parchear.raiz()
        parchear.informe(parchear.aplicar(parchear.runtime(raiz), CAMBIOS))

Las tres reglas que cumple todo parche de aquí, y que son el motivo de que `apply_uwp.py` pueda
detenerse a medias sin dejar un árbol inservible:

- **Todo o nada.** Cada ancla tiene que aparecer exactamente una vez; si una sola no cuadra, no se
  escribe nada —en ningún archivo de ese parche— y el script muere diciendo cuántas veces la
  encontró.
- **Idempotente.** La firma queda escrita dentro del archivo, así que pasarlo dos veces no cambia
  nada y lo dice.
- **Escritura atómica y sin tocar el formato.** Se escribe un `.tmp` al lado y se reemplaza de una
  vez, conservando el final de línea que el archivo ya tenía.

Los comentarios que los parches escriben DENTRO del árbol del juego van en inglés, como el resto
del runtime, y en ASCII: MSVC lee un archivo sin BOM con la página de códigos del sistema, y un
acento puede absorber el carácter siguiente. Los comentarios de los scripts van en español, que es
donde se escribieron.

Recompilaciones — https://github.com/jajdp/sfexpa-xbox
PolyForm Noncommercial License 1.0.0
"""
import os
import sys

__all__ = ['raiz', 'runtime', 'aplicar', 'informe']

# La raíz de un árbol del juego se reconoce por estos dos: el proyecto y el framework como submódulo.
SENAS = (os.path.join('PlusAlphaProject', 'CMakeLists.txt'), os.path.join('psxrecomp', 'runtime'))


def raiz(ayuda='<ruta de la raiz del arbol del juego>'):
    """La raíz del árbol del juego, tomada del primer argumento que no sea una opción.

    Comprueba las señas antes de devolverla: así un parche no empieza a buscar anclas en una carpeta
    que no es lo que cree, y el error dice qué falta en vez de «0 apariciones del ancla».
    """
    libres = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not libres:
        sys.exit('uso: %s %s' % (os.path.basename(sys.argv[0]), ayuda))
    r = os.path.abspath(libres[0])
    for sena in SENAS:
        if not os.path.exists(os.path.join(r, sena)):
            sys.exit('no es la raiz de un arbol del juego (falta %s): %s\n'
                     'Clonalo con --recurse-submodules; docs/INSTALL.es.md §2.' % (sena, r))
    return r


def runtime(raiz_juego, *partes):
    """Una ruta dentro del framework: runtime('…') o runtime('…', 'src', 'main.cpp')."""
    return os.path.join(raiz_juego, 'psxrecomp', 'runtime', *partes)


def aplicar(base, cambios, previos=()):
    """Aplica los cambios bajo `base`. Devuelve la lista de lo hecho (vacía si ya estaba todo).

    - `cambios`: `(archivo, firma, viejo, nuevo)`. `archivo` es relativo a `base`. Si la firma ya
      está en el archivo, ese cambio se salta; si no, `viejo` tiene que aparecer **una sola vez**.
    - `previos`: `(archivo, texto de una versión anterior de este parche, texto actual)`, que se
      sustituye antes de nada. Sirve para poner al día un árbol parcheado con una versión vieja.

    Nada se escribe hasta que todos los cambios han cuadrado.
    """
    textos, informe_ = {}, []

    def texto(nombre):
        if nombre not in textos:
            ruta = os.path.join(base, nombre)
            if not os.path.isfile(ruta):
                sys.exit('no existe %s' % ruta)
            with open(ruta, 'rb') as f:
                t = f.read().decode('utf-8')
            textos[nombre] = [ruta, '\r\n' if '\r\n' in t else '\n', t.replace('\r\n', '\n'), False]
        return textos[nombre]

    for nombre, anterior, actual in previos:
        reg = texto(nombre)
        if reg[2].count(anterior) == 1:
            reg[2] = reg[2].replace(anterior, actual)
            reg[3] = True
            informe_.append('%s: version anterior del parche puesta al dia' % nombre)

    for nombre, firma, viejo, nuevo in cambios:
        reg = texto(nombre)
        if firma in reg[2]:
            continue
        n = reg[2].count(viejo)
        if n != 1:
            sys.exit('%s: %d apariciones de %r\n'
                     'El arbol no es el que este parche espera: comprueba la version del proyecto '
                     'y que los parches anteriores estan puestos (docs/INSTALL.es.md §3).'
                     % (nombre, n, viejo[:80]))
        reg[2] = reg[2].replace(viejo, nuevo)
        if firma not in reg[2]:
            sys.exit('%s: la firma %r no queda en el texto nuevo (parche mal escrito)'
                     % (nombre, firma[:60]))
        reg[3] = True
        informe_.append('%s: %s' % (nombre, firma.splitlines()[0].strip()))

    for ruta, eol, t, cambiado in textos.values():
        if cambiado:
            tmp = ruta + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(t.replace('\n', eol).encode('utf-8'))
            os.replace(tmp, ruta)
    return informe_


def informe(hechos, nada='el parche ya estaba entero'):
    """Imprime lo que se hizo, o que ya estaba puesto."""
    print('\n'.join(hechos) if hechos else nada)
