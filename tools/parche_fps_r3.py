# -*- coding: utf-8 -*-
# R3 (pulsar el stick derecho) enciende y apaga el contador de FPS (parche_contador_fps.py), para poder dejarlo
# apagado mientras se juega. SELECT sería el botón natural, pero **sí** tiene función —en el modo entrenamiento
# reinicia las posiciones y repite la jugada, como dicen sus propias cadenas—, así que se usa R3, que queda libre: el mando va fijado en modo digital
# ([controller] default_mode = "digital", lock_mode = true) y ahí los clics de los sticks del DualShock no existen,
# de modo que el juego nunca ve ese botón. Vale también desde el teclado, donde R3 es la tecla Y (psx_keybinds), que
# tampoco se usa para jugar: así se puede comprobar sin mando.
#
# Alterna la misma variable que gobierna los dos avisos de FPS (parche_contador_fps.py): la barra de título en el PC
# y el contador en pantalla en la consola. Es un cambio en caliente: no se escribe en settings.toml, así que al
# arrancar vuelve a mandar [video] show_fps.
#
# ⚠ Dónde va la comprobación: sobre la palabra de botones YA COMBINADA del jugador 1, justo antes de entregarla al
# SIO. Puesta antes, dentro de pad_buttons_for(), se perdía el caso más común de la compilación de prueba: cuando el
# jugador 1 no tiene dispositivo asignado, esa función ni se llama y los botones salen del teclado y de todos los
# mandos conectados. El mando virtual del servidor de depuración NO pasa por aquí (apply_input_override_to_sio corta
# antes), de modo que pulsar «r3» con dbg.py no cambia nada: hace falta el mando o el teclado de verdad.
# Se mira el flanco de bajada (en esa palabra, 0 = pulsado).
# Los comentarios del código van en inglés, como el resto del runtime. Idempotente: con la firma presente, se salta.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

R = parchear.runtime(parchear.raiz())
MAIN = r'src\main.cpp'

ANCLA_FUNCION = 'static void sample_pad_into_sio(int override) {'
FUNCION = '''/* Recompilaciones (2026-10-04): R3 toggles the FPS readout — the title bar on the
 * PC and the on-screen counter on the Xbox (fps_overlay_draw). The game never sees
 * R3: the pad is pinned to digital mode, where the DualShock stick clicks do not
 * exist, so the button is free. Works from the keyboard too (Y is R3 there).
 * Edge-triggered on player 1's combined button word; the new state is not written
 * back to settings.toml, so [video] show_fps rules again on restart. */
#define PSXGP_BIT_R3_FPS (1u << 2)   /* same bit as PSXGP_BIT_R3 in psx_gamepad_binds.c */

static void fps_toggle_from_pad(uint16_t word) {
    static bool held = false;
    const bool down = (word & PSXGP_BIT_R3_FPS) == 0;   /* pad word: 0 = pressed */
    if (down && !held) g_show_fps = !g_show_fps;
    held = down;
}

static void sample_pad_into_sio(int override) {'''

ANCLA_LLAMADA = '        sio_set_pad_state_slot(s, btn);'
LLAMADA = '''        if (s == 0) fps_toggle_from_pad(btn);   /* Recompilaciones: R3 toggles the FPS readout */
        sio_set_pad_state_slot(s, btn);'''

# Versiones anteriores de este parche, que metían la comprobación dentro de pad_buttons_for().
V_ANTES = '''/* Recompilaciones (2026-10-04): R3 toggles the FPS readout — the title bar on the
 * PC and the on-screen counter on the Xbox (fps_overlay_draw). The game never sees
 * R3: the pad is pinned to digital mode, where the DualShock stick clicks do not
 * exist, so the button is free. Works from the keyboard too (Y is R3 there).
 * Edge-triggered on player 1; the new state is not written back to settings.toml,
 * so [video] show_fps rules again on restart. */
#define PSXGP_BIT_R3_FPS (1u << 2)   /* same bit as PSXGP_BIT_R3 in psx_gamepad_binds.c */

static void fps_toggle_from_pad(uint16_t word) {
    static bool held = false;
    const bool down = (word & PSXGP_BIT_R3_FPS) == 0;   /* pad word: 0 = pressed */
    if (down && !held) g_show_fps = !g_show_fps;
    held = down;
}

static uint16_t pad_buttons_for(const PlayerInput& p, int player, bool suppress_stick_axes) {
    uint16_t word = 0xFFFF;
    if (p.kind == 1)      word = pad_from_keyboard(player);
    else if (p.kind == 2) word = psx_gamepad_binds_pad_word(p.handle, player, suppress_stick_axes ? 1 : 0);
    if (player == 1) fps_toggle_from_pad(word);   /* Recompilaciones: R3 toggles the FPS readout */
    return word;
}'''
V_LIMPIO = '''static uint16_t pad_buttons_for(const PlayerInput& p, int player, bool suppress_stick_axes) {
    if (p.kind == 1) return pad_from_keyboard(player);
    if (p.kind == 2) return psx_gamepad_binds_pad_word(p.handle, player, suppress_stick_axes ? 1 : 0);
    return 0xFFFF;
}'''

CAMBIOS = [
    (MAIN, 'fps_toggle_from_pad(uint16_t word)', ANCLA_FUNCION, FUNCION),
    (MAIN, 'if (s == 0) fps_toggle_from_pad(btn);', ANCLA_LLAMADA, LLAMADA),
]
PREVIOS = [(MAIN, V_ANTES, V_LIMPIO)]

if __name__ == '__main__':
    parchear.informe(parchear.aplicar(R, CAMBIOS, PREVIOS))
