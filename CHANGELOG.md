# Changelog

All notable changes to this repository. Dates are `YYYY-MM-DD`.

The versions here are **the repository's**, not the package's. The package version is whatever you
pass to `construir-uwp.ps1 -Version`, and it has to go up on every package you install, because the
console will not replace a package with one of the same version.

## [1.0.1] — 2026-10-13

### Fixed

- **The `.ps1` files now carry a UTF-8 BOM, because without it PowerShell 5.1 will not parse them.**
  The guide says the PowerShell that ships with Windows is enough — and it is, except that a script
  saved as UTF-8 *without* a BOM is read by 5.1 using the system ANSI code page. Every accented
  character becomes two bytes and, as soon as one lands inside a string, the closing quote stops
  closing: the parser swallows on to the next quote and dies with an `Unexpected token` pointing at
  an unrelated line. `tools/construir-uwp.ps1` failed outright this way; the other two parsed by
  luck. PowerShell 7 assumes UTF-8 and never notices, which is why it went unseen.

## [1.0.0] — 2026-10-13

First publication. The recipe for the UWP port, as it was applied to the build that runs on a real
Xbox Series: 16:9 at 60 FPS, an on-screen FPS counter, and coming back where you left it after the
console terminates the game.

### Added

- **Thirteen guarded patches**, orchestrated by `tools/apply_uwp.py`, each one idempotent,
  all-or-nothing and atomic: the XA resampler, the static-overlay validation, `CreateFileA` in UWP,
  the overlay generator, loading a save state, resuming after termination (runtime and UWP halves),
  the FPS counter and its **R3** toggle, the GPU's debug rings, the per-second phase shares, and the
  fast rasteriser with the wide pass on a worker thread.
- **`src/SDL_winrt_main_NonXAML.cpp`** — the WinRT entry point: joins the split disc on first boot,
  keeps **B** from closing the game, and records why the app was started.
- **`tools/construir-uwp.ps1`** — builds SDL2 for WindowsStore, configures the game for
  `WindowsStore`, and has MSBuild package and sign it. Everything it needs comes in by parameter:
  the tree, the version, your certificate's thumbprint, your tiles.
- **The overlay tooling** — `captura_variantes.ps1`, `capturas_variantes.py`, `capturas_consola.py`
  and `overlays_estaticos.ps1`: how to get the code the game loads from the disc compiled into the
  package, which is the single biggest performance win here.
- **`tools/partir_disco.py`** — the disc in 150 MiB parts, because the Device Portal answers 500 to
  the whole thing.
- **Documentation in both languages**: a build-and-install guide that says which terminal each
  command goes in, whether administrator is needed (it is not, and in one step it breaks things),
  and how the console has to be set up — including that **with no profile signed in the console will
  not launch apps**, which is the kind of thing that costs an afternoon. Plus `HOW-IT-WORKS`, with
  every failure that had to be solved, how it was measured and what the log said.
- **`NOTICE`** — what is and is not here, exactly: 117 lines of the framework quoted across 48
  anchors, zero lines of the game project (it has no license), the public-domain SDL entry point,
  and the XA filter tables from psx-spx. And how to ask for a takedown.

### Not included, on purpose

- The disc, the BIOS, the built executable, the `.msix`, the saves and the package tiles.
- **The compiled overlays and their captures**: they are game code read off your own disc. The tools
  are here; the result is not, and `.gitignore` blocks it by name.
- The fatal-error report and the measuring scaffolding (the per-second probe and the bisection
  scripts) that produced the numbers in `HOW-IT-WORKS`: they were development tools, not part of the
  port.
