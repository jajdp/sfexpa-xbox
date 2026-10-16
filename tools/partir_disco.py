# Parte un archivo en trozos para subirlo por el Device Portal de la Xbox: las subidas pasan por
# D:\DevelopmentFiles (5 GB, casi lleno en la xbox series cuarto) y el disco de SF EX Plus Alpha entero
# (528 MB) respondió 500. La entrada UWP del juego (UWP\SDL_winrt_main_NonXAML.cpp) une las partes al
# arrancar. Copia de partir_disco.py de Melee (2026-10-01), con la carpeta de salida como argumento.
# Uso: py -3.13 partir_disco.py <archivo> <carpeta de salida> [MiB por parte, 150 por defecto]
import hashlib
import os
import sys

ruta, salida = sys.argv[1], sys.argv[2]
tam = (int(sys.argv[3]) if len(sys.argv) > 3 else 150) * 1024 * 1024
os.makedirs(salida, exist_ok=True)
nombre = os.path.basename(ruta)
h = hashlib.sha1()
i = 0
with open(ruta, "rb") as f:
    while True:
        datos = f.read(tam)
        if not datos:
            break
        i += 1
        h.update(datos)
        destino = os.path.join(salida, f"{nombre}.parte{i}")
        tmp = destino + ".tmp"
        with open(tmp, "wb") as o:
            o.write(datos)
        os.replace(tmp, destino)
        print(f"{destino}: {len(datos)} bytes")
print(f"{i} partes; SHA-1 del total {h.hexdigest()}")
