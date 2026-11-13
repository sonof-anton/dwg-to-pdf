# DWG to PDF

Plots every `.dwg` in a folder and merges them into **one PDF**, one page per drawing, in file-name order, with a bookmark per drawing.

It drives AutoCAD's background plotter (`accoreconsole.exe`), so the output looks like a normal AutoCAD plot. Your DWG files are never opened directly: each one is copied to a temp folder first.

## Requirements

- Windows with **AutoCAD or AutoCAD LT 2024+** installed (DWG TrueView alone isn't enough, because its plotter can't run LISP)
- **Python 3** (with tkinter, which the python.org installer includes)

## Install

```powershell
git clone https://github.com/sonof-anton/dwg-to-pdf.git
cd dwg-to-pdf
powershell -ExecutionPolicy Bypass -File install.ps1
```

This installs `pypdf` and adds **DWG to PDF** shortcuts to the Desktop, the Start menu and the right-click **Send to** menu.

## Use

- **Window:** open *DWG to PDF*, pick the folder, then click **Make PDF**. By default it saves `<folder name> - All Drawings.pdf` inside that folder.
- **Right-click:** right-click a folder, choose **Send to › DWG to PDF**, and the window opens with that folder filled in.
- **Command line:**
  ```
  python dwg_to_pdf.py "C:\path\to\drawings" --run [--color] [--paper "ANSI full bleed D (34.00 x 22.00 Inches)"] [--out file.pdf] [--recurse]
  ```

### Options

| Option | Default | Notes |
|---|---|---|
| Sheet size | AUTO | Picks the smallest ANSI/ARCH sheet the drawing's extents fit on (title blocks drawn 1:1 in inches). Anything else falls back to ARCH D. Drawings are always scaled to fit. |
| Color | off | Off uses `monochrome.ctb`; on plots in color with no plot style table. |
| Include subfolders | off | |

## How it works

1. Each DWG is copied to a temp folder.
2. `accoreconsole.exe` opens the copy and runs a script that contains the routine from `d2p.lsp`. The routine measures the drawing's extents, picks a sheet, and runs `-PLOT` (model space → Extents → Fit → *DWG To PDF.pc3*), then `QUIT`.
3. `pypdf` merges the single-page PDFs.

Notes for changing it:
- `d2p.lsp` is **pasted into the script**, not `(load)`-ed, because AutoCAD's SECURELOAD cancels loading LISP from untrusted folders. Comments and blank lines are stripped when it's pasted in, so don't use `;` inside a string there.
- The script ends with `_.QUIT` / `_Y`. Without that, the core console sits idle after plotting until it's killed. A 120 s timeout is the backstop.
- Only **model space** is plotted. Paper-space layouts aren't, yet.
