# Urbana Image Compressor & Renamer

A desktop app for batch-compressing images and renaming them according to
Urbana's product naming decision tree.

This tool is meant to be run as a standalone executable no Python
installation required for end users. Source code and build instructions
are included below for anyone maintaining or updating the tool.

## Running the App

1. Get `Urbana Image Tool.exe` (or the equivalent build for your OS) from
   wherever it's shared internally.
2. Double-click it to launch — no installation, Python, or setup needed.
3. If Windows SmartScreen or your antivirus flags it on first run, this is
   a common false positive for unsigned PyInstaller executables, not a
   sign anything is wrong. Choose "More info" → "Run anyway" (Windows) or
   allow it in your antivirus if prompted.

## How It Works

1. **Set the batch naming fields** at the top:
   - **Product Group** — Shelters, Toilets, Bridges, Access, Screens, Handrails.
   - **Product Range** — a dropdown for Shelters/Toilets (auto-fills the
     matching **SKU**); a free-text field for the other groups, since no
     range list was defined for them.
   - **Product Details** — same pattern: dropdown for Shelters/Toilets,
     free text otherwise.
   - **Date** is filled automatically (today's date, `yyyy-mm-dd`).
2. Click **Add Images...** and pick one or more JPEG/PNG/WEBP/BMP files.
   Each file's **Render View** (1–16) is auto-detected from a number in its
   original filename (e.g. `shelter_03.jpg` → view 3 → `front-view`).
3. If any file's view couldn't be detected (shown as "not detected"),
   select it in the list and click **Edit View for Selected...** to set it
   manually.
4. Click **Choose Output Folder...**.
5. Adjust the **Quality** slider (lower = smaller file, more compression
   artifacts). Defaults to 90.
6. Click **Compress & Rename**. Every file is compressed and saved as:

   ```
   Urbana-[Group]-[Range]-[SKU]-[Details]-[RenderView]-[yyyy-mm-dd].ext
   ```

   e.g. `Urbana-Shelters-Jarrah-U100-timber skillion-front-view-2026-01-14.jpg`

   Your originals are never modified — new files are written to the output
   folder, and name collisions get a `-2`, `-3`, etc. suffix rather than
   overwriting.
7. When it finishes, the status bar shows total size before/after and
   percentage saved.
8. Click **New Batch** to clear the file list and naming fields and start
   on a different product/batch. (Quality setting and output folder are
   kept, since those tend to stay constant between batches.)

## Building the Executable

For developers updating the tool. Build on the same OS you're targeting —
PyInstaller doesn't cross-compile, so build on Windows for a `.exe`, on
macOS for a Mac app, etc.

1. **Install build dependencies** (in addition to `requirements.txt`):

   ```bash
   pip install pyinstaller
   ```

   If `pip`/`pyinstaller` aren't recognized on Windows, use the Python
   launcher instead: `py -m pip install pyinstaller`, then run PyInstaller
   as `py -m PyInstaller ...` below.

2. **Build**, from the project folder:

   ```bash
   pyinstaller --onefile --windowed --name "Urbana Image Tool" image_compressor.py
   ```

   - `--onefile` bundles everything (Python, Tkinter, Pillow) into a single
     executable.
   - `--windowed` suppresses the console window behind the GUI.
   - `--name` sets the output filename — change this if you rename the app.
   - Optionally add `--icon=assets/icon.ico` (Windows: `.ico`, macOS: `.icns`)
     for a custom app icon.

3. **Find the build output**:
   - `dist/Urbana Image Tool.exe` (or equivalent) — this is the file to
     distribute.
   - `build/` — temporary files, safe to delete.
   - `Urbana Image Tool.spec` — a reusable build config; future builds can
     use `pyinstaller "Urbana Image Tool.spec"` instead of retyping flags.

4. **Test the executable** on a machine without Python installed, if
   possible, to confirm it's truly standalone.

5. **Distribute** the single file from `dist/` — no installer needed.

## Running from Source (for development/testing)

```bash
pip install -r requirements.txt
python image_compressor.py
```

Useful when iterating on the code before cutting a new build, or for
debugging an issue that's easier to reproduce with full error output in
the terminal (the packaged `--windowed` build hides that).

## Notes & Assumptions

- **Render view detection**: the tool takes the *last* number found in each
  filename and maps it (1–16) to a view name. If your render filenames
  include other numbers after the view number (e.g. a version suffix like
  `_v2`), the wrong number may be picked up — use **Edit View for
  Selected...** to correct it.
- **Product Range / Details for groups without a defined list** (Bridges,
  Access, Screens, Handrails): these become free-text fields rather than
  dropdowns, since no sub-lists were specified for them. Update
  `PRODUCT_RANGES` / `PRODUCT_DETAILS` in `image_compressor.py` once those
  lists are defined, then rebuild the executable.
- **Filename separator**: a plain hyphen `-` is used throughout (rather than
  the en dash shown before "Render-View" in the original spec), to keep
  the filename safe and consistent across operating systems.
- Compression runs in a background thread so the window doesn't freeze on
  large batches.
- PNG doesn't support a JPEG-style "quality" setting in Pillow, so the
  quality slider is mapped onto PNG's `compress_level` (0–9) instead —
  PNG compression is lossless either way, so savings will be smaller than
  for JPEG/WEBP.
- Natural next steps: resizing, output format conversion, drag-and-drop,
  and a per-file before/after size column.