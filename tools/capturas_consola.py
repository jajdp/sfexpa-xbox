# -*- coding: utf-8 -*-
# Reduce las capturas numeradas de una partida en la consola (overlay_captures_<sesión>_<n>.json, que son
# CÓDIGO DEL JUEGO leído de tu disco) a una por «configuración de código», y las añade a un archivo
# de capturas unidas.
#
# Una configuración termina cuando cambia alguna palabra en un PC ya ejecutado (otro overlay cargado encima). Dentro de
# una configuración el código no cambia y los PCs son acumulativos, así que basta la ÚLTIMA captura de cada una.
# Uso: capturas_consola.py --sesion 1791006427 --base unidas-29.json --salida unidas-29-mas-consola.json
import argparse, base64, glob, json, os

ap = argparse.ArgumentParser()
ap.add_argument('--carpeta', required=True,
                help='carpeta con lo bajado de logs\\ de la consola (bajar_capturas.ps1)')
ap.add_argument('--sesion', required=True)
ap.add_argument('--base', required=True, help='capturas unidas de antes (se conservan delante, tal cual)')
ap.add_argument('--salida', required=True)
a = ap.parse_args()

fs = sorted(glob.glob(os.path.join(a.carpeta, f'overlay_captures_{a.sesion}_*.json')))
snaps = []
for f in fs:
    caps = json.load(open(f, encoding='utf-8'))
    if len(caps) != 1:
        if caps:
            raise SystemExit(f'{f}: {len(caps)} regiones; este guion espera una')
        continue
    c = caps[0]
    snaps.append((os.path.basename(f), c, base64.b64decode(c['bytes_b64']), int(c['load_addr'], 16),
                  {int(x, 16) for x in c['executed_pcs']}))


def palabra(img, la, pc):
    off = (pc & 0x1FFFFFFF) - (la & 0x1FFFFFFF)
    return img[off:off + 4] if 0 <= off <= len(img) - 4 else None


grupos = [[snaps[0]]]
for prev, cur in zip(snaps, snaps[1:]):
    _, _, pimg, pla, pex = prev
    _, _, img, la, _ = cur
    cambia = any(palabra(img, la, p) != palabra(pimg, pla, p) for p in pex if palabra(img, la, p) is not None)
    if cambia:
        grupos.append([cur])
    else:
        grupos[-1].append(cur)

reps = [g[-1] for g in grupos]
print(f'{len(snaps)} capturas -> {len(grupos)} configuraciones')
for g in grupos:
    n, c, img, la, ex = g[-1]
    print(f'  {g[0][0][-8:-5]}..{n[-8:-5]} ({len(g):2d}) -> {n}: exec={len(ex)} disp={len(c["dispatch_entry_pcs"])} '
          f'sem={len(c["seeds"])}')

base = json.load(open(a.base, encoding='utf-8'))
lista = list(base) + [r[1] for r in reps]
tmp = a.salida + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(lista, f, indent=1)
os.replace(tmp, a.salida)
print(f'escrito {a.salida}: {len(base)} de la base + {len(reps)} de la consola = {len(lista)} capturas, '
      f'{os.path.getsize(a.salida):,} B')
