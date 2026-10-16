# -*- coding: utf-8 -*-
# psxrecomp (el framework del juego, en psxrecomp/): cargar un estado guardado (savestate.c,
# F1-F12 / Shift+F1-F12 y la orden savestate del servidor de depuración) dejaba el juego a 0,55x y lo cerraba a los pocos
# segundos («DISPATCH FATAL: misaligned target 0x801E34F1»). Las causas, casi todas ya corregidas en el psxrecomp original
# (RetroPortingToolkit, master del 2026-10-03), cuya versión es mucho más grande:
#  1. boot_state.c pone SIEMPRE cpu->pc = entry_pc al cargar (lo escribieron para la instantánea de arranque), así que un
#     estado de usuario se reanudaba en el punto de entrada del ejecutable con la RAM de mitad de partida. Ahora los
#     estados de usuario se reanudan en el PC guardado (boot_state_resume_saved_pc); el arranque rápido sigue igual.
#  2. Nada reajustaba el estado de interrupciones del lado del host, con marcas de ciclo absolutas de la línea de
#     tiempo anterior: interrupts_resync_after_restore, como la del original (post_exception_cooldown_until, latches…).
#  3. La RAM se restaura con memcpy, que no pasa por las escrituras vigiladas: ninguna generación de página se movía y
#     la validación de los overlays estáticos (y el cargador de DLL) seguía con los veredictos del código de antes.
#     overlay_watch_bump_all sube todas las generaciones y la del intérprete de RAM sucia.
#  4. Los plazos de la GTE y de MULT/DIV (cpu->gte_ts_done, muldiv_ts_done) y el «give-back» de las cargas son marcas de
#     ciclo absolutas del host que no van en la instantánea: la primera espera de la GTE tras cargar adelantaba el reloj
#     todo lo rebobinado de golpe, sin comprobar interrupciones (6 s sin cuadros y el vigilante abortaba).
#     psx_cycles_resync_cpu_after_restore los ancla al reloj restaurado, y se reinicia el detector de espera.
#  5. (propio) Un estado cargado antes del «juego empezado» de fntrace (en un arranque nuevo): el primer salto al juego
#     echaba ese cerrojo y borraba las marcas de RAM sucia de toda la ventana del ejecutable, con los overlays recién
#     restaurados dentro («FAIL-FAST unknown dispatch 0x8008E2C0»). fntrace_latch_game_started_after_restore lo echa
#     al cargar, sin borrar nada.
# Base de «guardar al suspender y cargar al volver» en la Xbox (parche_reanudar.py). Comentarios en inglés, como el
# runtime. Cada cambio tiene una firma: si ya está, se salta. Todo o nada; atómico.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

R = parchear.runtime(parchear.raiz(), 'src')
M = 'Xbox port (2026-10-03): save-state load'

CAMBIOS = [
    ('boot_state.c', 'void boot_state_resume_saved_pc(int on)',
     'static uint32_t s_capture_entry_pc;\n',
     'static uint32_t s_capture_entry_pc;\n\n'
     '/* ' + M + ': user save states (savestate.c) resume at the PC they were\n'
     ' * saved at; only the boot snapshot enters at the game entry. */\n'
     'static int s_resume_saved_pc = 0;\n'
     'void boot_state_resume_saved_pc(int on) { s_resume_saved_pc = on ? 1 : 0; }\n'),
    ('boot_state.c', 'cpu->pc = s_resume_saved_pc ? c->pc : entry_pc;',
     '        cpu->pc = entry_pc;   /* always enter at the game entry, never a mid-PC */\n',
     '        /* ' + M + ': the boot snapshot always enters at the game entry;\n'
     '         * a user save state resumes at its saved block-leader PC. */\n'
     '        cpu->pc = s_resume_saved_pc ? c->pc : entry_pc;\n'),
    ('boot_state.c', '            overlay_watch_bump_all();\n',
     '            psx_kernel_bless_note_range(0, RAM_SIZE);\n        }\n        return 1;\n',
     '            psx_kernel_bless_note_range(0, RAM_SIZE);\n        }\n'
     '        {   /* ' + M + ': the memcpy bypasses the store path, so no\n'
     '             * page generation moved and the overlay loader / static-overlay validation would\n'
     '             * keep their verdicts about the code that was in RAM before the load. */\n'
     '            extern void overlay_watch_bump_all(void);\n'
     '            overlay_watch_bump_all();\n'
     '        }\n'
     '        return 1;\n'),
    ('memory.c', 'void overlay_watch_bump_all(void) {',
     'static inline void overlay_watch_note_write(uint32_t phys, uint32_t size) {\n',
     '/* ' + M + ': RAM rewritten wholesale (boot_state.c), so any page may\n'
     ' * hold other code now, watched or not. Bump them all (generations only grow, so every\n'
     ' * cached sum changes) and the dirty-RAM code generation: cached verdicts and decoded\n'
     ' * blocks are re-checked on their next use. */\n'
     'void overlay_watch_bump_all(void) {\n'
     '    for (uint32_t pg = 0; pg < DIRTY_RAM_PAGE_COUNT; pg++) overlay_page_gen[pg]++;\n'
     '    g_dirty_ram_code_gen++;\n'
     '}\n\n'
     'static inline void overlay_watch_note_write(uint32_t phys, uint32_t size) {\n'),
    ('interrupts.c', 'void interrupts_resync_after_restore(void) {',
     '    cycles_since_vblank = 0;\n    last_sio_seq_seen = sio_get_seq();\n'
     '    last_sio_progress_cycle = psx_get_cycle_count();\n}\n',
     '    cycles_since_vblank = 0;\n    last_sio_seq_seen = sio_get_seq();\n'
     '    last_sio_progress_cycle = psx_get_cycle_count();\n}\n\n'
     '/* ' + M + ': host-side interrupt state keeps absolute guest-cycle\n'
     ' * stamps from the pre-load timeline. After a load the clock jumps (back, or forward on a\n'
     ' * fresh boot): a post_exception_cooldown_until left in the future blocks every IRQ, VBlank\n'
     ' * included, until the restored clock catches up. Same reset as the upstream psxrecomp\n'
     ' * (RetroPortingToolkit) interrupts_resync_after_restore; cycles_since_vblank is not in\n'
     ' * this build\'s IRQ section, so it restarts its frame phase. */\n'
     'void interrupts_resync_after_restore(void) {\n'
     '    post_exception_cooldown_until = 0;\n'
     '    dispatch_count = 0;\n'
     '    in_exception = 0;\n'
     '    exception_nest_depth = 0;\n'
     '    total_checks = 0;\n'
     '    cycles_since_vblank = 0;\n'
     '    last_sio_seq_seen = sio_get_seq();\n'
     '    last_sio_progress_cycle = psx_get_cycle_count();\n'
     '    s_defer_switch_pending = 0;\n'
     '    s_defer_switch_target = 0;\n'
     '    s_defer_switch_from = 0;\n'
     '    g_exception_real_epc = 0;\n'
     '    g_rfe_escape_pending = 0;\n'
     '    g_pending_exception_longjmp = 0;\n'
     '    s_compiled_interrupt_resume_pc = 0;\n'
     '    s_last_interrupt_check_pc = 0;\n'
     '    s_last_interrupt_check_cycle = UINT64_MAX;\n'
     '    g_dirty_safe_resume_pc = 0;\n'
     '}\n'),
    ('psx_cycles.c', 'void psx_cycles_resync_cpu_after_restore(CPUState *cpu) {',
     'void psx_cycles_resync_after_restore(void) {\n'
     '    s_devices_synced_cycle = psx_cycle_count;\n'
     '    s_next_service_cycle   = 0;   /* recompute on next charge */\n'
     '    s_in_device_service    = 0;\n'
     '}\n',
     'void psx_cycles_resync_after_restore(void) {\n'
     '    s_devices_synced_cycle = psx_cycle_count;\n'
     '    s_next_service_cycle   = 0;   /* recompute on next charge */\n'
     '    s_in_device_service    = 0;\n'
     '    /* ' + M + ': the idle-skip detector latches absolute\n'
     '     * cycle/store counters from the pre-load timeline; drop them (as upstream does). */\n'
     '    s_idle_pc = 0;\n'
     '    s_idle_streak = 0;\n'
     '    s_idle_progress_reg = -2;\n'
     '    s_idle_last_cycle = psx_cycle_count;\n'
     '}\n\n'
     '/* ' + M + ': GTE / mult-div completion deadlines and the load\n'
     ' * give-back are host-only absolute cycle stamps (not in the CPU section of the snapshot).\n'
     ' * After a load they still hold the pre-load timeline, so the next GTE or MFLO stall would\n'
     ' * advance the whole gap at once, with no IRQ checks (seconds with no frame: the starvation\n'
     ' * watchdog aborted SFEX+a). Anchor them at the restored clock, as upstream psxrecomp does. */\n'
     'void psx_cycles_resync_cpu_after_restore(CPUState *cpu) {\n'
     '    if (!cpu) return;\n'
     '    cpu->gte_ts_done = psx_cycle_count;\n'
     '    cpu->muldiv_ts_done = psx_cycle_count;\n'
     '    for (unsigned i = 0; i < sizeof(cpu->read_absorb); i++) cpu->read_absorb[i] = 0;\n'
     '    cpu->read_absorb_which = 0;\n'
     '    cpu->read_fudge = 0x20u;   /* no committed predecessor load */\n'
     '    cpu->ld_which_t = 0x20u;   /* no pending load dest */\n'
     '    cpu->ld_absorb = 0;\n'
     '}\n'),
    ('fntrace.c', 'void fntrace_latch_game_started_after_restore(void) {',
     'int fntrace_is_game_started(void) { return s_game_started; }\n',
     'int fntrace_is_game_started(void) { return s_game_started; }\n\n'
     '/* ' + M + ': a save state loaded on a fresh boot (resume after\n'
     ' * termination) is past the game start while this latch is still 0. The first game dispatch\n'
     ' * would then latch it AND clear the dirty-RAM baseline of the whole game-text window —\n'
     ' * wiping the restored overlay pages (SFEX+a overlays live at 0x80020000: FAIL-FAST unknown\n'
     ' * dispatch 0x8008E2C0) — and zero the low boot scratch. Latch it here without those side\n'
     ' * effects (the restored dirty bitmap is the right one) and switch the CD to the game speed,\n'
     ' * as the real game start does. */\n'
     'void fntrace_latch_game_started_after_restore(void) {\n'
     '    extern void cdrom_notify_game_started(void);\n'
     '    if (s_game_started) return;\n'
     '    s_game_started = 1;\n'
     '    cdrom_notify_game_started();\n'
     '}\n'),
    ('savestate.c', 'extern void psx_cycles_resync_cpu_after_restore(CPUState *cpu);',
     'extern int psx_hle_scheduler_enabled(void);\n',
     'extern int psx_hle_scheduler_enabled(void);\n'
     '/* ' + M + ' */\n'
     'extern void boot_state_resume_saved_pc(int on);\n'
     'extern void interrupts_resync_after_restore(void);\n'
     'extern void psx_cycles_resync_cpu_after_restore(CPUState *cpu);\n'),
    ('savestate.c', 'extern void fntrace_latch_game_started_after_restore(void);',
     'extern void psx_cycles_resync_cpu_after_restore(CPUState *cpu);\n',
     'extern void psx_cycles_resync_cpu_after_restore(CPUState *cpu);\n'
     'extern void fntrace_latch_game_started_after_restore(void);\n'),
    ('savestate.c', 'boot_state_resume_saved_pc(1);',
     '        if (boot_state_load(path, s_bios_checksum, s_entry_pc, cpu)) {\n'
     '            psx_cycles_resync_after_restore();\n',
     '        /* ' + M + ': resume at the saved PC, then drop the\n'
     '         * host-side interrupt and timing stamps of the pre-load timeline. */\n'
     '        boot_state_resume_saved_pc(1);\n'
     '        int loaded = boot_state_load(path, s_bios_checksum, s_entry_pc, cpu);\n'
     '        boot_state_resume_saved_pc(0);\n'
     '        if (loaded) {\n'
     '            psx_cycles_resync_after_restore();\n'
     '            psx_cycles_resync_cpu_after_restore(cpu);\n'
     '            interrupts_resync_after_restore();\n'),
    ('savestate.c', '            fntrace_latch_game_started_after_restore();',
     '            interrupts_resync_after_restore();\n',
     '            interrupts_resync_after_restore();\n'
     '            fntrace_latch_game_started_after_restore();   /* a load before the game start */\n'),
]


if __name__ == '__main__':
    parchear.informe(parchear.aplicar(R, CAMBIOS))
