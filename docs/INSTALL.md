# Building the port and getting it onto the console

*(Español: [INSTALL.es.md](INSTALL.es.md))*

Eleven steps. Steps 1 to 5 are done once; from step 7 on, rebuilding the package is two commands.

## 0. Before you start: where the commands go

This guide is full of blocks like the ones below. **They are all commands you type yourself** in a
terminal window, and each one says where from. If you have never used one, this section is
everything you need; if you have, skip it.

### The terminal: PowerShell

Everything here goes in **PowerShell**, the ordinary Windows terminal:

1. Press the **Windows** key.
2. Type `powershell`.
3. Press **Enter** on *Windows PowerShell*.

A window opens with a line ending in `>`. That is where you type the command and press **Enter**.

**Moving to a folder.** Almost every command is typed *from a particular folder*, usually this
repository's. Use `cd` and the path, in quotes if it has spaces:

```powershell
cd "C:\Users\you\Downloads\sfexpa-xbox"
```

**A shortcut that saves mistakes:** open the folder in File Explorer, click the address bar, type
`powershell` over whatever is there and press **Enter**. PowerShell opens already in that folder.

⚠ Some commands are long and split across lines with a **backtick** (`` ` ``) at the end of each.
Copy them whole, backticks included: that is what says "continues on the next line".

### Administrator is not needed — and is better avoided

Nothing in this guide needs "run as administrator". All of it was built and tested from an ordinary
account.

> ⚠ And in one step, being administrator **breaks** it: the certificate in §4 is created in the
> store of whoever runs the command. Create it in an elevated window and it lands in the
> administrator's store, and then MSBuild — running as you — will not find it, and the whole build
> fails at the last step.
>
> The only thing that asks for administrator is the Visual Studio **installer**, which asks by
> itself.

### Why the PowerShell commands carry `-ExecutionPolicy Bypass`

A freshly installed Windows **will not run `.ps1` files**: its policy is `Restricted` and it
answers something like "cannot be loaded because running scripts is disabled". The
`-ExecutionPolicy Bypass` in the examples lifts that **for that one command**, changing nothing on
your system.

**PowerShell 7 (`pwsh`) is not needed** anywhere here. The one Windows ships is enough.

### How to tell whether a command worked

The ones here end by saying what they did, and say so when something goes wrong. A command that
prints nothing usually worked; to confirm, this answers `True` when the previous one ended well:

```powershell
$?
```

---

## 1. What you need first

| | What for |
|---|---|
| **Visual Studio 2022** with the C++ tools **and the C++ UWP component** | Building, packaging and signing. Here MSBuild is what makes the package, so the UWP component is genuinely needed |
| **Python 3** | The patches. Standard library only |
| **Git** | Cloning the game project with its submodules |
| **Your own disc and BIOS** | An NTSC-U dump of `SLUS-00548` (`.bin` + `.cue`) and a **retail SCPH-1001 BIOS**. This game will not boot without it |
| **An Xbox Series in Developer Mode** | Installing the package |
| *For the overlays only (§10)* | **MSYS2** with `gcc`, and the framework's own recompiler built once |

### Which Visual Studio

The generator is pinned in one line of `tools/construir-uwp.ps1`:

```powershell
$Generador = 'Visual Studio 17 2022'
```

With another version of Visual Studio you have to change that line. The path to `cmake.exe` *is*
found for you, with `vswhere -latest`, falling back to whatever `cmake` is on the PATH.

> ⚠ **Newer is not automatically better here.** Microsoft has been winding down UWP support for
> years, and this port leans on C++/CX extensions and on MSBuild's WindowsStore target. If some
> future version drops either, this recipe will not work on it however new it is.

SDL2 does not need installing: `tools/construir-uwp.ps1` downloads 2.30.2 and builds it for
WindowsStore the first time. **SDL3 will not do**: it has no WinRT backend.

---

## 2. The game project

This repository does not carry the game: it carries what to do to it. Clone the project **with its
submodules** (the framework is one of them):

> **Where to type this:** in **PowerShell** — press the **Windows** key, type `powershell` and
> press **Enter** — in an **ordinary** window: you do not need "run as administrator", from
> wherever you want the tree.

```powershell
git clone --recurse-submodules https://github.com/guimaraf/plusalpha-recomp.git C:\sfexpa\plusalpha-recomp
```

About 200 MB: the C of the game's executable comes generated inside the repository.

⚠ **Build it and run it on your PC first**, following the project's own instructions. If it does
not run on the PC it will not run on the console, and you would be debugging two things at once.

**About the version.** This recipe was written and tested against the project's `main` branch,
commit `9e87fa7` (framework `eec0c31`). The patches check what they expect to find before writing,
so if the project moves underneath, the one that does not match stops and says so instead of
corrupting the tree. `main` is deliberate: its C of the executable covers **79.2%** of the game,
where the last released build covers 58%, and Sakura's stage running at full speed is in that
difference ([`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)).

---

## 3. Applying the port

> **Where to type this:** in **PowerShell** — press the **Windows** key, type `powershell` and
> press **Enter** — in an **ordinary** window: you do not need "run as administrator", from this
> repository's folder.

```powershell
python tools\apply_uwp.py C:\sfexpa\plusalpha-recomp
```

It reports each step as it goes: one line per patch, and at the end how many wrote anything.

Three things worth knowing:

- **It is idempotent.** Running it twice changes nothing: each patch leaves its signature inside
  the file and skips itself when it finds it.
- **It is all-or-nothing, per patch.** Every anchor has to appear exactly once. If one does not
  match, that patch writes *nothing* and the process stops there, naming it and how many times it
  found the anchor. Earlier patches stay applied, and running it again after fixing things picks up
  where it stopped.
- **It deletes nothing.** The two patches that need the original leave it beside the file, as
  `<file>.original`.

To see the steps without touching anything:

```powershell
python tools\apply_uwp.py --list
```

---

## 4. A certificate to sign with

Developer Mode accepts self-signed packages. Make one and **note its subject and its thumbprint**:
the manifest's `Publisher` has to match the subject letter for letter.

⚠ This is where not opening the window "as administrator" really matters: the certificate is created
in the store of whoever runs the command, so elevated it would land in the administrator's store and
MSBuild, running as you, would not find it.

> **Where to type this:** in **PowerShell** — press the **Windows** key, type `powershell` and
> press **Enter** — in an **ordinary** window: you do not need "run as administrator", from any
> folder.

```powershell
$c = New-SelfSignedCertificate -Type Custom -Subject "CN=YourName" `
       -KeyUsage DigitalSignature -FriendlyName "UWP signing" `
       -CertStoreLocation "Cert:\CurrentUser\My" `
       -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
$c.Thumbprint     # this is what goes in -Certificado
```

If you lose it, the ones you already have are listed with:

```powershell
Get-ChildItem Cert:\CurrentUser\My | Format-List Subject, Thumbprint
```

---

## 5. The manifest: your identity

`apply_uwp.py` copied `package/Package.appxmanifest` into the tree the first time. **Edit it** — the
one in the repository, so you do not lose it when you run the script again — and change:

```xml
<Identity Name="YOUR-PACKAGE-NAME"
          Publisher="CN=YourName"
          Version="1.0.0.0" />
<mp:PhoneIdentity PhoneProductId="a GUID of your own" ... />
...
<PublisherDisplayName>YourName</PublisherDisplayName>
```

- **`Publisher` has to be the exact subject of your certificate** (§4). If it is not, the build
  runs all the way to the end and fails at signing.
- A fresh GUID comes from `[guid]::NewGuid()` in PowerShell.
- `Version` is set by `construir-uwp.ps1` from its `-Version`; no need to touch it here.

Then run `apply_uwp.py` again to carry it into the tree. The script **does not overwrite** a
manifest that already carries its marker, so your edits in the tree survive; the repository's is
what wins if you delete the tree's.

---

## 6. The package tiles

`package/Assets/` ships **empty on purpose**: the real port's tiles are the game's artwork.
[`ASSETS.md`](ASSETS.md) lists the eleven names and sizes, and has a command that generates plain
ones in a moment. With no PNG in there, the next step stops and tells you.

---

## 7. Build, package and sign

> **Where to type this:** in **PowerShell** — press the **Windows** key, type `powershell` and
> press **Enter** — in an **ordinary** window: you do not need "run as administrator", from this
> repository's folder.

```powershell
powershell -ExecutionPolicy Bypass -File tools\construir-uwp.ps1 `
    -Raiz C:\sfexpa\plusalpha-recomp -Version 1.0.0.0 -Certificado <your thumbprint>
```

It does four things in a row: builds SDL2 for WindowsStore (first time only; a few minutes), puts
the version in the manifest and copies your tiles, configures the game for `WindowsStore` with no
launcher, no debug tools and no Vulkan, and builds the `psx-runtime` target, which MSBuild packages
and signs.

Out comes, in `<root>\paquete-<version>\`:

- `psx-runtime_<version>_x64.msix` — the package,
- `psx-runtime_<version>_x64.cer` — the public half of your certificate,
- `Dependencies\x64\Microsoft.VCLibs.x64.14.00.appx` — the dependency from §8.1, which MSBuild puts
  there for you.

**The disc and the BIOS do not go inside**: they go to the console separately, in §9.

⚠ **Bump the version for every new package.** The console will not change the tiles, or the
contents, of a package whose version matches the installed one.

With the overlays from §10, add `-OverlaysEstaticos <path to overlays_static.c>`.

---

## 8. Installing it on the console

### Before touching anything: how the console has to be

- **In Developer Mode**, with Dev Home installed. If it is not, that is a separate errand with
  Microsoft and this guide does not cover it. - **On, and with your profile signed in.** ⚠ With
  no user signed in the console **will not launch apps**: the package installs, shows up in the
  list, and launching it does nothing. This is one of the most expensive things to work out on
  your own. - **On the same network as your PC.** - **Its address**, which **Dev Home** shows
  on the console itself. The Device Portal listens on port **11443** over HTTPS. - **The
  portal's username and password**: the ones you set in **Dev Home → Remote Access Settings**
  when you turned remote access on.

### 8.1 The dependency: VCLibs

The executable uses the App Container CRT — `msvcp140_app.dll`, `vcruntime140_app.dll`,
`vccorlib140_app.dll` — which is not inside the package but in a **framework package** that has to be
installed **once per console**.

You do not have to go looking for it: MSBuild leaves it at
`<output>\Dependencies\x64\Microsoft.VCLibs.x64.14.00.appx` when it packages (§7). Later packages,
and later versions of this one, find it already installed.

### 8.2 Uploading it

Open `https://<console-ip>:11443` in your PC's browser.

⚠ The browser will warn that **the site's certificate is not trusted**. That is normal and not
a problem: the certificate belongs to the console, which issues it itself. Go in anyway — in
Edge and Chrome, **Advanced** → **Continue to … (unsafe)**; in Firefox, **Advanced** → **Accept
the Risk and Continue**. Then it asks for the portal's username and password (the ones you set
in Dev Home).

Once in, under **My games & apps → Add**:

1. **App package** → your `.msix`.
2. **Certificate** → not needed: the package is signed and Developer Mode accepts it.
3. **Optional packages / Dependency** → this is where `Microsoft.VCLibs.x64.14.00.appx` goes, the
   first time.
4. **Next → Install**, and wait for *Package successfully registered*.

> **The console will not ask you for the certificate you signed with.** In Developer Mode it
> installs any signed package without needing to know the signer: the **Add** screen has no field
> for it. The certificate was needed on your PC, to sign (§4), and that is the end of its job.
>
> If the portal ever did reject the signature, what has to be registered on the console is the
> **public half** of your certificate — the `.cer` that comes out beside the package, or taken from
> it like this:
>
> ```powershell
> (Get-AuthenticodeSignature -LiteralPath "<your .msix>").SignerCertificate |
>     Export-Certificate -FilePath "$env:USERPROFILE\Desktop\signer.cer"
> ```

### 8.3 If it says `There is not enough space on the disk`

The console is not full, and the message is misleading. **The first install of a package family goes
to `D:\DevelopmentFiles`**, a partition of about 5 GB that Developer Mode keeps for exactly that;
*updates* to an already registered family go elsewhere. That partition fills up with the first
version of everything you have ever installed, and **uninstalling a game does not empty it**.

The way out is to get your package in as an **update** rather than a first install, with a *seed*: a
package with the **same identity** — same `Identity Name` and `Publisher` — but a **lower version**
and a minimal executable inside, which never has to run. Install that first (with the VCLibs
dependency) and then the real one, which the portal takes as an update.

### 8.4 The first launch

The first launch **with no data does nothing visible**: it creates the `LocalState` folders and
exits. The log says `CREATE_FOLDERS_SUCCESS`. It is not a failure: it is what has to happen before
you can upload the disc. Upload them (§9) and open it again.

---

## 9. The disc, the BIOS and the configuration

They live in the app's own data folder, the one that first launch created:

```text
…\Packages\<identity>\LocalState\PSXRecomp\SLUS-00548\
    bios\    disc\    config\    saves\    logs\
```

Everything goes up through the Device Portal's **File explorer**, inside this app's `LocalState`:

| What | Where | How |
|---|---|---|
| The **BIOS** | `bios\` | `SCPH1001.BIN` as it is |
| The **disc** | `disc\` | The `.bin` **split**, and the `.cue` renamed to `game.cue` |
| The **configuration** | `config\` | `settings.toml` and `game.toml` |

### The disc, split

The portal answers **500** when you upload the `.bin`'s 528 MB in one go: uploads pass through
`D:\DevelopmentFiles`, which is small. Split it into 150 MiB parts and the port's entry point joins
them once, on the next launch, recording it in `logs\partes.txt`:

> **Where to type this:** in **PowerShell**, in an ordinary window, from this repository's folder.

```powershell
python tools\partir_disco.py "C:\path\to\your\disc.bin" C:\sfexpa\parts
```

Upload the resulting `disc.bin.parte1`, `.parte2`… to `disc\`.

⚠ **The `.cue` has to be named `game.cue`** in `disc\`, and its `FILE` line has to name the `.bin`
by its original name — the file you split, without the `.parteN`. For a single-track dump it ends up
like this:

```text
FILE "Street Fighter EX Plus Alpha (USA).bin" BINARY
  TRACK 01 MODE2/2352
    INDEX 01 00:00:00
```

### The settings

The project already ships a `settings.toml` meant for the console (software renderer, fullscreen, no
launcher, both pads on `auto` and in digital mode). What to add to it to get what this port gives:

| File | Section | Key | What for |
|---|---|---|---|
| `settings.toml` | `[video]` | `aspect_ratio = "16:9"` | Widescreen. The console's copy has no such key: you add it |
| `settings.toml` | `[video]` | `show_fps = true` | The FPS counter on by default (**R3** toggles it) |
| `settings.toml` | `[audio]` | `spu_hq = true` | The SPU interpolates in cubic instead of picking the nearest sample |
| `game.toml` | `[widescreen]` | `gte_game_mode = true` | Recognises fights as 3D from GTE activity. Without it everything comes out 4:3 with bars |
| `game.toml` | `[widescreen]` | `nw_phase_backdrop = true` | Stretches the 2D backdrop so there are no bars at the sides |
| `game.toml` | `[runtime]` | `overlay_cache = false` | On the console it does nothing but write captures every launch. On the PC it is the opposite: it is what §10 needs |

On every launch the port's entry point **seeds** `game.toml` from inside the package and leaves
`settings.toml` alone if it already exists: that one is yours.

Read `logs\debug_log.txt`. On a console it is all you have, and it is where the `[FPS]` line reports
the real frame rate.

---

## 10. The overlays: the presentation at full speed

This is optional and takes a while, but it is the difference between the Capcom presentation running
at **0.77x** and at **1.00x**, and between some stages crawling and not.

The why is in [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md); what to do is:

1. **Capture on the PC.** A test copy of the game on the PC, with `overlay_cache = true` in its
   `game.toml`, writes `overlay_captures.json`. The runtime **rewrites** it on every trigger and
   only keeps the last snapshot of RAM, so each version has to be copied while it runs:

   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\captura_variantes.ps1 `
       -Juego C:\sfexpa\test -Salida C:\sfexpa\captures -Segundos 150
   ```

2. **Merge them**, one entry per variant:

   ```powershell
   python tools\capturas_variantes.py C:\sfexpa\captures --unir C:\sfexpa\captures\merged.json
   ```

3. **Compile them**, with the framework's recompiler already built and a `gcc` from MSYS2:

   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\overlays_estaticos.ps1 `
       -Raiz C:\sfexpa\plusalpha-recomp -Capturas C:\sfexpa\captures\merged.json -Salida C:\sfexpa\overlays-v1
   ```

4. **Build the package with them**, adding to §7:

   ```powershell
   -OverlaysEstaticos C:\sfexpa\overlays-v1\overlays_static.c
   ```

The PC captures only ever see the presentation, the title screen and the attract demo. The code of
the fights and of each stage only shows up **while playing**, and for that you install a build with
`overlay_cache = true`, play, download the numbered captures from `logs\` with the Device Portal's
**File explorer**, and reduce them with `tools/capturas_consola.py`, which keeps one per code
configuration. Then step 3 again.

⚠ The captures and the `overlays_static.c` that comes out of them are **game code read off your
disc**. They are not published, and this repository's `.gitignore` blocks them by name.

---

## 11. Removing it from the console

⚠ **Your saves go with it.** They live inside the package, in its `LocalState`, and disappear with
it. To keep them, download them first from the Device Portal's **File explorer**: they are in
`LocalState\PSXRecomp\SLUS-00548\saves`.

To uninstall, in the Device Portal: **My games & apps**, find the game in the list, and **Remove**.
Nothing on your PC is touched: the `.msix`, the project, your disc and your BIOS stay where they
were.

Reinstalling afterwards starts from scratch, with empty saves. If what you want is to **update**
without losing them, do not uninstall: install a package with a **higher version** on top — the
`-Version` you pass to `construir-uwp.ps1` (§7). The same version replaces nothing.

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| The package installs and launching does nothing | First: is a **profile signed in** on the console? With no user signed in it will not launch apps. Second: the **first launch with no data** only creates the folders and exits (§8.4) |
| `There is not enough space on the disk` | It is not full: it is `D:\DevelopmentFiles` (§8.3) |
| It says a dependency is missing | The VCLibs from §8.1, which is added on the **Add** screen the first time |
| Signing fails at the end of the build | The manifest's `Publisher` is not the exact subject of your certificate (§5), or the certificate was created in an administrator window (§0) |
| The presentation is slow, or a stage crawls | The overlays are missing (§10). They are the biggest single win in this port |
| `C1128` while compiling | The overlays object exceeds COFF's section limit: it needs `/bigobj`, which `construir-uwp.ps1` puts in the `sources.cmake` it writes. If you configure by hand, that option is what you are missing |
| No controller | `settings.toml` has to have both pads on `auto`; the project's copy already does. When it works the log says `opened controller` |
| The game starts over when you come back from Home | That is what happens without `parche_reanudar.py` and `parche_uwp_reanudar.py`: Developer Mode terminates a suspended game. With them, the machine is saved as it goes to the background and restored on relaunch |
| Fights do not reach 60 FPS in 16:9 | `parche_raster_hilo.py` is what recovers that, and it is the last step of `apply_uwp.py`: check that it went in |
| Widescreen shows bars | The `[widescreen]` block is missing from `game.toml` (§9) |
| The music hisses | `parche_xa_zigzag.py` is missing, or `spu_hq = true` in `[audio]` (§9) |
