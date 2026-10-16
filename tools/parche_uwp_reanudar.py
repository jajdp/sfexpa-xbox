# -*- coding: utf-8 -*-
# La entrada UWP (UWP\SDL_winrt_main_NonXAML.cpp del árbol) y el SDL 2.30.2 que se compila para WindowsStore
# (UWP-Build\_deps\SDL-release-2.30.2, o el que digas con --sdl=): la otra mitad de parche_reanudar.py. El runtime solo restaura la
# máquina guardada si el sistema relanza la app después de terminarla (PreviousExecutionState == Terminated, 3), y ese
# dato solo lo trae la activación UWP.
#  - Versión 1 (0.2.8.0): lo leía con AppInstance::GetActivatedEventArgs() antes de SDL_main. En la consola devuelve
#    nulo: el registro decía «resume: previous execution state -1» en cada arranque y la máquina guardada se descartaba
#    (probado por el usuario el 2026-10-03: volvió de Home y el juego empezó de cero).
#  - Versión 2 (0.2.9.0): SDL guarda el estado en g_psx_prev_exec_state al recibir la activación
#    (SDL_WinRTApp::OnAppActivated, que sí trae los argumentos), y la entrada solo lo pisa si AppInstance da un valor.
#    El runtime lo lee al decidir, que es después de crear la ventana y procesar la activación.
# SDL se compila una sola vez: tras este parche hay que recompilarlo (construir-uwp.ps1 -RehacerSdl).
# Cada cambio tiene una firma: si ya está, se salta. Todo o nada; atómico; conserva el fin de línea.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

_RAIZ = parchear.raiz()
R = os.path.join(_RAIZ, 'UWP')
# El codigo de SDL que construir-uwp.ps1 descomprime para compilarlo para WindowsStore.
# Con --sdl <ruta> se le da otro (por ejemplo, si el arbol de compilacion esta aparte).
SDL = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--sdl=')),
           os.path.join(_RAIZ, 'UWP-Build', '_deps', 'SDL-release-2.30.2'))
ARCHIVO = 'SDL_winrt_main_NonXAML.cpp'
SDL_APP = r'src\core\winrt\SDL_winrtapp_direct3d.cpp'

DECLARACION = '''// --- Recompilaciones (2026-10-03): reanudar tras la terminación -------------------------------------
// En el modo desarrollador la consola termina el juego en segundo plano y, al volver de Home, lo relanza
// con PreviousExecutionState = Terminated (3). El runtime (main.cpp, «resume after termination») restaura
// entonces la máquina que guardó al ocultarse la ventana; con cualquier otro estado la descarta.
extern "C" int g_psx_prev_exec_state;

namespace {

int estado_previo()
{
    // La activación de este arranque; -1 si no se puede leer.
    try {
        auto a = Windows::ApplicationModel::AppInstance::GetActivatedEventArgs();
        if (a != nullptr) return static_cast<int>(a->PreviousExecutionState);
    } catch (Platform::Exception^) {
    }
    return -1;
}

int SDL_main_with_core_exit(int argc, char* argv[])
{
    g_psx_prev_exec_state = estado_previo();
    const int result = SDL_main(argc, argv);
'''

ENTRADA_V1 = '''    g_psx_prev_exec_state = estado_previo();
    const int result = SDL_main(argc, argv);
'''
ENTRADA_V2 = '''    // v2 (0.2.9.0): en la consola AppInstance da nulo; el estado lo anota SDL al recibir la activación
    // (SDL_WinRTApp::OnAppActivated, parche de SDL de este mismo script). Aquí solo se usa si AppInstance responde.
    {
        const int e = estado_previo();
        if (e >= 0) g_psx_prev_exec_state = e;
    }
    const int result = SDL_main(argc, argv);
'''

SDL_VIEJO = '''void SDL_WinRTApp::OnAppActivated(CoreApplicationView ^ applicationView, IActivatedEventArgs ^ args)
{
    CoreWindow::GetForCurrentThread()->Activate();
}'''
SDL_NUEVO = '''/* Recompilaciones (2026-10-03): the launch activation carries PreviousExecutionState (3 = Terminated),
 * which the game's runtime needs to resume after the console terminated it in the background. The
 * game's UWP entry cannot read it (AppInstance::GetActivatedEventArgs() returns null on the console), so
 * it is recorded here, once, for the runtime's resume decision (psxrecomp main.cpp). */
extern "C" int g_psx_prev_exec_state;

void SDL_WinRTApp::OnAppActivated(CoreApplicationView ^ applicationView, IActivatedEventArgs ^ args)
{
    static bool recorded = false;
    if (!recorded && args != nullptr) {
        g_psx_prev_exec_state = (int)args->PreviousExecutionState;
        recorded = true;
    }
    CoreWindow::GetForCurrentThread()->Activate();
}'''

if __name__ == '__main__':
    hechos = parchear.aplicar(R, [
        (ARCHIVO, 'int estado_previo()', '''namespace {

int SDL_main_with_core_exit(int argc, char* argv[])
{
    const int result = SDL_main(argc, argv);
''', DECLARACION),
        (ARCHIVO, 'v2 (0.2.9.0): en la consola AppInstance da nulo', ENTRADA_V1, ENTRADA_V2),
    ])
    # La mitad de SDL solo se puede aplicar cuando el codigo de SDL esta descomprimido, y eso lo hace
    # construir-uwp.ps1 al descargarlo. Ese script vuelve a llamar aqui con --sdl= en ese momento, asi
    # que en un arbol recien clonado esto no es un fallo: es que todavia no toca.
    if os.path.isdir(SDL):
        hechos += parchear.aplicar(SDL, [(SDL_APP, 'static bool recorded = false;',
                                          SDL_VIEJO, SDL_NUEVO)])
    else:
        hechos.append('SDL todavia no esta descargado (%s): su parte la aplica construir-uwp.ps1'
                      % SDL)
    parchear.informe(hechos)
