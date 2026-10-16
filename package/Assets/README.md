# Put your eleven package tiles here

*(Español: [README.es.md](README.es.md))*

This folder is **empty on purpose**. The tiles of the real port were cut from the game's own
artwork, which belongs to Capcom, so they are not distributed here — see
[`../../NOTICE.md`](../../NOTICE.md).

The exact names and sizes are in [`../../docs/ASSETS.md`](../../docs/ASSETS.md). Plain colour
images of the right dimensions are fine: the console only needs them to exist and to be the right
shape.

`tools/construir-uwp.ps1` stops before configuring anything if there is no PNG in here, and says
so. `.gitignore` keeps this folder's `*.png` out of the repository, so whatever you put here will
not be committed by accident.
