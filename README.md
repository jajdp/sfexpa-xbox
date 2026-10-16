# Street Fighter EX Plus Alpha on Xbox — the UWP port

How to take the [plusalpha-recomp](https://github.com/guimaraf/plusalpha-recomp) static recompilation of
*Street Fighter EX Plus α* (PlayStation, 1997, `SLUS-00548`) and run it **on an Xbox Series in Developer
Mode**, as a UWP package you build and sign yourself.

*(Español: [README.es.md](README.es.md))*

It is not a theory: the game boots, plays the Capcom presentation at full speed, reaches the title screen and
plays with a controller, in 16:9, at **60 FPS**, with an on-screen FPS counter, and it comes back where you
left it after the console terminates it.

## What this repository is

**A recipe and the tools that apply it.** The game project already carries a UWP profile — its author wrote
one and never published the package — so this is not a port from scratch: it is everything that profile still
needed to be a game you can play on a console. Thirteen guarded patches, a WinRT entry point, and the build
script. Everything here is applied **to your own checkout** of the game project, on your machine.

## What this repository is **not**

It contains **no game code, no disc image, no BIOS, no built executable, no `.msix` package and no
artwork**. It cannot produce a playable game on its own, and nothing you can download here is a game. You
need your own legally dumped copy of the disc, a retail BIOS, and a working build of the game project
first. See [`NOTICE.md`](NOTICE.md).

The package tiles are **not** in here either: the ones on the real console were made from the game's own
art, which is Capcom's. You supply your own — [`docs/ASSETS.md`](docs/ASSETS.md) lists the exact sizes, and
the build script stops with a clear message if the folder is empty.

Neither are the **compiled overlays**. They are the single biggest piece of this port's performance, and
they are *game code read from your disc*: the tools that produce them are here, the result never is.

## What you need first

| | |
|---|---|
| The game project | [guimaraf/plusalpha-recomp](https://github.com/guimaraf/plusalpha-recomp) on its [psxrecomp](https://github.com/guimaraf/psxrecomp-plusalpha) fork, cloned with `--recurse-submodules`, **building and running on your PC first** |
| Your own disc | An NTSC-U dump of `SLUS-00548`, plus a **retail SCPH-1001 BIOS** — this game refuses to boot without it |
| Visual Studio | 2022, with the C++ tools **and the C++ UWP component**: here MSBuild is what packages and signs, so the UWP workload is genuinely needed. The generator is pinned to `Visual Studio 17 2022` in one line of [`tools/construir-uwp.ps1`](tools/construir-uwp.ps1) |
| PowerShell | The one Windows already ships: **PowerShell 7 is not needed**. The commands carry `-ExecutionPolicy Bypass` because a stock Windows will not run a `.ps1` without it |
| Python 3 | For the patches. Nothing but the standard library |
| An Xbox in Developer Mode | And a certificate to sign with — a self-signed one is fine ([`docs/INSTALL.md`](docs/INSTALL.md) §5) |
| For the overlays only | MSYS2 with `gcc`, and the framework's own recompiler built once ([`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md)) |

SDL2 2.30.2 is downloaded and built for you: SDL3 has no WinRT backend, so 2.30.2 is what this works with.

## How it goes

Two commands. [`docs/INSTALL.md`](docs/INSTALL.md) §0 covers the terminal at more length, and the rest of
that guide is the long version of these two lines.

> **Where to type this:** in **PowerShell** — press the **Windows** key, type `powershell` and
> press **Enter** — in an **ordinary** window: you do not need "run as administrator", and using it
> would break the signing step, because the certificate lives in the store of whoever runs the
> command. From this repository's folder.

```powershell
# 1. patch your checkout of the game project (idempotent, atomic, nothing is deleted)
python tools\apply_uwp.py <path-to-game-project-root>

# 2. build, package and sign (your own tiles, your own certificate)
powershell -ExecutionPolicy Bypass -File tools\construir-uwp.ps1 `
    -Raiz <path-to-game-project-root> -Version 1.0.0.0 -Certificado <your certificate thumbprint>
```

`python tools\apply_uwp.py --list` prints the thirteen steps and what each one solves.

Then install the `.msix` through the Device Portal, upload your disc and BIOS to the app's `LocalState`,
and — if you want the Capcom presentation at full speed — build the overlays. Step by step, including the
console side: **[`docs/INSTALL.md`](docs/INSTALL.md)** ([en español](docs/INSTALL.es.md)).

## What it had to solve

Every one of these was a real failure on the console, and most of them hid the next. The detail, with what
the log said in each case and what was measured, is in
**[`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md)**.

| | Symptom | Fix |
|---|---|---|
| 1 | The disc would not upload: HTTP 500 | Uploads go through `D:\DevelopmentFiles`, which is small and usually full. The disc is split into 150 MiB parts and the entry point joins them on first boot |
| 2 | **B** closed the game | On an Xbox, B is also "back", and SDL hands it to the system unless you ask it not to |
| 3 | The presentation video ran at 0.77x | The video player is not in the game's executable: it is loaded from the disc at run time, and an interpreted overlay does not make it on this CPU. It is compiled **into** the package — in three attempts, because the capture only keeps the last snapshot and the generator picked the wrong bytes for orphan entries |
| 4 | Sakura's stage, and C. Jack's, crawled | The released build compiles 58% of the game's executable; the project's `main` branch compiles 79.2%, and what those stages were interpreting is in the difference |
| 5 | It closed during loading screens | The static-overlay validation cached its verdict forever: the page-generation counters it watched are only bumped by machinery a console does not have |
| 6 | `CreateFileA` truncated a handle | It is desktop-only; in a UWP build MSVC implied an `int` return |
| 7 | `C1128` | 63 000 compiled functions in one object file need `/bigobj` |
| 8 | The music sounded worse than the console | The XA resampler was 2-point linear and restarted every sector. It now does the hardware's own 25-point "zigzag", and the SPU interpolates in cubic |
| 9 | Coming back from Home started over | Developer Mode *terminates* a suspended game. The whole machine is saved when the window goes to the background and restored when the system relaunches it |
| 10 | 54–55 FPS in 16:9 | Three steps: a fast rasteriser path, the GPU's debug rings out of the build, and the wide pass moved to a worker thread — **60 sustained** |
| 11 | No way to know the frame rate | A console has no title bar, which is where the runtime writes it. An on-screen counter, toggled with **R3** |
| 12 | Loading a save state dropped to 0.55x and crashed | Five things the state did not carry; the fifth was ours |
| 13 | The executable had the wrong name | `main` renamed the desktop binary; the manifest and the console expect the old one |

## Credits and license

Port and tooling by **Recompilaciones**. Released under the
[PolyForm Noncommercial License 1.0.0](LICENSE), matching the license of the psxrecomp framework this is a
derivative of.

The patch scripts carry their comments in Spanish, which is where they were written; what they write *into*
the game tree is in English, like the rest of the runtime. The documentation is in both languages.

*Street Fighter EX Plus α* is © Capcom / Arika. This project is not affiliated with them, with Sony, with
Microsoft, or with the authors of the game project or the framework, and it distributes nothing that belongs
to them. The details — exactly what is and is not included here, and how to ask for a takedown — are in
[`NOTICE.md`](NOTICE.md). Rights holders can write to **jajdpmail@gmail.com**.
