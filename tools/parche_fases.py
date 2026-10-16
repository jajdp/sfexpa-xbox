# -*- coding: utf-8 -*-
# Reparto del tiempo del hilo del emulador en el registro de la consola (psxrecomp/runtime/src/main.cpp):
# un hilo muestrea ~1000 veces por segundo la fase que corre el hilo del juego
# (psx_exec_phase(): 0 = otro (el ejecutable compilado y el anfitrión: presentar, sonido…), 1 = intérprete,
# 2 = overlay nativo, 3 = overlay estático, 4 = GP0, el dibujo de la GPU) y la línea [FPS] de cada segundo añade las
# cuotas del último segundo: «… | phase other 0.12 interp 0.10 native 0.00 static 0.66 gp0 0.12 (n=987)».
# Es el perfilador de fases del servidor de depuración (debug_server.c, phase_profile), que en la consola no existe.
# Sirve para saber, con el juego del usuario, si una caída de FPS es el dibujo, el código del juego o el intérprete.
# Cuesta un hilo que duerme 1 ms entre muestras. Los comentarios del código van en inglés, como el resto del runtime.
# Cada cambio tiene una firma: si ya está, se salta. Todo o nada; atómico; conserva el fin de línea.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

R = parchear.runtime(parchear.raiz())
MAIN = r'src\main.cpp'

SAMPLER = '''/* Recompilaciones (2026-10-03): per-second wall-time phase shares of the emu thread,
 * appended to the [FPS] line (the debug server's phase_profile is not in the Xbox build).
 * A ~1 kHz sampler thread reads psx_exec_phase(): 0 other (main-exe code + host work),
 * 1 interpreter, 2 native overlay, 3 static overlay, 4 GP0 rasterization. */
extern "C" int psx_exec_phase(void);
static volatile uint32_t s_phase_cnt[5];
static volatile uint32_t s_phase_tot;
#ifdef _WIN32
static DWORD WINAPI phase_log_sampler(LPVOID) {
    for (;;) {
        Sleep(1);
        int p = psx_exec_phase();
        if (p < 0 || p > 4) p = 0;
        s_phase_cnt[p]++;
        s_phase_tot++;
    }
}
#endif

static void sdl_vblank_present(void) {'''

LINEA_V = '''            std::fprintf(stderr, "[FPS] game: %.1f fps (%.2fx) | frames: %llu\\n",
                         fps, speed, (unsigned long long)s_frame_count);'''
LINEA_N = '''            {   /* Recompilaciones: phase shares of the last second */
                static bool ph_started = false;
                static uint32_t ph_last[5], ph_last_tot;
#ifdef _WIN32
                if (!ph_started) {
                    ph_started = true;
                    HANDLE ph = CreateThread(NULL, 0, phase_log_sampler, NULL, 0, NULL);
                    if (ph) CloseHandle(ph);
                }
#endif
                uint32_t c[5], tot = s_phase_tot;
                for (int i = 0; i < 5; i++) { c[i] = s_phase_cnt[i] - ph_last[i]; ph_last[i] = s_phase_cnt[i]; }
                const uint32_t n = tot - ph_last_tot;
                ph_last_tot = tot;
                const double d = n ? (double)n : 1.0;
                std::fprintf(stderr, "[FPS] game: %.1f fps (%.2fx) | frames: %llu | phase other %.2f interp %.2f "
                             "native %.2f static %.2f gp0 %.2f (n=%u)\\n",
                             fps, speed, (unsigned long long)s_frame_count,
                             c[0] / d, c[1] / d, c[2] / d, c[3] / d, c[4] / d, n);
            }'''

CAMBIOS = [
    (MAIN, 'static DWORD WINAPI phase_log_sampler(LPVOID)', 'static void sdl_vblank_present(void) {', SAMPLER),
    (MAIN, 'Recompilaciones: phase shares of the last second', LINEA_V, LINEA_N),
]

if __name__ == '__main__':
    parchear.informe(parchear.aplicar(R, CAMBIOS))
