# -*- coding: utf-8 -*-
# psxrecomp (árbol de SFEXPA), runtime/src/overlay_loader.c: arreglo de la validación de los overlays ESTÁTICOS.
#
# psx_overlay_static_code_matches cachea si los bytes de un rango coinciden, y solo vuelve a calcular el CRC cuando cambia
# la suma de generaciones de sus páginas. Pero las generaciones solo suben en páginas del mapa de vigilancia, que solo
# rellenan el cargador de DLL y sljit: en la Xbox no hay ni uno ni otro, así que el primer veredicto de cada variante
# quedaba para siempre. Una variante validada en el título seguía «válida» después de que la carga de la demo pusiera
# otro código en esas direcciones (cierre de la demo en el cuadro 5243 y, muy probablemente, el de Akuma), y una que no
# coincidió la primera vez quedaba descartada para siempre.
#
# Cambios (comentarios en inglés, como el resto del runtime):
#  1. la primera validación de un rango marca sus páginas con overlay_watch_set_range;
#  2. la caché pasa de 4096 a 131072 entradas (la v4 tiene ~63 000 variantes y desbordaba la de 4096).
# Copia del original en <scratchpad>\validacion-estatica-original\overlay_loader.c. --quitar la restaura (shutil.copy).
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

RUTA = parchear.runtime(parchear.raiz(), 'src', 'overlay_loader.c')
COPIA = RUTA + '.original'   # la copia del original, junto a el
MARCA = 'Xbox port (2026-10-03): static-overlay validation'

CAMBIOS = [
    ('#define STATIC_MATCH_CACHE_CAP 4096u\n',
     '/* ' + MARCA + ': 4096 slots overflowed with ~63k static\n'
     ' * variants (every CPS resume wrapper has its own ranges array), and an entry\n'
     ' * that finds no slot is rehashed on every dispatch. */\n'
     '#define STATIC_MATCH_CACHE_CAP 131072u\n'),
    ('''    if (entry) {
        entry->ranges = lo_len_pairs;
        entry->count = count;
        entry->expected_crc = expected_crc;
        entry->gen_sum = gen_sum;
        entry->matches = matches;
    }
    return matches;''',
     '''    if (entry) {
        if (!entry->ranges) {
            /* ''' + MARCA + ''': page generations only move on
             * WATCHED pages, and only the DLL loader and sljit set the watch. With
             * static overlays alone (the Xbox build: no DLLs, no toolchain) nothing
             * was watched, gen_sum stayed constant and the first verdict was cached
             * forever: a variant validated on the title screen kept "matching" after
             * a load put other code at those addresses (SFEX+a closed itself on the
             * demo load, FAIL-FAST unknown dispatch 0x847C3C70), and one that did not
             * match on its first check was never used again. Watch the pages the
             * first time these ranges are validated, so later CPU or DMA stores bump
             * their generation and force a rehash. */
            extern void overlay_watch_set_range(uint32_t phys, uint32_t len);
            for (uint32_t i = 0; i < count; i++)
                overlay_watch_set_range(lo_len_pairs[i * 2u] & 0x1FFFFFFFu,
                                        lo_len_pairs[i * 2u + 1u]);
        }
        entry->ranges = lo_len_pairs;
        entry->count = count;
        entry->expected_crc = expected_crc;
        entry->gen_sum = gen_sum;
        entry->matches = matches;
    }
    return matches;'''),
]


def main():
    with open(RUTA, 'rb') as f:
        t = f.read().decode('utf-8')
    if '--quitar' in sys.argv:
        if MARCA in t and os.path.exists(COPIA):
            shutil.copy(COPIA, RUTA + '.tmp-val')
            os.replace(RUTA + '.tmp-val', RUTA)
            print('overlay_loader.c: restaurado')
        else:
            print('overlay_loader.c: sin cambios que quitar')
        return
    if MARCA in t:
        print('overlay_loader.c: ya tenía el arreglo')
        return
    os.makedirs(os.path.dirname(COPIA), exist_ok=True)
    if not os.path.exists(COPIA):
        shutil.copy2(RUTA, COPIA)
    eol = '\r\n' if '\r\n' in t else '\n'
    t = t.replace('\r\n', '\n')
    for viejo, nuevo in CAMBIOS:
        n = t.count(viejo)
        if n != 1:
            raise SystemExit(f'overlay_loader.c: se esperaba 1 aparición y hay {n}:\n{viejo[:200]}')
        t = t.replace(viejo, nuevo)
    with open(RUTA + '.tmp-val', 'wb') as f:
        f.write(t.replace('\n', eol).encode('utf-8'))
    os.replace(RUTA + '.tmp-val', RUTA)
    print('overlay_loader.c: arreglo puesto')


main()
