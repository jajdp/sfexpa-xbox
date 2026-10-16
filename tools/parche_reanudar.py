# -*- coding: utf-8 -*-
# «Reanudar tras la terminación», en psxrecomp/runtime/src/ (savestate.h, savestate.c y main.cpp).
# En el modo desarrollador de la Xbox, la consola TERMINA un juego UWP que pasa a segundo plano (y una app de más de
# 128 MB), así que al volver de Home el juego empieza de cero
# (Microsoft: «Games will be suspended and terminated in the background»). Este parche guarda la máquina entera cuando
# la ventana se oculta, se minimiza o pierde el foco —la app sigue corriendo unos segundos antes de suspenderse, y una
# vez suspendida CoreDispatcher::ProcessEvents no vuelve, así que ya no se podría— y la restaura cuando el sistema
# relanza la app tras terminarla (PreviousExecutionState == Terminated, que pone la entrada UWP en
# g_psx_prev_exec_state). Cualquier otro arranque descarta el estado guardado: era de una sesión que terminó bien.
# Los guardados esperan a que el juego haya empezado y a que una restauración pendiente termine (la ventana nace oculta,
# y un guardado junto con una carga se ejecutaría antes y la pisaría). Necesita parche_estado_guardado.py.
#  - savestate.h/.c: la ranura SAVESTATE_SLOT_SUSPEND (99), con su archivo state_<entrada>_suspend.pst junto a las
#    tarjetas, savestate_slot_exists y savestate_slot_discard.
#  - main.cpp: resume_state_note_background (en el bucle de eventos de SDL) y resume_state_maybe_restore (tras
#    savestate_configure). En el PC está apagado salvo PSX_RESUME_STATE=1; PSX_PREV_EXEC_STATE=<n> simula el
#    relanzamiento (3 = Terminated).
# Comentarios en inglés, como el runtime. Cada cambio tiene una firma: si ya está, se salta. Todo o nada; atómico.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

R = parchear.runtime(parchear.raiz())
MAIN = r'src\main.cpp'
MARCA = 'Xbox port (2026-10-03): resume after termination'

# La primera versión de este parche (2026-10-03, sin las esperas ni el descarte): si está en main.cpp, se cambia por la
# actual antes de nada.
AYUDANTES_V1 = '''/* ''' + MARCA + '''. In Dev Mode the console terminates a UWP
 * game sent to the background (and an app above 128 MB), so coming back from Home relaunched it
 * from scratch. The whole machine is saved when the window is hidden, minimized or loses focus —
 * the app still runs for a few seconds before it is suspended, and once it is, CoreDispatcher::
 * ProcessEvents never returns, so nothing could be saved then — and restored when the system
 * relaunches the app after terminating it (PreviousExecutionState == Terminated, set by the UWP
 * entry). PC: off unless PSX_RESUME_STATE=1; PSX_PREV_EXEC_STATE=<n> simulates the relaunch. */
extern "C" { int g_psx_prev_exec_state = -1; }   /* ApplicationExecutionState; 3 = Terminated */

static int resume_state_enabled(void) {
    static int s = -1;
    if (s < 0) {
#if defined(WINAPI_FAMILY) && (WINAPI_FAMILY == WINAPI_FAMILY_APP)
        s = 1;
#else
        const char *e = std::getenv("PSX_RESUME_STATE");
        s = (e && e[0] && e[0] != '0') ? 1 : 0;
#endif
    }
    return s;
}

static void resume_state_note_background(int window_event) {
    static Uint64 last = 0;
    if (!resume_state_enabled()) return;
    const Uint64 now = SDL_GetTicks64();
    if (last && now - last < 2000) return;   /* hidden + focus-lost arrive together */
    last = now;
    if (savestate_request_save(SAVESTATE_SLOT_SUSPEND))
        std::fprintf(stderr, "resume: window event %d -> saving the machine for a relaunch\\n",
                     window_event);
}

static void resume_state_maybe_restore(void) {
    if (!resume_state_enabled()) return;
    int prev = g_psx_prev_exec_state;
#if !(defined(WINAPI_FAMILY) && (WINAPI_FAMILY == WINAPI_FAMILY_APP))
    if (const char *e = std::getenv("PSX_PREV_EXEC_STATE")) prev = std::atoi(e);
#endif
    const int have = savestate_slot_exists(SAVESTATE_SLOT_SUSPEND);
    std::fprintf(stderr, "resume: previous execution state %d, saved machine %s\\n",
                 prev, have ? "present" : "absent");
    if (prev == 3 && have && savestate_request_load(SAVESTATE_SLOT_SUSPEND))
        std::fprintf(stderr, "resume: terminated in the background -> restoring the saved machine\\n");
}

static void sdl_vblank_present(void) {
'''

AYUDANTES = '''/* ''' + MARCA + '''. In Dev Mode the console terminates a UWP
 * game sent to the background (and an app above 128 MB), so coming back from Home relaunched it
 * from scratch. The whole machine is saved when the window is hidden, minimized or loses focus —
 * the app still runs for a few seconds before it is suspended, and once it is, CoreDispatcher::
 * ProcessEvents never returns, so nothing could be saved then — and restored when the system
 * relaunches the app after terminating it (PreviousExecutionState == Terminated, set by the UWP
 * entry). Any other start discards the saved machine: it belongs to a session that ended. Saves
 * wait for the game to have started and for a pending restore to land (the window is created
 * hidden, and a save staged together with a load would run first and overwrite it). PC: off
 * unless PSX_RESUME_STATE=1; PSX_PREV_EXEC_STATE=<n> simulates the relaunch. */
extern "C" { int g_psx_prev_exec_state = -1; }   /* ApplicationExecutionState; 3 = Terminated */
static Uint64 g_resume_quiet_until = 0;          /* no background saves before this tick */

static int resume_state_enabled(void) {
    static int s = -1;
    if (s < 0) {
#if defined(WINAPI_FAMILY) && (WINAPI_FAMILY == WINAPI_FAMILY_APP)
        s = 1;
#else
        const char *e = std::getenv("PSX_RESUME_STATE");
        s = (e && e[0] && e[0] != '0') ? 1 : 0;
#endif
    }
    return s;
}

static void resume_state_note_background(int window_event) {
    static Uint64 last = 0;
    if (!resume_state_enabled()) return;
    const Uint64 now = SDL_GetTicks64();
    if (!fntrace_is_game_started() || now < g_resume_quiet_until) return;
    if (last && now - last < 2000) return;   /* hidden + focus-lost arrive together */
    last = now;
    if (savestate_request_save(SAVESTATE_SLOT_SUSPEND))
        std::fprintf(stderr, "resume: window event %d -> saving the machine for a relaunch\\n",
                     window_event);
}

static void resume_state_maybe_restore(void) {
    if (!resume_state_enabled()) return;
    int prev = g_psx_prev_exec_state;
#if !(defined(WINAPI_FAMILY) && (WINAPI_FAMILY == WINAPI_FAMILY_APP))
    if (const char *e = std::getenv("PSX_PREV_EXEC_STATE")) prev = std::atoi(e);
#endif
    const int have = savestate_slot_exists(SAVESTATE_SLOT_SUSPEND);
    std::fprintf(stderr, "resume: previous execution state %d, saved machine %s\\n",
                 prev, have ? "present" : "absent");
    g_resume_quiet_until = SDL_GetTicks64() + 5000;
    if (prev == 3 && have) {
        if (savestate_request_load(SAVESTATE_SLOT_SUSPEND)) {
            g_resume_quiet_until = SDL_GetTicks64() + 15000;   /* let the restore land first */
            std::fprintf(stderr, "resume: terminated in the background -> restoring the saved machine\\n");
        }
    } else if (have) {
        savestate_slot_discard(SAVESTATE_SLOT_SUSPEND);
        std::fprintf(stderr, "resume: the last session ended normally -> saved machine discarded\\n");
    }
}

static void sdl_vblank_present(void) {
'''

CAMBIOS = [
    (r'include\savestate.h', '#define SAVESTATE_SLOT_SUSPEND 99',
     '#define SAVESTATE_SLOTS 12\n',
     '#define SAVESTATE_SLOTS 12\n'
     '/* ' + MARCA + ': a slot outside F1-F12, saved when the\n'
     ' * window goes to the background and restored after the system terminated the app. */\n'
     '#define SAVESTATE_SLOT_SUSPEND 99\n'),
    (r'include\savestate.h', 'int savestate_slot_exists(int slot);',
     'void savestate_poll(CPUState* cpu, uint32_t resume_pc);\n',
     'void savestate_poll(CPUState* cpu, uint32_t resume_pc);\n\n'
     '/* ' + MARCA + ': 1 if the slot\'s state file exists. */\n'
     'int savestate_slot_exists(int slot);\n'),
    (r'include\savestate.h', 'int savestate_slot_discard(int slot);',
     'int savestate_slot_exists(int slot);\n',
     'int savestate_slot_exists(int slot);\n'
     '/* ' + MARCA + ': removes the slot\'s state file. */\n'
     'int savestate_slot_discard(int slot);\n'),
    (r'src\savestate.c', 'state_%08X_suspend.pst',
     'static int slot_path(int slot, char* out, size_t cap) {\n'
     '    if (slot < 0 || slot >= SAVESTATE_SLOTS) return 0;\n',
     'static int slot_path(int slot, char* out, size_t cap) {\n'
     '    if (slot == SAVESTATE_SLOT_SUSPEND) {   /* ' + MARCA + ' */\n'
     '        snprintf(out, cap, "%s%sstate_%08X_suspend.pst",\n'
     '                 s_dir, (s_dir[0] ? "/" : ""), (unsigned)s_entry_pc);\n'
     '        return 1;\n'
     '    }\n'
     '    if (slot < 0 || slot >= SAVESTATE_SLOTS) return 0;\n'),
    (r'src\savestate.c',
     'int savestate_request_save(int slot) {\n'
     '    if (!s_configured) { fprintf(stderr, "savestate: not configured\\n"); return 0; }\n'
     '    if ((slot < 0 || slot >= SAVESTATE_SLOTS) && slot != SAVESTATE_SLOT_SUSPEND)',
     'int savestate_request_save(int slot) {\n'
     '    if (!s_configured) { fprintf(stderr, "savestate: not configured\\n"); return 0; }\n'
     '    if (slot < 0 || slot >= SAVESTATE_SLOTS) return 0;\n',
     'int savestate_request_save(int slot) {\n'
     '    if (!s_configured) { fprintf(stderr, "savestate: not configured\\n"); return 0; }\n'
     '    if ((slot < 0 || slot >= SAVESTATE_SLOTS) && slot != SAVESTATE_SLOT_SUSPEND) return 0;\n'),
    (r'src\savestate.c',
     'int savestate_request_load(int slot) {\n'
     '    if (!s_configured) { fprintf(stderr, "savestate: not configured\\n"); return 0; }\n'
     '    if ((slot < 0 || slot >= SAVESTATE_SLOTS) && slot != SAVESTATE_SLOT_SUSPEND)',
     'int savestate_request_load(int slot) {\n'
     '    if (!s_configured) { fprintf(stderr, "savestate: not configured\\n"); return 0; }\n'
     '    if (slot < 0 || slot >= SAVESTATE_SLOTS) return 0;\n',
     'int savestate_request_load(int slot) {\n'
     '    if (!s_configured) { fprintf(stderr, "savestate: not configured\\n"); return 0; }\n'
     '    if ((slot < 0 || slot >= SAVESTATE_SLOTS) && slot != SAVESTATE_SLOT_SUSPEND) return 0;\n'),
    (r'src\savestate.c', 'int savestate_slot_exists(int slot) {',
     'void savestate_poll(CPUState* cpu, uint32_t resume_pc) {\n',
     '/* ' + MARCA + ' */\n'
     'int savestate_slot_exists(int slot) {\n'
     '    char path[600];\n'
     '    if (!s_configured || !slot_path(slot, path, sizeof(path))) return 0;\n'
     '    FILE* f = fopen(path, "rb");\n'
     '    if (!f) return 0;\n'
     '    fclose(f);\n'
     '    return 1;\n'
     '}\n\n'
     'void savestate_poll(CPUState* cpu, uint32_t resume_pc) {\n'),
    (r'src\savestate.c', 'int savestate_slot_discard(int slot) {',
     '    FILE* f = fopen(path, "rb");\n'
     '    if (!f) return 0;\n'
     '    fclose(f);\n'
     '    return 1;\n'
     '}\n',
     '    FILE* f = fopen(path, "rb");\n'
     '    if (!f) return 0;\n'
     '    fclose(f);\n'
     '    return 1;\n'
     '}\n\n'
     '/* ' + MARCA + ' */\n'
     'int savestate_slot_discard(int slot) {\n'
     '    char path[600];\n'
     '    if (!s_configured || !slot_path(slot, path, sizeof(path))) return 0;\n'
     '    return remove(path) == 0;\n'
     '}\n'),
    (r'src\main.cpp', 'static Uint64 g_resume_quiet_until',
     'static void sdl_vblank_present(void) {\n', AYUDANTES),
    (r'src\main.cpp', 'resume_state_note_background(ev.window.event);',
     '            } else if (ev.type == SDL_KEYDOWN) {\n'
     '                const Uint16 mod = ev.key.keysym.mod;\n',
     '            } else if (ev.type == SDL_WINDOWEVENT &&\n'
     '                       (ev.window.event == SDL_WINDOWEVENT_HIDDEN ||\n'
     '                        ev.window.event == SDL_WINDOWEVENT_MINIMIZED ||\n'
     '                        ev.window.event == SDL_WINDOWEVENT_FOCUS_LOST)) {\n'
     '                resume_state_note_background(ev.window.event);   /* ' + MARCA + ' */\n'
     '            } else if (ev.type == SDL_KEYDOWN) {\n'
     '                const Uint16 mod = ev.key.keysym.mod;\n'),
    (r'src\main.cpp', 'resume_state_maybe_restore();   /*',
     '        savestate_configure(memcard_dir.string().c_str(),\n'
     '                            memory_get_bios_checksum(), game_entry_pc);\n'
     '    }\n',
     '        savestate_configure(memcard_dir.string().c_str(),\n'
     '                            memory_get_bios_checksum(), game_entry_pc);\n'
     '        resume_state_maybe_restore();   /* ' + MARCA + ' */\n'
     '    }\n'),
]


if __name__ == '__main__':
    parchear.informe(parchear.aplicar(
        R, CAMBIOS, [(MAIN, AYUDANTES_V1, AYUDANTES)]))
