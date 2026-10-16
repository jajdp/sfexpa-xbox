# -*- coding: utf-8 -*-
# GP0 sin los registros de depuración en la compilación que no los lleva (psxrecomp/runtime/src/gpu.c).
# gp0_execute_command apuntaba cada orden de la GPU en un
# anillo de 1 048 576 entradas (gp0_ring_record: unos 120 MB, con la dirección de retorno del juego) y cada primitiva
# en un censo de 2 097 152 (ws_census_record: 48 MB, con dos lecturas de la memoria del juego). Los dos solo los lee
# el servidor de depuración (gpu_frame_dump, ws_census), que la versión de Xbox no lleva (PSX_NO_DEBUG_TOOLS): ahí
# solo costaban tiempo y memoria en cada orden. Medido en la xbox series cuarto el 2026-10-03 (registro de fases): el
# dibujo de la GPU era el 26-32 % del cuadro en las peleas en 16:9. Se conserva lo que sí usa el modo ancho
# (ws_bg_phase_note, ws_note_overhang). Los comentarios del código van en inglés, como el resto del runtime.
# Cada cambio tiene una firma: si ya está, se salta. Todo o nada; atómico; conserva el fin de línea.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

R = parchear.runtime(parchear.raiz(), 'src')
GPU = 'gpu.c'

CAMBIOS = [
    (GPU, 'Recompilaciones (2026-10-03): debug-only GP0 ring',
     '''    gp0_opcode_count[opcode]++;
    gp0_ring_record(gp0_cmd_buf, gp0_words_needed);
''',
     '''    gp0_opcode_count[opcode]++;
#ifndef PSX_NO_DEBUG_TOOLS
    /* Recompilaciones (2026-10-03): debug-only GP0 ring — only the debug server reads it. */
    gp0_ring_record(gp0_cmd_buf, gp0_words_needed);
#endif
'''),
    (GPU, 'Recompilaciones (2026-10-03): debug-only draw census',
     '''    if (opcode >= 0x20 && opcode <= 0x7F) {
        int32_t cvx, cvy;
        parse_vertex(gp0_cmd_buf[1], &cvx, &cvy);
        ws_census_record(opcode, cvx, cvy);
        ws_note_overhang(opcode);   /* 2D-only-scene classifier world signal */
    }''',
     '''    if (opcode >= 0x20 && opcode <= 0x7F) {
#ifndef PSX_NO_DEBUG_TOOLS
        /* Recompilaciones (2026-10-03): debug-only draw census — only the debug server reads it. */
        int32_t cvx, cvy;
        parse_vertex(gp0_cmd_buf[1], &cvx, &cvy);
        ws_census_record(opcode, cvx, cvy);
#endif
        ws_note_overhang(opcode);   /* 2D-only-scene classifier world signal */
    }'''),
    (GPU, 'Recompilaciones (2026-10-03): debug-only polyline record',
     '''        uint32_t hdr_only[1] = { val };
        gp0_ring_record(hdr_only, 1);''',
     '''#ifndef PSX_NO_DEBUG_TOOLS
        /* Recompilaciones (2026-10-03): debug-only polyline record. */
        uint32_t hdr_only[1] = { val };
        gp0_ring_record(hdr_only, 1);
#endif'''),
]

if __name__ == '__main__':
    parchear.informe(parchear.aplicar(R, CAMBIOS))
