# Notice

*(Español: [NOTICE.es.md](NOTICE.es.md))*

## Not affiliated

This is an unofficial, noncommercial fan project. It is **not affiliated with, endorsed by or
connected to Capcom, Arika, Sony or Microsoft**, or any of their subsidiaries, nor to the author of
the [psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp) framework or to the author of the
[game project](https://github.com/guimaraf/plusalpha-recomp) this port is built on. *Street
Fighter*, *Street Fighter EX Plus α*, *Xbox* and all related names and marks are the property of
their respective owners, and are used here only to say what this works with.

Nothing here is for sale, and nothing here is monetized.

## What this repository does not distribute

No game code. No disc image. No BIOS. No built executable. No `.msix` package. No save data. No
artwork, audio, music or fonts from the game — not even the package tiles, which is why
`package/Assets/` is empty and [`docs/ASSETS.md`](docs/ASSETS.md) asks you to supply your own.

**And no compiled overlays.** This port's performance depends on compiling, into the package, the
code the game loads from the disc at run time. That code is *the game's*, read from your own disc:
the tools that capture and compile it are here, and the captures and the generated
`overlays_static.c` are not — `.gitignore` blocks them by name.

Nothing here produces a playable game on its own. You need your own legally dumped copy of the
disc, a retail BIOS, and a working build of the game project, none of which this repository
provides or can provide.

## What it does contain of other people's work

**Patches against the psxrecomp framework.** The thirteen patch scripts quote **117 lines** of the
framework's source in total, across **48 anchors**: the text each patch checks before writing, so
that it fails safely instead of corrupting a tree it does not recognise. The framework the game
uses ([guimaraf/psxrecomp-plusalpha](https://github.com/guimaraf/psxrecomp-plusalpha), a fork of
psxrecomp) carries the **PolyForm Noncommercial License 1.0.0**, © 2026 Matthew Stan, which permits
noncommercial derivative works; this repository is such a derivative, and is released under
[that same license](LICENSE).

**No code from the game project.** [guimaraf/plusalpha-recomp](https://github.com/guimaraf/plusalpha-recomp)
carries no license at all, so nothing of it is reproduced here. That is also why
`tools/apply_uwp.py` appends its CMake block at the **end** of the file: an anchor would have meant
quoting a line of it. The one file here that shares its shape with one of that project's is
`package/Package.appxmanifest` — a package manifest is a fixed Microsoft schema, so the element
names are the same in any manifest; the identity, the publisher, the device family, the version and
the description are ours, and you have to replace them with yours anyway.

**`src/SDL_winrt_main_NonXAML.cpp`** is SDL's WinRT entry point, *placed in the public domain by
David Ludwig*, with the two things this port needed marked inside it: joining the split disc on
first boot, and recording why the app was started so the runtime can decide whether to restore.
The original is part of [SDL](https://github.com/libsdl-org/SDL).

**The XA filter tables** in `tools/parche_xa_zigzag.py` — 7 × 29 coefficients — are the CD
controller's own interpolation filter as documented in [psx-spx](https://psx-spx.consoledev.net)
("CDROM XA Audio ADPCM Compression"). They are a description of the hardware, not anyone's code,
and the script checks them (DC gain, symmetry) before it writes anything.

**There are no screenshots here at all.** A screenshot of this running would be mostly Capcom's
artwork, and it would be showing their work rather than this one.

## Takedown and contact

If you hold rights in this material and want something here removed or changed, write to
**jajdpmail@gmail.com**, saying what you object to and in what capacity you are writing.

Requests from rights holders are honoured: the disputed part is removed, or the repository is
taken down, without argument, and you will get a reply confirming it. No notice or legal
process beyond that email is needed to reach the person who maintains this.
