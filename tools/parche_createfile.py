# -*- coding: utf-8 -*-
# psxrecomp eec0c31 (rama main de plusalpha-recomp), runtime/src/overlay_loader.c: el barrido de la caché de DLL marca
# su fin con CreateFileA, que en UWP no está declarado (solo escritorio). MSVC lo declara implícito como «int» y trunca
# el HANDLE de 64 bits. En UWP se crea la marca con fopen. Comentario en inglés, como el runtime. Escritura atómica.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

RUTA = parchear.runtime(parchear.raiz(), 'src', 'overlay_loader.c')
MARCA = 'Xbox port (2026-10-03): CreateFileA is desktop-only'
VIEJO = '''    HANDLE m = CreateFileA(marker, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    if (m != INVALID_HANDLE_VALUE) CloseHandle(m);
#else'''
NUEVO = '''#if defined(WINAPI_FAMILY) && (WINAPI_FAMILY == WINAPI_FAMILY_APP)
    /* ''' + MARCA + ''' (UWP headers do not declare it, so MSVC
     * implied an int return and truncated the HANDLE); a plain file does the job. */
    { FILE *mf = fopen(marker, "wb"); if (mf) fclose(mf); }
#else
    HANDLE m = CreateFileA(marker, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    if (m != INVALID_HANDLE_VALUE) CloseHandle(m);
#endif
#else'''
t = open(RUTA, 'rb').read().decode('utf-8')
if MARCA in t:
    print('overlay_loader.c: ya tenía el arreglo de CreateFileA')
    raise SystemExit
eol = '\r\n' if '\r\n' in t else '\n'
t = t.replace('\r\n', '\n')
if t.count(VIEJO) != 1:
    raise SystemExit(f'overlay_loader.c: el bloque aparece {t.count(VIEJO)} veces')
t = t.replace(VIEJO, NUEVO)
with open(RUTA + '.tmp', 'wb') as f:
    f.write(t.replace('\n', eol).encode('utf-8'))
os.replace(RUTA + '.tmp', RUTA)
print('overlay_loader.c: CreateFileA sustituido por fopen en UWP')
