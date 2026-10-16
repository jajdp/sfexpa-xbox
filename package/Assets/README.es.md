# Pon aquí tus once mosaicos del paquete

*(English: [README.md](README.md))*

Esta carpeta está **vacía a propósito**. Los mosaicos del port real están recortados del propio
material artístico del juego, que es de Capcom, así que no se distribuyen aquí — ver
[`../../NOTICE.es.md`](../../NOTICE.es.md).

Los nombres y las medidas exactas están en [`../../docs/ASSETS.es.md`](../../docs/ASSETS.es.md).
Valen imágenes de color liso con las dimensiones correctas: a la consola solo le hace falta que
existan y que tengan la forma adecuada.

`tools/construir-uwp.ps1` se detiene antes de configurar nada si aquí no hay ningún PNG, y te lo
dice. El `.gitignore` deja los `*.png` de esta carpeta fuera del repositorio, así que lo que pongas
aquí no se va a subir por descuido.
