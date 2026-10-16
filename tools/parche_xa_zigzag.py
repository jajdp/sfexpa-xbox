# -*- coding: utf-8 -*-
"""El remuestreo de la música XA, como lo hace el controlador de CD de la consola.

`psxrecomp/runtime/src/cdrom.c` llevaba la música del disco de 37800 Hz a 44100 Hz con una
interpolación LINEAL de dos puntos, y la reiniciaba en cada sector. Dos consecuencias audibles: las
imágenes de la frecuencia de muestreo vuelven a la banda audible (siseo metálico) y cada sector deja
una costura, 18,75 veces por segundo. Este parche lo cambia por lo que hace el hardware: la
interpolación **«zigzag» de 25 puntos** documentada en psx-spx («CDROM XA Audio ADPCM Compression»),
con sus **7 tablas de 29 coeficientes** —cada 6 muestras de entrada salen 7 de 44100 Hz, una por
tabla—, un anillo de 32 entradas y el estado conservado de un sector al siguiente, porque el
controlador filtra el flujo continuo. Se reinicia donde se reinicia el decodificador XA.

Las tablas son los coeficientes del filtro del hardware tal como psx-spx los publica (203 números;
`https://psx-spx.consoledev.net`): no son código de nadie, describen la consola. Las comprobaciones
de abajo son las mismas con que se leyeron de ahí: las 7 fases tienen la misma ganancia en continua
(~0,906, que es -0,86 dB y es del hardware) y la tabla central es simétrica.

El sonido sigue sin reverberación: eso es una carencia de psxrecomp, no de aquí.

Uso: py -3 parche_xa_zigzag.py <ruta de la raiz del arbol del juego>

Recompilaciones — https://github.com/jajdp/sfexpa-xbox
PolyForm Noncommercial License 1.0.0
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

# psx-spx, «CDROM XA Audio ADPCM Compression»: Table1..Table7, índices 1 a 29.
TABLAS = [
    [0, 0, 0, 0, 0, -2, 10, -34, 65, -84, 52, 9, -266, 1024, -2680, 9036, 26516, -6016, 3021,
     -1571, 848, -365, 107, 10, -16, 17, -8, 3, -1],
    [0, 0, 0, -2, 0, 3, -19, 60, -75, 162, -227, 306, -67, -615, 3229, 29883, -4532, 2488, -1471,
     882, -424, 166, -27, 5, 6, -8, 3, -1, 0],
    [0, 0, -1, 3, -2, -5, 31, -74, 179, -402, 689, -926, 1272, -1446, 31033, -1446, 1272, -926, 689,
     -402, 179, -74, 31, -5, -2, 3, -1, 0, 0],
    [0, -1, 3, -8, 6, 5, -27, 166, -424, 882, -1471, 2488, -4532, 29883, 3229, -615, -67, 306, -227,
     162, -75, 60, -19, 3, 0, -2, 0, 0, 0],
    [-1, 3, -8, 17, -16, 10, 107, -365, 848, -1571, 3021, -6016, 26516, 9036, -2680, 1024, -266, 9,
     52, -84, 65, -34, 10, -1, 0, 1, 0, 0, 0],
    [2, -8, 16, -35, 43, 26, -235, 635, -1352, 2810, -5882, 21472, 15367, -4681, 2062, -839, 347,
     -68, -23, 70, -35, 17, -5, 0, 0, 0, 0, 0, 0],
    [-5, 17, -35, 70, -23, -68, 347, -839, 2062, -4681, 15367, 21472, -5882, 2810, -1352, 635, -235,
     26, 43, -35, 16, -8, 2, 0, 0, 0, 0, 0, 0],
]

# Las tablas, comprobadas antes de escribir nada: si una se hubiera copiado mal, el sonido saldría
# con la ganancia o la fase equivocadas y costaría mucho más darse cuenta que aquí.
for _i, _t in enumerate(TABLAS, 1):
    if len(_t) != 29:
        sys.exit('la tabla %d tiene %d coeficientes, no 29' % (_i, len(_t)))
    if not 0.900 < sum(_t) / 0x8000 < 0.912:
        sys.exit('la tabla %d tiene una ganancia en continua de %.4f, fuera de ~0,906'
                 % (_i, sum(_t) / 0x8000))
if TABLAS[2] != TABLAS[2][::-1]:
    sys.exit('la tabla central (3) no es simetrica')

FIRMA = 'xa_zigzag_table'


def c_tabla(tab):
    return '{ ' + ', '.join(('-' if v < 0 else '') + '0x%04X' % abs(v) for v in tab) + ' }'


NUEVO = '''/* XA 37800/18900 Hz -> 44100 Hz exactly as the CD controller does it: the 25-point "zigzag" interpolation documented
 * in psx-spx ("CDROM XA Audio ADPCM Compression"). Every 6 input samples go into a 32-entry ring and produce 7 output
 * samples, one per table (29 taps each, /0x8000). 18900 Hz streams feed each sample twice. The ring and the phase
 * persist across sectors -- the hardware filters the continuous stream -- and reset with the XA decoder. This replaces
 * the previous 2-point linear interpolation, which let the 37.8 kHz images alias back into the audible band and
 * restarted at every sector (an 18.75 Hz seam). */
static const int16_t xa_zigzag_table[7][29] = {
''' + ',\n'.join('    ' + c_tabla(t) for t in TABLAS) + '''
};
static int16_t xa_zigzag_ring[2][32];
static uint32_t xa_zigzag_pos = 0;
static int xa_zigzag_six = 6;

static void xa_zigzag_reset(void) {
    memset(xa_zigzag_ring, 0, sizeof(xa_zigzag_ring));
    xa_zigzag_pos = 0;
    xa_zigzag_six = 6;
}

static int16_t xa_zigzag_tap(const int16_t *ring, uint32_t p, const int16_t *table) {
    int32_t sum = 0;
    for (int i = 1; i <= 29; i++)
        sum += (int32_t)ring[(p - (uint32_t)i) & 0x1Fu] * (int32_t)table[i - 1];
    return clamp16_cd(sum >> 15);
}

static int xa_resample_to_44100(const int16_t* in, int in_frames,
                                int sample_rate, int16_t* out, int max_frames) {
    if (!in || !out || in_frames <= 0 || sample_rate <= 0 || max_frames <= 0) return 0;
    const int reps = (sample_rate == 18900) ? 2 : 1;
    int out_frames = 0;

    for (int i = 0; i < in_frames; i++) {
        for (int r = 0; r < reps; r++) {
            xa_zigzag_ring[0][xa_zigzag_pos & 0x1Fu] = in[i * 2 + 0];
            xa_zigzag_ring[1][xa_zigzag_pos & 0x1Fu] = in[i * 2 + 1];
            xa_zigzag_pos++;
            if (--xa_zigzag_six == 0) {
                xa_zigzag_six = 6;
                for (int t = 0; t < 7 && out_frames < max_frames; t++) {
                    out[out_frames * 2 + 0] = xa_zigzag_tap(xa_zigzag_ring[0], xa_zigzag_pos, xa_zigzag_table[t]);
                    out[out_frames * 2 + 1] = xa_zigzag_tap(xa_zigzag_ring[1], xa_zigzag_pos, xa_zigzag_table[t]);
                    out_frames++;
                }
            }
        }
    }

    return out_frames;
}'''

# El reinicio del filtro va junto al del decodificador XA, y su declaracion antes del uso.
RESET_ANCLA = ('static void xa_reset_decode(void) {\n'
               '    xa_hist_l[0] = xa_hist_l[1] = 0;')
RESET_NUEVO = ('static void xa_zigzag_reset(void);\n\n'
               'static void xa_reset_decode(void) {\n'
               '    xa_zigzag_reset();\n'
               '    xa_hist_l[0] = xa_hist_l[1] = 0;')


def main():
    cdrom = parchear.runtime(parchear.raiz(), 'src', 'cdrom.c')
    with open(cdrom, 'rb') as f:
        crudo = f.read().decode('utf-8')
    eol = '\r\n' if '\r\n' in crudo else '\n'
    src = crudo.replace('\r\n', '\n')

    if FIRMA in src:
        print('el parche ya estaba')
        return 0

    # La funcion lineal entera, de su firma a su «return out_frames;}»: es lo que se sustituye.
    firma_vieja = 'static int xa_resample_to_44100(const int16_t* in, int in_frames,'
    if src.count(firma_vieja) != 1:
        sys.exit('cdrom.c: %d apariciones de xa_resample_to_44100 (el arbol no es el esperado)'
                 % src.count(firma_vieja))
    ini = src.index(firma_vieja)
    cierre = 'return out_frames;\n}'
    if cierre not in src[ini:]:
        sys.exit('cdrom.c: no encuentro el final de xa_resample_to_44100')
    fin = src.index(cierre, ini) + len(cierre)
    viejo = src[ini:fin]
    if '/ 44100' not in viejo or 'phase' not in viejo:
        sys.exit('cdrom.c: xa_resample_to_44100 no es la version lineal que este parche sustituye')
    src = src[:ini] + NUEVO + src[fin:]

    if src.count(RESET_ANCLA) != 1:
        sys.exit('cdrom.c: %d apariciones de xa_reset_decode' % src.count(RESET_ANCLA))
    src = src.replace(RESET_ANCLA, RESET_NUEVO, 1)

    if '#include <string.h>' not in src:
        src = src.replace('#include', '#include <string.h>\n#include', 1)

    tmp = cdrom + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(src.replace('\n', eol).encode('utf-8'))
    os.replace(tmp, cdrom)
    print('cdrom.c: remuestreo XA zigzag (7 tablas de 29 coeficientes, sumas %s)'
          % ' '.join(hex(sum(t)) for t in TABLAS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
