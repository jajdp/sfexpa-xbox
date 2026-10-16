# -*- coding: utf-8 -*-
# Parche local de psxrecomp/tools/compile_overlays.py (modo --static): cada entrada huérfana guarda TODAS las capturas
# que la contienen, no solo la última, y el pase de fragmentos aislados prueba cada una (sin repetir bytes iguales
# alrededor de la entrada) y conserva todos los fragmentos válidos. Motivo (SFEX+α, 2026-10-02): el reproductor de
# vídeo vive en 0x800D6000.. solo durante la intro; las capturas posteriores tienen datos en esas direcciones, y como
# ganaba la última, los fragmentos del reproductor (0x800E7784...) no se generaban y el vídeo iba en el intérprete.
# Copia del original en <scratchpad>\compile_overlays.py.original. Los comentarios del código van en inglés.
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

RUTA = os.path.join(parchear.raiz(), 'psxrecomp', 'tools', 'compile_overlays.py')
COPIA = RUTA + '.original'   # la copia del original, junto a el
MARCA = 'every capture that holds it (Xbox port, 2026-10-02)'

CAMBIOS = [
    ('''                static_requested_entries.add(entry)
                static_entry_sources[entry] = (
                    data, load_addr, size, phys_addr)
            # --force-interior''',
     '''                static_requested_entries.add(entry)
                # Keep every capture that holds it (Xbox port, 2026-10-02): the
                # last capture may carry unrelated bytes at this address (an FMV
                # player that a later overlay overwrote), so the orphan-fragment
                # pass below tries each distinct source instead of only the last.
                static_entry_sources.setdefault(entry, []).append(
                    (data, load_addr, size, phys_addr))
            # --force-interior'''),
    ('''                    static_requested_entries.add(entry)
                    static_entry_sources[entry] = (
                        data, load_addr, size, phys_addr)''',
     '''                    static_requested_entries.add(entry)
                    static_entry_sources.setdefault(entry, []).append(
                        (data, load_addr, size, phys_addr))'''),
    ('''        for entry in unresolved:
            if entry in existing_entries:
                continue
            source = static_entry_sources.get(entry)
            if source is None:
                continue
            data, load_addr, size, phys_addr = source
            part = generate_interior_fragment_static(
                entry, data, load_addr, size, phys_addr, args)
            if part is None:
                continue
            static_parts.append(part)
            new_fragment_parts.append(part)
            existing_entries.update(
                variant['addr'] for variant in part['variants'])
            fragment_built += 1''',
     '''        for entry in unresolved:
            if entry in existing_entries:
                continue
            sources = static_entry_sources.get(entry)
            if not sources:
                continue
            # Try every distinct code window around the entry; each successful
            # shard is content-validated at dispatch, so keeping several
            # variants of one entry is safe (they never run on foreign bytes).
            seen_windows = set()
            entry_parts = []
            for data, load_addr, size, phys_addr in sources:
                off = (entry & 0x1FFFFFFF) - (load_addr & 0x1FFFFFFF)
                window = binascii.crc32(data[max(0, off):off + 0x2000]) & 0xFFFFFFFF
                if window in seen_windows:
                    continue
                seen_windows.add(window)
                part = generate_interior_fragment_static(
                    entry, data, load_addr, size, phys_addr, args)
                if part is None:
                    continue
                entry_parts.append(part)
            for part in entry_parts:
                static_parts.append(part)
                new_fragment_parts.append(part)
                existing_entries.update(
                    variant['addr'] for variant in part['variants'])
                fragment_built += 1'''),
]


def main():
    with open(RUTA, 'rb') as f:
        t = f.read().decode('utf-8')
    if MARCA in t:
        print('ya estaba parcheado')
        return
    if not os.path.exists(COPIA):
        shutil.copy2(RUTA, COPIA)
    eol = '\r\n' if '\r\n' in t else '\n'
    t = t.replace('\r\n', '\n')
    for viejo, nuevo in CAMBIOS:
        n = t.count(viejo)
        if n != 1:
            raise SystemExit(f'se esperaba 1 aparición y hay {n}:\n{viejo[:300]}')
        t = t.replace(viejo, nuevo)
    t = t.replace('\n', eol)
    with open(RUTA + '.tmp', 'wb') as f:
        f.write(t.encode('utf-8'))
    os.replace(RUTA + '.tmp', RUTA)
    print('parcheado', RUTA)


main()
