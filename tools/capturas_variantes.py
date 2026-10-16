# -*- coding: utf-8 -*-
# Analiza las copias de overlay_captures.json que dejó captura_variantes.ps1 (son CÓDIGO DEL JUEGO leído
# de tu disco: no se publican)
# y, con --unir <salida.json>, escribe un único archivo con cada variante distinta (región, CRC de la imagen) una sola
# vez y la unión de sus PCs. Las semillas de cada foto son las del intérprete en toda la sesión hasta ese momento; se
# guardan todas (el despacho estático valida por contenido, así que una semilla de otra variante no hace daño).
import base64, binascii, glob, json, os, sys

# La carpeta con las copias de overlay_captures.json: codigo del juego leido del disco, asi
# que cada uno la tendra donde quiera. captura_variantes.ps1 las deja en su -Salida.
CARPETA = next((a for a in sys.argv[1:] if not a.startswith('-')), None)
if not CARPETA:
    sys.exit('uso: capturas_variantes.py <carpeta con las copias> [--unir <salida.json>]')


def cargar(ruta):
    with open(ruta, encoding='utf-8') as f:
        return json.load(f)


def main():
    rutas = sorted(glob.glob(os.path.join(CARPETA, '[0-9][0-9][0-9]s-overlay_captures.json')))
    variantes = {}   # (load_addr, size, crc) -> dict
    orden = []
    for ruta in rutas:
        caps = cargar(ruta)
        nombre = os.path.basename(ruta)[:4]
        partes = []
        for c in caps:
            data = base64.b64decode(c['bytes_b64'])
            la = int(c['load_addr'], 16)
            crc = binascii.crc32(data) & 0xFFFFFFFF
            clave = (la, len(data), crc)
            partes.append(f'{la:08X}+{len(data):6d} crc={crc:08X} pcs={len(c["executed_pcs"]):5d} sem={len(c["seeds"]):4d}')
            if clave not in variantes:
                variantes[clave] = {'cap': dict(c), 'desde': nombre,
                                    'exec': set(c['executed_pcs']), 'disp': set(c['dispatch_entry_pcs']),
                                    'seeds': set(c['seeds'])}
                orden.append(clave)
            else:
                v = variantes[clave]
                v['exec'] |= set(c['executed_pcs'])
                v['disp'] |= set(c['dispatch_entry_pcs'])
                v['seeds'] |= set(c['seeds'])
        print(nombre, ' | '.join(partes))
    print(f'\nvariantes distintas: {len(variantes)}')
    for clave in orden:
        la, sz, crc = clave
        v = variantes[clave]
        print(f'  {la:08X}+{sz:7d} crc={crc:08X} desde {v["desde"]} pcs={len(v["exec"])} sem={len(v["seeds"])}')
    if '--unir' in sys.argv:
        salida = sys.argv[sys.argv.index('--unir') + 1]
        lista = []
        for clave in orden:
            v = variantes[clave]
            c = v['cap']
            ordenar = lambda s: sorted(s, key=lambda x: int(x, 16))
            c['executed_pcs'] = ordenar(v['exec'])
            c['dispatch_entry_pcs'] = ordenar(v['disp'])
            c['seeds'] = ordenar(v['seeds'])
            lista.append(c)
        tmp = salida + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(lista, f, indent=1)
        os.replace(tmp, salida)
        print(f'escrito {salida} ({os.path.getsize(salida):,} B, {len(lista)} variantes)')


main()
