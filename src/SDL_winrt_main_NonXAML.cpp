/*
    SDL_winrt_main_NonXAML.cpp, placed in the public domain by David Ludwig  3/13/14
*/

#include "SDL_main.h"
#include "SDL_hints.h"
#include <cstdio>
#include <cwchar>
#include <string>
#include <vector>
#include <windows.h>
#include <wrl.h>

/* At least one file in any SDL/WinRT app appears to require compilation
   with C++/CX, otherwise a Windows Metadata file won't get created, and
   an APPX0702 build error can appear shortly after linking.

   The following set of preprocessor code forces this file to be compiled
   as C++/CX, which appears to cause Visual C++ 2012's build tools to
   create this .winmd file, and will help allow builds of SDL/WinRT apps
   to proceed without error.

   If other files in an app's project enable C++/CX compilation, then it might
   be possible for SDL_winrt_main_NonXAML.cpp to be compiled without /ZW,
   for Visual C++'s build tools to create a winmd file, and for the app to
   build without APPX0702 errors.  In this case, if
   SDL_WINRT_METADATA_FILE_AVAILABLE is defined as a C/C++ macro, then
   the #error (to force C++/CX compilation) will be disabled.

   Please note that /ZW can be specified on a file-by-file basis.  To do this,
   right click on the file in Visual C++, click Properties, then change the
   setting through the dialog that comes up.
*/
#ifndef SDL_WINRT_METADATA_FILE_AVAILABLE
#ifndef __cplusplus_winrt
#error SDL_winrt_main_NonXAML.cpp must be compiled with /ZW, otherwise build errors due to missing .winmd files can occur.
#endif
#endif

/* Prevent MSVC++ from warning about threading models when defining our
   custom WinMain.  The threading model will instead be set via a direct
   call to Windows::Foundation::Initialize (rather than via an attributed
   function).

   To note, this warning (C4447) does not seem to come up unless this file
   is compiled with C++/CX enabled (via the /ZW compiler flag).
*/
#ifdef _MSC_VER
#pragma warning(disable : 4447)
#endif

/* Make sure the function to initialize the Windows Runtime gets linked in. */
#ifdef _MSC_VER
#pragma comment(lib, "runtimeobject.lib")
#endif

// --- Recompilaciones (2026-10-03): reanudar tras la terminación -------------------------------------
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

    // Returning from SDL_main is not sufficient to dismiss the app reliably
    // on Xbox. Flush the LocalState log and explicitly end the UWP lifecycle.
    std::fflush(nullptr);
    Windows::ApplicationModel::Core::CoreApplication::Exit();
    return result;
}

// --- Recompilaciones (2026-10-02) -------------------------------------------------------------------
// El Device Portal de la Xbox sube los archivos a través de D:\DevelopmentFiles (5 GB, casi lleno en la
// xbox series cuarto) y respondió 500 al subir el disco entero (528 MB). Se sube partido en
// «<nombre>.parte1», «<nombre>.parte2»… dentro de LocalState\PSXRecomp\SLUS-00548\disc\ y aquí se une, una
// sola vez, antes de arrancar el runtime (las partes se quedan; el runtime lee el archivo que cita game.cue).
// Receta de la entrada UWP de Melee (Decompilaciones, 2026-10-01). LocalState se saca del Temp de la app
// («Packages\<PFN>\AC\Temp»): así no hace falta la Windows Runtime antes de SDL_WinRTRunApp.

std::wstring raiz_juego()
{
    wchar_t tmp[MAX_PATH] = {};
    const DWORD n = GetTempPathW(MAX_PATH, tmp);
    std::wstring t(tmp, n);
    if (!t.empty() && (t.back() == L'\\' || t.back() == L'/')) t.pop_back();
    for (int i = 0; i < 2; ++i) {
        const size_t p = t.find_last_of(L"\\/");
        if (p != std::wstring::npos) t.resize(p);
    }
    return t + L"\\LocalState\\PSXRecomp\\SLUS-00548\\";
}

void anota(const std::wstring& raiz, const char* texto)
{
    FILE* f = nullptr;
    if (_wfopen_s(&f, (raiz + L"logs\\partes.txt").c_str(), L"ab") == 0 && f) {
        std::fputs(texto, f);
        std::fputs("\r\n", f);
        std::fclose(f);
    }
}

void une_partes()
{
    const std::wstring raiz = raiz_juego();
    const std::wstring disco = raiz + L"disc\\";
    WIN32_FIND_DATAW d = {};
    HANDLE h = FindFirstFileExW((disco + L"*.parte1").c_str(), FindExInfoBasic, &d, FindExSearchNameMatch, nullptr, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    FindClose(h);
    std::wstring base(d.cFileName);
    base.resize(base.size() - std::wcslen(L".parte1"));
    const std::wstring destino = disco + base;
    if (GetFileAttributesW(destino.c_str()) != INVALID_FILE_ATTRIBUTES) return;  // ya unido
    const std::wstring tmp = destino + L".uniendo";
    FILE* out = nullptr;
    if (_wfopen_s(&out, tmp.c_str(), L"wb") != 0 || !out) {
        anota(raiz, "partes: no se pudo crear el archivo unido");
        return;
    }
    std::vector<char> buf(8u << 20);
    unsigned long long total = 0;
    int partes = 0;
    for (int i = 1;; ++i) {
        FILE* in = nullptr;
        if (_wfopen_s(&in, (destino + L".parte" + std::to_wstring(i)).c_str(), L"rb") != 0 || !in) break;
        size_t leidos;
        while ((leidos = std::fread(buf.data(), 1, buf.size(), in)) > 0) {
            std::fwrite(buf.data(), 1, leidos, out);
            total += leidos;
        }
        std::fclose(in);
        ++partes;
    }
    std::fclose(out);
    char msg[200];
    if (MoveFileExW(tmp.c_str(), destino.c_str(), MOVEFILE_REPLACE_EXISTING))
        std::snprintf(msg, sizeof msg, "partes: %d unidas, %llu bytes", partes, total);
    else
        std::snprintf(msg, sizeof msg, "partes: no se pudo renombrar (error %lu)", GetLastError());
    anota(raiz, msg);
}

} // namespace

int CALLBACK WinMain(HINSTANCE, HINSTANCE, LPSTR, int)
{
    une_partes();
    // En la Xbox, B es también el «atrás» del sistema: si nadie lo atiende, cierra la app. Con esta
    // pista SDL lo atiende y la pulsación sigue llegando al juego (receta de Melee, 2026-10-01).
    SDL_SetHint(SDL_HINT_WINRT_HANDLE_BACK_BUTTON, "1");
    return SDL_WinRTRunApp(SDL_main_with_core_exit, NULL);
}
