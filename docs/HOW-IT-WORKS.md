# How it works, and why each patch is there

*(Español: [HOW-IT-WORKS.es.md](HOW-IT-WORKS.es.md))*

Everything in this repository came out of a specific failure on a real console. This is what it was,
how it was measured, and what fixed it. If you only want to build the thing,
[`INSTALL.md`](INSTALL.md) is enough.

## Where it starts from

The game project **already carries a UWP profile**: its author wrote the `UWP\` folder (manifest,
WinRT entry point, resources and a script for Visual Studio 2019), and the framework it uses has a
"UWP/Xbox" profile in its `runtime.cmake` — no Win32 dialogs, UWP fibers, C11 atomics, logging into
`LocalState`. They never published the package.

So the starting point is a good one: the C of the game's executable and of the BIOS come generated
in the repository, and once configured, compiling takes under a minute. What this repository adds is
everything that was missing between "it compiles" and "it is a game you can play on a console".

On the console the game runs on the runtime's **software renderer**, presented by SDL2 (which on an
Xbox ends up in Direct3D 11), the BIOS in HLE mode with the real one as a fallback, and all its data
in `LocalState\PSXRecomp\SLUS-00548\`.

## The disc will not go up through the Device Portal

Uploading the 528 MB `.bin` gives **HTTP 500**. It is not the spaces and parentheses in the name
(that was tested): the portal's uploads pass through `D:\DevelopmentFiles`, Developer Mode's ~5 GB
partition, which is usually nearly full.

`tools/partir_disco.py` splits it into 150 MiB parts and the UWP entry point joins them on the next
launch, once, recording it in `logs\partes.txt` ("partes: 4 unidas, 528049872 bytes"). The parts
stay behind: they take space, but they are a backup.

## **B** closed the game

On an Xbox, **B** is also "back", and SDL hands it to the system, which closes the app. The entry
point sets `SDL_HINT_WINRT_HANDLE_BACK_BUTTON = 1` and the button goes back to being a game button.

## What the game loads from the disc: overlays

**The symptom.** The Capcom presentation video ran at **0.76–0.83x** (46–48 FPS) for about nine
seconds. On a desktop PC it runs at 1.00x.

**The cause.** The video player's code is not in the game's executable: the game loads it from the
disc at run time, at `0x800D6000…`. That is an **overlay**, and psxrecomp runs it in its
**interpreter** unless it has it compiled. On a PC it compiles it to a DLL on the fly; a console
cannot load those DLLs.

**How it was measured.** A temporary probe wrote, every second, the emulator thread's CPU time,
the time spent emulating, waiting and presenting, the MDEC, the GPU DMA, the interpreted
instructions and the static dispatch hits. During the video: the thread at **99%**, **11.5 million**
interpreted instructions per second (outside the video, under 0.5 million), and one single loop, at
`0x800E78DC`, accounting for 8.7 of those millions. MDEC, SPU and GPU together, under 30 ms per
second: it was not the drawing.

**The fix** is compiling the overlays **into** the executable, from captures of the game's memory.
It took three attempts:

| What it carried | Result on the video |
|---|---|
| One PC capture (90 s), 4 798 functions | 0.77x: static dispatch almost never hit |
| 29 variants captured over 150 s, 11 919 functions | 0.80x: it hit, but the loop was still interpreted |
| The same 29 with the generator patched, 16 059 functions and 174 fragments | **1.00x**, thread at 70–78% |

And it left two traps, which are the reason two of the tools here exist:

- **The capture only keeps the last snapshot.** The runtime rewrites `overlay_captures.json` on
  every trigger and keeps only the latest image of RAM. The player is only in memory while the
  presentation lasts: the snapshot at second 87 already had data at those addresses.
  `tools/captura_variantes.ps1` copies every version while the game runs, and
  `tools/capturas_variantes.py --unir` leaves one entry per variant.
- **The generator picked the wrong bytes.** For "orphan" entries — the ones with no function
  containing them, like the player — `compile_overlays.py --static` compiled a fragment from the
  bytes of the **last** capture that mentioned them. In the snapshots taken after the video, those
  are data, and the fragment never came out: *"STATIC COVERAGE WARNING: 9 captured dispatch entry(s)
  have no compiled body/owner"*. `tools/parche_compile_overlays.py` makes it try every capture and
  keep all the valid fragments: 0 warnings. Each fragment is validated by content when it is
  dispatched, so having several for one address is safe.

## The crash in loading screens

With the overlays compiled, the game started closing by itself during the attract demo, always at
~85 seconds, mid-load, with *"FAIL-FAST unknown dispatch: addr=0x847C3C70 ra=0x80016800"*: a jump to
an address that does not exist.

Since it was deterministic, it was found by **bisection**, building and installing versions carrying
parts of the captures:

| Overlays compiled | In the demo |
|---|---|
| All of them | Crashes |
| None | **Does not crash** |
| Only the video player's region | Does not crash |
| Halves of the 18 variants of `0x80020000` | Crashes with **variant 8** alone |
| Halves of that variant's 85 entries | Crashes with entries `0x8008F0A0` and `0x8008F0E4` |

Variant 8 is that region's image on the **title screen**, and those two entries are interior
fragments of a title-screen function.

**The cause is in the framework.** `psx_overlay_static_code_matches` caches whether a range's bytes
match, and only recomputes the CRC when the sum of its pages' generation counters changes. But those
counters are only bumped on pages marked for watching, and only the DLL loader and sljit mark any:
on a console there is neither, so the sum never changes and **each variant's first verdict stands
forever**. The title screen's fragments kept "matching" after the demo's loading had put different
code at those addresses: title code ran over the demo's, hence the garbage pointer. The other way
round, a variant that did not match the first time it was looked at was never used again, even once
its code was loaded.

`tools/parche_validacion_estatica.py` does two things: the first validation of a static range marks
its pages, so any later write — by the CPU or by the CD's DMA — forces a recheck; and the cache goes
from 4 096 to 131 072 entries, because with the captures of a whole play session each resume wrapper
has its own range, and whatever did not fit was recomputed on every call.

After that, 299 seconds of demo with 12 loads without a single crash. psxrecomp upstream had fixed
the same thing independently; the fork the game uses does not have it.

## A stage that crawled, and it was not the overlays

One particular stage stayed at **0.80x** for the whole fight. The measurement, comparing the slow
seconds with the normal ones of the same session:

| Per second | On that stage | Elsewhere |
|---|---|---|
| Emulation | 907 ms | 755 ms |
| GPU DMA | 133 ms | 57 ms |
| Jumps into uncompiled code | 343 000 | 48 000 |
| Static dispatch hits | 11 360 | 80 013 |
| Validation CRC recomputations | 7 | 1 027 |

The overlays were already compiled and the validation cost nothing. The addresses being interpreted
the most were **not** from the overlays but from the main executable: the C shipped with the
project's released build covers **454 540 of the 782 336 bytes** of its text (**58.1%**), and those
addresses fall in five of the holes. Code that is not compiled is interpreted in blocks of one or
two instructions, and every block is a jump into uncompiled code: 343 000 per second. On a PC you
cannot tell; on the console it cannot keep up.

There are two ways out. One is widening the coverage by hand, with seeds of function entry
addresses: those holes' entries were found (targets of `jal`, `lui`/`addiu` pairs, pointer tables
and prologues) and the fight went to **1.06x** — but other holes showed up on other stages. The
other, which is what this recipe uses, is the project's **`main`** branch, whose C of the executable
goes up to **1 358 functions and 619 384 bytes (79.2%)** and covers those addresses and the other
stages'. With it, a 511-second session with 15 loads had **not one second below 0.95x**.

That is why [`INSTALL.md`](INSTALL.md) §2 says `main` and not the latest release.

## Three small things that stopped the build

- **`CreateFileA`** is desktop-only. The framework's DLL cache sweep uses it to drop a marker, and
  in a UWP build MSVC does not find it declared: it implies an `int` return and truncates the
  64-bit handle. `tools/parche_createfile.py` puts a `fopen` inside an API-family `#if`.
- **`C1128`**: with 63 000 compiled functions, the overlays object exceeds COFF's section limit. It
  needs `/bigobj`, which `construir-uwp.ps1` writes into the `sources.cmake` it generates.
- **The executable's name**: `main` renamed the desktop binary to `exPlusAlpha`, and the manifest
  and the console expect `StreetFighterEXPlusAlphaRecomp.exe`. `apply_uwp.py` puts it back at the
  end of `CMakeLists.txt`, where it wins over the earlier value.

## The sound

The PlayStation version's music is **4-bit XA ADPCM at 37.8 kHz**: it is below the arcade's QSound
to begin with. The recomp made it worse in two ways, and both are fixed:

- **The resampler was 2-point linear and restarted every sector**: the sampling-rate images aliased
  back into the audible band, and every sector left a seam 18.75 times a second.
  `tools/parche_xa_zigzag.py` replaces it with the CD controller's own **25-point "zigzag"**
  interpolation, with its 7 tables of 29 coefficients, and keeps the state across sectors.
- **The SPU picked the nearest sample**: with `spu_hq = true` it interpolates in cubic. The log says
  *"SPU float-shadow enabled"*.

There is still no **reverb**: that is missing from psxrecomp, not from this port.

## Coming back from Home started over

In Developer Mode the console **terminates** a UWP game sent to the background (and any app over
128 MB). Coming back from Home, the system relaunches it, and a relaunch is a fresh start: the game
began from the beginning.

The fix is to save the whole machine **when the window is hidden, minimized or loses focus** — the
app keeps running for a few seconds before it is suspended, and once suspended the WinRT event loop
never returns, so nothing could be saved then — and to restore it when the system relaunches the app
after terminating it. It is two patches, split by where each half lives:

- `tools/parche_reanudar.py`, in the runtime: the suspend slot, the save and the restore, with the
  waits they need (the window is born hidden, and a save triggered alongside a load would run first
  and overwrite it).
- `tools/parche_uwp_reanudar.py`, in the UWP entry point **and in SDL**: whether this is a relaunch
  after a termination (`PreviousExecutionState == Terminated`) only comes with the UWP activation.
  The first version read it with `AppInstance::GetActivatedEventArgs()` before `SDL_main`, and on
  the console that returns **null**: the log said "previous execution state -1" on every launch and
  the saved machine was always discarded. The version here records it **inside SDL**, in the
  activation handler that does get the arguments, and the entry point only overrides it if it gets a
  value.

And before any of that, **loading a save state had to work at all**: it dropped the game to 0.55x
and crashed within seconds with *"DISPATCH FATAL: misaligned target"*. Five things the state did not
carry or did not rebuild on load — among them the boot `pc`, the watched pages' generations, and the
resync of interrupts and of the GTE's timings — and the fifth was this port's: a state loaded before
the runtime considered the game "started" skipped the hook that validates dispatches. That is
`tools/parche_estado_guardado.py`.

## 16:9 at 60 FPS

Widescreen in software cost **54–55 FPS** in fights. The cause: in native-wide mode every primitive
is drawn **twice** — once into the faithful 512-wide VRAM and once into a 682-wide surface — and the
game widens its clip. Three steps, in this order, each one measured:

1. **A fast path in the rasteriser.** The per-pixel calls re-read the draw state — mask bits,
   semi-transparency, texture window, texpage and CLUT — on every pixel, because MSVC cannot keep
   globals in registers across 16-bit stores, and re-checked bounds that the span clipping already
   guarantees. The fast path takes that state once per primitive. **1.8x on the bench, 56–59 FPS**,
   with bit-identical pixels: checked with a bench that draws the same thing with the original and
   with the new one, with the same random operations (5 seeds × 100 000, scale 1 and 2, with and
   without filtering), and all 40 comparisons give the same hash.
2. **The GPU without its debug records.** `gp0_execute_command` logged every command into a
   1 048 576-entry ring (about 120 MB) and every primitive into a 2 097 152-entry census (48 MB,
   with two reads of the game's memory). Both are only read by the debug server, which the console
   build does not carry: there they only cost time and memory on every command.
3. **The wide pass, on another core.** A single-producer single-consumer command ring with the state
   captured, and waits only where they are needed (texture or CLUT read rectangles against VRAM
   writes, and on present, dump or configure). **60 sustained FPS**, with drawing dropping from
   25–30% of the frame to 9–16%, and ~82 000 commands a second going to the thread with 0 waits.

All of that is `tools/parche_raster_hilo.py`, which **starts from the original
`gpu_sw_renderer.c`** and is the last step of `apply_uwp.py` for exactly that reason.

## The FPS counter

A console has no title bar, which is where the runtime writes `[60 fps 1.00x]`. Without it there is
no way to tell whether a drop is real while playing.

`tools/parche_contador_fps.py` draws that same value with SDL rectangles, after the frame is copied
and before it is presented: top left, 3×5 digits over a translucent black box, green at 59 or more,
amber from 55 to 58, red below. It is governed by the same setting as the title bar's,
`[video] show_fps`.

`tools/parche_fps_r3.py` adds **R3** to toggle it without restarting. SELECT would be the natural
button, but training mode already uses it — it resets positions and replays the move — while R3 is
free because the pad is pinned to digital mode, where the DualShock's stick clicks do not exist, so
the game never sees that button. The check sits on player 1's **already combined** button word,
right before it goes to the SIO: placed earlier it missed the most common case, the player with no
device assigned, where the buttons come from the keyboard and from every connected pad at once.

## What is not here

Three things from the development are not published, which is worth knowing so you do not go looking
for them:

- **The fatal-error report** (`crash_trace.c` and its hooks), which wrote the reason for a crash into
  the log and a `psx_last_run_report.json` into `logs\`. It is what made the loading-screen crash
  understandable, but it is diagnostics: the port works without it.
- **The measuring scaffolding**: the per-second probe, the phase profiler and the bisection scripts.
  Every number in this document comes from them. The one member of that family that *is* here is
  `tools/parche_fases.py`, which appends to the log's `[FPS]` line where each second went, because
  that is what helps diagnose a drop on somebody else's console.
- **The compiled overlays and their captures**, which are game code read off your disc
  ([`ASSETS.md`](ASSETS.md) and [`NOTICE.md`](../NOTICE.md)).
