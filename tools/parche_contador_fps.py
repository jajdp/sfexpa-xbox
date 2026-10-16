# -*- coding: utf-8 -*-
# Contador de FPS en pantalla, en psxrecomp/runtime/src/main.cpp. En una consola no hay barra de título, que es
# donde el runtime escribe «[60 fps 1.00x]», así que no hay forma de saber a qué velocidad va el juego mientras se
# juega. El contador dibuja ese mismo valor (los cuadros de la PS1 emulados en el último segundo, el de
# la línea [FPS] del registro) con rectángulos de SDL, después de copiar el cuadro y antes de presentarlo:
#  - arriba a la izquierda, en el margen del 16:9 (en las peleas, fondo del escenario; el marcador va en el centro 4:3);
#  - cifras de 3x5 en celdas de 3 px lógicos («60 FPS»), sobre un recuadro negro translúcido;
#  - verde con 59 o más, amarillo de 55 a 58 y rojo por debajo de 55.
# Lo gobierna el mismo ajuste que el del título, [video] show_fps de settings.toml (true de fábrica). Solo en el camino
# de presentación de SDL_Renderer (el de la consola, renderizador por software); el OpenGL del PC sigue con el título.
# Los comentarios del código van en inglés, como el resto del runtime. Cada cambio tiene una firma: si ya está, se salta.
# Todo o nada; atómico; conserva el fin de línea.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

R = parchear.runtime(parchear.raiz())
MAIN = r'src\main.cpp'

FUNCION = '''/* Recompilaciones (2026-10-03): on-screen FPS counter (Xbox has no title bar for
 * "[60 fps 1.00x]"). Draws the last whole-second emulated-vblank rate in the top-left
 * corner with SDL rects (3x5 cell font), after the frame copy and before present.
 * Governed by [video] show_fps, like the title-bar readout. */
static double g_fps_overlay_value = 0.0;

static void fps_overlay_draw(void) {
    static const unsigned char GLYPHS[13][5] = {
        {7,5,5,5,7}, {2,6,2,2,7}, {7,1,7,4,7}, {7,1,7,1,7}, {5,5,7,1,1},   /* 0-4 */
        {7,4,7,1,7}, {7,4,7,5,7}, {7,1,1,1,1}, {7,5,7,5,7}, {7,5,7,1,7},   /* 5-9 */
        {7,4,7,4,4}, {7,5,7,4,4}, {7,4,7,1,7},                             /* F P S */
    };
    char text[16];
    int v = (int)(g_fps_overlay_value + 0.5);
    if (v < 0) v = 0;
    if (v > 999) v = 999;
    snprintf(text, sizeof text, "%d FPS", v);
    const int cell = 3, adv = 4 * cell, margin = 6, pad = 4;
    const int n = (int)strlen(text);
    SDL_Rect box = { margin, margin, n * adv - cell + 2 * pad, 5 * cell + 2 * pad };
    SDL_Rect px[16 * 15];
    int count = 0;
    for (int i = 0; i < n; i++) {
        const char c = text[i];
        int g = -1;
        if (c >= '0' && c <= '9') g = c - '0';
        else if (c == 'F') g = 10;
        else if (c == 'P') g = 11;
        else if (c == 'S') g = 12;
        if (g < 0) continue;
        for (int row = 0; row < 5; row++) {
            for (int col = 0; col < 3; col++) {
                if (!(GLYPHS[g][row] & (4 >> col))) continue;
                if (count >= (int)(sizeof px / sizeof px[0])) break;
                px[count].x = box.x + pad + i * adv + col * cell;
                px[count].y = box.y + pad + row * cell;
                px[count].w = cell;
                px[count].h = cell;
                count++;
            }
        }
    }
    SDL_SetRenderDrawBlendMode(sdl_renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(sdl_renderer, 0, 0, 0, 150);
    SDL_RenderFillRect(sdl_renderer, &box);
    if (v >= 59)      SDL_SetRenderDrawColor(sdl_renderer, 0x50, 0xFF, 0x50, 0xFF);
    else if (v >= 55) SDL_SetRenderDrawColor(sdl_renderer, 0xFF, 0xE0, 0x40, 0xFF);
    else              SDL_SetRenderDrawColor(sdl_renderer, 0xFF, 0x50, 0x40, 0xFF);
    SDL_RenderFillRects(sdl_renderer, px, count);
    /* SDL_RenderClear of the next frame uses the current draw color: back to opaque black. */
    SDL_SetRenderDrawBlendMode(sdl_renderer, SDL_BLENDMODE_NONE);
    SDL_SetRenderDrawColor(sdl_renderer, 0, 0, 0, 0xFF);
}

static void sdl_vblank_present(void) {'''

CAMBIOS = [
    (MAIN, 'static void fps_overlay_draw(void)', 'static void sdl_vblank_present(void) {', FUNCION),
    (MAIN, 'g_fps_overlay_value = fps;',
     '            const double speed = fps / 59.94;\n',
     '            const double speed = fps / 59.94;\n'
     '            g_fps_overlay_value = fps;   /* Recompilaciones: on-screen counter */\n'),
    (MAIN, 'if (g_show_fps) fps_overlay_draw();',
     '    SDL_RenderCopy(sdl_renderer, sdl_texture, &src, &dst);\n',
     '    SDL_RenderCopy(sdl_renderer, sdl_texture, &src, &dst);\n'
     '    if (g_show_fps) fps_overlay_draw();   /* Recompilaciones: on-screen FPS counter */\n'),
]

if __name__ == '__main__':
    parchear.informe(parchear.aplicar(R, CAMBIOS))
